"""
CLI do Runtime — ponto de entrada para rodar qualquer agente.

Uso:
  python main.py rodar --agente ../monitor-agent --entrada "alerta de latencia"
  python main.py rodar --agente ../monitor-agent --entrada "alerta" --modo interactive
  python main.py rodar --agente ../monitor-agent --entrada "deploy falhou" --modo autonomous --evento deploy_falhou
  python main.py analisar --agente ../trace-analyzer
  python main.py validar --agente ../monitor-agent
  python main.py rastreamento
  python main.py replay --agente ../monitor-agent
"""

# Importa módulos para processar argumentos da linha de comando, entrada/saída, etc.
import argparse  # Usado para ler e parsear argumentos passados pelo terminal (ex: --agente, --entrada)
import io  # Usado para manipular fluxos de entrada/saída (ex: forçar UTF-8 no Windows)
import sys  # Acessa funcionalidades do sistema, como entrada padrão (stdin, stdout, stderr)
import json  # Trabalha com dados no formato JSON (leitura/escrita de arquivos de trace)
from pathlib import (
    Path,
)  # Trabalha com caminhos de arquivos/pastas de forma mais simples que os.path

# Garante UTF-8 no stdout/stderr em qualquer SO (resolve cp1252 no Windows)
# Verifica se a codificação atual do stdout não é UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    # Recria o stdout com codificação UTF-8, substituindo caracteres não suportados por "?"
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Importa as funções principais dos módulos do projeto
from ciclo import (
    rodar,
    replay,
    exibir_rastreamento,
)  # Funções que controlam o ciclo do agente
from validador import validar  # Função para validar os contratos do agente


def _resumir_trace(dados: dict) -> str:
    """
    Extrai um resumo compacto do trace para usar como entrada do analyzer.

    Parâmetros:
        dados (dict): Dicionário com os dados do trace (histórico de execução)

    Retorna:
        str: Texto resumido com as principais informações do trace
    """
    # Cria uma lista para acumular as linhas do resumo
    linhas = []

    # Adiciona informações básicas do trace
    linhas.append(f"TRACE_ID: {dados.get('trace_id', '?')}")  # ID único da execução
    linhas.append(f"AGENTE: {dados.get('agente', '?')}")  # Nome do agente executado
    linhas.append(
        f"TIPO: {dados.get('tipo_agente', '?')}"
    )  # Tipo do agente (ex: monitor, analyzer...)
    linhas.append(
        f"TEMPO_TOTAL: {dados.get('tempo_total_segundos', 0)}s"
    )  # Duração total em segundos
    linhas.append(
        f"TOKENS: {json.dumps(dados.get('tokens_consumidos', {}))}"
    )  # Tokens usados pela LLM

    # Adiciona resumo de cada etapa da execução
    for etapa in dados.get("etapas", []):  # Percorre cada etapa do pipeline
        num = etapa.get("etapa", "?")  # Número da etapa
        plano = etapa.get("plano", {})  # Plano de ação da etapa
        acao = plano.get("proxima_acao", "?")  # Qual ação foi tomada
        ferramenta = plano.get("nome_ferramenta", "-")  # Nome da ferramenta usada
        resultado = etapa.get("resultado_acao")  # Resultado da ação
        sucesso = (
            resultado.get("sucesso", False) if resultado else None
        )  # Se a ação foi bem sucedida
        avaliacao = etapa.get("avaliacao", {})  # Avaliação da qualidade da ação
        qualidade = avaliacao.get(
            "qualidade", ""
        )  # Qualidade da ação (ex: "bom", "ruim")
        objetivo = avaliacao.get(
            "objetivo_alcancado", False
        )  # Se o objetivo foi alcançado
        motivo = avaliacao.get("motivo", "")  # Motivo da avaliação
        problemas = avaliacao.get("problemas_saida", [])  # Problemas encontrados
        linhas.append(
            f"ETAPA {num}: acao={acao} ferramenta={ferramenta} sucesso={sucesso} "
            f"qualidade={qualidade} objetivo={objetivo} motivo={motivo}"
            + (f" problemas={problemas}" if problemas else "")
        )

    # Adiciona métricas de saúde (health metrics)
    hm = dados.get("health_metrics", {})
    if hm:
        linhas.append(
            f"HEALTH: taxa_sucesso={hm.get('taxa_sucesso_ferramentas', 0)}% "
            f"circuit_breaker={hm.get('circuit_breaker_ativacoes', 0)} "
            f"payload_falhas={hm.get('validacao_payload_falhas', 0)} "
            f"chamadas_llm={hm.get('chamadas_llm', 0)}"
        )

    # Adiciona dados de performance
    perf = dados.get("performance_data", {})
    if perf:
        linhas.append(f"PERF_TOKENS: {json.dumps(perf.get('tokens', {}))}")
        linhas.append(f"PERF_TEMPO_TOTAL_MS: {perf.get('tempo_total_ms', 0)}")
        for fase, d in perf.get("fases", {}).items():
            linhas.append(
                f"PERF_FASE {fase}: media={d['media_ms']}ms max={d['max_ms']}ms "
                f"total={d['total_ms']}ms contagem={d['contagem']}"
            )

    # Adiciona resumo final se existir
    if dados.get("resumo"):
        linhas.append(f"RESUMO: {dados['resumo']}")

    # Junta todas as linhas com quebra de linha
    return "\n".join(linhas)


