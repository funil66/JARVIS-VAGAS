"""
Database repository for RPA Vagas (SQLite with auto-migration and stats)
Unificado e estruturado para suportar o ciclo de vida completo da Gupy.
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from ..config import DB_PATH
    from .models import JobPosting, ApplicationRecord
except (ImportError, ValueError):
    from config import DB_PATH
    from database.models import JobPosting, ApplicationRecord

logger = logging.getLogger("rpa_vagas.database")

class VagasRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS vagas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                external_id TEXT NOT NULL,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                work_mode TEXT DEFAULT 'REMOTE',
                url TEXT NOT NULL,
                description TEXT,
                salary_min REAL,
                salary_max REAL,
                currency TEXT DEFAULT 'BRL',
                seniority TEXT,
                specialties TEXT,
                match_score INTEGER DEFAULT 0,
                match_reasoning TEXT,
                priority TEXT DEFAULT 'LOW',
                status TEXT DEFAULT 'DISCOVERED',
                applied_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(platform, external_id)
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidaturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                application_id TEXT,
                job_name TEXT,
                company TEXT,
                direct_url TEXT,
                application_status TEXT DEFAULT 'in_process',
                current_step INTEGER DEFAULT 0,
                status_esteira TEXT,
                method TEXT DEFAULT 'GUPY_SET_OF_MARK',
                cover_letter TEXT,
                cv_path TEXT,
                response_status TEXT DEFAULT 'SUCCESS',
                response_details TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vagas_status ON vagas(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vagas_match ON vagas(match_score)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vagas_platform ON vagas(platform)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cand_app_id ON candidaturas(application_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cand_status ON candidaturas(application_status)")
            try:
                cursor.execute("ALTER TABLE vagas ADD COLUMN applied_at TIMESTAMP")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def save_job(self, job: JobPosting) -> JobPosting:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute(
                "SELECT id, match_score, status FROM vagas WHERE platform = ? AND external_id = ?",
                (job.platform, job.external_id)
            )
            row = cursor.fetchone()

            if row:
                job.id = row["id"]
                cursor.execute("""
                UPDATE vagas SET
                    title = ?, company = ?, location = ?, work_mode = ?,
                    url = ?, description = ?, updated_at = ?
                WHERE id = ?
                """, (
                    job.title, job.company, job.location, job.work_mode,
                    job.url, job.description, now, job.id
                ))
            else:
                cursor.execute("""
                INSERT INTO vagas (
                    platform, external_id, title, company, location, work_mode,
                    url, description, salary_min, salary_max, currency,
                    match_score, match_reasoning, priority, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.platform, job.external_id, job.title, job.company, job.location, job.work_mode,
                    job.url, job.description, job.salary_min, job.salary_max, job.currency,
                    job.match_score, job.match_reasoning, job.priority, job.status, now, now
                ))
                job.id = cursor.lastrowid

            conn.commit()
            return job

    def get_job(self, job_id: int) -> Optional[JobPosting]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vagas WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            return self._row_to_job(row) if row else None

    def record_application(self, app: ApplicationRecord) -> ApplicationRecord:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("""
            INSERT INTO candidaturas (
                job_id, method, cover_letter, cv_path, response_status, response_details, applied_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                app.job_id, app.method, app.cover_letter, app.cv_path,
                app.response_status, app.response_details, now
            ))
            app.id = cursor.lastrowid
            cursor.execute("UPDATE vagas SET status = 'APPLIED', applied_at = ?, updated_at = ? WHERE id = ?", (now, now, app.job_id))
            conn.commit()
            return app

    def list_jobs(
        self,
        status: Optional[str] = None,
        min_score: Optional[int] = None,
        platform: Optional[str] = None,
        work_mode: Optional[str] = None,
        limit: int = 50
    ) -> List[JobPosting]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM vagas WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)
            if min_score is not None:
                query += " AND match_score >= ?"
                params.append(min_score)
            if platform:
                query += " AND platform = ?"
                params.append(platform)
            if work_mode:
                query += " AND work_mode = ?"
                params.append(work_mode)

            query += " ORDER BY match_score DESC, created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_job(r) for r in rows]

    def update_job_match(self, job_id: int, score: int, reasoning: str, priority: str, status: str = "EVALUATED"):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("""
            UPDATE vagas SET
                match_score = ?, match_reasoning = ?, priority = ?, status = ?, updated_at = ?
            WHERE id = ?
            """, (score, reasoning, priority, status, now, job_id))
            conn.commit()

    def update_job_status(self, job_id: int, status: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("UPDATE vagas SET status = ?, updated_at = ? WHERE id = ?", (status, now, job_id))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT count(*) FROM vagas")
            total_vagas = cursor.fetchone()[0]

            cursor.execute("SELECT count(*) FROM candidaturas")
            total_candidaturas = cursor.fetchone()[0]

            cursor.execute("SELECT count(*) FROM candidaturas WHERE application_status = 'in_process'")
            ativas_gupy = cursor.fetchone()[0]

            cursor.execute("SELECT count(*) FROM vagas WHERE match_score >= 75")
            high_match = cursor.fetchone()[0]

            cursor.execute("SELECT platform, count(*) as c FROM vagas GROUP BY platform")
            by_platform = {r["platform"]: r["c"] for r in cursor.fetchall()}

            cursor.execute("SELECT status, count(*) as c FROM vagas GROUP BY status")
            by_status = {r["status"]: r["c"] for r in cursor.fetchall()}

            cursor.execute("SELECT count(*) FROM vagas WHERE match_score >= 80")
            top_matches_80 = cursor.fetchone()[0]

            cursor.execute("SELECT work_mode, count(*) as c FROM vagas GROUP BY work_mode")
            por_modalidade = {r["work_mode"]: r["c"] for r in cursor.fetchall()}

            return {
                "total_vagas": total_vagas,
                "total_candidaturas": total_candidaturas,
                "candidaturas_ativas_gupy": ativas_gupy,
                "candidaturas_enviadas": total_candidaturas,
                "high_match_count": high_match,
                "top_matches_80plus": top_matches_80,
                "por_modalidade": por_modalidade,
                "by_platform": by_platform,
                "by_status": by_status
            }

    def _row_to_job(self, r: sqlite3.Row) -> JobPosting:
        return JobPosting(
            id=r["id"],
            platform=r["platform"],
            external_id=r["external_id"],
            title=r["title"],
            company=r["company"],
            location=r["location"],
            work_mode=r["work_mode"],
            url=r["url"],
            description=r["description"],
            salary_min=r["salary_min"],
            salary_max=r["salary_max"],
            currency=r["currency"],
            seniority=r["seniority"],
            specialties=r["specialties"].split(",") if r["specialties"] else [],
            match_score=r["match_score"],
            match_reasoning=r["match_reasoning"],
            priority=r["priority"],
            status=r["status"],
            applied_at=datetime.fromisoformat(r["applied_at"]) if ("applied_at" in r.keys() and r["applied_at"]) else None,
            created_at=datetime.fromisoformat(r["created_at"]) if r["created_at"] else None,
            updated_at=datetime.fromisoformat(r["updated_at"]) if r["updated_at"] else None
        )
