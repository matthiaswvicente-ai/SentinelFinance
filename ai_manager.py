import json
import base64
import requests

class AIManager:
    def __init__(self, db):
        self.db = db
        self.provider = self.db.get_preferencia("ia_provider", "API")
        self.api_key = self.db.get_preferencia("ia_api_key", "")
        self.vision_enabled = self.db.get_preferencia("ia_local_vision", "0") == "1"
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
                    
            contexto += "\nREGRA DE COMPORTAMENTO: Os dados acima são apenas para sua referência invisível. NÃO OS CITE OU RESUMA a menos que o usuário faça uma pergunta específica sobre eles. Se o usuário disser apenas 'Oi', responda com um simples cumprimento."
            contexto += "\nREGRA DE AÇÃO: Se o usuário pedir para ADICIONAR ou REGISTRAR um gasto/compra (ex: 'comprei um pão por 10 reais'), você NÃO deve conversar. Você DEVE retornar APENAS um JSON válido neste formato exato (sem Markdown): [{\"acao\": \"adicionar\", \"descricao\": \"Pão\", \"valor\": 10.00, \"categoria\": \"Despesa Variável\"}]. A categoria deve ser uma das suas cadastradas ou deixar genérica."
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
            model = genai.GenerativeModel('gemini-flash-latest', system_instruction=context)
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
            model = genai.GenerativeModel('gemini-flash-latest')
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
