"""
Engine de Benchmark — roda um dataset contra uma arquitetura e coleta metricas.

Uso (via main.py):
  python main.py benchmark --agente ../monitor-agent --suite ../evals/suites/monitor-agent.yaml
  python main.py benchmark --agente ../monitor-agent --suite ../evals/suites/monitor-agent.yaml --arquitetura react
  python main.py benchmark --agente ../monitor-agent --suite ../evals/suites/monitor-agent.yaml --arquitetura plan_execute
  python main.py benchmark --agente ../monitor-agent --suite ../evals/suites/monitor-agent.yaml --arquitetura reflect
"""

import json  # Para manipular arquivos JSON
import time  # Para medir tempo de execução
from pathlib import Path  # Para manipular caminhos de arquivos de forma segura

import yaml  # Para ler arquivos YAML

from ciclo import rodar  # Importa a função rodar do módulo ciclo


def _carregar_suite(caminho_suite: Path) -> dict:
    """Carrega a eval suite (YAML)."""
    texto = caminho_suite.read_text(encoding="utf-8")  # Lê o arquivo como texto
    return yaml.safe_load(texto)  # Converte o YAML para dicionário Python


def _carregar_dataset(caminho_suite: Path, suite: dict) -> list:
    """Carrega o dataset referenciado pela suite."""
    # Obtém o caminho do dataset (relativo à pasta da suite)
    caminho_dataset = caminho_suite.parent / suite["dataset"]
    # Lê e converte o JSON para lista Python
    return json.loads(caminho_dataset.read_text(encoding="utf-8"))


def _extrair_metricas_trace(trace: dict, caso: dict) -> dict:
    """Extrai metricas de um trace individual."""
    etapas = trace.get("historico", [])  # Lista de etapas executadas (vazia se não existir)
    tokens = trace.get("tokens_consumidos", {})  # Dicionário de consumo de tokens
    concluido = trace.get("concluido", False)  # Flag de conclusão do agente
    resultado = trace.get("resultado", "")  # Resultado final do processamento

    # Verifica se concluiu com sucesso (não foi encerrado por limite/erro)
    sucesso = concluido and "encerrado" not in resultado

    # Conjunto para armazenar ferramentas chamadas (usando set para evitar duplicatas)
    ferramentas_chamadas = set()
    # Dicionário para contar qualidade das etapas (completa, parcial, falha)
    qualidades = {"completa": 0, "parcial": 0, "falha": 0}
    
    for etapa in etapas:
        plano = etapa.get("plano", {})  # Extrai o plano da etapa
        nome = plano.get("nome_ferramenta")  # Nome da ferramenta chamada
        if nome:
            ferramentas_chamadas.add(nome)  # Adiciona ao conjunto
        qual = etapa.get("avaliacao", {}).get("qualidade", "")  # Qualidade da execução
        if qual in qualidades:
            qualidades[qual] += 1  # Incrementa o contador

    # Calcula cobertura de ferramentas esperadas (quantas esperadas vs quantas usadas)
    esperadas = set(caso.get("ferramentas_esperadas", []))  # Ferramentas que deveriam ser usadas
    # Percentual = (usadas ∩ esperadas) / (esperadas) * 100
    cobertura = len(ferramentas_chamadas & esperadas) / len(esperadas) * 100 if esperadas else 100

    return {
        "caso_id": caso["id"],  # Identificador do cenário
        "concluido": sucesso,  # Se completou com sucesso
        "etapas": len(etapas),  # Número total de etapas executadas
        "tokens_total": tokens.get("total", 0),  # Tokens totais consumidos
        "tokens_prompt": tokens.get("prompt", 0),  # Tokens usados no planejamento
        "ferramentas_chamadas": sorted(ferramentas_chamadas),  # Lista ordenada das ferramentas
        "cobertura_ferramentas": round(cobertura, 1),  # Cobertura com 1 casa decimal
        "qualidades": qualidades,  # Contagem de qualidades das etapas
        "reflexoes": trace.get("reflexoes_feitas", 0),  # Número de reflexões realizadas
    }


