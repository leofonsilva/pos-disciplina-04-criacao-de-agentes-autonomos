"""
Validador de Agente.

Verifica se os contratos do agente estao completos e consistentes.
"""

from pathlib import Path  # Para manipular caminhos de arquivos

from contratos import carregar_yaml_do_md  # Função que extrai YAML de arquivos .md


def validar(caminho_agente: str) -> bool:
    """
    Valida se os contratos do agente estao completos e consistentes.

    Verifica:
    - Existência de todos os arquivos obrigatórios
    - Consistência entre skills.md e toolbox.md
    - Ferramentas obrigatórias existem
    - Tipo do agente é válido
    - Estrutura básica dos contratos

    Retorna True se válido, False se houver erros.
    """
    # Resolve o caminho absoluto da pasta do agente
    caminho = Path(caminho_agente).resolve()
    pasta_contratos = caminho / "contracts"  # Subpasta com contratos do ciclo
    
    erros = []   # Lista para acumular problemas graves (impedem validação)
    avisos = []  # Lista para acumular problemas leves (recomendações)

    # Cabeçalho da validação
    print(f"\n{'='*60}")
    print(f"  Validando agente: {caminho.name}")
    print(f"{'='*60}\n")

    # 1. Verifica se todos os arquivos obrigatórios existem
    # Cada arquivo tem um nome descritivo e seu caminho correspondente
    arquivos_obrigatorios = {
        "agent.md": caminho / "agent.md",           # Configurações gerais do agente
        "rules.md": caminho / "rules.md",           # Regras e limites
        "skills.md": caminho / "skills.md",         # Definição das ferramentas
        "hooks.md": caminho / "hooks.md",           # Pontos de extensão (logs, alertas)
        "memory.md": caminho / "memory.md",         # Configuração de memória e resumo
        "contracts/loop.md": pasta_contratos / "loop.md",       # Definição do ciclo
        "contracts/planner.md": pasta_contratos / "planner.md", # Contrato do planejador
        "contracts/executor.md": pasta_contratos / "executor.md", # Contrato do executor
        "contracts/toolbox.md": pasta_contratos / "toolbox.md",   # Registro de ferramentas
    }

    # Percorre cada arquivo obrigatório
    for nome, caminho_arquivo in arquivos_obrigatorios.items():
        if caminho_arquivo.exists():
            # Tenta extrair o YAML do arquivo
            yaml_data = carregar_yaml_do_md(caminho_arquivo)
            if not yaml_data:
                erros.append(f"  [ERRO] {nome} existe mas nao contem YAML valido")
            else:
                print(f"  [OK] {nome}")  # Arquivo existe e tem YAML válido
        else:
            erros.append(f"  [ERRO] {nome} nao encontrado")

    # 2. Verifica consistência entre os contratos
    # Carrega cada contrato para análise cruzada
    habilidades = carregar_yaml_do_md(caminho / "skills.md")      # Definição das habilidades
    toolbox = carregar_yaml_do_md(pasta_contratos / "toolbox.md") # Registro de ferramentas
    regras = carregar_yaml_do_md(caminho / "rules.md")            # Regras do agente
    agente = carregar_yaml_do_md(caminho / "agent.md")            # Configuração do agente

    # Extrai os nomes das ferramentas de cada contrato (usa set para eliminar duplicatas)
    nomes_habilidades = {h["nome"] for h in habilidades.get("habilidades", []) if "nome" in h}
    nomes_toolbox = {f["nome"] for f in toolbox.get("ferramentas", []) if "nome" in f}

    # Verifica se ferramentas no toolbox existem em skills.md
    # (toolbox referencia habilidades que devem estar definidas)
    for nome in nomes_toolbox - nomes_habilidades:
        erros.append(f"  [ERRO] ferramenta '{nome}' esta no toolbox.md mas nao em skills.md")

    # Verifica se ferramentas em skills.md estão registradas no toolbox.md
    # (skills define, toolbox registra - gera apenas aviso)
    for nome in nomes_habilidades - nomes_toolbox:
        avisos.append(f"  [AVISO] ferramenta '{nome}' esta em skills.md mas nao no toolbox.md")

    # Verifica se as ferramentas obrigatórias (definidas nas regras) existem em skills.md
    for nome in regras.get("ferramentas_obrigatorias", []):
        if nome not in nomes_habilidades:
            erros.append(f"  [ERRO] ferramenta obrigatoria '{nome}' nao existe em skills.md")

    # Verifica se os limites definidos por ferramenta referem ferramentas existentes
    chamadas = regras.get("limites", {}).get("chamadas_ferramenta", {})
    if isinstance(chamadas, dict):
        for nome in chamadas:
            # Ignora o campo "total" (que não é nome de ferramenta)
            if nome != "total" and nome not in nomes_habilidades:
                avisos.append(f"  [AVISO] limite definido para '{nome}' que nao existe em skills.md")

    # Verifica se o tipo do agente é um valor válido
    tipo = agente.get("tipo", "")
    tipos_validos = {"task_based", "interactive", "goal_oriented", "autonomous"}
    if tipo and tipo not in tipos_validos:
        erros.append(f"  [ERRO] tipo '{tipo}' invalido. Valores: {', '.join(tipos_validos)}")

    # Verifica se o contrato de saída está definido (recomendado)
    contrato_saida = agente.get("contrato_saida", {})
    if not contrato_saida:
        avisos.append("  [AVISO] agent.md nao define contrato_saida")
    elif not contrato_saida.get("campos_obrigatorios"):
        avisos.append("  [AVISO] contrato_saida nao define campos_obrigatorios")

    # 3. Exibe o resultado da validação
    print()
    for aviso in avisos:
        print(aviso)
    for erro in erros:
        print(erro)

    total_erros = len(erros)
    total_avisos = len(avisos)
    
    print(f"\n{'='*60}")
    if total_erros == 0:
        print(f"  Resultado: VALIDO ({total_avisos} avisos)")
    else:
        print(f"  Resultado: INVALIDO ({total_erros} erros, {total_avisos} avisos)")
    print(f"{'='*60}\n")

    # Retorna True apenas se não houver erros (avisos não impedem validação)
    return total_erros == 0
