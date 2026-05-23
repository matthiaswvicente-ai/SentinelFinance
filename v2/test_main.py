import flet as ft

def main(page: ft.Page):
    try:
        c1 = ft.Icon("account_balance_wallet")
        page.add(c1)
        print("c1 added")
        
        c2 = ft.IconButton(icon="dashboard_rounded")
        page.add(c2)
        print("c2 added")
        
        c3 = ft.IconButton(icon="list_alt_rounded")
        page.add(c3)
        print("c3 added")
        
        c4 = ft.IconButton(icon="pie_chart_rounded")
        page.add(c4)
        print("c4 added")
        
        c5 = ft.IconButton(icon="auto_awesome_rounded")
        page.add(c5)
        print("c5 added")
        
        c6 = ft.IconButton(icon="settings_rounded")
        page.add(c6)
        print("c6 added")
        
        c7 = ft.FloatingActionButton(icon="add")
        page.add(c7)
        print("c7 added")
        
    except Exception as e:
        print("Exception:", e)

ft.run(main)
