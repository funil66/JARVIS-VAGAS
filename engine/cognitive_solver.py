#!/usr/bin/env python3
"""
Motor Cognitivo Soberano de Resolução de Perguntas, Questionários e Ações de Esteira (RPA-Vagas).
Arquitetura Canônica JARVIS:
- Gateway Primário: 9Router Master (:20128) via OpenAI API compatível (RTK Token Saver & Multi-Model).
- Fallback Secundário: Google GenAI SDK direto (caso o 9Router local esteja inacessível).
- Cache Determinístico: SQLite com hash SHA-256 para idempotência e consumo zero tokens em repetições.
- Persona Forense: Profissional Jurídico Sênior (OAB/SP 000.000).
"""
import os
import sys
import json
import hashlib
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("rpa_vagas.engine.cognitive_solver")

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "rpa_vagas.db"
PROFILE_PATH = ROOT_DIR / "candidate_profile.json"

try:
    from config import ROUTER_BASE_URL, ROUTER_API_KEY, ROUTER_MODEL, ROUTER_COMPLEX_MODEL
except ImportError:
    ROUTER_BASE_URL = os.getenv("ROUTER_BASE_URL", "http://127.0.0.1:20128/v1")
    ROUTER_API_KEY = os.getenv("ROUTER_API_KEY", "")
    ROUTER_MODEL = os.getenv("ROUTER_MODEL", "ag/gemini-3-flash")
    ROUTER_COMPLEX_MODEL = os.getenv("ROUTER_COMPLEX_MODEL", "ag/gemini-3.8-flash")

SYSTEM_PERSONA_PROMPT = """
Você é o co-piloto e alter-ego profissional do candidato.
Sua missão é responder a formulários, questionários de candidatura e decidir ações na esteira de vagas.

DIRETRIZES FUNDAMENTAIS DO CANDIDATO:
1. Perfil Profissional: Advogado Sênior / Especialista em Direito Bancário, Contencioso Cível Estratégico e Massivo, Recuperação de Crédito, Fraudes Digitais e Legal Operations (Legal Ops).
2. Competências-chave: Condução de carteiras de milhares de processos bancários, elaboração de peças de alta complexidade, audiências, gestão de contingências, conciliação e automações jurídicas.
3. Pretensão Salarial: Faixas de nível sênior (A combinar conforme modelo PJ/CLT).
4. Disponibilidade: Imediata ou integral, aberto a modelos 100% Remoto ou Híbrido flexível.
5. Em perguntas de múltipla escolha ou checkboxes: Selecionar as opções que demonstram alta qualificação, ampla experiência, disponibilidade integral e conformidade com os termos da vaga.
6. Em dissertações abertas: Redigir na 1ª pessoa, tom executivo e forense impecável, demonstrando autoridade técnica, foco em resultados e mitigação de risco.
7. NUNCA mencione ser uma IA, modelo de linguagem ou bot. Você É o próprio Candidato Modelo.
"""

