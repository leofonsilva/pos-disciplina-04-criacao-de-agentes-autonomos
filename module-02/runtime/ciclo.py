"""
Ciclo do Agente e Rastreamento.

Orquestra o ciclo principal: perceber -> planejar -> agir -> avaliar.
Salva e exibe o rastreamento da execucao.
Suporta 4 modos: task_based, interactive, goal_oriented, autonomous.

Implementa:
- Circuit breaker entre planejamento e execucao (protege contra respostas inválidas da LLM)
- Validacao de payload de ferramentas (garante que argumentos estão corretos)
- Controle de consumo de tokens (evita estourar limites)
- Telemetria estruturada com trace ID e timing por fase
"""

import json  # Para trabalhar com JSON (trace, histórico)
import sys  # Acessa funcionalidades do sistema
import time  # Para medir tempo de execução das fases
from pathlib import Path  # Trabalha com caminhos de arquivos de forma mais simples

# Importa funções dos módulos internos do projeto
from contratos import carregar_contratos, criar_estado  # Contratos do agente e estado
from executor import avaliar, executar, executar_gancho, validar_payload  # Execução e avaliação
from ferramentas import construir_ferramentas_dos_contratos, montar_argumentos_mock  # Ferramentas disponíveis
from planejador import chamar_llm, perceber  # Planejamento e percepção
from telemetria import Telemetria  # Para coletar métricas e performance


def exibir_kpis(estado: dict, tel, inicio: float, contratos: dict):
    """
    Imprime painel compacto de KPIs ao final de cada etapa do loop.
    
    KPIs = Key Performance Indicators (Indicadores-chave de performance)
    
    Parâmetros:
        estado (dict): Estado atual do agente (etapa, chamadas, tokens, etc.)
        tel: Objeto de telemetria (para metricas)
        inicio (float): Timestamp do início da execução (para calcular tempo decorrido)
        contratos (dict): Contratos do agente (ferramentas, regras, etc.)
    """
    # Extrai limites e contadores do estado
    max_etapas = estado["max_etapas"]  # Número máximo de etapas permitidas
    max_chamadas = estado["max_chamadas_ferramenta"]  # Total máximo de chamadas a ferramentas
    max_tokens = estado.get("max_tokens", 50000)  # Limite máximo de tokens (padrão 50000)
    limite_tempo = estado.get("limite_tempo_segundos", 120)  # Limite de tempo em segundos (padrão 120)

    etapa = estado["etapa"]  # Etapa atual (começa em 1)
    chamadas = estado["chamadas_ferramenta"]  # Número de chamadas a ferramentas já feitas
    tokens_total = estado["tokens_consumidos"]["total"]  # Total de tokens consumidos
    tempo_decorrido = round(time.time() - inicio, 1)  # Tempo decorrido (arredondado para 1 decimal)

    # Cria uma barra visual de progresso dos tokens (10 blocos)
    pct_tokens = tokens_total / max_tokens if max_tokens > 0 else 0  # Porcentagem usada
    blocos_cheios = int(pct_tokens * 10)  # Quantos blocos preencher (0-10)
    barra = "\u2593" * blocos_cheios + "\u2591" * (10 - blocos_cheios)  # Caractere bloco cheio + vazio
    pct_str = f"{pct_tokens * 100:.1f}%"  # Porcentagem formatada

    # Informações sobre ferramentas: já chamadas, obrigatórias, pendentes
    habilidades = contratos.get("habilidades", {}).get("habilidades", [])  # Lista de habilidades/ferramentas
    obrigatorias = set(contratos.get("regras", {}).get("ferramentas_obrigatorias", []))  # Ferramentas obrigatórias
    nomes_ferramentas = [h["nome"] for h in habilidades]  # Extrai só os nomes das ferramentas
    
    # Monta texto visual com símbolos: ✓ = já chamada, ! = obrigatória pendente, ○ = disponível
    partes_ferramentas = []
    for nome in nomes_ferramentas:
        if nome in estado["chamadas_por_ferramenta"]:
            partes_ferramentas.append(f"\u2713{nome}")  # Check mark - já foi chamada
        elif nome in obrigatorias:
            partes_ferramentas.append(f"!{nome}")  # Ponto de exclamação - obrigatória pendente
        else:
            partes_ferramentas.append(f"\u25cb{nome}")  # Círculo vazio - não chamada ainda
    texto_ferramentas = " ".join(partes_ferramentas)  # Junta tudo em uma string

    # Conta qualidade das ações no histórico
    ok = parcial = falha = 0
    for h in estado["historico"]:
        q = h.get("avaliacao", {}).get("qualidade", "")
        if q == "completa":
            ok += 1
        elif q == "parcial":
            parcial += 1
        elif q == "falha":
            falha += 1

    # Alertas de problemas
    cb = tel.circuit_breaker_ativacoes  # Quantas vezes o circuit breaker foi ativado
    pv = tel.validacao_payload_falhas  # Quantas validações de payload falharam

    # Latência (tempo de resposta) da etapa atual
    lat = tel.kpis_etapa(etapa)  # Obtém latências por fase (perceber, planejar, agir, avaliar)
    partes_lat = [f"{fase}={int(ms)}ms" for fase, ms in lat.items()]  # Formata cada fase
    texto_lat = "  ".join(partes_lat) if partes_lat else "-"

    # Monta e imprime o painel visual
    largura = 58
    print(f"\n  \u250c\u2500 KPIs {'_' * (largura - 8)}\u2510")  # Borda superior
    print(f"  \│ Progresso:  {etapa}/{max_etapas} etapas    {chamadas}/{max_chamadas} chamadas    {tempo_decorrido}s/{limite_tempo}s")
    print(f"  \│ Tokens:     {tokens_total}/{max_tokens} ({pct_str})  {barra}")
    print(f"  \│ Ferramentas: {texto_ferramentas}")
    print(f"  \│ Qualidade:  {ok}/{ok + parcial + falha} ok   {parcial} parcial   {falha} falha")
    print(f"  \│ Alertas:    {cb} circuit_breaker   {pv} payload_invalido")
    print(f"  \│ Latencia:   {texto_lat}")
    print(f"  \u2514{'_' * largura}\u2518")  # Borda inferior


