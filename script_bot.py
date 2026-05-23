import re
import json

class ScriptBot:
    def __init__(self, db):
        self.db = db
        self.state = "IDLE"
        self.data = {}

    def _match_categoria(self, user_text):
        user_cat = user_text.strip()
        if not user_cat:
            return "Diversos", "Despesa Variável"
            
        cats = self.db.get_categorias()
        for c in cats:
            if c[1].lower() == user_cat.lower():
                return c[1], c[2] # Retorna (Nome Correto, Pilar Correto)
        
        # Se não achar exato, procura contido
        for c in cats:
            if user_cat.lower() in c[1].lower():
                return c[1], c[2]
                
        return user_cat.title(), "Despesa Variável" # Fallback

    def processar_mensagem(self, text, historico=None):
        text_lower = text.lower().strip()
        
        if self.state == "IDLE":
            valores = re.findall(r'\b\d+(?:[\.,]\d+)?\b', text_lower)
            if not valores:
                return (
                    "🤖 **Bot de Lançamento Rápido**\n\n"
                    "Para agilizar, você pode digitar tudo de uma vez. Exemplo:\n"
                    "👉 *50 mercado pix*\n"
                    "👉 *120 gasolina cartao*\n\n"
                    "Por favor, me informe pelo menos o **VALOR** da transação para começarmos:"
                )
            
            self.data["valor"] = float(valores[0].replace(',', '.'))
            
            palavras = text_lower.split()
            formas_pagamento_map = {
                "pix": "Pix", "dinheiro": "Dinheiro", 
                "cartão": "Cartão de Crédito", "cartao": "Cartão de Crédito",
                "débito": "Cartão de Débito", "debito": "Cartão de Débito",
                "crédito": "Cartão de Crédito", "credito": "Cartão de Crédito"
            }
            
            pagamento_encontrado = None
            for p in palavras:
                if p in formas_pagamento_map:
                    pagamento_encontrado = formas_pagamento_map[p]
                    break
            
            palavras_originais = text.split()
            desc_words = []
            for w in palavras_originais:
                wl = w.lower()
                if wl not in valores and wl not in formas_pagamento_map:
                    if len(wl) > 2 or wl.isalpha():
                        desc_words.append(w)
            
            desc = " ".join(desc_words)
            self.data["descricao"] = desc.capitalize() if desc else "Nova Transação"
            
            if pagamento_encontrado:
                self.data["pagamento"] = pagamento_encontrado
                self.state = "AWAIT_CAT"
                return f"🤖 Identifiquei o valor R$ {self.data['valor']:.2f}, descrição '{self.data['descricao']}' e pagamento via {self.data['pagamento']}.\n\nQual a CATEGORIA?"
            else:
                self.state = "AWAIT_CAT_PAGAMENTO"
                return f"🤖 Identifiquei o valor R$ {self.data['valor']:.2f} e descrição '{self.data['descricao']}'.\n\nFaltaram 2 coisas:\n1. Qual a CATEGORIA?\n2. Qual o MÉTODO DE PAGAMENTO (Dinheiro, Pix, Cartão)?"
                
        elif self.state == "AWAIT_CAT_PAGAMENTO":
            formas_pagamento_map = {"pix": "Pix", "dinheiro": "Dinheiro", "cartão": "Cartão de Crédito", "cartao": "Cartão de Crédito", "débito": "Cartão de Débito", "debito": "Cartão de Débito", "crédito": "Cartão de Crédito", "credito": "Cartão de Crédito"}
            pag_encontrado = None
            cat_text = text_lower
            for w in text_lower.split():
                if w in formas_pagamento_map:
                    pag_encontrado = formas_pagamento_map[w]
                    cat_text = text_lower.replace(w, "").strip()
                    break
            
            cat_nome, cat_pilar = self._match_categoria(cat_text)
            self.data["categoria"] = cat_nome
            self.data["pilar"] = cat_pilar
            
            if pag_encontrado:
                self.data["pagamento"] = pag_encontrado
            else:
                self.state = "AWAIT_PAGAMENTO_SOLO"
                return f"🤖 Categoria definida: {self.data['categoria']}.\nQual o MÉTODO DE PAGAMENTO (Dinheiro, Pix, Cartão)?"
                
            if "Cartão" in self.data["pagamento"]:
                self.state = "AWAIT_CARTAO"
                return "🤖 Como foi no cartão, informe a BANDEIRA e o número de PARCELAS (ex: Visa 2)."
            else:
                self.state = "CONFIRM"
                return self._build_confirm()

        elif self.state == "AWAIT_CAT":
            cat_nome, cat_pilar = self._match_categoria(text)
            self.data["categoria"] = cat_nome
            self.data["pilar"] = cat_pilar
            
            if "Cartão" in self.data.get("pagamento", ""):
                self.state = "AWAIT_CARTAO"
                return "🤖 Como foi no cartão, informe a BANDEIRA e o número de PARCELAS (ex: Visa 2)."
            elif self.data.get("pagamento"):
                self.state = "CONFIRM"
                return self._build_confirm()
            else:
                self.state = "AWAIT_PAGAMENTO_SOLO"
                return "🤖 Qual o MÉTODO DE PAGAMENTO (Dinheiro, Pix, Cartão)?"
            
        elif self.state == "AWAIT_PAGAMENTO_SOLO":
            self.data["pagamento"] = text.title()
            if "cartão" in text_lower or "cartao" in text_lower:
                self.state = "AWAIT_CARTAO"
                return "🤖 Como foi no cartão, informe a BANDEIRA e o número de PARCELAS (ex: Visa 2)."
            else:
                self.state = "CONFIRM"
                return self._build_confirm()
                
        elif self.state == "AWAIT_CARTAO":
            self.data["bandeira"] = "Indefinida"
            self.data["parcelas"] = 1
            nums = re.findall(r'\b\d+\b', text_lower)
            if nums: 
                self.data["parcelas"] = int(nums[0])
            band = " ".join([w for w in text.split() if w not in nums])
            if band: self.data["bandeira"] = band.title()
            
            self.state = "CONFIRM"
            return self._build_confirm()
            
        elif self.state == "CONFIRM":
            if "sim" in text_lower or "ok" in text_lower or "confirmo" in text_lower or "pode" in text_lower:
                self.state = "IDLE"
                from datetime import datetime
                j = json.dumps([{
                    "acao": "adicionar",
                    "data": datetime.now().strftime("%d/%m/%Y"),
                    "descricao": self.data.get("descricao", "Transação"),
                    "valor": self.data.get("valor", 0.0),
                    "tipo_transacao": self.data.get("pilar", "Despesa Variável"),
                    "categoria": self.data.get("categoria", "Diversos"),
                    "metodo": self.data.get("pagamento", "Dinheiro"),
                    "parcelas": self.data.get("parcelas", 1),
                    "bandeira": self.data.get("bandeira", ""),
                    "dono_cartao": "Eu",
                    "divisao": "Eu",
                    "observacao": "Lançado via Bot Estruturado"
                }])
                self.data = {}
                return j
            else:
                self.state = "IDLE"
                self.data = {}
                return "🤖 Operação cancelada. Quando quiser lançar algo, é só me falar."

    def _build_confirm(self):
        val = self.data.get('valor', 0.0)
        desc = self.data.get('descricao', '')
        cat = self.data.get('categoria', '')
        pilar = self.data.get('pilar', '')
        pag = self.data.get('pagamento', '')
        parc = self.data.get('parcelas', 1)
        
        resumo = (
            "🤖 **Resumo da Operação:**\n"
            f"• Valor: R$ {val:.2f}\n"
            f"• Descrição: {desc}\n"
            f"• Categoria: {cat} ({pilar})\n"
            f"• Pagamento: {pag}\n"
        )
        if "Cartão" in pag:
            band = self.data.get('bandeira', '')
            resumo += f"• Bandeira: {band}\n• Parcelas: {parc}\n"
            
        resumo += "\nDigite **'sim'** para aprovar ou **'não'** para cancelar."
        return resumo
