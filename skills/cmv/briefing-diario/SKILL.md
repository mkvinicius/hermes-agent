---
name: briefing-diario
description: Gera briefing matinal em no máximo 5 frases com CMV atual, principal alerta e uma ação para hoje. Só envia se houver algo relevante ou for segunda-feira.
version: 1.0.0
author: MargemAI
license: MIT
metadata:
  hermes:
    tags: [briefing, matinal, diário, alerta, cmv, resumo, rotina]
    related_skills: [calcular-cmv, compras, consulta-livre]
---

# Briefing Diário

Use esta skill para gerar o resumo matinal do negócio. Roda automaticamente pela manhã (via cron) ou quando o usuário pede explicitamente.

## Quando enviar

Enviar briefing SOMENTE se pelo menos uma das condições for verdadeira:

1. **É segunda-feira** — início de semana sempre merece contexto.
2. **Há algum alerta relevante** — CMV acima da meta, alta de preço, break-even em risco.
3. **O usuário pediu explicitamente** — `"me dá o briefing"`, `"como está o negócio?"`.

Se for terça a sábado e não houver nada relevante: não enviar. Silêncio é sinal de que está tudo bem.

## Estrutura do briefing

Máximo 5 frases. Sem parágrafos longos. Sem introdução.

```
1. CMV atual: [X]% [meta: Y%] — [ok / atenção / alerta].
2. [Principal alerta ou destaque positivo do período.]
3. [Segunda informação relevante, se houver.]
4. [Terceira informação, se houver.]
5. Ação para hoje: [uma coisa concreta e acionável].
```

Se só há 1 alerta relevante, usar apenas 3 frases + a ação. Não encher com texto.

## Dados a consultar antes de gerar

- CMV do mês atual vs. meta configurada
- Compras dos últimos 7 dias com alta de preço
- Faturamento da semana vs. ponto de equilíbrio
- Alertas pendentes não resolvidos

## Exemplos

**Segunda-feira, tudo dentro do normal:**
```
CMV de maio: 33,1% — dentro da meta de 35%.
Semana passada: R$5.200 em compras, sem alta relevante.
Faturamento da semana: R$14.800 — acima do break-even.
Ação: revisar ficha técnica do prato novo antes de precificar.
```

**Alerta de alta:**
```
CMV subiu para 37,4% — acima da meta de 35%.
Frango subiu 12% desde a última compra: impacto de R$380/mês.
Ação: cotar frango com o Fornecedor B ou revisar porção do prato proteico.
```

**Risco de equilíbrio:**
```
Faturamento desta semana: R$9.100 — 18% abaixo do break-even.
Sem alerta de CMV, mas o volume de vendas precisa de atenção.
Ação: verificar se há feriado ou causa operacional que explique a queda.
```

## Tom e estilo

- Direto ao ponto. Nada de "Bom dia! Aqui está seu resumo diário..."
- Não usar jargões sem contexto.
- A ação deve ser algo que o dono pode fazer hoje, não uma recomendação vaga.
- Se está tudo bem, dizer isso claramente — não inflar com alertas imaginários.

## Regras

- Máximo 5 frases. Sem exceção.
- Nunca inventar dados — se não há informação no banco, omitir aquele campo.
- A ação deve ser sempre a última linha.
- Se não há nada relevante e não é segunda-feira: não gerar e não enviar.
