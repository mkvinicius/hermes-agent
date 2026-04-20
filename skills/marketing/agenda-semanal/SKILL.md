---
name: agenda-semanal
description: Monta calendário editorial de 7 dias com horários otimizados, balanceamento de tipos de conteúdo e entrega pronto para publicar.
version: 1.0.0
author: MargemAI
license: MIT
metadata:
  hermes:
    tags: [marketing, calendário, planejamento, instagram, conteúdo, restaurante]
    related_skills: [analise-redes, criacao-conteudo, publicacao]
---

# Agenda Semanal de Conteúdo

Use esta skill para montar o calendário editorial completo da semana, definindo horários e tipos de post por dia.

## Quando usar

- Após o Redator entregar o copy da semana
- Quando for necessário replanejar a semana por evento especial

## Etapas

### 1. Receber inputs

- Relatório do Analista (horários de pico, dias fracos)
- Copy completo do Redator (7 posts + 7 stories + 3 carrosséis)
- Prioridades do Diretor de Marketing

### 2. Definir horários por tipo de post

Usar os horários de pico do Analista. Se não houver dados, usar padrão:

| Dia | Feed | Stories | Carrossel |
|-----|------|---------|-----------|
| Segunda | 11:30 | 08:00 | — |
| Terça | 11:30 | 08:00 | 11:30 |
| Quarta | 11:30 | 08:00 | — |
| Quinta | 11:30 | 08:00 | 11:30 |
| Sexta | 11:30 | 08:00 | — |
| Sábado | 10:00 | 09:00 | 10:00 |
| Domingo | 12:00 | 10:00 | — |

### 3. Balancear tipos de conteúdo

A semana deve ter obrigatoriamente:
- Mínimo 1 post de promoção (preferencialmente em dia fraco)
- Mínimo 1 post de bastidores ou processo (humaniza a marca)
- Mínimo 1 post de produto destaque (visual apetitoso)
- Mínimo 1 post com CTA para visita ou delivery

Evitar: dois posts do mesmo tipo em dias consecutivos.

### 4. Montar agenda final

```
AGENDA SEMANAL — [seg DD/MM] a [dom DD/MM]

SEGUNDA [DD/MM]
  09:00 → STORY: [título]
  11:30 → FEED: [título do post]
  Tema: [fidelização|promoção|produto|bastidores|educativo]

TERÇA [DD/MM]
  09:00 → STORY: [título]
  11:30 → CARROSSEL: [título]
  Tema: [...]

[... demais dias ...]

RESUMO DA SEMANA:
  Posts de feed: 7
  Stories: 7
  Carrosséis: 3
  Promoções: [N]
  Pico esperado: [dia] [hora]
```

### 5. Entregar ao Publicador

Passar agenda com todos os arquivos de copy e artes para o Publicador via Paperclip. Confirmar que o Revisor aprovou todos os itens antes de passar.

## Regras

- Nunca agendar post sem copy e arte aprovados pelo Revisor.
- Em feriados, mover posts para o dia anterior ou seguinte.
- Promoções devem sempre ser agendadas com ao menos 24h de antecedência da data da oferta.
