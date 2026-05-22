from database import Database
from app_ui import AppUI

def main():
    # 1. Inicializa o banco de dados e cria as tabelas se não existirem
    print("Inicializando banco de dados...")
    db = Database()
    
    # 2. Inicia a interface gráfica
    print("Iniciando a interface gráfica...")
    app = AppUI(db)
    app.mainloop()

if __name__ == "__main__":
    main()
