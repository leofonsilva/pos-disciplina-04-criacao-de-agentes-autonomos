"""
Executor - Executar, Avaliar, Validar Payload e Ganchos.

Executa ferramentas, valida payloads contra schema, avalia resultados
semanticamente e dispara ganchos do ciclo.
"""

from datetime import datetime  # Para registrar timestamps nos ganchos


def executar_gancho(nome: str, contrato_ganchos: dict, **kwargs):
    """
    Executa um gancho conforme declarado no contrato.
    
    Ganchos (hooks) são ações que podem ser executadas em momentos específicos do ciclo:
    - antes_da_etapa: antes de cada etapa começar
    - apos_etapa: depois de cada etapa terminar
    - antes_da_acao: antes de chamar uma ferramenta
    - apos_acao: depois de chamar uma ferramenta
    - em_erro: quando ocorre um erro
    
    Parâmetros:
        nome (str): Nome do gancho (ex: "antes_da_etapa")
        contrato_ganchos (dict): Dicionário com os ganchos definidos no contrato
        **kwargs: Argumentos adicionais para contexto (etapa, ferramenta, etc.)
    """
    # Obtém o dicionário de ganchos ou vazio se não existir
    ganchos = contrato_ganchos.get("ganchos", {})
    
    # Pega a ação definida para este gancho (ex: "log" ou "alerta")
    acao = ganchos.get(nome)
    if not acao:
        return  # Se não há ação definida, não faz nada

    # Cria um timestamp no formato HH:MM:SS para log
    carimbo_tempo = datetime.now().strftime("%H:%M:%S")
    
    # Monta uma string com os argumentos extras (ex: "etapa=1 ferramenta=buscar")
    detalhe = " ".join(f"{chave}={valor}" for chave, valor in kwargs.items())

    # Executa a ação conforme configurada
    if acao == "log":
        print(f"  [{carimbo_tempo}] gancho:{nome} {detalhe}")
    elif acao == "alerta":
        print(f"  [{carimbo_tempo}] [ALERTA] gancho:{nome} {detalhe}")


# --- Gap 1: Validacao de Payload ---
# Mapeia strings de tipo para tipos Python correspondentes
# Isso é usado para validar se os argumentos têm o tipo correto
_MAPA_TIPOS = {
    "string": str,                        # Tipo texto (ex: "João")
    "int": (int,),                        # Tipo inteiro (ex: 42)
    "float": (int, float),                # Tipo decimal (ex: 3.14) - aceita int também
    "bool": (bool,),                      # Tipo booleano (True/False)
    "list": (list,),                      # Tipo lista (ex: [1, 2, 3])
    "object": (dict,),                    # Tipo dicionário/objeto (ex: {"nome": "João"})
}


def validar_payload(nome_ferramenta: str, argumentos: dict, contratos: dict) -> list:
    """
    Valida os argumentos contra o schema de entrada da ferramenta.
    
    Verifica se todos os campos obrigatórios estão presentes e se os tipos estão corretos.
    Retorna lista de erros. Lista vazia = payload valido.
    
    Parâmetros:
        nome_ferramenta (str): Nome da ferramenta que será chamada
        argumentos (dict): Dicionário com os argumentos que serão passados
        contratos (dict): Contratos do agente (contém definição das ferramentas)
    
    Retorna:
        list: Lista de strings com erros encontrados (vazia se tudo ok)
    """
    erros = []
    
    # Busca a definição da ferramenta nas habilidades do contrato
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])
    habilidade = next((h for h in habilidades if h.get("nome") == nome_ferramenta), None)

    # Se a ferramenta não foi encontrada nos contratos, retorna erro
    if not habilidade:
        return [f"ferramenta '{nome_ferramenta}' nao encontrada no schema de habilidades"]

    # Obtém o schema de entrada esperado para esta ferramenta
    # Ex: {"name": "string", "age": "int"}
    schema_entrada = habilidade.get("entrada", {})
    
    # Garante que argumentos seja um dicionário (se None, vira vazio)
    argumentos = argumentos or {}

    # Verifica cada campo definido no schema
    for campo, tipo_esperado in schema_entrada.items():
        # Verifica se o campo obrigatório está presente
        if campo not in argumentos:
            erros.append(f"campo obrigatorio '{campo}' ausente")
            continue

        valor = argumentos[campo]
        
        # Normaliza o tipo esperado para string (caso venha em outro formato)
        tipo_normalizado = tipo_esperado.lower() if isinstance(tipo_esperado, str) else "string"
        
        # Obtém os tipos Python correspondentes
        tipos_python = _MAPA_TIPOS.get(tipo_normalizado)

        # Valida o tipo do valor (se não for None)
        if tipos_python and valor is not None:
            # Se tipos_python é uma tupla (aceita múltiplos tipos)
            if isinstance(tipos_python, tuple):
                if not isinstance(valor, tipos_python):
                    erros.append(f"campo '{campo}': esperado {tipo_normalizado}, recebido {type(valor).__name__}")
            # Se é um tipo único
            elif not isinstance(valor, tipos_python):
                erros.append(f"campo '{campo}': esperado {tipo_normalizado}, recebido {type(valor).__name__}")

    return erros


