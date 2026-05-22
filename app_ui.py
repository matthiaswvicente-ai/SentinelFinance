import customtkinter as ctk
import tkinter as tk
import datetime
import os
import ctypes
from PIL import Image, ImageTk

class NovaTransacaoForm(ctk.CTkFrame):
    def __init__(self, parent, db, app_ui, is_integrated=False, edit_id=None):
        super().__init__(parent, fg_color="#1e222b", corner_radius=10)
        self.db = db
        self.app_ui = app_ui
        self.fechar_pos_save = True # Padrão para modal
        self.is_integrated = is_integrated
        self.edit_id = edit_id

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
        else:
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
            sucesso, msg = self.db.inserir_transacao(
                conta_id=1, 
                categoria_id=cat_id, 
                descricao=self.var_desc.get(), 
                data_ini=self.var_data.get(),
                valor_total=val_total,
                tipo_transacao=pilar,
                metodo=metodo_str,
                parcelas=num_parcelas,
                bandeira=self.var_bandeira.get() if "Cartão" in metodo_str else "",
                dono=self.var_dono_cartao.get() if "Cartão" in metodo_str else "",
                divisoes=divisoes,
                observacao=self.var_obs.get()
            )
        
        if sucesso:
            if self.fechar_pos_save:
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

class DashboardPanel(ctk.CTkFrame):
    def __init__(self, parent, app_ui, default_widget="Vazio", is_fixed=False, compact=False, excluded_widgets=None):
        super().__init__(parent, fg_color="#1e293b", corner_radius=15, border_width=1, border_color="#334155")
        self.app_ui = app_ui
        self.pack_propagate(False)
        self.grid_propagate(False)
        
        self.header_frame = ctk.CTkFrame(self, fg_color="#334155", corner_radius=15, height=40)
        self.header_frame.pack(fill="x", padx=2, pady=2)
        self.header_frame.pack_propagate(False)
        
        todas_opcoes = [
            "Vazio",
            "📊 Gráfico: Composição de Gastos",
            "📊 Gráfico: Composição de Receitas",
            "📊 Gráfico: Top 5 Categorias",
            "📊 Gráfico: Top 5 Subcategorias",
            "📊 Gráfico: Donut",
            "📊 Gráfico: Tipos de Pagamento",
            "📊 Gráfico: Uso de Cartões",
            "📋 Lista: Transações",
            "📋 Lista: Resumo Completo",
            "⚙️ Config: Categorias",
            "📝 Formulário: Novo Lançamento"
        ]
        
        if excluded_widgets:
            self.opcoes_widget = [opt for opt in todas_opcoes if opt not in excluded_widgets]
        else:
            self.opcoes_widget = todas_opcoes
            
        self.var_selecao = ctk.StringVar(value=default_widget)
        
        # Setas de Navegação (Rápida)
        btn_prev = ctk.CTkButton(self.header_frame, text="<", width=25, height=25, corner_radius=6, 
                                 fg_color="transparent", hover_color="#444444", 
                                 command=lambda: self.navegar_widget(-1))
        btn_prev.pack(side="left", padx=(5, 0))

        self.opt_widget = ctk.CTkOptionMenu(self.header_frame, values=self.opcoes_widget, variable=self.var_selecao, 
                                            command=self.mudar_widget, height=28, corner_radius=8, width=240, dynamic_resizing=False)
        self.opt_widget.pack(side="left", padx=5, pady=6)
        
        btn_next = ctk.CTkButton(self.header_frame, text=">", width=25, height=25, corner_radius=6, 
                                 fg_color="transparent", hover_color="#444444", 
                                 command=lambda: self.navegar_widget(1))
        btn_next.pack(side="left", padx=(0, 5))

        self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=2 if (is_fixed or compact) else 10, pady=2 if (is_fixed or compact) else 10)
        
        if is_fixed:
            self.header_frame.pack_forget()
            
        self.mudar_widget(default_widget)
        
    def mudar_widget(self, selecao):
        for w in self.body_frame.winfo_children():
            w.destroy()
            
        if "Transações" in selecao:
            self.app_ui.build_widget_transacoes(self.body_frame)
        elif "Composição de Gastos" in selecao:
            self.app_ui.build_widget_grafico(self.body_frame)
        elif "Composição de Receitas" in selecao:
            self.app_ui.build_widget_receitas(self.body_frame)
        elif "Top 5 Categorias" in selecao:
            self.app_ui.build_widget_top_despesas(self.body_frame)
        elif "Top 5 Subcategorias" in selecao:
            self.app_ui.build_widget_top_subcategorias(self.body_frame)
        elif "Donut" in selecao:
            self.app_ui.build_widget_pizza(self.body_frame)
        elif "Pagamento" in selecao:
            self.app_ui.build_widget_pagamentos(self.body_frame)
        elif "Cartões" in selecao:
            self.app_ui.build_widget_cartoes(self.body_frame)
        elif "Resumo Completo" in selecao:
            self.app_ui.build_widget_resumo_estruturado(self.body_frame, panel=self)
        elif "Categorias" in selecao:
            self.app_ui.build_widget_categorias(self.body_frame)
        elif "Lançamento" in selecao:
            self.app_ui.build_widget_formulario(self.body_frame)
        else:
            ctk.CTkLabel(self.body_frame, text="Painel Vazio", text_color="#aaaaaa").pack(expand=True)

    def navegar_widget(self, direcao):
        try:
            atual = self.opcoes_widget.index(self.var_selecao.get())
            novo = (atual + direcao) % len(self.opcoes_widget)
            self.var_selecao.set(self.opcoes_widget[novo])
            self.mudar_widget(self.opcoes_widget[novo])
        except: pass

    def abrir_detalhe_interno(self, cat_id, cat_nome, is_subperfil=False, is_cartao=False):
        for w in self.body_frame.winfo_children(): w.destroy()
        
        # Header de Detalhe Interno
        header_detalhe = ctk.CTkFrame(self.body_frame, fg_color="#1e222b", height=30)
        header_detalhe.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(header_detalhe, text="❮ Voltar", width=60, height=24, fg_color="#334155", 
                       command=lambda: self.mudar_widget(self.var_selecao.get())).pack(side="left", padx=5)
        
        if is_subperfil:
            ctk.CTkLabel(header_detalhe, text=f"GASTOS DE: {cat_nome.upper()}", font=ctk.CTkFont(weight="bold", size=12)).pack(side="left", padx=10)
            self.app_ui.build_widget_transacoes(self.body_frame, perfil_override=cat_nome, agrupar_por_subcat=True)
        elif is_cartao:
            ctk.CTkLabel(header_detalhe, text=f"USO DO CARTÃO: {cat_nome.upper()}", font=ctk.CTkFont(weight="bold", size=12)).pack(side="left", padx=10)
            self.app_ui.build_widget_transacoes(self.body_frame, cartao_override=cat_nome, agrupar_por_subcat=True)
        else:
            ctk.CTkLabel(header_detalhe, text=cat_nome.upper(), font=ctk.CTkFont(weight="bold", size=12)).pack(side="left", padx=10)
            self.app_ui.build_widget_transacoes(self.body_frame, categoria_id=cat_id)