def verificar_sem_progresso(estado: dict, nome_ferramenta: str) -> bool:
    """
    Detecta estagnacao: mesma ferramenta chamada N vezes seguidas.
    
    Parâmetros:
        estado (dict): Estado atual do agente
        nome_ferramenta (str): Nome da ferramenta que está sendo chamada
    
    Retorna:
        bool: True se o agente está estagnado (repetindo a mesma ferramenta sem progresso)
    """
    # Se a ferramenta é a mesma da última vez, incrementa contador
    if nome_ferramenta == estado.get("ultima_ferramenta"):
        estado["etapas_sem_progresso"] += 1
    else:
        # Ferramenta diferente, reseta contador
        estado["etapas_sem_progresso"] = 0
    
    # Atualiza qual foi a última ferramenta
    estado["ultima_ferramenta"] = nome_ferramenta

    # Limite de repetições permitidas (padrão 3)
    limite = estado.get("sem_progresso", 3)
    return estado["etapas_sem_progresso"] >= limite


def verificar_tempo(estado: dict, inicio: float) -> bool:
    """
    Verifica se o limite de tempo foi excedido.
    
    Parâmetros:
        estado (dict): Estado do agente (contém limite_tempo_segundos)
        inicio (float): Timestamp do início da execução
    
    Retorna:
        bool: True se o tempo limite foi excedido
    """
    limite = estado.get("limite_tempo_segundos", 120)  # Padrão 120 segundos (2 minutos)
    return (time.time() - inicio) >= limite


def pedir_confirmacao_humana(nome_ferramenta: str) -> bool:
    """
    Pede confirmacao do operador para acoes sensiveis.
    
    Parâmetros:
        nome_ferramenta (str): Nome da ferramenta que requer autorização
    
    Retorna:
        bool: True se o operador autorizou, False caso contrário
    """
    print(f"\n  [CONFIRMACAO HUMANA] A ferramenta '{nome_ferramenta}' requer autorizacao.")
    try:
        resposta = input(f"  Autorizar execucao de '{nome_ferramenta}'? (s/n): ").strip().lower()
        return resposta in ("s", "sim", "y", "yes")
    except EOFError:  # Caso não haja entrada disponível (ex: execução não-interativa)
        print("  [CONFIRMACAO HUMANA] sem input disponivel - negando por seguranca")
        return False


def acumular_tokens(estado: dict, uso_tokens: dict):
    """
    Acumula tokens consumidos no estado.
    
    Parâmetros:
        estado (dict): Estado do agente (contém tokens_consumidos)
        uso_tokens (dict): Tokens consumidos nesta operação (prompt, completion, total)
    """
    for chave in ("prompt", "completion", "total"):
        estado["tokens_consumidos"][chave] += uso_tokens.get(chave, 0)


def verificar_limite_tokens(estado: dict) -> bool:
    """
    Verifica se o limite de tokens foi excedido.
    
    Parâmetros:
        estado (dict): Estado do agente (contém tokens_consumidos total e max_tokens)
    
    Retorna:
        bool: True se o limite de tokens foi excedido
    """
    return estado["tokens_consumidos"]["total"] >= estado.get("max_tokens", 50000)


# --- Circuit Breaker ---
# Conjunto de ações válidas que a LLM pode retornar (protege contra ações inválidas)
_ACOES_VALIDAS = {"CHAMAR_FERRAMENTA", "FINALIZAR", "PERGUNTAR_USUARIO"}


