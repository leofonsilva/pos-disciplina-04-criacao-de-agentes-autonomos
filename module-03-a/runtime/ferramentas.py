"""
Ferramentas e Evidencias.

Resolve skills declarados em skills.md para implementacoes reais via adapters.
O campo tipo_implementacao define como resolver:
  - mock    → LLM gera dados (Unidades 1 e 2)
  - rest    → rest_adapter.py chama API HTTP
  - database → db_adapter.py executa query parametrizada
  - mcp     → mcp_adapter.py conecta a MCP server

Se tipo_implementacao nao esta definido, usa mock (backward compatible).
"""

import json  # Para trabalhar com JSON (argumentos e respostas)
import os  # Para acessar variáveis de ambiente (OPENAI_API_KEY)
import random  # Para gerar valores aleatórios no fallback
from pathlib import Path  # Para manipular caminhos de arquivos

try:
    from dotenv import load_dotenv  # Carrega variáveis de ambiente do arquivo .env
except ImportError:
    def load_dotenv(*a, **kw): pass  # Se não instalado, não faz nada

# Carrega variáveis de ambiente do arquivo .env na mesma pasta deste script
load_dotenv(Path(__file__).parent / ".env")

# Constante para consumo de tokens quando não há chamada à LLM
_TOKENS_ZERO = {"prompt": 0, "completion": 0, "total": 0}


def _chamar_llm_ferramenta(prompt_sistema: str, prompt_usuario: str, campos_saida: dict) -> tuple:
    """
    Chama a LLM para gerar a saida de uma ferramenta.

    Parâmetros:
    - prompt_sistema: instrução que define o comportamento da ferramenta
    - prompt_usuario: argumentos recebidos para gerar os dados
    - campos_saida: esquema com os campos que devem ser retornados

    Retorna (dados, uso_tokens). dados = None se falhar ou sem API key.
    """
    # Verifica se a chave da API OpenAI está configurada
    chave_api = os.environ.get("OPENAI_API_KEY")
    if not chave_api:
        return None, _TOKENS_ZERO.copy()  # Sem chave, retorna fallback

    from openai import OpenAI  # Importa o cliente OpenAI apenas se necessário

    cliente = OpenAI(api_key=chave_api)
    
    # Faz a chamada à LLM pedindo resposta em JSON
    resposta = cliente.chat.completions.create(
        model="gpt-4o-mini",  # Modelo pequeno e rápido, bom para ferramentas
        response_format={"type": "json_object"},  # Força resposta em JSON
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario},
        ],
    )

    # Extrai informações de consumo de tokens
    uso_tokens = _TOKENS_ZERO.copy()
    if resposta.usage:
        uso_tokens = {
            "prompt": resposta.usage.prompt_tokens or 0,
            "completion": resposta.usage.completion_tokens or 0,
            "total": resposta.usage.total_tokens or 0,
        }

    # Tenta converter a resposta para JSON
    try:
        return json.loads(resposta.choices[0].message.content), uso_tokens
    except (json.JSONDecodeError, IndexError):
        return None, uso_tokens  # Falha no parsing


def construir_ferramenta(habilidade: dict):
    """
    Cria uma funcao que usa a LLM para gerar dados reais.

    Parâmetro:
    - habilidade: dicionário com nome, descrição, entrada e saída da ferramenta

    Retorna uma função que recebe argumentos e retorna dicionário padronizado.
    """
    nome = habilidade.get("nome", "")
    descricao = habilidade.get("descricao", "")
    campos_saida = habilidade.get("saida", {})
    campos_entrada = habilidade.get("entrada", {})

    # Formata a lista de campos de saída para incluir no prompt
    texto_saida = "\n".join(f"  - {campo}: {tipo}" for campo, tipo in campos_saida.items())

    # Prompt do sistema que define o comportamento da ferramenta
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

    def funcao(argumentos):
        """Função executada quando a ferramenta é chamada."""
        # Converte os argumentos para JSON para envio à LLM
        prompt_usuario = f"Argumentos recebidos:\n{json.dumps(argumentos, indent=2, ensure_ascii=False)}"

        # Tenta gerar dados via LLM
        dados_llm, uso_tokens = _chamar_llm_ferramenta(prompt_sistema, prompt_usuario, campos_saida)

        if dados_llm:
            # Se conseguiu via LLM, retorna sucesso com os dados
            dados_llm["_entrada"] = argumentos  # Guarda os argumentos para rastreamento
            return {"sucesso": True, "dados": dados_llm, "_tokens": uso_tokens}

        # Fallback: gera dados mock simples (quando não tem API key ou falhou)
        dados = {}
        for nome_campo, tipo_campo in campos_saida.items():
            dados[nome_campo] = _gerar_valor_fallback(tipo_campo, nome_campo)
        dados["_entrada"] = argumentos
        return {"sucesso": True, "dados": dados, "_tokens": _TOKENS_ZERO.copy()}

    return funcao


