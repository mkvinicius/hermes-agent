---
name: compras
description: Registra compras, compara preço atual com histórico, detecta aumentos acima de 5%, calcula impacto financeiro mensal e sugere alternativa de fornecedor.
version: 1.0.0
author: MargemAI
license: MIT
metadata:
  hermes:
    tags: [compras, fornecedor, preço, insumo, custo, cmv, inflação]
    related_skills: [entrada-nota, calcular-cmv, consulta-livre]
---

# Gestão de Compras

Use esta skill ao registrar uma compra ou quando o usuário perguntar sobre preços de insumos e fornecedores.

## Quando usar

- Ao receber uma nota fiscal (chamada pela skill `entrada-nota`)
- Quando o usuário registra uma compra manualmente
- Quando pergunta "o frango tá mais caro?" ou "qual fornecedor tá mais barato?"

## Fluxo ao registrar uma compra

### 1. Salvar a compra

Persistir no banco:
- Data, fornecedor, insumo, quantidade, preço unitário, preço total

### 2. Comparar com histórico

Para cada insumo comprado:
```
preço_anterior = média dos últimos 3 registros do mesmo insumo
variação = (preço_atual - preço_anterior) / preço_anterior × 100
```

### 3. Detectar alertas

| Variação | Ação |
|----------|------|
| > +5% | Alertar e calcular impacto |
| > +15% | Alertar com urgência e sugerir alternativa |
| < -5% | Informar positivamente (oportunidade de comprar mais) |
| Dentro de ±5% | Sem alerta — registrar silenciosamente |

### 4. Calcular impacto financeiro

Quando há alta relevante:
```
consumo_mensal = média de compras do insumo nos últimos 3 meses (em unidade)
impacto_mensal = consumo_mensal × (preço_atual - preço_anterior)
```

Apresentar em reais: "esse aumento vai custar R$X a mais por mês se nada mudar."

### 5. Sugerir alternativa de fornecedor

Se houver outro fornecedor do mesmo insumo no banco com preço menor:
```
economia_potencial = (preço_atual - preço_alternativo) × consumo_mensal
```

Apresentar: "O fornecedor [Y] vendeu [insumo] a R$X no último registro. Isso economizaria R$Y/mês."

Se não houver alternativa: sugerir cotação ("vale comparar preços com outros fornecedores desta categoria").

## Apresentação de alertas

Alerta padrão (>5%):
```
Alta detectada: [insumo] subiu [X]% desde a última compra.
Preço anterior: R$[A]/[unidade] → Atual: R$[B]/[unidade]
Impacto estimado: +R$[C]/mês no seu custo.
[Se houver alternativa: "O fornecedor [Y] pratica R$[D]. Economia potencial: R$[E]/mês."]
```

## Relatório de compras do mês

Quando solicitado (`"como foram as compras do mês?"`):

1. Total gasto em compras
2. Top 5 insumos por valor
3. Insumos com alta de preço
4. Insumos com queda de preço (oportunidades)
5. Fornecedores mais usados

## Regras

- Nunca inventar histórico de preço — se não há dados, dizer "primeira compra registrada deste insumo".
- Alertas só disparam quando há histórico para comparar (mínimo 1 registro anterior).
- Sempre confirmar unidade antes de comparar (kg vs unidade vs litro).
