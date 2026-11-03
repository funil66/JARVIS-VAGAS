#!/usr/bin/env python3
"""
Módulo de Gerenciamento de Sessão Autenticada Gupy via Playwright.
Persiste e revalida tokens/cookies em data/gupy_session.json para execução 100% autônoma,
com suporte a auto-sincronização transparente a partir do Google Chrome local e
login interativo resiliente via Chrome oficial (CDP).
"""
import os
import sys
import json
import time
import logging
import sqlite3
import shutil
import tempfile
import hashlib
import subprocess
import re
from pathlib import Path
from typing import Optional, Tuple
from playwright.sync_api import sync_playwright, BrowserContext, Page

logger = logging.getLogger("rpa_vagas.browser.session_manager")

ROOT_DIR = Path(__file__).resolve().parent.parent
SESSION_PATH = ROOT_DIR / "data" / "gupy_session.json"
GUPY_LOGIN_URL = "https://login.gupy.io/candidates/signin"
GUPY_PORTAL_APPLICATIONS_URL = "https://portal.gupy.io/my/applications"
CHROME_COOKIES_PATH = Path.home() / ".config" / "google-chrome" / "Default" / "Cookies"
CDP_USER_DATA_DIR = Path("/tmp/chrome_gupy_login_profile")
CDP_PORT = 9222


def validate_page_auth(page: Page) -> Tuple[bool, str]:
    """
    Valida de forma estrita e em tempo real se a página atual do Playwright
    está autenticada na Gupy ou se caiu em tela de visitante / signin.
    """
    try:
        current_url = page.url.lower()

        # 1. Checar se a URL foi redirecionada para telas de autenticação
        if "signin" in current_url or "login.gupy.io" in current_url:
            return False, f"Redirecionado para tela de login/signin: {page.url}"

        # 2. Se estiver no portal Gupy, checar elementos de visitante não autenticado
        if "portal.gupy.io" in current_url:
            visitor_selectors = [
                "a:has-text('Cadastrar CV grátis')",
                "button:has-text('Cadastrar CV grátis')",
                "a:has-text('Entrar')",
                "button:has-text('Entrar')",
            ]
            for sel in visitor_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1200):
                        return False, f"Portal Gupy em modo visitante (elemento visível: {sel})"
                except Exception:
                    pass

            # Checar elementos positivos de usuário autenticado
            auth_selectors = [
                "a:has-text('Minhas candidaturas')",
                "button:has-text('Minhas candidaturas')",
                "div:has-text('Minhas candidaturas')",
                "[data-testid*='application-card']",
                "[data-testid*='candidate']",
                "[data-testid*='user']",
                "[aria-label*='perfil' i]",
                "[aria-label*='menu' i]",
                "button:has-text('Sair')"
            ]
            for sel in auth_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1500):
                        return True, f"Sessão confirmada no Portal (elemento {sel} visível)"
                except Exception:
                    pass

            # Checar se há texto característico de perfil/candidaturas
            body_text = page.locator("body").inner_text()
            if "Minhas candidaturas" in body_text or "Candidaturas ativas" in body_text:
                return True, "Sessão confirmada via texto de candidaturas ativas."

            if "Cadastrar CV" in body_text or "Conectando o seu talento" in body_text:
                return False, "Portal renderizou home pública para visitante anônimo."

        # 3. Se for uma URL de candidatura em subdomínio de empresa
        if "candidates/applications" in current_url:
            body_text = page.locator("body").inner_text()
            if "Entrar com sua conta" in body_text or "Acessar conta" in body_text:
                return False, "Subdomínio exige autenticação da conta de candidato."
            return True, "Acesso à página de candidatura liberado."

        # Redirecionado para home institucional da empresa
        if ".gupy.io" in current_url and "candidates/" not in current_url:
            return False, f"Redirecionado para home institucional pública: {page.url}"

        return True, "Página aberta sem restrição visível de login."

    except Exception as e:
        return False, f"Erro durante validação da página: {e}"


