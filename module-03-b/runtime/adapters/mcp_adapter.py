"""
MCP Adapter — conecta skills a MCP servers via Model Context Protocol.

O adapter le do contrato:
  - mcp_server: nome do server (definido em mcp/config.json)
  - tool_name: nome da tool exposta pelo server

O adapter:
  1. Carrega config do MCP server
  2. Inicia o processo do server (stdio transport) via SDK oficial
  3. Faz handshake (initialize) e chama a tool pelo nome
  4. Retorna resultado no formato padrao do harness

Se o MCP server nao estiver disponivel, faz fallback para simulacao.
"""

import asyncio  # Para programação assíncrona (chamadas não-bloqueantes)
import json  # Para manipular JSON (configurações e respostas)
import sys  # Para detectar sistema operacional (Windows)
import time  # Para medir latência da chamada
from pathlib import Path  # Para manipular caminhos de arquivos

from dotenv import load_dotenv  # Para carregar variáveis de ambiente

# Tenta importar as classes necessárias do SDK MCP
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _MCP_SDK_DISPONIVEL = True  # SDK está disponível
except ImportError:
    _MCP_SDK_DISPONIVEL = False  # SDK NÃO está disponível

# Carrega variáveis de ambiente do arquivo .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Configuração específica para Windows: usa ProactorEventLoop (melhor para subprocessos)
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass  # Versão antiga do Python não tem essa política

# Constante de tokens zero (MCP adapter não consome tokens diretamente)
_TOKENS_ZERO = {"prompt": 0, "completion": 0, "total": 0}


def _carregar_config_mcp() -> dict:
    """Carrega configuracao dos MCP servers de mcp/config.json."""
    # Procura o arquivo config.json na pasta mcp (sobe até a raiz do projeto)
    pasta_atual = Path(__file__).resolve().parent.parent.parent
    config_path = pasta_atual / "mcp" / "config.json"
    
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}  # Retorna vazio se não encontrar


async def _chamar_mcp_sdk(comando: str, args: list, cwd: str, tool_name: str, argumentos: dict) -> dict:
    """
    Abre sessao MCP via SDK (stdio_client + ClientSession), faz handshake e chama a tool.

    Este é o coração do adapter: conecta a um servidor MCP externo e executa uma tool.
    """
    # Configura os parâmetros do servidor (comando e argumentos)
    parametros = StdioServerParameters(command=comando, args=args, cwd=cwd)
    
    # Abre o cliente stdio (comunicação via entrada/saída padrão)
    async with stdio_client(parametros) as (leitura, escrita):
        # Cria uma sessão de cliente MCP
        async with ClientSession(leitura, escrita) as sessao:
            # Faz o handshake inicial (negocia capacidades com o servidor)
            await sessao.initialize()
            
            # Chama a tool solicitada
            resultado = await sessao.call_tool(tool_name, arguments=argumentos)
            
            # Verifica se a chamada falhou
            if resultado.isError:
                return None
            
            # Extrai o conteúdo da resposta
            conteudo = resultado.content
            if conteudo and hasattr(conteudo[0], "text"):
                try:
                    return json.loads(conteudo[0].text)  # Tenta converter para JSON
                except json.JSONDecodeError:
                    return {"texto_bruto": conteudo[0].text}  # Retorna como texto bruto
            return None


def _chamar_mcp_server(config_server: dict, tool_name: str, argumentos: dict) -> dict:
    """
    Chama uma tool no MCP server usando o SDK oficial (stdio transport).

    O SDK cuida do handshake JSON-RPC (initialize + initialized) antes do tools/call.
    """
    if not _MCP_SDK_DISPONIVEL:
        return None  # SDK não instalado

    # Extrai comando e argumentos da configuração
    comando = config_server.get("command", "python")
    args = config_server.get("args", [])

    # Converte caminhos relativos para absolutos (se forem arquivos .py)
    pasta_base = Path(__file__).resolve().parent.parent.parent
    args_absolutos = [str(pasta_base / a) if a.endswith(".py") else a for a in args]

    try:
        # Executa a chamada assíncrona com timeout de 15 segundos
        return asyncio.run(
            asyncio.wait_for(
                _chamar_mcp_sdk(comando, args_absolutos, str(pasta_base), tool_name, argumentos),
                timeout=15,
            )
        )
    except (asyncio.TimeoutError, FileNotFoundError, OSError, RuntimeError):
        return None  # Falha na conexão ou timeout
    except Exception:
        return None  # Qualquer outro erro


