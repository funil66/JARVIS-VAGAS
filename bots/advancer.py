"""
RPA-Advancer (Bot 2: Máquina de Estados & Visão Computacional Set-of-Mark para Gupy)
Opera no Paradigma "See & Click" via VLM Multimodal Google GenAI (Gemini):
1. Injeta script visual Set-of-Mark (SoM) desenhando Bounding Boxes e selos numéricos [ID].
2. Tira screenshot anotado e preserva histórico recente de ações (Context Preservation).
3. Consulta o motor de visão com o Dossiê Curricular Oficial (Ground Truth) do Candidato Modelo (OAB/SP 000.000).
4. Zero Scripts Heurísticos: Toda decisão é 100% visual e racional, ancorada nos dados oficiais.
5. Validação de segurança: Perguntas desconhecidas ou não cobertas pausam para validação humana.
6. Gerencia modais, banners LGPD/cookies, detecção de Captchas e Circuit Breaker de custos.
7. Persiste progresso no SQLite local de forma idempotente e recuperável.
"""
import os
import sys
import time
import json
import base64
import sqlite3
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from profile import CANDIDATE
try:
    from config import (
        GEMINI_API_KEY,
        GEMINI_PRIMARY_MODEL,
        GEMINI_FALLBACK_MODELS,
        GEMINI_MODEL
    )
except ImportError:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    GEMINI_PRIMARY_MODEL = "gemini-3-flash-preview"
    GEMINI_FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3.8-flash"]
    GEMINI_MODEL = GEMINI_PRIMARY_MODEL

from browser.session_manager import GupySessionManager

logger = logging.getLogger("rpa_vagas.bots.advancer")

DB_PATH = ROOT_DIR / "data" / "rpa_vagas.db"
CV_PATH = ROOT_DIR / "data" / "curriculo_exemplo.pdf"
SCREENSHOTS_DIR = ROOT_DIR / "logs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
SOM_SCRIPT_PATH = ROOT_DIR / "engine" / "vision" / "set_of_mark.js"

MAX_ACTIONS_CONTEXT = 3
MAX_STEPS_PER_APPLICATION = 35
MAX_BBOX_RETRIES = 3


class GeminiVisionClient:
    """Cliente visual multimodal soberano com fallback automático entre modelos Google GenAI."""

    def __init__(
        self,
        api_key: str,
        primary_model: str = "gemini-flash-lite-latest",
        fallback_models: Optional[List[str]] = None
    ):
        self.api_key = api_key
        fallback_list = fallback_models or ["gemini-3-flash-preview"]
        self.models = [primary_model] + [m for m in fallback_list if m != primary_model]

    def generate_decision(self, system_prompt: str, user_text: str, img_b64: str) -> Optional[Dict[str, Any]]:
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [{
                "parts": [
                    {"text": user_text},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": img_b64
                        }
                    }
                ]
            }],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
                "maxOutputTokens": 4096
            }
        }

        for model in self.models:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            for attempt in range(1, 4):
                try:
                    req = urllib.request.Request(
                        endpoint,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=35) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        candidates = data.get("candidates", [])
                        if not candidates:
                            break
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if not parts:
                            break
                        raw_text = parts[0].get("text", "{}").strip()
                        if raw_text.startswith("```json"):
                            raw_text = raw_text[7:]
                        if raw_text.startswith("```"):
                            raw_text = raw_text[3:]
                        if raw_text.endswith("```"):
                            raw_text = raw_text[:-3]
                        raw_text = raw_text.strip()
                        try:
                            decision = json.loads(raw_text)
                            decision["_model_used"] = model
                            logger.info(f"[GEMINI VISION] Decisão visual gerada com sucesso via '{model}'.")
                            return decision
                        except Exception:
                            import re
                            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                            if match:
                                decision = json.loads(match.group(0))
                                decision["_model_used"] = model
                                return decision
                            raise
                except Exception as ex:
                    err_str = str(ex)
                    if "429" in err_str:
                        logger.warning(f"[GEMINI VISION] Modelo '{model}' com Rate Limit (429). Pausa de 12s para reset de cota (tentativa {attempt}/3)...")
                        time.sleep(12.0)
                        continue
                    elif "503" in err_str or "404" in err_str:
                        logger.warning(f"[GEMINI VISION] Modelo '{model}' indisponível ({err_str}). Tentando próximo modelo...")
                        time.sleep(3.0)
                        break
                    time.sleep(2.0 * attempt)

        logger.error("[GEMINI VISION] Todos os modelos de visão multimodal falharam ou estão indisponíveis.")
        return None


