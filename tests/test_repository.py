#!/usr/bin/env python3
"""
test_repository.py
Testes unitários do repositório SQLite de vagas e candidaturas.
"""
import sys
import os
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.repository import VagasRepository
from database.models import JobPosting, ApplicationRecord

@pytest.fixture
def temp_repo(tmp_path):
    db_file = tmp_path / "test_vagas.db"
    return VagasRepository(db_path=db_file)

def test_save_and_list_jobs(temp_repo):
    job = JobPosting(
        platform="gupy",
        external_id="ext-12345",
        title="Advogado Sênior Cível",
        company="Escritório Teste",
        location="Remoto",
        work_mode="REMOTE",
        url="https://empresa-modelo.gupy.io/job/exemplo-123",
        description="Descrição detalhada"
    )

    saved = temp_repo.save_job(job)
    assert saved.id is not None
    assert saved.id > 0

    # Retrieve
    retrieved = temp_repo.get_job(saved.id)
    assert retrieved is not None
    assert retrieved.title == "Advogado Sênior Cível"
    assert retrieved.work_mode == "REMOTE"

    # List
    jobs = temp_repo.list_jobs(status="DISCOVERED")
    assert len(jobs) == 1

def test_match_update_and_stats(temp_repo):
    job = JobPosting(
        platform="linkedin",
        external_id="lk-999",
        title="Advogado Legal Ops",
        company="Tech Legal",
        location="Híbrido",
        work_mode="HYBRID",
        url="https://linkedin.com/jobs/999"
    )
    saved = temp_repo.save_job(job)

    temp_repo.update_job_match(saved.id, score=85, reasoning="Alta aderência", priority="ALTA")
    
    updated = temp_repo.get_job(saved.id)
    assert updated.match_score == 85
    assert updated.priority == "ALTA"
    assert updated.status == "EVALUATED"

    # Stats
    stats = temp_repo.get_stats()
    assert stats["total_vagas"] == 1
    assert stats["top_matches_80plus"] == 1

def test_record_application(temp_repo):
    job = JobPosting(
        platform="gupy",
        external_id="gupy-888",
        title="Advogado Trabalhista",
        company="Empresa ABC",
        location="Remoto",
        url="https://gupy.io/888"
    )
    saved = temp_repo.save_job(job)

    app = ApplicationRecord(
        job_id=saved.id,
        method="EMAIL",
        cover_letter="Carta teste",
        cv_path="/caminho/cv.pdf",
        response_status="SUCCESS"
    )
    temp_repo.record_application(app)

    updated = temp_repo.get_job(saved.id)
    assert updated.status == "APPLIED"
    assert updated.applied_at is not None
