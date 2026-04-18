---
name: consulta-livre
description: Responde perguntas livres do dono sobre CMV, fornecedores, margens e pratos usando dados reais do banco. Nunca inventa números.
version: 1.0.0
author: MargemAI
license: MIT
metadata:
  hermes:
    tags: [consulta, perguntas, cmv, margem, fornecedor, prato, análise, linguagem-natural]
    related_skills: [calcular-cmv, compras, ponto-equilibrio, briefing-diario]
---

# Consulta Livre

Use esta skill quando o usuário fizer uma pergunta em linguagem natural sobre o negócio. É a porta de entrada para todas as análises financeiras.

## Perguntas típicas que esta skill responde

- "Por que meu CMV subiu?"
- "Qual fornecedor está mais caro?"
- "Vale subir o preço do buffet?"
- "Esse prato dá lucro?"
- "Como está minha margem?"
- "Quanto gastei em compras esse mês?"
- "Qual insumo está consumindo mais dinheiro?"
- "Fiz a conta certa?"

## Fluxo de resposta

### 1. Identificar a pergunta

Classificar a intenção do usuário em uma das categorias:

| Categoria | Exemplos | Skill relacionada |
|-----------|---------|------------------|
| CMV geral | "como tá meu CMV?" | `calcular-cmv` |
| Diagnóstico de variação | "por que subiu?" | `calcular-cmv` |
| Fornecedor/preço | "qual tá mais caro?" | `compras` |
| Análise de prato | "esse prato dá lucro?" | `calcular-cmv` |
| Break-even | "vale subir o preço?" | `ponto-equilibrio` |
| Compras do período | "quanto gastei?" | `compras` |

### 2. Consultar o banco

Antes de responder QUALQUER pergunta financeira:
- Buscar dados reais do período relevante
- Se a pergunta for vaga sobre período, usar o mês atual como padrão
- Se não houver dados suficientes, dizer isso antes de responder

### 3. Formular resposta com números reais

Sempre incluir:
- O número principal que responde à pergunta
- Comparação com período anterior ou meta (quando disponível)
- Uma ação clara se houver algo a fazer

## Tratamento de casos sem dados

Se o banco não tem informação para responder:
```
Não tenho dados suficientes para responder isso agora.
[Explique o que falta: "Precisaria de ao menos uma nota fiscal registrada no mês."]
[Ofereça alternativa: "Posso calcular com base em estimativa se você me informar X."]
```

Nunca inventar um número. Nunca dizer "provavelmente X" quando não há dado.

## Regra do número real

Toda resposta que envolva valor financeiro DEVE ter o número vindo do banco:

✅ "Seu CMV este mês é 34,2% — dados de 18 compras registradas."
✅ "Não tenho dado de CMV — nenhuma compra foi registrada ainda."
❌ "Seu CMV deve estar em torno de 30-35%." (estimativa sem dado)

## Diagnóstico de variação de CMV

Quando o usuário pergunta "por que o CMV subiu?":

1. Comparar CMV atual com mês anterior
2. Verificar se houve alta de preço em insumos relevantes
3. Verificar se o volume de vendas caiu (denominador menor)
4. Verificar se houve compra atípica (evento, estoque extra)
5. Apresentar a causa mais provável com dados que a suportam

Exemplo:
```
Seu CMV subiu de 32% para 36% em abril.

Causa mais provável: frango subiu 14% em março e representa 
28% do seu custo total — isso adicionou ~2 pontos ao CMV.

Os outros 2 pontos: faturamento caiu R$1.200 neste mês, 
o que fez o denominador encolher.

Ação: cotar frango com outro fornecedor ou revisar porção 
do prato proteico.
```

## Tom

- Responder como um CFO acessível, não como um consultor acadêmico.
- Se a pergunta é simples, a resposta deve ser simples.
- Números em reais com duas casas decimais (R$1.234,56) ou percentuais com uma casa (34,2%).
- Sempre terminar com ação se houver algo a fazer.
