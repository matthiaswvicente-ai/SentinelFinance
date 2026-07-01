import flet as ft

def criar_card_resumo(titulo, valor, colors, cor_valor=None, cor_fundo=None, small=False, subtexto=None, is_currency=True):
    if cor_fundo is None:
        cor_fundo = colors["surface"]
    if cor_valor is None:
        cor_valor = colors["text"]
    pad = 12 if small else 20
    t_sz = 11 if small else 14
    v_sz = 18 if small else 28
    
    if is_currency:
        valor_str = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        valor_str = str(valor)
        
    controls = [
        ft.Text(titulo, size=t_sz, color=colors["subtext"], weight=ft.FontWeight.W_500),
        ft.Text(valor_str, size=v_sz, color=cor_valor, weight=ft.FontWeight.BOLD)
    ]
    if subtexto:
        controls.append(ft.Text(subtexto, size=10, color=colors["subtext"]))
        
    return ft.Container(
        expand=True,
        bgcolor=cor_fundo,
        border=ft.border.all(1, colors["border"]),
        border_radius=12,
        padding=pad,
        content=ft.Column(
            spacing=4 if small else None,
            controls=controls
        )
    )
