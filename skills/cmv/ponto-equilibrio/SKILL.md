---
name: ponto-equilibrio
description: Calcula break-even usando custos fixos, CMV e ticket médio. Simula cenários de reajuste de preço e redução de CMV. Responde em linguagem simples.
version: 1.0.0
author: MargemAI
license: MIT
metadata:
  hermes:
    tags: [break-even, ponto-equilibrio, simulação, preço, cmv, custo-fixo, margem]
    related_skills: [calcular-cmv, consulta-livre]
---

# Ponto de Equilíbrio

Use esta skill quando o usuário perguntar quantas vendas precisa fazer para cobrir os custos, ou quando quiser simular o efeito de mudar preço ou reduzir CMV.

## Conceitos

- **Ponto de equilíbrio**: faturamento mínimo para cobrir todos os custos (fixos + variáveis) sem lucro nem prejuízo.
- **Margem de contribuição**: o que sobra de cada venda depois de pagar o CMV.
- **Custos fixos**: despesas que não mudam com o volume (aluguel, salários, energia).

## Cálculo base

```
margem_contribuição = (1 - CMV%) × preço_médio_venda

ponto_equilíbrio_R$ = custos_fixos / (1 - CMV%)

ponto_equilíbrio_unidades = custos_fixos / margem_contribuição
```

Para buffet por quilo:
```
ponto_equilíbrio_kg = custos_fixos / margem_contribuição_por_kg
dias_para_equilibrio = ponto_equilíbrio_kg / venda_média_diária_kg
```

## Simulação de cenários

### Cenário 1 — Subir preço X%

```
novo_preço = preço_atual × (1 + X/100)
nova_margem = (1 - CMV%) × novo_preço
novo_ponto_equilibrio = custos_fixos / (1 - CMV%)
redução_em_vendas_necessárias = (ponto_atual - novo_ponto) / ponto_atual × 100
```

Apresentar: "Se você subir [X]%, pode vender [Y]% menos e ainda cobrir seus custos."

### Cenário 2 — Reduzir CMV Y pontos

```
novo_CMV% = CMV_atual% - Y
nova_margem = (1 - novo_CMV%) × preço_atual
novo_ponto_equilibrio = custos_fixos / (1 - novo_CMV%)
```

Apresentar: "Se você reduzir o CMV em [Y] pontos, seu break-even cai de R$[A] para R$[B]/mês."

### Cenário 3 — Combinado (subir preço + reduzir CMV)

Calcular os dois efeitos combinados e apresentar o resultado consolidado.

## Coleta de dados

Se os dados não estiverem no banco, perguntar:
1. Custos fixos mensais (aluguel, energia, salários, etc.)
2. CMV atual (%)
3. Ticket médio ou preço do quilo
4. Faturamento médio mensal (para contexto)

## Apresentação dos resultados

Sempre em linguagem simples. Evitar fórmulas na resposta final.

Exemplo padrão:
```
Seu ponto de equilíbrio é R$18.400/mês.
Com seu faturamento atual de R$22.000, você tem R$3.600 de folga.

Se você subir o preço 5%:
→ Break-even cai para R$17.500
→ Você pode vender 5kg/dia a menos e ainda cobrir tudo.

Se você reduzir o CMV 2 pontos (de 34% para 32%):
→ Break-even cai para R$17.100
→ Isso equivale a R$1.300 a mais no seu bolso por mês.
```

## Regras

- Nunca usar dados fictícios. Se o banco não tem custos fixos, perguntar antes de calcular.
- Sempre informar qual período foi usado nos cálculos.
- Dizer explicitamente quando um cenário é otimista vs. conservador.
- Não usar termos como "EBITDA", "MC%" sem explicar o que significam.
