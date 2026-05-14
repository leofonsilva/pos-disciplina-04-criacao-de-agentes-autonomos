# Pós Disciplina 03 – Criação de agentes autônomos

## Introdução
Pendente...

## Setup Python + Virtual Environment (WSL Ubuntu 24)

1. Atualizar o sistema
```bash
sudo apt update && sudo apt upgrade -y
```

2. Instalar Python e ferramentas necessárias
```bash
sudo apt install python3 python3-pip python3-venv -y
```

3. Acessar o diretório do projeto
```bash
cd <<disciplina>>
```

4. Criar o ambiente virtual
```bash
python3 -m venv .venv
```

5. Ativar o ambiente virtual
```bash
source .venv/bin/activate
```
- Após ativar, o terminal deve mostrar algo assim:
```bash
(.venv) user@machine:~/seu-projeto$
```

6. Instalar dependências do projeto (exemplo)
```bash
pip install -r runtime/requirements.txt
```

7. Verificar instalação (opcional)
```bash
python --version
pip list
```

8. Desativar o ambiente virtual
```bash
deactivate
```

9. Uso no dia a dia, sempre que voltar ao projeto:
```bash
cd <<disciplina>>
source .venv/bin/activate
cd <<modulo>>
```

10. Observações

* O ambiente virtual fica dentro da pasta `.venv/`
* Não deve ser versionado no Git
* Para remover o ambiente, basta deletar a pasta:
```bash
rm -rf .venv
```

## Módulos

### Módulo 01: Introdução aos Agentes Autônomos

#### **Projeto:** [monitor-agent](module-01)

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

#### **Projeto:** [monitor-agent-v2](module-01-a)

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

#### **Projeto:** [trace-analyzer](module-01-b)

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

#### **Projeto:** [agent-types](module-01-c)

**Tecnologias utilizadas:**
- **Python** - Runtime genérico para múltiplos tipos de agentes
- **LLM (Large Language Model)** - Motor adaptável conforme o modo
- **YAML** - Contratos específicos por tipo de agente
- **JSON** - Formato de entrada/saída e traces

**Conceitos abordados:**
- 4 tipos de agentes: `task_based`, `interactive`, `goal_oriented`, `autonomous`
- Contract-driven development: iterar sobre especificação, não código
- Mesmo runtime, comportamentos diferentes via flag `--modo`
- Decomposição de objetivos amplos em `goal_oriented`
- Confirmação humana para ações sensíveis em modo `autonomous`
- Validação cruzada antes da execução (`validar`)
- 8 projetos de portfólio com diferentes domínios

**Aplicação prática:**
O `module-01-c` demonstra como o mesmo runtime suporta diferentes comportamentos através da flag `--modo`:

- **`monitor-agent` (task_based)**: Recebe alerta e entrega relatório diretamente
- **`monitor-agent` (interactive)**: Faz perguntas para remover ambiguidades antes de agir
- **`backlog-decomposer` (goal_oriented)**: Decompõe objetivo em épicos → stories → critérios → riscos → backlog
- **`monitor-agent` (autonomous)**: Responde a eventos com limites rígidos e confirmação humana

O `backlog-decomposer` possui 6 skills encadeadas: `analisar_objetivo` → `gerar_epicos` → `detalhar_stories` → `avaliar_riscos` → `gerar_perguntas` → `montar_backlog`.

**Comandos executados:**
```bash
python runtime/main.py rodar --agente monitor-agent --entrada "Algo estranho no sistema" --modo interactive
python runtime/main.py rodar --agente backlog-decomposer --entrada "Permitir que novos usuários completem cadastro sem suporte humano"
python runtime/main.py rodar --agente monitor-agent --entrada "Cpu em 95 por cento no serviço de pagamentos" --modo autonomous --evento alerta_cpu
python runtime/main.py validar --agente monitor-agent
```

