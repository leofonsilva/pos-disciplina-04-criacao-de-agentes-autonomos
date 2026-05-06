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

**Arquitetura:**
```
Alerta → Runtime Python → Loop (Perceber → Planejar → Agir → Avaliar)
                            ↓
                    LLM (decisão de próxima ação)
                            ↓
                    Tools (consultar_metricas, buscar_logs, historico_deploys, relatorio_incidente)
                            ↓
                    Contratos (agent.md, skills.md, rules.md, contracts/*.md)
```

**Projeto:** [monitor-agent-v2](module-01-a)

**Tecnologias utilizadas:**
- **Python** - Runtime completo com módulos especializados
- **YAML** - Formato de contratos lidos pelo runtime
- **LLM (Large Language Model)** - Motor de decisão (GPT-4o-mini ou mock)
- **JSON** - Formato de troca de dados entre módulos

**Conceitos abordados:**
- Arquitetura interna do runtime (spec-driven development)
- Mapeamento direto: cada linha de YAML tem uma linha de Python que a lê
- Circuit breaker para validação de respostas da LLM
- Telemetria estruturada com trace_id, auditoria e métricas de saúde
- Validação cruzada de contratos (validador.py)
- Geração automática de ferramentas a partir de skills
- Observabilidade: eventos, tempo por fase, contagem de tokens
- CLI com comandos: rodar, validar, rastreamento, replay, analisar

**Aplicação prática:**
O `module-01-a` revela o "motor" por trás do agente. O runtime é genérico e não sabe sobre latência ou incidentes - ele apenas lê contratos e executa.

Módulos do runtime:
- `contratos.py` - Carrega os 9 arquivos `.md` e monta estado inicial
- `ciclo.py` - Orquestra o loop com circuit breaker
- `planejador.py` - Percepção e chamada à LLM (ou mock)
- `ferramentas.py` - Constrói tools a partir dos skills
- `executor.py` - Valida payload, executa, dispara hooks, avalia
- `telemetria.py` - Registra eventos, mede tempo, conta tokens
- `validador.py` - Valida cruzamento entre contratos

**Comandos executados:**
```bash
pip install -r runtime/requirements.txt
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência no serviço de pagamentos"
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência no serviço de pagamentos" --modo interactive
```

**Arquitetura do Runtime:**
```
main.py (CLI)
    ↓
contratos.py → carrega 9 .md → estado inicial
    ↓
ciclo.py → loop: perceber → planejar → validar → executar → avaliar
    ↓         ↓
planejador.py  executor.py
(chamar_llm)   (validar → executar → avaliar)
    ↓              ↓
ferramentas.py  telemetria.py
(cria tools)    (trace, audit, metrics)
```

**Projeto:** [trace-analyzer](module-01-b)

**Tecnologias utilizadas:**
- **Python** - Runtime compartilhado com análise especializada
- **JSON** - Formato do trace.json para análise estruturada
- **LLM (Large Language Model)** - Motor de diagnóstico do analyzer
- **Markdown** - Saída legível (analise-agente.md)

**Conceitos abordados:**
- Observabilidade em 4 níveis: hooks, KPIs, trace.json, análise automatizada
- Agente que analisa execução de outro agente (meta-análise)
- trace.json com 4 blocos: cabeçalho, etapas, health_metrics, performance_data
- Diagnóstico automatizado: saúde, performance, conformidade, anomalias, veredito
- Rastreabilidade completa: um agente roda, outro analisa, ambos com trace
- Orquestração garantida por regras do planner (execução sequencial)

**Aplicação prática:**
O `trace-analyzer` é um agente do tipo `task_based` que atua como um "agente auditor". Ele lê o `trace.json` gerado por qualquer outro agente e produz um diagnóstico estruturado.

O agente pode:
- Analisar saúde (taxa de sucesso, circuit breaker, qualidade) via `analisar_saude`
- Analisar performance (tempo, tokens, gargalos) via `analisar_performance`
- Verificar conformidade (ferramentas obrigatórias, pipeline) via `analisar_conformidade`
- Detectar anomalias (latência crescente, etapas improdutivas) via `detectar_anomalias`
- Consolidar tudo e gerar recomendações via `gerar_veredito`

Gera dois artefatos: `analise.json` (trace da análise) e `analise-agente.md` (relatório legível).

**Comandos executados:**
```bash
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência"
python runtime/main.py analisar --agente trace-analyzer
```

**Arquitetura da Observabilidade:**
```
Nível 1: Hooks (tempo real)
    ↓
Nível 2: Dashboard KPIs (tempo real)
    ↓
Nível 3: trace.json (post-mortem)
    ↓
Nível 4: trace-analyzer (análise automatizada)
    ↓
         trace-analyzer (task_based)
              ↓
    analisar_saude → analisar_performance → analisar_conformidade → detectar_anomalias → gerar_veredito
              ↓
    Saída: analise.json + analise-agente.md
```