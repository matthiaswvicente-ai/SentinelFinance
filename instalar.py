import flet as ft
import sys
import os
import shutil
import threading
import time
import getpass
import subprocess

def get_source_dir():
    if getattr(sys, 'frozen', False):
        # Quando rodando como executável congelado (PyInstaller), sys.executable aponta para o Instalador.exe
        return os.path.dirname(sys.executable)
    else:
        # Modo de desenvolvimento
        return os.path.dirname(os.path.abspath(__file__))

def get_desktop_path():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        path, _ = winreg.QueryValueEx(key, "Desktop")
        winreg.CloseKey(key)
        return os.path.expandvars(path)
    except Exception:
        # Fallbacks caso ocorra erro ao ler o registro
        userprofile = os.environ.get("USERPROFILE", "")
        onedrive = os.path.join(userprofile, "OneDrive", "Área de Trabalho")
        if os.path.exists(onedrive):
            return onedrive
        onedrive_en = os.path.join(userprofile, "OneDrive", "Desktop")
        if os.path.exists(onedrive_en):
            return onedrive_en
        desktop = os.path.join(userprofile, "Desktop")
        return desktop

def verificar_instalacao_unidade(drive_letter):
    username = getpass.getuser()
    drive_root = drive_letter + "\\" if not drive_letter.endswith("\\") else drive_letter
    
    # Marcador padrão na raiz
    marker_root = os.path.join(drive_root, ".sentinel_finance_installed")
    # Marcador alternativo na pasta de usuário
    marker_user = os.path.join(drive_root, "Users", username, ".sentinel_finance_installed")
    
    for p in [marker_root, marker_user]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    path = f.read().strip()
                    if os.path.exists(path):
                        return True, path
            except:
                pass
    return False, ""

def marcar_instalacao_unidade(drive_letter, dest_folder):
    username = getpass.getuser()
    drive_root = drive_letter + "\\" if not drive_letter.endswith("\\") else drive_letter
    marker_root = os.path.join(drive_root, ".sentinel_finance_installed")
    
    try:
        with open(marker_root, "w", encoding="utf-8") as f:
            f.write(dest_folder)
        subprocess.run(["attrib", "+h", marker_root], capture_output=True)
    except PermissionError:
        user_dir = os.path.join(drive_root, "Users", username)
        if os.path.exists(user_dir):
            marker_user = os.path.join(user_dir, ".sentinel_finance_installed")
            try:
                with open(marker_user, "w", encoding="utf-8") as f:
                    f.write(dest_folder)
                subprocess.run(["attrib", "+h", marker_user], capture_output=True)
            except Exception as e:
                print(f"Erro ao salvar marcador alternativo: {e}")

def criar_atalho_area_de_trabalho(dest_folder):
    try:
        desktop = get_desktop_path()
        shortcut_path = os.path.join(desktop, "Sentinel Finance.lnk")
        
        target_exe = os.path.join(dest_folder, "Sentinel Finance.exe")
        if not os.path.exists(target_exe):
            # Fallback para script python se o executável principal não estiver na pasta
            python_exe = sys.executable
            pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
            if not os.path.exists(pythonw_exe):
                pythonw_exe = python_exe
            main_py = os.path.join(dest_folder, "main.py")
            target_path = pythonw_exe
            arguments = f'"{main_py}"'
        else:
            target_path = target_exe
            arguments = ""
            
        icon_ico = os.path.join(dest_folder, "icon.ico")
        
        ps_script = f"""
        $Shell = New-Object -ComObject WScript.Shell
        $Shortcut = $Shell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{target_path}"
        if ("{arguments}" -ne "") {{
            $Shortcut.Arguments = '{arguments}'
        }}
        $Shortcut.WorkingDirectory = "{dest_folder}"
        if (Test-Path "{icon_ico}") {{
            $Shortcut.IconLocation = "{icon_ico}"
        }}
        $Shortcut.Save()
        """
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, check=True)
        return True
    except Exception as e:
        print(f"Erro ao criar atalho no desktop: {e}")
        return False

