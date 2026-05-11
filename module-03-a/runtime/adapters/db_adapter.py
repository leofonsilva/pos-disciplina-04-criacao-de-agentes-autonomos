"""
Database Adapter — conecta skills a bancos de dados via query parametrizada.

O adapter le do contrato:
  - tipo_banco, query_template, modo (read_only), timeout_segundos

O adapter le do ambiente (.env):
  - DB_CONNECTION_STRING (connection string do banco)

Seguranca:
  - Queries SEMPRE parametrizadas (NUNCA string format / concatenacao)
  - Modo read_only: rejeita queries com INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE
  - LIMIT obrigatorio: vem do contrato (limites.max_resultados)
  - Connection string NUNCA no .md, so no .env
  - Logging: registra query executada SEM dados sensiveis
"""

import json  # Para manipular JSON
import os  # Para acessar variáveis de ambiente (DB_CONNECTION_STRING)
import re  # Para expressões regulares (buscar parâmetros e operações SQL)
import time  # Para medir latência da query
from pathlib import Path  # Para manipular caminhos de arquivos

from dotenv import load_dotenv  # Para carregar variáveis do arquivo .env

# Carrega o arquivo .env da raiz do projeto (sobrescreve configurações anteriores)
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

# Constante de tokens zero (database adapter não consome tokens)
_TOKENS_ZERO = {"prompt": 0, "completion": 0, "total": 0}

# Palavras-chave proibidas em modo read_only (operações que modificam dados)
_OPERACOES_ESCRITA = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"}


def _validar_read_only(query: str) -> list:
    """Valida se a query e somente leitura. Retorna lista de violacoes."""
    violacoes = []
    query_upper = query.upper().strip()
    for op in _OPERACOES_ESCRITA:
        if re.search(rf'\b{op}\b', query_upper):  # \b = borda da palavra
            violacoes.append(f"operacao '{op}' proibida em modo read_only")
    return violacoes


def _substituir_parametros(query_template: str, argumentos: dict) -> tuple:
    """
    Substitui parametros nomeados (:nome) por placeholders seguros.

    Retorna (query_com_placeholders, lista_de_valores) para execucao parametrizada.
    NAO usa string format — usa placeholders numerados para evitar SQL injection.
    
    Exemplo: "SELECT * FROM logs WHERE servico = :servico" vira
             "SELECT * FROM logs WHERE servico = $1" com valores = ["checkout"]
    """
    # Encontra todos os parâmetros com formato :nome
    params_encontrados = re.findall(r':(\w+)', query_template)
    valores = []
    query_segura = query_template

    # Substitui cada :param por $1, $2, etc.
    for i, param in enumerate(params_encontrados, 1):
        valor = argumentos.get(param)
        if valor is None:
            valor = str(argumentos.get(param, ""))
        valores.append(valor)
        query_segura = query_segura.replace(f":{param}", f"${i}", 1)  # Substitui apenas a primeira ocorrência

    return query_segura, valores


def criar_funcao_database(habilidade: dict):
    """
    Cria funcao que executa query parametrizada em banco de dados.

    Lê query_template, modo e timeout do bloco 'conexao'.
    Retorna resultado no formato padrao do harness.
    """
    nome = habilidade.get("nome", "")
    conexao = habilidade.get("conexao", {})
    campos_saida = habilidade.get("saida", {})
    limites = habilidade.get("limites", {})

    query_template = conexao.get("query_template", "")
    tipo_banco = conexao.get("tipo_banco", "postgresql")
    modo = conexao.get("modo", "read_only")
    timeout = conexao.get("timeout_segundos", 5)
    max_resultados = limites.get("max_resultados", 100)

    def funcao(argumentos):
        """Função que será chamada pelo executor quando a IA usar esta ferramenta."""
        
        # 1. Valida modo read_only (rejeita operações de escrita)
        if modo == "read_only":
            violacoes = _validar_read_only(query_template)
            if violacoes:
                return {
                    "sucesso": False,
                    "erro": f"violacao de read_only: {'; '.join(violacoes)}",
                    "_adapter": "database",
                    "_tokens": _TOKENS_ZERO.copy(),
                }

        # 2. Prepara query parametrizada (NUNCA string format - previne SQL injection)
        query_segura, valores = _substituir_parametros(query_template, argumentos or {})

        # 3. Verifica se a connection string do banco está configurada
        conn_string = os.environ.get("DB_CONNECTION_STRING", "")

        if not conn_string:
            # Sem banco configurado: simula execucao com dados didaticos
            # Em producao, isso seria um erro. Aqui e para o aluno ver o fluxo.
            inicio = time.time()
            dados_simulados = _simular_query(nome, argumentos, campos_saida, max_resultados)
            latencia_ms = round((time.time() - inicio) * 1000, 1)

            return {
                "sucesso": True,
                "dados": dados_simulados,
                "_adapter": "database",
                "_modo": modo,
                "_query_segura": query_segura,
                "_parametros_count": len(valores),
                "_simulado": True,  # Indica que são dados simulados, não reais
                "_latencia_ms": latencia_ms,
                "_tokens": _TOKENS_ZERO.copy(),
            }

        # 4. Executa query real (com driver do banco)
        try:
            inicio = time.time()
            resultados = _executar_query_real(
                conn_string, tipo_banco, query_segura, valores, timeout, max_resultados
            )
            latencia_ms = round((time.time() - inicio) * 1000, 1)

            # Converte resultados para o formato de saida esperado pelo contrato
            dados = _parsear_resultados(resultados, campos_saida)
            dados["_entrada"] = argumentos

            return {
                "sucesso": True,
                "dados": dados,
                "_adapter": "database",
                "_modo": modo,
                "_query_segura": query_segura,
                "_simulado": False,
                "_latencia_ms": latencia_ms,
                "_tokens": _TOKENS_ZERO.copy(),
            }
        except Exception as e:
            return {
                "sucesso": False,
                "erro": f"erro no banco: {e}",
                "_adapter": "database",
                "_tokens": _TOKENS_ZERO.copy(),
            }

    return funcao


