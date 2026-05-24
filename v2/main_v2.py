import flet as ft
import sys
import os
import datetime
import io
import base64
import urllib.request
import json
import threading
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Garante que importa o database local da pasta v2 e permite fallback para a raiz
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import Database

def main(page: ft.Page):
    # Configurações da Janela
    page.title = "Sentinel Finance V2"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(font_family="Segoe UI")
    page.padding = 0
    page.bgcolor = "#0f172a" 
    page.window_width = 1200
    page.window_height = 800
    page.window_min_width = 900
    page.window_min_height = 600
    
    # Inicializa BD com caminho absoluto local à pasta v2
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financas.db")
    db = Database(db_name=db_path)
    
    hoje = datetime.datetime.now()
    meses_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    state = {
        "mes_idx": hoje.month - 1,
        "ano": hoje.year,
        "perfil": "Eu",
        "active_tab": "dashboard",
        "chart_left_idx": 0,
        "chart_right_idx": 0,
        "editing_card_id": None,
        "selected_color": "#1e293b",
        "form_nome": "",
        "form_dono": "",
        "form_bandeira": "Visa",
        "form_limite": "",
        "form_fechamento": "",
        "form_vencimento": "",
        "transacoes_view_mode": "mensal",
        "transacoes_tab_active": "pilar_categoria",
        "transacoes_locked": True,
        "investimentos_tab_active": "carteira",
        "cotacoes_cache": {},
        "cotacoes_status": "idle",
    }
    
    despesas_colors = ["#f87171", "#fb923c", "#fbbf24", "#f472b6", "#c084fc", "#a78bfa", "#fca5a5"]
    receitas_colors = ["#4ade80", "#38bdf8", "#facc15", "#c084fc", "#f472b6", "#a3e635", "#fb923c"]
    
    # Se não houver transações no mês atual, tenta achar o último mês com dados
    trans_iniciais = db.get_transacoes(mes=meses_pt[state["mes_idx"]], ano=str(state["ano"]), perfil_nome=state["perfil"])
    if not trans_iniciais:
        all_t = db.get_transacoes(perfil_nome=state["perfil"])
        if all_t:
            data_str = all_t[0][1] # "dd/mm/yyyy"
            if len(data_str) >= 10:
                m_idx = int(data_str[3:5]) - 1
                if 0 <= m_idx < 12:
                    state["mes_idx"] = m_idx
                state["ano"] = int(data_str[6:10])
    
    # ==========================
    # COMPONENTES DE LAYOUT
    # ==========================
    
    # Busca a Logo 1.png da raiz
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base_dir, "Logo 1.png")
    ico_path = os.path.join(base_dir, "icon.ico")
    
    if os.path.exists(logo_path):
        logo_widget = ft.Image(src="Logo 1.png", width=70, height=70, fit="contain")
        try:
            page.window.icon = ico_path if os.path.exists(ico_path) else logo_path # Compatibilidade nova
        except:
            page.window_icon = ico_path if os.path.exists(ico_path) else logo_path # Tenta compatibilidade antiga
    else:
        logo_widget = ft.Icon(ft.icons.Icons.ACCOUNT_BALANCE_WALLET, size=40, color="#3b82f6")

    def on_nav_click(e):
        # Atualizar a cor do botão ativo e mudar a página principal
        for btn in sidebar.content.controls:
            if isinstance(btn, ft.IconButton):
                btn.icon_color = "#64748b" # Inativo
        e.control.icon_color = "white" # Ativo
        
        if e.control.icon == ft.icons.Icons.DASHBOARD_ROUNDED:
            state["active_tab"] = "dashboard"
            render_dashboard()
        elif e.control.icon == ft.icons.Icons.PIE_CHART_ROUNDED:
            state["active_tab"] = "charts"
            render_dashboard()
        elif e.control.icon == ft.icons.Icons.CREDIT_CARD_ROUNDED:
            state["active_tab"] = "cartoes"
            # Reseta estado do form ao entrar na aba
            state["editing_card_id"] = None
            state["selected_color"] = "#1e293b"
            state["form_nome"] = ""
            state["form_dono"] = ""
            state["form_bandeira"] = "Visa"
            state["form_limite"] = ""
            state["form_fechamento"] = ""
            state["form_vencimento"] = ""
            render_cartoes()
        elif e.control.icon == ft.icons.Icons.LIST_ALT_ROUNDED:
            state["active_tab"] = "transacoes"
            render_transacoes()
        elif e.control.icon == ft.icons.Icons.SAVINGS_ROUNDED:
            state["active_tab"] = "investimentos"
            render_investimentos()
        else:
            titulo = e.control.tooltip
            body.content = ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(e.control.icon, size=100, color="#334155"),
                    ft.Text(f"Módulo: {titulo}", size=24, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text("Em desenvolvimento...", size=16, color="#64748b")
                ]
            )
            page.update()

    sidebar = ft.Container(
        width=100,
        bgcolor="#1e293b",
        padding=ft.Padding(left=10, top=20, right=10, bottom=20),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                logo_widget,
                ft.Divider(height=40, color="transparent"),
                ft.IconButton(icon=ft.icons.Icons.DASHBOARD_ROUNDED, tooltip="Dashboard", icon_color="white", icon_size=24, on_click=on_nav_click),
                ft.IconButton(icon=ft.icons.Icons.SAVINGS_ROUNDED, tooltip="Investimentos", icon_color="#64748b", icon_size=24, on_click=on_nav_click),
                ft.IconButton(icon=ft.icons.Icons.PIE_CHART_ROUNDED, tooltip="Gráficos", icon_color="#64748b", icon_size=24, on_click=on_nav_click),
                ft.IconButton(icon=ft.icons.Icons.LIST_ALT_ROUNDED, tooltip="Transações", icon_color="#64748b", icon_size=24, on_click=on_nav_click),
                ft.IconButton(icon=ft.icons.Icons.CREDIT_CARD_ROUNDED, tooltip="Cartões", icon_color="#64748b", icon_size=24, on_click=on_nav_click),
                ft.IconButton(icon=ft.icons.Icons.AUTO_AWESOME_ROUNDED, tooltip="Assistente IA", icon_color="#64748b", icon_size=24, on_click=on_nav_click),
                ft.Container(expand=True),
                ft.IconButton(icon=ft.icons.Icons.SETTINGS_ROUNDED, tooltip="Configurações", icon_color="#64748b", icon_size=24, on_click=on_nav_click)
            ]
        )
    )
    
    def criar_card_resumo(titulo, valor, cor_valor="#ffffff", cor_fundo="#1e293b"):
        return ft.Container(
            expand=True,
            bgcolor=cor_fundo,
            border_radius=12,
            padding=20,
            content=ft.Column(
                controls=[
                    ft.Text(titulo, size=14, color="#94a3b8", weight=ft.FontWeight.W_500),
                    ft.Text(f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=28, color=cor_valor, weight=ft.FontWeight.BOLD)
                ]
            )
        )
    
    # Função Helper para mapear Ícones por Categoria
    def get_icone_categoria(nome_cat):
        nome = nome_cat.upper()
        if "CASA" in nome or "ALUGUEL" in nome: return ft.icons.Icons.HOME_ROUNDED
        if "VEÍCULO" in nome or "CARRO" in nome or "MOTO" in nome: return ft.icons.Icons.DIRECTIONS_CAR_ROUNDED
        if "SAÚDE" in nome or "FARMÁCIA" in nome: return ft.icons.Icons.LOCAL_HOSPITAL_ROUNDED
        if "PET" in nome: return ft.icons.Icons.PETS_ROUNDED
        if "MERCADO" in nome or "ALIMENTAÇÃO" in nome: return ft.icons.Icons.SHOPPING_CART_ROUNDED
        if "LAZER" in nome or "STREAMING" in nome: return ft.icons.Icons.SPORTS_ESPORTS_ROUNDED
        if "INVESTIMENTO" in nome or "RENDIMENTO" in nome: return ft.icons.Icons.TRENDING_UP_ROUNDED
        if "RENDA" in nome or "SALÁRIO" in nome: return ft.icons.Icons.ATTACH_MONEY_ROUNDED
        if "CONSUMO" in nome or "ROUPA" in nome: return ft.icons.Icons.SHOPPING_BAG_ROUNDED
        return ft.icons.Icons.RECEIPT_ROUNDED

    def criar_lista_transacoes(titulo, transacoes, eh_despesa=True):
        itens = []
        for t in transacoes[:15]: # Limite de 15 para o dashboard
            data_str = t[1][:5] # Apenas dd/mm
            desc = t[2]
            valor = t[3]
            cat = t[4]
            tipo_t = t[5]
            parc_atual = t[6]   # parcela_atual
            parc_total = t[7]   # total_parcelas
            
            if tipo_t == "Investimento":
                icone_cor = "#3b82f6"
            else:
                icone_cor = "#ef4444" if eh_despesa else "#10b981"
            icone_tipo = get_icone_categoria(cat)

            # Monta subtítulo com parcela se aplicável
            subtitle = f"{data_str} • {cat.strip().title()}"
            if parc_total and parc_total > 1:
                subtitle += f" • Parcela {parc_atual} de {parc_total}"
            
            itens.append(
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor="#0f172a",
                    ink=True,
                    on_click=lambda e, tid=t[0], tipo_t=t[5]: abrir_overlay(
                        "despesa" if "despesa" in tipo_t.lower() else ("investimento" if tipo_t.lower() == "investimento" else "receita"),
                        editing_trans_id=tid
                    ),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                expand=True,
                                controls=[
                                    ft.Container(
                                        padding=10,
                                        bgcolor="#1e293b",
                                        border_radius=8,
                                        content=ft.Icon(icone_tipo, color=icone_cor, size=20)
                                    ),
                                    ft.Container(width=10),
                                    ft.Column(
                                        expand=True,
                                        spacing=2,
                                        controls=[
                                            ft.Text(desc, size=14, weight=ft.FontWeight.BOLD, color="white", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                            ft.Text(subtitle, size=12, color="#64748b", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                                        ]
                                    )
                                ]
                            ),
                            ft.Text(f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=14, weight=ft.FontWeight.BOLD, color=icone_cor)
                        ]
                    )
                )
            )
            
        if not itens:
            itens.append(ft.Text("Nenhum lançamento recente.", color="#64748b"))
            
        return ft.Container(
            expand=True,
            bgcolor="#1e293b",
            border_radius=12,
            padding=20,
            content=ft.Column(
                controls=[
                    ft.Text(titulo, size=18, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Divider(color="#334155"),
                    ft.ListView(
                        expand=True,
                        spacing=10,
                        controls=itens
                    )
                ]
            )
        )
        
    dashboard_view = ft.Column(expand=True)
    body = ft.Container(expand=True, padding=30, content=dashboard_view)

    def prev_month(e):
        if state["active_tab"] == "transacoes" and state["transacoes_view_mode"] == "anual":
            state["ano"] -= 1
            render_transacoes()
            return
        state["mes_idx"] -= 1
        if state["mes_idx"] < 0:
            state["mes_idx"] = 11
            state["ano"] -= 1
        if state["active_tab"] == "cartoes":
            render_cartoes()
        elif state["active_tab"] == "transacoes":
            render_transacoes()
        else:
            render_dashboard()
        
    def next_month(e):
        if state["active_tab"] == "transacoes" and state["transacoes_view_mode"] == "anual":
            state["ano"] += 1
            render_transacoes()
            return
        state["mes_idx"] += 1
        if state["mes_idx"] > 11:
            state["mes_idx"] = 0
            state["ano"] += 1
        if state["active_tab"] == "cartoes":
            render_cartoes()
        elif state["active_tab"] == "transacoes":
            render_transacoes()
        else:
            render_dashboard()

    def change_chart_left(e, inc):
        state["chart_left_idx"] = (state["chart_left_idx"] + inc) % 2
        render_dashboard()
        
    def change_chart_right(e, inc):
        state["chart_right_idx"] = (state["chart_right_idx"] + inc) % 2
        render_dashboard()

    def criar_painel_grafico(titulo, chart_control, on_prev, on_next):
        return ft.Container(
            expand=True,
            bgcolor="#1e293b",
            border_radius=12,
            padding=20,
            content=ft.Column(
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", on_click=on_prev),
                            ft.Text(titulo, size=18, weight=ft.FontWeight.BOLD, color="white"),
                            ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", on_click=on_next)
                        ]
                    ),
                    ft.Divider(color="#334155"),
                    ft.Container(expand=True, padding=10, content=chart_control)
                ]
            )
        )

    def gerar_grafico_base64(tipo, dados, labels, cores):
        fig, ax = plt.subplots(figsize=(5.5, 3.5), facecolor='#1e293b')
        ax.set_facecolor('#1e293b')
        
        if tipo == "pizza":
            if sum(dados) == 0: 
                dados = [1]; labels = ["Zero - 0%"]; cores = ["#334155"]
            else:
                total = sum(dados)
                labels = [f"{lbl} - {(val/total)*100:.1f}%" for lbl, val in zip(labels, dados)]
                
            def my_autopct(pct):
                return ('%1.0f%%' % pct) if pct >= 5 else ''
                
            wedges, texts, autotexts = ax.pie(dados, colors=cores, autopct=my_autopct,
                                              textprops=dict(color="w", fontsize=9), startangle=90)
            plt.setp(autotexts, size=9, weight="bold")
            leg = ax.legend(wedges, labels, title="Categorias", loc="center left", bbox_to_anchor=(0.9, 0, 0.5, 1),
                            facecolor="#1e293b", edgecolor="#334155", labelcolor="white", title_fontsize=9, fontsize=8)
            leg.get_title().set_color("white")
        elif tipo == "fluxo":
            cores_barras = ["#10b981" if v >= 0 else "#ef4444" for v in dados]
            ax.bar(labels, dados, color=cores_barras)
            ax.tick_params(colors='white', labelsize=8)
            for spine in ax.spines.values():
                spine.set_color('#334155')
            ax.axhline(0, color='white', linewidth=1)
            plt.grid(color='#334155', linestyle='--', linewidth=0.5, axis='y')

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True, bbox_inches="tight")
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    # ==================================================
    # SISTEMA DE FAB EXPANSÍVEL E OVERLAY IN-APP (MODAL)
    # ==================================================

    # Categorias organizadas de forma hierárquica
    cats_data = db.get_categorias()
    categorias_por_pilar = {}
    for c in cats_data:
        c_id, c_nome, c_tipo, c_pid, c_has_sub = c
        if c_pid is None:
            if c_tipo not in categorias_por_pilar:
                categorias_por_pilar[c_tipo] = {}
            categorias_por_pilar[c_tipo][c_id] = {"nome": c_nome.strip().title(), "subs": []}

    for c in cats_data:
        c_id, c_nome, c_tipo, c_pid, c_has_sub = c
        if c_pid is not None:
            if c_tipo in categorias_por_pilar and c_pid in categorias_por_pilar[c_tipo]:
                categorias_por_pilar[c_tipo][c_pid]["subs"].append((c_id, c_nome.strip().title()))

    # Estado do FAB expansível
    state["fab_expanded"] = False

    def toggle_fab(e=None):
        if state["fab_expanded"]:
            contrair_fab()
        else:
            expandir_fab()

    def contrair_fab():
        state["fab_expanded"] = False
        page.floating_action_button = ft.FloatingActionButton(
            icon=ft.icons.Icons.ADD,
            bgcolor="#3b82f6",
            on_click=toggle_fab,
            tooltip="Novo Lançamento"
        )
        page.update()

    def expandir_fab():
        state["fab_expanded"] = True
        page.floating_action_button = ft.Container(
            width=150,
            height=270,
            bgcolor="transparent",
            content=ft.Column(
                alignment=ft.MainAxisAlignment.END,
                horizontal_alignment=ft.CrossAxisAlignment.END,
                spacing=8,
                controls=[
                    ft.FloatingActionButton(
                        content=ft.Text("Despesa 🔴", color="white", weight=ft.FontWeight.BOLD),
                        width=140,
                        height=40,
                        bgcolor="#1e293b",
                        on_click=lambda e: (contrair_fab(), abrir_overlay("despesa"))
                    ),
                    ft.FloatingActionButton(
                        content=ft.Text("Receita 🟢", color="white", weight=ft.FontWeight.BOLD),
                        width=140,
                        height=40,
                        bgcolor="#1e293b",
                        on_click=lambda e: (contrair_fab(), abrir_overlay("receita"))
                    ),
                    ft.FloatingActionButton(
                        content=ft.Text("Aporte 🔵", color="white", weight=ft.FontWeight.BOLD),
                        width=140,
                        height=40,
                        bgcolor="#1e293b",
                        on_click=lambda e: (contrair_fab(), abrir_overlay("investimento"))
                    ),
                    ft.FloatingActionButton(
                        icon=ft.icons.Icons.CLOSE,
                        bgcolor="#374151",
                        width=54,
                        height=54,
                        on_click=toggle_fab
                    )
                ]
            )
        )
        page.update()

    def fechar_overlay(e=None):
        if len(overlay_stack.controls) > 1:
            overlay_stack.controls.pop()  # Remove o modal card
            overlay_stack.controls.pop()  # Remove o shield backdrop
            page.update()

    def abrir_overlay(tipo="despesa", editing_trans_id=None):
        # Garante que limpa overlays anteriores antes de abrir um novo
        while len(overlay_stack.controls) > 1:
            overlay_stack.controls.pop()

        details = None
        if editing_trans_id:
            details = db.get_transacao_by_id(editing_trans_id)
            if details:
                tipo_t = details["tipo_transacao"].lower()
                if "despesa" in tipo_t:
                    tipo = "despesa"
                elif tipo_t == "investimento":
                    tipo = "investimento"
                else:
                    tipo = "receita"

        shield = ft.Container(
            expand=True,
            bgcolor="#cc090d16",  # Premium blurred matte dark backdrop
            on_click=fechar_overlay
        )

        form_container = ft.Column(expand=True, spacing=15, scroll=ft.ScrollMode.ADAPTIVE)

        if tipo == "despesa":
            title_text = "✏️ Editar Despesa" if editing_trans_id else "🔴 Lançar Nova Despesa"
        elif tipo == "investimento":
            title_text = "✏️ Editar Investimento" if editing_trans_id else "🔵 Novo Lançamento de Investimento"
        else:
            title_text = "✏️ Editar Receita" if editing_trans_id else "🟢 Nova Receita"

        modal_card = ft.Container(
            width=540,
            height=660,
            bgcolor="#111827",
            border_radius=16,
            border=ft.border.Border(
                top=ft.border.BorderSide(1.5, "#1f2937"),
                bottom=ft.border.BorderSide(1.5, "#1f2937"),
                left=ft.border.BorderSide(1.5, "#1f2937"),
                right=ft.border.BorderSide(1.5, "#1f2937")
            ),
            padding=ft.Padding(left=25, top=20, right=25, bottom=20),
            content=ft.Column(
                expand=True,
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(
                                title_text,
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color="white"
                            ),
                            ft.IconButton(
                                icon=ft.icons.Icons.CLOSE_ROUNDED,
                                icon_color="#94a3b8",
                                icon_size=22,
                                on_click=fechar_overlay,
                                tooltip="Fechar"
                            )
                        ]
                    ),
                    ft.Divider(color="#1f2937", height=15),
                    ft.Container(
                        expand=True,
                        content=form_container
                    )
                ]
            )
        )

        if tipo == "despesa":
            populate_formulario_despesa(form_container, details=details)
        elif tipo == "investimento":
            populate_formulario_receita(form_container, details=details, locked_pilar="Investimento")
        else:
            populate_formulario_receita(form_container, details=details)

        overlay_stack.controls.append(shield)
        overlay_stack.controls.append(modal_card)
        page.update()

    def populate_formulario_receita(container, details=None, locked_pilar=None):
        is_invest = (locked_pilar == "Investimento") or (details and details["tipo_transacao"] == "Investimento")
        theme_color = "#3b82f6" if is_invest else "#10b981"
        btn_label = "INVESTIMENTO" if is_invest else "RECEITA"

        txt_desc = ft.TextField(
            label="Descrição", 
            hint_text="Ex: Salário Mensal", 
            border_color="#374151", 
            focused_border_color=theme_color, 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )
        txt_valor = ft.TextField(
            label="Valor (R$)", 
            hint_text="Ex: 5000.00", 
            border_color="#374151", 
            focused_border_color=theme_color, 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )
        txt_data = ft.TextField(
            label="Data (DD/MM/AAAA)", 
            value=datetime.datetime.now().strftime("%d/%m/%Y"), 
            border_color="#374151", 
            focused_border_color=theme_color, 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )
        txt_obs = ft.TextField(
            label="Observação (Opcional)", 
            border_color="#374151", 
            focused_border_color=theme_color, 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )

        drop_pilar = ft.Dropdown(
            label="Tipo de Lançamento",
            border_color="#374151",
            focused_border_color=theme_color,
            text_style=ft.TextStyle(color="white", size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a",
            options=[
                ft.dropdown.Option("Receita Fixa"),
                ft.dropdown.Option("Receita Variável"),
                ft.dropdown.Option("Investimento")
            ],
            value=locked_pilar if locked_pilar else "Receita Fixa",
            disabled=(locked_pilar is not None),
            on_select=lambda e: update_cats_receita()
        )

        drop_cat = ft.Dropdown(
            label="Categoria",
            border_color="#374151",
            focused_border_color=theme_color,
            text_style=ft.TextStyle(color="white", size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a",
            on_select=lambda e: update_subs_receita()
        )

        drop_sub = ft.Dropdown(
            label="Subcategoria",
            border_color="#374151",
            focused_border_color=theme_color,
            text_style=ft.TextStyle(color="white", size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )

        def update_cats_receita(set_initial=None):
            pilar = drop_pilar.value
            cats = categorias_por_pilar.get(pilar, {})
            drop_cat.options = [ft.dropdown.Option(key=str(cid), text=info["nome"]) for cid, info in cats.items()]
            if cats:
                if set_initial and str(set_initial) in cats:
                    drop_cat.value = str(set_initial)
                else:
                    first_cid = list(cats.keys())[0]
                    drop_cat.value = str(first_cid)
                update_subs_receita(set_initial=set_initial)
            else:
                drop_cat.value = None
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"
            page.update()

        def update_subs_receita(set_initial=None):
            pilar = drop_pilar.value
            try:
                parent_id = int(drop_cat.value)
            except:
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"
                page.update()
                return
            cats = categorias_por_pilar.get(pilar, {})
            cat_info = cats.get(parent_id, {})
            subs = cat_info.get("subs", [])
            if subs:
                drop_sub.options = [ft.dropdown.Option(key=str(sid), text=snome) for sid, snome in subs]
                sub_val = None
                if details and str(details["categoria_id"]) in [str(s[0]) for s in subs]:
                    sub_val = str(details["categoria_id"])
                
                if sub_val:
                    drop_sub.value = sub_val
                else:
                    drop_sub.value = str(subs[0][0])
            else:
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"
            page.update()

        def salvar_receita(e):
            desc = (txt_desc.value or "").strip()
            valor_str = (txt_valor.value or "").strip()
            data_str = (txt_data.value or "").strip()
            pilar = drop_pilar.value
            cat_id_str = drop_cat.value
            sub_id_str = drop_sub.value
            obs = (txt_obs.value or "").strip()

            if not desc or not valor_str or not data_str or not cat_id_str:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Por favor, preencha a descrição, valor e data!", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return

            try:
                valor = float(valor_str.replace(",", "."))
            except ValueError:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Valor inválido!", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return

            final_cat_id = int(cat_id_str)
            if sub_id_str and sub_id_str != "Geral":
                try: final_cat_id = int(sub_id_str)
                except: pass

            if details:
                success, msg = db.atualizar_transacao(
                    transacao_id=details["id"],
                    categoria_id=final_cat_id,
                    descricao=desc,
                    data=data_str,
                    valor_total=valor,
                    tipo_transacao=pilar,
                    metodo="Dinheiro",
                    bandeira="",
                    dono="",
                    observacao=obs,
                    divisoes={"Eu": valor}
                )
            else:
                success, msg = db.inserir_transacao(
                    conta_id=None,
                    categoria_id=final_cat_id,
                    descricao=desc,
                    data_ini=data_str,
                    valor_total=valor,
                    tipo_transacao=pilar,
                    metodo="Dinheiro",
                    parcelas=1,
                    bandeira="",
                    dono="",
                    recorrencia=None,
                    divisoes={"Eu": valor},
                    observacao=obs
                )

            if success:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Lançamento salvo com sucesso!" if details else f"{btn_label} adicionada com sucesso!", color="white"),
                    bgcolor="#10b981" if not is_invest else "#3b82f6"
                )
                fechar_overlay()
                if state["active_tab"] == "cartoes":
                    render_cartoes()
                elif state["active_tab"] == "transacoes":
                    render_transacoes()
                else:
                    render_dashboard()
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Erro ao salvar: {msg}", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()

        def excluir_transacao(e):
            def confirmar_delecao(e):
                dialog.open = False
                page.update()
                success, msg = db.deletar_transacao(details["id"])
                if success:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Lançamento excluído com sucesso!", color="white"),
                        bgcolor="#10b981"
                    )
                    fechar_overlay()
                    if state["active_tab"] == "cartoes":
                        render_cartoes()
                    elif state["active_tab"] == "transacoes":
                        render_transacoes()
                    else:
                        render_dashboard()
                else:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Erro ao excluir: {msg}", color="white"),
                        bgcolor="#ef4444"
                    )
                    page.snack_bar.open = True
                    page.update()

            def fechar_dialog(e):
                dialog.open = False
                page.update()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("CONFIRMAR EXCLUSÃO ⚠️", size=16, weight=ft.FontWeight.BOLD, color="white"),
                content=ft.Text("Deseja realmente excluir permanentemente este lançamento?", size=14, color="#94a3b8"),
                bgcolor="#1e293b",
                actions=[
                    ft.TextButton("CANCELAR", on_click=fechar_dialog, style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton("EXCLUIR", on_click=confirmar_delecao, bgcolor="#ef4444", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.dialog = dialog
            dialog.open = True
            page.update()

        # Pre-fill inputs
        if details:
            txt_desc.value = details["descricao"]
            txt_valor.value = f"{details['valor_total']:.2f}".replace(".", ",")
            txt_data.value = details["data"]
            txt_obs.value = details["observacao"]
            drop_pilar.value = details["tipo_transacao"]

        # Action Buttons layout
        action_buttons = []
        if details:
            action_buttons.append(
                ft.Button(
                    content=ft.Text("EXCLUIR", size=13, weight=ft.FontWeight.BOLD, color="white"),
                    bgcolor="#ef4444",
                    height=45,
                    on_click=excluir_transacao
                )
            )
            action_buttons.append(
                ft.Button(
                    content=ft.Text("SALVAR ALTERAÇÕES", size=13, weight=ft.FontWeight.BOLD, color="white"),
                    bgcolor=theme_color,
                    height=45,
                    expand=True,
                    on_click=salvar_receita
                )
            )
        else:
            action_buttons.append(
                ft.Button(
                    content=ft.Text(f"SALVAR {btn_label}", size=13, weight=ft.FontWeight.BOLD, color="white"),
                    bgcolor=theme_color,
                    height=45,
                    expand=True,
                    on_click=salvar_receita
                )
            )

        container.controls = [
            ft.Row([ft.Container(expand=True, content=txt_desc), ft.Container(width=15)]),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=drop_pilar),
                    ft.Container(expand=True, content=txt_data),
                    ft.Container(width=15)
                ]
            ),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=drop_cat),
                    ft.Container(expand=True, content=drop_sub),
                    ft.Container(width=15)
                ]
            ),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=txt_valor),
                    ft.Container(expand=True), # dummy spacer for symmetry
                    ft.Container(width=15)
                ]
            ),
            ft.Row([ft.Container(expand=True, content=txt_obs), ft.Container(width=15)]),
            ft.Container(height=10),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=ft.Row(controls=action_buttons, spacing=10)),
                    ft.Container(width=15)
                ]
            )
        ]

        if details:
            update_cats_receita(set_initial=details["parent_id"])
        else:
            update_cats_receita()

    def populate_formulario_despesa(container, details=None):
        txt_desc = ft.TextField(
            label="Descrição", 
            hint_text="Ex: Compras Supermercado", 
            border_color="#374151", 
            focused_border_color="#ef4444", 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )
        txt_valor = ft.TextField(
            label="Valor (R$)", 
            hint_text="Ex: 150.50", 
            border_color="#374151", 
            focused_border_color="#ef4444", 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a", 
            on_change=lambda e: update_sharing_labels()
        )
        txt_data = ft.TextField(
            label="Data (DD/MM/AAAA)", 
            value=datetime.datetime.now().strftime("%d/%m/%Y"), 
            border_color="#374151", 
            focused_border_color="#ef4444", 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )
        txt_obs = ft.TextField(
            label="Observação (Opcional)", 
            border_color="#374151", 
            focused_border_color="#ef4444", 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )

        drop_pilar = ft.Dropdown(
            label="Pilar da Despesa",
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color="white", size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a",
            options=[
                ft.dropdown.Option("Despesa Variável"),
                ft.dropdown.Option("Despesa Fixa")
            ],
            value="Despesa Variável",
            on_select=lambda e: update_cats_despesa()
        )

        drop_cat = ft.Dropdown(
            label="Categoria",
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color="white", size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a",
            on_select=lambda e: update_subs_despesa()
        )

        drop_sub = ft.Dropdown(
            label="Subcategoria",
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color="white", size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )

        drop_metodo = ft.Dropdown(
            label="Método de Pagamento",
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color="white", size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a",
            options=[
                ft.dropdown.Option("Dinheiro"),
                ft.dropdown.Option("Pix"),
                ft.dropdown.Option("Boleto"),
                ft.dropdown.Option("Cartão")
            ],
            value="Dinheiro",
            on_select=lambda e: toggle_metodo_fields()
        )

        cartoes = db.get_cartoes()
        card_options = []
        for c in cartoes:
            card_id, c_nome, c_lim, c_fech, c_venc, c_cor, c_band, c_dono, c_dig = c
            card_options.append(ft.dropdown.Option(
                key=f"{c_band}|{c_dono}", 
                text=f"{c_nome} ({c_band} - {c_dono} •••• {c_dig})"
            ))

        drop_cartao = ft.Dropdown(
            label="Selecione o Cartão",
            border_color="#374151",
            focused_border_color="#2563eb",
            text_style=ft.TextStyle(color="white", size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a",
            options=card_options
        )
        if card_options:
            drop_cartao.value = card_options[0].key

        txt_parcelas = ft.TextField(
            label="Parcelas", 
            value="1", 
            border_color="#374151", 
            focused_border_color="#2563eb", 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a"
        )
        chk_compartilhar = ft.Checkbox(
            label="Dividir despesa com a família", 
            value=False, 
            label_style=ft.TextStyle(size=13, font_family="Segoe UI", color="white"),
            on_change=lambda e: toggle_sharing_fields()
        )

        cartao_container = ft.Column(
            visible=False,
            spacing=10,
            controls=[
                ft.Text("💳 Detalhes do Cartão", size=12, weight=ft.FontWeight.BOLD, color="#3b82f6"),
                ft.Row(
                    controls=[
                        ft.Container(expand=3, content=drop_cartao),
                        ft.Container(expand=1, content=txt_parcelas),
                        ft.Container(width=15)
                    ],
                    spacing=10
                ),
                ft.Row([chk_compartilhar, ft.Container(width=15)])
            ]
        )

        perfis = db.get_perfis() if hasattr(db, 'get_perfis') else ["Eu"]
        if "Outro..." not in perfis: perfis.append("Outro...")

        # Analisar perfil customizado da divisão
        custom_name = ""
        if details and details["divisoes"]:
            for name in details["divisoes"].keys():
                if name not in perfis and name != "Eu":
                    custom_name = name
                    break

        member_checks = []
        member_widgets = []
        for p in perfis:
            is_checked = False
            if details and details["divisoes"]:
                if p == "Outro..." and custom_name:
                    is_checked = True
                else:
                    is_checked = (p in details["divisoes"])
            else:
                is_checked = (p == "Eu")
            
            # Create standard-sized hidden label checkbox
            cb = ft.Checkbox(
                value=is_checked,
                on_change=lambda e: rebuild_sharing_inputs()
            )
            cb.data = p # Store profile name in .data attribute
            member_checks.append(cb)
            
            # Wrap standard size checkbox with customized Segoe UI text side-by-side inside a 95px container
            widget = ft.Container(
                width=95,
                content=ft.Row(
                    spacing=2,
                    controls=[
                        cb,
                        ft.Text(p, size=13, font_family="Segoe UI", color="white", weight=ft.FontWeight.W_500)
                    ]
                )
            )
            member_widgets.append(widget)

        drop_div_tipo = ft.Dropdown(
            label="Tipo de Divisão",
            border_color="#374151",
            focused_border_color="#10b981",
            text_style=ft.TextStyle(color="white", size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a",
            options=[
                ft.dropdown.Option("Igualitária"),
                ft.dropdown.Option("Individual")
            ],
            value="Igualitária",
            on_select=lambda e: rebuild_sharing_inputs()
        )

        col_inputs = ft.Column(spacing=8)
        lbl_val_status = ft.Text(size=12, weight=ft.FontWeight.BOLD)
        txt_novo_perfil = ft.TextField(
            label="Nome do novo membro", 
            border_color="#374151", 
            focused_border_color="#10b981", 
            text_style=ft.TextStyle(color="white", size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor="#0f172a", 
            visible=False, 
            on_change=lambda e: update_sharing_labels()
        )
        txt_novo_perfil_row = ft.Row([ft.Container(expand=True, content=txt_novo_perfil), ft.Container(width=15)], visible=False)

        if custom_name:
            txt_novo_perfil.value = custom_name
            txt_novo_perfil.visible = True
            txt_novo_perfil_row.visible = True

        sharing_container = ft.Column(
            visible=False,
            spacing=10,
            controls=[
                ft.Text("👥 Compartilhamento & Divisão", size=12, weight=ft.FontWeight.BOLD, color="#10b981"),
                ft.Row(controls=member_widgets + [ft.Container(width=15)], wrap=True),
                txt_novo_perfil_row,
                ft.Row([ft.Container(expand=True, content=drop_div_tipo), ft.Container(width=15)]),
                col_inputs,
                ft.Row([lbl_val_status, ft.Container(width=15)])
            ]
        )

        inputs_individuais = {}

        def update_cats_despesa(set_initial=None):
            pilar = drop_pilar.value
            cats = categorias_por_pilar.get(pilar, {})
            drop_cat.options = [ft.dropdown.Option(key=str(cid), text=info["nome"]) for cid, info in cats.items()]
            if cats:
                if set_initial and str(set_initial) in cats:
                    drop_cat.value = str(set_initial)
                else:
                    first_cid = list(cats.keys())[0]
                    drop_cat.value = str(first_cid)
                update_subs_despesa(set_initial=set_initial)
            else:
                drop_cat.value = None
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"
            page.update()

        def update_subs_despesa(set_initial=None):
            pilar = drop_pilar.value
            try:
                parent_id = int(drop_cat.value)
            except:
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"
                page.update()
                return
            cats = categorias_por_pilar.get(pilar, {})
            cat_info = cats.get(parent_id, {})
            subs = cat_info.get("subs", [])
            if subs:
                drop_sub.options = [ft.dropdown.Option(key=str(sid), text=snome) for sid, snome in subs]
                sub_val = None
                if details and str(details["categoria_id"]) in [str(s[0]) for s in subs]:
                    sub_val = str(details["categoria_id"])
                
                if sub_val:
                    drop_sub.value = sub_val
                else:
                    drop_sub.value = str(subs[0][0])
            else:
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"
            page.update()

        def toggle_metodo_fields():
            is_cartao = drop_metodo.value == "Cartão"
            cartao_container.visible = is_cartao
            if not is_cartao:
                sharing_container.visible = False
                chk_compartilhar.value = False
            else:
                toggle_sharing_fields()
            page.update()

        def toggle_sharing_fields():
            is_shared = chk_compartilhar.value == True and drop_metodo.value == "Cartão"
            sharing_container.visible = is_shared
            if is_shared:
                rebuild_sharing_inputs()
            page.update()

        def rebuild_sharing_inputs():
            col_inputs.controls.clear()
            inputs_individuais.clear()

            outro_check = next((chk for chk in member_checks if chk.data == "Outro..."), None)
            is_visible = outro_check is not None and outro_check.value == True
            txt_novo_perfil.visible = is_visible
            txt_novo_perfil_row.visible = is_visible

            selected = [chk.data for chk in member_checks if chk.value == True]
            
            if drop_div_tipo.value == "Individual":
                temp_row_controls = []
                for p in selected:
                    nome_final = p if p != "Outro..." else "Novo Membro"
                    cota_valor = "0,00"
                    if details and details["divisoes"]:
                        key_p = custom_name if p == "Outro..." else p
                        if key_p in details["divisoes"]:
                            # A cota no banco está dividida pelas parcelas, então multiplicamos de volta para exibir o valor total da compra
                            cota_valor = f"{details['divisoes'][key_p] * (details['total_parcelas'] or 1):.2f}".replace(".", ",")

                    tf = ft.TextField(
                        label=f"Valor para {nome_final}", 
                        value=cota_valor, 
                        border_color="#374151", 
                        focused_border_color="#10b981", 
                        text_style=ft.TextStyle(color="white", size=14), 
                        label_style=ft.TextStyle(size=12),
                        height=48,
                        expand=True,
                        content_padding=ft.Padding(10, 5, 10, 5),
                        bgcolor="#0f172a", 
                        on_change=lambda e: update_sharing_labels()
                    )
                    inputs_individuais[p] = tf
                    temp_row_controls.append(ft.Container(expand=True, content=tf))

                # Pack into horizontal rows of 2 members
                for i in range(0, len(temp_row_controls), 2):
                    row_slice = temp_row_controls[i:i+2]
                    if len(row_slice) == 1:
                        # Dummy container to maintain exact 50% width grid symmetry
                        row_slice.append(ft.Container(expand=True))
                    col_inputs.controls.append(ft.Row(controls=row_slice + [ft.Container(width=15)]))
            
            update_sharing_labels()
            page.update()

        def update_sharing_labels():
            try:
                val_total = float(txt_valor.value.replace(",", "."))
            except:
                val_total = 0.0

            selected = [chk.data for chk in member_checks if chk.value == True]
            if not selected:
                lbl_val_status.value = "⚠️ Selecione pelo menos uma pessoa!"
                lbl_val_status.color = "#f59e0b"
                page.update()
                return

            if drop_div_tipo.value == "Igualitária":
                val_share = val_total / len(selected)
                lbl_val_status.value = f"Divisão: R$ {val_share:,.2f} para cada um ({len(selected)} pessoas)".replace(",", ".")
                lbl_val_status.color = "#10b981"
            else:
                soma = 0.0
                for p, tf in inputs_individuais.items():
                    try: soma += float(tf.value.replace(",", "."))
                    except: pass
                
                diff = val_total - soma
                if abs(diff) < 0.05:
                    lbl_val_status.value = f"Divisão OK! (R$ {soma:,.2f} alocados)".replace(",", ".")
                    lbl_val_status.color = "#10b981"
                elif diff > 0:
                    lbl_val_status.value = f"Falta alocar: R$ {diff:,.2f}".replace(",", ".")
                    lbl_val_status.color = "#f59e0b"
                else:
                    lbl_val_status.value = f"Excesso alocado: R$ {abs(diff):,.2f}".replace(",", ".")
                    lbl_val_status.color = "#ef4444"
            page.update()

        def salvar_despesa(e):
            desc = (txt_desc.value or "").strip()
            valor_str = (txt_valor.value or "").strip()
            data_str = (txt_data.value or "").strip()
            pilar = drop_pilar.value
            cat_id_str = drop_cat.value
            sub_id_str = drop_sub.value
            metodo = drop_metodo.value
            obs = (txt_obs.value or "").strip()

            if not desc or not valor_str or not data_str or not cat_id_str:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Por favor, preencha a descrição, valor e data!", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return

            try:
                valor = float(valor_str.replace(",", "."))
                parcelas = int(txt_parcelas.value) if metodo == "Cartão" else 1
            except ValueError:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Valor ou parcelas inválidos!", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return

            bandeira = ""
            dono = ""
            if metodo == "Cartão" and drop_cartao.value:
                parts = drop_cartao.value.split("|")
                bandeira = parts[0]
                dono = parts[1]

            divisoes = {}
            novo_nome = (txt_novo_perfil.value or "").strip() if txt_novo_perfil.visible else ""

            if metodo == "Cartão" and chk_compartilhar.value == True:
                selected = [chk.data for chk in member_checks if chk.value == True]
                if not selected:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Selecione pelo menos um membro para dividir!", color="white"),
                        bgcolor="#ef4444"
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                if drop_div_tipo.value == "Igualitária":
                    val_cota = valor / len(selected)
                    for p in selected:
                        nome_final = novo_nome if p == "Outro..." and novo_nome else p
                        if p == "Outro..." and not novo_nome: nome_final = "Desconhecido"
                        divisoes[nome_final] = val_cota
                else:
                    soma = 0.0
                    for p, tf in inputs_individuais.items():
                        try:
                            val = float(tf.value.replace(",", "."))
                        except:
                            val = 0.0
                        nome_final = novo_nome if p == "Outro..." and novo_nome else p
                        if p == "Outro..." and not novo_nome: nome_final = "Desconhecido"
                        divisoes[nome_final] = val
                        soma += val
                    
                    if abs(soma - valor) > 0.05:
                        page.snack_bar = ft.SnackBar(
                            content=ft.Text("A soma das cotas familiares deve bater com o total!", color="white"),
                            bgcolor="#ef4444"
                        )
                        page.snack_bar.open = True
                        page.update()
                        return
            else:
                divisoes = {"Eu": valor}

            final_cat_id = int(cat_id_str)
            if sub_id_str and sub_id_str != "Geral":
                try: final_cat_id = int(sub_id_str)
                except: pass

            if details:
                success, msg = db.atualizar_transacao(
                    transacao_id=details["id"],
                    categoria_id=final_cat_id,
                    descricao=desc,
                    data=data_str,
                    valor_total=valor,
                    tipo_transacao=pilar,
                    metodo=metodo,
                    bandeira=bandeira,
                    dono=dono,
                    observacao=obs,
                    divisoes=divisoes
                )
            else:
                success, msg = db.inserir_transacao(
                    conta_id=None,
                    categoria_id=final_cat_id,
                    descricao=desc,
                    data_ini=data_str,
                    valor_total=valor,
                    tipo_transacao=pilar,
                    metodo=metodo,
                    parcelas=parcelas,
                    bandeira=bandeira,
                    dono=dono,
                    recorrencia=None,
                    divisoes=divisoes,
                    observacao=obs
                )

            if success:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Despesa salva com sucesso!" if details else "Despesa adicionada com sucesso!", color="white"),
                    bgcolor="#10b981"
                )
                fechar_overlay()
                if state["active_tab"] == "cartoes":
                    render_cartoes()
                elif state["active_tab"] == "transacoes":
                    render_transacoes()
                else:
                    render_dashboard()
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Erro ao salvar: {msg}", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()

        def excluir_despesa(e):
            def confirmar_delecao(e):
                dialog.open = False
                page.update()
                success, msg = db.deletar_transacao(details["id"])
                if success:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Despesa excluída com sucesso!", color="white"),
                        bgcolor="#10b981"
                    )
                    fechar_overlay()
                    if state["active_tab"] == "cartoes":
                        render_cartoes()
                    elif state["active_tab"] == "transacoes":
                        render_transacoes()
                    else:
                        render_dashboard()
                else:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Erro ao excluir: {msg}", color="white"),
                        bgcolor="#ef4444"
                    )
                    page.snack_bar.open = True
                    page.update()

            def fechar_dialog(e):
                dialog.open = False
                page.update()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("CONFIRMAR EXCLUSÃO ⚠️", size=16, weight=ft.FontWeight.BOLD, color="white"),
                content=ft.Text("Deseja realmente excluir permanentemente esta despesa?", size=14, color="#94a3b8"),
                bgcolor="#1e293b",
                actions=[
                    ft.TextButton("CANCELAR", on_click=fechar_dialog, style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton("EXCLUIR", on_click=confirmar_delecao, bgcolor="#ef4444", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.dialog = dialog
            dialog.open = True
            page.update()

        # Pre-fill inputs
        if details:
            txt_desc.value = details["descricao"]
            txt_valor.value = f"{details['valor_total']:.2f}".replace(".", ",")
            txt_data.value = details["data"]
            txt_obs.value = details["observacao"]
            drop_pilar.value = details["tipo_transacao"]
            drop_metodo.value = details["metodo_pagamento"]
            if details["metodo_pagamento"] == "Cartão":
                cartao_container.visible = True
                drop_cartao.value = f"{details['bandeira_cartao']}|{details['dono_cartao']}"
                txt_parcelas.value = str(details["total_parcelas"])
                if details["divisoes"] and len(details["divisoes"]) > 1:
                    chk_compartilhar.value = True
                    sharing_container.visible = True

        # Action buttons layout
        action_buttons = []
        if details:
            action_buttons.append(
                ft.Button(
                    content=ft.Text("EXCLUIR", size=13, weight=ft.FontWeight.BOLD, color="white"),
                    bgcolor="#ef4444",
                    height=45,
                    on_click=excluir_despesa
                )
            )
            action_buttons.append(
                ft.Button(
                    content=ft.Text("SALVAR ALTERAÇÕES", size=13, weight=ft.FontWeight.BOLD, color="white"),
                    bgcolor="#10b981",
                    height=45,
                    expand=True,
                    on_click=salvar_despesa
                )
            )
        else:
            action_buttons.append(
                ft.Button(
                    content=ft.Text("SALVAR DESPESA", size=13, weight=ft.FontWeight.BOLD, color="white"),
                    bgcolor="#ef4444",
                    height=45,
                    expand=True,
                    on_click=salvar_despesa
                )
            )

        container.controls = [
            ft.Row([ft.Container(expand=True, content=txt_desc), ft.Container(width=15)]),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=drop_pilar),
                    ft.Container(expand=True, content=txt_data),
                    ft.Container(width=15)
                ]
            ),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=drop_cat),
                    ft.Container(expand=True, content=drop_sub),
                    ft.Container(width=15)
                ]
            ),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=txt_valor),
                    ft.Container(expand=True, content=drop_metodo),
                    ft.Container(width=15)
                ]
            ),
            cartao_container,
            sharing_container,
            ft.Row([ft.Container(expand=True, content=txt_obs), ft.Container(width=15)]),
            ft.Container(height=10),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=ft.Row(controls=action_buttons, spacing=10)),
                    ft.Container(width=15)
                ]
            )
        ]

        if details:
            update_cats_despesa(set_initial=details["parent_id"])
            if details["metodo_pagamento"] == "Cartão":
                toggle_metodo_fields()
        else:
            update_cats_despesa()


    def render_dashboard():
        mes_atual = meses_pt[state["mes_idx"]]
        ano_atual = str(state["ano"])
        
        resumo = db.get_resumo_financeiro(mes_atual, ano_atual, state["perfil"])
        receitas = resumo.get("Receita Fixa", 0) + resumo.get("Receita Variável", 0)
        despesas = resumo.get("Despesa Fixa", 0) + resumo.get("Despesa Variável", 0)
        investido = resumo.get("Investimento", 0)
        saldo = receitas - despesas - investido

        todas_transacoes = db.get_transacoes(mes=mes_atual, ano=ano_atual, perfil_nome=state["perfil"])
        lista_despesas = [t for t in todas_transacoes if "Despesa" in t[5]]
        lista_receitas = [t for t in todas_transacoes if "Receita" in t[5] or "Investimento" in t[5]]

        top_cards = ft.Row(
            spacing=20,
            controls=[
                criar_card_resumo("Saldo Total", saldo, "#10b981" if saldo >= 0 else "#ef4444"),
                criar_card_resumo("Despesas", despesas, "#ef4444"),
                criar_card_resumo("Receitas", receitas, "#10b981"),
                criar_card_resumo("Investido", investido, "#3b82f6")
            ]
        )
        
        # Agrupamentos para gráficos
        def get_top_categorias(lista):
            cat_totals = {}
            for t in lista:
                cat = t[4]
                val = t[3]
                cat_totals[cat] = cat_totals.get(cat, 0) + val
            return sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
            
        def get_fluxo_diario(lista):
            dias_totals = {}
            for t in lista:
                dia = t[1][:2] # Pega "dd" de "dd/mm/yyyy"
                try: dia_int = int(dia)
                except: continue
                val = t[3] if "Receita" in t[5] else -t[3]
                dias_totals[dia_int] = dias_totals.get(dia_int, 0) + val
            return sorted(dias_totals.items(), key=lambda x: x[0])
            
        if state["active_tab"] == "dashboard":
            main_panels = ft.Row(
                expand=True,
                spacing=20,
                controls=[
                    criar_lista_transacoes("Despesas do Mês", lista_despesas, True),
                    criar_lista_transacoes("Receitas do Mês", lista_receitas, False)
                ]
            )
        else: # charts
            cat_despesas = get_top_categorias(lista_despesas)
            left_chart = ft.Container(expand=True)
            left_title = "Despesas por Categoria"
            if not cat_despesas:
                left_chart = ft.Text("Sem dados de despesas", color="#64748b")
            else:
                if state["chart_left_idx"] == 0:
                    left_title = "Despesas por Categoria"
                    dados = [x[1] for x in cat_despesas]
                    labels = [x[0] for x in cat_despesas]
                    b64 = gerar_grafico_base64("pizza", dados, labels, despesas_colors)
                    left_chart = ft.Image(src="data:image/png;base64,"+b64, fit="contain")
                else:
                    left_title = "Top 5 Despesas"
                    top5 = cat_despesas[:5]
                    
                    max_val = max(x[1] for x in top5) if top5 else 1
                    linhas = []
                    for i, (cat, val) in enumerate(top5):
                        percent = val / max_val
                        cor = despesas_colors[i % len(despesas_colors)]
                        linhas.append(
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                        ft.Text(cat[:20], size=12, color="#94a3b8"),
                                        ft.Text(f"R$ {val:,.2f}", size=12, color="white", weight="bold")
                                    ]),
                                    ft.Container(
                                        width=None, height=12, border_radius=6, bgcolor="#0f172a",
                                        content=ft.Row(
                                            spacing=0,
                                            controls=[
                                                ft.Container(
                                                    expand=int(percent * 100) if percent > 0 else 1,
                                                    height=12, bgcolor=cor, border_radius=6,
                                                    tooltip=f"{cat}\nR$ {val:,.2f} ({(val/sum(x[1] for x in top5)*100):.1f}%)"
                                                ),
                                                ft.Container(expand=100 - int(percent * 100) if percent < 1 else 0)
                                            ]
                                        )
                                    )
                                ]
                            )
                        )
                    left_chart = ft.Container(padding=10, content=ft.Column(spacing=15, controls=linhas, expand=True))
            
            left_panel = criar_painel_grafico(left_title, left_chart, lambda e: change_chart_left(e, -1), lambda e: change_chart_left(e, 1))
            
            cat_receitas = get_top_categorias(lista_receitas)
            right_chart = ft.Container(expand=True)
            right_title = "Receitas por Categoria"
            if not cat_receitas and not lista_despesas:
                right_chart = ft.Text("Sem dados no mês", color="#64748b")
            else:
                if state["chart_right_idx"] == 0:
                    right_title = "Receitas por Categoria"
                    dados = [x[1] for x in cat_receitas]
                    labels = [x[0] for x in cat_receitas]
                    if dados:
                        b64 = gerar_grafico_base64("pizza", dados, labels, receitas_colors)
                        right_chart = ft.Image(src="data:image/png;base64,"+b64, fit="contain")
                    else:
                        right_chart = ft.Text("Sem receitas", color="#64748b")
                else:
                    right_title = "Fluxo de Caixa"
                    fluxo = get_fluxo_diario(lista_receitas + lista_despesas)
                    dados = [x[1] for x in fluxo]
                    labels = [str(x[0]) for x in fluxo]
                    if dados:
                        b64 = gerar_grafico_base64("fluxo", dados, labels, [])
                        right_chart = ft.Image(src="data:image/png;base64,"+b64, fit="contain")
                    else:
                        right_chart = ft.Text("Sem fluxo", color="#64748b")

            right_panel = criar_painel_grafico(right_title, right_chart, lambda e: change_chart_right(e, -1), lambda e: change_chart_right(e, 1))
            
            main_panels = ft.Row(
                expand=True,
                spacing=20,
                controls=[left_panel, right_panel]
            )
        
        header_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("Sentinel Finance", size=24, weight=ft.FontWeight.BOLD, color="white"),
                ft.Row(
                    spacing=5,
                    controls=[
                        ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", on_click=prev_month),
                        ft.Container(
                            bgcolor="#1e293b",
                            padding=ft.Padding(left=15, top=8, right=15, bottom=8),
                            border_radius=20,
                            content=ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Icon(ft.icons.Icons.CALENDAR_MONTH_ROUNDED, color="#94a3b8", size=18),
                                    ft.Text(f"{mes_atual} {ano_atual}", size=16, weight=ft.FontWeight.W_500, color="#94a3b8")
                                ]
                            )
                        ),
                        ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", on_click=next_month),
                    ]
                )
            ]
        )
        
        dashboard_view.controls = [
            header_row,
            ft.Container(height=10),
            top_cards,
            ft.Container(height=20),
            main_panels
        ]
        
        # Garante que o FAB aparece apenas na Dashboard
        contrair_fab()

        
        body.content = dashboard_view
        page.update()
        
    def render_cartoes():
        mes_atual_pt = meses_pt[state["mes_idx"]]
        mes_num = str(state["mes_idx"] + 1).zfill(2)
        ano_atual = str(state["ano"])
        
        color_selectors = []
        
        # Title and Cancel Button controls defined up front for direct property updates
        form_title_text = ft.Text(
            "Editar Cartão" if state["editing_card_id"] is not None else "Cadastrar Novo Cartão",
            size=18,
            weight=ft.FontWeight.BOLD,
            color="white"
        )
        
        def cancel_edit(e):
            state["editing_card_id"] = None
            state["selected_color"] = "#1e293b"
            
            # Update inputs directly
            txt_nome.value = ""
            txt_dono.value = ""
            txt_bandeira.value = "Visa"
            txt_limite.value = ""
            txt_fechamento.value = ""
            txt_vencimento.value = ""
            txt_digitos.value = ""
            
            # Reset title and cancel btn visibility
            form_title_text.value = "Cadastrar Novo Cartão"
            cancel_btn.visible = False
            
            # Reset color selectors UI
            update_color_selectors_ui("#1e293b")
            
            page.update()

        cancel_btn = ft.TextButton(
            content=ft.Text("CANCELAR", size=13, weight=ft.FontWeight.BOLD, color="#ef4444"),
            visible=state["editing_card_id"] is not None,
            on_click=cancel_edit
        )

        def update_color_selectors_ui(selected_color):
            for container in color_selectors:
                is_selected = (container.bgcolor == selected_color)
                container.border = ft.border.Border(
                    top=ft.border.BorderSide(2, "white"),
                    bottom=ft.border.BorderSide(2, "white"),
                    left=ft.border.BorderSide(2, "white"),
                    right=ft.border.BorderSide(2, "white")
                ) if is_selected else ft.border.Border(
                    top=ft.border.BorderSide(1, "#475569"),
                    bottom=ft.border.BorderSide(1, "#475569"),
                    left=ft.border.BorderSide(1, "#475569"),
                    right=ft.border.BorderSide(1, "#475569")
                )
        
        # Text fields pre-filled from state
        txt_nome = ft.TextField(
            label="Nome do Cartão",
            hint_text="Ex: Nubank, Itaú",
            value=state.get("form_nome", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a"
        )
        txt_dono = ft.TextField(
            label="Dono do Cartão",
            hint_text="Ex: João, Maria",
            value=state.get("form_dono", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a"
        )
        txt_bandeira = ft.Dropdown(
            label="Bandeira",
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a",
            options=[
                ft.dropdown.Option("Visa"),
                ft.dropdown.Option("Mastercard"),
                ft.dropdown.Option("Elo"),
                ft.dropdown.Option("American Express"),
                ft.dropdown.Option("Hipercard"),
                ft.dropdown.Option("Outra")
            ],
            value=state.get("form_bandeira", "Visa")
        )
        txt_limite = ft.TextField(
            label="Limite Total (R$)",
            hint_text="Ex: 5000.00",
            value=state.get("form_limite", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a"
        )
        txt_fechamento = ft.TextField(
            label="Dia do Fechamento",
            hint_text="Ex: 5 (1-31)",
            value=state.get("form_fechamento", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a"
        )
        txt_vencimento = ft.TextField(
            label="Dia do Vencimento",
            hint_text="Ex: 12 (1-31)",
            value=state.get("form_vencimento", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a"
        )
        txt_digitos = ft.TextField(
            label="Últimos 4 Dígitos",
            hint_text="Ex: 1234",
            max_length=4,
            value=state.get("form_digitos", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a",
            keyboard_type=ft.KeyboardType.NUMBER
        )

        # Edit/Delete Handlers
        def edit_cartao_click(card_id):
            cartoes = db.get_cartoes()
            card = next((c for c in cartoes if c[0] == card_id), None)
            if card:
                state["editing_card_id"] = card_id
                state["selected_color"] = card[5]
                
                # Update inputs directly
                txt_nome.value = card[1]
                txt_dono.value = card[7]
                txt_bandeira.value = card[6]
                txt_limite.value = str(card[2])
                txt_fechamento.value = str(card[3])
                txt_vencimento.value = str(card[4])
                txt_digitos.value = card[8] if len(card) > 8 else "1234"
                
                # Update form title & cancel button visibility directly
                form_title_text.value = "Editar Cartão"
                cancel_btn.visible = True
                
                # Update color selectors UI
                update_color_selectors_ui(card[5])
                
                page.update()

        def delete_cartao_click(card_id):
            success, msg = db.delete_cartao(card_id)
            if success:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Cartão excluído com sucesso!", color="white"),
                    bgcolor="#10b981"
                )
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Erro ao excluir: {msg}", color="white"),
                    bgcolor="#ef4444"
                )
            page.snack_bar.open = True
            if state["editing_card_id"] == card_id:
                state["editing_card_id"] = None
                state["selected_color"] = "#1e293b"
                state["form_nome"] = ""
                state["form_dono"] = ""
                state["form_bandeira"] = "Visa"
                state["form_limite"] = ""
                state["form_fechamento"] = ""
                state["form_vencimento"] = ""
                state["form_digitos"] = ""
            render_cartoes()

        def select_color(hex_color):
            state["selected_color"] = hex_color
            update_color_selectors_ui(hex_color)
            page.update()

        # Helper visual credit card inside the closure
        def criar_card_fisico(cartao_id, nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, gasto_mes, digitos):
            disponivel = limite - gasto_mes
            pct_gasto = min(1.0, gasto_mes / limite) if limite > 0 else 0.0
            
            return ft.Container(
                width=320,
                height=205,
                bgcolor=cor,
                border_radius=16,
                padding=16,
                content=ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        # Top Row: Brand & Card Name (with ellipsis truncation)
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Container(
                                    expand=True,
                                    content=ft.Text(nome, size=15, weight=ft.FontWeight.BOLD, color="white", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                                ),
                                ft.Container(
                                    padding=ft.padding.Padding(left=8, top=2, right=8, bottom=2),
                                    border_radius=6,
                                    bgcolor="#33ffffff", # 20% white
                                    content=ft.Text(bandeira.upper(), size=11, weight=ft.FontWeight.BOLD, color="white", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                                )
                            ]
                        ),
                        # Middle Row: Chip & Number (decorative)
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                # EMV Chip representation
                                ft.Container(
                                    width=38,
                                    height=26,
                                    bgcolor="#e2e8f0",
                                    border_radius=4,
                                    border=ft.border.Border(
                                        top=ft.border.BorderSide(1, "#cbd5e1"),
                                        bottom=ft.border.BorderSide(1, "#cbd5e1"),
                                        left=ft.border.BorderSide(1, "#cbd5e1"),
                                        right=ft.border.BorderSide(1, "#cbd5e1")
                                    ),
                                    content=ft.Container(
                                        margin=ft.margin.Margin(left=8, top=2, right=8, bottom=2),
                                        border=ft.border.Border(
                                            left=ft.border.BorderSide(1, "#94a3b8"),
                                            right=ft.border.BorderSide(1, "#94a3b8")
                                        ),
                                    )
                                ),
                                ft.Text(f"••••  ••••  ••••  {digitos}", size=14, color="white", weight=ft.FontWeight.W_500)
                            ]
                        ),
                        # Limit section
                        ft.Column(
                            spacing=3,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text("Disponível:", size=11, color="#ccffffff"), # 80% white
                                        ft.Text(f"R$ {disponivel:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=15, weight=ft.FontWeight.BOLD, color="white")
                                    ]
                                ),
                                # Custom limit bar
                                ft.Container(
                                    width=None,
                                    height=6,
                                    bgcolor="#33000000", # 20% black
                                    border_radius=3,
                                    content=ft.Row(
                                        spacing=0,
                                        controls=[
                                            ft.Container(
                                                expand=max(1, int(pct_gasto * 100)) if pct_gasto > 0 else 1,
                                                height=6,
                                                bgcolor="#ef4444" if pct_gasto > 0.8 else "#10b981", # Red if >80% spent, green otherwise
                                                border_radius=3
                                            ),
                                            ft.Container(expand=max(0, 100 - int(pct_gasto * 100)) if pct_gasto < 1 else 0)
                                        ]
                                    )
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(f"Limite: R$ {limite:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=10, color="#ccffffff"),
                                        ft.Text(f"Gasto: R$ {gasto_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=10, color="#ccffffff")
                                    ]
                                )
                            ]
                        ),
                        # Bottom Row: Owner, fechamento/vencimento & Actions (compacted buttons to prevent leaking)
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(
                                    spacing=1,
                                    expand=True,
                                    controls=[
                                        ft.Text(dono.upper(), size=11, weight=ft.FontWeight.BOLD, color="white", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(f"Fec: Dia {dia_fechamento} | Venc: Dia {dia_vencimento}", size=9, color="#ccffffff")
                                    ]
                                ),
                                ft.Row(
                                    spacing=2,
                                    controls=[
                                        ft.IconButton(
                                            icon=ft.icons.Icons.EDIT_ROUNDED,
                                            icon_color="white",
                                            icon_size=15,
                                            width=30,
                                            height=30,
                                            tooltip="Editar Cartão",
                                            on_click=lambda e, cid=cartao_id: edit_cartao_click(cid)
                                        ),
                                        ft.IconButton(
                                            icon=ft.icons.Icons.DELETE_ROUNDED,
                                            icon_color="#f87171",
                                            icon_size=15,
                                            width=30,
                                            height=30,
                                            tooltip="Excluir Cartão",
                                            on_click=lambda e, cid=cartao_id: delete_cartao_click(cid)
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                )
            )

        # Color Selector
        colors_list = [
            ("#1e293b", "Grafite"),
            ("#1e3a8a", "Azul"),
            ("#064e3b", "Verde"),
            ("#4c1d95", "Roxo"),
            ("#7c2d12", "Laranja"),
            ("#881337", "Vermelho"),
            ("#78350f", "Dourado")
        ]
        
        # Populating color selectors
        color_selectors.clear()
        for hex_color, name in colors_list:
            is_selected = state["selected_color"] == hex_color
            color_selectors.append(
                ft.Container(
                    width=30,
                    height=30,
                    border_radius=15,
                    bgcolor=hex_color,
                    border=ft.border.Border(
                        top=ft.border.BorderSide(2, "white"),
                        bottom=ft.border.BorderSide(2, "white"),
                        left=ft.border.BorderSide(2, "white"),
                        right=ft.border.BorderSide(2, "white")
                    ) if is_selected else ft.border.Border(
                        top=ft.border.BorderSide(1, "#475569"),
                        bottom=ft.border.BorderSide(1, "#475569"),
                        left=ft.border.BorderSide(1, "#475569"),
                        right=ft.border.BorderSide(1, "#475569")
                    ),
                    tooltip=name,
                    on_click=lambda e, hc=hex_color: select_color(hc)
                )
            )

        # Save Handler (with robust safe typing and stripping to prevent crash)
        def save_card(e):
            nome = (txt_nome.value or "").strip()
            dono = (txt_dono.value or "").strip()
            bandeira = txt_bandeira.value or "Visa"
            limite_str = (txt_limite.value or "").strip()
            fechamento_str = (txt_fechamento.value or "").strip()
            vencimento_str = (txt_vencimento.value or "").strip()
            digitos_str = (txt_digitos.value or "").strip()
            
            if not nome or not dono or not limite_str or not fechamento_str or not vencimento_str:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Por favor, preencha todos os campos!", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return
                
            try:
                limite = float(limite_str.replace(",", "."))
                dia_fechamento = int(fechamento_str)
                dia_vencimento = int(vencimento_str)
            except ValueError:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Valores inválidos para limite ou dias!", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return
                
            if not (1 <= dia_fechamento <= 31) or not (1 <= dia_vencimento <= 31):
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Dias de fechamento e vencimento devem ser entre 1 e 31!", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return
                
            # Digitos validation (default to 1234 if not exactly 4 digits)
            digitos = digitos_str if len(digitos_str) == 4 and digitos_str.isdigit() else "1234"
            cor = state["selected_color"]
            
            if state["editing_card_id"] is None:
                success, msg = db.add_cartao(nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, digitos)
            else:
                success, msg = db.update_cartao(state["editing_card_id"], nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, digitos)
                state["editing_card_id"] = None
                
            if success:
                # Reset local state values
                state["selected_color"] = "#1e293b"
                state["form_nome"] = ""
                state["form_dono"] = ""
                state["form_bandeira"] = "Visa"
                state["form_limite"] = ""
                state["form_fechamento"] = ""
                state["form_vencimento"] = ""
                state["form_digitos"] = ""
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(msg, color="white"),
                    bgcolor="#10b981"
                )
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Erro: {msg}", color="white"),
                    bgcolor="#ef4444"
                )
            page.snack_bar.open = True
            render_cartoes()

        # Build Card Grid
        cartoes = db.get_cartoes()
        cards_list = []
        for c in cartoes:
            card_id, nome_val, limite_val, dia_fechamento_val, dia_vencimento_val, cor_val, bandeira_val, dono_val, digitos_val = c
            gasto_mes = db.get_gasto_cartao_mes(bandeira_val, dono_val, mes_num, ano_atual)
            cards_list.append(
                criar_card_fisico(card_id, nome_val, limite_val, dia_fechamento_val, dia_vencimento_val, cor_val, bandeira_val, dono_val, gasto_mes, digitos_val)
            )

        if not cards_list:
            cards_grid = ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.icons.Icons.CREDIT_CARD_ROUNDED, size=60, color="#334155"),
                    ft.Text("Nenhum cartão cadastrado", size=16, color="#64748b", weight=ft.FontWeight.BOLD),
                    ft.Text("Use o formulário ao lado para cadastrar seu primeiro cartão.", size=12, color="#475569")
                ]
            )
        else:
            cards_grid = ft.ListView(
                expand=True,
                controls=[
                    ft.Row(
                        wrap=True,
                        spacing=20,
                        run_spacing=20,
                        controls=cards_list
                    )
                ]
            )

        form_panel = ft.Container(
            width=380,
            bgcolor="#1e293b",
            border_radius=12,
            padding=20,
            content=ft.Column(
                spacing=15,
                controls=[
                    form_title_text,
                    ft.Divider(color="#334155"),
                    ft.Row(
                        controls=[
                            ft.Container(expand=True, content=txt_nome),
                            ft.Container(expand=True, content=txt_dono),
                        ],
                        spacing=10
                    ),
                    ft.Row(
                        controls=[
                            ft.Container(expand=3, content=txt_bandeira),
                            ft.Container(expand=2, content=txt_digitos),
                        ],
                        spacing=10
                    ),
                    txt_limite,
                    ft.Row(
                        controls=[
                            ft.Container(expand=True, content=txt_fechamento),
                            ft.Container(expand=True, content=txt_vencimento),
                        ],
                        spacing=10
                    ),
                    ft.Column(
                        spacing=5,
                        controls=[
                            ft.Text("Cor do Cartão", size=12, color="#94a3b8", weight=ft.FontWeight.W_500),
                            ft.Row(controls=color_selectors, spacing=8)
                        ]
                    ),
                    ft.Container(height=5),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            cancel_btn,
                            ft.Button(
                                content=ft.Text("SALVAR", size=13, weight=ft.FontWeight.BOLD, color="white"),
                                bgcolor="#3b82f6",
                                height=40,
                                on_click=save_card
                            )
                        ]
                    )
                ]
            )
        )

        header_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Cartões de Crédito", size=24, weight=ft.FontWeight.BOLD, color="white"),
                        ft.Text("Gerencie seus limites e faturas", size=14, color="#64748b")
                    ]
                ),
                ft.Row(
                    spacing=5,
                    controls=[
                        ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", on_click=prev_month),
                        ft.Container(
                            bgcolor="#1e293b",
                            padding=ft.Padding(left=15, top=8, right=15, bottom=8),
                            border_radius=20,
                            content=ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Icon(ft.icons.Icons.CALENDAR_MONTH_ROUNDED, color="#94a3b8", size=18),
                                    ft.Text(f"{mes_atual_pt} {ano_atual}", size=16, weight=ft.FontWeight.W_500, color="#94a3b8")
                                ]
                            )
                        ),
                        ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", on_click=next_month),
                    ]
                )
            ]
        )

        # Assemble the entire main content panel
        main_panels = ft.Row(
            expand=True,
            spacing=20,
            controls=[
                ft.Container(expand=True, content=cards_grid),
                form_panel
            ]
        )

        cartoes_view = ft.Column(
            expand=True,
            controls=[
                header_row,
                ft.Container(height=20),
                main_panels
            ]
        )

        # Oculta o FAB na aba de Cartões
        page.floating_action_button = None
        
        body.content = cartoes_view
        page.update()

    def render_investimentos():
        mes_atual = meses_pt[state["mes_idx"]]
        ano_atual = str(state["ano"])
        tab_active = state.get("investimentos_tab_active", "carteira")
        cotacoes_cache = state.get("cotacoes_cache", {})
        cotacoes_status = state.get("cotacoes_status", "idle")

        def fmt(val):
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        tipo_cores = {
            "Ação": "#3b82f6", "FII": "#10b981", "ETF": "#a78bfa",
            "Tesouro": "#fbbf24", "CDB": "#fb923c", "Cripto": "#f472b6",
        }
        tipo_ordem = ["Ação", "FII", "ETF", "Tesouro", "CDB", "Cripto"]

        # ── DADOS ────────────────────────────────────────────────────
        total_aportado = db.get_total_investido_cumulativo(state["perfil"])
        carteira_ops = db.get_carteira()
        dividendos = db.get_dividendos_mes(mes_atual, ano_atual, state["perfil"])

        posicoes = {}
        for op in carteira_ops:
            op_id, ticker, tipo, operacao, qtd, preco, data_op, corretora, obs = op
            if ticker not in posicoes:
                posicoes[ticker] = {"qtd": 0.0, "custo_total": 0.0, "tipo": tipo, "ops": []}
            mult = 1.0 if operacao == "Compra" else -1.0
            posicoes[ticker]["qtd"] += mult * qtd
            posicoes[ticker]["custo_total"] += mult * qtd * preco
            posicoes[ticker]["ops"].append(op)

        posicoes_ativas = {k: v for k, v in posicoes.items() if v["qtd"] > 0.0001}
        patrimonio_custo = sum(p["custo_total"] for p in posicoes_ativas.values())
        saldo_disponivel = max(0.0, total_aportado - patrimonio_custo)

        valor_mercado = 0.0
        for ticker, pos in posicoes_ativas.items():
            cot_p = cotacoes_cache.get(ticker, {}).get("preco")
            valor_mercado += pos["qtd"] * cot_p if cot_p else pos["custo_total"]
        variacao_total = valor_mercado - patrimonio_custo

        # ── FUNÇÕES INTERNAS ─────────────────────────────────────────
        def buscar_cotacoes():
            if not posicoes_ativas:
                state["cotacoes_cache"] = {}
                state["cotacoes_status"] = "idle"
                render_investimentos()
                return
            tickers_str = ",".join(posicoes_ativas.keys())
            try:
                url = f"https://brapi.dev/api/quote/{tickers_str}?token=demo"
                req = urllib.request.Request(url, headers={"User-Agent": "SentinelFinance/2.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data_api = json.loads(resp.read().decode())
                cache = {}
                for item in data_api.get("results", []):
                    sym = item.get("symbol", "")
                    cache[sym] = {
                        "preco": item.get("regularMarketPrice"),
                        "variacao": item.get("regularMarketChangePercent"),
                        "nome": item.get("longName") or item.get("shortName") or sym,
                    }
                state["cotacoes_cache"] = cache
                state["cotacoes_status"] = "online"
            except Exception:
                state["cotacoes_status"] = "offline"
            render_investimentos()

        def set_tab_inv(tab_name):
            state["investimentos_tab_active"] = tab_name
            if tab_name == "cotacoes" and posicoes_ativas:
                state["cotacoes_status"] = "idle"
                render_investimentos()
                threading.Thread(target=buscar_cotacoes, daemon=True).start()
            else:
                render_investimentos()

        def _close_dlg():
            if page.dialog:
                page.dialog.open = False
            page.update()

        def _do_del_op(oid):
            _close_dlg()
            db.delete_operacao_carteira(oid)
            fechar_overlay()
            render_investimentos()

        def confirm_delete_op(oid):
            page.dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirmar Exclusão", color="white"),
                content=ft.Text("Excluir esta operação permanentemente?", color="#94a3b8"),
                bgcolor="#1e293b",
                actions=[
                    ft.TextButton("CANCELAR", on_click=lambda e: _close_dlg()),
                    ft.TextButton("EXCLUIR", style=ft.ButtonStyle(color="#ef4444"),
                                  on_click=lambda e: _do_del_op(oid))
                ]
            )
            page.dialog.open = True
            page.update()

        def mostrar_operacoes_ticker(ticker, pos):
            while len(overlay_stack.controls) > 1:
                overlay_stack.controls.pop()
            ops = pos["ops"]
            cor_tipo = tipo_cores.get(pos["tipo"], "#3b82f6")
            preco_medio = pos["custo_total"] / pos["qtd"] if pos["qtd"] > 0 else 0.0

            op_rows = []
            for op in ops:
                op_id, _t, _tipo, operacao, qtd, preco, data_op, corretora, _obs = op
                total = qtd * preco
                op_cor = "#10b981" if operacao == "Compra" else "#ef4444"
                op_rows.append(
                    ft.Container(
                        padding=ft.Padding(10, 8, 10, 8),
                        border=ft.Border(bottom=ft.BorderSide(1, "#1e293b")),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(spacing=2, controls=[
                                    ft.Row([
                                        ft.Container(
                                            padding=ft.Padding(5, 2, 5, 2),
                                            bgcolor=op_cor + "22", border_radius=4,
                                            content=ft.Text(operacao.upper(), size=10, color=op_cor, weight=ft.FontWeight.BOLD)
                                        ),
                                        ft.Text(data_op, size=12, color="#94a3b8")
                                    ], spacing=8),
                                    ft.Text(
                                        f"{qtd:,.0f} un × {fmt(preco)}",
                                        size=11, color="#64748b"
                                    )
                                ]),
                                ft.Row([
                                    ft.Column(spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END, controls=[
                                        ft.Text(fmt(total), size=13, weight=ft.FontWeight.BOLD, color="white"),
                                        ft.Text(corretora or "—", size=10, color="#475569")
                                    ]),
                                    ft.IconButton(
                                        icon=ft.icons.Icons.DELETE_OUTLINE_ROUNDED,
                                        icon_color="#ef4444", icon_size=18,
                                        tooltip="Excluir operação",
                                        on_click=lambda e, oid=op_id: confirm_delete_op(oid)
                                    )
                                ], spacing=0)
                            ]
                        )
                    )
                )

            modal = ft.Container(
                width=500, height=520, bgcolor="#111827", border_radius=16,
                border=ft.border.Border(
                    top=ft.border.BorderSide(1.5, "#1f2937"),
                    bottom=ft.border.BorderSide(1.5, "#1f2937"),
                    left=ft.border.BorderSide(3, cor_tipo),
                    right=ft.border.BorderSide(1.5, "#1f2937"),
                ),
                padding=ft.Padding(25, 20, 25, 20),
                content=ft.Column(expand=True, spacing=10, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Column(spacing=2, controls=[
                            ft.Text(ticker, size=20, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Text(f"{pos['qtd']:,.0f} un  •  PM: {fmt(preco_medio)}", size=12, color="#94a3b8")
                        ]),
                        ft.Row([
                            ft.ElevatedButton(
                                "NOVA COMPRA", bgcolor="#3b82f6", color="white",
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=lambda e, tk=ticker, tp=pos["tipo"]: [
                                    fechar_overlay(),
                                    abrir_form_operacao_inv(None, prefill_ticker=tk, prefill_tipo=tp)
                                ]
                            ),
                            ft.IconButton(ft.icons.Icons.CLOSE_ROUNDED, icon_color="#94a3b8", on_click=fechar_overlay)
                        ], spacing=5)
                    ]),
                    ft.Divider(color="#1f2937", height=12),
                    ft.Text("HISTÓRICO DE OPERAÇÕES", size=11, color="#64748b", weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True, content=ft.Column(
                        expand=True, scroll=ft.ScrollMode.ADAPTIVE, spacing=0,
                        controls=op_rows if op_rows else [ft.Text("Nenhuma operação.", color="#64748b")]
                    ))
                ])
            )
            shield = ft.Container(expand=True, bgcolor="#cc090d16", on_click=fechar_overlay)
            overlay_stack.controls.append(shield)
            overlay_stack.controls.append(modal)
            page.update()

        def abrir_form_operacao_inv(e, editing_op=None, prefill_ticker=None, prefill_tipo=None):
            while len(overlay_stack.controls) > 1:
                overlay_stack.controls.pop()

            txt_ticker_inv = ft.TextField(
                label="Ticker", hint_text="Ex: PETR4, MXRF11",
                value=prefill_ticker or (editing_op[1] if editing_op else ""),
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color="white", size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor="#0f172a",
                capitalization=ft.TextCapitalization.CHARACTERS
            )
            drop_tipo_inv = ft.Dropdown(
                label="Tipo de Ativo",
                value=prefill_tipo or (editing_op[2] if editing_op else "Ação"),
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color="white", size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor="#0f172a",
                options=[ft.dropdown.Option(t) for t in tipo_ordem]
            )
            drop_operacao_inv = ft.Dropdown(
                label="Operação",
                value=editing_op[3] if editing_op else "Compra",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color="white", size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor="#0f172a",
                options=[ft.dropdown.Option("Compra"), ft.dropdown.Option("Venda")]
            )
            txt_qtd_inv = ft.TextField(
                label="Quantidade", hint_text="Ex: 100",
                value=str(editing_op[4]) if editing_op else "",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color="white", size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor="#0f172a",
                keyboard_type=ft.KeyboardType.NUMBER
            )
            txt_preco_inv = ft.TextField(
                label="Preço Unitário (R$)", hint_text="Ex: 36.50",
                value=str(editing_op[5]) if editing_op else "",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color="white", size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor="#0f172a",
                keyboard_type=ft.KeyboardType.NUMBER
            )
            txt_data_inv = ft.TextField(
                label="Data (DD/MM/AAAA)",
                value=editing_op[6] if editing_op else datetime.datetime.now().strftime("%d/%m/%Y"),
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color="white", size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor="#0f172a"
            )
            txt_corretora_inv = ft.TextField(
                label="Corretora (Opcional)", hint_text="Ex: XP, Rico, Clear",
                value=editing_op[7] or "" if editing_op else "",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color="white", size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor="#0f172a"
            )
            txt_obs_inv = ft.TextField(
                label="Observação (Opcional)",
                value=editing_op[8] or "" if editing_op else "",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color="white", size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor="#0f172a"
            )

            def salvar_operacao_inv(e):
                ticker_val = (txt_ticker_inv.value or "").strip().upper()
                tipo_val = drop_tipo_inv.value or "Ação"
                op_val = drop_operacao_inv.value or "Compra"
                data_val = (txt_data_inv.value or "").strip()
                erros = []
                if not ticker_val:
                    erros.append("Ticker obrigatório")
                try:
                    qtd_val = float((txt_qtd_inv.value or "").replace(",", "."))
                    if qtd_val <= 0:
                        erros.append("Quantidade deve ser > 0")
                except Exception:
                    erros.append("Quantidade inválida")
                    qtd_val = 0.0
                try:
                    preco_val = float((txt_preco_inv.value or "").replace(",", "."))
                    if preco_val <= 0:
                        erros.append("Preço deve ser > 0")
                except Exception:
                    erros.append("Preço inválido")
                    preco_val = 0.0
                if erros:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("  •  ".join(erros), color="white"),
                        bgcolor="#ef4444"
                    )
                    page.snack_bar.open = True
                    page.update()
                    return
                if editing_op:
                    db.delete_operacao_carteira(editing_op[0])
                db.add_operacao_carteira(
                    ticker=ticker_val, tipo_ativo=tipo_val, operacao=op_val,
                    quantidade=qtd_val, preco_unitario=preco_val, data=data_val,
                    corretora=(txt_corretora_inv.value or "").strip() or None,
                    observacao=(txt_obs_inv.value or "").strip() or None
                )
                fechar_overlay()
                render_investimentos()

            title_str = "✏️ Editar Operação" if editing_op else "📈 Nova Operação"
            modal_card = ft.Container(
                width=540, height=560, bgcolor="#111827", border_radius=16,
                border=ft.border.Border(
                    top=ft.border.BorderSide(1.5, "#1f2937"),
                    bottom=ft.border.BorderSide(1.5, "#1f2937"),
                    left=ft.border.BorderSide(3, "#3b82f6"),
                    right=ft.border.BorderSide(1.5, "#1f2937"),
                ),
                padding=ft.Padding(25, 20, 25, 20),
                content=ft.Column(expand=True, spacing=10, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Text(title_str, size=18, weight=ft.FontWeight.BOLD, color="white"),
                        ft.IconButton(ft.icons.Icons.CLOSE_ROUNDED, icon_color="#94a3b8", icon_size=22, on_click=fechar_overlay)
                    ]),
                    ft.Divider(color="#1f2937", height=12),
                    ft.Container(expand=True, content=ft.Column(
                        spacing=12, scroll=ft.ScrollMode.ADAPTIVE, expand=True,
                        controls=[
                            ft.Row([txt_ticker_inv, drop_tipo_inv], spacing=10),
                            ft.Row([drop_operacao_inv, txt_qtd_inv], spacing=10),
                            ft.Row([txt_preco_inv, txt_data_inv], spacing=10),
                            txt_corretora_inv,
                            txt_obs_inv,
                            ft.Container(height=5),
                            ft.Row(alignment=ft.MainAxisAlignment.END, controls=[
                                ft.ElevatedButton(
                                    "SALVAR OPERAÇÃO", bgcolor="#3b82f6", color="white",
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                    on_click=salvar_operacao_inv
                                )
                            ])
                        ]
                    ))
                ])
            )
            shield = ft.Container(expand=True, bgcolor="#cc090d16", on_click=fechar_overlay)
            overlay_stack.controls.append(shield)
            overlay_stack.controls.append(modal_card)
            page.update()

        # ── HEADER ───────────────────────────────────────────────────
        header_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("Investimentos", size=24, weight=ft.FontWeight.BOLD, color="white"),
                ft.Row(spacing=8, controls=[
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(ft.icons.Icons.ADD_ROUNDED, color="white", size=16),
                            ft.Text("NOVA OPERAÇÃO", size=12, color="white", weight=ft.FontWeight.BOLD)
                        ], spacing=5),
                        bgcolor="#3b82f6",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=abrir_form_operacao_inv
                    ),
                    ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", on_click=prev_month),
                    ft.Container(
                        bgcolor="#1e293b", padding=ft.Padding(15, 8, 15, 8), border_radius=20,
                        content=ft.Row(spacing=10, controls=[
                            ft.Icon(ft.icons.Icons.CALENDAR_MONTH_ROUNDED, color="#94a3b8", size=18),
                            ft.Text(f"{mes_atual} {ano_atual}", size=16, weight=ft.FontWeight.W_500, color="#94a3b8")
                        ])
                    ),
                    ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", on_click=next_month),
                ])
            ]
        )

        # ── TOP CARDS ────────────────────────────────────────────────
        var_cor_total = "#10b981" if variacao_total >= 0 else "#ef4444"
        var_sinal = "+" if variacao_total >= 0 else ""
        var_pct_total = (variacao_total / patrimonio_custo * 100) if patrimonio_custo > 0 else 0.0

        top_cards = ft.Row(spacing=15, controls=[
            criar_card_resumo("💰 Saldo Disponível", saldo_disponivel, "#3b82f6"),
            criar_card_resumo("📊 Patrimônio (Custo)", patrimonio_custo, "#a78bfa"),
            ft.Container(
                expand=True, bgcolor="#1e293b", border_radius=12, padding=20,
                content=ft.Column(spacing=4, controls=[
                    ft.Text("💎 Valor de Mercado", size=14, color="#94a3b8", weight=ft.FontWeight.W_500),
                    ft.Text(fmt(valor_mercado), size=28, color="#10b981", weight=ft.FontWeight.BOLD),
                    ft.Text(
                        f"{var_sinal}{fmt(abs(variacao_total))}  ({var_sinal}{var_pct_total:.1f}%)",
                        size=12, color=var_cor_total
                    )
                ])
            ),
            criar_card_resumo("🎯 Dividendos do Mês", dividendos, "#fbbf24"),
        ])

        # ── TAB SWITCHER ─────────────────────────────────────────────
        def make_tab_inv(label, icon_name, tab_name):
            active = tab_active == tab_name
            return ft.Container(
                content=ft.Row([
                    ft.Icon(icon_name, color="white" if active else "#64748b", size=16),
                    ft.Text(label, size=12, color="white" if active else "#64748b", weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                padding=ft.Padding(20, 12, 20, 12),
                bgcolor="#1e293b" if active else "transparent",
                border_radius=10, expand=True, ink=True,
                on_click=lambda e, t=tab_name: set_tab_inv(t)
            )

        tab_switcher_inv = ft.Container(
            bgcolor="#0f172a", border_radius=12, padding=5,
            content=ft.Row(spacing=5, controls=[
                make_tab_inv("CARTEIRA", ft.icons.Icons.PIE_CHART_OUTLINE_ROUNDED, "carteira"),
                make_tab_inv("COTAÇÕES EM TEMPO REAL", ft.icons.Icons.SHOW_CHART_ROUNDED, "cotacoes"),
            ])
        )

        # ── ABA: CARTEIRA ─────────────────────────────────────────────
        content_view_inv = ft.Container(expand=True)

        if tab_active == "carteira":
            if not posicoes_ativas:
                content_view_inv.content = ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED, size=60, color="#334155"),
                        ft.Text("Carteira vazia", size=16, color="#64748b", weight=ft.FontWeight.BOLD),
                        ft.Text("Clique em \"Nova Operação\" para registrar sua primeira compra.", size=12, color="#475569")
                    ]
                )
            else:
                left_items_inv = []
                right_items_inv = []

                for ticker, pos in sorted(posicoes_ativas.items()):
                    cor_tp = tipo_cores.get(pos["tipo"], "#475569")
                    cot_item = cotacoes_cache.get(ticker, {})
                    preco_cot_item = cot_item.get("preco")
                    preco_medio_item = pos["custo_total"] / pos["qtd"] if pos["qtd"] > 0 else 0.0
                    valor_inv_item = pos["custo_total"]
                    valor_merc_item = pos["qtd"] * preco_cot_item if preco_cot_item else valor_inv_item
                    var_item = ((valor_merc_item - valor_inv_item) / valor_inv_item * 100) if valor_inv_item > 0 else 0.0
                    var_cor_item = "#10b981" if var_item >= 0 else "#ef4444"

                    left_items_inv.append(
                        ft.Container(
                            padding=ft.Padding(12, 10, 12, 10),
                            bgcolor="#0f172a", border_radius=8,
                            border=ft.Border(left=ft.BorderSide(3, cor_tp)),
                            ink=True,
                            on_click=lambda e, tk=ticker, p=pos: mostrar_operacoes_ticker(tk, p),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(controls=[
                                        ft.Container(
                                            width=52, height=36, bgcolor=cor_tp + "22",
                                            border_radius=6, alignment=ft.alignment.center,
                                            content=ft.Text(ticker[:6], size=11, weight=ft.FontWeight.BOLD,
                                                            color=cor_tp, text_align=ft.TextAlign.CENTER)
                                        ),
                                        ft.Container(width=8),
                                        ft.Column(spacing=1, controls=[
                                            ft.Row([
                                                ft.Text(ticker, size=13, weight=ft.FontWeight.BOLD, color="white"),
                                                ft.Container(
                                                    padding=ft.Padding(4, 1, 4, 1),
                                                    bgcolor=cor_tp + "22", border_radius=4,
                                                    content=ft.Text(pos["tipo"], size=9, color=cor_tp, weight=ft.FontWeight.W_600)
                                                )
                                            ], spacing=6),
                                            ft.Text(f"{pos['qtd']:,.0f} un  •  PM: {fmt(preco_medio_item)}",
                                                    size=11, color="#64748b")
                                        ])
                                    ]),
                                    ft.Column(spacing=1, horizontal_alignment=ft.CrossAxisAlignment.END, controls=[
                                        ft.Text(fmt(valor_merc_item), size=13, weight=ft.FontWeight.BOLD, color="white"),
                                        ft.Text(f"{'+' if var_item >= 0 else ''}{var_item:.1f}%",
                                                size=11, color=var_cor_item, weight=ft.FontWeight.W_600)
                                    ])
                                ]
                            )
                        )
                    )

                # Composição por tipo
                total_port = valor_mercado if valor_mercado > 0 else patrimonio_custo
                tipos_presentes = {}
                for tk, pos in posicoes_ativas.items():
                    cot_p2 = cotacoes_cache.get(tk, {}).get("preco")
                    val2 = pos["qtd"] * cot_p2 if cot_p2 else pos["custo_total"]
                    tipos_presentes[pos["tipo"]] = tipos_presentes.get(pos["tipo"], 0) + val2

                for tipo in [t for t in tipo_ordem if t in tipos_presentes]:
                    cor = tipo_cores[tipo]
                    val = tipos_presentes[tipo]
                    pct = (val / total_port * 100) if total_port > 0 else 0
                    right_items_inv.append(
                        ft.Container(
                            padding=ft.Padding(12, 10, 12, 10),
                            bgcolor="#0f172a", border_radius=8,
                            content=ft.Column(spacing=6, controls=[
                                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                    ft.Row([
                                        ft.Container(width=10, height=10, bgcolor=cor, border_radius=2),
                                        ft.Text(tipo, size=13, weight=ft.FontWeight.W_600, color="white")
                                    ], spacing=8),
                                    ft.Column(spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END, controls=[
                                        ft.Text(fmt(val), size=13, weight=ft.FontWeight.BOLD, color="white"),
                                        ft.Text(f"{pct:.1f}%", size=11, color=cor)
                                    ])
                                ]),
                                ft.Container(
                                    height=6, border_radius=3, bgcolor="#1e293b",
                                    content=ft.Row(spacing=0, controls=[
                                        ft.Container(expand=max(1, int(pct)), height=6, bgcolor=cor, border_radius=3),
                                        ft.Container(expand=max(0, 100 - int(pct)))
                                    ])
                                )
                            ])
                        )
                    )

                content_view_inv.content = ft.Row(expand=True, spacing=20, controls=[
                    ft.Container(
                        expand=True, bgcolor="#1e293b", border_radius=12,
                        padding=ft.Padding(15, 10, 15, 12),
                        content=ft.Column(expand=True, controls=[
                            ft.Row([
                                ft.Icon(ft.icons.Icons.TRENDING_UP_ROUNDED, color="#3b82f6", size=16),
                                ft.Text("MINHA CARTEIRA", size=12, weight=ft.FontWeight.BOLD, color="white"),
                                ft.Container(expand=True),
                                ft.Text(f"{len(posicoes_ativas)} ativo(s)", size=11, color="#64748b")
                            ], spacing=6),
                            ft.Divider(color="#334155", height=1),
                            ft.ListView(expand=True, spacing=8,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=left_items_inv)
                        ])
                    ),
                    ft.Container(
                        expand=True, bgcolor="#1e293b", border_radius=12,
                        padding=ft.Padding(15, 10, 15, 12),
                        content=ft.Column(expand=True, controls=[
                            ft.Row([
                                ft.Icon(ft.icons.Icons.DONUT_LARGE_ROUNDED, color="#a78bfa", size=16),
                                ft.Text("COMPOSIÇÃO DA CARTEIRA", size=12, weight=ft.FontWeight.BOLD, color="white")
                            ], spacing=6),
                            ft.Divider(color="#334155", height=1),
                            ft.ListView(expand=True, spacing=8,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=right_items_inv if right_items_inv else [ft.Text("Sem dados.", color="#64748b", size=12)])
                        ])
                    )
                ])

        # ── ABA: COTAÇÕES ─────────────────────────────────────────────
        else:
            status_map = {
                "online":  (ft.icons.Icons.WIFI_ROUNDED,     "#10b981", "Online"),
                "offline": (ft.icons.Icons.WIFI_OFF_ROUNDED, "#ef4444", "Sem conexão"),
                "idle":    (ft.icons.Icons.SYNC_ROUNDED,     "#94a3b8", "Atualizando..."),
            }
            s_icon, s_color, s_text = status_map.get(cotacoes_status, status_map["idle"])

            cotacao_cards = []
            for ticker, pos in posicoes_ativas.items():
                cot_c = cotacoes_cache.get(ticker, {})
                preco_cot_c = cot_c.get("preco")
                variacao_cot = cot_c.get("variacao")
                nome_cot = cot_c.get("nome", ticker)
                cor_tp = tipo_cores.get(pos["tipo"], "#3b82f6")
                preco_medio_c = pos["custo_total"] / pos["qtd"] if pos["qtd"] > 0 else 0.0

                if preco_cot_c is not None:
                    v_cor_c = "#10b981" if (variacao_cot or 0) >= 0 else "#ef4444"
                    v_str_c = f"{'+' if (variacao_cot or 0) >= 0 else ''}{variacao_cot:.2f}%" if variacao_cot is not None else "—"
                    preco_str_c = fmt(preco_cot_c)
                    pnl_c = pos["qtd"] * preco_cot_c - pos["custo_total"]
                    pnl_cor_c = "#10b981" if pnl_c >= 0 else "#ef4444"
                    pnl_str_c = f"{'+' if pnl_c >= 0 else ''}{fmt(abs(pnl_c))}"
                else:
                    v_cor_c = "#64748b"; v_str_c = "Sem cotação"
                    preco_str_c = "—"; pnl_str_c = "—"; pnl_cor_c = "#64748b"

                cotacao_cards.append(
                    ft.Container(
                        padding=ft.Padding(16, 12, 16, 12),
                        bgcolor="#0f172a", border_radius=10,
                        border=ft.Border(left=ft.BorderSide(3, cor_tp)),
                        content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                            ft.Column(spacing=3, controls=[
                                ft.Row([
                                    ft.Text(ticker, size=15, weight=ft.FontWeight.BOLD, color="white"),
                                    ft.Container(
                                        padding=ft.Padding(4, 1, 4, 1), bgcolor=cor_tp + "22", border_radius=4,
                                        content=ft.Text(pos["tipo"], size=9, color=cor_tp, weight=ft.FontWeight.W_600)
                                    )
                                ], spacing=8),
                                ft.Text(nome_cot[:45], size=11, color="#64748b",
                                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(f"{pos['qtd']:,.0f} un  •  PM: {fmt(preco_medio_c)}", size=11, color="#475569")
                            ]),
                            ft.Column(spacing=3, horizontal_alignment=ft.CrossAxisAlignment.END, controls=[
                                ft.Text(preco_str_c, size=20, weight=ft.FontWeight.BOLD, color="white"),
                                ft.Text(v_str_c, size=13, color=v_cor_c, weight=ft.FontWeight.W_600),
                                ft.Text(f"P&L: {pnl_str_c}", size=11, color=pnl_cor_c)
                            ])
                        ])
                    )
                )

            cotacoes_bar = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Row([
                    ft.Icon(s_icon, color=s_color, size=16),
                    ft.Text(s_text, size=13, color=s_color, weight=ft.FontWeight.W_500)
                ], spacing=6),
                ft.ElevatedButton(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.REFRESH_ROUNDED, size=14, color="white"),
                        ft.Text("ATUALIZAR", size=11, color="white", weight=ft.FontWeight.BOLD)
                    ], spacing=5),
                    bgcolor="#1e293b",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: threading.Thread(target=buscar_cotacoes, daemon=True).start()
                )
            ])

            if not posicoes_ativas:
                cotacoes_inner = ft.Column(
                    expand=True, alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.icons.Icons.SHOW_CHART_ROUNDED, size=60, color="#334155"),
                        ft.Text("Nenhum ativo na carteira", size=16, color="#64748b", weight=ft.FontWeight.BOLD),
                        ft.Text("Adicione ativos na aba Carteira para ver cotações.", size=12, color="#475569")
                    ]
                )
            else:
                cotacoes_inner = ft.Column(expand=True, controls=[
                    cotacoes_bar,
                    ft.Container(height=12),
                    ft.ListView(expand=True, spacing=8,
                                padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                controls=cotacao_cards)
                ])

            content_view_inv.content = ft.Container(
                expand=True, bgcolor="#1e293b", border_radius=12, padding=20,
                content=cotacoes_inner
            )

        # ── MONTAGEM FINAL ────────────────────────────────────────────
        investimentos_layout = ft.Column(expand=True, controls=[
            header_row,
            ft.Container(height=10),
            top_cards,
            ft.Container(height=15),
            tab_switcher_inv,
            ft.Container(height=15),
            content_view_inv
        ])

        page.floating_action_button = None
        body.content = investimentos_layout
        page.update()

    def render_transacoes():
        mes_atual = meses_pt[state["mes_idx"]]
        ano_atual = str(state["ano"])
        view_mode = state["transacoes_view_mode"]
        tab_active = state["transacoes_tab_active"]
        locked = state.get("transacoes_locked", True)

        if view_mode == "mensal":
            transacoes = db.get_transacoes(mes=mes_atual, ano=ano_atual, perfil_nome=state["perfil"])
        else:
            transacoes = db.get_transacoes(mes=None, ano=ano_atual, perfil_nome=state["perfil"])

        cartoes = db.get_cartoes()
        card_map = {}
        card_colors = {}
        for c in cartoes:
            key = f"{c[6]}|{c[7]}"
            card_map[key] = c[1]
            card_colors[key] = c[5] if c[5] else "#3b82f6"

        # Edit Lock Toggle Button
        lock_icon = ft.icons.Icons.EDIT_ROUNDED if locked else ft.icons.Icons.EDIT_OFF_ROUNDED
        lock_color = "#94a3b8" if locked else "#fbbf24"
        lock_tooltip = "Habilitar Edição (Destravar)" if locked else "Concluir Edição (Bloquear)"

        def toggle_transacoes_lock(e):
            state["transacoes_locked"] = not state.get("transacoes_locked", True)
            render_transacoes()

        btn_lock = ft.IconButton(
            icon=lock_icon,
            icon_color=lock_color,
            tooltip=lock_tooltip,
            icon_size=20,
            on_click=toggle_transacoes_lock
        )

        def show_locked_notification():
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Visualização ativa. Clique no cadeado dourado no topo para destravar a edição! 🔓🔒", color="white"),
                bgcolor="#fb923c"
            )
            page.snack_bar.open = True
            page.update()

        btn_mensal = ft.Container(
            content=ft.Text("MENSAL", size=11, color="white" if view_mode == "mensal" else "#94a3b8", weight=ft.FontWeight.BOLD),
            padding=ft.Padding(16, 8, 16, 8),
            bgcolor="#2563eb" if view_mode == "mensal" else "transparent",
            border_radius=8,
            on_click=lambda e: set_transacoes_view_mode("mensal")
        )
        btn_anual = ft.Container(
            content=ft.Text("ANUAL", size=11, color="white" if view_mode == "anual" else "#94a3b8", weight=ft.FontWeight.BOLD),
            padding=ft.Padding(16, 8, 16, 8),
            bgcolor="#2563eb" if view_mode == "anual" else "transparent",
            border_radius=8,
            on_click=lambda e: set_transacoes_view_mode("anual")
        )
        segmented_control = ft.Container(
            bgcolor="#0f172a",
            border_radius=10,
            padding=2,
            content=ft.Row(
                spacing=0,
                controls=[btn_mensal, btn_anual]
            )
        )

        date_label = f"{mes_atual} {ano_atual}" if view_mode == "mensal" else f"{ano_atual}"
        date_icon = ft.icons.Icons.CALENDAR_MONTH_ROUNDED if view_mode == "mensal" else ft.icons.Icons.CALENDAR_TODAY_ROUNDED

        date_navigator = ft.Row(
            spacing=5,
            controls=[
                ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", on_click=prev_month),
                ft.Container(
                    bgcolor="#1e293b",
                    padding=ft.Padding(15, 8, 15, 8),
                    border_radius=20,
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            ft.Icon(date_icon, color="#94a3b8", size=18),
                            ft.Text(date_label, size=16, weight=ft.FontWeight.W_500, color="#94a3b8")
                        ]
                    )
                ),
                ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", on_click=next_month),
            ]
        )

        header_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text("Transações", size=24, weight=ft.FontWeight.BOLD, color="white"),
                ft.Row(
                    spacing=15,
                    controls=[
                        btn_lock,
                        segmented_control,
                        date_navigator
                    ]
                )
            ]
        )

        tab_pilar = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.LIST_ROUNDED, color="white" if tab_active == "pilar_categoria" else "#64748b", size=18),
                ft.Text("POR PILAR & CATEGORIA", size=12, color="white" if tab_active == "pilar_categoria" else "#64748b", weight=ft.FontWeight.BOLD),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            padding=ft.Padding(20, 12, 20, 12),
            bgcolor="#1e293b" if tab_active == "pilar_categoria" else "transparent",
            border_radius=10,
            expand=True,
            ink=True,
            on_click=lambda e: set_transacoes_tab("pilar_categoria")
        )

        tab_pagamento = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.CREDIT_CARD_ROUNDED, color="white" if tab_active == "forma_pagamento" else "#64748b", size=18),
                ft.Text("POR FORMA DE PAGAMENTO", size=12, color="white" if tab_active == "forma_pagamento" else "#64748b", weight=ft.FontWeight.BOLD),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            padding=ft.Padding(20, 12, 20, 12),
            bgcolor="#1e293b" if tab_active == "forma_pagamento" else "transparent",
            border_radius=10,
            expand=True,
            ink=True,
            on_click=lambda e: set_transacoes_tab("forma_pagamento")
        )

        tab_switcher = ft.Container(
            bgcolor="#0f172a",
            border_radius=12,
            padding=5,
            content=ft.Row(
                spacing=5,
                controls=[tab_pilar, tab_pagamento]
            )
        )

        content_view = ft.Container(
            expand=True,
            bgcolor="#1e293b",
            border_radius=12,
            padding=20,
        )

        if not transacoes:
            content_view.content = ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.icons.Icons.INBOX_ROUNDED, size=60, color="#334155"),
                    ft.Text("Nenhuma transação encontrada", size=16, color="#64748b", weight=ft.FontWeight.BOLD),
                    ft.Text("Os lançamentos deste período aparecerão aqui.", size=12, color="#475569")
                ]
            )
        else:
            if tab_active == "pilar_categoria":
                left_column_items = []
                right_column_items = []
                
                pilar_groups = {}
                for t in transacoes:
                    pilar = t[5].strip()
                    cat = t[4].strip().title()
                    
                    if pilar not in pilar_groups:
                        pilar_groups[pilar] = {}
                    if cat not in pilar_groups[pilar]:
                        pilar_groups[pilar][cat] = []
                    pilar_groups[pilar][cat].append(t)

                for pilar_nome, categories_dict in pilar_groups.items():
                    pilar_total = sum(t[3] for cats in categories_dict.values() for t in cats)
                    
                    is_revenue_investment = ("Receita" in pilar_nome) or ("Investimento" in pilar_nome)
                    target_list = left_column_items if is_revenue_investment else right_column_items

                    if "Receita" in pilar_nome:
                        pilar_color = "#10b981"
                        indicator_color = "#10b981"
                    elif "Investimento" in pilar_nome:
                        pilar_color = "#3b82f6"
                        indicator_color = "#3b82f6"
                    else:
                        pilar_color = "#ef4444"
                        indicator_color = "#ef4444"

                    target_list.append(
                        ft.Container(
                            margin=ft.Margin(0, 10, 0, 5),
                            padding=ft.Padding(12, 8, 12, 8),
                            bgcolor="#0f172a",
                            border_radius=8,
                            border=ft.Border(left=ft.BorderSide(3, indicator_color)),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(pilar_nome.upper(), size=12, weight=ft.FontWeight.BOLD, color="white"),
                                    ft.Text(f"Total: R$ {pilar_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, weight=ft.FontWeight.BOLD, color=pilar_color)
                                ]
                            )
                        )
                    )

                    for cat_nome, t_list in categories_dict.items():
                        cat_total = sum(t[3] for t in t_list)
                        target_list.append(
                            ft.Container(
                                padding=ft.Padding(15, 6, 15, 2),
                                content=ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(cat_nome, size=11, weight=ft.FontWeight.W_600, color="#94a3b8"),
                                        ft.Text(f"R$ {cat_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=11, color="#64748b")
                                    ]
                                )
                            )
                        )

                        for t in t_list:
                            t_id = t[0]
                            t_data = t[1]
                            t_desc = t[2]
                            t_valor = t[3]
                            t_tipo = t[5]
                            t_metodo = t[8]
                            t_dono = t[9]
                            t_band = t[10]
                            t_divisoes = t[11]

                            subtitle_parts = [t_data]
                            if t_metodo == "Cartão":
                                card_display_name = "Cartão"
                                if t_band and t_dono:
                                    card_display_name = card_map.get(f"{t_band}|{t_dono}", f"Cartão {t_dono} ({t_band})")
                                subtitle_parts.append(card_display_name)
                                if t[6] and t[7] and t[7] > 1:
                                    subtitle_parts.append(f"Parc. {t[6]}/{t[7]}")
                            else:
                                if t_metodo:
                                    subtitle_parts.append(t_metodo)

                            if t_divisoes and t_divisoes > 0:
                                subtitle_parts.append("Dividido 👥")

                            subtitle_text = " • ".join(subtitle_parts)

                            if locked:
                                def get_show_locked_msg(tid=t_id):
                                    return lambda e: show_locked_notification()
                                click_handler = get_show_locked_msg()
                                row_bg = "transparent"
                                row_border = ft.Border(bottom=ft.BorderSide(1, "#334155"))
                                row_padding = ft.Padding(5, 8, 5, 8)
                                row_radius = 0
                                value_controls = [
                                    ft.Text(f"R$ {t_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=13, weight=ft.FontWeight.BOLD, color=pilar_color)
                                ]
                            else:
                                def get_open_overlay(tid=t_id, tipo_t=t_tipo):
                                    return lambda e: abrir_overlay(
                                        "despesa" if "despesa" in tipo_t.lower() else ("investimento" if tipo_t.lower() == "investimento" else "receita"),
                                        editing_trans_id=tid
                                    )
                                click_handler = get_open_overlay()
                                row_bg = "#0f172a"
                                row_border = None
                                row_padding = ft.Padding(15, 8, 15, 8)
                                row_radius = 8
                                value_controls = [
                                    ft.Text(f"R$ {t_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=13, weight=ft.FontWeight.BOLD, color=pilar_color),
                                    ft.Icon(ft.icons.Icons.EDIT_ROUNDED, color="#64748b", size=13)
                                ]

                            target_list.append(
                                ft.Container(
                                    padding=row_padding,
                                    border_radius=row_radius,
                                    bgcolor=row_bg,
                                    border=row_border,
                                    ink=True,
                                    on_click=click_handler,
                                    content=ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Row(
                                                expand=True,
                                                controls=[
                                                    ft.Container(
                                                        padding=6,
                                                        bgcolor="#1e293b",
                                                        border_radius=6,
                                                        content=ft.Icon(get_icone_categoria(t[4]), color=indicator_color, size=16)
                                                    ),
                                                    ft.Container(width=5),
                                                    ft.Column(
                                                        expand=True,
                                                        spacing=1,
                                                        controls=[
                                                            ft.Text(t_desc, size=13, weight=ft.FontWeight.W_500, color="white", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                                            ft.Text(subtitle_text, size=11, color="#64748b", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                                                        ]
                                                    )
                                                ]
                                            ),
                                            ft.Row(controls=value_controls, spacing=5, alignment=ft.MainAxisAlignment.END)
                                        ]
                                    )
                                )
                            )

                content_view.content = ft.Row(
                    expand=True,
                    spacing=20,
                    controls=[
                        # Coluna Esquerda: Despesas Gerais
                        ft.Container(
                            expand=True,
                            bgcolor="#1e293b",
                            border_radius=12,
                            padding=ft.Padding(left=15, right=15, top=10, bottom=12),
                            content=ft.Column(
                                expand=True,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.icons.Icons.ARROW_DOWNWARD_ROUNDED, color="#ef4444", size=16),
                                        ft.Text("DESPESAS GERAIS", size=12, weight=ft.FontWeight.BOLD, color="white")
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=right_column_items if right_column_items else [ft.Text("Nenhuma despesa neste período.", color="#64748b", size=12)]
                                    )
                                ]
                            )
                        ),
                        # Coluna Direita: Receitas & Investimentos
                        ft.Container(
                            expand=True,
                            bgcolor="#1e293b",
                            border_radius=12,
                            padding=ft.Padding(left=15, right=15, top=10, bottom=12),
                            content=ft.Column(
                                expand=True,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.icons.Icons.ARROW_UPWARD_ROUNDED, color="#10b981", size=16),
                                        ft.Text("RECEITAS & APORTES", size=12, weight=ft.FontWeight.BOLD, color="white")
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=left_column_items if left_column_items else [ft.Text("Nenhuma receita ou aporte neste período.", color="#64748b", size=12)]
                                    )
                                ]
                            )
                        )
                    ]
                )
            else:
                left_payment_items = []
                right_payment_items = []
                
                despesas_list = [t for t in transacoes if "Despesa" in t[5]]
                metodo_groups = {}
                for t in despesas_list:
                    metodo = t[8]
                    if not metodo:
                        metodo = "Não especificado"
                        
                    if metodo == "Cartão":
                        t_band = t[10]
                        t_dono = t[9]
                        card_name = card_map.get(f"{t_band}|{t_dono}", f"Cartão {t_dono} ({t_band})" if (t_band and t_dono) else "Cartão de Crédito")
                        group_key = f"Cartão {card_name}"
                    else:
                        group_key = metodo
                        
                    if group_key not in metodo_groups:
                        metodo_groups[group_key] = []
                    metodo_groups[group_key].append(t)

                sorted_keys = sorted(metodo_groups.keys())
                for group_key in sorted_keys:
                    t_list = metodo_groups[group_key]
                    group_total = sum(t[3] for t in t_list)

                    is_card = "Cartão" in group_key
                    target_list = left_payment_items if is_card else right_payment_items

                    if is_card:
                        indicator_color = "#fb923c"
                        for key, name in card_map.items():
                            if name in group_key:
                                indicator_color = card_colors.get(key, "#fb923c")
                                break
                    elif "Pix" in group_key:
                        indicator_color = "#a78bfa"
                    elif "Dinheiro" in group_key:
                        indicator_color = "#10b981"
                    else:
                        indicator_color = "#64748b"

                    target_list.append(
                        ft.Container(
                            margin=ft.Margin(0, 10, 0, 5),
                            padding=ft.Padding(12, 8, 12, 8),
                            bgcolor="#0f172a",
                            border_radius=8,
                            border=ft.Border(left=ft.BorderSide(3, indicator_color)),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row([
                                        ft.Icon(
                                            ft.icons.Icons.CREDIT_CARD_ROUNDED if is_card 
                                            else (ft.icons.Icons.QR_CODE_2_ROUNDED if "Pix" in group_key 
                                                  else (ft.icons.Icons.ATTACH_MONEY_ROUNDED if "Dinheiro" in group_key 
                                                        else ft.icons.Icons.PAYMENT_ROUNDED)), 
                                            color="white", size=16
                                        ),
                                        ft.Text(group_key.upper(), size=12, weight=ft.FontWeight.BOLD, color="white")
                                    ], spacing=8),
                                    ft.Text(f"Total: R$ {group_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, weight=ft.FontWeight.BOLD, color=indicator_color)
                                ]
                            )
                        )
                    )

                    for t in t_list:
                        t_id = t[0]
                        t_data = t[1]
                        t_desc = t[2]
                        t_valor = t[3]
                        t_cat = t[4].strip().title()
                        t_tipo = t[5]
                        t_divisoes = t[11]

                        subtitle_parts = [t_data, t_cat]
                        if t[6] and t[7] and t[7] > 1:
                            subtitle_parts.append(f"Parc. {t[6]}/{t[7]}")
                        if t_divisoes and t_divisoes > 0:
                            subtitle_parts.append("Dividido 👥")

                        subtitle_text = " • ".join(subtitle_parts)

                        if locked:
                            def get_show_locked_msg(tid=t_id):
                                return lambda e: show_locked_notification()
                            click_handler = get_show_locked_msg()
                            row_bg = "transparent"
                            row_border = ft.Border(bottom=ft.BorderSide(1, "#334155"))
                            row_padding = ft.Padding(5, 8, 5, 8)
                            row_radius = 0
                            value_controls = [
                                ft.Text(f"R$ {t_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=13, weight=ft.FontWeight.BOLD, color="#ef4444")
                            ]
                        else:
                            def get_open_overlay(tid=t_id, tipo_t=t_tipo):
                                return lambda e: abrir_overlay(
                                    "despesa" if "despesa" in tipo_t.lower() else ("investimento" if tipo_t.lower() == "investimento" else "receita"),
                                    editing_trans_id=tid
                                )
                            click_handler = get_open_overlay()
                            row_bg = "#0f172a"
                            row_border = None
                            row_padding = ft.Padding(15, 8, 15, 8)
                            row_radius = 8
                            value_controls = [
                                ft.Text(f"R$ {t_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=13, weight=ft.FontWeight.BOLD, color="#ef4444"),
                                ft.Icon(ft.icons.Icons.EDIT_ROUNDED, color="#64748b", size=13)
                            ]

                        target_list.append(
                            ft.Container(
                                padding=row_padding,
                                border_radius=row_radius,
                                bgcolor=row_bg,
                                border=row_border,
                                ink=True,
                                on_click=click_handler,
                                content=ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Row(
                                            expand=True,
                                            controls=[
                                                ft.Container(
                                                    padding=6,
                                                    bgcolor="#1e293b",
                                                    border_radius=6,
                                                    content=ft.Icon(get_icone_categoria(t[4]), color="#ef4444", size=16)
                                                ),
                                                ft.Container(width=5),
                                                ft.Column(
                                                    expand=True,
                                                    spacing=1,
                                                    controls=[
                                                        ft.Text(t_desc, size=13, weight=ft.FontWeight.W_500, color="white", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                                        ft.Text(subtitle_text, size=11, color="#64748b", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                                                    ]
                                                )
                                            ]
                                        ),
                                        ft.Row(controls=value_controls, spacing=5, alignment=ft.MainAxisAlignment.END)
                                    ]
                                )
                            )
                        )

                # Layout Aba 2: Duas Colunas
                content_view.content = ft.Row(
                    expand=True,
                    spacing=20,
                    controls=[
                        # Coluna Esquerda: Cartões de Crédito
                        ft.Container(
                            expand=True,
                            bgcolor="#1e293b",
                            border_radius=12,
                            padding=ft.Padding(left=15, right=15, top=10, bottom=12),
                            content=ft.Column(
                                expand=True,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.icons.Icons.CREDIT_CARD_ROUNDED, color="#fb923c", size=16),
                                        ft.Text("CARTÕES DE CRÉDITO", size=12, weight=ft.FontWeight.BOLD, color="white")
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=left_payment_items if left_payment_items else [ft.Text("Sem gastos no cartão neste período.", color="#64748b", size=12)]
                                    )
                                ]
                            )
                        ),
                        # Coluna Direita: Outras Formas
                        ft.Container(
                            expand=True,
                            bgcolor="#1e293b",
                            border_radius=12,
                            padding=ft.Padding(left=15, right=15, top=10, bottom=12),
                            content=ft.Column(
                                expand=True,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.icons.Icons.PAYMENT_ROUNDED, color="#a78bfa", size=16),
                                        ft.Text("OUTRAS FORMAS DE PAGAMENTO", size=12, weight=ft.FontWeight.BOLD, color="white")
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=right_payment_items if right_payment_items else [ft.Text("Sem outros gastos neste período.", color="#64748b", size=12)]
                                    )
                                ]
                            )
                        )
                    ]
                )

        trans_layout = ft.Column(
            expand=True,
            controls=[
                header_row,
                ft.Container(height=15),
                tab_switcher,
                ft.Container(height=15),
                content_view
            ]
        )

        page.floating_action_button = None
        body.content = trans_layout
        page.update()

    def set_transacoes_view_mode(mode):
        state["transacoes_view_mode"] = mode
        render_transacoes()

    def set_transacoes_tab(tab):
        state["transacoes_tab_active"] = tab
        render_transacoes()

    render_dashboard()
    
    main_row = ft.Row(
        expand=True,
        spacing=0,
        controls=[
            sidebar,
            body
        ]
    )
    overlay_stack = ft.Stack(
        expand=True,
        alignment=ft.Alignment(0, 0),
        controls=[
            main_row
        ]
    )
    page.add(overlay_stack)
    page.update()

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ft.run(main, assets_dir=base_dir)
