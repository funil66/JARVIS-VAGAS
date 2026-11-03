"""
RPA-Hunter (Bot 1: Descoberta e Triagem de Vagas na Gupy)
Isola o ciclo de vida de hunting exclusivo no Portal Gupy,
avaliação de aderência com perfil profissional do Candidato Modelo (OAB/SP 000.000)
e persistência soberana na base de dados (SQLite).
"""
import logging
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent

try:
    from database.repository import VagasRepository
    from database.models import JobPosting
    from adapters.gupy_adapter import GupyAdapter
    from engine.evaluator import JobEvaluator
    from engine.obsidian_sync import ObsidianVagasSync
    from notifications.telegram import TelegramNotifier
    from config import DEFAULT_SEARCH_TERMS, MIN_MATCH_SCORE_TO_NOTIFY
except ImportError:
    from ..database.repository import VagasRepository
    from ..database.models import JobPosting
    from ..adapters.gupy_adapter import GupyAdapter
    from ..engine.evaluator import JobEvaluator
    from ..engine.obsidian_sync import ObsidianVagasSync
    from ..notifications.telegram import TelegramNotifier
    from ..config import DEFAULT_SEARCH_TERMS, MIN_MATCH_SCORE_TO_NOTIFY

logger = logging.getLogger("rpa_vagas.bots.hunter")

class HunterBot:
    def __init__(self, repo: Optional[VagasRepository] = None):
        self.repo = repo or VagasRepository()
        self.evaluator = JobEvaluator()
        self.obsidian_sync = ObsidianVagasSync(self.repo)
        self.notifier = TelegramNotifier()
        self.gupy = GupyAdapter()
        self.jobspy = self.gupy

    def discover_jobs(
        self,
        terms: Optional[List[str]] = None,
        location: str = "Brasil",
        limit_per_source: int = 15,
        platforms: Optional[List[str]] = None
    ) -> List[JobPosting]:
        search_terms = terms or DEFAULT_SEARCH_TERMS
        found_jobs: List[JobPosting] = []

        logger.info(f"[HUNTER GUPY] Iniciando varredura para {len(search_terms)} termos exclusivamente no Portal Gupy...")

        for term in search_terms:
            try:
                g_jobs = self.gupy.search_jobs(search_term=term, location=location, limit=limit_per_source)
                for j in g_jobs:
                    saved = self.repo.save_job(j)
                    found_jobs.append(saved)
            except Exception as e:
                logger.error(f"[HUNTER GUPY] Erro ao buscar '{term}' na Gupy: {e}")

        evaluated = self.evaluate_pending_jobs(notify_digest=True)
        logger.info(f"[HUNTER GUPY] Descoberta concluída: {len(found_jobs)} vagas capturadas, {evaluated} avaliadas.")
        return found_jobs

    def evaluate_pending_jobs(self, notify_digest: bool = True) -> int:
        pending = self.repo.list_jobs(status="DISCOVERED", limit=200)
        evaluated_count = 0
        qualified_jobs = []

        for job in pending:
            score, reasoning, priority = self.evaluator.evaluate_job(job)
            self.repo.update_job_match(job.id, score, reasoning, priority)
            job.match_score = score
            job.match_reasoning = reasoning
            job.priority = priority

            if score >= MIN_MATCH_SCORE_TO_NOTIFY:
                qualified_jobs.append(job)

            evaluated_count += 1

        if notify_digest and qualified_jobs:
            self.notifier.notify_jobs_digest(qualified_jobs)

        if evaluated_count > 0:
            self.obsidian_sync.sync()

        return evaluated_count