**Arquitetura dos Tipos de Agente:**
```
Mesmo Runtime Python
       ↓
Flag --modo altera prompt do sistema:
       ↓
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ task_based   │ interactive  │ goal_oriented│ autonomous  │
│ tarefa clara │ pergunta    │ decompõe    │ evento/      │
│ execução     │ antes de     │ objetivo em  │ trigger com  │
│ direta       │ agir         │ sub-objetivos│ limites rígidos│
└──────────────┴──────────────┴──────────────┴──────────────┘
       ↓
Exemplos:
- monitor-agent (task_based): alerta → métricas → logs → deploy → relatório
- backlog-decomposer (goal_oriented): objetivo → épicos → stories → backlog
- monitor-agent (autonomous): evento → ação → confirmação humana
```
**Projetos de Portfólio Sugeridos:**
1. Incident Triage Report Agent (SRE/DevOps)
2. PR Review Gate Agent (Engenharia de Software)
3. API Contract Draft Agent (Backend Design)
4. Runbook Generator Agent (Platform Engineering)
5. Backlog Decomposer Agent (Product + Engineering)
6. Data Quality Auditor Agent (Data Engineering)
7. Compliance Checklist Agent (Governança)
8. Onboarding Guide Agent (Dev Productivity)

### Módulo 02: Raciocínio e Tomada de Decisão em Agentes

#### **Projeto:** [cognitive-architecture](module-02)

**Tecnologias utilizadas:**
- **Python** - Runtime com suporte a múltiplas arquiteturas cognitivas
- **LLM (Large Language Model)** - Motor com raciocínio estruturado
- **YAML** - Contratos de arquitetura (`architectures/<nome>/`)
- **JSON** - Formato de saída com campo `raciocínio`

**Conceitos abordados:**
- Arquiteturas cognitivas como contrato (ReAct, Plan-Execute, Reflection)
- Padrão Open-Closed: trocar arquitetura sem mexer no runtime
- ReAct (Reason + Act): raciocínio explícito antes de cada ação
- Inversão de dependência: runtime conhece o slot, não a arquitetura
- `formato_saida` dinâmico lido do contrato da arquitetura
- Sobrescrita de `planner.md` e `executor.md` via flag `--arquitetura`
- Raciocínio auditável no `trace.json`

**Aplicação prática:**
O `module-02` introduz o conceito de **arquitetura cognitiva como contrato**. O agente e o runtime não mudam - o que muda é a pasta `architectures/<nome>/` carregada em tempo de execução.

A arquitetura **ReAct** adiciona um campo `raciocínio` obrigatório ao formato de saída:
- O agente deve explicar: (1) o que já sei, (2) o que falta, (3) por que escolhi esta ação
- O raciocínio aparece no terminal e é gravado no `trace.json`
- Permite auditoria: você lê o trace e entende **por que** o agente decidiu cada passo

Para trocar de arquitetura, basta criar `architectures/plan_execute/planner.md` e rodar com `--arquitetura plan_execute`.

**Comandos executados:**
```bash
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência no checkout" --arquitetura react
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência no checkout"
```

**Arquitetura ReAct:**
```
Runtime Python (genérico)
       ↓
Flag --arquitetura react
       ↓
contratos.py carrega:
  - 9 contratos do agente (monitor-agent/)
  - sobrescreve com architectures/react/planner.md + executor.md
       ↓
ciclo.py → loop com raciocínio
       ↓
plano JSON:
{
  "raciocínio": "Já coletei: nada ainda. Próximo passo lógico: chamar consultar_metricas",
  "proxima_acao": "CHAMAR_FERRAMENTA",
  "nome_ferramenta": "consultar_metricas",
  ...
}
       ↓
trace.json → campo "arquitetura": "react" + raciocínio em cada etapa
```
**Arquiteturas Disponíveis:**
- **ReAct**: Reason + Act (raciocínio antes de agir)
- **Plan-Execute**: Planeja tudo, depois executa (aula 8)
- **Reflection**: Auto-crítica após cada ação (aula 8)

#### **Projeto:** [plan-execute-and-reflection](module-02-a)

**Tecnologias utilizadas:**
- **Python** - Runtime com suporte a múltiplas arquiteturas cognitivas
- **LLM (Large Language Model)** - Planejamento único (Plan-Execute) e crítica (Reflection)
- **YAML** - Contratos de arquitetura (`plan_execute/`, `reflect/`)
- **JSON** - Formato de saída com plano completo e crítica estruturada

