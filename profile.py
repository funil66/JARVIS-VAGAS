"""
Candidate Profile Configuration & Ground Truth Engine
Profissional Jurídico Sênior (OAB/SP 000.000)
Persistência permanente de dados cadastrais, regras de triagem Gupy e dossiê curricular para o motor de visão (VLM).
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
PROFILE_JSON_PATH = BASE_DIR / "candidate_profile.json"


@dataclass
class CandidateProfile:
    name: str = os.getenv("CANDIDATE_NAME", "Candidato Exemplo")
    title: str = os.getenv("CANDIDATE_TITLE", "Advogado Sênior")
    oab: str = os.getenv("CANDIDATE_OAB", "OAB/SP 000.000")
    email: str = os.getenv("CANDIDATE_EMAIL", "candidato@exemplo.com")
    phone: str = os.getenv("CANDIDATE_PHONE", "+55 (11) 99999-9999")
    phone_raw: str = os.getenv("CANDIDATE_PHONE_RAW", "+5511999999999")
    city: str = os.getenv("CANDIDATE_CITY", "São Paulo")
    state: str = os.getenv("CANDIDATE_STATE", "SP")
    country: str = "Brasil"
    linkedin_url: str = os.getenv("CANDIDATE_LINKEDIN", "https://www.linkedin.com/in/exemplo/")
    cv_pdf_path: str = os.getenv("LOCAL_CV_PATH", str(BASE_DIR / "data" / "curriculo_exemplo.pdf"))

    has_family_ties: bool = False
    available_for_relocation: bool = True

    @property
    def phone_formatted(self) -> str:
        return self.phone
    available_for_travel: bool = True
    has_cnh_b: bool = True
    english_level: str = "Avançado"

    salary_target: float = float(os.getenv("CANDIDATE_SALARY_TARGET", "0.0"))
    salary_display: str = os.getenv("CANDIDATE_SALARY_DISPLAY", "A combinar")
    salary_numeric: int = int(os.getenv("CANDIDATE_SALARY_NUMERIC", "0"))

    def __post_init__(self):
        if PROFILE_JSON_PATH.exists():
            try:
                with open(PROFILE_JSON_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.name = data.get("name", self.name)
                    self.title = data.get("title", self.title)
                    self.oab = data.get("oab", self.oab)
                    self.email = data.get("email", self.email)
                    self.phone = data.get("phone", self.phone)
                    self.city = data.get("city", self.city)
                    self.state = data.get("state", self.state)
                    self.linkedin_url = data.get("linkedin", self.linkedin_url)
            except Exception:
                pass

    def get_ground_truth_prompt(self) -> str:
        """
        Retorna o Dossiê Canônico Inviolável em formato estruturado
        para ser injetado diretamente no System Prompt de qualquer agente de visão/cognitivo.
        """
        return f"""# DOSSIÊ DO CANDIDATO (GROUND TRUTH INVIOLÁVEL EXTRAÍDO DO CURRÍCULO):
- Nome Completo: {self.name}
- Inscrição OAB: {self.oab}
- Cargo / Titulação: {self.title}
- Local de Residência: {self.city} - {self.state}, Brasil
- Telefone / WhatsApp: {self.phone}
- E-mail: {self.email}
- LinkedIn: {self.linkedin_url}
- Arquivo do Currículo (PDF Oficial): {self.cv_pdf_path}

## REGRAS OBRIGATÓRIAS DE TRIAGEM GUPY (GROUND TRUTH INVIOLÁVEL):
1. PARENTESCO / INDICAÇÃO INTERNA:
   - Resposta: SEMPRE "Não".
   - Regra: Candidato NÃO possui parentesco, laços familiares ou indicação interna com funcionários ou dirigentes de NENHUMA empresa contratante.

2. PRETENSÃO SALARIAL:
   - Resposta: Conforme configurado no perfil ou 'A combinar'.
   - Regra: Preencher conforme política da vaga ou 'A combinar'. JAMAIS digite cartas de apresentação ou frases dissertativas em campos de salário.

3. MOBILIDADE, RESIDÊNCIA E MUDANÇA:
   - Resposta: SEMPRE "Sim".
   - Regra: Embora resida em São Paulo/SP, possui DISPONIBILIDADE TOTAL para viagens e mudança de domicílio corporativo imediata para qualquer cidade ou estado do Brasil (São José/SC, Florianópolis, São Paulo, Rio de Janeiro, etc.). Se a pergunta for "Reside com fácil acesso ou tem disponibilidade de mudança?", marque SEMPRE "Sim".

4. HABILITAÇÃO / CNH:
   - Resposta: "Sim", CNH Categoria B ativa.

5. IDIOMAS:
   - Resposta: Inglês Avançado (leitura, escrita e conversação técnica fluente).

6. FORMAÇÃO ACADÊMICA:
   - Graduação em Direito pela Universidade de São Paulo (USP) – São Paulo/SP (2012–2017) - Concluído.
   - Técnico em Serviços Jurídicos pela ETEC José Martimiano da Silva – São Paulo/SP (2009–2010) - Concluído.

7. EXPERIÊNCIA PROFISSIONAL DESTACADA:
   - Contencioso Cível Estratégico e Bancário (defesa em fraudes digitais complexas, golpes do PIX, engenharia social, Lei de Superendividamento 14.181/2021).
   - Legal Operations (Legal Ops), jurimetria aplicada, auditoria de prazos, controladoria jurídica.
   - Sistemas e ERPs dominados: LEGALE, ELAW, ProJuris, CPJ, SPYDER, QUAL7Y, TEDESCO, PJUR, PROJURID, PJe, e-SAJ, Projudi, Eproc.
   - Escritórios Anteriores: Escritório de Advocacia Modelo (Fev/2025–Ago/2025); Banca Jurídica Modelo (Abr/2023–Jan/2025); Sociedade de Advocacia Modelo (Jan/2020–Mai/2021).

8. PERGUNTAS DESCONHECIDAS OU IRREVERSÍVEIS:
   - Se houver pergunta eliminatória da empresa cujos dados NÃO constem deste dossiê (ex: teste comportamental específico, pergunta subjetiva exclusiva da contratante), NÃO CHUTE. Ação deve ser 'wait' com a justificativa de solicitação de validação humana."""


CANDIDATE = CandidateProfile()
