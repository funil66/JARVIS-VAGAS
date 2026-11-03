"""
Obsidian Vault Synchronizer for Job Search & Applications
Gera o Painel Central em PROFISSIONAL/BUSCA_DE_EMPREGO_E_VAGAS/PAINEL_VAGAS_EMPREGO.md
"""
import logging
from datetime import datetime
from pathlib import Path

try:
    from ..config import VAULT_VAGAS_PANEL
    from ..database.repository import VagasRepository
except (ImportError, ValueError):
    from config import VAULT_VAGAS_PANEL
    from database.repository import VagasRepository

logger = logging.getLogger("rpa_vagas.obsidian_sync")

class ObsidianVagasSync:
    def __init__(self, repo: VagasRepository, output_path: Path = VAULT_VAGAS_PANEL):
        self.repo = repo
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def sync(self):
        stats = self.repo.get_stats()
        top_jobs = self.repo.list_jobs(min_score=60, limit=30)
        applied_jobs = self.repo.list_jobs(status="APPLIED", limit=20)

        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        lines = [
            "---",
            'id: "PANEL-VAGAS-CARREIRA"',
            'tipo: "painel"',
            'vertical: "ADVOCACIA"',
            'up: "[[01_ADVOCACIA/_INDEX]]"',
            'status: "ativo"',
            f'data_atualizacao: "{now_str}"',
            "tags:",
            "  - carreira",
            "  - vagas",
            "  - advocacia",
            "  - rpa",
            "---",
            "",
            "# 💼 Painel de Oportunidades & Vagas Jurídicas",
            "",
            "> [!NOTE]",
            f"> **Última sincronização autônoma:** {now_str}  ",
            "> **Candidato:** Profissional Jurídico Sênior (OAB/SP 000.000)  ",
            "> **Preferência Estrita de Modalidade:** 1º Home Office (Remoto) ➔ 2º Híbrido ➔ 3º Presencial",
            "",
            "## 📊 Métricas & Resumo do Pipeline",
            "",
            f"- **Total de Vagas Mapeadas:** `{stats.get('total_vagas', 0)}`",
            f"- **Top Matches (Score ≥ 80%):** `{stats.get('top_matches_80plus', stats.get('high_match_count', 0))}`",
            f"- **Candidaturas Enviadas:** `{stats.get('candidaturas_enviadas', stats.get('total_candidaturas', 0))}`",
            "",
            "### Distribuição por Modalidade:",
        ]

        for mode, count in stats.get("por_modalidade", {}).items():
            badge = "🏠 Remoto" if mode == "REMOTE" else ("🏢/🏠 Híbrido" if mode == "HYBRID" else "🏢 Presencial")
            lines.append(f"- **{badge}:** {count} vagas")

        lines.extend([
            "",
            "---",
            "",
            "## 🌟 Top Oportunidades Selecionadas (Match ≥ 60%)",
            "",
            "| Match | Modalidade | Cargo / Título | Empresa | Plataforma | Link Direto | Status |",
            "| :---: | :---: | :--- | :--- | :---: | :---: | :---: |"
        ])

        if not top_jobs:
            lines.append("| - | - | Nenhuma vaga com score ≥ 60% no momento | - | - | - | - |")
        else:
            for j in top_jobs:
                mode_icon = "🏠 Remoto" if j.work_mode == "REMOTE" else ("🏢/🏠 Híbrido" if j.work_mode == "HYBRID" else "🏢 Presencial")
                score_badge = f"🔥 **{j.match_score}%**" if j.match_score >= 80 else f"{j.match_score}%"
                lines.append(f"| {score_badge} | {mode_icon} | **{j.title}** | {j.company} | {j.platform.upper()} | [Acessar Vaga]({j.url}) | `{j.status}` |")

        if applied_jobs:
            lines.extend([
                "",
                "---",
                "",
                "## 🚀 Candidaturas Realizadas",
                "",
                "| Data | Cargo | Empresa | Modalidade | Match | Status |",
                "| :---: | :--- | :--- | :---: | :---: | :---: |"
            ])
            for a in applied_jobs:
                dt_str = a.applied_at.strftime("%d/%m/%Y %H:%M") if a.applied_at else "Recente"
                lines.append(f"| {dt_str} | {a.title} | {a.company} | {a.work_mode} | {a.match_score}% | `{a.status}` |")

        lines.extend([
            "",
            "---",
            "",
            "## ⚙️ Comandos Rápidos de Execução",
            "",
            "```bash",
            "# Varredura sob demanda de vagas remotas e híbridas",
            "python3 01_ADVOCACIA/05_RPA_Vagas/cli.py search --terms \"Advogado Sênior, Advogado Bancário, Advogado Legal Ops\" --limit 20",
            "",
            "# Avaliar e calcular match de todas as vagas pendentes",
            "python3 01_ADVOCACIA/05_RPA_Vagas/cli.py evaluate --all",
            "",
            "# Executar candidaturas em modo simulação (Dry-Run)",
            "python3 01_ADVOCACIA/05_RPA_Vagas/cli.py apply --min-score 80 --dry-run",
            "",
            "# Iniciar serviço contínuo (Daemon 24/7)",
            "python3 01_ADVOCACIA/05_RPA_Vagas/cli.py daemon --interval-minutes 60",
            "```"
        ])

        content = "\n".join(lines) + "\n"
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Painel Obsidian sincronizado em: {self.output_path}")
        return self.output_path