**Conceitos abordados:**
- **Plan-Execute**: Uma chamada à LLM gera plano completo, execução determinística com tokens=0 nas etapas seguintes
- **Reflection**: Fase de crítica antes de finalizar, com auto-correção baseada em feedback
- `critic.md`: Novo contrato definindo critérios, limiar de aprovação e formato de crítica
- Fase REFLEXÃO no loop: rejeita → corrige → aprova (até `max_reflexoes`)
- Open-Closed Principle: novas arquiteturas sem mexer no runtime
- Detecção por sinais: `modo_execucao: plan_execute` e presença de `critic.md`

**Aplicação prática:**
O `module-02-a` expande o slot de arquiteturas com duas novas opções:

- **Plan-Execute**: LLM gera todos os passos na primeira etapa (`plano_completo`). O runtime executa sequencialmente sem novas chamadas à LLM. Ideal quando o pipeline é determinístico e tokens importam.

- **Reflection**: Antes de `FINALIZAR`, o agente submete o resultado ao crítico. Se nota < `limiar_aprovacao` (70), recebe feedback e corrige (até `max_reflexoes: 2`). Garante qualidade e completude do output.

Fluxo típico Reflection (mock):
```
Etapa 1-3: consultar_metricas → buscar_logs → relatorio_incidente → FINALIZAR
   [reflexão] rejeitado. nota=55/100
     problemas: evidências não cruzadas
     sugestão: chamar buscar_logs com janela ampla
Etapa 4: buscar_logs (correção) → FINALIZAR
   [reflexão] aprovado! nota=85/100
```

**Comandos executados:**
```bash
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência no checkout" --arquitetura plan_execute
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência no checkout" --arquitetura reflect
```

**Arquiteturas Cognitivas Disponíveis:**
```
Runtime Python (agnóstico)
       ↓
┌─────────────────┬─────────────────┬─────────────────┐
│ ReAct           │ Plan-Execute    │ Reflection       │
│ Reason + Act    │ Planeja tudo    │ Executa + Crítica│
│ raciocínio/     │ depois executa  │ rejeita → corrige│
│ etapa           │ tokens=0 nas    │ até aprovação    │
│                 │ etapas seguintes│                  │
└─────────────────┴─────────────────┴─────────────────┘
       ↓
Sinais detectados pelo runtime:
- ReAct: formato_saida.raciocínio: obrigatório
- Plan-Execute: modo_execucao: plan_execute
- Reflection: presença de critic.md
```
**Comparativo de Arquiteturas:**
| Arquitetura | LLM por etapa | Fase extra | Quando usar |
|-------------|---------------|------------|-------------|
| ReAct | 1 por etapa | — | Auditoria passo a passo |
| Plan-Execute | 1 (só na primeira) | — | Pipeline determinístico, economia de tokens |
| Reflection | 1 + crítica | reflexão | Qualidade/completude crítica do output |

#### **Projeto:** [eval-suite](module-02-b)

**Tecnologias utilizadas:**
- **Python** - Benchmark engine e eval suite
- **YAML** - Definição de suites de avaliação com métricas e limiares
- **JSON** - Dataset de cenários e resultados de benchmark
- **Markdown** - Relatórios comparativos automáticos

**Conceitos abordados:**
- Evals: medir decisão, não código (taxa de conclusão, cobertura, tokens, tempo)
- Dataset com cenários e gabarito (`ferramentas_esperadas`)
- Suite de avaliação: métricas + limiares de qualidade
- Benchmark engine: itera dataset, extrai métricas, fiscaliza limiares
- Comparação entre 4 arquiteturas: `padrão`, `react`, `plan_execute`, `reflect`
- Relatório comparativo com melhor valor em negrito por métrica
- Equivalências com frameworks reais (LangChain, LangGraph)

**Aplicação prática:**
O `module-02-b` fecha a Unidade 2 com uma **eval suite** para escolher a melhor arquitetura baseada em evidências, não intuição.

Componentes:
- **Dataset** (`evals/datasets/incidentes.json`): 5 cenários com dificuldade e ferramentas esperadas
- **Suite** (`evals/suites/monitor-agent.yaml`): define métricas (taxa_conclusao, media_tokens, cobertura_ferramentas, etc.) e limiares mínimos
- **Benchmark Engine** (`runtime/benchmark.py`): roda arquitetura contra dataset, extrai métricas do trace, gera relatório
- **Equivalências** (`equivalencias/`): mapeamento nosso framework ↔ LangChain ↔ LangGraph

