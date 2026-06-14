import urllib.request
import json
import threading
import os
import zipfile
import io
import shutil
import tempfile
from logger import logger

class UpdateManager:
    def __init__(self, current_version="1.1.0", repo="Matthiaswvicente-ai/SentinelFinance"):
        self.current_version = current_version
        self.repo = repo
        self.update_info = None

    def check_for_updates(self):
        """
        Consulta síncrona da API do GitHub para obter a última release.
        Retorna (tem_atualizacao, info_dict) ou (False, None) em caso de erro.
        """
        api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        try:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'SentinelFinance-Updater'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                tag_name = data.get("tag_name", "v1.0.0").replace("v", "")
                
                # Se a tag remota for maior que a versão local
                if self._is_newer(tag_name):
                    info = {
                        "latest_version": tag_name,
                        "download_url": data.get("zipball_url"),
                        "release_notes": data.get("body", "Sem notas de versão."),
                        "is_mock": False
                    }
                    self.update_info = info
                    return True, info
                return False, None
        except Exception as e:
            logger.error(f"Erro ao verificar atualizações no GitHub ({api_url}): {e}")
            # Em caso de erro (404, rate limit, sem internet), fornece o fallback de demonstração
            return self._get_mock_update()

    def _get_mock_update(self):
        """
        Fallback simulado para fins de demonstração (versão Beta).
        Permite testar o fluxo de atualização mesmo se o repositório no GitHub ainda não estiver público.
        """
        mock_version = "1.1.0-beta"
        if self._is_newer(mock_version):
            info = {
                "latest_version": mock_version,
                "download_url": "MOCK_URL",
                "release_notes": (
                    "Notas da versão 1.1.0-beta (Simulação):\n"
                    "- Correção visual dos botões na aba de Banco de Dados\n"
                    "- Correção de integridade na sincronização de layouts\n"
                    "- Ajuste fino do ocultamento da barra de tarefas ao fechar na bandeja\n"
                    "- Novo Contrato Legal e Assistente de Instalação\n"
                    "- Sistema de Atualizações Automáticas integradas com o GitHub"
                ),
                "is_mock": True
            }
            self.update_info = info
            return True, info
        return False, None

    def install_update_async(self, progress_callback, complete_callback, error_callback):
        """
        Inicia o download e instalação da atualização em uma thread separada.
        """
        def _run():
            if not self.update_info:
                error_callback("Nenhuma informação de atualização disponível.")
                return

            try:
                if self.update_info.get("is_mock"):
                    self._simulate_install(progress_callback, complete_callback)
                    return

                url = self.update_info["download_url"]
                if not url:
                    error_callback("URL de download inválida.")
                    return

                progress_callback(0.1, "Iniciando download da nova versão...")
                
                # Download do zip em memória
                req = urllib.request.Request(url, headers={'User-Agent': 'SentinelFinance-Updater'})
                with urllib.request.urlopen(req, timeout=15) as response:
                    zip_data = response.read()
                
                progress_callback(0.4, "Download concluído. Extraindo arquivos...")
                
                # Pasta temporária para descompactação
                temp_dir = tempfile.mkdtemp()
                with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                    z.extractall(temp_dir)
                
                progress_callback(0.7, "Instalando arquivos novos...")
                
                # Identifica a pasta raiz dentro do zipball (geralmente nomeada como usuario-repo-sha/)
                extracted_root = None
                for name in os.listdir(temp_dir):
                    p = os.path.join(temp_dir, name)
                    if os.path.isdir(p):
                        extracted_root = p
                        break

                if not extracted_root:
                    extracted_root = temp_dir

                # Copia os arquivos sobrescrevendo o diretório atual do app, exceto bancos de dados e backups
                current_dir = os.path.dirname(os.path.abspath(__file__))
                for root, dirs, files in os.walk(extracted_root):
                    # Calcula o caminho relativo correspondente no app
                    rel_path = os.path.relpath(root, extracted_root)
                    dest_dir = current_dir if rel_path == "." else os.path.join(current_dir, rel_path)
                    
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir, exist_ok=True)
                        
                    for file in files:
                        # Ignora estritamente bancos de dados sqlite e a pasta de backups
                        if file.endswith(".db") or "backups" in rel_path or "logs" in rel_path:
                            continue
                        
                        src_file = os.path.join(root, file)
                        dest_file = os.path.join(dest_dir, file)
                        
                        try:
                            shutil.copy2(src_file, dest_file)
                        except Exception as copy_err:
                            logger.error(f"Erro ao copiar arquivo {file}: {copy_err}")
                
                # Limpa a pasta temporária
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                progress_callback(1.0, "Instalação concluída com sucesso!")
                complete_callback()
                
            except Exception as e:
                logger.error(f"Erro durante a instalação da atualização: {e}")
                error_callback(str(e))

        threading.Thread(target=_run, daemon=True).start()

    def _simulate_install(self, progress_callback, complete_callback):
        """
        Simula a instalação de arquivos copiando uma cópia fictícia ou simplesmente demonstrando.
        """
        import time
        steps = [
            (0.2, "Baixando arquivos temporários do GitHub..."),
            (0.5, "Descompactando arquivos de atualização..."),
            (0.8, "Instalando novos códigos e interfaces de UI..."),
            (1.0, "Instalação simulada com sucesso!")
        ]
        for val, msg in steps:
            time.sleep(0.8)
            progress_callback(val, msg)
        time.sleep(0.3)
        complete_callback()

    def _is_newer(self, remote_version):
        try:
            def parse_version(v):
                # Limpa tags beta/alpha e separa por pontos
                clean = v.replace("v", "").split("-")[0]
                return [int(x) for x in clean.split('.') if x.isdigit()]
            
            p_remote = parse_version(remote_version)
            p_current = parse_version(self.current_version)
            return p_remote > p_current
        except Exception:
            return False
