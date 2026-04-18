---
name: calcular-cmv
description: Calcula CMV teórico e real, detecta desvios e identifica pratos problemáticos
triggers:
  - CMV
  - custo
  - margem
  - lucro
  - caro
---

# Calcular CMV

## Quando usar
- Usuário pergunta sobre CMV, margem ou lucro
- Nova compra registrada
- Heartbeat semanal
- "Esse prato dá lucro?"

## Como agir
1. Buscar compras dos últimos 30 dias no banco
2. Buscar fichas técnicas ativas
3. Calcular CMV por prato: (custo ingredientes / preço venda) × 100
4. Calcular CMV geral ponderado
5. Comparar com meta por tipo de negócio:
   - Buffet/Restaurante: meta 28-35%
   - Padaria: meta 25-32%
   - Food truck: meta 30-38%
6. Identificar pratos acima da meta
7. Gerar recomendação

## Tom
- Use números reais: "Seu CMV está em 32%"
- Seja específico: "O frango está puxando o custo"
- Uma ação por vez
- Nunca inventar dados
- Se faltar dado, pedir ao usuário