Comandos:
- `benchmark`: roda uma arquitetura, salva `bench_<arq>.json`
- `comparar`: roda as 4 arquiteturas, gera `benchmarks/report.md` com tabela comparativa

**Comandos executados:**
```bash
python runtime/main.py benchmark --agente monitor-agent --suite evals/suites/monitor-agent.yaml --arquitetura react
python runtime/main.py comparar --agente monitor-agent --suite evals/suites/monitor-agent.yaml
```

**Arquitetura de Evals:**
```
Dataset (incidentes.json)
       ↓
Suite (monitor-agent.yaml) → métricas + limiares
       ↓
Benchmark Engine (benchmark.py)
       ↓
┌──────────────────────────────────────────┐
│ 4 arquiteturas rodando 5 cenários cada │
│ padrão | react | plan_execute | reflect │
└──────────────────────────────────────────┘
       ↓
bench_<arq>.json (4 arquivos)
       ↓
report.md (tabela comparativa + violações + veredito)
```

**Métricas Comparadas:**
| Métrica | O que mede | Quando preocupar |
|---------|-------------|------------------|
| `taxa_conclusao` | % de cenários completados | < 80% |
| `cobertura_ferramentas` | % das esperadas que foram chamadas | < 75% |
| `media_tokens` | custo médio por execução | valor mais alto = mais caro |
| `tokens_planejamento` | concentração de tokens no planejamento | Plan-Execute concentra aqui |
| `reflexoes_total` | ciclos rejeição→correção (só reflect) | muitas = output ruim inicial |

**Equivalências (Nosso Framework ↔ LangChain ↔ LangGraph):**
| Nosso Framework | LangChain | LangGraph |
|-----------------|-----------|-----------|
| `agent.md` | prompt template | `TypedDict` State |
| `skills.md` | `@tool` decorators | nodes do grafo |
| `planner.md` (ReAct) | `create_react_agent()` | `conditional_edges` |
| `ciclo.py` | `AgentExecutor` | `StateGraph` |
| `rules.md → max_etapas` | `max_iterations` | loop do grafo |
| `trace.json` | LangSmith | callbacks |

### Módulo 03: Integração com o Mundo Real e Ferramentas

#### **Projeto:** [mock-to-real](module-03)

**Tecnologias utilizadas**:
- **Python** - Runtime com padrão Adapter
- **FastAPI** - API local com endpoints reais
- **HTTP/REST** - Comunicação com APIs via adapter
- **YAML** - Contratos com `tipo_implementacao`, `conexao`, `limites`
- **Env** - Secrets (`API_BASE_URL`, `API_KEY`)

**Conceitos abordados**:
- Padrão Adapter: contrato declara tipo, runtime despacha, adapter conecta
- `tipo_implementacao`: `rest`, `database`, `mcp`, `mock` (ausente = mock)
- Resolutor dinâmico por tipo de implementação
- Backward compatible: sem `tipo_implementacao` → mock
- Graceful degradation: adapter não instalado → fallback mock
- Open-Closed: nova fonte entra como pasta nova em `adapters/`
- API local com dados consistentes (diferente do mock aleatório)
- Auditabilidade no trace: campo `_adapter` e `_latencia_ms`

**Aplicação prática**:
O `module-03` faz o `monitor-agent` sair do simulador. 3 skills viram REST via adapter, 1 continua mock.

- `consultar_metricas`, `buscar_logs`, `historico_deploys` usam `rest_adapter`
- `relatorio_incidente` continua com `mock` (convivem no mesmo agente)
- Cada habilidade resolve seu próprio adapter
- API local: `GET /api/v1/metrics`, `/logs`, `/deploys`
- Secrets no `.env`, nunca no contrato `.md`

**Comandos executados**:
```bash
python api_local/server.py
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência no checkout"
```

