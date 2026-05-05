"""
Planejador - Perceber e Planejar.

Monta o contexto (percepcao) e decide o proximo passo via LLM ou mock.
Suporta modos: task_based, interactive, goal_oriented, autonomous.
Retorna uso de tokens junto com o plano para controle de consumo.
"""

import json  # Para trabalhar com JSON (entrada/saída das ferramentas)
import os  # Para acessar variáveis de ambiente (ex: OPENAI_API_KEY)
from pathlib import Path  # Para trabalhar com caminhos de arquivos

# Tenta importar dotenv para carregar variáveis do arquivo .env
try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(*a, **kw):
        pass


# Importa funções auxiliares de ferramentas
from ferramentas import extrair_evidencias_do_historico, montar_argumentos_mock

# Carrega variáveis do arquivo .env na pasta atual
load_dotenv(Path(__file__).parent / ".env")

# Constante representando zero tokens (para quando não usa LLM ou falha)
_TOKENS_ZERO = {"prompt": 0, "completion": 0, "total": 0}


def perceber(estado: dict) -> str:
    """
    Monta o contexto atual para o planejador.

    Esta função transforma o estado atual do agente em um texto legível
    que será enviado para a LLM decidir o próximo passo.

    Parâmetros:
        estado (dict): Estado atual do agente (histórico, contadores, etc.)

    Retorna:
        str: Texto com o contexto completo para o planejador
    """
    # Lista para acumular as partes do contexto
    partes = []

    # Adiciona o alerta/entrada inicial
    partes.append(f"Alerta: {estado['entrada']}")

    # Adiciona o modo de operação
    tipo_agente = estado.get("tipo_agente", "task_based")
    partes.append(f"Modo: {tipo_agente}")

    # Adiciona o evento trigger (se houver)
    if estado.get("evento"):
        partes.append(f"Evento trigger: {estado['evento']}")

    # Adiciona o histórico de etapas já executadas
    for registro in estado["historico"]:
        etapa = registro["etapa"]
        plano = registro.get("plano", {})
        ferramenta_usada = plano.get("nome_ferramenta", "nenhuma")
        if registro.get("resultado_acao"):
            partes.append(
                f"Etapa {etapa} [{ferramenta_usada}]: {json.dumps(registro['resultado_acao'], ensure_ascii=False)}"
            )

    # Adiciona lista de ferramentas já utilizadas
    ferramentas_usadas = list(estado["chamadas_por_ferramenta"].keys())
    if ferramentas_usadas:
        partes.append(f"Ferramentas ja utilizadas: {', '.join(ferramentas_usadas)}")

    # Adiciona status de progresso
    partes.append(f"Etapas realizadas: {estado['etapa']}/{estado['max_etapas']}")
    partes.append(
        f"Chamadas de ferramenta: {estado['chamadas_ferramenta']}/{estado['max_chamadas_ferramenta']}"
    )

    # Adiciona alerta de estagnação (se houver)
    if estado.get("etapas_sem_progresso", 0) > 0:
        partes.append(
            f"ATENCAO: {estado['etapas_sem_progresso']} etapas sem progresso detectadas"
        )

    # Junta todas as partes com quebra de linha
    return "\n".join(partes)


