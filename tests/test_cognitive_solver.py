import pytest
from engine.cognitive_solver import CognitiveSolver

def test_cognitive_solver_cache_determinism():
    solver = CognitiveSolver()
    q = "Você tem disponibilidade para início imediato?"
    opts = ["Sim, disponibilidade imediata", "Apenas em 30 dias", "Não tenho disponibilidade"]
    
    # Primeira chamada: executa ou pega cache
    res1 = solver.solve(q, field_type="MULTIPLA_ESCOLHA", options=opts)
    assert res1 is not None
    assert "resposta" in res1
    assert res1["resposta"] in opts
    
    # Segunda chamada: deve vir OBRIGATORIAMENTE do cache determinístico
    res2 = solver.solve(q, field_type="MULTIPLA_ESCOLHA", options=opts)
    assert res2["from_cache"] is True
    assert res2["resposta"] == res1["resposta"]


def test_cognitive_solver_choice_resolution():
    solver = CognitiveSolver()
    q = "Qual o seu regime de contratação preferido?"
    opts = ["Apenas Estágio", "CLT ou PJ Sênior / Flexível", "Temporário 1 mês"]
    
    choice = solver.solve_choice(q, opts, vaga_contexto="Advogado Sênior")
    assert choice == "CLT ou PJ Sênior / Flexível"

def test_cognitive_solver_checkboxes_resolution():
    solver = CognitiveSolver()
    sec = "Selecione as áreas de atuação jurídica"
    opts = ["Direito Bancário", "Contencioso Cível Estratégico", "Direito Espacial"]
    
    selected = solver.solve_checkboxes(sec, opts, vaga_contexto="Advogado Bancário")
    assert "Direito Bancário" in selected
    assert "Contencioso Cível Estratégico" in selected
    assert "Direito Espacial" not in selected

def test_cognitive_solver_page_action_decision():
    solver = CognitiveSolver()
    summary = "Formulário preenchido com sucesso. Pronto para a próxima etapa."
    btns = ["Salvar e continuar", "Voltar", "Cancelar"]
    
    decision = solver.decide_page_action(summary, btns, vaga_contexto="Vaga Jurídica")
    assert decision["action"] == "CLICK"
    assert decision["target"] == "Salvar e continuar"
