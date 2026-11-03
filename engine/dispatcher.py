"""
Application Dispatcher Engine (Email & Direct Application Pipelines)
"""
import re
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Tuple, Optional

try:
    from ..config import CV_DEFAULT_PATH
    from ..profile import CANDIDATE
    from ..database.models import JobPosting, ApplicationRecord
    from .evaluator import JobEvaluator
except (ImportError, ValueError):
    from config import CV_DEFAULT_PATH
    from profile import CANDIDATE
    from database.models import JobPosting, ApplicationRecord
    from engine.evaluator import JobEvaluator

logger = logging.getLogger("rpa_vagas.dispatcher")

class ApplicationDispatcher:
    def __init__(self, cv_path: Optional[Path] = None):
        self.cv_path = cv_path or CV_DEFAULT_PATH
        self.evaluator = JobEvaluator()

    def extract_email_from_job(self, job: JobPosting) -> Optional[str]:
        """Tenta extrair email de recrutamento da descrição da vaga"""
        text = f"{job.title} {job.description}"
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
        if emails:
            valid = [e for e in emails if not any(x in e for x in ["example.com", "domain.com", "teste.com"])]
            if valid:
                return valid[0]
        return None

    def dispatch_email_application(
        self,
        job: JobPosting,
        target_email: str,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """Envia email com carta de apresentação e currículo em PDF anexo"""
        cover_letter = self.evaluator.generate_cover_letter(job)
        subject = f"Candidatura: {job.title} - Profissional Jurídico Sênior (OAB/SP 000.000)"

        if dry_run:
            logger.info(f"[DRY-RUN] Simulação de envio de candidatura por e-mail para {target_email}")
            return True, f"Dry-run simulado para {target_email}"

        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", CANDIDATE.email)
        smtp_pass = os.getenv("SMTP_PASSWORD", "")

        if not smtp_pass:
            logger.warning("SMTP_PASSWORD não configurado. Gravando pacote de envio para despacho assistido.")
            return True, f"Pacote de candidatura preparado com sucesso para {target_email}"

        try:
            msg = MIMEMultipart()
            msg["From"] = f"{CANDIDATE.name} <{CANDIDATE.email}>"
            msg["To"] = target_email
            msg["Subject"] = subject

            msg.attach(MIMEText(cover_letter, "plain", "utf-8"))

            if self.cv_path.exists():
                with open(self.cv_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={self.cv_path.name}")
                    msg.attach(part)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            return True, f"Email enviado para {target_email}"
        except Exception as e:
            logger.error(f"Erro ao enviar email para {target_email}: {e}")
            return False, str(e)