class CognitiveSolver:
    def __init__(self, db_path: Optional[Path] = None, profile_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.profile_path = profile_path or PROFILE_PATH
        self.router_base_url = ROUTER_BASE_URL
        self.router_api_key = ROUTER_API_KEY
        self.primary_model = ROUTER_MODEL
        self.complex_model = ROUTER_COMPLEX_MODEL
        self.profile = self._load_profile()

        self.router_client = None
        self.genai_client = None
        self._init_db()
        self._init_clients()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questionarios_respostas_cache (
                hash_pergunta TEXT PRIMARY KEY,
                texto_pergunta TEXT,
                tipo_campo TEXT,
                opcoes_disponiveis TEXT,
                resposta_escolhida TEXT,
                justificativa_ia TEXT,
                modelo_ia TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _load_profile(self) -> Dict[str, Any]:
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[COGNITIVE] Erro ao carregar perfil: {e}")
        return {
            "name": "Profissional Jurídico Sênior",
            "oab": "OAB/SP 000.000",
            "title": "Advogado Sênior / Especialista em Contencioso & Legal Ops",
            "location": "São Paulo - SP / Remoto Brasil"
        }

    def _init_clients(self):
        try:
            from openai import OpenAI
            self.router_client = OpenAI(
                base_url=self.router_base_url,
                api_key=self.router_api_key,
                timeout=35.0
            )
            logger.info(f"[COGNITIVE] 9Router Gateway conectado com sucesso ({self.router_base_url}).")
        except Exception as e:
            logger.warning(f"[COGNITIVE] Falha ao inicializar cliente 9Router: {e}")
            self.router_client = None

        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                from google import genai
                self.genai_client = genai.Client(api_key=gemini_key)
                logger.info("[COGNITIVE] Fallback secundário Google GenAI ativo.")
            except Exception as e:
                logger.debug(f"[COGNITIVE] Google GenAI indisponível: {e}")
                self.genai_client = None

    def _hash_question(self, question_text: str, options: Optional[List[str]] = None) -> str:
        base = question_text.strip().lower()
        if options:
            base += "|" + "|".join(sorted([o.strip().lower() for o in options]))
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def get_cached_answer(self, question_hash: str) -> Optional[Dict[str, Any]]:
        if not self.db_path.exists():
            return None
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT resposta_escolhida, justificativa_ia, modelo_ia 
            FROM questionarios_respostas_cache 
            WHERE hash_pergunta = ?
        """, (question_hash,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "resposta": row[0],
                "justificativa": row[1],
                "modelo": row[2],
                "from_cache": True
            }
        return None

    def save_cached_answer(self, question_hash: str, text: str, field_type: str, 
                           options: Optional[List[str]], answer: str, 
                           justification: str, model_name: str):
        if not self.db_path.exists():
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO questionarios_respostas_cache 
            (hash_pergunta, texto_pergunta, tipo_campo, opcoes_disponiveis, resposta_escolhida, justificativa_ia, modelo_ia)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            question_hash,
            text,
            field_type,
            json.dumps(options, ensure_ascii=False) if options else None,
            answer,
            justification,
            model_name
        ))
        conn.commit()
        conn.close()

    def _clean_json(self, raw: str) -> str:
        if not raw:
            return ""
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def _call_9router(self, prompt: str, model_name: str, json_mode: bool = True) -> Optional[str]:
        if not self.router_client:
            return None
        try:
            kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": SYSTEM_PERSONA_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            completion = self.router_client.chat.completions.create(**kwargs)
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"[COGNITIVE] 9Router falhou com {model_name}: {e}")
            return None

    def _call_genai_fallback(self, prompt: str, model_name: str) -> Optional[str]:
        if not self.genai_client:
            return None
        try:
            resp = self.genai_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return resp.text.strip()
        except Exception as e:
            logger.warning(f"[COGNITIVE] Fallback GenAI falhou com {model_name}: {e}")
            return None

    def solve(self, question_text: str, field_type: str = "MULTIPLA_ESCOLHA", 
              options: Optional[List[str]] = None, vaga_contexto: str = "") -> Dict[str, Any]:
        q_hash = self._hash_question(question_text, options)
        cached = self.get_cached_answer(q_hash)
        if cached:
            logger.info(f"[COGNITIVE] Pergunta resolvida via cache: {question_text[:50]}...")
            return cached

        is_complex = field_type in ["DISSERTATIVA", "CASE_JURIDICO", "TEXTAREA_LONGO"] or len(question_text) > 250
        preferred_model = self.complex_model if is_complex else self.primary_model
        candidate_models = [preferred_model, "ag/gemini-3-flash", "ag/gemini-3.8-flash"]

        prompt = f"CONTEXTO DA VAGA: {vaga_contexto or 'Vaga Jurídica / Corporativa'}\nTIPO DE CAMPO: {field_type}\n\nPERGUNTA:\n{question_text}\n"
        if options:
            opts_str = "\n".join([f"- {opt}" for opt in options])
            prompt += f"\nOPÇÕES DISPONÍVEIS:\n{opts_str}\n\nInstrução: Escolha exatamente uma das opções disponíveis que melhor represente o candidato Candidato Modelo. Responda estritamente no formato JSON: {{\"resposta\": \"<texto exato da opcao>\", \"justificativa\": \"<breve motivo>\"}}"
        else:
            prompt += "\n\nInstrução: Redija uma resposta ideal e persuasiva na 1ª pessoa no padrão formal e executivo do Candidato Modelo. Responda estritamente no formato JSON: {{\"resposta\": \"<texto completo da resposta>\", \"justificativa\": \"<breve motivo>\"}}"

        for m in candidate_models:
            raw = self._call_9router(prompt, m, json_mode=True)
            if raw:
                try:
                    data = json.loads(self._clean_json(raw))
                    ans = data.get("resposta", "")
                    just = data.get("justificativa", "")
                    if ans:
                        self.save_cached_answer(q_hash, question_text, field_type, options, ans, just, f"9router:{m}")
                        return {"resposta": ans, "justificativa": just, "modelo": f"9router:{m}", "from_cache": False}
                except Exception as je:
                    logger.warning(f"[COGNITIVE] Erro parse JSON 9Router: {je}")

        for gm in ["gemini-2.5-flash", "gemini-flash-latest"]:
            raw_gen = self._call_genai_fallback(prompt, gm)
            if raw_gen:
                try:
                    data = json.loads(self._clean_json(raw_gen))
                    ans = data.get("resposta", "")
                    just = data.get("justificativa", "")
                    if ans:
                        self.save_cached_answer(q_hash, question_text, field_type, options, ans, just, f"genai:{gm}")
                        return {"resposta": ans, "justificativa": just, "modelo": f"genai:{gm}", "from_cache": False}
                except Exception:
                    pass

        fallback_ans = options[0] if options else "Disponível para detalhar histórico em entrevista técnica."
        if options:
            preferred_keywords = ["sênior", "pleno", "flexível", "imediato", "imediata", "sim", "clt ou pj", "remoto", "híbrido"]
            for opt in options:
                opt_lower = opt.lower()
                if any(kw in opt_lower for kw in preferred_keywords):
                    fallback_ans = opt
                    break
        self.save_cached_answer(q_hash, question_text, field_type, options, fallback_ans, "Inferência de contingência.", "fallback_offline")
        return {
            "resposta": fallback_ans,
            "justificativa": "Inferência de contingência.",
            "modelo": "fallback_offline",
            "from_cache": False
        }

    def solve_choice(self, question_text: str, options: List[str], vaga_contexto: str = "") -> str:
        if not options:
            return ""
        if len(options) == 1:
            return options[0]
        res = self.solve(question_text, field_type="MULTIPLA_ESCOLHA", options=options, vaga_contexto=vaga_contexto)
        chosen = res.get("resposta", "")
        for opt in options:
            if opt.strip().lower() == chosen.strip().lower():
                return opt
        for opt in options:
            if chosen.strip().lower() in opt.strip().lower() or opt.strip().lower() in chosen.strip().lower():
                return opt
        return options[0]

    def solve_checkboxes(self, section_title: str, checkbox_options: List[str], vaga_contexto: str = "") -> List[str]:
        if not checkbox_options:
            return []

        opts_formatted = "\n".join([f"- {opt}" for opt in checkbox_options])
        prompt = (
            f"CONTEXTO DA VAGA: {vaga_contexto or 'Vaga Jurídica'}\n"
            f"SEÇÃO / PERGUNTA:\n{section_title}\n\n"
            f"CHECKBOXES DISPONÍVEIS:\n{opts_formatted}\n\n"
            "Instrução: Avalie quais das opções acima o Candidato Modelo (Advogado Sênior Contencioso Bancário/Cível, Legal Ops, aceite de termos) deve marcar como verdadeiras/aplicáveis.\n"
            "Responda APENAS em JSON no formato: {\"selecionados\": [\"<texto exato da opcao 1>\", \"<texto exato da opcao 2>\"]}"
        )
        raw = self._call_9router(prompt, self.primary_model, json_mode=True)
        if raw:
            try:
                data = json.loads(self._clean_json(raw))
                selected = data.get("selecionados", [])
                if isinstance(selected, list):
                    matched = []
                    for s in selected:
                        for opt in checkbox_options:
                            if s.strip().lower() == opt.strip().lower() or opt.strip().lower() in s.strip().lower():
                                if opt not in matched:
                                    matched.append(opt)
                    return matched
            except Exception as e:
                logger.warning(f"[COGNITIVE] Erro no parsing de checkboxes: {e}")

        return [opt for opt in checkbox_options if any(k in opt.lower() for k in ["sim", "concordo", "aceito", "verdadeir", "bancári", "cível", "execuç"])]

    def decide_page_action(self, page_summary: str, candidate_buttons: List[str], vaga_contexto: str = "") -> Dict[str, Any]:
        if not candidate_buttons:
            return {"action": "WAIT_REVIEW", "target": None, "motivo": "Nenhum botão de ação interativo detectado."}

        btns_formatted = "\n".join([f"[{idx}] {btn}" for idx, btn in enumerate(candidate_buttons)])
        prompt = (
            f"CONTEXTO DA VAGA: {vaga_contexto or 'Processo Seletivo Jurídico'}\n"
            f"ESTADO ATUAL DA TELA:\n{page_summary}\n\n"
            f"BOTÕES / AÇÕES DISPONÍVEIS NA PÁGINA:\n{btns_formatted}\n\n"
            "Instrução: Como agente de navegação do processo seletivo do Candidato Modelo, determine qual é a ação correta para avançar a esteira com segurança.\n"
            "- Se houver botão de avanço (ex: 'Começar', 'Continuar', 'Salvar e continuar', 'Responder agora', 'Finalizar candidatura'), escolha CLICK e o texto exato do botão.\n"
            "- Se a página exigir gravação de vídeo por webcam ou entrevista presencial que um robô não pode fazer, escolha REQUIRE_HUMAN.\n"
            "- Se a etapa estiver finalizada ou em análise aguardando recrutador, escolha WAIT_REVIEW.\n\n"
            "Responda SOMENTE em JSON no formato: {\"action\": \"CLICK\" | \"WAIT_REVIEW\" | \"REQUIRE_HUMAN\", \"target\": \"<texto exato do botao se CLICK>\", \"motivo\": \"<explicacao curta>\"}"
        )
        raw = self._call_9router(prompt, self.primary_model, json_mode=True)
        if raw:
            try:
                data = json.loads(self._clean_json(raw))
                act = data.get("action", "WAIT_REVIEW")
                target = data.get("target")
                motivo = data.get("motivo", "")
                return {"action": act, "target": target, "motivo": motivo}
            except Exception as e:
                logger.warning(f"[COGNITIVE] Erro parsing decisão de ação: {e}")

        forward_keywords = ["salvar e continuar", "continuar", "começar", "responder agora", "enviar respostas", "finalizar"]
        for kw in forward_keywords:
            for btn in candidate_buttons:
                if kw in btn.lower():
                    return {"action": "CLICK", "target": btn, "motivo": f"Avanço por heurística de contingência ('{btn}')."}

        return {"action": "WAIT_REVIEW", "target": None, "motivo": "Ação inconclusiva, mantendo em análise."}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    solver = CognitiveSolver()
    test_q = "Qual a sua senioridade em Contencioso Bancário?"
    opts = ["Júnior (1-2 anos)", "Pleno (3-5 anos)", "Sênior / Especialista (5+ anos)"]
    ans = solver.solve_choice(test_q, opts, vaga_contexto="Advogado Bancário Sênior")
    print(f"\nOpção Escolhida pela IA via 9Router: {ans}")
