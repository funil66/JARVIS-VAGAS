---
id: "DOM-01-ADV-05-RPA-VAGAS"
tipo: "sub-camada"
camada_nivel: 2
vertical: "ADVOCACIA"
up: "[[01_ADVOCACIA/_INDEX]]"
status: "ativo"
proximo_passo: "Monitoramento contínuo em segundo plano e disparo automatizado de candidaturas"
drive_path: "PROFISSIONAL/BUSCA_DE_EMPREGO_E_VAGAS"
tags:
  - vertical/advocacia
  - carreira
  - vagas
  - rpa
  - automacao
---

# 🤖 05_RPA_Vagas — Robô Autônomo de Busca de Vagas & Candidaturas Jurídicas

## 🧭 Visão Geral
Módulo autônomo responsável pela varredura multicanal de vagas jurídicas (Advogado Sênior/Pleno, Contencioso Cível, Bancário, Fraudes Digitais, Legal Ops), cálculo determinístico de compatibilidade (Match Score), priorização por regime de trabalho e candidatura automatizada com currículo canônico em PDF.

## 🎯 Hierarquia Estrita de Preferência
1. **1º Prioridade:** Home Office / 100% Remoto (`REMOTE`)
2. **2º Prioridade:** Híbrido (`HYBRID`)
3. **3º Prioridade:** Presencial em São Paulo/Região ou São Paulo (`PRESENTIAL`)

## 🧱 Arquitetura & Componentes
- **`adapters/`**: Scrapers para Gupy Portal, LinkedIn, Indeed Brasil, Glassdoor (`python-jobspy` e Playwright).
- **`engine/`**: Motor de avaliação e match score (`evaluator.py`), gerador de carta de apresentação e despachante de candidaturas (`dispatcher.py`).
- **`database/`**: Repositório SQLite local (`data/rpa_vagas.db`) com histórico completo e rastreabilidade de candidaturas.
- **`notifications/`**: Alertas instantâneos no Telegram para vagas com match alto.
- **`01_ADVOCACIA/02_Agentes_MCP/vagas_carreira.py`**: Ferramentas MCP expostas para o ecossistema de IA.
- **`ObsidianVault/PROFISSIONAL/BUSCA_DE_EMPREGO_E_VAGAS/PAINEL_VAGAS_EMPREGO.md`**: Painel visual dinâmico com links diretos e status.
