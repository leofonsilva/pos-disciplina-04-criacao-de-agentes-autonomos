# Relatorio de Impacto de Memoria — monitor-agent

**Data:** 2026-05-13 20:53:52
**Casos avaliados:** 2
**Tempo total:** 76.8s

## Metricas Agregadas

| Metrica | Valor | Threshold | Status |
|---------|-------|-----------|--------|
| retrieval_precision | 0.534 | 0.7 | FAIL |
| retrieval_recall | 0.541 | 0.6 | FAIL |
| memory_utilization | 0.000 | 0.5 | FAIL |
| hallucination_from_memory | 0.600 | 0.02 | FAIL |
| decision_improvement | 0.322 | 0.15 | PASS |
| lesson_quality | 1.000 | 0.4 | PASS |

## Comparativo: Sem Memoria vs Com Memoria

| Caso | Etapas Sem | Etapas Com | Improvement |
|------|-----------|-----------|-------------|
| case_001 | 7 | 6 | 0.14 |
| case_002 | 12 | 6 | 0.50 |

## Detalhamento por Caso

| Caso | Recuperados | Esperados | Precision | Recall | Util | Halluc |
|------|-------------|-----------|-----------|--------|------|--------|
| case_001 | 8 | 4 | 0.62 | 0.75 | 0.00 | 0.60 |
| case_002 | 9 | 3 | 0.44 | 0.33 | 0.00 | 0.60 |

## Conclusao

- 2 metricas aprovadas, 4 reprovadas
- Revisar memorias seed e logica de recuperacao para metricas reprovadas
