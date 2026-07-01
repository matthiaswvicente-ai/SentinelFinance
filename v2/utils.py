import datetime

def shift_months(date_str, offset):
    if not offset or offset == 0:
        return date_str
    try:
        dt = datetime.datetime.strptime(date_str, "%d/%m/%Y")
        mes = dt.month + offset
        ano = dt.year + (mes - 1) // 12
        mes = (mes - 1) % 12 + 1
        dia = min(dt.day, 28)
        return datetime.datetime(ano, mes, dia).strftime("%d/%m/%Y")
    except Exception:
        return date_str
