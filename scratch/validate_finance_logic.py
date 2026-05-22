import sqlite3
import os
import sys
import datetime

# Adiciona o diretório atual ao path para importar a Database
sys.path.append(os.getcwd())
from database import Database

def validate():
    print("--- Iniciando validacao de minucia extrema...")
    db_test = "test_financas_valid.db"
    if os.path.exists(db_test): os.remove(db_test)
    
    db = Database(db_test)
    
    try:
        # 1. Testar Criacao de Categorias e Subcategorias
        print("--- Testando Categorias ---")
        db.inserir_categoria("ALIMENTAÇÃO", "Despesa Variável")
        cats = db.get_categorias()
        # Verifica se criou o pai ALIMENTAÇÃO e o filho Alimentação
        pai = [c for c in cats if c[1] == "ALIMENTAÇÃO"][0]
        filho = [c for c in cats if c[1] == "Alimentação"][0]
        assert filho[3] == pai[0], "Erro na vinculacao de subcategoria automatica"
        print("[OK] Categorias e Subcategorias")

        # 2. Testar Insercao de Transacao Simples (Eu)
        print("--- Testando Transacao Simples ---")
        # Nota: inserir_transacao espera conta_id, categoria_id, descricao, data, valor, tipo...
        db.inserir_transacao(1, filho[0], "Almoco", "01/05/2026", 50.0, "Despesa Variável")
        resumo = db.get_resumo_financeiro("Maio", 2026, "Eu")
        assert resumo["Despesa Variável"] == 50.0, f"Erro no resumo simples: {resumo['Despesa Variável']}"
        print("[OK] Transacao Simples")

        # 3. Testar Transacao Compartilhada (Divisao)
        print("--- Testando Transacao Compartilhada ---")
        # Divisao: Eu (R$ 40), Mae (R$ 60) -> Total R$ 100
        div = {"Eu": 40.0, "Mãe": 60.0}
        db.inserir_transacao(1, filho[0], "Mercado Familiar", "02/05/2026", 100.0, "Despesa Variável", divisoes=div)
        
        resumo_eu = db.get_resumo_financeiro("Maio", 2026, "Eu")
        # Esperado para Eu: 50 (anterior) + 40 (cota da divisao) = 90
        assert resumo_eu["Despesa Variável"] == 90.0, f"Erro na cota 'Eu': {resumo_eu['Despesa Variável']}"
        # Esperado para Outros: 60 (cota da Mae)
        assert resumo_eu["Outros"] == 60.0, f"Erro na cota 'Outros': {resumo_eu['Outros']}"
        
        # Testar resumo para o subperfil "Mae"
        resumo_mae = db.get_resumo_financeiro("Maio", 2026, "Mãe")
        assert resumo_mae["Despesa Variável"] == 60.0, f"Erro na cota 'Mae': {resumo_mae['Despesa Variável']}"
        print("[OK] Transacao Compartilhada e Divisao")

        # 4. Testar Investimentos
        print("--- Testando Investimentos ---")
        # Criar categoria de investimento
        db.inserir_categoria("BOLSA", "Investimento")
        cats = db.get_categorias()
        cat_bolsa = [c for c in cats if c[1] == "Bolsa"][0]
        db.inserir_transacao(1, cat_bolsa[0], "Compra ITUB4", "03/05/2026", 500.0, "Investimento")
        
        resumo = db.get_resumo_financeiro("Maio", 2026, "Eu")
        assert resumo["Investimento"] == 500.0, "Erro no registro de Investimento"
        print("[OK] Investimentos")

        # 5. Testar Parcelamento
        print("--- Testando Parcelamento ---")
        # Compra de R$ 300 em 3x (Maio, Junho, Julho)
        db.inserir_transacao(1, filho[0], "Celular", "05/05/2026", 300.0, "Despesa Variável", parcelas=3)
        
        # Verificar Maio (Parcela 1/3 = 100)
        res_maio = db.get_resumo_financeiro("Maio", 2026, "Eu")
        # Anterior (90) + Celular (100) = 190
        assert res_maio["Despesa Variável"] == 190.0, f"Erro na parcela de Maio: {res_maio['Despesa Variável']}"
        
        # 6. Testar Parcelamento + Compartilhamento (O CASO CRITICO)
        print("--- Testando Parcelamento + Compartilhamento ---")
        # Compra de R$ 600 em 3x. Divisao total: Eu (R$ 300), Mae (R$ 300)
        # Esperado por mes: Parcela R$ 200. Eu (R$ 100), Mae (R$ 100)
        div_total = {"Eu": 300.0, "Mãe": 300.0}
        db.inserir_transacao(1, filho[0], "Smart TV", "10/05/2026", 600.0, "Despesa Variável", parcelas=3, divisoes=div_total)
        
        # Verificar Maio
        res_maio = db.get_resumo_financeiro("Maio", 2026, "Eu")
        # Anterior (190) + TV (100) = 290
        print(f"DEBUG: Cota Eu em Maio: {res_maio['Despesa Variável']}")
        assert res_maio["Despesa Variável"] == 290.0, f"Erro: Cota parcelada incorreta. Esperado 290, obteve {res_maio['Despesa Variável']}"
        
        # 7. Testar Atualização (Edição) de Transação
        print("--- Testando Edição de Transação ---")
        transacoes_maio = db.get_transacoes("Maio", 2026, "Eu")
        t_almoco = [t for t in transacoes_maio if t[2] == "Almoco"][0]
        id_almoco = t_almoco[0]
        
        # Buscar pelo ID para garantir que funciona
        dados_almoco = db.get_transacao_by_id(id_almoco)
        assert dados_almoco["valor_total"] == 50.0, "Erro ao buscar transação por ID"
        
        # Atualizar para 70.0
        db.atualizar_transacao(
            transacao_id=id_almoco,
            categoria_id=dados_almoco["categoria_id"],
            descricao="Almoco Editado",
            data=dados_almoco["data"],
            valor_total=70.0,
            tipo_transacao=dados_almoco["tipo_transacao"],
            metodo=dados_almoco["metodo_pagamento"],
            bandeira=dados_almoco["bandeira_cartao"],
            dono=dados_almoco["dono_cartao"],
            observacao="Fiquei com mais fome",
            divisoes={"Eu": 70.0}
        )
        
        # O resumo total anterior era 290. Como aumentou 20, deve ir para 310.
        res_maio_edit = db.get_resumo_financeiro("Maio", 2026, "Eu")
        assert res_maio_edit["Despesa Variável"] == 310.0, f"Erro na edição. Esperado 310.0, obteve {res_maio_edit['Despesa Variável']}"
        print("[OK] Edição de Transação")

        # 8. Testar Deleção de Transação
        print("--- Testando Exclusão de Transação ---")
        db.deletar_transacao(id_almoco)
        
        # Excluindo os 70, deve cair para 240 (310 - 70).
        res_maio_del = db.get_resumo_financeiro("Maio", 2026, "Eu")
        assert res_maio_del["Despesa Variável"] == 240.0, f"Erro na exclusão. Esperado 240.0, obteve {res_maio_del['Despesa Variável']}"
        
        assert db.get_transacao_by_id(id_almoco) is None, "A transação não foi excluída do banco!"
        print("[OK] Exclusão de Transação")

        print("\nVALIDACAO CONCLUIDA: Todos os sistemas estao integros e confiaveis!")
        
    except Exception as e:
        print(f"\nFALHA NA VALIDACAO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(db_test):
            try: os.remove(db_test)
            except: pass

if __name__ == "__main__":
    validate()
