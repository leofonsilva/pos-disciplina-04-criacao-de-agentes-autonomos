"""
Executor - Executar, Avaliar, Validar Payload e Ganchos.

Executa ferramentas, valida payloads contra schema, avalia resultados
semanticamente e dispara ganchos do ciclo.
"""

from datetime import datetime  # Para gerar timestamps nos logs


def executar_gancho(nome: str, contrato_ganchos: dict, **kwargs):
    """Executa um gancho conforme declarado no contrato."""
    ganchos = contrato_ganchos.get("ganchos", {})
    acao = ganchos.get(nome)  # Pega a ação definida para este gancho
    if not acao:
        return  # Se não há ação definida, não faz nada

    # Formata timestamp e detalhes para exibição
    carimbo_tempo = datetime.now().strftime("%H:%M:%S")
    detalhe = " ".join(f"{chave}={valor}" for chave, valor in kwargs.items())

    # Executa a ação conforme configurada
    if acao == "log":
        print(f"  [{carimbo_tempo}] gancho:{nome} {detalhe}")
    elif acao == "alerta":
        print(f"  [{carimbo_tempo}] [ALERTA] gancho:{nome} {detalhe}")


# Mapeia nomes de tipos em strings para os tipos Python correspondentes
# Usado na validação de payload para verificar se os argumentos têm o tipo correto
_MAPA_TIPOS = {
    "string": str,
    "int": (int,),           # Tupla com um elemento
    "float": (int, float),   # Aceita int ou float
    "bool": (bool,),
    "list": (list,),
    "object": (dict,),
}


def validar_payload(nome_ferramenta: str, argumentos: dict, contratos: dict) -> list:
    """Valida os argumentos contra o schema de entrada da ferramenta.

    Retorna lista de erros. Lista vazia = payload valido.
    """
    erros = []
    
    # Busca a definição da ferramenta no contrato de habilidades
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])
    habilidade = next((h for h in habilidades if h.get("nome") == nome_ferramenta), None)

    # Se a ferramenta não existe no schema, retorna erro
    if not habilidade:
        return [f"ferramenta '{nome_ferramenta}' nao encontrada no schema de habilidades"]

    # Pega o schema de entrada da ferramenta
    schema_entrada = habilidade.get("entrada", {})
    argumentos = argumentos or {}  # Se None, vira dicionário vazio

    # Verifica cada campo do schema
    for campo, tipo_esperado in schema_entrada.items():
        # Verifica se o campo está presente
        if campo not in argumentos:
            erros.append(f"campo obrigatorio '{campo}' ausente")
            continue

        valor = argumentos[campo]
        
        # Normaliza o tipo esperado (converte para minúsculo)
        tipo_normalizado = tipo_esperado.lower() if isinstance(tipo_esperado, str) else "string"
        tipos_python = _MAPA_TIPOS.get(tipo_normalizado)

        # Verifica se o valor tem o tipo correto
        if tipos_python and valor is not None:
            if isinstance(tipos_python, tuple):
                # Aceita qualquer tipo da tupla
                if not isinstance(valor, tipos_python):
                    erros.append(f"campo '{campo}': esperado {tipo_normalizado}, recebido {type(valor).__name__}")
            else:
                # Tipo único
                if not isinstance(valor, tipos_python):
                    erros.append(f"campo '{campo}': esperado {tipo_normalizado}, recebido {type(valor).__name__}")

    return erros


def validar_saida(nome_ferramenta: str, resultado: dict, contratos: dict) -> list:
    """Valida os dados de saida contra o schema da ferramenta.

    Retorna lista de problemas encontrados. Lista vazia = saida valida.
    """
    problemas = []
    
    # Se não há resultado ou falhou, não valida
    if not resultado or not resultado.get("sucesso"):
        return problemas

    dados = resultado.get("dados", {})
    
    # Busca a definição da ferramenta
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])
    habilidade = next((h for h in habilidades if h.get("nome") == nome_ferramenta), None)

    if not habilidade:
        return problemas  # Sem schema, não valida

    schema_saida = habilidade.get("saida", {})

    # Verifica cada campo do schema de saída
    for campo, tipo_esperado in schema_saida.items():
        # Verifica se o campo existe no resultado
        if campo not in dados:
            problemas.append(f"campo de saida '{campo}' ausente no resultado")
            continue

        valor = dados[campo]
        
        # Verifica se o valor não está vazio/nulo (mínimo de qualidade)
        if valor is None:
            problemas.append(f"campo de saida '{campo}' retornou None")
        elif isinstance(valor, str) and not valor.strip():
            problemas.append(f"campo de saida '{campo}' retornou string vazia")
        elif isinstance(valor, list) and len(valor) == 0:
            problemas.append(f"campo de saida '{campo}' retornou lista vazia")

    return problemas


def executar(nome_ferramenta: str, argumentos: dict, ferramentas: dict, contratos: dict) -> dict:
    """Executa uma ferramenta com validacao e suporte a retentativas."""
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
                # Segunda tentativa
                resultado = ferramentas[nome_ferramenta](argumentos or {})
            except Exception as erro_nova_tentativa:
                return {"sucesso": False, "erro": str(erro_nova_tentativa)}
        else:
            return {"sucesso": False, "erro": str(erro)}

    return resultado


def avaliar(plano: dict, resultado_acao: dict, contratos: dict = None) -> dict:
    """Avalia o resultado da acao com verificacao semantica."""
    
    # Se o plano decidiu FINALIZAR, considera objetivo alcançado
    if plano.get("proxima_acao") == "FINALIZAR":
        return {"objetivo_alcancado": True, "motivo": plano.get("criterio_sucesso", "")}

    # Se a ação falhou, retorna falha
    if not resultado_acao or not resultado_acao.get("sucesso"):
        motivo = f"etapa falhou - {resultado_acao.get('erro', 'sem dados') if resultado_acao else 'sem resultado'}"
        return {"objetivo_alcancado": False, "motivo": motivo, "qualidade": "falha"}

    # Avaliação semântica: valida saída contra schema da ferramenta
    nome_ferramenta = plano.get("nome_ferramenta", "")
    problemas_saida = []
    if contratos:
        problemas_saida = validar_saida(nome_ferramenta, resultado_acao, contratos)

    criterio = plano.get("criterio_sucesso", "")

    # Define qualidade baseada nos problemas encontrados
    if problemas_saida:
        motivo = f"etapa ok com ressalvas - {'; '.join(problemas_saida)}"
        qualidade = "parcial"
    else:
        motivo = f"etapa ok - criterio: {criterio}" if criterio else "etapa ok - continuar"
        qualidade = "completa"

    return {
        "objetivo_alcancado": False,  # Objetivo final ainda não alcançado
        "motivo": motivo,
        "qualidade": qualidade,
        "problemas_saida": problemas_saida,
    }
