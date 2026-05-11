"""
Planejador - Perceber e Planejar.

Monta o contexto (percepcao) e decide o proximo passo via LLM ou mock.
Suporta modos: task_based, interactive, goal_oriented, autonomous.
Retorna uso de tokens junto com o plano para controle de consumo.
"""

import json  # Para manipular JSON (planos)
import os  # Para acessar variáveis de ambiente (OPENAI_API_KEY)
from pathlib import Path  # Para manipular caminhos de arquivos

try:
    from dotenv import load_dotenv  # Carrega variáveis de ambiente do arquivo .env
except ImportError:
    def load_dotenv(*a, **kw): pass  # Se não instalado, não faz nada

from ferramentas import extrair_evidencias_do_historico, montar_argumentos_mock

# Carrega variáveis de ambiente do arquivo .env
load_dotenv(Path(__file__).parent / ".env")

# Constante para quando não há consumo de tokens
_TOKENS_ZERO = {"prompt": 0, "completion": 0, "total": 0}


def perceber(estado: dict) -> str:
    """
    Monta o contexto atual para o planejador.

    O contexto inclui: alerta/entrada, modo do agente, histórico de etapas,
    ferramentas usadas, progresso e avisos de estagnacao.
    """
    partes = [f"Alerta: {estado['entrada']}"]

    # Adiciona o modo de operacao do agente
    tipo_agente = estado.get("tipo_agente", "task_based")
    partes.append(f"Modo: {tipo_agente}")

    # Se houver evento (modo autonomous), adiciona
    if estado.get("evento"):
        partes.append(f"Evento trigger: {estado['evento']}")

    # Adiciona histórico de etapas (o que já foi feito)
    for registro in estado["historico"]:
        etapa = registro["etapa"]
        plano = registro.get("plano", {})
        ferramenta_usada = plano.get("nome_ferramenta", "nenhuma")
        if registro.get("resultado_acao"):
            partes.append(f"Etapa {etapa} [{ferramenta_usada}]: {json.dumps(registro['resultado_acao'], ensure_ascii=False)}")

    # Lista ferramentas já utilizadas
    ferramentas_usadas = list(estado["chamadas_por_ferramenta"].keys())
    if ferramentas_usadas:
        partes.append(f"Ferramentas ja utilizadas: {', '.join(ferramentas_usadas)}")

    # Mostra progresso (etapas e chamadas)
    partes.append(f"Etapas realizadas: {estado['etapa']}/{estado['max_etapas']}")
    partes.append(f"Chamadas de ferramenta: {estado['chamadas_ferramenta']}/{estado['max_chamadas_ferramenta']}")

    # Aviso de estagnacao (repeticao de ferramenta)
    if estado.get("etapas_sem_progresso", 0) > 0:
        partes.append(f"ATENCAO: {estado['etapas_sem_progresso']} etapas sem progresso detectadas")

    return "\n".join(partes)


