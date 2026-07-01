import sqlite3
import os
import datetime
import shutil
import glob
from logger import logger

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()

class Database:
    def __init__(self, db_name="financas.db"):
        self.db_name = db_name
        if db_name == "financas.db" and os.path.exists(db_name):
            self._auto_backup()
        self.create_tables()
        self.migrar_receitas_fixas_para_recorrencias()

    def _auto_backup(self):
        try:
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            hoje = datetime.datetime.now().strftime("%Y-%m-%d")
            backup_file = os.path.join(backup_dir, f"financas_{hoje}.db")
            
            if not os.path.exists(backup_file):
                shutil.copy2(self.db_name, backup_file)
                
            # Limpar backups antigos (manter 7 dias)
            backups = sorted(glob.glob(os.path.join(backup_dir, "financas_*.db")))
            while len(backups) > 7:
                oldest = backups.pop(0)
                os.remove(oldest)
        except Exception:
            logger.error("Erro ao fazer backup automático", exc_info=True)

    def export_database(self, dest_path):
        try:
            shutil.copy2(self.db_name, dest_path)
            return True, "Backup exportado com sucesso."
        except Exception as e:
            logger.error("Erro ao exportar banco de dados", exc_info=True)
            return False, str(e)

    def get_connection(self):
        return sqlite3.connect(self.db_name, factory=ClosingConnection)

    def close(self):
        """No caso de banco em arquivo, garante que não há conexões pendentes"""
        pass # No SQLite com 'with' as conexões fecham ao sair do bloco

    def switch_to_sandbox(self):
        import shutil
        if os.path.exists("financas.db"):
            shutil.copy("financas.db", "sandbox_financas.db")
        self.db_name = "sandbox_financas.db"
        self.create_tables()

    def switch_to_production(self):
        self.db_name = "financas.db"
        self.create_tables()

    def create_tables(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabela de Contas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Contas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome_conta TEXT NOT NULL,
                    tipo_conta TEXT NOT NULL
                )
            ''')
            
            # Tabela de Categorias
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Categorias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    parent_id INTEGER,
                    has_subcategories BOOLEAN DEFAULT 0,
                    FOREIGN KEY (parent_id) REFERENCES Categorias(id)
                )
            ''')
            
            # Tabela de Usuários da Família
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Usuarios_Familia (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    anotacoes TEXT DEFAULT ''
                )
            ''')
            
            # Garante que a coluna 'anotacoes' existe se o banco já tiver sido criado
            try:
                cursor.execute("ALTER TABLE Usuarios_Familia ADD COLUMN anotacoes TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
            
            # Tabela de Transações (Atualizada para suportar Parcelamento e Recorrência)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Transacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conta_id INTEGER,
                    categoria_id INTEGER,
                    descricao TEXT NOT NULL,
                    data TEXT NOT NULL,
                    data_real TEXT,
                    valor_total REAL NOT NULL,
                    tipo_transacao TEXT NOT NULL,
                    metodo_pagamento TEXT,
                    parcela_atual INTEGER DEFAULT 1,
                    total_parcelas INTEGER DEFAULT 1,
                    bandeira_cartao TEXT,
                    dono_cartao TEXT,
                    recorrencia TEXT,
                    grupo_id TEXT,
                    observacao TEXT,
                    FOREIGN KEY (conta_id) REFERENCES Contas(id),
                    FOREIGN KEY (categoria_id) REFERENCES Categorias(id)
                )
            ''')
            
            # Garante que a coluna 'data_real' existe se o banco já tiver sido criado
            try:
                cursor.execute("ALTER TABLE Transacoes ADD COLUMN data_real TEXT")
            except sqlite3.OperationalError:
                pass
            
            # Tabela de Divisões de Transação
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Divisoes_Transacao (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transacao_id INTEGER,
                    usuario_id INTEGER,
                    valor_cota REAL NOT NULL,
                    FOREIGN KEY (transacao_id) REFERENCES Transacoes(id),
                    FOREIGN KEY (usuario_id) REFERENCES Usuarios_Familia(id)
                )
            ''')
            
            # Índices para performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_data ON Transacoes(data)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_cat ON Transacoes(categoria_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_div_trans ON Divisoes_Transacao(transacao_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_div_user ON Divisoes_Transacao(usuario_id)")
            
            # Tabela de Preferências (Persistência de Layout/Configurações)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Preferencias (
                    chave TEXT PRIMARY KEY,
                    valor TEXT
                )
            ''')
            
            # Tabela de Cartões de Crédito
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Cartoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    limite REAL NOT NULL,
                    dia_fechamento INTEGER NOT NULL,
                    dia_vencimento INTEGER NOT NULL,
                    cor TEXT NOT NULL,
                    bandeira TEXT NOT NULL,
                    dono TEXT NOT NULL,
                    digitos TEXT DEFAULT '1234'
                )
            ''')
            
            # Garante que a coluna 'digitos' existe se o banco já tiver sido criado
            try:
                cursor.execute("ALTER TABLE Cartoes ADD COLUMN digitos TEXT DEFAULT '1234'")
            except sqlite3.OperationalError:
                pass

            # Tabela de Carteira de Investimentos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Carteira_Investimentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    tipo_ativo TEXT NOT NULL,
                    operacao TEXT NOT NULL,
                    quantidade REAL NOT NULL,
                    preco_unitario REAL NOT NULL,
                    data TEXT NOT NULL,
                    corretora TEXT,
                    observacao TEXT,
                    data_vencimento TEXT,
                    percentual_cdi REAL,
                    subtipo_investimento TEXT,
                    transacao_id INTEGER
                )
            ''')

            # Garante que as colunas extras de investimentos existem no banco de dados se já tiver sido criado
            columns_to_add = [
                ("data_vencimento", "TEXT"),
                ("percentual_cdi", "REAL"),
                ("subtipo_investimento", "TEXT"),
                ("transacao_id", "INTEGER")
            ]
            for col_name, col_type in columns_to_add:
                try:
                    cursor.execute(f"ALTER TABLE Carteira_Investimentos ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass

            # Tabela de Metas de Investimentos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Metas_Investimentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    descricao TEXT NOT NULL,
                    tipo_meta TEXT NOT NULL,
                    valor_objetivo REAL NOT NULL,
                    aporte_mensal REAL NOT NULL,
                    target_ticker TEXT,
                    target_categoria TEXT,
                    perfil TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')

            # Tabela de Financiamentos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Financiamentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    credor TEXT NOT NULL,
                    data_inicio TEXT NOT NULL,
                    valor_total REAL NOT NULL,
                    total_parcelas INTEGER NOT NULL,
                    taxa_juros REAL NOT NULL,
                    tipo_juros TEXT NOT NULL,
                    sistema_amortizacao TEXT NOT NULL,
                    conta_id INTEGER,
                    credito_transacao_id INTEGER,
                    perfil_nome TEXT NOT NULL,
                    observacao TEXT,
                    FOREIGN KEY (conta_id) REFERENCES Contas(id)
                )
            ''')

            # Tabela de Parcelas do Financiamento
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Parcelas_Financiamento (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    financiamento_id INTEGER,
                    transacao_id INTEGER,
                    numero_parcela INTEGER NOT NULL,
                    valor_amortizacao REAL NOT NULL,
                    valor_juros REAL NOT NULL,
                    FOREIGN KEY (financiamento_id) REFERENCES Financiamentos(id) ON DELETE CASCADE,
                    FOREIGN KEY (transacao_id) REFERENCES Transacoes(id) ON DELETE CASCADE
                )
            ''')

            # Tabela de Configurações de Recorrência
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Config_Recorrencias (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    tipo_transacao TEXT NOT NULL,
                    categoria_id INTEGER NOT NULL,
                    valor_padrao REAL NOT NULL,
                    conta_id INTEGER DEFAULT 1,
                    metodo_pagamento TEXT,
                    observacao TEXT,
                    perfil TEXT DEFAULT 'Eu',
                    bandeira_cartao TEXT,
                    dono_cartao TEXT,
                    FOREIGN KEY (categoria_id) REFERENCES Categorias(id),
                    FOREIGN KEY (conta_id) REFERENCES Contas(id)
                )
            ''')

            # Garante que as colunas 'bandeira_cartao' e 'dono_cartao' existam se o banco já tiver sido criado
            try:
                cursor.execute("ALTER TABLE Config_Recorrencias ADD COLUMN bandeira_cartao TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE Config_Recorrencias ADD COLUMN dono_cartao TEXT")
            except sqlite3.OperationalError:
                pass

            # Tabela de Divisões de Recorrência (Rateio)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Divisoes_Recorrencia (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorrencia_id INTEGER,
                    usuario_id INTEGER,
                    valor_cota REAL NOT NULL,
                    FOREIGN KEY (recorrencia_id) REFERENCES Config_Recorrencias(id) ON DELETE CASCADE,
                    FOREIGN KEY (usuario_id) REFERENCES Usuarios_Familia(id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_div_reco ON Divisoes_Recorrencia(recorrencia_id)")

            # Tabela de Veículos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Veiculos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    placa TEXT NOT NULL,
                    modelo TEXT NOT NULL,
                    perfil TEXT DEFAULT 'Eu'
                )
            ''')
            
            # Tabela de Pets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Pets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    raca TEXT,
                    perfil TEXT DEFAULT 'Eu'
                )
            ''')
            
            # Tabela de Saúde
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Saude (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    descricao TEXT,
                    perfil TEXT DEFAULT 'Eu'
                )
            ''')

            # Garante que as colunas veiculo_id, pet_id, saude_id existam em Transacoes
            for col in ['veiculo_id', 'pet_id', 'saude_id']:
                try:
                    cursor.execute(f"ALTER TABLE Transacoes ADD COLUMN {col} INTEGER")
                except sqlite3.OperationalError:
                    pass

            # Cria índices para performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_veiculo ON Transacoes(veiculo_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_pet ON Transacoes(pet_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_saude ON Transacoes(saude_id)")

            # Atualiza métodos de pagamento antigos para consistência com o restante do app
            try:
                cursor.execute("UPDATE Config_Recorrencias SET metodo_pagamento = 'Cartão' WHERE metodo_pagamento = 'Cartão de Crédito'")
                cursor.execute("UPDATE Transacoes SET metodo_pagamento = 'Cartão' WHERE metodo_pagamento = 'Cartão de Crédito'")
            except sqlite3.OperationalError:
                pass

            conn.commit()
            
        # Garante a inserção inicial das categorias da planilha
        self.seed_categorias_iniciais()
        self.seed_contas_iniciais()

    def seed_categorias_iniciais(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Categorias")
            if cursor.fetchone()[0] == 0:
                # Pais (Sempre MAIÚSCULO)
                pais = [
                    ('LAZER', 'Despesa Variável', 1),
                    ('PET', 'Despesa Variável', 1),
                    ('VEÍCULO', 'Despesa Variável', 1),
                    ('SAÚDE', 'Despesa Fixa', 1),
                    ('CASA', 'Despesa Fixa', 1),
                    ('RENDA', 'Receita Fixa', 1),
                    ('INVESTIMENTOS', 'Investimento', 1),
                    ('RENDIMENTOS', 'Receita Variável', 1),
                    ('FIXOS OUTROS', 'Despesa Fixa', 1),
                    ('CONSUMO', 'Despesa Variável', 1)
                ]
                cursor.executemany("INSERT INTO Categorias (nome, tipo, has_subcategories) VALUES (?, ?, ?)", pais)
                
                cursor.execute("SELECT id, nome FROM Categorias WHERE has_subcategories = 1")
                map_pais = {nome: id for id, nome in cursor.fetchall()}
                
                filhos_e_avulsos = [
                    # Investimentos
                    ('Investimentos', 'Investimento', map_pais.get('INVESTIMENTOS'), 0),
                    
                    # Renda (Trabalho / Serviços)
                    ('Estágio', 'Receita Fixa', map_pais.get('RENDA'), 0),
                    ('Emprego', 'Receita Fixa', map_pais.get('RENDA'), 0),
                    ('Serviços Extras', 'Receita Fixa', map_pais.get('RENDA'), 0),
                    
                    # Rendimentos (Investimentos)
                    ('Rendimentos de Ações', 'Receita Variável', map_pais.get('RENDIMENTOS'), 0),
                    ('Rendimentos de FIIs', 'Receita Variável', map_pais.get('RENDIMENTOS'), 0),
                    ('Cashback', 'Receita Variável', map_pais.get('RENDIMENTOS'), 0),
                    ('Resgate de Investimento', 'Receita Variável', map_pais.get('RENDIMENTOS'), 0),
                    
                    # Casa / Fixos
                    ('Aluguel', 'Despesa Fixa', map_pais.get('CASA'), 0),
                    ('Financiamento (Casa)', 'Despesa Fixa', map_pais.get('CASA'), 0),
                    ('Água', 'Despesa Fixa', map_pais.get('CASA'), 0),
                    ('Energia', 'Despesa Fixa', map_pais.get('CASA'), 0),
                    ('Internet', 'Despesa Fixa', map_pais.get('CASA'), 0),
                    ('Gás', 'Despesa Fixa', map_pais.get('CASA'), 0),
                    
                    # Consumo (Novo Pilar)
                    ('Vestimentas', 'Despesa Variável', map_pais.get('CONSUMO'), 0),
                    ('Presentes', 'Despesa Variável', map_pais.get('CONSUMO'), 0),
                    ('Compras', 'Despesa Variável', map_pais.get('CONSUMO'), 0),
                    
                    # Fixos Outros / Saúde
                    ('Plano de Saúde', 'Despesa Fixa', map_pais.get('SAÚDE'), 0),
                    ('Celular', 'Despesa Fixa', map_pais.get('FIXOS OUTROS'), 0),
                    ('Reserva-Manutenção', 'Despesa Fixa', map_pais.get('FIXOS OUTROS'), 0),
                    ('IR-DARF (Investimentos)', 'Despesa Variável', map_pais.get('FIXOS OUTROS'), 0),
                    
                    # Lazer / Variável
                    ('Cinema', 'Despesa Variável', map_pais.get('LAZER'), 0),
                    ('Games', 'Despesa Variável', map_pais.get('LAZER'), 0),
                    ('Livros', 'Despesa Variável', map_pais.get('LAZER'), 0),
                    ('Cursos', 'Despesa Variável', map_pais.get('LAZER'), 0),
                    
                    # Pet
                    ('Ração', 'Despesa Variável', map_pais.get('PET'), 0),
                    ('Remédios', 'Despesa Variável', map_pais.get('PET'), 0),
                    ('Brinquedos', 'Despesa Variável', map_pais.get('PET'), 0),
                    ('Plantas', 'Despesa Variável', map_pais.get('PET'), 0),
                    
                    # Veículo
                    ('Financiamento (Veículo)', 'Despesa Fixa', map_pais.get('VEÍCULO'), 0),
                    ('IPVA', 'Despesa Variável', map_pais.get('VEÍCULO'), 0),
                    ('Licenciamento', 'Despesa Variável', map_pais.get('VEÍCULO'), 0),
                    ('Taxas', 'Despesa Variável', map_pais.get('VEÍCULO'), 0),
                    ('Manutenção', 'Despesa Variável', map_pais.get('VEÍCULO'), 0),
                    ('Estacionamento', 'Despesa Variável', map_pais.get('VEÍCULO'), 0),
                    ('Combustível', 'Despesa Variável', map_pais.get('VEÍCULO'), 0)
                ]
                cursor.executemany("INSERT INTO Categorias (nome, tipo, parent_id, has_subcategories) VALUES (?, ?, ?, ?)", filhos_e_avulsos)
                conn.commit()

    def seed_contas_iniciais(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Contas")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO Contas (nome_conta, tipo_conta) VALUES (?, ?)", ("Principal", "Corrente"))
                conn.commit()

    def get_categorias(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, tipo, parent_id, has_subcategories FROM Categorias ORDER BY tipo, nome")
            return cursor.fetchall()
            
    def inserir_categoria(self, nome, tipo, parent_id=None):
        has_sub = 1 if parent_id is None else 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Categorias (nome, tipo, parent_id, has_subcategories) VALUES (?, ?, ?, ?)", 
                               (nome, tipo, parent_id, has_sub))
                
                # Auto-create subcategory for root categories
                if parent_id is None:
                    novo_id = cursor.lastrowid
                    sub_nome = nome.title() # Convert to Title Case for subcategory
                    cursor.execute("INSERT INTO Categorias (nome, tipo, parent_id, has_subcategories) VALUES (?, ?, ?, ?)", 
                                   (sub_nome, tipo, novo_id, 0))
                conn.commit()
                return True, "Categoria adicionada."
        except Exception as e:
            logger.error('Erro no BD', exc_info=True)
            return False, str(e)
            
    def atualizar_categoria(self, cat_id, novo_nome, tipo=None, parent_id=None):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Obter informações atuais da categoria
                cursor.execute("SELECT parent_id, tipo FROM Categorias WHERE id = ?", (cat_id,))
                row = cursor.fetchone()
                if not row:
                    return False, "Categoria não encontrada."
                old_parent_id, old_tipo = row
                
                # 2. Se parent_id for fornecido e mudou:
                #    A subcategoria herda o tipo do novo pai.
                if parent_id is not None and parent_id != old_parent_id:
                    # Obter tipo do novo pai
                    cursor.execute("SELECT tipo FROM Categorias WHERE id = ?", (parent_id,))
                    row_p = cursor.fetchone()
                    if row_p:
                        tipo = row_p[0] # Herda o tipo do novo pai!
                        
                # 3. Atualizar a própria categoria
                # Se parent_id for None (categoria principal), mantemos parent_id = None
                # Se parent_id for fornecido e diferente de None, atualizamos.
                if tipo is not None:
                    cursor.execute("""
                        UPDATE Categorias 
                        SET nome = ?, tipo = ?, parent_id = ?, has_subcategories = ? 
                        WHERE id = ?
                    """, (novo_nome, tipo, parent_id, 0 if parent_id is not None else 1, cat_id))
                else:
                    cursor.execute("UPDATE Categorias SET nome = ? WHERE id = ?", (novo_nome, cat_id))
                
                # 4. Propagar tipo para subcategorias se for categoria principal
                if old_parent_id is None and tipo is not None and tipo != old_tipo:
                    cursor.execute("UPDATE Categorias SET tipo = ? WHERE parent_id = ?", (tipo, cat_id))
                    
                # 5. Atualizar tipo_transacao de todas as transações associadas
                # Se for categoria principal (old_parent_id is None), atualizamos as transações dela
                # e também de todas as suas subcategorias!
                if tipo is not None and tipo != old_tipo:
                    if old_parent_id is None:
                        # Categoria principal: pega IDs das subcategorias
                        cursor.execute("SELECT id FROM Categorias WHERE parent_id = ?", (cat_id,))
                        sub_ids = [r[0] for r in cursor.fetchall()]
                        all_ids = [cat_id] + sub_ids
                        
                        # Atualiza transações
                        placeholders = ",".join("?" for _ in all_ids)
                        cursor.execute(f"""
                            UPDATE Transacoes 
                            SET tipo_transacao = ? 
                            WHERE categoria_id IN ({placeholders})
                        """, [tipo] + all_ids)
                        
                        # Atualiza recorrências
                        cursor.execute(f"""
                            UPDATE Config_Recorrencias 
                            SET tipo_transacao = ? 
                            WHERE categoria_id IN ({placeholders})
                        """, [tipo] + all_ids)
                    else:
                        # Subcategoria: atualiza apenas as dela
                        cursor.execute("UPDATE Transacoes SET tipo_transacao = ? WHERE categoria_id = ?", (tipo, cat_id))
                        cursor.execute("UPDATE Config_Recorrencias SET tipo_transacao = ? WHERE categoria_id = ?", (tipo, cat_id))
                
                # 6. Se moveu de subcategoria (parent_id mudou) e tipo não mudou, mas o tipo do pai mudou
                # (ex: mudou de pai A para pai B de tipos diferentes)
                if parent_id is not None and parent_id != old_parent_id and tipo is not None:
                    cursor.execute("UPDATE Transacoes SET tipo_transacao = ? WHERE categoria_id = ?", (tipo, cat_id))
                    cursor.execute("UPDATE Config_Recorrencias SET tipo_transacao = ? WHERE categoria_id = ?", (tipo, cat_id))

                conn.commit()
                return True, "Categoria atualizada com sucesso."
        except Exception as e:
            logger.error('Erro no BD ao atualizar categoria', exc_info=True)
            return False, str(e)
            
    def get_preferencia(self, chave, default=None):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT valor FROM Preferencias WHERE chave = ?", (chave,))
                res = cursor.fetchone()
                return res[0] if res else default
        except Exception:
            logger.error('Erro ao ler preferência', exc_info=True)
            return default

    def set_preferencia(self, chave, valor):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO Preferencias (chave, valor) VALUES (?, ?)", (chave, str(valor)))
                conn.commit()
        except Exception:
            logger.error('Erro ignorado', exc_info=True)

    def excluir_categoria(self, cat_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM Categorias WHERE parent_id = ?", (cat_id,))
                if cursor.fetchone()[0] > 0:
                    return False, "Possui subcategorias."
                cursor.execute("SELECT COUNT(*) FROM Transacoes WHERE categoria_id = ?", (cat_id,))
                if cursor.fetchone()[0] > 0:
                    return False, "Em uso em transações."
                cursor.execute("DELETE FROM Categorias WHERE id = ?", (cat_id,))
                conn.commit()
                return True, "Excluída."
        except Exception as e:
            logger.error('Erro no BD', exc_info=True)
            return False, str(e)

    def obter_ou_criar_usuario(self, cursor, nome):
        # Busca o usuário pelo nome
        cursor.execute("SELECT id FROM Usuarios_Familia WHERE nome = ?", (nome,))
        result = cursor.fetchone()
        if result:
            return result[0]
        # Se não existir, cria
        cursor.execute("INSERT INTO Usuarios_Familia (nome) VALUES (?)", (nome,))
        return cursor.lastrowid

    def inserir_transacao(self, conta_id, categoria_id, descricao, data_ini, valor_total, tipo_transacao, 
                          metodo="Dinheiro", parcelas=1, bandeira="", dono="", recorrencia=None, divisoes=None, observacao="", data_real=None,
                          veiculo_id=None, pet_id=None, saude_id=None):
        """
        Insere uma ou mais transações (em caso de parcelamento).
        divisoes: Lista de dicionários, um para cada parcela, contendo {nome_usuario: valor_cota}
                  Ou um único dicionário se for igual para todas as parcelas.
        """
        if data_real is None:
            data_real = data_ini

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Lógica para vincular automaticamente à recorrência se for Receita Fixa
            if tipo_transacao == "Receita Fixa":
                perfil_nome = "Eu"
                if divisoes:
                    if isinstance(divisoes, list) and len(divisoes) > 0 and divisoes[0]:
                        perfil_nome = list(divisoes[0].keys())[0]
                    elif isinstance(divisoes, dict) and divisoes:
                        perfil_nome = list(divisoes.keys())[0]
                
                cursor.execute("""
                    SELECT id FROM Config_Recorrencias 
                    WHERE nome = ? AND categoria_id = ? AND perfil = ? AND tipo_transacao = 'Receita Fixa'
                """, (descricao, categoria_id, perfil_nome))
                row_config = cursor.fetchone()
                if row_config:
                    config_id = row_config[0]
                else:
                    cursor.execute("""
                        INSERT INTO Config_Recorrencias (nome, tipo_transacao, categoria_id, valor_padrao, conta_id, metodo_pagamento, observacao, perfil, bandeira_cartao, dono_cartao)
                        VALUES (?, 'Receita Fixa', ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (descricao, categoria_id, valor_total, conta_id or 1, metodo, observacao, perfil_nome, bandeira, dono))
                    config_id = cursor.lastrowid
                    
                    r_div = divisoes[0] if isinstance(divisoes, list) else divisoes
                    if r_div:
                        for u_name, cota in r_div.items():
                            if cota > 0:
                                u_id = self.obter_ou_criar_usuario(cursor, u_name)
                                cursor.execute("""
                                    INSERT INTO Divisoes_Recorrencia (recorrencia_id, usuario_id, valor_cota)
                                    VALUES (?, ?, ?)
                                """, (config_id, u_id, cota))
                grupo_id = f"REC_{config_id}"
            else:
                grupo_id = f"GRP_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}" if parcelas > 1 else None
            
            # Converter data string para objeto date
            try:
                dt_base = datetime.datetime.strptime(data_ini, "%d/%m/%Y")
            except Exception:
                dt_base = datetime.datetime.now()

            for i in range(parcelas):
                # Calcula data da parcela (adicionando meses)
                mes = dt_base.month + i
                ano = dt_base.year + (mes - 1) // 12
                mes = (mes - 1) % 12 + 1
                dia = min(dt_base.day, 28) # Simplificação para evitar erro de dia 31
                dt_parcela = datetime.datetime(ano, mes, dia)
                data_str = dt_parcela.strftime("%d/%m/%Y")
                
                # Valor da parcela
                val_parcela = valor_total / parcelas
                
                cursor.execute('''
                    INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, data_real, valor_total, tipo_transacao, 
                                            metodo_pagamento, parcela_atual, total_parcelas, bandeira_cartao, 
                                            dono_cartao, recorrencia, grupo_id, observacao, veiculo_id, pet_id, saude_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (conta_id, categoria_id, descricao, data_str, data_real, val_parcela, tipo_transacao, 
                      metodo, i+1, parcelas, bandeira, dono, recorrencia, grupo_id, observacao, veiculo_id, pet_id, saude_id))
                
                transacao_id = cursor.lastrowid

                # Inserir Divisões para esta parcela específica
                parcela_div = divisoes[i] if isinstance(divisoes, list) else divisoes
                if parcela_div:
                    for nome_usuario, valor_cota in parcela_div.items():
                        if valor_cota > 0:
                            # CORREÇÃO: A cota individual também deve ser dividida pelas parcelas
                            cota_parcelada = valor_cota / parcelas
                            usuario_id = self.obter_ou_criar_usuario(cursor, nome_usuario)
                            cursor.execute('''
                                INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota)
                                VALUES (?, ?, ?)
                            ''', (transacao_id, usuario_id, cota_parcelada))

            conn.commit()
            return True, transacao_id
            
        except Exception as e:
            logger.error('Erro ao inserir transação', exc_info=True)
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def deletar_transacao(self, transacao_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Buscar o grupo_id da transação
                cursor.execute("SELECT grupo_id FROM Transacoes WHERE id = ?", (transacao_id,))
                row = cursor.fetchone()
                grupo_id = row[0] if row else None
                
                if grupo_id and grupo_id.startswith("GRP_"):
                    # Selecionar todos os IDs das transações do grupo
                    cursor.execute("SELECT id FROM Transacoes WHERE grupo_id = ?", (grupo_id,))
                    ids = [r[0] for r in cursor.fetchall()]
                    for tid in ids:
                        cursor.execute("DELETE FROM Divisoes_Transacao WHERE transacao_id = ?", (tid,))
                        cursor.execute("DELETE FROM Transacoes WHERE id = ?", (tid,))
                else:
                    cursor.execute("DELETE FROM Divisoes_Transacao WHERE transacao_id = ?", (transacao_id,))
                    cursor.execute("DELETE FROM Transacoes WHERE id = ?", (transacao_id,))
                    
                conn.commit()
                return True, "Transação excluída."
        except Exception as e:
            logger.error('Erro no BD', exc_info=True)
            return False, str(e)

    def get_transacao_by_id(self, transacao_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.categoria_id, t.descricao, t.data, t.valor_total, t.tipo_transacao, 
                       t.metodo_pagamento, t.total_parcelas, t.bandeira_cartao, t.dono_cartao, t.observacao, 
                       c.nome, c.parent_id, t.data_real, t.veiculo_id, t.pet_id, t.saude_id
                FROM Transacoes t
                LEFT JOIN Categorias c ON t.categoria_id = c.id
                WHERE t.id = ?
            """, (transacao_id,))
            t_row = cursor.fetchone()
            if not t_row:
                return None
            
            cursor.execute("""
                SELECT u.nome, d.valor_cota
                FROM Divisoes_Transacao d
                JOIN Usuarios_Familia u ON d.usuario_id = u.id
                WHERE d.transacao_id = ?
            """, (transacao_id,))
            divs = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "id": t_row[0], "categoria_id": t_row[1], "descricao": t_row[2], "data": t_row[3],
                "valor_total": t_row[4], "tipo_transacao": t_row[5], "metodo_pagamento": t_row[6],
                "total_parcelas": t_row[7], "bandeira_cartao": t_row[8], "dono_cartao": t_row[9],
                "observacao": t_row[10], "categoria_nome": t_row[11], "parent_id": t_row[12], "divisoes": divs,
                "data_real": t_row[13], "veiculo_id": t_row[14], "pet_id": t_row[15], "saude_id": t_row[16]
            }

    def atualizar_transacao(self, transacao_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                            metodo, bandeira, dono, observacao, divisoes, data_real=None, atualizar_grupo=True,
                            veiculo_id=None, pet_id=None, saude_id=None, keep_entity_links=True):
        if data_real is None:
            data_real = data
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if keep_entity_links:
                    cursor.execute("SELECT veiculo_id, pet_id, saude_id FROM Transacoes WHERE id = ?", (transacao_id,))
                    row_links = cursor.fetchone()
                    if row_links:
                        if veiculo_id is None: veiculo_id = row_links[0]
                        if pet_id is None: pet_id = row_links[1]
                        if saude_id is None: saude_id = row_links[2]
                
                # Buscar o grupo_id e a data antiga da transação
                cursor.execute("SELECT grupo_id, data FROM Transacoes WHERE id = ?", (transacao_id,))
                row = cursor.fetchone()
                grupo_id = row[0] if row else None
                old_data_str = row[1] if row else None
                
                # Lógica para Receita Fixa
                if tipo_transacao == "Receita Fixa":
                    perfil_nome = "Eu"
                    if divisoes:
                        perfil_nome = list(divisoes.keys())[0]
                    
                    cursor.execute("""
                        SELECT id FROM Config_Recorrencias 
                        WHERE nome = ? AND categoria_id = ? AND perfil = ? AND tipo_transacao = 'Receita Fixa'
                    """, (descricao, categoria_id, perfil_nome))
                    row_config = cursor.fetchone()
                    if row_config:
                        config_id = row_config[0]
                    else:
                        cursor.execute("""
                            INSERT INTO Config_Recorrencias (nome, tipo_transacao, categoria_id, valor_padrao, conta_id, metodo_pagamento, observacao, perfil, bandeira_cartao, dono_cartao)
                            VALUES (?, 'Receita Fixa', ?, ?, 1, ?, ?, ?, ?, ?)
                        """, (descricao, categoria_id, valor_total, metodo, observacao, perfil_nome, bandeira, dono))
                        config_id = cursor.lastrowid
                        
                        if divisoes:
                            for u_name, cota in divisoes.items():
                                if cota > 0:
                                    u_id = self.obter_ou_criar_usuario(cursor, u_name)
                                    cursor.execute("""
                                        INSERT INTO Divisoes_Recorrencia (recorrencia_id, usuario_id, valor_cota)
                                        VALUES (?, ?, ?)
                                    """, (config_id, u_id, cota))
                    grupo_id = f"REC_{config_id}"
                    # Garantir que o grupo_id da transação está atualizado no banco
                    cursor.execute("UPDATE Transacoes SET grupo_id = ? WHERE id = ?", (grupo_id, transacao_id))
                
                diff_months = 0
                if old_data_str and data:
                    try:
                        dt1 = datetime.datetime.strptime(old_data_str, "%d/%m/%Y")
                        dt2 = datetime.datetime.strptime(data, "%d/%m/%Y")
                        diff_months = (dt2.year - dt1.year) * 12 + dt2.month - dt1.month
                    except Exception:
                        pass
                
                if atualizar_grupo and grupo_id and grupo_id.startswith("GRP_"):
                    # Atualizar todas as parcelas do grupo
                    cursor.execute("SELECT id, data FROM Transacoes WHERE grupo_id = ?", (grupo_id,))
                    group_rows = cursor.fetchall()
                    for g_id, g_data_str in group_rows:
                        new_g_data = g_data_str
                        if diff_months != 0:
                            try:
                                g_dt = datetime.datetime.strptime(g_data_str, "%d/%m/%Y")
                                mes = g_dt.month + diff_months
                                ano = g_dt.year + (mes - 1) // 12
                                mes = (mes - 1) % 12 + 1
                                dia = min(g_dt.day, 28)
                                new_g_dt = datetime.datetime(ano, mes, dia)
                                new_g_data = new_g_dt.strftime("%d/%m/%Y")
                            except Exception:
                                pass
                        
                        cursor.execute('''
                            UPDATE Transacoes 
                            SET categoria_id=?, descricao=?, data=?, data_real=?, valor_total=?, tipo_transacao=?, 
                                metodo_pagamento=?, bandeira_cartao=?, dono_cartao=?, observacao=?,
                                veiculo_id=?, pet_id=?, saude_id=?
                            WHERE id=?
                        ''', (categoria_id, descricao, new_g_data, data_real, valor_total, tipo_transacao, metodo, bandeira, dono, observacao,
                              veiculo_id, pet_id, saude_id, g_id))
                        
                        cursor.execute("DELETE FROM Divisoes_Transacao WHERE transacao_id = ?", (g_id,))
                        if divisoes:
                            for nome_usuario, valor_cota in divisoes.items():
                                if valor_cota > 0:
                                    usuario_id = self.obter_ou_criar_usuario(cursor, nome_usuario)
                                    cursor.execute('''
                                        INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota)
                                        VALUES (?, ?, ?)
                                    ''', (g_id, usuario_id, valor_cota))
                else:
                    # Atualizar apenas esta transação
                    cursor.execute('''
                        UPDATE Transacoes 
                        SET categoria_id=?, descricao=?, data=?, data_real=?, valor_total=?, tipo_transacao=?, 
                            metodo_pagamento=?, bandeira_cartao=?, dono_cartao=?, observacao=?,
                            veiculo_id=?, pet_id=?, saude_id=?
                        WHERE id=?
                    ''', (categoria_id, descricao, data, data_real, valor_total, tipo_transacao, metodo, bandeira, dono, observacao,
                          veiculo_id, pet_id, saude_id, transacao_id))
                    
                    cursor.execute("DELETE FROM Divisoes_Transacao WHERE transacao_id = ?", (transacao_id,))
                    if divisoes:
                        for nome_usuario, valor_cota in divisoes.items():
                            if valor_cota > 0:
                                usuario_id = self.obter_ou_criar_usuario(cursor, nome_usuario)
                                cursor.execute('''
                                    INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota)
                                    VALUES (?, ?, ?)
                                    ''', (transacao_id, usuario_id, valor_cota))
                                
                conn.commit()
                return True, "Transação atualizada."
        except Exception as e:
            logger.error('Erro no BD', exc_info=True)
            return False, str(e)

    def get_transacoes(self, mes=None, ano=None, perfil_nome="Eu", categoria_id=None):
        months_map = {"Janeiro":"01","Fevereiro":"02","Março":"03","Abril":"04","Maio":"05","Junho":"06",
                      "Julho":"07","Agosto":"08","Setembro":"09","Outubro":"10","Novembro":"11","Dezembro":"12"}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT t.id, COALESCE(t.data_real, t.data) as data, t.descricao, 
                       CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor_exibido, 
                       c.nome, t.tipo_transacao, 
                       t.parcela_atual, t.total_parcelas, t.metodo_pagamento, t.dono_cartao,
                       t.bandeira_cartao,
                       (SELECT COUNT(*) FROM Divisoes_Transacao WHERE transacao_id = t.id) as num_divisoes,
                       t.observacao,
                       t.valor_total,
                       v.modelo, v.placa,
                       p.nome,
                       s.nome
                FROM Transacoes t 
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                LEFT JOIN Veiculos v ON t.veiculo_id = v.id
                LEFT JOIN Pets p ON t.pet_id = p.id
                LEFT JOIN Saude s ON t.saude_id = s.id
                WHERE (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
            """
            params = [perfil_nome, perfil_nome]
            
            if categoria_id:
                query += " AND t.categoria_id = ?"
                params.append(categoria_id)
            
            if mes and ano:
                mes_num = months_map.get(mes, "01")
                query += " AND substr(t.data, 4, 2) = ? AND substr(t.data, 7, 4) = ?"
                params.extend([mes_num, str(ano)])
            elif ano:
                query += " AND substr(t.data, 7, 4) = ?"
                params.append(str(ano))
                
            query += " ORDER BY substr(t.data, 7, 4) DESC, substr(t.data, 4, 2) DESC, substr(t.data, 1, 2) DESC"
            cursor.execute(query, params)
            return cursor.fetchall()

    def get_resumo_financeiro(self, mes, ano, perfil_nome="Eu"):
        months_map = {"Janeiro":"01","Fevereiro":"02","Março":"03","Abril":"04","Maio":"05","Junho":"06",
                      "Julho":"07","Agosto":"08","Setembro":"09","Outubro":"10","Novembro":"11","Dezembro":"12"}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # resumo foca na cota do perfil selecionado
            resumo = {"Receita Fixa": 0, "Receita Variável": 0, "Despesa Fixa": 0, "Despesa Variável": 0, "Investimento": 0, "Outros": 0}
            
            query_base = """
                SELECT c.tipo, 
                       SUM(CASE 
                            WHEN u.nome = ? THEN d.valor_cota 
                            WHEN d.id IS NULL AND ? = 'Eu' THEN t.valor_total
                            ELSE 0 
                           END) as cota_perfil,
                       SUM(CASE 
                            WHEN (u.nome != ? OR u.nome IS NULL) AND d.id IS NOT NULL THEN d.valor_cota 
                            ELSE 0 
                           END) as cota_outros
                FROM Transacoes t 
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
            """
            params_base = [perfil_nome, perfil_nome, perfil_nome]
            
            if mes:
                mes_num = months_map.get(mes, "01")
                query = query_base + " WHERE substr(t.data, 4, 2) = ? AND substr(t.data, 7, 4) = ? GROUP BY c.tipo"
                params = params_base + [mes_num, str(ano)]
            else:
                query = query_base + " WHERE substr(t.data, 7, 4) = ? GROUP BY c.tipo"
                params = params_base + [str(ano)]
                
            cursor.execute(query, params)
            resumo["Divisao_Familia"] = {p: 0 for p in ["Mãe", "Pai", "Irmã", "Outro"]}
            
            # Segunda query para o breakdown por pessoa
            query_breakdown = """
                SELECT u.nome, SUM(d.valor_cota)
                FROM Divisoes_Transacao d
                JOIN Usuarios_Familia u ON d.usuario_id = u.id
                JOIN Transacoes t ON d.transacao_id = t.id
                WHERE u.nome != 'Eu'
            """
            params_br = []
            if mes:
                mes_num = months_map.get(mes, "01")
                query_breakdown += " AND substr(t.data, 4, 2) = ? AND substr(t.data, 7, 4) = ?"
                params_br = [mes_num, str(ano)]
            else:
                query_breakdown += " AND substr(t.data, 7, 4) = ?"
                params_br = [str(ano)]
            
            query_breakdown += " GROUP BY u.nome"
            cursor.execute(query_breakdown, params_br)
            for nome, total in cursor.fetchall():
                if nome in resumo["Divisao_Familia"]:
                    resumo["Divisao_Familia"][nome] = total
            
            cursor.execute(query, params) # Re-executa a query principal pois o cursor foi usado
            for tipo, cota_p, cota_outros in cursor.fetchall():
                if tipo in resumo: 
                    resumo[tipo] = cota_p if cota_p is not None else 0
                resumo["Outros"] += cota_outros if cota_outros is not None else 0
            
            return resumo

    def get_saldo_acumulado_anterior(self, mes, ano, perfil_nome="Eu"):
        months_map = {"Janeiro":"01","Fevereiro":"02","Março":"03","Abril":"04","Maio":"05","Junho":"06",
                      "Julho":"07","Agosto":"08","Setembro":"09","Outubro":"10","Novembro":"11","Dezembro":"12"}
        mes_num = months_map.get(mes, "01")
        
        start_mes = self.get_preferencia("saldo_acumulado_inicio_mes", "")
        start_ano = self.get_preferencia("saldo_acumulado_inicio_ano", "")
        
        has_start_limit = False
        initial_balance = 0.0
        if start_mes and start_ano:
            try:
                start_mes_val = int(months_map.get(start_mes, "01"))
                start_ano_val = int(start_ano)
                target_mes_val = int(mes_num)
                target_ano_val = int(ano)
                
                try:
                    initial_balance = float(self.get_preferencia("saldo_acumulado_inicio_valor", "0.0"))
                except Exception:
                    initial_balance = 0.0

                # Se o mês alvo for anterior ao limite, o saldo carry-over é 0
                if (target_ano_val < start_ano_val) or (target_ano_val == start_ano_val and target_mes_val < start_mes_val):
                    return 0.0
                
                # Se o mês alvo for exatamente o limite, o saldo carry-over é o saldo inicial
                if target_ano_val == start_ano_val and target_mes_val == start_mes_val:
                    return initial_balance
                
                has_start_limit = True
                start_mes_str = f"{start_mes_val:02d}"
                start_ano_str = str(start_ano_val)
            except Exception:
                has_start_limit = False

        with self.get_connection() as conn:
            cursor = conn.cursor()
            if has_start_limit:
                query = """
                    SELECT c.tipo, 
                           SUM(CASE 
                                WHEN u.nome = ? THEN d.valor_cota 
                                WHEN d.id IS NULL AND ? = 'Eu' THEN t.valor_total
                                ELSE 0 
                               END) as cota_perfil
                    FROM Transacoes t 
                    JOIN Categorias c ON t.categoria_id = c.id
                    LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                    LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE (
                        (substr(t.data, 7, 4) > ?)
                        OR (substr(t.data, 7, 4) = ? AND substr(t.data, 4, 2) >= ?)
                    ) AND (
                        (substr(t.data, 7, 4) < ?)
                        OR (substr(t.data, 7, 4) = ? AND substr(t.data, 4, 2) < ?)
                    )
                    GROUP BY c.tipo
                """
                cursor.execute(query, [perfil_nome, perfil_nome, start_ano_str, start_ano_str, start_mes_str, str(ano), str(ano), mes_num])
            else:
                query = """
                    SELECT c.tipo, 
                           SUM(CASE 
                                WHEN u.nome = ? THEN d.valor_cota 
                                WHEN d.id IS NULL AND ? = 'Eu' THEN t.valor_total
                                ELSE 0 
                               END) as cota_perfil
                    FROM Transacoes t 
                    JOIN Categorias c ON t.categoria_id = c.id
                    LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                    LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE (substr(t.data, 7, 4) < ?) 
                       OR (substr(t.data, 7, 4) = ? AND substr(t.data, 4, 2) < ?)
                    GROUP BY c.tipo
                """
                cursor.execute(query, [perfil_nome, perfil_nome, str(ano), str(ano), mes_num])
            
            resumo = {"Receita Fixa": 0, "Receita Variável": 0, "Despesa Fixa": 0, "Despesa Variável": 0, "Investimento": 0}
            for tipo, cota_p in cursor.fetchall():
                if tipo in resumo:
                    resumo[tipo] = cota_p if cota_p is not None else 0
                    
            receitas = resumo.get("Receita Fixa", 0) + resumo.get("Receita Variável", 0)
            despesas = resumo.get("Despesa Fixa", 0) + resumo.get("Despesa Variável", 0)
            investido = resumo.get("Investimento", 0)
            
            result = receitas - despesas - investido
            if has_start_limit:
                result += initial_balance
            return result

    def get_range_anos(self):
        current_year = datetime.datetime.now().year
        anos = {str(current_year)}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT substr(data, 7, 4) FROM Transacoes")
            for row in cursor.fetchall():
                if row[0]:
                    anos.add(row[0])
        
        # Retorna lista ordenada
        return sorted(list(anos))

    def get_perfis(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT nome FROM Usuarios_Familia ORDER BY id")
                perfis = [row[0] for row in cursor.fetchall()]
                return perfis if perfis else ["Eu"]
            except Exception:
                return ["Eu"]

    def get_resumo_estruturado(self, mes, ano, perfil_nome="Eu"):
        months_map = {"Janeiro":"01","Fevereiro":"02","Março":"03","Abril":"04","Maio":"05","Junho":"06",
                      "Julho":"07","Agosto":"08","Setembro":"09","Outubro":"10","Novembro":"11","Dezembro":"12"}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            mes_num = months_map.get(mes, "01")
            cursor.execute("SELECT id, nome, tipo, parent_id FROM Categorias")
            cats = cursor.fetchall()
            
            # Soma a cota do perfil selecionado
            query = """
                SELECT t.categoria_id, 
                       SUM(CASE 
                            WHEN u.nome = ? THEN d.valor_cota 
                            WHEN d.id IS NULL AND ? = 'Eu' THEN t.valor_total
                            ELSE 0 
                           END)
                FROM Transacoes t
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
            """
            
            if mes:
                query += " WHERE substr(t.data, 4, 2) = ? AND substr(t.data, 7, 4) = ? GROUP BY t.categoria_id"
                cursor.execute(query, (perfil_nome, perfil_nome, mes_num, str(ano)))
            else:
                query += " WHERE substr(t.data, 7, 4) = ? GROUP BY t.categoria_id"
                cursor.execute(query, (perfil_nome, perfil_nome, str(ano)))
                
            somas = dict(cursor.fetchall())
            return cats, somas

    def get_evolucao_anual(self, ano, perfil_nome="Eu"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Agrupar Receitas e Despesas por mês do ano
            query = """
                SELECT substr(t.data, 4, 2) as mes, c.tipo,
                       SUM(CASE 
                            WHEN u.nome = ? THEN d.valor_cota 
                            WHEN d.id IS NULL AND ? = 'Eu' THEN t.valor_total
                            ELSE 0 
                           END)
                FROM Transacoes t
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                WHERE substr(t.data, 7, 4) = ?
                GROUP BY substr(t.data, 4, 2), c.tipo
            """
            cursor.execute(query, (perfil_nome, perfil_nome, str(ano)))
            resultados = cursor.fetchall()
            
            # Estruturar o retorno { "01": {"Receitas": 0, "Despesas": 0}, ... }
            evolucao = {str(i).zfill(2): {"Receitas": 0.0, "Despesas": 0.0} for i in range(1, 13)}
            
            for mes, tipo, valor in resultados:
                if valor is None:
                    valor = 0.0
                if "Receita" in tipo:
                    evolucao[mes]["Receitas"] += valor
                elif "Despesa" in tipo:
                    evolucao[mes]["Despesas"] += valor
                    
            return evolucao

    def get_gastos_diarios_mes(self, mes, ano, perfil_nome="Eu"):
        months_map = {"Janeiro":"01","Fevereiro":"02","Março":"03","Abril":"04","Maio":"05","Junho":"06",
                      "Julho":"07","Agosto":"08","Setembro":"09","Outubro":"10","Novembro":"11","Dezembro":"12"}
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT substr(t.data, 1, 2) as dia, c.tipo,
                       SUM(CASE 
                            WHEN u.nome = ? THEN d.valor_cota 
                            WHEN d.id IS NULL AND ? = 'Eu' THEN t.valor_total
                            ELSE 0 
                           END)
                FROM Transacoes t
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
            """
            
            if mes:
                mes_num = months_map.get(mes, "01")
                query += " WHERE substr(t.data, 4, 2) = ? AND substr(t.data, 7, 4) = ?"
                params = (perfil_nome, perfil_nome, mes_num, str(ano))
            else:
                query += " WHERE substr(t.data, 7, 4) = ?"
                params = (perfil_nome, perfil_nome, str(ano))
                
            query += " GROUP BY substr(t.data, 1, 2), c.tipo"
            
            cursor.execute(query, params)
            resultados = cursor.fetchall()
            
            diario = {}
            for dia, tipo, valor in resultados:
                if valor is None:
                    valor = 0.0
                if dia not in diario:
                    diario[dia] = {"Receitas": 0.0, "Despesas": 0.0}
                if "Receita" in tipo:
                    diario[dia]["Receitas"] += valor
                elif "Despesa" in tipo:
                    diario[dia]["Despesas"] += valor
                    
            return diario

    # ==========================
    # MÉTODOS DO MÓDULO DE CARTÕES
    # ==========================
    
    def add_cartao(self, nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, digitos):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Cartoes (nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, digitos)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, digitos))
            conn.commit()
            return True, "Cartão adicionado com sucesso."
        except Exception as e:
            logger.error("Erro ao adicionar cartão", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def get_cartoes(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, digitos FROM Cartoes ORDER BY nome")
            return cursor.fetchall()
        except Exception:
            logger.error("Erro ao obter cartões", exc_info=True)
            return []
        finally:
            conn.close()

    def update_cartao(self, cartao_id, nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, digitos):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE Cartoes 
                SET nome = ?, limite = ?, dia_fechamento = ?, dia_vencimento = ?, cor = ?, bandeira = ?, dono = ?, digitos = ?
                WHERE id = ?
            ''', (nome, limite, dia_fechamento, dia_vencimento, cor, bandeira, dono, digitos, cartao_id))
            conn.commit()
            return True, "Cartão atualizado com sucesso."
        except Exception as e:
            logger.error("Erro ao atualizar cartão", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def delete_cartao(self, cartao_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Cartoes WHERE id = ?", (cartao_id,))
            conn.commit()
            return True, "Cartão excluído com sucesso."
        except Exception as e:
            logger.error("Erro ao excluir cartão", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def get_gasto_cartao_mes(self, bandeira, dono, mes_num, ano):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(valor_total) FROM Transacoes 
                WHERE (bandeira_cartao = ? AND dono_cartao = ?) 
                  AND tipo_transacao LIKE 'Despesa%'
                  AND substr(data, 4, 2) = ? 
                  AND substr(data, 7, 4) = ?
            """, (bandeira, dono, mes_num, str(ano)))
            res = cursor.fetchone()
            return res[0] if res[0] is not None else 0.0
        except Exception:
            logger.error("Erro ao calcular gasto do cartão no mês", exc_info=True)
            return 0.0
        finally:
            conn.close()

    def get_gasto_cartao_total(self, bandeira, dono, mes_num, ano):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            target_period = f"{str(ano)}-{str(mes_num).zfill(2)}"
            cursor.execute("""
                SELECT SUM(valor_total) FROM Transacoes 
                WHERE (bandeira_cartao = ? AND dono_cartao = ?) 
                  AND tipo_transacao LIKE 'Despesa%'
                  AND (substr(data, 7, 4) || '-' || substr(data, 4, 2)) >= ?
            """, (bandeira, dono, target_period))
            res = cursor.fetchone()
            return res[0] if res[0] is not None else 0.0
        except Exception:
            logger.error("Erro ao calcular gasto total do cartão", exc_info=True)
            return 0.0
        finally:
            conn.close()

    # ── INVESTIMENTOS ────────────────────────────────────────────

    def get_total_investido_cumulativo(self, perfil_nome="Eu"):
        """Soma acumulada de todos os lançamentos do tipo Investimento menos os Resgates de Investimento."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # 1. Obter total de aportes
            query_aportes = """
                SELECT SUM(
                    CASE 
                        WHEN d.id IS NULL AND ? = 'Eu' THEN t.valor_total
                        WHEN u.nome = ? THEN d.valor_cota
                        ELSE 0
                    END
                )
                FROM Transacoes t
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                WHERE t.tipo_transacao = 'Investimento'
                AND (u.nome = ? OR d.id IS NULL)
            """
            cursor.execute(query_aportes, [perfil_nome, perfil_nome, perfil_nome])
            aportes = cursor.fetchone()[0] or 0.0

            # 2. Obter total de resgates
            query_resgates = """
                SELECT SUM(
                    CASE 
                        WHEN d.id IS NULL AND ? = 'Eu' THEN t.valor_total
                        WHEN u.nome = ? THEN d.valor_cota
                        ELSE 0
                    END
                )
                FROM Transacoes t
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                WHERE c.nome = 'Resgate de Investimento'
                AND (u.nome = ? OR d.id IS NULL)
                AND t.id >= (
                    SELECT COALESCE(MIN(id), 999999999)
                    FROM Transacoes
                    WHERE tipo_transacao = 'Investimento'
                )
            """
            cursor.execute(query_resgates, [perfil_nome, perfil_nome, perfil_nome])
            resgates = cursor.fetchone()[0] or 0.0

            return max(0.0, aportes - resgates)
        except Exception:
            logger.error("Erro ao obter total investido", exc_info=True)
            return 0.0
        finally:
            conn.close()

    def get_carteira(self):
        """Retorna todas as operações de compra/venda registradas na carteira."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, ticker, tipo_ativo, operacao, quantidade, preco_unitario, data, corretora, observacao,
                       data_vencimento, percentual_cdi, subtipo_investimento, transacao_id
                FROM Carteira_Investimentos
                ORDER BY data DESC
            """)
            return cursor.fetchall()
        except Exception:
            logger.error("Erro ao obter carteira", exc_info=True)
            return []
        finally:
            conn.close()

    def add_operacao_carteira(self, ticker, tipo_ativo, operacao, quantidade, preco_unitario, data, 
                              corretora=None, observacao=None, data_vencimento=None, percentual_cdi=None, 
                              subtipo_investimento=None, transacao_id=None):
        """Registra uma operação de compra ou venda de ativo."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Carteira_Investimentos
                    (ticker, tipo_ativo, operacao, quantidade, preco_unitario, data, corretora, observacao,
                     data_vencimento, percentual_cdi, subtipo_investimento, transacao_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [ticker.upper(), tipo_ativo, operacao, quantidade, preco_unitario, data, corretora, observacao,
                  data_vencimento, percentual_cdi, subtipo_investimento, transacao_id])
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error("Erro ao adicionar operação", exc_info=True)
            return None
        finally:
            conn.close()

    def delete_operacao_carteira(self, op_id):
        """Remove permanentemente uma operação da carteira e a transação associada."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # 1. Buscar transacao_id associada
            cursor.execute("SELECT transacao_id FROM Carteira_Investimentos WHERE id = ?", [op_id])
            row = cursor.fetchone()
            transacao_id = row[0] if row else None

            # 2. Deletar da carteira
            cursor.execute("DELETE FROM Carteira_Investimentos WHERE id = ?", [op_id])

            # 3. Deletar a transação e suas divisões associadas se houver
            if transacao_id:
                cursor.execute("DELETE FROM Divisoes_Transacao WHERE transacao_id = ?", [transacao_id])
                cursor.execute("DELETE FROM Transacoes WHERE id = ?", [transacao_id])

            conn.commit()
            return True
        except Exception:
            logger.error("Erro ao excluir operação", exc_info=True)
            return False
        finally:
            conn.close()

    def get_dividendos_mes(self, mes, ano, perfil_nome="Eu"):
        """Soma de dividendos/rendimentos de ações e FIIs no mês/ano informado."""
        months_map = {"Janeiro":"01","Fevereiro":"02","Março":"03","Abril":"04","Maio":"05","Junho":"06",
                      "Julho":"07","Agosto":"08","Setembro":"09","Outubro":"10","Novembro":"11","Dezembro":"12"}
        mes_num = months_map.get(mes, "01")
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            query = """
                SELECT SUM(
                    CASE
                        WHEN d.id IS NULL AND ? = 'Eu' THEN t.valor_total
                        WHEN u.nome = ? THEN d.valor_cota
                        ELSE 0
                    END
                )
                FROM Transacoes t
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                WHERE t.tipo_transacao = 'Receita Variável'
                AND c.nome IN ('Rendimentos de Ações', 'Rendimentos de FIIs')
                AND substr(t.data, 4, 2) = ?
                AND substr(t.data, 7, 4) = ?
                AND (u.nome = ? OR d.id IS NULL)
            """
            cursor.execute(query, [perfil_nome, perfil_nome, mes_num, str(ano), perfil_nome])
            result = cursor.fetchone()[0]
            return result or 0.0
        except Exception:
            logger.error("Erro ao obter dividendos do mês", exc_info=True)
            return 0.0
        finally:
            conn.close()

    # ── MÉTODOS ADICIONAIS DO PERFIL E METAS ──────────────────────────────────
    def get_anotacoes_usuario(self, nome):
        if nome == "Eu":
            return ""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT anotacoes FROM Usuarios_Familia WHERE nome = ?", (nome,))
            res = cursor.fetchone()
            if res:
                return res[0] or ""
            return ""
        except Exception as e:
            logger.error("Erro ao obter anotações do usuário", exc_info=True)
            return ""
        finally:
            conn.close()

    def update_anotacoes_usuario(self, nome, anotacoes):
        if nome == "Eu":
            return False, "O perfil principal não possui anotações persistidas por esta rota."
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM Usuarios_Familia WHERE nome = ?", (nome,))
            res = cursor.fetchone()
            if not res:
                cursor.execute("INSERT INTO Usuarios_Familia (nome, anotacoes) VALUES (?, ?)", (nome, anotacoes))
            else:
                cursor.execute("UPDATE Usuarios_Familia SET anotacoes = ? WHERE nome = ?", (anotacoes, nome))
            conn.commit()
            return True, "Anotações salvas com sucesso."
        except Exception as e:
            logger.error("Erro ao atualizar anotações do usuário", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def adicionar_usuario(self, nome):
        if not nome or not nome.strip():
            return False, "Nome do perfil não pode ser vazio."
        nome = nome.strip()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM Usuarios_Familia WHERE nome = ?", (nome,))
            if cursor.fetchone():
                return False, "Este perfil já existe."
            cursor.execute("INSERT INTO Usuarios_Familia (nome) VALUES (?)", (nome,))
            conn.commit()
            return True, "Perfil adicionado com sucesso."
        except Exception as e:
            logger.error("Erro ao adicionar usuário", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def excluir_usuario(self, nome):
        if nome == "Eu":
            return False, "O perfil principal 'Eu' não pode ser excluído."
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM Usuarios_Familia WHERE nome = ?", (nome,))
            res = cursor.fetchone()
            if not res:
                return False, "Perfil não encontrado."
            u_id = res[0]
            
            # Obter o id do perfil principal 'Eu'
            cursor.execute("SELECT id FROM Usuarios_Familia WHERE nome = 'Eu'")
            res_eu = cursor.fetchone()
            if not res_eu:
                cursor.execute("INSERT INTO Usuarios_Familia (nome) VALUES ('Eu')")
                eu_id = cursor.lastrowid
            else:
                eu_id = res_eu[0]
                
            # Transferir todas as divisões do usuário excluído para 'Eu'
            # 1. Divisões de Transações
            cursor.execute("""
                SELECT d_del.transacao_id, d_del.valor_cota, d_eu.id
                FROM Divisoes_Transacao d_del
                LEFT JOIN Divisoes_Transacao d_eu ON d_del.transacao_id = d_eu.transacao_id AND d_eu.usuario_id = ?
                WHERE d_del.usuario_id = ?
            """, (eu_id, u_id))
            divs_to_transfer = cursor.fetchall()
            
            for trans_id, cota, eu_div_id in divs_to_transfer:
                if eu_div_id:
                    cursor.execute("UPDATE Divisoes_Transacao SET valor_cota = valor_cota + ? WHERE id = ?", (cota, eu_div_id))
                else:
                    cursor.execute("INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota) VALUES (?, ?, ?)", (trans_id, eu_id, cota))
            
            cursor.execute("DELETE FROM Divisoes_Transacao WHERE usuario_id = ?", (u_id,))
            
            # 2. Divisões de Recorrências
            cursor.execute("""
                SELECT d_del.recorrencia_id, d_del.valor_cota, d_eu.id
                FROM Divisoes_Recorrencia d_del
                LEFT JOIN Divisoes_Recorrencia d_eu ON d_del.recorrencia_id = d_eu.recorrencia_id AND d_eu.usuario_id = ?
                WHERE d_del.usuario_id = ?
            """, (eu_id, u_id))
            rec_divs_to_transfer = cursor.fetchall()
            
            for rec_id, cota, eu_rec_div_id in rec_divs_to_transfer:
                if eu_rec_div_id:
                    cursor.execute("UPDATE Divisoes_Recorrencia SET valor_cota = valor_cota + ? WHERE id = ?", (cota, eu_rec_div_id))
                else:
                    cursor.execute("INSERT INTO Divisoes_Recorrencia (recorrencia_id, usuario_id, valor_cota) VALUES (?, ?, ?)", (rec_id, eu_id, cota))
            
            cursor.execute("DELETE FROM Divisoes_Recorrencia WHERE usuario_id = ?", (u_id,))
            
            # E agora podemos excluir o perfil
            cursor.execute("DELETE FROM Usuarios_Familia WHERE id = ?", (u_id,))
            conn.commit()
            return True, "Perfil excluído com sucesso e suas compras foram transferidas para 'Eu'."
        except Exception as e:
            logger.error("Erro ao excluir usuário", exc_info=True)
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def get_categoria_id_by_nome(self, nome):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM Categorias WHERE nome = ?", (nome,))
            res = cursor.fetchone()
            return res[0] if res else None
        finally:
            conn.close()

    def get_dividendos_detalhados_mes(self, mes, ano, perfil_nome="Eu"):
        months_map = {"Janeiro":"01","Fevereiro":"02","Março":"03","Abril":"04","Maio":"05","Junho":"06",
                      "Julho":"07","Agosto":"08","Setembro":"09","Outubro":"10","Novembro":"11","Dezembro":"12"}
        mes_num = months_map.get(mes, "01")
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            query = """
                SELECT t.id, COALESCE(t.data_real, t.data) as data, t.descricao, 
                       CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor,
                       c.nome, t.observacao
                FROM Transacoes t
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                WHERE t.tipo_transacao = 'Receita Variável'
                AND c.nome IN ('Rendimentos de Ações', 'Rendimentos de FIIs')
                AND substr(t.data, 4, 2) = ?
                AND substr(t.data, 7, 4) = ?
                AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                ORDER BY substr(t.data, 7, 4) DESC, substr(t.data, 4, 2) DESC, substr(t.data, 1, 2) DESC
            """
            cursor.execute(query, [mes_num, str(ano), perfil_nome, perfil_nome])
            return cursor.fetchall()
        except Exception:
            logger.error("Erro ao obter detalhe de dividendos", exc_info=True)
            return []
        finally:
            conn.close()

    def get_metas(self, perfil_nome="Eu"):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, descricao, tipo_meta, valor_objetivo, aporte_mensal, target_ticker, target_categoria, created_at
                FROM Metas_Investimentos
                WHERE perfil = ?
                ORDER BY id DESC
            """, [perfil_nome])
            return cursor.fetchall()
        except Exception:
            logger.error("Erro ao obter metas de investimento", exc_info=True)
            return []
        finally:
            conn.close()

    def add_meta(self, descricao, tipo_meta, valor_objetivo, aporte_mensal, target_ticker=None, target_categoria=None, perfil_nome="Eu"):
        import datetime
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            created_at = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            cursor.execute("""
                INSERT INTO Metas_Investimentos (descricao, tipo_meta, valor_objetivo, aporte_mensal, target_ticker, target_categoria, perfil, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [descricao, tipo_meta, valor_objetivo, aporte_mensal, target_ticker, target_categoria, perfil_nome, created_at])
            conn.commit()
            return cursor.lastrowid
        except Exception:
            logger.error("Erro ao adicionar meta de investimento", exc_info=True)
            return None
        finally:
            conn.close()

    def delete_meta(self, meta_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Metas_Investimentos WHERE id = ?", [meta_id])
            conn.commit()
            return True
        except Exception:
            logger.error("Erro ao excluir meta de investimento", exc_info=True)
            return False
        finally:
            conn.close()

    def atualizar_cdi_sgs(self):
        import urllib.request
        import json
        import ssl
        import datetime
        hoje = datetime.date.today()
        ref_mes = hoje.strftime("%Y-%m")
        last_fetch = self.get_preferencia("cdi_last_fetch", "")
        if last_fetch == ref_mes:
            try:
                return float(self.get_preferencia("cdi_latest_rate", "10.50"))
            except ValueError:
                return 10.50
        try:
            context = ssl._create_unverified_context()
            url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/1?formato=json"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, context=context, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data and isinstance(data, list) and len(data) > 0:
                    valor_str = data[0].get("valor")
                    if valor_str:
                        valor = float(valor_str)
                        self.set_preferencia("cdi_latest_rate", f"{valor:.2f}")
                        self.set_preferencia("cdi_last_fetch", ref_mes)
                        logger.info(f"CDI updated successfully to {valor:.2f}% (ref: {ref_mes})")
                        return valor
        except Exception as e:
            logger.error(f"Erro ao buscar CDI na API: {e}", exc_info=True)
        try:
            return float(self.get_preferencia("cdi_latest_rate", "10.50"))
        except ValueError:
            return 10.50

    # ── MÉTODOS DO MÓDULO DE FINANCIAMENTOS ──────────────────────────────────
    def get_ou_criar_categoria_emprestimo(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM Categorias WHERE nome = ? AND tipo = ?", ("Empréstimo", "Despesa Fixa"))
            res = cursor.fetchone()
            if res:
                return res[0]
            
            cursor.execute("SELECT id FROM Categorias WHERE nome = ?", ("FIXOS OUTROS",))
            parent = cursor.fetchone()
            parent_id = parent[0] if parent else None
            
            cursor.execute("INSERT INTO Categorias (nome, tipo, parent_id, has_subcategories) VALUES (?, ?, ?, 0)",
                           ("Empréstimo", "Despesa Fixa", parent_id))
            conn.commit()
            return cursor.lastrowid
        except Exception:
            logger.error("Erro ao obter/criar categoria empréstimo despesa", exc_info=True)
            return None
        finally:
            conn.close()

    def get_contas(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome_conta, tipo_conta FROM Contas ORDER BY nome_conta")
            return cursor.fetchall()
        except Exception:
            logger.error("Erro ao obter contas", exc_info=True)
            return []
        finally:
            conn.close()

    def add_financiamento(self, credor, data_inicio, valor_total, total_parcelas, taxa_juros, tipo_juros, sistema_amortizacao, conta_id, perfil_nome, observacao):
        conn = self.get_connection()
        import datetime
        try:
            cursor = conn.cursor()
            
            # 1. Get or create category "Empréstimo (Entrada)" (Receita Fixa)
            cursor.execute("SELECT id FROM Categorias WHERE nome = ? AND tipo = ?", ("Empréstimo (Entrada)", "Receita Fixa"))
            cat_receita_row = cursor.fetchone()
            if cat_receita_row:
                cat_receita_id = cat_receita_row[0]
            else:
                cursor.execute("SELECT id FROM Categorias WHERE nome = ?", ("RENDA",))
                parent_row = cursor.fetchone()
                parent_id = parent_row[0] if parent_row else None
                cursor.execute("INSERT INTO Categorias (nome, tipo, parent_id, has_subcategories) VALUES (?, ?, ?, 0)",
                               ("Empréstimo (Entrada)", "Receita Fixa", parent_id))
                cat_receita_id = cursor.lastrowid
            
            # 2. Insert the inflow transaction
            desc_credito = f"Crédito Empréstimo - {credor}"
            cursor.execute('''
                INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                                        metodo_pagamento, parcela_atual, total_parcelas, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?)
            ''', (conta_id, cat_receita_id, desc_credito, data_inicio, valor_total, "Receita Fixa", "Dinheiro", observacao))
            credito_trans_id = cursor.lastrowid
            
            # If perfil_nome != "Eu", create division
            if perfil_nome != "Eu":
                cursor.execute("SELECT id FROM Usuarios_Familia WHERE nome = ?", (perfil_nome,))
                user_row = cursor.fetchone()
                if user_row:
                    user_id = user_row[0]
                else:
                    cursor.execute("INSERT INTO Usuarios_Familia (nome) VALUES (?)", (perfil_nome,))
                    user_id = cursor.lastrowid
                
                cursor.execute('''
                    INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota)
                    VALUES (?, ?, ?)
                ''', (credito_trans_id, user_id, valor_total))

            # 3. Insert the financing contract
            cursor.execute('''
                INSERT INTO Financiamentos (credor, data_inicio, valor_total, total_parcelas, taxa_juros, tipo_juros, 
                                            sistema_amortizacao, conta_id, credito_transacao_id, perfil_nome, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (credor, data_inicio, valor_total, total_parcelas, taxa_juros, tipo_juros, 
                  sistema_amortizacao, conta_id, credito_trans_id, perfil_nome, observacao))
            financiamento_id = cursor.lastrowid
            
            # 4. Generate future parcels if NOT Flexible
            if sistema_amortizacao != "Flexível":
                # Get or create category "Empréstimo" (Despesa Fixa)
                cursor.execute("SELECT id FROM Categorias WHERE nome = ? AND tipo = ?", ("Empréstimo", "Despesa Fixa"))
                cat_despesa_row = cursor.fetchone()
                if cat_despesa_row:
                    cat_despesa_id = cat_despesa_row[0]
                else:
                    cursor.execute("SELECT id FROM Categorias WHERE nome = ?", ("FIXOS OUTROS",))
                    parent_row = cursor.fetchone()
                    parent_id = parent_row[0] if parent_row else None
                    cursor.execute("INSERT INTO Categorias (nome, tipo, parent_id, has_subcategories) VALUES (?, ?, ?, 0)",
                                   ("Empréstimo", "Despesa Fixa", parent_id))
                    cat_despesa_id = cursor.lastrowid
                
                try:
                    dt_base = datetime.datetime.strptime(data_inicio, "%d/%m/%Y")
                except Exception:
                    dt_base = datetime.datetime.now()
                    
                def add_months(dt, m):
                    month = dt.month + m
                    year = dt.year + (month - 1) // 12
                    month = (month - 1) % 12 + 1
                    day = min(dt.day, 28)
                    return datetime.datetime(year, month, day)
                
                rate = taxa_juros / 100.0
                if tipo_juros == "Anual":
                    rate = rate / 12.0
                
                amortization_const = round(valor_total / total_parcelas, 2)
                
                if sistema_amortizacao == "Price":
                    if rate > 0:
                        val_prestacao_price = round(valor_total * (rate * (1 + rate)**total_parcelas) / ((1 + rate)**total_parcelas - 1), 2)
                    else:
                        val_prestacao_price = round(valor_total / total_parcelas, 2)
                
                saldo_devedor = valor_total
                
                for k in range(1, total_parcelas + 1):
                    dt_parcela = add_months(dt_base, k)
                    data_str = dt_parcela.strftime("%d/%m/%Y")
                    
                    if sistema_amortizacao == "SAC":
                        val_amortizacao = amortization_const if k < total_parcelas else round(saldo_devedor, 2)
                        val_juros = round(saldo_devedor * rate, 2)
                        val_prestacao = round(val_amortizacao + val_juros, 2)
                        saldo_devedor = round(saldo_devedor - val_amortizacao, 2)
                    elif sistema_amortizacao == "Price":
                        val_juros = round(saldo_devedor * rate, 2)
                        if k < total_parcelas:
                            val_amortizacao = round(val_prestacao_price - val_juros, 2)
                        else:
                            val_amortizacao = round(saldo_devedor, 2)
                        val_prestacao = round(val_amortizacao + val_juros, 2)
                        saldo_devedor = round(saldo_devedor - val_amortizacao, 2)
                    else: # Sem Juros
                        val_juros = 0.0
                        val_amortizacao = amortization_const if k < total_parcelas else round(saldo_devedor, 2)
                        val_prestacao = val_amortizacao
                        saldo_devedor = round(saldo_devedor - val_amortizacao, 2)
                    
                    desc_despesa = f"{credor} - Parcela {k}/{total_parcelas}"
                    cursor.execute('''
                        INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                                                metodo_pagamento, parcela_atual, total_parcelas, observacao)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (conta_id, cat_despesa_id, desc_despesa, data_str, val_prestacao, "Despesa Fixa", "Dinheiro", k, total_parcelas, observacao))
                    trans_id = cursor.lastrowid
                    
                    if perfil_nome != "Eu":
                        cursor.execute('''
                            INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota)
                            VALUES (?, ?, ?)
                        ''', (trans_id, user_id, val_prestacao))
                        
                    cursor.execute('''
                        INSERT INTO Parcelas_Financiamento (financiamento_id, transacao_id, numero_parcela, valor_amortizacao, valor_juros)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (financiamento_id, trans_id, k, val_amortizacao, val_juros))

            conn.commit()
            return True, "Financiamento lançado com sucesso."
        except Exception as e:
            logger.error("Erro ao adicionar financiamento", exc_info=True)
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def add_amortizacao_manual(self, financiamento_id, valor, data_op, conta_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Fetch financing info
            cursor.execute("SELECT credor, perfil_nome FROM Financiamentos WHERE id = ?", (financiamento_id,))
            fin_row = cursor.fetchone()
            if not fin_row:
                return False, "Financiamento não encontrado."
            credor, perfil_nome = fin_row
            
            # Get next parcel number
            cursor.execute("SELECT COUNT(*) FROM Parcelas_Financiamento WHERE financiamento_id = ?", (financiamento_id,))
            num_parcelas = cursor.fetchone()[0]
            next_parcel_num = num_parcelas + 1
            
            # Get or create category "Empréstimo" (Despesa Fixa)
            cursor.execute("SELECT id FROM Categorias WHERE nome = ? AND tipo = ?", ("Empréstimo", "Despesa Fixa"))
            cat_row = cursor.fetchone()
            if cat_row:
                cat_despesa_id = cat_row[0]
            else:
                cursor.execute("SELECT id FROM Categorias WHERE nome = ?", ("FIXOS OUTROS",))
                parent_row = cursor.fetchone()
                parent_id = parent_row[0] if parent_row else None
                cursor.execute("INSERT INTO Categorias (nome, tipo, parent_id, has_subcategories) VALUES (?, ?, ?, 0)",
                               ("Empréstimo", "Despesa Fixa", parent_id))
                cat_despesa_id = cursor.lastrowid
                
            # Insert transaction
            desc = f"Amortização Empréstimo - {credor}"
            cursor.execute('''
                INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                                        metodo_pagamento, parcela_atual, total_parcelas, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (conta_id, cat_despesa_id, desc, data_op, valor, "Despesa Fixa", "Dinheiro", next_parcel_num, next_parcel_num, "Amortização Manual"))
            trans_id = cursor.lastrowid
            
            # Division if profile != "Eu"
            if perfil_nome != "Eu":
                cursor.execute("SELECT id FROM Usuarios_Familia WHERE nome = ?", (perfil_nome,))
                user_row = cursor.fetchone()
                if user_row:
                    user_id = user_row[0]
                else:
                    cursor.execute("INSERT INTO Usuarios_Familia (nome) VALUES (?)", (perfil_nome,))
                    user_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota)
                    VALUES (?, ?, ?)
                ''', (trans_id, user_id, valor))
                
            # Insert Parcela
            cursor.execute('''
                INSERT INTO Parcelas_Financiamento (financiamento_id, transacao_id, numero_parcela, valor_amortizacao, valor_juros)
                VALUES (?, ?, ?, ?, ?)
            ''', (financiamento_id, trans_id, next_parcel_num, valor, 0.0))
            
            conn.commit()
            return True, "Amortização registrada com sucesso."
        except Exception as e:
            logger.error("Erro ao registrar amortização manual", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def update_financiamento(self, fid, credor, data_inicio, valor_total, total_parcelas, taxa_juros, tipo_juros, sistema_amortizacao, conta_id, observacao):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE Financiamentos
                SET credor = ?, data_inicio = ?, valor_total = ?, total_parcelas = ?, 
                    taxa_juros = ?, tipo_juros = ?, sistema_amortizacao = ?, conta_id = ?, 
                    observacao = ?
                WHERE id = ?
            """, (credor, data_inicio, valor_total, total_parcelas, taxa_juros, tipo_juros, sistema_amortizacao, conta_id, observacao, fid))
            conn.commit()
            return True, "Financiamento atualizado com sucesso."
        except Exception as e:
            logger.error("Erro ao atualizar financiamento", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def delete_financiamento(self, financiamento_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get inflow credit transaction ID
            cursor.execute("SELECT credito_transacao_id FROM Financiamentos WHERE id = ?", (financiamento_id,))
            fin_row = cursor.fetchone()
            inflow_trans_id = fin_row[0] if fin_row else None
            
            # Get all amortization transaction IDs
            cursor.execute("SELECT transacao_id FROM Parcelas_Financiamento WHERE financiamento_id = ?", (financiamento_id,))
            trans_ids = [row[0] for row in cursor.fetchall() if row[0] is not None]
            
            # Combine all transaction IDs to delete
            all_trans_ids = []
            if inflow_trans_id:
                all_trans_ids.append(inflow_trans_id)
            all_trans_ids.extend(trans_ids)
            
            # Delete divisions and transactions
            if all_trans_ids:
                placeholders = ",".join("?" for _ in all_trans_ids)
                cursor.execute(f"DELETE FROM Divisoes_Transacao WHERE transacao_id IN ({placeholders})", all_trans_ids)
                cursor.execute(f"DELETE FROM Transacoes WHERE id IN ({placeholders})", all_trans_ids)
                
            # Delete parcels and the financing contract itself
            cursor.execute("DELETE FROM Parcelas_Financiamento WHERE financiamento_id = ?", (financiamento_id,))
            cursor.execute("DELETE FROM Financiamentos WHERE id = ?", (financiamento_id,))
            
            conn.commit()
            return True, "Financiamento excluído com sucesso."
        except Exception as e:
            logger.error("Erro ao excluir financiamento", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def get_financiamentos(self, perfil_nome="Eu"):
        conn = self.get_connection()
        import datetime
        hoje = datetime.date.today()
        
        def parse_date(d_str):
            try:
                return datetime.datetime.strptime(d_str, "%d/%m/%Y").date()
            except Exception:
                return hoje
                
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT f.id, f.credor, f.data_inicio, f.valor_total, f.total_parcelas, 
                       f.taxa_juros, f.tipo_juros, f.sistema_amortizacao, f.conta_id, 
                       c.nome_conta, f.observacao, f.credito_transacao_id
                FROM Financiamentos f
                LEFT JOIN Contas c ON f.conta_id = c.id
                WHERE f.perfil_nome = ?
                ORDER BY f.id DESC
            """, (perfil_nome,))
            rows = cursor.fetchall()
            
            result = []
            for r in rows:
                fid, credor, data_inicio, valor_total, total_parcelas, taxa_juros, tipo_juros, sistema, conta_id, nome_conta, observacao, credito_transacao_id = r
                
                # Fetch all parcels for this financing
                cursor.execute("""
                    SELECT pf.valor_amortizacao, pf.valor_juros, t.data
                    FROM Parcelas_Financiamento pf
                    JOIN Transacoes t ON pf.transacao_id = t.id
                    WHERE pf.financiamento_id = ?
                """, (fid,))
                parcels = cursor.fetchall()
                
                total_amortizado = 0.0
                total_juros = 0.0
                total_pago = 0.0
                
                for p_amort, p_juros, t_data in parcels:
                    dt = parse_date(t_data)
                    if dt <= hoje:
                        total_amortizado += p_amort
                        total_juros += p_juros
                        total_pago += (p_amort + p_juros)
                
                saldo_devedor = max(0.0, round(valor_total - total_amortizado, 2))
                quitado = (saldo_devedor <= 0.05)
                
                result.append({
                    "id": fid,
                    "credor": credor,
                    "data_inicio": data_inicio,
                    "valor_total": valor_total,
                    "total_parcelas": total_parcelas,
                    "taxa_juros": taxa_juros,
                    "tipo_juros": tipo_juros,
                    "sistema_amortizacao": sistema,
                    "conta_id": conta_id,
                    "nome_conta": nome_conta or "Sem Conta",
                    "observacao": observacao or "",
                    "credito_transacao_id": credito_transacao_id,
                    "total_amortizado": round(total_amortizado, 2),
                    "total_juros": round(total_juros, 2),
                    "total_pago": round(total_pago, 2),
                    "saldo_devedor": saldo_devedor,
                    "quitado": quitado
                })
            return result
        except Exception:
            logger.error("Erro ao obter financiamentos", exc_info=True)
            return []
        finally:
            conn.close()

    def get_financiamento_detalhes(self, financiamento_id):
        conn = self.get_connection()
        import datetime
        hoje = datetime.date.today()
        
        def parse_date(d_str):
            try:
                return datetime.datetime.strptime(d_str, "%d/%m/%Y").date()
            except Exception:
                return hoje
                
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT credor, valor_total FROM Financiamentos WHERE id = ?", (financiamento_id,))
            fin_row = cursor.fetchone()
            if not fin_row:
                return None
            credor, valor_total = fin_row
            
            cursor.execute("""
                SELECT pf.numero_parcela, t.data, pf.valor_amortizacao, pf.valor_juros, pf.transacao_id
                FROM Parcelas_Financiamento pf
                JOIN Transacoes t ON pf.transacao_id = t.id
                WHERE pf.financiamento_id = ?
                ORDER BY pf.numero_parcela ASC
            """, (financiamento_id,))
            rows = cursor.fetchall()
            
            parcelas = []
            saldo_restante = valor_total
            for r in rows:
                num_parcela, t_data, valor_amort, valor_juros, trans_id = r
                dt = parse_date(t_data)
                pago = (dt <= hoje)
                
                saldo_restante = round(saldo_restante - valor_amort, 2)
                
                parcelas.append({
                    "numero_parcela": num_parcela,
                    "data": t_data,
                    "valor_prestacao": round(valor_amort + valor_juros, 2),
                    "valor_amortizacao": round(valor_amort, 2),
                    "valor_juros": round(valor_juros, 2),
                    "saldo_devedor_restante": max(0.0, saldo_restante),
                    "transacao_id": trans_id,
                    "pago": pago
                })
                
            return {
                "credor": credor,
                "parcelas": parcelas
            }
        except Exception:
            logger.error("Erro ao obter detalhes do financiamento", exc_info=True)
            return None
        finally:
            conn.close()

    def get_abatimentos_pagos(self, perfil_nome="Eu"):
        conn = self.get_connection()
        import datetime
        hoje = datetime.date.today()
        
        def parse_date(d_str):
            try:
                return datetime.datetime.strptime(d_str, "%d/%m/%Y").date()
            except Exception:
                return hoje
                
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT f.credor, pf.numero_parcela, t.data, pf.valor_amortizacao, pf.valor_juros, pf.transacao_id, t.conta_id
                FROM Parcelas_Financiamento pf
                JOIN Financiamentos f ON pf.financiamento_id = f.id
                JOIN Transacoes t ON pf.transacao_id = t.id
                WHERE f.perfil_nome = ?
                ORDER BY substr(t.data, 7, 4) DESC, substr(t.data, 4, 2) DESC, substr(t.data, 1, 2) DESC
            """, (perfil_nome,))
            rows = cursor.fetchall()
            
            result = []
            for r in rows:
                credor, num_parcela, t_data, valor_amort, valor_juros, trans_id, conta_id = r
                dt = parse_date(t_data)
                if dt <= hoje:
                    result.append({
                        "credor": credor,
                        "numero_parcela": f"Parcela {num_parcela}" if num_parcela > 0 else "Avulsa",
                        "raw_numero_parcela": num_parcela,
                        "data": t_data,
                        "valor_pago": round(valor_amort + valor_juros, 2),
                        "valor_amortizacao": round(valor_amort, 2),
                        "valor_juros": round(valor_juros, 2),
                        "transacao_id": trans_id,
                        "conta_id": conta_id
                    })
            return result
        except Exception as e:
            logger.error("Erro ao obter abatimentos pagos", exc_info=True)
            return []
        finally:
            conn.close()

    def excluir_abatimento(self, transacao_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # 1. Buscar a parcela associada para identificar o financiamento e se é contratual
            cursor.execute("""
                SELECT pf.financiamento_id, pf.numero_parcela, f.sistema_amortizacao, f.total_parcelas, f.data_inicio
                FROM Parcelas_Financiamento pf
                JOIN Financiamentos f ON pf.financiamento_id = f.id
                WHERE pf.transacao_id = ?
            """, (transacao_id,))
            row = cursor.fetchone()
            if not row:
                return False, "Abatimento não encontrado."
            
            financiamento_id, num_parcela, sistema_amort, total_parc, data_inicio = row
            
            # Verificar se a transação é uma amortização manual avulsa
            cursor.execute("SELECT observacao FROM Transacoes WHERE id = ?", (transacao_id,))
            t_row = cursor.fetchone()
            observacao = t_row[0] if t_row else ""
            
            is_manual = (observacao == "Amortização Manual") or (sistema_amort == "Flexível")
            
            if is_manual:
                # Exclusão física: o cascade delete removerá a Parcela_Financiamento e as Divisões automaticamente
                cursor.execute("DELETE FROM Transacoes WHERE id = ?", (transacao_id,))
            else:
                # Exclusão lógica/reversão: redefine a data da parcela de volta para o vencimento original no futuro
                try:
                    import datetime
                    dt_base = datetime.datetime.strptime(data_inicio, "%d/%m/%Y")
                    # adiciona num_parcela meses
                    month = dt_base.month + num_parcela
                    year = dt_base.year + (month - 1) // 12
                    month = (month - 1) % 12 + 1
                    day = min(dt_base.day, 28)
                    dt_futura = datetime.datetime(year, month, day)
                    data_futura_str = dt_futura.strftime("%d/%m/%Y")
                except Exception:
                    data_futura_str = "01/01/2035" # Fallback para data futura
                
                cursor.execute("UPDATE Transacoes SET data = ? WHERE id = ?", (data_futura_str, transacao_id))
            
            conn.commit()
            return True, "Abatimento excluído/revertido com sucesso."
        except Exception as e:
            logger.error("Erro ao excluir abatimento", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def update_parcela_paga(self, trans_id, valor, data_op, conta_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Fetch existing parcel info
            cursor.execute("SELECT valor_juros FROM Parcelas_Financiamento WHERE transacao_id = ?", (trans_id,))
            p_row = cursor.fetchone()
            juros = p_row[0] if p_row else 0.0
            
            # Amortizacao is new total value minus juros
            amort = max(0.0, round(valor - juros, 2))
            
            # Update Transacoes
            cursor.execute("""
                UPDATE Transacoes
                SET data = ?, valor_total = ?, conta_id = ?
                WHERE id = ?
            """, (data_op, valor, conta_id, trans_id))
            
            # Update Parcelas_Financiamento
            cursor.execute("""
                UPDATE Parcelas_Financiamento
                SET valor_amortizacao = ?
                WHERE transacao_id = ?
            """, (amort, trans_id))
            
            conn.commit()
            return True, "Parcela atualizada com sucesso."
        except Exception as e:
            logger.error("Erro ao atualizar parcela paga", exc_info=True)
            return False, str(e)
        finally:
            conn.close()

    def add_config_recorrencia(self, nome, tipo_transacao, categoria_id, valor_padrao, metodo_pagamento, observacao, perfil="Eu", bandeira_cartao="", dono_cartao="", divisoes=None):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO Config_Recorrencias (nome, tipo_transacao, categoria_id, valor_padrao, metodo_pagamento, observacao, perfil, bandeira_cartao, dono_cartao)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nome, tipo_transacao, categoria_id, valor_padrao, metodo_pagamento, observacao, perfil, bandeira_cartao, dono_cartao))
                new_id = cursor.lastrowid
                
                if divisoes:
                    for nome_usuario, valor_cota in divisoes.items():
                        if valor_cota > 0:
                            usuario_id = self.obter_ou_criar_usuario(cursor, nome_usuario)
                            cursor.execute("""
                                INSERT INTO Divisoes_Recorrencia (recorrencia_id, usuario_id, valor_cota)
                                VALUES (?, ?, ?)
                            """, (new_id, usuario_id, valor_cota))
                conn.commit()
                return True, new_id
        except Exception as e:
            logger.error("Erro ao adicionar config recorrencia", exc_info=True)
            return False, str(e)

    def migrar_receitas_fixas_para_recorrencias(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Buscar todas as transações do tipo 'Receita Fixa' que não têm grupo_id iniciando com 'REC_'
                cursor.execute("""
                    SELECT t.id, t.descricao, t.categoria_id, t.valor_total, t.metodo_pagamento, t.observacao, t.conta_id, t.bandeira_cartao, t.dono_cartao
                    FROM Transacoes t
                    WHERE t.tipo_transacao = 'Receita Fixa' AND (t.grupo_id IS NULL OR t.grupo_id NOT LIKE 'REC_%')
                """)
                rows = cursor.fetchall()
                if not rows:
                    return
                
                for r in rows:
                    t_id, desc, cat_id, valor, metodo, obs, conta_id, bandeira, dono = r
                    
                    # Buscar divisões da transação
                    cursor.execute("""
                        SELECT u.nome, d.valor_cota
                        FROM Divisoes_Transacao d
                        JOIN Usuarios_Familia u ON d.usuario_id = u.id
                        WHERE d.transacao_id = ?
                    """, (t_id,))
                    divs = cursor.fetchall()
                    perfil_nome = "Eu"
                    if divs:
                        perfil_nome = divs[0][0]
                    
                    # Verificar se já existe uma configuração correspondente
                    cursor.execute("""
                        SELECT id FROM Config_Recorrencias 
                        WHERE nome = ? AND categoria_id = ? AND perfil = ? AND tipo_transacao = 'Receita Fixa'
                    """, (desc, cat_id, perfil_nome))
                    config_row = cursor.fetchone()
                    if config_row:
                        config_id = config_row[0]
                    else:
                        cursor.execute("""
                            INSERT INTO Config_Recorrencias (nome, tipo_transacao, categoria_id, valor_padrao, conta_id, metodo_pagamento, observacao, perfil, bandeira_cartao, dono_cartao)
                            VALUES (?, 'Receita Fixa', ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (desc, cat_id, valor, conta_id or 1, metodo, obs, perfil_nome, bandeira, dono))
                        config_id = cursor.lastrowid
                        
                        for u_name, cota in divs:
                            if cota > 0:
                                u_id = self.obter_ou_criar_usuario(cursor, u_name)
                                cursor.execute("""
                                    INSERT INTO Divisoes_Recorrencia (recorrencia_id, usuario_id, valor_cota)
                                    VALUES (?, ?, ?)
                                """, (config_id, u_id, cota))
                    
                    # Vincular a transação antiga
                    cursor.execute("UPDATE Transacoes SET grupo_id = ? WHERE id = ?", (f"REC_{config_id}", t_id))
                conn.commit()
        except Exception as e:
            logger.error("Erro na migração de receitas fixas para recorrências", exc_info=True)

    def get_configs_recorrencia(self, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT r.id, r.nome, r.tipo_transacao, r.categoria_id, r.valor_padrao, r.conta_id, r.metodo_pagamento, r.observacao, r.perfil, c.nome, r.bandeira_cartao, r.dono_cartao
                    FROM Config_Recorrencias r
                    JOIN Categorias c ON r.categoria_id = c.id
                    WHERE r.perfil = ? OR r.perfil = 'Eu'
                    ORDER BY r.nome
                """, (perfil,))
                return cursor.fetchall()
        except Exception as e:
            logger.error("Erro ao buscar configs recorrencia", exc_info=True)
            return []

    def get_divisions_recorrencia(self, config_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT u.nome, d.valor_cota
                    FROM Divisoes_Recorrencia d
                    JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE d.recorrencia_id = ?
                """, (config_id,))
                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            logger.error("Erro ao buscar divisões de recorrência", exc_info=True)
            return {}

    def delete_config_recorrencia(self, config_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM Divisoes_Recorrencia WHERE recorrencia_id = ?", (config_id,))
                cursor.execute("DELETE FROM Config_Recorrencias WHERE id = ?", (config_id,))
                conn.commit()
                return True, "Configuração de recorrência excluída."
        except Exception as e:
            logger.error("Erro ao excluir config recorrencia", exc_info=True)
            return False, str(e)

    def update_config_recorrencia(self, config_id, nome, tipo_transacao, categoria_id, valor_padrao, metodo_pagamento, observacao, bandeira_cartao="", dono_cartao="", divisoes=None):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE Config_Recorrencias
                    SET nome = ?, tipo_transacao = ?, categoria_id = ?, valor_padrao = ?, metodo_pagamento = ?, observacao = ?, bandeira_cartao = ?, dono_cartao = ?
                    WHERE id = ?
                """, (nome, tipo_transacao, categoria_id, valor_padrao, metodo_pagamento, observacao, bandeira_cartao, dono_cartao, config_id))
                
                cursor.execute("DELETE FROM Divisoes_Recorrencia WHERE recorrencia_id = ?", (config_id,))
                
                if divisoes:
                    for nome_usuario, valor_cota in divisoes.items():
                        if valor_cota > 0:
                            usuario_id = self.obter_ou_criar_usuario(cursor, nome_usuario)
                            cursor.execute("""
                                INSERT INTO Divisoes_Recorrencia (recorrencia_id, usuario_id, valor_cota)
                                VALUES (?, ?, ?)
                            """, (config_id, usuario_id, valor_cota))
                conn.commit()
                return True, "Configuração atualizada."
        except Exception as e:
            logger.error("Erro ao atualizar config recorrencia", exc_info=True)
            return False, str(e)

    def get_transacoes_recorrencia(self, config_id, perfil_nome="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                grupo_id = f"REC_{config_id}"
                cursor.execute("""
                    SELECT t.id, t.data, t.descricao, 
                           CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor_exibido, 
                           t.tipo_transacao, t.metodo_pagamento, t.observacao
                    FROM Transacoes t
                    LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                    LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE t.grupo_id = ? AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                    ORDER BY substr(t.data, 7, 4) ASC, substr(t.data, 4, 2) ASC, substr(t.data, 1, 2) ASC
                """, (grupo_id, perfil_nome, perfil_nome))
                return cursor.fetchall()
        except Exception as e:
            logger.error("Erro ao buscar transações de recorrência", exc_info=True)
            return []

    def gerar_transacoes_recorrentes(self, config_id, meses_lote, data_inicio_str, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT nome, tipo_transacao, categoria_id, valor_padrao, conta_id, metodo_pagamento, observacao, perfil, bandeira_cartao, dono_cartao
                    FROM Config_Recorrencias
                    WHERE id = ?
                """, (config_id,))
                config = cursor.fetchone()
                if not config:
                    return False
                
                nome, tipo_transacao, categoria_id, valor_padrao, conta_id, metodo, observacao, config_perfil, bandeira_cartao, dono_cartao = config
                
                try:
                    dt_base = datetime.datetime.strptime(data_inicio_str, "%d/%m/%Y")
                except Exception:
                    dt_base = datetime.datetime.now()
                
                grupo_id = f"REC_{config_id}"
                
                # Fetch divisions for this recurrence
                cursor.execute("""
                    SELECT u.nome, d.valor_cota
                    FROM Divisoes_Recorrencia d
                    JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE d.recorrencia_id = ?
                """, (config_id,))
                divs = cursor.fetchall()
                
                for i in range(meses_lote):
                    mes = dt_base.month + i
                    ano = dt_base.year + (mes - 1) // 12
                    mes = (mes - 1) % 12 + 1
                    dia = min(dt_base.day, 28)
                    dt_ocorr = datetime.datetime(ano, mes, dia)
                    data_str = dt_ocorr.strftime("%d/%m/%Y")
                    
                    mes_str = f"{mes:02d}"
                    ano_str = str(ano)
                    cursor.execute("""
                        SELECT COUNT(*) FROM Transacoes 
                        WHERE grupo_id = ? AND substr(data, 4, 2) = ? AND substr(data, 7, 4) = ?
                    """, (grupo_id, mes_str, ano_str))
                    if cursor.fetchone()[0] > 0:
                        continue
                    
                    cursor.execute("""
                        INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, data_real, valor_total, tipo_transacao, 
                                                metodo_pagamento, parcela_atual, total_parcelas, bandeira_cartao, dono_cartao, recorrencia, grupo_id, observacao)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, 'Recorrente', ?, ?)
                    """, (conta_id, categoria_id, nome, data_str, data_str, valor_padrao, tipo_transacao, metodo, bandeira_cartao, dono_cartao, grupo_id, observacao))
                    
                    transacao_id = cursor.lastrowid
                    
                    if divs:
                        for user_nome, val_cota in divs:
                            u_id = self.obter_ou_criar_usuario(cursor, user_nome)
                            cursor.execute("""
                                INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota)
                                VALUES (?, ?, ?)
                            """, (transacao_id, u_id, val_cota))
                    else:
                        usuario_id = self.obter_ou_criar_usuario(cursor, perfil)
                        cursor.execute("""
                            INSERT INTO Divisoes_Transacao (transacao_id, usuario_id, valor_cota)
                            VALUES (?, ?, ?)
                        """, (transacao_id, usuario_id, valor_padrao))
                    
                conn.commit()
                return True
        except Exception as e:
            logger.error("Erro ao gerar transações recorrentes", exc_info=True)
            return False

    def atualizar_transacao_recorrente(self, transacao_id, config_id, valor, alterar_futuros=False):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if not alterar_futuros:
                    cursor.execute("UPDATE Transacoes SET valor_total = ? WHERE id = ?", (valor, transacao_id))
                    cursor.execute("UPDATE Divisoes_Transacao SET valor_cota = ? WHERE transacao_id = ?", (valor, transacao_id))
                else:
                    cursor.execute("SELECT data FROM Transacoes WHERE id = ?", (transacao_id,))
                    row = cursor.fetchone()
                    if not row:
                        return False
                    data_limite_str = row[0]
                    dt_limite = datetime.datetime.strptime(data_limite_str, "%d/%m/%Y").date()
                    
                    grupo_id = f"REC_{config_id}"
                    cursor.execute("SELECT id, data FROM Transacoes WHERE grupo_id = ?", (grupo_id,))
                    rows = cursor.fetchall()
                    
                    for t_id, t_data in rows:
                        try:
                            t_dt = datetime.datetime.strptime(t_data, "%d/%m/%Y").date()
                        except:
                            continue
                        if t_dt >= dt_limite:
                            cursor.execute("UPDATE Transacoes SET valor_total = ? WHERE id = ?", (valor, t_id))
                            cursor.execute("UPDATE Divisoes_Transacao SET valor_cota = ? WHERE transacao_id = ?", (valor, t_id))
                            
                    cursor.execute("UPDATE Config_Recorrencias SET valor_padrao = ? WHERE id = ?", (valor, config_id))
                    
                conn.commit()
                return True
        except Exception as e:
            logger.error("Erro ao atualizar transação recorrente", exc_info=True)
            return False

    def excluir_transacao_recorrente(self, transacao_id, config_id, excluir_futuros=False):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if not excluir_futuros:
                    cursor.execute("DELETE FROM Divisoes_Transacao WHERE transacao_id = ?", (transacao_id,))
                    cursor.execute("DELETE FROM Transacoes WHERE id = ?", (transacao_id,))
                else:
                    cursor.execute("SELECT data FROM Transacoes WHERE id = ?", (transacao_id,))
                    row = cursor.fetchone()
                    if not row:
                        return False
                    data_limite_str = row[0]
                    dt_limite = datetime.datetime.strptime(data_limite_str, "%d/%m/%Y").date()
                    
                    grupo_id = f"REC_{config_id}"
                    cursor.execute("SELECT id, data FROM Transacoes WHERE grupo_id = ?", (grupo_id,))
                    rows = cursor.fetchall()
                    
                    for t_id, t_data in rows:
                        try:
                            t_dt = datetime.datetime.strptime(t_data, "%d/%m/%Y").date()
                        except:
                            continue
                        if t_dt >= dt_limite:
                            cursor.execute("DELETE FROM Divisoes_Transacao WHERE transacao_id = ?", (t_id,))
                            cursor.execute("DELETE FROM Transacoes WHERE id = ?", (t_id,))
                            
                conn.commit()
                return True
        except Exception as e:
            logger.error("Erro ao excluir transação recorrente", exc_info=True)
            return False

    def get_compras_parceladas(self, perfil_nome="Eu"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT t.grupo_id, MIN(COALESCE(t.data_real, t.data)) as data_inicio, t.descricao, 
                       SUM(CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END) as valor_total_exibido, 
                       t.total_parcelas, t.metodo_pagamento, t.bandeira_cartao, t.dono_cartao, t.categoria_id, c.nome,
                       SUM(t.valor_total) as valor_total_real
                FROM Transacoes t
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                WHERE t.total_parcelas > 1 AND t.grupo_id LIKE 'GRP_%' AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                GROUP BY t.grupo_id
                ORDER BY data_inicio DESC
            """
            cursor.execute(query, (perfil_nome, perfil_nome))
            return cursor.fetchall()

    def get_parcelas_compra(self, grupo_id, perfil_nome="Eu"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT t.id, COALESCE(t.data_real, t.data) as data, t.descricao, 
                       CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor_exibido,
                       t.parcela_atual, t.total_parcelas, t.metodo_pagamento, t.dono_cartao, t.bandeira_cartao,
                       t.valor_total, t.observacao, c.nome
                FROM Transacoes t
                JOIN Categorias c ON t.categoria_id = c.id
                LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                WHERE t.grupo_id = ? AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                ORDER BY t.parcela_atual ASC
            """
            cursor.execute(query, (grupo_id, perfil_nome, perfil_nome))
            return cursor.fetchall()

    # ==========================================
    # VEÍCULOS, PETS E SAÚDE
    # ==========================================

    def get_veiculos(self, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, placa, modelo, perfil FROM Veiculos WHERE perfil = ? ORDER BY modelo", (perfil,))
                return cursor.fetchall()
        except Exception as e:
            logger.error("Erro ao buscar veículos", exc_info=True)
            return []

    def add_veiculo(self, placa, modelo, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Veiculos (placa, modelo, perfil) VALUES (?, ?, ?)", (placa, modelo, perfil))
                conn.commit()
                return True, cursor.lastrowid
        except Exception as e:
            logger.error("Erro ao adicionar veículo", exc_info=True)
            return False, str(e)

    def update_veiculo(self, veiculo_id, placa, modelo):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Veiculos SET placa = ?, modelo = ? WHERE id = ?", (placa, modelo, veiculo_id))
                conn.commit()
                return True, "Veículo atualizado."
        except Exception as e:
            logger.error("Erro ao atualizar veículo", exc_info=True)
            return False, str(e)

    def delete_veiculo(self, veiculo_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Remove referências nas transações (ou mantém desvinculadas)
                cursor.execute("UPDATE Transacoes SET veiculo_id = NULL WHERE veiculo_id = ?", (veiculo_id,))
                cursor.execute("DELETE FROM Veiculos WHERE id = ?", (veiculo_id,))
                conn.commit()
                return True, "Veículo excluído."
        except Exception as e:
            logger.error("Erro ao excluir veículo", exc_info=True)
            return False, str(e)

    def get_pets(self, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, nome, raca, perfil FROM Pets WHERE perfil = ? ORDER BY nome", (perfil,))
                return cursor.fetchall()
        except Exception as e:
            logger.error("Erro ao buscar pets", exc_info=True)
            return []

    def add_pet(self, nome, raca, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Pets (nome, raca, perfil) VALUES (?, ?, ?)", (nome, raca, perfil))
                conn.commit()
                return True, cursor.lastrowid
        except Exception as e:
            logger.error("Erro ao adicionar pet", exc_info=True)
            return False, str(e)

    def update_pet(self, pet_id, nome, raca):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Pets SET nome = ?, raca = ? WHERE id = ?", (nome, raca, pet_id))
                conn.commit()
                return True, "Pet atualizado."
        except Exception as e:
            logger.error("Erro ao atualizar pet", exc_info=True)
            return False, str(e)

    def delete_pet(self, pet_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Transacoes SET pet_id = NULL WHERE pet_id = ?", (pet_id,))
                cursor.execute("DELETE FROM Pets WHERE id = ?", (pet_id,))
                conn.commit()
                return True, "Pet excluído."
        except Exception as e:
            logger.error("Erro ao excluir pet", exc_info=True)
            return False, str(e)

    def get_saude(self, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, nome, descricao, perfil FROM Saude WHERE perfil = ? ORDER BY nome", (perfil,))
                return cursor.fetchall()
        except Exception as e:
            logger.error("Erro ao buscar itens de saúde", exc_info=True)
            return []

    def add_saude(self, nome, descricao, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Saude (nome, descricao, perfil) VALUES (?, ?, ?)", (nome, descricao, perfil))
                conn.commit()
                return True, cursor.lastrowid
        except Exception as e:
            logger.error("Erro ao adicionar item de saúde", exc_info=True)
            return False, str(e)

    def update_saude(self, saude_id, nome, descricao):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Saude SET nome = ?, descricao = ? WHERE id = ?", (nome, descricao, saude_id))
                conn.commit()
                return True, "Item de saúde atualizado."
        except Exception as e:
            logger.error("Erro ao atualizar item de saúde", exc_info=True)
            return False, str(e)

    def delete_saude(self, saude_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Transacoes SET saude_id = NULL WHERE saude_id = ?", (saude_id,))
                cursor.execute("DELETE FROM Saude WHERE id = ?", (saude_id,))
                conn.commit()
                return True, "Item de saúde excluído."
        except Exception as e:
            logger.error("Erro ao excluir item de saúde", exc_info=True)
            return False, str(e)

    def get_transacoes_veiculo(self, veiculo_id, perfil_nome="Eu"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if veiculo_id == "geral":
                cursor.execute("SELECT id FROM Categorias WHERE UPPER(nome) = 'VEÍCULO'")
                row_p = cursor.fetchone()
                parent_id = row_p[0] if row_p else None
                query = """
                    SELECT t.id, COALESCE(t.data_real, t.data) as data, t.descricao, 
                           CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor_exibido, 
                           c.nome, t.tipo_transacao, 
                           t.parcela_atual, t.total_parcelas, t.metodo_pagamento, t.dono_cartao,
                           t.bandeira_cartao,
                           (SELECT COUNT(*) FROM Divisoes_Transacao WHERE transacao_id = t.id) as num_divisoes,
                           t.observacao,
                           t.valor_total
                    FROM Transacoes t 
                    JOIN Categorias c ON t.categoria_id = c.id
                    LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                    LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE t.veiculo_id IS NULL 
                      AND (c.parent_id = ? OR c.id = ?)
                      AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                    ORDER BY substr(t.data, 7, 4) DESC, substr(t.data, 4, 2) DESC, substr(t.data, 1, 2) DESC
                """
                cursor.execute(query, (parent_id, parent_id, perfil_nome, perfil_nome))
                return cursor.fetchall()
            else:
                query = """
                    SELECT t.id, COALESCE(t.data_real, t.data) as data, t.descricao, 
                           CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor_exibido, 
                           c.nome, t.tipo_transacao, 
                           t.parcela_atual, t.total_parcelas, t.metodo_pagamento, t.dono_cartao,
                           t.bandeira_cartao,
                           (SELECT COUNT(*) FROM Divisoes_Transacao WHERE transacao_id = t.id) as num_divisoes,
                           t.observacao,
                           t.valor_total
                    FROM Transacoes t 
                    JOIN Categorias c ON t.categoria_id = c.id
                    LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                    LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE t.veiculo_id = ? AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                    ORDER BY substr(t.data, 7, 4) DESC, substr(t.data, 4, 2) DESC, substr(t.data, 1, 2) DESC
                """
                cursor.execute(query, (veiculo_id, perfil_nome, perfil_nome))
                return cursor.fetchall()

    def get_transacoes_pet(self, pet_id, perfil_nome="Eu"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if pet_id == "geral":
                cursor.execute("SELECT id FROM Categorias WHERE UPPER(nome) = 'PET'")
                row_p = cursor.fetchone()
                parent_id = row_p[0] if row_p else None
                query = """
                    SELECT t.id, COALESCE(t.data_real, t.data) as data, t.descricao, 
                           CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor_exibido, 
                           c.nome, t.tipo_transacao, 
                           t.parcela_atual, t.total_parcelas, t.metodo_pagamento, t.dono_cartao,
                           t.bandeira_cartao,
                           (SELECT COUNT(*) FROM Divisoes_Transacao WHERE transacao_id = t.id) as num_divisoes,
                           t.observacao,
                           t.valor_total
                    FROM Transacoes t 
                    JOIN Categorias c ON t.categoria_id = c.id
                    LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                    LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE t.pet_id IS NULL 
                      AND (c.parent_id = ? OR c.id = ?)
                      AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                    ORDER BY substr(t.data, 7, 4) DESC, substr(t.data, 4, 2) DESC, substr(t.data, 1, 2) DESC
                """
                cursor.execute(query, (parent_id, parent_id, perfil_nome, perfil_nome))
                return cursor.fetchall()
            else:
                query = """
                    SELECT t.id, COALESCE(t.data_real, t.data) as data, t.descricao, 
                           CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor_exibido, 
                           c.nome, t.tipo_transacao, 
                           t.parcela_atual, t.total_parcelas, t.metodo_pagamento, t.dono_cartao,
                           t.bandeira_cartao,
                           (SELECT COUNT(*) FROM Divisoes_Transacao WHERE transacao_id = t.id) as num_divisoes,
                           t.observacao,
                           t.valor_total
                    FROM Transacoes t 
                    JOIN Categorias c ON t.categoria_id = c.id
                    LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                    LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE t.pet_id = ? AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                    ORDER BY substr(t.data, 7, 4) DESC, substr(t.data, 4, 2) DESC, substr(t.data, 1, 2) DESC
                """
                cursor.execute(query, (pet_id, perfil_nome, perfil_nome))
                return cursor.fetchall()

    def get_transacoes_saude(self, saude_id, perfil_nome="Eu"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if saude_id == "geral":
                cursor.execute("SELECT id FROM Categorias WHERE UPPER(nome) = 'SAÚDE'")
                row_p = cursor.fetchone()
                parent_id = row_p[0] if row_p else None
                query = """
                    SELECT t.id, COALESCE(t.data_real, t.data) as data, t.descricao, 
                           CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor_exibido, 
                           c.nome, t.tipo_transacao, 
                           t.parcela_atual, t.total_parcelas, t.metodo_pagamento, t.dono_cartao,
                           t.bandeira_cartao,
                           (SELECT COUNT(*) FROM Divisoes_Transacao WHERE transacao_id = t.id) as num_divisoes,
                           t.observacao,
                           t.valor_total
                    FROM Transacoes t 
                    JOIN Categorias c ON t.categoria_id = c.id
                    LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                    LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE t.saude_id IS NULL 
                      AND (c.parent_id = ? OR c.id = ?)
                      AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                    ORDER BY substr(t.data, 7, 4) DESC, substr(t.data, 4, 2) DESC, substr(t.data, 1, 2) DESC
                """
                cursor.execute(query, (parent_id, parent_id, perfil_nome, perfil_nome))
                return cursor.fetchall()
            else:
                query = """
                    SELECT t.id, COALESCE(t.data_real, t.data) as data, t.descricao, 
                           CASE WHEN d.id IS NULL THEN t.valor_total ELSE d.valor_cota END as valor_exibido, 
                           c.nome, t.tipo_transacao, 
                           t.parcela_atual, t.total_parcelas, t.metodo_pagamento, t.dono_cartao,
                           t.bandeira_cartao,
                           (SELECT COUNT(*) FROM Divisoes_Transacao WHERE transacao_id = t.id) as num_divisoes,
                           t.observacao,
                           t.valor_total
                    FROM Transacoes t 
                    JOIN Categorias c ON t.categoria_id = c.id
                    LEFT JOIN Divisoes_Transacao d ON t.id = d.transacao_id
                    LEFT JOIN Usuarios_Familia u ON d.usuario_id = u.id
                    WHERE t.saude_id = ? AND (u.nome = ? OR (d.id IS NULL AND ? = 'Eu'))
                    ORDER BY substr(t.data, 7, 4) DESC, substr(t.data, 4, 2) DESC, substr(t.data, 1, 2) DESC
                """
                cursor.execute(query, (saude_id, perfil_nome, perfil_nome))
                return cursor.fetchall()

    def get_subcategorias_por_pai(self, pai_nome):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM Categorias WHERE UPPER(nome) = UPPER(?) AND parent_id IS NULL", (pai_nome,))
                row = cursor.fetchone()
                if not row:
                    return []
                parent_id = row[0]
                cursor.execute("SELECT id, nome FROM Categorias WHERE parent_id = ? ORDER BY nome", (parent_id,))
                return cursor.fetchall()
        except Exception as e:
            logger.error("Erro ao buscar subcategorias por pai", exc_info=True)
            return []

    def migrar_transacoes_gerais_veiculo(self, veiculo_id, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM Categorias WHERE UPPER(nome) = 'VEÍCULO'")
                row_p = cursor.fetchone()
                if not row_p:
                    return False, "Categoria VEÍCULO não encontrada."
                parent_id = row_p[0]
                cursor.execute("SELECT id FROM Categorias WHERE parent_id = ? OR id = ?", (parent_id, parent_id))
                cats = [r[0] for r in cursor.fetchall()]
                if not cats:
                    return True, "Nenhuma categoria para migrar."
                placeholders = ",".join("?" for _ in cats)
                query = f"""
                    UPDATE Transacoes 
                    SET veiculo_id = ? 
                    WHERE veiculo_id IS NULL AND categoria_id IN ({placeholders})
                """
                cursor.execute(query, [veiculo_id] + cats)
                conn.commit()
                return True, "Transações migradas com sucesso."
        except Exception as e:
            logger.error("Erro ao migrar transações para veículo", exc_info=True)
            return False, str(e)

    def migrar_transacoes_gerais_pet(self, pet_id, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM Categorias WHERE UPPER(nome) = 'PET'")
                row_p = cursor.fetchone()
                if not row_p:
                    return False, "Categoria PET não encontrada."
                parent_id = row_p[0]
                cursor.execute("SELECT id FROM Categorias WHERE parent_id = ? OR id = ?", (parent_id, parent_id))
                cats = [r[0] for r in cursor.fetchall()]
                if not cats:
                    return True, "Nenhuma categoria para migrar."
                placeholders = ",".join("?" for _ in cats)
                query = f"""
                    UPDATE Transacoes 
                    SET pet_id = ? 
                    WHERE pet_id IS NULL AND categoria_id IN ({placeholders})
                """
                cursor.execute(query, [pet_id] + cats)
                conn.commit()
                return True, "Transações migradas com sucesso."
        except Exception as e:
            logger.error("Erro ao migrar transações para pet", exc_info=True)
            return False, str(e)

    def migrar_transacoes_gerais_saude(self, saude_id, perfil="Eu"):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM Categorias WHERE UPPER(nome) = 'SAÚDE'")
                row_p = cursor.fetchone()
                if not row_p:
                    return False, "Categoria SAÚDE não encontrada."
                parent_id = row_p[0]
                cursor.execute("SELECT id FROM Categorias WHERE parent_id = ? OR id = ?", (parent_id, parent_id))
                cats = [r[0] for r in cursor.fetchall()]
                if not cats:
                    return True, "Nenhuma categoria para migrar."
                placeholders = ",".join("?" for _ in cats)
                query = f"""
                    UPDATE Transacoes 
                    SET saude_id = ? 
                    WHERE saude_id IS NULL AND categoria_id IN ({placeholders})
                """
                cursor.execute(query, [saude_id] + cats)
                conn.commit()
                return True, "Transações migradas com sucesso."
        except Exception as e:
            logger.error("Erro ao migrar transações para saúde", exc_info=True)
            return False, str(e)

    def atualizar_transacao_veiculo(self, transacao_id, veiculo_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Transacoes SET veiculo_id = ? WHERE id = ?", (veiculo_id, transacao_id))
                conn.commit()
                return True, "Sucesso"
        except Exception as e:
            logger.error("Erro ao atualizar veículo da transação", exc_info=True)
            return False, str(e)

    def atualizar_transacao_pet(self, transacao_id, pet_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Transacoes SET pet_id = ? WHERE id = ?", (pet_id, transacao_id))
                conn.commit()
                return True, "Sucesso"
        except Exception as e:
            logger.error("Erro ao atualizar pet da transação", exc_info=True)
            return False, str(e)

    def atualizar_transacao_saude(self, transacao_id, saude_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE Transacoes SET saude_id = ? WHERE id = ?", (saude_id, transacao_id))
                conn.commit()
                return True, "Sucesso"
        except Exception as e:
            logger.error("Erro ao atualizar saúde da transação", exc_info=True)
            return False, str(e)

if __name__ == "__main__":
    db = Database()
    print("Banco de dados e tabelas criados com sucesso.")
