import unittest
import os
import sqlite3
import sys

# Adiciona o diretório raiz ao PYTHONPATH para os testes encontrarem os módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.test_db_name = "test_financas_temp.db"
        # Garante que começa limpo
        if os.path.exists(self.test_db_name):
            os.remove(self.test_db_name)
            
        self.db = Database(self.test_db_name)

    def tearDown(self):
        # Limpar objetos para fechar conexões SQLite retidas
        import gc
        self.db = None
        gc.collect()
        
        # Auto-limpeza após o teste
        if os.path.exists(self.test_db_name):
            try:
                os.remove(self.test_db_name)
            except Exception:
                pass

    def test_create_tables(self):
        # Verifica se as tabelas foram criadas
        conn = sqlite3.connect(self.test_db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        self.assertIn("Transacoes", tables)
        self.assertIn("Categorias", tables)
        self.assertIn("Usuarios_Familia", tables)

    def test_inserir_transacao(self):
        # Insere uma categoria de teste (ID 1)
        conn = sqlite3.connect(self.test_db_name)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Categorias (nome, tipo) VALUES ('Salário', 'Receita Fixa')")
        conn.commit()
        cursor.close()
        conn.close()

        sucesso = self.db.inserir_transacao(
            conta_id=1,
            categoria_id=1,
            descricao="Salário Mensal",
            data_ini="01/01/2024",
            valor_total=5000.00,
            tipo_transacao="Receita Fixa",
            divisoes={"Eu": 5000.00}
        )
        self.assertTrue(sucesso)
        
        # Verifica se foi inserido
        transacoes = self.db.get_transacoes()
        self.assertEqual(len(transacoes), 1)
        self.assertEqual(transacoes[0][3], 5000.00) # valor_exibido

    def test_export_database(self):
        export_path = "test_export_temp.db"
        if os.path.exists(export_path):
            os.remove(export_path)
            
        sucesso, msg = self.db.export_database(export_path)
        self.assertTrue(sucesso)
        self.assertTrue(os.path.exists(export_path))
        
        if os.path.exists(export_path):
            os.remove(export_path)

    def test_saldo_acumulado_anterior(self):
        # 1. Deve começar com 0.0
        saldo_ant = self.db.get_saldo_acumulado_anterior("Fevereiro", 2026, "Eu")
        self.assertEqual(saldo_ant, 0.0)

        # 2. Adiciona categoria e transação em Janeiro/2026
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Categorias (nome, tipo) VALUES ('Rendimento', 'Receita Variável')")
            cursor.execute("INSERT INTO Categorias (nome, tipo) VALUES ('Aluguel', 'Despesa Fixa')")
            conn.commit()
            
            cursor.execute("SELECT id FROM Categorias WHERE nome = 'Rendimento'")
            cat_rec_id = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM Categorias WHERE nome = 'Aluguel'")
            cat_des_id = cursor.fetchone()[0]
            cursor.close()

        # Receita de 1000 reais em Janeiro
        res_rec = self.db.inserir_transacao(
            conta_id=1,
            categoria_id=cat_rec_id,
            descricao="Dividendos",
            data_ini="15/01/2026",
            valor_total=1000.0,
            tipo_transacao="Receita Variável",
            divisoes={"Eu": 1000.0}
        )
        self.assertTrue(res_rec[0], res_rec[1])

        # Despesa de 300 reais em Janeiro
        res_des = self.db.inserir_transacao(
            conta_id=1,
            categoria_id=cat_des_id,
            descricao="Aluguel Apto",
            data_ini="20/01/2026",
            valor_total=300.0,
            tipo_transacao="Despesa Fixa",
            divisoes={"Eu": 300.0}
        )
        self.assertTrue(res_des[0], res_des[1])

        # 3. O saldo acumulado anterior a Fevereiro/2026 deve ser 1000 - 300 = 700
        saldo_ant_fev = self.db.get_saldo_acumulado_anterior("Fevereiro", 2026, "Eu")
        self.assertEqual(saldo_ant_fev, 700.0)

        # 4. O saldo acumulado anterior a Janeiro/2026 (mesmo ano) deve ser 0.0
        saldo_ant_jan = self.db.get_saldo_acumulado_anterior("Janeiro", 2026, "Eu")
        self.assertEqual(saldo_ant_jan, 0.0)

    def test_saldo_acumulado_anterior_com_data_limite(self):
        # Adiciona categorias e transações
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Categorias (nome, tipo) VALUES ('Rendimento', 'Receita Variável')")
            cursor.execute("INSERT INTO Categorias (nome, tipo) VALUES ('Aluguel', 'Despesa Fixa')")
            conn.commit()
            
            cursor.execute("SELECT id FROM Categorias WHERE nome = 'Rendimento'")
            cat_rec_id = cursor.fetchone()[0]
            cursor.execute("SELECT id FROM Categorias WHERE nome = 'Aluguel'")
            cat_des_id = cursor.fetchone()[0]
            cursor.close()

        # Inserção em Dezembro/2025
        self.db.inserir_transacao(1, cat_rec_id, "Salário Dez/25", "10/12/2025", 2000.0, "Receita Variável", divisoes={"Eu": 2000.0})
        self.db.inserir_transacao(1, cat_des_id, "Despesa Dez/25", "15/12/2025", 500.0, "Despesa Fixa", divisoes={"Eu": 500.0})

        # Inserção em Janeiro/2026
        self.db.inserir_transacao(1, cat_rec_id, "Salário Jan/26", "10/01/2026", 3000.0, "Receita Variável", divisoes={"Eu": 3000.0})
        self.db.inserir_transacao(1, cat_des_id, "Despesa Jan/26", "15/01/2026", 1000.0, "Despesa Fixa", divisoes={"Eu": 1000.0})

        # Inserção em Fevereiro/2026
        self.db.inserir_transacao(1, cat_rec_id, "Salário Fev/26", "10/02/2026", 4000.0, "Receita Variável", divisoes={"Eu": 4000.0})

        # 1. Sem limite de início configurado
        # O saldo acumulado anterior a Fevereiro/2026 deve ser:
        # (2000 - 500) [Dez/25] + (3000 - 1000) [Jan/26] = 1500 + 2000 = 3500
        saldo_ant_fev = self.db.get_saldo_acumulado_anterior("Fevereiro", 2026, "Eu")
        self.assertEqual(saldo_ant_fev, 3500.0)

        # 2. Configura limite de início para Janeiro/2026
        self.db.set_preferencia("saldo_acumulado_inicio_mes", "Janeiro")
        self.db.set_preferencia("saldo_acumulado_inicio_ano", "2026")

        # Agora o saldo acumulado anterior a Fevereiro/2026 deve desconsiderar Dezembro/2025:
        # (3000 - 1000) [Jan/26] = 2000
        saldo_ant_fev_limitado = self.db.get_saldo_acumulado_anterior("Fevereiro", 2026, "Eu")
        self.assertEqual(saldo_ant_fev_limitado, 2000.0)

        # E o saldo acumulado anterior a Janeiro/2026 (que é o mês limite) deve ser exatamente 0.0
        saldo_ant_jan_limitado = self.db.get_saldo_acumulado_anterior("Janeiro", 2026, "Eu")
        self.assertEqual(saldo_ant_jan_limitado, 0.0)

        # 3. Configura limite de início para Janeiro/2026 com saldo inicial de 5000.0
        self.db.set_preferencia("saldo_acumulado_inicio_valor", 5000.0)

        # O saldo acumulado anterior a Janeiro/2026 deve ser exatamente 5000.0 (o saldo inicial)
        saldo_ant_jan_com_valor = self.db.get_saldo_acumulado_anterior("Janeiro", 2026, "Eu")
        self.assertEqual(saldo_ant_jan_com_valor, 5000.0)

        # O saldo acumulado anterior a Fevereiro/2026 deve ser 5000.0 (saldo inicial) + 2000.0 (transações de Jan/26) = 7000.0
        saldo_ant_fev_com_valor = self.db.get_saldo_acumulado_anterior("Fevereiro", 2026, "Eu")
        self.assertEqual(saldo_ant_fev_com_valor, 7000.0)

    def test_anotacoes_usuario(self):
        # 1. Eu/Main profile should return empty notes
        self.assertEqual(self.db.get_anotacoes_usuario("Eu"), "")
        
        # 2. Add a subprofile
        sucesso, msg = self.db.adicionar_usuario("Maria")
        self.assertTrue(sucesso)
        
        # 3. Check default annotations (should be empty string)
        self.assertEqual(self.db.get_anotacoes_usuario("Maria"), "")
        
        # 4. Update annotations
        sucesso_up, msg_up = self.db.update_anotacoes_usuario("Maria", "Comprar pão\nMudar valor do plano de internet")
        self.assertTrue(sucesso_up)
        
        # 5. Retrieve annotations and assert equality
        self.assertEqual(self.db.get_anotacoes_usuario("Maria"), "Comprar pão\nMudar valor do plano de internet")

    def test_excluir_abatimento(self):
        # 1. Criar categoria e conta de teste
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO Categorias (nome, tipo) VALUES ('Empréstimo', 'Despesa Fixa')")
            conn.commit()
            cursor.close()

        # 2. Adicionar financiamento
        # add_financiamento cria o contrato e as parcelas futuras
        res = self.db.add_financiamento(
            credor="Banco X",
            data_inicio="01/01/2030",
            valor_total=1200.0,
            total_parcelas=12,
            taxa_juros=1.0,
            tipo_juros="Mensal",
            sistema_amortizacao="Price",
            conta_id=1,
            perfil_nome="Eu",
            observacao="Teste Financiamento"
        )
        self.assertTrue(res[0], res[1])

        # Busca detalhes do financiamento criado (deve ter id 1)
        details = self.db.get_financiamento_detalhes(1)
        self.assertIsNotNone(details)
        self.assertEqual(len(details["parcelas"]), 12)

        # 3. Pagar a Parcela 1 (originalmente futura, data 01/02/2026)
        # Vamos pegar a transação correspondente da Parcela 1
        parcela_1 = details["parcelas"][0]
        trans_1_id = parcela_1["transacao_id"]
        
        # Pagar a parcela colocando a data como hoje (para simular paga)
        import datetime
        hoje_str = datetime.date.today().strftime("%d/%m/%Y")
        res_pay = self.db.update_parcela_paga(trans_1_id, 100.0, hoje_str, 1)
        self.assertTrue(res_pay[0], res_pay[1])
        
        # Verificar se está nos abatimentos pagos
        ab_pagos = self.db.get_abatimentos_pagos("Eu")
        self.assertEqual(len(ab_pagos), 1)
        self.assertEqual(ab_pagos[0]["transacao_id"], trans_1_id)
        
        # 4. Reverter o pagamento da Parcela 1 usando excluir_abatimento
        res_del = self.db.excluir_abatimento(trans_1_id)
        self.assertTrue(res_del[0], res_del[1])
        
        # Verificar se voltou a ser provisionada (data futura e fora dos abatimentos pagos)
        ab_pagos_after = self.db.get_abatimentos_pagos("Eu")
        self.assertEqual(len(ab_pagos_after), 0)
        
        # 5. Adicionar Amortização Manual
        res_amort = self.db.add_amortizacao_manual(1, 50.0, hoje_str, 1)
        self.assertTrue(res_amort[0], res_amort[1])
        
        # Verificar se aparece nos abatimentos pagos
        ab_pagos_manual = self.db.get_abatimentos_pagos("Eu")
        self.assertEqual(len(ab_pagos_manual), 1)
        self.assertEqual(ab_pagos_manual[0]["raw_numero_parcela"], 13) # A parcela manual assume next_parcel_num
        trans_manual_id = ab_pagos_manual[0]["transacao_id"]
        
        # 6. Excluir fisicamente a Amortização Manual usando excluir_abatimento
        res_del_manual = self.db.excluir_abatimento(trans_manual_id)
        self.assertTrue(res_del_manual[0], res_del_manual[1])
        
        # Verificar se foi removida da lista
        ab_pagos_manual_after = self.db.get_abatimentos_pagos("Eu")
        self.assertEqual(len(ab_pagos_manual_after), 0)

    def test_gasto_cartao_total(self):
        # 1. Adicionar categoria Despesa
        conn = sqlite3.connect(self.test_db_name)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO Categorias (nome, tipo) VALUES ('Lazer', 'Despesa Fixa')")
        conn.commit()
        cursor.close()
        conn.close()

        # 2. Inserir transações com cartão de crédito
        # Transação no mês passado (Maio 2026)
        self.db.inserir_transacao(
            conta_id=1,
            categoria_id=2, # Categoria Lazer cadastrada (segunda categoria inserida no teste)
            descricao="Lazer Maio",
            data_ini="15/05/2026",
            valor_total=150.0,
            tipo_transacao="Despesa Fixa",
            metodo="Cartão de Crédito",
            parcelas=1,
            divisoes={},
            bandeira="Visa",
            dono="Eu"
        )
        
        # Transação no mês atual (Junho 2026)
        self.db.inserir_transacao(
            conta_id=1,
            categoria_id=2,
            descricao="Lazer Junho",
            data_ini="15/06/2026",
            valor_total=300.0,
            tipo_transacao="Despesa Fixa",
            metodo="Cartão de Crédito",
            parcelas=1,
            divisoes={},
            bandeira="Visa",
            dono="Eu"
        )
        
        # Transação no mês que vem (Julho 2026)
        self.db.inserir_transacao(
            conta_id=1,
            categoria_id=2,
            descricao="Lazer Julho",
            data_ini="15/07/2026",
            valor_total=200.0,
            tipo_transacao="Despesa Fixa",
            metodo="Cartão de Crédito",
            parcelas=1,
            divisoes={},
            bandeira="Visa",
            dono="Eu"
        )
        
        # Calcular gasto do mês de Junho 2026: deve ser apenas 300.0
        gasto_mes = self.db.get_gasto_cartao_mes("Visa", "Eu", "06", 2026)
        self.assertEqual(gasto_mes, 300.0)
        
        # Calcular gasto total a partir de Junho 2026: deve ser 300.0 + 200.0 = 500.0 (exclui Maio)
        gasto_total = self.db.get_gasto_cartao_total("Visa", "Eu", "06", 2026)
        self.assertEqual(gasto_total, 500.0)

if __name__ == '__main__':
    unittest.main()