**Arquitetura Adapter**:
```
skills.md (contrato)
    ↓
tipo_implementacao: rest | database | mcp | mock
    ↓
runtime/ferramentas.py → _resolver_adapter
    ↓
┌──────────────┬──────────────┬──────────────┐
│ rest_adapter │ db_adapter  │ mcp_adapter  │
│ (HTTP)       │ (Postgres)  │ (MCP)        │
└──────────────┴──────────────┴──────────────┘
    ↓ fallback → construir_ferramenta (mock)

trace.json marca:
{"_adapter": "rest", "_latencia_ms": 12.4, ...}
```

**Mock vs Real**:
| Característica | Mock | REST |
|----------------|------|------|
| Valores | aleatórios | consistentes |
| Latência | ~0ms | ms HTTP |
| Marca no trace | sem `_adapter` | `_adapter: "rest"` |
| Auditável | não | sim |

#### **Projeto:** [database-and-mcp](module-03-a)

**Tecnologias utilizadas**:
- **Python** - Runtime com adapters (rest, database, mcp)
- **FastAPI** - API local (inalterada da aula 10)
- **SQLite** - Banco de dados local via db_adapter
- **MCP (Model Context Protocol)** - Servidor stdio com SDK oficial
- **SQL** - Queries parametrizadas com segurança (read_only, LIMIT)
- **Env** - Secrets para conexão (`DB_CONNECTION_STRING`, `API_BASE_URL`, `API_KEY`)

**Conceitos abordados**:
- 4 tipos de adapter rodando simultaneamente: rest, database, mcp, mock
- `db_adapter.py`: 3 regras de segurança (read_only, parametrização, LIMIT)
- `mcp_adapter.py`: SDK oficial MCP via stdio com handshake
- Segurança em 3 camadas: política declarada (`rules.md`), validação no adapter, hooks em runtime
- Graceful degradation: infra indisponível → fallback mock com `_simulado: true`
- `seed_logs.py`: popula SQLite com dados consistentes
- MCP config padrão (compatível com Claude Code/Cursor)

**Aplicação prática**:
O `module-03-a` expande o `monitor-agent` com 6 tools e 4 adapters:

- **REST** (3 tools): `consultar_metricas`, `buscar_logs`, `historico_deploys`
- **Database** (1 tool): `buscar_logs_historico` — query parametrizada, read_only, LIMIT
- **MCP** (1 tool): `buscar_issues` — stdio MCP com handshake via SDK
- **Mock** (1 tool): `relatorio_incidente`

Segurança em 3 camadas:
1. Política declarada no `rules.md` (texto injetado no prompt)
2. Validação no adapter (`db_adapter` bloqueia INSERT/UPDATE/DELETE)
3. Hooks em runtime (`validar_rate_limit`, `verificar_budget`)

**Comandos executados**:
```bash
python seed_logs.py
python -c "import sqlite3; \
c = sqlite3.connect('monitor.db'); \
print(c.execute('SELECT service, level, timestamp FROM logs ORDER BY timestamp DESC LIMIT 5').fetchall());"
python api_local/server.py
python mcp/server.py
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência no checkout"
```

**Arquitetura Multi-Adapter**:
```
skills.md → tipo_implementacao: rest | database | mcp | mock
    ↓
_resolver_adapter (runtime/ferramentas.py)
    ↓
┌──────────┬──────────┬──────────┬──────────┐
│ rest     │ database│ mcp      │ mock     │
│ (HTTP)   │ (SQLite)│ (stdio)  │ (LLM)    │
└──────────┴──────────┴──────────┴──────────┘
    ↓
trace.json marca origem:
{"_adapter": "database", "_simulado": false}
{"_adapter": "mcp", "_via_mcp_real": true}
```

**Segurança em 3 Camadas**:
| Vetor | Onde mora | Quem fiscaliza |
|-------|-----------|-----------------|
| Política | rules.md (texto injetado) | LLM + auditoria |
| Validação | db_adapter (regex, parametrização) | runtime (bloqueia) |
| Hook | hooks.md (lista de ações) | runtime (intercepta) |

#### **Projeto:** [tool-selection-eval-suite](module-03-b)

**Tecnologias utilizadas**:
- **Python** - Eval runner para tool selection
- **YAML** - Suites de avaliação com métricas e limiares
- **JSON** - Dataset de casos de tool selection com gabarito explícito
- **Markdown** - Relatórios automáticos por arquitetura

