---
name: entrada-nota
description: Recebe nota fiscal por foto, XML, PDF, texto ou voz e salva no banco
triggers:
  - nota
  - compra
  - invoice
  - comprei
  - gastei
---

# Entrada de Nota Fiscal

## Quando usar
- Usuário envia foto de nota
- Usuário envia arquivo XML ou PDF
- Usuário descreve uma compra por texto ou voz
- "Comprei 10kg de frango a R$ 22"

## Como agir
1. Identificar tipo de entrada: foto, XML, PDF ou texto
2. Extrair dados:
   - Fornecedor
   - Data da compra
   - Itens, quantidades e preços
3. Confirmar com usuário antes de salvar:
   "Entendi: 10kg frango a R$22 no Frigorífico X. Confirma?"
4. Salvar no banco após confirmação
5. Informar impacto no CMV se houver variação de preço

## Tom
- Confirmar antes de salvar sempre
- Mostrar resumo claro do que foi entendido
- Se não entender algum item, perguntar
- Nunca inventar fornecedor ou preço
