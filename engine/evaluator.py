"""
Matching & Evaluation Engine for Lawyer Job Opportunities
Calcula pontuação de compatibilidade (0 - 100%) com base nas preferências canônicas e gera carta de apresentação.
"""
import re
import logging
from typing import Tuple

try:
    from ..profile import CANDIDATE, CandidateProfile
    from ..database.models import JobPosting
except (ImportError, ValueError):
    from profile import CANDIDATE, CandidateProfile
    from database.models import JobPosting

logger = logging.getLogger("rpa_vagas.evaluator")

class JobEvaluator:
    def __init__(self, profile: CandidateProfile = CANDIDATE):
        self.profile = profile

    def evaluate_job(self, job: JobPosting) -> Tuple[int, str, str]:
        """
        Calcula o match score (0-100), reasoning e nível de prioridade (ALTA, MEDIA, BAIXA).
        Regra estrita de preferência de modalidade:
        1. Home Office (Remoto) -> Boost +35
        2. Híbrido             -> Boost +20
        3. Presencial          -> Boost +10 (se região SP/Capital) ou -20 (se presencial distante)
        """
        score = 0
        reasons = []

        full_text = f"{job.title} {job.company} {job.location} {job.description}".lower()

        # 1. Avaliação de Modalidade de Trabalho (Preferência 1: Remoto, 2: Híbrido, 3: Presencial)
        if job.work_mode == "REMOTE" or "remoto" in full_text or "home office" in full_text or "100% remoto" in full_text:
            score += 35
            job.work_mode = "REMOTE"
            reasons.append("Modalidade Remota (1ª Prioridade do Candidato: +35pts)")
        elif job.work_mode == "HYBRID" or "híbrido" in full_text or "hibrido" in full_text:
            score += 20
            job.work_mode = "HYBRID"
            reasons.append("Modalidade Híbrida (2ª Prioridade do Candidato: +20pts)")
        else:
            job.work_mode = "PRESENTIAL"
            # Verificar se a localidade é compatível com SP / São Paulo
            is_sp_region = any(loc in full_text for loc in ["sp", "são paulo", "sao paulo", "campinas", "santos", "sorocaba"])
            if is_sp_region:
                score += 10
                reasons.append("Modalidade Presencial na região de atuação (SP/São Paulo: +10pts)")
            else:
                score -= 15
                reasons.append("Modalidade Presencial fora do domicílio principal (-15pts)")

        # 2. Avaliação de Cargo e Senioridade
        if any(term in full_text for term in ["sênior", "senior", "especialista", "coordenador", "head", "consultor"]):
            score += 25
            reasons.append("Senioridade Sênior / Especialista compatível (+25pts)")
        elif any(term in full_text for term in ["pleno", "advogado", "associado"]):
            score += 20
            reasons.append("Nível Pleno / Advogado Geral compatível (+20pts)")
        elif any(term in full_text for term in ["estágio", "estagiario", "estagiário", "assistente administrativo"]):
            score -= 30
            reasons.append("Vaga júnior/estágio abaixo do perfil sênior (-30pts)")

        # 3. Avaliação de Especialidade Jurídica (Cível, Bancário, Fraudes, Contratos, Legal Ops)
        specialties_found = []
        if any(w in full_text for w in ["bancário", "bancario", "banco", "instituição financeira", "instituicao financeira"]):
            score += 15
            specialties_found.append("Bancário")
        if any(w in full_text for w in ["cível", "civel", "contencioso cível", "contencioso"]):
            score += 15
            specialties_found.append("Contencioso Cível")
        if any(w in full_text for w in ["fraude", "pix", "fraudes digitais", "golpe"]):
            score += 15
            specialties_found.append("Fraudes Digitais / PIX")
        if any(w in full_text for w in ["legal ops", "controladoria", "jurimetria", "eraw", "legale", "projuris"]):
            score += 10
            specialties_found.append("Legal Ops / Jurimetria")
        if any(w in full_text for w in ["trabalhista", "labor"]):
            score += 10
            specialties_found.append("Trabalhista")
        if any(w in full_text for w in ["contrato", "contratos", "comercial"]):
            score += 10
            specialties_found.append("Contratos")

        if specialties_found:
            reasons.append(f"Áreas de especialidade identificadas: {', '.join(specialties_found)}")
        else:
            reasons.append("Área jurídica geral")

        # 4. Normalização do Score (0 a 100)
        score = max(0, min(100, score))

        # 5. Classificação de Prioridade
        if score >= 75:
            priority = "ALTA"
        elif score >= 50:
            priority = "MEDIA"
        else:
            priority = "BAIXA"

        reasoning_text = " | ".join(reasons)
        return score, reasoning_text, priority

    def generate_cover_letter(self, job: JobPosting) -> str:
        """
        Gera uma carta de apresentação altamente personalizada e persuasiva
        para a vaga específica, destacando as credenciais do Candidato.
        """
        company_name = job.company if job.company and job.company != "Gupy Enterprise" else "Equipe de Recursos Humanos"
        title = job.title or "Advogado Sênior"

        # Identificar destaques para o texto
        text_lower = f"{job.title} {job.description}".lower()
        if "bancário" in text_lower or "banco" in text_lower or "fraude" in text_lower:
            focus_text = (
                "Com sólida bagagem no contencioso massivo e estratégico bancário — tendo atuado em bancas "
                "de grande porte na defesa de instituições como Instituição Financeira Modelo e Banco Instituição Financeira Modelo —, possuo profundo "
                "domínio técnico em teses defensivas de fraudes digitais (golpes do PIX, engenharia social), "
                "ações de superendividamento (Lei 14.181/2021) e jurimetria aplicada para redução de contingências."
            )
        elif "legal ops" in text_lower or "controladoria" in text_lower or "gestão" in text_lower:
            focus_text = (
                "Aliando sólida experiência contenciosa a uma visão moderna de Legal Ops, atuo no saneamento de carteiras "
                "de alta volumetria, auditoria permanente de prazos e parametrização de ERPs jurídicos líderes "
                "(LEGALE, ELAW, ProJuris, CPJ, TEDESCO), garantindo tempestividade e eficiência operacional."
            )
        else:
            focus_text = (
                "Com mais de 8 anos de sólida atuação no contencioso cível, bancário e consultoria contratual, "
                "reúno histórico comprovado em condução estratégica de litígios, sustentação oral, redução de passivos "
                "e mitigação de riscos reputacionais e financeiros para empresas de médio e grande porte."
            )

        letter = f"""Prezados(as) recrutadores da {company_name},

Apresento minha candidatura à oportunidade de **{title}**.

Sou **Candidato Jurídico** ({self.profile.oab}), graduado em Direito com formação complementar em Serviços Jurídicos e inglês avançado.

{focus_text}

Estou plenamente alinhado com a dinâmica de atuação da vaga e coloco à disposição minha capacidade analítica, rigor ético e foco em resultados mensuráveis para agregar valor imediato à equipe.

Em anexo, encaminho meu currículo detalhado. Agradeço a atenção e permaneço à disposição para entrevista.

Cordialmente,

**Candidato Jurídico**
Advogado | {self.profile.oab}
📞 {self.profile.phone_formatted}
✉️ {self.profile.email}
🔗 {self.profile.linkedin_url}
"""
        return letter
