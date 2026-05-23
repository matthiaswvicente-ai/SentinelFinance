import sqlite3
import os
import datetime
import shutil
import glob
from logger import logger

class Database:
    def __init__(self, db_name="financas.db"):
        self.db_name = db_name
        if db_name == "financas.db" and os.path.exists(db_name):
            self._auto_backup()
        self.create_tables()

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
        return sqlite3.connect(self.db_name)

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
                    nome TEXT NOT NULL
                )
            ''')
            
            # Tabela de Transações (Atualizada para suportar Parcelamento e Recorrência)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Transacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conta_id INTEGER,
                    categoria_id INTEGER,
                    descricao TEXT NOT NULL,
                    data TEXT NOT NULL,
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
            
            conn.commit()
            
        # Garante a inserção inicial das categorias da planilha
        self.seed_categorias_iniciais()

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
        has_sub = 1 if parent_id is None else 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if tipo is not None:
                    cursor.execute("UPDATE Categorias SET nome = ?, tipo = ?, parent_id = ?, has_subcategories = ? WHERE id = ?", 
                                   (novo_nome, tipo, parent_id, has_sub, cat_id))
                else:
                    cursor.execute("UPDATE Categorias SET nome = ? WHERE id = ?", (novo_nome, cat_id))
                conn.commit()
                return True, "Categoria atualizada."
        except Exception as e:
            logger.error('Erro no BD', exc_info=True)
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
                          metodo="Dinheiro", parcelas=1, bandeira="", dono="", recorrencia=None, divisoes=None, observacao=""):
        """
        Insere uma ou mais transações (em caso de parcelamento).
        divisoes: Lista de dicionários, um para cada parcela, contendo {nome_usuario: valor_cota}
                  Ou um único dicionário se for igual para todas as parcelas.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
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
                    INSERT INTO Transacoes (conta_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                                            metodo_pagamento, parcela_atual, total_parcelas, bandeira_cartao, 
                                            dono_cartao, recorrencia, grupo_id, observacao)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (conta_id, categoria_id, descricao, data_str, val_parcela, tipo_transacao, 
                      metodo, i+1, parcelas, bandeira, dono, recorrencia, grupo_id, observacao))
                
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
            return True, "Transação(ões) salva(s) com sucesso."
            
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
                       t.metodo_pagamento, t.total_parcelas, t.bandeira_cartao, t.dono_cartao, t.observacao, c.nome, c.parent_id
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
                "observacao": t_row[10], "categoria_nome": t_row[11], "parent_id": t_row[12], "divisoes": divs
            }

    def atualizar_transacao(self, transacao_id, categoria_id, descricao, data, valor_total, tipo_transacao, 
                            metodo, bandeira, dono, observacao, divisoes):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE Transacoes 
                    SET categoria_id=?, descricao=?, data=?, valor_total=?, tipo_transacao=?, 
                        metodo_pagamento=?, bandeira_cartao=?, dono_cartao=?, observacao=?
                    WHERE id=?
                ''', (categoria_id, descricao, data, valor_total, tipo_transacao, metodo, bandeira, dono, observacao, transacao_id))
                
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
                SELECT t.id, t.data, t.descricao, 
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

if __name__ == "__main__":
    db = Database()
    print("Banco de dados e tabelas criados com sucesso.")
