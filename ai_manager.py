import json
import base64
import requests

class AIManager:
    def __init__(self, db):
        self.db = db
        self.provider = self.db.get_preferencia("ia_provider", "API")
        self.api_key = self.db.get_preferencia("ia_api_key", "")
        self.vision_enabled = self.db.get_preferencia("ia_local_vision", "0") == "1"
        self.api_model = self.db.get_preferencia("ia_api_model", "gemini-1.5-flash-latest")
        self.local_model_text = self.db.get_preferencia("ia_local_model_text", "llama3")
        self.local_model_vision = self.db.get_preferencia("ia_local_model_vision", "llava")

    def enviar_mensagem(self, msg, callback=None, abort_event=None):
        context = self._build_system_context()
        if self.provider == "API":
            return self._call_gemini_api(msg, context, callback, abort_event)
        else:
            return self._call_ollama_local(msg, context, callback, abort_event)

    def _build_system_context(self):
        from datetime import datetime
        now = datetime.now()
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        mes_atual = meses[now.month - 1]
        ano_atual = str(now.year)
        
        try:
            resumo = self.db.get_resumo_financeiro(mes_atual, ano_atual, "Eu")
            transacoes = self.db.get_transacoes(mes_atual, ano_atual, "Eu")
            ultimas = transacoes[:30]
            
            contexto = f"Você é um assistente financeiro inteligente do app TG Sentinel.\n"
            contexto += f"Hoje é {now.strftime('%d/%m/%Y')}. Resumo de {mes_atual}/{ano_atual}:\n"
            contexto += f"Receitas (Fixa: {resumo.get('Receita Fixa', 0):.2f}, Variável: {resumo.get('Receita Variável', 0):.2f})\n"
            contexto += f"Despesas (Fixa: {resumo.get('Despesa Fixa', 0):.2f}, Variável: {resumo.get('Despesa Variável', 0):.2f})\n"
            contexto += f"Investimentos: R$ {resumo.get('Investimento', 0):.2f}\n"
            
            if ultimas:
                contexto += "\n(Contexto Oculto - Histórico Recente do Mês):\n"
                for t in ultimas:
                    data, desc, valor, cat = t[1], t[2], t[3], t[4]
                    contexto += f"- {data} | {desc} | R$ {valor:.2f} | {cat}\n"
                    
            contexto += "\nREGRA DE COMPORTAMENTO: Os dados acima são apenas para sua referência invisível. NÃO OS CITE OU RESUMA a menos que o usuário faça uma pergunta específica."
            contexto += "\n\nREGRA DE AÇÃO PARA LANÇAMENTOS (MODO CONTADOR RIGOROSO):"
            contexto += "\nO usuário deseja registrar uma transação. Você age como um contador."
            contexto += "\n1. COLETA: Para lançar, você OBRIGATORIAMENTE precisa de: a) Valor Numérico, b) Descrição, c) Categoria, d) Método de Pagamento (Cartão, Pix, Dinheiro, etc)."
            contexto += "\n2. Se QUALQUER um desses 4 dados faltar na conversa, NÃO GERE JSON! Responda em texto natural fazendo uma pergunta curta para coletar o que falta."
            contexto += "\n3. RESUMO: Se você já tem todos os dados, NÃO GERE JSON AINDA! Responda com um resumo e peça confirmação. Ex: 'Confirme: Descrição: X | Valor: Y | Categoria: Z | Pagamento: W. Posso lançar?'"
            contexto += "\n4. AÇÃO: SOMENTE QUANDO o usuário CONFIRMAR o resumo (ex: 'sim', 'ok', 'pode lançar'), você DEVE retornar APENAS um array JSON válido neste exato formato (sem Markdown):"
            contexto += "\n[{\"acao\": \"adicionar\", \"descricao\": \"...\", \"valor\": 0.00, \"categoria\": \"...\", \"pagamento\": \"...\"}]"
            contexto += "\nNão retorne mais nenhum texto além do JSON nessa etapa final. Dica: observe o Histórico da Conversa para lembrar dos dados já informados."
            if self.provider == "Local":
                contexto += "\n\n=== RECURSO ESPECIAL DE BUSCA PROFUNDA ==="
                contexto += "\nVocê está rodando no modo IA Local e pode pedir ao app para ler o banco de dados."
                contexto += "\nO contexto acima tem apenas os 30 últimos lançamentos do mês atual para economizar tempo."
                contexto += "\nSe o usuário perguntar algo de meses anteriores (ex: 'Quanto gastei em Fevereiro de 2025?'), RETORNE APENAS ESTE COMANDO SECRETO:"
                contexto += "\n[BUSCAR_MES_ANO: MM/AAAA]"
                contexto += "\nExemplo de retorno exato: [BUSCAR_MES_ANO: 02/2025]"
                contexto += "\nNão responda mais nada. O app vai interceptar, buscar os dados e devolver para você."
            return contexto
        except Exception as e:
            return "Você é um assistente financeiro inteligente. Ajude o usuário a gerenciar suas finanças."

    def processar_nota(self, image_path, user_msg=""):
        if self.provider == "API":
            return self._call_gemini_vision(image_path, user_msg)
        else:
            if not self.vision_enabled:
                raise Exception("A leitura local de imagens está desativada nas configurações. (Ative para usar modelos como o Llava)")
            return self._call_ollama_vision(image_path, user_msg)

    def _call_gemini_api(self, text, context, callback, abort_event=None):
        if not self.api_key:
            raise Exception("Chave da API não configurada.")
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.api_model, system_instruction=context)
            if callback:
                response = model.generate_content(text, stream=True)
                for chunk in response:
                    if abort_event and abort_event.is_set():
                        break
                    callback(chunk.text)
                return ""
            else:
                response = model.generate_content(text)
                return response.text
        except Exception as e:
            raise Exception(f"Erro na API Gemini: {str(e)}. (Verifique a internet ou se a biblioteca google-generativeai está instalada no seu Python)")

    def _call_ollama_local(self, text, context, callback, abort_event=None):
        try:
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": self.local_model_text,
                "prompt": text,
                "system": context,
                "stream": bool(callback)
            }
            res = requests.post(url, json=payload, stream=bool(callback), timeout=300)
            if res.status_code == 200:
                if callback:
                    for line in res.iter_lines():
                        if abort_event and abort_event.is_set():
                            break
                        if line:
                            chunk = json.loads(line)
                            callback(chunk.get("response", ""))
                            if chunk.get("done"): break
                    return ""
                else:
                    return res.json().get("response", "")
            else:
                raise Exception(f"Erro {res.status_code}: {res.text}")
        except Exception as e:
            raise Exception(f"Erro ao conectar com Ollama local: {str(e)}. O serviço do Ollama está rodando e o modelo '{self.local_model_text}' está baixado?")

    def _get_vision_prompt(self):
        return """
Você é um assistente financeiro de um aplicativo de controle de gastos. 
Sua tarefa é ler esta nota fiscal/cupom fiscal e extrair os itens comprados.
Você DEVE retornar APENAS um array JSON válido, sem nenhum texto antes ou depois, neste exato formato:
[
  {
    "descricao": "Nome resumido do produto",
    "valor": 10.50,
    "categoria": "Despesa Variável"
  }
]
- O valor deve ser estritamente numérico (float).
- Categoria deve ser sempre uma string. Se souber, insira uma categoria como Mercado, Farmácia, Combustível, etc. Se não souber, deixe a string vazia "".
MUITO IMPORTANTE: Não retorne nenhuma outra palavra, apenas o colchete do JSON iniciando e finalizando a resposta.
"""

    def _call_gemini_vision(self, image_path, user_msg=""):
        if not self.api_key:
            raise Exception("Chave da API não configurada.")
        try:
            import google.generativeai as genai
            import PIL.Image
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.api_model)
            img = PIL.Image.open(image_path)
            
            prompt = self._get_vision_prompt()
            if user_msg:
                prompt = f"Instrução do usuário: {user_msg}\n\n" + prompt
                
            response = model.generate_content([prompt, img])
            return self._parse_json(response.text)
        except Exception as e:
            raise Exception(f"Erro de visão Gemini: {str(e)}")

    def _call_ollama_vision(self, image_path, user_msg=""):
        try:
            import PIL.Image
            from io import BytesIO
            import base64
            import requests

            img = PIL.Image.open(image_path)
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            img.thumbnail((1024, 1024))
            
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            encoded_string = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            prompt = self._get_vision_prompt()
            if user_msg:
                prompt = f"Instrução do usuário: {user_msg}\n\n" + prompt
                
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": self.local_model_vision, 
                "prompt": prompt,
                "images": [encoded_string],
                "stream": False,
                "format": "json"
            }
            res = requests.post(url, json=payload, timeout=300)
            if res.status_code == 200:
                return self._parse_json(res.json().get("response", ""))
            else:
                raise Exception(f"Erro {res.status_code}: {res.text}")
        except Exception as e:
            raise Exception(f"Erro de visão Ollama: {str(e)}. O modelo '{self.local_model_vision}' foi baixado no Ollama?")

    def _parse_json(self, text):
        try:
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())
        except Exception as e:
            raise Exception(f"A resposta da IA não foi um JSON válido. Retorno bruto: {text[:100]}...")