def rodar_benchmark(caminho_agente: str, caminho_suite: str, arquitetura: str = None) -> dict:
    """Roda todos os cenarios do dataset e coleta metricas agregadas."""
    # Converte strings para Path objects e resolve caminhos absolutos
    caminho_agente = Path(caminho_agente).resolve()
    caminho_suite = Path(caminho_suite).resolve()

    # Carrega a suite e o dataset
    suite = _carregar_suite(caminho_suite)
    dataset = _carregar_dataset(caminho_suite, suite)
    nome_arquitetura = arquitetura or "padrao"  # Usa "padrao" se nenhuma arquitetura for especificada

    # Cabeçalho informativo
    print(f"\n{'='*60}")
    print(f"  BENCHMARK")
    print(f"  Agente: {caminho_agente.name}")
    print(f"  Arquitetura: {nome_arquitetura}")
    print(f"  Dataset: {len(dataset)} cenarios")
    print(f"  Suite: {caminho_suite.name}")
    print(f"{'='*60}\n")

    resultados = []  # Lista para armazenar métricas de cada cenário
    inicio_total = time.time()  # Marca o início do benchmark

    # Itera sobre cada cenário do dataset (enumerate começa contando de 1)
    for i, caso in enumerate(dataset, 1):
        print(f"\n{'─'*40}")
        print(f"  Cenario {i}/{len(dataset)}: {caso['id']}")
        print(f"  Entrada: {caso['entrada'][:60]}...")  # Mostra apenas os 60 primeiros caracteres
        print(f"{'─'*40}")

        try:
            # Cria um arquivo temporário para salvar o trace
            saida_temp = str(Path(__file__).parent / f"_bench_{caso['id']}.json")
            
            # Executa o agente com os parâmetros fornecidos
            estado = rodar(
                caminho_agente=str(caminho_agente),
                texto_entrada=caso["entrada"],
                arquitetura=arquitetura,
                saida=saida_temp,
            )
            
            # Extrai as métricas a partir do trace gerado
            metricas = _extrair_metricas_trace(estado, caso)
        except Exception as e:
            print(f"  [benchmark] erro no cenario {caso['id']}: {e}")
            # Se houver erro, cria métricas indicando falha
            metricas = {
                "caso_id": caso["id"],
                "concluido": False,
                "etapas": 0,
                "tokens_total": 0,
                "tokens_prompt": 0,
                "ferramentas_chamadas": [],
                "cobertura_ferramentas": 0,
                "qualidades": {"completa": 0, "parcial": 0, "falha": 0},
                "reflexoes": 0,
            }

        resultados.append(metricas)

        # Remove o arquivo temporário (missing_ok=True não lança erro se não existir)
        Path(saida_temp).unlink(missing_ok=True)

    tempo_total = round(time.time() - inicio_total, 2)  # Tempo total em segundos

    # --- Agregar métricas (calcular médias e totais) ---
    total = len(resultados)
    concluidos = sum(1 for r in resultados if r["concluido"])  # Conta quantos concluíram
    
    agregado = {
        "arquitetura": nome_arquitetura,
        "agente": caminho_agente.name,
        "cenarios_total": total,
        "taxa_conclusao": round(concluidos / total * 100, 1) if total else 0,
        "media_etapas": round(sum(r["etapas"] for r in resultados) / total, 1) if total else 0,
        "media_tokens": round(sum(r["tokens_total"] for r in resultados) / total, 0) if total else 0,
        "tokens_planejamento": round(sum(r["tokens_prompt"] for r in resultados) / total, 0) if total else 0,
        "media_tempo_segundos": round(tempo_total / total, 1) if total else 0,
        "cobertura_ferramentas": round(sum(r["cobertura_ferramentas"] for r in resultados) / total, 1) if total else 0,
        "reflexoes_total": sum(r["reflexoes"] for r in resultados),
        "tempo_total_segundos": tempo_total,
        "resultados_por_cenario": resultados,
    }

    # Verificar se as métricas atendem aos limiares definidos na suite
    limiares = suite.get("limiares", {})  # Pega os limiares da suite (ou dicionário vazio)
    violacoes = []  # Lista para armazenar limiares violados
    for metrica, limiar in limiares.items():
        valor = agregado.get(metrica, 0)  # Pega o valor da métrica
        if valor < limiar:  # Se for menor que o limiar, registra violação
            violacoes.append(f"{metrica}: {valor} < {limiar}")
    agregado["limiares"] = limiares
    agregado["violacoes"] = violacoes

    # Exibir resumo dos resultados
    print(f"\n{'='*60}")
    print(f"  RESULTADO — {nome_arquitetura}")
    print(f"{'='*60}")
    print(f"  Taxa de conclusao:       {agregado['taxa_conclusao']}%")
    print(f"  Media de etapas:         {agregado['media_etapas']}")
    print(f"  Media de tokens:         {agregado['media_tokens']:.0f}")
    print(f"  Tokens planejamento:     {agregado['tokens_planejamento']:.0f}")
    print(f"  Cobertura ferramentas:   {agregado['cobertura_ferramentas']}%")
    print(f"  Reflexoes:               {agregado['reflexoes_total']}")
    print(f"  Tempo total:             {agregado['tempo_total_segundos']}s")
    
    if violacoes:
        print(f"  VIOLACOES:")
        for v in violacoes:
            print(f"    ✗ {v}")
    else:
        print(f"  Limiares:                todos aprovados ✓")
    print(f"{'='*60}\n")

    return agregado


