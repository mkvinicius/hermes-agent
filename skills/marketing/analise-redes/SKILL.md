---
name: analise-redes
description: Lê métricas do Instagram via Graph API, identifica padrões de engajamento e compara com a semana anterior.
version: 1.0.0
author: MargemAI
license: MIT
metadata:
  hermes:
    tags: [marketing, instagram, métricas, engajamento, redes-sociais, restaurante]
    related_skills: [criacao-conteudo, agenda-semanal, publicacao]
---

# Análise de Redes Sociais

Use esta skill para ler as métricas do Instagram e transformar dados em inteligência acionável para a equipe de conteúdo.

## Quando usar

- Heartbeat semanal de segunda 07:00
- Quando o Diretor de Marketing solicitar análise
- Após campanha ou promoção específica para avaliar resultado

## Etapas

### 1. Coletar métricas via Instagram Graph API

```
GET /me/media
  fields: id, caption, media_type, timestamp, like_count, comments_count, reach, impressions, saved

GET /me/insights
  metric: reach, impressions, profile_views, website_clicks
  period: week
```

Nunca inventar métricas. Se a API retornar erro, reportar ausência de dados com a mensagem de erro.

### 2. Calcular indicadores

- **Taxa de engajamento por post**: (curtidas + comentários + salvamentos) / alcance × 100
- **Horários de pico**: agrupar posts por faixa horária e ordenar por engajamento médio
- **Dias fracos**: cruzar dias da semana com menor alcance
- **Tipo de conteúdo mais eficaz**: comparar média de engajamento entre feed, carrossel, reels e stories

### 3. Comparar com semana anterior

Buscar métricas da semana anterior no banco local (tabela `marketing_weekly_metrics`). Calcular variação percentual de alcance e engajamento.

### 4. Gerar relatório

```
RELATÓRIO SEMANAL — [data_inicio] a [data_fim]
Alcance total: [N] ([+/-X%] vs semana anterior)
Engajamento médio: [X%]
Post de melhor performance: [tipo] — [engajamento]
Horários de pico: [HH:MM], [HH:MM], [HH:MM]
Dias de menor movimento: [dia], [dia]
Tipo mais eficaz: [feed|carrossel|reels|stories]
Recomendação: [1 frase acionável]
```

### 5. Salvar e passar adiante

Salvar relatório no banco e passar para o Redator via tarefa no Paperclip.

## Regras

- Sempre comparar com a semana anterior.
- Se não houver dados da semana anterior, indicar "primeira semana com dados".
- Nunca recomendar horário sem base em dados reais.
- Cruzar dias fracos do Instagram com dias de menor venda (se disponível no banco CMV).