def construir_prompt_sistema(contratos: dict) -> str:
    """
    Constroi o system prompt a partir dos contratos - sem conhecer o dominio.

    O prompt do sistema define as regras que a LLM deve seguir para planejar
    as ações do agente.

    Parâmetros:
        contratos (dict): Contratos do agente (agente, ciclo, habilidades, etc.)

    Retorna:
        str: Prompt de sistema completo para a LLM
    """
    # Extrai informações do agente
    agente = contratos.get("agente", {})
    nome_agente = agente.get("nome", "agente")
    descricao_agente = agente.get("descricao", "")
    tipo_agente = agente.get("tipo", "task_based")

    # Extrai objetivo e etapas do ciclo
    objetivo = contratos.get("ciclo", {}).get("objetivo", "desconhecido")
    etapas = contratos.get("ciclo", {}).get("etapas", [])

    # --- Constrói descrição das ferramentas disponíveis ---
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])
    bloco_ferramentas = ""
    for habilidade in habilidades:
        nome = habilidade.get("nome", "")
        descricao = habilidade.get("descricao", "")
        entradas = habilidade.get("entrada", {})
        saidas = habilidade.get("saida", {})
        # Formata campos de entrada: "campo: tipo"
        texto_entradas = (
            ", ".join(
                f"{nome_campo}: {tipo_campo}"
                for nome_campo, tipo_campo in entradas.items()
            )
            if entradas
            else "nenhuma"
        )
        # Formata campos de saída: "campo: tipo"
        texto_saidas = (
            ", ".join(
                f"{nome_campo}: {tipo_campo}"
                for nome_campo, tipo_campo in saidas.items()
            )
            if saidas
            else "nenhuma"
        )
        bloco_ferramentas += f"- {nome}: {descricao}\n  entrada: {{{texto_entradas}}}\n  saida: {{{texto_saidas}}}\n"

    if not bloco_ferramentas:
        bloco_ferramentas = "- nenhuma ferramenta disponivel\n"

    # --- Constrói regras do planejador ---
    planejador = contratos.get("planejador", {})
    regras_planejador = planejador.get("regras", [])
    texto_regras = (
        "\n".join(f"- {regra}" for regra in regras_planejador)
        if regras_planejador
        else ""
    )

    # --- Constrói políticas do agente ---
    politicas = contratos.get("regras", {}).get("politicas", [])
    texto_politicas = (
        "\n".join(f"- {politica}" for politica in politicas) if politicas else ""
    )

    # --- Instruções específicas por tipo de agente ---
    instrucoes_tipo = ""
    if tipo_agente == "interactive":
        instrucoes_tipo = """
MODO INTERACTIVE:
- Antes de agir, valide ambiguidades com o usuario usando PERGUNTAR_USUARIO
- Se faltar informacao critica, pergunte antes de chamar ferramentas
- Inclua o campo "pergunta" com a pergunta para o usuario
"""
    elif tipo_agente == "goal_oriented":
        instrucoes_tipo = """
MODO GOAL-ORIENTED:
- Decomponha o objetivo em sub-objetivos executaveis
- Para cada sub-objetivo, planeje quais ferramentas usar
- Reavalie o plano apos cada etapa com base nos resultados
"""
    elif tipo_agente == "autonomous":
        instrucoes_tipo = """
MODO AUTONOMOUS:
- Responda ao evento trigger fornecido na percepcao
- Opere dentro dos limites rigidos definidos
- NUNCA execute acoes destrutivas sem confirmacao humana
- Priorize seguranca sobre velocidade
"""

    # Monta e retorna o prompt completo
    return f"""Voce e o planejador de um agente autonomo.

Agente: {nome_agente} - {descricao_agente}
Tipo: {tipo_agente}
Objetivo: {objetivo}

Etapas do ciclo: {' -> '.join(etapas) if etapas else 'perceber -> planejar -> agir -> avaliar'}

Ferramentas disponiveis:
{bloco_ferramentas}
Formato de resposta (APENAS JSON valido):
{{
  "proxima_acao": "CHAMAR_FERRAMENTA" ou "FINALIZAR" ou "PERGUNTAR_USUARIO",
  "nome_ferramenta": "nome da ferramenta (obrigatorio se CHAMAR_FERRAMENTA)",
  "argumentos_ferramenta": {{}},
  "criterio_sucesso": "o que define sucesso para esta etapa",
  "pergunta": "pergunta para o usuario (obrigatorio se PERGUNTAR_USUARIO)"
}}

CRITICO: o campo "proxima_acao" DEVE ser exatamente um destes 3 valores:
- "CHAMAR_FERRAMENTA" — para executar uma ferramenta
- "FINALIZAR" — para encerrar o ciclo
- "PERGUNTAR_USUARIO" — para pedir informacao ao usuario
NUNCA use o nome da ferramenta como proxima_acao. Use "CHAMAR_FERRAMENTA" e coloque o nome em "nome_ferramenta".

Regras gerais:
- Use cada ferramenta no maximo uma vez, a menos que precise de parametros diferentes
- As chaves de argumentos_ferramenta devem corresponder exatamente aos campos de entrada da ferramenta
- Para campos do tipo object, use dados reais coletados nas etapas anteriores
{instrucoes_tipo}
IMPORTANTE — Regras do planejador (voce DEVE seguir TODAS):
{texto_regras}

IMPORTANTE — Politicas do agente (voce DEVE seguir TODAS):
{texto_politicas}

ATENCAO: voce NAO pode usar FINALIZAR enquanto alguma regra ou politica acima nao for satisfeita.
Se uma regra exige chamar uma ferramenta antes de finalizar, voce DEVE chama-la primeiro.
"""


