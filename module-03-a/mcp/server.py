"""
MCP Server — expoe tools de monitoramento via Model Context Protocol.

Este servidor e um processo separado que roda independente do agente.
Qualquer agente (nosso framework, LangChain, Claude Code, etc.) pode conectar.

Uso:
  python mcp/server.py

O servidor expoe 2 tools via protocolo MCP (stdio transport):
  - buscar_issues: busca issues abertas num repositorio
  - verificar_ci_status: verifica status do CI/CD de um servico

Requisitos:
  pip install mcp

Nota: Este servidor usa dados simulados para fins didaticos.
      Em producao, conectaria ao GitHub API, Jenkins, etc.
"""

import json  # Para formatar respostas como JSON
from datetime import datetime, timedelta  # Para manipular datas/horas nos dados simulados

# Tenta importar as classes necessárias do pacote MCP
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    _MCP_DISPONIVEL = True  # Flag indicando que o MCP está disponível
except ImportError:
    _MCP_DISPONIVEL = False  # Flag indicando que o MCP NÃO está instalado


def _buscar_issues(repositorio: str, estado: str = "open", labels: list = None) -> dict:
    """Simula busca de issues no repositorio. Retorna dados fictícios."""
    agora = datetime.now()
    
    # Lista simulada de issues com dados realistas
    issues = [
        {
            "numero": 142,
            "titulo": "Latencia elevada apos deploy v2.4.1",
            "estado": "open",
            "labels": ["bug", "p1", "producao"],
            "autor": "eng-oncall",
            "criado_em": (agora - timedelta(hours=2)).isoformat(),  # 2 horas atrás
            "repositorio": repositorio,
        },
        {
            "numero": 138,
            "titulo": "Circuit breaker ativando para upstream-payments",
            "estado": "open",
            "labels": ["bug", "p2"],
            "autor": "monitoring-bot",
            "criado_em": (agora - timedelta(hours=5)).isoformat(),  # 5 horas atrás
            "repositorio": repositorio,
        },
        {
            "numero": 135,
            "titulo": "Aumentar pool de conexoes do checkout",
            "estado": "open",
            "labels": ["enhancement", "infra"],
            "autor": "tech-lead",
            "criado_em": (agora - timedelta(days=2)).isoformat(),  # 2 dias atrás
            "repositorio": repositorio,
        },
    ]

    # Filtra por labels se fornecido
    if labels:
        issues = [i for i in issues if any(l in i["labels"] for l in labels)]
    
    # Filtra por estado se fornecido
    if estado:
        issues = [i for i in issues if i["estado"] == estado]

    return {"issues": issues, "contagem_total": len(issues)}


def _verificar_ci_status(servico: str) -> dict:
    """Simula verificacao de status do CI/CD. Retorna dados fictícios."""
    agora = datetime.now()
    return {
        "servico": servico,
        "pipeline": "main",
        "ultimo_build": {
            "status": "sucesso",
            "versao": "v2.4.1",
            "data": (agora - timedelta(hours=1)).isoformat(),  # 1 hora atrás
            "duracao_segundos": 247,
        },
        "ultimo_deploy": {
            "status": "sucesso",
            "ambiente": "producao",
            "data": (agora - timedelta(minutes=45)).isoformat(),  # 45 minutos atrás
        },
        "testes": {
            "total": 342,
            "passaram": 340,
            "falharam": 2,
            "cobertura_pct": 87.3,
        },
    }


def criar_servidor_mcp():
    """Cria e configura o MCP server com as tools disponiveis."""
    # Verifica se o pacote MCP está instalado
    if not _MCP_DISPONIVEL:
        raise ImportError(
            "Pacote 'mcp' nao instalado. Instale com: pip install mcp\n"
            "Documentacao: https://modelcontextprotocol.io"
        )

    # Cria a instância do servidor MCP com um nome identificador
    server = Server("monitor-mcp-server")

    # Decorator que registra a função que lista as tools disponíveis
    @server.list_tools()
    async def listar_tools():
        """Retorna a lista de ferramentas que a IA pode usar."""
        return [
            Tool(
                name="buscar_issues",
                description="Busca issues abertas no repositorio. Util para correlacionar incidentes com issues conhecidas.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repositorio": {"type": "string", "description": "Nome do repositorio (ex: org/checkout-service)"},
                        "estado": {"type": "string", "description": "Estado das issues: open, closed, all", "default": "open"},
                        "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels para filtrar"},
                    },
                    "required": ["repositorio"],  # Apenas repositorio é obrigatório
                },
            ),
            Tool(
                name="verificar_ci_status",
                description="Verifica status do CI/CD de um servico. Mostra ultimo build, deploy e resultados de testes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "servico": {"type": "string", "description": "Nome do servico"},
                    },
                    "required": ["servico"],
                },
            ),
        ]

    # Decorator que registra a função que executa as tools
    @server.call_tool()
    async def chamar_tool(name: str, arguments: dict):
        """Executa a ferramenta solicitada pela IA."""
        if name == "buscar_issues":
            resultado = _buscar_issues(
                repositorio=arguments.get("repositorio", ""),
                estado=arguments.get("estado", "open"),
                labels=arguments.get("labels"),
            )
        elif name == "verificar_ci_status":
            resultado = _verificar_ci_status(
                servico=arguments.get("servico", ""),
            )
        else:
            resultado = {"erro": f"tool '{name}' nao encontrada"}

        # Retorna o resultado como texto JSON (formato esperado pelo MCP)
        return [TextContent(type="text", text=json.dumps(resultado, ensure_ascii=False, indent=2))]

    return server


# --- Modo standalone (stdio transport) ---
# Executado apenas se este arquivo for rodado diretamente
if __name__ == "__main__":
    # Verifica se o pacote MCP está instalado antes de prosseguir
    if not _MCP_DISPONIVEL:
        print("ERRO: pacote 'mcp' nao instalado.")
        print("Instale com: pip install mcp")
        print("Documentacao: https://modelcontextprotocol.io")
        exit(1)

    import asyncio  # Importa asyncio para rodar o servidor de forma assíncrona

    async def main():
        """Função principal que inicia o servidor MCP."""
        server = criar_servidor_mcp()
        # O stdio_server permite comunicação via entrada/saída padrão
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    print("MCP Server iniciado (stdio transport)")
    print("Tools disponiveis: buscar_issues, verificar_ci_status")
    asyncio.run(main())