**Conceitos abordados**:
- Tool selection eval: mede precisão de escolha de ferramenta (caso a caso)
- Dataset com `tool_esperada`, `argumentos_esperados`, `tools_nao_esperadas`
- 4 métricas: `tool_selection_accuracy`, `argument_accuracy`, `unnecessary_calls_rate`, `wrong_tool_rate`
- Eval mais barato que benchmark: chama só o planejador, não o ciclo inteiro
- Comparativo entre 4 arquiteturas via `tool-eval-comparar`
- Refinamento spec-driven: melhorar `descricao` da skill = accuracy sobe sem código

**Aplicação prática**:
O `module-03-b` mede se o agente **escolhe a tool certa para a etapa certa com os argumentos certos**.

Componentes:
- **Dataset** (`tool_selection_cases.json`): casos com entrada, etapa, contexto, tool esperada, justificativa
- **Suite** (`tool_selection.yaml`): métricas + limiares de qualidade
- **Runner** (`tool_eval.py`): itera dataset, chama planejador, avalia caso a caso
- **Refinamento**: melhorar `descricao` da skill pode subir accuracy 20 pontos sem mudar código

**Comandos executados**:
```bash
python runtime/main.py tool-eval --agente monitor-agent --suite evals/suites/tool_selection.yaml
python runtime/main.py tool-eval-comparar --agente monitor-agent --suite evals/suites/tool_selection.yaml
```

**Arquitetura do Tool Eval**:
```
dataset (tool_selection_cases.json)
       ↓
suite (tool_selection.yaml) → métricas + limiares
       ↓
tool_eval.py → rodar_tool_eval
       ↓
┌──────────────────────────────────────────────┐
│ 4 arquiteturas: padrão, react, plan_execute, │
│ reflect — cada uma roda o planejador apenas │
└──────────────────────────────────────────────┘
       ↓
tool_eval_<arq>.json (4 arquivos)
       ↓
tool_selection_report.md (comparativo + negrito no melhor valor)
```

**Métricas e Limiares**:
| Métrica | Direção | Limiar |
|---------|---------|--------|
| `tool_selection_accuracy` | maior = melhor | ≥ 80% |
| `argument_accuracy` | maior = melhor | - |
| `unnecessary_calls_rate` | menor = melhor | ≤ 10% |
| `wrong_tool_rate` | menor = melhor | ≤ 15% |

**Comparativo Esperado por Arquitetura**:
| Arquitetura | Comportamento |
|-------------|---------------|
| `react` | accuracy alta — raciocina antes de cada escolha |
| `reflect` | accuracy alta — crítico corrige tool errada |
| `plan_execute` | accuracy menor — decide tudo no início |
| `padrão` | baseline sem raciocínio explícito |

### Módulo 04: Memória e Evolução de Agentes Inteligentes

#### **Projeto:** [agent-that-remembers](module-04)

**Tecnologias utilizadas**:
- **Python** - Runtime com memory adapter e memory_store
- **YAML** - Contratos de memória com 4 tipos e políticas
- **LLM (Large Language Model)** - Motor com contexto recuperado de memória
- **JSON** - Formato de resumos de episódios

**Conceitos abordados**:
- 4 tipos de memória: curta (local/RAM), longa (fatos persistentes YAML), episódica (resumos de execuções), contextual (embeddings, aula 14)
- memory_adapter.py: 5 operações (gravar, recuperar, atualizar, remover, listar) — mesmo padrão dos tool adapters
- Hooks de memória: antes/depois de recuperar e persistir contexto
- Políticas de memória no rules.md: governança sobre o que pode ser gravado
- Integração no ciclo: _recuperar_contexto (antes do loop) e _persistir_memoria (depois do loop)
- Memória opt-in: sem tipagem_memoria no contrato, volta ao comportamento da U1

**Aplicação prática**:
O `monitor-agent` agora acumula conhecimento entre execuções. Na primeira rodada, grava fatos confirmados em `memory_store/longa/` e resumo do episódio em `memory_store/episodica/`. Na segunda rodada, recupera o contexto antes do loop e o agente já vê histórico relevante — tende a tomar atalhos e não reinvestigar do zero.

O agente pode:
- Recuperar fatos conhecidos antes de começar (`_recuperar_contexto`)
- Persistir resumo do episódio após finalizar (`_persistir_memoria`)
- Aplicar políticas de governança (nunca secrets, só fatos confirmados, etc.)

