"""
Ferramentas e Evidencias.

Cada ferramenta usa a LLM para gerar dados reais baseados no contexto.
Sem API key, usa fallback mock simples.
Inclui consumo de tokens (_tokens) no resultado para rastreamento.
"""

import json  # Para trabalhar com JSON (entrada/saída das ferramentas)
import os  # Para acessar variáveis de ambiente (ex: OPENAI_API_KEY)
import random  # Para gerar valores aleatórios no fallback
from pathlib import Path  # Para trabalhar com caminhos de arquivos

# Tenta importar dotenv para carregar variáveis do arquivo .env
# Se não estiver instalado, define uma função vazia (não faz nada)
try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(*a, **kw):
        pass


# Carrega variáveis do arquivo .env na pasta atual
load_dotenv(Path(__file__).parent / ".env")

# Constante representando zero tokens (para quando não usa LLM ou falha)
_TOKENS_ZERO = {"prompt": 0, "completion": 0, "total": 0}


def _chamar_llm_ferramenta(
    prompt_sistema: str, prompt_usuario: str, campos_saida: dict
) -> tuple:
    """
    Chama a LLM para gerar a saida de uma ferramenta.

    Parâmetros:
        prompt_sistema (str): Instruções de sistema para a LLM (papel, regras, formato)
        prompt_usuario (str): Pergunta/contexto do usuário
        campos_saida (dict): Esquema dos campos que a LLM deve retornar

    Retorna:
        tuple: (dados, uso_tokens)
        - dados: Dicionário com os dados gerados, ou None se falhar
        - uso_tokens: Dicionário com contagem de tokens consumidos
    """
    # Verifica se a chave da API OpenAI está configurada
    chave_api = os.environ.get("OPENAI_API_KEY")
    if not chave_api:
        # Sem API key, não consegue chamar a LLM
        return None, _TOKENS_ZERO.copy()

    # Importa o cliente OpenAI (importado aqui dentro para não falhar se não tiver a biblioteca)
    from openai import OpenAI

    # Cria cliente com a chave da API
    cliente = OpenAI(api_key=chave_api)

    # Faz a chamada para a LLM
    resposta = cliente.chat.completions.create(
        model="gpt-4o-mini",  # Modelo usado (bom custo-benefício)
        response_format={"type": "json_object"},  # Força a resposta ser JSON válido
        messages=[
            {"role": "system", "content": prompt_sistema},  # Instruções do sistema
            {"role": "user", "content": prompt_usuario},  # Pergunta do usuário
        ],
    )

    # Extrai informações de uso de tokens da resposta
    uso_tokens = _TOKENS_ZERO.copy()
    if resposta.usage:
        uso_tokens = {
            "prompt": resposta.usage.prompt_tokens
            or 0,  # Tokens da mensagem do usuário
            "completion": resposta.usage.completion_tokens or 0,  # Tokens da resposta
            "total": resposta.usage.total_tokens or 0,  # Soma dos dois
        }

    # Tenta converter a resposta da LLM (texto) em JSON/dicionário
    try:
        return json.loads(resposta.choices[0].message.content), uso_tokens
    except (json.JSONDecodeError, IndexError):
        # Se falhou (JSON inválido ou índice inválido), retorna None
        return None, uso_tokens


def construir_ferramenta(habilidade: dict):
    """
    Cria uma funcao que usa a LLM para gerar dados reais.

    Esta função é um factory (fábrica) que retorna uma função pronta para ser usada
    como ferramenta pelo agente.

    Parâmetros:
        habilidade (dict): Definição da ferramenta (nome, descrição, entrada, saída)

    Retorna:
        function: Função que executa a ferramenta
    """
    # Extrai informações da habilidade
    nome = habilidade.get("nome", "")
    descricao = habilidade.get("descricao", "")
    campos_saida = habilidade.get("saida", {})  # O que a ferramenta deve retornar
    campos_entrada = habilidade.get("entrada", {})  # O que a ferramenta recebe

    # Cria uma descrição textual dos campos de saída (para o prompt)
    texto_saida = "\n".join(
        f"  - {campo}: {tipo}" for campo, tipo in campos_saida.items()
    )

    # Prompt do sistema que define o comportamento da LLM para esta ferramenta
    prompt_sistema = f"""Voce e uma ferramenta chamada '{nome}'.
Funcao: {descricao}

Voce DEVE retornar APENAS JSON valido com exatamente estes campos:
{texto_saida}

Regras:
- Gere dados realistas e coerentes com os argumentos recebidos
- Para campos do tipo 'list', retorne uma lista de objetos com detalhes reais
- Para campos do tipo 'object', retorne um objeto estruturado com dados reais
- Para campos do tipo 'string', retorne texto descritivo e especifico
- NUNCA use placeholders como 'mock', 'exemplo', 'teste' — gere conteudo real
- Os dados devem ser coerentes entre si e com o contexto fornecido
- Responda em portugues"""

    # Define a função que será executada quando o agente chamar esta ferramenta
    def funcao(argumentos):
        # Monta o prompt do usuário com os argumentos recebidos
        prompt_usuario = f"Argumentos recebidos:\n{json.dumps(argumentos, indent=2, ensure_ascii=False)}"

        # Tenta chamar a LLM para gerar os dados
        dados_llm, uso_tokens = _chamar_llm_ferramenta(
            prompt_sistema, prompt_usuario, campos_saida
        )

        # Se conseguiu gerar dados com a LLM
        if dados_llm:
            dados_llm["_entrada"] = (
                argumentos  # Adiciona os argumentos recebidos (para rastreamento)
            )
            return {"sucesso": True, "dados": dados_llm, "_tokens": uso_tokens}

        # Fallback: se não tem API key ou falhou, gera valores mock simples
        dados = {}
        for nome_campo, tipo_campo in campos_saida.items():
            dados[nome_campo] = _gerar_valor_fallback(tipo_campo, nome_campo)
        dados["_entrada"] = argumentos
        return {"sucesso": True, "dados": dados, "_tokens": _TOKENS_ZERO.copy()}

    return funcao


