"""
Seed Gupy Candidaturas into SQLite from candidaturas_gupy_completas.json
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import DB_PATH
from database.repository import VagasRepository

JSON_PATH = ROOT_DIR / "data" / "candidaturas_exemplo.json"

def seed():
    repo = VagasRepository(DB_PATH)
    if not JSON_PATH.exists():
        print(f"Arquivo {JSON_PATH} não encontrado.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    count = 0
    for item in data:
        app_id = str(item.get("applicationId"))
        job_name = item.get("jobName") or "Advogado"
        company = item.get("careerPageName") or "Gupy Enterprise"
        status = item.get("applicationStatus") or "in_process"
        subdomain = item.get("careerPageSubdomain")
        direct_url = f"https://{subdomain}.gupy.io/candidates/applications/{app_id}" if subdomain else f"https://portal.gupy.io/candidates/applications/{app_id}"

        cursor.execute("SELECT id FROM candidaturas WHERE application_id = ?", (app_id,))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO candidaturas (
                application_id, job_name, company, direct_url, application_status,
                current_step, status_esteira, method, applied_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (app_id, job_name, company, direct_url, status, 0, "IMPORTADO_JSON", "GUPY_PORTAL"))
            count += 1

    conn.commit()
    conn.close()
    print(f"Importação concluída: {count} novas candidaturas Gupy inseridas em {DB_PATH}.")

if __name__ == "__main__":
    seed()
