"""
Validador de Agente.

Verifica se os contratos do agente estao completos e consistentes.
O validador checa se todos os arquivos obrigatórios existem e se as
referências entre eles estão corretas.
"""

from pathlib import Path  # Para trabalhar com caminhos de arquivos

from contratos import carregar_yaml_do_md  # Função que extrai YAML de arquivos .md


def validar(caminho_agente: str) -> bool:
    """
    Valida se os contratos do agente estao completos e consistentes.
    
    Esta função verifica:
    1. Se todos os arquivos obrigatórios existem
    2. Se os YAML dentro deles são válidos
    3. Se as referências entre contratos são consistentes (ex: ferramentas existem)
    
    Parâmetros:
        caminho_agente (str): Caminho para a pasta do agente
    
    Retorna:
        bool: True se o agente é válido, False se houver erros
    """
    # Converte para Path object (caminho absoluto)
    caminho = Path(caminho_agente).resolve()
    
    # Caminho da pasta contracts dentro do agente
    pasta_contratos = caminho / "contracts"
    
    # Listas para acumular erros e avisos
    erros = []
    avisos = []

    # Cabeçalho da validação
    print(f"\n{'='*60}")
    print(f"  Validando agente: {caminho.name}")  # nome da pasta do agente
    print(f"{'='*60}\n")

    # ============================================
    # 1. Verificar existencia dos arquivos obrigatorios
    # ============================================
    # Dicionário mapeando nome descritivo -> caminho do arquivo
    arquivos_obrigatorios = {
        "agent.md": caminho / "agent.md",
        "rules.md": caminho / "rules.md",
        "skills.md": caminho / "skills.md",
        "hooks.md": caminho / "hooks.md",
        "memory.md": caminho / "memory.md",
        "contracts/loop.md": pasta_contratos / "loop.md",
        "contracts/planner.md": pasta_contratos / "planner.md",
        "contracts/executor.md": pasta_contratos / "executor.md",
        "contracts/toolbox.md": pasta_contratos / "toolbox.md",
    }

    # Percorre cada arquivo obrigatório
    for nome, caminho_arquivo in arquivos_obrigatorios.items():
        if caminho_arquivo.exists():
            # Se o arquivo existe, tenta carregar o YAML
            yaml_data = carregar_yaml_do_md(caminho_arquivo)
            if not yaml_data:
                # Arquivo existe mas não tem YAML válido (ou está vazio)
                erros.append(f"  [ERRO] {nome} existe mas nao contem YAML valido")
            else:
                # Tudo certo
                print(f"  [OK] {nome}")
        else:
            # Arquivo obrigatório não encontrado
            erros.append(f"  [ERRO] {nome} nao encontrado")

    # ============================================
    # 2. Verificar consistencia entre contratos
    # ============================================
    
    # Carrega os YAMLs principais para validação cruzada
    habilidades = carregar_yaml_do_md(caminho / "skills.md")      # Lista de habilidades/ferramentas
    toolbox = carregar_yaml_do_md(pasta_contratos / "toolbox.md")  # Registro de ferramentas
    regras = carregar_yaml_do_md(caminho / "rules.md")            # Regras e limites
    agente = carregar_yaml_do_md(caminho / "agent.md")            # Configurações do agente

    # Extrai os nomes das ferramentas de cada arquivo (usando set para evitar duplicatas)
    # Set comprehension: {expressão for item in lista if condição}
    nomes_habilidades = {h["nome"] for h in habilidades.get("habilidades", []) if "nome" in h}
    nomes_toolbox = {f["nome"] for f in toolbox.get("ferramentas", []) if "nome" in f}

    # Verifica: ferramentas no toolbox devem existir em skills
    # nomes_toolbox - nomes_habilidades = ferramentas que estão no toolbox mas NÃO estão em skills
    for nome in nomes_toolbox - nomes_habilidades:
        erros.append(f"  [ERRO] ferramenta '{nome}' esta no toolbox.md mas nao em skills.md")

    # Verifica: ferramentas em skills que não estão no toolbox (apenas aviso, não é erro crítico)
    for nome in nomes_habilidades - nomes_toolbox:
        avisos.append(f"  [AVISO] ferramenta '{nome}' esta em skills.md mas nao no toolbox.md")

    # Verifica: ferramentas obrigatórias (definidas em rules.md) devem existir em skills
    for nome in regras.get("ferramentas_obrigatorias", []):
        if nome not in nomes_habilidades:
            erros.append(f"  [ERRO] ferramenta obrigatoria '{nome}' nao existe em skills.md")

    # Verifica: limites por ferramenta devem referir ferramentas existentes
    chamadas = regras.get("limites", {}).get("chamadas_ferramenta", {})
    if isinstance(chamadas, dict):
        for nome in chamadas:
            # "total" é uma chave especial (limite global), não precisa ser uma ferramenta
            if nome != "total" and nome not in nomes_habilidades:
                avisos.append(f"  [AVISO] limite definido para '{nome}' que nao existe em skills.md")

    # Verifica: tipo do agente deve ser um dos valores válidos
    tipo = agente.get("tipo", "")
    tipos_validos = {"task_based", "interactive", "goal_oriented", "autonomous"}
    if tipo and tipo not in tipos_validos:
        erros.append(f"  [ERRO] tipo '{tipo}' invalido. Valores: {', '.join(tipos_validos)}")

    # Verifica: contrato de saida deve ter campos obrigatórios
    contrato_saida = agente.get("contrato_saida", {})
    if not contrato_saida:
        avisos.append("  [AVISO] agent.md nao define contrato_saida")
    elif not contrato_saida.get("campos_obrigatorios"):
        avisos.append("  [AVISO] contrato_saida nao define campos_obrigatorios")

    # ============================================
    # 3. Exibir resultado final
    # ============================================
    print()
    
    # Exibe todos os avisos encontrados
    for aviso in avisos:
        print(aviso)
    
    # Exibe todos os erros encontrados
    for erro in erros:
        print(erro)

    # Conta total de erros e avisos
    total_erros = len(erros)
    total_avisos = len(avisos)
    
    # Exibe resultado consolidado
    print(f"\n{'='*60}")
    if total_erros == 0:
        print(f"  Resultado: VALIDO ({total_avisos} avisos)")
    else:
        print(f"  Resultado: INVALIDO ({total_erros} erros, {total_avisos} avisos)")
    print(f"{'='*60}\n")

    # Retorna True se não houver erros (apenas avisos é aceitável)
    return total_erros == 0
