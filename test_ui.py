import traceback
import customtkinter as ctk
from database import Database
from app_ui import AppUI

try:
    db = Database()
    app = ctk.CTk()
    f = ctk.CTkFrame(app)
    ui = AppUI(db)
    ui.cats_data = db.get_categorias()
    ui._renderizar_itens_aprovacao_ia(f, [{'acao':'adicionar', 'descricao':'Pet', 'valor':350.0, 'categoria':'Lazer'}])
    print('Sucesso')
except Exception as e:
    traceback.print_exc()

