---
name: publicacao
description: Publica conteúdo aprovado via Instagram Graph API e Telegram Bot API, confirma publicação e registra no banco.
version: 1.0.0
author: MargemAI
license: MIT
metadata:
  hermes:
    tags: [marketing, instagram, telegram, publicação, api, restaurante]
    related_skills: [analise-redes, criacao-conteudo, agenda-semanal]
---

# Publicação de Conteúdo

Use esta skill para publicar ou agendar conteúdo aprovado no Instagram e no Telegram.

## Quando usar

- Heartbeat semanal de segunda 10:00 (após aprovação do Revisor)
- Quando solicitado para publicação pontual urgente

## Pré-requisito obrigatório

**Nunca publicar sem aprovação do Revisor.** Verificar status de aprovação no Paperclip antes de qualquer publicação.

## Instagram Graph API

### Publicar post de feed (imagem única)

```
POST /me/media
  image_url: [URL da imagem hospedada]
  caption: [legenda completa com hashtags]

POST /me/media_publish
  creation_id: [id retornado acima]
```

### Publicar carrossel

```
# 1. Criar cada slide individualmente
POST /me/media
  image_url: [URL do slide N]
  is_carousel_item: true
→ retorna: carousel_item_id_N

# 2. Criar o container do carrossel
POST /me/media
  media_type: CAROUSEL
  children: [carousel_item_id_1, carousel_item_id_2, ...]
  caption: [legenda]
→ retorna: creation_id

# 3. Publicar
POST /me/media_publish
  creation_id: [id acima]
```

### Agendar post (para publicação futura)

```
POST /me/media
  image_url: [URL]
  caption: [legenda]
  published: false
  scheduled_publish_time: [unix timestamp]
```

Nota: o agendamento via API requer conta Business ou Creator com permissão `instagram_content_publish`.

### Publicar story

```
POST /me/media
  media_type: IMAGE
  image_url: [URL da arte 1080x1920]

POST /me/media_publish
  creation_id: [id]
```

## Telegram Bot API

### Enviar mensagem com imagem

```
POST /bot{TOKEN}/sendPhoto
  chat_id: [id do canal ou grupo]
  photo: [URL ou file_id]
  caption: [texto — máx 1024 caracteres]
  parse_mode: HTML
```

### Enviar mensagem de texto simples

```
POST /bot{TOKEN}/sendMessage
  chat_id: [id]
  text: [texto]
  parse_mode: HTML
```

## Etapas de execução

### 1. Verificar aprovação

Consultar Paperclip: status do conteúdo da semana. Prosseguir apenas se `status === "aprovado"`.

### 2. Publicar ou agendar

Para cada item da agenda (feed, story, carrossel):
- Fazer upload da arte para storage temporário se necessário
- Chamar API correspondente
- Aguardar confirmação de `id` de publicação

### 3. Registrar no banco

Para cada publicação confirmada:
```
INSERT INTO marketing_posts (
  platform, post_type, scheduled_at, published_at,
  instagram_post_id, caption_preview, status
)
```

### 4. Reportar

Após concluir todas as publicações, enviar resumo ao CEO:
```
Marketing da semana agendado:
- X posts de feed
- X stories  
- X carrosséis
Próxima publicação: [dia] às [hora]
Promoção em destaque: [nome] — [data]
```

## Tratamento de erros

| Erro | Ação |
|------|------|
| Rate limit (código 32) | Aguardar 60s e tentar novamente |
| Token expirado (código 190) | Alertar Diretor de Marketing para renovar token |
| Imagem inválida (código 36003) | Devolver ao Designer para reexportar |
| Outro erro | Registrar no Paperclip, alertar Diretor |

Máximo 2 tentativas por publicação antes de escalar para o Diretor.
