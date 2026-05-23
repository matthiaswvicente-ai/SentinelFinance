import flet as ft
import sys
import os
import datetime
import io
import base64
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
        "form_vencimento": ""
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
                ft.IconButton(icon=ft.icons.Icons.PIE_CHART_ROUNDED, tooltip="Gráficos", icon_color="#64748b", icon_size=24, on_click=on_nav_click),
                ft.IconButton(icon=ft.icons.Icons.CREDIT_CARD_ROUNDED, tooltip="Cartões", icon_color="#64748b", icon_size=24, on_click=on_nav_click),
                ft.IconButton(icon=ft.icons.Icons.LIST_ALT_ROUNDED, tooltip="Transações", icon_color="#64748b", icon_size=24, on_click=on_nav_click),
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
            icone_cor = "#ef4444" if eh_despesa else "#10b981"
            icone_tipo = get_icone_categoria(cat)
            
            itens.append(
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor="#0f172a",
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        padding=10,
                                        bgcolor="#1e293b",
                                        border_radius=8,
                                        content=ft.Icon(icone_tipo, color=icone_cor, size=20)
                                    ),
                                    ft.Container(width=10),
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text(desc, size=14, weight=ft.FontWeight.BOLD, color="white"),
                                            ft.Text(f"{data_str} • {cat}", size=12, color="#64748b")
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
        state["mes_idx"] -= 1
        if state["mes_idx"] < 0:
            state["mes_idx"] = 11
            state["ano"] -= 1
        if state["active_tab"] == "cartoes":
            render_cartoes()
        else:
            render_dashboard()
        
    def next_month(e):
        state["mes_idx"] += 1
        if state["mes_idx"] > 11:
            state["mes_idx"] = 0
            state["ano"] += 1
        if state["active_tab"] == "cartoes":
            render_cartoes()
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
        lista_receitas = [t for t in todas_transacoes if "Receita" in t[5]]

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
        page.floating_action_button = ft.FloatingActionButton(
            icon=ft.icons.Icons.ADD,
            bgcolor="#3b82f6",
            on_click=fab_click,
            tooltip="Novo Lançamento"
        )
        
        body.content = dashboard_view
        page.update()
        
    def render_cartoes():
        mes_atual_pt = meses_pt[state["mes_idx"]]
        mes_num = str(state["mes_idx"] + 1).zfill(2)
        ano_atual = str(state["ano"])
        
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
            label="Dia do Fechamento (1-31)",
            hint_text="Ex: 5",
            value=state.get("form_fechamento", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a"
        )
        txt_vencimento = ft.TextField(
            label="Dia do Vencimento (1-31)",
            hint_text="Ex: 12",
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
                state["form_nome"] = card[1]
                state["form_limite"] = str(card[2])
                state["form_fechamento"] = str(card[3])
                state["form_vencimento"] = str(card[4])
                state["form_bandeira"] = card[6]
                state["form_dono"] = card[7]
                state["form_digitos"] = card[8] if len(card) > 8 else "1234"
                render_cartoes()

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
            state["form_nome"] = txt_nome.value
            state["form_dono"] = txt_dono.value
            state["form_bandeira"] = txt_bandeira.value
            state["form_limite"] = txt_limite.value
            state["form_fechamento"] = txt_fechamento.value
            state["form_vencimento"] = txt_vencimento.value
            state["form_digitos"] = txt_digitos.value
            render_cartoes()

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
        
        color_selectors = []
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

        # Form Setup
        form_title = "Cadastrar Novo Cartão"
        cancel_btn = ft.Container()
        
        if state["editing_card_id"] is not None:
            form_title = "Editar Cartão"
            
            def cancel_edit(e):
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
                
            cancel_btn = ft.TextButton(
                content="Cancelar",
                style=ft.ButtonStyle(color="#ef4444"),
                on_click=cancel_edit
            )

        form_panel = ft.Container(
            width=340,
            bgcolor="#1e293b",
            border_radius=12,
            padding=20,
            content=ft.Column(
                spacing=15,
                controls=[
                    ft.Text(form_title, size=18, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Divider(color="#334155"),
                    txt_nome,
                    txt_dono,
                    txt_bandeira,
                    txt_limite,
                    ft.Row(
                        controls=[
                            ft.Container(expand=True, content=txt_digitos),
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
                                content="Salvar",
                                bgcolor="#3b82f6",
                                color="white",
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

    render_dashboard()
    
    layout = ft.Row(
        expand=True,
        spacing=0,
        controls=[
            sidebar,
            body
        ]
    )
    
    def fab_click(e):
        # Text fields
        txt_desc = ft.TextField(label="Descrição", hint_text="Ex: Compras Supermercado", border_color="#475569", text_style=ft.TextStyle(color="white"), bgcolor="#0f172a")
        txt_valor = ft.TextField(label="Valor (R$)", hint_text="Ex: 150.50", border_color="#475569", text_style=ft.TextStyle(color="white"), bgcolor="#0f172a")
        txt_data = ft.TextField(label="Data (DD/MM/AAAA)", value=datetime.datetime.now().strftime("%d/%m/%Y"), border_color="#475569", text_style=ft.TextStyle(color="white"), bgcolor="#0f172a")
        txt_parcelas = ft.TextField(label="Parcelas", value="1", border_color="#475569", text_style=ft.TextStyle(color="white"), bgcolor="#0f172a", visible=False)
        txt_obs = ft.TextField(label="Observação (Opcional)", border_color="#475569", text_style=ft.TextStyle(color="white"), bgcolor="#0f172a")
        
        # Transaction Type
        drop_tipo = ft.Dropdown(
            label="Tipo",
            border_color="#475569",
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a",
            options=[
                ft.dropdown.Option("Despesa Fixa"),
                ft.dropdown.Option("Despesa Variável"),
                ft.dropdown.Option("Receita Fixa"),
                ft.dropdown.Option("Receita Variável"),
                ft.dropdown.Option("Investimento")
            ],
            value="Despesa Variável"
        )
        
        # Payment Method
        drop_metodo = ft.Dropdown(
            label="Método de Pagamento",
            border_color="#475569",
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a",
            options=[
                ft.dropdown.Option("Dinheiro"),
                ft.dropdown.Option("Pix"),
                ft.dropdown.Option("Boleto"),
                ft.dropdown.Option("Cartão de Crédito")
            ],
            value="Dinheiro",
            on_change=lambda e: toggle_card_fields()
        )
        
        # Credit Card Selectors
        cartoes = db.get_cartoes()
        card_options = []
        for c in cartoes:
            # card structure: id, nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, digitos
            card_id, c_nome, c_lim, c_fech, c_venc, c_cor, c_band, c_dono, c_dig = c
            card_options.append(ft.dropdown.Option(
                key=f"{c_band}|{c_dono}", 
                text=f"{c_nome} ({c_band} - {c_dono} •••• {c_dig})"
            ))
            
        drop_cartao = ft.Dropdown(
            label="Selecione o Cartão",
            border_color="#475569",
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a",
            options=card_options,
            visible=False
        )
        
        # Categories Dropdown
        cats = db.get_categorias()
        cat_options = []
        for cat in cats:
            c_id, c_nome, c_tipo, c_pid, c_has_sub = cat
            if not c_has_sub: # leaf
                cat_options.append(ft.dropdown.Option(key=str(c_id), text=f"{c_nome} ({c_tipo})"))
                
        drop_cat = ft.Dropdown(
            label="Categoria",
            border_color="#475569",
            text_style=ft.TextStyle(color="white"),
            bgcolor="#0f172a",
            options=cat_options
        )
        if cat_options:
            drop_cat.value = cat_options[0].key

        # Dynamic Visibility Handler for Card Selector
        def toggle_card_fields():
            is_card = drop_metodo.value == "Cartão de Crédito"
            drop_cartao.visible = is_card
            txt_parcelas.visible = is_card
            dialog.content.update()

        # Save Transaction Handler
        def salvar_lancamento(e):
            desc = (txt_desc.value or "").strip()
            valor_str = (txt_valor.value or "").strip()
            data_str = (txt_data.value or "").strip()
            tipo = drop_tipo.value
            metodo = drop_metodo.value
            cat_id_str = drop_cat.value
            parcelas_str = (txt_parcelas.value or "").strip()
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
                parcelas = int(parcelas_str) if metodo == "Cartão de Crédito" else 1
            except ValueError:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Valor ou número de parcelas inválido!", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return
                
            bandeira = ""
            dono = ""
            if metodo == "Cartão de Crédito":
                if not drop_cartao.value:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Por favor, selecione um cartão de crédito!", color="white"),
                        bgcolor="#ef4444"
                    )
                    page.snack_bar.open = True
                    page.update()
                    return
                parts = drop_cartao.value.split("|")
                bandeira = parts[0]
                dono = parts[1]
                
            success, msg = db.inserir_transacao(
                conta_id=None,
                categoria_id=int(cat_id_str),
                descricao=desc,
                data_ini=data_str,
                valor_total=valor,
                tipo_transacao=tipo,
                metodo=metodo,
                parcelas=parcelas,
                bandeira=bandeira,
                dono=dono,
                recorrencia=None,
                divisoes=None,
                observacao=obs
            )
            
            if success:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Lançamento adicionado com sucesso!", color="white"),
                    bgcolor="#10b981"
                )
                # Close Dialog
                dialog.open = False
                page.update()
                # Re-render dashboard
                render_dashboard()
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Erro ao salvar: {msg}", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()

        def fechar_dialog(e):
            dialog.open = False
            page.update()

        # Dialog structure
        dialog_content = ft.Container(
            width=400,
            height=450,
            content=ft.ListView(
                spacing=15,
                controls=[
                    txt_desc,
                    txt_valor,
                    txt_data,
                    drop_tipo,
                    drop_metodo,
                    drop_cartao,
                    txt_parcelas,
                    drop_cat,
                    txt_obs
                ]
            )
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Novo Lançamento", color="white", weight=ft.FontWeight.BOLD),
            content=dialog_content,
            bgcolor="#1e293b",
            actions=[
                ft.TextButton(content="Cancelar", on_click=fechar_dialog),
                ft.Button(
                    content="Salvar Lançamento",
                    bgcolor="#3b82f6",
                    color="white",
                    on_click=salvar_lancamento
                )
            ]
        )
        
        page.dialog = dialog
        dialog.open = True
        page.update()
    
    page.add(layout)
    page.update()

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ft.run(main, assets_dir=base_dir)
