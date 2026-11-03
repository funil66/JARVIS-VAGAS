"""
Tier 1 Cognitive Agent (Gemini 2.5 Flash / Pro)
Responsible for:
1. Analyzing application complexity (Simple standard vs Complex with custom dissertations/fit questions)
2. Generating tailored, high-IQ juridical responses based on Candidato Modelo's canonical background
3. Refining responses based on interactive user feedback / prompts from Telegram
"""
import json
import logging
from typing import Dict, List, Optional, Tuple
import requests

try:
    from ..config import GOOGLE_API_KEY, GEMINI_MODEL, ROUTER_BASE_URL, ROUTER_API_KEY, ROUTER_MODEL
    from ..profile import CANDIDATE
    from ..database.models import JobPosting
except (ImportError, ValueError):
    from config import GOOGLE_API_KEY, GEMINI_MODEL, ROUTER_BASE_URL, ROUTER_API_KEY, ROUTER_MODEL
    from profile import CANDIDATE
    from database.models import JobPosting

logger = logging.getLogger("rpa_vagas.engine.tier1_agent")

class Tier1JobAgent:
    def __init__(self, api_key: str = GOOGLE_API_KEY, model: str = GEMINI_MODEL):
        self.api_key = api_key
        self.model = model
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def _call_gemini(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Executa chamada direta à API do Google Gemini com fallback seguro."""
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY não configurada para o Tier 1.")
            return ""

        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        try:
            resp = requests.post(self.api_url, json=payload, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    return candidates[0]["content"]["parts"][0]["text"].strip()
            else:
                logger.error(f"Erro na chamada Gemini Tier 1: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Exceção ao consultar Gemini Tier 1: {e}")

        return ""

    def analyze_complexity(self, job: JobPosting, form_questions: List[str]) -> Tuple[bool, str]:
        """
        Determina se a candidatura é COMPLEXA (exige revisão humana / HITL) ou SIMPLES (pode auto-aplicar).
        Retorna: (is_complex, reason)
        """
        # Se houver campos de perguntas dissertativas ou testes identificados
        if form_questions and len(form_questions) > 0:
            return True, f"Identificadas {len(form_questions)} perguntas personalizadas/dissertativas no formulário."

        # Se a descrição indicar necessidade de portfólio prévio, casos práticos ou pretensão negociada
        desc_lower = (job.description or "").lower()
        complex_triggers = [
            "pretensão salarial", "estudo de caso", "teste prático", "questões dissertativas",
            "vídeo de apresentação", "redija", "descreva um caso", "case prático"
        ]
        for trigger in complex_triggers:
            if trigger in desc_lower:
                return True, f"Vaga exige '{trigger}' identificado na descrição."

        return False, "Candidatura padrão (apenas dados cadastrais e anexo de currículo)."

    def answer_custom_questions(self, job: JobPosting, questions: List[str]) -> Dict[str, str]:
        """
        Gera respostas de alto padrão advocatício para as perguntas do formulário
        utilizando a inteligência do Candidato Modelo.
        """
        if not questions:
            return {}

        system_instruction = (
            f"Você é o co-piloto jurídico e profissional do Dr. {CANDIDATE.name} ({CANDIDATE.oab}). "
            f"Ele é Advogado especialista em Contencioso Cível e Bancário Massivo e Estratégico, "
            f"com vasta experiência na defesa de instituições financeiras (Instituição Financeira Modelo, Instituição Financeira Modelo), "
            f"especialista em fraudes bancárias digitais (PIX, engenharia social), Lei de Superendividamento "
            f"e Legal Ops (ELAW, LEGALE, ProJuris). "
            f"Responda a cada pergunta de forma profissional, persuasiva, objetiva e com vocabulário jurídico refinado."
        )

        prompt = (
            f"VAGA DE EMPREGO:\n"
            f"Título: {job.title}\n"
            f"Empresa: {job.company}\n"
            f"Local: {job.location} | Modalidade: {job.work_mode}\n\n"
            f"PERGUNTAS DO FORMULÁRIO DE CANDIDATURA:\n"
            f"{json.dumps(questions, ensure_ascii=False, indent=2)}\n\n"
            f"Gere um JSON onde cada chave é a pergunta exata e o valor é a resposta profissional recomendada para o Candidato.\n"
            f"Responda APENAS o JSON válido, sem markdown extra."
        )

        res = self._call_gemini(prompt, system_instruction)
        clean_res = res.strip()
        if clean_res.startswith("```json"):
            clean_res = clean_res[7:]
        if clean_res.endswith("```"):
            clean_res = clean_res[:-3]
        clean_res = clean_res.strip()

        try:
            return json.loads(clean_res)
        except Exception:
            # Fallback seguro estruturado
            answers = {}
            for q in questions:
                answers[q] = (
                    f"Com atuação sólida de mais de 8 anos em contencioso cível e bancário (Instituição Financeira Modelo e Instituição Financeira Modelo), "
                    f"possuo ampla experiência prática nas matérias exigidas, com foco em resultados, "
                    f"redução de contingências e alta capacidade resolutiva."
                )
            return answers

    def refine_answer_with_user_prompt(self, question: str, current_answer: str, user_instruction: str) -> str:
        """
        Refina uma resposta específica baseada nas instruções e ajustes enviados pelo Candidato no Telegram.
        """
        system_instruction = (
            f"Você é o assistente de carreira do Dr. {CANDIDATE.name} ({CANDIDATE.oab}). "
            f"O Candidato enviou uma instrução específica de revisão para uma resposta de candidatura."
        )

        prompt = (
            f"Pergunta: {question}\n\n"
            f"Resposta Proposta Inicialmente:\n{current_answer}\n\n"
            f"Instrução / Ajuste do Usuário:\n\"{user_instruction}\"\n\n"
            f"Reescreva a resposta incorporando as instruções do usuário com polidez, persuasão e rigor técnico.\n"
            f"Retorne apenas o texto final da resposta revisada."
        )

        res = self._call_gemini(prompt, system_instruction)
        return res.strip() if res else current_answer