class AdvancerBot:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        cv_path: Optional[Path] = None,
        som_js_path: Optional[Path] = None,
        gemini_api_key: Optional[str] = None
    ):
        self.db_path = db_path or DB_PATH
        self.cv_path = cv_path or CV_PATH
        self.som_js_path = som_js_path or SOM_SCRIPT_PATH
        self.session_mgr = GupySessionManager()
        self.api_key = gemini_api_key or GEMINI_API_KEY
        self.recent_actions: List[Dict[str, Any]] = []

        try:
            p_model = GEMINI_PRIMARY_MODEL
            f_models = GEMINI_FALLBACK_MODELS
        except NameError:
            p_model = "gemini-3-flash-preview"
            f_models = ["gemini-3.5-flash", "gemini-3.8-flash"]

        self.gemini_client = GeminiVisionClient(
            self.api_key,
            primary_model=p_model,
            fallback_models=f_models
        ) if self.api_key else None

        if self.gemini_client:
            logger.info(f"[ADVANCER GUPY] Motor cognitivo visual configurado com modelos {self.gemini_client.models}.")
        else:
            logger.warning("[ADVANCER GUPY] GEMINI_API_KEY ausente. VLM indisponível.")

    def push_action_context(self, action_type: str, bbox_id: Optional[int], element_text: str, reason: str):
        self.recent_actions.append({
            "action": action_type,
            "bbox_id": bbox_id,
            "element": element_text[:50],
            "reason": reason,
            "timestamp": time.strftime("%H:%M:%S")
        })
        if len(self.recent_actions) > MAX_ACTIONS_CONTEXT:
            self.recent_actions.pop(0)

    def _read_som_script(self) -> str:
        if not self.som_js_path.exists():
            raise FileNotFoundError(f"Script Set-of-Mark não encontrado em: {self.som_js_path}")
        with open(self.som_js_path, "r", encoding="utf-8") as f:
            return f.read()

    def annotate_page(self, page, shot_name: str = "step") -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
        """Injeta SoM e retorna bboxes filtrados, metadados e caminho do screenshot."""
        som_js_code = self._read_som_script()

        page.evaluate(som_js_code)
        bboxes_raw = page.evaluate("window.applySetOfMark()")
        meta = page.evaluate("window.applySetOfMark.meta || {}")

        bboxes = bboxes_raw if isinstance(bboxes_raw, list) else bboxes_raw.get("bboxes", [])

        timestamp = int(time.time())
        screenshot_path = SCREENSHOTS_DIR / f"{shot_name}_{timestamp}.png"
        page.screenshot(path=str(screenshot_path), full_page=False)

        latest_path = SCREENSHOTS_DIR / "live_latest.png"
        page.screenshot(path=str(latest_path), full_page=False)

        page.evaluate("window.clearSetOfMark()")
        return bboxes, meta, str(screenshot_path)

    def dismiss_overlays_if_present(self, page, bboxes: List[Dict[str, Any]], meta: Dict[str, Any]) -> bool:
        """Detecção e fechamento de banners LGPD, OneTrust e modais."""
        try:
            for sel in [
                "#onetrust-accept-btn-handler",
                "text='Aceitar todos os cookies'",
                "text='Aceitar cookies'",
                "button:has-text('Aceitar')"
            ]:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    logger.info(f"[ADVANCER GUPY] Banner LGPD/Cookies detectado ({sel}). Aceitando...")
                    btn.click()
                    page.wait_for_timeout(1000)
                    return True
        except Exception:
            pass

        dismiss_id = meta.get("modal_dismiss_id")
        if dismiss_id is not None:
            target_bbox = next((b for b in bboxes if b.get("id") == dismiss_id), None)
            if target_bbox:
                logger.info(f"[ADVANCER GUPY] Modal overlay detectado. Acionando dismiss [ID {dismiss_id}]...")
                page.mouse.click(target_bbox["center_x"], target_bbox["center_y"])
                self.push_action_context("click_dismiss", dismiss_id, "Dismiss Modal/Overlay", "Overlay detectado")
                page.wait_for_timeout(1000)
                return True

        return False

    def _heuristic_fallback_decision(self, bboxes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback heurístico determinístico para avançar botões clássicos quando o VLM não estiver disponível."""
        target_texts = ["salvar e continuar", "continuar", "avançar", "próximo", "submeter"]
        for target in target_texts:
            for b in bboxes:
                text = str(b.get("text", "")).lower()
                if target in text:
                    return {
                        "acao": "click",
                        "bbox_id": b.get("id"),
                        "justificativa": f"Fallback heurístico: {b.get('text')}"
                    }
        return {"acao": "wait", "bbox_id": None, "justificativa": "Nenhum botão de avanço identificado"}

    def consult_vlm_decision(
        self,
        screenshot_path: str,
        bboxes: List[Dict[str, Any]],
        job_context: str = "",
        error_feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envia a imagem anotada e os bboxes diretamente ao Google GenAI VLM com o Dossiê Curricular Oficial.
        Zero scripts de contingência: decisão 100% visual e racional.
        """
        elements_summary = []
        for b in bboxes[:80]:
            elements_summary.append(
                f"[{b.get('id')}] Tag: {b.get('tag')} | Tipo: {b.get('type')} | Texto: {b.get('text')} | Coords: ({b.get('center_x')},{b.get('center_y')})"
            )
        catalog_text = "\n".join(elements_summary)

        recent_actions_text = (
            json.dumps(self.recent_actions, ensure_ascii=False)
            if self.recent_actions
            else "Nenhuma ação anterior nesta página."
        )

        ground_truth = CANDIDATE.get_ground_truth_prompt()

        system_prompt = (
            f"{ground_truth}\n\n"
            "## DIRETRIZES OPERACIONAIS DE NAVEGAÇÃO E AVALIAÇÃO VISUAL NA GUPY:\n"
            "1. PÁGINA DE PROGRESSO / ETAPAS (ex: 'Sobre o processo', 'Seu progresso 1/4'):\n"
            "   - Identifique qual etapa está ativa/desbloqueada e localize o botão de ação correspondente.\n"
            "   - Reconheça botões da etapa: 'Começar', 'Iniciar', 'Responder agora', 'Fazer teste', 'Aproveitar resultado anterior', 'Continuar', 'Avançar', 'Salvar e continuar'.\n"
            "   - Se a opção 'Aproveitar resultado anterior' estiver disponível, priorize-a para reutilizar testes já concluídos sem refazer.\n\n"
            "2. FORMULÁRIOS E QUESTIONÁRIOS DA EMPRESA:\n"
            "   - Leia atentamente cada pergunta antes de clicar ou preencher.\n"
            "   - PARENTESCO: Selecione SEMPRE 'Não'. O candidato NÃO possui parentesco ou indicação interna com colaboradores de nenhuma contratante.\n"
            "   - PRETENSÃO SALARIAL: Preencha conforme configurado no perfil ou 'A combinar'. NUNCA insira textos dissertativos de apresentação.\n"
            "   - RESIDÊNCIA / DISPONIBILIDADE DE MUDANÇA: Selecione SEMPRE 'Sim'. Possui total mobilidade para viagens ou mudança de domicílio corporativo imediata.\n"
            "   - PERGUNTA DESCONHECIDA OU CRÍTICA: Se houver pergunta eliminatória com resposta não coberta pelo dossiê, NÃO CHUTE. Retorne acao: 'wait' com justificativa iniciando por 'PERGUNTA_DESCONHECIDA: [pergunta]'.\n   - FORMULÁRIOS COM MÚLTIPLAS PERGUNTAS:\n     * Formulários da Gupy frequentemente contêm várias perguntas na mesma página.\n     * Preencha cada pergunta pendente (texto ou radio button). Só clique em 'Salvar e continuar' ou 'Avançar' após responder todas as perguntas visíveis.\n     * Se houver aviso em vermelho de 'Campo obrigatório', preencha o campo apontado imediatamente.\n     * Se houver mais perguntas ou o botão de envio/salvar estiver fora da visão, use acao: 'scroll' com direcao: 'down' e pixels: 600 para rolar a página e revelar o restante do formulário.\n\n"
            "3. TESTES ONLINE, PROVAS TÉCNICAS E FIT CULTURAL (GUPY ASSESSMENTS):\n"
            "   - Se houver opção 'Aproveitar resultado anterior' visível ou sugerida, clique SEMPRE nela com prioridade máxima para reaproveitar avaliações já feitas.\n"
            "   - Se estiver em uma tela de prova ou teste (questão com alternativas):\n"
            "     * Leia com máxima atenção o enunciado e cada uma das alternativas exibidas na tela.\n"
            "     * Como alter-ego do Candidato (Advogado Sênior, raciocínio lógico apurado, domínio de Direito, português impecável e inglês técnico), escolha a resposta correta.\n"
            "     * Selecione o [ID] da alternativa correta (ou clique no radio button correspondente).\n"
            "     * Em seguida, clique em 'Confirmar', 'Próxima questão', 'Avançar' ou 'Finalizar teste' para continuar.\n"
            "     * Prossiga até que o teste seja 100% concluído.\n\n"
            "4. FORMATO ESTRITO DE RESPOSTA (JSON):\n"
            "{\n"
            '  "acao": "click" | "fill" | "scroll" | "finish" | "wait",\n'
            '  "direcao": "down" | "up",\n'
            '  "pixels": 500,\n'
            '  "bbox_id": <numero_do_selo_ID_visivel_na_imagem>,\n'
            '  "texto": "<texto_caso_acao_seja_fill_ou_null>",\n'
            '  "justificativa": "<explicacao_curta_e_racional_baseada_no_curriculo>"\n'
            "}\n"
            "REGRAS INVIOLÁVEIS:\n"
            "1. O 'bbox_id' DEVE existir estritamente na lista de elementos visíveis.\n"
            "2. Se todas as etapas estiverem concluídas ou aguardando análise da empresa, retorne 'finish'.\n"
            "3. ZERO SCRIPT: Toda decisão é 100% visual e racional, ancorada no dossiê oficial."
        )

        user_prompt = (
            f"Contexto da Vaga na Gupy: {job_context}\n"
            f"Histórico Recente de Ações:\n{recent_actions_text}\n\n"
            f"Elementos Mapeados com Selos Numéricos [ID]:\n{catalog_text}\n\n"
        )

        if error_feedback:
            user_prompt += f"⚠️ ATENÇÃO: A tentativa anterior falhou: {error_feedback}. Corrija a escolha imediatamente!\n"

        try:
            with open(screenshot_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as img_err:
            logger.error(f"[ADVANCER GUPY] Falha ao codificar imagem {screenshot_path}: {img_err}")
            return {
                "acao": "wait",
                "bbox_id": None,
                "texto": None,
                "justificativa": f"Falha na imagem: {img_err}"
            }

        time.sleep(3.0)

        if self.gemini_client:
            decision = self.gemini_client.generate_decision(
                system_prompt=system_prompt,
                user_text=user_prompt,
                img_b64=img_b64
            )
            if decision and isinstance(decision, dict):
                return decision

        logger.warning("[ADVANCER GUPY] Modelo visual não retornou decisão. Nenhuma ação heurística será executada (Script Blind Protections).")
        return {
            "acao": "wait",
            "bbox_id": None,
            "texto": None,
            "justificativa": "Aguardando modelo visual. Ação por script bloqueada."
        }

    def validate_and_execute_step(
        self,
        page,
        bboxes: List[Dict[str, Any]],
        meta: Dict[str, Any],
        screenshot_path: str,
        job_context: str
    ) -> Tuple[bool, str]:
        """Ciclo de validação visual com retry e proteção de integridade."""
        if self.dismiss_overlays_if_present(page, bboxes, meta):
            return True, "MODAL_DISMISSED"

        if meta.get("has_captcha"):
            logger.warning("[ADVANCER GUPY] Captcha visual detectado na página! Entrando em Babysitting Mode...")
            return False, "CAPTCHA_DETECTED"

        error_msg = None
        for attempt in range(1, MAX_BBOX_RETRIES + 1):
            decision = self.consult_vlm_decision(
                screenshot_path=screenshot_path,
                bboxes=bboxes,
                job_context=job_context,
                error_feedback=error_msg
            )

            acao = decision.get("acao", "wait").lower()
            bbox_id = decision.get("bbox_id")
            texto = decision.get("texto")
            justificativa = decision.get("justificativa", "")

            if acao == "finish":
                logger.info(f"[ADVANCER GUPY] Finalização da candidatura detectada: {justificativa}")
                return False, "FINISHED"

            if acao == "wait":
                logger.info(f"[ADVANCER GUPY] VLM recomendou aguardar: {justificativa}")
                if "PERGUNTA_DESCONHECIDA" in justificativa:
                    logger.warning(f"[ADVANCER GUPY SEGURANÇA] Questionário da empresa requer validação humana: {justificativa}")
                    return False, "AGUARDANDO_VALIDACAO_MANUAL"
                return False, "WAIT_CALLED"

            target_bbox = next((b for b in bboxes if b.get("id") == bbox_id), None)
            if not target_bbox:
                error_msg = f"Selo numérico [ID {bbox_id}] não existe no catálogo de elementos."
                logger.warning(f"[ADVANCER RETRY] Tentativa #{attempt}: {error_msg}")
                continue

            cx = target_bbox["center_x"]
            cy = target_bbox["center_y"]
            tag_name = target_bbox.get("tag", "").lower()
            element_text = target_bbox.get("text", "")

            if acao == "click":
                if len(self.recent_actions) >= 2:
                    last_two = [a.get("element") for a in self.recent_actions[-2:] if a.get("action") == "click"]
                    if len(last_two) == 2 and last_two[0] == last_two[1] and last_two[0] == (element_text or tag_name):
                        logger.warning(f"[ADVANCER LOOP BREAKER] Elemento '{element_text}' repetido consecutivamente. Rolando para baixo para revelar novo conteúdo...")
                        page.mouse.wheel(0, 400)
                        page.wait_for_timeout(1500)
                        self.push_action_context("scroll", None, "scroll_down", "Loop breaker scroll")
                        return True, "LOOP_BREAKER_SCROLL"

                logger.info(f"[ADVANCER CLICK] Clicando no [ID {bbox_id}] '{element_text}' ({cx}, {cy}). Motivo: {justificativa}")
                try:
                    clicked_dom = False
                    loc = page.locator(f"[data-som-id='{bbox_id}']")
                    if loc.count() > 0:
                        try:
                            loc.first.click(timeout=3500)
                            clicked_dom = True
                        except Exception:
                            pass
                    if not clicked_dom:
                        page.mouse.click(cx, cy)
                except Exception:
                    try:
                        page.mouse.click(cx, cy)
                    except Exception:
                        pass
                self.push_action_context("click", bbox_id, element_text or tag_name, justificativa)
                return True, f"CLICKED_{bbox_id}"

            elif acao == "scroll":
                direcao = decision.get("direcao", "down")
                pixels = int(decision.get("pixels", 600))
                logger.info(f"[ADVANCER SCROLL] Rolando página {direcao} {pixels}px. Motivo: {justificativa}")
                try:
                    if direcao == "up":
                        page.mouse.wheel(0, -pixels)
                    else:
                        page.mouse.wheel(0, pixels)
                    page.wait_for_timeout(1000)
                except Exception as sc_err:
                    logger.warning(f"[ADVANCER SCROLL] Erro no scroll: {sc_err}")
                self.push_action_context("scroll", 0, f"Scroll {direcao} {pixels}px", justificativa)
                return True, f"SCROLLED_{direcao.upper()}"

            elif acao == "fill":
                fill_value = texto or ""
                logger.info(f"[ADVANCER FILL] Preenchendo [ID {bbox_id}] com '{fill_value}'. Motivo: {justificativa}")
                try:
                    loc = page.locator(f"[data-som-id='{bbox_id}']")
                    if loc.count() > 0:
                        loc.first.fill(str(fill_value), timeout=3500)
                    else:
                        page.mouse.click(cx, cy)
                        page.wait_for_timeout(300)
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                        page.keyboard.type(str(fill_value))
                except Exception:
                    page.mouse.click(cx, cy)
                    page.wait_for_timeout(300)
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    page.keyboard.type(str(fill_value))
                self.push_action_context("fill", bbox_id, f"Input: {fill_value}", justificativa)
                return True, f"FILLED_{bbox_id}"

        return False, "MAX_RETRIES_EXCEEDED"

    def advance_application(
        self,
        application_id: str,
        url: str,
        job_name: str = "",
        company: str = "",
        dry_run: bool = False,
        visible: bool = False
    ) -> Dict[str, Any]:
        """Avança as etapas de uma candidatura específica da Gupy."""
        from playwright.sync_api import sync_playwright

        logger.info(f"[ADVANCER GUPY] Iniciando avanço para {job_name} ({company}) - App ID: {application_id}")
        job_context = f"{job_name} na empresa {company} (Gupy Application #{application_id})"

        step_count = 0
        final_status = "IN_PROGRESS"

        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome",
                headless=not visible,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-infobars"]
            )
            context_args = {
                "viewport": {"width": 1280, "height": 1080},
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
            }

            state_file = self.session_mgr.session_path
            if state_file.exists():
                context_args["storage_state"] = str(state_file)

            context = browser.new_context(**context_args)
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40)
                page.wait_for_timeout(3000)

                body_text = page.inner_text("body").lower()
                if "404" in page.title() or "não encontramos a página" in body_text or "ops! não encontramos" in body_text:
                    logger.warning(f"[ADVANCER GUPY] Candidatura {application_id} não encontrada ou encerrada pela empresa (404). Pulando.")
                    self._update_candidatura_db(application_id, step=0, status_esteira="ENCERRADA_404")
                    try:
                        conn = sqlite3.connect(self.db_path)
                        conn.execute("UPDATE candidaturas SET application_status = 'expired' WHERE application_id = ? OR id = ?", (application_id, application_id))
                        conn.commit()
                        conn.close()
                    except Exception:
                        pass
                    return {"status": "ENCERRADA_404", "application_id": application_id}

                if "login" in page.url or "identity.gupy.io" in page.url:
                    logger.warning(f"[ADVANCER GUPY] Redirecionado para tela de login ({page.url}). Sessão desautenticada para {application_id}.")
                    return {"status": "AUTH_REQUIRED", "application_id": application_id}

                while step_count < MAX_STEPS_PER_APPLICATION:
                    step_count += 1
                    logger.info(f"[ADVANCER GUPY] Iteração SoM #{step_count}/{MAX_STEPS_PER_APPLICATION}...")

                    active_page = context.pages[-1] if context.pages else page
                    if active_page != page:
                        logger.info(f"[ADVANCER GUPY] Alternando para aba ativa: {active_page.url}")
                        active_page.bring_to_front()

                    bboxes, meta, shot_path = self.annotate_page(active_page, shot_name=f"app_{application_id}_step_{step_count}")

                    should_continue, step_result = self.validate_and_execute_step(
                        page=active_page,
                        bboxes=bboxes,
                        meta=meta,
                        screenshot_path=shot_path,
                        job_context=job_context
                    )

                    self._update_candidatura_db(
                        application_id=application_id,
                        step=step_count,
                        status_esteira=f"ETAPA_{step_count}_{step_result}"
                    )

                    if not should_continue:
                        final_status = step_result
                        break

                    active_page.wait_for_timeout(3500)

                if step_count >= MAX_STEPS_PER_APPLICATION:
                    logger.warning("[ADVANCER GUPY CIRCUIT BREAKER] Limite máximo de etapas por job atingido.")
                    final_status = "CIRCUIT_BREAKER_LIMIT"

            except Exception as e:
                logger.error(f"[ADVANCER GUPY] Erro durante navegação da candidatura {application_id}: {e}")
                final_status = f"ERRO_{str(e)[:40]}"
            finally:
                browser.close()

        self._update_candidatura_db(
            application_id=application_id,
            step=step_count,
            status_esteira=final_status
        )

        return {
            "application_id": application_id,
            "steps_executed": step_count,
            "status": final_status
        }

    def _update_candidatura_db(self, application_id: str, step: int, status_esteira: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE candidaturas
                SET current_step = ?, status_esteira = ?, updated_at = ?
                WHERE application_id = ? OR id = ?
            """, (step, status_esteira, time.strftime("%Y-%m-%d %H:%M:%S"), application_id, application_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"[ADVANCER DB] Aviso ao atualizar estado de candidatura: {e}")

    def run_pipeline(self, limit: int = 5, dry_run: bool = False, visible: bool = False) -> List[Dict[str, Any]]:
        state_file = self.session_mgr.session_path
        if not state_file.exists():
            logger.warning("[ADVANCER GUPY] Arquivo de sessão 'gupy_session.json' ausente. Pulando avanço.")
            return []
        logger.info(f"[ADVANCER GUPY] Buscando até {limit} candidaturas ativas no banco...")
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            query = """
                SELECT id, application_id, job_name, company, direct_url
                FROM candidaturas
                WHERE application_status = 'in_process'
                ORDER BY updated_at ASC, id ASC
                LIMIT ?
            """
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            conn.close()

            for r in rows:
                c_id, app_id, job_name, company, direct_url = r
                target_url = direct_url or f"https://portal.gupy.io/candidate/applications/{app_id}"
                res = self.advance_application(
                    application_id=str(app_id or c_id),
                    url=target_url,
                    job_name=job_name or "Vaga Gupy",
                    company=company or "Confidencial",
                    dry_run=dry_run,
                    visible=visible
                )
                results.append(res)
        except Exception as e:
            logger.error(f"[ADVANCER GUPY] Erro ao executar pipeline: {e}")

        return results
