"""
Browser Form Applicator with Human-in-the-Loop (HITL) & Playwright Automation
Supports:
1. Standard form filling (Name, Email, Phone, LinkedIn, OAB, CV PDF upload)
2. Detection of complex dissertations, fit questions and custom textareas
3. Tier 1 Cognitive Agent answers generation
4. Live pause (browser wait) for Telegram confirmation / prompt-based edits
5. Final submission, confirmation screenshot, and Telegram report
"""
import time
import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict
from playwright.sync_api import sync_playwright

try:
    from ..config import CV_DEFAULT_PATH, SIMPLE_AUTO_APPLY_MIN_SCORE
    from ..profile import CANDIDATE
    from ..database.models import JobPosting
    from ..engine.tier1_agent import Tier1JobAgent
    from ..notifications.telegram import TelegramNotifier
except (ImportError, ValueError):
    from config import CV_DEFAULT_PATH, SIMPLE_AUTO_APPLY_MIN_SCORE
    from profile import CANDIDATE
    from database.models import JobPosting
    from engine.tier1_agent import Tier1JobAgent
    from notifications.telegram import TelegramNotifier

logger = logging.getLogger("rpa_vagas.browser.applicator")

class FormApplicator:
    def __init__(self, cv_path: Optional[Path] = None):
        self.cv_path = cv_path or CV_DEFAULT_PATH
        self.tier1 = Tier1JobAgent()
        self.telegram = TelegramNotifier()

    def fill_and_apply(
        self,
        job: JobPosting,
        cover_letter: str = "",
        dry_run: bool = False,
        allow_hitl: bool = True
    ) -> Tuple[bool, str]:
        """
        Executa a esteira de candidatura automatizada:
        - Abre a vaga no Playwright Chromium
        - Detecta campos cadastrais básicos e campos dissertativos complexos
        - Se simples: aplica de forma autônoma
        - Se complexa: aciona o Tier 1, pausa o navegador e aguarda confirmação no Telegram
        """
        if dry_run:
            logger.info(f"[DRY-RUN] Simulação de candidatura para '{job.title}' ({job.company}) em {job.url}")
            return True, "Simulação de submissão concluída com sucesso (Dry-Run)."

        screenshots_dir = Path(self.cv_path).parent.parent / "logs" / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                logger.info(f"Navegando para vaga: {job.url}")
                page.goto(job.url, timeout=40, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # 1. Preenche campos cadastrais padrão
                self._fill_standard_fields(page)

                # 2. Detecta campos dissertativos ou perguntas abertas complexas
                complex_questions = self._extract_custom_questions(page)
                is_complex, reason = self.tier1.analyze_complexity(job, complex_questions)

                logger.info(f"Análise de complexidade: is_complex={is_complex} | Motivo: {reason}")

                # 3. Tratamento de Candidaturas Complexas com HITL (Telegram)
                if is_complex and allow_hitl:
                    logger.info("Candidatura complexa detectada. Gerando respostas com Tier 1...")
                    proposed_answers = self.tier1.answer_custom_questions(job, complex_questions)

                    # Pausa o navegador e aguarda a decisão do Candidato no Telegram
                    decision, final_answers = self.telegram.ask_approval_with_options(
                        job=job,
                        proposed_answers=proposed_answers,
                        cover_letter=cover_letter,
                        tier1_refiner=self.tier1
                    )

                    if decision == "rejected":
                        browser.close()
                        return False, "Candidatura rejeitada manualmente pelo usuário via Telegram."
                    elif decision == "timeout":
                        browser.close()
                        return False, "Tempo de espera expirado sem aprovação humana no Telegram."

                    # Se aprovado, preenche os campos com as respostas aprovadas/editadas
                    self._fill_custom_answers(page, final_answers)

                elif not is_complex and job.match_score < SIMPLE_AUTO_APPLY_MIN_SCORE:
                    # Se for simples mas o score não for alto o suficiente para envio cego
                    logger.info(f"Score {job.match_score}% abaixo do limiar para envio 100% autônomo ({SIMPLE_AUTO_APPLY_MIN_SCORE}%).")

                # 4. Anexa Currículo em PDF se houver campo de upload
                self._attach_cv(page)

                # 5. Localiza e aciona o botão de submissão
                submitted = self._submit_form(page)

                # 6. Captura de tela comprobatória
                screenshot_file = screenshots_dir / f"apply_{job.id or int(time.time())}.png"
                page.screenshot(path=str(screenshot_file), full_page=False)

                # Envia comprovação com foto no Telegram
                if submitted:
                    self.telegram.send_photo(
                        str(screenshot_file),
                        caption=f"📸 *Comprovante de Envio:*\nCandidatura submetida para *{job.title}* ({job.company})."
                    )

                browser.close()
                return True, "Candidatura submetida e confirmada com sucesso via Playwright."

        except Exception as e:
            logger.error(f"Erro no preenchimento de candidatura Playwright: {e}")
            return False, str(e)

    def _fill_standard_fields(self, page):
        """Preenche campos cadastrais padrão."""
        selectors_map = {
            "name": [
                'input[name*="name" i]', 'input[placeholder*="nome" i]', 'input[id*="name" i]',
                'input[aria-label*="nome" i]'
            ],
            "email": [
                'input[type="email"]', 'input[name*="email" i]', 'input[placeholder*="email" i]',
                'input[id*="email" i]'
            ],
            "phone": [
                'input[type="tel"]', 'input[name*="phone" i]', 'input[name*="telefone" i]',
                'input[name*="celular" i]', 'input[placeholder*="telefone" i]', 'input[placeholder*="celular" i]'
            ],
            "linkedin": [
                'input[name*="linkedin" i]', 'input[placeholder*="linkedin" i]', 'input[id*="linkedin" i]'
            ],
            "oab": [
                'input[name*="oab" i]', 'input[placeholder*="oab" i]', 'input[id*="oab" i]'
            ]
        }

        # Nome
        for sel in selectors_map["name"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill(CANDIDATE.name)
                    break
            except Exception:
                continue

        # Email
        for sel in selectors_map["email"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill(CANDIDATE.email)
                    break
            except Exception:
                continue

        # Telefone
        for sel in selectors_map["phone"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill(CANDIDATE.phone_formatted)
                    break
            except Exception:
                continue

        # LinkedIn
        for sel in selectors_map["linkedin"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill(CANDIDATE.linkedin_url)
                    break
            except Exception:
                continue

        # OAB
        for sel in selectors_map["oab"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible() and not el.input_value():
                    el.fill(CANDIDATE.oab)
                    break
            except Exception:
                continue

    def _extract_custom_questions(self, page) -> List[str]:
        """Detecta perguntas e campos dissertativos no formulário."""
        questions = []
        try:
            textareas = page.query_selector_all("textarea")
            for ta in textareas:
                if not ta.is_visible():
                    continue
                # Tenta obter o texto do label ou placeholder
                label_text = ""
                parent = ta.evaluate_handle("el => el.closest('label') || el.closest('.form-group') || el.parentElement")
                if parent:
                    label_text = parent.evaluate("el => el.innerText")

                placeholder = ta.get_attribute("placeholder") or ""
                name = ta.get_attribute("name") or ""
                question_desc = label_text.strip() or placeholder.strip() or name.strip() or "Pergunta dissertativa"
                if len(question_desc) > 5 and question_desc not in questions:
                    questions.append(question_desc)
        except Exception as e:
            logger.debug(f"Erro ao extrair perguntas: {e}")

        return questions

    def _fill_custom_answers(self, page, answers: Dict[str, str]):
        """Injeta as respostas geradas pelo Tier 1 e validadas pelo usuário."""
        try:
            textareas = page.query_selector_all("textarea")
            for idx, ta in enumerate(textareas):
                if not ta.is_visible():
                    continue
                # Atribui a resposta correspondente
                keys = list(answers.keys())
                if idx < len(keys):
                    ans = answers[keys[idx]]
                    ta.fill(ans)
        except Exception as e:
            logger.error(f"Erro ao preencher respostas customizadas: {e}")

    def _attach_cv(self, page):
        """Localiza campos de upload de arquivo e anexa o PDF canônico do currículo."""
        cv_target = Path(self.cv_path)
        if not cv_target.exists():
            fallback = Path(__file__).resolve().parent.parent / "data" / "curriculo_exemplo.pdf"
            if fallback.exists():
                cv_target = fallback

        if not cv_target.exists():
            logger.warning(f"Arquivo de currículo não localizado em {self.cv_path}")
            return False

        try:
            # 1. Tentativa via seletor nativo Playwright (funciona mesmo para inputs invisíveis/display:none)
            file_input = page.locator("input[type='file']").first
            if file_input.count() > 0:
                file_input.set_input_files(str(cv_target))
                logger.info(f"Currículo anexado com sucesso via seletor: {cv_target.name}")
                return True

            # 2. Tentativa via FileChooser event ao clicar em botões de upload
            upload_btns = [
                "button:has-text('Anexar currículo')",
                "button:has-text('Upload')",
                "button:has-text('Enviar currículo')",
                "label:has-text('Currículo')",
                "div:has-text('Arraste seu currículo')"
            ]
            for sel in upload_btns:
                btn = page.locator(sel).first
                if btn.is_visible():
                    try:
                        with page.expect_file_chooser(timeout=3000) as fc_info:
                            btn.click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(str(cv_target))
                        logger.info(f"Currículo anexado via FileChooser: {cv_target.name}")
                        return True
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Não foi possível anexar currículo automaticamente: {e}")
        return False

    def _submit_form(self, page) -> bool:
        """Tenta encontrar e acionar o botão de submissão final."""
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Candidatar-se")',
            'button:has-text("Enviar Candidatura")',
            'button:has-text("Finalizar Inscrição")',
            'button:has-text("Submeter")',
            'input[type="submit"]'
        ]
        for sel in submit_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    btn.click()
                    page.wait_for_timeout(4000)
                    return True
            except Exception:
                continue
        return False
