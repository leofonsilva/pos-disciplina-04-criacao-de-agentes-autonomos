# Relatorio de Impacto de Memoria — monitor-agent

**Data:** 2026-05-13 20:49:24
**Casos avaliados:** 2
**Tempo total:** 87.4s

## Metricas Agregadas

| Metrica | Valor | Threshold | Status |
|---------|-------|-----------|--------|
| retrieval_precision | 0.625 | 0.8 | FAIL |
| retrieval_recall | 0.167 | 0.6 | FAIL |
| memory_utilization | 0.500 | 0.5 | PASS |
| hallucination_from_memory | 0.800 | 0.02 | FAIL |
| decision_improvement | 0.250 | 0.15 | PASS |
| lesson_quality | 1.000 | 0.4 | PASS |

## Comparativo: Sem Memoria vs Com Memoria

| Caso | Etapas Sem | Etapas Com | Improvement |
|------|-----------|-----------|-------------|
| case_001 | 7 | 7 | 0.00 |
| case_002 | 12 | 6 | 0.50 |

## Detalhamento por Caso

| Caso | Recuperados | Esperados | Precision | Recall | Util | Halluc |
|------|-------------|-----------|-----------|--------|------|--------|
| case_001 | 0 | 4 | 1.00 | 0.00 | 1.00 | 0.80 |
| case_002 | 4 | 3 | 0.25 | 0.33 | 0.00 | 0.80 |

## Conclusao

- 3 metricas aprovadas, 3 reprovadas
- Revisar memorias seed e logica de recuperacao para metricas reprovadas
