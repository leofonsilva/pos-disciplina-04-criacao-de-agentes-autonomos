"""
Telemetria Estruturada.

Coleta eventos do ciclo de execucao e gera streams de observabilidade:
- TELEMETRY_STREAM: eventos do ciclo em tempo real
- AUDIT_LOGS: decisoes e acoes para auditoria
- HEALTH_METRICS: saude do agente (taxas de sucesso, estagnacao)
- PERFORMANCE_DATA: tempos por fase e consumo de tokens
"""

import time  # Para medir tempos de execução (performance)
import uuid  # Para gerar IDs únicos (trace_id)
from datetime import datetime  # Para timestamps legíveis dos eventos


class Telemetria:
    """
    Coletor de telemetria estruturada para uma execucao do agente.
    
    Esta classe é responsável por coletar e armazenar métricas e eventos
    durante a execução de um agente. Os dados são usados para:
    - Depuração (saber o que aconteceu)
    - Performance (medir tempos de cada fase)
    - Saúde do sistema (taxa de sucesso das ferramentas)
    - Auditoria (quem fez o quê e quando)
    """

    def __init__(self, agente: str, tipo_agente: str):
        """
        Inicializa o coletor de telemetria.
        
        Parâmetros:
            agente (str): Nome do agente (ex: "monitor-agent", "trace-analyzer")
            tipo_agente (str): Tipo do agente (task_based, interactive, etc.)
        """
        # ID único para rastrear esta execução (primeiros 12 caracteres de um UUID)
        self.trace_id = uuid.uuid4().hex[:12]
        
        # Informações básicas do agente
        self.agente = agente
        self.tipo_agente = tipo_agente
        
        # Tempo de início da execução (usado para calcular durações)
        self.inicio = time.time()
        
        # Lista que armazena todos os eventos ocorridos
        self.eventos = []
        
        # Lista que armazena medições de tempo por fase (perceber, planejar, agir, avaliar)
        self.fases = []
        
        # Contadores de tokens consumidos pelas LLMs
        self.tokens = {"prompt": 0, "completion": 0, "total": 0}
        
        # Contador de quantas chamadas à LLM foram feitas
        self.chamadas_llm = 0
        
        # Contadores de sucesso/falha das ferramentas executadas
        self.ferramentas_sucesso = 0
        self.ferramentas_falha = 0
        
        # Contador de ativações do circuit breaker (quando a LLM respondeu com formato inválido)
        self.circuit_breaker_ativacoes = 0
        
        # Contador de falhas na validação de payload (argumentos de ferramentas inválidos)
        self.validacao_payload_falhas = 0

    # --- registro de eventos ---

    def registrar(self, tipo: str, dados: dict = None):
        """
        Registra um evento generico na telemetria.
        
        Parâmetros:
            tipo (str): Tipo do evento (ex: "inicio", "plano_gerado", "ferramenta_executada")
            dados (dict, opcional): Dados adicionais do evento (ex: ferramenta usada, sucesso, etc.)
        """
        # Calcula o tempo decorrido desde o início (em milissegundos)
        elapsed_ms = round((time.time() - self.inicio) * 1000)
        
        # Cria o registro do evento
        self.eventos.append({
            "timestamp": datetime.now().isoformat(),  # Data/hora atual em formato ISO
            "elapsed_ms": elapsed_ms,                  # Tempo decorrido em ms
            "trace_id": self.trace_id,                 # ID da execução (para correlacionar eventos)
            "tipo": tipo,                              # Tipo do evento
            "dados": dados or {},                      # Dados do evento (ou dicionário vazio)
        })

    def iniciar_fase(self, nome_fase: str, etapa: int) -> dict:
        """
        Inicia a medicao de tempo de uma fase.
        
        Uma fase é uma etapa do ciclo do agente:
        - "perceber": montar contexto
        - "planejar": LLM decide próxima ação
        - "agir": executar ferramenta
        - "avaliar": avaliar resultado
        
        Parâmetros:
            nome_fase (str): Nome da fase ("perceber", "planejar", "agir", "avaliar")
            etapa (int): Número da etapa atual
        
        Retorna:
            dict: Marcador da fase (contém início, nome, etapa)
        """
        marcador = {
            "fase": nome_fase,
            "etapa": etapa,
            "inicio": time.time(),   # Marca o instante exato do início
            "fim": None,              # Será preenchido na finalização
            "duracao_ms": None,       # Será preenchido na finalização
        }
        return marcador

    def finalizar_fase(self, marcador: dict):
        """
        Finaliza a medicao de uma fase e registra.
        
        Parâmetros:
            marcador (dict): Marcador retornado por iniciar_fase()
        """
        # Marca o fim da fase
        marcador["fim"] = time.time()
        
        # Calcula a duração em milissegundos (com 1 casa decimal)
        marcador["duracao_ms"] = round((marcador["fim"] - marcador["inicio"]) * 1000, 1)
        
        # Armazena a fase na lista
        self.fases.append(marcador)
        
        # Registra um evento indicando que a fase foi concluída
        self.registrar("fase_concluida", {
            "fase": marcador["fase"],
            "etapa": marcador["etapa"],
            "duracao_ms": marcador["duracao_ms"],
        })

    def registrar_tokens(self, uso: dict):
        """
        Acumula consumo de tokens.
        
        Parâmetros:
            uso (dict): Dicionário com campos "prompt", "completion", "total"
        """
        self.tokens["prompt"] += uso.get("prompt", 0)
        self.tokens["completion"] += uso.get("completion", 0)
        self.tokens["total"] += uso.get("total", 0)
        self.chamadas_llm += 1  # Incrementa contador de chamadas à LLM

    def registrar_resultado_ferramenta(self, sucesso: bool):
        """
        Contabiliza sucesso/falha de ferramentas.
        
        Parâmetros:
            sucesso (bool): True se a ferramenta executou com sucesso, False caso contrário
        """
        if sucesso:
            self.ferramentas_sucesso += 1
        else:
            self.ferramentas_falha += 1

    def registrar_circuit_breaker(self, motivo: str):
        """
        Registra ativacao do circuit breaker.
        
        O circuit breaker é ativado quando a LLM retorna uma resposta
        mal formatada ou inválida.
        
        Parâmetros:
            motivo (str): Descrição do problema que ativou o circuit breaker
        """
        self.circuit_breaker_ativacoes += 1
        self.registrar("circuit_breaker", {"motivo": motivo})

    def registrar_validacao_payload_falha(self, ferramenta: str, erros: list):
        """
        Registra falha na validacao de payload.
        
        Parâmetros:
            ferramenta (str): Nome da ferramenta que teve argumentos inválidos
            erros (list): Lista de erros encontrados na validação
        """
        self.validacao_payload_falhas += 1
        self.registrar("validacao_payload_falha", {
            "ferramenta": ferramenta,
            "erros": erros
        })

    # --- streams de saida ---

    def telemetry_stream(self) -> list:
        """Retorna todos os eventos ordenados por timestamp."""
        return self.eventos

    def audit_logs(self) -> list:
        """
        Retorna apenas eventos de decisao e acao para auditoria.
        
        Estes são os eventos mais importantes para rastrear o que o agente decidiu
        e executou.
        """
        tipos_auditoria = {
            "plano_gerado",           # O que o agente planejou fazer
            "ferramenta_executada",   # Qual ferramenta foi executada
            "circuit_breaker",        # Quando o circuit breaker foi ativado
            "validacao_payload_falha",# Quando argumentos estavam inválidos
            "confirmacao_humana",     # Quando pediu/perguntou para o humano
            "finalizado",             # Quando a execução terminou
        }
        return [e for e in self.eventos if e["tipo"] in tipos_auditoria]

    def health_metrics(self) -> dict:
        """
        Retorna metricas de saude do agente.
        
        Métricas importantes para monitorar a qualidade da execução.
        
        Retorna:
            dict: Dicionário com taxa de sucesso, contadores de falhas, etc.
        """
        # Calcula o total de ferramentas executadas
        total_ferramentas = self.ferramentas_sucesso + self.ferramentas_falha
        
        # Calcula a taxa de sucesso (percentual)
        taxa_sucesso = (
            round(self.ferramentas_sucesso / total_ferramentas * 100, 1)
            if total_ferramentas > 0 else 0.0
        )
        
        return {
            "trace_id": self.trace_id,
            "taxa_sucesso_ferramentas": taxa_sucesso,      # Percentual de sucesso
            "ferramentas_sucesso": self.ferramentas_sucesso,  # Quantas funcionaram
            "ferramentas_falha": self.ferramentas_falha,      # Quantas falharam
            "circuit_breaker_ativacoes": self.circuit_breaker_ativacoes,
            "validacao_payload_falhas": self.validacao_payload_falhas,
            "chamadas_llm": self.chamadas_llm,
        }

    def performance_data(self) -> dict:
        """
        Retorna dados de performance: tempos por fase e tokens.
        
        Estes dados ajudam a identificar gargalos e otimizar a execução.
        
        Retorna:
            dict: Dicionário com tempos por fase, tokens totais, etc.
        """
        # Calcula estatísticas por fase: tempo total, máximo, contagem
        tempos_por_fase = {}
        for fase in self.fases:
            nome = fase["fase"]
            if nome not in tempos_por_fase:
                tempos_por_fase[nome] = {"total_ms": 0, "contagem": 0, "max_ms": 0}
            
            tempos_por_fase[nome]["total_ms"] += fase["duracao_ms"]
            tempos_por_fase[nome]["contagem"] += 1
            
            if fase["duracao_ms"] > tempos_por_fase[nome]["max_ms"]:
                tempos_por_fase[nome]["max_ms"] = fase["duracao_ms"]

        # Calcula a média para cada fase
        for nome, dados in tempos_por_fase.items():
            dados["media_ms"] = round(dados["total_ms"] / dados["contagem"], 1)

        return {
            "trace_id": self.trace_id,
            "tempo_total_ms": round((time.time() - self.inicio) * 1000),  # Duração total
            "tokens": self.tokens,                                        # Tokens consumidos
            "chamadas_llm": self.chamadas_llm,                           # Quantas chamadas à LLM
            "fases": tempos_por_fase,                                     # Tempos por fase
        }

    def kpis_etapa(self, etapa: int) -> dict:
        """
        Retorna latencias das fases planejar e agir para uma etapa especifica.
        
        Parâmetros:
            etapa (int): Número da etapa (1, 2, 3, ...)
        
        Retorna:
            dict: Dicionário com as latências (em ms) de "planejar" e "agir"
        """
        latencias = {}
        for fase in self.fases:
            if fase["etapa"] == etapa and fase["fase"] in ("planejar", "agir"):
                latencias[fase["fase"]] = fase["duracao_ms"]
        return latencias

    def resumo_completo(self) -> dict:
        """
        Retorna todos os streams consolidados para o trace.json.
        
        Este método é chamado ao final da execução para salvar todos os
        dados de telemetria em um único dicionário.
        
        Retorna:
            dict: Todos os dados de telemetria consolidados
        """
        return {
            "trace_id": self.trace_id,
            "agente": self.agente,
            "tipo_agente": self.tipo_agente,
            "telemetry_stream": self.telemetry_stream(),  # Todos os eventos
            "audit_logs": self.audit_logs(),              # Eventos de auditoria
            "health_metrics": self.health_metrics(),      # Métricas de saúde
            "performance_data": self.performance_data(),  # Dados de performance
        }
