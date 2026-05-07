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

**Projeto:** [agent-types](module-01-c)

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
**Projeto:** [cognitive-architecture](module-02)

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

**Projeto:** [plan-execute-and-reflection](module-02-a)

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
