import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

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
