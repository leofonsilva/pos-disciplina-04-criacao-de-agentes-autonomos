"""
Carregador de Contratos e Estado.

Le contratos (.md com YAML) e cria o estado inicial do agente.
"""

import re  # Para usar expressões regulares (buscar blocos YAML em markdown)
from pathlib import Path  # Para manipular caminhos de arquivos

import yaml  # Para converter YAML em dicionários Python


def carregar_yaml_do_md(caminho_arquivo: Path) -> dict:
    """
    Extrai o primeiro bloco YAML de um arquivo .md.

    Procura por um bloco de código com a linguagem yaml e converte para dicionário.
    """
    # Verifica se o arquivo existe, se não existir retorna dicionário vazio
    if not caminho_arquivo.exists():
        return {}
    
    # Lê o conteúdo do arquivo como texto
    texto = caminho_arquivo.read_text(encoding="utf-8")
    
    # Expressão regular para encontrar blocos: ```yaml ... ```
    correspondencia = re.search(r"```yaml\n(.*?)```", texto, re.DOTALL)
    if not correspondencia:
        return {}
    
    # Converte o YAML encontrado em dicionário Python
    return yaml.safe_load(correspondencia.group(1)) or {}


def carregar_contratos(caminho_agente: Path, arquitetura: str = None) -> dict:
    """
    Carrega todos os contratos de um agente.

    Se arquitetura for informada, sobrescreve planner.md e executor.md
    com os da pasta architectures/<arquitetura>/.
    """
    pasta_contratos = caminho_agente / "contracts"

    # Carrega cada arquivo de contrato e armazena em um dicionário
    contratos = {
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

    # Se uma arquitetura foi especificada, tenta carregar os contratos específicos
    if arquitetura:
        raiz = Path(caminho_agente).resolve().parent
        pasta_arq = raiz / "architectures" / arquitetura
        
        # Verifica se a pasta da arquitetura existe
        if not pasta_arq.exists():
            print(f"  [aviso] pasta de arquitetura nao encontrada: {pasta_arq}")
        else:
            # Carrega planner da arquitetura específica
            planner_arq = carregar_yaml_do_md(pasta_arq / "planner.md")
            if planner_arq:
                contratos["planejador"] = planner_arq
                print(f"  [arquitetura] planner.md carregado de {arquitetura}/")
            
            # Carrega executor da arquitetura específica
            executor_arq = carregar_yaml_do_md(pasta_arq / "executor.md")
            if executor_arq:
                contratos["executor"] = executor_arq
                print(f"  [arquitetura] executor.md carregado de {arquitetura}/")
            
            # Carrega critic (para reflexão) se existir
            critic_arq = carregar_yaml_do_md(pasta_arq / "critic.md")
            if critic_arq:
                contratos["critico"] = critic_arq
                print(f"  [arquitetura] critic.md carregado de {arquitetura}/")

    return contratos


def criar_estado(contratos: dict, texto_entrada: str, modo: str = None, evento: str = None, arquitetura: str = None) -> dict:
    """
    Cria o estado inicial do agente a partir dos contratos.

    Parâmetros:
    - contratos: dicionário com todos os contratos carregados
    - texto_entrada: comando/entrada do usuário
    - modo: tipo de agente (task_based, interactive, goal_oriented, autonomous)
    - evento: nome do evento (para goal_oriented)
    - arquitetura: react, plan_execute, reflect

    Retorna: dicionário com o estado inicial
    """
    regras = contratos.get("regras", {})
    ciclo = contratos.get("ciclo", {})
    agente = contratos.get("agente", {})
    config_chamadas = regras.get("limites", {}).get("chamadas_ferramenta", {})

    # Configuração de limites de chamadas de ferramenta
    if isinstance(config_chamadas, dict):
        # Se for dicionário, separa o total dos limites por ferramenta
        max_chamadas_ferramenta = config_chamadas.get("total", 10)
        limites_por_ferramenta = {
            nome_ferramenta: limite
            for nome_ferramenta, limite in config_chamadas.items()
            if nome_ferramenta != "total"
        }
    else:
        # Se for um número direto, usa ele como total e sem limites individuais
        max_chamadas_ferramenta = config_chamadas
        limites_por_ferramenta = {}

    # Define o tipo do agente: o parâmetro CLI tem prioridade sobre o contrato
    tipo_agente = modo or agente.get("tipo", "task_based")

    # Retorna o estado inicial com todos os campos necessários para o loop
    return {
        "objetivo": ciclo.get("objetivo", "desconhecido"),  # Objetivo principal do agente
        "entrada": texto_entrada,  # Comando original do usuário
        "tipo_agente": tipo_agente,  # Modo de operação
        "arquitetura": arquitetura or "padrao",  # Arquitetura usada
        "evento": evento,  # Nome do evento (opcional)
        "etapa": 0,  # Número da etapa atual (começa em 0)
        "chamadas_ferramenta": 0,  # Contador total de chamadas de ferramentas
        "chamadas_por_ferramenta": {},  # Contador por ferramenta individual
        "max_etapas": regras.get("limites", {}).get("max_etapas", 10),  # Limite de etapas
        "max_chamadas_ferramenta": max_chamadas_ferramenta,  # Limite total de chamadas
        "limites_por_ferramenta": limites_por_ferramenta,  # Limites por ferramenta
        "sem_progresso": regras.get("limites", {}).get("sem_progresso", 3),  # Limite de repetições
        "limite_tempo_segundos": regras.get("limites", {}).get("limite_tempo_segundos", 120),  # Tempo máximo
        "max_tokens": regras.get("limites", {}).get("max_tokens", 50000),  # Limite de tokens
        "tokens_consumidos": {"prompt": 0, "completion": 0, "total": 0},  # Acumulador de tokens
        "acoes_sensiveis": regras.get("acoes_sensiveis", []),  # Ações que exigem confirmação
        "historico": [],  # Registro de todas as etapas executadas
        "concluido": False,  # Flag indicando se o objetivo foi alcançado
        "resultado": "",  # Mensagem final de resultado ou erro
        "etapas_sem_progresso": 0,  # Contador de etapas sem avanço
        "ultima_ferramenta": None,  # Última ferramenta chamada (para detectar repetição)
    }