def _gerar_valor_fallback(tipo_campo: str, nome_campo: str):
    """
    Fallback quando nao ha API key — gera valores minimos.

    Retorna um valor falso mas com o tipo correto para não quebrar a execução.
    """
    tipo_normalizado = tipo_campo.lower() if isinstance(tipo_campo, str) else "string"
    
    if tipo_normalizado == "float":
        return round(random.uniform(0.01, 100.0), 2)
    if tipo_normalizado == "int":
        return random.randint(1, 500)
    if tipo_normalizado == "bool":
        return random.choice([True, False])
    if tipo_normalizado == "list":
        return [{"item": f"{nome_campo}_1"}, {"item": f"{nome_campo}_2"}]
    if tipo_normalizado == "object":
        return {"campo": nome_campo, "valor": "sem_api_key"}
    # string e outros tipos
    return f"{nome_campo}_sem_api_key"


def _resolver_adapter(habilidade: dict):
    """
    Resolve o adapter correto com base no tipo_implementacao da skill.

    Retorna uma funcao(argumentos) -> dict com o mesmo formato de sempre:
    {"sucesso": bool, "dados": dict, "_tokens": dict}
    """
    tipo = habilidade.get("tipo_implementacao", "mock")

    if tipo == "rest":
        try:
            from adapters.rest_adapter import criar_funcao_rest
            return criar_funcao_rest(habilidade)
        except ImportError:
            print(f"  [adapters] rest_adapter nao encontrado, usando mock para {habilidade.get('nome')}")
            return construir_ferramenta(habilidade)  # Fallback para mock

    if tipo == "database":
        try:
            from adapters.db_adapter import criar_funcao_database
            return criar_funcao_database(habilidade)
        except ImportError:
            print(f"  [adapters] db_adapter nao encontrado, usando mock para {habilidade.get('nome')}")
            return construir_ferramenta(habilidade)

    if tipo == "mcp":
        try:
            from adapters.mcp_adapter import criar_funcao_mcp
            return criar_funcao_mcp(habilidade)
        except ImportError:
            print(f"  [adapters] mcp_adapter nao encontrado, usando mock para {habilidade.get('nome')}")
            return construir_ferramenta(habilidade)

    # mock (padrao) — comportamento das Unidades 1 e 2
    return construir_ferramenta(habilidade)


def construir_ferramentas_dos_contratos(contratos: dict) -> dict:
    """
    Constroi o registro de ferramentas a partir dos contratos (habilidades).

    Despacha cada skill para o adapter correto via tipo_implementacao.
    Se o adapter nao existe, faz fallback para mock (backward compatible).

    Retorna um dicionário onde as chaves são os nomes das ferramentas
    e os valores são as funções que as implementam.
    """
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])
    ferramentas = {}
    
    for habilidade in habilidades:
        nome = habilidade.get("nome")
        if nome:
            tipo = habilidade.get("tipo_implementacao", "mock")
            ferramentas[nome] = _resolver_adapter(habilidade)
            if tipo != "mock":
                print(f"  [ferramentas] {nome} → {tipo}")
    
    return ferramentas


def extrair_evidencias_do_historico(historico: list) -> dict:
    """
    Extrai evidencias coletadas do historico de forma generica.

    Percorre o histórico e coleta os dados retornados pelas ferramentas
    que foram bem-sucedidas. Usado para alimentar ferramentas futuras.
    """
    evidencias = {}
    for registro in historico:
        plano = registro.get("plano", {})
        resultado = registro.get("resultado_acao")
        nome_ferramenta = plano.get("nome_ferramenta")
        
        # Se a ferramenta foi bem-sucedida, guarda seus dados
        if resultado and resultado.get("sucesso") and nome_ferramenta:
            evidencias[nome_ferramenta] = resultado.get("dados", {})
    
    return evidencias


def montar_argumentos_mock(habilidade: dict, historico: list) -> dict:
    """
    Monta argumentos para uma ferramenta usando evidencias do historico.

    Usado quando a LLM não foi chamada ou o circuit breaker redireciona
    para uma ferramenta. Preenche argumentos baseados no que já foi coletado.
    """
    argumentos = {}
    evidencias = extrair_evidencias_do_historico(historico)

    # Para cada campo de entrada da ferramenta, tenta preencher
    for nome_campo, tipo_campo in habilidade.get("entrada", {}).items():
        tipo_normalizado = tipo_campo.lower() if isinstance(tipo_campo, str) else "string"

        # Se o campo é do tipo 'object' e temos evidencias, usa elas
        if tipo_normalizado == "object" and evidencias:
            argumentos[nome_campo] = evidencias
        else:
            # Caso contrário, gera um valor fallback
            argumentos[nome_campo] = _gerar_valor_fallback(tipo_campo, nome_campo)

    return argumentos
