---
name: entrada-nota
description: Recebe nota fiscal por foto, XML NF-e, PDF ou texto/voz. Extrai itens, quantidades, preços, fornecedor e data. Confirma com o usuário antes de salvar no banco.
version: 1.0.0
author: MargemAI
license: MIT
metadata:
  hermes:
    tags: [nota-fiscal, nfe, ocr, compras, entrada, fornecedor, cmv]
    related_skills: [compras, calcular-cmv]
---

# Entrada de Nota Fiscal

Use esta skill quando o usuário enviar uma nota fiscal em qualquer formato. O objetivo é extrair os dados com precisão, confirmar com o usuário e salvar no banco do Paperclip.

## Formatos aceitos

| Formato | Como processar |
|---------|---------------|
| Foto (JPG/PNG) | OCR via Claude Vision — ler imagem e extrair campos |
| XML NF-e | Parsear campos padrão NF-e brasileiro |
| PDF | Extrair texto e identificar campos estruturados |
| Texto digitado | Interpretar linguagem natural ("comprei 5kg de frango a R$12") |
| Voz transcrita | Mesmo fluxo do texto após transcrição |

## Campos a extrair

Obrigatórios:
- `fornecedor`: nome do fornecedor
- `data`: data da nota ou da compra
- `itens`: lista com nome, quantidade, unidade, preço unitário, preço total

Opcionais (extrair se disponíveis):
- `numero_nota`: número da NF
- `chave_nfe`: chave de acesso NF-e (44 dígitos)
- `cnpj_fornecedor`
- `valor_total`

## Fluxo de processamento

### Passo 1 — Extrair

Para foto/PDF:
```
Usar Claude Vision ou extração de texto.
Identificar todos os itens visíveis.
Normalizar unidades: "Kg", "KG", "quilos" → "kg"
Normalizar preços: remover R$, vírgula → ponto decimal
```

Para XML NF-e:
```
Parsear <det> para cada item:
  xProd → nome do produto
  qCom → quantidade comercial
  uCom → unidade
  vUnCom → valor unitário
  vProd → valor total do item
Parsear <emit><xNome> → fornecedor
Parsear <ide><dEmi> → data
```

### Passo 2 — Confirmar com o usuário

SEMPRE mostrar resumo antes de salvar:

```
Encontrei na nota:
Fornecedor: [nome]
Data: [data]

Itens:
• [item 1] — [qtd] [unidade] × R$[preço] = R$[total]
• [item 2] — [qtd] [unidade] × R$[preço] = R$[total]
...

Total: R$[valor]

Está correto? Posso salvar. Se quiser corrigir algo, me diga.
```

Aguardar confirmação explícita ("sim", "pode salvar", "ok") antes de persistir.

### Passo 3 — Salvar no banco

Após confirmação:
- Criar registro de compra com todos os itens
- Vincular ao fornecedor (criar se não existir)
- Atualizar histórico de preços por insumo
- Disparar verificação de variação de preço (skill `compras`)

### Passo 4 — Confirmar salvamento

```
Salvo! 
[N] itens registrados de [fornecedor] — [data].
Custo total: R$[valor].
```

## Tratamento de erros

- **Campo ilegível**: perguntar ao usuário especificamente o que não foi possível ler
- **Quantidade ambígua**: confirmar unidade ("é kg ou unidade?")
- **Fornecedor desconhecido**: perguntar se quer cadastrar como novo
- **Nota duplicada**: alertar "Já existe uma nota similar de [fornecedor] em [data]. Quer salvar mesmo assim?"

## Regras

- Nunca salvar sem confirmação do usuário.
- Nunca inventar campos que não estão na nota.
- Se a imagem estiver ilegível, pedir foto melhor em vez de adivinhar.
