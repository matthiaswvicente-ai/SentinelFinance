import os
import datetime
import random
import sqlite3

def get_demo_db_path():
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "financas_demo.db")

def generate_demo_data():
    db_path = get_demo_db_path()
    
    # Sempre deletar para garantir um sandbox fresco
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except:
            pass # Se estiver em uso, o sqlite vai lidar ou dar erro no connect
            
    from database import Database
    # Instancia para criar o schema básico
    db = Database(db_path)
    # Fecha a conexão do db manager para liberar lock
    if hasattr(db, 'conn') and db.conn:
        db.conn.close()
    
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
    # Cria transacoes para os ultimos 2 meses, o atual, e os proximos 2 meses
    for offset in [-2, -1, 0, 1, 2]:
        m, a = mes_at + offset, ano_at
        if m < 1: 
            m += 12; a -= 1
        elif m > 12: 
            m -= 12; a += 1
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

        # GERAR TRANSAÇÕES ALEATÓRIAS BÁSICAS
        for m, a in periodos:
            for sub in sub_cats:
                cid, nome, tipo = sub[0], sub[1], sub[2]
                
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
                    
                    cursor.execute('''
                        INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                                                metodo_pagamento, parcela_atual, total_parcelas, bandeira_cartao, 
                                                dono_cartao, observacao)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (1, cid, desc, data_str, valor, tipo, metodo, 1, 1, cart_b, cart_n, ""))
                    
                    trans_id = cursor.lastrowid
                    
                    if random.random() < 0.4:
                        outros = [p for p in perfis if p != dono]
                        parceiro = random.choice(outros)
                        cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)",
                                       (trans_id, user_ids[dono], valor * 0.5))
                        cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)",
                                       (trans_id, user_ids[parceiro], valor * 0.5))
                    else:
                        cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)",
                                       (trans_id, user_ids[dono], valor))

        # INJEÇÃO DE CENÁRIOS COMPLEXOS DE TESTE (Para validação visual)
        cat_viagem = next((c[0] for c in sub_cats if "Viagem" in c[1] or "Lazer" in c[1]), sub_cats[-1][0])
        cat_eletro = next((c[0] for c in sub_cats if "Eletrônicos" in c[1] or "Casa" in c[1]), sub_cats[-1][0])
        
        # 1. Compra Parcelada em 10x (1200.00) dividida em 3 pessoas
        valor_parcelada = 1200.00
        valor_parcela = valor_parcelada / 10
        cota_eu = valor_parcela / 3
        cota_mae = valor_parcela / 3
        cota_pai = valor_parcela / 3
        
        for i in range(1, 11):
            pm, pa = mes_at + i - 1, ano_at
            if pm > 12: pm -= 12; pa += 1
            data_parcela = f"15/{pm:02d}/{pa}"
            
            cursor.execute('''
                INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                                        metodo_pagamento, parcela_atual, total_parcelas, bandeira_cartao, dono_cartao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (1, cat_viagem, "Passagem Aérea (Simulação 10x Trio)", data_parcela, valor_parcela, "Despesa Variável", "Cartão de Crédito", i, 10, "Master", "Eu"))
            t_id = cursor.lastrowid
            
            cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)", (t_id, user_ids["Eu"], cota_eu))
            cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)", (t_id, user_ids["Mãe"], cota_mae))
            cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)", (t_id, user_ids["Pai"], cota_pai))

        # 2. Compra com Divisão Assimétrica (Eu 70% / Irmã 30%)
        pm, pa = mes_at, ano_at
        data_assim = f"20/{pm:02d}/{pa}"
        valor_assim = 3500.00
        
        cursor.execute('''
            INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                                    metodo_pagamento, parcela_atual, total_parcelas, bandeira_cartao, dono_cartao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (1, cat_eletro, "TV Sala (Simulação Assimétrica 70/30)", data_assim, valor_assim, "Despesa Variável", "Pix", 1, 1, "", ""))
        t_id_assim = cursor.lastrowid
        cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)", (t_id_assim, user_ids["Eu"], valor_assim * 0.70))
        cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)", (t_id_assim, user_ids["Irmã"], valor_assim * 0.30))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro ao gerar demo: {e}")
    finally:
        conn.close()

    return db_path

if __name__ == "__main__":
    generate_demo_data()
