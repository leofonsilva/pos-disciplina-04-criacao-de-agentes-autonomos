"""
Carregador de Contratos e Estado.

Le contratos (.md com YAML) e cria o estado inicial do agente.
Os contratos definem como o agente deve se comportar, quais ferramentas tem,
regras, limites, etc.
"""

import re  # Módulo para expressões regulares (encontrar padrões no texto)
from pathlib import Path  # Trabalha com caminhos de arquivos

import yaml  # Biblioteca para ler/parsear arquivos YAML


def carregar_yaml_do_md(caminho_arquivo: Path) -> dict:
    """
    Extrai o primeiro bloco YAML de um arquivo .md.

    Arquivos .md (Markdown) podem conter blocos de código YAML delimitados por
    ```yaml ... ```. Esta função encontra o primeiro e o converte em dicionário.

    Parâmetros:
        caminho_arquivo (Path): Caminho do arquivo .md a ser lido

    Retorna:
        dict: Dicionário com os dados do YAML, ou dicionário vazio se não encontrar
    """
    # Verifica se o arquivo existe, se não existir retorna dicionário vazio
    if not caminho_arquivo.exists():
        return {}

    # Lê todo o conteúdo do arquivo como string
    texto = caminho_arquivo.read_text(encoding="utf-8")

    # Busca o primeiro bloco ```yaml ... ``` no texto
    # re.DOTALL permite que o ponto (.) também capture quebras de linha
    # O padrão captura tudo entre ```yaml e ``` (no grupo 1)
    correspondencia = re.search(r"```yaml\n(.*?)```", texto, re.DOTALL)

    # Se não encontrou bloco YAML, retorna dicionário vazio
    if not correspondencia:
        return {}

    # Converte o YAML encontrado (string) em dicionário Python e retorna
    return yaml.safe_load(correspondencia.group(1)) or {}


def carregar_contratos(caminho_agente: Path) -> dict:
    """
    Carrega todos os contratos de um agente.

    Os contratos são arquivos .md que definem diferentes aspectos do agente:
    - agent.md: configurações gerais do agente (nome, tipo, etc.)
    - loop.md: configurações do ciclo do agente (objetivo, etc.)
    - planner.md: configurações do planejador (como LLM deve planejar)
    - toolbox.md: registro de todas as ferramentas disponíveis
    - executor.md: configurações de execução das ferramentas
    - rules.md: regras e limites (máximo de etapas, tokens, tempo, etc.)
    - hooks.md: ganchos para executar ações em momentos específicos
    - skills.md: habilidades/ferramentas específicas que o agente tem
    - memory.md: configurações de memória e resumo

    Parâmetros:
        caminho_agente (Path): Caminho da pasta do agente

    Retorna:
        dict: Dicionário com todos os contratos carregados
    """
    # Constrói o caminho para a pasta contracts dentro do agente
    pasta_contratos = caminho_agente / "contracts"

    # Retorna um dicionário onde cada chave é o tipo de contrato e o valor são os dados carregados
    return {
        "agente": carregar_yaml_do_md(caminho_agente / "agent.md"),
        "ciclo": carregar_yaml_do_md(pasta_contratos / "loop.md"),
        "planejador": carregar_yaml_do_md(pasta_contratos / "planner.md"),
        "caixa_ferramentas": carregar_yaml_do_md(pasta_contratos / "toolbox.md"),
        "executor": carregar_yaml_do_md(pasta_contratos / "executor.md"),
        "regras": carregar_yaml_do_md(caminho_agente / "rules.md"),
        "ganchos": carregar_yaml_do_md(caminho_agente / "hooks.md"),
        "habilidades": carregar_yaml_do_md(caminho_agente / "skills.md"),
        "memoria": carregar_yaml_do_md(caminho_agente / "memory.md"),
    }


