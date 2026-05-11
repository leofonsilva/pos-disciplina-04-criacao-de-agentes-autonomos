"""
Tool Selection Eval — mede se o agente escolhe a ferramenta certa.

Pra cada caso do dataset, o eval:
1. Monta o contexto (percepcao) simulando a etapa descrita
2. Chama o planejador (LLM ou mock) pedindo a proxima acao
3. Compara a tool escolhida com a esperada
4. Compara os argumentos com os esperados
5. Verifica se chamou tool que nao deveria

Metricas:
  - tool_selection_accuracy: % de acertos na tool
  - argument_accuracy: % de argumentos corretos
  - unnecessary_calls_rate: % de chamadas indevidas
  - wrong_tool_rate: % de tools erradas
"""

import json  # Para manipular arquivos JSON (dataset)
from pathlib import Path  # Para manipular caminhos de arquivos

import yaml  # Para ler arquivos YAML (eval suite)

from contratos import carregar_contratos  # Carrega os contratos do agente
from planejador import chamar_llm  # Importa a funcao que chama o planejador


def _carregar_suite(caminho_suite: Path) -> dict:
    """Carrega a eval suite de tool selection (YAML)."""
    texto = caminho_suite.read_text(encoding="utf-8")
    return yaml.safe_load(texto)


def _carregar_dataset(caminho_suite: Path, suite: dict) -> list:
    """Carrega o dataset referenciado pela suite de tool selection."""
    caminho_dataset = caminho_suite.parent / suite["dataset"]
    return json.loads(caminho_dataset.read_text(encoding="utf-8"))


def _montar_percepcao_caso(caso: dict) -> str:
    """
    Monta string de percepcao simulando o contexto do caso.

    Simula o que o agente "ve" antes de decidir qual ferramenta chamar.
    """
    partes = [
        f"Alerta: {caso['entrada']}",
        f"Modo: task_based",
        f"Etapas realizadas: {caso.get('etapa', 1) - 1}/10",
    ]
    
    contexto = caso.get("contexto", "")
    if contexto:
        partes.append(f"Contexto: {contexto}")
    
    ferramentas_ja_usadas = caso.get("ferramentas_ja_usadas", [])
    if ferramentas_ja_usadas:
        partes.append(f"Ferramentas ja utilizadas: {', '.join(ferramentas_ja_usadas)}")
    
    return "\n".join(partes)


def _avaliar_caso(caso: dict, plano: dict) -> dict:
    """
    Avalia a resposta do planejador contra o caso esperado.

    Retorna:
    - tool_correta: se a ferramenta escolhida eh a esperada
    - arg_accuracy: percentual de argumentos corretos
    - chamada_desnecessaria: se chamou uma ferramenta proibida
    """
    tool_escolhida = plano.get("nome_ferramenta", "")
    tool_esperada = caso.get("tool_esperada", "")
    args_escolhidos = plano.get("argumentos_ferramenta", {}) or {}
    args_esperados = caso.get("argumentos_esperados", {})
    tools_proibidas = caso.get("tools_nao_esperadas", [])

    # Verifica se a ferramenta escolhida eh a correta
    tool_correta = tool_escolhida == tool_esperada

    # Calcula acuracia dos argumentos (comparacao flexivel: contem o valor esperado)
    args_corretos = 0
    args_total = len(args_esperados)
    for chave, valor_esperado in args_esperados.items():
        valor_recebido = args_escolhidos.get(chave, "")
        # Comparacao case-insensitive: o valor recebido contem o valor esperado
        if str(valor_esperado).lower() in str(valor_recebido).lower():
            args_corretos += 1

    arg_accuracy = args_corretos / args_total if args_total > 0 else 1.0

    # Verifica chamada desnecessaria (ferramenta proibida)
    chamada_desnecessaria = tool_escolhida in tools_proibidas

    return {
        "caso_id": caso["id"],
        "tool_esperada": tool_esperada,
        "tool_escolhida": tool_escolhida,
        "tool_correta": tool_correta,
        "arg_accuracy": round(arg_accuracy, 2),
        "chamada_desnecessaria": chamada_desnecessaria,
        "justificativa_esperada": caso.get("justificativa", ""),
    }