def realizar_copia_arquivos(src_dir, dest_dir, progress_cb):
    try:
        os.makedirs(dest_dir, exist_ok=True)
        
        # Lista todos os arquivos a serem copiados e calcula o tamanho total em bytes
        files_to_copy = []
        
        # 1. Sentinel Finance.exe (90 MB)
        src_exe = os.path.join(src_dir, "Sentinel Finance.exe")
        if os.path.exists(src_exe):
            files_to_copy.append((src_exe, os.path.join(dest_dir, "Sentinel Finance.exe"), os.path.getsize(src_exe)))
            
        # 2. Arquivos de raiz
        itens_raiz = [
            "main.py", "logger.py", 
            "update_manager.py", "icon.ico", "Logo 1.png", "Logo 2.png", 
            "requirements.txt", ".ai_version_rules.md"
        ]
        for item in itens_raiz:
            src_path = os.path.join(src_dir, item)
            if os.path.exists(src_path):
                files_to_copy.append((src_path, os.path.join(dest_dir, item), os.path.getsize(src_path)))
                
        # 3. Diretório v2
        src_v2 = os.path.join(src_dir, "v2")
        dest_v2 = os.path.join(dest_dir, "v2")
        if os.path.exists(src_v2):
            for root, dirs, files in os.walk(src_v2):
                rel_path = os.path.relpath(root, src_v2)
                if "backups" in rel_path or "logs" in rel_path or "__pycache__" in rel_path:
                    continue
                for file in files:
                    if not file.endswith(".db"):
                        src_file = os.path.join(root, file)
                        dst_file = os.path.join(dest_v2 if rel_path == "." else os.path.join(dest_v2, rel_path), file)
                        files_to_copy.append((src_file, dst_file, os.path.getsize(src_file)))
                        
        # 4. Desinstalador (desinstalar.exe - 80 MB)
        if getattr(sys, 'frozen', False):
            src_installer = sys.executable
            files_to_copy.append((src_installer, os.path.join(dest_dir, "desinstalar.exe"), os.path.getsize(src_installer)))
            
        # Calcula tamanho total e inicia cópia
        total_bytes = sum(size for _, _, size in files_to_copy)
        bytes_copied = 0
        chunk_size = 1024 * 1024  # blocos de 1 MB
        
        last_update_time = [0.0]
        
        def update_progress(bytes_copied_now, filename, force=False):
            if total_bytes <= 0:
                percent = 1.0
            else:
                percent = bytes_copied_now / total_bytes
            val = 0.95 * percent
            current_time = time.time()
            if force or percent == 1.0 or (current_time - last_update_time[0] > 0.05):
                last_update_time[0] = current_time
                progress_cb(val, f"Instalando {filename} ({int(percent * 100)}%)...")
                time.sleep(0.005)
        
        for src_file, dst_file, file_size in files_to_copy:
            filename = os.path.basename(src_file)
            
            # Garante que a pasta pai exista
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            
            # Copia em blocos se o arquivo for maior que 1 MB para reportar progresso
            if file_size > chunk_size:
                with open(src_file, 'rb') as fsrc:
                    with open(dst_file, 'wb') as fdst:
                        while True:
                            chunk = fsrc.read(chunk_size)
                            if not chunk:
                                break
                            fdst.write(chunk)
                            bytes_copied += len(chunk)
                            update_progress(bytes_copied, filename)
                try:
                    shutil.copystat(src_file, dst_file)
                except:
                    pass
                update_progress(bytes_copied, filename, force=True)
            else:
                shutil.copy2(src_file, dst_file)
                bytes_copied += file_size
                update_progress(bytes_copied, filename, force=True)
                
        # 5. Gravação final e registro (os 5% finais da barra)
        progress_cb(0.96, "Gravando configurações finais...")
        from v2.database import Database
        dest_db_path = os.path.join(dest_v2, "financas.db")
        db = Database(db_name=dest_db_path)
        db.set_preferencia("app_installed", "True")
        
        # Registra no painel de controle do Windows
        progress_cb(0.98, "Registrando desinstalador no Windows...")
        registrar_desinstalador(dest_dir)
        
        progress_cb(0.99, "Criando atalho na Área de Trabalho...")
        criar_atalho_area_de_trabalho(dest_dir)
        
        progress_cb(1.0, "Instalação concluída com sucesso!")
        return True
    except Exception as e:
        print(f"Erro ao instalar arquivos: {e}")
        return False