class AppUI(ctk.CTk):
    def __init__(self, db=None):
        super().__init__()
        self.db = db

        # Forçar o Windows a reconhecer o ícone customizado na barra de tarefas
        try:
            myappid = 'tg.sentinel.finance.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass

        self.title("TG Sentinel")
        self.geometry("1100x800")
        
        # Carregar Logo 1 como ícone da janela (mais estável que a Logo 2 para ícones)
        # Usando after para garantir que o CTk não sobreponha o ícone no startup
        def aplicar_icone_oficial():
            base_path = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base_path, "Logo 1.png")
            if os.path.exists(icon_path):
                try:
                    icon_img = Image.open(icon_path)
                    # Criar versão otimizada
                    icon_res = icon_img.resize((32, 32), Image.LANCZOS)
                    self.icon_photo = ImageTk.PhotoImage(icon_res)
                    self.iconphoto(False, self.icon_photo)
                except Exception as e:
                    print(f"Erro ao aplicar ícone: {e}")
        
        self.after(200, aplicar_icone_oficial)

        try:
            self.state('zoomed') 
        except:
            pass
        ctk.set_appearance_mode("dark")
        # Tema customizado para tons mais modernos
        ctk.set_default_color_theme("blue") 

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # ==================== MENU LATERAL (SIDEBAR) ====================
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color="#111827")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        self.ai_sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color="#1e293b")
        # Será mostrada apenas quando o chat de IA for aberto
        self.grid_columnconfigure(0, minsize=280)
        self.sidebar_frame.grid_propagate(False)
        self.ai_sidebar_frame.grid_propagate(False)
        # Carregar Logo Oficial
        base_path = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_path, "Logo 1.png")
        try:
            pil_img = Image.open(logo_path)
            self.logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(100, 100))
        except:
            self.logo_img = None

        # Container principal da marca (Pure Pack)
        self.brand_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.brand_frame.pack(side="top", fill="x", pady=(15, 10), padx=10)
        
        # Logo Oficial à esquerda
        if self.logo_img:
            self.icon_lbl = ctk.CTkLabel(self.brand_frame, text="", image=self.logo_img)
        else:
            self.icon_lbl = ctk.CTkLabel(self.brand_frame, text="🛡️", font=ctk.CTkFont(size=32))
            
        self.icon_lbl.pack(side="left", padx=(0, 8))
        
        # Container para o texto (Título + Slogan)
        self.text_frame = ctk.CTkFrame(self.brand_frame, fg_color="transparent")
        self.text_frame.pack(side="left", fill="x", expand=True)
        
        self.name_lbl = ctk.CTkLabel(self.text_frame, text="TG SENTINEL", 
                                     font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"), 
                                     text_color="#3a7ebf", anchor="w")
        self.name_lbl.pack(fill="x")
        
        self.slogan_lbl = ctk.CTkLabel(self.text_frame, text="Inteligência financeira\nsob o seu controle", 
                                         font=ctk.CTkFont(family="Segoe UI", size=11), 
                                         text_color="#888888", justify="left", anchor="w")
        self.slogan_lbl.pack(fill="x")
        
        # Variáveis de Estado (Definidas no topo para evitar erros de inicialização)
        self.months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                       "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        now = datetime.datetime.now()
        self.var_mes = ctk.StringVar(value=self.months[now.month-1])
        self.var_ano = ctk.StringVar(value=str(now.year))
        self.var_perfil = ctk.StringVar(value="Eu")
        self.var_view_mode = ctk.StringVar(value="Mensal")
        self.var_layout = ctk.StringVar(value=self.db.get_preferencia("layout_type", "Modelo Integrado"))

        # === SELETOR DE VISÃO ===
        self.seg_view = ctk.CTkSegmentedButton(self.sidebar_frame, values=["Mensal", "Anual"], 
                                               variable=self.var_view_mode, command=lambda _: self.refresh_all_widgets())
        self.seg_view.pack(side="top", fill="x", padx=10, pady=(5, 0))

        self.resumo_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.resumo_frame.pack(side="top", fill="x", padx=10, pady=5)
        
        self.card_saldo = self.create_sidebar_card(self.resumo_frame, "SALDO:", "R$ 0,00", "#3a7ebf")
        self.card_receitas = self.create_sidebar_card(self.resumo_frame, "RECEITAS: ↑", "R$ 0,00", "#4CAF50")
        self.card_despesas = self.create_sidebar_card(self.resumo_frame, "DESPESAS: ↓", "R$ 0,00", "#F44336")
        self.card_investido = self.create_sidebar_card(self.resumo_frame, "VALOR INVESTIDO:", "R$ 0,00", "#9C27B0")

        # === MENU DE NAVEGAÇÃO ===
        self.nav_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.nav_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        def create_nav_btn(text, cmd=None):
            return ctk.CTkButton(self.nav_frame, text=text, 
                                 fg_color="#1e293b", hover_color="#2c313c", 
                                 anchor="w", corner_radius=10, height=36,
                                 # padx não é suportado no construtor do CTkButton
                                 font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                 command=cmd)

        self.btn_investimentos = create_nav_btn("📈 Investimentos")
        self.btn_investimentos.pack(fill="x", pady=2, padx=10)

        self.btn_ia = create_nav_btn("🤖 Assistente IA", self.abrir_chat_ia)
        self.btn_ia.pack(fill="x", pady=2, padx=10)

        self.btn_bot = create_nav_btn("► Bot de Integridade", self.rodar_bot_integridade)
        self.btn_bot.pack(fill="x", pady=2, padx=10)
        
        self.btn_ia_config = create_nav_btn("⚙️ Configurações da IA", self.abrir_config_ia)
        self.btn_ia_config.pack(fill="x", pady=2, padx=10)
        
        # Rodapé da sidebar (Branding + Demo) - pure pack, sem grid
        self.bottom_sidebar = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.bottom_sidebar.pack(side="bottom", fill="x", pady=(0, 10))

        self.lbl_brand = ctk.CTkLabel(self.bottom_sidebar, text="Developed by Taurus Green Studios",
                                      font=ctk.CTkFont(size=9), text_color="#555555")
        self.lbl_brand.pack(pady=(0, 4))

        self.var_demo_mode = ctk.BooleanVar(value=False)
        self.original_db = self.db

        self.sw_demo = ctk.CTkSwitch(self.bottom_sidebar, text="Modo Demonstração 🎭",
                                     variable=self.var_demo_mode,
                                     command=self.toggle_demo_mode,
                                     font=ctk.CTkFont(size=12, weight="bold"),
                                     progress_color="#fbbf24")
        self.sw_demo.pack(padx=10)

        # Linha separadora entre sidebar e dashboard
        tk.Frame(self, bg="#334155", width=2).grid(row=0, column=1, sticky="nsew")
        self.grid_columnconfigure(1, weight=0, minsize=2)

        # ==================== ÁREA CENTRAL (MAIN FRAME) ====================
        self.main_frame = tk.Frame(self, bg="#0f172a")
        self.main_frame.grid(row=0, column=2, sticky="nsew")
        self.grid_columnconfigure(2, weight=1)

        self.header_dash = tk.Frame(self.main_frame, bg="#0f172a")
        self.header_dash.pack(side="top", fill="x", padx=10, pady=(8, 4))
        
        # Configuração de Datas
        title_container = tk.Frame(self.header_dash, bg="#0f172a")
        title_container.pack(side="left")
        
        ctk.CTkLabel(title_container, text="Dashboard", font=ctk.CTkFont(size=24, weight="bold")).pack(side="left")
        
        self.opt_mes = ctk.CTkOptionMenu(title_container, variable=self.var_mes, values=self.months, width=120, height=32, corner_radius=10, command=self.refresh_all_widgets)
        self.opt_mes.pack(side="left", padx=10)
        
        self.year_frame = tk.Frame(title_container, bg="#0f172a")
        self.year_frame.pack(side="left", padx=5)
        self.opt_ano = ctk.CTkOptionMenu(self.year_frame, variable=self.var_ano, values=self.db.get_range_anos(), width=90, height=32, corner_radius=10, command=self.refresh_all_widgets)
        self.opt_ano.pack(side="left")

        self.opt_ano.pack(side="left")

        # Espaçador

        # Espaçador
        tk.Frame(self.header_dash, bg="#0f172a", width=20).pack(side="left", expand=True)

        self.active_panels = []

        # Seletor de Layout
        self.opt_layout = ctk.CTkOptionMenu(self.header_dash, values=["Modelo Integrado", "2 Painéis (1x2)", "3 Painéis (1 Topo, 2 Baixo)", "3 Painéis (3 Lado a Lado)", "4 Painéis (2x2)"],
                                            variable=self.var_layout, command=self.mudar_layout)
        self.opt_layout.pack(side="right")
        ctk.CTkLabel(self.header_dash, text="Layout:").pack(side="right", padx=10)

        self.btn_global_nova = ctk.CTkButton(self.header_dash, text="+ NOVA TRANSAÇÃO",
                                             fg_color="#1f538d", hover_color="#266bb6",
                                             font=ctk.CTkFont(weight="bold"),
                                             command=self.abrir_nova_transacao)
        self.btn_global_nova.pack(side="right", padx=20)

        self.panels_container = tk.Frame(self.main_frame, bg="#0f172a")
        self.panels_container.pack(side="top", fill="both", expand=True, padx=15, pady=(0, 10))

        self.mudar_layout(self.var_layout.get())
        self.limpar_arquivos_temporarios()
        self.after(500, self.atualizar_resumo_sidebar)

    def toggle_demo_mode(self):
        self._is_refreshing = True
        from database import Database
        if self.var_demo_mode.get():
            self.original_db = self.db
            from demo_data import generate_demo_data
            try:
                demo_path = generate_demo_data()
                self.db = Database(demo_path)
                self.sidebar_frame.configure(fg_color="#334155")
                self.main_frame.configure(bg="#1e293b")
                self.panels_container.configure(bg="#1e293b")
                self.header_dash.configure(bg="#1e293b")
            except Exception as e:
                print(f"Erro ao ativar demo: {e}")
                self.var_demo_mode.set(False)
                self._is_refreshing = False
                return
        else:
            self.db = self.original_db
            self.sidebar_frame.configure(fg_color="#111827")
            self.main_frame.configure(bg="#0f172a")
            self.panels_container.configure(bg="#0f172a")
            self.header_dash.configure(bg="#0f172a")
        self.var_perfil.set("Eu")
        self.update_db_references_and_refresh()
        self.after(100, lambda: setattr(self, "_is_refreshing", False))


    def update_db_references_and_refresh(self):
        # Limpar painéis existentes
        for w in self.panels_container.winfo_children():
            w.destroy()
        self.active_panels = []
        
        # Reconstruir layout (isso criará novos painéis com o self.db atualizado)
        self.mudar_layout(self.var_layout.get())
        
        # Atualizar seletores e sidebar
        self.refresh_year_selector()
        self.atualizar_resumo_sidebar()
        self.limpar_arquivos_temporarios()

    def limpar_arquivos_temporarios(self):
        """Remove arquivos de teste que sobraram de sessões anteriores"""
        import os, glob
        for f in glob.glob("integridade_test_*.db"):
            try: os.remove(f)
            except: pass

    def create_sidebar_card(self, parent, title, value, color):
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color="#1e293b", border_width=1, border_color="#334155")
        card.pack(fill="x", pady=4, padx=5)
        
        # Linha Única: Título e Valor
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(6, 0))
        
        ctk.CTkLabel(top_row, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(side="left")
        ctk.CTkLabel(top_row, text=value, font=ctk.CTkFont(size=15, weight="bold")).pack(side="right")
        
        # Barra de progresso logo abaixo
        progress = ctk.CTkProgressBar(card, progress_color=color, height=4, corner_radius=10)
        progress.pack(fill="x", padx=10, pady=(4, 8))
        progress.set(0.1) 
        return card

    def mudar_layout(self, layout_type):
        self.db.set_preferencia("layout_type", layout_type)
        for w in self.panels_container.winfo_children():
            w.destroy()
        self.active_panels = []
            
        if layout_type == "Modelo Integrado":
            if hasattr(self, "btn_global_nova"):
                self.btn_global_nova.pack_forget()
                
            pw_main = tk.PanedWindow(self.panels_container, orient="horizontal", sashwidth=4, bg="#0f172a", bd=0)
            pw_main.pack(fill="both", expand=True)
            
            p_left = DashboardPanel(pw_main, self, "📋 Lista: Resumo Completo", is_fixed=True, compact=True)
            pw_main.add(p_left, stretch="always")
            
            pw_right = tk.PanedWindow(pw_main, orient="vertical", sashwidth=4, bg="#0f172a", bd=0)
            pw_main.add(pw_right, stretch="always")
            
            p_top = DashboardPanel(pw_right, self, "📝 Formulário: Novo Lançamento", is_fixed=True, compact=True)
            p_bot = DashboardPanel(pw_right, self, "📋 Lista: Transações", is_fixed=False, compact=True, excluded_widgets=["Vazio", "📋 Lista: Resumo Completo", "📝 Formulário: Novo Lançamento", "⚙️ Config: Categorias"])
            pw_right.add(p_top, stretch="always")
            pw_right.add(p_bot, stretch="always")
            
            self.active_panels = [p_left, p_top, p_bot]
            
            # Forçar Proporções Exatas (45/55 lateral, 60/40 vertical)
            def set_proportions():
                try:
                    self.update_idletasks()
                    w = pw_main.winfo_width()
                    h = pw_right.winfo_height()
                    if w > 100:
                        pw_main.sash_place(0, int(w * 0.45), 0)
                        pw_right.sash_place(0, 0, int(h * 0.60))
                except: pass
            self.after(500, set_proportions)

        elif layout_type == "2 Painéis (1x2)":
            if hasattr(self, "btn_global_nova") and not self.btn_global_nova.winfo_manager():
                self.btn_global_nova.pack(side="right", padx=20)
            pw = tk.PanedWindow(self.panels_container, orient="horizontal", sashwidth=6, bg="#444444")
            pw.pack(fill="both", expand=True)
            p1 = DashboardPanel(pw, self, "📋 Lista: Transações")
            p2 = DashboardPanel(pw, self, "📊 Gráfico: Composição de Gastos")
            self.active_panels = [p1, p2]
            pw.add(p1, minsize=300)
            pw.add(p2, minsize=300)
            
        elif layout_type == "3 Painéis (1 Topo, 2 Baixo)":
            pw_main = tk.PanedWindow(self.panels_container, orient="vertical", sashwidth=6, bg="#444444")
            pw_main.pack(fill="both", expand=True)
            p_top = DashboardPanel(pw_main, self, "📊 Gráfico: Composição de Gastos")
            pw_main.add(p_top, minsize=200)
            pw_bottom = tk.PanedWindow(pw_main, orient="horizontal", sashwidth=6, bg="#444444")
            pw_main.add(pw_bottom, minsize=200)
            p_bl = DashboardPanel(pw_bottom, self, "📋 Lista: Transações")
            p_br = DashboardPanel(pw_bottom, self, "⚙️ Config: Categorias")
            self.active_panels = [p_top, p_bl, p_br]
            pw_bottom.add(p_bl, minsize=250)
            pw_bottom.add(p_br, minsize=250)
            
        elif layout_type == "3 Painéis (3 Lado a Lado)":
            pw = tk.PanedWindow(self.panels_container, orient="horizontal", sashwidth=6, bg="#444444")
            pw.pack(fill="both", expand=True)
            p1 = DashboardPanel(pw, self, "📋 Lista: Transações")
            p2 = DashboardPanel(pw, self, "📊 Gráfico: Composição de Gastos")
            p3 = DashboardPanel(pw, self, "⚙️ Config: Categorias")
            self.active_panels = [p1, p2, p3]
            pw.add(p1, minsize=200)
            pw.add(p2, minsize=200)
            pw.add(p3, minsize=200)
            
        elif layout_type == "4 Painéis (2x2)":
            # Restaurando PanedWindow para permitir ajuste manual de proporção
            pw_main = tk.PanedWindow(self.panels_container, orient="horizontal", sashwidth=4, bg="#0f172a", bd=0)
            pw_main.pack(fill="both", expand=True)
            
            pw_left = tk.PanedWindow(pw_main, orient="vertical", sashwidth=4, bg="#0f172a", bd=0)
            pw_right = tk.PanedWindow(pw_main, orient="vertical", sashwidth=4, bg="#0f172a", bd=0)
            
            pw_main.add(pw_left)
            pw_main.add(pw_right)
            
            p_tl = DashboardPanel(pw_left, self, "📋 Lista: Transações")
            p_bl = DashboardPanel(pw_left, self, "⚙️ Config: Categorias")
            pw_left.add(p_tl)
            pw_left.add(p_bl)
            
            p_tr = DashboardPanel(pw_right, self, "📊 Gráfico: Composição de Gastos")
            p_br = DashboardPanel(pw_right, self, "📋 Lista: Resumo Completo")
            pw_right.add(p_tr)
            pw_right.add(p_br)
            
            # Forçar proporção ideal (40/60 e 35/65) via sashes
            def set_ideal_proportions():
                try:
                    w = pw_main.winfo_width()
                    h = pw_main.winfo_height()
                    if w > 100: # Garantir que a janela já tenha tamanho
                        pw_main.sash_place(0, int(w * 0.40), 0)
                        pw_left.sash_place(0, 0, int(h * 0.35))
                        pw_right.sash_place(0, 0, int(h * 0.35))
                except: pass
            self.after(200, set_ideal_proportions)
            
            self.active_panels = [p_tl, p_tr, p_bl, p_br]



    def build_widget_formulario(self, parent):
        # NOTA: O NovaTransacaoForm já possui um scroll interno.
        # Portanto, não usamos ScrollableFrame aqui para evitar scroll duplo.
        form = NovaTransacaoForm(parent, self.db, self, is_integrated=True)
        form.pack(fill="both", expand=True, padx=2, pady=2)
        # O formulário interno não deve fechar a janela, mas sim dar refresh
        form.fechar_pos_save = False 

    def deletar_transacao_ui(self, transacao_id):
        import tkinter.messagebox
        if tkinter.messagebox.askyesno("Confirmar", "Deseja excluir permanentemente esta transação?"):
            sucesso, msg = self.db.deletar_transacao(transacao_id)
            if sucesso:
                self.refresh_all_widgets()
            else:
                tkinter.messagebox.showerror("Erro", f"Falha ao excluir: {msg}")

    def abrir_edicao_transacao(self, transacao_id):
        form_panel = None
        for p in self.active_panels:
            if "Lançamento" in p.var_selecao.get():
                form_panel = p
                break
                
        if form_panel:
            for w in form_panel.body_frame.winfo_children(): w.destroy()
            form = NovaTransacaoForm(form_panel.body_frame, self.db, self, is_integrated=True, edit_id=transacao_id)
            form.pack(fill="both", expand=True, padx=2, pady=2)
            form.fechar_pos_save = False
        else:
            top = ctk.CTkToplevel(self)
            top.title("Editar Transação")
            top.geometry("450x700")
            top.attributes("-topmost", True)
            form = NovaTransacaoForm(top, self.db, self, edit_id=transacao_id)
            form.pack(fill="both", expand=True)
            self.current_modal = top

    def build_widget_transacoes(self, parent, categoria_id=None, perfil_override=None, agrupar_por_subcat=False, cartao_override=None):
        mes, ano, perfil = self.var_mes.get(), self.var_ano.get(), perfil_override if perfil_override else self.var_perfil.get()
        
        # OTIMIZAÇÃO: Usa cache se não for um drill-down específico
        if hasattr(self, "_refresh_cache") and self._refresh_cache and categoria_id is None and perfil_override is None and cartao_override is None:
            transacoes = self._refresh_cache["transacoes"]
        else:
            transacoes = self.db.get_transacoes(mes, ano, perfil, categoria_id)
            
        if cartao_override:
            # Filtra apenas as transações feitas com o cartão específico
            transacoes = [t for t in transacoes if t[8] and "Cartão" in t[8] and f"💳 {t[10] or 'Outra'} - 👤 {t[9] or 'N/I'}" == cartao_override]
        
        # Cabeçalho Fixo
        header_frame = ctk.CTkFrame(parent, fg_color="#1e293b", height=35, corner_radius=8)
        header_frame.pack(fill="x", padx=5, pady=(0, 5))
        
        ctk.CTkLabel(header_frame, text="Data", font=ctk.CTkFont(weight="bold", size=11), width=60).pack(side="left", padx=10)
        ctk.CTkLabel(header_frame, text="Descrição e Detalhes", font=ctk.CTkFont(weight="bold", size=11), anchor="w").pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(header_frame, text="Valor", font=ctk.CTkFont(weight="bold", size=11), width=100).pack(side="right", padx=10)
            
        # Lista com Scroll
        scroll_t = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll_t.pack(fill="both", expand=True)
        
        if not transacoes:
            ctk.CTkLabel(scroll_t, text="Nenhuma transação encontrada.", text_color="#64748b").pack(pady=40)
        else:
            # OTIMIZAÇÃO: Limite de 50 itens para manter a fluidez da UI do CustomTkinter
            display_list = transacoes[:50]
            if len(transacoes) > 50:
                ctk.CTkLabel(scroll_t, text=f"⚠️ Exibindo 50 de {len(transacoes)} (Filtre por mês para ver tudo)", 
                             text_color="#fbbf24", font=ctk.CTkFont(size=10)).pack(pady=2)
            
            def render_row(t, parent_container):
                row = ctk.CTkFrame(parent_container, fg_color="#1e222b", corner_radius=10, border_width=1, border_color="#334155")
                row.pack(fill="x", pady=3, padx=2)
                
                # Data e Tipo (Pilar)
                f_left = ctk.CTkFrame(row, fg_color="transparent", width=70)
                f_left.pack(side="left", padx=5, pady=5)
                ctk.CTkLabel(f_left, text=t[1][:5], font=ctk.CTkFont(size=11, weight="bold")).pack()
                tipo_cor = "#4CAF50" if "Receita" in t[5] else "#F44336"
                ctk.CTkLabel(f_left, text=t[5].split()[0], font=ctk.CTkFont(size=8), text_color=tipo_cor).pack()

                # Info Central
                f_mid = ctk.CTkFrame(row, fg_color="transparent")
                f_mid.pack(side="left", fill="both", expand=True, padx=10, pady=5)
                
                # Linha 1: Descrição e Categoria
                txt_desc = f"{t[2]} • {t[4]}"
                ctk.CTkLabel(f_mid, text=txt_desc, anchor="w", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
                
                # Linha 2: Tags e Observação
                tags = []
                if t[7] > 1: tags.append(f"📦 Parcela {t[6]}/{t[7]}")
                if t[8]: 
                    if "Cartão" in t[8]:
                        tags.append(f"💳 {t[10] or 'Outra'} - 👤 {t[9] or 'N/I'}")
                    else:
                        tags.append(f"💸 {t[8]}")
                if t[11] > 0: tags.append("👥 Compartilhada")
                
                info_text = " | ".join(tags)
                if t[12]: # Observação
                    info_text += f"\n💬 {t[12]}"
                
                if info_text:
                    ctk.CTkLabel(f_mid, text=info_text, font=ctk.CTkFont(size=10), text_color="#94a3b8", justify="left", anchor="w").pack(anchor="w")
                
                # Ações (Editar/Excluir)
                f_actions = ctk.CTkFrame(row, fg_color="transparent")
                f_actions.pack(side="right", padx=5)
                
                btn_del = ctk.CTkButton(f_actions, text="🗑️", width=25, height=25, corner_radius=6,
                                        fg_color="transparent", hover_color="#f43f5e", text_color="#ef4444", 
                                        command=lambda tid=t[0]: self.deletar_transacao_ui(tid))
                btn_del.pack(side="right")
                
                btn_edit = ctk.CTkButton(f_actions, text="✏️", width=25, height=25, corner_radius=6,
                                         fg_color="transparent", hover_color="#3b82f6", text_color="#60a5fa", 
                                         command=lambda tid=t[0]: self.abrir_edicao_transacao(tid))
                btn_edit.pack(side="right", padx=5)
                
                # Valor
                # Se for filtro por cartão, mostra o valor total da compra para bater com a fatura. Caso contrário, valor exibido
                val_mostrar = t[13] if cartao_override else t[3]
                ctk.CTkLabel(row, text=f"R$ {val_mostrar:,.2f}".replace(",", "."), 
                             text_color=tipo_cor, font=ctk.CTkFont(weight="bold", size=13), width=100, anchor="e").pack(side="right", padx=5)

            if agrupar_por_subcat:
                grupos = {}
                for t in display_list:
                    cat_nome = t[4]
                    if cat_nome not in grupos: grupos[cat_nome] = []
                    grupos[cat_nome].append(t)
                
                for cat_nome, itens in grupos.items():
                    ctk.CTkLabel(scroll_t, text=cat_nome.upper(), font=ctk.CTkFont(weight="bold", size=12), text_color="#3a7ebf", anchor="w").pack(fill="x", padx=5, pady=(15, 2))
                    for t in itens:
                        render_row(t, scroll_t)
            else:
                for t in display_list:
                    render_row(t, scroll_t)


    def build_widget_grafico(self, parent):
        chart_container = ctk.CTkFrame(parent, fg_color="transparent")
        chart_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        mes, ano, perfil = self.var_mes.get(), self.var_ano.get(), self.var_perfil.get()
        resumo = self.db.get_resumo_financeiro(mes, ano, perfil)
        
        data = [
            {"label": "Fixa", "val": resumo["Despesa Fixa"], "color": "#f43f5e"},
            {"label": "Var.", "val": resumo["Despesa Variável"], "color": "#fbbf24"},
            {"label": "Inv.", "val": resumo["Investimento"], "color": "#8b5cf6"}
        ]
        
        total = sum(d["val"] for d in data)
        ctk.CTkLabel(chart_container, text=f"COMPOSIÇÃO DE GASTOS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8").pack(pady=(0, 10))
        
        bar_bg = ctk.CTkFrame(chart_container, fg_color="#1e293b", height=32, corner_radius=16, border_width=1, border_color="#334155")
        bar_bg.pack(fill="x", pady=5)
        
        if total > 0:
            curr_x = 0
            for d in data:
                pct = d["val"] / total
                if pct > 0:
                    seg = ctk.CTkFrame(bar_bg, fg_color=d["color"], corner_radius=0)
                    seg.place(relx=curr_x, rely=0, relwidth=pct, relheight=1)
                    if pct > 0.10:
                        ctk.CTkLabel(seg, text=f"{pct*100:.0f}%", text_color="white", font=ctk.CTkFont(size=10, weight="bold")).place(relx=0.5, rely=0.5, anchor="center")
                    curr_x += pct
        else:
            ctk.CTkLabel(bar_bg, text="Sem gastos registrados", text_color="#64748b", font=ctk.CTkFont(size=11)).place(relx=0.5, rely=0.5, anchor="center")

        # Legenda Compacta
        leg = ctk.CTkFrame(chart_container, fg_color="transparent")
        leg.pack(fill="x", pady=10)
        for d in data:
            item = ctk.CTkFrame(leg, fg_color="transparent")
            item.pack(side="left", expand=True)
            ctk.CTkFrame(item, width=10, height=10, fg_color=d["color"], corner_radius=3).pack(side="left", padx=4)
            ctk.CTkLabel(item, text=f"{d['label']}: R$ {d['val']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), font=ctk.CTkFont(size=10)).pack(side="left")

    def build_widget_receitas(self, parent):
        chart_container = ctk.CTkFrame(parent, fg_color="transparent")
        chart_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        mes, ano, perfil = self.var_mes.get(), self.var_ano.get(), self.var_perfil.get()
        resumo = self.db.get_resumo_financeiro(mes, ano, perfil)
        
        data = [
            {"label": "Fixa", "val": resumo["Receita Fixa"], "color": "#22c55e"},
            {"label": "Var.", "val": resumo["Receita Variável"], "color": "#3b82f6"}
        ]
        
        total = sum(d["val"] for d in data)
        ctk.CTkLabel(chart_container, text=f"ORIGEM DAS RECEITAS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8").pack(pady=(0, 10))
        
        bar_bg = ctk.CTkFrame(chart_container, fg_color="#1e293b", height=32, corner_radius=16, border_width=1, border_color="#334155")
        bar_bg.pack(fill="x", pady=5)
        
        if total > 0:
            curr_x = 0
            for d in data:
                pct = d["val"] / total
                if pct > 0:
                    seg = ctk.CTkFrame(bar_bg, fg_color=d["color"], corner_radius=0)
                    seg.place(relx=curr_x, rely=0, relwidth=pct, relheight=1)
                    if pct > 0.10:
                        ctk.CTkLabel(seg, text=f"{pct*100:.0f}%", text_color="white", font=ctk.CTkFont(size=10, weight="bold")).place(relx=0.5, rely=0.5, anchor="center")
                    curr_x += pct
        else:
            ctk.CTkLabel(bar_bg, text="Sem receitas registradas", text_color="#64748b", font=ctk.CTkFont(size=11)).place(relx=0.5, rely=0.5, anchor="center")

        # Legenda Compacta
        leg = ctk.CTkFrame(chart_container, fg_color="transparent")
        leg.pack(fill="x", pady=10)
        for d in data:
            f = ctk.CTkFrame(leg, fg_color="transparent")
            f.pack(side="left", expand=True)
            ctk.CTkFrame(f, width=10, height=10, fg_color=d["color"], corner_radius=3).pack(side="left", padx=4)
            ctk.CTkLabel(f, text=f"{d['label']}: R$ {d['val']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), font=ctk.CTkFont(size=10)).pack(side="left")

    def build_widget_top_despesas(self, parent):
        chart_container = ctk.CTkFrame(parent, fg_color="transparent")
        chart_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        mes, ano, perfil = self.var_mes.get(), self.var_ano.get(), self.var_perfil.get()
        cats, somas_raw = self.db.get_resumo_estruturado(mes, ano, perfil)
        
        # Agregação: Somar filhos nos pais
        somas_agregadas = {}
        for c_id, nome, tipo, p_id in cats:
            if p_id is not None: # É um filho
                val = somas_raw.get(c_id, 0)
                somas_agregadas[p_id] = somas_agregadas.get(p_id, 0) + val
        
        despesas = []
        for c_id, nome, tipo, p_id in cats:
            if p_id is None and "Despesa" in tipo: # É um pai de despesa
                val = somas_agregadas.get(c_id, 0)
                if val > 0: despesas.append({"nome": nome, "val": val})
        
        despesas = sorted(despesas, key=lambda x: x["val"], reverse=True)[:5]
        
        if not despesas:
            ctk.CTkLabel(chart_container, text="Sem categorias no período", text_color="#64748b").pack(expand=True)
            return

        max_v = despesas[0]["val"]
        for d in despesas:
            row = ctk.CTkFrame(chart_container, fg_color="transparent", height=32)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=d["nome"], font=ctk.CTkFont(size=11), width=100, anchor="w").pack(side="left")
            bar_bg = ctk.CTkFrame(row, fg_color="#1e293b", height=10, corner_radius=5)
            bar_bg.pack(side="left", fill="x", expand=True, padx=10)
            pct = d["val"] / max_v
            ctk.CTkFrame(bar_bg, fg_color="#f43f5e", width=1, height=10, corner_radius=5).place(relx=0, rely=0, relwidth=pct, relheight=1)
            ctk.CTkLabel(row, text=f"R$ {d['val']:,.0f}".replace(",", "."), font=ctk.CTkFont(size=11, weight="bold"), width=70, anchor="e").pack(side="right")



    def build_widget_top_subcategorias(self, parent):
        chart_container = ctk.CTkFrame(parent, fg_color="transparent")
        chart_container.pack(fill="both", expand=True, padx=10, pady=10)
        mes, ano, perfil = self.var_mes.get(), self.var_ano.get(), self.var_perfil.get()
        cats, somas = self.db.get_resumo_estruturado(mes, ano, perfil)
        subdespesas = []
        for c_id, nome, tipo, p_id in cats:
            if p_id is not None and "Despesa" in tipo:
                val = somas.get(c_id, 0)
                if val > 0: subdespesas.append({"nome": nome, "val": val})
        subdespesas = sorted(subdespesas, key=lambda x: x["val"], reverse=True)[:5]
        if not subdespesas:
            ctk.CTkLabel(chart_container, text="Sem subcategorias no período", text_color="#64748b").pack(expand=True)
            return
        max_v = subdespesas[0]["val"]
        for d in subdespesas:
            row = ctk.CTkFrame(chart_container, fg_color="transparent", height=35)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=d["nome"], font=ctk.CTkFont(size=11), width=100, anchor="w").pack(side="left")
            bar_bg = ctk.CTkFrame(row, fg_color="#1e293b", height=12, corner_radius=6)
            bar_bg.pack(side="left", fill="x", expand=True, padx=10)
            pct = d["val"] / max_v
            ctk.CTkFrame(bar_bg, fg_color="#fbbf24", width=1, height=12, corner_radius=6).place(relx=0, rely=0, relwidth=pct, relheight=1)
            ctk.CTkLabel(row, text=f"R$ {d['val']:,.0f}".replace(",", "."), font=ctk.CTkFont(size=11, weight="bold"), width=70, anchor="e").pack(side="right")

    def build_widget_pizza(self, parent):
        # Limpar para evitar sobreposição ao alternar o switch
        for w in parent.winfo_children(): w.destroy()
        
        # Controle de estado para exibir receitas
        if not hasattr(self, "var_donut_receitas"):
            self.var_donut_receitas = tk.BooleanVar(value=False)

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(5, 0))
        
        ctk.CTkSwitch(header, text="Incluir Receitas", variable=self.var_donut_receitas, 
                      command=lambda: self.build_widget_pizza(parent), # Refresh próprio
                      font=ctk.CTkFont(size=10), progress_color="#10b981").pack(side="right")

        canvas = tk.Canvas(parent, bg="#1e222b", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=10, pady=5)
        
        mes, ano, perfil = self.var_mes.get(), self.var_ano.get(), self.var_perfil.get()
        resumo = self.db.get_resumo_financeiro(mes, ano, perfil)
        
        data = [
            ("Despesa Fixa", resumo["Despesa Fixa"], "#f43f5e"),
            ("Despesa Variável", resumo["Despesa Variável"], "#fbbf24"),
            ("Investimento", resumo["Investimento"], "#8b5cf6")
        ]
        
        if self.var_donut_receitas.get():
            data.append(("Receita Fixa", resumo["Receita Fixa"], "#10b981"))
            data.append(("Receita Variável", resumo["Receita Variável"], "#3b82f6"))

        total = sum(d[1] for d in data)
        if total == 0:
            ctk.CTkLabel(parent, text="Sem dados para o gráfico", text_color="#64748b").place(relx=0.5, rely=0.5, anchor="center")
            return
        
        # Desenhar Arcos (Posicionamento elevado para evitar cortes)
        start_ang = 90
        center_x, center_y = 90, 80 # Subido um pouco mais para dar espaço ao switch
        radius = 65
        for i, (label, val, color) in enumerate(data):
            if val <= 0: continue
            extent = (val / total) * 359.9
            canvas.create_arc(center_x-radius, center_y-radius, center_x+radius, center_y+radius, start=start_ang, extent=-extent, fill=color, outline=color)
            
            # Legenda lateral
            y_pos = 20 + (i * 30)
            canvas.create_rectangle(190, y_pos, 205, y_pos+15, fill=color, outline="")
            canvas.create_text(215, y_pos+7, text=f"{label} ({val/total*100:.0f}%)", fill="white", font=("Segoe UI", 9, "bold"), anchor="w")
            start_ang -= extent
            
        # Efeito Donut
        inner_r = 30
        canvas.create_oval(center_x-inner_r, center_y-inner_r, center_x+inner_r, center_y+inner_r, fill="#1e222b", outline="")

    def build_widget_pagamentos(self, parent):
        for w in parent.winfo_children(): w.destroy()
        
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=15, pady=15)
        
        mes, ano, perfil = self.var_mes.get(), self.var_ano.get(), self.var_perfil.get()
        trans = self.db.get_transacoes(mes, ano, perfil)
        
        dist = {}
        total_p = 0
        for t in trans:
            # t indices: 3:valor, 8:metodo_pagamento
            metodo = t[8] or "Não Informado"
            valor = t[3]
            dist[metodo] = dist.get(metodo, 0) + valor
            total_p += valor
            
        if not dist or total_p == 0:
            ctk.CTkLabel(container, text="Sem dados de pagamento", text_color="#64748b").place(relx=0.5, rely=0.5, anchor="center")
            return
            
        canvas = tk.Canvas(container, bg="#1e222b", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        
        colors = ['#f43f5e', '#3b82f6', '#10b981', '#fbbf24', '#8b5cf6', '#ef4444', '#f97316', '#14b8a6']
        
        start_ang = 90
        center_x, center_y = 90, 90
        radius = 65
        
        for i, (met, val) in enumerate(sorted(dist.items(), key=lambda x: x[1], reverse=True)):
            color = colors[i % len(colors)]
            extent = (val / total_p) * 359.9
            canvas.create_arc(center_x-radius, center_y-radius, center_x+radius, center_y+radius, start=start_ang, extent=-extent, fill=color, outline=color)
            
            # Legenda lateral
            y_pos = 10 + (i * 25)
            canvas.create_rectangle(190, y_pos, 205, y_pos+15, fill=color, outline="")
            canvas.create_text(215, y_pos+7, text=f"{met} ({val/total_p*100:.0f}%)", fill="white", font=("Segoe UI", 9, "bold"), anchor="w")
            start_ang -= extent
            
        # Efeito Donut
        inner_r = 30
        canvas.create_oval(center_x-inner_r, center_y-inner_r, center_x+inner_r, center_y+inner_r, fill="#1e222b", outline="")

    def build_widget_cartoes(self, parent):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=15, pady=15)
        
        mes, ano, perfil = self.var_mes.get(), self.var_ano.get(), self.var_perfil.get()
        trans = self.db.get_transacoes(mes, ano, perfil)
        
        dist = {}
        total_c = 0
        for t in trans:
            # t indices: 3:valor, 8:metodo, 9:cartao_nome, 10:cartao_bandeira
            if t[8] and "Cartão" in t[8]:
                bandeira = t[10] or "Outra"
                # Exibe Bandeira (Nome do Cartão) e Dono
                label = f"💳 {bandeira} - 👤 {t[9] or 'N/I'}"
                valor = t[13] # Usa o valor_total da compra, e não apenas a cota do usuário
                dist[label] = dist.get(label, 0) + valor
                total_c += valor
                
        if not dist or total_c == 0:
            ctk.CTkLabel(container, text="Sem uso de cartões no período", text_color="#64748b").pack(expand=True)
            return
            
        scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        max_v = max(dist.values())
        for cart, val in sorted(dist.items(), key=lambda x: x[1], reverse=True):
            pct = (val / total_c) * 100
            row = ctk.CTkFrame(scroll, fg_color="transparent", height=35)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=cart, font=ctk.CTkFont(size=11), width=120, anchor="w", wraplength=110).pack(side="left")
            bar_bg = ctk.CTkFrame(row, fg_color="#1e293b", height=10, corner_radius=5)
            bar_bg.pack(side="left", fill="x", expand=True, padx=10)
            
            bar_pct = val / max_v
            ctk.CTkFrame(bar_bg, fg_color="#ec4899", width=1, height=10, corner_radius=5).place(relx=0, rely=0, relwidth=bar_pct, relheight=1)
            
            ctk.CTkLabel(row, text=f"{pct:.0f}% • R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), font=ctk.CTkFont(size=11, weight="bold"), width=110, anchor="e").pack(side="right")

    def build_widget_resumo_estruturado(self, parent, panel=None, subperfil_view=None):
        mes, ano, base_perfil = self.var_mes.get(), self.var_ano.get(), self.var_perfil.get()
        perfil = subperfil_view if subperfil_view else base_perfil
        
        # OTIMIZAÇÃO: Usa cache
        if hasattr(self, "_refresh_cache") and self._refresh_cache and not subperfil_view:
            cats, somas = self._refresh_cache["resumo_estruturado"]
        else:
            cats, somas = self.db.get_resumo_estruturado(mes, ano, perfil)
        pais = [c for c in cats if c[3] is None]
        filhos = [c for c in cats if c[3] is not None]
        resumo_data = {}
        
        if perfil == "Eu" and not subperfil_view:
            tipos = ["Receita Fixa", "Receita Variável", "Despesa Fixa", "Despesa Variável", "Investimento"]
        else:
            tipos = ["Despesa Fixa", "Despesa Variável", "Receita Variável", "Receita Fixa"]
        for t in tipos: resumo_data[t] = {"total": 0, "pais": {}}
        for p in pais:
            p_id, p_nome, p_tipo, _ = p
            if p_tipo not in resumo_data: continue
            p_filhos = [f for f in filhos if f[3] == p_id]
            sub_somas = {}
            total_pai = 0
            for f in p_filhos:
                f_id, f_nome, _, _ = f
                f_total = somas.get(f_id, 0)
                sub_somas[f_id] = {"nome": f_nome, "total": f_total}
                total_pai += f_total
            total_pai += somas.get(p_id, 0)
            resumo_data[p_tipo]["pais"][p_id] = {"nome": p_nome, "total": total_pai, "filhos": sub_somas}
            resumo_data[p_tipo]["total"] += total_pai
        main_wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        main_wrapper.pack(fill="both", expand=True)

        # Empacotar o botão ANTES do scroll para que o Tkinter calcule o layout corretamente
        if self.var_layout.get() == "Modelo Integrado":
            btn_abrir_config = ctk.CTkButton(main_wrapper, text="⚙️ Ajustes de Categorias", 
                                             fg_color="#334155", hover_color="#475569")
            btn_abrir_config.pack(fill="x", pady=(5, 0), side="bottom")

        scroll = ctk.CTkScrollableFrame(main_wrapper, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        all_bodies = [] # Guardar referências para colapsar
        colors = {"Receita Fixa": "#2E7D32", "Receita Variável": "#1976D2", "Despesa Fixa": "#C62828", "Despesa Variável": "#E65100", "Investimento": "#6A1B9A"}
        
        def toggle(frame, btn, label_base, build_func=None):
            if frame.winfo_manager() or frame.winfo_children(): 
                # Extermina fisicamente os filhos para o CustomTkinter parar de somar as alturas deles
                for w in frame.winfo_children(): w.destroy()
                frame.pack_forget()
                btn.configure(text=f"▶ {label_base}")
            else: 
                # Constrói apenas sob demanda
                if build_func: build_func(frame)
                frame.pack(fill="x")
                btn.configure(text=f"▼ {label_base}")

        def build_pilar(parent_frame, p_tipo):
            for p_id, p_info in resumo_data[p_tipo]["pais"].items():
                f_pai_wrapper = ctk.CTkFrame(parent_frame, fg_color="transparent", height=0)
                f_pai_wrapper.pack(fill="x", pady=1)
                
                f_header_pai = ctk.CTkFrame(f_pai_wrapper, fg_color="#2b2b2b", corner_radius=4, height=0)
                f_header_pai.pack(fill="x")
                
                f_body_pai = ctk.CTkFrame(f_pai_wrapper, fg_color="transparent", height=0)
                
                def build_pai(parent_pai, inner_info=p_info):
                    for f_id, f_info in inner_info["filhos"].items():
                        f_filho = ctk.CTkFrame(parent_pai, fg_color="transparent", height=0)
                        f_filho.pack(fill="x")
                        btn_drill = ctk.CTkButton(f_filho, text=f"   └─ {f_info['nome']}", 
                                                   font=ctk.CTkFont(size=11), text_color="#aaaaaa",
                                                   fg_color="transparent", hover_color="#334155", anchor="w",
                                                   command=lambda fid=f_id, fnome=f_info['nome']: panel.abrir_detalhe_interno(fid, fnome) if panel else None)
                        btn_drill.pack(side="left", fill="x", expand=True, padx=(20, 5))
                        ctk.CTkLabel(f_filho, text=f"R$ {f_info['total']:,.2f}".replace(",", "."), font=ctk.CTkFont(size=11), text_color="#aaaaaa").pack(side="right", padx=25)
                        
                btn_pai = ctk.CTkButton(f_header_pai, text=f"▶ 📂 {p_info['nome']}", font=ctk.CTkFont(weight="bold", size=11),
                                         fg_color="transparent", hover_color="#3a3f4b", anchor="w")
                btn_pai.pack(side="left", fill="both", expand=True, padx=5)
                btn_pai.configure(command=lambda f=f_body_pai, b=btn_pai, n=f"📂 {p_info['nome']}", bf=build_pai: toggle(f, b, n, bf))
                ctk.CTkLabel(f_header_pai, text=f"R$ {p_info['total']:,.2f}".replace(",", "."), font=ctk.CTkFont(size=11)).pack(side="right", padx=15)

        for t in tipos:
            cor = colors.get(t, "#444")
            f_pilar_wrapper = ctk.CTkFrame(scroll, fg_color="transparent", height=0)
            f_pilar_wrapper.pack(fill="x", pady=(5, 1))
            
            f_header_pilar = ctk.CTkFrame(f_pilar_wrapper, fg_color=cor, corner_radius=6, height=0)
            f_header_pilar.pack(fill="x")
            
            f_body_pilar = ctk.CTkFrame(f_pilar_wrapper, fg_color="transparent", height=0)
            
            btn_pilar = ctk.CTkButton(f_header_pilar, text=f"▶ {t.upper()}", font=ctk.CTkFont(weight="bold", size=12), 
                                      fg_color="transparent", hover_color="#444444", anchor="w")
            btn_pilar.pack(side="left", fill="both", expand=True)
            btn_pilar.configure(command=lambda f=f_body_pilar, b=btn_pilar, t_str=t.upper(), tv=t: toggle(f, b, t_str, lambda fr, val=tv: build_pilar(fr, val)))
            
            all_bodies.append((f_body_pilar, btn_pilar, t.upper()))
            ctk.CTkLabel(f_header_pilar, text=f"R$ {resumo_data[t]['total']:,.2f}".replace(",", "."), font=ctk.CTkFont(weight="bold", size=12), text_color="white").pack(side="right", padx=10)

        # Seção de Compartilhamento (Síncrona com Subperfis) - Integrada ao sistema de cascata
        if perfil == "Eu" and not subperfil_view:
            resumo_sidebar = self.db.get_resumo_financeiro(mes, ano, perfil)
            
            f_outros_wrapper = ctk.CTkFrame(scroll, fg_color="transparent", height=0)
            f_outros_wrapper.pack(fill="x", pady=(5, 1))
            
            f_outros_header = ctk.CTkFrame(f_outros_wrapper, fg_color="#334155", corner_radius=6, height=0) # Slate Navy p/ distinguir
            f_outros_header.pack(fill="x")
            
            f_outros_body = ctk.CTkFrame(f_outros_wrapper, fg_color="transparent", height=0)
            
            def build_outros(parent_frame):
                for nome, valor in resumo_sidebar.get("Divisao_Familia", {}).items():
                    f_item = ctk.CTkFrame(parent_frame, fg_color="transparent", height=0)
                    f_item.pack(fill="x", padx=25, pady=1)
                    
                    btn_drill = ctk.CTkButton(f_item, text=f"   └─ {nome}", 
                                               font=ctk.CTkFont(size=11), text_color="#aaaaaa",
                                               fg_color="transparent", hover_color="#334155", anchor="w",
                                               command=lambda p_nome=nome: panel.abrir_detalhe_interno(None, p_nome, is_subperfil=True) if panel else None)
                    btn_drill.pack(side="left", fill="x", expand=True)
                    
                    ctk.CTkLabel(f_item, text=f"R$ {valor:,.2f}".replace(",", "."), font=ctk.CTkFont(size=11), text_color="#aaaaaa").pack(side="right")

            btn_outros = ctk.CTkButton(f_outros_header, text="▶ GASTOS COMPARTILHADOS (OUTROS)", 
                                       font=ctk.CTkFont(weight="bold", size=12),
                                       fg_color="transparent", hover_color="#444444", anchor="w")
            btn_outros.pack(side="left", fill="both", expand=True)
            btn_outros.configure(command=lambda f=f_outros_body, b=btn_outros, t_str="GASTOS COMPARTILHADOS (OUTROS)": toggle(f, b, t_str, build_outros))
            
            ctk.CTkLabel(f_outros_header, text=f"R$ {resumo_sidebar['Outros']:,.2f}".replace(",", "."), 
                         font=ctk.CTkFont(weight="bold", size=12), text_color="white").pack(side="right", padx=10)
                         
        # Seção de Uso de Cartões (Colapsável)
        trans = self.db.get_transacoes(mes, ano, perfil)
        cartoes = {}
        total_cartoes = 0
        for t in trans:
            if t[8] and "Cartão" in t[8]:
                label_c = f"💳 {t[10] or 'Outra'} - 👤 {t[9] or 'N/I'}"
                cartoes[label_c] = cartoes.get(label_c, 0) + t[13] # Usa valor_total
                total_cartoes += t[13]
                
        if cartoes:
            f_cartoes_wrapper = ctk.CTkFrame(scroll, fg_color="transparent", height=0)
            f_cartoes_wrapper.pack(fill="x", pady=(5, 1))
            
            f_cartoes_header = ctk.CTkFrame(f_cartoes_wrapper, fg_color="#475569", corner_radius=6, height=0)
            f_cartoes_header.pack(fill="x")
            
            f_cartoes_body = ctk.CTkFrame(f_cartoes_wrapper, fg_color="transparent", height=0)
            
            def build_cartoes(parent_frame):
                for nome, valor in sorted(cartoes.items(), key=lambda x: x[1], reverse=True):
                    f_item = ctk.CTkFrame(parent_frame, fg_color="transparent", height=0)
                    f_item.pack(fill="x", padx=25, pady=1)
                    
                    btn_drill = ctk.CTkButton(f_item, text=f"   └─ {nome}", 
                                               font=ctk.CTkFont(size=11), text_color="#aaaaaa",
                                               fg_color="transparent", hover_color="#334155", anchor="w",
                                               command=lambda p_nome=nome: panel.abrir_detalhe_interno(None, p_nome, is_cartao=True) if panel else None)
                    btn_drill.pack(side="left", fill="x", expand=True)
                    
                    ctk.CTkLabel(f_item, text=f"R$ {valor:,.2f}".replace(",", "."), font=ctk.CTkFont(size=11), text_color="#aaaaaa").pack(side="right")

            btn_cartoes = ctk.CTkButton(f_cartoes_header, text="▶ USO DE CARTÕES", 
                                       font=ctk.CTkFont(weight="bold", size=12),
                                       fg_color="transparent", hover_color="#526075", anchor="w")
            btn_cartoes.pack(side="left", fill="both", expand=True)
            btn_cartoes.configure(command=lambda f=f_cartoes_body, b=btn_cartoes, t_str="USO DE CARTÕES": toggle(f, b, t_str, build_cartoes))
            
            ctk.CTkLabel(f_cartoes_header, text=f"R$ {total_cartoes:,.2f}".replace(",", "."), 
                         font=ctk.CTkFont(weight="bold", size=12), text_color="white").pack(side="right", padx=10)
                
        # Integração da Aba de Configuração de Categorias
        if self.var_layout.get() == "Modelo Integrado":
            config_wrapper = ctk.CTkFrame(main_wrapper, fg_color="transparent")

            def fechar_config():
                config_wrapper.pack_forget()
                # Forçar o empacotamento completo novamente para resetar a largura
                scroll.pack(fill="both", expand=True)
                if hasattr(scroll, '_parent_canvas'):
                    scroll._parent_canvas.yview_moveto(0)
                btn_abrir_config.pack(fill="x", pady=(5, 0), side="bottom")

            def abrir_config():
                # Colapsar todos os pilares e painel de outros
                for body, btn, label in all_bodies:
                    if body.winfo_manager() or body.winfo_children():
                        for w in body.winfo_children(): w.destroy()
                        body.pack_forget()
                        btn.configure(text=f"▶ {label}")
                if 'f_outros_body' in locals() and f_outros_body.winfo_manager():
                    f_outros_body.pack_forget()
                    btn_outros.configure(text="▶ GASTOS COMPARTILHADOS (OUTROS)")
                if 'f_cartoes_body' in locals() and f_cartoes_body.winfo_manager():
                    f_cartoes_body.pack_forget()
                    btn_cartoes.configure(text="▶ USO DE CARTÕES")
                
                btn_abrir_config.pack_forget()
                # Mantém expand=True para permitir que a lista cresça ao expandir categorias
                scroll.pack(fill="both", expand=True) 
                if hasattr(scroll, '_parent_canvas'):
                    scroll._parent_canvas.yview_moveto(0)
                config_wrapper.pack(fill="both", expand=True, pady=(5, 0))
                
                # Renderiza apenas na primeira vez
                if not config_wrapper.winfo_children():
                    btn_fechar = ctk.CTkButton(config_wrapper, text="Fechar Ajustes ✕", 
                                               fg_color="#F44336", hover_color="#D32F2F", 
                                               height=28, command=fechar_config)
                    btn_fechar.pack(fill="x", pady=(0, 10))
                    
                    work_area = ctk.CTkFrame(config_wrapper, fg_color="transparent")
                    work_area.pack(fill="both", expand=True)
                    self.build_widget_categorias(work_area)
            
            btn_abrir_config.configure(command=abrir_config)

    def build_widget_categorias(self, parent):
        # Top Frame (Ordem) - 10%
        top_frame = ctk.CTkFrame(parent, fg_color="transparent")
        top_frame.place(relx=0, rely=0, relwidth=1, relheight=0.08)
        
        parent.var_sort_order = ctk.StringVar(value="Contábil (R > D)")
        opt_sort = ctk.CTkOptionMenu(top_frame, variable=parent.var_sort_order, values=["Contábil (R > D)", "Prioridade (Fixa > Var)", "Padrão (D > R)"], 
                                     command=lambda _: self.carregar_lista_categorias(parent), height=22, font=ctk.CTkFont(size=11), corner_radius=8)
        opt_sort.pack(side="right", padx=2)
        ctk.CTkLabel(top_frame, text="Ordem:", font=ctk.CTkFont(size=11)).pack(side="right")
        
        # Form de Adição - 22%
        add_frame = ctk.CTkFrame(parent, fg_color="#1e293b", corner_radius=12, border_width=1, border_color="#334155")
        add_frame.place(relx=0.02, rely=0.08, relwidth=0.96, relheight=0.22)
        
        parent.var_nova_cat = ctk.StringVar(); parent.var_novo_tipo = ctk.StringVar(value="Despesa Variável")
        parent.var_tem_subcat = ctk.BooleanVar(value=False); parent.var_parent_cat = ctk.StringVar(value="(Nenhum Pai)"); parent.editing_id = None
        
        row1 = ctk.CTkFrame(add_frame, fg_color="transparent")
        row1.pack(fill="x", padx=5, pady=(5, 2))
        ctk.CTkEntry(row1, textvariable=parent.var_nova_cat, placeholder_text="Nome da Categoria", height=28, corner_radius=8).pack(side="left", fill="x", expand=True, padx=2)
        parent.opt_tipo = ctk.CTkOptionMenu(row1, variable=parent.var_novo_tipo, values=["Receita Fixa", "Receita Variável", "Despesa Fixa", "Despesa Variável", "Investimento"], width=130, height=28, corner_radius=8)
        parent.opt_tipo.pack(side="left", padx=2)
        
        row2 = ctk.CTkFrame(add_frame, fg_color="transparent")
        row2.pack(fill="x", padx=5, pady=2)
        def toggle_parent_selector():
            if parent.var_tem_subcat.get(): parent.opt_parent.configure(state="normal")
            else: parent.opt_parent.configure(state="disabled"); parent.var_parent_cat.set("(Nenhum Pai)")
            
        parent.chk_subcat = ctk.CTkCheckBox(row2, text="É Sub", variable=parent.var_tem_subcat, command=toggle_parent_selector, checkbox_width=18, checkbox_height=18)
        parent.chk_subcat.pack(side="left", padx=5)
        
        parent.parent_options = ["(Nenhum Pai)"]
        parent.opt_parent = ctk.CTkOptionMenu(row2, variable=parent.var_parent_cat, values=parent.parent_options, width=120, height=28, corner_radius=8)
        parent.opt_parent.pack(side="left", padx=2); parent.opt_parent.configure(state="disabled")
        
        parent.btn_add = ctk.CTkButton(row2, text="Adicionar", width=70, height=28, corner_radius=8, command=lambda: self.salvar_categoria(parent))
        parent.btn_add.pack(side="right", padx=2)
        
        parent.btn_cancel = ctk.CTkButton(row2, text="X", width=30, height=28, fg_color="#F44336", hover_color="#D32F2F", corner_radius=8, command=lambda: self.cancelar_edicao_cat(parent))
        
        # Status Label - 5%
        parent.lbl_status_cat = ctk.CTkLabel(parent, text="", text_color="#10b981", font=ctk.CTkFont(size=10))
        parent.lbl_status_cat.place(relx=0, rely=0.30, relwidth=1, relheight=0.05)
        
        # Lista Scroll - 65%
        parent.scroll_cat = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        parent.scroll_cat.place(relx=0, rely=0.35, relwidth=1, relheight=0.65)
        self.carregar_lista_categorias(parent)

    def cancelar_edicao_cat(self, p):
        p.editing_id = None; p.var_nova_cat.set(""); p.btn_add.configure(text="Adicionar", fg_color=["#3a7ebf", "#1f538d"]); p.btn_cancel.pack_forget()
        p.var_tem_subcat.set(False); p.opt_parent.configure(state="disabled"); p.var_parent_cat.set("(Nenhum Pai)"); p.lbl_status_cat.configure(text="")

    def iniciar_edicao_cat(self, p, cat_id, nome, tipo, parent_id):
        p.editing_id = cat_id; p.var_nova_cat.set(nome); p.var_novo_tipo.set(tipo)
        if parent_id:
            p.var_tem_subcat.set(True); p.opt_parent.configure(state="normal")
            n_p = next((c[1] for c in self.db.get_categorias() if c[0] == parent_id), "(Nenhum Pai)"); p.var_parent_cat.set(n_p)
        else: p.var_tem_subcat.set(False); p.opt_parent.configure(state="disabled"); p.var_parent_cat.set("(Nenhum Pai)")
        p.btn_add.configure(text="Salvar Ed.", fg_color="#4CAF50"); p.btn_cancel.pack(side="right", padx=2)

    def salvar_categoria(self, p):
        nome = p.var_nova_cat.get().strip()
        if not nome: return
        tipo = p.var_novo_tipo.get(); is_sub = p.var_tem_subcat.get(); p_name = p.var_parent_cat.get(); p_id = None
        if is_sub and p_name != "(Nenhum Pai)":
            for c in self.db.get_categorias():
                if c[1] == p_name and c[3] is None: p_id = c[0]; tipo = c[2]; break
        nome = nome.upper() if p_id is None else nome.title()
        if p.editing_id: suc, msg = self.db.atualizar_categoria(p.editing_id, nome, tipo, p_id)
        else: suc, msg = self.db.inserir_categoria(nome, tipo, p_id)
        if suc: self.cancelar_edicao_cat(p); self.carregar_lista_categorias(p); p.lbl_status_cat.configure(text="Sucesso", text_color="green")
        else: p.lbl_status_cat.configure(text=msg, text_color="red")

    def carregar_lista_categorias(self, p):
        for w in p.scroll_cat.winfo_children(): w.destroy()
        categorias = self.db.get_categorias(); pais = [c for c in categorias if c[3] is None]; filhos = [c for c in categorias if c[3] is not None]
        p.parent_options = ["(Nenhum Pai)"] + [c[1] for c in pais]; p.opt_parent.configure(values=p.parent_options); p.var_parent_cat.set("(Nenhum Pai)")
        ordem = p.var_sort_order.get()
        tipos = ["Receita Fixa", "Receita Variável", "Despesa Fixa", "Despesa Variável", "Investimento"]
        for tipo in tipos:
            pais_tipo = [c for c in pais if c[2] == tipo]
            if not pais_tipo: continue
            pw = ctk.CTkFrame(p.scroll_cat, fg_color="transparent"); pw.pack(fill="x", pady=2)
            mc = ctk.CTkFrame(pw, fg_color="transparent"); mc.pack(fill="x")
            mb = ctk.CTkButton(mc, text=f"▶ {tipo}", anchor="w", fg_color="transparent", text_color="#aaaaaa", font=ctk.CTkFont(weight="bold"))
            mb.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(mc, text=str(len(pais_tipo)), width=18, height=18, fg_color="#444444", corner_radius=9).pack(side="right", padx=5)
            content = ctk.CTkFrame(pw, fg_color="transparent")
            def toggle(b=mb, c=content, t=tipo):
                if c.winfo_ismapped(): c.pack_forget(); b.configure(text=f"▶ {t}")
                else: c.pack(fill="x", padx=(10, 0), pady=2); b.configure(text=f"▼ {t}")
            mb.configure(command=toggle)
            for c in pais_tipo:
                c_id, c_nome = c[0], c[1]; m_f = [f for f in filhos if f[3] == c_id]
                if m_f:
                    pc = ctk.CTkFrame(content, fg_color="transparent"); pc.pack(fill="x", pady=1)
                    ph = ctk.CTkFrame(pc, fg_color="#2b2b2b", corner_radius=4); ph.pack(fill="x")
                    pb = ctk.CTkButton(ph, text=f"▶ 📂 {c_nome}", anchor="w", fg_color="transparent")
                    pb.pack(side="left", fill="x", expand=True)
                    self.add_cat_action_buttons(ph, p, c_id, c_nome, tipo, None)
                    ctk.CTkLabel(ph, text=str(len(m_f)), width=18, height=18, fg_color="#3a7ebf", corner_radius=9).pack(side="right", padx=5)
                    p_cnt = ctk.CTkFrame(pc, fg_color="transparent")
                    def t_p(b=pb, c=p_cnt, n=c_nome):
                        if c.winfo_ismapped(): c.pack_forget(); b.configure(text=f"▶ 📂 {n}")
                        else: c.pack(fill="x", padx=(15, 0), pady=1); b.configure(text=f"▼ 📂 {n}")
                    pb.configure(command=t_p)
                    for f in m_f: self.criar_linha_simples(p_cnt, p, f[0], f[1], tipo, c_id, True)
                else: self.criar_linha_simples(content, p, c_id, c_nome, tipo, None, False)

    def criar_linha_simples(self, container, p_w, c_id, nome, tipo, p_id, is_child):
        f = ctk.CTkFrame(container, fg_color="#2b2b2b" if not is_child else "transparent", corner_radius=4); f.pack(fill="x", pady=1)
        ctk.CTkLabel(f, text=("└─ " if is_child else "📂 ") + nome, anchor="w").pack(side="left", fill="x", expand=True, padx=5)
        self.add_cat_action_buttons(f, p_w, c_id, nome, tipo, p_id)

    def add_cat_action_buttons(self, f, p_w, c_id, nome, tipo, p_id):
        ctk.CTkButton(f, text="✏️", width=30, height=20, fg_color="transparent", command=lambda: self.iniciar_edicao_cat(p_w, c_id, nome, tipo, p_id)).pack(side="right", padx=2)
        ctk.CTkButton(f, text="🗑️", width=30, height=20, fg_color="transparent", command=lambda: self.excluir_categoria(p_w, c_id)).pack(side="right", padx=2)

    def excluir_categoria(self, p, c_id):
        suc, msg = self.db.excluir_categoria(c_id)
        if suc: self.carregar_lista_categorias(p); p.lbl_status_cat.configure(text="Excluída", text_color="green")
        else: p.lbl_status_cat.configure(text=msg, text_color="red")

    def abrir_nova_transacao(self):
        # Esconder painéis e mostrar formulário
        self.panels_container.grid_forget()
        self.btn_global_nova.configure(state="disabled")
        
        if hasattr(self, "form_transacao"):
            try: self.form_transacao.destroy()
            except: pass
            
        self.form_transacao = NovaTransacaoForm(self.main_frame, self.db, self)
        self.form_transacao.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.main_frame.update_idletasks()

    def fechar_formulario(self):
        if hasattr(self, "form_transacao"):
            self.form_transacao.destroy()
        self.btn_global_nova.configure(state="normal")
        self.panels_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.refresh_all_widgets()

    def refresh_year_selector(self):
        anos = self.db.get_range_anos()
        curr = self.var_ano.get()
        if curr not in anos: anos.append(curr); anos.sort()
        self.opt_ano.configure(values=anos)

    def refresh_profile_selector(self):
        perfis = self.db.get_perfis() if hasattr(self.db, 'get_perfis') else ["Eu"]
        curr = self.var_perfil.get()
        if curr not in perfis:
            self.var_perfil.set("Eu" if "Eu" in perfis else (perfis[0] if perfis else ""))
        if hasattr(self, 'opt_perfil'):
            self.opt_perfil.configure(values=perfis)

    def prev_year(self): self.var_ano.set(str(int(self.var_ano.get()) - 1)); self.refresh_all_widgets()
    def next_year(self): self.var_ano.set(str(int(self.var_ano.get()) + 1)); self.refresh_all_widgets()

    def rodar_bot_integridade(self):
        try:
            import os, time, random
            from database import Database
            # Usar arquivo único por teste para evitar erro de 'win32: file in use'
            test_db_path = f"integridade_test_{int(time.time())}.db"
            test_db = Database(test_db_path)
        except Exception as e:
            tk.messagebox.showerror("Erro", f"Não foi possível iniciar o motor de testes: {e}")
            return
        
        report = []
        report.append("🔍 INICIANDO DIAGNÓSTICO DE INTEGRIDADE - TG SENTINEL\n")
        report.append("-" * 50)
        
        # Criar modal imediatamente para mostrar "log" em tempo real
        modal, txt_area = self.preparar_modal_vivo()
        
        def log(msg):
            report.append(msg)
            txt_area.configure(state="normal")
            txt_area.insert("end", msg + "\n")
            txt_area.see("end")
            txt_area.configure(state="disabled")
            self.update()
            time.sleep(0.4) # Delay para percepção humana
            
        try:
            # Teste 1: Estrutura de Categorias
            log("✅ Teste 1: Semeando categorias iniciais...")
            cats = test_db.get_categorias()
            if len(cats) > 0: log(f"   [OK] {len(cats)} categorias mapeadas.")
            else: raise Exception("Falha ao semear categorias.")
            
            # Teste 2: Transação Simples Randomizada
            val_salario = round(random.uniform(5000, 9000), 2)
            cat_id_rec = next((c[0] for c in cats if c[2] == "Receita Fixa"), None)
            
            log(f"\n✅ Teste 2: Lançamento de Receita (Valor: R$ {val_salario:,.2f})")
            test_db.inserir_transacao(
                conta_id=1,
                categoria_id=cat_id_rec,
                descricao=f"Salário Real Time {int(time.time())}",
                data_ini="01/01/2024",
                valor_total=val_salario,
                tipo_transacao="Receita Fixa",
                metodo="Pix"
            )
            
            res = test_db.get_resumo_financeiro("Janeiro", 2024, "Eu")
            if abs(res["Receita Fixa"] - val_salario) < 0.01: 
                log(f"   [OK] Motor capturou exatamente R$ {res['Receita Fixa']:,.2f}")
            else: raise Exception(f"Erro no saldo: {res['Receita Fixa']}")
            
            # Teste 3: Parcelamento Randomizado
            val_compra = round(random.uniform(300, 1200), 2)
            cota_esperada = round(val_compra / 6, 2) # 50% de 1/3 (6 parcelas no total)
            cat_id_des = next((c[0] for c in cats if c[2] == "Despesa Variável"), None)
            
            log(f"\n✅ Teste 3: Compra R$ {val_compra:,.2f} em 3x (50% Compartilhada)")
            divisoes = {"Eu": val_compra/2, "Mãe": val_compra/2}
            test_db.inserir_transacao(
                conta_id=1,
                categoria_id=cat_id_des,
                descricao="Validando Divisão Dinâmica",
                data_ini="01/01/2024",
                valor_total=val_compra,
                tipo_transacao="Despesa Variável",
                metodo="Cartão", 
                parcelas=3, 
                divisoes=divisoes
            )
            
            res_m1 = test_db.get_resumo_financeiro("Janeiro", 2024, "Eu")
            cota_real = res_m1["Despesa Variável"]
            # Margem de erro para centavos
            if abs(cota_real - (val_compra / 2 / 3)) < 0.1:
                log(f"   [OK] Cota mensal individual em compra parcelada validada: R$ {cota_real:,.2f}")
            else: raise Exception(f"Erro na cota: {cota_real}")
            
            # Teste 5: Divisão Assimétrica (70/30)
            val_asimetric = round(random.uniform(1000, 2000), 2)
            log(f"\n✅ Teste 5: Divisão Assimétrica 70/30 (R$ {val_asimetric:,.2f})")
            div_asimetrica = {"Eu": val_asimetric * 0.7, "Mãe": val_asimetric * 0.3}
            test_db.inserir_transacao(
                conta_id=1, categoria_id=cat_id_des, descricao="Teste Assimétrico",
                data_ini="01/01/2024", valor_total=val_asimetric, tipo_transacao="Despesa Variável",
                metodo="Dinheiro", divisoes=div_asimetrica
            )
            res_asimetrico = test_db.get_resumo_financeiro("Janeiro", 2024, "Eu")
            cota_esperada_as = val_asimetric * 0.7
            if abs(res_asimetrico["Despesa Variável"] - (cota_real + cota_esperada_as)) < 0.1:
                log(f"   [OK] Cota assimétrica processada: R$ {cota_esperada_as:,.2f}")
            else: raise Exception(f"Erro na cota assimétrica")

            # Teste 6: Divisão entre 3 pessoas (Eu, Mãe, Pai)
            val_trio = 900.0
            log(f"\n✅ Teste 6: Divisão em Trio (R$ {val_trio:,.2f} / 3 pessoas)")
            div_trio = {"Eu": 300.0, "Mãe": 300.0, "Pai": 300.0}
            test_db.inserir_transacao(
                conta_id=1, categoria_id=cat_id_des, descricao="Teste Trio",
                data_ini="01/01/2024", valor_total=val_trio, tipo_transacao="Despesa Variável",
                metodo="Pix", divisoes=div_trio
            )
            res_trio = test_db.get_resumo_financeiro("Janeiro", 2024, "Eu")
            if abs(res_trio["Despesa Variável"] - (cota_real + cota_esperada_as + 300.0)) < 0.1:
                log(f"   [OK] Cota de 1/3 validada com sucesso.")
            else: raise Exception("Erro na divisão em trio")

            # Teste 7: Validação de 'Cota de Outros' (O que não é meu)
            log("\n✅ Teste 7: Verificação de 'Cota de Outros' (Rastreabilidade)")
            outros_total = res_trio["Outros"] # Valor acumulado do que Mãe/Pai pagaram
            if outros_total > 0:
                log(f"   [OK] O sistema identificou R$ {outros_total:,.2f} pagos por terceiros.")
            else: raise Exception("Falha ao rastrear pagamentos de outros usuários.")

            res_fin = test_db.get_resumo_financeiro("Janeiro", 2024, "Eu")
            rec = res_fin["Receita Fixa"] + res_fin["Receita Variável"]
            des = res_fin["Despesa Fixa"] + res_fin["Despesa Variável"]
            inv = res_fin["Investimento"]
            saldo_calculado = rec - des - inv
            
            log(f"\n📊 RESUMO CONSOLIDADO (MULTICAMADAS):")
            log(f"   - Receitas Totais: R$ {rec:,.2f}")
            log(f"   - Despesas Individuais: R$ {des:,.2f}")
            log(f"   - Total Pagos por Outros: R$ {outros_total:,.2f}")
            log(f"   - Saldo Líquido Final: R$ {saldo_calculado:,.2f}")
            
            log("\n" + "=" * 50)
            log("🎯 DIAGNÓSTICO CONCLUÍDO: SISTEMA 100% ÍNTEGRO")
            log("   (Testes de Partilha Assimétrica e Múltipla: OK)")
            
        except Exception as e:
            log(f"\n❌ FALHA CRÍTICA NO MOTOR: {str(e)}")
        finally:
            # Limpeza robusta
            try:
                import gc
                # Pequeno delay para o Windows liberar o handle do arquivo
                del test_db
                gc.collect() 
                time.sleep(0.5)
                if 'test_db_path' in locals() and os.path.exists(test_db_path):
                    os.remove(test_db_path)
                    # Não logar no modal pois ele pode já estar fechando
            except Exception as e:
                print(f"Erro ao deletar banco temporário: {e}")

    def preparar_modal_vivo(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Sentinel Bot - Diagnóstico em Tempo Real")
        modal.geometry("650x550")
        modal.attributes("-topmost", True)
        
        frame = ctk.CTkFrame(modal, fg_color="#1e222b", corner_radius=15)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(frame, text="🛡️ SENTINEL ENGINE MONITOR", font=ctk.CTkFont(size=16, weight="bold"), text_color="#3a7ebf").pack(pady=10)
        
        txt_area = ctk.CTkTextbox(frame, fg_color="#0f172a", font=ctk.CTkFont(family="Consolas", size=11))
        txt_area.pack(fill="both", expand=True, padx=15, pady=15)
        txt_area.configure(state="disabled")
        
        btn_fechar = ctk.CTkButton(frame, text="CONCLUIR", command=modal.destroy, state="disabled")
        btn_fechar.pack(pady=10)
        
        # Função para habilitar fechar ao final
        def habilitar_fechar(): btn_fechar.configure(state="normal")
        modal.after(5000, habilitar_fechar) # Estimativa de tempo
        
        return modal, txt_area

    def mostrar_modal_relatorio(self, texto):
        modal = ctk.CTkToplevel(self)
        modal.title("Relatório de Integridade")
        modal.geometry("600x500")
        modal.attributes("-topmost", True)
        
        frame = ctk.CTkFrame(modal, fg_color="#1e222b", corner_radius=15)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(frame, text="RELATÓRIO DO SENTINEL BOT", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        txt_area = ctk.CTkTextbox(frame, fg_color="#0f172a", font=ctk.CTkFont(family="Consolas", size=12))
        txt_area.pack(fill="both", expand=True, padx=15, pady=15)
        txt_area.insert("0.0", texto)
        txt_area.configure(state="disabled")
        
        ctk.CTkButton(frame, text="FECHAR", command=modal.destroy).pack(pady=10)

    def refresh_all_widgets(self, *args):
        # Limpeza proativa de cache
        self._refresh_cache = None
        
        # OTIMIZAÇÃO: Cache de dados para evitar múltiplas queries idênticas
        mes, ano, perfil = self.var_mes.get(), self.var_ano.get(), self.var_perfil.get()
        self._refresh_cache = {
            "resumo_financeiro": self.db.get_resumo_financeiro(mes, ano, perfil),
            "resumo_estruturado": self.db.get_resumo_estruturado(mes, ano, perfil),
            "transacoes": self.db.get_transacoes(mes, ano, perfil)
        }
        
        self.refresh_year_selector()
        for p in self.active_panels: p.mudar_widget(p.var_selecao.get())
        self.atualizar_resumo_sidebar()
        
        # Limpa cache
        self._refresh_cache = None

    def atualizar_resumo_sidebar(self):
        modo = self.var_view_mode.get(); mes = self.var_mes.get() if modo == "Mensal" else None; ano = self.var_ano.get()
        perfil = self.var_perfil.get()
        
        # Usa cache se disponível
        if hasattr(self, "_refresh_cache") and self._refresh_cache and modo == "Mensal":
            resumo = self._refresh_cache["resumo_financeiro"]
        else:
            resumo = self.db.get_resumo_financeiro(mes, ano, perfil)
        
        rec = resumo["Receita Fixa"] + resumo["Receita Variável"]; des = resumo["Despesa Fixa"] + resumo["Despesa Variável"]; inv = resumo["Investimento"]
        saldo = rec - des - inv

        if perfil == "Eu":
            # Mostrar tudo
            self.card_receitas.pack(fill="x", pady=5)
            self.card_investido.pack(fill="x", pady=5)
            self.card_despesas.pack(fill="x", pady=5)
            
            prefix = modo.upper()
            self.card_saldo.winfo_children()[0].winfo_children()[0].configure(text=f"SALDO {prefix}:")
            self.card_despesas.winfo_children()[0].winfo_children()[0].configure(text="DESPESAS: ↓")
        else:
            # Perfil de consulta: esconder receitas e investimentos
            self.card_receitas.pack_forget()
            self.card_investido.pack_forget()
            # No perfil de consulta, "Saldo Devedor" é o total de despesas dele
            self.card_saldo.winfo_children()[0].winfo_children()[0].configure(text="SALDO DEVEDOR:")
            # Podemos manter o card de despesas ou não, conforme preferência. 
            # O usuário disse: "Deve aparecer apenas o saldo devedor e o pilar de despesa variável"
            self.card_despesas.pack_forget()

        def set_val(card, val, color=None):
            # O label de valor agora está dentro do primeiro filho (top_row) do card
            top_row = card.winfo_children()[0]
            lbl = top_row.winfo_children()[1]
            lbl.configure(text=val)
            if color: lbl.configure(text_color=color)
            
        if perfil == "Eu":
            set_val(self.card_saldo, f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "#4CAF50" if saldo >= 0 else "#F44336")
            set_val(self.card_receitas, f"R$ {rec:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            set_val(self.card_despesas, f"R$ {des:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            set_val(self.card_investido, f"R$ {inv:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        else:
            # Para outros perfis, o saldo devedor é o total de gastos (des)
            set_val(self.card_saldo, f"R$ {des:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "#F44336")

    def abrir_config_ia(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Configurações da IA")
        modal.geometry("450x680")
        modal.attributes("-topmost", True)
        
        frame = ctk.CTkFrame(modal, fg_color="#1e222b", corner_radius=15)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(frame, text="⚙️ CONFIGURAÇÕES DA IA", font=ctk.CTkFont(weight="bold", size=18)).pack(pady=(10, 20))
        
        # Ativar IA
        var_ativa = ctk.BooleanVar(value=self.db.get_preferencia("ia_ativa", "0") == "1")
        sw_ativa = ctk.CTkSwitch(frame, text="Ativar Assistente de IA", variable=var_ativa)
        sw_ativa.pack(anchor="w", padx=20, pady=10)
        
        # Provedor
        ctk.CTkLabel(frame, text="Provedor:").pack(anchor="w", padx=20, pady=(10, 0))
        var_provider = ctk.StringVar(value=self.db.get_preferencia("ia_provider", "API"))
        opt_provider = ctk.CTkOptionMenu(frame, variable=var_provider, values=["API (Gemini)", "Local (Ollama)"])
        opt_provider.pack(fill="x", padx=20, pady=5)
        
        # API Key
        ctk.CTkLabel(frame, text="Chave da API (apenas para API):").pack(anchor="w", padx=20, pady=(10, 0))
        var_key = ctk.StringVar(value=self.db.get_preferencia("ia_api_key", ""))
        entry_key = ctk.CTkEntry(frame, textvariable=var_key, show="*")
        entry_key.pack(fill="x", padx=20, pady=5)
        
        # Visão Local
        ctk.CTkLabel(frame, text="Visão Computacional (Leitura de Notas):").pack(anchor="w", padx=20, pady=(10, 0))
        var_vision = ctk.BooleanVar(value=self.db.get_preferencia("ia_local_vision", "0") == "1")
        sw_vision = ctk.CTkSwitch(frame, text="Ativar Leitura de Imagens", variable=var_vision)
        sw_vision.pack(anchor="w", padx=20, pady=5)
        ctk.CTkLabel(frame, text="⚠️ Modelos locais exigem muito hardware para processar imagens. APIs em nuvem são mais rápidas e recomendadas.", font=ctk.CTkFont(size=10), text_color="#f59e0b", wraplength=350, justify="left").pack(anchor="w", padx=20, pady=(0, 10))
        
        # Modelos Locais
        ctk.CTkLabel(frame, text="Modelos Locais (Ollama):").pack(anchor="w", padx=20, pady=(10, 0))
        
        f_models = ctk.CTkFrame(frame, fg_color="transparent")
        f_models.pack(fill="x", padx=20, pady=5)
        
        var_model_text = ctk.StringVar(value=self.db.get_preferencia("ia_local_model_text", "llama3"))
        var_model_vision = ctk.StringVar(value=self.db.get_preferencia("ia_local_model_vision", "llava"))
        
        ctk.CTkLabel(f_models, text="Texto:").pack(side="left")
        opt_model_text = ctk.CTkOptionMenu(f_models, variable=var_model_text, values=[var_model_text.get()], width=110)
        opt_model_text.pack(side="left", fill="x", expand=True, padx=(5, 10))
        
        ctk.CTkLabel(f_models, text="Visão:").pack(side="left")
        opt_model_vision = ctk.CTkOptionMenu(f_models, variable=var_model_vision, values=[var_model_vision.get()], width=110)
        opt_model_vision.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        def buscar_modelos():
            try:
                import requests
                res = requests.get("http://localhost:11434/api/tags", timeout=5)
                if res.status_code == 200:
                    models = [m["name"] for m in res.json().get("models", [])]
                    if models:
                        opt_model_text.configure(values=models)
                        opt_model_vision.configure(values=models)
                        if var_model_text.get() not in models: var_model_text.set(models[0])
                        if var_model_vision.get() not in models: var_model_vision.set(models[0])
                        from tkinter import messagebox
                        messagebox.showinfo("Modelos", f"Encontrados {len(models)} modelos no Ollama local.")
                    else:
                        from tkinter import messagebox
                        messagebox.showwarning("Modelos", "Nenhum modelo instalado no Ollama.")
                else:
                    from tkinter import messagebox
                    messagebox.showerror("Erro", "Não foi possível buscar os modelos.")
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror("Erro de Conexão", "Ollama não está rodando. Inicie o aplicativo Ollama no seu computador antes de buscar os modelos.")

        ctk.CTkButton(frame, text="🔄 Buscar Modelos Instalados", fg_color="#334155", hover_color="#475569", command=buscar_modelos).pack(fill="x", padx=20, pady=5)
        
        def salvar():
            self.db.set_preferencia("ia_ativa", "1" if var_ativa.get() else "0")
            self.db.set_preferencia("ia_provider", "API" if "API" in var_provider.get() else "Local")
            self.db.set_preferencia("ia_api_key", var_key.get())
            self.db.set_preferencia("ia_local_vision", "1" if var_vision.get() else "0")
            self.db.set_preferencia("ia_local_model_text", var_model_text.get())
            self.db.set_preferencia("ia_local_model_vision", var_model_vision.get())
            modal.destroy()
            
        ctk.CTkButton(frame, text="SALVAR", fg_color="#2E7D32", hover_color="#1B5E20", command=salvar).pack(pady=20)

    def abrir_chat_ia(self):
        if self.db.get_preferencia("ia_ativa", "0") != "1":
            from tkinter import messagebox
            messagebox.showwarning("IA Desativada", "Por favor, ative a IA no painel de configurações antes de usar.")
            return
            
        if self.sidebar_frame.winfo_viewable():
            self.sidebar_frame.grid_remove()
            self.ai_sidebar_frame.grid(row=0, column=0, sticky="nsew")
            
            if not self.ai_sidebar_frame.winfo_children():
                if self.db.get_preferencia("ia_provider", "API") == "Local":
                    self.show_loading_and_build_chat()
                else:
                    self.build_ai_chat()
        else:
            self.fechar_chat_ia()

    def show_loading_and_build_chat(self):
        self.loading_frame = ctk.CTkFrame(self.ai_sidebar_frame, fg_color="transparent")
        self.loading_frame.pack(fill="both", expand=True)
        
        # O botão de fechar ainda precisa estar disponível para abortar
        btn_close = ctk.CTkButton(self.loading_frame, text="✕", width=30, fg_color="#F44336", hover_color="#D32F2F", command=self.fechar_chat_ia)
        btn_close.pack(anchor="ne", padx=10, pady=10)
        
        ctk.CTkLabel(self.loading_frame, text="⚙️ Iniciando IA Local...", font=ctk.CTkFont(weight="bold", size=16)).pack(pady=(150, 10))
        ctk.CTkLabel(self.loading_frame, text="Carregando modelo na memória...\n(Isso pode demorar alguns minutos)", text_color="#64748b", justify="center").pack()
        
        def preload_model():
            try:
                from ai_manager import AIManager
                ai = AIManager(self.db)
                import requests
                # Dummy request para forçar o carregamento do modelo no Ollama
                url = "http://localhost:11434/api/generate"
                payload = {"model": ai.local_model_text, "prompt": ""}
                requests.post(url, json=payload, timeout=300)
            except: pass
            
            self.after(0, lambda: self.loading_frame.destroy() if hasattr(self, 'loading_frame') and self.loading_frame.winfo_exists() else None)
            self.after(0, lambda: self.build_ai_chat() if self.ai_sidebar_frame.winfo_viewable() else None)
            
        import threading
        threading.Thread(target=preload_model, daemon=True).start()

    def fechar_chat_ia(self):
        self.ai_sidebar_frame.grid_remove()
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
    def toggle_ai_chat_size(self):
        if not hasattr(self, 'ai_chat_size_level'):
            self.ai_chat_size_level = 1
            
        self.ai_chat_size_level = (self.ai_chat_size_level % 3) + 1
        
        if self.ai_chat_size_level == 1:
            self.grid_columnconfigure(0, minsize=280, weight=0)
            self.ai_sidebar_frame.configure(width=280)
            self.grid_columnconfigure(1, minsize=2)
            self.main_frame.grid()
        elif self.ai_chat_size_level == 2:
            self.grid_columnconfigure(0, minsize=550, weight=0)
            self.ai_sidebar_frame.configure(width=550)
            self.grid_columnconfigure(1, minsize=2)
            self.main_frame.grid()
        elif self.ai_chat_size_level == 3:
            self.grid_columnconfigure(0, minsize=0, weight=1)
            self.grid_columnconfigure(1, minsize=0)
            self.main_frame.grid_remove()

    def build_ai_chat(self):
        header = ctk.CTkFrame(self.ai_sidebar_frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(header, text="🤖 Assistente IA", font=ctk.CTkFont(weight="bold", size=16)).pack(side="left")
        
        ctk.CTkButton(header, text="✕", width=30, fg_color="#F44336", hover_color="#D32F2F", command=self.fechar_chat_ia).pack(side="right")
        ctk.CTkButton(header, text="⛶", width=30, fg_color="#334155", hover_color="#475569", command=self.toggle_ai_chat_size).pack(side="right", padx=5)
        
        self.ai_chat_history = ctk.CTkScrollableFrame(self.ai_sidebar_frame, fg_color="#0f172a", corner_radius=10)
        self.ai_chat_history.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.current_wrap_len = 230
        
        def _on_chat_resize(event):
            wrap = max(200, event.width - 40)
            if abs(getattr(self, 'current_wrap_len', 0) - wrap) > 20:
                self.current_wrap_len = wrap
                def _update_labels(widget):
                    for child in widget.winfo_children():
                        if isinstance(child, ctk.CTkLabel) and getattr(child, "cget", lambda x: None)("justify") == "left":
                            try: child.configure(wraplength=wrap)
                            except: pass
                        _update_labels(child)
                _update_labels(self.ai_chat_history)
                
        self.ai_chat_history.bind("<Configure>", _on_chat_resize)
        
        f_input = ctk.CTkFrame(self.ai_sidebar_frame, fg_color="transparent")
        f_input.pack(fill="x", padx=10, pady=(5, 10))
        
        self.var_ai_input = ctk.StringVar()
        self.entry_ai = ctk.CTkEntry(f_input, textvariable=self.var_ai_input, placeholder_text="Digite ou anexe nota...")
        self.entry_ai.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_ai.bind("<Return>", lambda e: self.enviar_msg_ia())
        
        btn_anexo = ctk.CTkButton(f_input, text="📎", width=30, fg_color="#334155", hover_color="#475569", command=self.anexar_imagem_ia)
        btn_anexo.pack(side="left", padx=(0, 5))
        
        btn_mic = ctk.CTkButton(f_input, text="🎤", width=30, fg_color="#ef4444", hover_color="#dc2626", command=self.capturar_voz_ia)
        btn_mic.pack(side="left", padx=(0, 5))
        
        btn_enviar = ctk.CTkButton(f_input, text="➤", width=30, fg_color="#3b82f6", hover_color="#2563eb", command=self.enviar_msg_ia)
        btn_enviar.pack(side="left")

    def capturar_voz_ia(self):
        def _listen():
            try:
                import speech_recognition as sr
                r = sr.Recognizer()
                with sr.Microphone() as source:
                    self.after(0, lambda: self.var_ai_input.set("Ouvindo... Fale agora."))
                    audio = r.listen(source, timeout=5, phrase_time_limit=15)
                self.after(0, lambda: self.var_ai_input.set("Processando voz..."))
                text = r.recognize_google(audio, language="pt-BR")
                self.after(0, lambda: self.var_ai_input.set(text))
            except Exception as e:
                self.after(0, lambda: self.var_ai_input.set(""))
                from tkinter import messagebox
                messagebox.showerror("Erro de Voz", f"Não foi possível capturar a voz.\nVerifique se o microfone está conectado e se a biblioteca SpeechRecognition e o PyAudio estão instalados.")
        
        import threading
        threading.Thread(target=_listen, daemon=True).start()

    def anexar_imagem_ia(self):
        from tkinter import filedialog
        import os
        path = filedialog.askopenfilename(title="Selecione a Nota Fiscal", filetypes=[("Imagens", "*.png *.jpg *.jpeg")])
        if path:
            self.caminho_anexo_ia = path
            self.entry_ai.configure(placeholder_text=f"Anexo: {os.path.basename(path)}")
            self.entry_ai.focus()

    def enviar_msg_ia(self):
        msg = self.var_ai_input.get().strip()
        path = getattr(self, "caminho_anexo_ia", None)
        
        if not msg and not path: return
        self.var_ai_input.set("")
        
        if path:
            import os
            self.adicionar_msg_chat("Você", f"[Anexo: {os.path.basename(path)}]\n{msg}")
            self.entry_ai.configure(placeholder_text="Digite ou anexe nota...")
            del self.caminho_anexo_ia
            
            import threading
            threading.Thread(target=self.processar_nota_ia, args=(path, msg), daemon=True).start()
        else:
            self.adicionar_msg_chat("Você", msg)
            import threading
            threading.Thread(target=self.processar_msg_ia, args=(msg,), daemon=True).start()
        
    def adicionar_msg_chat(self, autor, texto, frame_custom=None):
        f = ctk.CTkFrame(self.ai_chat_history, fg_color="transparent")
        f.pack(fill="x", pady=2)
        cor_autor = "#3b82f6" if autor == "Você" else "#10b981"
        ctk.CTkLabel(f, text=f"{autor}:", font=ctk.CTkFont(weight="bold", size=11), text_color=cor_autor).pack(anchor="w")
        if texto:
            wrap = getattr(self, 'current_wrap_len', 230)
            ctk.CTkLabel(f, text=texto, font=ctk.CTkFont(size=12), justify="left", wraplength=wrap).pack(anchor="w")
        if frame_custom:
            frame_custom(f)
        self.ai_chat_history.update_idletasks()
        if hasattr(self.ai_chat_history, '_parent_canvas'):
            self.ai_chat_history._parent_canvas.yview_moveto(1.0)
            
    def processar_msg_ia(self, msg):
        try:
            import threading
            import time
            from ai_manager import AIManager
            ai = AIManager(self.db)
            
            f = ctk.CTkFrame(self.ai_chat_history, fg_color="transparent")
            f.pack(fill="x", pady=2)
            
            f_header = ctk.CTkFrame(f, fg_color="transparent")
            f_header.pack(fill="x")
            
            ctk.CTkLabel(f_header, text="IA:", font=ctk.CTkFont(weight="bold", size=11), text_color="#10b981").pack(side="left")
            lbl_stats = ctk.CTkLabel(f_header, text="", font=ctk.CTkFont(size=9), text_color="#64748b")
            lbl_stats.pack(side="left", padx=(10, 0))
            
            abort_event = threading.Event()
            btn_stop = ctk.CTkButton(f_header, text="🛑 Parar", width=50, height=20, fg_color="#F44336", hover_color="#D32F2F", font=ctk.CTkFont(size=10), command=lambda: abort_event.set())
            btn_stop.pack(side="right")
            
            wrap = getattr(self, 'current_wrap_len', 230)
            lbl_resp = ctk.CTkLabel(f, text="Pensando...", font=ctk.CTkFont(size=12), justify="left", wraplength=wrap)
            lbl_resp.pack(anchor="w")
            
            self.ai_chat_history.update_idletasks()
            if hasattr(self.ai_chat_history, '_parent_canvas'):
                self.ai_chat_history._parent_canvas.yview_moveto(1.0)
            
            accumulated = [""]
            is_first = [True]
            start_time = [0]
            token_count = [0]
            
            def on_chunk(chunk):
                if is_first[0]:
                    is_first[0] = False
                    accumulated[0] = ""
                    start_time[0] = time.time()
                
                accumulated[0] += chunk
                token_count[0] += 1
                
                elapsed = time.time() - start_time[0]
                tps = token_count[0] / elapsed if elapsed > 0 else 0
                
                def update_ui():
                    try:
                        lbl_resp.configure(text=accumulated[0])
                        lbl_stats.configure(text=f"{tps:.1f} t/s")
                        if hasattr(self.ai_chat_history, '_parent_canvas'):
                            self.ai_chat_history._parent_canvas.yview_moveto(1.0)
                    except: pass
                
                self.after(0, update_ui)
                
            res = ai.enviar_mensagem(msg, callback=on_chunk, abort_event=abort_event)
            
            self.after(0, lambda: btn_stop.destroy() if btn_stop.winfo_exists() else None)
            
            final_text = accumulated[0].strip()
            
            # Limpa formatação markdown se a IA colocar
            if final_text.startswith("```json"):
                final_text = final_text[7:].strip()
            if final_text.startswith("```"):
                final_text = final_text[3:].strip()
            if final_text.endswith("```"):
                final_text = final_text[:-3].strip()
                
            # Se for um comando JSON
            if final_text.startswith("[") and final_text.endswith("]"):
                try:
                    import json
                    parsed = json.loads(final_text)
                    if isinstance(parsed, list) and len(parsed) > 0 and "acao" in parsed[0]:
                        self.after(0, lambda lbl=lbl_resp, f_ref=f, p=parsed: (lbl.pack_forget(), self._renderizar_itens_aprovacao_ia(f_ref, p)))
                        return
                except: pass
            
            if is_first[0]:
                if res:
                    self.after(0, lambda r=res, lbl=lbl_resp: lbl.configure(text=r))
                else:
                    self.after(0, lambda lbl=lbl_resp: lbl.configure(text="Erro: A IA não retornou nenhuma resposta."))
                
        except Exception as e:
            err_msg = str(e)
            try:
                self.after(0, lambda btn=btn_stop: btn.destroy() if btn.winfo_exists() else None)
                self.after(0, lambda lbl=lbl_resp, msg=err_msg: lbl.configure(text=f"Erro: {msg}"))
            except:
                self.after(0, lambda msg=err_msg: self.adicionar_msg_chat("IA", f"Erro: {msg}"))
            
    def processar_nota_ia(self, path, user_msg=""):
        self.adicionar_msg_chat("IA", "Analisando imagem...")
        try:
            from ai_manager import AIManager
            ai = AIManager(self.db)
            itens = ai.processar_nota(path, user_msg)
            
            # Remove o "Pensando..."
            for child in self.ai_chat_history.winfo_children()[-1].winfo_children(): child.destroy()
            self.ai_chat_history.winfo_children()[-1].destroy()
            
            if not itens:
                self.adicionar_msg_chat("IA", "Não consegui extrair itens desta nota.")
                return
                
            self.adicionar_msg_chat("IA", "Aqui estão os itens encontrados. Revise-os antes de adicionar:")
            
            def custom_frame(f):
                self._renderizar_itens_aprovacao_ia(f, itens)
            
            self.adicionar_msg_chat("Sistema", "", frame_custom=custom_frame)
            
        except Exception as e:
            for child in self.ai_chat_history.winfo_children()[-1].winfo_children(): child.destroy()
            self.ai_chat_history.winfo_children()[-1].destroy()
            self.adicionar_msg_chat("IA", f"Erro ao processar: {str(e)}")

    def _renderizar_itens_aprovacao_ia(self, parent_frame, itens):
        try:
            for item in itens:
                item_f = ctk.CTkFrame(parent_frame, fg_color="#1e293b", corner_radius=5)
                item_f.pack(fill="x", pady=2, padx=2)
                
                var_check = ctk.BooleanVar(value=True)
                item['var_check'] = var_check
                chk = ctk.CTkCheckBox(item_f, text="", variable=var_check, width=20)
                chk.pack(side="left", padx=5)
                
                f_info = ctk.CTkFrame(item_f, fg_color="transparent")
                f_info.pack(side="left", fill="x", expand=True, padx=2, pady=2)
                
                var_desc = ctk.StringVar(value=item.get("descricao", "Item"))
                item['var_desc'] = var_desc
                ctk.CTkEntry(f_info, textvariable=var_desc, height=24, font=ctk.CTkFont(size=11)).pack(fill="x", pady=(0, 2))
                
                f_bottom = ctk.CTkFrame(f_info, fg_color="transparent")
                f_bottom.pack(fill="x")
                
                var_val = ctk.StringVar(value=f"{item.get('valor', 0):.2f}".replace(".", ","))
                item['var_val'] = var_val
                ctk.CTkEntry(f_bottom, textvariable=var_val, height=24, width=60, font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 5))
                
                cats = [str(c[1]) for c in self.cats_data]
                cat_sug = str(item.get("categoria", ""))
                if cat_sug not in cats: cat_sug = cats[0] if cats else ""
                
                var_cat = ctk.StringVar(value=cat_sug)
                item['var_cat'] = var_cat
                ctk.CTkOptionMenu(f_bottom, variable=var_cat, values=cats if cats else [""], height=24, font=ctk.CTkFont(size=10)).pack(side="left", fill="x", expand=True)
                
            btn_salvar = ctk.CTkButton(parent_frame, text="Salvar Selecionados", fg_color="#2E7D32")
            btn_salvar.pack(pady=5)
                
            def salvar_selecionados():
                self.adicionar_msg_chat("IA", "Salvando...")
                sucesso = 0
                for item in itens:
                    if item['var_check'].get():
                        cat_id = None
                        cat_tipo = "Despesa Variável"
                        for c in self.db.get_categorias():
                            if str(c[1]) == str(item['var_cat'].get()):
                                cat_id = c[0]
                                cat_tipo = c[2]
                                break
                        val_str = str(item['var_val'].get()).replace(".", "").replace(",", ".")
                        try: val = float(val_str)
                        except: val = 0.0
                            
                        if val > 0 and cat_id:
                            from datetime import datetime
                            self.db.inserir_transacao(
                                conta_id=1,
                                categoria_id=cat_id,
                                descricao=item['var_desc'].get(),
                                data_ini=datetime.now().strftime("%d/%m/%Y"),
                                valor_total=val,
                                tipo_transacao=cat_tipo,
                                metodo="Não Informado"
                            )
                            sucesso += 1
                
                self.adicionar_msg_chat("IA", f"✅ {sucesso} itens salvos com sucesso!")
                btn_salvar.configure(state="disabled", text="Salvos")
                self.refresh_all_widgets()
                
            btn_salvar.configure(command=salvar_selecionados)
            
        except Exception as e:
            self.adicionar_msg_chat("Sistema", f"Erro crítico de interface na caixa de seleção: {str(e)}")
if __name__ == "__main__":
    from database import Database
    db = Database()
    app = AppUI(db)
    app.mainloop()