def rodar_tool_eval(caminho_agente: str, caminho_suite: str, arquitetura: str = None) -> dict:
    """
    Roda avaliacao de tool selection contra dataset.

    Para cada caso do dataset, monta a percepcao, chama o planejador,
    e avalia se a ferramenta e os argumentos estao corretos.
    """
    # Resolve caminhos absolutos
    caminho_agente = Path(caminho_agente).resolve()
    caminho_suite = Path(caminho_suite).resolve()

    # Carrega suite, dataset e contratos
    suite = _carregar_suite(caminho_suite)
    dataset = _carregar_dataset(caminho_suite, suite)
    contratos = carregar_contratos(caminho_agente, arquitetura=arquitetura)
    nome_arq = arquitetura or "padrao"

    # Cabecalho informativo
    print(f"\n{'='*60}")
    print(f"  TOOL SELECTION EVAL")
    print(f"  Agente: {caminho_agente.name}")
    print(f"  Arquitetura: {nome_arq}")
    print(f"  Dataset: {len(dataset)} casos")
    print(f"{'='*60}\n")

    resultados = []

    # Itera sobre cada caso do dataset
    for i, caso in enumerate(dataset, 1):
        # Monta a percepcao simulada
        percepcao = _montar_percepcao_caso(caso)
        
        # Chama o planejador (LLM ou mock) para decidir a proxima acao
        plano, _ = chamar_llm(percepcao, contratos, [])
        
        # Avalia a resposta
        avaliacao = _avaliar_caso(caso, plano)
        resultados.append(avaliacao)

        # Exibe resultado individual (✓ = acertou, ✗ = errou)
        status = "✓" if avaliacao["tool_correta"] else "✗"
        print(f"  {status} {caso['id']}: esperada={caso['tool_esperada']}, escolhida={avaliacao['tool_escolhida']}, args={avaliacao['arg_accuracy']}")

    # --- Agrega metricas ---
    total = len(resultados)
    tool_corretas = sum(1 for r in resultados if r["tool_correta"])
    desnecessarias = sum(1 for r in resultados if r["chamada_desnecessaria"])
    erradas = sum(1 for r in resultados if not r["tool_correta"])
    media_arg_accuracy = sum(r["arg_accuracy"] for r in resultados) / total if total else 0

    agregado = {
        "arquitetura": nome_arq,
        "agente": caminho_agente.name,
        "total_casos": total,
        "tool_selection_accuracy": round(tool_corretas / total, 3) if total else 0,
        "argument_accuracy": round(media_arg_accuracy, 3),
        "unnecessary_calls_rate": round(desnecessarias / total, 3) if total else 0,
        "wrong_tool_rate": round(erradas / total, 3) if total else 0,
        "resultados_por_caso": resultados,
    }

    # Verifica limiares definidos na suite
    limiares = suite.get("limiares", {})
    violacoes = []
    for metrica, limiar in limiares.items():
        valor = agregado.get(metrica, 0)
        # Para taxas de erro (unnecessary_calls_rate, wrong_tool_rate): menor eh melhor
        if metrica in ("unnecessary_calls_rate", "wrong_tool_rate"):
            if valor > limiar:
                violacoes.append(f"{metrica}: {valor} > {limiar}")
        else:
            # Para metricas de acerto (accuracy): maior eh melhor
            if valor < limiar:
                violacoes.append(f"{metrica}: {valor} < {limiar}")
    agregado["limiares"] = limiares
    agregado["violacoes"] = violacoes

    # Exibe resumo dos resultados
    print(f"\n{'='*60}")
    print(f"  RESULTADO — {nome_arq}")
    print(f"{'='*60}")
    print(f"  Tool selection accuracy:  {agregado['tool_selection_accuracy']*100:.1f}%")
    print(f"  Argument accuracy:        {agregado['argument_accuracy']*100:.1f}%")
    print(f"  Unnecessary calls rate:   {agregado['unnecessary_calls_rate']*100:.1f}%")
    print(f"  Wrong tool rate:          {agregado['wrong_tool_rate']*100:.1f}%")
    
    if violacoes:
        print(f"  VIOLACOES:")
        for v in violacoes:
            print(f"    ✗ {v}")
    else:
        print(f"  Limiares:                 todos aprovados ✓")
    print(f"{'='*60}\n")

    return agregado