def registrar_desinstalador(dest_folder):
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SentinelFinance"
        key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE)
        
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Sentinel Finance")
        
        desinstalar_path = os.path.join(dest_folder, "desinstalar.exe")
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{desinstalar_path}" --uninstall')
        
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, dest_folder)
        
        icon_path = os.path.join(dest_folder, "icon.ico")
        if os.path.exists(icon_path):
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, icon_path)
            
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Sentinel Finance")
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "2.0.0")
        
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Erro ao registrar desinstalador no registro: {e}")
        return False

def remover_registro_desinstalador():
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteKey(key, "SentinelFinance")
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Erro ao remover chave de registro: {e}")
        return False

def limpar_marcadores_unidade(dest_folder):
    username = getpass.getuser()
    for d in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]:
        drive_root = d + ":\\"
        if os.path.exists(drive_root):
            marker_root = os.path.join(drive_root, ".sentinel_finance_installed")
            marker_user = os.path.join(drive_root, "Users", username, ".sentinel_finance_installed")
            for marker in [marker_root, marker_user]:
                if os.path.exists(marker):
                    try:
                        with open(marker, "r", encoding="utf-8") as f:
                            path = f.read().strip()
                            if os.path.normpath(path) == os.path.normpath(dest_folder):
                                os.remove(marker)
                    except:
                        pass

def remove_self_and_dir(install_dir):
    temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))
    bat_path = os.path.join(temp_dir, "uninstall_sentinel.bat")
    
    bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
