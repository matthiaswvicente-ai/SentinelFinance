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

if __name__ == '__main__':
    unittest.main()