def gerar_relatorio_tool_eval(resultados: list, caminho_saida: str):
    """
    Gera relatorio markdown com resultados de tool selection eval.

    Compara diferentes arquiteturas (padrao, react, plan_execute, reflect)
    em metricas como acuracia de tool selection, acuracia de argumentos,
    taxa de chamadas desnecessarias e taxa de ferramentas erradas.
    """
    md = []
    md.append("# Tool Selection Eval — Relatorio")
    md.append("")

    if not resultados:
        md.append("Nenhum resultado.")
        Path(caminho_saida).write_text("\n".join(md), encoding="utf-8")
        return

    agente = resultados[0].get("agente", "?")
    md.append(f"**Agente:** {agente}")
    md.append(f"**Casos:** {resultados[0].get('total_casos', '?')}")
    md.append("")

    # Tabela comparativa por arquitetura
    md.append("## Comparativo por Arquitetura")
    md.append("")
    md.append("| Metrica | " + " | ".join(r["arquitetura"] for r in resultados) + " |")
    md.append("|" + "---|" * (len(resultados) + 1))

    metricas = [
        ("Tool selection accuracy", "tool_selection_accuracy", True),  # maior é melhor
        ("Argument accuracy", "argument_accuracy", True),               # maior é melhor
        ("Unnecessary calls rate", "unnecessary_calls_rate", False),    # menor é melhor
        ("Wrong tool rate", "wrong_tool_rate", False),                  # menor é melhor
    ]

    for nome, chave, maior_melhor in metricas:
        nums = [r.get(chave, 0) for r in resultados]
        melhor = max(nums) if maior_melhor else min(nums)
        valores = []
        for r in resultados:
            val = r.get(chave, 0)
            txt = f"{val*100:.1f}%"
            if val == melhor and len(resultados) > 1:
                txt = f"**{txt}**"  # Destaca o melhor resultado
            valores.append(txt)
        md.append(f"| {nome} | " + " | ".join(valores) + " |")
    md.append("")

    # Detalhamento por caso (usando o primeiro resultado como referencia)
    md.append("## Detalhamento por Caso")
    md.append("")
    md.append("| Caso | Tool Esperada | Tool Escolhida | Acertou | Args |")
    md.append("|------|--------------|----------------|---------|------|")
    for caso in resultados[0].get("resultados_por_caso", []):
        acertou = "✓" if caso["tool_correta"] else "✗"
        md.append(f"| {caso['caso_id']} | {caso['tool_esperada']} | {caso['tool_escolhida']} | {acertou} | {caso['arg_accuracy']*100:.0f}% |")
    md.append("")

    # Violacoes de limiares
    md.append("## Violacoes")
    md.append("")
    alguma = False
    for r in resultados:
        if r.get("violacoes"):
            alguma = True
            md.append(f"**{r['arquitetura']}:** " + ", ".join(r["violacoes"]))
    if not alguma:
        md.append("Nenhuma violacao.")
    md.append("")

    # Salva o relatorio
    Path(caminho_saida).write_text("\n".join(md), encoding="utf-8")
    print(f"  Relatorio salvo: {caminho_saida}")
