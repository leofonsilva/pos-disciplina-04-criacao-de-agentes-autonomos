"""
REST Adapter — conecta skills declaradas em skills.md a APIs HTTP reais.

O adapter le do contrato:
  - endpoint, metodo, timeout_segundos, retries, autenticacao

O adapter le do ambiente (.env):
  - API_BASE_URL (base da URL, ex: http://localhost:8100)
  - API_KEY (se autenticacao == header_api_key)

O adapter NUNCA decide nada — apenas conecta.
Toda decisao vem do contrato .md.
"""

import json  # Para manipular JSON (respostas da API)
import os  # Para acessar variáveis de ambiente (API_BASE_URL, API_KEY)
import time  # Para medir latência da chamada HTTP
from pathlib import Path  # Para manipular caminhos de arquivos

import requests  # Biblioteca para fazer requisições HTTP
from dotenv import load_dotenv  # Para carregar variáveis do arquivo .env

# Carrega variáveis de ambiente do arquivo .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Constante de tokens zero (REST adapter não consome tokens)
_TOKENS_ZERO = {"prompt": 0, "completion": 0, "total": 0}


def _mapear_argumentos_para_params(argumentos: dict, campos_entrada: dict) -> dict:
    """
    Mapeia argumentos do agente para query params da API.

    Converte nomes em portugues (do contrato) para nomes em ingles (da API).
    Exemplo: "nome_servico" vira "service"
    """
    # Dicionário de tradução português -> inglês
    mapa = {
        "nome_servico": "service",
        "janela_tempo_minutos": "window_minutes",
        "janela_tempo_horas": "window_hours",
        "nivel_minimo": "min_level",
    }
    
    params = {}
    for chave, valor in argumentos.items():
        # Ignora campos que começam com _ (metadados internos)
        if chave.startswith("_"):
            continue
        # Traduz o nome do campo se houver mapeamento, senão mantém original
        chave_api = mapa.get(chave, chave)
        params[chave_api] = valor
    
    return params


def criar_funcao_rest(habilidade: dict):
    """
    Cria funcao que chama API REST real com base no contrato da skill.

    Lê endpoint, metodo, timeout, retries e autenticacao do bloco 'conexao'.
    Retorna resultado no mesmo formato que o harness espera:
    {"sucesso": bool, "dados": dict, "_tokens": dict}
    """
    # Extrai informações da habilidade (skill)
    nome = habilidade.get("nome", "")
    conexao = habilidade.get("conexao", {})
    campos_entrada = habilidade.get("entrada", {})
    campos_saida = habilidade.get("saida", {})

    # Configurações da conexão com a API
    endpoint = conexao.get("endpoint", "/")  # Caminho da API (ex: "/api/v1/metrics")
    metodo = conexao.get("metodo", "GET").upper()  # GET, POST, PUT, DELETE
    timeout = conexao.get("timeout_segundos", 10)  # Timeout em segundos
    retries = conexao.get("retries", 1)  # Número de tentativas em caso de falha
    tipo_auth = conexao.get("autenticacao", "")  # Tipo de autenticação (ex: "header_api_key")

    # Base URL vinda do ambiente (ex: "http://localhost:8100")
    base_url = os.environ.get("API_BASE_URL", "http://localhost:8100")

    def funcao(argumentos):
        """Função executada quando o agente chama esta ferramenta."""
        
        # Monta a URL completa
        url = f"{base_url}{endpoint}"
        
        # Mapeia argumentos para parâmetros da API (português -> inglês)
        params = _mapear_argumentos_para_params(argumentos or {}, campos_entrada)

        # Monta cabeçalhos HTTP
        headers = {"Content-Type": "application/json"}
        
        # Adiciona autenticação por API Key se configurada
        if tipo_auth == "header_api_key":
            api_key = os.environ.get("API_KEY", "")
            if api_key:
                headers["X-API-Key"] = api_key

        # Executa a requisição com suporte a retentativas
        ultimo_erro = None
        for tentativa in range(1, retries + 1):
            try:
                inicio = time.time()  # Marca início da requisição

                # Executa o método HTTP conforme configurado
                if metodo == "GET":
                    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
                elif metodo == "POST":
                    resp = requests.post(url, json=params, headers=headers, timeout=timeout)
                else:
                    # Para outros métodos (PUT, DELETE, etc.)
                    resp = requests.request(metodo, url, params=params, headers=headers, timeout=timeout)

                latencia_ms = round((time.time() - inicio) * 1000, 1)

                # Verifica se a resposta indica erro (status code >= 400)
                if resp.status_code >= 400:
                    ultimo_erro = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    if tentativa < retries:
                        continue  # Tenta novamente se ainda há retries
                    return {
                        "sucesso": False,
                        "erro": ultimo_erro,
                        "_adapter": "rest",
                        "_latencia_ms": latencia_ms,
                        "_tokens": _TOKENS_ZERO.copy(),
                    }

                # Converte a resposta (JSON) para dicionário Python
                dados = resp.json()

                # Filtra apenas os campos declarados no contrato de saída
                if campos_saida:
                    dados_filtrados = {}
                    for campo in campos_saida:
                        if campo in dados:
                            dados_filtrados[campo] = dados[campo]
                        else:
                            dados_filtrados[campo] = dados.get(campo)
                    
                    # Mantém campos extras úteis para rastreamento
                    for chave in ("servico", "coletado_em"):
                        if chave in dados:
                            dados_filtrados[chave] = dados[chave]
                    
                    dados = dados_filtrados

                # Adiciona metadado de entrada para rastreamento
                dados["_entrada"] = argumentos
                
                return {
                    "sucesso": True,
                    "dados": dados,
                    "_adapter": "rest",
                    "_latencia_ms": latencia_ms,
                    "_tokens": _TOKENS_ZERO.copy(),
                }

            except requests.Timeout:
                ultimo_erro = f"timeout apos {timeout}s (tentativa {tentativa}/{retries})"
                if tentativa < retries:
                    continue  # Tenta novamente
                    
            except requests.ConnectionError:
                ultimo_erro = f"conexao recusada: {url} (tentativa {tentativa}/{retries})"
                if tentativa < retries:
                    continue  # Tenta novamente
                    
            except Exception as e:
                ultimo_erro = f"erro inesperado: {e}"
                break  # Erro inesperado, não tenta novamente

        # Se chegou aqui, todas as tentativas falharam
        return {
            "sucesso": False,
            "erro": ultimo_erro,
            "_adapter": "rest",
            "_tokens": _TOKENS_ZERO.copy(),
        }

    return funcao
