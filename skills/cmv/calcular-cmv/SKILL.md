---
name: calcular-cmv
description: Calcula CMV teórico e real, detecta desvio entre os dois, identifica qual prato está puxando o custo e sugere ação corretiva.
version: 1.0.0
author: MargemAI
license: MIT
metadata:
  hermes:
    tags: [cmv, custo, margem, restaurante, gastronomia, financeiro]
    related_skills: [consulta-livre, ponto-equilibrio, briefing-diario]
---

# Calcular CMV

Use esta skill para calcular o Custo de Mercadoria Vendida (CMV) teórico e real, comparar os dois, e identificar onde o custo está fugindo do controle.

## Conceitos

- **CMV Teórico**: calculado pelas fichas técnicas × quantidade vendida. O que deveria ter sido gasto.
- **CMV Real**: calculado pelas compras realizadas × estoque. O que foi efetivamente gasto.
- **Desvio**: diferença entre teórico e real. Acima de 3 pontos percentuais, exige investigação.

## Etapas

### 1. Coletar dados do banco

Sempre consultar o banco antes de calcular. Nunca inventar números.

```
Dados necessários:
- Período de análise (padrão: mês atual)
- Vendas por prato (quantidade e valor)
- Fichas técnicas (ingredientes e quantidades)
- Compras realizadas no período
- Estoque inicial e final
```

### 2. Calcular CMV Teórico

```
Para cada prato vendido:
  custo_prato = soma(ingrediente × quantidade_usada × preço_unitário)
  custo_total_prato = custo_prato × quantidade_vendida

CMV_teórico = soma(custo_total_prato) / faturamento_total × 100
```

### 3. Calcular CMV Real

```
CMV_real = (estoque_inicial + compras_período - estoque_final) / faturamento_total × 100
```

### 4. Calcular Desvio

```
desvio = CMV_real - CMV_teórico
```

Se `desvio > 3%`: investigar causas (perdas, desperdício, furto, erro de ficha técnica).

### 5. Identificar prato crítico

Ranquear pratos por custo absoluto e por % de custo sobre preço de venda. O prato com maior custo proporcional é o candidato a ajuste.

### 6. Sugerir ação corretiva

| Situação | Ação sugerida |
|----------|---------------|
| CMV real > teórico + 3% | Investigar perdas e medir estoque |
| Prato com CMV > 40% | Revisar ficha técnica ou subir preço |
| Insumo com alta recente | Substituir ou negociar com fornecedor |
| CMV caindo com qualidade igual | Manter — está no caminho certo |

## Apresentação dos resultados

Sempre apresentar:

1. CMV teórico e real (em %)
2. Desvio (em pontos percentuais)
3. Top 3 pratos mais custosos
4. Uma ação prioritária clara

Usar linguagem direta. Evitar jargão. Se o dono pergunta "tô bem?", responder com um número e uma ação — não com uma análise acadêmica.

## Parâmetros aceitos

- `periodo`: "hoje", "semana", "mes", "YYYY-MM" — padrão: mês atual
- `prato`: nome específico para análise individual
- `comparar_com`: "mes_anterior", "mesmo_mes_ano_passado"

## Exemplo de resposta

```
CMV de abril: 34,2% (meta: 32%)
Desvio: +2,2 pontos — dentro do limite, mas monitorar.

Prato mais custoso: Buffet proteico — CMV 41%
Ação: revisar porção de carne ou subir R$0,50/kg.
```