def _gerar_relatorio_md(dados_trace: dict, dados_analise: dict) -> str:
    """
    Gera relatorio markdown legivel a partir do trace original e da analise.

    Parâmetros:
        dados_trace (dict): Dados do trace original (execução do agente)
        dados_analise (dict): Dados da análise gerada pelo analyzer

    Retorna:
        str: Texto formatado em Markdown com o relatório completo
    """
    # Extrai informações básicas do trace
    agente = dados_trace.get("agente", "desconhecido")
    trace_id = dados_trace.get("trace_id", "?")
    tipo = dados_trace.get("tipo_agente", "?")
    tempo = dados_trace.get("tempo_total_segundos", 0)
    tokens = dados_trace.get("tokens_consumidos", {})
    hm = dados_trace.get("health_metrics", {})
    perf = dados_trace.get("performance_data", {})

    # Extrai resultados das ferramentas do analyzer
    # Um dicionário que mapeia nome da ferramenta -> resultado
    resultados = {}
    for etapa in dados_analise.get("etapas", []):
        plano = etapa.get("plano", {})
        nome = plano.get("nome_ferramenta")
        resultado = etapa.get("resultado_acao")
        if nome and resultado and resultado.get("sucesso"):
            resultados[nome] = resultado.get("dados", {})

    # Pega os dados específicos de cada tipo de análise
    saude = resultados.get("analisar_saude", {})
    performance = resultados.get("analisar_performance", {})
    conformidade = resultados.get("analisar_conformidade", {})
    anomalias_dados = resultados.get("detectar_anomalias", {})
    veredito_dados = resultados.get("gerar_veredito", {})

    # --- montar markdown ---
    md = []  # Lista que acumulará as linhas do relatório

    # Cabeçalho e informações básicas
    md.append(f"# Analise de Execucao: {agente}")
    md.append("")
    md.append(f"- **Trace ID:** {trace_id}")
    md.append(f"- **Tipo:** {tipo}")
    md.append(f"- **Tempo total:** {tempo}s")
    md.append(
        f"- **Tokens:** {tokens.get('total', 0)} (prompt={tokens.get('prompt', 0)}, completion={tokens.get('completion', 0)})"
    )
    md.append("")

    # Tabela com as etapas do pipeline
    etapas_trace = dados_trace.get("etapas", [])
    md.append("## Pipeline Executado")
    md.append("")
    md.append("| Etapa | Acao | Ferramenta | Sucesso | Qualidade |")
    md.append("|-------|------|------------|---------|-----------|")
    for et in etapas_trace:
        num = et.get("etapa", "?")
        plano = et.get("plano", {})
        acao = plano.get("proxima_acao", "-")
        ferr = plano.get("nome_ferramenta", "-") or "-"
        res = et.get("resultado_acao")
        suc = res.get("sucesso", "-") if res else "-"
        qual = et.get("avaliacao", {}).get("qualidade", "-") or "-"
        md.append(f"| {num} | {acao} | {ferr} | {suc} | {qual} |")
    md.append("")

    # Seção de saúde
    md.append("## Saude")
    md.append("")
    md.append(
        f"- **Taxa de sucesso:** {saude.get('taxa_sucesso', hm.get('taxa_sucesso_ferramentas', '?'))}%"
    )
    md.append(
        f"- **Circuit breaker:** {saude.get('circuit_breaker_ativacoes', hm.get('circuit_breaker_ativacoes', 0))} ativacoes"
    )
    md.append(
        f"- **Payload invalido:** {saude.get('payload_invalido', hm.get('validacao_payload_falhas', 0))} falhas"
    )
    qualidade_resumo = saude.get("qualidade_resumo", "")
    if qualidade_resumo:
        md.append(f"- **Qualidade:** {qualidade_resumo}")
    problemas_saude = saude.get("problemas", [])
    if problemas_saude:
        md.append(f"- **Problemas:** {', '.join(str(p) for p in problemas_saude)}")
    md.append("")

    # Seção de performance
    md.append("## Performance")
    md.append("")
    tempo_pct = performance.get("tempo_usado_pct", "?")
    tokens_pct = performance.get("tokens_usado_pct", "?")
    md.append(f"- **Tempo usado:** {tempo_pct}% do limite")
    md.append(f"- **Tokens usados:** {tokens_pct}% do limite")
    tendencia = performance.get("latencia_planejar_tendencia", "?")
    md.append(f"- **Latencia planejar:** tendencia {tendencia}")
    agir_media = performance.get("latencia_agir_media_ms", "?")
    md.append(f"- **Latencia agir:** media {agir_media}ms")
    gargalos = performance.get("gargalos", [])
    if gargalos:
        md.append("- **Gargalos:**")
        for g in gargalos:
            md.append(
                f"  - {g if isinstance(g, str) else json.dumps(g, ensure_ascii=False)}"
            )
    md.append("")

    # Detalhamento por fase (parte da performance)
    fases = perf.get("fases", {})
    if fases:
        md.append("### Detalhamento por Fase")
        md.append("")
        md.append("| Fase | Media | Max | Total | Chamadas |")
        md.append("|------|-------|-----|-------|----------|")
        for fase, d in fases.items():
            md.append(
                f"| {fase} | {d['media_ms']}ms | {d['max_ms']}ms | {d['total_ms']}ms | {d['contagem']}x |"
            )
        md.append("")

    # Seção de conformidade
    md.append("## Conformidade")
    md.append("")
    obrig = conformidade.get("ferramentas_obrigatorias_chamadas", "?")
    pipeline = conformidade.get("pipeline_completo", "?")
    guardrails = conformidade.get("guardrails_ativados", 0)
    md.append(f"- **Ferramentas obrigatorias chamadas:** {obrig}")
    md.append(f"- **Pipeline completo:** {pipeline}")
    md.append(f"- **Guardrails ativados:** {guardrails}")
    violacoes = conformidade.get("violacoes", [])
    if violacoes:
        md.append("- **Violacoes:**")
        for v in violacoes:
            md.append(
                f"  - {v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}"
            )
    md.append("")

    # Seção de anomalias
    md.append("## Anomalias")
    md.append("")
    anomalias_lista = anomalias_dados.get("anomalias", [])
    severidade = anomalias_dados.get("severidade", "?")
    if anomalias_lista:
        md.append(f"**Severidade geral:** {severidade}")
        md.append("")
        for a in anomalias_lista:
            if isinstance(a, str):
                md.append(f"- {a}")
            elif isinstance(a, dict):
                desc = a.get(
                    "descricao", a.get("description", json.dumps(a, ensure_ascii=False))
                )
                md.append(f"- {desc}")
            else:
                md.append(f"- {a}")
    else:
        md.append("Nenhuma anomalia detectada.")
    md.append("")

    # Seção de veredito (conclusão da análise)
    md.append("## Veredito")
    md.append("")
    veredito_texto = veredito_dados.get("veredito", "")
    if veredito_texto:
        md.append(f"> {veredito_texto}")
    else:
        md.append("> Veredito nao disponivel.")
    md.append("")

    # Recomendações
    recomendacoes = veredito_dados.get("recomendacoes", [])
    if recomendacoes:
        md.append("### Recomendacoes")
        md.append("")
        for r in recomendacoes:
            if isinstance(r, str):
                md.append(f"- {r}")
            elif isinstance(r, dict):
                desc = r.get(
                    "descricao",
                    r.get("recomendacao", json.dumps(r, ensure_ascii=False)),
                )
                md.append(f"- {desc}")
            else:
                md.append(f"- {r}")
        md.append("")

    # Junta tudo em uma única string
    return "\n".join(md)


