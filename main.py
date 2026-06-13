import os
import sys
import importlib.util

# As importações abaixo dentro de try/except garantem que o PyInstaller detecte
# e empacote todas as dependências críticas do aplicativo (como Flet, matplotlib, pandas, etc.)
# para que o executável 'Sentinel Finance.exe' seja totalmente autônomo.
try:
    import flet
    import matplotlib
    import matplotlib.pyplot
    import pandas
    import yfinance
    import sqlite3
    import logger
    import update_manager
    import v2.database
    import v2.main_v2
except ImportError:
    pass

def main():
    # Se estiver rodando como executável compilado (.exe) do PyInstaller
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    script_path = os.path.join(app_dir, "v2", "main_v2.py")
    v2_dir = os.path.join(app_dir, "v2")

    # Adiciona diretórios ao sys.path para importações relativas
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    if v2_dir not in sys.path:
        sys.path.insert(0, v2_dir)

    print(f"Diretório base: {app_dir}")
    print(f"Caminho do script dinâmico: {script_path}")

    # Se o script dinâmico v2/main_v2.py existir no disco, carrega ele dinamicamente.
    # Isso permite que atualizações feitas pelo Auto-Updater (update_manager) entrem em vigor.
    if os.path.exists(script_path):
        try:
            # Pré-carrega o banco de dados dinamicamente
            db_script_path = os.path.join(v2_dir, "database.py")
            if os.path.exists(db_script_path):
                db_spec = importlib.util.spec_from_file_location("database", db_script_path)
                db_module = importlib.util.module_from_spec(db_spec)
                sys.modules["database"] = db_module
                db_spec.loader.exec_module(db_module)

            # Carrega main_v2 dinamicamente
            spec = importlib.util.spec_from_file_location("v2.main_v2", script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["v2.main_v2"] = module
            spec.loader.exec_module(module)
            
            # Inicializa a interface gráfica usando o módulo dinâmico
            import flet as ft
            ft.run(module.main, assets_dir=app_dir)
            return
        except Exception as e:
            import traceback
            error_log_path = os.path.join(v2_dir, "dynamic_load_error.log")
            try:
                with open(error_log_path, "w", encoding="utf-8") as f:
                    f.write(f"Erro ao carregar dinamicamente:\n{e}\n\n")
                    traceback.print_exc(file=f)
            except:
                pass
            print(f"Erro ao carregar dinamicamente: {e}. Executando versão embutida...", file=sys.stderr)

    # Fallback: se o arquivo no disco não existir ou falhar, executa a versão estática compilada
    try:
        import flet as ft
        import v2.main_v2 as bundled_main
        ft.run(bundled_main.main, assets_dir=app_dir)
    except Exception as e:
        # Se falhar totalmente (catastrófico), exibe mensagem usando Tkinter
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Erro Crítico",
                f"Não foi possível iniciar o Sentinel Finance.\n\nDetalhes do erro:\n{e}"
            )
        except:
            print(f"Erro catastrófico ao iniciar o app: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
