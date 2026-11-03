"""
Gupy Automation Service - Serviço Soberano Unificado de Carreira na Gupy
Roda exclusivamente no PC2 com Google Gemini 3.8 Flash (VLM).
Eliminada qualquer outra plataforma ou robô legado.
"""
import os
import sys
import time
import signal
import logging
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    DEFAULT_SEARCH_TERMS,
    DEFAULT_PLATFORMS,
    DB_PATH
)
from browser.session_manager import GupySessionManager
from bots.hunter import HunterBot
from bots.advancer import AdvancerBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [GUPY-SERVICE] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("gupy_service")

class GupyAutomationService:
    def __init__(self, interval_minutes: int = 60, dry_run: bool = False, visible: bool = False):
        self.interval_seconds = interval_minutes * 60
        self.dry_run = dry_run
        self.visible = visible
        self.running = True

        self.session_mgr = GupySessionManager()
        self.hunter = HunterBot()
        self.advancer = AdvancerBot(gemini_api_key=GEMINI_API_KEY)

        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Sinal de encerramento recebido ({signum}). Parando o serviço Gupy graciosamente...")
        self.running = False

    def health_check(self) -> dict:
        """Verifica a integridade da sessão Gupy e do motor de IA Gemini 3.8 Flash."""
        logger.info("=== VERIFICAÇÃO DE SAÚDE DO SERVIÇO GUPY ===")

        # 1. Checagem Gemini 3.8 Flash
        has_gemini = bool(GEMINI_API_KEY)
        gemini_status = "CONFIGURADA (gemini-3.8-flash)" if has_gemini else "NÃO CONFIGURADA"

        # 2. Checagem de Sessão Gupy
        has_session = self.session_mgr.has_session()
        is_session_active, session_detail = self.session_mgr.verify_session_detail() if has_session else (False, "Arquivo de sessão ausente")

        # 3. Checagem do Banco SQLite
        db_exists = DB_PATH.exists()

        status = {
            "gemini_model": GEMINI_MODEL,
            "gemini_status": gemini_status,
            "gupy_session_file": has_session,
            "gupy_authenticated": is_session_active,
            "gupy_detail": session_detail,
            "database_path": str(DB_PATH),
            "database_exists": db_exists
        }

        for k, v in status.items():
            logger.info(f"  • {k}: {v}")

        return status

    def run_hunt_cycle(self, limit_per_term: int = 15) -> int:
        """Executa a descoberta de novas vagas na Gupy."""
        logger.info(f"Iniciando ciclo de Hunting no Portal Gupy ({len(DEFAULT_SEARCH_TERMS)} termos)...")
        found = self.hunter.discover_jobs(
            terms=DEFAULT_SEARCH_TERMS,
            limit_per_source=limit_per_term,
            platforms=["gupy"]
        )
        logger.info(f"Ciclo de Hunting concluído: {len(found)} vagas capturadas/avaliadas.")
        return len(found)

    def run_advance_cycle(self, limit: int = 10) -> list:
        """Executa o avanço de etapas nas candidaturas ativas da Gupy."""
        logger.info(f"Iniciando avanço de etapas SoM nas candidaturas ativas (limite: {limit})...")
        results = self.advancer.run_pipeline(
            limit=limit,
            dry_run=self.dry_run,
            visible=self.visible
        )
        logger.info(f"Avanço concluído: {len(results)} candidaturas processadas.")
        return results

    def run_full_cycle(self):
        """Executa 1 ciclo completo: Avanço de Etapas/Provas (Prioridade) + Mineração."""
        logger.info("================ INÍCIO DE CICLO GUPY ================")
        try:
            self.run_advance_cycle(limit=10)
        except Exception as e:
            logger.error(f"Erro no ciclo de Avanço: {e}")

        try:
            self.run_hunt_cycle(limit_per_term=15)
        except Exception as e:
            logger.error(f"Erro no ciclo de Hunting: {e}")

        logger.info("================ FIM DE CICLO GUPY ================")

    def run_daemon(self):
        """Loop contínuo 24/7 para rodar como systemd service no PC2."""
        logger.info(f"Iniciando Gupy Service Daemon no PC2 (Intervalo: {self.interval_seconds // 60} minutos)...")
        self.health_check()

        while self.running:
            start_time = time.time()
            try:
                self.run_full_cycle()
            except Exception as e:
                logger.error(f"Exceção não tratada durante o ciclo do daemon: {e}", exc_info=True)

            elapsed = time.time() - start_time
            sleep_time = max(10, self.interval_seconds - elapsed)

            logger.info(f"Aguardando {int(sleep_time)}s para o próximo ciclo autônomo...")

            # Sleep interruptível
            step = 5
            total_slept = 0
            while total_slept < sleep_time and self.running:
                time.sleep(min(step, sleep_time - total_slept))
                total_slept += step

        logger.info("Gupy Service Daemon encerrado.")


def main():
    parser = argparse.ArgumentParser(description="Gupy Autonomous Service (PC2 Native)")
    parser.add_argument("command", choices=["check", "hunt", "advance", "cycle", "daemon", "sync-session"], help="Comando a executar")
    parser.add_argument("--interval", type=int, default=60, help="Intervalo em minutos para o daemon (padrão: 60)")
    parser.add_argument("--limit", type=int, default=10, help="Limite de vagas a processar")
    parser.add_argument("--visible", action="store_true", help="Abrir navegador visível (debug)")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem cliques finais")

    args = parser.parse_args()
    service = GupyAutomationService(
        interval_minutes=args.interval,
        dry_run=args.dry_run,
        visible=args.visible
    )

    if args.command == "check":
        service.health_check()
    elif args.command == "hunt":
        service.run_hunt_cycle(limit_per_term=args.limit)
    elif args.command == "advance":
        service.run_advance_cycle(limit=args.limit)
    elif args.command == "cycle":
        service.run_full_cycle()
    elif args.command == "daemon":
        service.run_daemon()
    elif args.command == "sync-session":
        success = service.session_mgr.sync_from_local_chrome()
        logger.info(f"Sincronização de cookies do Chrome: {'SUCESSO' if success else 'FALHA'}")


if __name__ == "__main__":
    main()
