---
id: "AGENTS-RPA-VAGAS"
tipo: "ai_governance"
nivel: 2
dominio: "RPA_VAGAS"
status: "ativo"
versao: "1.0.0"
data_revisao: "2026-09-07"
---

# 🤖 Diretrizes para Agentes IA — RPA Vagas & Matching de Carreira

## Contexto
Este repositório implementa o robô autônomo de busca de vagas jurídicas do Profissional Jurídico Sênior (OAB/SP 000.000).

## Regras de Bloqueio
- 🚫 O timer `rpa-vagas.timer` está **deliberadamente pausado** a pedido do titular. Não reativar sem autorização explícita.
- 🚫 Não alterar o `candidate_profile.json` sem conferência com o titular.
- 🚫 Não disparar candidaturas automáticas sem autorização humana de 1 clique.

## Próximo Passo Canônico
Fase 6 — Deploy 24/7: ativar timer systemd quando o titular autorizar retomada.
