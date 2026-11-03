"""
Unit tests for Tier 1 Agent and Telegram HITL components
"""
import pytest
from database.models import JobPosting
from engine.tier1_agent import Tier1JobAgent
from notifications.telegram import TelegramNotifier

@pytest.fixture
def sample_job():
    return JobPosting(
        title="Advogado Sênior Contencioso Bancário e Cível",
        company="Banco Modelo / Advocacia Corporativa",
        location="São Paulo, SP",
        work_mode="REMOTE",
        platform="gupy",
        url="https://empresa-modelo.gupy.io/job/exemplo-123",
        description="Buscamos advogado com experiência em teses bancárias, fraudes PIX e gestão de prazos.",
        match_score=85
    )

def test_tier1_complexity_detection(sample_job):
    agent = Tier1JobAgent()
    
    # Simple form (no dissertations)
    is_complex, reason = agent.analyze_complexity(sample_job, form_questions=[])
    assert is_complex is False

    # Complex form (with dissertations / custom questions)
    is_complex, reason = agent.analyze_complexity(
        sample_job,
        form_questions=["Descreva um caso relevante em fraudes PIX que você conduziu.", "Qual sua pretensão PJ?"]
    )
    assert is_complex is True
    assert "perguntas personalizadas" in reason

def test_tier1_custom_answers_mock(sample_job, monkeypatch):
    agent = Tier1JobAgent()
    
    # Mocking Gemini response for deterministic testing
    def mock_call(prompt, system_instruction=None):
        return '{"Qual sua experiência em contencioso bancário?": "Atuação consolidada em bancos de grande porte como Instituição Financeira Modelo e Instituição Financeira Modelo."}'
    
    monkeypatch.setattr(agent, "_call_gemini", mock_call)
    
    questions = ["Qual sua experiência em contencioso bancário?"]
    answers = agent.answer_custom_questions(sample_job, questions)
    
    assert "Qual sua experiência em contencioso bancário?" in answers
    assert "Instituição Financeira Modelo e Instituição Financeira Modelo" in answers["Qual sua experiência em contencioso bancário?"]

def test_telegram_message_formatting(sample_job):
    notifier = TelegramNotifier()
    assert notifier.bot_token is not None
    assert notifier.chat_id is not None
