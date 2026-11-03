"""
Telegram notification & Human-in-the-Loop (HITL) module for RPA Vagas
Supports interactive approval, custom prompt-based edits, and status alerts.
"""
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
import requests

try:
    from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, HITL_WAIT_TIMEOUT_SECONDS
    from ..database.models import JobPosting
except (ImportError, ValueError):
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, HITL_WAIT_TIMEOUT_SECONDS
    from database.models import JobPosting

logger = logging.getLogger("rpa_vagas.notifications.telegram")

class TelegramNotifier:
    def __init__(self, bot_token: str = TELEGRAM_BOT_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
        import os
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.api_url = f"{self.base_url}/sendMessage"
        self._last_update_id = 0
        self.notify_vagas_enabled = os.getenv("TELEGRAM_NOTIFY_VAGAS", "false").lower() in ("true", "1", "yes")

    def notify_jobs_digest(self, jobs: List[JobPosting]) -> bool:
        if not self.notify_vagas_enabled:
            logger.info("Notificação de resumo de vagas silenciada por configuração.")
            return True
        if not self.bot_token or not self.chat_id or not jobs:
            return False
        lines = [
            f"📋 *RADAR DE VAGAS — RESUMO CONSOLIDADO ({len(jobs)} vagas)*",
            ""
        ]
        for i, j in enumerate(jobs[:5], 1):
            mode_badge = "🏠 Remoto" if j.work_mode == "REMOTE" else ("🔄 Híbrido" if j.work_mode == "HYBRID" else "🏢 Presencial")
            company_name = j.company or "Confidencial"
            lines.append(f"*{i}. {j.title}* — _{company_name}_")
            lines.append(f"   📍 {j.location} ({mode_badge}) | ⭐ Match: *{j.match_score}%*")
            lines.append(f"   🔗 [Acessar Vaga]({j.url})")
            lines.append("")
        try:
            r = requests.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": "\n".join(lines),
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True
                },
                timeout=10
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar digest no Telegram: {e}")
            return False

    def notify_job_found(self, job: JobPosting) -> bool:
        if not self.notify_vagas_enabled:
            logger.info("Notificação de vaga encontrada silenciada por configuração.")
            return True
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not set.")
            return False

        mode_badge = "🏠 100% Home Office (Remoto)" if job.work_mode == "REMOTE" else ("🏢/🏠 Híbrido" if job.work_mode == "HYBRID" else "🏢 Presencial")

        text = (
            f"🎯 *NOVA OPORTUNIDADE DE ADVOGADO ENCONTRADA*\n\n"
            f"📌 *Cargo:* {job.title}\n"
            f"🏢 *Empresa:* {job.company or 'Não informada'}\n"
            f"📍 *Local/Modalidade:* {job.location} ({mode_badge})\n"
            f"🌐 *Plataforma:* {job.platform.upper()}\n"
            f"⭐ *Match Score:* *{job.match_score}%* (Prioridade: {job.priority})\n\n"
            f"💡 *Motivo do Match:*\n_{job.match_reasoning}_\n\n"
            f"🔗 [Acessar Vaga e Candidatura]({job.url})\n"
        )

        try:
            r = requests.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False
                },
                timeout=10
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar notificação Telegram: {e}")
            return False

    def notify_application_sent(self, job: JobPosting, method: str, notes: str = "") -> bool:
        if not self.notify_vagas_enabled:
            logger.info("Confirmação de candidatura enviada silenciada por configuração.")
            return True
        if not self.bot_token or not self.chat_id:
            return False

        text = (
            f"✅ *CANDIDATURA SUBMETIDA COM SUCESSO!*\n\n"
            f"📌 *Cargo:* {job.title}\n"
            f"🏢 *Empresa:* {job.company}\n"
            f"🚀 *Método:* {method}\n"
            f"⭐ *Match Score:* {job.match_score}%\n"
        )
        if notes:
            text += f"\n📝 *Observações:* {notes}\n"

        text += f"\n🔗 [Link da Vaga]({job.url})"

        try:
            r = requests.post(
                self.api_url,
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10
            )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao notificar envio no Telegram: {e}")
            return False

    def send_photo(self, photo_path: str, caption: str = "") -> bool:
        """Envia captura de tela comprobatória para o Telegram."""
        if not self.bot_token or not self.chat_id:
            return False
        url = f"{self.base_url}/sendPhoto"
        try:
            with open(photo_path, "rb") as f:
                r = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption, "parse_mode": "Markdown"},
                    files={"photo": f},
                    timeout=20
                )
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar foto no Telegram: {e}")
            return False

    def ask_approval_with_options(
        self,
        job: JobPosting,
        proposed_answers: Dict[str, str],
        cover_letter: str,
        timeout_seconds: int = HITL_WAIT_TIMEOUT_SECONDS,
        tier1_refiner: Optional[Any] = None
    ) -> Tuple[str, Dict[str, str]]:
        """
        HUMAN-IN-THE-LOOP (HITL):
        Envia a proposta de candidatura para o Candidato no Telegram com botões interativos:
        [✅ Aprovar e Enviar] | [✏️ Editar Respostas] | [❌ Rejeitar Vaga]

        Aguarda a confirmação (ou novas instruções de edição por texto) antes de prosseguir.
        Retorna: (decision, final_answers) -> decision: 'approved', 'rejected', 'timeout'
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("Credenciais do Telegram não disponíveis para HITL. Cancelando com segurança.")
            return "timeout", proposed_answers

        # Formata o resumo para o Telegram
        answers_text = ""
        if proposed_answers:
            answers_text = "\n*📝 Respostas Elaboradas pela IA (Tier 1):*\n"
            for q, a in proposed_answers.items():
                short_q = (q[:75] + "...") if len(q) > 75 else q
                answers_text += f"• *{short_q}*\n_{a}_\n\n"

        short_letter = (cover_letter[:280] + "...") if len(cover_letter) > 280 else cover_letter

        prompt_msg = (
            f"🚨 *SOLICITAÇÃO DE APROVAÇÃO — CANDIDATURA COMPLEXA*\n\n"
            f"📌 *Vaga:* {job.title} | *Empresa:* {job.company}\n"
            f"⭐ *Match Score:* *{job.match_score}%* | Modalidade: *{job.work_mode}*\n\n"
            f"*📜 Trecho da Carta de Apresentação:*\n_{short_letter}_\n"
            f"{answers_text}"
            f"⏳ *O navegador está pausado aguardando sua decisão.*"
        )

        job_ref = str(job.id or "current")
        inline_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Aprovar e Enviar", "callback_data": f"approve:{job_ref}"},
                    {"text": "✏️ Editar / Ajustar", "callback_data": f"edit:{job_ref}"}
                ],
                [
                    {"text": "❌ Rejeitar Vaga", "callback_data": f"reject:{job_ref}"}
                ]
            ]
        }

        try:
            # Envia a mensagem com os botões
            resp = requests.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": prompt_msg,
                    "parse_mode": "Markdown",
                    "reply_markup": inline_keyboard
                },
                timeout=15
            )
            if resp.status_code != 200:
                logger.error(f"Falha ao enviar mensagem HITL no Telegram: {resp.text}")
                return "timeout", proposed_answers
        except Exception as e:
            logger.error(f"Exceção ao enviar solicitação HITL: {e}")
            return "timeout", proposed_answers

        # Sincroniza offset para capturar apenas novas mensagens a partir de agora
        self._sync_offset()

        start_time = time.time()
        current_answers = dict(proposed_answers)

        logger.info(f"Aguardando decisão humana no Telegram por até {timeout_seconds} segundos...")

        while time.time() - start_time < timeout_seconds:
            updates = self._get_updates()
            for u in updates:
                # 1. Checa cliques em botões Inline (Callback Query)
                if "callback_query" in u:
                    cb = u["callback_query"]
                    cb_data = cb.get("data", "")
                    cb_id = cb.get("id")

                    if cb_data.startswith(f"approve:{job_ref}"):
                        self._answer_callback(cb_id, "✅ Candidatura Aprovada! Submetendo...")
                        self._send_simple_text("🚀 *Aprovado pelo Candidato!* O bot está finalizando a submissão agora...")
                        return "approved", current_answers

                    elif cb_data.startswith(f"reject:{job_ref}"):
                        self._answer_callback(cb_id, "❌ Vaga rejeitada.")
                        self._send_simple_text("🚫 Vaga rejeitada e descartada pelo usuário.")
                        return "rejected", current_answers

                    elif cb_data.startswith(f"edit:{job_ref}"):
                        self._answer_callback(cb_id, "✏️ Modo de edição ativado.")
                        self._send_simple_text(
                            "✏️ *Modo Edição Ativo:*\n"
                            "Envie sua instrução ou texto revisado agora como resposta nesta conversa "
                            "(ex: _'Coloque pretensão salarial de 12k PJ e enfatize fraudes PIX'_):"
                        )
                        # Aguarda o próximo texto do usuário
                        edited_text = self._wait_for_text_reply(timeout_seconds=300)
                        if edited_text:
                            if tier1_refiner and current_answers:
                                self._send_simple_text("🧠 *Tier 1 refinando as respostas com base na sua instrução...*")
                                for q in list(current_answers.keys()):
                                    current_answers[q] = tier1_refiner.refine_answer_with_user_prompt(
                                        question=q,
                                        current_answer=current_answers[q],
                                        user_instruction=edited_text
                                    )
                            else:
                                current_answers["observacao_adicional"] = edited_text

                            # Re-apresenta com as respostas atualizadas
                            updated_msg = (
                                f"✨ *Respostas Atualizadas com Sucesso:*\n\n"
                            )
                            for q, a in current_answers.items():
                                updated_msg += f"• *{q[:60]}...*\n_{a}_\n\n"
                            updated_msg += "Deseja submeter agora?"

                            requests.post(
                                self.api_url,
                                json={
                                    "chat_id": self.chat_id,
                                    "text": updated_msg,
                                    "parse_mode": "Markdown",
                                    "reply_markup": inline_keyboard
                                },
                                timeout=10
                            )
                        else:
                            self._send_simple_text("⚠️ Nenhuma resposta recebida para a edição a tempo.")

            time.sleep(3)

        self._send_simple_text(f"⏰ *Tempo esgotado ({timeout_seconds // 60} min)* para confirmação da vaga *{job.title}*. Ela foi colocada em pausa.")
        return "timeout", current_answers

    def _sync_offset(self):
        """Descarta mensagens antigas ajustando o offset do getUpdates."""
        try:
            r = requests.get(f"{self.base_url}/getUpdates?offset=-1", timeout=5).json()
            if r.get("ok") and r.get("result"):
                self._last_update_id = r["result"][-1]["update_id"] + 1
        except Exception:
            pass

    def _get_updates(self) -> List[Dict]:
        """Busca novas mensagens / callbacks no Telegram."""
        try:
            url = f"{self.base_url}/getUpdates?offset={self._last_update_id}&timeout=2"
            r = requests.get(url, timeout=6).json()
            if r.get("ok") and r.get("result"):
                results = r["result"]
                self._last_update_id = results[-1]["update_id"] + 1
                return results
        except Exception:
            pass
        return []

    def _answer_callback(self, callback_id: str, text: str):
        try:
            requests.post(f"{self.base_url}/answerCallbackQuery", json={"callback_query_id": callback_id, "text": text}, timeout=5)
        except Exception:
            pass

    def _send_simple_text(self, text: str):
        try:
            requests.post(self.api_url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}, timeout=5)
        except Exception:
            pass

    def _wait_for_text_reply(self, timeout_seconds: int = 300) -> Optional[str]:
        """Espera um texto digitado pelo usuário."""
        start = time.time()
        while time.time() - start < timeout_seconds:
            updates = self._get_updates()
            for u in updates:
                msg = u.get("message")
                if msg and str(msg.get("chat", {}).get("id")) == str(self.chat_id) and "text" in msg:
                    return msg["text"].strip()
            time.sleep(2)
        return None