def _gerar_valor_fallback(tipo_campo: str, nome_campo: str):
    """
    Fallback quando nao ha API key — gera valores minimos/placeholder.

    Parâmetros:
        tipo_campo (str): Tipo esperado (string, int, float, bool, list, object)
        nome_campo (str): Nome do campo (usado para gerar valores descritivos)

    Retorna:
        Valor mock apropriado para o tipo
    """
    # Normaliza o tipo para minúsculas (ex: "String" -> "string")
    tipo_normalizado = tipo_campo.lower() if isinstance(tipo_campo, str) else "string"

    # Retorna um valor mock baseado no tipo
    if tipo_normalizado == "float":
        return round(
            random.uniform(0.01, 100.0), 2
        )  # Número decimal aleatório entre 0.01 e 100
    if tipo_normalizado == "int":
        return random.randint(1, 500)  # Inteiro aleatório entre 1 e 500
    if tipo_normalizado == "bool":
        return random.choice([True, False])  # True ou False aleatório
    if tipo_normalizado == "list":
        return [
            {"item": f"{nome_campo}_1"},
            {"item": f"{nome_campo}_2"},
        ]  # Lista com 2 itens
    if tipo_normalizado == "object":
        return {"campo": nome_campo, "valor": "sem_api_key"}  # Objeto simples
    # Tipo string (padrão)
    return f"{nome_campo}_sem_api_key"


def construir_ferramentas_dos_contratos(contratos: dict) -> dict:
    """
    Constroi o registro de ferramentas a partir dos contratos (habilidades).

    Parâmetros:
        contratos (dict): Contratos do agente (contém seção "habilidades")

    Retorna:
        dict: Dicionário onde chave = nome da ferramenta, valor = função da ferramenta
    """
    # Extrai a lista de habilidades dos contratos
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])

    # Constrói o dicionário de ferramentas
    ferramentas = {}
    for habilidade in habilidades:
        nome = habilidade.get("nome")
        if nome:  # Só adiciona se tiver nome
            ferramentas[nome] = construir_ferramenta(habilidade)

    return ferramentas


def extrair_evidencias_do_historico(historico: list) -> dict:
    """
    Extrai evidencias coletadas do historico de forma generica.

    Evidências são os dados retornados pelas ferramentas durante a execução.
    Isso permite que ferramentas posteriores usem dados de ferramentas anteriores.

    Parâmetros:
        historico (list): Lista de etapas executadas pelo agente

    Retorna:
        dict: Dicionário onde chave = nome da ferramenta, valor = dados retornados
    """
    evidencias = {}
    for registro in historico:
        plano = registro.get("plano", {})
        resultado = registro.get("resultado_acao")
        nome_ferramenta = plano.get("nome_ferramenta")

        # Se a ferramenta foi bem sucedida, guarda seus dados como evidência
        if resultado and resultado.get("sucesso") and nome_ferramenta:
            evidencias[nome_ferramenta] = resultado.get("dados", {})

    return evidencias


def montar_argumentos_mock(habilidade: dict, historico: list) -> dict:
    """
    Monta argumentos para uma ferramenta usando evidencias do historico.

    Quando o agente precisa chamar uma ferramenta mas não sabe quais argumentos passar,
    esta função cria argumentos automaticamente usando dados de ferramentas anteriores.

    Parâmetros:
        habilidade (dict): Definição da ferramenta (contém os campos esperados)
        historico (list): Histórico de execução (para extrair evidências)

    Retorna:
        dict: Dicionário com argumentos montados para a ferramenta
    """
    argumentos = {}

    # Extrai evidências (resultados de ferramentas anteriores)
    evidencias = extrair_evidencias_do_historico(historico)

    # Para cada campo esperado na entrada da ferramenta
    for nome_campo, tipo_campo in habilidade.get("entrada", {}).items():
        tipo_normalizado = (
            tipo_campo.lower() if isinstance(tipo_campo, str) else "string"
        )

        # Se o campo é do tipo 'object' e temos evidências, usa as evidências
        if tipo_normalizado == "object" and evidencias:
            argumentos[nome_campo] = evidencias
        else:
            # Caso contrário, gera um valor mock simples
            argumentos[nome_campo] = _gerar_valor_fallback(tipo_campo, nome_campo)

    return argumentos
