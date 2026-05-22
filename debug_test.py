import traceback
import customtkinter as ctk
from database import Database
from app_ui import AppUI

db = Database()
app = ctk.CTk()
f = ctk.CTkFrame(app)
try:
    ui = AppUI(db)
    ui.cats_data = db.get_categorias()
    ui._renderizar_itens_aprovacao_ia(f, [{'acao':'adicionar', 'descricao':'Pet', 'valor':350.0, 'categoria':'Lazer'}])
    print('Rendered OK')
except Exception as e:
    traceback.print_exc()