def _simular_mcp(tool_name: str, argumentos: dict) -> dict:
    """
    Simulacao de resposta MCP quando o server nao esta disponivel.

    Usa as mesmas funcoes do server.py para gerar dados consistentes.
    """
    if tool_name == "buscar_issues":
        from datetime import datetime, timedelta
        agora = datetime.now()
        issues = [
            {
                "numero": 142,
                "titulo": "Latencia elevada apos deploy v2.4.1",
                "estado": "open",
                "labels": ["bug", "p1", "producao"],
                "autor": "eng-oncall",
                "criado_em": (agora - timedelta(hours=2)).isoformat(),
                "repositorio": argumentos.get("repositorio", "desconhecido"),
            },
            {
                "numero": 138,
                "titulo": "Circuit breaker ativando para upstream-payments",
                "estado": "open",
                "labels": ["bug", "p2"],
                "autor": "monitoring-bot",
                "criado_em": (agora - timedelta(hours=5)).isoformat(),
                "repositorio": argumentos.get("repositorio", "desconhecido"),
            },
        ]
        return {"issues": issues, "contagem_total": len(issues)}

    if tool_name == "verificar_ci_status":
        return {
            "servico": argumentos.get("servico", "desconhecido"),
            "ultimo_build": {"status": "sucesso", "versao": "v2.4.1"},
            "testes": {"total": 342, "passaram": 340, "falharam": 2, "cobertura_pct": 87.3},
        }

    return {"erro": f"tool '{tool_name}' nao encontrada no simulador MCP"}


def criar_funcao_mcp(habilidade: dict):
    """
    Cria funcao que chama tool via MCP server.

    Le mcp_server e tool_name do bloco 'conexao'.
    Tenta conectar ao server real. Se falhar, usa simulacao.
    """
    nome = habilidade.get("nome", "")  # Nome da habilidade (fallback)
    conexao = habilidade.get("conexao", {})
    campos_saida = habilidade.get("saida", {})

    nome_server = conexao.get("mcp_server", "")  # Nome do servidor (ex: "monitor-mcp")
    tool_name = conexao.get("tool_name", nome)  # Nome da tool (ex: "buscar_issues")

    def funcao(argumentos):
        """Função executada quando o agente chama esta ferramenta."""
        inicio = time.time()  # Marca início da medição

        # Tenta conectar ao MCP server real
        config = _carregar_config_mcp()  # Carrega config.json
        servers = config.get("mcpServers", {})
        config_server = servers.get(nome_server)

        resultado = None
        via_mcp = False  # Flag indicando se usou MCP real ou simulação

        # Se o servidor está configurado, tenta chamar via MCP
        if config_server:
            resultado = _chamar_mcp_server(config_server, tool_name, argumentos or {})
            if resultado:
                via_mcp = True  # Conseguiu via MCP real

        # Fallback: se falhou, usa simulação
        if resultado is None:
            resultado = _simular_mcp(tool_name, argumentos or {})

        latencia_ms = round((time.time() - inicio) * 1000, 1)

        # Filtra os campos de saída conforme definido no contrato
        if campos_saida and isinstance(resultado, dict):
            dados_filtrados = {}
            for campo in campos_saida:
                if campo in resultado:
                    dados_filtrados[campo] = resultado[campo]
            if not dados_filtrados:
                dados_filtrados = resultado  # Se nenhum campo corresponde, mantém tudo
            dados = dados_filtrados
        else:
            dados = resultado

        # Adiciona metadado de entrada para rastreamento
        if isinstance(dados, dict):
            dados["_entrada"] = argumentos

        # Retorna no formato padrão esperado pelo executor
        return {
            "sucesso": True,
            "dados": dados,
            "_adapter": "mcp",  # Identifica qual adapter foi usado
            "_mcp_server": nome_server,
            "_tool_name": tool_name,
            "_via_mcp_real": via_mcp,  # True = MCP real, False = simulação
            "_latencia_ms": latencia_ms,
            "_tokens": _TOKENS_ZERO.copy(),
        }

    return funcao