def validar_saida(nome_ferramenta: str, resultado: dict, contratos: dict) -> list:
    """
    Valida os dados de saida contra o schema da ferramenta.
    
    Verifica se todos os campos esperados estão presentes e se não estão vazios.
    Retorna lista de problemas encontrados. Lista vazia = saida valida.
    
    Parâmetros:
        nome_ferramenta (str): Nome da ferramenta
        resultado (dict): Resultado da execução da ferramenta
        contratos (dict): Contratos do agente
    
    Retorna:
        list: Lista de problemas encontrados (vazia se tudo ok)
    """
    problemas = []
    
    # Se não há resultado ou falhou, não precisa validar
    if not resultado or not resultado.get("sucesso"):
        return problemas

    # Extrai os dados de resultado (sucesso=true, dados={...})
    dados = resultado.get("dados", {})
    
    # Busca a definição da ferramenta
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])
    habilidade = next((h for h in habilidades if h.get("nome") == nome_ferramenta), None)

    # Se não encontrou a definição, não valida (assume que está ok)
    if not habilidade:
        return problemas

    # Obtém o schema de saída esperado
    schema_saida = habilidade.get("saida", {})

    # Verifica cada campo do schema de saída
    for campo, tipo_esperado in schema_saida.items():
        # Verifica se o campo está presente no resultado
        if campo not in dados:
            problemas.append(f"campo de saida '{campo}' ausente no resultado")
            continue

        valor = dados[campo]
        tipo_normalizado = tipo_esperado.lower() if isinstance(tipo_esperado, str) else "string"

        # Verifica se o valor não é vazio/nulo (problemas semânticos)
        if valor is None:
            problemas.append(f"campo de saida '{campo}' retornou None")
        elif isinstance(valor, str) and not valor.strip():
            problemas.append(f"campo de saida '{campo}' retornou string vazia")
        elif isinstance(valor, list) and len(valor) == 0:
            problemas.append(f"campo de saida '{campo}' retornou lista vazia")

    return problemas


# --- Execucao ---

def executar(nome_ferramenta: str, argumentos: dict, ferramentas: dict, contratos: dict) -> dict:
    """
    Executa uma ferramenta com validacao e tentativas em caso de falha.
    
    Parâmetros:
        nome_ferramenta (str): Nome da ferramenta a executar
        argumentos (dict): Argumentos para a ferramenta
        ferramentas (dict): Dicionário de funções das ferramentas disponíveis
        contratos (dict): Contratos do agente (para configurar retry)
    
    Retorna:
        dict: Resultado da execução com "sucesso" e "dados" ou "erro"
    """
    # Verifica se a ferramenta existe
    if nome_ferramenta not in ferramentas:
        return {"sucesso": False, "erro": f"Ferramenta '{nome_ferramenta}' nao encontrada na caixa de ferramentas"}

    try:
        # Tenta executar a ferramenta
        resultado = ferramentas[nome_ferramenta](argumentos or {})
    except Exception as erro:
        # Verifica se deve tentar novamente em caso de falha
        config_executor = contratos.get("executor", {}).get("execucao", {})
        if config_executor.get("tentar_novamente_em_falha"):
            try:
                # Tenta executar novamente
                resultado = ferramentas[nome_ferramenta](argumentos or {})
            except Exception as erro_nova_tentativa:
                return {"sucesso": False, "erro": str(erro_nova_tentativa)}
        else:
            # Se não deve tentar novamente, retorna erro
            return {"sucesso": False, "erro": str(erro)}

    return resultado


# --- Gap 4: Avaliacao Semantica ---

def avaliar(plano: dict, resultado_acao: dict, contratos: dict = None) -> dict:
    """
    Avalia o resultado da acao com verificacao semantica.
    
    Esta função determina se a ação teve sucesso e com que qualidade.
    - "completa": ação bem sucedida e dentro do esperado
    - "parcial": ação bem sucedida mas com ressalvas
    - "falha": ação falhou
    
    Parâmetros:
        plano (dict): O plano que foi executado (contém qual ação tomar)
        resultado_acao (dict): Resultado da execução da ferramenta
        contratos (dict, opcional): Contratos para validação semântica
    
    Retorna:
        dict: Avaliação com objetivo_alcancado, motivo, qualidade e problemas
    """
    # Caso especial: se o plano é FINALIZAR, considera objetivo alcançado
    if plano.get("proxima_acao") == "FINALIZAR":
        return {
            "objetivo_alcancado": True,
            "motivo": plano.get("criterio_sucesso", "")
        }

    # Se não há resultado ou a ação falhou
    if not resultado_acao or not resultado_acao.get("sucesso"):
        # Monta mensagem de motivo com o erro
        motivo = f"etapa falhou - {resultado_acao.get('erro', 'sem dados') if resultado_acao else 'sem resultado'}"
        return {
            "objetivo_alcancado": False,
            "motivo": motivo,
            "qualidade": "falha"
        }

    # --- Avaliacao semantica: validar saida contra schema ---
    nome_ferramenta = plano.get("nome_ferramenta", "")
    problemas_saida = []
    
    # Se tiver contratos, valida a saída da ferramenta
    if contratos:
        problemas_saida = validar_saida(nome_ferramenta, resultado_acao, contratos)

    criterio = plano.get("criterio_sucesso", "")  # Critério que define sucesso

    # Avalia com base nos problemas encontrados
    if problemas_saida:
        # Sucesso parcial: executou mas com problemas
        motivo = f"etapa ok com ressalvas - {'; '.join(problemas_saida)}"
        qualidade = "parcial"
    else:
        # Sucesso completo
        motivo = f"etapa ok - criterio: {criterio}" if criterio else "etapa ok - continuar"
        qualidade = "completa"

    # Retorna avaliação (objetivo_alcancado é False pois pode ter mais ações)
    return {
        "objetivo_alcancado": False,
        "motivo": motivo,
        "qualidade": qualidade,
        "problemas_saida": problemas_saida,
    }