**Comandos executados**:
```bash
python runtime/main.py rodar --agente monitor-agent --entrada "Alerta de latência no serviço de pagamentos"
python runtime/main.py rodar --agente monitor-agent --entrada "Erro 500 no serviço de pagamentos"
```

**Arquitetura da Memória**:
```
monitor-agent/memory.md (contrato)
    ↓
tipos_memoria: curta | longa | episodica | contextual
    ↓
runtime/adapters/memory_adapter.py
    ↓
┌────────────┬────────────┬────────────┬────────────┐
│ curta/     │ longa/     │ episodica/ │ contextual/│
│ (RAM)      │ (YAML)     │ (YAML)     │ (emb.)    │
└────────────┴────────────┴────────────┴────────────┘
    ↓
ciclo.py: _recuperar_contexto → loop → _persistir_memoria
    ↓
hooks: antes/depois de recuperar e persistir
```

**Políticas de Memória (rules.md)**:
- Nunca gravar secrets, tokens ou senhas
- Memória longa só aceita fatos confirmados por evidência de tool
- Memória episódica deve ser resumida, nunca trace completo
- Max 2000 tokens de contexto recuperado por execução
- Memórias com mais de 90 dias sem acesso podem ser arquivadas

#### **Projeto:** [embeddings-evolutive-reflection](module-04-a)

**Tecnologias utilizadas**:
- **Python** - Runtime com embedding adapter e reflection store
- **YAML** - Contratos de reflexão com extração, detecção e injeção de lições
- **LLM (Large Language Model)** - Motor de extração de lições e busca semântica
- **JSON** - Índice local de embeddings (indice.json)

**Conceitos abordados**:
- **Embedding adapter**: indexar texto, buscar por similaridade de cosseno, reindexar memórias existentes
- **Memória contextual**: busca semântica com `text-embedding-3-small` e limiar de similaridade (`limiar_similaridade: 0.7`)
- **Reflection store**: 3 subdiretórios — `licoes/` (YAMLs com situacao, acao, resultado, licao), `padroes/` (detecção consolidada), `meta.yaml` (contador de execuções)
- **Lazy reindex**: na primeira execução, reindexa automaticamente `longa` + `episodica` sem script de setup
- **Extração de lições**: só quando resultado inesperado (erro, falha, estouro de etapas) — no máximo 3 por execução, generalizáveis, filtradas contra secrets
- **Detecção de padrões**: contador MVP a cada 10 execuções
- **Injeção no planner**: lições relevantes entram no `contexto_do_planner` como `licoes_relevantes`
- **Contexto enriquecido**: planner recebe `conhecimento_relevante`, `experiencia_anterior`, `licoes_relevantes`, `fatos_conhecidos`

**Aplicação prática**:
O agente agora não só lembra fatos e episódios, ele entende similaridade semântica e aprende com os erros. Na primeira execução, reindexa automaticamente memórias existentes no índice de embeddings. Quando o resultado é inesperado (erro, falha, timeout), extrai até 3 lições generalizáveis e persiste em `reflection_store/licoes/`. Execuções seguintes recebem contexto enriquecido: fragmentos similares, episódios anteriores e lições relevantes injetados no planner.

O agente pode:
- Buscar conhecimento semântico por similaridade (`embedding_adapter.buscar`)
- Extrair lições ao final de execuções com erro (`_extrair_licoes`)
- Receber lições relevantes no planner da próxima execução
- Reindexar automaticamente se o índice estiver vazio (lazy reindex)

**Comandos executados**:
```bash
python runtime/main.py rodar --agente monitor-agent --entrada "Erro 500 no serviço de pagamentos"
python runtime/main.py rodar --agente monitor-agent --entrada "Investigar incidente de latência no checkout após deploy"
```

