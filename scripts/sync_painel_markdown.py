#!/usr/bin/env python3
"""
Sincroniza o banco de dados refatorado rpa_vagas.db com o painel de governança
05_PESSOAL/04_Carreira_e_Vagas/ACOMPANHAMENTO_FASES_SELETIVAS.md.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "rpa_vagas.db"
MD_PATH = ROOT_DIR / "docs" / "ACOMPANHAMENTO_FASES_SELETIVAS.md"

def sync():
    if not DB_PATH.exists():
        print(f"Banco não encontrado: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Contagens gerais
    cursor.execute("SELECT COUNT(*) FROM candidaturas")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM candidaturas WHERE application_status = 'in_process'")
    ativas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM candidaturas WHERE application_status = 'in_process' AND workplace_type = 'remote'")
    remoto = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM candidaturas WHERE application_status = 'in_process' AND workplace_type = 'hybrid'")
    hibrido = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM candidaturas WHERE application_status = 'in_process' AND workplace_type = 'on-site'")
    presencial = cursor.fetchone()[0]

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    md_content = f"""# 🏛️ Painel de Acompanhamento de Fases de Processos Seletivos

**Data da Auditoria:** {now_str} **Candidato:** Profissional Jurídico Sênior (OAB/SP 000.000)
**Total Histórico de Candidaturas:** {total} submissões | **Processos Ativos em Andamento:** {ativas} processos

- 🏠 **100% Remoto (Home Office):** {remoto} vagas ativas
- 🏢/🏠 **Híbrido:** {hibrido} vagas ativas
- 🏢 **Presencial:** {presencial} vagas ativas

---

## 🏆 1. Candidaturas Ativas — 100% Remoto (Foco Prioritário Brasil)

| ID Candidatura | Vaga | Empresa / Banca | Etapa Atual | Status Esteira | Acesso Direto |
|:---|:---|:---|:---|:---|:---|
"""
    # Buscar vagas remotas ativas
    cursor.execute("""
        SELECT application_id, job_name, company, current_step, total_steps, status_esteira, direct_url
        FROM candidaturas
        WHERE application_status = 'in_process' AND workplace_type = 'remote'
        ORDER BY id DESC
    """)
    for r in cursor.fetchall():
        app_id, job, comp, cur_s, tot_s, status_est, url = r
        step_str = f"Fase {cur_s} de {tot_s}" if tot_s > 0 else "Inscrição"
        md_content += f"| {app_id} | **{job}** | {comp} | {step_str} | `{status_est}` | [Acessar]({url}) |\n"

    md_content += """\n---\n\n## 🏢 2. Candidaturas Ativas — Híbrido & Presencial\n\n| ID Candidatura | Vaga | Empresa / Banca | Modalidade | Etapa Atual | Status Esteira | Acesso Direto |\n|:---|:---|:---|:---|:---|:---|:---|\n"""

    cursor.execute("""
        SELECT application_id, job_name, company, workplace_type, current_step, total_steps, status_esteira, direct_url
        FROM candidaturas
        WHERE application_status = 'in_process' AND workplace_type != 'remote'
        ORDER BY id DESC
    """)
    for r in cursor.fetchall():
        app_id, job, comp, wtype, cur_s, tot_s, status_est, url = r
        step_str = f"Fase {cur_s} de {tot_s}" if tot_s > 0 else "Inscrição"
        mod_label = "Híbrido" if wtype == "hybrid" else "Presencial"
        md_content += f"| {app_id} | **{job}** | {comp} | {mod_label} | {step_str} | `{status_est}` | [Acessar]({url}) |\n"

    conn.close()

    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Painel sincronizado com sucesso: {MD_PATH}")

if __name__ == "__main__":
    sync()