def gerar_relatorio_comparativo(resultados: list, caminho_saida: str):
    """Gera relatorio markdown comparando varias arquiteturas."""
    md = []  # Lista para acumular linhas do markdown
    md.append("# Benchmark Comparativo de Arquiteturas")
    md.append("")

    # Verifica se há resultados
    if not resultados:
        md.append("Nenhum resultado disponivel.")
        Path(caminho_saida).write_text("\n".join(md), encoding="utf-8")
        return

    # Cabeçalho geral
    agente = resultados[0].get("agente", "?")
    md.append(f"**Agente:** {agente}")
    md.append(f"**Cenarios:** {resultados[0].get('cenarios_total', '?')}")
    md.append("")

    # Construção da tabela comparativa
    md.append("## Comparativo")
    md.append("")
    md.append("| Metrica | " + " | ".join(r["arquitetura"] for r in resultados) + " |")
    md.append("|" + "---|" * (len(resultados) + 1))  # Linha separadora da tabela

    # Métricas que serão exibidas na tabela
    metricas_exibir = [
        ("Taxa conclusao", "taxa_conclusao", "%"),
        ("Media etapas", "media_etapas", ""),
        ("Media tokens", "media_tokens", ""),
        ("Tokens planejamento", "tokens_planejamento", ""),
        ("Cobertura ferramentas", "cobertura_ferramentas", "%"),
        ("Reflexoes", "reflexoes_total", ""),
        ("Tempo total", "tempo_total_segundos", "s"),
    ]

    # Preenche cada linha da tabela
    for nome, chave, sufixo in metricas_exibir:
        valores = []
        nums = [r.get(chave, 0) for r in resultados]  # Lista de valores das arquiteturas
        
        # Determina qual é o melhor valor (menor ou maior dependendo da métrica)
        melhor = None
        # Para essas métricas, menor é melhor
        if chave in ("media_etapas", "media_tokens", "tokens_planejamento", "tempo_total_segundos", "reflexoes_total"):
            melhor = min(nums) if any(n > 0 for n in nums) else None
        else:  # Para as demais (ex: taxa_conclusao, cobertura), maior é melhor
            melhor = max(nums)

        for r in resultados:
            val = r.get(chave, 0)
            txt = f"{val}{sufixo}"
            # Se for o melhor valor e houver mais de uma arquitetura, destaca em negrito
            if val == melhor and len(resultados) > 1:
                txt = f"**{txt}**"
            valores.append(txt)
        md.append(f"| {nome} | " + " | ".join(valores) + " |")

    md.append("")

    # Seção de violações de limiares
    md.append("## Violacoes de Limiares")
    md.append("")
    alguma_violacao = False
    for r in resultados:
        violacoes = r.get("violacoes", [])
        if violacoes:
            alguma_violacao = True
            md.append(f"**{r['arquitetura']}:**")
            for v in violacoes:
                md.append(f"- ✗ {v}")
            md.append("")
    if not alguma_violacao:
        md.append("Nenhuma violacao detectada em nenhuma arquitetura.")
        md.append("")

    # Veredito final (comparação entre arquiteturas)
    md.append("## Veredito")
    md.append("")

    if len(resultados) > 1:
        # Encontra a melhor arquitetura para cada métrica
        mais_eficiente = min(resultados, key=lambda r: r.get("media_tokens", float("inf")))  # Menos tokens
        mais_completo = max(resultados, key=lambda r: r.get("cobertura_ferramentas", 0))  # Maior cobertura
        mais_rapido = min(resultados, key=lambda r: r.get("tempo_total_segundos", float("inf")))  # Menos tempo

        md.append(f"- **Mais eficiente (tokens):** {mais_eficiente['arquitetura']}")
        md.append(f"- **Maior cobertura:** {mais_completo['arquitetura']}")
        md.append(f"- **Mais rapido:** {mais_rapido['arquitetura']}")
    md.append("")

    # Salva o relatório no arquivo especificado
    Path(caminho_saida).write_text("\n".join(md), encoding="utf-8")
    print(f"  Relatorio salvo: {caminho_saida}")