**Arquitetura de Memória + Reflexão**:
```
Contratos: memory.md + reflection.md
    ↓
runtime/adapters/
├── memory_adapter.py  (gravar, recuperar, atualizar, remover, listar)
└── embedding_adapter.py (indexar, buscar, reindexar)
    ↓
┌────────────┬────────────┬────────────┬────────────┬────────────────┐
│ curta/     │ longa/     │ episodica/ │ contextual/│ reflection_    │
│ (RAM)      │ (YAML)     │ (YAML)     │ indice.json│ store/licoes/  │
└────────────┴────────────┴────────────┴────────────┴────────────────┘
    ↓
ciclo.py:
  _recuperar_contexto → (longa + episodica + contextual + licoes)
       ↓
  loop principal (planner com contexto_enriquecido)
       ↓
  _persistir_memoria → (episodica)
  _extrair_licoes   → (reflection_store/licoes/) [se resultado inesperado]
```

**Políticas de Reflexão**:
- Só extrair lição se resultado inesperado (erro, falha, estouro de etapas)
- Lição deve ser generalizável, nunca específica a um input
- Máximo 3 lições por execução
- Filtrar secrets/tokens/senhas antes de persistir
- Máximo 5 lições injetadas por execução, ordenadas por relevância ao objetivo

#### **Projeto:** [memory-eval-suite](module-04-b)

**Tecnologias utilizadas**:
- **Python** - Runtime com embedding adapter e reflection store
- **YAML** - Contratos de reflexão com extração, detecção e injeção de lições
- **LLM (Large Language Model)** - Motor de extração de lições e busca semântica
- **JSON** - Índice local de embeddings (indice.json)

**Conceitos abordados**:
- Avaliar se a memória melhora a tomada de decisões do agente
- Dataset com 5+ casos cobrindo memória ajudando, ruído, desatualização, sem memória e lições
- 6 métricas com limiares: precisão, recall, utilização, alucinação, melhoria de decisão, qualidade de lições
- Execução dos casos duas vezes: uma com memória, outra com memória desativada
- Diagnóstico de métricas baixas e falso-positivos

**Aplicação prática**:
Este eval da aula 15 mede quantitativamente o impacto da memória instalada e funcionando:
- Roda casos do dataset com e sem memória via flag `MEMORY_DISABLED`
- Reporta métricas e gera relatório markdown com comparativos
- Permite eval rápido com `--max-casos` para iterar mais rápido
- Fornece guia rápido para diagnóstico e ajuste de parâmetros

**Arquitetura**:
```txt
runtime/memory_eval.py  → execucao do harness
evals/datasets/memory_impact_cases.json  → dataset de casos de teste
evals/suites/memory_impact_eval.yaml  → definição das métricas e limiares
evals/resultados/memory_impact_report_<ts>.md  → relatório markdown da execução
```

**Comandos executados**:
```bash
python runtime/main.py memory-eval --agente monitor-agent --suite evals/suites/memory_impact_eval.yaml
python runtime/main.py memory-eval --agente monitor-agent --suite evals/suites/memory_impact_eval.yaml --max-casos 2
```

**Métricas avaliadas**:
| Métrica                | Descrição                                  | Limiar    |
|------------------------|--------------------------------------------|-----------|
| `retrieval_precision`  | Fragmentos recuperados são úteis           | 0.7       |
| `retrieval_recall`     | Encontrou tudo que importava               | 0.6       |
| `memory_utilization`   | O planner usou o contexto recuperado       | 0.5       |
| `hallucination_from_memory` | Inventou dados não presentes na memória | max 0.1   |
| `decision_improvement` | Decisões melhoram com memória               | min 0.15  |
| `lesson_quality`       | Lições extraídas são úteis                   | 0.6       |

**Regras para garantir qualidade da métrica `lesson_quality`**:
- A pasta `reflection_store/licoes` precisa estar populada antes do eval
- Forçar extração de lições para obter dados válidos (exemplo: reduzir max_etapas temporariamente)

**Diagnóstico & Ajustes**:
- `retrieval_precision`: aumentar `contextual.limiar_similaridade` para filtrar melhor
- `retrieval_recall`: reduzir limiar para recuperar mais
- `memory_utilization`: ajustar regras no planner para usar memória
- `hallucination_from_memory`: configurar política de expiração para descartar memórias antigas
- `decision_improvement`: avaliar sintoma, não causa
- `lesson_quality`: revisar configuração de extração no reflection.md

**Comandos executados**:
```bash
python runtime/main.py memory-eval --agente monitor-agent --suite evals/suites/memory_impact_eval.yaml --max-casos 2
```