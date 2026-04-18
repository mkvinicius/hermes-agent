---
name: compras
description: Registra compras, detecta aumento de preço e compara fornecedores
triggers:
  - fornecedor
  - preço
  - compra
  - subiu
  - mais caro
---

# Gestão de Compras

## Quando usar
- Nova compra registrada
- Usuário pergunta sobre fornecedor
- Heartbeat diário 06:00
- "Qual fornecedor está mais caro?"

## Como agir
1. Buscar histórico de preços dos últimos 30 dias
2. Comparar preço atual com média histórica
3. Calcular variação percentual
4. Classificar alerta:
   - CRÍTICO: aumento acima de 15%
   - ATENÇÃO: aumento entre 5% e 15%
   - OK: variação abaixo de 5%
5. Calcular impacto financeiro mensal
6. Se CRÍTICO ou ATENÇÃO, sugerir alternativa

## Tom
- Liderar com impacto financeiro: "O frango subiu 23% — R$ 340 a mais esse mês"
- Sugerir ação concreta
- Nunca inventar preço histórico
