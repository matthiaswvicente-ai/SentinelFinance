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
# Referência global para o ícone de bandeja (system tray)
# Referência global para o ícone de bandeja (system tray)
tray_icon = None

def shift_months(date_str, offset):
    if not offset or offset == 0:
        return date_str
    try:
        dt = datetime.datetime.strptime(date_str, "%d/%m/%Y")
        mes = dt.month + offset
        ano = dt.year + (mes - 1) // 12
        mes = (mes - 1) % 12 + 1
        dia = min(dt.day, 28)
        return datetime.datetime(ano, mes, dia).strftime("%d/%m/%Y")
    except Exception:
        return date_str

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
    
    TRANSLATIONS = {
        "en": {
            "Dashboard": "Dashboard",
            "Investimentos": "Investments",
            "Gráficos": "Charts",
            "Transações": "Transactions",
            "Cartões": "Cards",
            "Assistente IA": "AI Assistant",
            "Configurações": "Settings",
            "Banco de Dados": "Database",
            "Perfis Familiares": "Family Profiles",
            "Categorias": "Categories",
            "Contrato Legal": "Legal Agreement",
            "Atualizações": "Updates",
            "Tutorial e FAQ": "Tutorial & FAQ",
            "Receitas": "Incomes",
            "Despesas": "Expenses",
            "Saldo Líquido": "Net Balance",
            "Limite Utilizado": "Used Limit",
            "Saldo Total": "Total Balance",
            "Investido": "Invested",
            "Despesas do Mês": "Month's Expenses",
            "Receitas do Mês": "Month's Incomes",
            "Despesas por Categoria": "Expenses by Category",
            "Receitas por Categoria": "Incomes by Category",
            "Sem dados de despesas": "No expense data",
            "Módulo": "Module",
            "Faturas dos Cartões": "Card Statements",
            "Backup Manual do Banco de Dados": "Manual Database Backup",
            "Exportar uma cópia de segurança do banco de dados para um local de sua escolha.": "Export a backup copy of the database to a location of your choice.",
            "EXPORTAR BACKUP": "EXPORT BACKUP",
            "Membros da Família (Perfis)": "Family Members (Profiles)",
            "Novo Membro da Família": "New Family Member",
            "Nome do Novo Perfil": "New Profile Name",
            "Por favor, preencha o nome do perfil!": "Please fill in the profile name!",
            "Perfil cadastrado com sucesso!": "Profile registered successfully!",
            "Confirmar Exclusão": "Confirm Deletion",
            "Excluir esta operação permanentemente?": "Permanently delete this operation?",
            "CANCELAR": "CANCEL",
            "EXCLUIR": "DELETE",
            "Excluir este perfil permanentemente?": "Delete this profile permanently?",
            "Excluir": "Delete",
            "Temas Claro/Escuro": "Light/Dark Themes",
            "Idioma": "Language",
            "Português": "Portuguese",
            "Inglês": "English",
            "Alemão": "German",
            "Espanhol": "Spanish",
            "Tema do Aplicativo": "App Theme",
            "Tema Escuro": "Dark Theme",
            "Tema Claro": "Light Theme",
            "Banco de Dados & Preferências": "Database & Preferences",
            "Tema e Idioma": "Theme & Language",
            "Altere o tema visual e o idioma do aplicativo. Algumas alterações exigem o recarregamento da tela.": "Change the visual theme and language of the application. Some changes require reloading the view.",
            "INICIAR TUTORIAL GUIADO": "START GUIDED TUTORIAL",
            "PULAR TOUR": "SKIP TOUR",
            "PRÓXIMO": "NEXT",
            "CONCLUIR": "FINISH",
            "INICIAR TOUR": "START TOUR",
            "Bem-vindo ao Sentinel Finance!": "Welcome to Sentinel Finance!",
            "Identificamos que esta é a primeira execução da versão V2 do Sentinel Finance. Gostaria de fazer um rápido tour guiado interativo para conhecer os novos módulos e funcionalidades do aplicativo?": "We detected this is the first run of Sentinel Finance V2. Would you like to take a quick interactive guided tour to explore the new modules and features of the application?",
            "NÃO, OBRIGADO": "NO, THANKS",
            "Tutorial concluído com sucesso!": "Tutorial completed successfully!",
            "Tour pulado. Você pode iniciá-lo quando quiser nas Configurações.": "Tour skipped. You can start it anytime in the Settings.",
            "Passo": "Step",
            "de": "of",
            "Ativo": "Asset",
            "Quantidade": "Quantity",
            "Preço Médio": "Average Price",
            "Cotação Atual": "Current Price",
            "Saldo Atual": "Current Balance",
            "Valorização": "Appreciation",
            "Dividendos Projetados": "Projected Dividends",
            "Ações": "Stocks",
            "Fundos Imobiliários": "Real Estate Funds",
            "Renda Fixa": "Fixed Income",
            "Gastos por Pilar": "Spending by Pillar",
            "Gastos por Categoria": "Spending by Category",
            "Resumo Mensal": "Monthly Summary",
            "Módulo: Assistente IA": "Module: AI Assistant",
            "Em desenvolvimento...": "In development...",
            "Visualização Geral": "General Overview",
            "Investimentos Cadastrados": "Registered Investments",
            "Nova Operação": "New Operation",
            "Ticker (Código)": "Ticker (Code)",
            "Tipo": "Type",
            "Operação": "Operation",
            "Preço Unitário": "Unit Price",
            "Data da Compra/Venda": "Purchase/Sale Date",
            "Corretora": "Broker",
            "Observações (Opcional)": "Notes (Optional)",
            "SALVAR": "SAVE",
            "Compra": "Buy",
            "Venda": "Sell",
            "Descrição": "Description",
            "Valor": "Value",
            "Data": "Date",
            "Categoria": "Category",
            "Perfil": "Profile",
            "Adicionar Transação": "Add Transaction",
            "Adicionar Entrada": "Add Income",
            "Adicionar Saída": "Add Expense",
            "Dia": "Day",
            "Mês": "Month",
            "Ano": "Year",
            "Filtrar por Perfil": "Filter by Profile",
            "Filtrar por Categoria": "Filter by Category",
            "Todos": "All",
            "Filtros Rápidos": "Quick Filters",
            "Limpar Filtros": "Clear Filters",
            "Histórico de Lançamentos": "Transaction History",
            "Nome do Cartão": "Card Name",
            "Limite": "Limit",
            "Dia de Fechamento": "Closing Day",
            "Dia de Vencimento": "Due Day",
            "Dono do Cartão": "Card Owner",
            "Bandeira": "Flag",
            "Adicionar Cartão": "Add Card",
            "Limpar": "Clear",
            "Cartões Cadastrados": "Registered Cards",
            "Vencimento": "Due Date",
            "Fechamento": "Closing",
            "Limites dos Cartões": "Card Limits",
            "Tutorial e Perguntas Frequentes (FAQ)": "Tutorial & Frequently Asked Questions (FAQ)",
            "Precisa de ajuda para entender como o Sentinel Finance funciona? Clique abaixo para iniciar um tour guiado interativo:": "Need help understanding how Sentinel Finance works? Click below to start an interactive guided tour:",
            "Guia Rápido dos Módulos (FAQ):": "Quick Guide to Modules (FAQ):",
            "Configurações Gerais": "General Settings",
            "Idioma alterado com sucesso! Recarregando...": "Language changed successfully! Reloading...",
            "Simulação de IR": "Income Tax Simulation",
            "ATIVADA": "ENABLED",
            "DESATIVADA": "DISABLED",
            "Janeiro": "January",
            "Fevereiro": "February",
            "Março": "March",
            "Abril": "April",
            "Maio": "May",
            "Junho": "June",
            "Julho": "July",
            "Agosto": "August",
            "Setembro": "September",
            "Outubro": "October",
            "Novembro": "November",
            "Dezembro": "December",
            "Cadastrar Novo Cartão": "Register New Card",
            "Editar Cartão": "Edit Card",
            "Limite Total (R$)": "Total Limit (R$)",
            "Dia do Fechamento": "Closing Day",
            "Dia do Vencimento": "Due Day",
            "Últimos 4 Dígitos": "Last 4 Digits",
            "Cartão excluído com sucesso!": "Card deleted successfully!",
            "Erro ao excluir:": "Error deleting:",
            "CONFIRMAR EXCLUSÃO ⚠️": "CONFIRM DELETION ⚠️",
            "Deseja realmente excluir permanentemente este lançamento?": "Do you really want to permanently delete this entry?",
            "CONFIRMAR EXCLUSÃO": "CONFIRM DELETION",
            "Excluir este cartão permanentemente?": "Delete this card permanently?",
            "Lançamento salvo com sucesso!": "Entry saved successfully!",
            "adicionada com sucesso!": "added successfully!",
            "Erro ao salvar:": "Error saving:",
            "Por favor, preencha a descrição, valor e data!": "Please fill in the description, value, and date!",
            "Valor inválido!": "Invalid value!",
            "Habilitar Edição (Destravar)": "Enable Editing (Unlock)",
            "Concluir Edição (Bloquear)": "Finish Editing (Lock)",
            "Visualização ativa. Clique no cadeado dourado no topo para destravar a edição! 🔓🔒": "Viewing mode active. Click the golden padlock at the top to unlock editing! 🔓🔒",
            "Dividido 👥": "Split 👥",
            "💰 Saldo Disponível": "💰 Available Balance",
            "📊 Patrimônio (Custo)": "📊 Equity (Cost)",
            "💎 Valor de Mercado": "💎 Market Value",
            "🎯 Dividendos do Mês": "🎯 Month's Dividends",
            "Carteira vazia": "Empty portfolio",
            "Clique em \"Nova Operação\" para registrar sua primeira compra.": "Click on \"New Operation\" to register your first purchase.",
            "INVESTIMENTO": "INVESTMENT",
            "RECEITA": "INCOME",
            "DESPESA": "EXPENSE",
            "Valor (R$)": "Value (R$)",
            "Data (DD/MM/AAAA)": "Date (DD/MM/YYYY)",
            "Observação (Opcional)": "Observation (Optional)",
            "Tipo de Lançamento": "Entry Type",
            "Membro da Família": "Family Member",
            "Lançar Nova Despesa": "Log New Expense",
            "Lançar Nova Receita": "Log New Income",
            "Novo Lançamento de Investimento": "New Investment Entry",
            "✏️ Editar Despesa": "✏️ Edit Expense",
            "✏️ Editar Receita": "✏️ Edit Income",
            "✏️ Editar Investimento": "✏️ Edit Investment",
            "Despesa 🔴": "Expense 🔴",
            "Receita 🟢": "Income 🟢",
            "Aporte 🔵": "Contribution 🔵",
            "Novo Lançamento": "New Entry",
            "Fechar": "Close",
            "CARTEIRA": "PORTFOLIO",
            "RENDIMENTOS": "EARNINGS",
            "COTAÇÕES EM TEMPO REAL": "REAL-TIME QUOTES",
            "MENSAL": "MONTHLY",
            "ANUAL": "ANNUAL",
            "POR PILAR & CATEGORIA": "BY PILLAR & CATEGORY",
            "HISTÓRICO COMPLETO": "COMPLETE HISTORY",
            "Simular IR nas vendas": "Simulate IR on sales",
            "IR: Isento": "IR: Exempt",
            "Est. IR:": "Est. IR:",
            "NOVA OPERAÇÃO": "NEW OPERATION",
            "SALVAR OPERAÇÃO": "SAVE OPERATION",
            "Tesouro Selic (Pós-fixado)": "Treasury Selic (Post-fixed)",
            "Tesouro Prefixado (Pré-fixado)": "Treasury Prefix (Pre-fixed)",
            "Tesouro IPCA+ (Híbrido)": "Treasury IPCA+ (Hybrid)",
            "Outros": "Others",
            "Posição Inicial Consolidada": "Consolidated Initial Position",
            "Preço Unitário (R$)": "Unit Price (R$)",
            "Preço Médio Existente (R$)": "Existing Average Price (R$)",
            "Disponível para venda:": "Available for sale:",
            "Aviso: Você não possui o ativo": "Warning: You do not own the asset",
            "Selecione a Categoria do Tesouro": "Select Treasury Category",
            "Quantidade deve ser > 0": "Quantity must be > 0",
            "Preço deve ser > 0": "Price must be > 0",
            "Ticker obrigatório": "Ticker required",
            "Quantidade inválida": "Invalid quantity",
            "Preço inválido": "Invalid price",
            "Quantidade máxima de venda permitida:": "Maximum allowed sale quantity:",
            "Percentual do CDI deve ser > 0": "CDI percentage must be > 0",
            "Percentual do CDI inválido": "Invalid CDI percentage",
            "Saldo Inicial Consolidado": "Consolidated Initial Balance",
            "Posição inicial consolidada": "Consolidated initial position",
            "✏️ Editar Operação": "✏️ Edit Operation",
            "📈 Nova Operação": "📈 New Operation",
            "Top 5 Despesas": "Top 5 Expenses",
            "Sem dados no mês": "No data this month",
            "Sem receitas": "No incomes",
            "Sem fluxo": "No cash flow",
            "Aviso: Você não possui o ativo na carteira!": "Warning: You do not own the asset in your portfolio!",
            "Novas Operações": "New Operations",
            "Subcategoria": "Subcategory",
            "Pilar da Despesa": "Expense Pillar",
            "Método de Pagamento": "Payment Method",
            "Selecione o Cartão": "Select Card",
            "Parcelas": "Installments",
            "Dividir despesa com a família": "Split expense with family",
            "Tipo de Divisão": "Division Type",
            "Nome do novo membro": "New member name",
            "POR FORMA DE PAGAMENTO": "BY PAYMENT METHOD",
            "Nenhuma transação encontrada": "No transactions found",
            "Os lançamentos deste período aparecerão aqui.": "Entries for this period will appear here.",
            "DESPESAS GERAIS": "GENERAL EXPENSES",
            "Nenhuma despesa neste período.": "No expenses in this period.",
            "RECEITAS & APORTES": "INCOMES & CONTRIBUTIONS",
            "Nenhuma receita ou aporte neste período.": "No income or contributions in this period.",
            "Não especificado": "Not specified",
            "Cartão de Crédito": "Credit Card",
            "CARTÕES DE CRÉDITO": "CREDIT CARDS",
            "Sem gastos no cartão neste período.": "No card expenses in this period.",
            "OUTRAS FORMAS DE PAGAMENTO": "OTHER PAYMENT METHODS",
            "Sem outros gastos neste período.": "No other expenses in this period.",
            "💳 Detalhes do Cartão": "💳 Card Details",
            "Igualitária": "Equal",
            "Individual": "Individual",
            "Despesa Variável": "Variable Expense",
            "Despesa Fixa": "Fixed Expense",
            "Receita Fixa": "Fixed Income",
            "Receita Variável": "Variable Income",
            "Investimento": "Investment",
            "Dinheiro": "Cash",
            "Pix": "Pix",
            "Boleto": "Boleto",
            "Cartão": "Card",
            "Rendimentos de Ações": "Stock Earnings",
            "Rendimentos de FIIs": "FII Earnings",
            "Pago": "Paid",
            "Provisionado": "Provisioned",
            "Ticker / FII": "Ticker / FII",
            "Ex: PETR4, MXRF11": "Ex: PETR4, MXRF11",
            "Tipo de Rendimento": "Earnings Type",
            "Valor Total (R$)": "Total Value (R$)",
            "Ex: 150.50": "Ex: 150.50",
            "Status": "Status",
            "Ticker / Nome do Ativo": "Ticker / Asset Name",
            "Ex: PETR4, MXRF11, CDB XP": "Ex: PETR4, MXRF11, CDB XP",
            "Tipo de Ativo": "Asset Type",
            "Ex: 100": "Ex: 100",
            "Ex: 36.50": "Ex: 36.50",
            "Corretora (Opcional)": "Broker (Optional)",
            "Ex: XP, Rico, Clear": "Ex: XP, Rico, Clear",
            "Vencimento (Desabilitado)": "Maturity (Disabled)",
            "Vencimento (DD/MM/AAAA) (Opcional)": "Maturity (DD/MM/YYYY) (Optional)",
            "Ex: 31/12/2028": "Ex: 31/12/2028",
            "Liquidez Diária": "Daily Liquidity",
            "Percentual do CDI (%) (Opcional)": "CDI Percentage (%) (Optional)",
            "Ex: 110": "Ex: 110",
            "Categoria do Tesouro": "Treasury Category",
            "Pai Root": "Root Parent",
            "Por favor, digite o nome da categoria!": "Please type the category name!",
            "Categoria adicionada com sucesso!": "Category added successfully!",
            "ADICIONAR CATEGORIA": "ADD CATEGORY",
            "Categoria excluída com sucesso!": "Category deleted successfully!",
            "Ex: Filho, Cônjuge": "Ex: Son, Spouse",
            "CADASTRAR PERFIL": "REGISTER PROFILE",
            "Excluir Perfil": "Delete Profile",
            "Nova Categoria": "New Category",
            "Nome": "Name",
            "Categoria Pai": "Parent Category",
            "Erro:": "Error:",
            "Ação": "Stock",
            "FII": "FII",
            "ETF": "ETF",
            "Tesouro": "Treasury",
            "CDB": "CDB",
            "Cripto": "Crypto",
            "Categorias e Subcategorias": "Categories and Subcategories",
            "Contrato Legal e Termos de Uso": "Legal Agreement and Terms of Use",
            "O Dashboard apresenta o resumo consolidado do mês ativo. Ele exibe suas Receitas, Despesas, Saldo Líquido e o total de limite utilizado em seus cartões. Os gráficos circulares na parte inferior mostram a distribuição de gastos por Pilar e por Categoria. Você pode navegar entre os meses e anos usando as setas de navegação no topo da página.": "The Dashboard displays a consolidated summary of the active month. It shows your Incomes, Expenses, Net Balance, and total credit card limits used. The pie charts at the bottom show the distribution of spending by Pillar and Category. You can navigate between months and years using the arrows at the top.",
            "Nesta aba, você cadastra suas Ações e Fundos Imobiliários. O sistema calcula a cotação média de compra e busca a cotação de mercado atualizada (via API pública do Yahoo Finance) para mostrar a valorização e o saldo total da sua carteira. Além disso, calcula uma estimativa de dividendos projetados com base nos últimos proventos distribuídos.": "In this tab, you register your Stocks and Real Estate Funds (FIIs). The system calculates the average purchase price and fetches current market quotes (via Yahoo Finance API) to display the appreciation and total balance of your portfolio. It also estimates projected dividends based on recent distributions.",
            "Apresenta uma visão analítica e comparativa detalhada da evolução financeira mensal. Útil para identificar padrões de consumo e tendências ao longo do tempo.": "Presents a detailed analytical and comparative view of monthly financial evolution. Useful for identifying consumption patterns and trends over time.",
            "Aqui você realiza os lançamentos diários de despesas e receitas. É possível filtrar as transações de forma detalhada por Mês, Ano, Perfil Familiar (Membros) e Categorias. O sistema permite travar transações para evitar edições acidentais.": "Here you log your daily income and expense entries. You can filter transactions in detail by Month, Year, Family Profile (Members), and Categories. The system allows locking transactions to prevent accidental edits.",
            "O Sentinel Finance suporta múltiplos perfis na mesma base. Você pode cadastrar dependentes ou cônjuges para separar as despesas de cada membro da família. Na aba de Categorias, você gerencia e cria subcategorias personalizadas para o seu controle financeiro.": "Sentinel Finance supports multiple profiles on the same database. You can register dependents or spouses to separate each family member's expenses. In the Categories tab, you manage and create custom subcategories.",
            "Todos os seus dados são guardados localmente no seu computador em um banco de dados SQLite (arquivo financas.db). Nenhuma informação financeira é enviada a servidores externos. Recomendamos exportar cópias de segurança periodicamente através do botão de 'Exportar Backup' na aba de Banco de Dados.": "All your data is stored locally on your computer in an SQLite database (financas.db file). No financial information is sent to external servers. We recommend exporting backups periodically using the 'Export Backup' button in the Database tab.",
            "📊 Dashboard (Painel Geral)": "📊 Dashboard (General Panel)",
            "📈 Investimentos (Carteira)": "📈 Investments (Portfolio)",
            "🎨 Gráficos Comparativos": "🎨 Comparative Charts",
            "📝 Transações e Lançamentos": "📝 Transactions and Entries",
            "👥 Perfis Familiares e Categorias": "👥 Family Profiles & Categories",
            "💾 Backup e Privacidade Absoluta": "💾 Backup & Absolute Privacy",
            "Anotações do Subperfil": "Sub-profile Notes",
            "Digite aqui suas anotações para este subperfil (compras futuras, mudanças de valores, etc.)...": "Enter your notes for this sub-profile here (future purchases, value changes, etc.)...",
            "Histórico de Backups de Sessão": "Session Backups History",
            "Os backups são gerados automaticamente cada vez que o aplicativo é iniciado. Eles são mantidos por no máximo 7 dias para permitir a reversão de alterações indesejadas.": "Backups are generated automatically each time the application is started. They are kept for a maximum of 7 days to allow reverting undesired changes.",
            "Reverter": "Revert",
            "Excluir Backup": "Delete Backup",
            "Nenhum backup de sessão disponível no momento.": "No session backups currently available.",
            "CONFIRMAR RESTAURAÇÃO ⚠️": "CONFIRM RESTORATION ⚠️",
            "Deseja realmente reverter as alterações para esta sessão? Todos os dados gravados após este backup serão substituídos.": "Are you sure you want to revert changes to this session? All data saved after this backup will be replaced.",
            "Alterações revertidas com sucesso! Recarregando...": "Changes reverted successfully! Reloading...",
            "Backup de sessão excluído com sucesso!": "Session backup deleted successfully!",
            "Backup": "Backup",
            "Abatimento excluído/revertido com sucesso!": "Amortization deleted/reverted successfully!",
            "Deseja realmente excluir ou reverter este abatimento?": "Are you sure you want to delete or revert this amortization?",
            "REVERTER": "REVERT",
            "Erro ao excluir": "Error deleting",
            "Mês": "Month",
            "Usado": "Used",
            "Resumo Anual": "Annual Summary",
            "Soma dos Selecionados (Absoluto):": "Sum of Selected (Absolute):",
            "Selecione os cards para consolidar e somar seus totais anuais:": "Select the cards to consolidate and sum their annual totals:",
            "Saldo Inicial": "Initial Balance",
            "Saldo inicial atualizado com sucesso!": "Initial balance updated successfully!",
            "Por favor, digite um valor numérico válido!": "Please enter a valid numeric value!"
        },
        "de": {
            "Dashboard": "Dashboard",
            "Investimentos": "Investitionen",
            "Gráficos": "Diagramme",
            "Transações": "Transaktionen",
            "Cartões": "Karten",
            "Assistente IA": "KI-Assistent",
            "Configurações": "Einstellungen",
            "Banco de Dados": "Datenbank",
            "Perfis Familiares": "Familienprofile",
            "Categorias": "Kategorien",
            "Contrato Legal": "Rechtliche Vereinbarung",
            "Atualizações": "Updates",
            "Tutorial e FAQ": "Tutorial & FAQ",
            "Receitas": "Einnahmen",
            "Despesas": "Ausgaben",
            "Saldo Líquido": "Netto-Saldo",
            "Limite Utilizado": "Genutztes Limit",
            "Saldo Total": "Gesamtsaldo",
            "Investido": "Investiert",
            "Despesas do Mês": "Monatliche Ausgaben",
            "Receitas do Mês": "Monatliche Einnahmen",
            "Despesas por Categoria": "Ausgaben nach Kategorie",
            "Receitas por Categoria": "Einnahmen nach Kategorie",
            "Sem dados de despesas": "Keine Ausgabendaten",
            "Módulo": "Modul",
            "Faturas dos Cartões": "Kartenabrechnungen",
            "Backup Manual do Banco de Dados": "Manuelles Datenbank-Backup",
            "Exportar uma cópia de segurança do banco de dados para um local de sua escolha.": "Exportieren Sie eine Sicherungskopie der Datenbank an einen Ort Ihrer Wahl.",
            "EXPORTAR BACKUP": "BACKUP EXPORTIEREN",
            "Membros da Família (Perfis)": "Familienmitglieder (Profile)",
            "Novo Membro da Família": "Neues Familienmitglied",
            "Nome do Novo Perfil": "Name des neuen Profils",
            "Por favor, preencha o nome do perfil!": "Bitte füllen Sie den Profilnamen aus!",
            "Perfil cadastrado com sucesso!": "Profil erfolgreich registriert!",
            "Confirmar Exclusão": "Löschen bestätigen",
            "Excluir esta operação permanentemente?": "Diese Operation dauerhaft löschen?",
            "CANCELAR": "ABBRECHEN",
            "EXCLUIR": "LÖSCHEN",
            "Excluir este perfil permanentemente?": "Dieses Profil dauerhaft löschen?",
            "Excluir": "Löschen",
            "Temas Claro/Escuro": "Helle/Dunkle Themen",
            "Idioma": "Sprache",
            "Português": "Portugiesisch",
            "Inglês": "Englisch",
            "Alemão": "Deutsch",
            "Espanhol": "Spanisch",
            "Tema do Aplicativo": "App-Thema",
            "Tema Escuro": "Dunkles Thema",
            "Tema Claro": "Helles Thema",
            "Banco de Dados & Preferências": "Datenbank & Einstellungen",
            "Tema e Idioma": "Thema & Sprache",
            "Altere o tema visual e o idioma do aplicativo. Algumas alterações exigem o recarregamento da tela.": "Ändern Sie das visuelle Thema und die Sprache der Anwendung. Einige Änderungen erfordern das Neuladen der Ansicht.",
            "INICIAR TUTORIAL GUIADO": "GUIDED TUTORIAL STARTEN",
            "PULAR TOUR": "TOUR ÜBERSPRINGEN",
            "PRÓXIMO": "WEITER",
            "CONCLUIR": "ABSCHLIESSEN",
            "INICIAR TOUR": "TOUR STARTEN",
            "Bem-vindo ao Sentinel Finance!": "Willkommen bei Sentinel Finance!",
            "Identificamos que esta é a primeira execução da versão V2 do Sentinel Finance. Gostaria de fazer um rápido tour guiado interativo para conhecer os novos módulos e funcionalidades do aplicativo?": "Wir haben festgestellt, dass dies der erste Start von Sentinel Finance V2 is. Möchten Sie eine kurze interaktive Führung machen, um die neuen Module und Funktionen der Anwendung kennenzulernen?",
            "NÃO, OBRIGADO": "NEIN, DANKE",
            "Tutorial concluído com sucesso!": "Tutorial erfolgreich abgeschlossen!",
            "Tour pulado. Você pode iniciá-lo quando quiser nas Configurações.": "Tour übersprungen. Sie können sie jederzeit in den Einstellungen starten.",
            "Passo": "Schritt",
            "de": "von",
            "Ativo": "Anlage",
            "Quantidade": "Menge",
            "Preço Médio": "Durchschnittspreis",
            "Cotação Atual": "Aktueller Kurs",
            "Saldo Atual": "Aktueller Saldo",
            "Valorização": "Wertsteigerung",
            "Dividendos Projetados": "Projizierte Dividenden",
            "Ações": "Aktien",
            "Fundos Imobiliários": "Immobilienfonds",
            "Renda Fixa": "Festverzinslich",
            "Gastos por Pilar": "Ausgaben nach Säule",
            "Gastos por Categoria": "Ausgaben nach Kategorie",
            "Resumo Mensal": "Monatliche Übersicht",
            "Módulo: Assistente IA": "Modul: KI-Assistent",
            "Em desenvolvimento...": "In Entwicklung...",
            "Visualização Geral": "Allgemeine Ansicht",
            "Investimentos Cadastrados": "Registrierte Investitionen",
            "Nova Operação": "Neue Transaktion",
            "Ticker (Código)": "Ticker (Symbol)",
            "Tipo": "Typ",
            "Operação": "Transaktion",
            "Preço Unitário": "Einzelpreis",
            "Data da Compra/Venda": "Kauf-/Verkaufsdatum",
            "Corretora": "Broker",
            "Observações (Opcional)": "Bemerkungen (Optional)",
            "SALVAR": "SPEICHERN",
            "Compra": "Kauf",
            "Venda": "Verkauf",
            "Descrição": "Beschreibung",
            "Valor": "Wert",
            "Data": "Datum",
            "Categoria": "Kategorie",
            "Perfil": "Profil",
            "Adicionar Transação": "Transaktion hinzufügen",
            "Adicionar Entrada": "Einnahme hinzufügen",
            "Adicionar Saída": "Ausgabe hinzufügen",
            "Dia": "Tag",
            "Mês": "Monat",
            "Ano": "Jahr",
            "Filtrar por Perfil": "Nach Profil filtern",
            "Filtrar por Categoria": "Nach Kategorie filtern",
            "Todos": "Alle",
            "Filtros Rápidos": "Schnellfilter",
            "Limpar Filtros": "Filter löschen",
            "Histórico de Lançamentos": "Transaktionsverlauf",
            "Nome do Cartão": "Kartenname",
            "Limite": "Limit",
            "Dia de Fechamento": "Abrechnungstag",
            "Dia de Vencimento": "Fälligkeitstag",
            "Dono do Cartão": "Karteninhaber",
            "Bandeira": "Marke",
            "Adicionar Cartão": "Karte hinzufügen",
            "Limpar": "Löschen",
            "Cartões Cadastrados": "Registrierte Karten",
            "Vencimento": "Fälligkeit",
            "Fechamento": "Schluss",
            "Limites dos Cartões": "Kartenlimits",
            "Tutorial e Perguntas Frequentes (FAQ)": "Tutorial & Häufig gestellte Fragen (FAQ)",
            "Precisa de ajuda para entender como o Sentinel Finance funciona? Clique abaixo para iniciar um tour guiado interativo:": "Benötigen Sie Hilfe beim Verständnis von Sentinel Finance? Klicken Sie unten, um eine interaktive Tour zu starten:",
            "Guia Rápido dos Módulos (FAQ):": "Kurzanleitung zu Modulen (FAQ):",
            "Configurações Gerais": "Allgemeine Einstellungen",
            "Idioma alterado com sucesso! Recarregando...": "Sprache erfolgreich geändert! Wird neu geladen...",
            "Simulação de IR": "Steuersimulation",
            "ATIVADA": "AKTIVIERT",
            "DESATIVADA": "DEAKTIVIERT",
            "Janeiro": "Januar",
            "Fevereiro": "Februar",
            "Março": "März",
            "Abril": "April",
            "Maio": "Mai",
            "Junho": "Juni",
            "Julho": "Juli",
            "Agosto": "August",
            "Setembro": "September",
            "Outubro": "Oktober",
            "Novembro": "November",
            "Dezembro": "Dezember",
            "Cadastrar Novo Cartão": "Neue Karte registrieren",
            "Editar Cartão": "Karte bearbeiten",
            "Limite Total (R$)": "Gesamtlimit (R$)",
            "Dia do Fechamento": "Abrechnungstag",
            "Dia do Vencimento": "Fälligkeitstag",
            "Últimos 4 Dígitos": "Letzte 4 Ziffern",
            "Cartão excluído com sucesso!": "Karte erfolgreich gelöscht!",
            "Erro ao excluir:": "Fehler beim Löschen:",
            "CONFIRMAR EXCLUSÃO ⚠️": "LÖSCHEN BESTÄTIGEN ⚠️",
            "Deseja realmente excluir permanentemente este lançamento?": "Möchten Sie diesen Eintrag wirklich dauerhaft löschen?",
            "CONFIRMAR EXCLUSÃO": "LÖSCHEN BESTÄTIGEN",
            "Excluir este cartão permanentemente?": "Diese Karte dauerhaft löschen?",
            "Lançamento salvo com sucesso!": "Eintrag erfolgreich gespeichert!",
            "adicionada com sucesso!": "erfolgreich hinzugefügt!",
            "Erro ao salvar:": "Fehler beim Speichern:",
            "Por favor, preencha a descrição, valor e data!": "Bitte füllen Sie Beschreibung, Wert und Datum aus!",
            "Valor inválido!": "Ungültiger Wert!",
            "Habilitar Edição (Destravar)": "Bearbeitung aktivieren (Entsperren)",
            "Concluir Edição (Bloquear)": "Bearbeitung abschließen (Sperren)",
            "Visualização ativa. Clique no cadeado dourado no topo para destravar a edição! 🔓🔒": "Ansichtsmodus aktiv. Klicken Sie oben auf das goldene Schloss, um die Bearbeitung freizugeben! 🔓🔒",
            "Dividido 👥": "Aufgeteilt 👥",
            "💰 Saldo Disponível": "💰 Verfügbares Guthaben",
            "📊 Patrimônio (Custo)": "📊 Vermögen (Kosten)",
            "💎 Valor de Mercado": "💎 Marktwert",
            "🎯 Dividendos do Mês": "🎯 Monatliche Dividenden",
            "Carteira vazia": "Leeres Portfolio",
            "Clique em \"Nova Operação\" para registrar sua primeira compra.": "Klicken Sie auf \"Neue Transaktion\", um Ihren ersten Kauf zu registrieren.",
            "INVESTIMENTO": "INVESTITION",
            "RECEITA": "EINNAHME",
            "DESPESA": "AUSGABE",
            "Valor (R$)": "Wert (R$)",
            "Data (DD/MM/AAAA)": "Datum (TT/MM/JJJJ)",
            "Observação (Opcional)": "Bemerkung (Optional)",
            "Tipo de Lançamento": "Transaktionsart",
            "Membro da Família": "Familienmitglied",
            "Lançar Nova Despesa": "Neue Ausgabe buchen",
            "Lançar Nova Receita": "Neue Einnahme buchen",
            "Novo Lançamento de Investimento": "Neue Investitionstransaktion",
            "✏️ Editar Despesa": "✏️ Ausgabe bearbeiten",
            "✏️ Editar Receita": "✏️ Einnahme bearbeiten",
            "✏️ Editar Investimento": "✏️ Investition bearbeiten",
            "Despesa 🔴": "Ausgabe 🔴",
            "Receita 🟢": "Einnahme 🟢",
            "Aporte 🔵": "Beitrag 🔵",
            "Novo Lançamento": "Neuer Eintrag",
            "Fechar": "Schließen",
            "CARTEIRA": "PORTFOLIO",
            "RENDIMENTOS": "ERTRÄGE",
            "COTAÇÕES EM TEMPO REAL": "ECHTZEIT-KURSE",
            "MENSAL": "MONATLICH",
            "ANUAL": "JÄHRLICH",
            "POR PILAR & CATEGORIA": "NACH SÄULE & KATEGORIE",
            "HISTÓRICO COMPLETO": "VOLLSTÄNDIGER VERLAUF",
            "Simular IR nas vendas": "IR bei Verkäufen simulieren",
            "IR: Isento": "IR: Steuerfrei",
            "Est. IR:": "Gesch. IR:",
            "NOVA OPERAÇÃO": "NEUE TRANSAKTION",
            "SALVAR OPERAÇÃO": "TRANSAKTION SPEICHERN",
            "Tesouro Selic (Pós-fixado)": "Schatz Selic (Post-fixed)",
            "Tesouro Prefixado (Pré-fixado)": "Schatz Prefix (Pre-fixed)",
            "Tesouro IPCA+ (Híbrido)": "Schatz IPCA+ (Hybrid)",
            "Outros": "Andere",
            "Posição Inicial Consolidada": "Konsolidierter Anfangsbestand",
            "Preço Unitário (R$)": "Einzelpreis (R$)",
            "Preço Médio Existente (R$)": "Existierender Durchschnittspreis (R$)",
            "Disponível para venda:": "Verfügbar für Verkauf:",
            "Aviso: Você não possui o ativo": "Hinweis: Sie besitzen den Vermögenswert nicht",
            "Selecione a Categoria do Tesouro": "Kategorie der Anleihe wählen",
            "Quantidade deve ser > 0": "Menge muss > 0 sein",
            "Preço deve ser > 0": "Preis muss > 0 sein",
            "Ticker obrigatório": "Ticker erforderlich",
            "Quantidade inválida": "Ungültige Menge",
            "Preço inválido": "Ungültiger Preis",
            "Quantidade máxima de venda permitida:": "Maximal zulässige Verkaufsmenge:",
            "Percentual do CDI deve ser > 0": "CDI-Prozentsatz muss > 0 sein",
            "Percentual do CDI inválido": "Ungültiger CDI-Prozentsatz",
            "Saldo Inicial Consolidado": "Konsolidierter Anfangsbestand",
            "Posição inicial consolidada": "Konsolidierter Anfangsbestand",
            "✏️ Editar Operação": "✏️ Transaktion bearbeiten",
            "📈 Nova Operação": "📈 Neue Transaktion",
            "Top 5 Despesas": "Top 5 Ausgaben",
            "Sem dados no mês": "Keine Daten in diesem Monat",
            "Sem receitas": "Keine Einnahmen",
            "Sem fluxo": "Kein Cashflow",
            "Aviso: Você não possui o ativo na carteira!": "Hinweis: Sie besitzen diesen Vermögenswert nicht im Portfolio!",
            "Novas Operações": "Neue Transaktionen",
            "Subcategoria": "Unterkategorie",
            "Pilar da Despesa": "Ausgabensäule",
            "Método de Pagamento": "Zahlungsmethode",
            "Selecione o Cartão": "Karte auswählen",
            "Parcelas": "Raten",
            "Dividir despesa com a família": "Ausgaben mit der Familie teilen",
            "Tipo de Divisão": "Aufteilungstyp",
            "Nome do novo membro": "Name des neuen Mitglieds",
            "POR FORMA DE PAGAMENTO": "NACH ZAHLUNGSMETHODE",
            "Nenhuma transação encontrada": "Keine Transaktionen gefunden",
            "Os lançamentos deste período aparecerão aqui.": "Einträge für diesen Zeitraum werden hier angezeigt.",
            "DESPESAS GERAIS": "ALLGEMEINE AUSGABEN",
            "Nenhuma despesa neste período.": "Keine Ausgaben in diesem Zeitraum.",
            "RECEITAS & APORTES": "EINNAHMEN & BEITRÄGE",
            "Nenhuma receita ou aporte neste período.": "Keine Einnahmen oder Beiträge in diesem Zeitraum.",
            "Não especificado": "Nicht angegeben",
            "Cartão de Crédito": "Kreditkarte",
            "CARTÕES DE CRÉDITO": "KREDITKARTEN",
            "Sem gastos no cartão neste período.": "Keine Kartenausgaben in diesem Zeitraum.",
            "OUTRAS FORMAS DE PAGAMENTO": "ANDERE ZAHLUNGSMETHODEN",
            "Sem outros gastos neste período.": "Keine sonstigen Ausgaben in diesem Zeitraum.",
            "💳 Detalhes do Cartão": "💳 Kartendetails",
            "Igualitária": "Gleich",
            "Individual": "Individuell",
            "Despesa Variável": "Variable Ausgaben",
            "Despesa Fixa": "Feste Ausgaben",
            "Receita Fixa": "Feste Einnahmen",
            "Receita Variável": "Variable Einnahmen",
            "Investimento": "Investition",
            "Dinheiro": "Bargeld",
            "Pix": "Pix",
            "Boleto": "Boleto",
            "Cartão": "Karte",
            "Rendimentos de Ações": "Aktienerträge",
            "Rendimentos de FIIs": "FII-Erträge",
            "Pago": "Bezahlt",
            "Provisionado": "Rückgestellt",
            "Ticker / FII": "Ticker / FII",
            "Ex: PETR4, MXRF11": "Z.B.: PETR4, MXRF11",
            "Tipo de Rendimento": "Ertragsart",
            "Valor Total (R$)": "Gesamtwert (R$)",
            "Ex: 150.50": "Z.B.: 150.50",
            "Status": "Status",
            "Ticker / Nome do Ativo": "Ticker / Name des Vermögenswerts",
            "Ex: PETR4, MXRF11, CDB XP": "Z.B.: PETR4, MXRF11, CDB XP",
            "Tipo de Ativo": "Anlagetyp",
            "Ex: 100": "Z.B.: 100",
            "Ex: 36.50": "Z.B.: 36.50",
            "Corretora (Opcional)": "Broker (Optional)",
            "Ex: XP, Rico, Clear": "Z.B.: XP, Rico, Clear",
            "Vencimento (Desabilitado)": "Fälligkeit (Deaktiviert)",
            "Vencimento (DD/MM/AAAA) (Opcional)": "Fälligkeit (TT/MM/JJJJ) (Optional)",
            "Ex: 31/12/2028": "Z.B.: 31/12/2028",
            "Liquidez Diária": "Tägliche Liquidität",
            "Percentual do CDI (%) (Opcional)": "CDI-Prozentsatz (%) (Optional)",
            "Ex: 110": "Z.B.: 110",
            "Categoria do Tesouro": "Schatzkategorie",
            "Pai Root": "Hauptkategorie",
            "Por favor, digite o nome da categoria!": "Bitte geben Sie den Kategorienamen ein!",
            "Categoria adicionada com sucesso!": "Kategorie erfolgreich hinzugefügt!",
            "ADICIONAR CATEGORIA": "KATEGORIE HINZUFÜGEN",
            "Categoria excluída com sucesso!": "Kategorie erfolgreich gelöscht!",
            "Ex: Filho, Cônjuge": "Z.B.: Sohn, Ehepartner",
            "CADASTRAR PERFIL": "PROFIL REGISTRIEREN",
            "Excluir Perfil": "Profil löschen",
            "Nova Categoria": "Neue Kategorie",
            "Nome": "Name",
            "Categoria Pai": "Elternkategorie",
            "Erro:": "Fehler:",
            "Ação": "Aktie",
            "FII": "FII",
            "ETF": "ETF",
            "Tesouro": "Schatz",
            "CDB": "CDB",
            "Cripto": "Krypto",
            "Categorias e Subcategorias": "Kategorien und Unterkategorien",
            "Contrato Legal e Termos de Uso": "Nutzungsbedingungen und EULA",
            "O Dashboard apresenta o resumo consolidado do mês ativo. Ele exibe suas Receitas, Despesas, Saldo Líquido e o total de limite utilizado em seus cartões. Os gráficos circulares na parte inferior mostram a distribuição de gastos por Pilar e por Categoria. Você pode navegar entre os meses e anos usando as setas de navegação no topo da página.": "Das Dashboard zeigt eine konsolidierte Zusammenfassung des aktiven Monats. Es zeigt Ihre Einnahmen, Ausgaben, Netto-Saldo und die genutzten Kreditkartenlimits. Die Kreisdiagramme unten zeigen die Verteilung der Ausgaben nach Säule und Kategorie. Sie können mit den Navigationspfeilen oben zwischen Monaten und Jahren wechseln.",
            "Nesta aba, você cadastra suas Ações e Fundos Imobiliários. O sistema calcula a cotação média de compra e busca a cotação de mercado atualizada (via API pública do Yahoo Finance) para mostrar a valorização e o saldo total da sua carteira. Além disso, calcula uma estimativa de dividendos projetados com base nos últimos proventos distribuídos.": "In diesem Reiter registrieren Sie Ihre Aktien und Immobilienfonds (FIIs). Das System berechnet den durchschnittlichen Kaufpreis und ruft aktuelle Marktkurse (über die Yahoo Finance API) ab, um die Wertsteigerung und den Gesamtsaldo Ihres Portfolios anzuzeigen. Es schätzt auch die projizierten Dividenden basierend auf den letzten Ausschüttungen.",
            "Apresenta uma visão analítica e comparativa detalhada da evolução financeira mensal. Útil para identificar padrões de consumo e tendências ao longo do tempo.": "Bietet eine detaillierte analytische und vergleicheichende Sicht auf die monatliche finanzielle Entwicklung. Hilfreich, um Konsummuster und Trends im Zeitverlauf zu erkennen.",
            "Aqui você realiza os lançamentos diários de despesas e receitas. É possível filtrar as transações de forma detalhada por Mês, Ano, Perfil Familiar (Membros) e Categorias. O sistema permite travar transações para evitar edições acidentais.": "Hier erfassen Sie Ihre täglichen Einnahmen- und Ausgabeneinträge. Sie können Transaktionen detailliert nach Monat, Jahr, Familienprofil (Mitglieder) und Kategorien filtern. Das System ermöglicht das Sperren von Transaktionen, um versehentliche Bearbeitungen zu verhindern.",
            "O Sentinel Finance suporta múltiplos perfis na mesma base. Você pode cadastrar dependentes ou cônjuges para separar as despesas de cada membro da família. Na aba de Categorias, você gerencia e cria subcategorias personalizadas para o seu controle financeiro.": "Sentinel Finance unterstützt mehrere Profile in derselben Datenbank. Sie können Angehörige oder Ehepartner registrieren, um die Ausgaben jedes Familienmitglieds zu trennen. Im Reiter Kategorien können Sie benutzerdefinierte Unterkategorien verwalten und erstellen.",
            "Todos os seus dados são guardados localmente no seu computador em um banco de dados SQLite (arquivo financas.db). Nenhuma informação financeira é enviada a servidores externos. Recomendamos exportar cópias de segurança periodicamente através do botão de 'Exportar Backup' na aba de Banco de Dados.": "Alle Ihre Daten werden lokal auf Ihrem Computer in einer SQLite-Datenbank (Datei financas.db) gespeichert. Es werden keine Finanzdaten an externe Server gesendet. Wir empfehlen, regelmäßig Sicherungskopien über die Schaltfläche 'Backup exportieren' zu erstellen.",
            "📊 Dashboard (Painel Geral)": "📊 Dashboard (Allgemeines Panel)",
            "📈 Investimentos (Carteira)": "📈 Investitionen (Portfolio)",
            "🎨 Gráficos Comparativos": "🎨 Vergleichende Diagramme",
            "📝 Transações e Lançamentos": "📝 Transaktionen und Einträge",
            "👥 Perfis Familiares e Categorias": "👥 Familienprofile & Kategorien",
            "💾 Backup e Privacidade Absoluta": "💾 Backup & Absolute Privatsphäre",
            "Histórico de Backups de Sessão": "Verlauf der Sitzungs-Backups",
            "Os backups são gerados automaticamente cada vez que o aplicativo é iniciado. Eles são mantidos por no máximo 7 dias para permitir a reversão de alterações indesejadas.": "Backups werden automatisch bei jedem Start der Anwendung erstellt. Sie werden maximal 7 Tage aufbewahrt, um unerwünschte Änderungen rückgängig zu machen.",
            "Reverter": "Rückgängig machen",
            "Excluir Backup": "Backup löschen",
            "Nenhum backup de sessão disponível no momento.": "Derzeit sind keine Sitzungs-Backups verfügbar.",
            "CONFIRMAR RESTAURAÇÃO ⚠️": "WIEDERHERSTELLUNG BESTÄTIGEN ⚠️",
            "Deseja realmente reverter as alterações para esta sessão? Todos os dados gravados após este backup serão substituídos.": "Möchten Sie die Änderungen für diese Sitzung wirklich rückgängig machen? Alle nach diesem Backup gespeicherten Daten werden überschrieben.",
            "Alterações revertidas com sucesso! Recarregando...": "Änderungen erfolgreich rückgängig gemacht! Wird neu geladen...",
            "Backup de sessão excluído com sucesso!": "Sitzungs-Backup erfolgreich gelöscht!",
            "Backup": "Sicherung",
            "Anotações do Subperfil": "Notizen des Subprofils",
            "Digite aqui suas anotações para este subperfil (compras futuras, mudanças de valores, etc.)...": "Geben Sie hier Ihre Notizen für dieses Subprofil ein (zukünftige Einkäufe, Wertänderungen usw.)...",
            "Abatimento excluído/revertido com sucesso!": "Tilgung erfolgreich gelöscht/rückgängig gemacht!",
            "CONFIRMAR EXCLUSÃO ⚠️": "LÖSCHEN BESTÄTIGEN ⚠️",
            "Deseja realmente excluir ou reverter este abatimento?": "Möchten Sie diese Tilgung wirklich löschen oder rückgängig machen?",
            "REVERTER": "RÜCKGÄNGIG MACHEN",
            "Erro ao excluir": "Fehler beim Löschen",
            "Mês": "Monat",
            "Usado": "Gesamt",
            "Resumo Anual": "Jahresübersicht",
            "Soma dos Selecionados (Absoluto):": "Summe der Ausgewählten (Absolut):",
            "Selecione os cards para consolidar e somar seus totais anuais:": "Wählen Sie die Karten aus, um ihre Jahressummen zu konsolidieren und zu addieren:",
            "Saldo Inicial": "Anfangsbestand",
            "Saldo inicial atualizado com sucesso!": "Anfangsbestand erfolgreich aktualisiert!",
            "Por favor, digite um valor numérico válido!": "Bitte geben Sie einen gültigen numerischen Wert ein!"
        },
        "es": {
            "Dashboard": "Tablero",
            "Investimentos": "Inversiones",
            "Gráficos": "Gráficos",
            "Transações": "Transacciones",
            "Cartões": "Tarjetas",
            "Assistente IA": "Asistente IA",
            "Configurações": "Configuraciones",
            "Banco de Dados": "Base de Datos",
            "Perfis Familiares": "Perfiles Familiares",
            "Categorias": "Categorías",
            "Contrato Legal": "Contrato Legal",
            "Atualizações": "Actualizaciones",
            "Tutorial e FAQ": "Tutorial y FAQ",
            "Receitas": "Ingresos",
            "Despesas": "Gastos",
            "Saldo Líquido": "Saldo Neto",
            "Limite Utilizado": "Límite Utilizado",
            "Saldo Total": "Saldo Total",
            "Investido": "Invertido",
            "Despesas do Mês": "Gastos del Mes",
            "Receitas do Mês": "Ingresos del Mes",
            "Despesas por Categoria": "Gastos por Categoría",
            "Receitas por Categoria": "Ingresos por Categoría",
            "Sem dados de despesas": "Sin datos de gastos",
            "Módulo": "Módulo",
            "Faturas dos Cartões": "Facturas de Tarjetas",
            "Backup Manual do Banco de Dados": "Respaldo Manual de Base de Datos",
            "Exportar uma cópia de segurança do banco de dados para um local de sua escolha.": "Exportar una copia de seguridad de la base de datos a la ubicación de su elección.",
            "EXPORTAR BACKUP": "EXPORTAR RESPALDO",
            "Membros da Família (Perfis)": "Miembros de la Familia (Perfiles)",
            "Novo Membro da Família": "Nuevo Miembro de la Familia",
            "Nome do Novo Perfil": "Nombre del Nuevo Perfil",
            "Por favor, preencha o nome do perfil!": "¡Por favor, complete el nombre del perfil!",
            "Perfil cadastrado com sucesso!": "¡Perfil registrado con éxito!",
            "Confirmar Exclusão": "Confirmar Eliminación",
            "Excluir esta operação permanentemente?": "¿Eliminar esta operación permanentemente?",
            "CANCELAR": "CANCELAR",
            "EXCLUIR": "ELIMINAR",
            "Excluir este perfil permanentemente?": "¿Eliminar este perfil permanentemente?",
            "Excluir": "Eliminar",
            "Temas Claro/Escuro": "Temas Claro/Oscuro",
            "Idioma": "Idioma",
            "Português": "Portugués",
            "Inglês": "Inglés",
            "Alemão": "Alemán",
            "Espanhol": "Español",
            "Tema do Aplicativo": "Tema de la Aplicación",
            "Tema Escuro": "Tema Oscuro",
            "Tema Claro": "Tema Claro",
            "Banco de Dados & Preferências": "Base de Datos y Preferencias",
            "Tema e Idioma": "Tema e Idioma",
            "Altere o tema visual e o idioma do aplicativo. Algumas alterações exigem o recarregamento da tela.": "Cambie el tema visual y el idioma de la aplicación. Algunos cambios requieren recargar la vista.",
            "INICIAR TUTORIAL GUIADO": "INICIAR TUTORIAL GUIADO",
            "PULAR TOUR": "OMITIR TOUR",
            "PRÓXIMO": "SIGUIENTE",
            "CONCLUIR": "FINALIZAR",
            "INICIAR TOUR": "INICIAR TOUR",
            "Bem-vindo ao Sentinel Finance!": "¡Bienvenido a Sentinel Finance!",
            "Identificamos que esta é a primeira execução da versão V2 do Sentinel Finance. Gostaria de fazer um rápido tour guiado interativo para conhecer os novos módulos e funcionalidades do aplicativo?": "¿Detectamos que esta es la primera ejecución de la versión V2 de Sentinel Finance. ¿Le gustaría hacer un recorrido guiado rápido e interactivo para conocer las nuevas características y módulos de la aplicación?",
            "NÃO, OBRIGADO": "NO, GRACIAS",
            "Tutorial concluído com sucesso!": "¡Tutorial completado con éxito!",
            "Tour pulado. Você pode iniciá-lo quando quiser nas Configurações.": "Recorrido omitido. Puede iniciarlo en cualquier momento en las Configuraciones.",
            "Passo": "Paso",
            "de": "de",
            "Ativo": "Activo",
            "Quantidade": "Cantidad",
            "Preço Médio": "Precio Medio",
            "Cotação Atual": "Cotización Actual",
            "Saldo Atual": "Saldo Actual",
            "Valorização": "Valorización",
            "Dividendos Projetados": "Dividendos Proyectados",
            "Ações": "Acciones",
            "Fundos Inmobiliários": "Fondos Inmobiliarios",
            "Renda Fija": "Renta Fija",
            "Gastos por Pilar": "Gastos por Pilar",
            "Gastos por Categoria": "Gastos por Categoría",
            "Resumo Mensal": "Resumen Mensal",
            "Módulo: Assistente IA": "Módulo: Asistente IA",
            "Em desenvolvimento...": "En desarrollo...",
            "Visualização Geral": "Visualización General",
            "Investimentos Cadastrados": "Inversiones Registradas",
            "Nova Operação": "Nueva Operación",
            "Ticker (Código)": "Ticker (Código)",
            "Tipo": "Tipo",
            "Operação": "Operación",
            "Preço Unitário": "Precio Unitario",
            "Data da Compra/Venda": "Fecha de Compra/Venta",
            "Corretora": "Corredor",
            "Observações (Opcional)": "Notas (Opcional)",
            "SALVAR": "GUARDAR",
            "Compra": "Compra",
            "Venda": "Venta",
            "Descrição": "Descripción",
            "Valor": "Valor",
            "Data": "Fecha",
            "Categoria": "Categoría",
            "Perfil": "Perfil",
            "Adicionar Transação": "Añadir Transacción",
            "Adicionar Entrada": "Añadir Ingreso",
            "Adicionar Saída": "Añadir Gasto",
            "Dia": "Día",
            "Mês": "Mes",
            "Ano": "Año",
            "Filtrar por Perfil": "Filtrar por Perfil",
            "Filtrar por Categoria": "Filtrar por Categoría",
            "Todos": "Todos",
            "Filtros Rápidos": "Filtros Rápidos",
            "Limpar Filtros": "Limpiar Filtros",
            "Histórico de Lançamentos": "Historial de Transacciones",
            "Nome do Cartão": "Nombre de Tarjeta",
            "Limite": "Límite",
            "Dia de Fechamento": "Día de Cierre",
            "Dia de Vencimento": "Día de Vencimiento",
            "Dono do Cartão": "Titular de Tarjeta",
            "Bandeira": "Marca",
            "Adicionar Cartão": "Añadir Tarjeta",
            "Limpar": "Limpiar",
            "Cartões Cadastrados": "Tarjetas Registradas",
            "Vencimento": "Vencimiento",
            "Fechamento": "Cierre",
            "Limites dos Cartões": "Límites de Tarjetas",
            "Tutorial e Perguntas Frequentes (FAQ)": "Tutorial y Preguntas Frecuentes (FAQ)",
            "Precisa de ajuda para entender como o Sentinel Finance funciona? Clique abaixo para iniciar um tour guiado interativo:": "Necesita ayuda para entender cómo funciona Sentinel Finance? Haga clic abajo para iniciar un recorrido guiado interactivo:",
            "Guia Rápido dos Módulos (FAQ):": "Guía Rápida de Módulos (FAQ):",
            "Configurações Gerais": "Configuraciones Generales",
            "Idioma alterado com sucesso! Recarregando...": "Idioma cambiado con éxito! Recargando...",
            "Simulação de IR": "Simulación de IR",
            "ATIVADA": "ACTIVADA",
            "DESATIVADA": "DESACTIVADA",
            "Janeiro": "Enero",
            "Fevereiro": "Febrero",
            "Março": "Marzo",
            "Abril": "Abril",
            "Maio": "Mayo",
            "Junho": "Junio",
            "Julho": "Julio",
            "Agosto": "Agosto",
            "Setembro": "Septiembre",
            "Outubro": "Octubre",
            "Novembro": "Noviembre",
            "Dezembro": "Diciembre",
            "Cadastrar Novo Cartão": "Registrar Nueva Tarjeta",
            "Editar Cartão": "Editar Tarjeta",
            "Limite Total (R$)": "Límite Total (R$)",
            "Dia do Fechamento": "Día de Cierre",
            "Dia do Vencimento": "Día de Vencimiento",
            "Últimos 4 Dígitos": "Últimos 4 Dígitos",
            "Cartão excluído com sucesso!": "¡Tarjeta eliminada con éxito!",
            "Erro ao excluir:": "Error al eliminar:",
            "CONFIRMAR EXCLUSÃO ⚠️": "CONFIRMAR ELIMINACIÓN ⚠️",
            "Deseja realmente excluir permanentemente este lançamento?": "¿Realmente desea eliminar permanentemente este registro?",
            "CONFIRMAR EXCLUSÃO": "CONFIRMAR ELIMINACIÓN",
            "Excluir este cartão permanentemente?": "¿Eliminar esta tarjeta permanentemente?",
            "Lançamento salvo com sucesso!": "¡Registro guardado con éxito!",
            "adicionada com sucesso!": "¡añadida con éxito!",
            "Erro ao salvar:": "Error al guardar:",
            "Por favor, preencha a descrição, valor e data!": "¡Por favor, complete la descripción, el valor y la fecha!",
            "Valor inválido!": "¡Valor inválido!",
            "Habilitar Edição (Destravar)": "Habilitar Edición (Desbloquear)",
            "Concluir Edição (Bloquear)": "Finalizar Edición (Bloquear)",
            "Visualização ativa. Clique no cadeado dourado no topo para destravar a edição! 🔓🔒": "Visualización activa. ¡Haga clic en el candado dorado arriba para desbloquear la edición! 🔓🔒",
            "Dividido 👥": "Dividido 👥",
            "💰 Saldo Disponível": "💰 Saldo Disponible",
            "📊 Patrimônio (Custo)": "📊 Patrimonio (Costo)",
            "💎 Valor de Mercado": "💎 Valor de Mercado",
            "🎯 Dividendos do Mês": "🎯 Dividendos del Mes",
            "Carteira vazia": "Cartera vacía",
            "Clique em \"Nova Operação\" para registrar sua primeira compra.": "Haga clic en \"Nueva Operación\" para registrar su primera compra.",
            "INVESTIMENTO": "INVERSIÓN",
            "RECEITA": "INGRESO",
            "DESPESA": "GASTO",
            "Valor (R$)": "Valor (R$)",
            "Data (DD/MM/AAAA)": "Fecha (DD/MM/AAAA)",
            "Observação (Opcional)": "Observación (Opcional)",
            "Tipo de Lançamento": "Tipo de Transacción",
            "Membro da Família": "Miembro de la Familia",
            "Lançar Nova Despesa": "Registrar Nuevo Gasto",
            "Lançar Nova Receita": "Registrar Nuevo Ingreso",
            "Novo Lançamento de Investimento": "Nueva Transacción de Inversión",
            "✏️ Editar Despesa": "✏️ Editar Gasto",
            "✏️ Editar Receita": "✏️ Editar Ingreso",
            "✏️ Editar Investimento": "✏️ Editar Inversión",
            "Despesa 🔴": "Gasto 🔴",
            "Receita 🟢": "Ingreso 🟢",
            "Aporte 🔵": "Aporte 🔵",
            "Novo Lançamento": "Nuevo Registro",
            "Fechar": "Cerrar",
            "CARTEIRA": "CARTERA",
            "RENDIMENTOS": "RENDIMIENTOS",
            "COTAÇÕES EM TEMPO REAL": "COTIZACIONES EN TIEMPO REAL",
            "MENSAL": "MENSUAL",
            "ANUAL": "ANUAL",
            "POR PILAR & CATEGORIA": "POR PILAR Y CATEGORÍA",
            "HISTÓRICO COMPLETO": "HISTORIAL COMPLETO",
            "Simular IR nas vendas": "Simular IR en las ventas",
            "IR: Isento": "IR: Exento",
            "Est. IR:": "Est. IR:",
            "NOVA OPERAÇÃO": "NUEVA OPERACIÓN",
            "SALVAR OPERAÇÃO": "GUARDAR OPERACIÓN",
            "Tesouro Selic (Pós-fixado)": "Tesoro Selic (Post-fixado)",
            "Tesouro Prefixado (Pré-fixado)": "Tesoro Prefixado (Pre-fixado)",
            "Tesouro IPCA+ (Híbrido)": "Tesoro IPCA+ (Híbrido)",
            "Outros": "Otros",
            "Posição Inicial Consolidada": "Posición Inicial Consolidada",
            "Preço Unitário (R$)": "Precio Unitario (R$)",
            "Preço Médio Existente (R$)": "Precio Medio Existente (R$)",
            "Disponível para venda:": "Disponible para la venta:",
            "Aviso: Você não possui o ativo": "Aviso: ¡No posees el activo",
            "Selecione a Categoria do Tesouro": "Selecciona la Categoría del Tesoro",
            "Quantidade deve ser > 0": "La cantidad debe ser > 0",
            "Preço deve ser > 0": "El precio debe ser > 0",
            "Ticker obrigatório": "Ticker obligatorio",
            "Quantidade inválida": "Cantidad inválida",
            "Preço inválido": "Precio inválido",
            "Quantidade máxima de venda permitida:": "Cantidad máxima de venta permitida:",
            "Percentual do CDI deve ser > 0": "El porcentaje de CDI debe ser > 0",
            "Percentual do CDI inválido": "CDI inválido",
            "Saldo Inicial Consolidado": "Saldo Inicial Consolidado",
            "Posição inicial consolidada": "Posición inicial consolidada",
            "✏️ Editar Operação": "✏️ Editar Operación",
            "📈 Nova Operação": "📈 Nueva Operación",
            "Top 5 Despesas": "Top 5 Gastos",
            "Sem dados no mês": "Sin datos en el mes",
            "Sem receitas": "Sin ingresos",
            "Sem fluxo": "Sin flujo",
            "Aviso: Você não possui o ativo na carteira!": "¡Aviso: No posees el activo en la cartera!",
            "Novas Operações": "Nuevas Operaciones",
            "Subcategoria": "Subcategoría",
            "Pilar da Despesa": "Pilar de Gasto",
            "Método de Pagamento": "Método de Pago",
            "Selecione o Cartão": "Seleccione la Tarjeta",
            "Parcelas": "Cuotas",
            "Dividir despesa com a família": "Dividir gasto con la familia",
            "Tipo de Divisão": "Tipo de División",
            "Nome do novo membro": "Nombre del nuevo miembro",
            "POR FORMA DE PAGAMENTO": "POR FORMA DE PAGO",
            "Nenhuma transação encontrada": "No se encontraron transacciones",
            "Os lançamentos deste período aparecerão aqui.": "Los registros de este período aparecerán aquí.",
            "DESPESAS GERAIS": "GASTOS GENERALES",
            "Nenhuma despesa neste período.": "No hay gastos en este período.",
            "RECEITAS & APORTES": "INGRESOS Y APORTES",
            "Nenhuma receita ou aporte neste período.": "No hay ingresos o aportes en este período.",
            "Não especificado": "No especificado",
            "Cartão de Crédito": "Tarjeta de Crédito",
            "CARTÕES DE CRÉDITO": "TARJETAS DE CRÉDITO",
            "Sem gastos no cartão neste período.": "Sin gastos de tarjeta en este período.",
            "OUTRAS FORMAS DE PAGAMENTO": "OTRAS FORMAS DE PAGO",
            "Sem outros gastos neste período.": "Sin otros gastos en este período.",
            "💳 Detalhes do Cartão": "💳 Detalles de la Tarjeta",
            "Igualitária": "Equitativa",
            "Individual": "Individual",
            "Despesa Variável": "Gasto Variable",
            "Despesa Fixa": "Gasto Fijo",
            "Receita Fixa": "Ingreso Fijo",
            "Receita Variável": "Ingreso Variable",
            "Investimento": "Inversión",
            "Dinheiro": "Efectivo",
            "Pix": "Pix",
            "Boleto": "Boleto",
            "Cartão": "Tarjeta",
            "Rendimentos de Ações": "Rendimientos de Acciones",
            "Rendimentos de FIIs": "Rendimientos de FIIs",
            "Pago": "Pagado",
            "Provisionado": "Provisionado",
            "Ticker / FII": "Ticker / FII",
            "Ex: PETR4, MXRF11": "Ej: PETR4, MXRF11",
            "Tipo de Rendimento": "Tipo de Rendimiento",
            "Valor Total (R$)": "Valor Total (R$)",
            "Ex: 150.50": "Ej: 150.50",
            "Status": "Estado",
            "Ticker / Nome do Ativo": "Ticker / Nombre del Activo",
            "Ex: PETR4, MXRF11, CDB XP": "Ej: PETR4, MXRF11, CDB XP",
            "Tipo de Ativo": "Tipo de Activo",
            "Ex: 100": "Ej: 100",
            "Ex: 36.50": "Ej: 36.50",
            "Corretora (Opcional)": "Corredor (Opcional)",
            "Ex: XP, Rico, Clear": "Ej: XP, Rico, Clear",
            "Vencimento (Desabilitado)": "Vencimiento (Desactivado)",
            "Vencimento (DD/MM/AAAA) (Opcional)": "Vencimiento (DD/MM/AAAA) (Opcional)",
            "Ex: 31/12/2028": "Ej: 31/12/2028",
            "Liquidez Diária": "Liquidez Diaria",
            "Percentual do CDI (%) (Opcional)": "Porcentaje de CDI (%) (Opcional)",
            "Ex: 110": "Ej: 110",
            "Categoria do Tesouro": "Categoría del Tesoro",
            "Pai Root": "Categoría Raíz",
            "Por favor, digite o nome da categoria!": "¡Por favor, escriba el nombre de la categoría!",
            "Categoria adicionada com sucesso!": "¡Categoría añadida con éxito!",
            "ADICIONAR CATEGORIA": "AÑADIR CATEGORÍA",
            "Categoria excluída com sucesso!": "¡Categoría eliminada con éxito!",
            "Ex: Filho, Cônjuge": "Ej: Hijo, Cónyuge",
            "CADASTRAR PERFIL": "REGISTRAR PERFIL",
            "Excluir Perfil": "Eliminar Perfil",
            "Nova Categoria": "Nueva Categoría",
            "Nome": "Nombre",
            "Categoria Pai": "Categoría Padre",
            "Erro:": "Error:",
            "Ação": "Acción",
            "FII": "FII",
            "ETF": "ETF",
            "Tesouro": "Tesoro",
            "CDB": "CDB",
            "Cripto": "Cripto",
            "Categorias e Subcategorias": "Categorías y Subcategorías",
            "Contrato Legal e Termos de Uso": "Contrato Legal y Términos de Uso",
            "O Dashboard apresenta o resumo consolidado do mês ativo. Ele exibe suas Receitas, Despesas, Saldo Líquido e o total de limite utilizado em seus cartões. Os gráficos circulares na parte inferior mostram a distribuição de gastos por Pilar e por Categoria. Você pode navegar entre os meses e anos usando as setas de navegação no topo da página.": "El Dashboard presenta el resumen consolidado del mes activo. Muestra sus Ingresos, Gastos, Saldo Neto y el límite utilizado en sus tarjetas. Los gráficos circulares abajo muestran la distribución de gastos por Pilar y Categoría. Puede navegar entre meses y años usando las flechas arriba.",
            "Nesta aba, você cadastra suas Ações e Fundos Inmobiliários. O sistema calcula a cotação média de compra e busca a cotação de mercado atualizada (via API pública do Yahoo Finance) para mostrar a valorização e o saldo total da sua carteira. Além disso, calcula uma estimativa de dividendos projetados com base nos últimos proventos distribuídos.": "En esta pestaña registra sus Acciones y Fondos Inmobiliarios (FIIs). El sistema calcula el precio promedio de compra y busca cotizaciones actualizadas (vía API Yahoo Finance) para mostrar la valorización y saldo total de la cartera. También calcula una estimación de dividendos basada en distribuciones recientes.",
            "Apresenta uma visão analítica e comparativa detalhada da evolução financeira mensal. Útil para identificar padrões de consumo e tendências ao longo do tempo.": "Presenta una visión analítica y comparativa detallada de la evolución financiera mensual. Útil para identificar patrones de consumo y tendencias a lo largo del tiempo.",
            "Aqui você realiza os lançamentos diários de despesas e receitas. É possível filtrar as transações de forma detalhada por Mês, Ano, Perfil Familiar (Membros) e Categorias. O sistema permite travar transações para evitar edições acidentais.": "Aquí registra sus transacciones diarias de gastos e ingresos. Es posible filtrar detalladamente por Mes, Año, Perfil Familiar (Miembros) y Categorías. El sistema permite bloquear transacciones para evitar ediciones accidentales.",
            "O Sentinel Finance suporta múltiplos perfis na mesma base. Você pode cadastrar dependentes ou cônjuges para separar as despesas de cada membro da família. Na aba de Categorias, você gerencia e cria subcategorias personalizadas para o seu controle financeiro.": "Sentinel Finance admite múltiples perfiles en la misma base de datos. Puede registrar dependientes o cónyuges para separar los gastos de cada miembro. En la pestaña Categorías, administra y crea subcategorías personalizadas.",
            "Todos os seus dados são guardados localmente no seu computador em um banco de dados SQLite (arquivo financas.db). Nenhuma informação financeira é enviada a servidores externos. Recomendamos exportar cópias de segurança periodicamente através do botão de 'Exportar Backup' na aba de Banco de Dados.": "Todos sus datos se guardan localmente en su computadora en una base de datos SQLite (archivo financas.db). No se envía información financiera a servidores externos. Se recomienda exportar copias de seguridad periódicamente mediante el botón 'Exportar Respaldo'.",
            "📊 Dashboard (Painel Geral)": "📊 Tablero (Panel General)",
            "📈 Investimentos (Carteira)": "📈 Inversiones (Cartera)",
            "🎨 Gráficos Comparativos": "🎨 Gráficos Comparativos",
            "📝 Transações e Lançamentos": "📝 Transacciones y Registros",
            "👥 Perfis Familiares e Categorias": "👥 Perfiles Familiares y Categorías",
            "💾 Backup e Privacidade Absoluta": "💾 Respaldo y Privacidad Absoluta",
            "Anotações do Subperfil": "Notas del Subperfil",
            "Digite aqui suas anotações para este subperfil (compras futuras, mudanças de valores, etc.)...": "Ingrese sus notas para este subperfil aquí (compras futuras, cambios de valor, etc.)....",
            "Histórico de Backups de Sessão": "Historial de Respaldos de Sesión",
            "Os backups são gerados automaticamente cada vez que se inicia o aplicativo. Eles são mantidos por no máximo 7 dias para permitir a reversão de alterações indesejadas.": "Los respaldos se generan automáticamente cada vez que se inicia la aplicación. Se conservan durante un máximo de 7 días para permitir revertir cambios no deseados.",
            "Reverter": "Revertir",
            "Excluir Backup": "Eliminar Respaldo",
            "Nenhum backup de sessão disponível no momento.": "Ningún respaldo de sesión disponible en este momento.",
            "CONFIRMAR RESTAURAÇÃO ⚠️": "CONFIRMAR RESTAURACIÓN ⚠️",
            "Deseja realmente reverter as alterações para esta sessão? Todos os dados gravados após este backup serão substituídos.": "¿De verdad desea revertir los cambios para esta sesión? Todos los datos guardados después de este respaldo serán reemplazados.",
            "Alterações revertidas com sucesso! Recarregando...": "¡Cambios revertidos con éxito! Recargando...",
            "Backup de sessão excluído com sucesso!": "¡Respaldo de sesión eliminado con éxito!",
            "Backup": "Respaldo",
            "Abatimento excluído/revertido com sucesso!": "¡Amortización eliminada/revertida con éxito!",
            "CONFIRMAR EXCLUSÃO ⚠️": "CONFIRMAR ELIMINACIÓN ⚠️",
            "Deseja realmente excluir ou reverter este abatimento?": "¿De verdad desea eliminar o revertir esta amortización?",
            "REVERTER": "REVERTIR",
            "Erro ao excluir": "Error al eliminar",
            "Mês": "Mes",
            "Usado": "Usado",
            "Resumo Anual": "Resumen Anual",
            "Soma dos Selecionados (Absoluto):": "Suma de Seleccionados (Absoluto):",
            "Selecione os cards para consolidar e somar seus totais anuais:": "Seleccione las tarjetas para consolidar y sumar sus totales anuales:",
            "Saldo Inicial": "Saldo Inicial",
            "Saldo inicial atualizado com sucesso!": "¡Saldo inicial actualizado con éxito!",
            "Por favor, digite um valor numérico válido!": "¡Por favor, introduzca un valor numérico válido!"
        }
    }
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
        else:
            render_dashboard()

    def build_sidebar_controls():
        order_str = db.get_preferencia("sidebar_order", "dashboard,investimentos,charts,transacoes,cartoes,financiamentos,ia")
        order = order_str.split(",")
        
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
        order_str = db.get_preferencia("sidebar_order", "dashboard,investimentos,charts,transacoes,cartoes,financiamentos,ia")
        current_order = order_str.split(",")
        
        items_info = {
            "dashboard": {"label": "Dashboard", "icon": ft.icons.Icons.DASHBOARD_ROUNDED},
            "investimentos": {"label": "Investimentos", "icon": ft.icons.Icons.SAVINGS_ROUNDED},
            "charts": {"label": "Gráficos", "icon": ft.icons.Icons.PIE_CHART_ROUNDED},
            "transacoes": {"label": "Transações", "icon": ft.icons.Icons.LIST_ALT_ROUNDED},
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

    def criar_card_resumo(titulo, valor, cor_valor=None, cor_fundo=None, small=False, subtexto=None):
        colors = get_colors()
        if cor_fundo is None:
            cor_fundo = colors["surface"]
        if cor_valor is None:
            cor_valor = colors["text"]
        pad = 12 if small else 20
        t_sz = 11 if small else 14
        v_sz = 18 if small else 28
        
        controls = [
            ft.Text(titulo, size=t_sz, color=colors["subtext"], weight=ft.FontWeight.W_500),
            ft.Text(f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=v_sz, color=cor_valor, weight=ft.FontWeight.BOLD)
        ]
        if subtexto:
            controls.append(ft.Text(subtexto, size=10, color=colors["subtext"]))
            
        return ft.Container(
            expand=True,
            bgcolor=cor_fundo,
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=12,
            padding=pad,
            content=ft.Column(
                spacing=4 if small else None,
                controls=controls
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
        for t in transacoes: # Exibe todos os lançamentos
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
            
            try:
                t_divisoes = t[11]
            except IndexError:
                t_divisoes = 0

            if t_divisoes and t_divisoes > 1:
                subtitle += " • Dividido 👥"
            
            itens.append(
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor=get_colors()["bg"],
                    border=ft.border.all(1, get_colors()["border"]),
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
                                        bgcolor=get_colors()["surface"],
                                        border_radius=8,
                                        content=ft.Icon(icone_tipo, color=icone_cor, size=20)
                                    ),
                                    ft.Container(width=10),
                                    ft.Column(
                                        expand=True,
                                        spacing=2,
                                        controls=[
                                            ft.Text(desc, size=14, weight=ft.FontWeight.BOLD, color=get_colors()["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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
            bgcolor=get_colors()["surface"],
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=12,
            padding=20,
            content=ft.Column(
                controls=[
                    ft.Text(titulo, size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
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

    def gerar_grafico_donut_base64(dados, labels, cores, is_light=False):
        fig, ax = plt.subplots(figsize=(4.5, 4.5), facecolor='none')
        ax.set_facecolor('none')
        
        text_color = "#0f172a" if is_light else "#ffffff"
        edge_color = "#ffffff" if is_light else "#1e293b"
        
        if not dados or sum(dados) == 0:
            dados = [1]; labels = ["Sem Dados"]; cores = ["#334155"]
            ax.pie(
                dados, labels=labels, colors=cores, startangle=90,
                wedgeprops=dict(width=0.4, edgecolor=edge_color, linewidth=1.5),
                textprops=dict(color=text_color, fontsize=10, weight="bold")
            )
        else:
            wedges, texts, autotexts = ax.pie(
                dados, labels=labels, colors=cores, startangle=90,
                wedgeprops=dict(width=0.4, edgecolor=edge_color, linewidth=1.5),
                textprops=dict(color=text_color, fontsize=10, weight="bold"),
                autopct="%1.0f%%",
                pctdistance=0.8
            )
            for autotext in autotexts:
                autotext.set_color("white" if not is_light else "black")
                autotext.set_fontsize(9)
                autotext.set_weight("bold")
        
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", dpi=100)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def gerar_grafico_evolucao_patrimonio_base64(meses, aplicados, mercados, is_light=False):
        fig, ax = plt.subplots(figsize=(6, 3.5), facecolor='none')
        ax.set_facecolor('none')
        
        text_color = "#0f172a" if is_light else "#ffffff"
        grid_color = "#cbd5e1" if is_light else "#334155"
        
        ganhos = []
        for a, m in zip(aplicados, mercados):
            ganhos.append(max(0.0, m - a))
            
        bar1 = ax.bar(meses, aplicados, label="Valor Aplicado", color="#10b981")
        bar2 = ax.bar(meses, ganhos, bottom=aplicados, label="Ganho de Capital", color="#a7f3d0")
        
        def format_lbl(val):
            if val >= 1000:
                return f"R${val/1000:.1f}k"
            elif val > 0:
                return f"R${val:.0f}"
            else:
                return ""
                
        labels1 = [format_lbl(v) for v in aplicados]
        ax.bar_label(bar1, labels=labels1, label_type='center', color="#064e3b", fontsize=8, weight="bold")
        
        labels2 = [format_lbl(v) for v in mercados]
        ax.bar_label(bar2, labels=labels2, label_type='edge', color=text_color, fontsize=10, padding=3, weight="bold")
        
        ax.tick_params(colors=text_color, labelsize=10)
        for spine in ax.spines.values():
            spine.set_color(grid_color)
            
        ax.legend(facecolor='none', edgecolor=grid_color, labelcolor=text_color, fontsize=10)
        plt.grid(color=grid_color, linestyle='--', linewidth=0.5, axis='y')
        
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", dpi=100)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def gerar_grafico_linhas_rentabilidade_base64(meses, carteira, cdi, ipca, is_light=False):
        fig, ax = plt.subplots(figsize=(6, 3.5), facecolor='none')
        ax.set_facecolor('none')
        
        text_color = "#0f172a" if is_light else "#ffffff"
        grid_color = "#cbd5e1" if is_light else "#334155"
        
        ax.plot(meses, carteira, label="Rentabilidade", color="#3b82f6", linewidth=2.5)
        ax.plot(meses, cdi, label="CDI", color="#fb923c", linewidth=2, linestyle="--")
        if ipca:
            ax.plot(meses, ipca, label="IPCA", color="#a78bfa", linewidth=2, linestyle=":")
            
        if len(carteira) > 0:
            ax.text(len(carteira) - 0.5, carteira[-1], f"{carteira[-1]:.1f}%", color="#3b82f6", fontsize=10, weight="bold", va="center")
        if len(cdi) > 0:
            ax.text(len(cdi) - 0.5, cdi[-1], f"{cdi[-1]:.1f}%", color="#fb923c", fontsize=10, weight="bold", va="center")
            
        ax.tick_params(colors=text_color, labelsize=10)
        for spine in ax.spines.values():
            spine.set_color(grid_color)
            
        ax.legend(facecolor='none', edgecolor=grid_color, labelcolor=text_color, fontsize=10)
        plt.grid(color=grid_color, linestyle='--', linewidth=0.5)
        
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", dpi=100)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def gerar_grafico_barras_proventos_base64(meses, recebidos, a_receber, is_light=False):
        fig, ax = plt.subplots(figsize=(6, 3.5), facecolor='none')
        ax.set_facecolor('none')
        
        text_color = "#0f172a" if is_light else "#ffffff"
        grid_color = "#cbd5e1" if is_light else "#334155"
        
        bar1 = ax.bar(meses, recebidos, label="Recebidos", color="#3b82f6")
        bar2 = ax.bar(meses, a_receber, bottom=recebidos, label="A receber", color="#93c5fd")
        
        def format_lbl(val):
            if val >= 1000:
                return f"R${val/1000:.1f}k"
            elif val > 0:
                return f"R${val:.0f}"
            else:
                return ""
                
        labels1 = [format_lbl(v) for v in recebidos]
        ax.bar_label(bar1, labels=labels1, label_type='center', color="#ffffff", fontsize=8, weight="bold")
        
        totals = [r + ar for r, ar in zip(recebidos, a_receber)]
        labels2 = [format_lbl(v) for v in totals]
        ax.bar_label(bar2, labels=labels2, label_type='edge', color=text_color, fontsize=10, padding=3, weight="bold")
        
        ax.tick_params(colors=text_color, labelsize=10)
        for spine in ax.spines.values():
            spine.set_color(grid_color)
            
        ax.legend(facecolor='none', edgecolor=grid_color, labelcolor=text_color, fontsize=10)
        plt.grid(color=grid_color, linestyle='--', linewidth=0.5, axis='y')
        
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", dpi=100)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def gerar_grafico_aportes_base64(meses, compras, vendas, is_light=False):
        fig, ax = plt.subplots(figsize=(6, 3.5), facecolor='none')
        ax.set_facecolor('none')
        
        text_color = "#0f172a" if is_light else "#ffffff"
        grid_color = "#cbd5e1" if is_light else "#334155"
        
        vendas_neg = [-v for v in vendas]
        
        bar1 = ax.bar(meses, compras, label="Compras", color="#10b981")
        bar2 = ax.bar(meses, vendas_neg, label="Vendas", color="#f87171")
        
        def format_lbl(val):
            val_abs = abs(val)
            sinal = "-" if val < 0 else ""
            if val_abs >= 1000:
                return f"{sinal}R${val_abs/1000:.1f}k"
            elif val_abs > 0:
                return f"{sinal}R${val_abs:.0f}"
            else:
                return ""
                
        labels1 = [format_lbl(v) for v in compras]
        ax.bar_label(bar1, labels=labels1, label_type='edge', color=text_color, fontsize=10, padding=3, weight="bold")
        
        labels2 = [format_lbl(v) for v in vendas_neg]
        ax.bar_label(bar2, labels=labels2, label_type='edge', color=text_color, fontsize=10, padding=3, weight="bold")
        
        ax.axhline(0, color=text_color, linewidth=0.8)
        ax.tick_params(colors=text_color, labelsize=10)
        for spine in ax.spines.values():
            spine.set_color(grid_color)
            
        ax.legend(facecolor='none', edgecolor=grid_color, labelcolor=text_color, fontsize=10)
        plt.grid(color=grid_color, linestyle='--', linewidth=0.5, axis='y')
        
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", dpi=100)
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

        months_short = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        chks_lote = []
        for i, m_name in enumerate(months_short, start=1):
            chk = ft.Checkbox(
                label=m_name,
                value=False,
                label_style=ft.TextStyle(size=12, font_family="Segoe UI", color=get_colors()["text"]),
            )
            chk.data = i
            chks_lote.append(chk)

        lote_container = ft.Column(
            visible=False,
            spacing=5,
            controls=[
                ft.Text(_t("Lançar em Lote (Selecione os meses)"), size=12, weight=ft.FontWeight.BOLD, color=theme_color),
                ft.Row(
                    wrap=True,
                    spacing=5,
                    run_spacing=5,
                    controls=chks_lote
                ),
                ft.Container(height=5)
            ]
        )

        def sync_date_with_lote(e=None):
            val = txt_data.value
            try:
                day_str, month_str, year_str = val.split("/")
                m = int(month_str)
                if 1 <= m <= 12:
                    for chk in chks_lote:
                        chk.value = (chk.data == m)
                    page.update()
            except Exception:
                pass

        txt_data.on_change = sync_date_with_lote

        def toggle_lote_visibility():
            if details:
                lote_container.visible = False
            else:
                lote_container.visible = (drop_pilar.value == "Receita Fixa")

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
                selected_months = [chk.data for chk in chks_lote if chk.value] if (pilar == "Receita Fixa") else []
                if selected_months:
                    try:
                        day_str, month_str, year_str = data_str.split("/")
                        dia = int(day_str)
                        ano = int(year_str)
                    except Exception:
                        page.snack_bar = ft.SnackBar(
                            content=ft.Text(_t("Data inválida! Use o formato DD/MM/AAAA"), color=get_colors()["text"]),
                            bgcolor="#ef4444"
                        )
                        page.snack_bar.open = True
                        page.update()
                        return

                    success = True
                    errors = []
                    for m in selected_months:
                        data_lote = build_safe_date(dia, m, ano)
                        ok, msg = db.inserir_transacao(
                            conta_id=None,
                            categoria_id=final_cat_id,
                            descricao=desc,
                            data_ini=data_lote,
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
                        if not ok:
                            success = False
                            errors.append(f"{months_short[m-1]}: {msg}")
                    if not success:
                        msg = ", ".join(errors)
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
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=txt_valor),
                    ft.Container(expand=True), # dummy spacer for symmetry
                    ft.Container(width=15)
                ]
            ),
            lote_container,
            ft.Row([ft.Container(expand=True, content=txt_obs), ft.Container(width=15)]),
            ft.Container(height=10),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=ft.Row(controls=action_buttons, spacing=10)),
                    ft.Container(width=15)
                ]
            )
        ]

        sync_date_with_lote()

        if details:
            initial_parent = details["parent_id"] if details["parent_id"] is not None else details["categoria_id"]
            update_cats_receita(set_initial=initial_parent)
        else:
            update_cats_receita()

    def populate_formulario_despesa(container, details=None):
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
            value="Despesa Variável",
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

        months_short = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        chks_lote = []
        for i, m_name in enumerate(months_short, start=1):
            chk = ft.Checkbox(
                label=m_name,
                value=False,
                label_style=ft.TextStyle(size=12, font_family="Segoe UI", color=get_colors()["text"]),
            )
            chk.data = i
            chks_lote.append(chk)

        lote_container = ft.Column(
            visible=False,
            spacing=5,
            controls=[
                ft.Text(_t("Lançar em Lote (Selecione os meses)"), size=12, weight=ft.FontWeight.BOLD, color="#ef4444"),
                ft.Row(
                    wrap=True,
                    spacing=5,
                    run_spacing=5,
                    controls=chks_lote
                ),
                ft.Container(height=5)
            ]
        )

        def sync_date_with_lote(e=None):
            val = txt_data.value
            try:
                day_str, month_str, year_str = val.split("/")
                m = int(month_str)
                if 1 <= m <= 12:
                    for chk in chks_lote:
                        chk.value = (chk.data == m)
                    page.update()
            except Exception:
                pass

        txt_data.on_change = sync_date_with_lote

        def toggle_lote_visibility():
            if details:
                lote_container.visible = False
            else:
                lote_container.visible = (drop_pilar.value == "Despesa Fixa")

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
            toggle_lote_visibility()
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
                selected_months = [chk.data for chk in chks_lote if chk.value] if (pilar == "Despesa Fixa") else []
                if selected_months:
                    try:
                        day_str, month_str, year_str = data_str.split("/")
                        dia = int(day_str)
                        ano = int(year_str)
                    except Exception:
                        page.snack_bar = ft.SnackBar(
                            content=ft.Text(_t("Data inválida! Use o formato DD/MM/AAAA"), color=get_colors()["text"]),
                            bgcolor="#ef4444"
                        )
                        page.snack_bar.open = True
                        page.update()
                        return

                    success = True
                    errors = []
                    for m in selected_months:
                        data_lote = build_safe_date(dia, m, ano)
                        ok, msg = db.inserir_transacao(
                            conta_id=None,
                            categoria_id=final_cat_id,
                            descricao=desc,
                            data_ini=data_lote,
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
                        if not ok:
                            success = False
                            errors.append(f"{months_short[m-1]}: {msg}")
                    if not success:
                        msg = ", ".join(errors)
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
            lote_container,
            ft.Row([ft.Container(expand=True, content=txt_obs), ft.Container(width=15)]),
            ft.Container(height=10),
            ft.Row(
                controls=[
                    ft.Container(expand=True, content=ft.Row(controls=action_buttons, spacing=10)),
                    ft.Container(width=15)
                ]
            )
        ]

        sync_date_with_lote()

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
        
        def abrir_resumo_anual_modal(e):
            months_data = []
            
            # Fetch all 12 months' data
            for mes_nome in meses_pt:
                resumo = db.get_resumo_financeiro(mes_nome, str(state["ano"]), state["perfil"])
                receitas = resumo.get("Receita Fixa", 0) + resumo.get("Receita Variável", 0)
                despesas = resumo.get("Despesa Fixa", 0) + resumo.get("Despesa Variável", 0)
                investido = resumo.get("Investimento", 0)
                saldo_mes = receitas - despesas - investido
                saldo_anterior = db.get_saldo_acumulado_anterior(mes_nome, str(state["ano"]), state["perfil"])
                saldo_total = saldo_anterior + saldo_mes
                
                months_data.append({
                    "name": mes_nome,
                    "receitas": receitas,
                    "despesas": despesas,
                    "investido": investido,
                    "saldo_total": saldo_total
                })
            
            # Local state for selection
            selection = {m: True for m in meses_pt}
            
            lbl_total_receitas = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color="#10b981")
            lbl_total_despesas = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color="#ef4444")
            lbl_total_investido = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color="#3b82f6")
            lbl_total_fluxo = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
            
            def atualizar_totais():
                sum_rec = 0.0
                sum_desp = 0.0
                sum_inv = 0.0
                
                for m_data in months_data:
                    if selection[m_data["name"]]:
                        sum_rec += m_data["receitas"]
                        sum_desp += m_data["despesas"]
                        sum_inv += m_data["investido"]
                        
                sum_fluxo = sum_rec - sum_desp - sum_inv
                
                lbl_total_receitas.value = f"R$ {sum_rec:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                lbl_total_despesas.value = f"R$ {sum_desp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                lbl_total_investido.value = f"R$ {sum_inv:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                lbl_total_fluxo.value = f"R$ {sum_fluxo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                lbl_total_fluxo.color = "#10b981" if sum_fluxo >= 0 else "#ef4444"
                
                lbl_total_receitas.update()
                lbl_total_despesas.update()
                lbl_total_investido.update()
                lbl_total_fluxo.update()
                
            def on_toggle_month(mes_nome, e):
                selection[mes_nome] = e.control.value
                atualizar_totais()
                
            # Create header
            colors = get_colors()
            header_tabela = ft.Container(
                bgcolor=colors["bg"],
                padding=ft.Padding(left=15, top=10, right=15, bottom=10),
                border_radius=8,
                content=ft.Row(
                    controls=[
                        ft.Container(content=ft.Text(_t("Mês"), size=11, weight=ft.FontWeight.BOLD, color=colors["text"]), width=120),
                        ft.Container(content=ft.Text(_t("Receitas"), size=11, weight=ft.FontWeight.BOLD, color="#10b981"), width=120),
                        ft.Container(content=ft.Text(_t("Despesas"), size=11, weight=ft.FontWeight.BOLD, color="#ef4444"), width=120),
                        ft.Container(content=ft.Text(_t("Investido"), size=11, weight=ft.FontWeight.BOLD, color="#3b82f6"), width=120),
                        ft.Container(content=ft.Text(_t("Saldo Total"), size=11, weight=ft.FontWeight.BOLD, color=colors["text"]), width=140),
                    ]
                )
            )
            
            rows_controls = []
            for m_data in months_data:
                colors = get_colors()
                val_rec = m_data["receitas"]
                val_desp = m_data["despesas"]
                val_inv = m_data["investido"]
                val_saldo = m_data["saldo_total"]
                
                chk = ft.Checkbox(
                    value=selection[m_data["name"]],
                    on_change=lambda e, mn=m_data["name"]: on_toggle_month(mn, e),
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
                                width=120
                            ),
                            ft.Container(content=ft.Text(f"R$ {val_rec:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, color="#10b981"), width=120),
                            ft.Container(content=ft.Text(f"R$ {val_desp:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, color="#ef4444"), width=120),
                            ft.Container(content=ft.Text(f"R$ {val_inv:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, color="#3b82f6"), width=120),
                            ft.Container(content=ft.Text(f"R$ {val_saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), size=12, color="#10b981" if val_saldo >= 0 else "#ef4444", weight=ft.FontWeight.BOLD), width=140),
                        ]
                    )
                )
                rows_controls.append(row_cont)
                
            list_container = ft.Container(
                height=260,
                content=ft.Column(
                    scroll=ft.ScrollMode.ADAPTIVE,
                    controls=rows_controls,
                    spacing=0
                )
            )
            
            totals_row = ft.Container(
                bgcolor=get_colors()["bg"],
                padding=ft.Padding(left=15, top=10, right=15, bottom=10),
                border_radius=8,
                content=ft.Row(
                    controls=[
                        ft.Container(content=ft.Text(_t("Total Selecionado"), size=11, weight=ft.FontWeight.BOLD, color=get_colors()["text"]), width=120),
                        ft.Container(content=lbl_total_receitas, width=120),
                        ft.Container(content=lbl_total_despesas, width=120),
                        ft.Container(content=lbl_total_investido, width=120),
                        ft.Container(content=lbl_total_fluxo, width=140),
                    ]
                )
            )
            
            # Set initial values
            sum_rec_ini = sum(m["receitas"] for m in months_data)
            sum_desp_ini = sum(m["despesas"] for m in months_data)
            sum_inv_ini = sum(m["investido"] for m in months_data)
            sum_fluxo_ini = sum_rec_ini - sum_desp_ini - sum_inv_ini
            
            lbl_total_receitas.value = f"R$ {sum_rec_ini:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lbl_total_despesas.value = f"R$ {sum_desp_ini:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lbl_total_investido.value = f"R$ {sum_inv_ini:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lbl_total_fluxo.value = f"R$ {sum_fluxo_ini:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lbl_total_fluxo.color = "#10b981" if sum_fluxo_ini >= 0 else "#ef4444"
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.icons.Icons.ANALYTICS_ROUNDED, color="#3b82f6", size=22),
                        ft.Text(f"{_t('Resumo Anual')} - {state['ano']}", size=18, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                    ]
                ),
                content=ft.Container(
                    width=680,
                    height=380,
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Text(_t("Selecione os meses para consolidar os totais anuais:"), size=11, color=get_colors()["subtext"]),
                            header_tabela,
                            list_container,
                            totals_row
                        ]
                    )
                ),
                bgcolor=get_colors()["surface"],
                actions=[
                    ft.TextButton(_t("Fechar"), on_click=lambda e: page.pop_dialog(), style=ft.ButtonStyle(color="white"))
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            page.show_dialog(dialog)

        def on_change_perfil_dash(e):
            state["perfil"] = e.control.value
            render_dashboard()

        seletor_perfil = criar_seletor_perfil(on_change_perfil_dash)

        header_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text(_t("Sentinel Finance"), size=24, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.Row(
                    spacing=15,
                    controls=[
                        ft.TextButton(
                            content=ft.Row([
                                ft.Icon(ft.icons.Icons.ANALYTICS_ROUNDED, color="#3b82f6", size=18),
                                ft.Text(_t("Resumo Anual"), size=13, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                            ], spacing=5),
                            on_click=abrir_resumo_anual_modal
                        ),
                        seletor_perfil,
                        ft.IconButton(
                            icon=ft.icons.Icons.CATEGORY_ROUNDED, 
                            tooltip=_t("Criar Categoria"), 
                            icon_color="#3b82f6", 
                            icon_size=22,
                            on_click=abrir_criar_categoria_modal
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
                                            ft.Text(f"{_t(mes_atual)} {ano_atual}", size=16, weight=ft.FontWeight.W_500, color=get_colors()["subtext"])
                                        ]
                                    )
                                ),
                                ft.IconButton(ft.icons.Icons.CHEVRON_RIGHT_ROUNDED, icon_color="#94a3b8", on_click=next_month),
                            ]
                        )
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
            "Tesouro": "#fbbf24", "CDB": "#fb923c", "Cripto": "#f472b6",
        }
        tipo_ordem = ["Ação", "FII", "ETF", "Tesouro", "CDB", "Cripto"]
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

        header_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text(_t("Transações"), size=24, weight=ft.FontWeight.BOLD, color=get_colors()["text"]),
                ft.Row(
                    spacing=15,
                    controls=[
                        seletor_perfil,
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
                ft.Text(_t("POR PILAR & CATEGORIA"), size=12, color=get_colors()["text"] if tab_active == "pilar_categoria" else "#64748b", weight=ft.FontWeight.BOLD),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            padding=ft.Padding(20, 12, 20, 12),
            bgcolor=get_colors()["surface"] if tab_active == "pilar_categoria" else "transparent",
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=10,
            expand=True,
            ink=True,
            on_click=lambda e: set_transacoes_tab("pilar_categoria")
        )

        tab_pagamento = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.Icons.CREDIT_CARD_ROUNDED, color="white" if tab_active == "forma_pagamento" else "#64748b", size=18),
                ft.Text(_t("POR FORMA DE PAGAMENTO"), size=12, color=get_colors()["text"] if tab_active == "forma_pagamento" else "#64748b", weight=ft.FontWeight.BOLD),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            padding=ft.Padding(20, 12, 20, 12),
            bgcolor=get_colors()["surface"] if tab_active == "forma_pagamento" else "transparent",
            border=ft.border.all(1, get_colors()["border"]),
            border_radius=10,
            expand=True,
            ink=True,
            on_click=lambda e: set_transacoes_tab("forma_pagamento")
        )

        tab_switcher = ft.Container(
            bgcolor=get_colors()["bg"],
            border_radius=12,
            padding=5,
            content=ft.Row(
                spacing=5,
                controls=[tab_pilar, tab_pagamento]
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
                        # Coluna Esquerda: Despesas Gerais
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
                                        ft.Text(_t("DESPESAS GERAIS"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=right_column_items if right_column_items else [ft.Text(_t("Nenhuma despesa neste período."), color="#64748b", size=12)]
                                    )
                                ]
                            )
                        ),
                        # Coluna Direita: Receitas & Investimentos
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
                                        ft.Text(_t("RECEITAS & APORTES"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=left_column_items if left_column_items else [ft.Text(_t("Nenhuma receita ou aporte neste período."), color="#64748b", size=12)]
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
                        metodo = _t("Não especificado")
                        
                    if metodo == "Cartão":
                        t_band = t[10]
                        t_dono = t[9]
                        card_name = card_map.get(f"{t_band}|{t_dono}", f"Cartão {t_dono} ({t_band})" if (t_band and t_dono) else _t("Cartão de Crédito"))
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
                            bgcolor=get_colors()["bg"],
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
                        if t_divisoes and t_divisoes > 1:
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
                            row_bg = get_colors()["card_bg"]
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
                                                    bgcolor=get_colors()["surface"],
                                                    border_radius=6,
                                                    content=ft.Icon(get_icone_categoria(t[4]), color="#ef4444", size=16)
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

                # Layout Aba 2: Duas Colunas
                content_view.content = ft.Row(
                    expand=True,
                    spacing=20,
                    controls=[
                        # Coluna Esquerda: Cartões de Crédito
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
                                        ft.Icon(ft.icons.Icons.CREDIT_CARD_ROUNDED, color="#fb923c", size=16),
                                        ft.Text(_t("CARTÕES DE CRÉDITO"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=left_payment_items if left_payment_items else [ft.Text(_t("Sem gastos no cartão neste período."), color="#64748b", size=12)]
                                    )
                                ]
                            )
                        ),
                        # Coluna Direita: Outras Formas
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
                                        ft.Icon(ft.icons.Icons.PAYMENT_ROUNDED, color="#a78bfa", size=16),
                                        ft.Text(_t("OUTRAS FORMAS DE PAGAMENTO"), size=12, weight=ft.FontWeight.BOLD, color=get_colors()["text"])
                                    ], spacing=6),
                                    ft.Divider(color="#334155", height=1),
                                    ft.ListView(
                                        expand=True,
                                        spacing=6,
                                        padding=ft.Padding(right=15, left=0, top=0, bottom=0),
                                        controls=right_payment_items if right_payment_items else [ft.Text(_t("Sem outros gastos neste período."), color="#64748b", size=12)]
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
        # Grid Principal de 2 Colunas (direct children, no wrapping containers to allow height expansion propagation)
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
                            ft.IconButton(
                                icon=ft.icons.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color="#ef4444",
                                icon_size=14,
                                visible=len(group["children"]) == 0,
                                on_click=lambda e, cid=p_info[0]: run_delete_category(cid)
                            )
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
                                    ft.Text(child[1], size=11, color=get_colors()["subtext"])
                                ], spacing=5),
                                ft.IconButton(
                                    icon=ft.icons.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_color="#ef4444",
                                    icon_size=13,
                                    on_click=lambda e, cid=child[0]: run_delete_category(cid)
                                )
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
                updater = UpdateManager(current_version="1.1.0")
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
                    lbl_status_update.value = "Seu aplicativo já está na versão mais recente (v1.1.0)."
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
                            ft.Text("v1.1.0 (Beta)", size=12, color="white", weight=ft.FontWeight.BOLD)
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

    def navegar_para_aba(tab_name):
        icon_mapping = {
            "dashboard": (ft.icons.Icons.DASHBOARD_ROUNDED, render_dashboard),
            "investimentos": (ft.icons.Icons.SAVINGS_ROUNDED, render_investimentos),
            "charts": (ft.icons.Icons.PIE_CHART_ROUNDED, render_dashboard),
            "transacoes": (ft.icons.Icons.LIST_ALT_ROUNDED, render_transacoes),
            "cartoes": (ft.icons.Icons.CREDIT_CARD_ROUNDED, render_cartoes),
            "financiamentos": (ft.icons.Icons.ACCOUNT_BALANCE_ROUNDED, render_financiamentos),
            "assistente": (ft.icons.Icons.AUTO_AWESOME_ROUNDED, None),
            "configuracoes": (ft.icons.Icons.SETTINGS_ROUNDED, render_configuracoes)
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
