# Pós Disciplina 03 – Criação de agentes autônomos

## Introdução
Pendente...

## Setup Python + Virtual Environment (WSL Ubuntu 24)

### 1. Atualizar o sistema
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Instalar Python e ferramentas necessárias
```bash
sudo apt install python3 python3-pip python3-venv -y
```

### 3. Acessar o diretório do projeto
```bash
cd seu-projeto
```

### 4. Criar o ambiente virtual
```bash
python3 -m venv .venv
```

### 5. Ativar o ambiente virtual
```bash
source .venv/bin/activate
```
Após ativar, o terminal deve mostrar algo assim:

```bash
(.venv) user@machine:~/seu-projeto$
```

### 6. Instalar dependências do projeto (exemplo)
```bash
pip install -r module-01/runtime/requirements.txt
```

### 7. Verificar instalação (opcional)
```bash
python --version
pip list
```

### 8. Desativar o ambiente virtual
```bash
deactivate
```

### Uso no dia a dia
Sempre que voltar ao projeto:
```bash
cd seu-projeto
source .venv/bin/activate
```

### Observações

* O ambiente virtual fica dentro da pasta `.venv/`
* Não deve ser versionado no Git
* Para remover o ambiente, basta deletar a pasta:
```bash
rm -rf .venv
```

## Módulos

### Módulo 01: Introdução aos Agentes Autônomos
**Projeto:** [monitor-agent](module-01)

**Tecnologias utilizadas:**
- **Python** - Linguagem principal para o runtime do agente
- **YAML** - Formato de definição de contratos e configurações do agente
- **LLM (Large Language Model)** - Motor de decisão e planejamento do agente

**Conceitos abordados:**
- Definição de agentes baseada em contratos (contract-based agents)
- Estrutura de 9 arquivos de configuração: identidade, ciclo, decisão, capacidades, ferramentas, execução, limites, observabilidade e memória
- Separação entre habilidades (skills) e ferramentas disponíveis (toolbox)
- Geração automática de implementações mock a partir de contratos
- Ciclo de vida do agente: perceber → planejar → agir → avaliar
- Observabilidade com hooks em pontos críticos da execução
- Gestão de memória curta e resumo final

**Aplicação prática:**
O `monitor-agent` é um agente do tipo `task_based` especializado em monitoramento e diagnóstico de incidentes de produção. Ele recebe um alerta como entrada e executa um ciclo autônomo para investigar o problema.

O agente pode:
- Consultar métricas de latência, vazão e taxa de erro (`consultar_metricas`)
- Buscar logs estruturados em janelas de tempo (`buscar_logs`)
- Verificar histórico de deploys recentes (`historico_deploys`)
- Abrir incidente formal com diagnóstico e recomendação (`relatorio_incidente`)

O runtime lê os arquivos de configuração (`.md` e `.yaml`) e orquestra a execução, delegando as decisões de planejamento à LLM e executando as ferramentas com implementações mock realistas.
