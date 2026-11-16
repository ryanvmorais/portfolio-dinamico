# Política de segurança

## Versões suportadas

Só a versão mais recente (a branch `main`) recebe correções de segurança. A demonstração
pública acompanha a `main`.

| Versão | Suportada |
|---|---|
| `main` e a demonstração pública | sim |
| commits anteriores, cópias e forks | não |

## Como reportar uma vulnerabilidade

Reporte **em privado**, pelos avisos de segurança do GitHub: abra a aba **Security and quality** do
repositório e escolha **Report a vulnerability**, ou use o
[link direto](https://github.com/ryanvmorais/portfolio-dinamico/security/advisories/new). Não abra
issue nem pull request públicos para isso.

Inclua o necessário para reproduzir: o commit, os passos, o que você esperava e o que aconteceu, e
o impacto que você enxerga. Teste só numa cópia local do projeto, nunca na demonstração pública.

O objetivo é **confirmar o recebimento em até 7 dias**.

## Política de divulgação

A divulgação é coordenada: a correção é preparada em privado, publicada, e só então o aviso é
divulgado. O prazo-alvo é de no máximo **90 dias** a partir do relato, ou antes se a correção
ficar pronta. O relator recebe o crédito no aviso, a menos que prefira não aparecer.

## Escopo

Este é um portfólio em Django feito como template educacional: uma página pública, um formulário
de contato e o painel Admin. O que cabe aqui é uma falha no código do projeto (views, formulário,
upload de mídia, configurações de segurança), numa dependência ou num workflow do GitHub Actions.

Os limites que as especificações já registram em "Limites conhecidos" (por exemplo, o Admin sem
autenticação em dois fatores) são decisões de escala, não vulnerabilidades. Dúvidas e sugestões
comuns vão pelas [issues](https://github.com/ryanvmorais/portfolio-dinamico/issues).
