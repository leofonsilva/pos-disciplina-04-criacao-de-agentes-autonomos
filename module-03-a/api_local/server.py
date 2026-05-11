"""
API local para testes — simula endpoints de monitoramento.

Uso:
  pip install fastapi uvicorn
  python server.py

Endpoints:
  GET  /api/v1/metrics?service=checkout&window_minutes=60
  GET  /api/v1/logs?service=checkout&window_minutes=60&min_level=WARN
  GET  /api/v1/deploys?service=checkout&window_hours=24

Esta API retorna dados realistas (nao mock) com valores fixos
para que o aluno possa comparar trace mock vs trace real.
"""

# Importa a função random para gerar números aleatórios (não está sendo usada no momento)
import random
# Importa o módulo time para funções relacionadas a tempo (não está sendo usado no momento)
import time
# Importa datetime e timedelta para manipular datas e horas
from datetime import datetime, timedelta

# Importa o uvicorn (servidor ASGI para rodar a aplicação FastAPI)
import uvicorn
# Importa FastAPI para criar a aplicação web e Query para parâmetros de consulta
from fastapi import FastAPI, Query

# Cria a aplicação FastAPI com título e versão
app = FastAPI(title="Monitor API Local", version="1.0")


@app.get("/api/v1/metrics")
def get_metrics(
    service: str = Query(..., description="Nome do servico"),
    window_minutes: int = Query(60, description="Janela de tempo em minutos"),
):
    """Retorna metricas reais do servico."""
    # Retorna um dicionário com dados fixos de métricas
    # O ... no Query significa que o parâmetro é obrigatório
    return {
        "latencia_p99_ms": 342.7,           # Latência percentil 99 em milissegundos
        "vazao_rps": 1847,                  # Requisições por segundo
        "taxa_erro": 4.2,                   # Percentual de erros
        "status": "degradado",              # Status atual do serviço
        "servico": service,                 # Nome do serviço (ecoando o parâmetro)
        "janela_minutos": window_minutes,   # Janela de tempo (ecoando o parâmetro)
        "coletado_em": datetime.now().isoformat(),  # Timestamp atual no formato ISO
    }


@app.get("/api/v1/logs")
def get_logs(
    service: str = Query(..., description="Nome do servico"),
    window_minutes: int = Query(60, description="Janela de tempo"),
    min_level: str = Query("WARN", description="Nivel minimo"),
):
    """Retorna logs estruturados do servico."""
    # Pega a data/hora atual
    agora = datetime.now()
    return {
        "eventos": [
            {
                # Timestamp de 12 minutos atrás
                "timestamp": (agora - timedelta(minutes=12)).isoformat(),
                "nivel": "ERROR",
                "mensagem": f"timeout conectando a upstream-payments: 30s exceeded",
                "servico": service,
            },
            {
                # Timestamp de 8 minutos atrás
                "timestamp": (agora - timedelta(minutes=8)).isoformat(),
                "nivel": "ERROR",
                "mensagem": f"circuit breaker aberto para upstream-payments",
                "servico": service,
            },
            {
                # Timestamp de 5 minutos atrás
                "timestamp": (agora - timedelta(minutes=5)).isoformat(),
                "nivel": "WARN",
                "mensagem": f"latencia p99 acima do SLO: 342ms > 200ms",
                "servico": service,
            },
        ],
        "contagem_total": 3,
    }


@app.get("/api/v1/deploys")
def get_deploys(
    service: str = Query(..., description="Nome do servico"),
    window_hours: int = Query(24, description="Janela em horas"),
):
    """Retorna historico de deploys do servico."""
    agora = datetime.now()
    return {
        "deploys": [
            {
                "versao": "v2.4.1",         # Versão do deploy
                # Timestamp de 45 minutos atrás
                "data_hora": (agora - timedelta(minutes=45)).isoformat(),
                "autor": "ci/cd-pipeline",  # Quem fez o deploy
                "status": "sucesso",        # Status do deploy
                "mudancas": "refactor connection pool settings",  # O que mudou
            },
        ],
        "contagem_total": 1,
    }


# Executa apenas se este arquivo for rodado diretamente (não importado como módulo)
if __name__ == "__main__":
    print("Iniciando API local em http://localhost:8100")
    print("Endpoints:")
    print("  GET /api/v1/metrics?service=checkout&window_minutes=60")
    print("  GET /api/v1/logs?service=checkout&window_minutes=60&min_level=WARN")
    print("  GET /api/v1/deploys?service=checkout&window_hours=24")
    # Inicia o servidor uvicorn na porta 8100, acessível de qualquer IP
    uvicorn.run(app, host="0.0.0.0", port=8100)