def _simular_query(nome: str, argumentos: dict, campos_saida: dict, max_resultados: int) -> dict:
    """
    Simula resultado de query quando nao ha banco configurado.

    Retorna dados didaticos realistas para o aluno ver o fluxo completo.
    """
    # Tenta extrair o nome do serviço dos argumentos
    servico = "desconhecido"
    for v in (argumentos or {}).values():
        if isinstance(v, str) and len(v) > 2:
            servico = v
            break

    # Se o campo de saída sugere logs/eventos, retorna estrutura adequada
    if "eventos" in campos_saida or "logs" in campos_saida:
        return {
            "eventos": [
                {"timestamp": "2024-01-15T10:32:00Z", "nivel": "ERROR", "mensagem": f"connection timeout em {servico}", "servico": servico},
                {"timestamp": "2024-01-15T10:28:00Z", "nivel": "WARN", "mensagem": f"pool de conexoes esgotado em {servico}", "servico": servico},
                {"timestamp": "2024-01-15T10:25:00Z", "nivel": "ERROR", "mensagem": f"query lenta detectada em {servico}: 4500ms", "servico": servico},
            ][:max_resultados],
            "contagem_total": min(3, max_resultados),
            "_entrada": argumentos,
        }

    # Fallback genérico para outros tipos de resposta
    dados = {}
    for campo, tipo in campos_saida.items():
        if tipo == "list":
            dados[campo] = [{"item": f"resultado_db_{i}"} for i in range(1, min(4, max_resultados + 1))]
        elif tipo == "int":
            dados[campo] = min(3, max_resultados)
        else:
            dados[campo] = f"{campo}_do_banco"
    dados["_entrada"] = argumentos
    return dados


def _executar_query_real(conn_string: str, tipo_banco: str, query: str, valores: list, timeout: int, max_resultados: int) -> list:
    """
    Executa query real no banco de dados.

    Suporta PostgreSQL (psycopg2) e SQLite (sqlite3).
    Outros bancos podem ser adicionados.
    """
    if tipo_banco == "sqlite":
        import sqlite3
        # Resolve o caminho relativo a partir da raiz do projeto
        db_path = Path(conn_string)
        if not db_path.is_absolute():
            db_path = Path(__file__).resolve().parent.parent.parent / conn_string
        
        # Converte placeholders $N para ? (formato SQLite)
        query_sqlite = re.sub(r'\$\d+', '?', query)
        
        # Conecta e executa
        conn = sqlite3.connect(str(db_path))
        conn.execute(f"PRAGMA busy_timeout = {timeout * 1000}")  # Timeout em milissegundos
        cursor = conn.execute(query_sqlite, valores)
        
        # Extrai nomes das colunas e monta lista de dicionários
        colunas = [desc[0] for desc in cursor.description] if cursor.description else []
        resultados = [dict(zip(colunas, row)) for row in cursor.fetchmany(max_resultados)]
        conn.close()
        return resultados

    if tipo_banco == "postgresql":
        try:
            import psycopg2
            conn = psycopg2.connect(conn_string, connect_timeout=timeout)
            cursor = conn.cursor()
            cursor.execute(query, valores)  # Query parametrizada (segura!)
            colunas = [desc[0] for desc in cursor.description] if cursor.description else []
            resultados = [dict(zip(colunas, row)) for row in cursor.fetchmany(max_resultados)]
            cursor.close()
            conn.close()
            return resultados
        except ImportError:
            raise RuntimeError("psycopg2 nao instalado. Instale com: pip install psycopg2-binary")

    raise RuntimeError(f"tipo_banco '{tipo_banco}' nao suportado. Use 'postgresql' ou 'sqlite'.")


def _parsear_resultados(resultados: list, campos_saida: dict) -> dict:
    """Converte lista de rows do banco pro formato de saida do contrato."""
    dados = {}
    for campo, tipo in campos_saida.items():
        if tipo == "list":
            dados[campo] = resultados  # Retorna a lista completa de resultados
        elif tipo == "int":
            dados[campo] = len(resultados)  # Retorna a contagem
        else:
            # Para outros tipos, pega o primeiro resultado (se existir)
            dados[campo] = str(resultados[0].get(campo, "")) if resultados else ""
    return dados