def validar_resposta_llm(plano: dict, ferramentas_disponiveis: set) -> list:
    """
    Circuit breaker: valida a resposta da LLM antes de passar ao executor.
    
    Verifica se o plano retornado pela LLM está bem formatado e é válido.
    Lista vazia = resposta valida. Lista com itens = problemas encontrados.
    
    Parâmetros:
        plano (dict): Plano gerado pela LLM (contém proxima_acao, nome_ferramenta, etc.)
        ferramentas_disponiveis (set): Conjunto com nomes das ferramentas que existem
    
    Retorna:
        list: Lista de strings com problemas encontrados (vazia se tudo ok)
    """
    problemas = []

    # Verifica se o plano é um dicionário
    if not isinstance(plano, dict):
        return ["resposta da LLM nao e um dicionario valido"]

    # Verifica se tem o campo obrigatório 'proxima_acao'
    proxima_acao = plano.get("proxima_acao")
    if not proxima_acao:
        problemas.append("campo 'proxima_acao' ausente na resposta da LLM")
    elif proxima_acao not in _ACOES_VALIDAS:
        problemas.append(f"proxima_acao '{proxima_acao}' invalida (validas: {', '.join(_ACOES_VALIDAS)})")

    # Se for para chamar ferramenta, valida os dados da ferramenta
    if proxima_acao == "CHAMAR_FERRAMENTA":
        nome = plano.get("nome_ferramenta")
        if not nome:
            problemas.append("CHAMAR_FERRAMENTA sem 'nome_ferramenta'")
        elif nome not in ferramentas_disponiveis:
            problemas.append(f"ferramenta '{nome}' nao existe (disponiveis: {', '.join(ferramentas_disponiveis)})")

        # Verifica se argumentos_ferramenta é um dicionário (se existir)
        args = plano.get("argumentos_ferramenta")
        if args is not None and not isinstance(args, dict):
            problemas.append(f"argumentos_ferramenta deve ser dict, recebido {type(args).__name__}")

    # Se for para perguntar ao usuário, valida se tem a pergunta
    if proxima_acao == "PERGUNTAR_USUARIO":
        if not plano.get("pergunta"):
            problemas.append("PERGUNTAR_USUARIO sem campo 'pergunta'")

    return problemas


def gerar_resumo_final(estado: dict, contratos: dict) -> str:
    """
    Gera resumo final da execucao conforme memory.md.
    
    Parâmetros:
        estado (dict): Estado final do agente
        contratos (dict): Contratos do agente (contém configuração de memória)
    
    Retorna:
        str: Texto com resumo da execução (objetivo, etapas, ferramentas, resultado)
    """
    # Obtém configuração de resumo dos contratos (padrão: 5 linhas)
    config_memoria = contratos.get("memoria", {})
    config_resumo = config_memoria.get("resumo_final", {})
    max_linhas = config_resumo.get("max_linhas", 5)

    # Lista as ferramentas que foram chamadas
    ferramentas_chamadas = list(estado["chamadas_por_ferramenta"].keys())
    
    # Monta as linhas do resumo
    linhas = [
        f"Objetivo: {estado['objetivo']}",
        f"Etapas executadas: {estado['etapa']}",
        f"Ferramentas chamadas: {', '.join(ferramentas_chamadas) if ferramentas_chamadas else 'nenhuma'}",
        f"Resultado: {estado['resultado'] or 'max_etapas_excedido'}",
        f"Tipo: {estado.get('tipo_agente', 'task_based')}",
    ]
    return "\n".join(linhas[:max_linhas])  # Retorna apenas as primeiras N linhas


