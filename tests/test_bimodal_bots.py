import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from bots.hunter import HunterBot
from bots.advancer import AdvancerBot, MAX_ACTIONS_CONTEXT, MAX_STEPS_PER_APPLICATION

def test_hunter_bot_init():
    mock_repo = MagicMock()
    hunter = HunterBot(repo=mock_repo)
    assert hunter.repo == mock_repo
    assert hunter.evaluator is not None
    assert hunter.jobspy is not None
    assert hunter.gupy is not None

def test_hunter_bot_evaluate_pending():
    mock_repo = MagicMock()
    fake_job = MagicMock()
    fake_job.id = 101
    mock_repo.list_jobs.return_value = [fake_job]

    hunter = HunterBot(repo=mock_repo)
    hunter.evaluator.evaluate_job = MagicMock(return_value=(90, "Perfil compatível", "ALTA"))
    hunter.notifier.notify_jobs_digest = MagicMock()
    hunter.obsidian_sync.sync = MagicMock()

    count = hunter.evaluate_pending_jobs(notify_digest=True)
    assert count == 1
    mock_repo.update_job_match.assert_called_once_with(101, 90, "Perfil compatível", "ALTA")
    hunter.notifier.notify_jobs_digest.assert_called_once()
    hunter.obsidian_sync.sync.assert_called_once()

def test_advancer_bot_init():
    advancer = AdvancerBot()
    assert advancer.som_js_path.exists()
    assert advancer.session_mgr is not None
    assert advancer.session_mgr.storage_state_path is not None
    assert isinstance(advancer.session_mgr.storage_state_path, Path)
    script = advancer._read_som_script()
    assert "applySetOfMark" in script
    assert "clearSetOfMark" in script
    assert "som-marker-box" in script

def test_advancer_context_preservation():
    advancer = AdvancerBot()
    advancer.recent_actions.clear()

    # Adiciona 4 ações: deve reter no máximo MAX_ACTIONS_CONTEXT (3)
    advancer.push_action_context("click", 1, "Iniciar Teste", "Avanço etapa")
    advancer.push_action_context("fill", 2, "Experiência", "Preenchimento tempo de advocacia")
    advancer.push_action_context("click", 3, "Salvar", "Confirmação de dados")
    advancer.push_action_context("click", 4, "Avançar", "Transição para próxima tela")

    assert len(advancer.recent_actions) == MAX_ACTIONS_CONTEXT
    # O primeiro elemento deve ser o ID 2 (o ID 1 foi descartado pela janela deslizante)
    assert advancer.recent_actions[0]["bbox_id"] == 2
    assert advancer.recent_actions[1]["bbox_id"] == 3
    assert advancer.recent_actions[2]["bbox_id"] == 4

def test_advancer_modal_dismissal():
    advancer = AdvancerBot()
    mock_page = MagicMock()
    mock_page.query_selector.return_value = None

    bboxes = [
        {"id": 1, "text": "Título da Vaga", "is_dismiss": False, "is_clickable": False, "center_x": 100, "center_y": 100},
        {"id": 2, "text": "Aceitar cookies", "is_dismiss": True, "is_clickable": True, "center_x": 300, "center_y": 600}
    ]
    meta = {"has_modal": True, "has_captcha": False, "modal_dismiss_id": 2}

    dismissed = advancer.dismiss_overlays_if_present(mock_page, bboxes, meta)
    assert dismissed is True
    # Deve ter executado o clique espacial nas coordenadas do botão de aceitar cookies
    mock_page.mouse.click.assert_called_with(300, 600)
    assert len(advancer.recent_actions) > 0
    assert advancer.recent_actions[-1]["action"] == "click_dismiss"

def test_advancer_heuristic_fallback():
    advancer = AdvancerBot()
    bboxes = [
        {"id": 10, "text": "Informações Confidenciais"},
        {"id": 11, "text": "Salvar e continuar"},
        {"id": 12, "text": "Voltar"}
    ]

    decision = advancer._heuristic_fallback_decision(bboxes)
    assert decision["acao"] == "click"
    assert decision["bbox_id"] == 11
    assert "Salvar e continuar" in decision["justificativa"]

def test_advancer_validate_step_anti_hallucination_retry():
    advancer = AdvancerBot()
    mock_page = MagicMock()
    mock_page.query_selector.return_value = None

    bboxes = [
        {"id": 5, "text": "Opção CLT Sênior", "center_x": 200, "center_y": 400}
    ]
    meta = {"has_modal": False, "has_captcha": False, "modal_dismiss_id": None}

    # Primeira resposta alucina bbox_id 999 (inexistente), segunda retorna bbox_id 5 (válido)
    responses = [
        {"acao": "click", "bbox_id": 999, "justificativa": "Alucinação de elemento"},
        {"acao": "click", "bbox_id": 5, "justificativa": "Seleção correta de opção"}
    ]

    with patch.object(advancer, "consult_vlm_decision", side_effect=responses):
        success, result = advancer.validate_and_execute_step(
            page=mock_page,
            bboxes=bboxes,
            meta=meta,
            screenshot_path="dummy.png",
            job_context="Vaga Advogado"
        )

        assert success is True
        assert result in ["CLICK_5", "CLICKED_5"]
        mock_page.mouse.click.assert_called_with(200, 400)

def test_advancer_db_state_persistence(tmp_path):
    import sqlite3
    db_file = tmp_path / "test_vagas.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE candidaturas (
            id INTEGER PRIMARY KEY,
            application_id TEXT,
            current_step INTEGER,
            status_esteira TEXT,
            updated_at TEXT
        );
    """)
    cursor.execute("INSERT INTO candidaturas (application_id, current_step, status_esteira) VALUES ('app-42', 1, 'INICIADO')")
    conn.commit()
    conn.close()

    advancer = AdvancerBot(db_path=db_file)
    advancer._update_candidatura_db(application_id="app-42", step=3, status_esteira="ETAPA_3_CLICK_10")

    conn = sqlite3.connect(db_file)
    row = conn.cursor().execute("SELECT current_step, status_esteira FROM candidaturas WHERE application_id = 'app-42'").fetchone()
    conn.close()

    assert row[0] == 3
    assert row[1] == "ETAPA_3_CLICK_10"

