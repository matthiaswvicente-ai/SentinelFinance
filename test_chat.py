import time
import customtkinter as ctk
from database import Database
from app_ui import AppUI

db = Database()
app = AppUI(db)
app.processar_msg_ia('insira uma compra de 350 reais com pet')
while True:
    app.update()
    time.sleep(0.1)