def chamar_llm(percepcao: str, contratos: dict, historico: list = None) -> tuple:
    """
    Chama a LLM para decidir o proximo passo.

    Parâmetros:
        percepcao (str): Contexto montado pela função perceber()
        contratos (dict): Contratos do agente
        historico (list, opcional): Histórico de etapas anteriores

    Retorna:
        tuple: (plano, uso_tokens)
        - plano (dict): Decisão da LLM (próxima ação, ferramenta, argumentos, etc.)
        - uso_tokens (dict): Quantidade de tokens consumidos
    """
    # Verifica se tem chave da API OpenAI
    chave_api = os.environ.get("OPENAI_API_KEY")

    # Se não tem API key, usa o planejador mock
    if not chave_api:
        return (
            planejador_mock(percepcao, contratos, historico or []),
            _TOKENS_ZERO.copy(),
        )

    # Importa o cliente OpenAI (importado aqui para não falhar se não tiver a biblioteca)
    from openai import OpenAI

    # Cria cliente e faz a chamada
    cliente = OpenAI(api_key=chave_api)
    resposta = cliente.chat.completions.create(
        model="gpt-4o-mini",  # Modelo usado
        response_format={"type": "json_object"},  # Força resposta em JSON
        messages=[
            {
                "role": "system",
                "content": construir_prompt_sistema(contratos),
            },  # Instruções do sistema
            {"role": "user", "content": percepcao},  # Contexto atual
        ],
    )

    # Extrai informações de uso de tokens
    uso_tokens = _TOKENS_ZERO.copy()
    if resposta.usage:
        uso_tokens = {
            "prompt": resposta.usage.prompt_tokens or 0,
            "completion": resposta.usage.completion_tokens or 0,
            "total": resposta.usage.total_tokens or 0,
        }

    # Tenta converter a resposta (JSON) em dicionário
    try:
        plano = json.loads(resposta.choices[0].message.content)
        return plano, uso_tokens
    except (json.JSONDecodeError, IndexError):
        # Se falhou, retorna plano padrão (encerrar)
        return {
            "proxima_acao": "FINALIZAR",
            "criterio_sucesso": "Resposta da LLM nao interpretavel",
        }, uso_tokens


def planejador_mock(percepcao: str, contratos: dict, historico: list = None) -> dict:
    """
    Planejador mock generico - percorre as ferramentas em ordem.

    Usado quando não há API key configurada. Simula um planejador simples
    que chama as ferramentas na ordem em que aparecem no contrato.

    Parâmetros:
        percepcao (str): Contexto atual (usado para detectar o modo)
        contratos (dict): Contratos do agente (para saber quais ferramentas existem)
        historico (list, opcional): Histórico de etapas

    Retorna:
        dict: Plano mock (próxima ação, ferramenta, argumentos, etc.)
    """
    # Obtém lista de ferramentas disponíveis
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])
    nomes_ferramentas = [
        habilidade["nome"] for habilidade in habilidades if "nome" in habilidade
    ]
    historico = historico or []

    # Detecta o tipo do agente a partir da percepção (modo passado na CLI)
    tipo_agente = "task_based"
    for linha in percepcao.split("\n"):
        if linha.startswith("Modo: "):
            tipo_agente = linha.replace("Modo: ", "").strip()
            break

    # Se não detectou, usa o que está no contrato
    if tipo_agente == "task_based":
        tipo_agente = contratos.get("agente", {}).get("tipo", "task_based")

    # --- Modo interactive: pergunta na primeira etapa se não há histórico ---
    if tipo_agente == "interactive" and not historico:
        return {
            "proxima_acao": "PERGUNTAR_USUARIO",
            "nome_ferramenta": None,
            "argumentos_ferramenta": None,
            "criterio_sucesso": "obter informacoes iniciais do usuario",
            "pergunta": "Qual servico esta com problema e desde quando voce observou o alerta?",
        }

    # --- Descobre qual a proxima ferramenta não usada ---
    # Verifica quais ferramentas ainda não foram mencionadas na percepção
    for nome in nomes_ferramentas:
        if nome not in percepcao:
            # Encontra a definição da ferramenta
            habilidade = next((hab for hab in habilidades if hab["nome"] == nome), {})
            # Monta argumentos mock baseados no histórico
            argumentos = montar_argumentos_mock(habilidade, historico)
            return {
                "proxima_acao": "CHAMAR_FERRAMENTA",
                "nome_ferramenta": nome,
                "argumentos_ferramenta": argumentos,
                "criterio_sucesso": f"{nome} executado com sucesso",
            }

    # --- Se todas as ferramentas já foram usadas, finaliza ---
    # Extrai evidências para montar o resumo final
    evidencias = extrair_evidencias_do_historico(historico)
    resumo_partes = []
    for nome_ferramenta, dados in evidencias.items():
        # Pega todos os campos que não começam com "_" (ignora metadados)
        campos = ", ".join(
            f"{chave}={valor}"
            for chave, valor in dados.items()
            if not chave.startswith("_")
        )
        resumo_partes.append(f"[{nome_ferramenta}] {campos}")
    resumo = " | ".join(resumo_partes) if resumo_partes else "sem evidencias"

    return {
        "proxima_acao": "FINALIZAR",
        "nome_ferramenta": None,
        "argumentos_ferramenta": None,
        "criterio_sucesso": f"Diagnostico: {resumo}",
    }