def main():
    """
    Função principal do programa.
    Analisa os argumentos da linha de comando e executa o comando solicitado.
    """
    # Cria o parser principal de argumentos
    parser = argparse.ArgumentParser(description="Runtime do Agente")

    # Adiciona subcomandos (rodar, validar, rastreamento, analisar, replay)
    subparsers = parser.add_subparsers(dest="comando")

    # Subcomando "rodar" - executa um agente
    parser_rodar = subparsers.add_parser("rodar", help="Roda um agente")
    parser_rodar.add_argument(
        "--agente", required=True, help="Caminho para a pasta do agente"
    )
    parser_rodar.add_argument(
        "--entrada", required=True, help="Entrada do agente (ex: alerta de latencia)"
    )
    parser_rodar.add_argument(
        "--modo",
        required=False,
        help="Modo de operacao (task_based, interactive, goal_oriented, autonomous)",
    )
    parser_rodar.add_argument(
        "--evento",
        required=False,
        help="Evento trigger para modo autonomous (ex: alerta_cpu, deploy_falhou)",
    )

    # Subcomando "validar" - valida os contratos do agente
    parser_validar = subparsers.add_parser(
        "validar", help="Valida os contratos do agente"
    )
    parser_validar.add_argument(
        "--agente", required=True, help="Caminho para a pasta do agente"
    )

    # Subcomando "rastreamento" - exibe o rastreamento da última execução
    subparsers.add_parser(
        "rastreamento", help="Exibe o rastreamento da ultima execucao"
    )

    # Subcomando "analisar" - analisa o trace usando um agente analyzer
    parser_analisar = subparsers.add_parser(
        "analisar", help="Analisa o trace da ultima execucao usando um agente analyzer"
    )
    parser_analisar.add_argument(
        "--agente", required=True, help="Caminho para o agente trace-analyzer"
    )
    parser_analisar.add_argument(
        "--trace",
        required=False,
        help="Caminho para o trace.json (default: ultimo trace)",
    )

    # Subcomando "replay" - reexecuta com a mesma entrada da última execução
    parser_replay = subparsers.add_parser(
        "replay", help="Reexecuta com a mesma entrada da ultima execucao"
    )
    parser_replay.add_argument(
        "--agente", required=True, help="Caminho para a pasta do agente"
    )

    # Processa os argumentos fornecidos pelo usuário
    argumentos = parser.parse_args()

    # Executa o comando correspondente
    if argumentos.comando == "rodar":
        rodar(
            caminho_agente=argumentos.agente,
            texto_entrada=argumentos.entrada,
            modo=argumentos.modo,
            evento=argumentos.evento,
        )
    elif argumentos.comando == "validar":
        validar(caminho_agente=argumentos.agente)
    elif argumentos.comando == "rastreamento":
        exibir_rastreamento()
    elif argumentos.comando == "analisar":
        # Define o caminho do arquivo trace (padrão é trace.json na mesma pasta)
        caminho_trace = argumentos.trace or str(Path(__file__).parent / "trace.json")
        caminho_trace = Path(caminho_trace)

        # Verifica se o arquivo de trace existe
        if not caminho_trace.exists():
            print(f"Trace nao encontrado: {caminho_trace}")
            print("Rode um agente primeiro para gerar o trace.")
            return

        # Carrega os dados do trace
        dados_trace = json.loads(caminho_trace.read_text(encoding="utf-8"))

        # Gera um resumo do trace para usar como entrada do analyzer
        entrada_trace = _resumir_trace(dados_trace)

        # Caminho onde será salva a análise
        caminho_analise = str(Path(__file__).parent / "analise.json")

        # Executa o analyzer com o resumo do trace
        rodar(
            caminho_agente=argumentos.agente,
            texto_entrada=entrada_trace,
            saida=caminho_analise,
        )

        # Gera um relatório markdown legível a partir da análise
        caminho_analise_path = Path(caminho_analise)
        if caminho_analise_path.exists():
            dados_analise = json.loads(caminho_analise_path.read_text(encoding="utf-8"))
            relatorio = _gerar_relatorio_md(dados_trace, dados_analise)
            caminho_md = Path(__file__).parent / "analise-agente.md"
            caminho_md.write_text(relatorio, encoding="utf-8")
            print(f"  Relatorio salvo: {caminho_md}")
    elif argumentos.comando == "replay":
        replay(caminho_agente=argumentos.agente)
    else:
        # Se nenhum comando foi passado, exibe a ajuda
        parser.print_help()


# Este bloco verifica se o script está sendo executado diretamente (não importado como módulo)
# Se sim, chama a função main()
if __name__ == "__main__":
    main()