def construir_prompt_sistema(contratos: dict) -> str:
    """
    Constroi o system prompt a partir dos contratos - sem conhecer o dominio.

    O prompt do sistema define para a LLM:
    - Quem ela é (agente)
    - Quais ferramentas estão disponíveis
    - Como deve formatar a resposta
    - Quais regras e políticas deve seguir
    - Comportamento específico por tipo de agente
    """
    # Informações básicas do agente
    agente = contratos.get("agente", {})
    nome_agente = agente.get("nome", "agente")
    descricao_agente = agente.get("descricao", "")
    tipo_agente = agente.get("tipo", "task_based")

    # Objetivo do ciclo
    objetivo = contratos.get("ciclo", {}).get("objetivo", "desconhecido")
    etapas = contratos.get("ciclo", {}).get("etapas", [])

    # Constroi bloco com descricao de todas as ferramentas disponíveis
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])
    bloco_ferramentas = ""
    for habilidade in habilidades:
        nome = habilidade.get("nome", "")
        descricao = habilidade.get("descricao", "")
        entradas = habilidade.get("entrada", {})
        saidas = habilidade.get("saida", {})
        texto_entradas = ", ".join(f"{nome_campo}: {tipo_campo}" for nome_campo, tipo_campo in entradas.items()) if entradas else "nenhuma"
        texto_saidas = ", ".join(f"{nome_campo}: {tipo_campo}" for nome_campo, tipo_campo in saidas.items()) if saidas else "nenhuma"
        bloco_ferramentas += f"- {nome}: {descricao}\n  entrada: {{{texto_entradas}}}\n  saida: {{{texto_saidas}}}\n"

    if not bloco_ferramentas:
        bloco_ferramentas = "- nenhuma ferramenta disponivel\n"

    # Regras do planejador (como deve tomar decisoes)
    planejador = contratos.get("planejador", {})
    regras_planejador = planejador.get("regras", [])
    texto_regras = "\n".join(f"- {regra}" for regra in regras_planejador) if regras_planejador else ""

    # Formato de saida (pode ser customizado por arquitetura)
    formato_saida = planejador.get("formato_saida", {})
    if isinstance(formato_saida, dict) and formato_saida:
        campos_formato = []
        for campo, descricao in formato_saida.items():
            campos_formato.append(f'  "{campo}": "{descricao}"')
        bloco_formato = "{\n" + ",\n".join(campos_formato) + "\n}"
    else:
        # Formato padrao (backward compatible)
        bloco_formato = """{
  "proxima_acao": "CHAMAR_FERRAMENTA" ou "FINALIZAR" ou "PERGUNTAR_USUARIO",
  "nome_ferramenta": "nome da ferramenta (obrigatorio se CHAMAR_FERRAMENTA)",
  "argumentos_ferramenta": {},
  "criterio_sucesso": "o que define sucesso para esta etapa",
  "pergunta": "pergunta para o usuario (obrigatorio se PERGUNTAR_USUARIO)"
}"""

    # Politicas do agente (restricoes de seguranca/comportamento)
    politicas = contratos.get("regras", {}).get("politicas", [])
    texto_politicas = "\n".join(f"- {politica}" for politica in politicas) if politicas else ""

    # Instrucoes especificas por tipo de agente
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
{bloco_formato}

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
    - percepcao: contexto atual montado pela funcao perceber()
    - contratos: definicoes do agente (ferramentas, regras, etc.)
    - historico: lista de etapas ja executadas

    Retorna (plano, uso_tokens) onde plano é um dicionario com a decisao
    e uso_tokens contem {prompt, completion, total, _modo}.
    """
    chave_api = os.environ.get("OPENAI_API_KEY")

    # Se nao tem API key, usa o planejador mock (fallback)
    if not chave_api:
        tokens_mock = _TOKENS_ZERO.copy()
        tokens_mock["_modo"] = "mock"  # Marca que veio do mock
        return planejador_mock(percepcao, contratos, historico or []), tokens_mock

    from openai import OpenAI
    cliente = OpenAI(api_key=chave_api)
    
    # Faz a chamada à LLM pedindo resposta em JSON
    # temperature=0 para respostas determinísticas (menos criativas, mais consistentes)
    # seed=42 para garantir reprodutibilidade (mesma entrada gera mesma saida)
    resposta = cliente.chat.completions.create(
        model="gpt-4o-mini",  # Modelo rapido e barato
        response_format={"type": "json_object"},  # Forca resposta em JSON
        temperature=0,  # Deterministico (reprodutivel)
        seed=42,  # Semente fixa para reproducao dos resultados
        messages=[
            {"role": "system", "content": construir_prompt_sistema(contratos)},
            {"role": "user", "content": percepcao},
        ],
    )

    # Extrai consumo de tokens
    uso_tokens = _TOKENS_ZERO.copy()
    if resposta.usage:
        uso_tokens = {
            "prompt": resposta.usage.prompt_tokens or 0,
            "completion": resposta.usage.completion_tokens or 0,
            "total": resposta.usage.total_tokens or 0,
        }

    # Tenta converter a resposta para JSON
    try:
        plano = json.loads(resposta.choices[0].message.content)
        uso_tokens["_modo"] = "llm"  # Marca que veio da LLM
        return plano, uso_tokens
    except (json.JSONDecodeError, IndexError):
        # Se falhar, retorna um plano de finalizacao com erro
        uso_tokens["_modo"] = "llm"
        return {"proxima_acao": "FINALIZAR", "criterio_sucesso": "Resposta da LLM nao interpretavel"}, uso_tokens


def planejador_mock(percepcao: str, contratos: dict, historico: list = None) -> dict:
    """
    Planejador mock generico - percorre as ferramentas em ordem.

    Usado quando nao ha API key ou para testes. Segue uma logica simples:
    1. Se é modo plan_execute e nao ha historico, gera plano completo
    2. Se é modo interactive e nao ha historico, pergunta ao usuario
    3. Senao, chama a proxima ferramenta nao usada
    4. Se todas foram usadas, finaliza
    """
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])
    nomes_ferramentas = [habilidade["nome"] for habilidade in habilidades if "nome" in habilidade]
    historico = historico or []

    # Detecta se a arquitetura produz campo de raciocinio
    formato_saida = contratos.get("planejador", {}).get("formato_saida", {})
    inclui_raciocinio = "raciocinio" in formato_saida

    # Detecta o tipo do agente pela percepcao
    tipo_agente = "task_based"
    for linha in percepcao.split("\n"):
        if linha.startswith("Modo: "):
            tipo_agente = linha.replace("Modo: ", "").strip()
            break
    if tipo_agente == "task_based":
        tipo_agente = contratos.get("agente", {}).get("tipo", "task_based")

    # Modo plan_execute: gera plano completo na primeira etapa
    modo_execucao = contratos.get("planejador", {}).get("modo_execucao")
    if modo_execucao == "plan_execute" and not historico:
        passos = []
        for i, nome in enumerate(nomes_ferramentas, 1):
            habilidade = next((hab for hab in habilidades if hab["nome"] == nome), {})
            argumentos = montar_argumentos_mock(habilidade, [])
            passos.append({
                "passo": i,
                "objetivo": f"executar {nome}",
                "ferramenta": nome,
                "argumentos_ferramenta": argumentos,
                "criterio_sucesso": f"{nome} executado com dados coletados",
            })
        primeiro_passo = passos[0] if passos else {}
        return {
            "plano_completo": passos,  # Lista completa de passos
            "proxima_acao": "CHAMAR_FERRAMENTA",
            "nome_ferramenta": primeiro_passo.get("ferramenta"),
            "argumentos_ferramenta": primeiro_passo.get("argumentos_ferramenta", {}),
            "criterio_sucesso": primeiro_passo.get("criterio_sucesso", ""),
        }

    # Modo interactive: pergunta na primeira etapa se nao ha historico
    if tipo_agente == "interactive" and not historico:
        plano = {
            "proxima_acao": "PERGUNTAR_USUARIO",
            "nome_ferramenta": None,
            "argumentos_ferramenta": None,
            "criterio_sucesso": "obter informacoes iniciais do usuario",
            "pergunta": "Qual servico esta com problema e desde quando voce observou o alerta?",
        }
        if inclui_raciocinio:
            plano["raciocinio"] = "A entrada e ambigua. Faltam dados criticos como nome do servico e janela de tempo. Preciso perguntar antes de agir."
        return plano

    # Descobre qual a proxima ferramenta nao usada
    ferramentas_usadas = [nome for nome in nomes_ferramentas if nome in percepcao]
    for nome in nomes_ferramentas:
        if nome not in percepcao:
            habilidade = next((hab for hab in habilidades if hab["nome"] == nome), {})
            argumentos = montar_argumentos_mock(habilidade, historico)
            plano = {
                "proxima_acao": "CHAMAR_FERRAMENTA",
                "nome_ferramenta": nome,
                "argumentos_ferramenta": argumentos,
                "criterio_sucesso": f"{nome} executado com sucesso",
            }
            if inclui_raciocinio:
                ja_coletei = ", ".join(ferramentas_usadas) if ferramentas_usadas else "nada ainda"
                plano["raciocinio"] = f"Ja coletei: {ja_coletei}. Proximo passo logico: chamar {nome} para obter mais evidencias."
            return plano

    # Se todas as ferramentas foram usadas, monta resumo e finaliza
    evidencias = extrair_evidencias_do_historico(historico)
    resumo_partes = []
    for nome_ferramenta, dados in evidencias.items():
        campos = ", ".join(f"{chave}={valor}" for chave, valor in dados.items() if not chave.startswith("_"))
        resumo_partes.append(f"[{nome_ferramenta}] {campos}")
    resumo = " | ".join(resumo_partes) if resumo_partes else "sem evidencias"

    plano = {
        "proxima_acao": "FINALIZAR",
        "nome_ferramenta": None,
        "argumentos_ferramenta": None,
        "criterio_sucesso": f"Diagnostico: {resumo}",
    }
    if inclui_raciocinio:
        plano["raciocinio"] = f"Todas as ferramentas foram chamadas. Evidencias coletadas: {', '.join(evidencias.keys())}. Posso finalizar com diagnostico."
    return plano