def criar_estado(
    contratos: dict, texto_entrada: str, modo: str = None, evento: str = None
) -> dict:
    """
    Cria o estado inicial do agente a partir dos contratos.

    O estado é um dicionário que mantém todas as informações da execução atual:
    quantas etapas já foram executadas, quantas chamadas de ferramenta foram feitas,
    histórico, tokens consumidos, etc.

    Parâmetros:
        contratos (dict): Dicionário com todos os contratos carregados
        texto_entrada (str): Entrada/informação do usuário para o agente processar
        modo (str, opcional): Modo de operação (sobrescreve o contrato)
        evento (str, opcional): Evento trigger para modo autonomous

    Retorna:
        dict: Estado inicial do agente
    """
    # Extrai as diferentes seções dos contratos
    regras = contratos.get("regras", {})  # Regras e limites
    ciclo = contratos.get("ciclo", {})  # Configurações do ciclo
    agente = contratos.get("agente", {})  # Configurações gerais do agente

    # Configuração de limites de chamada de ferramentas
    # Pode ser um número (total) ou um dicionário com limites por ferramenta
    config_chamadas = regras.get("limites", {}).get("chamadas_ferramenta", {})

    if isinstance(config_chamadas, dict):
        # Se é um dicionário, o campo "total" é o limite global
        max_chamadas_ferramenta = config_chamadas.get("total", 10)
        # As outras chaves são limites específicos de cada ferramenta
        limites_por_ferramenta = {
            nome_ferramenta: limite
            for nome_ferramenta, limite in config_chamadas.items()
            if nome_ferramenta != "total"
        }
    else:
        # Se não é dicionário, assume que é o número total de chamadas
        max_chamadas_ferramenta = config_chamadas
        limites_por_ferramenta = {}

    # Determina o tipo do agente:
    # - Prioriza o modo passado por parâmetro (CLI)
    # - Se não foi passado, usa o que está no contrato do agente
    # - Se nenhum, usa "task_based" como padrão
    tipo_agente = modo or agente.get("tipo", "task_based")

    # Retorna o estado inicial completo
    return {
        # Informações básicas
        "objetivo": ciclo.get("objetivo", "desconhecido"),  # O que o agente deve fazer
        "entrada": texto_entrada,  # Input do usuário
        "tipo_agente": tipo_agente,  # task_based, interactive, goal_oriented, autonomous
        "evento": evento,  # Evento que disparou a execução (modo autonomous)
        # Contadores
        "etapa": 0,  # Etapa atual (começa em 0)
        "chamadas_ferramenta": 0,  # Total de chamadas a ferramentas
        "chamadas_por_ferramenta": {},  # Mapa: nome_ferramenta -> quantidade de chamadas
        # Limites
        "max_etapas": regras.get("limites", {}).get(
            "max_etapas", 10
        ),  # Máximo de etapas
        "max_chamadas_ferramenta": max_chamadas_ferramenta,  # Máximo total de chamadas
        "limites_por_ferramenta": limites_por_ferramenta,  # Limite por ferramenta
        "sem_progresso": regras.get("limites", {}).get(
            "sem_progresso", 3
        ),  # Detecção de estagnação
        "limite_tempo_segundos": regras.get("limites", {}).get(
            "limite_tempo_segundos", 120
        ),  # Tempo máximo
        "max_tokens": regras.get("limites", {}).get(
            "max_tokens", 50000
        ),  # Máximo de tokens
        # Tokens consumidos (começam em zero)
        "tokens_consumidos": {"prompt": 0, "completion": 0, "total": 0},
        # Controle de execução
        "acoes_sensiveis": regras.get(
            "acoes_sensiveis", []
        ),  # Ações que precisam confirmação humana
        "historico": [],  # Lista de todas as etapas executadas
        "concluido": False,  # Flag indicando se o agente terminou
        "resultado": "",  # Resultado final da execução
        # Controle de estagnação
        "etapas_sem_progresso": 0,  # Contador de etapas repetindo mesma ferramenta
        "ultima_ferramenta": None,  # Nome da última ferramenta chamada
    }