class GupySessionManager:
    def __init__(self, session_path: Optional[Path] = None):
        self.session_path = session_path or SESSION_PATH
        self.session_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def storage_state_path(self) -> Path:
        """Caminho canônico do arquivo de storage_state da sessão Playwright."""
        return self.session_path

    def has_session(self) -> bool:
        """Verifica se o arquivo de storage_state existe e contém dados."""
        if not self.session_path.exists():
            return False
        try:
            if self.session_path.stat().st_size <= 50:
                return False
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
            cookies = data.get("cookies", [])
            origins = data.get("origins", [])
            return len(cookies) > 0 or len(origins) > 0
        except Exception:
            return False

    def sync_from_local_chrome(self) -> bool:
        """
        Método desativado por conformidade com padrões de segurança e privacidade.
        Utilize import_session_from_json para injetar cookies exportados de forma explícita.
        """
        logger.info("[SESSION] sync_from_local_chrome desativado por governança de segurança. Use JSON de sessão.")
        return False

    def verify_session_detail(self, timeout_ms: int = 10) -> Tuple[bool, str]:
        """
        Audita minuciosamente em tempo real se a sessão persistida está de fato
        autenticada no Portal Gupy ou se foi invalidada.
        """
        if not self.has_session():
            return False, "Arquivo de sessão inexistente ou vazio."

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel="chrome", headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
                context = browser.new_context(
                    storage_state=str(self.session_path),
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                resp = page.goto(GUPY_PORTAL_APPLICATIONS_URL, wait_until="domcontentloaded", timeout=timeout_ms)
                time.sleep(2.0)  # Aguardar hidratação de componentes

                is_auth, reason = validate_page_auth(page)
                browser.close()
                return is_auth, reason
        except Exception as e:
            return False, f"Falha na conexão de validação: {e}"

    def is_session_valid(self, timeout_ms: int = 10) -> bool:
        """
        Retorna True apenas se a sessão for confirmada como autenticada em tempo real.
        """
        if not self.has_session():
            return False

        valid, reason = self.verify_session_detail(timeout_ms=timeout_ms)
        if not valid:
            logger.warning(f"[SESSION] Sessão inválida em tempo real: {reason}")
        else:
            logger.info(f"[SESSION] Sessão validada com sucesso: {reason}")
        return valid

    def save_session_from_context(self, context: BrowserContext) -> bool:
        """Salva o estado atual dos cookies/localStorage no arquivo de sessão."""
        try:
            context.storage_state(path=str(self.session_path))
            logger.info(f"[SESSION] Sessão salva com sucesso em {self.session_path}")
            return True
        except Exception as e:
            logger.error(f"[SESSION] Erro ao salvar sessão: {e}")
            return False

    def create_authenticated_context(self, p, headless: bool = True) -> BrowserContext:
        """Cria e retorna um BrowserContext autenticado com o storage_state atual."""
        browser = p.chromium.launch(channel="chrome", headless=headless, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        kwargs = {
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800}
        }

        if self.has_session():
            kwargs["storage_state"] = str(self.session_path)
            logger.info("[SESSION] Carregando cookies e storage_state persistido.")
        else:
            logger.warning("[SESSION] Inicializando contexto sem sessão prévia.")

        return browser.new_context(**kwargs)

    def interactive_login(self, timeout_sec: int = 300) -> bool:
        """
        Abre uma instância oficial do Google Chrome com porta de depuração CDP,
        permitindo login com Google OAuth, Passkey, CPF ou Senha sem bloqueios.
        Monitora em tempo real e captura a sessão assim que o login for autenticado.
        """
        CDP_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        display = os.environ.get("DISPLAY", ":1")
        logger.info(f"[SESSION] Iniciando Google Chrome em {display} via CDP na porta {CDP_PORT}...")

        chrome_cmd = [
            "/usr/bin/google-chrome",
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={CDP_USER_DATA_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            GUPY_LOGIN_URL
        ]

        env = os.environ.copy()
        env["DISPLAY"] = display

        chrome_proc = subprocess.Popen(
            chrome_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env
        )

        time.sleep(3)

        try:
            with sync_playwright() as p:
                try:
                    browser = p.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
                except Exception as cdp_err:
                    logger.error(f"[SESSION] Erro ao conectar ao Chrome via CDP: {cdp_err}")
                    chrome_proc.terminate()
                    return False

                context = browser.contexts[0]
                logger.info("[SESSION] Conectado ao Chrome via CDP. Aguardando conclusão do login pelo usuário...")

                start_time = time.time()
                logged_in = False

                while time.time() - start_time < timeout_sec:
                    for page in context.pages:
                        is_auth, reason = validate_page_auth(page)
                        if is_auth:
                            logger.info(f"[SESSION] Login detectado em tempo real: {reason}")
                            logged_in = True
                            break
                    if logged_in:
                        break
                    time.sleep(2)

                if logged_in:
                    time.sleep(3)  # Aguardar persistência de tokens
                    self.save_session_from_context(context)
                    browser.close()
                    chrome_proc.terminate()

                    # Validação de sanidade do arquivo gerado
                    valid, detail = self.verify_session_detail()
                    if valid:
                        logger.info(f"[SESSION] 🎉 Sessão salva e confirmada com sucesso em tempo real! ({detail})")
                        return True
                    else:
                        logger.warning(f"[SESSION] Arquivo salvo mas re-validação headless falhou: {detail}")
                        return False
                else:
                    logger.warning(f"[SESSION] Timeout de {timeout_sec}s excedido sem confirmação de login.")
                    browser.close()
                    chrome_proc.terminate()
                    return False
        except Exception as e:
            logger.error(f"[SESSION] Falha no fluxo de login interativo: {e}")
            if chrome_proc.poll() is None:
                chrome_proc.terminate()
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    manager = GupySessionManager()

    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        success = manager.sync_from_local_chrome()
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == "--login":
        success = manager.interactive_login()
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == "--check":
        valid, reason = manager.verify_session_detail()
        print(f"Sessão válida: {valid} | Detalhes: {reason}")
        sys.exit(0 if valid else 1)
    else:
        print(f"Possui sessão persistida: {manager.has_session()}")
        if manager.has_session():
            valid, reason = manager.verify_session_detail()
            print(f"Sessão válida: {valid} | Detalhes: {reason}")
