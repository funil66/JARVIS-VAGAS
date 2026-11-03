#!/usr/bin/env python3
"""
test_evaluator.py
Testes unitários do motor de compatibilidade e matching de vagas.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.models import JobPosting
from engine.evaluator import JobEvaluator

def test_remote_lawyer_job_scoring():
    evaluator = JobEvaluator()
    job = JobPosting(
        title="Advogado Sênior Contencioso Cível e Bancário",
        company="Banco XPTO",
        location="Brasil (100% Home Office)",
        work_mode="REMOTE",
        description="Vaga para Advogado Sênior com sólida experiência em defesas de fraudes do PIX e contencioso cível bancário. Atuação 100% remota."
    )

    score, reasoning, priority = evaluator.evaluate_job(job)
    assert score >= 75
    assert priority == "ALTA"
    assert "Modalidade Remota" in reasoning
    assert "Bancário" in reasoning

def test_hybrid_vs_presential_scoring():
    evaluator = JobEvaluator()
    job_hybrid = JobPosting(
        title="Advogado Pleno - Contratos",
        company="Empresa ABC",
        location="São Paulo - SP",
        work_mode="HYBRID",
        description="Contratos civis e comerciais. Modelo híbrido."
    )
    score_h, _, _ = evaluator.evaluate_job(job_hybrid)

    job_presential = JobPosting(
        title="Advogado Pleno - Contratos",
        company="Empresa ABC",
        location="Curitiba - PR",
        work_mode="PRESENTIAL",
        description="Contratos civis. Presencial em Curitiba."
    )
    score_p, _, _ = evaluator.evaluate_job(job_presential)

    # Remote/Hybrid should score significantly higher than distant presential
    assert score_h > score_p

def test_cover_letter_generation():
    evaluator = JobEvaluator()
    job = JobPosting(
        title="Advogado Bancário e Fraudes Digitais",
        company="Banca de Advogados Associados",
        location="Remoto",
        work_mode="REMOTE",
        description="Defesa em fraudes bancárias e Legal Ops."
    )

    letter = evaluator.generate_cover_letter(job)
    assert "Candidato Jurídico" in letter
    assert "OAB/SP 000.000" in letter
    assert "Banca de Advogados Associados" in letter
    assert "fraudes digitais" in letter
