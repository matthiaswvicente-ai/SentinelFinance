import os
import datetime
import random
import sqlite3

def get_demo_db_path():
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "financas_demo.db")

def generate_demo_data():
    db_path = get_demo_db_path()
    # Se já existir, não regera (evita lentidão e travamentos)
    if os.path.exists(db_path):
        return db_path
        
    from database import Database
    db_obj = Database(db_path) # Cria as tabelas e categorias iniciais
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Mapeamento Total de Categorias
    cursor.execute("SELECT id, nome, tipo, parent_id FROM Categorias")
    cats = cursor.fetchall()
    sub_cats = [c for c in cats if c[3] is not None]
    
    # 2. Configuração de Datas
    now = datetime.datetime.now()
    mes_at, ano_at = now.month, now.year
    
    periodos = []
    for offset in [-1, 0, 1]:
        m, a = mes_at + offset, ano_at
        if m < 1: m = 12; a -= 1
        elif m > 12: m = 1; a += 1
        periodos.append((m, a))

    metodos = ["Pix", "Dinheiro", "Cartão de Crédito"]
    bandeiras = ["Visa", "Master", "Elo"]
    nomes_cartao = ["Nubank", "Inter", "Santander"]
    perfis = ["Eu", "Mãe", "Pai", "Irmã"]

    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Mapear usuários
        user_ids = {}
        for p in perfis:
            cursor.execute("INSERT OR IGNORE INTO Usuarios_Familia (nome) VALUES (?)", (p,))
            cursor.execute("SELECT id FROM Usuarios_Familia WHERE nome = ?", (p,))
            user_ids[p] = cursor.fetchone()[0]

        for m, a in periodos:
            for sub in sub_cats:
                cid, nome, tipo = sub[0], sub[1], sub[2]
                
                # Gerar 1 ou 2 lançamentos por categoria para não sobrecarregar
                num_lancamentos = 1 if "Receita" in tipo or "Fixa" in tipo else random.randint(1, 2)
                
                for i in range(num_lancamentos):
                    desc = f"Exemplo: {nome}"
                    dia = random.randint(1, 28)
                    data_str = f"{dia:02d}/{m:02d}/{a}"
                    
                    if "Receita" in tipo:
                        valor = random.uniform(3500, 8000) if "Fixa" in tipo else random.uniform(200, 1500)
                    elif "Investimento" in tipo:
                        valor = random.uniform(500, 2000)
                    else: # Despesas
                        valor = random.uniform(200, 1500) if "Fixa" in tipo else random.uniform(30, 600)
                    
                    metodo = random.choice(metodos)
                    cart_n = random.choice(nomes_cartao) if "Cartão" in metodo else ""
                    cart_b = random.choice(bandeiras) if "Cartão" in metodo else ""
                    dono = random.choice(perfis)
                    
                    # Inserir Transação
                    cursor.execute('''
                        INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                                                metodo_pagamento, parcela_atual, total_parcelas, bandeira_cartao, 
                                                dono_cartao, observacao)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (1, cid, desc, data_str, valor, tipo, metodo, 1, 1, cart_b, cart_n, ""))
                    
                    trans_id = cursor.lastrowid
                    
                    # Divisões: 40% das transações são compartilhadas
                    if random.random() < 0.4:
                        outros = [p for p in perfis if p != dono]
                        parceiro = random.choice(outros)
                        # Dono paga metade, parceiro paga metade
                        cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)",
                                       (trans_id, user_ids[dono], valor * 0.5))
                        cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)",
                                       (trans_id, user_ids[parceiro], valor * 0.5))
                    else:
                        # 100% para o dono
                        cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)",
                                       (trans_id, user_ids[dono], valor))
                                       
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro ao gerar demo: {e}")
    finally:
        conn.close()

    return db_path

if __name__ == "__main__":
    generate_demo_data()
