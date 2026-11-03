#!/usr/bin/env python3
"""
Captura a sessão da Gupy sem bloqueio do Google OAuth ou Passkey.
Abre uma instância do Google Chrome oficial e aguarda o login do usuário.
Assim que detecta a autenticação real no portal/candidaturas, exporta a sessão em data/gupy_session.json
e valida de forma determinística via Playwright headless antes de concluir.
"""
import os
import sys
import time
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from browser.session_manager import (
    GupySessionManager,
    validate_page_auth,
    SESSION_PATH,
    CDP_USER_DATA_DIR,
    CDP_PORT,
    GUPY_LOGIN_URL
)

def main():
    manager = GupySessionManager()
    display = os.environ.get("DISPLAY", ":1")
    print(f"🚀 Iniciando login interativo da Gupy no display {display}...")
    success = manager.interactive_login(timeout_sec=300)
    if success:
        print("\n🎉 SESSÃO AUTENTICADA E CAPTURADA COM SUCESSO ABSOLUTO!")
        print(f"📁 Arquivo validado em: {SESSION_PATH}")
        sys.exit(0)
    else:
        print("\n❌ Falha ao autenticar sessão da Gupy.")
        sys.exit(1)

if __name__ == "__main__":
    main()
