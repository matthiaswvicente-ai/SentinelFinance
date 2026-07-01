import flet as ft
# Patch flet.controls.border to implement .all() if missing in this Flet version
if not hasattr(ft.border, "all"):
    ft.border.all = lambda w=None, c=None: ft.border.Border(
        top=ft.border.BorderSide(w, c),
        bottom=ft.border.BorderSide(w, c),
        left=ft.border.BorderSide(w, c),
        right=ft.border.BorderSide(w, c)
    )
import sys
import os
class UnbufferedStderr(object):
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
    def writelines(self, datas):
        self.stream.writelines(datas)
        self.stream.flush()
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

sys.stderr = UnbufferedStderr(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "flet_stderr.log"), "w", encoding="utf-8"))
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
from utils import shift_months
# Referência global para o ícone de bandeja (system tray)
# Referência global para o ícone de bandeja (system tray)
tray_icon = None

def main(page: ft.Page):
    import time
    
    # Configurações da Janela
    page.title = "Sentinel Finance V2"
    page.theme = ft.Theme(font_family="Segoe UI")
    page.padding = 0
    page.window_width = 1200
    page.window_height = 800
    page.window_min_width = 900
    page.window_min_height = 600
    
    # Inicializa BD com caminho absoluto local à pasta v2
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financas.db")
    db = Database(db_name=db_path)
    
    def _criar_backup_sessao():
        try:
            import datetime
            import shutil
            base_dir = os.path.dirname(os.path.abspath(db_path))
            backup_dir = os.path.join(base_dir, "session_backups")
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            # Limpa backups antigos de sessão (mantém por 7 dias)
            agora = datetime.datetime.now()
            limite = agora - datetime.timedelta(days=7)
            if os.path.exists(backup_dir):
                for f in os.listdir(backup_dir):
                    fpath = os.path.join(backup_dir, f)
                    if os.path.isfile(fpath) and f.startswith("backup_sessao_") and f.endswith(".db"):
                        try:
                            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
                            if mtime < limite:
                                os.remove(fpath)
                        except Exception:
                            pass
            
            # Cria o backup da sessão atual se o BD já existir
            if os.path.exists(db_path):
                timestamp = agora.strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(backup_dir, f"backup_sessao_{timestamp}.db")
                shutil.copy2(db_path, backup_file)
        except Exception as e:
            from logger import logger
            logger.error(f"Erro ao criar backup de sessão: {e}", exc_info=True)

    _criar_backup_sessao()
    
    # Inicialização dinâmica de tema e cor de fundo
    pref_theme = db.get_preferencia("theme_mode", "dark")
    page.theme_mode = ft.ThemeMode.LIGHT if pref_theme == "light" else ft.ThemeMode.DARK
    page.bgcolor = "#f8fafc" if pref_theme == "light" else "#0f172a"
    
    # Comportamento de fechar janela
    def on_window_event(e):
        if e.data == "close":
            os._exit(0)
                
    page.on_window_event = on_window_event
    
    # Roteador de Sandbox baseado em preferências persistidas do banco real
    original_prod_path = db_path
    if db.get_preferencia("use_sandbox", "False") == "True":
        db.switch_to_sandbox()
        
    def update_use_sandbox_preference(is_sandbox):
        try:
            import sqlite3
            conn = sqlite3.connect(original_prod_path)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS Preferencias (chave TEXT PRIMARY KEY, valor TEXT)")
            cursor.execute("INSERT OR REPLACE INTO Preferencias (chave, valor) VALUES (?, ?)", ("use_sandbox", "True" if is_sandbox else "False"))
            conn.commit()
            conn.close()
        except Exception as err:
            import logging
            logging.error(f"Erro ao salvar sandbox nas preferências do banco real: {err}")
    
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
        "language": db.get_preferencia("language", "pt")
    }
    
    from translations import TRANSLATIONS
    def _t(text):
        if not text:
            return ""
        lang = state.get("language", "pt")
        if lang == "pt":
            return text
        lang_dict = TRANSLATIONS.get(lang, {})
        return lang_dict.get(text, text)
    

    def build_safe_date(d, m, y):
        try:
            return datetime.datetime(y, m, d).strftime("%d/%m/%Y")
        except ValueError:
            for day_clamp in range(d - 1, 27, -1):
                try:
                    return datetime.datetime(y, m, day_clamp).strftime("%d/%m/%Y")
                except ValueError:
                    pass
            return f"28/{m:02d}/{y}"

    def get_colors():
        is_light = (page.theme_mode == ft.ThemeMode.LIGHT)
        return {
            "bg": "#f1f5f9" if is_light else "#0f172a",
            "surface": "#ffffff" if is_light else "#1e293b",
            "sidebar": "#ffffff" if is_light else "#1e293b",
            "text": "#0f172a" if is_light else "#ffffff",
            "subtext": "#334155" if is_light else "#cbd5e1",
            "border": "#cbd5e1" if is_light else "#334155",
            "card_bg": "#ffffff" if is_light else "#0f172a"
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
            page.window.icon = ico_path if os.path.exists(ico_path) else logo_path
        except:
            pass
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
        elif e.control.icon == ft.icons.Icons.SETTINGS_ROUNDED:
            state["active_tab"] = "configuracoes"
            render_configuracoes()
        elif e.control.icon == ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED:
            state["active_tab"] = "financiamentos"
            render_financiamentos()
        elif e.control.icon == ft.icons.Icons.AUTORENEW_ROUNDED:
            state["active_tab"] = "recorrencias"
            render_recorrencias()
        elif e.control.icon == ft.icons.Icons.ANALYTICS_ROUNDED:
            state["active_tab"] = "resumo_anual"
            render_resumo_anual()
        else:
            titulo = e.control.tooltip
            body.content = ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(e.control.icon, size=100, color="#334155"),
                    ft.Text(f"Módulo: {titulo}", size=24, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                    ft.Text("Em desenvolvimento...", size=16, color="#64748b")
                ]
            )
            page.update()

    def refresh_current_view(e=None):
        active = state.get("active_tab", "dashboard")
        if active == "dashboard" or active == "charts":
            render_dashboard()
        elif active == "cartoes":
            render_cartoes()
        elif active == "transacoes":
            render_transacoes()
        elif active == "investimentos":
            render_investimentos()
        elif active == "financiamentos":
            render_financiamentos()
        elif active == "configuracoes":
            render_configuracoes()
        elif active == "recorrencias":
            render_recorrencias()
        elif active == "resumo_anual":
            render_resumo_anual()
        elif active == "veiculos":
            render_veiculos()
        elif active == "pets":
            render_pets()
        elif active == "saude":
            render_saude()
        else:
            render_dashboard()

    def build_sidebar_controls():
        order_str = db.get_preferencia("sidebar_order", "dashboard,investimentos,charts,cartoes,financiamentos,recorrencias,ia")
        order = order_str.split(",")
        order = [item for item in order if item not in ("resumo_anual", "transacoes", "recorrencias")]
        
        items_map = {
            "dashboard": ft.IconButton(
                icon=ft.icons.Icons.DASHBOARD_ROUNDED,
                tooltip=_t("Dashboard"),
                icon_color="white" if state["active_tab"] == "dashboard" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            ),
            "investimentos": ft.IconButton(
                icon=ft.icons.Icons.SAVINGS_ROUNDED,
                tooltip=_t("Investimentos"),
                icon_color="white" if state["active_tab"] == "investimentos" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            ),
            "charts": ft.IconButton(
                icon=ft.icons.Icons.PIE_CHART_ROUNDED,
                tooltip=_t("Gráficos"),
                icon_color="white" if state["active_tab"] == "charts" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            ),
            "transacoes": ft.IconButton(
                icon=ft.icons.Icons.LIST_ALT_ROUNDED,
                tooltip=_t("Transações"),
                icon_color="white" if state["active_tab"] == "transacoes" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            ),
            "cartoes": ft.IconButton(
                icon=ft.icons.Icons.CREDIT_CARD_ROUNDED,
                tooltip=_t("Cartões"),
                icon_color="white" if state["active_tab"] == "cartoes" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            ),
            "financiamentos": ft.IconButton(
                icon=ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED,
                tooltip=_t("Financiamentos"),
                icon_color="white" if state["active_tab"] == "financiamentos" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            ),
            "recorrencias": ft.IconButton(
                icon=ft.icons.Icons.AUTORENEW_ROUNDED,
                tooltip=_t("Recorrências"),
                icon_color="white" if state["active_tab"] == "recorrencias" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            ),
            "resumo_anual": ft.IconButton(
                icon=ft.icons.Icons.ANALYTICS_ROUNDED,
                tooltip=_t("Resumo Anual"),
                icon_color="white" if state["active_tab"] == "resumo_anual" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            ),
            "ia": ft.IconButton(
                icon=ft.icons.Icons.AUTO_AWESOME_ROUNDED,
                tooltip=_t("Assistente IA"),
                icon_color="white" if state["active_tab"] == "ia" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            ),
        }
        
        controls = [logo_widget, ft.Divider(height=40, color="transparent")]
        for item_id in order:
            if item_id in items_map:
                controls.append(items_map[item_id])
                
        controls.append(ft.Container(expand=True))
        
        # Reorder Button
        controls.append(
            ft.IconButton(
                icon=ft.icons.Icons.SWAP_VERT_ROUNDED,
                tooltip=_t("Personalizar Menu"),
                icon_color="#64748b",
                icon_size=24,
                on_click=abrir_reordenar_menu
            )
        )
        
        # Refresh Button
        controls.append(
            ft.IconButton(
                icon=ft.icons.Icons.REFRESH_ROUNDED,
                tooltip=_t("Atualizar"),
                icon_color="#64748b",
                icon_size=24,
                on_click=refresh_current_view
            )
        )
        
        # Settings Button
        controls.append(
            ft.IconButton(
                icon=ft.icons.Icons.SETTINGS_ROUNDED,
                tooltip=_t("Configurações"),
                icon_color="white" if state["active_tab"] == "configuracoes" else "#64748b",
                icon_size=24,
                on_click=on_nav_click
            )
        )
        
        return controls

    def abrir_reordenar_menu(e):
        order_str = db.get_preferencia("sidebar_order", "dashboard,investimentos,charts,cartoes,financiamentos,recorrencias,ia")
        current_order = order_str.split(",")
        current_order = [x for x in current_order if x not in ("resumo_anual", "transacoes", "recorrencias")]
        
        items_info = {
            "dashboard": {"label": "Dashboard", "icon": ft.icons.Icons.DASHBOARD_ROUNDED},
            "investimentos": {"label": "Investimentos", "icon": ft.icons.Icons.SAVINGS_ROUNDED},
            "charts": {"label": "Gráficos", "icon": ft.icons.Icons.PIE_CHART_ROUNDED},
            "cartoes": {"label": "Cartões", "icon": ft.icons.Icons.CREDIT_CARD_ROUNDED},
            "financiamentos": {"label": "Financiamentos", "icon": ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED},
            "ia": {"label": "Assistente IA", "icon": ft.icons.Icons.AUTO_AWESOME_ROUNDED},
        }
        
        for k in items_info:
            if k not in current_order:
                current_order.append(k)
                
        local_order = list(current_order)
        list_container = ft.Column(spacing=10, width=320)
        dialog = None
        
        def rebuild_list():
            list_container.controls.clear()
            for idx, item_id in enumerate(local_order):
                if item_id not in items_info:
                    continue
                info = items_info[item_id]
                
                btn_up = ft.IconButton(
                    icon=ft.icons.Icons.ARROW_UPWARD_ROUNDED,
                    icon_color="#3b82f6" if idx > 0 else "#64748b",
                    disabled=idx == 0,
                    data=idx,
                    on_click=move_up,
                    icon_size=16
                )
                
                btn_down = ft.IconButton(
                    icon=ft.icons.Icons.ARROW_DOWNWARD_ROUNDED,
                    icon_color="#3b82f6" if idx < len(local_order) - 1 else "#64748b",
                    disabled=idx == len(local_order) - 1,
                    data=idx,
                    on_click=move_down,
                    icon_size=16
                )
                
                row = ft.Container(
                    bgcolor=get_colors()["bg"],
                    padding=ft.Padding(10, 5, 10, 5),
                    border_radius=8,
                    border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(info["icon"], color="#3b82f6", size=20),
                                    ft.Text(_t(info["label"]), color=get_colors()["text"], size=14, weight=ft.FontWeight.BOLD),
                                ]
                            ),
                            ft.Row(
                                spacing=0,
                                controls=[btn_up, btn_down]
                            )
                        ]
                    )
                )
                list_container.controls.append(row)
            
            if dialog:
                dialog.update()
                
        def move_up(e):
            idx = e.control.data
            if idx > 0:
                local_order[idx], local_order[idx-1] = local_order[idx-1], local_order[idx]
                rebuild_list()
                
        def move_down(e):
            idx = e.control.data
            if idx < len(local_order) - 1:
                local_order[idx], local_order[idx+1] = local_order[idx+1], local_order[idx]
                rebuild_list()
                
        def fechar_dialog(e):
            page.pop_dialog()
            
        def salvar_ordem(e):
            new_order_str = ",".join(local_order)
            db.set_preferencia("sidebar_order", new_order_str)
            sidebar.content.controls = build_sidebar_controls()
            sidebar.update()
            page.pop_dialog()
            
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(_t("Personalizar Menu Lateral"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=list_container,
            bgcolor=get_colors()["surface"],
            actions=[
                ft.TextButton(_t("CANCELAR"), on_click=fechar_dialog, style=ft.ButtonStyle(color="white")),
                ft.ElevatedButton(_t("SALVAR"), on_click=salvar_ordem, bgcolor="#3b82f6", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.show_dialog(dialog)
        rebuild_list()

    def abrir_criar_categoria_modal(e=None):
        categorias = db.get_categorias()
        
        txt_nome = ft.TextField(
            label=_t("Nome da Categoria"),
            hint_text=_t("Ex: Alimentação, Transporte..."),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"],
            height=48,
            content_padding=ft.Padding(10, 5, 10, 5),
            text_size=12
        )
        
        drop_type = ft.Dropdown(
            label=_t("Tipo"),
            options=[
                ft.dropdown.Option(key="Receita Fixa", text=_t("Receita Fixa")),
                ft.dropdown.Option(key="Receita Variável", text=_t("Receita Variável")),
                ft.dropdown.Option(key="Despesa Fixa", text=_t("Despesa Fixa")),
                ft.dropdown.Option(key="Despesa Variável", text=_t("Despesa Variável")),
                ft.dropdown.Option(key="Investimento", text=_t("Investimento"))
            ],
            value="Despesa Variável",
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"],
            height=48,
            content_padding=ft.Padding(10, 5, 10, 5),
            text_size=12
        )
        
        parents = [c for c in categorias if c[3] is None]
        parent_options = [ft.dropdown.Option(key="None", text=_t("Pai Root"))]
        for p_cat in parents:
            parent_options.append(ft.dropdown.Option(key=str(p_cat[0]), text=p_cat[1]))
            
        drop_parent = ft.Dropdown(
            label=_t("Categoria Pai"),
            options=parent_options,
            value="None",
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"],
            height=48,
            content_padding=ft.Padding(10, 5, 10, 5),
            text_size=12
        )
        
        def fechar_dialog(e):
            page.pop_dialog()
            
        def run_salvar(e):
            nome = (txt_nome.value or "").strip()
            tipo = drop_type.value
            p_val = drop_parent.value
            parent_id = None if p_val == "None" else int(p_val)
            
            if not nome:
                page.snack_bar = ft.SnackBar(content=ft.Text(_t("Por favor, digite o nome da categoria!"), color=get_colors()["text"]), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            success, msg = db.inserir_categoria(nome, tipo, parent_id)
            if success:
                page.snack_bar = ft.SnackBar(content=ft.Text(_t("Categoria adicionada com sucesso!"), color=get_colors()["text"]), bgcolor="#10b981")
                page.pop_dialog()
                if state.get("active_tab") == "configuracoes":
                    render_configuracoes()
                elif state.get("active_tab") in ["dashboard", "charts"]:
                    render_dashboard()
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro:')} {msg}", color=get_colors()["text"]), bgcolor="#ef4444")
                
            page.snack_bar.open = True
            page.update()
            
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(_t("Criar Nova Categoria"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=ft.Column(
                controls=[
                    txt_nome,
                    ft.Container(height=5),
                    drop_type,
                    ft.Container(height=5),
                    drop_parent
                ],
                tight=True,
                spacing=10
            ),
            bgcolor=get_colors()["surface"],
            actions=[
                ft.TextButton(_t("CANCELAR"), on_click=fechar_dialog, style=ft.ButtonStyle(color="white")),
                ft.ElevatedButton(_t("CRIAR"), on_click=run_salvar, bgcolor="#3b82f6", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.show_dialog(dialog)

    sidebar = ft.Container(
        width=100,
        bgcolor=get_colors()["surface"],
        border=ft.border.all(1, get_colors()["border"]),
        padding=ft.Padding(left=10, top=20, right=10, bottom=20),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[]
        )
    )
    sidebar.content.controls = build_sidebar_controls()

    def atualizar_textos_globais():
        try:
            sidebar.content.controls = build_sidebar_controls()
            sidebar.update()
        except Exception as ex:
            pass

    
    def criar_seletor_perfil(on_change_callback):
        perfis = db.get_perfis()
        if "Eu" not in perfis:
            perfis = ["Eu"] + perfis
        
        return ft.Container(
            bgcolor=get_colors()["surface"],
            border=ft.border.all(1, get_colors()["border"]),
            padding=ft.Padding(left=10, top=0, right=10, bottom=0),
            border_radius=20,
            height=38,
            content=ft.Row(
                spacing=5,
                controls=[
                    ft.Icon(ft.icons.Icons.PERSON_ROUNDED, color="#94a3b8", size=16),
                    ft.Dropdown(
                        value=state["perfil"],
                        options=[ft.dropdown.Option(p) for p in perfis],
                        on_select=on_change_callback,
                        width=120,
                        height=36,
                        border_color="transparent",
                        text_style=ft.TextStyle(color=get_colors()["text"], size=13, weight=ft.FontWeight.W_500),
                        content_padding=ft.Padding(5, 0, 5, 0),
                        bgcolor="transparent",
                    )
                ]
            )
        )

    def criar_tab_header(aba_ativa, seletor_perfil_widget, subcontroles=None):
        """
        Constrói o header persistente de 2 linhas para as telas principais:
          Linha 1: Logo | Abas (Dashboard/Histórico/Resumo Anual/Recorrências) | Seletor de perfil
          Linha 2: Controles contextuais específicos da aba ativa
        """
        abas = [
            ("dashboard",    ft.icons.Icons.DASHBOARD_ROUNDED,  _t("Dashboard")),
            ("transacoes",   ft.icons.Icons.LIST_ALT_ROUNDED,    _t("Histórico")),
            ("resumo_anual", ft.icons.Icons.ANALYTICS_ROUNDED,   _t("Resumo Anual")),
            ("recorrencias", ft.icons.Icons.AUTORENEW_ROUNDED,   _t("Recorrências")),
            ("parcelamentos", ft.icons.Icons.CREDIT_CARD_ROUNDED, _t("Parcelamentos")),
            ("veiculos",     ft.icons.Icons.DIRECTIONS_CAR_ROUNDED, _t("Veículos")),
            ("pets",         ft.icons.Icons.PETS_ROUNDED,        _t("Pet")),
            ("saude",        ft.icons.Icons.LOCAL_HOSPITAL_ROUNDED, _t("Saúde")),
        ]

        tab_widgets = []
        for tab_id, tab_icon, tab_label in abas:
            is_active = (aba_ativa == tab_id)
            tab_widgets.append(
                ft.Container(
                    content=ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(tab_icon, size=15,
                                    color="white" if is_active else "#64748b"),
                            ft.Text(tab_label, size=13, weight=ft.FontWeight.BOLD,
                                    color="white" if is_active else "#64748b"),
                        ]
                    ),
                    padding=ft.Padding(14, 8, 14, 8),
                    border_radius=8,
                    bgcolor="#2563eb" if is_active else "transparent",
                    ink=True,
                    on_click=(lambda e, t=tab_id: navegar_para_aba(t)) if not is_active else None,
                    tooltip=None if is_active else tab_label,
                )
            )

        linha1 = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(_t("Sentinel Finance"), size=22, weight=ft.FontWeight.BOLD,
                        color=get_colors()["text"]),
                ft.Row(spacing=4, controls=tab_widgets),
                seletor_perfil_widget,
            ]
        )

        linha2_controls = subcontroles or []
        linha2 = ft.Row(
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=linha2_controls,
        )

        return ft.Column(
            spacing=6,
            controls=[
                linha1,
                ft.Divider(color=get_colors()["border"], height=1),
                linha2,
            ]
        )


    def criar_card_resumo(titulo, valor, cor_valor=None, cor_fundo=None, small=False, subtexto=None, is_currency=True):
        from ui_components.cards import criar_card_resumo as _criar_card_resumo
        return _criar_card_resumo(titulo, valor, get_colors(), cor_valor, cor_fundo, small, subtexto, is_currency)
    
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

    def abrir_detalhes_categoria_dialog(cat_nome, trans_list, eh_despesa):
        def fechar_dialog(e):
            page.pop_dialog()

        detalhes_controls = []
        for t in trans_list:
            data_str = t[1][:5] if t[1] else "" # Apenas dd/mm
            desc = t[2]
            valor = t[3]
            tipo_t = t[5]
            parc_atual = t[6]
            parc_total = t[7]
            metodo_pagto = t[8]
            dono_cartao = t[9]
            bandeira_cartao = t[10]

            if tipo_t == "Investimento":
                item_cor = "#3b82f6"
            else:
                item_cor = "#ef4444" if eh_despesa else "#10b981"

            meta_parts = [data_str]
            if metodo_pagto:
                pagto_str = metodo_pagto
                if "cartão" in metodo_pagto.lower() or "cartao" in metodo_pagto.lower():
                    cartao_parts = []
                    if bandeira_cartao:
                        cartao_parts.append(bandeira_cartao)
                    if dono_cartao:
                        cartao_parts.append(dono_cartao)
                    if cartao_parts:
                        pagto_str += f" ({' - '.join(cartao_parts)})"
                meta_parts.append(pagto_str)

            if parc_total and parc_total > 1:
                meta_parts.append(f"Parcela {parc_atual} de {parc_total}")

            try:
                t_divisoes = t[11]
            except IndexError:
                t_divisoes = 0

            if t_divisoes and t_divisoes > 1:
                meta_parts.append("Dividido 👥")

            vinculo_parts = []
            if len(t) > 15:
                v_mod = t[14]
                v_pla = t[15]
                p_nome = t[16]
                s_nome = t[17]
                if v_mod or v_pla:
                    v_str = "🚗 "
                    if v_mod: v_str += v_mod
                    if v_pla: v_str += f" ({v_pla})"
                    vinculo_parts.append(v_str)
                if p_nome:
                    vinculo_parts.append(f"🐾 {p_nome}")
                if s_nome:
                    vinculo_parts.append(f"🏥 {s_nome}")
            
            if vinculo_parts:
                meta_parts.append(" • ".join(vinculo_parts))

            sub_text = " • ".join(meta_parts)
            valor_formatado = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            detalhes_controls.append(
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor=get_colors()["bg"],
                    border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                expand=True,
                                spacing=2,
                                controls=[
                                    ft.Text(desc, size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(sub_text, size=12, color="#64748b", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                                ]
                            ),
                            ft.Text(valor_formatado, size=14, weight=ft.FontWeight.BOLD, color=item_cor)
                        ]
                    )
                )
            )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{_t('Detalhes')} - {cat_nome}", size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=ft.Container(
                width=450,
                height=300,
                content=ft.ListView(
                    spacing=10,
                    controls=detalhes_controls,
                    expand=True
                )
            ),
            bgcolor=get_colors()["surface"],
            actions=[
                ft.TextButton(_t("FECHAR"), on_click=fechar_dialog, style=ft.ButtonStyle(color="white"))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.show_dialog(dialog)

    def criar_lista_transacoes(titulo, transacoes, eh_despesa=True):
        # Chaves de estado específicas por painel
        sort_state_key = "sort_despesas" if eh_despesa else "sort_receitas"
        sort_key = state.get(sort_state_key, "valor")  # "valor" ou "alfa"
        group_state_key = "group_despesas" if eh_despesa else "group_receitas"
        group_mode = state.get(group_state_key, "categoria")  # "categoria" ou "subcategoria"

        # 1. Agrupar lançamentos por categoria ou subcategoria
        categorias = db.get_categorias()
        cat_id_to_name = {c[0]: c[1].strip().title() for c in categorias}
        sub_to_parent = {}
        for c in categorias:
            c_id, c_name, _, parent_id, _ = c
            c_name_title = c_name.strip().title()
            if parent_id and parent_id in cat_id_to_name:
                sub_to_parent[c_name_title] = cat_id_to_name[parent_id]
            else:
                sub_to_parent[c_name_title] = c_name_title

        groups = {}
        for t in transacoes:
            subcat = t[4].strip().title() if t[4] else "Sem Categoria"
            if group_mode == "categoria":
                group_key = sub_to_parent.get(subcat, subcat)
            else:
                group_key = subcat
                
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(t)

        # 2. Calcular totais por grupo
        grouped_data = []
        for cat, trans_list in groups.items():
            total_val = sum(t[3] for t in trans_list)
            grouped_data.append((cat, total_val, trans_list))

        # 3. Ordenar conforme o modo escolhido pelo usuário
        if sort_key == "alfa":
            grouped_data.sort(key=lambda x: x[0].lower())
        else:  # "valor" — maior primeiro
            grouped_data.sort(key=lambda x: x[1], reverse=True)

        itens = []
        for cat, total_val, trans_list in grouped_data:
            parent_cat = sub_to_parent.get(cat, cat)
            icone_tipo = get_icone_categoria(parent_cat)

            # Se alguma transação no grupo for Investimento, usa cor de investimento
            tem_investimento = any(t[5] == "Investimento" for t in trans_list)
            if tem_investimento:
                icone_cor = "#3b82f6"
            else:
                icone_cor = "#ef4444" if eh_despesa else "#10b981"

            num_lancamentos = len(trans_list)
            txt_lancamentos = f"{num_lancamentos} lançamento" if num_lancamentos == 1 else f"{num_lancamentos} lançamentos"

            # Formata o valor total somado
            valor_formatado = f"R$ {total_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            def make_on_click(cat_name, transactions):
                return lambda e: abrir_detalhes_categoria_dialog(cat_name, transactions, eh_despesa)
            on_click_handler = make_on_click(cat, trans_list)

            itens.append(
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor=get_colors()["bg"],
                    border=ft.border.all(1, get_colors()["border"]),
                    ink=True,
                    on_click=on_click_handler,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                expand=True,
                                controls=[
                                    ft.Container(
                                        padding=10,
                                        bgcolor=get_colors()["surface"],
                                        border_radius=8,
                                        content=ft.Icon(icone_tipo, color=icone_cor, size=20)
                                    ),
                                    ft.Container(width=10),
                                    ft.Column(
                                        expand=True,
                                        spacing=2,
                                        controls=[
                                            ft.Text(cat, size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                            ft.Text(txt_lancamentos, size=12, color="#64748b", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                                        ]
                                    )
                                ]
                            ),
                            ft.Text(valor_formatado, size=14, weight=ft.FontWeight.BOLD, color=icone_cor)
                        ]
                    )
                )
            )

        if not itens:
            itens.append(ft.Text("Nenhum lançamento recente.", color="#64748b"))

        # --- Botões de controle do painel ---
        def make_sort_toggle(sk):
            def _on_click(e):
                state[sort_state_key] = sk
                render_dashboard()
            return _on_click

        def make_group_toggle(gk):
            def _on_click(e):
                state[group_state_key] = gk
                render_dashboard()
            return _on_click

        btn_sort_alfa = ft.IconButton(
            icon=ft.icons.Icons.SORT_BY_ALPHA_ROUNDED,
            icon_size=18,
            icon_color="#3b82f6" if sort_key == "alfa" else "#64748b",
            tooltip=_t("Ordem Alfabética"),
            on_click=make_sort_toggle("alfa"),
            style=ft.ButtonStyle(padding=ft.Padding(4,4,4,4))
        )
        btn_sort_valor = ft.IconButton(
            icon=ft.icons.Icons.ARROW_DOWNWARD_ROUNDED,
            icon_size=18,
            icon_color="#3b82f6" if sort_key == "valor" else "#64748b",
            tooltip=_t("Maior Valor"),
            on_click=make_sort_toggle("valor"),
            style=ft.ButtonStyle(padding=ft.Padding(4,4,4,4))
        )
        btn_group = ft.IconButton(
            icon=ft.icons.Icons.LAYERS_ROUNDED if group_mode == "categoria" else ft.icons.Icons.LAYERS_CLEAR_ROUNDED,
            icon_size=18,
            icon_color="#3b82f6" if group_mode == "subcategoria" else "#64748b",
            tooltip=_t("Ver Subcategorias") if group_mode == "categoria" else _t("Ver Categorias"),
            on_click=make_group_toggle("subcategoria" if group_mode == "categoria" else "categoria"),
            style=ft.ButtonStyle(padding=ft.Padding(4,4,4,4))
        )

        header_row_panel = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(titulo, size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.Row(spacing=0, controls=[btn_group, btn_sort_alfa, btn_sort_valor])
            ]
        )

        return ft.Container(
            expand=True,
            bgcolor=get_colors()["surface"],
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=12,
            padding=20,
            content=ft.Column(
                expand=True,
                controls=[
                    header_row_panel,
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
        elif state["active_tab"] == "investimentos":
            render_investimentos()
        elif state["active_tab"] == "financiamentos":
            render_financiamentos()
        elif state["active_tab"] == "veiculos":
            render_veiculos()
        elif state["active_tab"] == "pets":
            render_pets()
        elif state["active_tab"] == "saude":
            render_saude()
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
        elif state["active_tab"] == "investimentos":
            render_investimentos()
        elif state["active_tab"] == "financiamentos":
            render_financiamentos()
        elif state["active_tab"] == "veiculos":
            render_veiculos()
        elif state["active_tab"] == "pets":
            render_pets()
        elif state["active_tab"] == "saude":
            render_saude()
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
            bgcolor=get_colors()["surface"],
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=12,
            padding=20,
            content=ft.Column(
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", on_click=on_prev),
                            ft.Text(titulo, size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", on_click=on_next)
                        ]
                    ),
                    ft.Divider(color="#334155"),
                    ft.Container(expand=True, padding=10, content=chart_control)
                ]
            )
        )

    def gerar_grafico_base64(tipo, dados, labels, cores):
        from ui_components.charts import gerar_grafico_base64 as _impl
        return _impl(tipo, dados, labels, cores)

    def gerar_grafico_donut_base64(dados, labels, cores, is_light=False):
        from ui_components.charts import gerar_grafico_donut_base64 as _impl
        return _impl(dados, labels, cores, is_light)

    def gerar_grafico_evolucao_patrimonio_base64(meses, aplicados, mercados, is_light=False):
        from ui_components.charts import gerar_grafico_evolucao_patrimonio_base64 as _impl
        return _impl(meses, aplicados, mercados, is_light)

    def gerar_grafico_linhas_rentabilidade_base64(meses, carteira, cdi, ipca, is_light=False):
        from ui_components.charts import gerar_grafico_linhas_rentabilidade_base64 as _impl
        return _impl(meses, carteira, cdi, ipca, is_light)

    def gerar_grafico_barras_proventos_base64(meses, recebidos, a_receber, is_light=False):
        from ui_components.charts import gerar_grafico_barras_proventos_base64 as _impl
        return _impl(meses, recebidos, a_receber, is_light)

    def gerar_grafico_aportes_base64(meses, compras, vendas, is_light=False):
        from ui_components.charts import gerar_grafico_aportes_base64 as _impl
        return _impl(meses, compras, vendas, is_light)

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
            tooltip=_t("Novo Lançamento")
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
                        content=ft.Text(_t("Despesa 🔴"), color=get_colors()["text"], weight=ft.FontWeight.BOLD),
                        width=140,
                        height=40,
                        bgcolor=get_colors()["surface"],
                        on_click=lambda e: (contrair_fab(), abrir_overlay("despesa"))
                    ),
                    ft.FloatingActionButton(
                        content=ft.Text(_t("Receita 🟢"), color=get_colors()["text"], weight=ft.FontWeight.BOLD),
                        width=140,
                        height=40,
                        bgcolor=get_colors()["surface"],
                        on_click=lambda e: (contrair_fab(), abrir_overlay("receita"))
                    ),
                    ft.FloatingActionButton(
                        content=ft.Text(_t("Aporte 🔵"), color=get_colors()["text"], weight=ft.FontWeight.BOLD),
                        width=140,
                        height=40,
                        bgcolor=get_colors()["surface"],
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
                
                # Configura entidade vinculada na edição a partir do histórico geral
                if details.get("veiculo_id"):
                    state["overlay_entity_type"] = "veiculo"
                    state["overlay_entity_id"] = details["veiculo_id"]
                elif details.get("pet_id"):
                    state["overlay_entity_type"] = "pet"
                    state["overlay_entity_id"] = details["pet_id"]
                elif details.get("saude_id"):
                    state["overlay_entity_type"] = "saude"
                    state["overlay_entity_id"] = details["saude_id"]
                else:
                    if state.get("active_tab") not in ["veiculos", "pets", "saude"]:
                        state["overlay_entity_type"] = None
                        state["overlay_entity_id"] = None
        else:
            # Novo lançamento: se não vier de uma aba específica, limpa as entidades do state
            if state.get("active_tab") not in ["veiculos", "pets", "saude"]:
                state["overlay_entity_type"] = None
                state["overlay_entity_id"] = None

        shield = ft.Container(
            expand=True,
            bgcolor="#cc090d16",  # Premium blurred matte dark backdrop
            on_click=fechar_overlay
        )

        form_container = ft.Column(expand=True, spacing=15, scroll=ft.ScrollMode.ADAPTIVE)

        if tipo == "despesa":
            title_text = _t("✏️ Editar Despesa") if editing_trans_id else _t("Lançar Nova Despesa")
        elif tipo == "investimento":
            title_text = _t("✏️ Editar Investimento") if editing_trans_id else _t("Novo Lançamento de Investimento")
        else:
            title_text = _t("✏️ Editar Receita") if editing_trans_id else _t("Nova Receita")

        modal_card = ft.Container(
            width=540,
            height=660,
            bgcolor=get_colors()["surface"],
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
                                color=get_colors()["text"]
                            ),
                            ft.IconButton(
                                icon=ft.icons.Icons.CLOSE_ROUNDED,
                                icon_color="#94a3b8",
                                icon_size=22,
                                on_click=fechar_overlay,
                                tooltip=_t("Fechar")
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
            ent_type = state.get("overlay_entity_type")
            locked_pilar = None
            if ent_type == "veiculo":
                locked_pilar = "Despesa Variável"
            elif ent_type == "pet":
                locked_pilar = "Despesa Variável"
            elif ent_type == "saude":
                locked_pilar = "Despesa Fixa"
            populate_formulario_despesa(form_container, details=details, locked_pilar=locked_pilar)
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
        btn_label = _t("INVESTIMENTO") if is_invest else _t("RECEITA")

        txt_desc = ft.TextField(
            label=_t("Descrição"), 
            hint_text="Ex: Salário Mensal", 
            border_color="#374151", 
            focused_border_color=theme_color, 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )
        txt_valor = ft.TextField(
            label=_t("Valor (R$)"), 
            hint_text="Ex: 5000.00", 
            border_color="#374151", 
            focused_border_color=theme_color, 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )
        txt_data = ft.TextField(
            label=_t("Data (DD/MM/AAAA)"), 
            value=datetime.datetime.now().strftime("%d/%m/%Y"), 
            border_color="#374151", 
            focused_border_color=theme_color, 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )
        txt_obs = ft.TextField(
            label=_t("Observação (Opcional)"), 
            border_color="#374151", 
            focused_border_color=theme_color, 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )

        drop_pilar = ft.Dropdown(
            label=_t("Tipo de Lançamento"),
            border_color="#374151",
            focused_border_color=theme_color,
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=[
                ft.dropdown.Option(key="Receita Fixa", text=_t("Receita Fixa")),
                ft.dropdown.Option(key="Receita Variável", text=_t("Receita Variável")),
                ft.dropdown.Option(key="Investimento", text=_t("Investimento"))
            ],
            value=locked_pilar if locked_pilar else "Receita Fixa",
            disabled=(locked_pilar is not None),
            on_select=lambda e: update_cats_receita()
        )

        drop_cat = ft.Dropdown(
            label=_t("Categoria"),
            border_color="#374151",
            focused_border_color=theme_color,
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            on_select=lambda e: update_subs_receita()
        )

        drop_sub = ft.Dropdown(
            label=_t("Subcategoria"),
            border_color="#374151",
            focused_border_color=theme_color,
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )

        # Banner informativo sobre recorrências (substitui o lote)
        banner_recorrencia = ft.Container(
            margin=ft.Margin(0, 0, 15, 0),
            padding=ft.Padding(12, 8, 12, 8),
            border_radius=8,
            bgcolor=get_colors()["bg"],
            border=ft.border.all(1, get_colors()["border"]),
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.icons.Icons.AUTORENEW_ROUNDED, color="#64748b", size=14),
                    ft.Text(
                        _t("Lançamentos recorrentes em vários meses podem ser configurados no menu de Recorrências."),
                        size=11,
                        color="#64748b",
                        expand=True
                    )
                ]
            )
        )

        def toggle_lote_visibility():
            pass  # Removido — função mantida para não quebrar chamadas existentes

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
            toggle_lote_visibility()
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
                    content=ft.Text(_t("Por favor, preencha a descrição, valor e data!"), color=get_colors()["text"]),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return

            try:
                valor = float(valor_str.replace(",", "."))
            except ValueError:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(_t("Valor inválido!"), color=get_colors()["text"]),
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
                    content=ft.Text(_t("Lançamento salvo com sucesso!") if details else f"{btn_label} {_t('adicionada com sucesso!')}", color=get_colors()["text"]),
                    bgcolor="#10b981" if not is_invest else "#3b82f6"
                )
                page.snack_bar.open = True
                fechar_overlay()
                if state["active_tab"] == "cartoes":
                    render_cartoes()
                elif state["active_tab"] == "transacoes":
                    render_transacoes()
                elif state["active_tab"] == "financiamentos":
                    render_financiamentos()
                else:
                    render_dashboard()
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"{_t('Erro ao salvar:')} {msg}", color=get_colors()["text"]),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()

        def excluir_transacao(e):
            def confirmar_delecao(e):
                page.pop_dialog()
                success, msg = db.deletar_transacao(details["id"])
                if success:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(_t("Lançamento excluído com sucesso!"), color=get_colors()["text"]),
                        bgcolor="#10b981"
                    )
                    page.snack_bar.open = True
                    fechar_overlay()
                    if state["active_tab"] == "cartoes":
                        render_cartoes()
                    elif state["active_tab"] == "transacoes":
                        render_transacoes()
                    elif state["active_tab"] == "financiamentos":
                        render_financiamentos()
                    else:
                        render_dashboard()
                else:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"{_t('Erro ao excluir:')} {msg}", color=get_colors()["text"]),
                        bgcolor="#ef4444"
                    )
                    page.snack_bar.open = True
                    page.update()

            def fechar_dialog(e):
                page.pop_dialog()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(_t("CONFIRMAR EXCLUSÃO ⚠️"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                content=ft.Text(_t("Deseja realmente excluir permanentemente este lançamento?"), size=14, color=get_colors()["subtext"]),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=fechar_dialog, style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton("EXCLUIR", on_click=confirmar_delecao, bgcolor="#ef4444", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

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
                ft.ElevatedButton(
                    content="EXCLUIR",
                    color="white",
                    bgcolor="#ef4444",
                    height=45,
                    on_click=excluir_transacao,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                )
            )
            action_buttons.append(
                ft.ElevatedButton(
                    content="SALVAR ALTERAÇÕES",
                    color="white",
                    bgcolor=theme_color,
                    height=45,
                    expand=True,
                    on_click=salvar_receita,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                )
            )
        else:
            action_buttons.append(
                ft.ElevatedButton(
                    content=f"SALVAR {btn_label}",
                    color="white",
                    bgcolor=theme_color,
                    height=45,
                    expand=True,
                    on_click=salvar_receita,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
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
            row_vinculos,
            drop_vinculo_row,
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=txt_valor),
                    ft.Container(expand=True), # dummy spacer for symmetry
                    ft.Container(width=15)
                ]
            ),
            ft.Row([ft.Container(expand=True, content=txt_obs), ft.Container(width=15)]),
            banner_recorrencia,
            ft.Container(height=10),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=ft.Row(controls=action_buttons, spacing=10)),
                    ft.Container(width=15)
                ]
            )
        ]

        if details:
            initial_parent = details["parent_id"] if details["parent_id"] is not None else details["categoria_id"]
            update_cats_receita(set_initial=initial_parent)
        else:
            update_cats_receita()

    def populate_formulario_despesa(container, details=None, locked_pilar=None):
        txt_desc = ft.TextField(
            label=_t("Descrição"), 
            hint_text="Ex: Compras Supermercado", 
            border_color="#374151", 
            focused_border_color="#ef4444", 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )
        txt_valor = ft.TextField(
            label=_t("Valor (R$)"), 
            hint_text="Ex: 150.50", 
            border_color="#374151", 
            focused_border_color="#ef4444", 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"], 
            on_change=lambda e: update_sharing_labels()
        )
        txt_data = ft.TextField(
            label=_t("Data (DD/MM/AAAA)"), 
            value=datetime.datetime.now().strftime("%d/%m/%Y"), 
            border_color="#374151", 
            focused_border_color="#ef4444", 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )
        txt_obs = ft.TextField(
            label=_t("Observação (Opcional)"), 
            border_color="#374151", 
            focused_border_color="#ef4444", 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )

        drop_pilar = ft.Dropdown(
            label=_t("Pilar da Despesa"),
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=[
                ft.dropdown.Option(key="Despesa Variável", text=_t("Despesa Variável")),
                ft.dropdown.Option(key="Despesa Fixa", text=_t("Despesa Fixa"))
            ],
            value=locked_pilar if locked_pilar else "Despesa Variável",
            disabled=(locked_pilar is not None),
            on_select=lambda e: update_cats_despesa()
        )

        drop_cat = ft.Dropdown(
            label=_t("Categoria"),
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            on_select=lambda e: update_subs_despesa()
        )

        drop_sub = ft.Dropdown(
            label=_t("Subcategoria"),
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )

        perfil_ativo = state.get("perfil", "Eu")
        veiculos_list = db.get_veiculos(perfil_ativo)
        pets_list = db.get_pets(perfil_ativo)
        saude_list = db.get_saude(perfil_ativo)

        drop_veiculo = ft.Dropdown(
            label=_t("Veículo Vinculado"),
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=[ft.dropdown.Option(key="sem_vinculo", text=_t("Sem Vínculo / Geral"))] + [
                ft.dropdown.Option(key=str(v[0]), text=f"{v[2]} ({v[1]})" if v[1] else v[2]) for v in veiculos_list
            ],
            value="sem_vinculo",
            visible=False
        )

        drop_pet = ft.Dropdown(
            label=_t("Pet Vinculado"),
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=[ft.dropdown.Option(key="sem_vinculo", text=_t("Sem Vínculo / Geral"))] + [
                ft.dropdown.Option(key=str(p[0]), text=p[1]) for p in pets_list
            ],
            value="sem_vinculo",
            visible=False
        )

        drop_saude = ft.Dropdown(
            label=_t("Item de Saúde Vinculado"),
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=[ft.dropdown.Option(key="sem_vinculo", text=_t("Sem Vínculo / Geral"))] + [
                ft.dropdown.Option(key=str(s[0]), text=s[1]) for s in saude_list
            ],
            value="sem_vinculo",
            visible=False
        )

        row_vinculos = ft.Row(
            visible=False,
            controls=[
                ft.Container(expand=True, content=drop_veiculo),
                ft.Container(expand=True, content=drop_pet),
                ft.Container(expand=True, content=drop_saude),
                ft.Container(width=15)
            ]
        )

        drop_vinculo = ft.Dropdown(
            label="",
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=[],
            visible=False
        )

        drop_vinculo_row = ft.Row(
            controls=[
                ft.Container(expand=True, content=drop_vinculo),
                ft.Container(width=15)
            ],
            visible=False
        )

        drop_metodo = ft.Dropdown(
            label=_t("Método de Pagamento"),
            border_color="#374151",
            focused_border_color="#ef4444",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=[
                ft.dropdown.Option(key="Dinheiro", text=_t("Dinheiro")),
                ft.dropdown.Option(key="Pix", text=_t("Pix")),
                ft.dropdown.Option(key="Boleto", text=_t("Boleto")),
                ft.dropdown.Option(key="Cartão", text=_t("Cartão"))
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
            label=_t("Selecione o Cartão"),
            border_color="#374151",
            focused_border_color="#2563eb",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=card_options
        )
        if card_options:
            drop_cartao.value = card_options[0].key

        txt_parcelas = ft.TextField(
            label=_t("Parcelas"), 
            value="1", 
            border_color="#374151", 
            focused_border_color="#2563eb", 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"]
        )
        chk_compartilhar = ft.Checkbox(
            label=_t("Dividir despesa com a família"), 
            value=False, 
            label_style=ft.TextStyle(size=13, font_family="Segoe UI", color=get_colors()["text"]),
            on_change=lambda e: toggle_sharing_fields()
        )

        drop_mes_inicio = ft.Dropdown(
            label=_t("Início da Cobrança"),
            border_color="#374151",
            focused_border_color="#2563eb",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=[
                ft.dropdown.Option(key="0", text=_t("Mês atual (data do lançamento)")),
                ft.dropdown.Option(key="1", text=_t("Próximo mês")),
                ft.dropdown.Option(key="2", text=_t("Mês subsequente (em 2 meses)")),
            ],
            value="0"
        )

        cartao_container = ft.Column(
            visible=False,
            spacing=10,
            controls=[
                ft.Text(_t("💳 Detalhes do Cartão"), size=12, weight=ft.FontWeight.BOLD, color="#3b82f6"),
                ft.Row(
                    controls=[
                        ft.Container(expand=3, content=drop_cartao),
                        ft.Container(expand=1, content=txt_parcelas),
                        ft.Container(width=15)
                    ],
                    spacing=10
                ),
                ft.Row(
                    controls=[
                        ft.Container(expand=1, content=drop_mes_inicio),
                        ft.Container(width=15)
                    ],
                    spacing=10
                )
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
                        ft.Text(p, size=13, font_family="Segoe UI", color=get_colors()["text"], weight=ft.FontWeight.W_500)
                    ]
                )
            )
            member_widgets.append(widget)

        drop_div_tipo = ft.Dropdown(
            label=_t("Tipo de Divisão"),
            border_color="#374151",
            focused_border_color="#10b981",
            text_style=ft.TextStyle(color=get_colors()["text"], size=14),
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"],
            options=[
                ft.dropdown.Option(key="Igualitária", text=_t("Igualitária")),
                ft.dropdown.Option(key="Individual", text=_t("Individual"))
            ],
            value="Igualitária",
            on_select=lambda e: rebuild_sharing_inputs()
        )

        col_inputs = ft.Column(spacing=8)
        lbl_val_status = ft.Text(size=12, weight=ft.FontWeight.BOLD)
        txt_novo_perfil = ft.TextField(
            label=_t("Nome do novo membro"), 
            border_color="#374151", 
            focused_border_color="#10b981", 
            text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
            label_style=ft.TextStyle(size=12),
            height=48,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"], 
            visible=False, 
            on_change=lambda e: update_sharing_labels()
        )
        txt_novo_perfil_row = ft.Row([ft.Container(expand=True, content=txt_novo_perfil), ft.Container(width=15)], visible=False)

        if custom_name:
            txt_novo_perfil.value = custom_name
            txt_novo_perfil.visible = True
            txt_novo_perfil_row.visible = True

        divisoes_personalizadas = []
        col_parcelas_fino = ft.Column(spacing=8, visible=False)

        lbl_controle_fino_status = ft.Text(
            "Controle fino por parcela não configurado (clique no botão para configurar)",
            size=11,
            color="#94a3b8",
            visible=False
        )

        def alternar_controle_fino(e):
            if col_parcelas_fino.visible:
                col_parcelas_fino.visible = False
                col_parcelas_fino.controls.clear()
                btn_controle_fino.text = "⚙️ Controle Fino por Parcela"
                page.update()
                return

            try:
                val_total = float(txt_valor.value.replace(",", "."))
            except ValueError:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Por favor, digite um valor total válido para a despesa!", color=get_colors()["text"]),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return

            try:
                num_parcelas = int(txt_parcelas.value)
                if num_parcelas <= 1:
                    raise ValueError()
            except ValueError:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("O controle fino por parcela só é aplicável para compras parceladas (> 1 parcela)!", color="white"),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return

            selected = [chk.data for chk in member_checks if chk.value == True]
            if not selected:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Por favor, selecione pelo menos um membro para dividir!", color=get_colors()["text"]),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return

            val_parcela = val_total / num_parcelas
            novo_nome = (txt_novo_perfil.value or "").strip() if txt_novo_perfil.visible else ""

            tf_map = []

            nonlocal divisoes_personalizadas
            totais_individuais = {}
            soma_totais_individuais = 0.0
            for p in selected:
                nome_final = novo_nome if p == "Outro..." and novo_nome else p
                if p == "Outro..." and not novo_nome: nome_final = "Desconhecido"
                try:
                    tf = inputs_individuais.get(p)
                    val_str = tf.value if tf is not None else "0,00"
                    totais_individuais[nome_final] = float(val_str.replace(",", "."))
                except:
                    totais_individuais[nome_final] = 0.0
                soma_totais_individuais += totais_individuais[nome_final]

            has_valid_proportions = abs(soma_totais_individuais - val_total) < 0.05

            if not divisoes_personalizadas or len(divisoes_personalizadas) != num_parcelas:
                divisoes_personalizadas = []
                for i in range(num_parcelas):
                    parcel_dict = {}
                    for p in selected:
                        nome_final = novo_nome if p == "Outro..." and novo_nome else p
                        if p == "Outro..." and not novo_nome: nome_final = "Desconhecido"
                        if has_valid_proportions:
                            parcel_dict[nome_final] = totais_individuais[nome_final] / num_parcelas
                        else:
                            parcel_dict[nome_final] = val_parcela / len(selected)
                    divisoes_personalizadas.append(parcel_dict)

            col_parcelas_fino.controls.clear()
            
            # Subtítulo
            col_parcelas_fino.controls.append(
                ft.Text(
                    "⚙️ Distribuição Fina por Parcela:",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color="#3b82f6"
                )
            )

            for i in range(num_parcelas):
                parcela_label = ft.Text(
                    f"📦 Parcela {i+1} de {num_parcelas} (R$ {val_parcela:.2f})",
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color="#94a3b8"
                )
                
                row_inputs = []
                tf_parcela_map = {}
                
                for p in selected:
                    nome_final = novo_nome if p == "Outro..." and novo_nome else p
                    if p == "Outro..." and not novo_nome: nome_final = "Desconhecido"
                    
                    val_cota_inicial = divisoes_personalizadas[i].get(nome_final, 0.0)
                    
                    tf_cota = ft.TextField(
                        label=f"{nome_final}",
                        value=f"{val_cota_inicial:.2f}".replace(".", ","),
                        border_color="#374151",
                        focused_border_color="#10b981",
                        text_style=ft.TextStyle(color=get_colors()["text"], size=13),
                        label_style=ft.TextStyle(size=11),
                        height=40,
                        expand=True,
                        content_padding=ft.Padding(8, 2, 8, 2),
                        bgcolor=get_colors()["bg"],
                        on_change=lambda e: atualizar_valores_fino_digitados()
                    )
                    tf_parcela_map[nome_final] = tf_cota
                    row_inputs.append(ft.Container(expand=True, content=tf_cota))
                
                tf_map.append(tf_parcela_map)
                
                col_parcelas_fino.controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                parcela_label,
                                ft.Row(controls=row_inputs, spacing=8)
                            ],
                            spacing=4
                        ),
                        margin=ft.Margin(0, 0, 0, 5)
                    )
                )

            def atualizar_valores_fino_digitados():
                novas_divisoes = []
                todos_validos = True
                
                for idx in range(num_parcelas):
                    soma_p = 0.0
                    parcel_dict = {}
                    for nome_final, tf in tf_map[idx].items():
                        try:
                            val = float(tf.value.replace(",", "."))
                        except ValueError:
                            val = 0.0
                        parcel_dict[nome_final] = val
                        soma_p += val
                    
                    novas_divisoes.append(parcel_dict)
                    
                    if abs(soma_p - val_parcela) > 0.05:
                        todos_validos = False

                nonlocal divisoes_personalizadas
                divisoes_personalizadas = novas_divisoes

                if todos_validos:
                    lbl_controle_fino_status.value = f"✅ Controle fino configurado e válido ({num_parcelas} parcelas)!"
                    lbl_controle_fino_status.color = "#10b981"
                else:
                    lbl_controle_fino_status.value = f"⚠️ Soma de alguma parcela não bate com R$ {val_parcela:.2f}!"
                    lbl_controle_fino_status.color = "#fb923c"
                lbl_controle_fino_status.visible = True
                page.update()

            atualizar_valores_fino_digitados()
            col_parcelas_fino.visible = True
            btn_controle_fino.text = "❌ Ocultar Controle Fino por Parcela"
            page.update()

        btn_controle_fino = ft.ElevatedButton(
            content="⚙️ Controle Fino por Parcela",
            color="white",
            on_click=alternar_controle_fino,
            bgcolor="#3b82f6",
            height=45,
            visible=False,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
        )

        sharing_container = ft.Column(
            visible=False,
            spacing=10,
            controls=[
                ft.Text("👥 Compartilhamento & Divisão", size=12, weight=ft.FontWeight.BOLD, color="#10b981"),
                ft.Row(controls=member_widgets + [ft.Container(width=15)], wrap=True),
                txt_novo_perfil_row,
                ft.Row([ft.Container(expand=True, content=drop_div_tipo), ft.Container(width=15)]),
                col_inputs,
                ft.Row([ft.Container(expand=True, content=btn_controle_fino), ft.Container(width=15)]),
                col_parcelas_fino,
                ft.Row([lbl_controle_fino_status, ft.Container(width=15)]),
                ft.Row([lbl_val_status, ft.Container(width=15)])
            ]
        )

        inputs_individuais = {}

        # Banner informativo sobre recorrências (substitui o lote)
        banner_recorrencia_desp = ft.Container(
            margin=ft.Margin(0, 0, 15, 0),
            padding=ft.Padding(12, 8, 12, 8),
            border_radius=8,
            bgcolor=get_colors()["bg"],
            border=ft.border.all(1, get_colors()["border"]),
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.icons.Icons.AUTORENEW_ROUNDED, color="#64748b", size=14),
                    ft.Text(
                        _t("Para despesas recorrentes (não parceladas no cartão), configure pelo menu de Recorrências."),
                        size=11,
                        color="#64748b",
                        expand=True
                    )
                ]
            )
        )

        def sync_date_with_lote(e=None):
            pass  # Removido — mantido para não quebrar chamadas existentes

        txt_data.on_change = sync_date_with_lote

        def toggle_lote_visibility():
            pass  # Removido — função mantida para não quebrar chamadas existentes

        def update_cats_despesa(set_initial=None):
            pilar = drop_pilar.value
            cats = categorias_por_pilar.get(pilar, {})
            ent_type = state.get("overlay_entity_type")
            if ent_type:
                target_root = "VEÍCULO" if ent_type == "veiculo" else ("PET" if ent_type == "pet" else "SAÚDE")
                cats = {cid: info for cid, info in cats.items() if info["nome"].upper() == target_root}
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
            toggle_lote_visibility()
            page.update()

        def update_vinculo_dropdown(set_initial_val=None):
            pilar = drop_pilar.value
            try:
                parent_id = int(drop_cat.value)
            except:
                drop_vinculo.visible = False
                drop_vinculo_row.visible = False
                return
            
            cats = categorias_por_pilar.get(pilar, {})
            cat_info = cats.get(parent_id, {})
            root_name = cat_info.get("nome", "").upper()
            
            if root_name in ("VEÍCULO", "PET", "SAÚDE"):
                drop_vinculo.options = [
                    ft.dropdown.Option(key="geral", text=_t("Geral / Sem vínculo"))
                ]
                
                if root_name == "VEÍCULO":
                    drop_vinculo.label = _t("Veículo Vinculado")
                    veiculos_list = db.get_veiculos(state["perfil"])
                    for v in veiculos_list:
                        label_text = f"{v[2]} ({v[1]})" if v[1] else v[2]
                        drop_vinculo.options.append(ft.dropdown.Option(key=str(v[0]), text=label_text))
                elif root_name == "PET":
                    drop_vinculo.label = _t("Pet Vinculado")
                    pets_list = db.get_pets(state["perfil"])
                    for p in pets_list:
                        label_text = f"{p[1]} ({p[2]})" if p[2] else p[1]
                        drop_vinculo.options.append(ft.dropdown.Option(key=str(p[0]), text=label_text))
                elif root_name == "SAÚDE":
                    drop_vinculo.label = _t("Profissional / Serviço de Saúde")
                    saude_list = db.get_saude(state["perfil"])
                    for s in saude_list:
                        label_text = f"{s[1]} ({s[2]})" if s[2] else s[1]
                        drop_vinculo.options.append(ft.dropdown.Option(key=str(s[0]), text=label_text))
                
                if set_initial_val is not None:
                    drop_vinculo.value = str(set_initial_val)
                elif state.get("overlay_entity_type") == root_name.lower().replace("veículo", "veiculo") and state.get("overlay_entity_id"):
                    drop_vinculo.value = str(state.get("overlay_entity_id"))
                else:
                    drop_vinculo.value = "geral"
                    
                drop_vinculo.visible = True
                drop_vinculo_row.visible = True
            else:
                drop_vinculo.visible = False
                drop_vinculo_row.visible = False

        def update_subs_despesa(set_initial=None):
            pilar = drop_pilar.value
            try:
                parent_id = int(drop_cat.value)
            except:
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"
                update_vinculo_dropdown()
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

            initial_vinculo_val = "geral"
            if details:
                if details.get("veiculo_id"):
                    initial_vinculo_val = details["veiculo_id"]
                elif details.get("pet_id"):
                    initial_vinculo_val = details["pet_id"]
                elif details.get("saude_id"):
                    initial_vinculo_val = details["saude_id"]

            update_vinculo_dropdown(set_initial_val=initial_vinculo_val)
            page.update()

        def toggle_metodo_fields():
            is_cartao = drop_metodo.value == "Cartão"
            cartao_container.visible = is_cartao
            toggle_sharing_fields()
            page.update()

        def toggle_sharing_fields():
            is_shared = chk_compartilhar.value == True
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
                        text_style=ft.TextStyle(color=get_colors()["text"], size=14), 
                        label_style=ft.TextStyle(size=12),
                        height=48,
                        expand=True,
                        content_padding=ft.Padding(10, 5, 10, 5),
                        bgcolor=get_colors()["bg"], 
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
            
            is_individual = drop_div_tipo.value == "Individual" and drop_metodo.value == "Cartão"
            try:
                p_val = int(txt_parcelas.value or "1")
            except:
                p_val = 1
            show_btn = is_individual and p_val > 1
            btn_controle_fino.visible = show_btn
            lbl_controle_fino_status.visible = show_btn

            if not show_btn:
                divisoes_personalizadas.clear()
                lbl_controle_fino_status.value = "Controle fino por parcela não configurado (clique no botão para configurar)"
                lbl_controle_fino_status.color = "#94a3b8"

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
                    content=ft.Text(_t("Por favor, preencha a descrição, valor e data!"), color=get_colors()["text"]),
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
                    content=ft.Text("Valor ou parcelas inválidos!", color=get_colors()["text"]),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return

            if metodo == "Cartão" and drop_mes_inicio.value:
                try:
                    offset = int(drop_mes_inicio.value)
                    if offset > 0:
                        data_str = shift_months(data_str, offset)
                except Exception:
                    pass

            bandeira = ""
            dono = ""
            if metodo == "Cartão" and drop_cartao.value:
                parts = drop_cartao.value.split("|")
                bandeira = parts[0]
                dono = parts[1]

            divisoes = {}
            novo_nome = (txt_novo_perfil.value or "").strip() if txt_novo_perfil.visible else ""

            if chk_compartilhar.value == True:
                selected = [chk.data for chk in member_checks if chk.value == True]
                if not selected:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Selecione pelo menos um membro para dividir!", color=get_colors()["text"]),
                        bgcolor="#ef4444"
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                usa_controle_fino = False
                if divisoes_personalizadas and len(divisoes_personalizadas) == parcelas:
                    first_p_div = divisoes_personalizadas[0]
                    current_fine_members = set(first_p_div.keys())
                    selected_mapped = set(
                        (novo_nome if p == "Outro..." and novo_nome else p) if p != "Outro..." or novo_nome else "Desconhecido"
                        for p in selected
                    )
                    if current_fine_members == selected_mapped:
                        usa_controle_fino = True

                if drop_div_tipo.value == "Igualitária":
                    val_cota = valor / len(selected)
                    for p in selected:
                        nome_final = novo_nome if p == "Outro..." and novo_nome else p
                        if p == "Outro..." and not novo_nome: nome_final = "Desconhecido"
                        divisoes[nome_final] = val_cota
                elif usa_controle_fino:
                    divisoes = divisoes_personalizadas
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
                            content=ft.Text("A soma das cotas familiares deve bater com o total!", color=get_colors()["text"]),
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

            v_id = None
            p_id = None
            s_id = None

            if drop_vinculo.visible:
                val = drop_vinculo.value
                if val and val != "geral":
                    pilar = drop_pilar.value
                    try:
                        parent_id = int(drop_cat.value)
                        cats = categorias_por_pilar.get(pilar, {})
                        cat_info = cats.get(parent_id, {})
                        root_name = cat_info.get("nome", "").upper()
                        
                        selected_entity_id = int(val)
                        if root_name == "VEÍCULO":
                            v_id = selected_entity_id
                        elif root_name == "PET":
                            p_id = selected_entity_id
                        elif root_name == "SAÚDE":
                            s_id = selected_entity_id
                    except:
                        pass
            else:            v_id = None
            p_id = None
            s_id = None

            try:
                parent_id = int(drop_cat.value)
                cats = categorias_por_pilar.get(pilar, {})
                cat_name = cats.get(parent_id, {}).get("nome", "").upper()
            except:
                cat_name = ""

            if cat_name == "VEÍCULO":
                if drop_veiculo.value and drop_veiculo.value != "sem_vinculo":
                    try: v_id = int(drop_veiculo.value)
                    except: pass
            elif cat_name == "PET":
                if drop_pet.value and drop_pet.value != "sem_vinculo":
                    try: p_id = int(drop_pet.value)
                    except: pass
            elif cat_name == "SAÚDE":
                if drop_saude.value and drop_saude.value != "sem_vinculo":
                    try: s_id = int(drop_saude.value)
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
                    divisoes=divisoes,
                    veiculo_id=v_id,
                    pet_id=p_id,
                    saude_id=s_id,
                    keep_entity_links=False
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
                    observacao=obs,
                    veiculo_id=v_id,
                    pet_id=p_id,
                    saude_id=s_id
                )

            if success:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Despesa salva com sucesso!" if details else "Despesa adicionada com sucesso!", color=get_colors()["text"]),
                    bgcolor="#10b981"
                )
                page.snack_bar.open = True
                fechar_overlay()
                if state["active_tab"] == "cartoes":
                    render_cartoes()
                elif state["active_tab"] == "transacoes":
                    render_transacoes()
                elif state["active_tab"] == "financiamentos":
                    render_financiamentos()
                elif state["active_tab"] == "veiculos":
                    render_veiculos()
                elif state["active_tab"] == "pets":
                    render_pets()
                elif state["active_tab"] == "saude":
                    render_saude()
                else:
                    render_dashboard()
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"{_t('Erro ao salvar:')} {msg}", color=get_colors()["text"]),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()

        def excluir_despesa(e):
            def confirmar_delecao(e):
                page.pop_dialog()
                success, msg = db.deletar_transacao(details["id"])
                if success:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("Despesa excluída com sucesso!", color=get_colors()["text"]),
                        bgcolor="#10b981"
                    )
                    page.snack_bar.open = True
                    fechar_overlay()
                    if state["active_tab"] == "cartoes":
                        render_cartoes()
                    elif state["active_tab"] == "transacoes":
                        render_transacoes()
                    elif state["active_tab"] == "financiamentos":
                        render_financiamentos()
                    else:
                        render_dashboard()
                else:
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"{_t('Erro ao excluir:')} {msg}", color=get_colors()["text"]),
                        bgcolor="#ef4444"
                    )
                    page.snack_bar.open = True
                    page.update()

            def fechar_dialog(e):
                page.pop_dialog()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(_t("CONFIRMAR EXCLUSÃO ⚠️"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                content=ft.Text("Deseja realmente excluir permanentemente esta despesa?", size=14, color=get_colors()["subtext"]),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=fechar_dialog, style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton("EXCLUIR", on_click=confirmar_delecao, bgcolor="#ef4444", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

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
            
            # Ativa compartilhamento se houver divisões com outros membros cadastrados
            has_other_members = details["divisoes"] and (len(details["divisoes"]) > 1 or "Eu" not in details["divisoes"])
            if has_other_members:
                chk_compartilhar.value = True
                sharing_container.visible = True
                
            # Pré-preenche vínculos se existirem
            if details.get("veiculo_id"):
                drop_veiculo.value = str(details["veiculo_id"])
            if details.get("pet_id"):
                drop_pet.value = str(details["pet_id"])
            if details.get("saude_id"):
                drop_saude.value = str(details["saude_id"])
        else:
            # Caso seja um novo lançamento originado de uma aba específica
            ent_type = state.get("overlay_entity_type")
            ent_id = state.get("overlay_entity_id")
            if ent_type == "veiculo" and ent_id and ent_id != "geral":
                drop_veiculo.value = str(ent_id)
            elif ent_type == "pet" and ent_id and ent_id != "geral":
                drop_pet.value = str(ent_id)
            elif ent_type == "saude" and ent_id and ent_id != "geral":
                drop_saude.value = str(ent_id)

        update_vinculo_dropdown()

        # Action buttons layout
        action_buttons = []
        if details:
            action_buttons.append(
                ft.ElevatedButton(
                    content="EXCLUIR",
                    color="white",
                    bgcolor="#ef4444",
                    height=45,
                    on_click=excluir_despesa,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                )
            )
            action_buttons.append(
                ft.ElevatedButton(
                    content="SALVAR ALTERAÇÕES",
                    color="white",
                    bgcolor="#10b981",
                    height=45,
                    expand=True,
                    on_click=salvar_despesa,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                )
            )
        else:
            action_buttons.append(
                ft.ElevatedButton(
                    content="SALVAR DESPESA",
                    color="white",
                    bgcolor="#ef4444",
                    height=45,
                    expand=True,
                    on_click=salvar_despesa,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
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
            ft.Row([chk_compartilhar, ft.Container(width=15)]),
            sharing_container,
            banner_recorrencia_desp,
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
            initial_parent = details["parent_id"] if details["parent_id"] is not None else details["categoria_id"]
            update_cats_despesa(set_initial=initial_parent)
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
        saldo_anterior = db.get_saldo_acumulado_anterior(mes_atual, ano_atual, state["perfil"])
        saldo_total = saldo_anterior + saldo
        subtexto = f"Saldo Mês: R$ {saldo:,.2f} | Ant: R$ {saldo_anterior:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if saldo_anterior != 0 else None

        todas_transacoes = db.get_transacoes(mes=mes_atual, ano=ano_atual, perfil_nome=state["perfil"])
        lista_despesas = [t for t in todas_transacoes if "Despesa" in t[5]]
        lista_receitas = [t for t in todas_transacoes if "Receita" in t[5] or "Investimento" in t[5]]

        top_cards = ft.Row(
            spacing=20,
            controls=[
                criar_card_resumo(_t("Saldo Total"), saldo_total, "#10b981" if saldo_total >= 0 else "#ef4444", subtexto=subtexto),
                criar_card_resumo(_t("Despesas"), despesas, "#ef4444"),
                criar_card_resumo(_t("Receitas"), receitas, "#10b981"),
                criar_card_resumo(_t("Investido"), investido, "#3b82f6")
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
            if state["perfil"] == "Eu":
                right_panel = criar_lista_transacoes(_t("Receitas do Mês"), lista_receitas, False)
            else:
                anotacoes_iniciais = db.get_anotacoes_usuario(state["perfil"])
                txt_anotacoes = ft.TextField(
                    multiline=True,
                    min_lines=12,
                    max_lines=18,
                    bgcolor=get_colors()["bg"],
                    border_color=get_colors()["border"],
                    focused_border_color="#3b82f6",
                    text_style=ft.TextStyle(color=get_colors()["text"], size=14),
                    hint_text=_t("Digite aqui suas anotações para este subperfil (compras futuras, mudanças de valores, etc.)..."),
                    hint_style=ft.TextStyle(color="#64748b", size=14),
                    value=anotacoes_iniciais,
                    expand=True,
                    on_change=lambda e: db.update_anotacoes_usuario(state["perfil"], e.control.value)
                )
                right_panel = ft.Container(
                    expand=True,
                    bgcolor=get_colors()["surface"],
                    border=ft.border.all(1, get_colors()["border"]),
                    border_radius=12,
                    padding=20,
                    content=ft.Column(
                        expand=True,
                        controls=[
                            ft.Text(_t("Anotações do Subperfil"), size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.Divider(color="#334155"),
                            ft.Container(expand=True, content=txt_anotacoes)
                        ]
                    )
                )

            main_panels = ft.Row(
                expand=True,
                spacing=20,
                controls=[
                    criar_lista_transacoes(_t("Despesas do Mês"), lista_despesas, True),
                    right_panel
                ]
            )
        else: # charts
            cat_despesas = get_top_categorias(lista_despesas)
            left_chart = ft.Container(expand=True)
            left_title = _t("Despesas por Categoria")
            if not cat_despesas:
                left_chart = ft.Text(_t("Sem dados de despesas"), color="#64748b")
            else:
                if state["chart_left_idx"] == 0:
                    left_title = _t("Despesas por Categoria")
                    dados = [x[1] for x in cat_despesas]
                    labels = [x[0] for x in cat_despesas]
                    b64 = gerar_grafico_base64("pizza", dados, labels, despesas_colors)
                    left_chart = ft.Image(src="data:image/png;base64,"+b64, fit="contain")
                else:
                    left_title = _t("Top 5 Despesas")
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
                                        ft.Text(cat[:20], size=12, color=get_colors()["subtext"]),
                                        ft.Text(f"R$ {val:,.2f}", size=12, color=get_colors()["text"], weight="bold")
                                    ]),
                                    ft.Container(
                                        width=None, height=12, border_radius=6, bgcolor=get_colors()["bg"],
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
            right_title = _t("Receitas por Categoria")
            if not cat_receitas and not lista_despesas:
                right_chart = ft.Text(_t("Sem dados no mês"), color="#64748b")
            else:
                if state["chart_right_idx"] == 0:
                    right_title = _t("Receitas por Categoria")
                    dados = [x[1] for x in cat_receitas]
                    labels = [x[0] for x in cat_receitas]
                    if dados:
                        b64 = gerar_grafico_base64("pizza", dados, labels, receitas_colors)
                        right_chart = ft.Image(src="data:image/png;base64,"+b64, fit="contain")
                    else:
                        right_chart = ft.Text(_t("Sem receitas"), color="#64748b")
                else:
                    right_title = _t("Fluxo de Caixa")
                    fluxo = get_fluxo_diario(lista_receitas + lista_despesas)
                    dados = [x[1] for x in fluxo]
                    labels = [str(x[0]) for x in fluxo]
                    if dados:
                        b64 = gerar_grafico_base64("fluxo", dados, labels, [])
                        right_chart = ft.Image(src="data:image/png;base64,"+b64, fit="contain")
                    else:
                        right_chart = ft.Text(_t("Sem fluxo"), color="#64748b")

            right_panel = criar_painel_grafico(right_title, right_chart, lambda e: change_chart_right(e, -1), lambda e: change_chart_right(e, 1))
            
            main_panels = ft.Row(
                expand=True,
                spacing=20,
                controls=[left_panel, right_panel]
            )

        def on_change_perfil_dash(e):
            state["perfil"] = e.control.value
            render_dashboard()

        seletor_perfil = criar_seletor_perfil(on_change_perfil_dash)

        def toggle_dashboard_grouping(e):
            pass  # Agrupamento migrado para dentro de cada painel (group_despesas / group_receitas)

        # Sub-controles da aba Dashboard: botão categoria + navegador de mês
        btn_criar_cat = ft.IconButton(
            icon=ft.icons.Icons.CATEGORY_ROUNDED,
            tooltip=_t("Criar Categoria"),
            icon_color="#64748b",
            icon_size=20,
            on_click=abrir_criar_categoria_modal
        )
        nav_mes = ft.Row(
            spacing=4,
            controls=[
                ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", icon_size=18, on_click=prev_month),
                ft.Container(
                    bgcolor=get_colors()["surface"],
                    border=ft.border.all(1, get_colors()["border"]),
                    padding=ft.Padding(left=12, top=6, right=12, bottom=6),
                    border_radius=20,
                    content=ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.icons.Icons.CALENDAR_MONTH_ROUNDED, color="#94a3b8", size=16),
                            ft.Text(f"{_t(mes_atual)} {ano_atual}", size=14, weight=ft.FontWeight.W_500, color=get_colors()["subtext"])
                        ]
                    )
                ),
                ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", icon_size=18, on_click=next_month),
            ]
        )

        tab_header = criar_tab_header(
            "dashboard",
            seletor_perfil,
            subcontroles=[btn_criar_cat, nav_mes]
        )

        dashboard_view.controls = [
            tab_header,
            ft.Container(height=8),
            top_cards,
            ft.Container(height=16),
            main_panels
        ]
        
        # Garante que o FAB aparece apenas na Dashboard
        contrair_fab()

        body.content = dashboard_view
        page.update()

    def render_resumo_anual():
        months_data = []
        for mes_nome in meses_pt:
            resumo = db.get_resumo_financeiro(mes_nome, str(state["ano"]), state["perfil"])
            receitas = resumo.get("Receita Fixa", 0) + resumo.get("Receita Variável", 0)
            despesas = resumo.get("Despesa Fixa", 0) + resumo.get("Despesa Variável", 0)
            investido = resumo.get("Investimento", 0)
            saldo_mes = receitas - despesas - investido
            
            months_data.append({
                "name": mes_nome,
                "receitas": receitas,
                "despesas": despesas,
                "investido": investido,
                "saldo_mes": saldo_mes
            })

        if "resumo_anual_selection" not in state or len(state["resumo_anual_selection"]) != 12:
            state["resumo_anual_selection"] = {m: True for m in meses_pt}
            
        lbl_total_receitas = ft.Text("", size=28, weight=ft.FontWeight.BOLD, color="#10b981")
        lbl_total_despesas = ft.Text("", size=28, weight=ft.FontWeight.BOLD, color="#ef4444")
        lbl_total_investido = ft.Text("", size=28, weight=ft.FontWeight.BOLD, color="#3b82f6")
        lbl_total_fluxo = ft.Text("", size=28, weight=ft.FontWeight.BOLD, color=get_colors()["text"])

        def atualizar_totais_page():
            sum_rec = 0.0
            sum_desp = 0.0
            sum_inv = 0.0
            
            for m_data in months_data:
                if state["resumo_anual_selection"][m_data["name"]]:
                    sum_rec += m_data["receitas"]
                    sum_desp += m_data["despesas"]
                    sum_inv += m_data["investido"]
                    
            sum_fluxo = sum_rec - sum_desp - sum_inv
            
            lbl_total_receitas.value = f"R$ {sum_rec:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lbl_total_despesas.value = f"R$ {sum_desp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lbl_total_investido.value = f"R$ {sum_inv:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lbl_total_fluxo.value = f"R$ {sum_fluxo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lbl_total_fluxo.color = "#10b981" if sum_fluxo >= 0 else "#ef4444"
            try:
                page.update()
            except:
                pass

        def on_toggle_month_page(mes_nome, e):
            state["resumo_anual_selection"][mes_nome] = e.control.value
            atualizar_totais_page()

        def prev_year_anual(e):
            state["ano"] -= 1
            render_resumo_anual()
            
        def next_year_anual(e):
            state["ano"] += 1
            render_resumo_anual()
            
        def on_change_perfil_anual(e):
            state["perfil"] = e.control.value
            render_resumo_anual()

        seletor_perfil = criar_seletor_perfil(on_change_perfil_anual)

        # Sub-controles da aba Resumo Anual: navegador de ano
        nav_ano = ft.Row(
            spacing=4,
            controls=[
                ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", icon_size=18, on_click=prev_year_anual),
                ft.Container(
                    bgcolor=get_colors()["surface"],
                    border=ft.border.all(1, get_colors()["border"]),
                    padding=ft.Padding(12, 6, 12, 6),
                    border_radius=20,
                    content=ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.icons.Icons.CALENDAR_TODAY_ROUNDED, color="#94a3b8", size=16),
                            ft.Text(str(state["ano"]), size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                        ]
                    )
                ),
                ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", icon_size=18, on_click=next_year_anual),
            ]
        )

        tab_header = criar_tab_header(
            "resumo_anual",
            seletor_perfil,
            subcontroles=[nav_ano]
        )

        card_receitas = criar_card_resumo(_t("Receitas"), 0.0, "#10b981", get_colors()["surface"])
        card_despesas = criar_card_resumo(_t("Despesas"), 0.0, "#ef4444", get_colors()["surface"])
        card_investido = criar_card_resumo(_t("Investido"), 0.0, "#3b82f6", get_colors()["surface"])
        card_fluxo = criar_card_resumo(_t("Saldo Líquido"), 0.0, "#10b981", get_colors()["surface"])

        card_receitas.content.controls[1] = lbl_total_receitas
        card_despesas.content.controls[1] = lbl_total_despesas
        card_investido.content.controls[1] = lbl_total_investido
        card_fluxo.content.controls[1] = lbl_total_fluxo

        totals_cards_row = ft.Row(
            controls=[card_receitas, card_despesas, card_investido, card_fluxo],
            spacing=15
        )

        colors = get_colors()
        header_table = ft.Container(
            bgcolor=colors["bg"],
            padding=ft.Padding(left=15, top=10, right=15, bottom=10),
            border_radius=8,
            content=ft.Row(
                controls=[
                    ft.Container(content=ft.Text(_t("Mês"), size=11, weight=ft.FontWeight.BOLD, color=colors["text"]), expand=1),
                    ft.Container(content=ft.Text(_t("Receitas"), size=11, weight=ft.FontWeight.BOLD, color="#10b981"), expand=1),
                    ft.Container(content=ft.Text(_t("Despesas"), size=11, weight=ft.FontWeight.BOLD, color="#ef4444"), expand=1),
                    ft.Container(content=ft.Text(_t("Investido"), size=11, weight=ft.FontWeight.BOLD, color="#3b82f6"), expand=1),
                    ft.Container(content=ft.Text(_t("Saldo"), size=11, weight=ft.FontWeight.BOLD, color=colors["text"]), expand=1),
                ]
            )
        )

        rows_controls = []
        for m_data in months_data:
            val_rec = m_data["receitas"]
            val_desp = m_data["despesas"]
            val_inv = m_data["investido"]
            val_saldo = m_data["saldo_mes"]
            
            chk = ft.Checkbox(
                value=state["resumo_anual_selection"][m_data["name"]],
                on_change=lambda e, mn=m_data["name"]: on_toggle_month_page(mn, e),
                fill_color={"": "#3b82f6"},
                scale=0.8
            )
            
            row_cont = ft.Container(
                padding=ft.Padding(left=10, top=4, right=10, bottom=4),
                border=ft.border.Border(bottom=ft.border.BorderSide(1, colors["border"])),
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Row([
                                chk,
                                ft.Text(_t(m_data["name"]), size=12, color=colors["text"], weight=ft.FontWeight.W_500)
                            ], spacing=2),
                            expand=1
                        ),
                        ft.Container(content=ft.Text(f"R$ {val_rec:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, color="#10b981"), expand=1),
                        ft.Container(content=ft.Text(f"R$ {val_desp:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, color="#ef4444"), expand=1),
                        ft.Container(content=ft.Text(f"R$ {val_inv:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, color="#3b82f6"), expand=1),
                        ft.Container(content=ft.Text(f"R$ {val_saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, color="#10b981" if val_saldo >= 0 else "#ef4444", weight=ft.FontWeight.BOLD), expand=1),
                    ]
                )
            )
            rows_controls.append(row_cont)

        table_panel = ft.Container(
            bgcolor=colors["surface"],
            border=ft.border.all(1, colors["border"]),
            border_radius=12,
            padding=20,
            expand=True,
            content=ft.Column([
                header_table,
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        scroll=ft.ScrollMode.ADAPTIVE,
                        controls=rows_controls,
                        spacing=0
                    )
                )
            ], spacing=10)
        )

        layout = ft.Column(
            expand=True,
            controls=[
                tab_header,
                ft.Container(height=5),
                totals_cards_row,
                ft.Container(height=10),
                table_panel
            ],
            spacing=10,
            scroll=ft.ScrollMode.ADAPTIVE
        )

        page.floating_action_button = None
        body.content = layout
        atualizar_totais_page()


        
    def render_cartoes():
        mes_atual_pt = meses_pt[state["mes_idx"]]
        mes_num = str(state["mes_idx"] + 1).zfill(2)
        ano_atual = str(state["ano"])
        
        color_selectors = []
        
        # Title and Cancel Button controls defined up front for direct property updates
        form_title_text = ft.Text(
            _t("Editar Cartão") if state["editing_card_id"] is not None else _t("Cadastrar Novo Cartão"),
            size=18,
            weight=ft.FontWeight.BOLD,
            color=get_colors()["text"]
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
            form_title_text.value = _t("Cadastrar Novo Cartão")
            cancel_btn.visible = False
            
            # Reset color selectors UI
            update_color_selectors_ui("#1e293b")
            
            page.update()

        cancel_btn = ft.TextButton(
            content=ft.Text(_t("CANCELAR"), size=13, weight=ft.FontWeight.BOLD, color="#ef4444"),
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
            label=_t("Nome do Cartão"),
            hint_text="Ex: Nubank, Itaú",
            value=state.get("form_nome", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"]
        )
        txt_dono = ft.TextField(
            label=_t("Dono do Cartão"),
            hint_text="Ex: João, Maria",
            value=state.get("form_dono", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"]
        )
        txt_bandeira = ft.Dropdown(
            label=_t("Bandeira"),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"],
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
            label=_t("Limite Total (R$)"),
            hint_text="Ex: 5000.00",
            value=state.get("form_limite", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"]
        )
        txt_fechamento = ft.TextField(
            label=_t("Dia do Fechamento"),
            hint_text="Ex: 5 (1-31)",
            value=state.get("form_fechamento", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"]
        )
        txt_vencimento = ft.TextField(
            label=_t("Dia do Vencimento"),
            hint_text="Ex: 12 (1-31)",
            value=state.get("form_vencimento", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"]
        )
        txt_digitos = ft.TextField(
            label=_t("Últimos 4 Dígitos"),
            hint_text="Ex: 1234",
            max_length=4,
            value=state.get("form_digitos", ""),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"],
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
                form_title_text.value = _t("Editar Cartão")
                cancel_btn.visible = True
                
                # Update color selectors UI
                update_color_selectors_ui(card[5])
                
                page.update()

        def delete_cartao_click(card_id):
            success, msg = db.delete_cartao(card_id)
            if success:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(_t("Cartão excluído com sucesso!"), color=get_colors()["text"]),
                    bgcolor="#10b981"
                )
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"{_t('Erro ao excluir:')} {msg}", color=get_colors()["text"]),
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
        def criar_card_fisico(cartao_id, nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, gasto_mes, gasto_total, digitos):
            disponivel = limite - gasto_total
            pct_gasto = min(1.0, gasto_total / limite) if limite > 0 else 0.0
            
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
                                    content=ft.Text(nome, size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                                ),
                                ft.Container(
                                    padding=ft.Padding(left=8, top=2, right=8, bottom=2),
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
                                ft.Text(f"••••  ••••  ••••  {digitos}", size=14, color=get_colors()["text"], weight=ft.FontWeight.W_500)
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
                                        ft.Text(f"{_t('Limite')}: R$ {limite:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=8.5, color="#ccffffff"),
                                        ft.Text(f"{_t('Mês')}: R$ {gasto_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=8.5, color="#ccffffff"),
                                        ft.Text(f"{_t('Usado')}: R$ {gasto_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=8.5, color="#ccffffff")
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
            ("#820ad1", "Roxo Nubank"),
            ("#ff7a00", "Laranja Inter"),
            ("#111111", "Preto C6 Carbon"),
            ("#00d2f3", "Azul Neon"),
            ("#cc092f", "Bradesco"),
            ("#ec0000", "Santander"),
            ("#ffe600", "BB Amarelo"),
            ("#002f6c", "Itaú Navy"),
            ("#d4af37", "Personnalité Dourado"),
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
                    content=ft.Text("Por favor, preencha todos os campos!", color=get_colors()["text"]),
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
                    content=ft.Text("Valores inválidos para limite ou dias!", color=get_colors()["text"]),
                    bgcolor="#ef4444"
                )
                page.snack_bar.open = True
                page.update()
                return
                
            if not (1 <= dia_fechamento <= 31) or not (1 <= dia_vencimento <= 31):
                page.snack_bar = ft.SnackBar(
                    content=ft.Text("Dias de fechamento e vencimento devem ser entre 1 e 31!", color=get_colors()["text"]),
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
                    content=ft.Text(msg, color=get_colors()["text"]),
                    bgcolor="#10b981"
                )
            else:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"{_t('Erro:')} {msg}", color=get_colors()["text"]),
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
            gasto_total = db.get_gasto_cartao_total(bandeira_val, dono_val, mes_num, ano_atual)
            cards_list.append(
                criar_card_fisico(card_id, nome_val, limite_val, dia_fechamento_val, dia_vencimento_val, cor_val, bandeira_val, dono_val, gasto_mes, gasto_total, digitos_val)
            )

        if not cards_list:
            cards_grid = ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.icons.Icons.CREDIT_CARD_ROUNDED, size=60, color="#334155"),
                    ft.Text(_t("Nenhum cartão cadastrado"), size=16, color="#64748b", weight=ft.FontWeight.BOLD),
                    ft.Text(_t("Use o formulário ao lado para cadastrar seu primeiro cartão."), size=12, color="#475569")
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
            bgcolor=get_colors()["surface"],
            border=ft.border.all(1, get_colors()["border"]),
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
                            ft.Text("Cor do Cartão", size=12, color=get_colors()["subtext"], weight=ft.FontWeight.W_500),
                            ft.Row(controls=color_selectors, spacing=8, wrap=True)
                        ]
                    ),
                    ft.Container(height=5),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            cancel_btn,
                            ft.ElevatedButton(
                                content="SALVAR",
                                color="white",
                                bgcolor="#3b82f6",
                                height=40,
                                on_click=save_card,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
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
                        ft.Text(_t("Cartões de Crédito"), size=24, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Text(_t("Gerencie seus limites e faturas"), size=14, color="#64748b")
                    ]
                ),
                ft.Row(
                    spacing=5,
                    controls=[
                        ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", on_click=prev_month),
                        ft.Container(
                            bgcolor=get_colors()["surface"],
                            border=ft.border.all(1, get_colors()["border"]),
                            padding=ft.Padding(left=15, top=8, right=15, bottom=8),
                            border_radius=20,
                            content=ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Icon(ft.icons.Icons.CALENDAR_MONTH_ROUNDED, color="#94a3b8", size=18),
                                    ft.Text(f"{_t(mes_atual_pt)} {ano_atual}", size=16, weight=ft.FontWeight.W_500, color=get_colors()["subtext"])
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
        import collections
        mes_atual = meses_pt[state["mes_idx"]]
        ano_atual = str(state["ano"])
        tab_active = state.get("investimentos_tab_active", "patrimonio")
        cotacoes_cache = state.get("cotacoes_cache", {})
        cotacoes_status = state.get("cotacoes_status", "idle")
        
        state["simular_ir"] = db.get_preferencia("simular_ir", "False") == "True"
        if "dpg_inputs" not in state:
            state["dpg_inputs"] = {}

        def fmt(val):
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        tipo_cores = {
            "Ação": "#3b82f6", "FII": "#10b981", "ETF": "#a78bfa",
            "Tesouro": "#fbbf24", "CDB": "#fb923c", "RDB": "#ec4899", "Cripto": "#f472b6",
        }
        tipo_ordem = ["Ação", "FII", "ETF", "Tesouro", "CDB", "RDB", "Cripto"]
        meses_nomes_curtos = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

        # ── DISPARAR BUSCA DE CDI MENSAL ──────────────────────────────
        def cdi_update_worker():
            db.atualizar_cdi_sgs()
        
        # Dispara atualização em segundo plano se necessário
        threading.Thread(target=cdi_update_worker, daemon=True).start()

        # ── RECUPERAÇÃO DE DADOS BÁSICOS ──────────────────────────────
        total_aportado = db.get_total_investido_cumulativo(state["perfil"])
        carteira_ops = db.get_carteira()
        dividendos = db.get_dividendos_mes(mes_atual, ano_atual, state["perfil"])

        def parse_date(date_str):
            try:
                return datetime.datetime.strptime(date_str, "%d/%m/%Y")
            except:
                return datetime.datetime.min

        carteira_ops_sorted = sorted(carteira_ops, key=lambda x: parse_date(x[6]))

        # Reconstrução de Posições
        posicoes = {}
        for op in carteira_ops_sorted:
            op_id, ticker, tipo, operacao, qtd, preco, data_op, corretora, obs = op[:9]
            if ticker not in posicoes:
                posicoes[ticker] = {"qtd": 0.0, "custo_total": 0.0, "tipo": tipo, "ops": []}
            
            if operacao == "Compra":
                posicoes[ticker]["qtd"] += qtd
                posicoes[ticker]["custo_total"] += qtd * preco
            elif operacao == "Venda":
                pm_antes = 0.0
                if posicoes[ticker]["qtd"] > 0:
                    pm_antes = posicoes[ticker]["custo_total"] / posicoes[ticker]["qtd"]
                posicoes[ticker]["qtd"] = max(0.0, posicoes[ticker]["qtd"] - qtd)
                posicoes[ticker]["custo_total"] = posicoes[ticker]["qtd"] * pm_antes
            
            posicoes[ticker]["ops"].append(op)

        for k in posicoes.keys():
            posicoes[k]["ops"].reverse()

        posicoes_ativas = {k: v for k, v in posicoes.items() if v["qtd"] > 0.0001}
        acoes_ativas = {k: v for k, v in posicoes_ativas.items() if v["tipo"] == "Ação"}
        patrimonio_custo = sum(p["custo_total"] for p in posicoes_ativas.values())
        saldo_disponivel = max(0.0, total_aportado - patrimonio_custo)

        valor_mercado = 0.0
        for ticker, pos in posicoes_ativas.items():
            cot_p = cotacoes_cache.get(ticker, {}).get("preco")
            valor_mercado += pos["qtd"] * cot_p if cot_p else pos["custo_total"]
        variacao_total = valor_mercado - patrimonio_custo

        # ── MATRIZ DE RENTABILIDADE E PATRIMÔNIO HISTÓRICO ───────────
        def obter_historico_patrimonio_local():
            hoje = datetime.date.today()
            meses_alvo = []
            for i in range(11, -1, -1):
                ano_diff = (hoje.month - 1 - i) // 12
                m_idx = (hoje.month - 1 - i) % 12 + 1
                a = hoje.year + ano_diff
                meses_alvo.append((m_idx, a))
                
            def parse_date_internal(d_str):
                try:
                    return datetime.datetime.strptime(d_str, "%d/%m/%Y").date()
                except:
                    return datetime.date.min
                    
            meses_lbls = []
            vals_aplicados = []
            vals_mercado = []
            
            for m, y in meses_alvo:
                if m == 12:
                    ultimo_dia = datetime.date(y, 12, 31)
                else:
                    ultimo_dia = datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)
                    
                pos_no_mes = {}
                for op in carteira_ops:
                    tk = op[1]; tp = op[2]; operacao = op[3]; qtd = op[4]; preco = op[5]; dt_op = parse_date_internal(op[6])
                    if dt_op <= ultimo_dia:
                        if tk not in pos_no_mes:
                            pos_no_mes[tk] = {"qtd": 0.0, "custo_total": 0.0, "tipo": tp, "primeira_compra": dt_op}
                        if operacao == "Compra":
                            pos_no_mes[tk]["qtd"] += qtd
                            pos_no_mes[tk]["custo_total"] += qtd * preco
                        elif operacao == "Venda":
                            pm = pos_no_mes[tk]["custo_total"] / pos_no_mes[tk]["qtd"] if pos_no_mes[tk]["qtd"] > 0 else 0.0
                            pos_no_mes[tk]["qtd"] = max(0.0, pos_no_mes[tk]["qtd"] - qtd)
                            pos_no_mes[tk]["custo_total"] = pos_no_mes[tk]["qtd"] * pm
                            
                tot_ap = 0.0
                tot_mer = 0.0
                
                for tk, p_info in pos_no_mes.items():
                    if p_info["qtd"] > 0.0001:
                        cost = p_info["custo_total"]
                        tot_ap += cost
                        
                        cot_atual = cotacoes_cache.get(tk, {}).get("preco")
                        pm_compra = cost / p_info["qtd"]
                        
                        if cot_atual is None:
                            val_merc = cost
                        else:
                            total_days = (hoje - p_info["primeira_compra"]).days
                            elapsed_days = (ultimo_dia - p_info["primeira_compra"]).days
                            if total_days <= 0 or elapsed_days <= 0:
                                val_merc = cost
                            elif elapsed_days >= total_days:
                                val_merc = p_info["qtd"] * cot_atual
                            else:
                                ratio = elapsed_days / total_days
                                p_interp = pm_compra + (cot_atual - pm_compra) * ratio
                                val_merc = p_info["qtd"] * p_interp
                        tot_mer += val_merc
                        
                meses_lbls.append(f"{m:02d}/{str(y)[2:]}")
                vals_aplicados.append(tot_ap)
                vals_mercado.append(tot_mer)
                
            return meses_lbls, vals_aplicados, vals_mercado

        def obter_historico_rentabilidade(meses, aplicados, mercado, db):
            cdi_anual = 10.50
            try:
                cdi_anual = float(db.get_preferencia("cdi_latest_rate", "10.50"))
            except:
                pass
            
            cdi_mensal = (1 + cdi_anual / 100) ** (1 / 12) - 1
            
            ret_carteira = []
            ret_cdi = []
            
            for i in range(len(meses)):
                ap = aplicados[i]
                mer = mercado[i]
                ret_c = ((mer - ap) / ap * 100) if ap > 0 else 0.0
                ret_carteira.append(ret_c)
                
            start_val = ret_carteira[0] if ret_carteira else 0.0
            for i in range(len(meses)):
                ret_cdi_val = start_val + ((1 + cdi_mensal) ** i - 1) * 100
                ret_cdi.append(ret_cdi_val)
                
            return ret_carteira, ret_cdi

        def obter_matriz_rentabilidade(carteira_ops, cotacoes_cache):
            import datetime
            hoje = datetime.date.today()
            anos = []
            def parse_date_internal(d_str):
                try:
                    return datetime.datetime.strptime(d_str, "%d/%m/%Y").date()
                except:
                    return datetime.date.min
            for op in carteira_ops:
                dt = parse_date_internal(op[6])
                if dt != datetime.date.min:
                    anos.append(dt.year)
            if not anos:
                anos = [hoje.year]
            ano_inicio = min(anos)
            ano_fim = hoje.year
            matriz_ret = {}
            totais_ret = {}
            for y in range(ano_inicio, ano_fim + 1):
                matriz_ret[y] = [0.0] * 12
            linha_tempo_meses = []
            for y in range(ano_inicio, ano_fim + 1):
                for m in range(1, 13):
                    if y == hoje.year and m > hoje.month:
                        continue
                    linha_tempo_meses.append((y, m))
            rentabilidades_acumuladas = {}
            rentabilidades_acumuladas[(ano_inicio, 0)] = 0.0
            for y, m in linha_tempo_meses:
                if m == 12:
                    ultimo_dia = datetime.date(y, 12, 31)
                else:
                    ultimo_dia = datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)
                pos_no_mes = {}
                for op in carteira_ops:
                    tk = op[1]; tp = op[2]; operacao = op[3]; qtd = op[4]; preco = op[5]; dt_op = parse_date_internal(op[6])
                    if dt_op <= ultimo_dia:
                        if tk not in pos_no_mes:
                            pos_no_mes[tk] = {"qtd": 0.0, "custo_total": 0.0, "tipo": tp, "primeira_compra": dt_op}
                        if operacao == "Compra":
                            pos_no_mes[tk]["qtd"] += qtd
                            pos_no_mes[tk]["custo_total"] += qtd * preco
                        elif operacao == "Venda":
                            pm = pos_no_mes[tk]["custo_total"] / pos_no_mes[tk]["qtd"] if pos_no_mes[tk]["qtd"] > 0 else 0.0
                            pos_no_mes[tk]["qtd"] = max(0.0, pos_no_mes[tk]["qtd"] - qtd)
                            pos_no_mes[tk]["custo_total"] = pos_no_mes[tk]["qtd"] * pm
                tot_ap = 0.0
                tot_mer = 0.0
                for tk, p_info in pos_no_mes.items():
                    if p_info["qtd"] > 0.0001:
                        cost = p_info["custo_total"]
                        tot_ap += cost
                        cot_atual = cotacoes_cache.get(tk, {}).get("preco")
                        pm_compra = cost / p_info["qtd"]
                        if cot_atual is None:
                            val_merc = cost
                        else:
                            total_days = (hoje - p_info["primeira_compra"]).days
                            elapsed_days = (ultimo_dia - p_info["primeira_compra"]).days
                            if total_days <= 0 or elapsed_days <= 0:
                                val_merc = cost
                            elif elapsed_days >= total_days:
                                val_merc = p_info["qtd"] * cot_atual
                            else:
                                ratio = elapsed_days / total_days
                                p_interp = pm_compra + (cot_atual - pm_compra) * ratio
                                val_merc = p_info["qtd"] * p_interp
                        tot_mer += val_merc
                rent_c = ((tot_mer - tot_ap) / tot_ap * 100) if tot_ap > 0 else 0.0
                rentabilidades_acumuladas[(y, m)] = rent_c
            for y in range(ano_inicio, ano_fim + 1):
                for m in range(1, 13):
                    if (y, m) not in rentabilidades_acumuladas:
                        matriz_ret[y][m - 1] = 0.0
                        continue
                    y_ant, m_ant = y, m - 1
                    if m_ant == 0:
                        y_ant, m_ant = y - 1, 12
                    rent_ant = rentabilidades_acumuladas.get((y_ant, m_ant), 0.0)
                    rent_atual = rentabilidades_acumuladas[(y, m)]
                    matriz_ret[y][m - 1] = rent_atual - rent_ant
                rent_fim_ano = rentabilidades_acumuladas.get((y, 12 if y < hoje.year else hoje.month), 0.0)
                rent_ini_ano = rentabilidades_acumuladas.get((y - 1, 12), 0.0)
                totais_ret[y] = rent_fim_ano - rent_ini_ano
            return matriz_ret, totais_ret

        meses_hist, aplicados_hist, mercado_hist = obter_historico_patrimonio_local()
        bar_labels = meses_hist
        mes_ano_lista_ultimos_12 = []
        hoje_temp = datetime.date.today()
        for i in range(11, -1, -1):
            ano_diff = (hoje_temp.month - 1 - i) // 12
            m_idx = (hoje_temp.month - 1 - i) % 12 + 1
            a = hoje_temp.year + ano_diff
            mes_ano_lista_ultimos_12.append((m_idx, a))

        # ── CÁLCULO DE IR ESTIMADO ──────────────────────────────────
        vendas_acoes_reais_mes = 0.0
        for op in carteira_ops:
            op_id, ticker_op, tipo_op, operacao_op, qtd_op, preco_op, data_op = op[:7]
            if tipo_op == "Ação" and operacao_op == "Venda":
                try:
                    dt = datetime.datetime.strptime(data_op, "%d/%m/%Y")
                    if dt.month == state["mes_idx"] + 1 and dt.year == state["ano"]:
                        vendas_acoes_reais_mes += qtd_op * preco_op
                except:
                    pass

        def calcular_ir_estimado(ticker, pos, current_price):
            if current_price is None:
                current_price = pos["custo_total"] / pos["qtd"] if pos["qtd"] > 0 else 0.0
            
            tipo = pos["tipo"]
            preco_medio = pos["custo_total"] / pos["qtd"] if pos["qtd"] > 0 else 0.0
            lucro_total = pos["qtd"] * (current_price - preco_medio)
            
            if lucro_total <= 0:
                return 0.0, "R$ 0,00", False
            
            if tipo == "Ação":
                vol_simulado = pos["qtd"] * current_price
                total_vol = vendas_acoes_reais_mes + vol_simulado
                if total_vol <= 20000.0:
                    return 0.0, "Isento (Vendas <= 20k)", True
                else:
                    return lucro_total * 0.15, f"Est. IR: 15% ({fmt(lucro_total * 0.15)})", False
            elif tipo == "FII":
                return lucro_total * 0.20, f"Est. IR: 20% ({fmt(lucro_total * 0.20)})", False
            elif tipo == "ETF":
                return lucro_total * 0.15, f"Est. IR: 15% ({fmt(lucro_total * 0.15)})", False
            elif tipo in ("CDB", "Tesouro"):
                ticker_ops = sorted(pos["ops"], key=lambda x: parse_date(x[6]))
                lots = []
                for op in ticker_ops:
                    op_id, tk, tp, operacao, qtd, preco, data_op = op[:7]
                    dt_op = parse_date(data_op)
                    if operacao == "Compra":
                        lots.append({"qtd": qtd, "preco": preco, "date": dt_op})
                    elif operacao == "Venda":
                        to_consume = qtd
                        while to_consume > 0 and lots:
                            if lots[0]["qtd"] <= to_consume:
                                to_consume -= lots[0]["qtd"]
                                lots.pop(0)
                            else:
                                lots[0]["qtd"] -= to_consume
                                to_consume = 0
                
                total_ir = 0.0
                total_profit = 0.0
                for lot in lots:
                    lot_profit = lot["qtd"] * (current_price - lot["preco"])
                    if lot_profit > 0:
                        total_profit += lot_profit
                        days = (datetime.datetime.now() - lot["date"]).days
                        if days <= 180: rate = 0.225
                        elif days <= 360: rate = 0.20
                        elif days <= 720: rate = 0.175
                        else: rate = 0.15
                        total_ir += lot_profit * rate
                
                eff_rate = (total_ir / total_profit * 100) if total_profit > 0 else 0.0
                return total_ir, f"Est. IR: {eff_rate:.1f}% ({fmt(total_ir)})", False
            
            return 0.0, "R$ 0,00", False

        # ── BUSCA DE COTAÇÕES E DIVIDENDOS ────────────────────────────
        def buscar_cotacoes():
            if not posicoes_ativas:
                state["cotacoes_cache"] = {}
                state["cotacoes_status"] = "idle"
                render_investimentos()
                return
            cache = {}
            success_count = 0
            for ticker in posicoes_ativas.keys():
                try:
                    import re, ssl, traceback
                    clean_ticker = ticker.strip().upper()
                    yticker = clean_ticker
                    if not clean_ticker.endswith(".SA") and re.search(r'\d+$', clean_ticker):
                        yticker = f"{clean_ticker}.SA"
                    
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yticker}"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    
                    res_data = None
                    try:
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            res_data = json.loads(resp.read().decode())
                    except Exception as err_ssl:
                        try:
                            context = ssl._create_unverified_context()
                            with urllib.request.urlopen(req, context=context, timeout=10) as resp:
                                res_data = json.loads(resp.read().decode())
                        except Exception as err_unverified:
                            raise err_unverified
                    
                    if res_data and "chart" in res_data and res_data["chart"].get("result"):
                        meta = res_data["chart"]["result"][0]["meta"]
                        price = meta.get("regularMarketPrice")
                        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
                        var_pct = 0.0
                        if price and prev_close:
                            var_pct = ((price - prev_close) / prev_close) * 100
                        
                        cache[ticker] = {
                            "preco": price,
                            "variacao": var_pct,
                            "nome": meta.get("longName") or meta.get("shortName") or ticker,
                        }
                        success_count += 1
                except:
                    pass
            
            if success_count > 0:
                state["cotacoes_cache"] = cache
                state["cotacoes_status"] = "online"
            else:
                try:
                    import ssl
                    google_req = urllib.request.Request("https://www.google.com", headers={"User-Agent": "Mozilla/5.0"})
                    context = ssl._create_unverified_context()
                    with urllib.request.urlopen(google_req, context=context, timeout=5):
                        state["cotacoes_status"] = "api_error"
                except:
                    state["cotacoes_status"] = "offline"
            render_investimentos()

        def buscar_dividendos_web():
            if not posicoes_ativas:
                state["dividendos_web_data"] = []
                state["dividendos_web_status"] = "fetched"
                render_investimentos()
                return
            
            tickers_alvo = [tk for tk, pos in posicoes_ativas.items() if pos["tipo"] in ("Ação", "FII")]
            if not tickers_alvo:
                state["dividendos_web_data"] = []
                state["dividendos_web_status"] = "fetched"
                render_investimentos()
                return
                
            state["dividendos_web_status"] = "loading"
            render_investimentos()
            
            import urllib.request, json, ssl, time, re
            web_divs = []
            current_time = int(time.time())
            one_year_ago = current_time - 365 * 24 * 60 * 60
            one_year_future = current_time + 365 * 24 * 60 * 60
            context = ssl._create_unverified_context()
            
            for ticker in tickers_alvo:
                try:
                    clean_ticker = ticker.strip().upper()
                    yticker = clean_ticker
                    if not clean_ticker.endswith(".SA") and re.search(r'\d+$', clean_ticker):
                        yticker = f"{clean_ticker}.SA"
                        
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yticker}?period1={one_year_ago}&period2={one_year_future}&interval=1d&events=div"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    
                    res_data = None
                    try:
                        with urllib.request.urlopen(req, timeout=8) as resp:
                            res_data = json.loads(resp.read().decode())
                    except:
                        try:
                            with urllib.request.urlopen(req, context=context, timeout=8) as resp:
                                res_data = json.loads(resp.read().decode())
                        except:
                            pass
                            
                    if res_data and "chart" in res_data and res_data["chart"].get("result"):
                        result = res_data["chart"]["result"][0]
                        if "events" in result and "dividends" in result["events"]:
                            divs = result["events"]["dividends"]
                            for t_stamp_str, div_item in divs.items():
                                ex_date_val = int(div_item["date"])
                                amount = float(div_item["amount"])
                                dt_ex = datetime.datetime.fromtimestamp(ex_date_val)
                                ex_date_str = dt_ex.strftime("%d/%m/%Y")
                                
                                holdings_before_ex = 0.0
                                ticker_ops = [op for op in carteira_ops if op[1] == ticker]
                                
                                def get_op_dt(op_item):
                                    try: return datetime.datetime.strptime(op_item[6], "%d/%m/%Y")
                                    except: return datetime.datetime.min
                                    
                                ticker_ops_sorted = sorted(ticker_ops, key=get_op_dt)
                                
                                for op in ticker_ops_sorted:
                                    op_dt = get_op_dt(op)
                                    if op_dt < dt_ex:
                                        op_type = op[3]
                                        qtd = op[4]
                                        if op_type == "Compra": holdings_before_ex += qtd
                                        elif op_type == "Venda": holdings_before_ex = max(0.0, holdings_before_ex - qtd)
                                            
                                entitled = holdings_before_ex > 0.0001
                                val_to_receive = holdings_before_ex * amount if entitled else 0.0
                                
                                web_divs.append({
                                    "ticker": ticker,
                                    "ex_date": dt_ex,
                                    "ex_date_str": ex_date_str,
                                    "amount": amount,
                                    "holdings": holdings_before_ex,
                                    "entitled": entitled,
                                    "val_to_receive": val_to_receive
                                })
                except Exception as err:
                    sys.stderr.write(f"Erro ao buscar dividendos na web para {ticker}: {err}\n")
                    sys.stderr.flush()
                    
            web_divs = sorted(web_divs, key=lambda x: x["ex_date"], reverse=True)
            state["dividendos_web_data"] = web_divs
            state["dividendos_web_status"] = "fetched"
            try: render_investimentos()
            except: pass

        def set_tab_inv(tab_name):
            state["investimentos_tab_active"] = tab_name
            if tab_name == "rentabilidade":
                # Forçar atualização de CDI ao entrar se necessário
                render_investimentos()
            elif tab_name == "proventos" and state.get("dividendos_web_status") not in ("loading", "fetched"):
                state["dividendos_web_status"] = "loading"
                render_investimentos()
                threading.Thread(target=buscar_dividendos_web, daemon=True).start()
            else:
                render_investimentos()

        def _close_dlg():
            page.pop_dialog()

        def _do_del_op(oid):
            _close_dlg()
            db.delete_operacao_carteira(oid)
            state["cotacoes_status"] = "idle"
            fechar_overlay()
            render_investimentos()

        def confirm_delete_op(oid):
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text(_t("Confirmar Exclusão"), color=get_colors()["text"]),
                content=ft.Text(_t("Excluir esta operação permanentemente?"), color=get_colors()["subtext"]),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: _close_dlg()),
                    ft.TextButton(_t("EXCLUIR"), style=ft.ButtonStyle(color="#ef4444"), on_click=lambda e: _do_del_op(oid))
                ]
            )
            page.show_dialog(dlg)

        def mostrar_operacoes_ticker(ticker, pos):
            while len(overlay_stack.controls) > 1:
                overlay_stack.controls.pop()
            ops = pos["ops"]
            cor_tipo = tipo_cores.get(pos["tipo"], "#3b82f6")
            preco_medio = pos["custo_total"] / pos["qtd"] if pos["qtd"] > 0 else 0.0

            op_rows = []
            for op in ops:
                op_id, _t, _tipo, operacao, qtd, preco, data_op, corretora, _obs = op[:9]
                total = qtd * preco
                op_cor = "#10b981" if operacao == "Compra" else "#ef4444"
                
                desc_extra = ""
                if len(op) > 9:
                    data_venc, pct_cdi, subtipo = op[9:12]
                    if _tipo == "CDB" and pct_cdi:
                        desc_extra = f" • {pct_cdi:,.1f}% CDI"
                        if data_venc: desc_extra += f" (Venc: {data_venc})"
                    elif _tipo == "Tesouro" and subtipo:
                        desc_extra = f" • {subtipo}"

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
                                        ft.Text(data_op, size=12, color=get_colors()["subtext"])
                                    ], spacing=8),
                                    ft.Text(f"{qtd:,.0f} un × {fmt(preco)}{desc_extra}", size=11, color="#64748b")
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
                width=500, height=520, bgcolor=get_colors()["surface"], border_radius=16,
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
                            ft.Text(ticker, size=24, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.Text(f"{pos['qtd']:,.0f} un  •  PM: {fmt(preco_medio)}  •  Custo Total: {fmt(pos['custo_total'])}", size=12, color="#94a3b8")
                        ]),
                        ft.IconButton(ft.icons.Icons.CLOSE_ROUNDED, icon_color="#94a3b8", on_click=fechar_overlay)
                    ]),
                    ft.Row(alignment=ft.MainAxisAlignment.END, spacing=10, controls=[
                        ft.ElevatedButton(
                            "NOVA COMPRA", bgcolor="#3b82f6", color="white",
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda e, tk=ticker, tp=pos["tipo"]: [
                                fechar_overlay(),
                                abrir_form_operacao_inv(None, prefill_ticker=tk, prefill_tipo=tp, prefill_op="Compra")
                            ]
                        ),
                        ft.ElevatedButton(
                            "NOVA VENDA", bgcolor="#ef4444", color="white",
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda e, tk=ticker, tp=pos["tipo"]: [
                                fechar_overlay(),
                                abrir_form_operacao_inv(None, prefill_ticker=tk, prefill_tipo=tp, prefill_op="Venda")
                            ]
                        )
                    ]),
                    ft.Divider(color="#1f2937", height=12),
                    *( [
                        ft.Container(
                            padding=ft.Padding(10, 8, 10, 8),
                            bgcolor=get_colors()["surface"], border_radius=8,
                            content=ft.Row([
                                ft.Row([
                                    ft.Icon(ft.icons.Icons.MONETIZATION_ON_OUTLINED, color="#fbbf24", size=16),
                                    ft.Text("Simulação de Imposto:", size=12, color=get_colors()["text"], weight=ft.FontWeight.BOLD),
                                ], spacing=6),
                                ft.Text(
                                    calcular_ir_estimado(ticker, pos, cotacoes_cache.get(ticker, {}).get("preco"))[1],
                                    size=12,
                                    color="#10b981" if calcular_ir_estimado(ticker, pos, cotacoes_cache.get(ticker, {}).get("preco"))[2] else "#f59e0b",
                                    weight=ft.FontWeight.BOLD
                                )
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        )
                    ] if state.get("simular_ir", False) else [] ),
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

        def abrir_form_rendimento(e):
            while len(overlay_stack.controls) > 1:
                overlay_stack.controls.pop()

            txt_ticker_rend = ft.TextField(
                label=_t("Ticker / FII"), hint_text=_t("Ex: PETR4, MXRF11"),
                border_color="#374151", focused_border_color="#fbbf24",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                capitalization=ft.TextCapitalization.CHARACTERS
            )

            drop_tipo_rend = ft.Dropdown(
                label=_t("Tipo de Rendimento"), value="Rendimentos de Ações",
                border_color="#374151", focused_border_color="#fbbf24",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                options=[
                    ft.dropdown.Option(key="Rendimentos de Ações", text=_t("Rendimentos de Ações")),
                    ft.dropdown.Option(key="Rendimentos de FIIs", text=_t("Rendimentos de FIIs"))
                ]
            )

            txt_valor_rend = ft.TextField(
                label=_t("Valor Total (R$)"), hint_text=_t("Ex: 150.50"),
                border_color="#374151", focused_border_color="#fbbf24",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                keyboard_type=ft.KeyboardType.NUMBER
            )

            txt_data_rend = ft.TextField(
                label=_t("Data (DD/MM/AAAA)"), value=datetime.datetime.now().strftime("%d/%m/%Y"),
                border_color="#374151", focused_border_color="#fbbf24",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"]
            )

            drop_status_rend = ft.Dropdown(
                label=_t("Status"), value="Pago",
                border_color="#374151", focused_border_color="#fbbf24",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                options=[
                    ft.dropdown.Option(key="Pago", text=_t("Pago")),
                    ft.dropdown.Option(key="Provisionado", text=_t("Provisionado"))
                ]
            )

            list_sug_rend = ft.ListView(expand=True, spacing=2)
            cnt_sug_rend = ft.Container(
                bgcolor=get_colors()["surface"], border_radius=8,
                padding=5, height=100, visible=False,
                border=ft.Border(top=ft.BorderSide(1, "#374151"), bottom=ft.BorderSide(1, "#374151"), left=ft.BorderSide(1, "#374151"), right=ft.BorderSide(1, "#374151")),
                content=list_sug_rend
            )

            def selecionar_sug_rend(val):
                txt_ticker_rend.value = val
                cnt_sug_rend.visible = False
                fii_sugs = ["MXRF11", "HGLG11", "KNIP11", "KNRI11", "XPML11", "XPLG11", "VISC11", "BTLG11", "HGRU11"]
                if val in fii_sugs: drop_tipo_rend.value = "Rendimentos de FIIs"
                else: drop_tipo_rend.value = "Rendimentos de Ações"
                page.update()

            def filtrar_sug_rend(e=None):
                txt = (txt_ticker_rend.value or "").strip().upper()
                list_sug_rend.controls.clear()
                sugs = ["WEGE3", "ITUB4", "BBDC4", "VALE3", "PETR4", "BBAS3", "MXRF11", "HGLG11", "XPML11", "KNRI11"]
                filtered = [s for s in sugs if txt in s.upper()] if txt else sugs[:8]
                
                if filtered:
                    for s in filtered[:8]:
                        list_sug_rend.controls.append(
                            ft.Container(
                                content=ft.Text(s, size=12, color=get_colors()["text"], weight=ft.FontWeight.W_500),
                                padding=ft.Padding(10, 6, 10, 6), border_radius=4, ink=True,
                                on_click=lambda e, val=s: selecionar_sug_rend(val)
                            )
                        )
                    cnt_sug_rend.visible = True
                else:
                    cnt_sug_rend.visible = False
                page.update()

            txt_ticker_rend.on_change = filtrar_sug_rend

            def salvar_rendimento(e):
                try:
                    ticker_val = (txt_ticker_rend.value or "").strip().upper()
                    tipo_rend_val = drop_tipo_rend.value
                    data_val = (txt_data_rend.value or "").strip()
                    status_val = drop_status_rend.value
                    erros = []
                    if not ticker_val: erros.append("Ticker é obrigatório")
                    
                    try:
                        valor_val = float((txt_valor_rend.value or "").replace(",", "."))
                        if valor_val <= 0: erros.append("Valor deve ser > 0")
                    except:
                        erros.append("Valor inválido")
                        valor_val = 0.0

                    if erros:
                        page.snack_bar = ft.SnackBar(content=ft.Text("  •  ".join(erros), color="white"), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return

                    cat_id = db.get_categoria_id_by_nome(tipo_rend_val) or 8
                    desc_trans = f"Rendimento {ticker_val}"
                    
                    with db.get_connection() as conn:
                        cursor = conn.conn.cursor() if hasattr(db.get_connection(), "conn") else conn.cursor()
                        cursor.execute("SELECT id FROM Contas LIMIT 1")
                        row = cursor.fetchone()
                        conta_id = row[0] if row else 1

                    divisoes = None
                    if state["perfil"] != "Eu": divisoes = {state["perfil"]: valor_val}

                    success, msg = db.inserir_transacao(
                        conta_id=conta_id, categoria_id=cat_id, descricao=desc_trans,
                        data_ini=data_val, valor_total=valor_val, tipo_transacao="Receita Variável",
                        metodo="Dinheiro", observacao=status_val, divisoes=divisoes
                    )

                    if success:
                        fechar_overlay()
                        render_investimentos()
                    else:
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro:')} {msg}", color=get_colors()["text"]), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                except Exception as ex:
                    sys.stderr.write(f"\nError: {ex}\n")
                    sys.stderr.flush()

            col_ticker_container = ft.Column(spacing=2, expand=True, controls=[txt_ticker_rend, cnt_sug_rend])

            modal_card = ft.Container(
                width=450, height=480, bgcolor=get_colors()["surface"], border_radius=16,
                border=ft.border.Border(top=ft.border.BorderSide(1.5, "#1f2937"), bottom=ft.border.BorderSide(1.5, "#1f2937"), left=ft.border.BorderSide(3, "#fbbf24"), right=ft.border.BorderSide(1.5, "#1f2937")),
                padding=ft.Padding(25, 20, 25, 20),
                content=ft.Column(expand=True, spacing=10, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Text("💰 Lançar Rendimento Manual", size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.IconButton(ft.icons.Icons.CLOSE_ROUNDED, icon_color="#94a3b8", icon_size=22, on_click=fechar_overlay)
                    ]),
                    ft.Divider(color="#1f2937", height=12),
                    ft.Container(expand=True, content=ft.Column(
                        spacing=12, scroll=ft.ScrollMode.ADAPTIVE, expand=True,
                        controls=[
                            ft.Row([col_ticker_container, drop_tipo_rend], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
                            ft.Row([txt_valor_rend, txt_data_rend], spacing=10),
                            ft.Row([drop_status_rend], spacing=10),
                            ft.Container(height=10),
                            ft.Row(alignment=ft.MainAxisAlignment.END, controls=[
                                ft.ElevatedButton("SALVAR RENDIMENTO", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), bgcolor="#fbbf24", color="#111827", on_click=salvar_rendimento)
                            ])
                        ]
                    ))
                ])
            )
            shield = ft.Container(expand=True, bgcolor="#cc090d16", on_click=fechar_overlay)
            overlay_stack.controls.append(shield)
            overlay_stack.controls.append(modal_card)
            page.update()

        def abrir_form_operacao_inv(e, editing_op=None, prefill_ticker=None, prefill_tipo=None, prefill_op=None):
            while len(overlay_stack.controls) > 1:
                overlay_stack.controls.pop()

            SUGGESTIONS_DATABASE = {
                "Ação": ["PETR4", "VALE3", "WEGE3", "ITUB4", "BBDC4", "ABEV3", "MGLU3", "BBAS3", "RENT3", "SUZB3"],
                "FII": ["MXRF11", "HGLG11", "KNIP11", "KNRI11", "XPML11", "XPLG11", "VISC11", "BTLG11", "HGRU11"],
                "ETF": ["BOVA11", "IVVB11", "SMAL11", "HASH11"],
                "Tesouro": ["Tesouro Selic 2026", "Tesouro Selic 2029", "Tesouro IPCA+ 2029", "Tesouro Prefixado 2026"],
                "CDB": ["CDB Banco do Brasil", "CDB Itaú", "CDB Nubank", "CDB Inter"],
            }

            txt_ticker_inv = ft.TextField(
                label=_t("Ticker / Nome do Ativo"), hint_text=_t("Ex: PETR4, MXRF11"),
                value=prefill_ticker or (editing_op[1] if editing_op else ""),
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                capitalization=ft.TextCapitalization.CHARACTERS
            )
            
            drop_tipo_inv = ft.Dropdown(
                label=_t("Tipo de Ativo"), value=prefill_tipo or (editing_op[2] if editing_op else "Ação"),
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                options=[ft.dropdown.Option(key=t, text=_t(t)) for t in tipo_ordem]
            )

            drop_operacao_inv = ft.Dropdown(
                label=_t("Operação"), value=prefill_op or (editing_op[3] if editing_op else "Compra"),
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                options=[ft.dropdown.Option(key="Compra", text=_t("Compra")), ft.dropdown.Option(key="Venda", text=_t("Venda"))]
            )

            txt_qtd_inv = ft.TextField(
                label=_t("Quantidade"), hint_text=_t("Ex: 100"), value=str(editing_op[4]) if editing_op else "",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                keyboard_type=ft.KeyboardType.NUMBER
            )

            txt_preco_inv = ft.TextField(
                label=_t("Preço Unitário (R$)"), hint_text=_t("Ex: 36.50"), value=str(editing_op[5]) if editing_op else "",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                keyboard_type=ft.KeyboardType.NUMBER
            )

            txt_data_inv = ft.TextField(
                label=_t("Data (DD/MM/AAAA)"), value=editing_op[6] if editing_op else datetime.datetime.now().strftime("%d/%m/%Y"),
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"]
            )

            txt_corretora_inv = ft.TextField(
                label=_t("Corretora (Opcional)"), hint_text=_t("Ex: XP"), value=editing_op[7] or "" if editing_op else "",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"]
            )

            txt_obs_inv = ft.TextField(
                label=_t("Observação (Opcional)"), value=editing_op[8] or "" if editing_op else "",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"]
            )

            is_editing_cdb = (editing_op[2] == "CDB" if editing_op else False)
            editing_venc = editing_op[9] if (editing_op and len(editing_op) > 9 and editing_op[9]) else ""
            is_liquidez_diaria = (editing_venc == "Liquidez Diária")

            txt_vencimento_inv = ft.TextField(
                label=_t("Vencimento (Desabilitado)") if is_liquidez_diaria else _t("Vencimento (DD/MM/AAAA)"),
                hint_text=_t("Ex: 31/12/2028"), value="" if is_liquidez_diaria else editing_venc,
                disabled=is_liquidez_diaria, border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"]
            )
            
            chk_liquidez_diaria_inv = ft.Checkbox(label=_t("Liquidez Diária"), value=is_liquidez_diaria, visible=is_editing_cdb)

            def lidar_liquidez_diaria(e=None):
                if chk_liquidez_diaria_inv.value:
                    txt_vencimento_inv.value = ""
                    txt_vencimento_inv.disabled = True
                    txt_vencimento_inv.label = _t("Vencimento (Desabilitado)")
                else:
                    txt_vencimento_inv.disabled = False
                    txt_vencimento_inv.label = _t("Vencimento (DD/MM/AAAA)")
                page.update()
                
            chk_liquidez_diaria_inv.on_change = lidar_liquidez_diaria

            txt_cdi_inv = ft.TextField(
                label=_t("Percentual do CDI (%)"), hint_text="Ex: 110",
                value=str(editing_op[10]) if (editing_op and len(editing_op) > 10 and editing_op[10] is not None) else "",
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                keyboard_type=ft.KeyboardType.NUMBER
            )
            
            row_cdb_especifico = ft.Column([
                ft.Row([txt_vencimento_inv, txt_cdi_inv], spacing=10),
                ft.Row([chk_liquidez_diaria_inv], spacing=10)
            ], spacing=5, visible=is_editing_cdb)

            drop_subtipo_inv = ft.Dropdown(
                label=_t("Categoria do Tesouro"), value=editing_op[11] if (editing_op and len(editing_op) > 11) else None,
                border_color="#374151", focused_border_color="#3b82f6",
                text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                options=[
                    ft.dropdown.Option(key="Tesouro Selic (Pós-fixado)", text="Tesouro Selic (Pós-fixado)"),
                    ft.dropdown.Option(key="Tesouro Prefixado (Pré-fixado)", text="Tesouro Prefixado (Pré-fixado)"),
                    ft.dropdown.Option(key="Tesouro IPCA+ (Híbrido)", text="Tesouro IPCA+ (Híbrido)")
                ]
            )
            row_tesouro_especifico = ft.Row([drop_subtipo_inv], spacing=10, visible=(editing_op[2] == "Tesouro" if editing_op else False))

            chk_consolidada_inv = ft.Checkbox(label=_t("Posição Inicial Consolidada"), value=False, visible=(prefill_op != "Venda" and (editing_op[3] != "Venda" if editing_op else True)))
            lbl_limite_venda = ft.Text("", size=11, color="#f59e0b", visible=False)

            list_suggestions = ft.ListView(expand=True, spacing=2)
            cnt_suggestions = ft.Container(
                bgcolor=get_colors()["surface"], border_radius=8,
                padding=5, height=120, visible=False,
                border=ft.Border(top=ft.BorderSide(1, "#374151"), bottom=ft.BorderSide(1, "#374151"), left=ft.BorderSide(1, "#374151"), right=ft.BorderSide(1, "#374151")),
                content=list_suggestions
            )

            def selecionar_sugestao(val):
                txt_ticker_inv.value = val
                cnt_suggestions.visible = False
                
                cat_encontrada = None
                for cat, sugs in SUGGESTIONS_DATABASE.items():
                    if val in sugs:
                        cat_encontrada = cat
                        break
                if cat_encontrada:
                    drop_tipo_inv.value = cat_encontrada
                    atualizar_campos_especificos()
                
                if drop_tipo_inv.value == "Tesouro":
                    if "Selic" in val: drop_subtipo_inv.value = "Tesouro Selic (Pós-fixado)"
                    elif "IPCA+" in val: drop_subtipo_inv.value = "Tesouro IPCA+ (Híbrido)"
                    elif "Prefixado" in val: drop_subtipo_inv.value = "Tesouro Prefixado (Pré-fixado)"
                
                atualizar_limites_venda()
                page.update()

            def filtrar_sugestoes(e=None):
                txt = (txt_ticker_inv.value or "").strip().upper()
                list_suggestions.controls.clear()
                
                filtered = []
                if not txt:
                    tipo = drop_tipo_inv.value or "Ação"
                    filtered = [(s, tipo) for s in SUGGESTIONS_DATABASE.get(tipo, [])[:10]]
                else:
                    for tipo_cat, sugs in SUGGESTIONS_DATABASE.items():
                        for s in sugs:
                            if txt in s.upper(): filtered.append((s, tipo_cat))
                
                if filtered:
                    for s, cat in filtered[:10]:
                        list_suggestions.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Text(s, size=12, color=get_colors()["text"], weight=ft.FontWeight.W_500),
                                    ft.Container(
                                        content=ft.Text(cat, size=9, color=get_colors()["subtext"]),
                                        padding=ft.Padding(4, 1, 4, 1),
                                        border=ft.border.all(1, "#334155"), border_radius=3
                                    )
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                padding=ft.Padding(10, 6, 10, 6), border_radius=4, ink=True,
                                on_click=lambda e, val=s: selecionar_sugestao(val)
                            )
                        )
                    cnt_suggestions.visible = True
                else:
                    cnt_suggestions.visible = False
                page.update()

            def atualizar_limites_venda(e=None):
                op = drop_operacao_inv.value
                ticker = (txt_ticker_inv.value or "").strip().upper()
                
                if op == "Compra": chk_consolidada_inv.visible = True
                else:
                    chk_consolidada_inv.value = False
                    chk_consolidada_inv.visible = False
                    txt_preco_inv.label = "Preço Unitário (R$)"
                
                if op == "Venda" and ticker:
                    pos = posicoes_ativas.get(ticker)
                    if pos:
                        lbl_limite_venda.value = f"Disponível para venda: {pos['qtd']:,.4f} un (PM: {fmt(pos['custo_total']/pos['qtd'])})"
                        lbl_limite_venda.color = "#10b981"
                        lbl_limite_venda.visible = True
                    else:
                        lbl_limite_venda.value = f"Aviso: Você não possui o ativo {ticker} na carteira!"
                        lbl_limite_venda.color = "#ef4444"
                        lbl_limite_venda.visible = True
                else:
                    lbl_limite_venda.visible = False
                page.update()

            def atualizar_campos_especificos(e=None):
                t = drop_tipo_inv.value
                row_cdb_especifico.visible = (t == "CDB")
                chk_liquidez_diaria_inv.visible = (t == "CDB")
                row_tesouro_especifico.visible = (t == "Tesouro")
                
                if t != "CDB":
                    txt_vencimento_inv.value = ""
                    txt_cdi_inv.value = ""
                    chk_liquidez_diaria_inv.value = False
                    txt_vencimento_inv.disabled = False
                    txt_vencimento_inv.label = _t("Vencimento (DD/MM/AAAA)")
                else:
                    lidar_liquidez_diaria()
                if t != "Tesouro": drop_subtipo_inv.value = None
                
                filtrar_sugestoes()
                atualizar_limites_venda()
                page.update()

            def atualizar_labels_consolidada(e=None):
                if chk_consolidada_inv.value:
                    txt_preco_inv.label = "Preço Médio Existente (R$)"
                    if not txt_obs_inv.value: txt_obs_inv.value = "Posição inicial consolidada"
                else:
                    txt_preco_inv.label = "Preço Unitário (R$)"
                    if txt_obs_inv.value == "Posição inicial consolidada": txt_obs_inv.value = ""
                page.update()

            txt_ticker_inv.on_change = filtrar_sugestoes
            drop_tipo_inv.on_change = atualizar_campos_especificos
            drop_operacao_inv.on_change = atualizar_limites_venda
            chk_consolidada_inv.on_change = atualizar_labels_consolidada

            def salvar_operacao_inv(e):
                try:
                    ticker_val = (txt_ticker_inv.value or "").strip().upper()
                    tipo_val = drop_tipo_inv.value or "Ação"
                    op_val = drop_operacao_inv.value or "Compra"
                    data_val = (txt_data_inv.value or "").strip()
                    erros = []
                    
                    if not ticker_val: erros.append("Ticker obrigatório")
                    
                    try:
                        qtd_val = float((txt_qtd_inv.value or "").replace(",", "."))
                        if qtd_val <= 0: erros.append("Quantidade deve ser > 0")
                    except:
                        erros.append("Quantidade inválida")
                        qtd_val = 0.0
                        
                    try:
                        preco_val = float((txt_preco_inv.value or "").replace(",", "."))
                        if preco_val <= 0: erros.append("Preço deve ser > 0")
                    except:
                        erros.append("Preço inválido")
                        preco_val = 0.0

                    if op_val == "Venda" and ticker_val:
                        pos = posicoes_ativas.get(ticker_val)
                        if not pos: erros.append(f"Você não possui o ativo {ticker_val} na carteira.")
                        elif qtd_val > pos["qtd"] + 0.0001: erros.append(f"Quantidade máxima permitida: {pos['qtd']:,.4f} un.")

                    venc_val = "Liquidez Diária" if (tipo_val == "CDB" and chk_liquidez_diaria_inv.value) else (txt_vencimento_inv.value.strip() if (tipo_val == "CDB" and txt_vencimento_inv.value) else None)
                    cdi_val = None
                    if tipo_val == "CDB" and txt_cdi_inv.value:
                        try:
                            cdi_val = float(txt_cdi_inv.value.replace(",", "."))
                            if cdi_val <= 0: erros.append("Percentual do CDI deve ser > 0")
                        except:
                            erros.append("Percentual do CDI inválido")
                    
                    subtipo_val = drop_subtipo_inv.value if tipo_val == "Tesouro" else None
                    if tipo_val == "Tesouro" and not subtipo_val: erros.append("Selecione a Categoria do Tesouro")

                    if erros:
                        page.snack_bar = ft.SnackBar(content=ft.Text("  •  ".join(erros), color="white"), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
                    
                    if editing_op: db.delete_operacao_carteira(editing_op[0])
                    
                    obs_val = (txt_obs_inv.value or "").strip()
                    if chk_consolidada_inv.value and op_val == "Compra":
                        if not obs_val or obs_val == "Posição inicial consolidada": obs_val = "Saldo Inicial Consolidado"

                    db.add_operacao_carteira(
                        ticker=ticker_val, tipo_ativo=tipo_val, operacao=op_val,
                        quantidade=qtd_val, preco_unitario=preco_val, data=data_val,
                        corretora=(txt_corretora_inv.value or "").strip() or None,
                        observacao=obs_val or None, data_vencimento=venc_val,
                        percentual_cdi=cdi_val, subtipo_investimento=subtipo_val
                    )
                    fechar_overlay()
                    state["cotacoes_status"] = "idle"
                    render_investimentos()
                except Exception as ex:
                    sys.stderr.write(f"\nError: {ex}\n")
                    sys.stderr.flush()

            if prefill_op: atualizar_limites_venda()

            title_str = _t("✏️ Editar Operação") if editing_op else _t("📈 Nova Operação")
            col_ticker_container = ft.Column(spacing=2, expand=True, controls=[txt_ticker_inv, cnt_suggestions])

            modal_card = ft.Container(
                width=540, height=600, bgcolor=get_colors()["surface"], border_radius=16,
                border=ft.border.Border(top=ft.border.BorderSide(1.5, "#1f2937"), bottom=ft.border.BorderSide(1.5, "#1f2937"), left=ft.border.BorderSide(3, "#3b82f6"), right=ft.border.BorderSide(1.5, "#1f2937")),
                padding=ft.Padding(25, 20, 25, 20),
                content=ft.Column(expand=True, spacing=10, controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Text(title_str, size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.IconButton(ft.icons.Icons.CLOSE_ROUNDED, icon_color="#94a3b8", icon_size=22, on_click=fechar_overlay)
                    ]),
                    ft.Divider(color="#1f2937", height=12),
                    ft.Container(expand=True, content=ft.Column(
                        spacing=12, scroll=ft.ScrollMode.ADAPTIVE, expand=True,
                        controls=[
                            ft.Row([col_ticker_container, drop_tipo_inv], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
                            ft.Row([drop_operacao_inv, txt_qtd_inv], spacing=10),
                            ft.Row([txt_preco_inv, txt_data_inv], spacing=10),
                            row_cdb_especifico,
                            row_tesouro_especifico,
                            ft.Row([chk_consolidada_inv], spacing=10),
                            lbl_limite_venda,
                            txt_corretora_inv,
                            txt_obs_inv,
                            ft.Container(height=5),
                            ft.Row(alignment=ft.MainAxisAlignment.END, controls=[
                                ft.ElevatedButton("SALVAR OPERAÇÃO", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), bgcolor="#3b82f6", color="white", on_click=salvar_operacao_inv)
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
        def on_change_simular_ir(e):
            state["simular_ir"] = e.control.value
            db.set_preferencia("simular_ir", "True" if e.control.value else "False")
            render_investimentos()

        switch_ir = ft.Switch(value=state.get("simular_ir", False), on_change=on_change_simular_ir)
        switch_ir_row = ft.Row([switch_ir, ft.Text(_t("Simular IR nas vendas"), size=11, color=get_colors()["subtext"])], spacing=2)

        header_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text(_t("Investimentos"), size=24, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.Row(spacing=8, controls=[
                    switch_ir_row,
                    ft.ElevatedButton(
                        content=ft.Row([
                            ft.Icon(ft.icons.Icons.ADD_ROUNDED, color="white", size=16),
                            ft.Text(_t("NOVA OPERAÇÃO"), size=12, color=get_colors()["text"], weight=ft.FontWeight.BOLD)
                        ], spacing=5),
                        bgcolor="#3b82f6", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=abrir_form_operacao_inv
                    ),
                    ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, icon_color="#94a3b8", on_click=prev_month),
                    ft.Container(
                        bgcolor=get_colors()["surface"], padding=ft.Padding(15, 8, 15, 8), border_radius=20,
                        border=ft.border.all(1, get_colors()["border"]),
                        content=ft.Row(spacing=10, controls=[
                            ft.Icon(ft.icons.Icons.CALENDAR_MONTH_ROUNDED, color="#94a3b8", size=18),
                            ft.Text(f"{_t(mes_atual)} {ano_atual}", size=16, weight=ft.FontWeight.W_500, color=get_colors()["subtext"])
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
            criar_card_resumo(_t("💰 Saldo Disponível"), saldo_disponivel, "#3b82f6", small=True),
            criar_card_resumo(_t("📊 Patrimônio (Custo)"), patrimonio_custo, "#a78bfa", small=True),
            ft.Container(
                expand=True, bgcolor=get_colors()["surface"], border_radius=12, padding=12,
                border=ft.border.all(1, get_colors()["border"]),
                content=ft.Column(spacing=4, controls=[
                    ft.Text(_t("💎 Valor de Mercado"), size=11, color=get_colors()["subtext"], weight=ft.FontWeight.W_500),
                    ft.Text(fmt(valor_mercado), size=18, color="#10b981", weight=ft.FontWeight.BOLD),
                    ft.Text(f"{var_sinal}{fmt(abs(variacao_total))}  ({var_sinal}{var_pct_total:.1f}%)", size=10, color=var_cor_total)
                ])
            ),
            criar_card_resumo(_t("🎯 Dividendos do Mês"), dividendos, "#fbbf24", small=True),
        ])

        # ── TAB SWITCHER STYLE INVESTIDOR10 ────────────────────────────
        def make_tab_inv(label, icon_name, tab_name):
            active = tab_active == tab_name
            return ft.Container(
                content=ft.Row([
                    ft.Icon(icon_name, color="white" if active else "#64748b", size=16),
                    ft.Text(label, size=11, color=get_colors()["text"] if active else "#64748b", weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                padding=ft.Padding(12, 10, 12, 10),
                bgcolor=get_colors()["surface"] if active else "transparent",
                border=ft.border.all(1, get_colors()["border"]),
                border_radius=8, expand=True, ink=True,
                on_click=lambda e, t=tab_name: set_tab_inv(t)
            )

        tab_switcher_inv = ft.Container(
            bgcolor=get_colors()["bg"], border_radius=12, padding=5,
            content=ft.Row(spacing=5, controls=[
                make_tab_inv(_t("PATRIMÔNIO"), ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED, "patrimonio"),
                make_tab_inv(_t("RENTABILIDADE"), ft.icons.Icons.TRENDING_UP_ROUNDED, "rentabilidade"),
                make_tab_inv(_t("PROVENTOS"), ft.icons.Icons.MONETIZATION_ON_OUTLINED, "proventos"),
                make_tab_inv(_t("METAS"), ft.icons.Icons.TRACK_CHANGES_ROUNDED, "metas"),
                make_tab_inv(_t("LANÇAMENTOS"), ft.icons.Icons.HISTORY_ROUNDED, "lancamentos_inv"),
            ])
        )

        content_view_inv = ft.Container(expand=True)

        is_light_theme = page.theme_mode == ft.ThemeMode.LIGHT

        # ── SUB-ABA: PATRIMÔNIO ────────────────────────────────────────
        if tab_active == "patrimonio":
            if not posicoes_ativas:
                content_view_inv.content = ft.Column(
                    expand=True, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED, size=60, color="#334155"),
                        ft.Text(_t("Carteira vazia"), size=16, color="#64748b", weight=ft.FontWeight.BOLD),
                        ft.Text(_t("Adicione operações em Lançamentos ou Nova Operação."), size=12, color="#475569")
                    ]
                )
            else:
                # 1. Composição por tipo
                total_port = valor_mercado if valor_mercado > 0 else patrimonio_custo
                tipos_presentes = {}
                for tk, pos_p in posicoes_ativas.items():
                    cot_p2 = cotacoes_cache.get(tk, {}).get("preco")
                    val2 = pos_p["qtd"] * cot_p2 if cot_p2 else pos_p["custo_total"]
                    tipos_presentes[pos_p["tipo"]] = tipos_presentes.get(pos_p["tipo"], 0) + val2

                tipos_labels = []
                tipos_dados = []
                tipos_cores_list = []
                list_tipos_rows = []

                for tipo in [t for t in tipo_ordem if t in tipos_presentes]:
                    cor = tipo_cores[tipo]
                    val = tipos_presentes[tipo]
                    pct = (val / total_port * 100) if total_port > 0 else 0
                    tipos_labels.append(tipo)
                    tipos_dados.append(val)
                    tipos_cores_list.append(cor)
                    
                    list_tipos_rows.append(
                        ft.Container(
                            padding=8, bgcolor=get_colors()["bg"], border_radius=6,
                            content=ft.Column(spacing=4, controls=[
                                ft.Row([
                                    ft.Row([
                                        ft.Container(width=8, height=8, bgcolor=cor, border_radius=2),
                                        ft.Text(tipo, size=12, color=get_colors()["text"], weight=ft.FontWeight.W_500)
                                    ], spacing=6),
                                    ft.Text(f"{fmt(val)} ({pct:.1f}%)", size=12, color=get_colors()["text"], weight=ft.FontWeight.BOLD)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.ProgressBar(value=pct/100, color=cor, bgcolor=get_colors()["surface"], height=4)
                            ])
                        )
                    )

                donut_tipos_b64 = gerar_grafico_donut_base64(tipos_dados, tipos_labels, tipos_cores_list, is_light=is_light_theme)

                # 2. Composição de Ações
                acoes_ativas = {k: v for k, v in posicoes_ativas.items() if v["tipo"] == "Ação"}
                acoes_labels, acoes_dados, acoes_cores = [], [], []
                list_acoes_rows = []
                if acoes_ativas:
                    tot_acoes = sum(p["qtd"] * cotacoes_cache.get(k, {}).get("preco", p["custo_total"]/p["qtd"]) if cotacoes_cache.get(k, {}).get("preco") else p["custo_total"] for k, p in acoes_ativas.items())
                    for tk, pos_a in sorted(acoes_ativas.items()):
                        val_a = pos_a["qtd"] * cotacoes_cache.get(tk, {}).get("preco", pos_a["custo_total"]/pos_a["qtd"]) if cotacoes_cache.get(tk, {}).get("preco") else pos_a["custo_total"]
                        pct_a = (val_a / tot_acoes * 100) if tot_acoes > 0 else 0
                        acoes_labels.append(tk)
                        acoes_dados.append(val_a)
                        # Gera uma cor variante
                        acoes_cores.append(tipo_cores["Ação"])
                        
                        list_acoes_rows.append(
                            ft.Row([
                                ft.Text(tk, size=11, color=get_colors()["text"], weight=ft.FontWeight.BOLD),
                                ft.Text(f"{fmt(val_a)} ({pct_a:.1f}%)", size=11, color=get_colors()["subtext"])
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        )
                    donut_acoes_b64 = gerar_grafico_donut_base64(acoes_dados, acoes_labels, acoes_cores, is_light=is_light_theme)
                else:
                    donut_acoes_b64 = None

                # 3. Composição de FIIs
                fiis_ativos = {k: v for k, v in posicoes_ativas.items() if v["tipo"] == "FII"}
                fiis_labels, fiis_dados, fiis_cores = [], [], []
                list_fiis_rows = []
                if fiis_ativos:
                    tot_fiis = sum(p["qtd"] * cotacoes_cache.get(k, {}).get("preco", p["custo_total"]/p["qtd"]) if cotacoes_cache.get(k, {}).get("preco") else p["custo_total"] for k, p in fiis_ativos.items())
                    for tk, pos_f in sorted(fiis_ativos.items()):
                        val_f = pos_f["qtd"] * cotacoes_cache.get(tk, {}).get("preco", pos_f["custo_total"]/pos_f["qtd"]) if cotacoes_cache.get(tk, {}).get("preco") else pos_f["custo_total"]
                        pct_f = (val_f / tot_fiis * 100) if tot_fiis > 0 else 0
                        fiis_labels.append(tk)
                        fiis_dados.append(val_f)
                        fiis_cores.append(tipo_cores["FII"])
                        
                        list_fiis_rows.append(
                            ft.Row([
                                ft.Text(tk, size=11, color=get_colors()["text"], weight=ft.FontWeight.BOLD),
                                ft.Text(f"{fmt(val_f)} ({pct_f:.1f}%)", size=11, color=get_colors()["subtext"])
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        )
                    donut_fiis_b64 = gerar_grafico_donut_base64(fiis_dados, fiis_labels, fiis_cores, is_light=is_light_theme)
                else:
                    donut_fiis_b64 = None

                # 4. Evolução do Patrimônio
                evo_patrimonio_b64 = gerar_grafico_evolucao_patrimonio_base64(meses_hist, aplicados_hist, mercado_hist, is_light=is_light_theme)

                # Layout de Patrimônio
                layout_patrimonio = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.ADAPTIVE, controls=[
                    # Bloco de Evolução
                    ft.Container(
                        padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                        content=ft.Column([
                            ft.Text(_t("Evolução do Patrimônio"), size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.Row([
                                ft.Container(ft.Image(src="data:image/png;base64,"+evo_patrimonio_b64, width=550, height=220), expand=True, alignment=ft.Alignment(0, 0)),
                                ft.Column([
                                    ft.Text(_t("Legenda"), size=11, weight=ft.FontWeight.BOLD, color=get_colors()["subtext"]),
                                    ft.Row([ft.Container(width=10, height=10, bgcolor="#10b981", border_radius=2), ft.Text("Valor Aplicado (Custo)", size=12, color=get_colors()["text"])]),
                                    ft.Row([ft.Container(width=10, height=10, bgcolor="#a7f3d0", border_radius=2), ft.Text("Ganho de Capital", size=12, color=get_colors()["text"])]),
                                ], spacing=8, width=200)
                            ])
                        ])
                    ),
                    # Bloco de Pizza
                    ft.Row([
                        # Tipo de ativos
                        ft.Container(
                            expand=True, padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                            content=ft.Column([
                                ft.Text(_t("Alocação por Tipo de Ativo"), size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                                ft.Row([
                                    ft.Image(src="data:image/png;base64,"+donut_tipos_b64, width=220, height=220),
                                    ft.Column(list_tipos_rows, spacing=5, expand=True)
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                            ])
                        ),
                    ], spacing=20),
                    ft.Row([
                        # Ações
                        *( [
                            ft.Container(
                                expand=True, padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                                content=ft.Column([
                                    ft.Text(_t("Distribuição de Ações"), size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                                    ft.Row([
                                        ft.Image(src="data:image/png;base64,"+donut_acoes_b64, width=180, height=180),
                                        ft.Container(content=ft.Column(list_acoes_rows, spacing=4, scroll=ft.ScrollMode.ADAPTIVE), expand=True, height=180)
                                    ])
                                ])
                            )
                        ] if acoes_ativas else [] ),
                        # FIIs
                        *( [
                            ft.Container(
                                expand=True, padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                                content=ft.Column([
                                    ft.Text(_t("Distribuição de FIIs"), size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                                    ft.Row([
                                        ft.Image(src="data:image/png;base64,"+donut_fiis_b64, width=180, height=180),
                                        ft.Container(content=ft.Column(list_fiis_rows, spacing=4, scroll=ft.ScrollMode.ADAPTIVE), expand=True, height=180)
                                    ])
                                ])
                            )
                        ] if fiis_ativos else [] )
                    ], spacing=20)
                ])
                content_view_inv.content = layout_patrimonio

        # ── SUB-ABA: RENTABILIDADE ──────────────────────────────────────
        elif tab_active == "rentabilidade":
            # 1. Cards
            ret_carteira_hist, ret_cdi_hist = obter_historico_rentabilidade(meses_hist, aplicados_hist, mercado_hist, db)
            
            # Rentabilidade de fechamento atual
            rent_total = ret_carteira_hist[-1] if ret_carteira_hist else 0.0
            rent_12m = ret_carteira_hist[-1] - ret_carteira_hist[0] if len(ret_carteira_hist) >= 12 else rent_total
            rent_1m = ret_carteira_hist[-1] - ret_carteira_hist[-2] if len(ret_carteira_hist) >= 2 else rent_total
            
            rent_total_cor = "#10b981" if rent_total >= 0 else "#ef4444"
            rent_12m_cor = "#10b981" if rent_12m >= 0 else "#ef4444"
            rent_1m_cor = "#10b981" if rent_1m >= 0 else "#ef4444"
            
            cards_rent = ft.Row([
                ft.Container(
                    expand=True, bgcolor=get_colors()["surface"], border_radius=12, padding=15, border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Column([
                        ft.Text("Rentabilidade Total", size=12, color=get_colors()["subtext"]),
                        ft.Text(f"{'+' if rent_total >= 0 else ''}{rent_total:.2f}%", size=20, color=rent_total_cor, weight=ft.FontWeight.BOLD)
                    ], spacing=4)
                ),
                ft.Container(
                    expand=True, bgcolor=get_colors()["surface"], border_radius=12, padding=15, border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Column([
                        ft.Text("Últimos 12 meses", size=12, color=get_colors()["subtext"]),
                        ft.Text(f"{'+' if rent_12m >= 0 else ''}{rent_12m:.2f}%", size=20, color=rent_12m_cor, weight=ft.FontWeight.BOLD)
                    ], spacing=4)
                ),
                ft.Container(
                    expand=True, bgcolor=get_colors()["surface"], border_radius=12, padding=15, border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Column([
                        ft.Text("Último mês", size=12, color=get_colors()["subtext"]),
                        ft.Text(f"{'+' if rent_1m >= 0 else ''}{rent_1m:.2f}%", size=20, color=rent_1m_cor, weight=ft.FontWeight.BOLD)
                    ], spacing=4)
                ),
            ], spacing=15)

            # 2. Gráfico comparativo de linha
            cdi_latest = 10.50
            try: cdi_latest = float(db.get_preferencia("cdi_latest_rate", "10.50"))
            except: pass
            
            line_chart_b64 = gerar_grafico_linhas_rentabilidade_base64(meses_hist, ret_carteira_hist, ret_cdi_hist, None, is_light=is_light_theme)

            # 3. Matriz de Rentabilidade
            matriz_ret, totais_ret = obter_matriz_rentabilidade(carteira_ops, cotacoes_cache)
            
            meses_nomes_curtos = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            cols_ret = [ft.DataColumn(ft.Text("Ano", weight=ft.FontWeight.BOLD))] + [ft.DataColumn(ft.Text(m)) for m in meses_nomes_curtos] + [ft.DataColumn(ft.Text("Total", weight=ft.FontWeight.BOLD))]
            rows_ret = []
            
            for ano in sorted(matriz_ret.keys(), reverse=True):
                valores_ano = matriz_ret[ano]
                cells = [ft.DataCell(ft.Text(str(ano), weight=ft.FontWeight.BOLD))]
                for val in valores_ano:
                    cell_cor = "#10b981" if val > 0 else ("#ef4444" if val < 0 else get_colors()["subtext"])
                    cells.append(ft.DataCell(ft.Text(f"{val:.2f}%" if val != 0.0 else "-", color=cell_cor)))
                
                tot_val = totais_ret.get(ano, 0.0)
                tot_cor = "#10b981" if tot_val > 0 else ("#ef4444" if tot_val < 0 else get_colors()["subtext"])
                cells.append(ft.DataCell(ft.Text(f"{tot_val:.2f}%", weight=ft.FontWeight.BOLD, color=tot_cor)))
                rows_ret.append(ft.DataRow(cells=cells))

            tabela_matriz_rentabilidade = ft.DataTable(
                columns=cols_ret, rows=rows_ret,
                border_radius=8,
                heading_row_color=get_colors()["surface"],
                border=ft.border.all(0.5, get_colors()["border"])
            )

            layout_rentabilidade = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.ADAPTIVE, controls=[
                cards_rent,
                ft.Container(
                    padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Column([
                        ft.Row([
                            ft.Text("Rentabilidade comparada com CDI", size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.Text(f"CDI Atual SGS: {cdi_latest:.2f}% a.a.", size=11, color="#f59e0b")
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(ft.Image(src="data:image/png;base64,"+line_chart_b64, width=700, height=220), expand=True, alignment=ft.Alignment(0, 0))
                    ])
                ),
                ft.Container(
                    padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Column([
                        ft.Text("Histórico de Rentabilidade Mensal", size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Row([tabela_matriz_rentabilidade], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
                    ], spacing=10)
                )
            ])
            content_view_inv.content = layout_rentabilidade

        # ── SUB-ABA: PROVENTOS ─────────────────────────────────────────
        elif tab_active == "proventos":
            # 1. Recuperar receitas de proventos nos últimos 12 meses
            import collections
            all_trans = db.get_transacoes(mes=None, ano=None, perfil_nome=state["perfil"])
            
            proventos_por_ativo = collections.defaultdict(float)
            proventos_por_mes_recebidos = collections.defaultdict(float)
            proventos_por_mes_a_receber = collections.defaultdict(float)
            
            mes_ano_lista_ultimos_12 = []
            hoje = datetime.date.today()
            for i in range(11, -1, -1):
                ano_diff = (hoje.month - 1 - i) // 12
                m_idx = (hoje.month - 1 - i) % 12 + 1
                a = hoje.year + ano_diff
                mes_ano_lista_ultimos_12.append((m_idx, a))
            
            for t in all_trans:
                cat_name = t[4]
                desc = t[2]
                val = t[3]
                data_str = t[1]
                status = t[12]
                
                if cat_name in ('Rendimentos de Ações', 'Rendimentos de FIIs'):
                    # Tenta extrair o ticker da descrição (ex: "Rendimento PETR4")
                    parts = desc.split()
                    ticker = parts[-1].upper() if parts else "OUTROS"
                    proventos_por_ativo[ticker] += val
                    
                    try:
                        dt = datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
                        m_y = (dt.month, dt.year)
                        if m_y in mes_ano_lista_ultimos_12:
                            ref_str = f"{dt.month:02d}/{str(dt.year)[2:]}"
                            if status == "Provisionado":
                                proventos_por_mes_a_receber[ref_str] += val
                            else:
                                proventos_por_mes_recebidos[ref_str] += val
                    except:
                        pass

            # Gráfico Pizza Distribuição Proventos
            prov_labels, prov_dados, prov_cores = [], [], []
            for tk, val in sorted(proventos_por_ativo.items(), key=lambda x: x[1], reverse=True):
                prov_labels.append(tk)
                prov_dados.append(val)
                prov_cores.append("#3b82f6" if tk in acoes_ativas else "#10b981")
            
            donut_prov_b64 = gerar_grafico_donut_base64(prov_dados[:10], prov_labels[:10], prov_cores[:10], is_light=is_light_theme)

            # Gráfico de barras Proventos Recebidos vs A receber
            bar_recebidos, bar_a_receber = [], []
            bar_labels = []
            for m, y in mes_ano_lista_ultimos_12:
                ref = f"{m:02d}/{str(y)[2:]}"
                bar_labels.append(ref)
                bar_recebidos.append(proventos_por_mes_recebidos[ref])
                bar_a_receber.append(proventos_por_mes_a_receber[ref])
                
            bar_proventos_b64 = gerar_grafico_barras_proventos_base64(bar_labels, bar_recebidos, bar_a_receber, is_light=is_light_theme)

            # Matriz Histórica de Proventos
            proventos_matrix = collections.defaultdict(lambda: [0.0]*12)
            for t in all_trans:
                cat_name = t[4]
                val = t[3]
                data_str = t[1]
                if cat_name in ('Rendimentos de Ações', 'Rendimentos de FIIs'):
                    try:
                        dt = datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
                        proventos_matrix[dt.year][dt.month - 1] += val
                    except:
                        pass
            
            cols_prov = [ft.DataColumn(ft.Text("Ano", weight=ft.FontWeight.BOLD))] + [ft.DataColumn(ft.Text(m)) for m in meses_nomes_curtos] + [ft.DataColumn(ft.Text("Total", weight=ft.FontWeight.BOLD))]
            rows_prov = []
            for ano in sorted(proventos_matrix.keys(), reverse=True):
                vals = proventos_matrix[ano]
                cells = [ft.DataCell(ft.Text(str(ano), weight=ft.FontWeight.BOLD))]
                for v in vals:
                    cells.append(ft.DataCell(ft.Text(fmt(v) if v > 0 else "-")))
                tot = sum(vals)
                cells.append(ft.DataCell(ft.Text(fmt(tot), weight=ft.FontWeight.BOLD, color="#10b981")))
                rows_prov.append(ft.DataRow(cells=cells))

            table_matrix_proventos = ft.DataTable(
                columns=cols_prov, rows=rows_prov,
                border_radius=8, heading_row_color=get_colors()["surface"], border=ft.border.all(0.5, get_colors()["border"])
            )

            # Tabela de proventos detalhados
            tabela_meus_proventos_rows = []
            for t in all_trans:
                cat_name = t[4]
                desc = t[2]
                val = t[3]
                data_str = t[1]
                status = t[12] or "Pago"
                
                if cat_name in ('Rendimentos de Ações', 'Rendimentos de FIIs'):
                    parts = desc.split()
                    ticker = parts[-1].upper() if parts else "OUTROS"
                    status_cor = "#10b981" if status == "Pago" else "#f59e0b"
                    
                    tabela_meus_proventos_rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(ticker, weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text("FII" if cat_name == "Rendimentos de FIIs" else "Ações")),
                            ft.DataCell(ft.Text(status.upper(), color=status_cor, weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text("Dividendo" if cat_name == "Rendimentos de Ações" else "Rendimento")),
                            ft.DataCell(ft.Text(data_str)),
                            ft.DataCell(ft.Text(fmt(val))),
                            ft.DataCell(ft.IconButton(
                                icon=ft.icons.Icons.DELETE_OUTLINE_ROUNDED, icon_color="#ef4444", icon_size=15,
                                on_click=lambda e, tid=t[0]: [db.deletar_transacao(tid), render_investimentos()]
                            ))
                        ])
                    )

            table_meus_proventos = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Ativo")),
                    ft.DataColumn(ft.Text("Tipo")),
                    ft.DataColumn(ft.Text("Status")),
                    ft.DataColumn(ft.Text("Tipo Rendimento")),
                    ft.DataColumn(ft.Text("Data Pagamento")),
                    ft.DataColumn(ft.Text("Valor")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=tabela_meus_proventos_rows,
                border_radius=8, heading_row_color=get_colors()["surface"], border=ft.border.all(0.5, get_colors()["border"])
            )

            layout_proventos = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.ADAPTIVE, controls=[
                ft.Row([
                    ft.Container(
                        expand=True, padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                        content=ft.Column([
                            ft.Text("Distribuição de Proventos (Top 10)", size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.Row([
                                ft.Image(src="data:image/png;base64,"+donut_prov_b64, width=200, height=200),
                                ft.Column([
                                    ft.Text(f"{tk}: {fmt(val)}", size=11, color=get_colors()["text"])
                                    for tk, val in sorted(proventos_por_ativo.items(), key=lambda x: x[1], reverse=True)[:5]
                                ], spacing=4, expand=True)
                            ])
                        ])
                    ),
                    ft.Container(
                        expand=True, padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                        content=ft.Column([
                            ft.Text("Evolução Mensal de Proventos", size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.Container(ft.Image(src="data:image/png;base64,"+bar_proventos_b64, width=450, height=200), expand=True, alignment=ft.Alignment(0, 0))
                        ])
                    )
                ], spacing=20),
                # Histórico Mensal Matrix
                ft.Container(
                    padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Column([
                        ft.Text("Histórico Anual de Proventos", size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Row([table_matrix_proventos], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
                    ], spacing=10)
                ),
                # Listagem Meus Proventos
                ft.Container(
                    padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Column([
                        ft.Row([
                            ft.Text("Meus Proventos Lançados", size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.ElevatedButton("LANÇAR PROVENTO", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)), bgcolor="#fbbf24", color="#111827", on_click=abrir_form_rendimento)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([table_meus_proventos], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
                    ], spacing=10)
                )
            ])
            content_view_inv.content = layout_proventos

        # ── SUB-ABA: METAS ─────────────────────────────────────────────
        elif tab_active == "metas":
            metas_list = db.get_metas(state["perfil"])
            
            # Modal de Criação de Meta
            def abrir_form_nova_meta(e):
                while len(overlay_stack.controls) > 1:
                    overlay_stack.controls.pop()
                
                txt_desc_meta = ft.TextField(
                    label=_t("Nome / Descrição da Meta"), hint_text="Ex: Total de Patrimônio 15k",
                    border_color="#374151", focused_border_color="#10b981",
                    text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                    height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"]
                )
                
                drop_tipo_meta = ft.Dropdown(
                    label=_t("Tipo da Meta"), value="Patrimônio Total",
                    border_color="#374151", focused_border_color="#10b981",
                    text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                    height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                    options=[
                        ft.dropdown.Option(key="Patrimônio Total", text="Patrimônio Total"),
                        ft.dropdown.Option(key="Categoria", text="Categoria"),
                        ft.dropdown.Option(key="Ativo", text="Ativo")
                    ]
                )
                
                txt_target_detail = ft.TextField(
                    label=_t("Ativo / Categoria Alvo (Opcional)"), hint_text="Ex: WEGE3 ou Ação",
                    border_color="#374151", focused_border_color="#10b981",
                    text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                    height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                    visible=False
                )
                
                def on_tipo_meta_change(e):
                    if drop_tipo_meta.value == "Patrimônio Total":
                        txt_target_detail.visible = False
                    else:
                        txt_target_detail.visible = True
                        if drop_tipo_meta.value == "Categoria":
                            txt_target_detail.label = _t("Categoria Alvo")
                            txt_target_detail.hint_text = "Ex: Ação, FII, CDB"
                        else:
                            txt_target_detail.label = _t("Ticker do Ativo")
                            txt_target_detail.hint_text = "Ex: ITSA4, PETR4"
                    page.update()
                
                drop_tipo_meta.on_change = on_tipo_meta_change
                
                txt_objetivo_meta = ft.TextField(
                    label=_t("Valor Objetivo (R$)"), hint_text="Ex: 15000",
                    border_color="#374151", focused_border_color="#10b981",
                    text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                    height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                    keyboard_type=ft.KeyboardType.NUMBER
                )
                
                txt_aporte_meta = ft.TextField(
                    label=_t("Aporte Mensal (R$)"), hint_text="Ex: 250",
                    border_color="#374151", focused_border_color="#10b981",
                    text_style=ft.TextStyle(color=get_colors()["text"], size=14), label_style=ft.TextStyle(size=12),
                    height=48, expand=True, content_padding=ft.Padding(10, 5, 10, 5), bgcolor=get_colors()["bg"],
                    keyboard_type=ft.KeyboardType.NUMBER
                )
                
                def salvar_nova_meta(e):
                    desc = txt_desc_meta.value.strip()
                    tipo = drop_tipo_meta.value
                    tgt = txt_target_detail.value.strip().upper() if txt_target_detail.visible else None
                    
                    try:
                        obj = float(txt_objetivo_meta.value.replace(",", "."))
                        ap = float(txt_aporte_meta.value.replace(",", "."))
                    except:
                        page.snack_bar = ft.SnackBar(content=ft.Text("Valores objetivo e aporte devem ser numéricos"), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
                        
                    if not desc:
                        page.snack_bar = ft.SnackBar(content=ft.Text("Descrição da meta é obrigatória"), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
                        
                    t_ticker = tgt if tipo == "Ativo" else None
                    t_cat = tgt if tipo == "Categoria" else None
                    
                    db.add_meta(desc, tipo, obj, ap, target_ticker=t_ticker, target_categoria=t_cat, perfil_nome=state["perfil"])
                    fechar_overlay()
                    render_investimentos()
                
                modal_card = ft.Container(
                    width=450, height=450, bgcolor=get_colors()["surface"], border_radius=16,
                    border=ft.border.all(1, get_colors()["border"]),
                    padding=ft.Padding(25, 20, 25, 20),
                    content=ft.Column(expand=True, spacing=10, controls=[
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                            ft.Text("🎯 Criar Nova Meta Financeira", size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.IconButton(ft.icons.Icons.CLOSE_ROUNDED, icon_color="#94a3b8", on_click=fechar_overlay)
                        ]),
                        ft.Divider(color="#1f2937", height=12),
                        txt_desc_meta,
                        ft.Row([drop_tipo_meta, txt_target_detail], spacing=10),
                        ft.Row([txt_objetivo_meta, txt_aporte_meta], spacing=10),
                        ft.Container(height=10),
                        ft.Row(alignment=ft.MainAxisAlignment.END, controls=[
                            ft.ElevatedButton("SALVAR META", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)), bgcolor="#10b981", color="white", on_click=salvar_nova_meta)
                        ])
                    ])
                )
                shield = ft.Container(expand=True, bgcolor="#cc090d16", on_click=fechar_overlay)
                overlay_stack.controls.append(shield)
                overlay_stack.controls.append(modal_card)
                page.update()

            cards_meta = []
            
            for m_item in metas_list:
                m_id, m_desc, m_tipo, m_obj, m_ap, m_ticker, m_cat, m_created = m_item
                
                # Calcular valor atual para a meta específica
                val_atual_meta = 0.0
                if m_tipo == "Patrimônio Total":
                    val_atual_meta = valor_mercado
                elif m_tipo == "Categoria" and m_cat:
                    val_atual_meta = sum(pos_p["qtd"] * cotacoes_cache.get(tk, {}).get("preco", pos_p["custo_total"]/pos_p["qtd"]) if cotacoes_cache.get(tk, {}).get("preco") else pos_p["custo_total"]
                                         for tk, pos_p in posicoes_ativas.items() if pos_p["tipo"].upper() == m_cat.upper())
                elif m_tipo == "Ativo" and m_ticker:
                    pos_t = posicoes_ativas.get(m_ticker)
                    if pos_t:
                        val_atual_meta = pos_t["qtd"] * cotacoes_cache.get(m_ticker, {}).get("preco", pos_t["custo_total"]/pos_t["qtd"]) if cotacoes_cache.get(m_ticker, {}).get("preco") else pos_t["custo_total"]
                
                prog_pct = (val_atual_meta / m_obj * 100) if m_obj > 0 else 0.0
                faltam = max(0.0, m_obj - val_atual_meta)
                
                # Conclusão estimada
                if m_ap > 0:
                    meses_restantes = int(faltam // m_ap) + (1 if faltam % m_ap > 0 else 0)
                    hoje = datetime.date.today()
                    # Adicionar meses
                    mes_comp = (hoje.month - 1 + meses_restantes) % 12 + 1
                    ano_comp = hoje.year + (hoje.month - 1 + meses_restantes) // 12
                    concl_est = f"{meses_pt[mes_comp - 1]} / {ano_comp}"
                else:
                    concl_est = "Indefinido"
                
                cards_meta.append(
                    ft.Container(
                        bgcolor=get_colors()["surface"], border_radius=12, padding=20, border=ft.border.all(1, get_colors()["border"]),
                        content=ft.Column([
                            ft.Row([
                                ft.Row([
                                    ft.Icon(ft.icons.Icons.FLAG_ROUNDED, color="#3b82f6", size=18),
                                    ft.Text(m_desc, size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                                ], spacing=6),
                                ft.Row([
                                    ft.Text(f"{prog_pct:.1f}%", size=13, weight=ft.FontWeight.BOLD, color="#10b981"),
                                    ft.IconButton(
                                        icon=ft.icons.Icons.DELETE_OUTLINE_ROUNDED, icon_color="#ef4444", icon_size=16,
                                        on_click=lambda e, mid=m_id: [db.delete_meta(mid), render_investimentos()]
                                    )
                                ], spacing=4)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.ProgressBar(value=min(1.0, prog_pct/100), color="#3b82f6", bgcolor=get_colors()["bg"], height=8),
                            ft.Divider(color=get_colors()["border"], height=8),
                            ft.Row([
                                ft.Column([
                                    ft.Text("Atual", size=10, color=get_colors()["subtext"]),
                                    ft.Text(fmt(val_atual_meta), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                ], spacing=2, expand=True),
                                ft.Column([
                                    ft.Text("Aporte Mensal", size=10, color=get_colors()["subtext"]),
                                    ft.Text(fmt(m_ap), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                ], spacing=2, expand=True),
                                ft.Column([
                                    ft.Text("Faltam", size=10, color=get_colors()["subtext"]),
                                    ft.Text(fmt(faltam), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                ], spacing=2, expand=True),
                                ft.Column([
                                    ft.Text("Conclusão Estimada", size=10, color=get_colors()["subtext"]),
                                    ft.Text(concl_est, size=12, weight=ft.FontWeight.BOLD, color="#10b981")
                                ], spacing=2, expand=True),
                                ft.Column([
                                    ft.Text("Objetivo", size=10, color=get_colors()["subtext"]),
                                    ft.Text(fmt(m_obj), size=12, weight=ft.FontWeight.BOLD, color="#3b82f6")
                                ], spacing=2, expand=True)
                            ])
                        ], spacing=10)
                    )
                )

            layout_metas = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.ADAPTIVE, controls=[
                ft.Row([
                    ft.Text("Metas Financeiras em Andamento", size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                    ft.ElevatedButton("CRIAR NOVA META", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)), bgcolor="#10b981", color="white", on_click=abrir_form_nova_meta)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Column(cards_meta if cards_meta else [
                    ft.Container(
                        padding=30, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                        content=ft.Column([
                            ft.Icon(ft.icons.Icons.FLAG_ROUNDED, size=50, color="#64748b"),
                            ft.Text("Nenhuma meta ativa cadastrada.", size=13, color="#64748b", weight=ft.FontWeight.BOLD),
                            ft.Text("Clique em 'Criar nova meta' acima para definir seu primeiro objetivo.", size=11, color="#64748b")
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                    )
                ], spacing=15)
            ])
            content_view_inv.content = layout_metas

        # ── SUB-ABA: LANÇAMENTOS ───────────────────────────────────────
        else:
            # 1. Gráfico de barras consolidação de aportes (compras vs vendas)
            aportes_compra = collections.defaultdict(float)
            aportes_venda = collections.defaultdict(float)
            
            for op in carteira_ops:
                op_type = op[3]
                qtd = op[4]
                preco = op[5]
                data_str = op[6]
                try:
                    dt = datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
                    m_y = (dt.month, dt.year)
                    if m_y in mes_ano_lista_ultimos_12:
                        ref = f"{dt.month:02d}/{str(dt.year)[2:]}"
                        if op_type == "Compra": aportes_compra[ref] += qtd * preco
                        elif op_type == "Venda": aportes_venda[ref] += qtd * preco
                except:
                    pass
            
            bar_compras, bar_vendas = [], []
            for ref in bar_labels:
                bar_compras.append(aportes_compra[ref])
                bar_vendas.append(aportes_venda[ref])
                
            aportes_chart_b64 = gerar_grafico_aportes_base64(bar_labels, bar_compras, bar_vendas, is_light=is_light_theme)

            # 2. Tabela detalhada de transações
            tabela_operacoes_rows = []
            for op in carteira_ops:
                op_id, ticker, tipo, operacao, qtd, preco, data_op, corretora, obs = op[:9]
                op_cor = "#10b981" if operacao == "Compra" else "#ef4444"
                
                tabela_operacoes_rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(ticker, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(tipo)),
                        ft.DataCell(ft.Text(operacao.upper(), color=op_cor, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"{qtd:,.4f}")),
                        ft.DataCell(ft.Text(fmt(preco))),
                        ft.DataCell(ft.Text(fmt(qtd * preco))),
                        ft.DataCell(ft.Text(data_op)),
                        ft.DataCell(ft.Text(corretora or "—")),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.Icons.EDIT_ROUNDED, icon_color="#3b82f6", icon_size=15,
                                    on_click=lambda e, op_data=op: abrir_form_operacao_inv(None, editing_op=op_data)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.Icons.DELETE_OUTLINE_ROUNDED, icon_color="#ef4444", icon_size=15,
                                    on_click=lambda e, oid=op_id: confirm_delete_op(oid)
                                )
                            ], spacing=2)
                        )
                    ])
                )

            table_operacoes = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Ativo")),
                    ft.DataColumn(ft.Text("Tipo")),
                    ft.DataColumn(ft.Text("Operação")),
                    ft.DataColumn(ft.Text("Quantidade")),
                    ft.DataColumn(ft.Text("Preço Unitário")),
                    ft.DataColumn(ft.Text("Total")),
                    ft.DataColumn(ft.Text("Data")),
                    ft.DataColumn(ft.Text("Corretora")),
                    ft.DataColumn(ft.Text("Ações")),
                ],
                rows=tabela_operacoes_rows,
                border_radius=8, heading_row_color=get_colors()["surface"], border=ft.border.all(0.5, get_colors()["border"])
            )

            layout_lancamentos = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.ADAPTIVE, controls=[
                ft.Container(
                    padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Column([
                        ft.Text("Consolidação de Aportes", size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Container(ft.Image(src="data:image/png;base64,"+aportes_chart_b64, width=700, height=220), expand=True, alignment=ft.Alignment(0, 0))
                    ])
                ),
                ft.Container(
                    padding=15, bgcolor=get_colors()["surface"], border_radius=12, border=ft.border.all(1, get_colors()["border"]),
                    content=ft.Column([
                        ft.Row([
                            ft.Text("Histórico de Transações de Ativos", size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.ElevatedButton(
                                content=ft.Row([
                                    ft.Icon(ft.icons.Icons.ADD_ROUNDED, size=14, color="white"),
                                    ft.Text("REGISTRAR TRANSAÇÃO", size=11, color="white", weight=ft.FontWeight.BOLD)
                                ], spacing=5),
                                bgcolor="#3b82f6", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                                on_click=abrir_form_operacao_inv
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([table_operacoes], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
                    ], spacing=10)
                )
            ])
            content_view_inv.content = layout_lancamentos

        # ── MONTAGEM FINAL ────────────────────────────────────────────
        investimentos_layout = ft.Column(expand=True, controls=[
            header_row,
            ft.Container(height=2),
            top_cards,
            ft.Container(height=4),
            tab_switcher_inv,
            ft.Container(height=4),
            content_view_inv
        ])

        page.floating_action_button = None
        body.content = investimentos_layout
        page.update()

        if state.get("cotacoes_status") == "idle" and posicoes_ativas:
            state["cotacoes_status"] = "fetching"
            threading.Thread(target=buscar_cotacoes, daemon=True).start()
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
        lock_tooltip = _t("Habilitar Edição (Destravar)") if locked else _t("Concluir Edição (Bloquear)")

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
                content=ft.Text(_t("Visualização ativa. Clique no cadeado dourado no topo para destravar a edição! 🔓🔒"), color=get_colors()["text"]),
                bgcolor="#fb923c"
            )
            page.snack_bar.open = True
            page.update()

        btn_mensal = ft.Container(
            content=ft.Text(_t("MENSAL"), size=11, color=get_colors()["text"] if view_mode == "mensal" else "#94a3b8", weight=ft.FontWeight.BOLD),
            padding=ft.Padding(16, 8, 16, 8),
            bgcolor="#2563eb" if view_mode == "mensal" else "transparent",
            border_radius=8,
            on_click=lambda e: set_transacoes_view_mode("mensal")
        )
        btn_anual = ft.Container(
            content=ft.Text(_t("ANUAL"), size=11, color=get_colors()["text"] if view_mode == "anual" else "#94a3b8", weight=ft.FontWeight.BOLD),
            padding=ft.Padding(16, 8, 16, 8),
            bgcolor="#2563eb" if view_mode == "anual" else "transparent",
            border_radius=8,
            on_click=lambda e: set_transacoes_view_mode("anual")
        )
        segmented_control = ft.Container(
            bgcolor=get_colors()["bg"],
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
                    bgcolor=get_colors()["surface"],
                    border=ft.border.all(1, get_colors()["border"]),
                    padding=ft.Padding(15, 8, 15, 8),
                    border_radius=20,
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            ft.Icon(date_icon, color="#94a3b8", size=18),
                            ft.Text(date_label, size=16, weight=ft.FontWeight.W_500, color=get_colors()["subtext"])
                        ]
                    )
                ),
                ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", on_click=next_month),
            ]
        )

        def on_change_perfil_trans(e):
            state["perfil"] = e.control.value
            render_transacoes()

        seletor_perfil = criar_seletor_perfil(on_change_perfil_trans)

        # Sub-controles da aba Histórico
        tab_header = criar_tab_header(
            "transacoes",
            seletor_perfil,
            subcontroles=[btn_lock, segmented_control, date_navigator]
        )

        # Garantir que a aba ativa está sincronizada se vier do estado antigo
        if tab_active not in ("pilar_categoria", "receitas_aportes"):
            tab_active = "pilar_categoria"
            state["transacoes_tab_active"] = "pilar_categoria"

        tab_despesas = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.MONEY_OFF_ROUNDED, color="white" if tab_active == "pilar_categoria" else "#64748b", size=18),
                ft.Text(_t("DESPESAS (FIXAS E VARIÁVEIS)"), size=12, color=get_colors()["text"] if tab_active == "pilar_categoria" else "#64748b", weight=ft.FontWeight.BOLD),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            padding=ft.Padding(20, 12, 20, 12),
            bgcolor=get_colors()["surface"] if tab_active == "pilar_categoria" else "transparent",
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=10,
            expand=True,
            ink=True,
            on_click=lambda e: set_transacoes_tab("pilar_categoria")
        )

        tab_receitas = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.TRENDING_UP_ROUNDED, color="white" if tab_active == "receitas_aportes" else "#64748b", size=18),
                ft.Text(_t("RECEITAS & APORTES"), size=12, color=get_colors()["text"] if tab_active == "receitas_aportes" else "#64748b", weight=ft.FontWeight.BOLD),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            padding=ft.Padding(20, 12, 20, 12),
            bgcolor=get_colors()["surface"] if tab_active == "receitas_aportes" else "transparent",
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=10,
            expand=True,
            ink=True,
            on_click=lambda e: set_transacoes_tab("receitas_aportes")
        )

        tab_switcher = ft.Container(
            bgcolor=get_colors()["bg"],
            border_radius=12,
            padding=5,
            content=ft.Row(
                spacing=5,
                controls=[tab_despesas, tab_receitas]
            )
        )

        content_view = ft.Container(
            expand=True,
            bgcolor=get_colors()["surface"],
            border=ft.border.all(1, get_colors()["border"]),
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
                    ft.Text(_t("Nenhuma transação encontrada"), size=16, color="#64748b", weight=ft.FontWeight.BOLD),
                    ft.Text(_t("Os lançamentos deste período aparecerão aqui."), size=12, color="#475569")
                ]
            )
        else:
            if tab_active == "pilar_categoria":
                despesas_variaveis_items = []
                despesas_fixas_items = []
                
                # Filtrar apenas despesas
                despesas_only = [t for t in transacoes if "Despesa" in t[5]]
                
                pilar_groups = {}
                for t in despesas_only:
                    pilar = t[5].strip()
                    cat = t[4].strip().title()
                    
                    if pilar not in pilar_groups:
                        pilar_groups[pilar] = {}
                    if cat not in pilar_groups[pilar]:
                        pilar_groups[pilar][cat] = []
                    pilar_groups[pilar][cat].append(t)

                for pilar_nome, categories_dict in pilar_groups.items():
                    pilar_total = sum(t[3] for cats in categories_dict.values() for t in cats)
                    
                    if "Despesa Fixa" in pilar_nome:
                        pilar_color = "#f43f5e" # rose-500
                        indicator_color = "#f43f5e"
                        target_list = despesas_fixas_items
                    else:
                        pilar_color = "#ef4444"
                        indicator_color = "#ef4444"
                        target_list = despesas_variaveis_items

                    target_list.append(
                        ft.Container(
                            margin=ft.Margin(0, 10, 0, 5),
                            padding=ft.Padding(12, 8, 12, 8),
                            bgcolor=get_colors()["bg"],
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
                                        ft.Text(cat_nome, size=11, weight=ft.FontWeight.W_600, color=get_colors()["subtext"]),
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
                            
                            if t_divisoes and t_divisoes > 1:
                                subtitle_parts.append("Dividido 👥")

                            vinculo_parts = []
                            if len(t) > 15:
                                v_mod = t[14]
                                v_pla = t[15]
                                p_nome = t[16]
                                s_nome = t[17]
                                if v_mod or v_pla:
                                    v_str = "🚗 "
                                    if v_mod: v_str += v_mod
                                    if v_pla: v_str += f" ({v_pla})"
                                    vinculo_parts.append(v_str)
                                if p_nome:
                                    vinculo_parts.append(f"🐾 {p_nome}")
                                if s_nome:
                                    vinculo_parts.append(f"🏥 {s_nome}")
                            
                            if vinculo_parts:
                                subtitle_parts.append(" • ".join(vinculo_parts))
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
                                row_bg = get_colors()["card_bg"]
                                row_border = None
                                row_padding = ft.Padding(15, 8, 15, 8)
                                row_radius = 8
                                value_controls = [
                                    ft.Text(f"R$ {t_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=13, weight=ft.FontWeight.BOLD, color=pilar_color),
                                    ft.Icon(ft.icons.Icons.EDIT_ROUNDED, color="#64748b", size=13)
                                ]

                            despesas_variaveis_items.append(
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
                                                        bgcolor=get_colors()["surface"],
                                                        border_radius=6,
                                                        content=ft.Icon(get_icone_categoria(t[4]), color=indicator_color, size=16)
                                                    ),
                                                    ft.Container(width=5),
                                                    ft.Column(
                                                        expand=True,
                                                        spacing=1,
                                                        controls=[
                                                            ft.Text(t_desc, size=13, weight=ft.FontWeight.W_500, color=get_colors()["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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
                        # Coluna Esquerda: Despesas Variáveis
                        ft.Container(
                            expand=True,
                            bgcolor=get_colors()["surface"],
                            border=ft.border.all(1, get_colors()["border"]),
                            border_radius=12,
                            padding=ft.Padding(left=15, right=15, top=10, bottom=12),
                            content=ft.Column(
                                expand=True,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.icons.Icons.ARROW_DOWNWARD_ROUNDED, color="#ef4444", size=16),
                                        ft.Text(_t("DESPESAS VARIÁVEIS"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=despesas_variaveis_items if despesas_variaveis_items else [ft.Text(_t("Nenhuma despesa variável neste período."), color="#64748b", size=12)]
                                    )
                                ]
                            )
                        ),
                        # Coluna Direita: Despesas Fixas
                        ft.Container(
                            expand=True,
                            bgcolor=get_colors()["surface"],
                            border=ft.border.all(1, get_colors()["border"]),
                            border_radius=12,
                            padding=ft.Padding(left=15, right=15, top=10, bottom=12),
                            content=ft.Column(
                                expand=True,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.icons.Icons.PUSH_PIN_ROUNDED, color="#f43f5e", size=16),
                                        ft.Text(_t("DESPESAS FIXAS"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=despesas_fixas_items if despesas_fixas_items else [ft.Text(_t("Nenhuma despesa fixa neste período."), color="#64748b", size=12)]
                                    )
                                ]
                            )
                        )
                    ]
                )
            else:
                receitas_items = []
                investimentos_items = []
                
                # Filtrar apenas receitas e investimentos
                entradas_only = [t for t in transacoes if "Receita" in t[5] or "Investimento" in t[5]]
                
                pilar_groups = {}
                for t in entradas_only:
                    pilar = t[5].strip()
                    cat = t[4].strip().title()
                    
                    if pilar not in pilar_groups:
                        pilar_groups[pilar] = {}
                    if cat not in pilar_groups[pilar]:
                        pilar_groups[pilar][cat] = []
                    pilar_groups[pilar][cat].append(t)

                for pilar_nome, categories_dict in pilar_groups.items():
                    pilar_total = sum(t[3] for cats in categories_dict.values() for t in cats)
                    
                    if "Investimento" in pilar_nome:
                        pilar_color = "#3b82f6"
                        indicator_color = "#3b82f6"
                        target_list = investimentos_items
                    else:
                        pilar_color = "#10b981"
                        indicator_color = "#10b981"
                        target_list = receitas_items

                    target_list.append(
                        ft.Container(
                            margin=ft.Margin(0, 10, 0, 5),
                            padding=ft.Padding(12, 8, 12, 8),
                            bgcolor=get_colors()["bg"],
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
                                        ft.Text(cat_nome, size=11, weight=ft.FontWeight.W_600, color=get_colors()["subtext"]),
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
                            
                            if t_divisoes and t_divisoes > 1:
                                subtitle_parts.append("Dividido 👥")

                            vinculo_parts = []
                            if len(t) > 15:
                                v_mod = t[14]
                                v_pla = t[15]
                                p_nome = t[16]
                                s_nome = t[17]
                                if v_mod or v_pla:
                                    v_str = "🚗 "
                                    if v_mod: v_str += v_mod
                                    if v_pla: v_str += f" ({v_pla})"
                                    vinculo_parts.append(v_str)
                                if p_nome:
                                    vinculo_parts.append(f"🐾 {p_nome}")
                                if s_nome:
                                    vinculo_parts.append(f"🏥 {s_nome}")
                            
                            if vinculo_parts:
                                subtitle_parts.append(" • ".join(vinculo_parts))
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
                                row_bg = get_colors()["card_bg"]
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
                                                        bgcolor=get_colors()["surface"],
                                                        border_radius=6,
                                                        content=ft.Icon(get_icone_categoria(t[4]), color=indicator_color, size=16)
                                                    ),
                                                    ft.Container(width=5),
                                                    ft.Column(
                                                        expand=True,
                                                        spacing=1,
                                                        controls=[
                                                            ft.Text(t_desc, size=13, weight=ft.FontWeight.W_500, color=get_colors()["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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
                        # Coluna Esquerda: Receitas (Fixas e Variáveis)
                        ft.Container(
                            expand=True,
                            bgcolor=get_colors()["surface"],
                            border=ft.border.all(1, get_colors()["border"]),
                            border_radius=12,
                            padding=ft.Padding(left=15, right=15, top=10, bottom=12),
                            content=ft.Column(
                                expand=True,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.icons.Icons.ARROW_UPWARD_ROUNDED, color="#10b981", size=16),
                                        ft.Text(_t("RECEITAS (FIXAS E VARIÁVEIS)"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=receitas_items if receitas_items else [ft.Text(_t("Nenhuma receita ou aporte neste período."), color="#64748b", size=12)]
                                    )
                                ]
                            )
                        ),
                        # Coluna Direita: Investimentos (Aportes)
                        ft.Container(
                            expand=True,
                            bgcolor=get_colors()["surface"],
                            border=ft.border.all(1, get_colors()["border"]),
                            border_radius=12,
                            padding=ft.Padding(left=15, right=15, top=10, bottom=12),
                            content=ft.Column(
                                expand=True,
                                controls=[
                                    ft.Row([
                                        ft.Icon(ft.icons.Icons.SAVINGS_ROUNDED, color="#3b82f6", size=16),
                                        ft.Text(_t("INVESTIMENTOS & APORTES"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=investimentos_items if investimentos_items else [ft.Text(_t("Nenhum investimento neste período."), color="#64748b", size=12)]
                                    )
                                ]
                            )
                        )
                    ]
                )

        trans_layout = ft.Column(
            expand=True,
            controls=[
                tab_header,
                ft.Container(height=10),
                tab_switcher,
                ft.Container(height=10),
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

    def render_financiamentos():
        colors = get_colors()
        page.floating_action_button = ft.FloatingActionButton(
            icon=ft.icons.Icons.ADD,
            bgcolor="#3b82f6",
            tooltip=_t("Lançar Financiamento"),
            on_click=lambda e: abrir_modal_novo_financiamento(e)
        )
        
        # Obter dados
        financiamentos = db.get_financiamentos(state["perfil"])
        abatimentos = db.get_abatimentos_pagos(state["perfil"])
        
        # Resumos
        saldo_devedor_total = sum(f["saldo_devedor"] for f in financiamentos if not f["quitado"])
        juros_pagos_total = sum(f["total_juros"] for f in financiamentos)
        qtd_ativos = sum(1 for f in financiamentos if not f["quitado"])
        
        def confirmar_exclusao_financiamento(financiamento_id):
            # Garante que limpa overlays anteriores antes de abrir um novo
            while len(overlay_stack.controls) > 1:
                overlay_stack.controls.pop()

            def do_delete(fid):
                fechar_overlay()
                success, msg = db.delete_financiamento(fid)
                if success:
                    render_financiamentos()
                    page.snack_bar = ft.SnackBar(content=ft.Text(_t("Financiamento excluído com sucesso!")), bgcolor="#10b981")
                    page.snack_bar.open = True
                    page.update()
                else:
                    page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro ao excluir')}: {msg}"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()

            shield = ft.Container(
                expand=True,
                bgcolor="#cc090d16",  # Premium blurred matte dark backdrop
                on_click=fechar_overlay
            )

            modal_card = ft.Container(
                width=450,
                height=220,
                bgcolor=colors["surface"],
                border_radius=16,
                border=ft.border.all(1.5, "#1f2937"),
                padding=ft.Padding(left=25, top=20, right=25, bottom=20),
                content=ft.Column(
                    expand=True,
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(
                                    _t("Confirmar Exclusão"),
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                    color=colors["text"]
                                ),
                                ft.IconButton(
                                    icon=ft.icons.Icons.CLOSE_ROUNDED,
                                    icon_color="#94a3b8",
                                    icon_size=22,
                                    on_click=fechar_overlay,
                                    tooltip=_t("Fechar")
                                )
                            ]
                        ),
                        ft.Divider(color="#1f2937", height=10),
                        ft.Text(
                            _t("Excluir este contrato de financiamento e todos os seus lançamentos (receitas/despesas) vinculados?"),
                            color=colors["subtext"],
                            size=13
                        ),
                        ft.Divider(color="#1f2937", height=10),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            spacing=10,
                            controls=[
                                ft.TextButton(
                                    _t("CANCELAR"), 
                                    on_click=fechar_overlay
                                ),
                                ft.ElevatedButton(
                                    _t("EXCLUIR"), 
                                    bgcolor="#ef4444", 
                                    color="white", 
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                    on_click=lambda e: do_delete(financiamento_id)
                                )
                            ]
                        )
                    ]
                )
            )

            overlay_stack.controls.append(shield)
            overlay_stack.controls.append(modal_card)
            page.update()
            
        def abrir_modal_novo_financiamento(e=None):
            try:
                # Garante que limpa overlays anteriores antes de abrir um novo
                while len(overlay_stack.controls) > 1:
                    overlay_stack.controls.pop()

                # TextFields e Dropdowns formatados e organizados
                txt_credor = ft.TextField(
                    label=_t("Credor"), 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                txt_data_inicio = ft.TextField(
                    label=_t("Data de Início (DD/MM/AAAA)"), 
                    value=datetime.date.today().strftime("%d/%m/%Y"), 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                txt_valor_total = ft.TextField(
                    label=_t("Valor Total"), 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                dropdown_sistema = ft.Dropdown(
                    label=_t("Sistema de Amortização"), 
                    value="SAC", 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True,
                    options=[
                        ft.dropdown.Option("SAC"), 
                        ft.dropdown.Option("Price"), 
                        ft.dropdown.Option("Sem Juros"), 
                        ft.dropdown.Option("Flexível")
                    ]
                )
                txt_total_parcelas = ft.TextField(
                    label=_t("Total de Parcelas"), 
                    value="12", 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                txt_taxa_juros = ft.TextField(
                    label=_t("Taxa de Juros (%)"), 
                    value="0", 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                dropdown_tipo_juros = ft.Dropdown(
                    label=_t("Tipo de Taxa"), 
                    value="Mensal", 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True,
                    options=[
                        ft.dropdown.Option("Mensal"), 
                        ft.dropdown.Option("Anual")
                    ]
                )
                dropdown_conta = ft.Dropdown(
                    label=_t("Conta para Débito"), 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                txt_observacao = ft.TextField(
                    label=_t("Observação (Opcional)"), 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                
                # Linha de detalhes da amortização (SAC/Price/Sem Juros)
                row_detalhes_amort = ft.Row(
                    controls=[txt_total_parcelas, txt_taxa_juros, dropdown_tipo_juros],
                    spacing=10,
                    visible=True
                )
                
                def on_sistema_change(e):
                    is_flex = (dropdown_sistema.value == "Flexível")
                    row_detalhes_amort.visible = not is_flex
                    page.update()
                    
                dropdown_sistema.on_change = lambda e: on_sistema_change(e)
                
                contas = db.get_contas()
                dropdown_conta.options = [ft.dropdown.Option(text=c[1], key=str(c[0])) for c in contas]
                if contas:
                    dropdown_conta.value = str(contas[0][0])
                    
                def salvar_novo_financiamento(e):
                    credor = txt_credor.value
                    data_inicio = txt_data_inicio.value
                    valor_total_str = txt_valor_total.value
                    sistema = dropdown_sistema.value
                    
                    if not credor or not data_inicio or not valor_total_str:
                        page.snack_bar = ft.SnackBar(content=ft.Text(_t("Por favor, preencha todos os campos obrigatórios.")), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
                        
                    try:
                        valor_total = float(valor_total_str.replace(",", "."))
                    except ValueError:
                        page.snack_bar = ft.SnackBar(content=ft.Text(_t("Valor Total inválido.")), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
                        
                    if sistema == "Flexível":
                        total_parcelas = 1
                        taxa = 0.0
                        tipo_taxa = "Mensal"
                    else:
                        try:
                            total_parcelas = int(txt_total_parcelas.value)
                            taxa = float(txt_taxa_juros.value.replace(",", "."))
                        except ValueError:
                            page.snack_bar = ft.SnackBar(content=ft.Text(_t("Total de parcelas ou taxa de juros inválida.")), bgcolor="#ef4444")
                            page.snack_bar.open = True
                            page.update()
                            return
                        tipo_taxa = dropdown_tipo_juros.value
                        
                    conta_id = int(dropdown_conta.value) if dropdown_conta.value else 1
                    obs = txt_observacao.value
                    
                    success, msg = db.add_financiamento(
                        credor=credor,
                        data_inicio=data_inicio,
                        valor_total=valor_total,
                        total_parcelas=total_parcelas,
                        taxa_juros=taxa,
                        tipo_juros=tipo_taxa,
                        sistema_amortizacao=sistema,
                        conta_id=conta_id,
                        perfil_nome=state["perfil"],
                        observacao=obs
                    )
                    
                    if success:
                        fechar_overlay()
                        render_financiamentos()
                        page.snack_bar = ft.SnackBar(content=ft.Text(_t("Financiamento lançado com sucesso!")), bgcolor="#10b981")
                        page.snack_bar.open = True
                        page.update()
                    else:
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro ao salvar')}: {msg}"), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                
                shield = ft.Container(
                    expand=True,
                    bgcolor="#cc090d16",  # Premium blurred matte dark backdrop
                    on_click=fechar_overlay
                )

                modal_card = ft.Container(
                    width=580,
                    height=510,
                    bgcolor=colors["surface"],
                    border_radius=16,
                    border=ft.border.all(1.5, "#1f2937"),
                    padding=ft.Padding(left=25, top=20, right=25, bottom=20),
                    content=ft.Column(
                        expand=True,
                        spacing=10,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(
                                        _t("Lançar Novo Financiamento"),
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=colors["text"]
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.Icons.CLOSE_ROUNDED,
                                        icon_color="#94a3b8",
                                        icon_size=22,
                                        on_click=fechar_overlay,
                                        tooltip=_t("Fechar")
                                    )
                                ]
                            ),
                            ft.Divider(color="#1f2937", height=15),
                            ft.Column(
                                expand=True,
                                spacing=15,
                                scroll=ft.ScrollMode.ADAPTIVE,
                                controls=[
                                    ft.Row([txt_credor, txt_data_inicio], spacing=10),
                                    ft.Row([txt_valor_total, dropdown_sistema], spacing=10),
                                    row_detalhes_amort,
                                    ft.Row([dropdown_conta], spacing=10),
                                    ft.Row([txt_observacao], spacing=10)
                                ]
                            ),
                            ft.Divider(color="#1f2937", height=15),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                spacing=10,
                                controls=[
                                    ft.TextButton(
                                        _t("CANCELAR"), 
                                        on_click=fechar_overlay
                                    ),
                                    ft.ElevatedButton(
                                        _t("SALVAR"), 
                                        bgcolor="#3b82f6", 
                                        color="white", 
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                        on_click=lambda e: salvar_novo_financiamento(e)
                                    )
                                ]
                            )
                        ]
                    )
                )

                overlay_stack.controls.append(shield)
                overlay_stack.controls.append(modal_card)
                page.update()
            except Exception as ex:
                import logging
                logging.error("Erro ao abrir modal novo financiamento", exc_info=True)
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Erro ao abrir modal: {ex}"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()

        def abrir_modal_amortizar_flexivel(financiamento_id):
            # Garante que limpa overlays anteriores antes de abrir um novo
            while len(overlay_stack.controls) > 1:
                overlay_stack.controls.pop()

            txt_data_op = ft.TextField(
                label=_t("Data do Pagamento (DD/MM/AAAA)"), 
                value=datetime.date.today().strftime("%d/%m/%Y"), 
                border_color="#374151", 
                text_style=ft.TextStyle(color=colors["text"], size=14),
                focused_border_color="#3b82f6",
                bgcolor=colors["bg"],
                expand=True
            )
            txt_valor_pagar = ft.TextField(
                label=_t("Valor Pago (R$)"), 
                border_color="#374151", 
                text_style=ft.TextStyle(color=colors["text"], size=14),
                focused_border_color="#3b82f6",
                bgcolor=colors["bg"],
                expand=True
            )
            dropdown_conta_op = ft.Dropdown(
                label=_t("Conta de Origem"), 
                border_color="#374151", 
                text_style=ft.TextStyle(color=colors["text"], size=14),
                focused_border_color="#3b82f6",
                bgcolor=colors["bg"],
                expand=True
            )
            
            contas = db.get_contas()
            dropdown_conta_op.options = [ft.dropdown.Option(text=c[1], key=str(c[0])) for c in contas]
            if contas:
                dropdown_conta_op.value = str(contas[0][0])
                
            def salvar_amortizacao(e):
                data_op = txt_data_op.value
                valor_str = txt_valor_pagar.value
                
                if not data_op or not valor_str:
                    page.snack_bar = ft.SnackBar(content=ft.Text(_t("Por favor, preencha todos os campos.")), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return
                    
                try:
                    valor = float(valor_str.replace(",", "."))
                except ValueError:
                    page.snack_bar = ft.SnackBar(content=ft.Text(_t("Valor inválido.")), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return
                    
                conta_id = int(dropdown_conta_op.value) if dropdown_conta_op.value else 1
                
                success, msg = db.add_amortizacao_manual(
                    financiamento_id=financiamento_id,
                    valor=valor,
                    data_op=data_op,
                    conta_id=conta_id
                )
                
                if success:
                    fechar_overlay()
                    render_financiamentos()
                    page.snack_bar = ft.SnackBar(content=ft.Text(_t("Amortização registrada com sucesso!")), bgcolor="#10b981")
                    page.snack_bar.open = True
                    page.update()
                else:
                    page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro ao salvar')}: {msg}"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    
            shield = ft.Container(
                expand=True,
                bgcolor="#cc090d16",  # Premium blurred matte dark backdrop
                on_click=fechar_overlay
            )

            modal_card = ft.Container(
                width=420,
                height=380,
                bgcolor=colors["surface"],
                border_radius=16,
                border=ft.border.all(1.5, "#1f2937"),
                padding=ft.Padding(left=25, top=20, right=25, bottom=20),
                content=ft.Column(
                    expand=True,
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(
                                    _t("Lançar Amortização"),
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                    color=colors["text"]
                                ),
                                ft.IconButton(
                                    icon=ft.icons.Icons.CLOSE_ROUNDED,
                                    icon_color="#94a3b8",
                                    icon_size=22,
                                    on_click=fechar_overlay,
                                    tooltip=_t("Fechar")
                                )
                            ]
                        ),
                        ft.Divider(color="#1f2937", height=15),
                        ft.Column(
                            expand=True,
                            spacing=15,
                            scroll=ft.ScrollMode.ADAPTIVE,
                            controls=[
                                txt_data_op,
                                txt_valor_pagar,
                                dropdown_conta_op
                            ]
                        ),
                        ft.Divider(color="#1f2937", height=15),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            spacing=10,
                            controls=[
                                ft.TextButton(
                                    _t("CANCELAR"), 
                                    on_click=fechar_overlay
                                ),
                                ft.ElevatedButton(
                                    _t("SALVAR"), 
                                    bgcolor="#ea580c", 
                                    color="white", 
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                    on_click=lambda e: salvar_amortizacao(e)
                                )
                            ]
                        )
                    ]
                )
            )

            overlay_stack.controls.append(shield)
            overlay_stack.controls.append(modal_card)
            page.update()
            
        def abrir_modal_detalhes_financiamento(financiamento_id):
            details = db.get_financiamento_detalhes(financiamento_id)
            if not details:
                return
                
            rows = []
            for p in details["parcelas"]:
                pago_status = _t("Pago") if p["pago"] else _t("Provisionado")
                pago_color = "#10b981" if p["pago"] else "#fb923c"
                
                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(p["numero_parcela"]), color=colors["text"])),
                            ft.DataCell(ft.Text(p["data"], color=colors["text"])),
                            ft.DataCell(ft.Text(f"R$ {p['valor_prestacao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), color=colors["text"])),
                            ft.DataCell(ft.Text(f"R$ {p['valor_amortizacao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), color=colors["text"])),
                            ft.DataCell(ft.Text(f"R$ {p['valor_juros']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), color=colors["text"])),
                            ft.DataCell(ft.Text(f"R$ {p['saldo_devedor_restante']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), color=colors["text"])),
                            ft.DataCell(ft.Text(pago_status, color=pago_color, weight=ft.FontWeight.BOLD)),
                        ]
                    )
                )
                
            table = ft.DataTable(
                column_spacing=12,
                border=ft.border.all(0.5, colors["border"]),
                border_radius=8,
                columns=[
                    ft.DataColumn(ft.Text(_t("Parcela"), weight=ft.FontWeight.BOLD, color=colors["text"])),
                    ft.DataColumn(ft.Text(_t("Vencimento"), weight=ft.FontWeight.BOLD, color=colors["text"])),
                    ft.DataColumn(ft.Text(_t("Valor Parcela"), weight=ft.FontWeight.BOLD, color=colors["text"])),
                    ft.DataColumn(ft.Text(_t("Amortização"), weight=ft.FontWeight.BOLD, color=colors["text"])),
                    ft.DataColumn(ft.Text(_t("Juros"), weight=ft.FontWeight.BOLD, color=colors["text"])),
                    ft.DataColumn(ft.Text(_t("Saldo Devedor"), weight=ft.FontWeight.BOLD, color=colors["text"])),
                    ft.DataColumn(ft.Text(_t("Status"), weight=ft.FontWeight.BOLD, color=colors["text"])),
                ],
                rows=rows
            )
            
            shield = ft.Container(
                expand=True,
                bgcolor="#cc090d16",  # Premium blurred matte dark backdrop
                on_click=fechar_overlay
            )

            modal_card = ft.Container(
                width=760,
                height=530,
                bgcolor=colors["surface"],
                border_radius=16,
                border=ft.border.all(1.5, "#1f2937"),
                padding=ft.Padding(left=25, top=20, right=25, bottom=20),
                content=ft.Column(
                    expand=True,
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(
                                    f"{_t('Detalhes do Financiamento')} - {details['credor']}",
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                    color=colors["text"]
                                ),
                                ft.IconButton(
                                    icon=ft.icons.Icons.CLOSE_ROUNDED,
                                    icon_color="#94a3b8",
                                    icon_size=22,
                                    on_click=fechar_overlay,
                                    tooltip=_t("Fechar")
                                )
                            ]
                        ),
                        ft.Divider(color="#1f2937", height=15),
                        ft.Column(
                            scroll=ft.ScrollMode.ADAPTIVE,
                            expand=True,
                            controls=[
                                ft.Row(
                                    [table],
                                    scroll=ft.ScrollMode.ADAPTIVE
                                )
                            ]
                        ),
                        ft.Divider(color="#1f2937", height=15),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            controls=[
                                ft.TextButton(_t("FECHAR"), on_click=fechar_overlay)
                            ]
                        )
                    ]
                )
            )

            overlay_stack.controls.append(shield)
            overlay_stack.controls.append(modal_card)
            page.update()

        def abrir_modal_editar_financiamento(financiamento_id):
            try:
                fin_data = next((x for x in financiamentos if x["id"] == financiamento_id), None)
                if not fin_data:
                    return

                # Garante que limpa overlays anteriores antes de abrir um novo
                while len(overlay_stack.controls) > 1:
                    overlay_stack.controls.pop()

                # TextFields e Dropdowns formatados e organizados
                txt_credor = ft.TextField(
                    label=_t("Credor"), 
                    value=fin_data["credor"],
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                txt_data_inicio = ft.TextField(
                    label=_t("Data de Início (DD/MM/AAAA)"), 
                    value=fin_data["data_inicio"], 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                txt_valor_total = ft.TextField(
                    label=_t("Valor Total"), 
                    value=str(fin_data["valor_total"]),
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                dropdown_sistema = ft.Dropdown(
                    label=_t("Sistema de Amortização"), 
                    value=fin_data["sistema_amortizacao"], 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True,
                    options=[
                        ft.dropdown.Option("SAC"), 
                        ft.dropdown.Option("Price"), 
                        ft.dropdown.Option("Sem Juros"), 
                        ft.dropdown.Option("Flexível")
                    ]
                )
                txt_total_parcelas = ft.TextField(
                    label=_t("Total de Parcelas"), 
                    value=str(fin_data["total_parcelas"]), 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                txt_taxa_juros = ft.TextField(
                    label=_t("Taxa de Juros (%)"), 
                    value=str(fin_data["taxa_juros"]), 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                dropdown_tipo_juros = ft.Dropdown(
                    label=_t("Tipo de Taxa"), 
                    value=fin_data["tipo_juros"], 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True,
                    options=[
                        ft.dropdown.Option("Mensal"), 
                        ft.dropdown.Option("Anual")
                    ]
                )
                dropdown_conta = ft.Dropdown(
                    label=_t("Conta para Débito"), 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                txt_observacao = ft.TextField(
                    label=_t("Observação (Opcional)"), 
                    value=fin_data["observacao"],
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                
                # Linha de detalhes da amortização (SAC/Price/Sem Juros)
                is_flex = (fin_data["sistema_amortizacao"] == "Flexível")
                row_detalhes_amort = ft.Row(
                    controls=[txt_total_parcelas, txt_taxa_juros, dropdown_tipo_juros],
                    spacing=10,
                    visible=not is_flex
                )
                
                def on_sistema_change(e):
                    is_flex_now = (dropdown_sistema.value == "Flexível")
                    row_detalhes_amort.visible = not is_flex_now
                    page.update()
                    
                dropdown_sistema.on_change = lambda e: on_sistema_change(e)
                
                contas = db.get_contas()
                dropdown_conta.options = [ft.dropdown.Option(text=c[1], key=str(c[0])) for c in contas]
                dropdown_conta.value = str(fin_data["conta_id"])
                
                def salvar_edicao(e):
                    credor = txt_credor.value
                    data_inicio = txt_data_inicio.value
                    valor_total_str = txt_valor_total.value
                    sistema = dropdown_sistema.value
                    
                    if not credor or not data_inicio or not valor_total_str:
                        page.snack_bar = ft.SnackBar(content=ft.Text(_t("Por favor, preencha todos os campos obrigatórios.")), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
                        
                    try:
                        valor_total = float(valor_total_str.replace(",", "."))
                    except ValueError:
                        page.snack_bar = ft.SnackBar(content=ft.Text(_t("Valor Total inválido.")), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
                        
                    if sistema == "Flexível":
                        total_parcelas = 1
                        taxa = 0.0
                        tipo_taxa = "Mensal"
                    else:
                        try:
                            total_parcelas = int(txt_total_parcelas.value)
                            taxa = float(txt_taxa_juros.value.replace(",", "."))
                        except ValueError:
                            page.snack_bar = ft.SnackBar(content=ft.Text(_t("Total de parcelas ou taxa de juros inválida.")), bgcolor="#ef4444")
                            page.snack_bar.open = True
                            page.update()
                            return
                        tipo_taxa = dropdown_tipo_juros.value
                        
                    conta_id = int(dropdown_conta.value) if dropdown_conta.value else 1
                    obs = txt_observacao.value
                    
                    success, msg = db.update_financiamento(
                        fid=financiamento_id,
                        credor=credor,
                        data_inicio=data_inicio,
                        valor_total=valor_total,
                        total_parcelas=total_parcelas,
                        taxa_juros=taxa,
                        tipo_juros=tipo_taxa,
                        sistema_amortizacao=sistema,
                        conta_id=conta_id,
                        observacao=obs
                    )
                    
                    if success:
                        fechar_overlay()
                        render_financiamentos()
                        page.snack_bar = ft.SnackBar(content=ft.Text(_t("Financiamento atualizado com sucesso!")), bgcolor="#10b981")
                        page.snack_bar.open = True
                        page.update()
                    else:
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro ao salvar')}: {msg}"), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                
                shield = ft.Container(
                    expand=True,
                    bgcolor="#cc090d16",  # Premium blurred matte dark backdrop
                    on_click=fechar_overlay
                )

                modal_card = ft.Container(
                    width=580,
                    height=510,
                    bgcolor=colors["surface"],
                    border_radius=16,
                    border=ft.border.all(1.5, "#1f2937"),
                    padding=ft.Padding(left=25, top=20, right=25, bottom=20),
                    content=ft.Column(
                        expand=True,
                        spacing=10,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(
                                        _t("Editar Financiamento"),
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=colors["text"]
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.Icons.CLOSE_ROUNDED,
                                        icon_color="#94a3b8",
                                        icon_size=22,
                                        on_click=fechar_overlay,
                                        tooltip=_t("Fechar")
                                    )
                                ]
                            ),
                            ft.Divider(color="#1f2937", height=15),
                            ft.Column(
                                expand=True,
                                spacing=15,
                                scroll=ft.ScrollMode.ADAPTIVE,
                                controls=[
                                    ft.Row([txt_credor, txt_data_inicio], spacing=10),
                                    ft.Row([txt_valor_total, dropdown_sistema], spacing=10),
                                    row_detalhes_amort,
                                    ft.Row([dropdown_conta], spacing=10),
                                    ft.Row([txt_observacao], spacing=10)
                                ]
                            ),
                            ft.Divider(color="#1f2937", height=15),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                spacing=10,
                                controls=[
                                    ft.TextButton(
                                        _t("CANCELAR"), 
                                        on_click=fechar_overlay
                                    ),
                                    ft.ElevatedButton(
                                        _t("SALVAR"), 
                                        bgcolor="#3b82f6", 
                                        color="white", 
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                        on_click=lambda e: salvar_edicao(e)
                                    )
                                ]
                            )
                        ]
                    )
                )

                overlay_stack.controls.append(shield)
                overlay_stack.controls.append(modal_card)
                page.update()
            except Exception as ex:
                import logging
                logging.error("Erro ao abrir modal editar financiamento", exc_info=True)
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Erro ao abrir modal: {ex}"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()

        def abrir_modal_editar_parcela(ab):
            try:
                # Garante que limpa overlays anteriores antes de abrir um novo
                while len(overlay_stack.controls) > 1:
                    overlay_stack.controls.pop()

                txt_data_op = ft.TextField(
                    label=_t("Data do Pagamento (DD/MM/AAAA)"), 
                    value=ab["data"], 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                txt_valor_pagar = ft.TextField(
                    label=_t("Valor Pago (R$)"), 
                    value=str(ab["valor_pago"]),
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                dropdown_conta_op = ft.Dropdown(
                    label=_t("Conta de Origem"), 
                    border_color="#374151", 
                    text_style=ft.TextStyle(color=colors["text"], size=14),
                    focused_border_color="#3b82f6",
                    bgcolor=colors["bg"],
                    expand=True
                )
                
                contas = db.get_contas()
                dropdown_conta_op.options = [ft.dropdown.Option(text=c[1], key=str(c[0])) for c in contas]
                dropdown_conta_op.value = str(ab["conta_id"])
                
                def salvar_edicao_parcela(e):
                    data_op = txt_data_op.value
                    valor_str = txt_valor_pagar.value
                    
                    if not data_op or not valor_str:
                        page.snack_bar = ft.SnackBar(content=ft.Text(_t("Por favor, preencha todos os campos.")), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
                        
                    try:
                        valor = float(valor_str.replace(",", "."))
                    except ValueError:
                        page.snack_bar = ft.SnackBar(content=ft.Text(_t("Valor inválido.")), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
                        
                    conta_id = int(dropdown_conta_op.value) if dropdown_conta_op.value else 1
                    
                    success, msg = db.update_parcela_paga(
                        trans_id=ab["transacao_id"],
                        valor=valor,
                        data_op=data_op,
                        conta_id=conta_id
                    )
                    
                    if success:
                        fechar_overlay()
                        render_financiamentos()
                        page.snack_bar = ft.SnackBar(content=ft.Text(_t("Amortização atualizada com sucesso!")), bgcolor="#10b981")
                        page.snack_bar.open = True
                        page.update()
                    else:
                        page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro ao salvar')}: {msg}"), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        
                def confirmar_exclusao_parcela(e):
                    def fechar_dialog(e):
                        page.pop_dialog()
                    
                    def realizar_exclusao(e2):
                        page.pop_dialog()
                        success, msg = db.excluir_abatimento(ab["transacao_id"])
                        if success:
                            fechar_overlay()
                            render_financiamentos()
                            page.snack_bar = ft.SnackBar(content=ft.Text(_t("Abatimento excluído/revertido com sucesso!")), bgcolor="#10b981")
                            page.snack_bar.open = True
                        else:
                            page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro ao excluir')}: {msg}"), bgcolor="#ef4444")
                            page.snack_bar.open = True
                        page.update()

                    dialog = ft.AlertDialog(
                        modal=True,
                        title=ft.Text(_t("CONFIRMAR EXCLUSÃO ⚠️"), size=16, weight=ft.FontWeight.BOLD, color=colors["text"]),
                        content=ft.Text(_t("Deseja realmente excluir ou reverter este abatimento?"), size=14, color=colors["subtext"]),
                        bgcolor=colors["surface"],
                        actions=[
                            ft.TextButton(_t("CANCELAR"), on_click=fechar_dialog, style=ft.ButtonStyle(color="white")),
                            ft.ElevatedButton("EXCLUIR", on_click=realizar_exclusao, bgcolor="#ef4444", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                        ],
                        actions_alignment=ft.MainAxisAlignment.END,
                    )
                    page.show_dialog(dialog)
                        
                shield = ft.Container(
                    expand=True,
                    bgcolor="#cc090d16",  # Premium blurred matte dark backdrop
                    on_click=fechar_overlay
                )

                modal_card = ft.Container(
                    width=420,
                    height=380,
                    bgcolor=colors["surface"],
                    border_radius=16,
                    border=ft.border.all(1.5, "#1f2937"),
                    padding=ft.Padding(left=25, top=20, right=25, bottom=20),
                    content=ft.Column(
                        expand=True,
                        spacing=10,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(
                                        f"{_t('Editar Pagamento')} - {ab['credor']}",
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                        color=colors["text"]
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.Icons.CLOSE_ROUNDED,
                                        icon_color="#94a3b8",
                                        icon_size=22,
                                        on_click=fechar_overlay,
                                        tooltip=_t("Fechar")
                                    )
                                ]
                            ),
                            ft.Divider(color="#1f2937", height=15),
                            ft.Column(
                                expand=True,
                                spacing=15,
                                scroll=ft.ScrollMode.ADAPTIVE,
                                controls=[
                                    txt_data_op,
                                    txt_valor_pagar,
                                    dropdown_conta_op
                                ]
                            ),
                            ft.Divider(color="#1f2937", height=15),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.TextButton(
                                        _t("EXCLUIR"), 
                                        style=ft.ButtonStyle(color="#ef4444"),
                                        on_click=lambda e: confirmar_exclusao_parcela(e)
                                    ),
                                    ft.Row(
                                        spacing=10,
                                        controls=[
                                            ft.TextButton(
                                                _t("CANCELAR"), 
                                                on_click=fechar_overlay
                                            ),
                                            ft.ElevatedButton(
                                                _t("SALVAR"), 
                                                bgcolor="#3b82f6", 
                                                color="white", 
                                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                                on_click=lambda e: salvar_edicao_parcela(e)
                                            )
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                )

                overlay_stack.controls.append(shield)
                overlay_stack.controls.append(modal_card)
                page.update()
            except Exception as ex:
                import logging
                logging.error("Erro ao abrir modal editar parcela", exc_info=True)

        # Cabeçalho
        header = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED, size=28, color="#3b82f6"),
                        ft.Text(_t("Financiamentos"), size=24, weight=ft.FontWeight.BOLD, color=colors["text"])
                    ]
                ),
                ft.Row(
                    spacing=10,
                    controls=[
                        criar_seletor_perfil(lambda e: (state.update({"perfil": e.control.value}), render_financiamentos()))
                    ]
                )
            ]
        )
        
        # Cards de Resumo
        resumos_row = ft.Row(
            spacing=15,
            controls=[
                criar_card_resumo(_t("Saldo Devedor Total"), saldo_devedor_total, cor_valor="#f87171"),
                criar_card_resumo(_t("Total de Juros Pagos"), juros_pagos_total, cor_valor="#fb923c"),
                ft.Container(
                    expand=True,
                    bgcolor=colors["surface"],
                    border=ft.border.all(1, colors["border"]),
                    border_radius=12,
                    padding=20,
                    content=ft.Column(
                        controls=[
                            ft.Text(_t("Contratos Ativos"), size=14, color=colors["subtext"], weight=ft.FontWeight.W_500),
                            ft.Text(str(qtd_ativos), size=28, color=colors["text"], weight=ft.FontWeight.BOLD)
                        ]
                    )
                )
            ]
        )
        
        # Coluna da Esquerda: Créditos Adquiridos (Lista de Contratos)
        cards_contratos = []
        for f in financiamentos:
            # Badge para o sistema de amortização
            badge_color = "#3b82f6"
            if f["sistema_amortizacao"] == "SAC":
                badge_color = "#8b5cf6"
            elif f["sistema_amortizacao"] == "Price":
                badge_color = "#ec4899"
            elif f["sistema_amortizacao"] == "Sem Juros":
                badge_color = "#10b981"
            elif f["sistema_amortizacao"] == "Flexível":
                badge_color = "#ea580c"
                
            badge_sistema = ft.Container(
                content=ft.Text(f["sistema_amortizacao"], color="white", size=10, weight=ft.FontWeight.BOLD),
                bgcolor=badge_color,
                padding=ft.Padding(8, 3, 8, 3),
                border_radius=8
            )
            
            # Badge de Quitado ou Ativo
            if f["quitado"]:
                badge_status = ft.Container(
                    content=ft.Text(_t("QUITADO"), color="white", size=10, weight=ft.FontWeight.BOLD),
                    bgcolor="#10b981",
                    padding=ft.Padding(8, 3, 8, 3),
                    border_radius=8
                )
            else:
                badge_status = ft.Container(
                    content=ft.Text(_t("ATIVO"), color="white", size=10, weight=ft.FontWeight.BOLD),
                    bgcolor="#f59e0b",
                    padding=ft.Padding(8, 3, 8, 3),
                    border_radius=8
                )
                
            warnings = []
            if f["sistema_amortizacao"] == "Flexível" and not f["quitado"]:
                warnings.append(
                    ft.Container(
                        margin=ft.Margin(0, 10, 0, 0),
                        padding=10,
                        bgcolor="#fff7ed" if colors["surface"] == "#ffffff" else "#451a03",
                        border=ft.border.all(1, "#f97316"),
                        border_radius=8,
                        content=ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.icons.Icons.WARNING_ROUNDED, color="#f97316", size=18),
                                ft.Text(
                                    _t("Fluxo Flexível - Sem Provisionamento de Débito"),
                                    color="#c2410c" if colors["surface"] == "#ffffff" else "#fdba74",
                                    size=11,
                                    weight=ft.FontWeight.W_600
                                )
                            ]
                        )
                    )
                )
                
            # Detalhes rápidos do contrato
            amortizado_perc = (f["total_amortizado"] / f["valor_total"]) * 100 if f["valor_total"] > 0 else 0
            progresso = ft.ProgressBar(value=amortizado_perc / 100, color="#10b981", bgcolor=colors["bg"])
            
            # Botões de ação
            botoes_acao = [
                ft.TextButton(
                    _t("Ver Detalhes"),
                    icon=ft.icons.Icons.ZOOM_IN_ROUNDED,
                    icon_color="#3b82f6",
                    on_click=lambda e, fid=f["id"]: abrir_modal_detalhes_financiamento(fid)
                ),
                ft.TextButton(
                    _t("Editar"),
                    icon=ft.icons.Icons.EDIT_ROUNDED,
                    icon_color="#10b981",
                    on_click=lambda e, fid=f["id"]: abrir_modal_editar_financiamento(fid)
                )
            ]
            
            if f["sistema_amortizacao"] == "Flexível" and not f["quitado"]:
                botoes_acao.append(
                    ft.ElevatedButton(
                        _t("Amortizar"),
                        icon=ft.icons.Icons.PAYMENT_ROUNDED,
                        bgcolor="#ea580c",
                        color="white",
                        on_click=lambda e, fid=f["id"]: abrir_modal_amortizar_flexivel(fid)
                    )
                )
                
            botoes_acao.append(
                ft.IconButton(
                    icon=ft.icons.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_color="#ef4444",
                    tooltip=_t("Excluir Financiamento"),
                    on_click=lambda e, fid=f["id"]: confirmar_exclusao_financiamento(fid)
                )
            )
            
            obs_text = []
            if f["observacao"]:
                obs_text.append(ft.Text(f["observacao"], size=12, color=colors["subtext"], italic=True))
                
            card_content = ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(f["credor"], size=16, weight=ft.FontWeight.BOLD, color=colors["text"]),
                            ft.Row(spacing=5, controls=[badge_sistema, badge_status])
                        ]
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(_t("Valor Total:"), size=13, color=colors["subtext"]),
                            ft.Text(f"R$ {f['valor_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=13, color=colors["text"], weight=ft.FontWeight.W_500)
                        ]
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(_t("Saldo Devedor:"), size=13, color=colors["subtext"]),
                            ft.Text(f"R$ {f['saldo_devedor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=13, color="#ef4444", weight=ft.FontWeight.BOLD)
                        ]
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(_t("Total Pago:"), size=13, color=colors["subtext"]),
                            ft.Text(f"R$ {f['total_pago']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=13, color="#10b981", weight=ft.FontWeight.W_500)
                        ]
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(_t("Conta Padrão:"), size=13, color=colors["subtext"]),
                            ft.Text(f["nome_conta"], size=13, color=colors["text"])
                        ]
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(f"{_t('Amortizado')}: {amortizado_perc:.1f}%", size=11, color=colors["subtext"]),
                            ft.Text(
                                f"{_t('Pago')}: R$ {f['total_pago']:,.2f} | {_t('Falta')}: R$ {f['saldo_devedor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                                if f["sistema_amortizacao"] == "Flexível"
                                else f"Taxa: {f['taxa_juros']}% a.({f['tipo_juros'][0].lower()})",
                                size=11,
                                color=colors["subtext"],
                                weight=ft.FontWeight.W_500 if f["sistema_amortizacao"] == "Flexível" else ft.FontWeight.NORMAL
                            )
                        ]
                    ),
                    progresso,
                ] + obs_text + warnings + [
                    ft.Divider(color=colors["border"]),
                    ft.Row(alignment=ft.MainAxisAlignment.END, spacing=10, controls=botoes_acao)
                ]
            )
            
            cards_contratos.append(
                ft.Container(
                    bgcolor=colors["surface"],
                    border=ft.border.all(1, colors["border"]),
                    border_radius=12,
                    padding=15,
                    margin=ft.Margin(0, 0, 0, 15),
                    content=card_content
                )
            )
            
        if not cards_contratos:
            cards_contratos.append(
                ft.Container(
                    alignment=ft.Alignment(0, 0),
                    padding=40,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED, size=48, color=colors["subtext"]),
                            ft.Text(_t("Nenhum financiamento cadastrado neste perfil."), color=colors["subtext"], size=14)
                        ]
                    )
                )
            )
            
        col_creditos = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE,
            controls=[
                ft.Text(_t("Créditos Adquiridos (Contratos)"), size=18, weight=ft.FontWeight.BOLD, color=colors["text"]),
                ft.Divider(color=colors["border"]),
                ft.Column(
                    spacing=5,
                    controls=cards_contratos
                )
            ]
        )
        
        # Coluna da Direita: Abatimentos Realizados (Lista de Amortizações pagas)
        row_abatimentos = []
        for ab in abatimentos:
            row_abatimentos.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(ab["credor"], color=colors["text"], size=12)),
                        ft.DataCell(ft.Text(str(ab["numero_parcela"]), color=colors["text"], size=12)),
                        ft.DataCell(ft.Text(ab["data"], color=colors["text"], size=12)),
                        ft.DataCell(ft.Text(f"R$ {ab['valor_pago']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), color="#10b981", size=12, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"R$ {ab['valor_amortizacao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), color=colors["text"], size=12)),
                        ft.DataCell(ft.Text(f"R$ {ab['valor_juros']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), color=colors["text"], size=12)),
                        ft.DataCell(
                            ft.Container(
                                content=ft.IconButton(
                                    icon=ft.icons.Icons.EDIT_OUTLINED,
                                    icon_size=16,
                                    icon_color="#3b82f6",
                                    tooltip=_t("Editar Pagamento"),
                                    on_click=lambda e, ab_item=ab: abrir_modal_editar_parcela(ab_item)
                                ),
                                padding=ft.Padding(0, 0, 25, 0)
                            )
                        ),
                    ]
                )
            )
            
        tabela_abatimentos = ft.DataTable(
            column_spacing=28,
            horizontal_margin=10,
            columns=[
                ft.DataColumn(ft.Text(_t("Contrato"), size=12, weight=ft.FontWeight.BOLD, color=colors["text"])),
                ft.DataColumn(ft.Text(_t("Parcela"), size=12, weight=ft.FontWeight.BOLD, color=colors["text"])),
                ft.DataColumn(ft.Text(_t("Data"), size=12, weight=ft.FontWeight.BOLD, color=colors["text"])),
                ft.DataColumn(ft.Text(_t("Valor Pago"), size=12, weight=ft.FontWeight.BOLD, color=colors["text"])),
                ft.DataColumn(ft.Text(_t("Amortização"), size=12, weight=ft.FontWeight.BOLD, color=colors["text"])),
                ft.DataColumn(ft.Text(_t("Juros"), size=12, weight=ft.FontWeight.BOLD, color=colors["text"])),
                ft.DataColumn(ft.Text(_t("Ações    "), size=12, weight=ft.FontWeight.BOLD, color=colors["text"])),
            ],
            rows=row_abatimentos
        )

        col_abatimentos = ft.Column(
            expand=True,
            controls=[
                ft.Text(_t("Abatimentos Realizados (Histórico)"), size=18, weight=ft.FontWeight.BOLD, color=colors["text"]),
                ft.Divider(color=colors["border"]),
                ft.Container(
                    expand=True,
                    bgcolor=colors["surface"],
                    border=ft.border.all(1, colors["border"]),
                    border_radius=12,
                    padding=15,
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.ADAPTIVE,
                        controls=[
                            ft.Row(
                                [tabela_abatimentos],
                                scroll=ft.ScrollMode.ADAPTIVE
                            )
                        ]
                    )
                )
            ]
        )
        # Grid Principal de 2 Colunas
        grid_financiamentos = ft.Row(
            expand=True,
            spacing=25,
            controls=[
                col_creditos,
                col_abatimentos
            ]
        )
        
        # Layout Final
        layout = ft.Column(
            expand=True,
            spacing=20,
            controls=[
                header,
                resumos_row,
                ft.Container(expand=True, content=grid_financiamentos)
            ]
        )
        
        body.content = layout
        page.update()

    def render_recorrencias():
        configs = db.get_configs_recorrencia(state["perfil"])
        
        # Filtrar as recorrências que já foram totalmente realizadas (última parcela anterior ao mês atual)
        import datetime
        now = datetime.datetime.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        active_configs = []
        for c in configs:
            occurrences_for_c = db.get_transacoes_recorrencia(c[0], state["perfil"])
            if not occurrences_for_c:
                active_configs.append(c)
            else:
                latest_dt = None
                for occ in occurrences_for_c:
                    try:
                        occ_dt = datetime.datetime.strptime(occ[1], "%d/%m/%Y")
                    except:
                        occ_dt = now
                    if latest_dt is None or occ_dt > latest_dt:
                        latest_dt = occ_dt
                if latest_dt and latest_dt >= current_month_start:
                    active_configs.append(c)
        configs = active_configs
        
        def on_change_perfil_rec(e):
            state["perfil"] = e.control.value
            render_recorrencias()

        seletor_perfil_rec = criar_seletor_perfil(on_change_perfil_rec)

        btn_nova_rec = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.ADD_ROUNDED, size=16, color="white"),
                ft.Text(_t("NOVA RECORRÊNCIA"), size=11, color="white", weight=ft.FontWeight.BOLD)
            ], spacing=5),
            bgcolor="#3b82f6",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
            on_click=abrir_form_config_recorrencia
        )
        tab_header = criar_tab_header(
            "recorrencias",
            seletor_perfil_rec,
            subcontroles=[btn_nova_rec]
        )
        
        if not configs:
            empty_state = ft.Container(
                alignment=ft.Alignment(0, 0),
                expand=True,
                padding=40,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.icons.Icons.AUTORENEW_ROUNDED, size=80, color="#64748b"),
                        ft.Text(_t("Nenhuma recorrência cadastrada"), size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Text(_t("Cadastre despesas como plano de saúde, mensalidades ou receitas recorrentes para começar."), size=14, color="#64748b", text_align=ft.TextAlign.CENTER),
                        ft.Container(height=10),
                        ft.ElevatedButton(
                            _t("CADASTRAR PRIMEIRA RECORRÊNCIA"),
                            on_click=abrir_form_config_recorrencia,
                            bgcolor="#3b82f6",
                            color="white"
                        )
                    ]
                )
            )
            body.content = ft.Column(expand=True, controls=[tab_header, ft.Divider(color="#1f2937", height=20), empty_state])
            page.update()
            return

        # Resolve all categories for display names
        categorias = db.get_categorias()
        cat_id_to_name = {c[0]: c[1].strip() for c in categorias}
        cat_id_to_parent_id = {c[0]: c[3] for c in categorias}
        
        def get_cat_display(cat_id):
            name = cat_id_to_name.get(cat_id, "Sem Categoria")
            parent_id = cat_id_to_parent_id.get(cat_id)
            if parent_id and parent_id in cat_id_to_name:
                parent_name = cat_id_to_name[parent_id]
                return f"{parent_name} - {name}"
            return name

        # Group configs by category display name
        categorias_dict = {}
        for c in configs:
            cat_display = get_cat_display(c[3])
            if cat_display not in categorias_dict:
                categorias_dict[cat_display] = []
            categorias_dict[cat_display].append(c)
            
        unique_cat_groups = list(categorias_dict.keys())
        
        active_group = state.get("active_recurrence_group")
        if active_group not in unique_cat_groups:
            active_group = unique_cat_groups[0] if unique_cat_groups else None
            state["active_recurrence_group"] = active_group
            
        configs_in_group = categorias_dict.get(active_group, []) if active_group else []
        
        active_id = state.get("active_recurrence_id")
        config_ids_in_group = [c[0] for c in configs_in_group]
        if active_id not in config_ids_in_group:
            active_id = config_ids_in_group[0] if config_ids_in_group else None
            state["active_recurrence_id"] = active_id
            
        active_config = next((c for c in configs if c[0] == active_id), None)
        if not active_config and configs_in_group:
            active_config = configs_in_group[0]
            active_id = active_config[0]
            state["active_recurrence_id"] = active_id
            
        tabs_controls = []
        for cat_group in unique_cat_groups:
            is_active_group = (cat_group == active_group)
            
            def make_on_click_group(target_group):
                def click_handler(e):
                    state["active_recurrence_group"] = target_group
                    group_configs = categorias_dict[target_group]
                    state["active_recurrence_id"] = group_configs[0][0]
                    render_recorrencias()
                return click_handler
                
            tabs_controls.append(
                ft.Container(
                    content=ft.Text(cat_group, size=12, color="white" if is_active_group else get_colors()["text"], weight=ft.FontWeight.BOLD),
                    bgcolor="#3b82f6" if is_active_group else get_colors()["surface"],
                    border=ft.border.all(1, "#3b82f6" if is_active_group else get_colors()["border"]),
                    border_radius=20,
                    padding=ft.Padding(15, 8, 15, 8),
                    on_click=make_on_click_group(cat_group)
                )
            )
        
        def select_recurrence(target_id):
            state["active_recurrence_id"] = target_id
            # Sync active group when selecting a specific recurrence
            for grp, grp_configs in categorias_dict.items():
                if any(gc[0] == target_id for gc in grp_configs):
                    state["active_recurrence_group"] = grp
                    break
            render_recorrencias()
            
        tabs_row = ft.Row(
            controls=tabs_controls,
            scroll=ft.ScrollMode.ADAPTIVE,
            spacing=10
        )
        
        cid, nome, tipo_transacao, categoria_id, valor_padrao, conta_id, metodo, obs, perf, cat_nome, band_cartao, dono_cartao = active_config
        
        occurrences = db.get_transacoes_recorrencia(cid, state["perfil"])
        
        import datetime
        now = datetime.datetime.now()
        total_gasto = 0.0
        compromisso_futuro = 0.0
        
        for occ in occurrences:
            try:
                occ_dt = datetime.datetime.strptime(occ[1], "%d/%m/%Y")
            except:
                occ_dt = now
            if occ_dt < now.replace(day=1, hour=0, minute=0, second=0, microsecond=0):
                total_gasto += occ[3]
            else:
                compromisso_futuro += occ[3]
                
        card_valor_mensal = criar_card_resumo(_t("Valor Padrão"), valor_padrao, "#38bdf8", get_colors()["surface"], small=True)
        card_total_gasto = criar_card_resumo(_t("Histórico Pago/Recebido"), total_gasto, "#10b981", get_colors()["surface"], small=True)
        card_compromisso = criar_card_resumo(_t("Planejado/Futuro"), compromisso_futuro, "#fb923c", get_colors()["surface"], small=True)
        
        cards_row = ft.Row(
            controls=[card_valor_mensal, card_total_gasto, card_compromisso],
            spacing=15
        )
        
        months_dropdown = ft.Dropdown(
            label=_t("Quantidade de Meses"),
            options=[
                ft.dropdown.Option("3", "3 meses"),
                ft.dropdown.Option("6", "6 meses"),
                ft.dropdown.Option("12", "12 meses"),
                ft.dropdown.Option("24", "24 meses"),
            ],
            value="12",
            width=180,
            bgcolor=get_colors()["bg"],
            border_color=get_colors()["border"],
            color=get_colors()["text"]
        )
        
        start_date_input = ft.TextField(
            label=_t("A partir de (DD/MM/AAAA)"),
            value=now.strftime("01/%m/%Y"),
            width=200,
            bgcolor=get_colors()["bg"],
            border_color=get_colors()["border"],
            color=get_colors()["text"]
        )
        
        def do_batch_generation(e):
            n_months = int(months_dropdown.value)
            start_date = start_date_input.value.strip()
            try:
                datetime.datetime.strptime(start_date, "%d/%m/%Y")
            except:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Data inicial inválida! Use DD/MM/AAAA"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            success = db.gerar_transacoes_recorrentes(cid, n_months, start_date, state["perfil"])
            if success:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Lançamentos em lote programados com sucesso!"), color="white"), bgcolor="#10b981")
                page.snack_bar.open = True
                render_recorrencias()
            else:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao gerar lançamentos!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()

        btn_gerar = ft.ElevatedButton(
            _t("PROGRAMAR LANÇAMENTOS"),
            on_click=do_batch_generation,
            bgcolor="#3b82f6",
            color="white",
            height=45
        )
        
        batch_container = ft.Container(
            padding=20,
            bgcolor=get_colors()["surface"],
            border_radius=12,
            border=ft.border.all(1, get_colors()["border"]),
            content=ft.Column([
                ft.Text(_t("Lançamento em Lote 🚀"), size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.Text(_t("Gere lançamentos automáticos para os próximos meses de forma simples."), size=12, color="#64748b"),
                ft.Container(height=10),
                ft.Row([months_dropdown, start_date_input], spacing=10),
                ft.Container(height=10),
                btn_gerar
            ], spacing=10)
        )
        
        def fmt(val):
            if val is None:
                return "R$ 0,00"
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
        rows = []
        for occ in occurrences:
            occ_id, occ_data, occ_desc, occ_valor, occ_tipo, occ_metodo, occ_obs = occ
            
            try:
                occ_dt = datetime.datetime.strptime(occ_data, "%d/%m/%Y")
            except:
                occ_dt = now
                
            status_text = _t("Realizado") if occ_dt < now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) else _t("Agendado")
            status_color = "#10b981" if status_text == _t("Realizado") else "#fb923c"
            
            def make_edit_click(o_id, o_val, o_data):
                return lambda e: abrir_edit_ocorrencia(o_id, o_val, o_data)
                
            def make_delete_click(o_id, o_data):
                return lambda e: abrir_delete_ocorrencia(o_id, o_data)
                
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(occ_data, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(occ_desc, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(fmt(occ_valor), color=get_colors()["text"], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(
                            ft.Container(
                                content=ft.Text(status_text, size=10, color="white", weight=ft.FontWeight.BOLD),
                                bgcolor=status_color,
                                border_radius=4,
                                padding=ft.Padding(8, 4, 8, 4)
                            )
                        ),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(ft.icons.Icons.EDIT_ROUNDED, icon_color="#3b82f6", icon_size=18, tooltip=_t("Editar Valor"), on_click=make_edit_click(occ_id, occ_valor, occ_data)),
                                ft.IconButton(ft.icons.Icons.DELETE_ROUNDED, icon_color="#ef4444", icon_size=18, tooltip=_t("Excluir Ocorrência"), on_click=make_delete_click(occ_id, occ_data)),
                            ], spacing=5)
                        )
                    ]
                )
            )
            
        tabela = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(_t("Mês/Data"))),
                ft.DataColumn(ft.Text(_t("Descrição"))),
                ft.DataColumn(ft.Text(_t("Valor"))),
                ft.DataColumn(ft.Text(_t("Status"))),
                ft.DataColumn(ft.Text(_t("Ações"))),
            ],
            rows=rows,
            border_radius=8,
            border=ft.border.all(0.5, get_colors()["border"]),
            heading_row_color=get_colors()["surface"],
            expand=True
        )
        
        tabela_container = ft.Container(
            padding=20,
            bgcolor=get_colors()["surface"],
            border_radius=12,
            border=ft.border.all(1, get_colors()["border"]),
            expand=True,
            content=ft.Column([
                ft.Row([
                    ft.Text(_t("Ocorrências Programadas"), size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                    ft.Row([
                        ft.IconButton(ft.icons.Icons.EDIT_ROUNDED, icon_color="#3b82f6", tooltip=_t("Editar Configuração"), on_click=lambda e: abrir_form_config_recorrencia(e, active_config)),
                        ft.IconButton(ft.icons.Icons.DELETE_FOREVER_ROUNDED, icon_color="#ef4444", tooltip=_t("Excluir Configuração Recorrência"), on_click=lambda e: abrir_delete_config(cid))
                    ], spacing=5)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=10),
                ft.Row([tabela], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
            ], spacing=10)
        )
        
        # Build individual recurrence selection buttons inside the screen
        config_buttons = []
        for c in configs_in_group:
            cid_curr = c[0]
            c_nome_curr = c[1]
            
            # Check if active (has future occurrences)
            has_future = False
            occurrences_for_c = db.get_transacoes_recorrencia(cid_curr, state["perfil"])
            for occ in occurrences_for_c:
                try:
                    occ_dt = datetime.datetime.strptime(occ[1], "%d/%m/%Y")
                except:
                    occ_dt = now
                if occ_dt >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0):
                    has_future = True
                    break
            
            is_selected = (cid_curr == active_id)
            status_icon = ft.icons.Icons.CIRCLE_ROUNDED
            status_color = "#10b981" if has_future else "#64748b"
            status_tooltip = _t("Ativa (com agendamentos futuros)") if has_future else _t("Inativa (sem agendamentos futuros)")
            
            def make_click_config(target_id):
                return lambda e: select_recurrence(target_id)
                
            config_buttons.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(status_icon, color=status_color, size=10, tooltip=status_tooltip),
                        ft.Text(c_nome_curr, size=12, color="white" if is_selected else get_colors()["text"], weight=ft.FontWeight.BOLD)
                    ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                    bgcolor="#3b82f6" if is_selected else get_colors()["surface"],
                    border=ft.border.all(1, "#3b82f6" if is_selected else get_colors()["border"]),
                    border_radius=8,
                    padding=ft.Padding(12, 10, 12, 10),
                    on_click=make_click_config(cid_curr),
                    width=190
                )
            )
            
        config_selector_panel = ft.Container(
            padding=20,
            bgcolor=get_colors()["surface"],
            border_radius=12,
            border=ft.border.all(1, get_colors()["border"]),
            content=ft.Column([
                ft.Text(_t("Recorrências Cadastradas"), size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.Text(_t("Selecione a recorrência nesta categoria/subcategoria:"), size=12, color="#64748b"),
                ft.Container(height=5),
                ft.Row(controls=config_buttons, wrap=True, spacing=10)
            ], spacing=10)
        )

        dashboard_layout = ft.Column(
            expand=True,
            controls=[
                tab_header,
                ft.Container(height=5),
                tabs_row,
                ft.Container(height=10),
                cards_row,
                ft.Container(height=15),
                ft.Row([
                    ft.Column([
                        batch_container,
                        ft.Container(height=15),
                        config_selector_panel
                    ], width=420),
                    tabela_container
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START, expand=True)
            ],
            spacing=10,
            scroll=ft.ScrollMode.ADAPTIVE
        )
        
        page.floating_action_button = None
        body.content = dashboard_layout
        page.update()

    def render_veiculos():
        veiculos = db.get_veiculos(state["perfil"])
        veiculos = [("geral", "", _t("Geral / Sem vínculo"), state["perfil"])] + veiculos
        
        if "veiculos_selected_ids" not in state:
            state["veiculos_selected_ids"] = set()
        selected_trans_ids = state["veiculos_selected_ids"]
        
        def fmt(val):
            if val is None: return "R$ 0,00"
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        def on_change_perfil_veic(e):
            state["perfil"] = e.control.value
            render_veiculos()

        seletor_perfil_veic = criar_seletor_perfil(on_change_perfil_veic)

        def abrir_form_veiculo(e, veic_to_edit=None):
            txt_mod = ft.TextField(
                label=_t("Modelo do Veículo"),
                value=veic_to_edit[2] if veic_to_edit else "",
                border_color="#475569", focused_border_color="#3b82f6",
                label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
                bgcolor=get_colors()["bg"], height=48, text_size=12
            )
            txt_placa = ft.TextField(
                label=_t("Placa (ex: ABC-1234)"),
                value=veic_to_edit[1] if veic_to_edit else "",
                border_color="#475569", focused_border_color="#3b82f6",
                label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
                bgcolor=get_colors()["bg"], height=48, text_size=12
            )
            chk_migrar = ft.Checkbox(
                label=_t("Vincular gastos 'Geral / Sem vínculo' a este veículo"),
                value=False,
                label_style=ft.TextStyle(size=11, color=get_colors()["text"]),
                visible=(veic_to_edit is None)
            )
            
            def salvar_veiculo(e):
                mod = txt_mod.value.strip()
                placa = txt_placa.value.strip().upper()
                if not mod or not placa:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Preencha todos os campos!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return
                if veic_to_edit:
                    success, msg = db.update_veiculo(veic_to_edit[0], placa, mod)
                else:
                    success, msg = db.add_veiculo(placa, mod, state["perfil"])
                    if success and isinstance(msg, int):
                        if chk_migrar.value:
                            db.migrar_transacoes_gerais_veiculo(msg, state["perfil"])
                        callback = state.pop("post_create_veiculo_callback", None)
                        if callback:
                            callback(msg)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Veículo salvo com sucesso!"), color="white"), bgcolor="#10b981")
                    page.pop_dialog()
                    if not veic_to_edit and isinstance(msg, int):
                        state["active_veiculo_id"] = msg
                    render_veiculos()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao salvar:')} {msg}", color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(_t("Editar Veículo") if veic_to_edit else _t("Adicionar Veículo"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                content=ft.Column([txt_mod, txt_placa, chk_migrar], tight=True, spacing=10),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("SALVAR"), on_click=salvar_veiculo, bgcolor="#3b82f6", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        def abrir_excluir_veiculo(veic_id):
            def confirmar_exclusao(e):
                success, msg = db.delete_veiculo(veic_id)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Veículo excluído com sucesso!"), color="white"), bgcolor="#10b981")
                    if state.get("active_veiculo_id") == veic_id:
                        state["active_veiculo_id"] = None
                    page.pop_dialog()
                    render_veiculos()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao excluir:')} {msg}", color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
            dialog = ft.AlertDialog(
                title=ft.Text(_t("Excluir Veículo?")),
                content=ft.Text(_t("As transações continuarão no histórico, mas serão desvinculadas deste veículo.")),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("EXCLUIR"), on_click=confirmar_exclusao, bgcolor="#ef4444", color="white")
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        btn_novo_veic = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.ADD_ROUNDED, size=16, color="white"),
                ft.Text(_t("NOVO VEÍCULO"), size=11, color="white", weight=ft.FontWeight.BOLD)
            ], spacing=5),
            bgcolor="#3b82f6",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
            on_click=lambda e: abrir_form_veiculo(e)
        )
        
        tab_header = criar_tab_header(
            "veiculos",
            seletor_perfil_veic,
            subcontroles=[btn_novo_veic]
        )

        active_id = state.get("active_veiculo_id")
        if active_id not in [v[0] for v in veiculos]:
            active_id = veiculos[0][0]
            state["active_veiculo_id"] = active_id
            
        active_veiculo = next((v for v in veiculos if v[0] == active_id), veiculos[0])
        state["active_veiculo_id"] = active_veiculo[0]
        
        transacoes_veiculo = db.get_transacoes_veiculo(active_veiculo[0], state["perfil"])
        
        # Apply Month/Year Filters
        import datetime
        now = datetime.datetime.now()
        
        def parse_date(d):
            if d is None:
                return datetime.datetime.min
            if isinstance(d, datetime.datetime):
                return d
            if isinstance(d, datetime.date):
                return datetime.datetime.combine(d, datetime.time.min)
            d_str = str(d).strip()
            if not d_str:
                return datetime.datetime.min
            d_str = d_str.split()[0]
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    return datetime.datetime.strptime(d_str, fmt)
                except:
                    pass
            return datetime.datetime.min
            
        vf = state.get("veiculos_filter", "todos")
        
        def _match_filter_veic(date_str):
            if vf == "todos":
                return True
            dt = parse_date(date_str)
            if dt == datetime.datetime.min:
                return vf == "todos"
            if vf.startswith("ano_"):
                return str(dt.year) == vf[4:]
            if vf.startswith("mes_"):
                parts = vf[4:].split("_")
                return f"{dt.month:02d}" == parts[0] and str(dt.year) == parts[1]
            return True
            
        filtered_trans = [t for t in transacoes_veiculo if _match_filter_veic(t[1])]
                    
        # Apply Sorting
        sort_mode = state.get("veiculos_sort", "date_desc")
        if sort_mode == "date_desc":
            filtered_trans.sort(key=lambda t: (parse_date(t[1]), t[0] if isinstance(t[0], int) else 0), reverse=True)
        elif sort_mode == "date_asc":
            filtered_trans.sort(key=lambda t: (parse_date(t[1]), t[0] if isinstance(t[0], int) else 0))
        elif sort_mode == "cat":
            filtered_trans.sort(key=lambda t: ((t[4] or "").lower(), parse_date(t[1])))
        elif sort_mode == "val_desc":
            filtered_trans.sort(key=lambda t: (t[3] or 0), reverse=True)
        elif sort_mode == "val_asc":
            filtered_trans.sort(key=lambda t: (t[3] or 0))
            
        total_gasto = sum(t[3] for t in filtered_trans)
        
        if vf != "todos":
            gasto_mes_atual = total_gasto
        else:
            gasto_mes_atual = sum(
                t[3] for t in transacoes_veiculo
                if parse_date(t[1]).month == now.month and parse_date(t[1]).year == now.year
            )
            
        card_label_mes = _t("Gasto Mês Atual") if vf == "todos" else _t("Gasto no Período")
        card_total = criar_card_resumo(_t("Total Gasto"), total_gasto, "#ef4444", get_colors()["surface"], small=True)
        card_mes = criar_card_resumo(card_label_mes, gasto_mes_atual, "#fb923c", get_colors()["surface"], small=True)
        card_qtd = criar_card_resumo(_t("Qtd Lançamentos"), len(filtered_trans), "#3b82f6", get_colors()["surface"], small=True, is_currency=False)

        # ── Month Navigator (dashboard-style) ──────────────────────────────
        if vf.startswith("mes_"):
            _p = vf[4:].split("_")
            nav_month, nav_year = int(_p[0]), int(_p[1])
        elif vf.startswith("ano_"):
            nav_month, nav_year = 0, int(vf[4:])
        else:
            nav_month, nav_year = now.month, now.year
        
        _meses_abrev = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                        "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        if vf.startswith("mes_"):
            nav_label = f"{_meses_abrev[nav_month-1]} {nav_year}"
        elif vf.startswith("ano_"):
            nav_label = str(nav_year)
        else:
            nav_label = _t("Todos")
        
        def prev_veic_period(e):
            nonlocal vf
            if vf == "todos":
                state["veiculos_filter"] = f"mes_{now.month:02d}_{now.year}"
            elif vf.startswith("ano_"):
                yr = int(vf[4:])
                state["veiculos_filter"] = f"ano_{yr - 1}"
            else:
                _p = vf[4:].split("_"); m, y = int(_p[0]), int(_p[1])
                m -= 1
                if m < 1: m, y = 12, y - 1
                state["veiculos_filter"] = f"mes_{m:02d}_{y}"
            render_veiculos()
            
        def next_veic_period(e):
            nonlocal vf
            if vf == "todos":
                state["veiculos_filter"] = f"mes_{now.month:02d}_{now.year}"
            elif vf.startswith("ano_"):
                yr = int(vf[4:])
                state["veiculos_filter"] = f"ano_{yr + 1}"
            else:
                _p = vf[4:].split("_"); m, y = int(_p[0]), int(_p[1])
                m += 1
                if m > 12: m, y = 1, y + 1
                state["veiculos_filter"] = f"mes_{m:02d}_{y}"
            render_veiculos()
        
        def set_veic_year(e):
            state["veiculos_filter"] = f"ano_{nav_year}"
            render_veiculos()
        
        def set_veic_todos(e):
            state["veiculos_filter"] = "todos"
            render_veiculos()
        
        btn_prev_v = ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, on_click=prev_veic_period,
                                   icon_color="#94a3b8", icon_size=20, style=ft.ButtonStyle(padding=4))
        btn_next_v = ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, on_click=next_veic_period,
                                   icon_color="#94a3b8", icon_size=20, style=ft.ButtonStyle(padding=4))
        lbl_period_v = ft.Text(nav_label, size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"], width=110, text_align=ft.TextAlign.CENTER)
        
        btn_ano_v = ft.TextButton(
            _t("Ano Completo"),
            on_click=set_veic_year,
            style=ft.ButtonStyle(color="white" if vf.startswith("ano_") else "#64748b", padding=ft.Padding(8, 3, 8, 3))
        )
        btn_todos_v = ft.TextButton(
            _t("Todos"),
            on_click=set_veic_todos,
            style=ft.ButtonStyle(color="white" if vf == "todos" else "#64748b", padding=ft.Padding(8, 3, 8, 3))
        )
        
        sort_options = [
            ("date_desc", _t("Mais recentes")),
            ("date_asc", _t("Mais antigas")),
            ("cat", _t("Tipo / Categoria")),
            ("val_desc", _t("Valor (Maior)")),
            ("val_asc", _t("Valor (Menor)")),
        ]
        drop_sort = ft.Dropdown(
            label=_t("Ordenar por"),
            options=[ft.dropdown.Option(key=so[0], text=so[1]) for so in sort_options],
            value=state.get("veiculos_sort", "date_desc"),
            width=165,
            height=38,
            text_size=11,
            content_padding=ft.Padding(8, 2, 8, 2),
            bgcolor=get_colors()["bg"],
            border_color="#374151",
            focused_border_color="#3b82f6"
        )
        def on_change_veiculos_sort(e):
            state["veiculos_sort"] = e.control.value
            render_veiculos()
        drop_sort.on_change = on_change_veiculos_sort
        
        filtros_row = ft.Row([
            ft.Icon(ft.icons.Icons.CALENDAR_MONTH_ROUNDED, color="#64748b", size=16),
            btn_prev_v, lbl_period_v, btn_next_v,
            ft.Container(width=8),
            btn_ano_v,
            btn_todos_v,
            ft.Container(expand=True),
            drop_sort
        ], spacing=2, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        cards_row = ft.Row(
            controls=[card_total, card_mes, card_qtd],
            spacing=15
        )
        
        config_buttons = []
        for v in veiculos:
            is_selected = (v[0] == active_veiculo[0])
            is_virtual = (v[0] == "geral")
            
            def make_click_veiculo(vid):
                return lambda e: [selected_trans_ids.clear(), state.update({"active_veiculo_id": vid, "veiculos_migration_mode": False}), render_veiculos()]
                
            config_buttons.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.icons.Icons.DIRECTIONS_CAR_ROUNDED, color="#3b82f6" if is_selected else "#64748b", size=16),
                                ft.Column([
                                    ft.Text(v[2], size=12, color="white" if is_selected else get_colors()["text"], weight=ft.FontWeight.BOLD),
                                    ft.Text(v[1] or _t("Geral"), size=10, color="#cbd5e1" if is_selected else "#64748b")
                                ], spacing=2, tight=True, expand=True),
                            ], spacing=8),
                            expand=True,
                            on_click=make_click_veiculo(v[0])
                        ),
                        ft.Row([
                            ft.IconButton(ft.icons.Icons.EDIT_ROUNDED, icon_color="white" if is_selected else "#3b82f6", icon_size=14, on_click=lambda e, v_item=v: abrir_form_veiculo(e, v_item), tooltip=_t("Editar")),
                            ft.IconButton(ft.icons.Icons.DELETE_ROUNDED, icon_color="white" if is_selected else "#ef4444", icon_size=14, on_click=lambda e, vid=v[0]: abrir_excluir_veiculo(vid), tooltip=_t("Excluir")),
                        ], spacing=0, visible=not is_virtual)
                    ], spacing=8, expand=True),
                    bgcolor="#3b82f6" if is_selected else get_colors()["surface"],
                    border=ft.border.all(1, "#3b82f6" if is_selected else get_colors()["border"]),
                    border_radius=8,
                    padding=ft.Padding(10, 8, 10, 8),
                    width=260
                )
            )
            
        config_selector_panel = ft.Container(
            padding=20,
            bgcolor=get_colors()["surface"],
            border_radius=12,
            border=ft.border.all(1, get_colors()["border"]),
            content=ft.Column([
                ft.Text(_t("Veículos Cadastrados"), size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.Container(height=5),
                ft.Column(controls=config_buttons, spacing=8)
            ], spacing=10),
            width=300
        )
        
        def abrir_excluir_transacao(t_id):
            def confirmar_exclusao(e):
                success = db.deletar_transacao(t_id)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Lançamento excluído com sucesso!"), color="white"), bgcolor="#10b981")
                    page.pop_dialog()
                    render_veiculos()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao excluir!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
            dialog = ft.AlertDialog(
                title=ft.Text(_t("Excluir Lançamento?")),
                content=ft.Text(_t("Esta ação excluirá permanentemente esta transação do histórico e do saldo.")),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("EXCLUIR"), on_click=confirmar_exclusao, bgcolor="#ef4444", color="white")
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        row_refs_v = {}

        def make_on_select_changed(tid):
            def handler(e):
                is_selected = False
                if hasattr(e, "selected") and e.selected is not None:
                    is_selected = bool(e.selected)
                elif hasattr(e, "data") and e.data is not None:
                    is_selected = str(e.data).lower() in ("true", "1")
                else:
                    is_selected = tid not in selected_trans_ids
                
                if is_selected:
                    selected_trans_ids.add(tid)
                else:
                    selected_trans_ids.discard(tid)
                
                e.control.selected = is_selected
                e.control.update()
            return handler

        rows = []
        for t in filtered_trans:
            t_id, t_data, t_desc, t_valor, t_cat, t_tipo, t_part, t_tot_part, t_metodo, t_dono, t_band, t_divs, t_obs, t_val_real = t
            
            def make_edit_click(t_item):
                return lambda e: [state.update({"overlay_entity_type": "veiculo", "overlay_entity_id": active_veiculo[0]}), abrir_overlay("despesa", editing_trans_id=t_item[0])]
                
            def make_delete_click(tid):
                return lambda e: abrir_excluir_transacao(tid)
                
            row = ft.DataRow(
                    selected=(t_id in selected_trans_ids),
                    on_select_change=make_on_select_changed(t_id),
                    cells=[
                        ft.DataCell(ft.Text(t_data, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(t_desc, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(t_cat, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(fmt(t_valor), color=get_colors()["text"], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(t_metodo or "Outros", color=get_colors()["text"])),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(ft.icons.Icons.EDIT_ROUNDED, icon_color="#3b82f6", icon_size=18, tooltip=_t("Editar"), on_click=make_edit_click(t)),
                                ft.IconButton(ft.icons.Icons.DELETE_ROUNDED, icon_color="#ef4444", icon_size=18, tooltip=_t("Excluir"), on_click=make_delete_click(t_id)),
                            ], spacing=5)
                        )
                    ]
                )
            row_refs_v[t_id] = row
            rows.append(row)

        other_veiculos = [v for v in veiculos if v[0] != active_veiculo[0]]
        options = [ft.dropdown.Option(key=str(ov[0]), text=f"{ov[2]} ({ov[1]})" if ov[1] else ov[2]) for ov in other_veiculos]
        options.append(ft.dropdown.Option(key="novo", text=_t("+ Novo Item")))
        
        drop_dest = ft.Dropdown(
            label=_t("Destino"),
            options=options,
            width=150,
            height=38,
            text_size=11,
            content_padding=ft.Padding(8, 2, 8, 2),
            bgcolor=get_colors()["bg"],
            border_color="#374151",
            focused_border_color="#3b82f6"
        )
        if options:
            drop_dest.value = options[0].key

        def confirmar_migracao(e):
            if not selected_trans_ids:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Selecione pelo menos um lançamento!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            dest_val = drop_dest.value
            if dest_val == "novo":
                def post_create_callback(new_vid):
                    for tid in selected_trans_ids:
                        db.atualizar_transacao_veiculo(tid, new_vid)
                    selected_trans_ids.clear()
                    state["veiculos_migration_mode"] = False
                    render_veiculos()
                    
                state["post_create_veiculo_callback"] = post_create_callback
                abrir_form_veiculo(e)
            else:
                target_id = None if dest_val == "geral" else int(dest_val)
                for tid in selected_trans_ids:
                    db.atualizar_transacao_veiculo(tid, target_id)
                selected_trans_ids.clear()
                state["veiculos_migration_mode"] = False
                render_veiculos()

        tabela_veiculos = ft.DataTable(
            show_checkbox_column=state.get("veiculos_migration_mode", False),
            columns=[
                ft.DataColumn(ft.Text(_t("Mês/Data"))),
                ft.DataColumn(ft.Text(_t("Descrição"))),
                ft.DataColumn(ft.Text(_t("Categoria"))),
                ft.DataColumn(ft.Text(_t("Valor"))),
                ft.DataColumn(ft.Text(_t("Método"))),
                ft.DataColumn(ft.Text(_t("Ações"))),
            ],
            rows=rows,
            border_radius=8,
            border=ft.border.all(0.5, get_colors()["border"]),
            heading_row_color=get_colors()["surface"],
            expand=True
        )
        tabela = tabela_veiculos

        def selecionar_todos_veiculos(e):
            all_ids = {t[0] for t in filtered_trans}
            if all_ids.issubset(selected_trans_ids):
                for tid in all_ids:
                    selected_trans_ids.discard(tid)
                    if tid in row_refs_v: row_refs_v[tid].selected = False
            else:
                for tid in all_ids:
                    selected_trans_ids.add(tid)
                    if tid in row_refs_v: row_refs_v[tid].selected = True
            tabela_veiculos.update()
        
        all_sel_veic = bool(filtered_trans) and {t[0] for t in filtered_trans}.issubset(selected_trans_ids)
        
        tabela_header_row = ft.Row([
            ft.Row([
                ft.Text(_t("Selecione as transações para migrar:"), size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.TextButton(
                    _t("Desmarcar Todos") if all_sel_veic else _t("Selecionar Todos"),
                    on_click=selecionar_todos_veiculos,
                    style=ft.ButtonStyle(color="#3b82f6", padding=ft.Padding(6, 2, 6, 2))
                ),
            ], spacing=8),
            ft.Row([
                drop_dest,
                ft.IconButton(ft.icons.Icons.CHECK_ROUNDED, icon_color="#10b981", tooltip=_t("Confirmar Migração"), on_click=confirmar_migracao),
                ft.IconButton(ft.icons.Icons.CLOSE_ROUNDED, icon_color="#ef4444", tooltip=_t("Cancelar"), on_click=lambda e: [selected_trans_ids.clear(), state.update({"veiculos_migration_mode": False}), render_veiculos()]),
            ], spacing=5)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN) if state.get("veiculos_migration_mode") else ft.Row([
            ft.Text(f"{_t('Gastos de')} {active_veiculo[2]} ({active_veiculo[1]})" if active_veiculo[1] else f"{_t('Gastos de')} {active_veiculo[2]}", size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            ft.Row([
                ft.ElevatedButton(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.MOVE_UP_ROUNDED, size=16, color="white"),
                        ft.Text(_t("MIGRAR PARA..."), size=11, color="white", weight=ft.FontWeight.BOLD)
                    ], spacing=5),
                    bgcolor="#3b82f6",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                    on_click=lambda e: [state.update({"veiculos_migration_mode": True}), render_veiculos()]
                ),
                ft.ElevatedButton(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.ADD_ROUNDED, size=16, color="white"),
                        ft.Text(_t("NOVO GASTO"), size=11, color="white", weight=ft.FontWeight.BOLD)
                    ], spacing=5),
                    bgcolor="#10b981",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                    on_click=lambda e: [state.update({"overlay_entity_type": "veiculo", "overlay_entity_id": active_veiculo[0]}), abrir_overlay("despesa")]
                )
            ], spacing=10)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        tabela_container = ft.Container(
            padding=20,
            bgcolor=get_colors()["surface"],
            border_radius=12,
            border=ft.border.all(1, get_colors()["border"]),
            expand=True,
            content=ft.Column([
                tabela_header_row,
                filtros_row,
                ft.Container(height=5),
                ft.Row([tabela_veiculos], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
            ], spacing=10)
        )
        
        dashboard_layout = ft.Column(
            expand=True,
            controls=[
                tab_header,
                ft.Container(height=5),
                cards_row,
                ft.Container(height=10),
                ft.Row([
                    config_selector_panel,
                    tabela_container
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START, expand=True)
            ],
            spacing=10,
            scroll=ft.ScrollMode.ADAPTIVE
        )
        
        page.floating_action_button = None
        body.content = dashboard_layout
        page.update()

    def render_pets():
        pets = db.get_pets(state["perfil"])
        pets = [("geral", _t("Geral / Sem vínculo"), "", state["perfil"])] + pets
        
        if "pets_selected_ids" not in state:
            state["pets_selected_ids"] = set()
        selected_trans_ids = state["pets_selected_ids"]
        
        def fmt(val):
            if val is None: return "R$ 0,00"
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        def on_change_perfil_pet(e):
            state["perfil"] = e.control.value
            render_pets()

        seletor_perfil_pet = criar_seletor_perfil(on_change_perfil_pet)

        def abrir_form_pet(e, pet_to_edit=None):
            txt_nome = ft.TextField(
                label=_t("Nome do Pet"),
                value=pet_to_edit[1] if pet_to_edit else "",
                border_color="#475569", focused_border_color="#3b82f6",
                label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
                bgcolor=get_colors()["bg"], height=48, text_size=12
            )
            txt_raca = ft.TextField(
                label=_t("Espécie / Raça"),
                value=pet_to_edit[2] if pet_to_edit else "",
                border_color="#475569", focused_border_color="#3b82f6",
                label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
                bgcolor=get_colors()["bg"], height=48, text_size=12
            )
            chk_migrar = ft.Checkbox(
                label=_t("Vincular gastos 'Geral / Sem vínculo' a este pet"),
                value=False,
                label_style=ft.TextStyle(size=11, color=get_colors()["text"]),
                visible=(pet_to_edit is None)
            )
            
            def salvar_pet(e):
                nome = txt_nome.value.strip()
                raca = txt_raca.value.strip()
                if not nome:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Preencha o nome do pet!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return
                if pet_to_edit:
                    success, msg = db.update_pet(pet_to_edit[0], nome, raca)
                else:
                    success, msg = db.add_pet(nome, raca, state["perfil"])
                    if success and isinstance(msg, int):
                        if chk_migrar.value:
                            db.migrar_transacoes_gerais_pet(msg, state["perfil"])
                        callback = state.pop("post_create_pet_callback", None)
                        if callback:
                            callback(msg)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Pet salvo com sucesso!"), color="white"), bgcolor="#10b981")
                    page.pop_dialog()
                    if not pet_to_edit and isinstance(msg, int):
                        state["active_pet_id"] = msg
                    render_pets()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao salvar:')} {msg}", color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(_t("Editar Pet") if pet_to_edit else _t("Adicionar Pet"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                content=ft.Column([txt_nome, txt_raca, chk_migrar], tight=True, spacing=10),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("SALVAR"), on_click=salvar_pet, bgcolor="#3b82f6", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        def abrir_excluir_pet(pet_id):
            def confirmar_exclusao(e):
                success, msg = db.delete_pet(pet_id)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Pet excluído com sucesso!"), color="white"), bgcolor="#10b981")
                    if state.get("active_pet_id") == pet_id:
                        state["active_pet_id"] = None
                    page.pop_dialog()
                    render_pets()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao excluir:')} {msg}", color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
            dialog = ft.AlertDialog(
                title=ft.Text(_t("Excluir Pet?")),
                content=ft.Text(_t("As transações continuarão no histórico, mas serão desvinculadas deste pet.")),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("EXCLUIR"), on_click=confirmar_exclusao, bgcolor="#ef4444", color="white")
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        btn_novo_pet = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.ADD_ROUNDED, size=16, color="white"),
                ft.Text(_t("NOVO PET"), size=11, color="white", weight=ft.FontWeight.BOLD)
            ], spacing=5),
            bgcolor="#3b82f6",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
            on_click=lambda e: abrir_form_pet(e)
        )
        
        tab_header = criar_tab_header(
            "pets",
            seletor_perfil_pet,
            subcontroles=[btn_novo_pet]
        )

        active_id = state.get("active_pet_id")
        if active_id not in [p[0] for p in pets]:
            active_id = pets[0][0]
            state["active_pet_id"] = active_id
            
        active_pet = next((p for p in pets if p[0] == active_id), pets[0])
        state["active_pet_id"] = active_pet[0]
        
        transacoes_pet = db.get_transacoes_pet(active_pet[0], state["perfil"])
        
        # Apply Month/Year Filters
        import datetime
        now = datetime.datetime.now()
        
        def parse_date(d):
            if d is None:
                return datetime.datetime.min
            if isinstance(d, datetime.datetime):
                return d
            if isinstance(d, datetime.date):
                return datetime.datetime.combine(d, datetime.time.min)
            d_str = str(d).strip()
            if not d_str:
                return datetime.datetime.min
            d_str = d_str.split()[0]
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    return datetime.datetime.strptime(d_str, fmt)
                except:
                    pass
            return datetime.datetime.min
            
        pf = state.get("pets_filter", "todos")
        
        def _match_filter_pet(date_str):
            if pf == "todos":
                return True
            dt = parse_date(date_str)
            if dt == datetime.datetime.min:
                return pf == "todos"
            if pf.startswith("ano_"):
                return str(dt.year) == pf[4:]
            if pf.startswith("mes_"):
                parts = pf[4:].split("_")
                return f"{dt.month:02d}" == parts[0] and str(dt.year) == parts[1]
            return True
            
        filtered_trans = [t for t in transacoes_pet if _match_filter_pet(t[1])]
                    
        # Apply Sorting
        sort_mode = state.get("pets_sort", "date_desc")
        if sort_mode == "date_desc":
            filtered_trans.sort(key=lambda t: (parse_date(t[1]), t[0] if isinstance(t[0], int) else 0), reverse=True)
        elif sort_mode == "date_asc":
            filtered_trans.sort(key=lambda t: (parse_date(t[1]), t[0] if isinstance(t[0], int) else 0))
        elif sort_mode == "cat":
            filtered_trans.sort(key=lambda t: ((t[4] or "").lower(), parse_date(t[1])))
        elif sort_mode == "val_desc":
            filtered_trans.sort(key=lambda t: (t[3] or 0), reverse=True)
        elif sort_mode == "val_asc":
            filtered_trans.sort(key=lambda t: (t[3] or 0))
            
        total_gasto = sum(t[3] for t in filtered_trans)
        
        if pf != "todos":
            gasto_mes_atual = total_gasto
        else:
            gasto_mes_atual = sum(
                t[3] for t in transacoes_pet
                if parse_date(t[1]).month == now.month and parse_date(t[1]).year == now.year
            )
            
        card_label_mes = _t("Gasto Mês Atual") if pf == "todos" else _t("Gasto no Período")
        card_total = criar_card_resumo(_t("Total Gasto"), total_gasto, "#ef4444", get_colors()["surface"], small=True)
        card_mes = criar_card_resumo(card_label_mes, gasto_mes_atual, "#fb923c", get_colors()["surface"], small=True)
        card_qtd = criar_card_resumo(_t("Qtd Lançamentos"), len(filtered_trans), "#3b82f6", get_colors()["surface"], small=True, is_currency=False)

        # ── Month Navigator (dashboard-style) ──────────────────────────────
        if pf.startswith("mes_"):
            _p = pf[4:].split("_")
            nav_month, nav_year = int(_p[0]), int(_p[1])
        elif pf.startswith("ano_"):
            nav_month, nav_year = 0, int(pf[4:])
        else:
            nav_month, nav_year = now.month, now.year
        
        _meses_abrev = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                        "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        if pf.startswith("mes_"):
            nav_label = f"{_meses_abrev[nav_month-1]} {nav_year}"
        elif pf.startswith("ano_"):
            nav_label = str(nav_year)
        else:
            nav_label = _t("Todos")
        
        def prev_pet_period(e):
            nonlocal pf
            if pf == "todos":
                state["pets_filter"] = f"mes_{now.month:02d}_{now.year}"
            elif pf.startswith("ano_"):
                yr = int(pf[4:])
                state["pets_filter"] = f"ano_{yr - 1}"
            else:
                _p = pf[4:].split("_"); m, y = int(_p[0]), int(_p[1])
                m -= 1
                if m < 1: m, y = 12, y - 1
                state["pets_filter"] = f"mes_{m:02d}_{y}"
            render_pets()
            
        def next_pet_period(e):
            nonlocal pf
            if pf == "todos":
                state["pets_filter"] = f"mes_{now.month:02d}_{now.year}"
            elif pf.startswith("ano_"):
                yr = int(pf[4:])
                state["pets_filter"] = f"ano_{yr + 1}"
            else:
                _p = pf[4:].split("_"); m, y = int(_p[0]), int(_p[1])
                m += 1
                if m > 12: m, y = 1, y + 1
                state["pets_filter"] = f"mes_{m:02d}_{y}"
            render_pets()
        
        def set_pet_year(e):
            state["pets_filter"] = f"ano_{nav_year}"
            render_pets()
        
        def set_pet_todos(e):
            state["pets_filter"] = "todos"
            render_pets()
        
        btn_prev_p = ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, on_click=prev_pet_period,
                                   icon_color="#94a3b8", icon_size=20, style=ft.ButtonStyle(padding=4))
        btn_next_p = ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, on_click=next_pet_period,
                                   icon_color="#94a3b8", icon_size=20, style=ft.ButtonStyle(padding=4))
        lbl_period_p = ft.Text(nav_label, size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"], width=110, text_align=ft.TextAlign.CENTER)
        
        btn_ano_p = ft.TextButton(
            _t("Ano Completo"),
            on_click=set_pet_year,
            style=ft.ButtonStyle(color="white" if pf.startswith("ano_") else "#64748b", padding=ft.Padding(8, 3, 8, 3))
        )
        btn_todos_p = ft.TextButton(
            _t("Todos"),
            on_click=set_pet_todos,
            style=ft.ButtonStyle(color="white" if pf == "todos" else "#64748b", padding=ft.Padding(8, 3, 8, 3))
        )
        
        sort_options = [
            ("date_desc", _t("Mais recentes")),
            ("date_asc", _t("Mais antigas")),
            ("cat", _t("Tipo / Categoria")),
            ("val_desc", _t("Valor (Maior)")),
            ("val_asc", _t("Valor (Menor)")),
        ]
        drop_sort = ft.Dropdown(
            label=_t("Ordenar por"),
            options=[ft.dropdown.Option(key=so[0], text=so[1]) for so in sort_options],
            value=state.get("pets_sort", "date_desc"),
            width=165,
            height=38,
            text_size=11,
            content_padding=ft.Padding(8, 2, 8, 2),
            bgcolor=get_colors()["bg"],
            border_color="#374151",
            focused_border_color="#3b82f6"
        )
        def on_change_pets_sort(e):
            state["pets_sort"] = e.control.value
            render_pets()
        drop_sort.on_change = on_change_pets_sort
        
        filtros_row = ft.Row([
            ft.Icon(ft.icons.Icons.CALENDAR_MONTH_ROUNDED, color="#64748b", size=16),
            btn_prev_p, lbl_period_p, btn_next_p,
            ft.Container(width=8),
            btn_ano_p,
            btn_todos_p,
            ft.Container(expand=True),
            drop_sort
        ], spacing=2, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        cards_row = ft.Row(
            controls=[card_total, card_mes, card_qtd],
            spacing=15
        )
        
        config_buttons = []
        for p in pets:
            is_selected = (p[0] == active_pet[0])
            is_virtual = (p[0] == "geral")
            
            def make_click_pet(pid):
                return lambda e: [selected_trans_ids.clear(), state.update({"active_pet_id": pid, "pets_migration_mode": False}), render_pets()]
                
            config_buttons.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.icons.Icons.PETS_ROUNDED, color="#3b82f6" if is_selected else "#64748b", size=16),
                                ft.Column([
                                    ft.Text(p[1], size=12, color="white" if is_selected else get_colors()["text"], weight=ft.FontWeight.BOLD),
                                    ft.Text(p[2] or _t("Geral"), size=10, color="#cbd5e1" if is_selected else "#64748b")
                                ], spacing=2, tight=True, expand=True),
                            ], spacing=8),
                            expand=True,
                            on_click=make_click_pet(p[0])
                        ),
                        ft.Row([
                            ft.IconButton(ft.icons.Icons.EDIT_ROUNDED, icon_color="white" if is_selected else "#3b82f6", icon_size=14, on_click=lambda e, p_item=p: abrir_form_pet(e, p_item), tooltip=_t("Editar")),
                            ft.IconButton(ft.icons.Icons.DELETE_ROUNDED, icon_color="white" if is_selected else "#ef4444", icon_size=14, on_click=lambda e, pid=p[0]: abrir_excluir_pet(pid), tooltip=_t("Excluir")),
                        ], spacing=0, visible=not is_virtual)
                    ], spacing=8, expand=True),
                    bgcolor="#3b82f6" if is_selected else get_colors()["surface"],
                    border=ft.border.all(1, "#3b82f6" if is_selected else get_colors()["border"]),
                    border_radius=8,
                    padding=ft.Padding(10, 8, 10, 8),
                    width=260
                )
            )
            
        config_selector_panel = ft.Container(
            padding=20,
            bgcolor=get_colors()["surface"],
            border_radius=12,
            border=ft.border.all(1, get_colors()["border"]),
            content=ft.Column([
                ft.Text(_t("Pets Cadastrados"), size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.Container(height=5),
                ft.Column(controls=config_buttons, spacing=8)
            ], spacing=10),
            width=300
        )
        
        def abrir_excluir_transacao(t_id):
            def confirmar_exclusao(e):
                success = db.deletar_transacao(t_id)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Lançamento excluído com sucesso!"), color="white"), bgcolor="#10b981")
                    page.pop_dialog()
                    render_pets()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao excluir!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
            dialog = ft.AlertDialog(
                title=ft.Text(_t("Excluir Lançamento?")),
                content=ft.Text(_t("Esta ação excluirá permanentemente esta transação do histórico e do saldo.")),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("EXCLUIR"), on_click=confirmar_exclusao, bgcolor="#ef4444", color="white")
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        row_refs_p = {}

        def make_on_select_changed(tid):
            def handler(e):
                is_selected = False
                if hasattr(e, "selected") and e.selected is not None:
                    is_selected = bool(e.selected)
                elif hasattr(e, "data") and e.data is not None:
                    is_selected = str(e.data).lower() in ("true", "1")
                else:
                    is_selected = tid not in selected_trans_ids
                
                if is_selected:
                    selected_trans_ids.add(tid)
                else:
                    selected_trans_ids.discard(tid)
                
                e.control.selected = is_selected
                e.control.update()
            return handler

        rows = []
        for t in filtered_trans:
            t_id, t_data, t_desc, t_valor, t_cat, t_tipo, t_part, t_tot_part, t_metodo, t_dono, t_band, t_divs, t_obs, t_val_real = t
            
            def make_edit_click(t_item):
                return lambda e: [state.update({"overlay_entity_type": "pet", "overlay_entity_id": active_pet[0]}), abrir_overlay("despesa", editing_trans_id=t_item[0])]
                
            def make_delete_click(tid):
                return lambda e: abrir_excluir_transacao(tid)
                
            row = ft.DataRow(
                    selected=(t_id in selected_trans_ids),
                    on_select_change=make_on_select_changed(t_id),
                    cells=[
                        ft.DataCell(ft.Text(t_data, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(t_desc, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(t_cat, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(fmt(t_valor), color=get_colors()["text"], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(t_metodo or "Outros", color=get_colors()["text"])),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(ft.icons.Icons.EDIT_ROUNDED, icon_color="#3b82f6", icon_size=18, tooltip=_t("Editar"), on_click=make_edit_click(t)),
                                ft.IconButton(ft.icons.Icons.DELETE_ROUNDED, icon_color="#ef4444", icon_size=18, tooltip=_t("Excluir"), on_click=make_delete_click(t_id)),
                            ], spacing=5)
                        )
                    ]
                )
            row_refs_p[t_id] = row
            rows.append(row)

        other_pets = [p for p in pets if p[0] != active_pet[0]]
        options = [ft.dropdown.Option(key=str(op[0]), text=op[1]) for op in other_pets]
        options.append(ft.dropdown.Option(key="novo", text=_t("+ Novo Item")))
        
        drop_dest = ft.Dropdown(
            label=_t("Destino"),
            options=options,
            width=150,
            height=38,
            text_size=11,
            content_padding=ft.Padding(8, 2, 8, 2),
            bgcolor=get_colors()["bg"],
            border_color="#374151",
            focused_border_color="#3b82f6"
        )
        if options:
            drop_dest.value = options[0].key

        def confirmar_migracao(e):
            if not selected_trans_ids:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Selecione pelo menos um lançamento!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            dest_val = drop_dest.value
            if dest_val == "novo":
                def post_create_callback(new_pid):
                    for tid in selected_trans_ids:
                        db.atualizar_transacao_pet(tid, new_pid)
                    selected_trans_ids.clear()
                    state["pets_migration_mode"] = False
                    render_pets()
                    
                state["post_create_pet_callback"] = post_create_callback
                abrir_form_pet(e)
            else:
                target_id = None if dest_val == "geral" else int(dest_val)
                for tid in selected_trans_ids:
                    db.atualizar_transacao_pet(tid, target_id)
                selected_trans_ids.clear()
                state["pets_migration_mode"] = False
                render_pets()

        tabela_pets = ft.DataTable(
            show_checkbox_column=state.get("pets_migration_mode", False),
            columns=[
                ft.DataColumn(ft.Text(_t("Mês/Data"))),
                ft.DataColumn(ft.Text(_t("Descrição"))),
                ft.DataColumn(ft.Text(_t("Categoria"))),
                ft.DataColumn(ft.Text(_t("Valor"))),
                ft.DataColumn(ft.Text(_t("Método"))),
                ft.DataColumn(ft.Text(_t("Ações"))),
            ],
            rows=rows,
            border_radius=8,
            border=ft.border.all(0.5, get_colors()["border"]),
            heading_row_color=get_colors()["surface"],
            expand=True
        )
        tabela = tabela_pets

        def selecionar_todos_pets(e):
            all_ids = {t[0] for t in filtered_trans}
            if all_ids.issubset(selected_trans_ids):
                for tid in all_ids:
                    selected_trans_ids.discard(tid)
                    if tid in row_refs_p: row_refs_p[tid].selected = False
            else:
                for tid in all_ids:
                    selected_trans_ids.add(tid)
                    if tid in row_refs_p: row_refs_p[tid].selected = True
            tabela_pets.update()
        
        all_sel_pets = bool(filtered_trans) and {t[0] for t in filtered_trans}.issubset(selected_trans_ids)
        
        tabela_header_row = ft.Row([
            ft.Row([
                ft.Text(_t("Selecione as transações para migrar:"), size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.TextButton(
                    _t("Desmarcar Todos") if all_sel_pets else _t("Selecionar Todos"),
                    on_click=selecionar_todos_pets,
                    style=ft.ButtonStyle(color="#3b82f6", padding=ft.Padding(6, 2, 6, 2))
                ),
            ], spacing=8),
            ft.Row([
                drop_dest,
                ft.IconButton(ft.icons.Icons.CHECK_ROUNDED, icon_color="#10b981", tooltip=_t("Confirmar Migração"), on_click=confirmar_migracao),
                ft.IconButton(ft.icons.Icons.CLOSE_ROUNDED, icon_color="#ef4444", tooltip=_t("Cancelar"), on_click=lambda e: [selected_trans_ids.clear(), state.update({"pets_migration_mode": False}), render_pets()]),
            ], spacing=5)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN) if state.get("pets_migration_mode") else ft.Row([
            ft.Text(f"{_t('Gastos de')} {active_pet[1]}", size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            ft.Row([
                ft.ElevatedButton(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.MOVE_UP_ROUNDED, size=16, color="white"),
                        ft.Text(_t("MIGRAR PARA..."), size=11, color="white", weight=ft.FontWeight.BOLD)
                    ], spacing=5),
                    bgcolor="#3b82f6",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                    on_click=lambda e: [state.update({"pets_migration_mode": True}), render_pets()]
                ),
                ft.ElevatedButton(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.ADD_ROUNDED, size=16, color="white"),
                        ft.Text(_t("NOVO GASTO"), size=11, color="white", weight=ft.FontWeight.BOLD)
                    ], spacing=5),
                    bgcolor="#10b981",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                    on_click=lambda e: [state.update({"overlay_entity_type": "pet", "overlay_entity_id": active_pet[0]}), abrir_overlay("despesa")]
                )
            ], spacing=10)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        tabela_container = ft.Container(
            padding=20,
            bgcolor=get_colors()["surface"],
            border_radius=12,
            border=ft.border.all(1, get_colors()["border"]),
            expand=True,
            content=ft.Column([
                tabela_header_row,
                filtros_row,
                ft.Container(height=5),
                ft.Row([tabela_pets], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
            ], spacing=10)
        )
        
        dashboard_layout = ft.Column(
            expand=True,
            controls=[
                tab_header,
                ft.Container(height=5),
                cards_row,
                ft.Container(height=10),
                ft.Row([
                    config_selector_panel,
                    tabela_container
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START, expand=True)
            ],
            spacing=10,
            scroll=ft.ScrollMode.ADAPTIVE
        )
        
        page.floating_action_button = None
        body.content = dashboard_layout
        page.update()

    def render_saude():
        saude_list = db.get_saude(state["perfil"])
        
        def on_change_perfil_saude(e):
            state["perfil"] = e.control.value
            render_saude()

        seletor_perfil_saude = criar_seletor_perfil(on_change_perfil_saude)

        def abrir_form_saude(e, saude_to_edit=None):
            txt_nome = ft.TextField(
                label=_t("Nome / Pessoa / Serviço"),
                value=saude_to_edit[1] if saude_to_edit else "",
                border_color="#475569", focused_border_color="#3b82f6",
                label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
                bgcolor=get_colors()["bg"], height=48, text_size=12
            )
            txt_desc = ft.TextField(
                label=_t("Descrição / Detalhes"),
                value=saude_to_edit[2] if saude_to_edit else "",
                border_color="#475569", focused_border_color="#3b82f6",
                label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
                bgcolor=get_colors()["bg"], height=48, text_size=12
            )
            chk_migrar = ft.Checkbox(
                label=_t("Vincular gastos 'Geral / Sem vínculo' a este item de saúde"),
                value=False,
                label_style=ft.TextStyle(size=11, color=get_colors()["text"]),
                visible=(saude_to_edit is None)
            )
            
            def salvar_saude(e):
                nome = txt_nome.value.strip()
                descricao = txt_desc.value.strip()
                if not nome:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Preencha o nome!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return
                if saude_to_edit:
                    success, msg = db.update_saude(saude_to_edit[0], nome, descricao)
                else:
                    success, msg = db.add_saude(nome, descricao, state["perfil"])
                    if success and isinstance(msg, int):
                        if chk_migrar.value:
                            db.migrar_transacoes_gerais_saude(msg, state["perfil"])
                        callback = state.pop("post_create_saude_callback", None)
                        if callback:
                            callback(msg)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Item de saúde salvo com sucesso!"), color="white"), bgcolor="#10b981")
                    page.pop_dialog()
                    if not saude_to_edit and isinstance(msg, int):
                        state["active_saude_id"] = msg
                    render_saude()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao salvar:')} {msg}", color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(_t("Editar Item de Saúde") if saude_to_edit else _t("Adicionar Item de Saúde"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                content=ft.Column([txt_nome, txt_desc, chk_migrar], tight=True, spacing=10),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("SALVAR"), on_click=salvar_saude, bgcolor="#3b82f6", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        def abrir_excluir_saude(saude_id):
            def confirmar_exclusao(e):
                success, msg = db.delete_saude(saude_id)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Item de saúde excluído com sucesso!"), color="white"), bgcolor="#10b981")
                    if state.get("active_saude_id") == saude_id:
                        state["active_saude_id"] = None
                    page.pop_dialog()
                    render_saude()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao excluir:')} {msg}", color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
            dialog = ft.AlertDialog(
                title=ft.Text(_t("Excluir Item de Saúde?")),
                content=ft.Text(_t("As transações continuarão no histórico, mas serão desvinculadas deste item.")),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("EXCLUIR"), on_click=confirmar_exclusao, bgcolor="#ef4444", color="white")
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        btn_novo_saude = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.ADD_ROUNDED, size=16, color="white"),
                ft.Text(_t("NOVO LANÇAMENTO"), size=11, color="white", weight=ft.FontWeight.BOLD)
            ], spacing=5),
            bgcolor="#3b82f6",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
            on_click=lambda e: abrir_form_saude(e)
        )
        
        tab_header = criar_tab_header(
            "saude",
            seletor_perfil_saude,
            subcontroles=[btn_novo_saude]
        )
        
        if not saude_list:
            empty_state = ft.Container(
                alignment=ft.Alignment(0, 0),
                expand=True,
                padding=40,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.icons.Icons.LOCAL_HOSPITAL_ROUNDED, size=80, color="#64748b"),
                        ft.Text(_t("Nenhum item de saúde cadastrado"), size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Text(_t("Cadastre itens de saúde (como membros da família, convênios ou categorias de gastos) para gerenciar."), size=14, color="#64748b", text_align=ft.TextAlign.CENTER),
                        ft.Container(height=10),
                        ft.ElevatedButton(
                            _t("CADASTRAR PRIMEIRA ITEM"),
                            on_click=lambda e: abrir_form_saude(e),
                            bgcolor="#3b82f6",
                            color="white"
                        )
                    ]
                )
            )
            body.content = ft.Column(expand=True, controls=[tab_header, ft.Divider(color="#1f2937", height=20), empty_state])
            page.update()
            return

        active_id = state.get("active_saude_id")
        if active_id not in [s[0] for s in saude_list]:
            active_id = saude_list[0][0]
            state["active_saude_id"] = active_id
            
        active_saude = next((s for s in saude_list if s[0] == active_id), saude_list[0])
        state["active_saude_id"] = active_saude[0]
        
        transacoes_saude = db.get_transacoes_saude(active_saude[0], state["perfil"])
        
        # Apply Month/Year Filters
        import datetime
        now = datetime.datetime.now()
        
        def parse_date(d):
            if d is None:
                return datetime.datetime.min
            if isinstance(d, datetime.datetime):
                return d
            if isinstance(d, datetime.date):
                return datetime.datetime.combine(d, datetime.time.min)
            d_str = str(d).strip()
            if not d_str:
                return datetime.datetime.min
            d_str = d_str.split()[0]
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    return datetime.datetime.strptime(d_str, fmt)
                except:
                    pass
            return datetime.datetime.min
        
        # ── Filter state: "todos" | "ano_YYYY" | "mes_MM_YYYY"
        sf = state.get("saude_filter", "todos")
        
        def _match_filter_saude(date_str):
            if sf == "todos":
                return True
            dt = parse_date(date_str)
            if dt == datetime.datetime.min:
                return sf == "todos"
            if sf.startswith("ano_"):
                return str(dt.year) == sf[4:]
            if sf.startswith("mes_"):
                parts = sf[4:].split("_")
                return f"{dt.month:02d}" == parts[0] and str(dt.year) == parts[1]
            return True
        
        filtered_trans = [t for t in transacoes_saude if _match_filter_saude(t[1])]
            
        # Apply Sorting
        sort_mode = state.get("saude_sort", "date_desc")
        if sort_mode == "date_desc":
            filtered_trans.sort(key=lambda t: (parse_date(t[1]), t[0] if isinstance(t[0], int) else 0), reverse=True)
        elif sort_mode == "date_asc":
            filtered_trans.sort(key=lambda t: (parse_date(t[1]), t[0] if isinstance(t[0], int) else 0))
        elif sort_mode == "cat":
            filtered_trans.sort(key=lambda t: ((t[4] or "").lower(), parse_date(t[1])))
        elif sort_mode == "val_desc":
            filtered_trans.sort(key=lambda t: (t[3] or 0), reverse=True)
        elif sort_mode == "val_asc":
            filtered_trans.sort(key=lambda t: (t[3] or 0))
            
        total_gasto = sum(t[3] for t in filtered_trans)
        
        if sf != "todos":
            gasto_mes_atual = total_gasto
        else:
            gasto_mes_atual = sum(
                t[3] for t in transacoes_saude
                if parse_date(t[1]).month == now.month and parse_date(t[1]).year == now.year
            )
        
        card_label_mes = _t("Gasto Mês Atual") if sf == "todos" else _t("Gasto no Período")
        card_total = criar_card_resumo(_t("Total Gasto"), total_gasto, "#ef4444", get_colors()["surface"], small=True)
        card_mes = criar_card_resumo(card_label_mes, gasto_mes_atual, "#fb923c", get_colors()["surface"], small=True)
        card_qtd = criar_card_resumo(_t("Qtd Lançamentos"), len(filtered_trans), "#3b82f6", get_colors()["surface"], small=True, is_currency=False)
        
        # ── Month Navigator (dashboard-style) ──────────────────────────────
        if sf.startswith("mes_"):
            _p = sf[4:].split("_")
            nav_month, nav_year = int(_p[0]), int(_p[1])
        elif sf.startswith("ano_"):
            nav_month, nav_year = 0, int(sf[4:])
        else:
            nav_month, nav_year = now.month, now.year
        
        _meses_abrev = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                        "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        if sf.startswith("mes_"):
            nav_label = f"{_meses_abrev[nav_month-1]} {nav_year}"
        elif sf.startswith("ano_"):
            nav_label = str(nav_year)
        else:
            nav_label = _t("Todos")
        
        def prev_saude_period(e):
            nonlocal sf
            if sf == "todos":
                state["saude_filter"] = f"mes_{now.month:02d}_{now.year}"
            elif sf.startswith("ano_"):
                yr = int(sf[4:])
                state["saude_filter"] = f"ano_{yr - 1}"
            else:
                _p = sf[4:].split("_"); m, y = int(_p[0]), int(_p[1])
                m -= 1
                if m < 1: m, y = 12, y - 1
                state["saude_filter"] = f"mes_{m:02d}_{y}"
            render_saude()
            
        def next_saude_period(e):
            nonlocal sf
            if sf == "todos":
                state["saude_filter"] = f"mes_{now.month:02d}_{now.year}"
            elif sf.startswith("ano_"):
                yr = int(sf[4:])
                state["saude_filter"] = f"ano_{yr + 1}"
            else:
                _p = sf[4:].split("_"); m, y = int(_p[0]), int(_p[1])
                m += 1
                if m > 12: m, y = 1, y + 1
                state["saude_filter"] = f"mes_{m:02d}_{y}"
            render_saude()
        
        def set_saude_year(e):
            state["saude_filter"] = f"ano_{nav_year}"
            render_saude()
        
        def set_saude_todos(e):
            state["saude_filter"] = "todos"
            render_saude()
        
        btn_prev_s = ft.IconButton(ft.icons.Icons.CHEVRON_LEFT_ROUNDED, on_click=prev_saude_period,
                                   icon_color="#94a3b8", icon_size=20, style=ft.ButtonStyle(padding=4))
        btn_next_s = ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, on_click=next_saude_period,
                                   icon_color="#94a3b8", icon_size=20, style=ft.ButtonStyle(padding=4))
        lbl_period_s = ft.Text(nav_label, size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"], width=110, text_align=ft.TextAlign.CENTER)
        
        btn_ano_s = ft.TextButton(
            _t("Ano Completo"),
            on_click=set_saude_year,
            style=ft.ButtonStyle(color="white" if sf.startswith("ano_") else "#64748b", padding=ft.Padding(8, 3, 8, 3))
        )
        btn_todos_s = ft.TextButton(
            _t("Todos"),
            on_click=set_saude_todos,
            style=ft.ButtonStyle(color="white" if sf == "todos" else "#64748b", padding=ft.Padding(8, 3, 8, 3))
        )
        
        sort_options = [
            ("date_desc", _t("Mais recentes")),
            ("date_asc", _t("Mais antigas")),
            ("cat", _t("Tipo / Categoria")),
            ("val_desc", _t("Valor (Maior)")),
            ("val_asc", _t("Valor (Menor)")),
        ]
        drop_sort = ft.Dropdown(
            label=_t("Ordenar por"),
            options=[ft.dropdown.Option(key=so[0], text=so[1]) for so in sort_options],
            value=state.get("saude_sort", "date_desc"),
            width=165,
            height=38,
            text_size=11,
            content_padding=ft.Padding(8, 2, 8, 2),
            bgcolor=get_colors()["bg"],
            border_color="#374151",
            focused_border_color="#3b82f6"
        )
        def on_change_saude_sort(e):
            state["saude_sort"] = e.control.value
            render_saude()
        drop_sort.on_change = on_change_saude_sort
        
        filtros_row = ft.Row([
            ft.Icon(ft.icons.Icons.CALENDAR_MONTH_ROUNDED, color="#64748b", size=16),
            btn_prev_s, lbl_period_s, btn_next_s,
            ft.Container(width=8),
            btn_ano_s,
            btn_todos_s,
            ft.Container(expand=True),
            drop_sort
        ], spacing=2, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        cards_row = ft.Row(
            controls=[card_total, card_mes, card_qtd],
            spacing=15
        )

        
        config_buttons = []
        for s in saude_list:
            is_selected = (s[0] == active_saude[0])
            is_virtual = (s[0] == "geral")
            
            def make_click_saude(sid):
                return lambda e: [selected_trans_ids.clear(), state.update({"active_saude_id": sid, "saude_migration_mode": False}), render_saude()]
                
            config_buttons.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.icons.Icons.LOCAL_HOSPITAL_ROUNDED, color="#3b82f6" if is_selected else "#64748b", size=16),
                                ft.Column([
                                    ft.Text(s[1], size=12, color="white" if is_selected else get_colors()["text"], weight=ft.FontWeight.BOLD),
                                    ft.Text(s[2] or _t("Geral"), size=10, color="#cbd5e1" if is_selected else "#64748b")
                                ], spacing=2, tight=True, expand=True),
                            ], spacing=8),
                            expand=True,
                            on_click=make_click_saude(s[0])
                        ),
                        ft.Row([
                            ft.IconButton(ft.icons.Icons.EDIT_ROUNDED, icon_color="white" if is_selected else "#3b82f6", icon_size=14, on_click=lambda e, s_item=s: abrir_form_saude(e, s_item), tooltip=_t("Editar")),
                            ft.IconButton(ft.icons.Icons.DELETE_ROUNDED, icon_color="white" if is_selected else "#ef4444", icon_size=14, on_click=lambda e, sid=s[0]: abrir_excluir_saude(sid), tooltip=_t("Excluir")),
                        ], spacing=0, visible=not is_virtual)
                    ], spacing=8, expand=True),
                    bgcolor="#3b82f6" if is_selected else get_colors()["surface"],
                    border=ft.border.all(1, "#3b82f6" if is_selected else get_colors()["border"]),
                    border_radius=8,
                    padding=ft.Padding(10, 8, 10, 8),
                    width=260
                )
            )
            
        config_selector_panel = ft.Container(
            padding=20,
            bgcolor=get_colors()["surface"],
            border_radius=12,
            border=ft.border.all(1, get_colors()["border"]),
            content=ft.Column([
                ft.Text(_t("Itens de Saúde Cadastrados"), size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.Container(height=5),
                ft.Column(controls=config_buttons, spacing=8)
            ], spacing=10),
            width=300
        )
        
        def abrir_excluir_transacao(t_id):
            def confirmar_exclusao(e):
                success = db.deletar_transacao(t_id)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Lançamento excluído com sucesso!"), color="white"), bgcolor="#10b981")
                    page.pop_dialog()
                    render_saude()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao excluir!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
            dialog = ft.AlertDialog(
                title=ft.Text(_t("Excluir Lançamento?")),
                content=ft.Text(_t("Esta ação excluirá permanentemente esta transação do histórico e do saldo.")),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("EXCLUIR"), on_click=confirmar_exclusao, bgcolor="#ef4444", color="white")
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        # Map tid -> DataRow reference, so on_select_change can update in-place
        row_refs = {}

        row_refs_p = {}

        row_refs_s = {}
        row_map_saude = row_refs

        def make_on_select_changed(tid):
            def handler(e):
                is_selected = False
                if hasattr(e, "selected") and e.selected is not None:
                    is_selected = bool(e.selected)
                elif hasattr(e, "data") and e.data is not None:
                    is_selected = str(e.data).lower() in ("true", "1")
                else:
                    is_selected = tid not in selected_trans_ids
                
                if is_selected:
                    selected_trans_ids.add(tid)
                else:
                    selected_trans_ids.discard(tid)
                
                e.control.selected = is_selected
                e.control.update()
            return handler

        rows = []
        for t in filtered_trans:
            t_id, t_data, t_desc, t_valor, t_cat, t_tipo, t_part, t_tot_part, t_metodo, t_dono, t_band, t_divs, t_obs, t_val_real = t
            
            def make_edit_click(t_item):
                return lambda e: [state.update({"overlay_entity_type": "saude", "overlay_entity_id": active_saude[0]}), abrir_overlay("despesa", editing_trans_id=t_item[0])]
                
            def make_delete_click(tid):
                return lambda e: abrir_excluir_transacao(tid)
                
            row = ft.DataRow(
                    selected=(t_id in selected_trans_ids),
                    on_select_change=make_on_select_changed(t_id),
                    cells=[
                        ft.DataCell(ft.Text(t_data, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(t_desc, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(t_cat, color=get_colors()["text"])),
                        ft.DataCell(ft.Text(fmt(t_valor), color=get_colors()["text"], weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(t_metodo or "Outros", color=get_colors()["text"])),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(ft.icons.Icons.EDIT_ROUNDED, icon_color="#3b82f6", icon_size=18, tooltip=_t("Editar"), on_click=make_edit_click(t)),
                                ft.IconButton(ft.icons.Icons.DELETE_ROUNDED, icon_color="#ef4444", icon_size=18, tooltip=_t("Excluir"), on_click=make_delete_click(t_id)),
                            ], spacing=5)
                        )
                    ]
                )
            row_refs[t_id] = row
            rows.append(row)
            
        # Dropdown options for target saude
        other_saude = [s for s in saude_list if s[0] != active_saude[0]]
        options = [ft.dropdown.Option(key=str(os[0]), text=os[1]) for os in other_saude]
        options.append(ft.dropdown.Option(key="novo", text=_t("+ Novo Item")))
        
        drop_dest = ft.Dropdown(
            label=_t("Destino"),
            options=options,
            width=150,
            height=38,
            text_size=11,
            content_padding=ft.Padding(8, 2, 8, 2),
            bgcolor=get_colors()["bg"],
            border_color="#374151",
            focused_border_color="#3b82f6"
        )
        if options:
            drop_dest.value = options[0].key

        def confirmar_migracao(e):
            if not selected_trans_ids:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Selecione pelo menos um lançamento!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            dest_val = drop_dest.value
            if dest_val == "novo":
                def post_create_callback(new_sid):
                    for tid in selected_trans_ids:
                        db.atualizar_transacao_saude(tid, new_sid)
                    selected_trans_ids.clear()
                    state["saude_migration_mode"] = False
                    render_saude()
                    
                state["post_create_saude_callback"] = post_create_callback
                abrir_form_saude(e)
            else:
                target_id = None if dest_val == "geral" else int(dest_val)
                for tid in selected_trans_ids:
                    db.atualizar_transacao_saude(tid, target_id)
                selected_trans_ids.clear()
                state["saude_migration_mode"] = False
                render_saude()

        tabela_saude = ft.DataTable(
            show_checkbox_column=state.get("saude_migration_mode", False),
            columns=[
                ft.DataColumn(ft.Text(_t("Mês/Data"))),
                ft.DataColumn(ft.Text(_t("Descrição"))),
                ft.DataColumn(ft.Text(_t("Categoria"))),
                ft.DataColumn(ft.Text(_t("Valor"))),
                ft.DataColumn(ft.Text(_t("Método"))),
                ft.DataColumn(ft.Text(_t("Ações"))),
            ],
            rows=rows,
            border_radius=8,
            border=ft.border.all(0.5, get_colors()["border"]),
            heading_row_color=get_colors()["surface"],
            expand=True
        )
        tabela = tabela_saude  # alias for on_select_change closures
        
        def selecionar_todos_saude(e):
            all_ids = {t[0] for t in filtered_trans}
            if all_ids.issubset(selected_trans_ids):
                for tid in all_ids:
                    selected_trans_ids.discard(tid)
                    if tid in row_map_saude: row_map_saude[tid].selected = False
            else:
                for tid in all_ids:
                    selected_trans_ids.add(tid)
                    if tid in row_map_saude: row_map_saude[tid].selected = True
            tabela_saude.update()
        
        all_sel_saude = bool(filtered_trans) and {t[0] for t in filtered_trans}.issubset(selected_trans_ids)
        
        tabela_header_row = ft.Row([
            ft.Row([
                ft.Text(_t("Selecione as transações para migrar:"), size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.TextButton(
                    _t("Desmarcar Todos") if all_sel_saude else _t("Selecionar Todos"),
                    on_click=selecionar_todos_saude,
                    style=ft.ButtonStyle(color="#3b82f6", padding=ft.Padding(6, 2, 6, 2))
                ),
            ], spacing=8),
            ft.Row([
                drop_dest,
                ft.IconButton(ft.icons.Icons.CHECK_ROUNDED, icon_color="#10b981", tooltip=_t("Confirmar Migração"), on_click=confirmar_migracao),
                ft.IconButton(ft.icons.Icons.CLOSE_ROUNDED, icon_color="#ef4444", tooltip=_t("Cancelar"), on_click=lambda e: [selected_trans_ids.clear(), state.update({"saude_migration_mode": False}), render_saude()]),
            ], spacing=5)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN) if state.get("saude_migration_mode") else ft.Row([
            ft.Text(f"{_t('Gastos de')} {active_saude[1]}", size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            ft.Row([
                ft.ElevatedButton(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.MOVE_UP_ROUNDED, size=16, color="white"),
                        ft.Text(_t("MIGRAR PARA..."), size=11, color="white", weight=ft.FontWeight.BOLD)
                    ], spacing=5),
                    bgcolor="#3b82f6",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                    on_click=lambda e: [state.update({"saude_migration_mode": True}), render_saude()]
                ),
                ft.ElevatedButton(
                    content=ft.Row([
                        ft.Icon(ft.icons.Icons.ADD_ROUNDED, size=16, color="white"),
                        ft.Text(_t("NOVO GASTO"), size=11, color="white", weight=ft.FontWeight.BOLD)
                    ], spacing=5),
                    bgcolor="#10b981",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                    on_click=lambda e: [state.update({"overlay_entity_type": "saude", "overlay_entity_id": active_saude[0]}), abrir_overlay("despesa")]
                )
            ], spacing=10)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        tabela_container = ft.Container(
            padding=20,
            bgcolor=get_colors()["surface"],
            border_radius=12,
            border=ft.border.all(1, get_colors()["border"]),
            expand=True,
            content=ft.Column([
                tabela_header_row,
                filtros_row,
                ft.Container(height=5),
                ft.Row([tabela], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
            ], spacing=10)
        )
        
        dashboard_layout = ft.Column(
            expand=True,
            controls=[
                tab_header,
                ft.Container(height=5),
                cards_row,
                ft.Container(height=10),
                ft.Row([
                    config_selector_panel,
                    tabela_container
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START, expand=True)
            ],
            spacing=10,
            scroll=ft.ScrollMode.ADAPTIVE
        )
        
        page.floating_action_button = None
        body.content = dashboard_layout
        page.update()

    def abrir_form_transacao_entidade(tipo_entidade, entidade_id, transacao_to_edit=None):
        import datetime
        now = datetime.datetime.now()
        
        pai_nome = "VEÍCULO" if tipo_entidade == "veiculo" else ("PET" if tipo_entidade == "pet" else "SAÚDE")
        subcats = db.get_subcategorias_por_pai(pai_nome)
        cat_options = [ft.dropdown.Option(str(sc[0]), sc[1]) for sc in subcats]
        
        if not cat_options:
            parent_id = db.get_categoria_id_by_nome(pai_nome)
            if parent_id:
                cat_options = [ft.dropdown.Option(str(parent_id), pai_nome.title())]
        
        txt_desc = ft.TextField(
            label=_t("Descrição"),
            value=transacao_to_edit[2] if transacao_to_edit else "",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        txt_valor = ft.TextField(
            label=_t("Valor (R$)"),
            value=f"{transacao_to_edit[3]:.2f}".replace(".", ",") if transacao_to_edit else "",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        txt_data = ft.TextField(
            label=_t("Data (DD/MM/AAAA)"),
            value=transacao_to_edit[1] if transacao_to_edit else now.strftime("%d/%m/%Y"),
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        drop_cat = ft.Dropdown(
            label=_t("Categoria"),
            options=cat_options,
            value=str(transacao_to_edit[4]) if transacao_to_edit and any(str(opt.key) == str(transacao_to_edit[4]) for opt in cat_options) else (cat_options[0].key if cat_options else None),
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        drop_metodo = ft.Dropdown(
            label=_t("Método de Pagamento"),
            options=[
                ft.dropdown.Option("Boleto", _t("Boleto")),
                ft.dropdown.Option("Pix", _t("Pix")),
                ft.dropdown.Option("Dinheiro", _t("Dinheiro")),
                ft.dropdown.Option("Cartão", _t("Cartão")),
                ft.dropdown.Option("Outros", _t("Outros")),
            ],
            value=transacao_to_edit[8] if transacao_to_edit else "Boleto",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
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
            label=_t("Selecione o Cartão"),
            border_color="#475569",
            focused_border_color="#2563eb",
            text_style=ft.TextStyle(color=get_colors()["text"], size=12),
            label_style=ft.TextStyle(size=11),
            height=48,
            bgcolor=get_colors()["bg"],
            options=card_options
        )
        
        if transacao_to_edit and transacao_to_edit[8] == "Cartão":
            band = transacao_to_edit[10] or ""
            dono = transacao_to_edit[9] or ""
            key_val = f"{band}|{dono}"
            if any(opt.key == key_val for opt in card_options):
                drop_cartao.value = key_val
                
        cartao_container = ft.Container(
            content=drop_cartao,
            visible=drop_metodo.value == "Cartão"
        )
        
        def on_metodo_change(e):
            cartao_container.visible = (drop_metodo.value == "Cartão")
            cartao_container.update()
            
        drop_metodo.on_change = on_metodo_change
        
        txt_obs = ft.TextField(
            label=_t("Observação"),
            value=transacao_to_edit[12] if transacao_to_edit else "",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        def salvar_transacao(e):
            desc = txt_desc.value.strip()
            val_str = txt_valor.value.strip().replace(",", ".")
            data_str = txt_data.value.strip()
            cat_id_str = drop_cat.value
            metodo = drop_metodo.value
            obs = txt_obs.value.strip()
            
            if not desc or not val_str or not data_str or not cat_id_str:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Preencha todos os campos obrigatórios!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            try:
                valor = float(val_str)
                if valor <= 0: raise ValueError()
            except:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Digite um valor numérico válido maior que zero!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            try:
                datetime.datetime.strptime(data_str, "%d/%m/%Y")
            except:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Data inválida! Use o formato DD/MM/AAAA"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            bandeira = ""
            dono = ""
            if metodo == "Cartão" and drop_cartao.value:
                parts = drop_cartao.value.split("|")
                if len(parts) == 2:
                    bandeira, dono = parts[0], parts[1]
            
            pilar = "Despesa Fixa" if pai_nome == "SAÚDE" else "Despesa Variável"
            cat_id = int(cat_id_str)
            
            v_id = entidade_id if tipo_entidade == "veiculo" else None
            p_id = entidade_id if tipo_entidade == "pet" else None
            s_id = entidade_id if tipo_entidade == "saude" else None
            
            if transacao_to_edit:
                success, msg = db.atualizar_transacao(
                    transacao_id=transacao_to_edit[0],
                    categoria_id=cat_id,
                    descricao=desc,
                    data=data_str,
                    valor_total=valor,
                    tipo_transacao=pilar,
                    metodo=metodo,
                    bandeira=bandeira,
                    dono=dono,
                    observacao=obs,
                    divisoes={"Eu": valor},
                    veiculo_id=v_id,
                    pet_id=p_id,
                    saude_id=s_id,
                    keep_entity_links=False
                )
            else:
                success, msg = db.inserir_transacao(
                    conta_id=None,
                    categoria_id=cat_id,
                    descricao=desc,
                    data_ini=data_str,
                    valor_total=valor,
                    tipo_transacao=pilar,
                    metodo=metodo,
                    parcelas=1,
                    bandeira=bandeira,
                    dono=dono,
                    recorrencia=None,
                    divisoes={"Eu": valor},
                    observacao=obs,
                    veiculo_id=v_id,
                    pet_id=p_id,
                    saude_id=s_id
                )
                
            if success:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Lançamento salvo com sucesso!"), color="white"), bgcolor="#10b981")
                page.pop_dialog()
                if tipo_entidade == "veiculo":
                    render_veiculos()
                elif tipo_entidade == "pet":
                    render_pets()
                else:
                    render_saude()
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao salvar:')} {msg}", color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(_t("Editar Lançamento") if transacao_to_edit else _t("Novo Lançamento"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=ft.Column(
                controls=[
                    txt_desc,
                    txt_valor,
                    txt_data,
                    drop_cat,
                    drop_metodo,
                    cartao_container,
                    txt_obs
                ],
                spacing=10,
                scroll=ft.ScrollMode.ADAPTIVE
            ),
            bgcolor=get_colors()["surface"],
            actions=[
                ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                ft.ElevatedButton(_t("SALVAR"), on_click=salvar_transacao, bgcolor="#3b82f6", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    def abrir_form_config_recorrencia(e, config_to_edit=None):
        txt_nome = ft.TextField(
            label=_t("Nome da Recorrência"),
            value=config_to_edit[1] if config_to_edit else "",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        txt_valor = ft.TextField(
            label=_t("Valor Padrão (R$)"),
            value=f"{config_to_edit[4]:.2f}".replace(".", ",") if config_to_edit else "",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12,
            on_change=lambda e: update_sharing_labels()
        )
        
        txt_obs = ft.TextField(
            label=_t("Observação"),
            value=config_to_edit[7] if config_to_edit else "",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        drop_tipo = ft.Dropdown(
            label=_t("Tipo"),
            options=[
                ft.dropdown.Option("Despesa Fixa", _t("Despesa Fixa")),
                ft.dropdown.Option("Despesa Variável", _t("Despesa Variável")),
                ft.dropdown.Option("Receita Fixa", _t("Receita Fixa")),
                ft.dropdown.Option("Receita Variável", _t("Receita Variável")),
            ],
            value=config_to_edit[2] if config_to_edit else "Despesa Fixa",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        drop_cat = ft.Dropdown(
            label=_t("Categoria"),
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        drop_sub = ft.Dropdown(
            label=_t("Subcategoria"),
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        drop_metodo = ft.Dropdown(
            label=_t("Método de Pagamento"),
            options=[
                ft.dropdown.Option("Boleto", _t("Boleto")),
                ft.dropdown.Option("Pix", _t("Pix")),
                ft.dropdown.Option("Dinheiro", _t("Dinheiro")),
                ft.dropdown.Option("Cartão", _t("Cartão de Crédito")),
                ft.dropdown.Option("Outros", _t("Outros")),
            ],
            value=config_to_edit[6] if config_to_edit else "Boleto",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
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
            label=_t("Selecione o Cartão"),
            border_color="#475569",
            focused_border_color="#2563eb",
            text_style=ft.TextStyle(color=get_colors()["text"], size=12),
            label_style=ft.TextStyle(size=11),
            height=48,
            expand=True,
            bgcolor=get_colors()["bg"],
            options=card_options
        )
        
        if config_to_edit and config_to_edit[6] == "Cartão":
            band = config_to_edit[10] or ""
            dono = config_to_edit[11] or ""
            key_val = f"{band}|{dono}"
            if any(opt.key == key_val for opt in card_options):
                drop_cartao.value = key_val
            elif card_options:
                drop_cartao.value = card_options[0].key
        elif card_options:
            drop_cartao.value = card_options[0].key

        cartao_container = ft.Container(
            visible=(config_to_edit[6] == "Cartão") if config_to_edit else False,
            content=ft.Column(
                controls=[
                    ft.Text(_t("💳 Detalhes do Cartão"), size=12, weight=ft.FontWeight.BOLD, color="#3b82f6"),
                    ft.Row(
                        controls=[
                            ft.Container(expand=True, content=drop_cartao),
                            ft.Container(width=15)
                        ]
                    )
                ],
                spacing=5
            )
        )

        chk_compartilhar = ft.Checkbox(
            label=_t("Dividir despesa com a família"), 
            value=False, 
            label_style=ft.TextStyle(size=12, color=get_colors()["text"]),
        )
        
        existing_divs = db.get_divisions_recorrencia(config_to_edit[0]) if config_to_edit else {}
        if existing_divs:
            chk_compartilhar.value = True

        perfis = db.get_perfis() if hasattr(db, 'get_perfis') else ["Eu"]
        if "Outro..." not in perfis: perfis.append("Outro...")

        custom_name = ""
        if existing_divs:
            for name in existing_divs.keys():
                if name not in perfis and name != "Eu":
                    custom_name = name
                    break

        member_checks = []
        member_widgets = []
        for p in perfis:
            is_checked = False
            if existing_divs:
                if p == "Outro..." and custom_name:
                    is_checked = True
                else:
                    is_checked = (p in existing_divs)
            else:
                is_checked = (p == "Eu")
            
            cb = ft.Checkbox(
                value=is_checked,
            )
            cb.data = p
            member_checks.append(cb)
            
            widget = ft.Container(
                width=95,
                content=ft.Row(
                    spacing=2,
                    controls=[
                        cb,
                        ft.Text(p, size=12, color=get_colors()["text"], weight=ft.FontWeight.W_500)
                    ]
                )
            )
            member_widgets.append(widget)

        drop_div_tipo = ft.Dropdown(
            label=_t("Tipo de Divisão"),
            border_color="#475569",
            focused_border_color="#10b981",
            text_style=ft.TextStyle(color=get_colors()["text"], size=12),
            label_style=ft.TextStyle(size=11),
            height=48,
            expand=True,
            bgcolor=get_colors()["bg"],
            options=[
                ft.dropdown.Option(key="Igualitária", text=_t("Igualitária")),
                ft.dropdown.Option(key="Individual", text=_t("Individual"))
            ],
            value="Igualitária"
        )
        
        if existing_divs:
            vals = list(existing_divs.values())
            if len(set(vals)) > 1:
                drop_div_tipo.value = "Individual"

        col_inputs = ft.Column(spacing=8)
        inputs_individuais = {}
        lbl_val_status = ft.Text(size=11, weight=ft.FontWeight.BOLD)
        
        txt_novo_perfil = ft.TextField(
            label=_t("Nome do novo membro"), 
            border_color="#475569", 
            focused_border_color="#10b981", 
            text_style=ft.TextStyle(color=get_colors()["text"], size=12), 
            label_style=ft.TextStyle(size=11),
            height=44,
            expand=True,
            content_padding=ft.Padding(10, 5, 10, 5),
            bgcolor=get_colors()["bg"], 
            visible=False,
        )
        txt_novo_perfil_row = ft.Row([ft.Container(expand=True, content=txt_novo_perfil), ft.Container(width=15)], visible=False)

        if custom_name:
            txt_novo_perfil.value = custom_name
            txt_novo_perfil.visible = True
            txt_novo_perfil_row.visible = True

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
                    if existing_divs:
                        key_p = custom_name if p == "Outro..." else p
                        if key_p in existing_divs:
                            cota_valor = f"{existing_divs[key_p]:.2f}".replace(".", ",")

                    tf = ft.TextField(
                        label=f"Valor para {nome_final}", 
                        value=cota_valor, 
                        border_color="#475569", focused_border_color="#10b981", 
                        text_style=ft.TextStyle(color=get_colors()["text"], size=12), 
                        label_style=ft.TextStyle(size=11),
                        height=44,
                        expand=True,
                        content_padding=ft.Padding(10, 5, 10, 5),
                        bgcolor=get_colors()["bg"], 
                        on_change=lambda e: update_sharing_labels()
                    )
                    inputs_individuais[p] = tf
                    temp_row_controls.append(ft.Container(expand=True, content=tf))

                for i in range(0, len(temp_row_controls), 2):
                    row_slice = temp_row_controls[i:i+2]
                    if len(row_slice) == 1:
                        row_slice.append(ft.Container(expand=True))
                    col_inputs.controls.append(ft.Row(controls=row_slice + [ft.Container(width=15)]))
            
            update_sharing_labels()
            page.update()

        def update_sharing_labels():
            try:
                val_total = float(txt_valor.value.strip().replace(".", "").replace(",", "."))
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
                    try:
                        soma += float(tf.value.replace(",", "."))
                    except:
                        pass
                
                diff = val_total - soma
                if abs(diff) < 0.01:
                    lbl_val_status.value = "✓ Divisão completa e batida!"
                    lbl_val_status.color = "#10b981"
                elif diff > 0:
                    lbl_val_status.value = f"Restam R$ {diff:,.2f} para alocar".replace(",", ".")
                    lbl_val_status.color = "#f59e0b"
                else:
                    lbl_val_status.value = f"Excedeu em R$ {abs(diff):,.2f}".replace(",", ".")
                    lbl_val_status.color = "#ef4444"
            page.update()
            
        for cb in member_checks:
            cb.on_change = lambda e: rebuild_sharing_inputs()
        txt_novo_perfil.on_change = lambda e: update_sharing_labels()
        drop_div_tipo.on_select = lambda e: rebuild_sharing_inputs()
        
        def toggle_sharing_fields():
            sharing_container.visible = chk_compartilhar.value
            rebuild_sharing_inputs()
            
        chk_compartilhar.on_change = lambda e: toggle_sharing_fields()

        sharing_container = ft.Container(
            visible=chk_compartilhar.value,
            content=ft.Column(
                controls=[
                    ft.Text(_t("👥 Divisão de Valores (Rateio)"), size=12, weight=ft.FontWeight.BOLD, color="#10b981"),
                    ft.Row(
                        controls=member_widgets,
                        wrap=True,
                        spacing=10
                    ),
                    txt_novo_perfil_row,
                    ft.Row(
                        controls=[
                            ft.Container(expand=True, content=drop_div_tipo),
                            ft.Container(width=15)
                        ]
                    ),
                    col_inputs,
                    lbl_val_status
                ],
                spacing=8
            )
        )

        txt_meses_inicial = ft.TextField(
            label=_t("Programar quantos meses?"),
            value="12",
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        import datetime
        now = datetime.datetime.now()
        txt_data_inicial = ft.TextField(
            label=_t("A partir de (DD/MM/AAAA)"),
            value=now.strftime("01/%m/%Y"),
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        lote_container = ft.Container(
            visible=(config_to_edit is None),
            content=ft.Column(
                controls=[
                    ft.Text(_t("📅 Programação Inicial"), size=12, weight=ft.FontWeight.BOLD, color="#fb923c"),
                    ft.Row(
                        controls=[
                            ft.Container(expand=1, content=txt_meses_inicial),
                            ft.Container(expand=1, content=txt_data_inicial),
                            ft.Container(width=15)
                        ],
                        spacing=10
                    )
                ],
                spacing=5
            )
        )

        def on_tipo_change(e):
            tipo = drop_tipo.value
            cats = categorias_por_pilar.get(tipo, {})
            drop_cat.options = [ft.dropdown.Option(key=str(cid), text=info["nome"]) for cid, info in cats.items()]
            if cats:
                first_cid = list(cats.keys())[0]
                drop_cat.value = str(first_cid)
                update_subcategories(first_cid)
            else:
                drop_cat.value = None
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"
            page.update()

        def on_cat_change(e):
            if drop_cat.value:
                update_subcategories(int(drop_cat.value))
            else:
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"
            page.update()

        def update_subcategories(parent_cid):
            tipo = drop_tipo.value
            cats = categorias_por_pilar.get(tipo, {})
            cat_info = cats.get(parent_cid, {})
            subs = cat_info.get("subs", [])
            if subs:
                drop_sub.options = [ft.dropdown.Option(key=str(sid), text=snome) for sid, snome in subs]
                drop_sub.value = str(subs[0][0])
            else:
                drop_sub.options = [ft.dropdown.Option(key="Geral", text="Geral")]
                drop_sub.value = "Geral"

        drop_tipo.on_select = on_tipo_change
        drop_cat.on_select = on_cat_change
        drop_metodo.on_select = lambda e: toggle_metodo_fields()
        
        def toggle_metodo_fields():
            cartao_container.visible = (drop_metodo.value == "Cartão")
            page.update()

        tipo_inicial = drop_tipo.value
        cats_iniciais = categorias_por_pilar.get(tipo_inicial, {})
        drop_cat.options = [ft.dropdown.Option(key=str(cid), text=info["nome"]) for cid, info in cats_iniciais.items()]
        
        if config_to_edit:
            categoria_ativa = config_to_edit[3]
            parent_id = None
            for cid, info in cats_iniciais.items():
                if cid == categoria_ativa:
                    parent_id = cid
                    break
                if categoria_ativa in [s[0] for s in info["subs"]]:
                    parent_id = cid
                    break
            
            if parent_id:
                drop_cat.value = str(parent_id)
                update_subcategories(parent_id)
                if parent_id != categoria_ativa:
                    drop_sub.value = str(categoria_ativa)
            elif cats_iniciais:
                first_cid = list(cats_iniciais.keys())[0]
                drop_cat.value = str(first_cid)
                update_subcategories(first_cid)
        else:
            if cats_iniciais:
                first_cid = list(cats_iniciais.keys())[0]
                drop_cat.value = str(first_cid)
                update_subcategories(first_cid)

        def salvar_config(e):
            nome = txt_nome.value.strip()
            tipo = drop_tipo.value
            cat_val = drop_cat.value
            sub_val = drop_sub.value
            valor_str = txt_valor.value.strip().replace(".", "").replace(",", ".")
            metodo = drop_metodo.value
            obs = txt_obs.value.strip()
            
            if not nome:
                page.snack_bar = ft.SnackBar(ft.Text(_t("O nome da recorrência é obrigatório!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            try:
                valor = float(valor_str)
                if valor <= 0:
                    raise ValueError()
            except:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Digite um valor numérico válido maior que zero!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            categoria_final_id = int(sub_val) if (sub_val and sub_val != "Geral") else int(cat_val)
            
            bandeira = ""
            dono = ""
            if metodo == "Cartão":
                if drop_cartao.value:
                    parts = drop_cartao.value.split("|")
                    if len(parts) == 2:
                        bandeira, dono = parts[0], parts[1]
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Selecione o cartão de crédito!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return

            divisoes = {}
            if chk_compartilhar.value:
                selected = [chk.data for chk in member_checks if chk.value]
                if not selected:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Selecione pelo menos uma pessoa para a divisão!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return
                
                has_outro = "Outro..." in selected
                nome_outro = txt_novo_perfil.value.strip()
                if has_outro and not nome_outro:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Digite o nome do novo membro!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return
                
                if drop_div_tipo.value == "Igualitária":
                    share_val = valor / len(selected)
                    for p in selected:
                        p_name = nome_outro if p == "Outro..." else p
                        divisoes[p_name] = share_val
                else:
                    soma = 0.0
                    for p in selected:
                        tf = inputs_individuais.get(p)
                        if not tf:
                            continue
                        try:
                            val_p = float(tf.value.replace(",", "."))
                        except:
                            val_p = 0.0
                        p_name = nome_outro if p == "Outro..." else p
                        divisoes[p_name] = val_p
                        soma += val_p
                    
                    if abs(soma - valor) > 0.02:
                        page.snack_bar = ft.SnackBar(ft.Text(_t("A soma das partes deve ser igual ao valor total!"), color="white"), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return
            else:
                divisoes = None

            n_meses = 0
            start_date = ""
            if not config_to_edit:
                try:
                    n_meses_str = txt_meses_inicial.value.strip()
                    n_meses = int(n_meses_str) if n_meses_str else 0
                    if n_meses < 0:
                        raise ValueError()
                except:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Digite uma quantidade de meses válida!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return
                
                if n_meses > 0:
                    start_date = txt_data_inicial.value.strip()
                    try:
                        datetime.datetime.strptime(start_date, "%d/%m/%Y")
                    except:
                        page.snack_bar = ft.SnackBar(ft.Text(_t("Data inicial inválida! Use DD/MM/AAAA"), color="white"), bgcolor="#ef4444")
                        page.snack_bar.open = True
                        page.update()
                        return

            if config_to_edit:
                success, msg = db.update_config_recorrencia(
                    config_to_edit[0], nome, tipo, categoria_final_id, valor, metodo, obs, bandeira, dono, divisoes
                )
            else:
                success, msg = db.add_config_recorrencia(
                    nome, tipo, categoria_final_id, valor, metodo, obs, state["perfil"], bandeira, dono, divisoes
                )
                if success:
                    state["active_recurrence_id"] = msg
                    if n_meses > 0:
                        db.gerar_transacoes_recorrentes(msg, n_meses, start_date, state["perfil"])

            if success:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Configuração salva com sucesso!"), color="white"), bgcolor="#10b981")
                page.pop_dialog()
                render_recorrencias()
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao salvar:')} {msg}", color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()

        form_content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_t("📝 Informações Básicas"), size=12, weight=ft.FontWeight.BOLD, color="#3b82f6"),
                    txt_nome,
                    txt_valor,
                    drop_tipo,
                    drop_cat,
                    drop_sub,
                    drop_metodo,
                    cartao_container,
                    chk_compartilhar,
                    sharing_container,
                    lote_container,
                    txt_obs
                ],
                spacing=10,
                scroll=ft.ScrollMode.ADAPTIVE
            ),
            width=460,
            height=480
        )
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(_t("Editar Recorrência") if config_to_edit else _t("Adicionar Lançamento Recorrente"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=form_content,
            bgcolor=get_colors()["surface"],
            actions=[
                ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                ft.ElevatedButton(_t("SALVAR"), on_click=salvar_config, bgcolor="#3b82f6", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)
        
        if existing_divs:
            rebuild_sharing_inputs()

    def abrir_edit_ocorrencia(occ_id, val, date):
        txt_new_val = ft.TextField(
            label=_t("Novo Valor (R$)"),
            value=str(val),
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        choice_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="single", label=_t("Alterar apenas este mês")),
                ft.Radio(value="future", label=_t("Alterar deste mês em diante (Alterar padrão)")),
            ]),
            value="single"
        )
        
        def salvar_edicao(e):
            val_str = txt_new_val.value.strip().replace(",", ".")
            try:
                new_val = float(val_str)
                if new_val <= 0:
                    raise ValueError()
            except:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Digite um valor numérico válido!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            alterar_futuros = (choice_group.value == "future")
            success = db.atualizar_transacao_recorrente(occ_id, state["active_recurrence_id"], new_val, alterar_futuros)
            if success:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Operação atualizada com sucesso!"), color="white"), bgcolor="#10b981")
                page.pop_dialog()
                render_recorrencias()
            else:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao atualizar!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{_t('Editar Ocorrência')} ({date})", size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=ft.Column(
                controls=[
                    txt_new_val,
                    ft.Container(height=10),
                    choice_group
                ],
                tight=True,
                spacing=10
            ),
            bgcolor=get_colors()["surface"],
            actions=[
                ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                ft.ElevatedButton(_t("SALVAR"), on_click=salvar_edicao, bgcolor="#3b82f6", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    def abrir_delete_ocorrencia(occ_id, date):
        choice_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="single", label=_t("Excluir apenas este mês")),
                ft.Radio(value="future", label=_t("Excluir deste mês em diante")),
            ]),
            value="single"
        )
        
        def confirmar_exclusao(e):
            excluir_futuros = (choice_group.value == "future")
            success = db.excluir_transacao_recorrente(occ_id, state["active_recurrence_id"], excluir_futuros)
            if success:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Ocorrência excluída com sucesso!"), color="white"), bgcolor="#10b981")
                page.pop_dialog()
                render_recorrencias()
            else:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao excluir!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(_t("Confirmar Exclusão"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=ft.Column(
                controls=[
                    ft.Text(f"{_t('Tem certeza que deseja excluir a ocorrência de')} {date}?", color=get_colors()["text"]),
                    ft.Container(height=10),
                    choice_group
                ],
                tight=True,
                spacing=10
            ),
            bgcolor=get_colors()["surface"],
            actions=[
                ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                ft.ElevatedButton(_t("EXCLUIR"), on_click=confirmar_exclusao, bgcolor="#ef4444", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    def abrir_delete_config(config_id):
        def confirmar_exclusao_config(e):
            success, msg = db.delete_config_recorrencia(config_id)
            if success:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Configuração excluída com sucesso!"), color="white"), bgcolor="#10b981")
                page.pop_dialog()
                state["active_recurrence_id"] = None
                render_recorrencias()
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao excluir:')} {msg}", color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(_t("Confirmar Exclusão de Configuração"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=ft.Text(_t("Deseja excluir esta configuração de recorrência? As transações existentes não serão excluídas."), color=get_colors()["text"]),
            bgcolor=get_colors()["surface"],
            actions=[
                ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                ft.ElevatedButton(_t("EXCLUIR CONFIGURAÇÃO"), on_click=confirmar_exclusao_config, bgcolor="#ef4444", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    def render_configuracoes():
        # Desativa o floating action button se houver
        page.floating_action_button = None
        
        # Obter perfis e categorias
        perfis = db.get_perfis()
        categorias = db.get_categorias()
        
        # Estado do tab interno das configurações (padrão: banco_dados)
        active_config_tab = state.get("config_active_tab", "banco_dados")
        
        def select_config_tab(tid):
            state["config_active_tab"] = tid
            render_configuracoes()
            
        # 1. TÍTULO E SUBTÍTULO DA TELA
        header_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Configurações do Sistema", size=22, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Text("Gerencie perfis, categorias, backups e preferências da interface", size=13, color="#64748b")
                    ]
                )
            ]
        )
        
        # 2. DEFINIÇÃO E COMPILAÇÃO DE ELEMENTOS COMUNS
        # 2.1 PREFERÊNCIAS E MODO SANDBOX (DEPRECIADO)
        is_sandbox = "sandbox_financas.db" in db.db_name
        
        # Manipuladores de alteração de tema e idioma
        def on_change_theme(e):
            val = e.control.value
            db.set_preferencia("theme_mode", val)
            page.theme_mode = ft.ThemeMode.LIGHT if val == "light" else ft.ThemeMode.DARK
            
            # Atualiza cores da página e da barra lateral imediatamente
            colors = get_colors()
            page.bgcolor = colors["bg"]
            sidebar.bgcolor = colors["sidebar"]
            
            # Recarrega a aba ativa imediatamente para re-renderizar todos os painéis com as novas cores
            active_tab = state.get("active_tab", "dashboard")
            if active_tab == "dashboard":
                render_dashboard()
            elif active_tab == "investimentos":
                render_investimentos()
            elif active_tab == "cartoes":
                render_cartoes()
            elif active_tab == "transacoes":
                render_transacoes()
            elif active_tab == "financiamentos":
                render_financiamentos()
            elif active_tab == "configuracoes":
                render_configuracoes()
            
        def on_change_lang(e):
            val = e.control.value
            db.set_preferencia("language", val)
            state["language"] = val
            atualizar_textos_globais()
            page.snack_bar = ft.SnackBar(
                content=ft.Text(_t("Idioma alterado com sucesso! Recarregando..."), color="white"),
                bgcolor="#10b981"
            )
            page.snack_bar.open = True
            page.update()
            
            # Recarrega a aba ativa imediatamente para aplicar a tradução em toda a tela
            active_tab = state.get("active_tab", "dashboard")
            if active_tab == "dashboard":
                render_dashboard()
            elif active_tab == "investimentos":
                render_investimentos()
            elif active_tab == "cartoes":
                render_cartoes()
            elif active_tab == "transacoes":
                render_transacoes()
            elif active_tab == "financiamentos":
                render_financiamentos()
            elif active_tab == "configuracoes":
                render_configuracoes()

        dropdown_theme = ft.Dropdown(
            label=_t("Tema do Aplicativo"),
            value=db.get_preferencia("theme_mode", "dark"),
            on_select=on_change_theme,
            options=[
                ft.dropdown.Option("dark", _t("Tema Escuro")),
                ft.dropdown.Option("light", _t("Tema Claro"))
            ],
            width=200,
            border_color="#475569",
            focused_border_color="#3b82f6",
            text_style=ft.TextStyle(color=get_colors()["text"], size=12),
            label_style=ft.TextStyle(color=get_colors()["text"], size=12),
            bgcolor=get_colors()["bg"]
        )
        
        dropdown_lang = ft.Dropdown(
            label=_t("Idioma"),
            value=state.get("language", "pt"),
            on_select=on_change_lang,
            options=[
                ft.dropdown.Option("pt", _t("Português")),
                ft.dropdown.Option("en", _t("Inglês")),
                ft.dropdown.Option("de", _t("Alemão")),
                ft.dropdown.Option("es", _t("Espanhol"))
            ],
            width=200,
            border_color="#475569",
            focused_border_color="#3b82f6",
            text_style=ft.TextStyle(color=get_colors()["text"], size=12),
            label_style=ft.TextStyle(color=get_colors()["text"], size=12),
            bgcolor=get_colors()["bg"]
        )

        months_options = [ft.dropdown.Option("", _t("Desde o início"))]
        for m in ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]:
            months_options.append(ft.dropdown.Option(m, _t(m)))
            
        current_year = datetime.datetime.now().year
        years_options = [ft.dropdown.Option("", _t("Desde o início"))]
        for y in range(current_year - 5, current_year + 10):
            years_options.append(ft.dropdown.Option(str(y), str(y)))

        def on_change_start_month(e):
            val = e.control.value
            db.set_preferencia("saldo_acumulado_inicio_mes", val)
            page.snack_bar = ft.SnackBar(
                content=ft.Text(_t("Mês de início do saldo acumulado atualizado!"), color=get_colors()["text"]),
                bgcolor="#10b981"
            )
            page.snack_bar.open = True
            page.update()

        def on_change_start_year(e):
            val = e.control.value
            db.set_preferencia("saldo_acumulado_inicio_ano", val)
            page.snack_bar = ft.SnackBar(
                content=ft.Text(_t("Ano de início do saldo acumulado atualizado!"), color=get_colors()["text"]),
                bgcolor="#10b981"
            )
            page.snack_bar.open = True
            page.update()

        dropdown_start_mes = ft.Dropdown(
            label=_t("Mês Inicial"),
            value=db.get_preferencia("saldo_acumulado_inicio_mes", ""),
            on_select=on_change_start_month,
            options=months_options,
            width=200,
            border_color="#475569",
            focused_border_color="#3b82f6",
            text_style=ft.TextStyle(color=get_colors()["text"], size=12),
            label_style=ft.TextStyle(color=get_colors()["text"], size=12),
            bgcolor=get_colors()["bg"]
        )

        dropdown_start_ano = ft.Dropdown(
            label=_t("Ano Inicial"),
            value=db.get_preferencia("saldo_acumulado_inicio_ano", ""),
            on_select=on_change_start_year,
            options=years_options,
            width=200,
            border_color="#475569",
            focused_border_color="#3b82f6",
            text_style=ft.TextStyle(color=get_colors()["text"], size=12),
            label_style=ft.TextStyle(color=get_colors()["text"], size=12),
            bgcolor=get_colors()["bg"]
        )

        def on_change_start_value(e):
            val_str = (e.control.value or "").strip().replace(".", "").replace(",", ".")
            try:
                val = float(val_str) if val_str else 0.0
                db.set_preferencia("saldo_acumulado_inicio_valor", val)
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(_t("Saldo inicial atualizado com sucesso!"), color=get_colors()["text"]),
                    bgcolor="#10b981"
                )
            except ValueError:
                page.snack_bar = ft.SnackBar(
                    content=ft.Text(_t("Por favor, digite um valor numérico válido!"), color=get_colors()["text"]),
                    bgcolor="#ef4444"
                )
            page.snack_bar.open = True
            page.update()

        try:
            start_val_pref = float(db.get_preferencia("saldo_acumulado_inicio_valor", "0.0"))
        except Exception:
            start_val_pref = 0.0

        txt_start_value = ft.TextField(
            label=_t("Saldo Inicial"),
            value=f"{start_val_pref:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            on_submit=on_change_start_value,
            on_blur=on_change_start_value,
            width=200,
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color=get_colors()["text"], size=12),
            text_style=ft.TextStyle(color=get_colors()["text"], size=12),
            bgcolor=get_colors()["bg"],
            height=48,
            content_padding=ft.Padding(10, 5, 10, 5)
        )
        
        def run_db_export(e):
            import tkinter as tk
            from tkinter import filedialog
            
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            
            base_dir_backup = os.path.dirname(os.path.abspath(original_prod_path))
            initial_dir = os.path.join(base_dir_backup, "backups")
            os.makedirs(initial_dir, exist_ok=True)
            default_backup_name = f"manual_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            
            path = filedialog.asksaveasfilename(
                initialfile=default_backup_name,
                initialdir=initial_dir,
                defaultextension=".db",
                filetypes=[("SQLite Database", "*.db"), ("Todos os Arquivos", "*.*")],
                title="Salvar Backup do Banco de Dados"
            )
            root.destroy()
            
            if not path:
                return
                
            success, msg = db.export_database(path)
            if success:
                page.snack_bar = ft.SnackBar(content=ft.Text("Banco de dados exportado com sucesso!", color=get_colors()["text"]), bgcolor="#10b981")
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Erro ao exportar: {msg}", color=get_colors()["text"]), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()
            
        btn_export = ft.ElevatedButton(
            content="EXPORTAR BACKUP",
            color="white",
            bgcolor="#3b82f6",
            height=40,
            on_click=run_db_export,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
        )
        
        # 2.3 CADASTRO DE PERFIL
        txt_new_profile = ft.TextField(
            label=_t("Nome do Novo Perfil"),
            hint_text=_t("Ex: Filho, Cônjuge"),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"],
            height=48,
            content_padding=ft.Padding(10, 5, 10, 5),
            text_size=11
        )
        
        def run_add_profile(e):
            nome = (txt_new_profile.value or "").strip()
            if not nome:
                page.snack_bar = ft.SnackBar(content=ft.Text(_t("Por favor, preencha o nome do perfil!"), color=get_colors()["text"]), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
            
            success, msg = db.adicionar_usuario(nome)
            if success:
                page.snack_bar = ft.SnackBar(content=ft.Text(_t("Perfil cadastrado com sucesso!"), color=get_colors()["text"]), bgcolor="#10b981")
                txt_new_profile.value = ""
                render_configuracoes()
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro:')} {msg}", color=get_colors()["text"]), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()
            
        btn_add_profile = ft.ElevatedButton(
            content=_t("CADASTRAR PERFIL"),
            color="white",
            bgcolor="#3b82f6",
            height=40,
            on_click=run_add_profile,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
        )
        
        def run_delete_profile(nome):
            success, msg = db.excluir_usuario(nome)
            if success:
                page.snack_bar = ft.SnackBar(content=ft.Text(_t("Perfil excluído com sucesso!"), color=get_colors()["text"]), bgcolor="#10b981")
                render_configuracoes()
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro:')} {msg}", color=get_colors()["text"]), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()
            
        profiles_rows = []
        for p in perfis:
            is_eu = (p == "Eu")
            profiles_rows.append(
                ft.Container(
                    bgcolor=get_colors()["bg"],
                    border=ft.border.Border(
                        top=ft.border.BorderSide(1, "#334155" if is_eu else "#1e293b"),
                        bottom=ft.border.BorderSide(1, "#334155" if is_eu else "#1e293b"),
                        left=ft.border.BorderSide(1, "#334155" if is_eu else "#1e293b"),
                        right=ft.border.BorderSide(1, "#334155" if is_eu else "#1e293b")
                    ),
                    padding=ft.Padding(12, 8, 12, 8),
                    border_radius=8,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.icons.Icons.PERSON_ROUNDED, color="#3b82f6" if is_eu else "#94a3b8", size=15),
                                ft.Text(p, size=12, weight=ft.FontWeight.BOLD if is_eu else ft.FontWeight.NORMAL, color=get_colors()["text"])
                            ], spacing=6),
                            ft.IconButton(
                                icon=ft.icons.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color="#ef4444",
                                icon_size=15,
                                tooltip=_t("Excluir Perfil"),
                                visible=not is_eu,
                                on_click=lambda e, name=p: run_delete_profile(name)
                            )
                        ]
                    )
                )
            )
            
        # 2.4 CADASTRO DE CATEGORIAS
        txt_new_cat = ft.TextField(
            label=_t("Nova Categoria"),
            hint_text=_t("Nome"),
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"],
            height=48,
            content_padding=ft.Padding(10, 5, 10, 5),
            text_size=11
        )
        
        dropdown_type = ft.Dropdown(
            label=_t("Tipo"),
            options=[
                ft.dropdown.Option(key="Receita Fixa", text=_t("Receita Fixa")),
                ft.dropdown.Option(key="Receita Variável", text=_t("Receita Variável")),
                ft.dropdown.Option(key="Despesa Fixa", text=_t("Despesa Fixa")),
                ft.dropdown.Option(key="Despesa Variável", text=_t("Despesa Variável")),
                ft.dropdown.Option(key="Investimento", text=_t("Investimento"))
            ],
            value="Despesa Variável",
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"],
            height=48,
            content_padding=ft.Padding(10, 5, 10, 5),
            text_size=11
        )
        
        parents = [c for c in categorias if c[3] is None]
        parent_options = [ft.dropdown.Option(key="None", text=_t("Pai Root"))]
        for p_cat in parents:
            parent_options.append(ft.dropdown.Option(key=str(p_cat[0]), text=p_cat[1]))
            
        dropdown_parent = ft.Dropdown(
            label=_t("Categoria Pai"),
            options=parent_options,
            value="None",
            border_color="#475569",
            focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"),
            text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"],
            height=48,
            content_padding=ft.Padding(10, 5, 10, 5),
            text_size=11
        )
        
        def run_add_category(e):
            nome = (txt_new_cat.value or "").strip()
            tipo = dropdown_type.value
            p_val = dropdown_parent.value
            parent_id = None if p_val == "None" else int(p_val)
            
            if not nome:
                page.snack_bar = ft.SnackBar(content=ft.Text(_t("Por favor, digite o nome da categoria!"), color=get_colors()["text"]), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return
                
            success, msg = db.inserir_categoria(nome, tipo, parent_id)
            if success:
                page.snack_bar = ft.SnackBar(content=ft.Text(_t("Categoria adicionada com sucesso!"), color=get_colors()["text"]), bgcolor="#10b981")
                txt_new_cat.value = ""
                dropdown_parent.value = "None"
                render_configuracoes()
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro:')} {msg}", color=get_colors()["text"]), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()
            
        btn_add_category = ft.ElevatedButton(
            content=_t("ADICIONAR CATEGORIA"),
            color="white",
            bgcolor="#3b82f6",
            height=40,
            on_click=run_add_category,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
        )
        
        def run_delete_category(cat_id):
            success, msg = db.excluir_categoria(cat_id)
            if success:
                page.snack_bar = ft.SnackBar(content=ft.Text(_t("Categoria excluída com sucesso!"), color=get_colors()["text"]), bgcolor="#10b981")
                render_configuracoes()
            else:
                page.snack_bar = ft.SnackBar(content=ft.Text(f"{_t('Erro:')} {msg}", color=get_colors()["text"]), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()

        def abrir_editar_categoria(cat_info):
            cat_id = cat_info[0]
            cat_nome = cat_info[1]
            cat_tipo = cat_info[2]
            cat_parent_id = cat_info[3]
            
            txt_edit_nome = ft.TextField(
                label=_t("Nome da Categoria"),
                value=cat_nome,
                border_color="#475569", focused_border_color="#3b82f6",
                label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
                bgcolor=get_colors()["bg"], height=48, text_size=12
            )
            
            tipos = [
                ("Receita Fixa", _t("Receita Fixa")),
                ("Receita Variável", _t("Receita Variável")),
                ("Despesa Fixa", _t("Despesa Fixa")),
                ("Despesa Variável", _t("Despesa Variável")),
                ("Investimento", _t("Investimento"))
            ]
            
            drop_edit_tipo = ft.Dropdown(
                label=_t("Pilar / Tipo"),
                options=[ft.dropdown.Option(t[0], t[1]) for t in tipos],
                value=cat_tipo,
                width=300,
                height=48,
                text_size=12,
                bgcolor=get_colors()["bg"],
                border_color="#475569",
                focused_border_color="#3b82f6",
                disabled=(cat_parent_id is not None)
            )
            
            todos_pais = [c for c in categorias if c[3] is None and c[0] != cat_id]
            options_p = [ft.dropdown.Option("None", _t("Nenhum (Tornar Categoria Principal)"))]
            for p in todos_pais:
                options_p.append(ft.dropdown.Option(str(p[0]), f"{p[1]} ({p[2]})"))
                
            drop_edit_parent = ft.Dropdown(
                label=_t("Categoria Pai (opcional)"),
                options=options_p,
                value=str(cat_parent_id) if cat_parent_id is not None else "None",
                width=300,
                height=48,
                text_size=12,
                bgcolor=get_colors()["bg"],
                border_color="#475569",
                focused_border_color="#3b82f6"
            )
            
            def on_parent_change(e):
                sel_p = e.control.value
                if sel_p == "None":
                    drop_edit_tipo.disabled = False
                else:
                    drop_edit_tipo.disabled = True
                    p_id = int(sel_p)
                    parent_cat = next((c for c in categorias if c[0] == p_id), None)
                    if parent_cat:
                        drop_edit_tipo.value = parent_cat[2]
                drop_edit_tipo.update()
                
            drop_edit_parent.on_change = on_parent_change
            
            lbl_info = ft.Text(
                _t("Nota: Mudar o tipo ou mover subcategorias atualizará automaticamente todos os lançamentos existentes no banco de dados."),
                size=10,
                color="#facc15",
                italic=True
            )
            
            def salvar_edicao(e):
                novo_n = txt_edit_nome.value.strip()
                if not novo_n:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Preencha o nome da categoria!"), color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    return
                    
                sel_parent = drop_edit_parent.value
                novo_parent_id = None if sel_parent == "None" else int(sel_parent)
                
                novo_tipo = drop_edit_tipo.value
                if novo_parent_id is not None:
                    parent_cat = next((c for c in categorias if c[0] == novo_parent_id), None)
                    if parent_cat:
                        novo_tipo = parent_cat[2]
                
                success, msg = db.atualizar_categoria(cat_id, novo_n, novo_tipo, novo_parent_id)
                if success:
                    page.snack_bar = ft.SnackBar(ft.Text(_t("Categoria atualizada com sucesso!"), color="white"), bgcolor="#10b981")
                    page.pop_dialog()
                    render_configuracoes()
                else:
                    page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao salvar:')} {msg}", color="white"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()
                    
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(_t("Editar Categoria"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                content=ft.Column([
                    txt_edit_nome,
                    drop_edit_parent,
                    drop_edit_tipo,
                    lbl_info
                ], tight=True, spacing=12),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                    ft.ElevatedButton(_t("SALVAR"), on_click=salvar_edicao, bgcolor="#3b82f6", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)
            
        cats_grouped = {}
        for cat in categorias:
            if cat[3] is None:
                cats_grouped[cat[0]] = {"info": cat, "children": []}
                
        for cat in categorias:
            p_id = cat[3]
            if p_id is not None:
                if p_id in cats_grouped:
                    cats_grouped[p_id]["children"].append(cat)
                else:
                    cats_grouped[cat[0]] = {"info": cat, "children": []}
                    
        category_rows = []
        for p_id, group in cats_grouped.items():
            p_info = group["info"]
            
            def make_edit_click(info_item):
                return lambda e: abrir_editar_categoria(info_item)
                
            def make_delete_click(cid):
                return lambda e: run_delete_category(cid)

            category_rows.append(
                ft.Container(
                    bgcolor=get_colors()["bg"],
                    border=ft.border.all(1, get_colors()["border"]),
                    padding=ft.Padding(8, 4, 8, 4),
                    border_radius=6,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.icons.Icons.FOLDER_OPEN_ROUNDED, color="#facc15", size=14),
                                ft.Text(p_info[1].upper(), size=11, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                                ft.Container(
                                    bgcolor=get_colors()["surface"],
                                    padding=ft.Padding(3, 1, 3, 1),
                                    border_radius=4,
                                    content=ft.Text(p_info[2], size=8, color=get_colors()["subtext"])
                                )
                            ], spacing=5),
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.Icons.EDIT_ROUNDED,
                                    icon_color="#3b82f6",
                                    icon_size=14,
                                    tooltip=_t("Editar Categoria"),
                                    on_click=make_edit_click(p_info)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.Icons.DELETE_ROUNDED,
                                    icon_color="#ef4444",
                                    icon_size=14,
                                    visible=len(group["children"]) == 0,
                                    on_click=make_delete_click(p_info[0])
                                )
                            ], spacing=2)
                        ]
                    )
                )
            )
            
            for child in group["children"]:
                category_rows.append(
                    ft.Container(
                        padding=ft.Padding(20, 1, 8, 1),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row([
                                    ft.Icon(ft.icons.Icons.SUBDIRECTORY_ARROW_RIGHT_ROUNDED, color="#475569", size=12),
                                    ft.Text(child[1], size=11, color=get_colors()["subtext"]),
                                    ft.Container(
                                        bgcolor=get_colors()["surface"],
                                        padding=ft.Padding(3, 1, 3, 1),
                                        border_radius=4,
                                        content=ft.Text(child[2], size=8, color=get_colors()["subtext"])
                                    )
                                ], spacing=5),
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.icons.Icons.EDIT_ROUNDED,
                                        icon_color="#3b82f6",
                                        icon_size=13,
                                        tooltip=_t("Editar Subcategoria"),
                                        on_click=make_edit_click(child)
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.Icons.DELETE_ROUNDED,
                                        icon_color="#ef4444",
                                        icon_size=13,
                                        on_click=make_delete_click(child[0])
                                    )
                                ], spacing=2)
                            ]
                        )
                    )
                )
                
        # 3. CONSTRUÇÃO DO PAINEL DE DETALHE SELECIONADO
        if active_config_tab == "banco_dados":
            detail_panel = ft.Container(
                bgcolor=get_colors()["surface"],
                border=ft.border.all(1, get_colors()["border"]),
                border_radius=12,
                padding=20,
                expand=True,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Text(_t("Banco de Dados & Preferências"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Divider(color="#334155"),
                        ft.Text(_t("Tema e Idioma"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Row([
                            dropdown_theme,
                            dropdown_lang
                        ], spacing=20),
                        ft.Text(_t("Altere o tema visual e o idioma do aplicativo. Algumas alterações exigem o recarregamento da tela."), size=11, color="#64748b"),
                        ft.Divider(color="#334155"),
                        ft.Text(_t("Cálculo do Saldo Acumulado"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Row([
                            dropdown_start_mes,
                            dropdown_start_ano,
                            txt_start_value
                        ], spacing=20),
                        ft.Text(_t("Defina a partir de qual mês/ano e com qual saldo inicial o cálculo do saldo acumulado deve começar a contar para evitar distorções por parcelas antigas."), size=11, color="#64748b"),
                        ft.Divider(color="#334155"),
                        ft.Text(_t("Backup Manual do Banco de Dados"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Text(_t("Exportar uma cópia de segurança do banco de dados para um local de sua escolha."), size=11, color="#64748b"),
                        ft.Row([btn_export], alignment=ft.MainAxisAlignment.END)
                    ]
                )
            )
            
        elif active_config_tab == "perfis":
            detail_panel = ft.Container(
                bgcolor=get_colors()["surface"],
                border=ft.border.all(1, get_colors()["border"]),
                border_radius=12,
                padding=20,
                expand=True,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Text(_t("Membros da Família (Perfis)"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Divider(color="#334155"),
                        ft.Container(
                            expand=True,
                            content=ft.Column(
                                scroll=ft.ScrollMode.ADAPTIVE,
                                spacing=6,
                                controls=profiles_rows
                            )
                        ),
                        ft.Divider(color="#334155"),
                        ft.Text(_t("Novo Membro da Família"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Row([
                            ft.Container(expand=True, content=txt_new_profile),
                            btn_add_profile
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    ]
                )
            )
            
        elif active_config_tab == "categorias":
            detail_panel = ft.Container(
                bgcolor=get_colors()["surface"],
                border=ft.border.all(1, get_colors()["border"]),
                border_radius=12,
                padding=20,
                expand=True,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Text(_t("Categorias e Subcategorias"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Divider(color="#334155"),
                        ft.Container(
                            expand=True,
                            content=ft.Column(
                                scroll=ft.ScrollMode.ADAPTIVE,
                                spacing=4,
                                controls=category_rows
                            )
                        ),
                        ft.Divider(color="#334155"),
                        # Formulário de Categorias dividido em duas linhas para não espremer
                        ft.Row([
                            ft.Container(expand=1, content=txt_new_cat),
                            ft.Container(expand=1, content=dropdown_type),
                            ft.Container(expand=1, content=dropdown_parent),
                        ], spacing=6),
                        ft.Row([
                            btn_add_category
                        ], alignment=ft.MainAxisAlignment.END)
                    ]
                )
            )
            
        elif active_config_tab == "contrato_legal":
            termos_legais_completo = (
            "CONTRATO DE LICENÇA DE USUÁRIO FINAL (EULA) - SENTINEL FINANCE\n\n"
            "1. TERMOS GERAIS:\n"
            "Este Contrato regula o uso do Sentinel Finance V2. Ao instalar e utilizar o software, você concorda com todas as cláusulas aqui contidas. Se não concordar, não prossiga com a instalação.\n\n"
            "2. USO DA LICENÇA:\n"
            "O Sentinel Finance é um software de código aberto licenciado para uso pessoal de controle e gestão de finanças. É vedada a revenda ou comercialização não autorizada do software.\n\n"
            "3. SEGURANÇA E PRIVACIDADE DE DADOS:\n"
            "Os dados inseridos no sistema são de propriedade exclusiva do usuário e são armazenados exclusivamente em formato de banco de dados SQLite local (arquivo financas.db). O Sentinel Finance não possui backend na nuvem próprio para coletar ou armazenar dados confidenciais dos usuários. Toda a inteligência artificial (se configurada) e as consultas de cotações são processadas diretamente das APIs configuradas pelo usuário.\n\n"
            "4. ISENÇÃO DE RESPONSABILIDADE:\n"
            "O Sentinel Finance V2 busca cotações de dividendos, fundos imobiliários e ações diretamente de APIs públicas (como Yahoo Finance). Essas informações são fornecidas sem garantia de exatidão ou atualidade e servem apenas para fins educacionais e de planejamento. Este aplicativo não é e não deve ser considerado recomendação de investimentos, recomendação de compra ou venda de ações ou assessoria de investimentos profissional. Decisões de investimento são de responsabilidade do próprio usuário.\n\n"
            "5. EXCLUSÃO DE GARANTIAS:\n"
            "O software é fornecido 'no estado em que se encontra' (as-is), sem garantias de qualquer tipo, expressas ou implícitas. Os desenvolvedores não serão responsáveis por perdas financeiras em operações do mercado, erros de cálculo do imposto de renda ou inconsistências no saldo cadastrado."
        )
            detail_panel = ft.Container(
                bgcolor=get_colors()["surface"],
                border_radius=12,
                padding=20,
                expand=True,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Text(_t("Contrato Legal e Termos de Uso"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Divider(color="#334155"),
                        ft.Container(
                            expand=True,
                            bgcolor=get_colors()["bg"],
                            border_radius=8,
                            padding=15,
                            border=ft.border.Border(top=ft.border.BorderSide(1, "#334155"), bottom=ft.border.BorderSide(1, "#334155"), left=ft.border.BorderSide(1, "#334155"), right=ft.border.BorderSide(1, "#334155")),
                            content=ft.Column(
                                scroll=ft.ScrollMode.ALWAYS,
                                controls=[
                                    ft.Text(termos_legais_completo, size=11, color=get_colors()["subtext"])
                                ]
                            )
                        ),

                    ]
                )
            )
            
        elif active_config_tab == "atualizacoes":
            lbl_status_update = ft.Text("Clique abaixo para buscar novas versões no GitHub.", size=12, color=get_colors()["subtext"])
            prog_update = ft.ProgressBar(value=0.0, visible=False, color="#3b82f6")
            txt_notes = ft.Text("", size=11, color=get_colors()["subtext"])
            notes_container = ft.Container(
                bgcolor=get_colors()["bg"],
                border_radius=8,
                padding=10,
                border=ft.border.Border(top=ft.border.BorderSide(1, "#334155"), bottom=ft.border.BorderSide(1, "#334155"), left=ft.border.BorderSide(1, "#334155"), right=ft.border.BorderSide(1, "#334155")),
                visible=False,
                expand=True,
                content=ft.Column(
                    scroll=ft.ScrollMode.ALWAYS,
                    controls=[txt_notes]
                )
            )
            btn_apply_update = ft.ElevatedButton(
                "BAIXAR E INSTALAR ATUALIZAÇÃO",
                bgcolor="#22c55e",
                color="white",
                visible=False,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
            )
            
            def on_check_click(e):
                btn_check.disabled = True
                lbl_status_update.value = "Verificando repositório no GitHub..."
                lbl_status_update.color = "white"
                page.update()
                
                from update_manager import UpdateManager
                updater = UpdateManager(current_version="1.3.0")
                tem_update, info = updater.check_for_updates()
                
                if tem_update and info:
                    lbl_status_update.value = "Nova versão encontrada: " + info['latest_version'] + "!"
                    lbl_status_update.color = "#22c55e"
                    txt_notes.value = info["release_notes"]
                    notes_container.visible = True
                    btn_apply_update.visible = True
                    
                    def on_apply_click(e2):
                        btn_apply_update.disabled = True
                        prog_update.visible = True
                        page.update()
                        
                        def prog_cb(val, msg):
                            prog_update.value = val
                            lbl_status_update.value = msg
                            page.update()
                            
                        def comp_cb():
                            lbl_status_update.value = "Atualização concluída com sucesso! Por favor, reinicie o programa para aplicar."
                            lbl_status_update.color = "#22c55e"
                            btn_apply_update.visible = False
                            prog_update.visible = False
                            page.update()
                            
                        def err_cb(err_msg):
                            lbl_status_update.value = "Erro na atualização: " + err_msg
                            lbl_status_update.color = "#ef4444"
                            btn_apply_update.disabled = False
                            prog_update.visible = False
                            page.update()
                            
                        updater.install_update_async(prog_cb, comp_cb, err_cb)
                        
                    btn_apply_update.on_click = on_apply_click
                else:
                    lbl_status_update.value = "Seu aplicativo já está na versão mais recente (v1.3.0)."
                    lbl_status_update.color = "#10b981"
                    
                btn_check.disabled = False
                page.update()

            btn_check = ft.ElevatedButton(
                "BUSCAR ATUALIZAÇÃO NO GITHUB",
                bgcolor="#3b82f6",
                color="white",
                on_click=on_check_click,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
            )
            
            detail_panel = ft.Container(
                bgcolor=get_colors()["surface"],
                border=ft.border.all(1, get_colors()["border"]),
                border_radius=12,
                padding=20,
                expand=True,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Text("Atualização do Sentinel Finance", size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Divider(color="#334155"),
                        ft.Row([
                            ft.Text("Versão Atual:", size=12, color=get_colors()["subtext"]),
                            ft.Text("v1.3.0", size=12, color="white", weight=ft.FontWeight.BOLD)
                        ]),
                        ft.Divider(color="#334155"),
                        lbl_status_update,
                        prog_update,
                        notes_container,
                        ft.Row([
                            btn_check,
                            btn_apply_update
                        ], spacing=10)
                    ]
                )
            )
            
        elif active_config_tab == "backups_sessoes":
            # Obter a lista de backups na pasta session_backups
            import shutil
            base_dir = os.path.dirname(os.path.abspath(original_prod_path))
            backup_dir = os.path.join(base_dir, "session_backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            backups_disponiveis = []
            if os.path.exists(backup_dir):
                for f in os.listdir(backup_dir):
                    if f.startswith("backup_sessao_") and f.endswith(".db"):
                        fpath = os.path.join(backup_dir, f)
                        try:
                            mtime = os.path.getmtime(fpath)
                            dt_mod = datetime.datetime.fromtimestamp(mtime)
                            size_kb = os.path.getsize(fpath) / 1024.0
                            backups_disponiveis.append({
                                "filename": f,
                                "filepath": fpath,
                                "data_formatada": dt_mod.strftime("%d/%m/%Y %H:%M:%S"),
                                "tamanho": f"{size_kb:.1f} KB",
                                "mtime": mtime
                            })
                        except Exception:
                            pass
            
            # Ordenar do mais recente para o mais antigo
            backups_disponiveis.sort(key=lambda x: x["mtime"], reverse=True)
            
            def restaurar_backup_sessao(filepath):
                def realizar_restauracao(e2):
                    page.pop_dialog()
                    try:
                        # 1. Faz cópia de segurança antes de reverter
                        shutil.copy2(original_prod_path, original_prod_path + ".bak")
                        # 2. Copia o backup selecionado por cima do original
                        shutil.copy2(filepath, original_prod_path)
                        
                        # Re-inicializa o banco
                        db.switch_to_production()
                        
                        page.snack_bar = ft.SnackBar(
                            content=ft.Text(_t("Alterações revertidas com sucesso! Recarregando..."), color="white"),
                            bgcolor="#10b981"
                        )
                        page.snack_bar.open = True
                        page.update()
                        
                        # Recarrega o app
                        render_dashboard()
                    except Exception as err:
                        page.snack_bar = ft.SnackBar(
                            content=ft.Text(f"Erro ao reverter alterações: {err}", color="white"),
                            bgcolor="#ef4444"
                        )
                        page.snack_bar.open = True
                        page.update()
                
                dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text(_t("CONFIRMAR RESTAURAÇÃO ⚠️"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                    content=ft.Text(_t("Deseja realmente reverter as alterações para esta sessão? Todos os dados gravados após este backup serão substituídos."), size=14, color=get_colors()["subtext"]),
                    bgcolor=get_colors()["surface"],
                    actions=[
                        ft.TextButton(_t("CANCELAR"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white")),
                        ft.ElevatedButton(_t("REVERTER"), on_click=realizar_restauracao, bgcolor="#ef4444", color="white", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                page.show_dialog(dialog)

            def excluir_backup_sessao(filepath):
                try:
                    os.remove(filepath)
                    page.snack_bar = ft.SnackBar(content=ft.Text(_t("Backup de sessão excluído com sucesso!")), bgcolor="#10b981")
                    page.snack_bar.open = True
                    render_configuracoes()
                except Exception as err:
                    page.snack_bar = ft.SnackBar(content=ft.Text(f"Erro ao excluir backup: {err}"), bgcolor="#ef4444")
                    page.snack_bar.open = True
                    page.update()

            backups_rows = []
            for b in backups_disponiveis:
                backups_rows.append(
                    ft.Container(
                        bgcolor=get_colors()["bg"],
                        border=ft.border.all(1, get_colors()["border"]),
                        padding=ft.Padding(12, 10, 12, 10),
                        border_radius=8,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row([
                                    ft.Icon(ft.icons.Icons.HISTORY_ROUNDED, color="#3b82f6", size=18),
                                    ft.Column([
                                        ft.Text(b["data_formatada"], size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                                        ft.Text(f"Tamanho: {b['tamanho']}", size=10, color=get_colors()["subtext"])
                                    ], spacing=2)
                                ], spacing=8),
                                ft.Row([
                                    ft.ElevatedButton(
                                        _t("Reverter"),
                                        bgcolor="#3b82f6",
                                        color="white",
                                        height=32,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                                        on_click=lambda e, fp=b["filepath"]: restaurar_backup_sessao(fp)
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.Icons.DELETE_OUTLINE_ROUNDED,
                                        icon_color="#ef4444",
                                        icon_size=16,
                                        tooltip=_t("Excluir Backup"),
                                        on_click=lambda e, fp=b["filepath"]: excluir_backup_sessao(fp)
                                    )
                                ], spacing=5)
                            ]
                        )
                    )
                )
            
            if not backups_rows:
                backups_rows.append(ft.Text(_t("Nenhum backup de sessão disponível no momento."), color="#64748b", size=12))

            detail_panel = ft.Container(
                bgcolor=get_colors()["surface"],
                border=ft.border.all(1, get_colors()["border"]),
                border_radius=12,
                padding=20,
                expand=True,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Text(_t("Histórico de Backups de Sessão"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Divider(color="#334155"),
                        ft.Text(
                            _t("Os backups são gerados automaticamente cada vez que o aplicativo é iniciado. Eles são mantidos por no máximo 7 dias para permitir a reversão de alterações indesejadas."),
                            size=12,
                            color=get_colors()["subtext"]
                        ),
                        ft.Divider(color="#334155"),
                        ft.Container(
                            expand=True,
                            content=ft.Column(
                                scroll=ft.ScrollMode.ADAPTIVE,
                                spacing=8,
                                controls=backups_rows
                            )
                        )
                    ]
                )
            )

        else: # active_config_tab == "tutorial_faq"
            faq_items = [
                (_t("📊 Dashboard (Painel Geral)"), 
                 _t("O Dashboard apresenta o resumo consolidado do mês ativo. Ele exibe suas Receitas, Despesas, Saldo Líquido e o total de limite utilizado em seus cartões. "
                 "Os gráficos circulares na parte inferior mostram a distribuição de gastos por Pilar e por Categoria. Você pode navegar entre os meses e anos "
                 "usando as setas de navegação no topo da página.")),
                
                (_t("📈 Investimentos (Carteira)"), 
                 _t("Nesta aba, você cadastra suas Ações e Fundos Imobiliários. O sistema calcula a cotação média de compra e busca a cotação de mercado atualizada "
                 "(via API pública do Yahoo Finance) para mostrar a valorização e o saldo total da sua carteira. Além disso, calcula uma estimativa de dividendos "
                 "projetados com base nos últimos proventos distribuídos.")),
                
                (_t("🎨 Gráficos Comparativos"), 
                 _t("Apresenta uma visão analítica e comparativa detalhada da evolução financeira mensal. Útil para identificar padrões de consumo e tendências "
                 "ao longo do tempo.")),
                
                (_t("📝 Transações e Lançamentos"), 
                 _t("Aqui você realiza os lançamentos diários de despesas e receitas. É possível filtrar as transações de forma detalhada por Mês, Ano, "
                 "Perfil Familiar (Membros) e Categorias. O sistema permite travar transações para evitar edições acidentais.")),
                
                (_t("👥 Perfis Familiares e Categorias"), 
                 _t("O Sentinel Finance suporta múltiplos perfis na mesma base. Você pode cadastrar dependentes ou cônjuges para separar as despesas de cada "
                 "membro da família. Na aba de Categorias, você gerencia e cria subcategorias personalizadas para o seu controle financeiro.")),
                
                (_t("💾 Backup e Privacidade Absoluta"), 
                 _t("Todos os seus dados são guardados localmente no seu computador em um banco de dados SQLite (arquivo financas.db). Nenhuma informação financeira é enviada a "
                 "servidores externos. Recomendamos exportar cópias de segurança periodicamente através do botão de 'Exportar Backup' na aba de Banco de Dados."))
            ]
            
            faq_controls = []
            for q_title, q_ans in faq_items:
                faq_controls.append(
                    ft.Container(
                        bgcolor=get_colors()["bg"],
                        padding=12,
                        border_radius=8,
                        border=ft.border.Border(
                            top=ft.border.BorderSide(1, "#334155"),
                            bottom=ft.border.BorderSide(1, "#334155"),
                            left=ft.border.BorderSide(1, "#334155"),
                            right=ft.border.BorderSide(1, "#334155")
                        ),
                        content=ft.Column([
                            ft.Text(q_title, size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.Text(q_ans, size=11, color=get_colors()["subtext"])
                        ], spacing=5)
                    )
                )
                
            btn_start_tut = ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.icons.Icons.PLAY_ARROW_ROUNDED, size=18),
                    ft.Text(_t("INICIAR TUTORIAL GUIADO"), size=11, weight=ft.FontWeight.BOLD)
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=5),
                color="white",
                bgcolor="#3b82f6",
                height=42,
                on_click=lambda e: iniciar_tutorial_usuario(),
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
            )
            
            detail_panel = ft.Container(
                bgcolor=get_colors()["surface"],
                border=ft.border.all(1, get_colors()["border"]),
                border_radius=12,
                padding=20,
                expand=True,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Text(_t("Tutorial e Perguntas Frequentes (FAQ)"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Divider(color="#334155"),
                        ft.Text(_t("Precisa de ajuda para entender como o Sentinel Finance funciona? Clique abaixo para iniciar um tour guiado interativo:"), size=12, color=get_colors()["subtext"]),
                        btn_start_tut,
                        ft.Divider(color="#334155"),
                        ft.Text(_t("Guia Rápido dos Módulos (FAQ):"), size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Container(
                            expand=True,
                            content=ft.Column(
                                scroll=ft.ScrollMode.ADAPTIVE,
                                spacing=8,
                                controls=faq_controls
                            )
                        )
                    ]
                )
            )
            
        # 4. CONSTRUÇÃO DO MENU LATERAL INTERNO (CASCATA DE BOTÕES)
        menu_items = [
            (_t("Banco de Dados"), ft.icons.Icons.STORAGE_ROUNDED, "banco_dados"),
            (_t("Perfis Familiares"), ft.icons.Icons.PEOPLE_ROUNDED, "perfis"),
            (_t("Categorias"), ft.icons.Icons.CATEGORY_ROUNDED, "categorias"),
            (_t("Backup"), ft.icons.Icons.BACKUP_ROUNDED, "backups_sessoes"),
            (_t("Contrato Legal"), ft.icons.Icons.DESCRIPTION_ROUNDED, "contrato_legal"),
            (_t("Atualizações"), ft.icons.Icons.SYSTEM_UPDATE_ALT_ROUNDED, "atualizacoes"),
            (_t("Tutorial e FAQ"), ft.icons.Icons.HELP_OUTLINE_ROUNDED, "tutorial_faq")
        ]
        
        sidebar_controls = []
        for label, icon, tab_id in menu_items:
            is_active = (tab_id == active_config_tab)
            
            # Helper de evento
            def make_handler(tid):
                return lambda e: select_config_tab(tid)
                
            sidebar_controls.append(
                ft.Container(
                    bgcolor="#1e3a8a" if is_active else "transparent",
                    padding=ft.Padding(12, 10, 12, 10),
                    border_radius=8,
                    on_click=make_handler(tab_id),
                    content=ft.Row([
                        ft.Icon(icon, color="white" if is_active else "#94a3b8", size=18),
                        ft.Text(label, size=13, weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL, color=get_colors()["text"] if is_active else "#94a3b8")
                    ], spacing=10)
                )
            )
            
        config_sidebar = ft.Container(
            width=220,
            bgcolor=get_colors()["surface"],
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=12,
            padding=10,
            content=ft.Column(
                spacing=5,
                controls=sidebar_controls
            )
        )
        
        # 5. ASSEMBLE GENERAL LAYOUT (2 COLUMNS SIDE-BY-SIDE)
        main_layout_row = ft.Row(
            expand=True,
            spacing=15,
            controls=[
                config_sidebar,
                detail_panel
            ],
            vertical_alignment=ft.CrossAxisAlignment.STRETCH
        )
        
        configuracoes_layout = ft.Column(
            expand=True,
            spacing=15,
            controls=[
                header_row,
                ft.Container(height=5),
                main_layout_row
            ]
        )
        
        body.content = configuracoes_layout
        page.update()

    def abrir_edit_parcela_individual(trans_id, val, date):
        txt_new_val = ft.TextField(
            label=_t("Novo Valor (R$)"),
            value=str(val),
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )
        
        txt_new_date = ft.TextField(
            label=_t("Nova Data (DD/MM/AAAA)"),
            value=str(date),
            border_color="#475569", focused_border_color="#3b82f6",
            label_style=ft.TextStyle(color="#94a3b8"), text_style=ft.TextStyle(color=get_colors()["text"]),
            bgcolor=get_colors()["bg"], height=48, text_size=12
        )

        def salvar_parcela(e):
            val_str = txt_new_val.value.strip().replace(",", ".")
            date_str = txt_new_date.value.strip()
            
            try:
                new_val = float(val_str)
                if new_val <= 0:
                    raise ValueError()
            except:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Digite um valor numérico válido!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return

            try:
                import datetime
                datetime.datetime.strptime(date_str, "%d/%m/%Y")
            except:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Data inválida! Use DD/MM/AAAA"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return

            details = db.get_transacao_by_id(trans_id)
            if not details:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao buscar transação!"), color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()
                return

            # Escalar proporcionalmente os valores das divisões
            # O valor editado pelo usuário corresponde ao valor exibido para o seu perfil.
            # Portanto, calculamos o ratio com base na cota anterior do perfil atual.
            old_cota = details["divisoes"].get(state["perfil"]) if details["divisoes"] else details["valor_total"]
            ratio = new_val / old_cota if old_cota > 0 else 1.0
            new_total = details["valor_total"] * ratio
            
            new_divisoes = {}
            if details["divisoes"]:
                for user, cota in details["divisoes"].items():
                    new_divisoes[user] = cota * ratio

            success, msg = db.atualizar_transacao(
                transacao_id=trans_id,
                categoria_id=details["categoria_id"],
                descricao=details["descricao"],
                data=date_str,
                valor_total=new_total,
                tipo_transacao=details["tipo_transacao"],
                metodo=details["metodo_pagamento"],
                bandeira=details["bandeira_cartao"],
                dono=details["dono_cartao"],
                observacao=details["observacao"],
                divisoes=new_divisoes,
                data_real=date_str,  # Atualizar data_real também para mover no dashboard
                atualizar_grupo=False
            )

            if success:
                page.snack_bar = ft.SnackBar(ft.Text(_t("Parcela atualizada com sucesso!"), color="white"), bgcolor="#10b981")
                page.snack_bar.open = True
                page.pop_dialog()
                render_parcelamentos()
            else:
                page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao atualizar:')} {msg}", color="white"), bgcolor="#ef4444")
                page.snack_bar.open = True
                page.update()

        def fechar_dialog(e):
            page.pop_dialog()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(_t("Editar Parcela Individual"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=ft.Column(
                controls=[
                    txt_new_val,
                    ft.Container(height=5),
                    txt_new_date
                ],
                height=120,
                tight=True
            ),
            actions=[
                ft.TextButton(_t("Cancelar"), on_click=fechar_dialog),
                ft.ElevatedButton(_t("Salvar"), on_click=salvar_parcela, bgcolor="#3b82f6", color="white")
            ]
        )
        page.show_dialog(dialog)

    def empurrar_parcela(trans_id):
        details = db.get_transacao_by_id(trans_id)
        if not details:
            page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao buscar transação!"), color="white"), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()
            return
            
        data_atual = details["data"]
        try:
            import datetime
            dt = datetime.datetime.strptime(data_atual, "%d/%m/%Y")
            # Adiciona 1 mês
            mes = dt.month + 1
            ano = dt.year + (mes - 1) // 12
            mes = (mes - 1) % 12 + 1
            dia = min(dt.day, 28)
            new_dt = datetime.datetime(ano, mes, dia)
            new_date_str = new_dt.strftime("%d/%m/%Y")
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao calcular nova data:')} {ex}", color="white"), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()
            return

        # Escalar as divisões (invariante aqui, mas necessário para não zerar)
        success, msg = db.atualizar_transacao(
            transacao_id=trans_id,
            categoria_id=details["categoria_id"],
            descricao=details["descricao"],
            data=new_date_str,
            valor_total=details["valor_total"],
            tipo_transacao=details["tipo_transacao"],
            metodo=details["metodo_pagamento"],
            bandeira=details["bandeira_cartao"],
            dono=details["dono_cartao"],
            observacao=details["observacao"],
            divisoes=details["divisoes"],
            data_real=new_date_str,  # Atualizar data_real também para mover no dashboard
            atualizar_grupo=False
        )

        if success:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"{_t('Parcela empurrada para')} {new_date_str}!", color="white"), 
                bgcolor="#10b981"
            )
            page.snack_bar.open = True
            render_parcelamentos()
        else:
            page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao empurrar:')} {msg}", color="white"), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()

    def puxar_parcela(trans_id):
        details = db.get_transacao_by_id(trans_id)
        if not details:
            page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao buscar transação!"), color="white"), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()
            return
            
        data_atual = details["data"]
        try:
            import datetime
            dt = datetime.datetime.strptime(data_atual, "%d/%m/%Y")
            # Subtrai 1 mês
            mes = dt.month - 1
            ano = dt.year + (mes - 1) // 12
            mes = (mes - 1) % 12 + 1
            dia = min(dt.day, 28)
            new_dt = datetime.datetime(ano, mes, dia)
            new_date_str = new_dt.strftime("%d/%m/%Y")
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao calcular nova data:')} {ex}", color="white"), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()
            return

        success, msg = db.atualizar_transacao(
            transacao_id=trans_id,
            categoria_id=details["categoria_id"],
            descricao=details["descricao"],
            data=new_date_str,
            valor_total=details["valor_total"],
            tipo_transacao=details["tipo_transacao"],
            metodo=details["metodo_pagamento"],
            bandeira=details["bandeira_cartao"],
            dono=details["dono_cartao"],
            observacao=details["observacao"],
            divisoes=details["divisoes"],
            data_real=new_date_str,  # Atualizar data_real também para mover no dashboard
            atualizar_grupo=False
        )

        if success:
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"{_t('Parcela puxada para')} {new_date_str}!", color="white"), 
                bgcolor="#10b981"
            )
            page.snack_bar.open = True
            render_parcelamentos()
        else:
            page.snack_bar = ft.SnackBar(ft.Text(f"{_t('Erro ao puxar:')} {msg}", color="white"), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()

    def confirmar_mover_parcela(trans_id, direcao):
        details = db.get_transacao_by_id(trans_id)
        if not details:
            page.snack_bar = ft.SnackBar(ft.Text(_t("Erro ao buscar transação!"), color="white"), bgcolor="#ef4444")
            page.snack_bar.open = True
            page.update()
            return

        label_action = _t("empurrar para o próximo mês") if direcao == "empurrar" else _t("trazer para o mês anterior")
        
        def on_confirm(e):
            page.pop_dialog()
            if direcao == "empurrar":
                empurrar_parcela(trans_id)
            else:
                puxar_parcela(trans_id)

        def on_cancel(e):
            page.pop_dialog()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(_t("Confirmar Ação"), size=16, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
            content=ft.Text(f"{_t('Tem certeza que deseja')} {label_action} {_t('esta parcela de')} {details['descricao']}?", color=get_colors()["text"]),
            actions=[
                ft.TextButton(_t("Cancelar"), on_click=on_cancel),
                ft.ElevatedButton(_t("Confirmar"), on_click=on_confirm, bgcolor="#3b82f6", color="white")
            ]
        )
        page.show_dialog(dialog)

    def render_parcelamentos():
        compras = db.get_compras_parceladas(state["perfil"])
        
        # Filtrar apenas parcelamentos ativos (mês atual e parcelas futuras)
        import datetime
        now = datetime.datetime.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        active_compras = []
        for c in compras:
            g_id = c[0]
            parcelas = db.get_parcelas_compra(g_id, state["perfil"])
            latest_dt = None
            for p in parcelas:
                try:
                    p_dt = datetime.datetime.strptime(p[1], "%d/%m/%Y")
                except:
                    p_dt = now
                if latest_dt is None or p_dt > latest_dt:
                    latest_dt = p_dt
            
            if latest_dt and latest_dt >= current_month_start:
                active_compras.append(c)
        compras = active_compras
        
        # Build card map dynamically
        cartoes = db.get_cartoes()
        card_map = {}
        for c in cartoes:
            key = f"{c[6]}|{c[7]}"
            card_map[key] = c[1]

        pagamentos = {}
        for c in compras:
            metodo = c[5]
            band = c[6]
            dono = c[7]
            if metodo == "Cartão":
                card_name = card_map.get(f"{band}|{dono}", f"Cartão {dono} ({band})" if (band and dono) else _t("Cartão de Crédito"))
                key = f"Cartão {card_name}"
            else:
                key = metodo
                
            if key not in pagamentos:
                pagamentos[key] = []
            pagamentos[key].append(c)

        sorted_keys = sorted(pagamentos.keys())
        
        active_pay_method = state.get("active_payment_method_installments")
        if active_pay_method not in sorted_keys:
            active_pay_method = sorted_keys[0] if sorted_keys else None
            state["active_payment_method_installments"] = active_pay_method

        left_buttons = []
        for key in sorted_keys:
            is_active = (key == active_pay_method)
            is_card = "Cartão" in key
            icon = ft.icons.Icons.CREDIT_CARD_ROUNDED if is_card else (ft.icons.Icons.QR_CODE_2_ROUNDED if "Pix" in key else (ft.icons.Icons.ATTACH_MONEY_ROUNDED if "Dinheiro" in key else ft.icons.Icons.PAYMENT_ROUNDED))
            
            def make_on_click_pay(target_key):
                def click_handler(e):
                    state["active_payment_method_installments"] = target_key
                    render_parcelamentos()
                return click_handler

            left_buttons.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(icon, color="white" if is_active else "#64748b", size=18),
                        ft.Text(key.upper(), size=12, color=get_colors()["text"] if is_active else "#64748b", weight=ft.FontWeight.BOLD),
                    ], spacing=8),
                    padding=ft.Padding(15, 12, 15, 12),
                    bgcolor=get_colors()["surface"] if is_active else "transparent",
                    border=ft.border.all(1, get_colors()["border"] if is_active else "transparent"),
                    border_radius=10,
                    ink=True,
                    on_click=make_on_click_pay(key)
                )
            )

        def toggle_expand_purchase(g_id):
            if state.get("expanded_installment_purchase_id") == g_id:
                state["expanded_installment_purchase_id"] = None
            else:
                state["expanded_installment_purchase_id"] = g_id
            render_parcelamentos()

        purchase_cards = []
        selected_key = active_pay_method
        for c in pagamentos.get(selected_key, []) if selected_key else []:
            g_id = c[0]
            dt_ini = c[1]
            desc = c[2].split(" - Parcela ")[0]
            val_total = c[3]
            tot_parc = c[4]
            cat_name = c[9]
            
            is_expanded = (state.get("expanded_installment_purchase_id") == g_id)
            
            # Gerar bolinhas numeradas representando as parcelas (verde = paga, cinza = pendente)
            bolinhas = []
            parcelas_status = db.get_parcelas_compra(g_id, state["perfil"])
            for p in parcelas_status:
                p_data = p[1]
                p_num = p[4]
                try:
                    p_dt = datetime.datetime.strptime(p_data, "%d/%m/%Y")
                except:
                    p_dt = now
                p_paid = p_dt < current_month_start
                
                bolinhas.append(
                    ft.Container(
                        width=18,
                        height=18,
                        border_radius=9,
                        bgcolor="#10b981" if p_paid else "#475569",
                        content=ft.Text(str(p_num), size=9, color="white", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                        alignment=ft.Alignment(0, 0)
                    )
                )
            bolinhas_row = ft.Row(controls=bolinhas, spacing=3, alignment=ft.MainAxisAlignment.CENTER)
            
            header_content = ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row([
                        ft.Container(
                            padding=6,
                            bgcolor=get_colors()["surface"],
                            border_radius=6,
                            content=ft.Icon(get_icone_categoria(cat_name), color="#fb923c", size=16)
                        ),
                        ft.Column([
                            ft.Text(desc, size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                            ft.Text(f"{cat_name} • {_t('Início em')} {dt_ini} • {tot_parc}x", size=11, color="#64748b")
                        ], spacing=2)
                    ], spacing=10),
                    ft.Container(
                        content=bolinhas_row,
                        alignment=ft.Alignment(0, 0),
                        expand=True,
                        margin=ft.Margin(15, 0, 15, 0)
                    ),
                    ft.Row([
                        ft.Text(f"R$ {val_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=13, weight=ft.FontWeight.BOLD, color="#fb923c"),
                        ft.Icon(ft.icons.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if not is_expanded else ft.icons.Icons.KEYBOARD_ARROW_UP_ROUNDED, color="#64748b", size=20)
                    ], spacing=10)
                ]
            )
            
            card_content = ft.Column(spacing=10, controls=[
                ft.Container(
                    content=header_content,
                    ink=True,
                    on_click=lambda e, gid=g_id: toggle_expand_purchase(gid),
                    padding=10
                )
            ])
            
            if is_expanded:
                parcelas = db.get_parcelas_compra(g_id, state["perfil"])
                rows = []
                for p in parcelas:
                    p_id = p[0]
                    p_data = p[1]
                    p_desc = p[2]
                    p_valor = p[3]
                    p_num = p[4]
                    p_tot = p[5]
                    
                    try:
                        p_dt = datetime.datetime.strptime(p_data, "%d/%m/%Y")
                    except:
                        p_dt = now
                    p_paid = p_dt < current_month_start

                    # Número da parcela com checkmark verde se já paga
                    if p_paid:
                        num_cell_content = ft.Row([
                            ft.Text(f"{p_num}/{p_tot}", color=get_colors()["text"], size=12),
                            ft.Icon(ft.icons.Icons.CHECK_CIRCLE_ROUNDED, color="#10b981", size=14)
                        ], spacing=4)
                    else:
                        num_cell_content = ft.Text(f"{p_num}/{p_tot}", color=get_colors()["text"], size=12)

                    def make_edit_parcela(tid, val, dt):
                        return lambda e: abrir_edit_parcela_individual(tid, val, dt)
                    
                    def make_mover_parcela(tid, dir):
                        return lambda e: confirmar_mover_parcela(tid, dir)

                    rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(num_cell_content),
                                ft.DataCell(ft.Text(p_data, color=get_colors()["text"], size=12)),
                                ft.DataCell(ft.Text(f"R$ {p_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), color=get_colors()["text"], weight=ft.FontWeight.BOLD, size=12)),
                                ft.DataCell(
                                    ft.Row([
                                        ft.IconButton(
                                            ft.icons.Icons.EDIT_ROUNDED, 
                                            icon_color="#3b82f6", 
                                            icon_size=16, 
                                            tooltip=_t("Editar esta parcela"), 
                                            on_click=make_edit_parcela(p_id, p_valor, p_data)
                                        ),
                                        ft.IconButton(
                                            ft.icons.Icons.SKIP_PREVIOUS_ROUNDED, 
                                            icon_color="#fb923c", 
                                            icon_size=16, 
                                            tooltip=_t("Trazer para o mês anterior"), 
                                            on_click=make_mover_parcela(p_id, "puxar")
                                        ),
                                        ft.IconButton(
                                            ft.icons.Icons.SKIP_NEXT_ROUNDED, 
                                            icon_color="#fb923c", 
                                            icon_size=16, 
                                            tooltip=_t("Empurrar para o próximo mês"), 
                                            on_click=make_mover_parcela(p_id, "empurrar")
                                        )
                                    ], spacing=5)
                                )
                            ]
                        )
                    )
                
                table = ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text(_t("Nº"), size=11, weight=ft.FontWeight.BOLD)),
                        ft.DataColumn(ft.Text(_t("Vencimento"), size=11, weight=ft.FontWeight.BOLD)),
                        ft.DataColumn(ft.Text(_t("Valor"), size=11, weight=ft.FontWeight.BOLD)),
                        ft.DataColumn(ft.Text(_t("Ações"), size=11, weight=ft.FontWeight.BOLD)),
                    ],
                    rows=rows,
                    heading_row_height=30,
                    data_row_min_height=30,
                    data_row_max_height=38,
                    border_radius=8,
                    border=ft.border.all(0.5, get_colors()["border"]),
                    heading_row_color=get_colors()["bg"],
                )
                
                card_content.controls.append(
                    ft.Container(
                        padding=ft.Padding(10, 0, 10, 10),
                        content=ft.Row([table], scroll=ft.ScrollMode.ADAPTIVE)
                    )
                )
            
            purchase_cards.append(
                ft.Container(
                    content=card_content,
                    bgcolor=get_colors()["surface"],
                    border=ft.border.all(1, get_colors()["border"]),
                    border_radius=10,
                    margin=ft.Margin(0, 0, 0, 10)
                )
            )

        def on_change_perfil_parc(e):
            state["perfil"] = e.control.value
            render_parcelamentos()

        seletor_perfil_parc = criar_seletor_perfil(on_change_perfil_parc)
        tab_header = criar_tab_header("parcelamentos", seletor_perfil_parc, subcontroles=[])

        # Left Panel (Payment methods list)
        panel_left = ft.Container(
            width=260,
            bgcolor=get_colors()["surface"],
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=12,
            padding=15,
            content=ft.Column(
                controls=[
                    ft.Text(_t("Formas de Pagamento"), size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                    ft.Divider(color=get_colors()["border"], height=10),
                    ft.ListView(
                        controls=left_buttons if left_buttons else [ft.Text(_t("Sem dados"), color="#64748b", size=12)],
                        spacing=5,
                        expand=True
                    )
                ],
                expand=True
            )
        )
        
        # Right Panel (Purchases list)
        panel_right = ft.Container(
            expand=True,
            bgcolor=get_colors()["surface"],
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=12,
            padding=20,
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.Text(f"{_t('Compras Parceladas em')} {selected_key if selected_key else ''}", size=15, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                        ft.Text(f"{len(purchase_cards)} {_t('compras')}", size=11, color="#64748b")
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(color=get_colors()["border"], height=10),
                    ft.ListView(
                        controls=purchase_cards if purchase_cards else [ft.Text(_t("Nenhuma compra parcelada cadastrada para esta forma."), color="#64748b", size=12)],
                        spacing=5,
                        expand=True
                    )
                ],
                expand=True
            )
        )
        
        main_container = ft.Row(
            controls=[panel_left, panel_right],
            spacing=20,
            expand=True
        )
        
        layout = ft.Column(
            expand=True,
            controls=[
                tab_header,
                ft.Container(height=10),
                main_container
            ],
            spacing=0
        )
        
        body.content = layout
        page.floating_action_button = None
        page.update()

    def navegar_para_aba(tab_name):
        icon_mapping = {
            "dashboard": (ft.icons.Icons.DASHBOARD_ROUNDED, render_dashboard),
            "investimentos": (ft.icons.Icons.SAVINGS_ROUNDED, render_investimentos),
            "charts": (ft.icons.Icons.PIE_CHART_ROUNDED, render_dashboard),
            "transacoes": (ft.icons.Icons.LIST_ALT_ROUNDED, render_transacoes),
            "cartoes": (ft.icons.Icons.CREDIT_CARD_ROUNDED, render_cartoes),
            "financiamentos": (ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED, render_financiamentos),
            "assistente": (ft.icons.Icons.AUTO_AWESOME_ROUNDED, None),
            "configuracoes": (ft.icons.Icons.SETTINGS_ROUNDED, render_configuracoes),
            "resumo_anual": (ft.icons.Icons.ANALYTICS_ROUNDED, render_resumo_anual),
            "recorrencias": (ft.icons.Icons.AUTORENEW_ROUNDED, render_recorrencias),
            "parcelamentos": (ft.icons.Icons.CREDIT_CARD_ROUNDED, render_parcelamentos),
            "veiculos": (ft.icons.Icons.DIRECTIONS_CAR_ROUNDED, render_veiculos),
            "pets": (ft.icons.Icons.PETS_ROUNDED, render_pets),
            "saude": (ft.icons.Icons.LOCAL_HOSPITAL_ROUNDED, render_saude)
        }
        
        target_icon, render_func = icon_mapping.get(tab_name, (None, None))
        state["active_tab"] = tab_name
        
        for btn in sidebar.content.controls:
            if isinstance(btn, ft.IconButton):
                if btn.icon == target_icon:
                    btn.icon_color = "white"
                else:
                    btn.icon_color = "#64748b"
        
        if render_func:
            if tab_name == "charts":
                state["active_tab"] = "charts"
                render_dashboard()
            else:
                render_func()
        else:
            body.content = ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(target_icon, size=100, color="#334155"),
                    ft.Text("Módulo: Assistente IA", size=24, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                    ft.Text("Em desenvolvimento...", size=16, color="#64748b")
                ]
            )
            page.update()

    def iniciar_tutorial_usuario(primeira_vez=False):
        steps = [
            {
                "tab": "dashboard",
                "title": "📊 Dashboard (Painel Geral)",
                "content": "Aqui está o painel principal! Ele resume o mês ativo, exibindo suas Receitas, Despesas, Saldo Líquido e uso de limites dos cartões. Na parte inferior, gráficos mostram seus gastos por Pilar e Categorias. Use as setas no topo para navegar entre meses."
            },
            {
                "tab": "investimentos",
                "title": "📈 Investimentos (Carteira)",
                "content": "Esta é a sua carteira de investimentos! Aqui você cadastra suas Ações e Fundos Imobiliários. O sistema calcula o preço médio de compra e busca a cotação de mercado atualizada em tempo real via Yahoo Finance, estimando também seus dividendos projetados."
            },
            {
                "tab": "charts",
                "title": "🎨 Gráficos Comparativos",
                "content": "Nesta visão comparativa do Dashboard, você encontra gráficos analíticos e comparativos de gastos. Veja a evolução mensal das despesas e receitas para identificar padrões de consumo e tendências financeiras."
            },
            {
                "tab": "transacoes",
                "title": "📝 Transações e Lançamentos",
                "content": "Aqui você gerencia todos os seus lançamentos diários (entradas e saídas). Filtre facilmente por Mês, Ano, Categoria ou Membro Familiar. O sistema permite 'travar' lançamentos para evitar edições acidentais."
            },
            {
                "tab": "cartoes",
                "title": "💳 Cartões de Crédito",
                "content": "Controle suas faturas! Cadastre seus cartões de crédito, limites, datas de fechamento e vencimento. O sistema calcula automaticamente o comprometimento do limite e as parcelas futuras."
            },
            {
                "tab": "recorrencias",
                "title": "🔄 Recorrências (Lançamentos Automáticos)",
                "content": "Cadastre e gerencie suas despesas e receitas fixas ou recorrentes. O sistema as projeta automaticamente nos meses futuros e permite confirmar ou editar cada ocorrência individualmente."
            },
            {
                "tab": "parcelamentos",
                "title": "💳 Parcelamentos (Visão Detalhada)",
                "content": "Acompanhe e gerencie todas as suas compras parceladas ativas agrupadas por forma de pagamento. Você pode expandir cada compra para ver as parcelas, editar valores de parcelas individuais e empurrar ou puxar vencimentos."
            },
            {
                "tab": "assistente",
                "title": "🤖 Assistente Financeiro IA",
                "content": "Seu consultor inteligente integrado! Faça perguntas sobre seus investimentos, peça conselhos de economia baseados nos seus gastos ou solicite resumos financeiros mensais diretamente no chat."
            },
            {
                "tab": "configuracoes",
                "title": "⚙️ Configurações do Sistema",
                "content": "No menu de configurações você gerencia seus bancos de dados (efetuando exportações de backup), perfis familiares e categorias personalizadas. Você também pode buscar atualizações ou reiniciar este tutorial."
            }
        ]
        
        step_idx = [0]
        
        def fechar_tutorial(sucesso=True):
            db.set_preferencia("tutorial_v2_shown", "True")
            page.pop_dialog()
            navegar_para_aba("configuracoes")
            
            msg = "Tutorial concluído com sucesso!" if sucesso else "Tour pulado. Você pode iniciá-lo quando quiser nas Configurações."
            page.snack_bar = ft.SnackBar(
                content=ft.Text(msg, color=get_colors()["text"]),
                bgcolor="#22c55e" if sucesso else "#334155"
            )
            page.snack_bar.open = True
            page.update()
            
        def ir_para_passo(idx):
            step_idx[0] = idx
            step_data = steps[idx]
            navegar_para_aba(step_data["tab"])
            
            dlg_title.value = step_data["title"]
            dlg_content.value = step_data["content"]
            dlg_step_indicator.value = f"Passo {idx + 1} de {len(steps)}"
            
            if idx == len(steps) - 1:
                btn_next.text = "CONCLUIR"
                btn_next.on_click = lambda e: fechar_tutorial(True)
            else:
                btn_next.text = "PRÓXIMO"
                btn_next.on_click = lambda e, next_idx=idx+1: ir_para_passo(next_idx)
                
            if tour_dialog in page._dialogs.controls:
                tour_dialog.update()
            else:
                page.show_dialog(tour_dialog)

        dlg_title = ft.Text("", size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
        dlg_content = ft.Text("", size=12, color=get_colors()["subtext"])
        dlg_step_indicator = ft.Text("", size=10, color="#64748b", weight=ft.FontWeight.W_500)
        
        btn_skip = ft.TextButton("PULAR TOUR", on_click=lambda e: fechar_tutorial(False))
        btn_next = ft.ElevatedButton("PRÓXIMO", bgcolor="#3b82f6", color="white")
        
        dialog_content = ft.Container(
            padding=10,
            width=420,
            content=ft.Column([
                dlg_content,
                ft.Container(height=10),
                ft.Row([
                    dlg_step_indicator,
                    ft.Row([
                        btn_skip,
                        btn_next
                    ], spacing=10)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], tight=True)
        )
        
        tour_dialog = ft.AlertDialog(
            modal=True,
            title=dlg_title,
            content=dialog_content,
            bgcolor=get_colors()["surface"]
        )
        
        if primeira_vez:
            def aceitou_tour(e):
                page.pop_dialog()
                ir_para_passo(0)
                
            welcome_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Bem-vindo ao Sentinel Finance!", size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                content=ft.Container(
                    width=420,
                    content=ft.Column([
                        ft.Text(
                            "Identificamos que esta é a primeira execução da versão V2 do Sentinel Finance. "
                            "Gostaria de fazer um rápido tour guiado interativo para conhecer os novos módulos e funcionalidades do aplicativo?",
                            size=12, color=get_colors()["subtext"]
                        ),
                        ft.Container(height=15),
                        ft.Row([
                            ft.TextButton("NÃO, OBRIGADO", on_click=lambda e: fechar_tutorial(False)),
                            ft.ElevatedButton("INICIAR TOUR", bgcolor="#22c55e", color="white", on_click=aceitou_tour)
                        ], alignment=ft.MainAxisAlignment.END, spacing=10)
                    ], tight=True)
                ),
                bgcolor=get_colors()["surface"]
            )
            page.show_dialog(welcome_dialog)
        else:
            ir_para_passo(0)

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
        controls=[]
    )
    
    page.add(overlay_stack)
    render_dashboard()
    overlay_stack.controls = [main_row]
    # Aplica a cor do tema na barra lateral no carregamento inicial
    colors = get_colors()
    sidebar.bgcolor = colors["sidebar"]
    page.update()

    # Exibe caixa de diálogo de tutorial na primeira abertura do app pós-instalação
    try:
        first_run = db.get_preferencia("tutorial_v2_shown", "False")
        if first_run == "False":
            iniciar_tutorial_usuario(primeira_vez=True)
    except Exception as ex:
        print(f"Erro ao verificar primeira execução do tutorial: {ex}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ft.run(main, assets_dir=base_dir)
