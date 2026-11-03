"""
Orchestrator for Job Search, Evaluation and Application Pipeline
"""
import logging
from typing import List, Optional, Dict, Any

try:
    from ..config import DEFAULT_SEARCH_TERMS, DEFAULT_PLATFORMS, MIN_MATCH_SCORE_TO_APPLY, MIN_MATCH_SCORE_TO_NOTIFY
    from ..database.repository import VagasRepository
    from ..database.models import JobPosting, ApplicationRecord
    from ..adapters.jobspy_adapter import JobSpyAdapter
    from ..adapters.gupy_adapter import GupyAdapter
    from ..browser.applicator import FormApplicator
    from .evaluator import JobEvaluator
    from .dispatcher import ApplicationDispatcher
    from .obsidian_sync import ObsidianVagasSync
    from ..notifications.telegram import TelegramNotifier
except (ImportError, ValueError):
    from config import DEFAULT_SEARCH_TERMS, DEFAULT_PLATFORMS, MIN_MATCH_SCORE_TO_APPLY, MIN_MATCH_SCORE_TO_NOTIFY
    from database.repository import VagasRepository
    from database.models import JobPosting, ApplicationRecord
    from adapters.jobspy_adapter import JobSpyAdapter
    from adapters.gupy_adapter import GupyAdapter
    from browser.applicator import FormApplicator
    from engine.evaluator import JobEvaluator
    from engine.dispatcher import ApplicationDispatcher
    from engine.obsidian_sync import ObsidianVagasSync
    from notifications.telegram import TelegramNotifier

logger = logging.getLogger("rpa_vagas.orchestrator")

class VagasOrchestrator:
    def __init__(self, repo: Optional[VagasRepository] = None):
        self.repo = repo or VagasRepository()
        self.evaluator = JobEvaluator()
        self.dispatcher = ApplicationDispatcher()
        self.applicator = FormApplicator()
        self.obsidian_sync = ObsidianVagasSync(self.repo)
        self.notifier = TelegramNotifier()
        self.jobspy = JobSpyAdapter()
        self.gupy = GupyAdapter()

    def run_search(
        self,
        terms: Optional[List[str]] = None,
        location: str = "Brasil",
        limit_per_source: int = 15,
        platforms: Optional[List[str]] = None
    ) -> List[JobPosting]:
        search_terms = terms or DEFAULT_SEARCH_TERMS
        target_platforms = platforms or DEFAULT_PLATFORMS
        found_jobs: List[JobPosting] = []

        logger.info(f"Iniciando busca para {len(search_terms)} termos nas plataformas: {target_platforms}")

        for term in search_terms:
            # 1. Gupy Portal
            if "gupy" in target_platforms:
                try:
                    g_jobs = self.gupy.search_jobs(search_term=term, location=location, limit=limit_per_source)
                    for j in g_jobs:
                        saved = self.repo.save_job(j)
                        found_jobs.append(saved)
                except Exception as e:
                    logger.error(f"Erro ao buscar '{term}' no Gupy: {e}")

            # 2. JobSpy (LinkedIn, Indeed, Glassdoor)
            jobspy_sites = [p for p in target_platforms if p in ["linkedin", "indeed", "glassdoor", "zip_recruiter"]]
            if jobspy_sites:
                try:
                    js_jobs = self.jobspy.search_jobs(
                        search_term=term,
                        location=location,
                        limit=limit_per_source
                    )
                    for j in js_jobs:
                        saved = self.repo.save_job(j)
                        found_jobs.append(saved)
                except Exception as e:
                    logger.error(f"Erro ao buscar '{term}' no JobSpy: {e}")

        # Avaliar automaticamente as novas vagas
        self.evaluate_pending_jobs()
        self.obsidian_sync.sync()

        return found_jobs

    def evaluate_pending_jobs(self, notify_digest: bool = False) -> int:
        pending = self.repo.list_jobs(status="DISCOVERED", limit=200)
        evaluated_count = 0
        qualified_jobs = []

        for job in pending:
            score, reasoning, priority = self.evaluator.evaluate_job(job)
            self.repo.update_job_match(job.id, score, reasoning, priority)
            job.match_score = score
            job.match_reasoning = reasoning
            job.priority = priority

            # Agrupa qualificadas para digest consolidado (elimina spam individual)
            if score >= MIN_MATCH_SCORE_TO_NOTIFY:
                qualified_jobs.append(job)

            evaluated_count += 1

        # Envia no máximo 1 resumo consolidado para todo o lote se expressamente solicitado
        if notify_digest and qualified_jobs:
            self.notifier.notify_jobs_digest(qualified_jobs)

        if evaluated_count > 0:
            self.obsidian_sync.sync()

        return evaluated_count

    def apply_to_top_jobs(
        self,
        min_score: int = MIN_MATCH_SCORE_TO_APPLY,
        dry_run: bool = True,
        max_applications: int = 5,
        allow_hitl: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Aplica para as melhores vagas que ainda não receberam candidatura.
        Utiliza despacho por e-mail quando disponível ou preenchimento web com Playwright + HITL.
        """
        candidates = self.repo.list_jobs(status="EVALUATED", min_score=min_score, limit=max_applications)
        results = []

        for job in candidates:
            cover_letter = self.evaluator.generate_cover_letter(job)
            email = self.dispatcher.extract_email_from_job(job)

            if email:
                success, details = self.dispatcher.dispatch_email_application(job, email, dry_run=dry_run)
                method = "EMAIL"
            else:
                # Disparo com Playwright + Tier 1 + Human-in-the-Loop
                success, details = self.applicator.fill_and_apply(
                    job=job,
                    cover_letter=cover_letter,
                    dry_run=dry_run,
                    allow_hitl=allow_hitl
                )
                method = "WEB_PLAYWRIGHT_HITL"

            if success:
                record = ApplicationRecord(
                    job_id=job.id,
                    method=method,
                    cover_letter=cover_letter,
                    cv_path=str(self.dispatcher.cv_path),
                    response_status="SUCCESS" if not dry_run else "DRY_RUN",
                    response_details=details
                )
                self.repo.record_application(record)
                if not dry_run:
                    self.notifier.notify_application_sent(job, method, notes=details)

            results.append({
                "job_id": job.id,
                "title": job.title,
                "company": job.company,
                "score": job.match_score,
                "method": method,
                "status": "SUCCESS" if success else "FAILED",
                "details": details
            })

        self.obsidian_sync.sync()
        return results
