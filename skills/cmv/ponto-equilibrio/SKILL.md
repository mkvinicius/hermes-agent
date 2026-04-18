---
name: ponto-equilibrio
description: Calcula break-even e simula cenários de reajuste de preço
triggers:
  - ponto de equilíbrio
  - break-even
  - custos fixos
  - quanto preciso vender
  - vale subir o preço
---

# Ponto de Equilíbrio

## Quando usar
- Usuário pergunta quanto precisa vender
- Usuário quer saber se vale subir preço
- Usuário pergunta sobre custos fixos
- Heartbeat mensal

## Como agir
1. Buscar custos fixos mensais do banco
2. Buscar CMV atual e ticket médio
3. Calcular ponto de equilíbrio:
   PE = Custos Fixos / (1 - CMV%)
4. Comparar com faturamento atual
5. Calcular margem de segurança:
   MS = (Faturamento - PE) / Faturamento × 100
6. Se usuário pedir simulação:
   - Simular novo preço ou novo CMV
   - Mostrar novo PE e nova margem
   - Comparar com situação atual

## Tom
- Usar números reais: "Você precisa faturar R$ 28.000 para cobrir seus custos"
- Mostrar margem de segurança: "Você está R$ 4.000 acima do ponto de equilíbrio"
- Simulações claras: "Se subir o preço 10%, seu PE cai para R$ 25.000"
- Nunca inventar custos fixos
