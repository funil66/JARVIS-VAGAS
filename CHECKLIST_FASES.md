# 📋 Checklist Operacional de Fases Canônicas: RPA-VAGAS
**Profissional Jurídico Sênior (OAB/SP 000.000)**  
**Manual de Referência:** `GOOGLE-1/03_MICRO_SAAS/PROCEDIMENTO_OFICIAL_PRODUTOS_DEV_FASES_E_CHECKLISTS.md`  
**Fase Atual Homologada:** **Fase 4**

---

### 🔹 Fase 0 — Ideação, PRD & Modelagem de Negócio (Gate 0)
- [x] PRD redigido com proposta única de vendas (USP), persona e fluxos principais (`docs/01_CONCEITO_E_VISAO_DE_PRODUTO.md`).
- [x] Planos e preços definidos com custo de infraestrutura calculado (`docs/02_PLANO_FINANCEIRO_E_REGISTRO_PRECOS.md`).
- [x] Conformidade com LGPD e diretrizes de privacidade registradas.
- [x] Política anti-pirataria e blindagem de propriedade intelectual documentadas.

### 🔹 Fase 1 — Repositório Git Soberano & Governança Fractal (Gate 1)
- [x] Repositório Git dedicado criado no GitHub sob a organização `funil66`.
- [x] Clone local ativo em `/home/candidato/DEV/RPA-VAGAS`.
- [x] `.gitignore` e `.env.example` versionados sem vazamento de segredos.
- [x] Tríade Fractal Canônica implantada (`README.md`, `_INDEX.md`, `_GLOSSARY.md`, `_LOG_ATOS.md`).
- [x] Diretrizes para Agentes IA versionadas em `AGENTS.md`.
- [x] Ponte de governança vinculada no Hub Central `GOOGLE-1/03_MICRO_SAAS/`.

### 🔹 Fase 2 — Arquitetura Técnica, Contratos de API & Schemas (Gate 2)
- [x] Migrations SQL / Schemas DDL versionados e testados.
- [x] Contratos de dados (Pydantic / DTOs) tipados com validação estrita.
- [x] Clean Architecture implementada (`core/`, `adapters/`, `services/`, `tests/`).
- [x] Diagrama de arquitetura e fluxo de dados registrado em `docs/03_ARQUITETURA_DE_SISTEMA_E_ESCALABILIDADE.md`.

### 🔹 Fase 3 — Engenharia do Core, Adaptadores & Idempotência (Gate 3)
- [x] Core algorítmico desacoplado de dependências diretas de persistência ou rede.
- [x] Idempotência implementada em operações críticas e rotinas de escrita.
- [x] Sanitização defensiva contra injeção e payloads corrompidos.
- [x] Logging estruturado em JSON e tratamento gracioso de falhas.

### 🔹 Fase 4 — Suíte de Testes Automatizados & Quality Gate de Segurança (Gate 4)
- [x] Mínimo de testes automatizados cobrindo fluxos felizes e exceções.
- [x] 100% dos testes verdes no runner nativo (`pytest` ou `phpunit`).
- [x] Mocks determinísticos de APIs externas e dependências remotas.
- [x] Auditoria de segurança aprovada: zero tokens, chaves ou senhas no Git.

### 🔹 Fase 5 — Esteira de Monetização, Trava Financeira Pix & Paywall (Gate 5)
- [ ] Emissão de QR Code Pix dinâmico no padrão EMV BACEN com CRC-16.
- [ ] Webhook de pagamento idempotente com validação de assinatura HMAC / Token.
- [ ] Trava Financeira de Produto: recursos liberados apenas após confirmação transacional.
- [ ] Notificação automática de recibo no WhatsApp (Evolution API) ou Telegram.

### 🔹 Fase 6 — Deploy 24/7, Observabilidade & Zero Limbo (Gate 6)
- [ ] Dockerfile multi-stage e `docker-compose.yml` funcionais e testados.
- [ ] Serviço em execução estável sob Docker ou `systemd` (`restart: unless-stopped`).
- [ ] Endpoint de `/health` monitorado 24/7 com alertas de contingência.
- [ ] Encerramento Zero Limbo: `_INDEX.md`, `_LOG_ATOS.md` e Canvas do ecossistema sincronizados.
