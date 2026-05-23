import customtkinter as ctk
import tkinter as tk
import datetime
import os
import ctypes
from PIL import Image, ImageTk
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from logger import logger
class NovaTransacaoForm(ctk.CTkFrame):
    def __init__(self, parent, db, app_ui, is_integrated=False, edit_id=None, initial_data=None):
        super().__init__(parent, fg_color="#1e222b", corner_radius=10)
        self.db = db
        self.app_ui = app_ui
        self.fechar_pos_save = True # Padrão para modal
        self.is_integrated = is_integrated
        self.edit_id = edit_id
        self.initial_data = initial_data

        # Variáveis de Estado
        self.var_data = ctk.StringVar(value=datetime.datetime.now().strftime("%d/%m/%Y"))
        self.var_desc = ctk.StringVar()
        self.var_pilar = ctk.StringVar(value="Despesa Fixa")
        self.var_categoria = ctk.StringVar()
        self.var_subcategoria = ctk.StringVar()
        self.var_valor = ctk.StringVar(value="0,00")
        self.var_obs = ctk.StringVar()
        
        # Pagamento
        self.metodos = ["Dinheiro", "Pix", "Cartão"]
        self.var_metodos = {m: tk.BooleanVar(value=False) for m in self.metodos}
        self.var_parcelas = ctk.StringVar(value="1")
        self.var_bandeira = ctk.StringVar(value="Visa")
        self.var_dono_cartao = ctk.StringVar(value="Eu")
        self.var_inicio_pag = ctk.StringVar(value=datetime.datetime.now().strftime("%m/%Y"))
        
        self.var_repetir_meses = ctk.StringVar(value="1 Mês")

        # Compartilhamento
        self.pessoas = self.db.get_perfis() if hasattr(self.db, 'get_perfis') else ["Eu"]
        if "Outro..." not in self.pessoas: self.pessoas.append("Outro...")
        
        self.var_pessoas = {p: tk.BooleanVar(value=(p=="Eu")) for p in self.pessoas}
        self.var_divisao_tipo = ctk.StringVar(value="Igualitária") # Igualitária ou Individual
        self.pessoa_valores = {} # {pessoa: StringVar}

        # Carregar categorias
        self.cats_data = self.db.get_categorias()
        self.categorias_por_pilar = {}
        # Primeiro passo: Criar todos os pais
        for c in self.cats_data:
            if c[3] is None:
                pilar = c[2]
                if pilar not in self.categorias_por_pilar: self.categorias_por_pilar[pilar] = {}
                self.categorias_por_pilar[pilar][c[0]] = {"nome": c[1], "subs": []}
        # Segundo passo: Adicionar os filhos
        for c in self.cats_data:
            if c[3] is not None:
                pilar = c[2]
                if pilar in self.categorias_por_pilar and c[3] in self.categorias_por_pilar[pilar]:
                    self.categorias_por_pilar[pilar][c[3]]["subs"].append((c[0], c[1]))

        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        if self.edit_id:
            self.load_edit_data()
        elif getattr(self, "initial_data", None):
            self.load_initial_data()
        else:
            self.render_step_1()


    def load_initial_data(self):
        t = self.initial_data
        from datetime import datetime
        data_str = t.get("data", datetime.now().strftime("%d/%m/%Y"))
        if data_str.lower() in ["hoje", "today"]: data_str = datetime.now().strftime("%d/%m/%Y")
        self.var_data.set(data_str)
        self.var_desc.set(t.get("descricao", "Nova Transação"))
        self.var_pilar.set(t.get("tipo_transacao", "Despesa Variável"))
        self.var_categoria.set(t.get("categoria", ""))
        self.var_subcategoria.set("Geral")
        self.var_valor.set(f"{float(t.get('valor', 0)):.2f}".replace(".", ","))
        self.var_obs.set(t.get("observacao", ""))
        
        m_ai = t.get("metodo", "Dinheiro")
        for m in self.metodos:
            self.var_metodos[m].set(m.lower() in m_ai.lower())
            
        self.var_parcelas.set(str(t.get("parcelas", 1)))
        self.var_bandeira.set(t.get("bandeira", "Visa"))
        self.var_dono_cartao.set(t.get("dono_cartao", "Eu"))
        
        div_ai = t.get("divisao", "Eu")
        for p in self.pessoas:
            self.var_pessoas[p].set(p.lower() in div_ai.lower())
            
        self.render_step_1()
    def load_edit_data(self):
        t = self.db.get_transacao_by_id(self.edit_id)
        if not t:
            self.render_step_1()
            return
            
        self.var_data.set(t["data"])
        self.var_desc.set(t["descricao"])
        self.var_pilar.set(t["tipo_transacao"])
        
        if t["parent_id"] is None:
            self.var_categoria.set(t["categoria_nome"])
            self.var_subcategoria.set("Geral")
        else:
            parent_nome = next((c[1] for c in self.cats_data if c[0] == t["parent_id"]), "Geral")
            self.var_categoria.set(parent_nome)
            self.var_subcategoria.set(t["categoria_nome"])
            
        self.var_valor.set(f"{t['valor_total']:.2f}".replace(".", ","))
        self.var_obs.set(t["observacao"] or "")
        
        for m in self.metodos:
            self.var_metodos[m].set(m in (t["metodo_pagamento"] or ""))
            
        self.var_parcelas.set(str(t["total_parcelas"]))
        self.var_bandeira.set(t["bandeira_cartao"] or "Visa")
        self.var_dono_cartao.set(t["dono_cartao"] or "Eu")
        
        if t["divisoes"]:
            for p in self.pessoas:
                self.var_pessoas[p].set(p in t["divisoes"])
            ativos = len(t["divisoes"])
            val_total = t["valor_total"]
            is_equal = all(abs(v - (val_total/ativos)) < 0.01 for v in t["divisoes"].values()) if ativos > 0 else True
            
            self.var_divisao_tipo.set("Igualitária" if is_equal else "Individual")
            if not is_equal:
                for p, v in t["divisoes"].items():
                    if p not in self.pessoa_valores: self.pessoa_valores[p] = ctk.StringVar()
                    self.pessoa_valores[p].set(f"{v:.2f}".replace(".", ","))
        else:
            for p in self.pessoas: self.var_pessoas[p].set(p=="Eu")
            self.var_divisao_tipo.set("Igualitária")
            
        self.render_step_1()

    def clean_container(self):
        for w in self.main_container.winfo_children(): w.destroy()

    def render_step_1(self):
        self.clean_container()
        
        header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header.pack(fill="x", pady=10)
        titulo = "EDITAR TRANSAÇÃO" if self.edit_id else "NOVA TRANSAÇÃO"
        ctk.CTkLabel(header, text=titulo, font=ctk.CTkFont(weight="bold", size=18)).pack(side="left", padx=20)
        
        # Ocultar o X no modelo integrado
        if not self.is_integrated:
            ctk.CTkButton(header, text="✕", width=30, fg_color="#F44336", hover_color="#D32F2F", command=self.app_ui.fechar_formulario).pack(side="right", padx=20)
        
        ctk.CTkLabel(self.main_container, text="DADOS BÁSICOS", font=ctk.CTkFont(weight="bold", size=14), text_color="#aaaaaa").pack(pady=5)
        
        f = ctk.CTkFrame(self.main_container, fg_color="transparent")
        # Reduzir padx no modelo integrado para economizar espaço
        f.pack(fill="x", padx=10 if self.is_integrated else 30)
        
        ctk.CTkLabel(f, text="Data:").pack(anchor="w")
        ctk.CTkEntry(f, textvariable=self.var_data).pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(f, text="Descrição / Tag:").pack(anchor="w")
        ctk.CTkEntry(f, textvariable=self.var_desc, placeholder_text="Ex: Compras Supermercado").pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(f, text="Pilar:").pack(anchor="w")
        pilares = ["Receita Fixa", "Receita Variável", "Despesa Fixa", "Despesa Variável", "Investimento"]
        ctk.CTkOptionMenu(f, variable=self.var_pilar, values=pilares, command=self.update_cats).pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(f, text="Categoria:").pack(anchor="w")
        self.opt_cat = ctk.CTkOptionMenu(f, variable=self.var_categoria, values=[""], command=self.update_subs)
        self.opt_cat.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(f, text="Subcategoria:").pack(anchor="w")
        self.opt_sub = ctk.CTkOptionMenu(f, variable=self.var_subcategoria, values=[""])
        self.opt_sub.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(f, text="Observação (curto):").pack(anchor="w")
        ctk.CTkEntry(f, textvariable=self.var_obs, placeholder_text="Ex: Compra do mês no Carrefour").pack(fill="x", pady=(0, 10))
        
        self.update_cats(self.var_pilar.get())
        
        ctk.CTkButton(self.main_container, text="PRÓXIMO ➔", command=self.render_step_2).pack(pady=20)

    def update_cats(self, pilar):
        cats = self.categorias_por_pilar.get(pilar, {})
        nomes = [c["nome"] for c in cats.values()]
        self.opt_cat.configure(values=nomes if nomes else ["Sem Categoria"])
        
        curr = self.var_categoria.get()
        if curr not in nomes and nomes:
            self.var_categoria.set(nomes[0])
            
        self.update_subs(self.var_categoria.get())

    def update_subs(self, cat_nome):
        pilar = self.var_pilar.get()
        cats = self.categorias_por_pilar.get(pilar, {})
        sub_nomes = []
        for c in cats.values():
            if c["nome"] == cat_nome:
                sub_nomes = [s[1] for s in c["subs"]]
                break
        self.opt_sub.configure(values=sub_nomes if sub_nomes else ["Geral"])
        
        curr = self.var_subcategoria.get()
        if curr not in sub_nomes:
            if sub_nomes: self.var_subcategoria.set(sub_nomes[0])
            else: self.var_subcategoria.set("Geral")

    def render_step_2(self):
        pilar = self.var_pilar.get()
        self.clean_container()
        
        ctk.CTkLabel(self.main_container, text="VALORES E PAGAMENTO", font=ctk.CTkFont(weight="bold", size=16)).pack(pady=10)
        
        f = ctk.CTkFrame(self.main_container, fg_color="transparent")
        f.pack(fill="x", padx=10 if getattr(self, 'is_integrated', False) else 30)
        
        ctk.CTkLabel(f, text="Valor Total:").pack(anchor="w")
        ctk.CTkEntry(f, textvariable=self.var_valor, placeholder_text="0,00", font=ctk.CTkFont(size=18, weight="bold")).pack(fill="x", pady=5)
        
        if "Despesa" in pilar:
            ctk.CTkLabel(f, text="Método de Pagamento:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 0))
            for m in self.metodos:
                ctk.CTkCheckBox(f, text=m, variable=self.var_metodos[m], command=self.check_parcelado).pack(anchor="w", pady=2)
            
            self.parcelado_frame = ctk.CTkFrame(self.main_container, fg_color="#222222")
            self.render_parcelado_options()
            
            self.botoes_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
            self.botoes_frame.pack(fill="x", pady=20)
            ctk.CTkButton(self.botoes_frame, text="SALVAR DESPESA", fg_color="#2E7D32", command=self.salvar).pack(pady=(0, 10))
            ctk.CTkButton(self.botoes_frame, text="⟲ VOLTAR", fg_color="transparent", border_width=1, command=self.render_step_1).pack()
        else:
            self.botoes_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
            self.botoes_frame.pack(fill="x", pady=20)
            btn_txt = "SALVAR EDIÇÃO" if self.edit_id else "SALVAR " + pilar.upper()
            ctk.CTkButton(self.botoes_frame, text=btn_txt, fg_color="#2E7D32" if not self.edit_id else "#3b82f6", command=self.salvar).pack(pady=(0, 10))
            if self.edit_id:
                ctk.CTkButton(self.botoes_frame, text="CANCELAR", fg_color="#f43f5e", hover_color="#e11d48", command=self.cancelar_edicao).pack(pady=(0, 10))
            ctk.CTkButton(self.botoes_frame, text="⟲ VOLTAR", fg_color="transparent", border_width=1, command=self.render_step_1).pack()

    def cancelar_edicao(self):
        # Reinicia o formulário sem o edit_id
        self.edit_id = None
        self.var_desc.set("")
        self.var_valor.set("0,00")
        self.var_obs.set("")
        self.render_step_1()

    def check_parcelado(self):
        if self.var_metodos["Cartão"].get():
            self.parcelado_frame.pack(fill="x", padx=10 if self.is_integrated else 20, pady=10, before=self.botoes_frame)
        else:
            self.parcelado_frame.pack_forget()

    def render_parcelado_options(self):
        f = self.parcelado_frame
        for w in f.winfo_children(): w.destroy()
        
        ctk.CTkLabel(f, text="DETALHES DO PARCELAMENTO", font=ctk.CTkFont(size=11, weight="bold")).pack(pady=5)
        
        row1 = ctk.CTkFrame(f, fg_color="transparent")
        row1.pack(fill="x", padx=10)
        ctk.CTkLabel(row1, text="Nº Parcelas:").pack(side="left")
        ctk.CTkEntry(row1, textvariable=self.var_parcelas, width=50).pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="Bandeira:").pack(side="left", padx=(10,0))
        ctk.CTkOptionMenu(row1, variable=self.var_bandeira, values=["Visa", "Master", "Elo", "Itaú", "Outra"], width=90).pack(side="left", padx=5)
        
        row2 = ctk.CTkFrame(f, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(row2, text="Início (MM/AAAA):").pack(side="left")
        ctk.CTkEntry(row2, textvariable=self.var_inicio_pag, width=80).pack(side="left", padx=5)
        
        ctk.CTkLabel(row2, text="No cartão de:").pack(side="left", padx=(5,0))
        ctk.CTkOptionMenu(row2, variable=self.var_dono_cartao, values=self.pessoas, width=80).pack(side="left", padx=5)

        # Divisão Familiar
        ctk.CTkLabel(f, text="COMPARTILHAMENTO", font=ctk.CTkFont(size=11, weight="bold")).pack(pady=(10, 0))
        div_p = ctk.CTkFrame(f, fg_color="transparent")
        div_p.pack(fill="x", padx=10)
        for p in self.pessoas:
            ctk.CTkCheckBox(div_p, text=p, variable=self.var_pessoas[p], command=self.update_divisao_ui).pack(side="left", padx=2)
            
        ctk.CTkOptionMenu(f, variable=self.var_divisao_tipo, values=["Igualitária", "Individual"], command=self.update_divisao_ui).pack(pady=5)
        self.div_ui_container = ctk.CTkFrame(f, fg_color="transparent", height=0)
        self.div_ui_container.pack(fill="x")
        self.update_divisao_ui() # Forçar atualização inicial para ajustar a altura

    def update_divisao_ui(self, *args):
        for w in self.div_ui_container.winfo_children(): w.destroy()
        
        if self.var_pessoas.get("Outro...", tk.BooleanVar()).get():
            f_outro = ctk.CTkFrame(self.div_ui_container, fg_color="transparent")
            f_outro.pack(fill="x", padx=20, pady=(0, 5))
            ctk.CTkLabel(f_outro, text="Nome do novo perfil:").pack(side="left")
            if not hasattr(self, 'var_novo_perfil'): self.var_novo_perfil = ctk.StringVar()
            ctk.CTkEntry(f_outro, textvariable=self.var_novo_perfil, width=150).pack(side="right")

        if self.var_divisao_tipo.get() == "Individual":
            for p in self.pessoas:
                if self.var_pessoas[p].get():
                    row = ctk.CTkFrame(self.div_ui_container, fg_color="transparent")
                    row.pack(fill="x", padx=20, pady=2)
                    label_txt = p if p != "Outro..." else "Novo Perfil"
                    ctk.CTkLabel(row, text=label_txt, width=60).pack(side="left")
                    if p not in self.pessoa_valores: self.pessoa_valores[p] = ctk.StringVar(value="0,00")
                    
                    entry = ctk.CTkEntry(row, textvariable=self.pessoa_valores[p], width=80)
                    entry.pack(side="right")
                    self.pessoa_valores[p].trace_add("write", lambda *args: self.atualizar_label_validacao())

            self.lbl_validacao_divisao = ctk.CTkLabel(self.div_ui_container, text="", font=ctk.CTkFont(weight="bold"))
            self.lbl_validacao_divisao.pack(pady=10)
            if not hasattr(self, '_valor_trace_id'):
                self._valor_trace_id = self.var_valor.trace_add("write", lambda *args: self.atualizar_label_validacao())
            self.atualizar_label_validacao()

    def atualizar_label_validacao(self):
        if not hasattr(self, 'lbl_validacao_divisao') or not self.lbl_validacao_divisao.winfo_exists(): return
        try:
            val_total = float(self.var_valor.get().replace(",", "."))
        except:
            val_total = 0.0
            
        soma = 0.0
        for p in self.pessoas:
            if self.var_pessoas[p].get() and p in self.pessoa_valores:
                try: soma += float(self.pessoa_valores[p].get().replace(",", "."))
                except: pass
                
        diff = val_total - soma
        if abs(diff) < 0.05:
            self.lbl_validacao_divisao.configure(text=f"Status da Divisão: OK! (R$ {soma:.2f} alocados)", text_color="#2E7D32")
        elif diff > 0:
            self.lbl_validacao_divisao.configure(text=f"Falta alocar: R$ {diff:.2f}", text_color="#E65100")
        else:
            self.lbl_validacao_divisao.configure(text=f"Excesso: R$ {abs(diff):.2f}", text_color="#C62828")

    def salvar(self):
        try:
            val_total = float(self.var_valor.get().replace(",", "."))
            if val_total <= 0: raise ValueError
        except:
            return

        # Identificar IDs
        pilar = self.var_pilar.get()
        cat_nome = self.var_categoria.get()
        sub_nome = self.var_subcategoria.get()
        
        # Mapear Categoria ID
        cat_id = None
        for c in self.cats_data:
            if c[1] == sub_nome and c[2] == pilar: # Prioridade subcategoria
                cat_id = c[0]
                break
        if not cat_id:
            for c in self.cats_data:
                if c[1] == cat_nome and c[2] == pilar:
                    cat_id = c[0]
                    break

        metodos_selecionados = [m for m, v in self.var_metodos.items() if v.get()]
        metodo_str = ", ".join(metodos_selecionados) if metodos_selecionados else "Dinheiro"
        
        num_parcelas = int(self.var_parcelas.get()) if self.var_metodos["Cartão"].get() else 1
        
        # Lógica de Divisão
        divisoes = {}
        novo_nome = self.var_novo_perfil.get().strip() if hasattr(self, 'var_novo_perfil') else ""
        
        if self.var_divisao_tipo.get() == "Igualitária":
            ativos = [p for p in self.pessoas if self.var_pessoas[p].get()]
            if ativos:
                val_por_pessoa = val_total / len(ativos)
                for p in ativos:
                    nome_final = novo_nome if p == "Outro..." and novo_nome else p
                    if p == "Outro..." and not novo_nome: nome_final = "Desconhecido"
                    divisoes[nome_final] = val_por_pessoa
        else:
            soma_individual = 0.0
            for p in self.pessoas:
                if self.var_pessoas[p].get() and p in self.pessoa_valores:
                    nome_final = novo_nome if p == "Outro..." and novo_nome else p
                    if p == "Outro..." and not novo_nome: nome_final = "Desconhecido"
                    try: val = float(self.pessoa_valores[p].get().replace(",", "."))
                    except: val = 0.0
                    divisoes[nome_final] = val
                    soma_individual += val
            
            if abs(soma_individual - val_total) > 0.05:
                tk.messagebox.showerror("Erro de Validação", f"A soma das divisões (R$ {soma_individual:.2f}) não bate com o Valor Total (R$ {val_total:.2f}).")
                return

        if self.edit_id:
            sucesso, msg = self.db.atualizar_transacao(
                transacao_id=self.edit_id,
                categoria_id=cat_id, 
                descricao=self.var_desc.get(), 
                data=self.var_data.get(),
                valor_total=val_total,
                tipo_transacao=pilar,
                metodo=metodo_str,
                bandeira=self.var_bandeira.get() if "Cartão" in metodo_str else "",
                dono=self.var_dono_cartao.get() if "Cartão" in metodo_str else "",
                observacao=self.var_obs.get(),
                divisoes=divisoes
            )
        else:
            qtde_meses = int(self.var_repetir_meses.get().split()[0])
            import datetime
            from dateutil.relativedelta import relativedelta
            try: data_base = datetime.datetime.strptime(self.var_data.get(), "%d/%m/%Y")
            except: data_base = datetime.datetime.now()
            
            sucesso = True
            msg = ""
            for i in range(qtde_meses):
                data_lote = (data_base + relativedelta(months=i)).strftime("%d/%m/%Y")
                s, m = self.db.inserir_transacao(
                    conta_id=1, 
                    categoria_id=cat_id, 
                    descricao=self.var_desc.get() if i == 0 else f"{self.var_desc.get()} ({i+1}/{qtde_meses})" if qtde_meses > 1 else self.var_desc.get(), 
                    data_ini=data_lote,
                    valor_total=val_total,
                    tipo_transacao=pilar,
                    metodo=metodo_str,
                    parcelas=num_parcelas,
                    bandeira=self.var_bandeira.get() if "Cartão" in metodo_str else "",
                    dono=self.var_dono_cartao.get() if "Cartão" in metodo_str else "",
                    divisoes=divisoes,
                    observacao=self.var_obs.get()
                )
                if not s:
                    sucesso = False; msg = m; break
        
        if sucesso:
            if self.fechar_pos_save:
                if not getattr(self, "is_integrated", True):
                    self.master.destroy()
                    self.app_ui.refresh_all_widgets()
                else:
                    self.app_ui.fechar_formulario()
            else:
                self.edit_id = None
                self.var_desc.set("")
                self.var_valor.set("0,00")
                self.var_obs.set("")
                if hasattr(self, 'render_step_1'):
                    self.render_step_1()
                
            self.app_ui.after(100, self.app_ui.refresh_all_widgets)
        else:
            tk.messagebox.showerror("Erro", f"Falha ao salvar transação: {msg}")

