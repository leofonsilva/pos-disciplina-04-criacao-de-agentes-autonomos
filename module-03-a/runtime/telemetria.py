"""
Telemetria Estruturada.

Coleta eventos do ciclo de execucao e gera streams de observabilidade:
- TELEMETRY_STREAM: eventos do ciclo em tempo real
- AUDIT_LOGS: decisoes e acoes para auditoria
- HEALTH_METRICS: saude do agente (taxas de sucesso, estagnacao)
- PERFORMANCE_DATA: tempos por fase e consumo de tokens
"""

import time  # Para medir tempo de execução
import uuid  # Para gerar IDs únicos (trace_id)
from datetime import datetime  # Para timestamps legíveis


class Telemetria:
    """Coletor de telemetria estruturada para uma execucao do agente."""

    def __init__(self, agente: str, tipo_agente: str):
        """Inicializa o coletor de telemetria com identificadores únicos."""
        # Gera um ID único de 12 caracteres hexadecimais para rastrear esta execução
        self.trace_id = uuid.uuid4().hex[:12]
        self.agente = agente  # Nome do agente sendo executado
        self.tipo_agente = tipo_agente  # Tipo: task_based, interactive, etc.
        self.inicio = time.time()  # Timestamp de início da execução
        
        # Lista para armazenar todos os eventos da execução
        self.eventos = []
        
        # Lista para armazenar medições de tempo por fase (perceber, planejar, agir, avaliar)
        self.fases = []
        
        # Acumulador de tokens consumidos (prompt = entrada, completion = saída, total = soma)
        self.tokens = {"prompt": 0, "completion": 0, "total": 0}
        
        # Contadores de saúde do agente
        self.chamadas_llm = 0  # Quantas vezes a LLM foi chamada
        self.ferramentas_sucesso = 0  # Ferramentas que executaram com sucesso
        self.ferramentas_falha = 0  # Ferramentas que falharam
        self.circuit_breaker_ativacoes = 0  # Quantas vezes o circuit breaker foi ativado
        self.validacao_payload_falhas = 0  # Quantas validações de payload falharam

    # --- registro de eventos ---

    def registrar(self, tipo: str, dados: dict = None):
        """Registra um evento generico na telemetria."""
        self.eventos.append({
            "timestamp": datetime.now().isoformat(),  # Momento exato do evento
            "elapsed_ms": round((time.time() - self.inicio) * 1000),  # ms desde o início
            "trace_id": self.trace_id,  # ID da execução
            "tipo": tipo,  # Tipo do evento (ex: "plano_gerado", "ferramenta_executada")
            "dados": dados or {},  # Dados específicos do evento
        })

    def iniciar_fase(self, nome_fase: str, etapa: int) -> dict:
        """
        Inicia a medicao de tempo de uma fase. Retorna o marcador.

        O marcador é um dicionário que será usado depois em finalizar_fase()
        para calcular quanto tempo a fase levou.
        """
        marcador = {
            "fase": nome_fase,  # Ex: "perceber", "planejar", "agir", "avaliar"
            "etapa": etapa,  # Número da etapa atual
            "inicio": time.time(),  # Momento de início
            "fim": None,  # Será preenchido em finalizar_fase()
            "duracao_ms": None,  # Será preenchido em finalizar_fase()
        }
        return marcador

    def finalizar_fase(self, marcador: dict):
        """Finaliza a medicao de uma fase e registra."""
        marcador["fim"] = time.time()
        # Calcula a duração em milissegundos (1 ms = 0.001 segundo)
        marcador["duracao_ms"] = round((marcador["fim"] - marcador["inicio"]) * 1000, 1)
        
        # Armazena na lista de fases para consultas futuras
        self.fases.append(marcador)
        
        # Registra o evento de conclusão da fase
        self.registrar("fase_concluida", {
            "fase": marcador["fase"],
            "etapa": marcador["etapa"],
            "duracao_ms": marcador["duracao_ms"],
        })

    def registrar_tokens(self, uso: dict):
        """Acumula consumo de tokens."""
        self.tokens["prompt"] += uso.get("prompt", 0)
        self.tokens["completion"] += uso.get("completion", 0)
        self.tokens["total"] += uso.get("total", 0)
        self.chamadas_llm += 1  # Incrementa contador de chamadas à LLM

    def registrar_resultado_ferramenta(self, sucesso: bool):
        """Contabiliza sucesso/falha de ferramentas."""
        if sucesso:
            self.ferramentas_sucesso += 1
        else:
            self.ferramentas_falha += 1

    def registrar_circuit_breaker(self, motivo: str):
        """Registra ativacao do circuit breaker (quando a LLM retorna resposta inválida)."""
        self.circuit_breaker_ativacoes += 1
        self.registrar("circuit_breaker", {"motivo": motivo})

    def registrar_validacao_payload_falha(self, ferramenta: str, erros: list):
        """Registra falha na validacao de payload (argumentos da ferramenta inválidos)."""
        self.validacao_payload_falhas += 1
        self.registrar("validacao_payload_falha", {"ferramenta": ferramenta, "erros": erros})

    # --- streams de saida (diferentes visões dos dados) ---

    def telemetry_stream(self) -> list:
        """Retorna todos os eventos ordenados por timestamp (visão completa)."""
        return self.eventos

    def audit_logs(self) -> list:
        """
        Retorna apenas eventos de decisao e acao para auditoria.

        Filtra eventos importantes para quem precisa auditar o comportamento do agente.
        """
        tipos_auditoria = {
            "plano_gerado",  # Decisão do planejador
            "ferramenta_executada",  # Ação executada
            "circuit_breaker",  # Falha de validação
            "validacao_payload_falha",  # Argumentos inválidos
            "confirmacao_humana",  # Intervenção humana
            "finalizado",  # Término da execução
        }
        return [e for e in self.eventos if e["tipo"] in tipos_auditoria]

    def health_metrics(self) -> dict:
        """
        Retorna metricas de saude do agente.

        Métricas-chave para avaliar se o agente está funcionando bem.
        """
        total_ferramentas = self.ferramentas_sucesso + self.ferramentas_falha
        taxa_sucesso = (
            round(self.ferramentas_sucesso / total_ferramentas * 100, 1)
            if total_ferramentas > 0 else 0.0
        )
        return {
            "trace_id": self.trace_id,
            "taxa_sucesso_ferramentas": taxa_sucesso,  # Percentual de sucesso
            "ferramentas_sucesso": self.ferramentas_sucesso,
            "ferramentas_falha": self.ferramentas_falha,
            "circuit_breaker_ativacoes": self.circuit_breaker_ativacoes,
            "validacao_payload_falhas": self.validacao_payload_falhas,
            "chamadas_llm": self.chamadas_llm,
        }

    def performance_data(self) -> dict:
        """
        Retorna dados de performance: tempos por fase e tokens.

        Útil para identificar gargalos (ex: fase "planejar" muito lenta).
        """
        # Agrupa tempos por nome de fase (perceber, planejar, agir, avaliar)
        tempos_por_fase = {}
        for fase in self.fases:
            nome = fase["fase"]
            if nome not in tempos_por_fase:
                tempos_por_fase[nome] = {"total_ms": 0, "contagem": 0, "max_ms": 0}
            
            tempos_por_fase[nome]["total_ms"] += fase["duracao_ms"]
            tempos_por_fase[nome]["contagem"] += 1
            
            # Atualiza o tempo máximo registrado para esta fase
            if fase["duracao_ms"] > tempos_por_fase[nome]["max_ms"]:
                tempos_por_fase[nome]["max_ms"] = fase["duracao_ms"]

        # Calcula a média para cada fase (total / contagem)
        for nome, dados in tempos_por_fase.items():
            dados["media_ms"] = round(dados["total_ms"] / dados["contagem"], 1)

        return {
            "trace_id": self.trace_id,
            "tempo_total_ms": round((time.time() - self.inicio) * 1000),  # Duração total
            "tokens": self.tokens,
            "chamadas_llm": self.chamadas_llm,
            "fases": tempos_por_fase,
        }

    def kpis_etapa(self, etapa: int) -> dict:
        """
        Retorna latencias das fases planejar e agir para uma etapa especifica.

        Usado para exibir KPIs em tempo real durante a execução.
        """
        latencias = {}
        for fase in self.fases:
            if fase["etapa"] == etapa and fase["fase"] in ("planejar", "agir"):
                latencias[fase["fase"]] = fase["duracao_ms"]
        return latencias

    def resumo_completo(self) -> dict:
        """
        Retorna todos os streams consolidados para o trace.json.

        Esta é a função chamada no final da execução para salvar tudo no arquivo de trace.
        """
        return {
            "trace_id": self.trace_id,
            "agente": self.agente,
            "tipo_agente": self.tipo_agente,
            "telemetry_stream": self.telemetry_stream(),
            "audit_logs": self.audit_logs(),
            "health_metrics": self.health_metrics(),
            "performance_data": self.performance_data(),
        }