rmdir /s /q "{install_dir}"
del "%~f0"
"""
    try:
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        print(f"Erro ao agendar remoção da pasta: {e}")

def main(page: ft.Page):
    # Detecta se está em modo de desinstalação
    is_uninstall = (
        "--uninstall" in sys.argv or 
        "desinstalar" in os.path.basename(sys.executable).lower() or
        (len(sys.argv) > 0 and "desinstalar" in os.path.basename(sys.argv[0]).lower())
    )
    
    if is_uninstall:
        page.title = "Desinstalador do Sentinel Finance"
    else:
        page.title = "Instalador do Sentinel Finance"
        
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(font_family="Segoe UI")
    page.padding = 0
    page.bgcolor = "#1e293b"
    page.window.width = 560
    page.window.height = 440
    page.window.resizable = False
    
    # Define o ícone da janela/barra de tarefas
    ico_path = os.path.join(get_source_dir(), "icon.ico")
    if not os.path.exists(ico_path):
        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.exists(ico_path):
        page.window.icon = ico_path
        
    if is_uninstall:
        uninstall_state = {
            "step": 1,
            "path": get_source_dir()
        }
        
        uninstall_card = ft.Container(
            expand=True,
            bgcolor="#1e293b",
            padding=20,
            content=ft.Column(expand=True)
        )
        
        def render_uninstall_step():
            step = uninstall_state["step"]
            col = uninstall_card.content
            col.controls.clear()
            
            if step == 1:
                col.controls = [
                    ft.Text("Desinstalar Sentinel Finance", size=20, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Text("Sentinel Finance V2", size=14, color="#ef4444", weight=ft.FontWeight.W_500),
                    ft.Divider(color="#334155"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=15,
                            controls=[
                                ft.Icon(ft.icons.Icons.DELETE_FOREVER_ROUNDED, size=50, color="#ef4444"),
                                ft.Text(
                                    "Tem certeza que deseja desinstalar o Sentinel Finance e todos os seus componentes do seu computador?",
                                    size=12, color="#cbd5e1", text_align=ft.TextAlign.CENTER
                                )
                            ]
                        )
                    ),
                    ft.Divider(color="#334155"),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        controls=[
                            ft.OutlinedButton("Cancelar", on_click=lambda e: sys.exit(0), style=ft.ButtonStyle(color="#94a3b8")),
                            ft.ElevatedButton("Desinstalar", on_click=lambda e: ir_para_desinstalacao(), bgcolor="#ef4444", color="white")
                        ]
                    )
                ]
            elif step == 2:
                prog_bar = ft.ProgressBar(value=0.0, color="#ef4444")
                lbl_prog_status = ft.Text("Removendo arquivos do Sentinel Finance...", size=11, color="#cbd5e1")
                
                col.controls = [
                    ft.Text("Desinstalando o Sentinel Finance...", size=18, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Divider(color="#334155"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                lbl_prog_status,
                                ft.Container(height=10),
                                prog_bar
                            ]
                        )
                    )
                ]
                
                def uninstall_thread():
                    dest_dir = uninstall_state["path"]
                    
                    # 1. Remover atalho da área de trabalho
                    lbl_prog_status.value = "Removendo atalho na Área de Trabalho..."
                    desktop = get_desktop_path()
                    shortcut = os.path.join(desktop, "Sentinel Finance.lnk")
                    if os.path.exists(shortcut):
                        try:
                            os.remove(shortcut)
                        except Exception as e:
                            print(f"Erro ao remover atalho: {e}")
                    for i in range(1, 11):
                        prog_bar.value = i * 0.01
                        page.update()
                        time.sleep(0.01)
                            
                    # 2. Limpar marcadores de unidade
                    lbl_prog_status.value = "Limpando marcadores de instalação nas unidades..."
                    username = getpass.getuser()
                    drives = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
                    for idx, d in enumerate(drives):
                        prog_bar.value = 0.1 + 0.1 * ((idx + 1) / len(drives))
                        page.update()
                        drive_root = d + ":\\"
                        if os.path.exists(drive_root):
                            marker_root = os.path.join(drive_root, ".sentinel_finance_installed")
                            marker_user = os.path.join(drive_root, "Users", username, ".sentinel_finance_installed")
                            for marker in [marker_root, marker_user]:
                                if os.path.exists(marker):
                                    try:
                                        with open(marker, "r", encoding="utf-8") as f:
                                            path = f.read().strip()
                                            if os.path.normpath(path) == os.path.normpath(dest_dir):
                                                os.remove(marker)
                                    except:
                                        pass
                        time.sleep(0.005)
                    
                    # 3. Remover arquivos instalados (exceto desinstalar.exe que está rodando)
                    lbl_prog_status.value = "Identificando arquivos instalados..."
                    files_to_delete = []
                    if os.path.exists(dest_dir):
                        for root, dirs, files in os.walk(dest_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                if file.lower() == "desinstalar.exe":
                                    continue
                                try:
                                    files_to_delete.append((file_path, os.path.getsize(file_path)))
                                except:
                                    pass
                                    
                    total_delete_bytes = sum(size for _, size in files_to_delete)
                    bytes_deleted = 0
                    
                    for file_path, file_size in files_to_delete:
                        if not os.path.exists(file_path):
                            continue
                        try:
                            filename = os.path.basename(file_path)
                            lbl_prog_status.value = f"Removendo {filename}..."
                            os.remove(file_path)
                            bytes_deleted += file_size
                            if total_delete_bytes > 0:
                                percent = bytes_deleted / total_delete_bytes
                                prog_bar.value = 0.2 + 0.6 * percent
                            page.update()
                            time.sleep(0.01)
                        except Exception as e:
                            print(f"Erro ao remover arquivo {file_path}: {e}")
                            
                    # Remove pastas vazias
                    if os.path.exists(dest_dir):
                        for root, dirs, files in os.walk(dest_dir, topdown=False):
                            for d in dirs:
                                dir_path = os.path.join(root, d)
                                try:
                                    os.rmdir(dir_path)
                                except:
                                    pass
                    
                    # 4. Remover registro do Painel de Controle
                    lbl_prog_status.value = "Removendo chaves de registro do sistema..."
                    remover_registro_desinstalador()
                    for i in range(1, 11):
                        prog_bar.value = 0.8 + i * 0.01
                        page.update()
                        time.sleep(0.01)
                    
                    # 5. Finalizando desinstalação
                    lbl_prog_status.value = "Concluindo desinstalação..."
                    for i in range(1, 11):
                        prog_bar.value = 0.9 + i * 0.01
                        page.update()
                        time.sleep(0.01)
                        
                    page.update()
                    ir_para_passo_uninstall(3)
                    
                threading.Thread(target=uninstall_thread, daemon=True).start()
                
            elif step == 3:
                col.controls = [
                    ft.Text("Desinstalação Concluída", size=18, weight=ft.FontWeight.BOLD, color="white"),
                    ft.Divider(color="#334155"),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=15,
                            controls=[
                                ft.Icon(ft.icons.Icons.CHECK_CIRCLE_ROUNDED, size=50, color="#22c55e"),
                                ft.Text(
                                    "O Sentinel Finance foi completamente removido do computador.\nEsta janela será fechada automaticamente em instantes.",
                                    size=12, color="#cbd5e1", text_align=ft.TextAlign.CENTER
                                )
                            ]
                        )
                    ),
                    ft.Divider(color="#334155"),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        controls=[
                            ft.ElevatedButton("Fechar", on_click=lambda e: concluir_desinstalacao(), bgcolor="#22c55e", color="white")
                        ]
                    )
                ]
                
                # Auto-conclui após 3 segundos
                def auto_close():
                    time.sleep(3.0)
                    concluir_desinstalacao()
                threading.Thread(target=auto_close, daemon=True).start()
                
            page.update()
            
        def ir_para_desinstalacao():
            ir_para_passo_uninstall(2)
            
        def ir_para_passo_uninstall(p):
            uninstall_state["step"] = p
            render_uninstall_step()
            
        def concluir_desinstalacao():
            dest_dir = uninstall_state["path"]
            remove_self_and_dir(dest_dir)
            sys.exit(0)
            
        page.add(uninstall_card)
        render_uninstall_step()
        return
    
    # Estado do Instalador
    instalador_state = {
        "step": 1,
        "accept": False,
        "path": "C:\\Program Files\\Sentinel Finance",
        "error_msg": "",
        "is_valid": True
    }
    
    # FilePicker nativo via Tkinter
    def procurar_pasta(e):
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        
        path = filedialog.askdirectory(
            initialdir=instalador_state["path"], 
            title="Selecione a Pasta de Instalação"
        )
        root.destroy()
        
        if path:
            instalador_state["path"] = os.path.normpath(path)
            # Executa validação de unidade
            drive = os.path.splitdrive(instalador_state["path"])[0]
            existe, caminho = verificar_instalacao_unidade(drive)
            if existe:
                instalador_state["error_msg"] = f"⚠️ Já existe uma instalação no drive {drive} em: {caminho}"
                instalador_state["is_valid"] = False
            else:
                instalador_state["error_msg"] = ""
                instalador_state["is_valid"] = True
            ir_para_passo(3)
    
    installer_card = ft.Container(
        expand=True,
        bgcolor="#1e293b",
        padding=20,
        content=ft.Column(expand=True)
    )
    
    def render_installer_step():
        step = instalador_state["step"]
        col = installer_card.content
        col.controls.clear()
        
        if step == 1:
            col.controls = [
                ft.Text("Assistente de Instalação", size=20, weight=ft.FontWeight.BOLD, color="white"),
                ft.Text("Sentinel Finance V2", size=14, color="#3b82f6", weight=ft.FontWeight.W_500),
                ft.Divider(color="#334155"),
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=15,
                        controls=[
                            ft.Icon(ft.icons.Icons.DOWNLOAD_FOR_OFFLINE_ROUNDED, size=50, color="#3b82f6"),
                            ft.Text(
                                "Este instalador guiará você pelas etapas necessárias para configurar o aplicativo Sentinel Finance no seu computador.",
                                size=12, color="#cbd5e1", text_align=ft.TextAlign.CENTER
                            )
                        ]
                    )
                ),
                ft.Divider(color="#334155"),
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.OutlinedButton("Cancelar", on_click=lambda e: sys.exit(0), style=ft.ButtonStyle(color="#94a3b8")),
                        ft.ElevatedButton("Avançar", on_click=lambda e: ir_para_passo(2), bgcolor="#3b82f6", color="white")
                    ]
                )
            ]
        elif step == 2:
            termos_legais = (
                "CONTRATO DE LICENÇA DE USUÁRIO FINAL (EULA) - SENTINEL FINANCE\n\n"
                "1. LICENÇA DE USO:\n"
                "O Sentinel Finance concede a você uma licença pessoal, revogável, não exclusiva e intransferível para utilizar este software para fins de controle financeiro pessoal.\n\n"
                "2. ARMAZENAMENTO DE DADOS:\n"
                "Todos os seus dados cadastrados, incluindo contas, transações, perfis e cartões, são armazenados localmente no seu computador (no arquivo SQLite 'financas.db'). O software não envia seus dados financeiros pessoais para nenhum servidor externo, garantindo privacidade local absoluta.\n\n"
                "3. ISENÇÃO DE RESPONSABILIDADE FINANCEIRA:\n"
                "O Sentinel Finance é um aplicativo de controle e simulação de investimentos. Os dados de cotações e dividendos obtidos da internet são apenas para fins informativos. Este software NÃO CONSTITUI assessoria financeira ou recomendação de investimentos. Decisões de investimento são de inteira responsabilidade do usuário.\n\n"
                "4. LIMITAÇÃO DE RESPONSABILIDADE:\n"
                "Os desenvolvedores do Sentinel Finance não serão responsáveis por perdas financeiras ou danos decorrentes do uso deste aplicativo.\n\n"
                "5. ATUALIZAÇÕES:\n"
                "As atualizações do programa baixadas do GitHub substituem os arquivos de código para melhorar a estabilidade, mas preservam intacto o banco de dados 'financas.db'."
            )
            
            chk_accept = ft.Checkbox(
                label="Eu li e aceito os termos do contrato legal acima",
                value=instalador_state["accept"],
                on_change=lambda e: toggle_accept(e.control.value),
                label_style=ft.TextStyle(size=11, color="white")
            )
            
            btn_next = ft.ElevatedButton(
                "Avançar",
                disabled=not instalador_state["accept"],
                on_click=lambda e: ir_para_passo(3),
                bgcolor="#3b82f6",
                color="white"
            )
            
            def toggle_accept(val):
                instalador_state["accept"] = val
                btn_next.disabled = not val
                page.update()

            col.controls = [
                ft.Text("Contrato de Licença Legal", size=18, weight=ft.FontWeight.BOLD, color="white"),
                ft.Divider(color="#334155"),
                ft.Container(
                    expand=True,
                    bgcolor="#0f172a",
                    border_radius=8,
                    padding=10,
                    border=ft.border.Border(top=ft.border.BorderSide(1, "#1e293b"), bottom=ft.border.BorderSide(1, "#1e293b"), left=ft.border.BorderSide(1, "#1e293b"), right=ft.border.BorderSide(1, "#1e293b")),
                    content=ft.Column(
                        scroll=ft.ScrollMode.ALWAYS,
                        controls=[
                            ft.Text(termos_legais, size=10, color="#94a3b8")
                        ]
                    )
                ),
                ft.Divider(color="#334155"),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        chk_accept,
                        ft.Row([
                            ft.OutlinedButton("Voltar", on_click=lambda e: ir_para_passo(1), style=ft.ButtonStyle(color="#94a3b8")),
                            btn_next
                        ])
                    ]
                )
            ]
        elif step == 3:
            txt_path = ft.TextField(
                label="Pasta de Instalação",
                value=instalador_state["path"],
                border_color="#334155",
                focused_border_color="#3b82f6",
                bgcolor="#0f172a",
                height=45,
                text_size=11,
                text_style=ft.TextStyle(color="white"),
                label_style=ft.TextStyle(color="#94a3b8")
            )
            
            lbl_err = ft.Text(
                instalador_state["error_msg"], 
                size=11, 
                color="#ef4444", 
                weight=ft.FontWeight.BOLD,
                visible=bool(instalador_state["error_msg"])
            )
            
            btn_instalar = ft.ElevatedButton(
                "Instalar", 
                disabled=not instalador_state["is_valid"], 
                on_click=lambda e: iniciar_processo_instalacao(), 
                bgcolor="#22c55e", 
                color="white"
            )

            col.controls = [
                ft.Text("Escolha a Pasta de Destino", size=18, weight=ft.FontWeight.BOLD, color="white"),
                ft.Divider(color="#334155"),
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        spacing=15,
                        controls=[
                            ft.Text("O assistente instalará os arquivos do Sentinel Finance no diretório a seguir. Clique em Procurar para mudar.", size=12, color="#cbd5e1"),
                            ft.Row([
                                ft.Container(expand=True, content=txt_path),
                                ft.ElevatedButton(
                                    "Procurar...",
                                    icon=ft.icons.Icons.FOLDER_OPEN_ROUNDED,
                                    on_click=procurar_pasta,
                                    bgcolor="#3b82f6",
                                    color="white"
                                )
                            ], spacing=10),
                            lbl_err,
                            ft.Text("Espaço em disco necessário: 50 MB\nEspaço em disco disponível: > 10 GB", size=11, color="#64748b")
                        ]
                    )
                ),
                ft.Divider(color="#334155"),
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.OutlinedButton("Voltar", on_click=lambda e: ir_para_passo(2), style=ft.ButtonStyle(color="#94a3b8")),
                        btn_instalar
                    ]
                )
            ]
        elif step == 4:
            prog_bar = ft.ProgressBar(value=0.0, color="#3b82f6")
            lbl_prog_status = ft.Text("Copiando arquivos do Sentinel Finance...", size=11, color="#cbd5e1")
            
            col.controls = [
                ft.Text("Instalando o Sentinel Finance...", size=18, weight=ft.FontWeight.BOLD, color="white"),
                ft.Divider(color="#334155"),
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            lbl_prog_status,
                            ft.Container(height=10),
                            prog_bar
                        ]
                    )
                )
            ]
            
            def progress_thread():
                src_dir = get_source_dir()
                dest_dir = instalador_state["path"]
                drive = os.path.splitdrive(dest_dir)[0]
                
                # Callback de progresso
                def prog_cb(val, msg):
                    prog_bar.value = val
                    lbl_prog_status.value = msg
                    page.update()
                
                # Executa a cópia
                sucesso = realizar_copia_arquivos(src_dir, dest_dir, prog_cb)
                if sucesso:
                    # Marca a instalação nesta unidade de armazenamento
                    marcar_instalacao_unidade(drive, dest_dir)
                    time.sleep(0.4)
                    ir_para_passo(5)
                else:
                    lbl_prog_status.value = "❌ Falha na instalação! Verifique as permissões de gravação da pasta."
                    lbl_prog_status.color = "#ef4444"
                    page.update()

            threading.Thread(target=progress_thread, daemon=True).start()
            
        elif step == 5:
            chk_launch = ft.Checkbox(label="Executar o Sentinel Finance agora", value=True, label_style=ft.TextStyle(color="white"))
            
            def finalizar_instalador(e):
                if chk_launch.value:
                    # Executa o aplicativo instalado de forma independente
                    target_exe = os.path.join(instalador_state["path"], "Sentinel Finance.exe")
                    if os.path.exists(target_exe):
                        subprocess.Popen([target_exe], cwd=instalador_state["path"])
                    else:
                        python_exe = sys.executable
                        main_py = os.path.join(instalador_state["path"], "main.py")
                        subprocess.Popen([python_exe, main_py], cwd=instalador_state["path"])
                sys.exit(0)

            col.controls = [
                ft.Text("Instalação Concluída", size=18, weight=ft.FontWeight.BOLD, color="white"),
                ft.Divider(color="#334155"),
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=15,
                        controls=[
                            ft.Icon(ft.icons.Icons.CHECK_CIRCLE_ROUNDED, size=50, color="#22c55e"),
                            ft.Text(
                                "O Sentinel Finance V2 foi instalado com sucesso em seu computador.\nO atalho foi criado na sua Área de Trabalho.",
                                size=12, color="#cbd5e1", text_align=ft.TextAlign.CENTER
                            ),
                            chk_launch
                        ]
                    )
                ),
                ft.Divider(color="#334155"),
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.ElevatedButton("Concluir", on_click=finalizar_instalador, bgcolor="#22c55e", color="white")
                    ]
                )
            ]
        page.update()
        
    def ir_para_passo(p):
        instalador_state["step"] = p
        render_installer_step()
        
    def iniciar_processo_instalacao():
        # Garante que o caminho final da instalação sempre termine com "Sentinel Finance"
        path = os.path.normpath(instalador_state["path"])
        if not path.endswith("Sentinel Finance"):
            path = os.path.join(path, "Sentinel Finance")
        instalador_state["path"] = path
        ir_para_passo(4)
        
    page.add(installer_card)
    render_installer_step()

if __name__ == "__main__":
    ft.run(main)
