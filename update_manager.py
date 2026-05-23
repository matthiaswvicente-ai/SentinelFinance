import urllib.request
import json
import threading
from logger import logger

class UpdateManager:
    def __init__(self, current_version="1.0.0", update_url="https://raw.githubusercontent.com/seunome/seu-repo/main/version.json"):
        """
        update_url deve apontar para um arquivo JSON estruturado assim:
        {
          "latest_version": "1.1.0",
          "download_url": "https://link-para-o-novo-exe-ou-site.com",
          "release_notes": "Adicionada função X e correção de Y."
        }
        """
        self.current_version = current_version
        self.update_url = update_url
        self.update_info = None

    def check_for_updates_async(self, callback):
        def _check():
            try:
                # O timeout de 5 segundos garante que o app não trave se não houver internet
                req = urllib.request.Request(self.update_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    if self._is_newer(data.get("latest_version", "0.0.0")):
                        self.update_info = data
                        if callback:
                            callback(data)
            except Exception:
                logger.error("Erro ao verificar atualizações de versão silenciosamente", exc_info=True)
        
        # Roda em background thread para não congelar a UI principal
        threading.Thread(target=_check, daemon=True).start()

    def _is_newer(self, remote_version):
        try:
            def parse_version(v):
                return [int(x) for x in v.replace("v", "").split('.') if x.isdigit()]
            return parse_version(remote_version) > parse_version(self.current_version)
        except Exception:
            return False
