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
            "📉 Fluxo de Gastos Mensal",
            "🍩 Despesas por Categoria",
            "📊 Ranking de Gastos",
            "🚥 Resumo do Mês",
            "📊 Gráfico: Comparação Anual",
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
        elif "Fluxo de Gastos Mensal" in selecao:
            self.app_ui.build_widget_fluxo_mensal(self.body_frame)
        elif "Despesas por Categoria" in selecao:
            self.app_ui.build_widget_donut_categorias(self.body_frame)
        elif "Ranking de Gastos" in selecao:
            self.app_ui.build_widget_ranking(self.body_frame)
        elif "Resumo do Mês" in selecao:
            self.app_ui.build_widget_resumo_mes(self.body_frame)
        elif "Comparação Anual" in selecao:
            self.app_ui.build_widget_comparacao_anual(self.body_frame)
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