def rodar(
    caminho_agente: str,
    texto_entrada: str,
    modo: str = None,
    evento: str = None,
    saida: str = None,
    arquitetura: str = None,  # NOVO: parâmetro para arquitetura cognitiva (react, plan_execute, reflect)
) -> dict:
    """
    Roda o ciclo completo do agente.
    
    Esta é a função principal que orquestra o loop:
    1. Perceber - monta contexto baseado no estado atual
    2. Planejar - LLM decide qual ação tomar
    3. Agir - executa a ferramenta escolhida
    4. Avaliar - verifica se o objetivo foi alcançado
    
    Parâmetros:
        caminho_agente (str): Caminho para a pasta do agente
        texto_entrada (str): Entrada/input do usuário para o agente
        modo (str, opcional): Modo de operação (task_based, interactive, goal_oriented, autonomous)
        evento (str, opcional): Evento trigger para modo autonomous
        saida (str, opcional): Caminho do arquivo para salvar o trace/resultado
        arquitetura (str, opcional): Arquitetura cognitiva (react, plan_execute, reflect) - NOVO
    
    Retorna:
        dict: Estado final do agente após execução
    """
    # Converte caminho para Path object (caminho absoluto)
    caminho_agente = Path(caminho_agente).resolve()
    
    # Carrega contratos do agente, agora passando arquitetura
    contratos = carregar_contratos(caminho_agente, arquitetura=arquitetura)
    
    # Cria estado inicial, agora passando arquitetura também
    estado = criar_estado(contratos, texto_entrada, modo=modo, evento=evento, arquitetura=arquitetura)
    
    # Constrói as ferramentas que o agente pode usar
    ferramentas = construir_ferramentas_dos_contratos(contratos)
    
    # Carrega contratos de ganchos (hooks) para ações antes/depois das etapas
    contrato_ganchos = contratos.get("ganchos", {})
    inicio = time.time()  # Marca o início da execução

    tipo_agente = estado.get("tipo_agente", "task_based")  # Tipo do agente

    # Inicializa telemetria (coleta de métricas e performance)
    tel = Telemetria(agente=caminho_agente.name, tipo_agente=tipo_agente)
    tel.registrar(
        "inicio",
        {
            "entrada": estado["entrada"],
            "objetivo": estado["objetivo"],
            "max_etapas": estado["max_etapas"],
            "max_tokens": estado.get("max_tokens", 50000),
        },
    )

    # Imprime cabeçalho com informações da execução
    print(f"\n{'='*60}")
    print(f"  Agente: {caminho_agente.name}")
    print(f"  Trace ID: {tel.trace_id}")  # ID único para rastrear esta execução
    print(f"  Tipo: {tipo_agente}")
    print(f"  Objetivo: {estado['objetivo']}")
    print(f"  Entrada: {estado['entrada']}")
    if estado.get("evento"):
        print(f"  Evento: {estado['evento']}")
    if estado.get("arquitetura") and estado["arquitetura"] != "padrao":
        print(f"  Arquitetura: {estado['arquitetura']}")  # NOVO: mostra a arquitetura escolhida
    print(f"  Max etapas: {estado['max_etapas']}")
    print(f"  Limite tempo: {estado['limite_tempo_segundos']}s")
    print(f"  Limite tokens: {estado.get('max_tokens', 50000)}")
    print(f"  Ferramentas: {', '.join(ferramentas.keys())}")
    print(f"{'='*60}\n")

    # Conjunto com nomes das ferramentas disponíveis (para validação)
    nomes_ferramentas_disponiveis = set(ferramentas.keys())

    # Loop principal do agente
    while not estado["concluido"] and estado["etapa"] < estado["max_etapas"]:
        estado["etapa"] += 1  # Incrementa contador de etapas

        # Executa gancho "antes da etapa" se definido nos contratos
        executar_gancho("antes_da_etapa", contrato_ganchos, etapa=estado["etapa"])
        print(f"--- Etapa {estado['etapa']} ---")

        # --- Verificação de limites antes de cada etapa ---
        
        # Verifica limite de tempo
        if verificar_tempo(estado, inicio):
            print(f"  [regras] limite de tempo excedido ({estado['limite_tempo_segundos']}s)")
            tel.registrar("limite_tempo_excedido", {"segundos": estado["limite_tempo_segundos"]})
            estado["concluido"] = True
            estado["resultado"] = "encerrado por limite de tempo"
            break

        # Verifica limite de tokens
        if verificar_limite_tokens(estado):
            print(f"  [regras] limite de tokens excedido ({estado['tokens_consumidos']['total']}/{estado['max_tokens']})")
            tel.registrar("limite_tokens_excedido", estado["tokens_consumidos"])
            estado["concluido"] = True
            estado["resultado"] = f"encerrado por limite de tokens ({estado['tokens_consumidos']['total']})"
            break

        # --- FASE 1: PERCEBER ---
        # Monta o contexto atual (histórico, estado atual, objetivo)
        marcador_perceber = tel.iniciar_fase("perceber", estado["etapa"])
        percepcao = perceber(estado)  # Função que gera o prompt de contexto
        tel.finalizar_fase(marcador_perceber)
        print(f"  [perceber] contexto montado ({marcador_perceber['duracao_ms']}ms)")

        # --- FASE 2: PLANEJAR ---
        # LLM decide qual ação tomar baseada no contexto
        marcador_planejar = tel.iniciar_fase("planejar", estado["etapa"])
        plano, uso_tokens_plano = chamar_llm(percepcao, contratos, estado["historico"])
        tel.finalizar_fase(marcador_planejar)

        # Acumula tokens consumidos pelo planejador
        acumular_tokens(estado, uso_tokens_plano)
        tel.registrar_tokens(uso_tokens_plano)

        # NOVO: mostra se usou LLM real ou mock
        modo_planejar = uso_tokens_plano.get("_modo", "mock")  # "llm" ou "mock"
        print(f"  [planejar] proxima_acao={plano.get('proxima_acao')} ferramenta={plano.get('nome_ferramenta')} ({marcador_planejar['duracao_ms']}ms, tokens={uso_tokens_plano['total']}, via={modo_planejar})")

        # --- REASONING TRACE: exibir raciocinio se a arquitetura produzir ---
        # NOVO: mostra o raciocínio da IA quando disponível (para arquiteturas como "reflect")
        raciocinio = plano.get("raciocinio")
        if raciocinio:
            print(f"  [raciocinio] {raciocinio}")

        # --- CIRCUIT BREAKER: valida resposta da LLM antes de prosseguir ---
        problemas_llm = validar_resposta_llm(plano, nomes_ferramentas_disponiveis)
        if problemas_llm:
            tel.registrar_circuit_breaker("; ".join(problemas_llm))
            print(f"  [circuit_breaker] resposta da LLM rejeitada: {'; '.join(problemas_llm)}")

            # Tenta auto-correção: ação inválida mas nome da ferramenta é válido
            nome_no_plano = plano.get("nome_ferramenta") or plano.get("proxima_acao")
            if (
                any("invalida" in p for p in problemas_llm)
                and nome_no_plano in nomes_ferramentas_disponiveis
            ):
                plano["proxima_acao"] = "CHAMAR_FERRAMENTA"
                plano["nome_ferramenta"] = nome_no_plano
                print(f"  [circuit_breaker] auto-correcao: proxima_acao -> CHAMAR_FERRAMENTA, ferramenta={nome_no_plano}")

            # Fallback: ferramenta não existe, redireciona para próxima não usada
            elif any("nao existe" in p for p in problemas_llm):
                habilidades = contratos.get("habilidades", {}).get("habilidades", [])
                # Procura a primeira ferramenta disponível que ainda não foi chamada
                ferramenta_fallback = next(
                    (h["nome"] for h in habilidades
                     if h.get("nome") in nomes_ferramentas_disponiveis
                     and h["nome"] not in estado["chamadas_por_ferramenta"]),
                    None,
                )
                if ferramenta_fallback:
                    habilidade_fb = next(h for h in habilidades if h["nome"] == ferramenta_fallback)
                    # Cria um novo plano com a ferramenta fallback
                    plano = {
                        "proxima_acao": "CHAMAR_FERRAMENTA",
                        "nome_ferramenta": ferramenta_fallback,
                        "argumentos_ferramenta": montar_argumentos_mock(habilidade_fb, estado["historico"]),
                        "criterio_sucesso": f"fallback apos circuit breaker: {ferramenta_fallback}",
                    }
                    print(f"  [circuit_breaker] redirecionando para fallback: {ferramenta_fallback}")
                else:
                    # Sem fallback disponível, encerra
                    estado["concluido"] = True
                    estado["resultado"] = f"encerrado por circuit breaker: {'; '.join(problemas_llm)}"
                    break
            else:
                # Problemas que não podem ser corrigidos
                estado["concluido"] = True
                estado["resultado"] = f"encerrado por circuit breaker: {'; '.join(problemas_llm)}"
                break

        # Registra o plano gerado na telemetria
        tel.registrar(
            "plano_gerado",
            {
                "proxima_acao": plano.get("proxima_acao"),
                "nome_ferramenta": plano.get("nome_ferramenta"),
                "criterio_sucesso": plano.get("criterio_sucesso"),
            },
        )

        # --- Modo INTERACTIVE: tratar PERGUNTAR_USUARIO ---
        if plano.get("proxima_acao") == "PERGUNTAR_USUARIO":
            pergunta = plano.get("pergunta", "Preciso de mais informacoes.")
            print(f"\n  [interactive] {pergunta}")

            # Se for modo interactive, espera resposta do usuário
            if tipo_agente == "interactive":
                try:
                    resposta_usuario = input("  > Sua resposta: ").strip()
                except EOFError:
                    resposta_usuario = "(sem input disponivel)"
                    print(f"  [interactive] {resposta_usuario}")
            else:
                # Modo não-interativo: não pode perguntar, assume resposta vazia
                resposta_usuario = "(modo nao-interativo: sem resposta do usuario)"
                print(f"  [interactive] {resposta_usuario}")

            # Adiciona ao histórico a interação
            estado["historico"].append({
                "etapa": estado["etapa"],
                "percepcao": percepcao,
                "plano": plano,
                "resultado_acao": {"sucesso": True, "dados": {"resposta_usuario": resposta_usuario}},
                "avaliacao": {"objetivo_alcancado": False, "motivo": "aguardando resposta do usuario"},
            })

            # Executa gancho "após etapa"
            executar_gancho("apos_etapa", contrato_ganchos, etapa=estado["etapa"], acao="pergunta_usuario")
            continue  # Volta para o início do loop

        # --- Verificar ferramentas obrigatórias antes de permitir FINALIZAR ---
        if plano.get("proxima_acao") == "FINALIZAR":
            # Pega lista de ferramentas obrigatórias dos contratos
            obrigatorias = contratos.get("regras", {}).get("ferramentas_obrigatorias", [])
            # Verifica quais ainda não foram chamadas
            faltantes = [
                nome_obrigatoria for nome_obrigatoria in obrigatorias
                if nome_obrigatoria not in estado["chamadas_por_ferramenta"]
            ]
            if faltantes:
                print(f"  [regras] ferramentas obrigatorias pendentes: {', '.join(faltantes)}")
                # Redireciona para a primeira ferramenta obrigatória pendente
                habilidades = contratos.get("habilidades", {}).get("habilidades", [])
                habilidade_faltante = next(
                    (hab for hab in habilidades if hab.get("nome") == faltantes[0]),
                    {},
                )
                plano = {
                    "proxima_acao": "CHAMAR_FERRAMENTA",
                    "nome_ferramenta": faltantes[0],
                    "argumentos_ferramenta": montar_argumentos_mock(habilidade_faltante, estado["historico"]),
                    "criterio_sucesso": f"{faltantes[0]} obrigatorio antes de finalizar",
                }
                print(f"  [regras] redirecionando para: {faltantes[0]}")

        # --- FASE 3: AGIR ---
        resultado_acao = None
        if plano.get("proxima_acao") == "CHAMAR_FERRAMENTA" and plano.get("nome_ferramenta"):
            nome_ferramenta = plano["nome_ferramenta"]

            # Verifica limite total de chamadas de ferramentas
            if estado["chamadas_ferramenta"] >= estado["max_chamadas_ferramenta"]:
                print(f"  [regras] limite total de chamadas de ferramenta atingido ({estado['max_chamadas_ferramenta']})")
                estado["concluido"] = True
                estado["resultado"] = "encerrado por limite total de chamadas de ferramenta"
                break

            # Verifica limite específico desta ferramenta
            chamadas_desta_ferramenta = estado["chamadas_por_ferramenta"].get(nome_ferramenta, 0)
            limite_desta_ferramenta = estado["limites_por_ferramenta"].get(nome_ferramenta)
            if limite_desta_ferramenta and chamadas_desta_ferramenta >= limite_desta_ferramenta:
                print(f"  [regras] limite de {nome_ferramenta} atingido ({limite_desta_ferramenta})")
                estado["concluido"] = True
                estado["resultado"] = f"encerrado por limite de {nome_ferramenta}"
                break

            # Verifica se está estagnado (repetindo mesma ferramenta)
            if verificar_sem_progresso(estado, nome_ferramenta):
                print(f"  [regras] sem progresso detectado - {estado['sem_progresso']} chamadas consecutivas a '{nome_ferramenta}'")
                estado["concluido"] = True
                estado["resultado"] = f"encerrado por estagnacao (ferramenta repetida: {nome_ferramenta})"
                break

            # Verifica se ação sensível requer confirmação humana
            if nome_ferramenta in estado.get("acoes_sensiveis", []):
                tel.registrar("confirmacao_humana", {"ferramenta": nome_ferramenta})
                if not pedir_confirmacao_humana(nome_ferramenta):
                    print(f"  [regras] operador negou execucao de '{nome_ferramenta}'")
                    estado["concluido"] = True
                    estado["resultado"] = f"encerrado por negacao humana ({nome_ferramenta})"
                    break

            # --- VALIDACAO DE PAYLOAD ---
            # Verifica se os argumentos da ferramenta estão corretos (tipos, campos obrigatórios)
            marcador_validacao = tel.iniciar_fase("validar_payload", estado["etapa"])
            erros_payload = validar_payload(nome_ferramenta, plano.get("argumentos_ferramenta"), contratos)
            tel.finalizar_fase(marcador_validacao)

            if erros_payload:
                tel.registrar_validacao_payload_falha(nome_ferramenta, erros_payload)
                print(f"  [validacao_payload] {'; '.join(erros_payload)}")
                # Não bloqueia a execução - apenas registra e continua (graceful degradation)

            # --- EXECUCAO DA FERRAMENTA ---
            marcador_agir = tel.iniciar_fase("agir", estado["etapa"])
            executar_gancho("antes_da_acao", contrato_ganchos, ferramenta=nome_ferramenta)
            resultado_acao = executar(nome_ferramenta, plano.get("argumentos_ferramenta"), ferramentas, contratos)
            tel.finalizar_fase(marcador_agir)

            # Atualiza contadores
            estado["chamadas_ferramenta"] += 1
            estado["chamadas_por_ferramenta"][nome_ferramenta] = chamadas_desta_ferramenta + 1

            # Acumula tokens da ferramenta (se ela usou LLM internamente)
            tokens_ferramenta = resultado_acao.pop("_tokens", {})
            if tokens_ferramenta:
                acumular_tokens(estado, tokens_ferramenta)
                tel.registrar_tokens(tokens_ferramenta)

            sucesso = resultado_acao.get("sucesso", False)
            tel.registrar_resultado_ferramenta(sucesso)
            tel.registrar(
                "ferramenta_executada",
                {
                    "ferramenta": nome_ferramenta,
                    "sucesso": sucesso,
                    "duracao_ms": marcador_agir["duracao_ms"],
                    "tokens": tokens_ferramenta.get("total", 0),
                },
            )

            # Executa ganchos pós-ação
            executar_gancho("apos_acao", contrato_ganchos, sucesso=sucesso)

            if not sucesso:
                executar_gancho("em_erro", contrato_ganchos, erro=resultado_acao.get("erro", ""))

            print(f"  [agir] resultado={json.dumps(resultado_acao, ensure_ascii=False)[:100]} ({marcador_agir['duracao_ms']}ms)")

        # --- FASE 4: AVALIAR ---
        # Avalia se a ação alcançou o objetivo esperado
        marcador_avaliar = tel.iniciar_fase("avaliar", estado["etapa"])
        avaliacao = avaliar(plano, resultado_acao, contratos)
        tel.finalizar_fase(marcador_avaliar)

        qualidade = avaliacao.get("qualidade", "")
        problemas_saida = avaliacao.get("problemas_saida", [])
        if problemas_saida:
            print(f"  [avaliar] qualidade={qualidade} problemas={problemas_saida}")

        print(f"  [avaliar] objetivo_alcancado={avaliacao['objetivo_alcancado']} - {avaliacao['motivo']} ({marcador_avaliar['duracao_ms']}ms)")

        # Atualiza histórico com o resultado desta etapa
        estado["historico"].append({
            "etapa": estado["etapa"],
            "percepcao": percepcao,
            "plano": plano,
            "resultado_acao": resultado_acao,
            "avaliacao": avaliacao,
        })

        # Se objetivo foi alcançado, encerra o loop
        if avaliacao["objetivo_alcancado"]:
            estado["concluido"] = True
            estado["resultado"] = avaliacao["motivo"]

        # Executa gancho "após etapa"
        executar_gancho("apos_etapa", contrato_ganchos, etapa=estado["etapa"], concluido=estado["concluido"])

        # Exibe painel de KPIs atualizado
        exibir_kpis(estado, tel, inicio, contratos)

    # --- Finalização da execução ---
    
    # Registra finalização na telemetria
    tel.registrar(
        "finalizado",
        {
            "etapas": estado["etapa"],
            "resultado": estado["resultado"] or "max_etapas_excedido",
            "tokens_total": estado["tokens_consumidos"]["total"],
        },
    )

    # Calcula tempo total e gera resumo
    tempo_total = round(time.time() - inicio, 2)
    resumo = gerar_resumo_final(estado, contratos)

    # Imprime resumo final
    print(f"\n{'='*60}")
    print(f"  Trace ID: {tel.trace_id}")
    print(f"  Finalizado em {estado['etapa']} etapas ({tempo_total}s)")
    print(f"  Chamadas de ferramenta: {estado['chamadas_ferramenta']}")
    print(f"  Tokens consumidos: {estado['tokens_consumidos']['total']} (prompt={estado['tokens_consumidos']['prompt']}, completion={estado['tokens_consumidos']['completion']})")
    print(f"  Resultado: {estado['resultado'] or 'max_etapas_excedido'}")

    # Exibe Health Metrics (métricas de saúde)
    metricas = tel.health_metrics()
    print(f"\n  --- Health Metrics ---")
    print(f"  Taxa sucesso ferramentas: {metricas['taxa_sucesso_ferramentas']}%")
    print(f"  Circuit breaker ativacoes: {metricas['circuit_breaker_ativacoes']}")
    print(f"  Validacao payload falhas: {metricas['validacao_payload_falhas']}")
    print(f"  Chamadas LLM: {metricas['chamadas_llm']}")

    # Exibe Performance Data
    perf = tel.performance_data()
    print(f"\n  --- Performance por Fase ---")
    for nome_fase, dados_fase in perf["fases"].items():
        print(f"  {nome_fase}: media={dados_fase['media_ms']}ms max={dados_fase['max_ms']}ms total={dados_fase['total_ms']}ms ({dados_fase['contagem']}x)")

    # Exibe resumo
    print(f"\n  --- Resumo ---")
    for linha in resumo.split("\n"):
        print(f"  {linha}")
    print(f"{'='*60}\n")

    # Salva rastreamento em arquivo JSON (agora com arquitetura e agente)
    dados_rastreamento = {
        "trace_id": tel.trace_id,
        "agente": caminho_agente.name,  # NOVO: nome do agente no trace
        "tipo_agente": estado.get("tipo_agente", "task_based"),
        "arquitetura": estado.get("arquitetura", "padrao"),  # NOVO: arquitetura usada
        "entrada": estado["entrada"],
        "evento": estado.get("evento"),
        "tempo_total_segundos": tempo_total,
        "tokens_consumidos": estado["tokens_consumidos"],
        "etapas": estado["historico"],
        "resumo": resumo,
        **tel.resumo_completo(),  # Inclui health_metrics e performance_data
    }

    # Define caminho do arquivo de saída
    caminho_rastreamento = Path(saida) if saida else Path(__file__).parent / "trace.json"
    caminho_rastreamento.write_text(
        json.dumps(dados_rastreamento, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Rastreamento salvo: {caminho_rastreamento}")

    return estado


def replay(caminho_agente: str) -> dict:
    """
    Reexecuta o agente com a mesma entrada da ultima execucao.
    
    Lê o arquivo trace.json da última execução e usa a mesma entrada para rodar novamente.
    
    Parâmetros:
        caminho_agente (str): Caminho para a pasta do agente
    
    Retorna:
        dict: Estado final do agente após reexecução
    """
    caminho_rastreamento = Path(__file__).parent / "trace.json"

    if not caminho_rastreamento.exists():
        print("Nenhum rastreamento encontrado. Rode o agente primeiro.")
        return {}

    # Carrega dados do trace anterior
    dados = json.loads(caminho_rastreamento.read_text(encoding="utf-8"))

    entrada = dados.get("entrada")
    tipo = dados.get("tipo_agente")
    evento = dados.get("evento")

    if not entrada:
        print("Rastreamento nao contem entrada. Nao e possivel fazer replay.")
        return {}

    print(f"  [replay] reexecutando com entrada: {entrada}")
    if tipo:
        print(f"  [replay] tipo: {tipo}")
    if evento:
        print(f"  [replay] evento: {evento}")

    # Roda o agente com os mesmos parâmetros
    return rodar(caminho_agente, entrada, modo=tipo, evento=evento)


def exibir_rastreamento():
    """
    Exibe o rastreamento da ultima execucao em formato legível.
    
    Lê e formata o arquivo trace.json mostrando cada etapa,
    plano, resultado da ação, avaliação, e métricas.
    """
    caminho_rastreamento = Path(__file__).parent / "trace.json"

    if not caminho_rastreamento.exists():
        print("Nenhum rastreamento encontrado. Rode o agente primeiro.")
        return

    # Carrega dados do trace
    dados = json.loads(caminho_rastreamento.read_text(encoding="utf-8"))

    # Suporta formato antigo (lista) e novo (dict com metadados)
    if isinstance(dados, list):
        historico = dados
        metadados = {}
    else:
        historico = dados.get("etapas", [])
        metadados = dados

    # Imprime cabeçalho com metadados
    print(f"\n{'='*60}")
    print("  RASTREAMENTO - ultima execucao")
    if metadados.get("trace_id"):
        print(f"  Trace ID: {metadados['trace_id']}")
    if metadados.get("tipo_agente"):
        print(f"  Tipo: {metadados['tipo_agente']}")
    if metadados.get("entrada"):
        print(f"  Entrada: {metadados['entrada']}")
    if metadados.get("tempo_total_segundos"):
        print(f"  Tempo: {metadados['tempo_total_segundos']}s")
    if metadados.get("tokens_consumidos"):
        tokens = metadados["tokens_consumidos"]
        print(f"  Tokens: {tokens.get('total', 0)} (prompt={tokens.get('prompt', 0)}, completion={tokens.get('completion', 0)})")
    print(f"{'='*60}\n")

    # Exibe cada etapa do histórico
    for registro in historico:
        etapa = registro["etapa"]
        plano = registro.get("plano", {})
        resultado = registro.get("resultado_acao")
        avaliacao = registro.get("avaliacao", {})

        print(f"Etapa {etapa}")
        print(f"  plano     : {plano.get('proxima_acao')} -> {plano.get('nome_ferramenta', '-')}")
        print(f"  criterio  : {plano.get('criterio_sucesso', '-')}")
        if resultado:
            situacao = "ok" if resultado.get("sucesso") else "falha"
            print(f"  acao      : {situacao} - {json.dumps(resultado.get('dados', resultado.get('erro', '')), ensure_ascii=False)[:80]}")
        qualidade = avaliacao.get("qualidade", "")
        print(f"  avaliacao : objetivo_alcancado={avaliacao.get('objetivo_alcancado')}{f' qualidade={qualidade}' if qualidade else ''}")
        print()

    # Exibe Health Metrics se disponíveis
    if metadados.get("health_metrics"):
        metricas = metadados["health_metrics"]
        print("--- Health Metrics ---")
        print(f"  Taxa sucesso: {metricas.get('taxa_sucesso_ferramentas', 0)}%")
        print(f"  Circuit breaker: {metricas.get('circuit_breaker_ativacoes', 0)}")
        print(f"  Payload falhas: {metricas.get('validacao_payload_falhas', 0)}")
        print()

    # Exibe Performance Data se disponível
    if metadados.get("performance_data"):
        perf = metadados["performance_data"]
        print("--- Performance ---")
        print(f"  Tokens: {perf.get('tokens', {})}")
        print(f"  Chamadas LLM: {perf.get('chamadas_llm', 0)}")
        for nome_fase, dados_fase in perf.get("fases", {}).items():
            print(f"  {nome_fase}: media={dados_fase['media_ms']}ms max={dados_fase['max_ms']}ms")
        print()

    # Exibe resumo final
    if metadados.get("resumo"):
        print("--- Resumo ---")
        print(metadados["resumo"])
        print()
