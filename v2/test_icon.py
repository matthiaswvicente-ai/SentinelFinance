import flet as ft

def main(page: ft.Page):
    try:
        b1 = ft.IconButton(icon="add")
        print("b1 ok")
    except Exception as e:
        print("b1 err:", e)
        
    try:
        b2 = ft.Icon("account_balance_wallet")
        print("b2 ok")
    except Exception as e:
        print("b2 err:", e)
        
    try:
        page.add(b1)
        page.add(b2)
        print("added ok")
    except Exception as e:
        print("add err:", e)
        
    page.update()

ft.run(main)
