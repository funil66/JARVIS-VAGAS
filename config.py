"""
Configuration settings for JARVIS Vagas (Gupy Autonomous Worker)
Isolado exclusivamente para Gupy Portal & Google Gemini 3.8 Flash (VLM).
Eliminados quaisquer modelos ou plataformas legadas (LinkedIn, Indeed, JobSpy, 9Router).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Local directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load local .env or root .env
if (BASE_DIR / ".env").exists():
    load_dotenv(BASE_DIR / ".env")
else:
    load_dotenv(BASE_DIR.parent.parent / ".env")

# Canonical Database Path
DB_PATH = DATA_DIR / "rpa_vagas.db"
if not DB_PATH.exists() and (DATA_DIR / "jarvis_vagas.db").exists():
    DB_PATH = DATA_DIR / "jarvis_vagas.db"

# Candidate CV path
LOCAL_CV_PATH = Path(os.getenv("LOCAL_CV_PATH", DATA_DIR / "curriculo_exemplo.pdf"))
CV_DEFAULT_PATH = LOCAL_CV_PATH

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Tier 1 AI Agent Configuration - Motor Visual Oficial (Google GenAI Multimodal)
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or ""
)
GOOGLE_API_KEY = GEMINI_API_KEY
GEMINI_PRIMARY_MODEL = "gemini-flash-lite-latest"
GEMINI_FALLBACK_MODELS = ["gemini-3-flash-preview"]
GEMINI_MODEL = GEMINI_PRIMARY_MODEL
ROUTER_BASE_URL = os.getenv("ROUTER_BASE_URL", "")
ROUTER_API_KEY = os.getenv("ROUTER_API_KEY", "")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "gemini-flash-lite-latest")

# Gupy Session Configuration
GUPY_PORTAL_URL = "https://portal.gupy.io"
GUPY_APPLICATIONS_URL = "https://portal.gupy.io/candidates/applications"
GUPY_SESSION_PATH = DATA_DIR / "gupy_session.json"

# Matching & Auto-Apply Configuration
MIN_MATCH_SCORE_TO_APPLY = int(os.getenv("MIN_MATCH_SCORE_TO_APPLY", "75"))
MIN_MATCH_SCORE_TO_NOTIFY = int(os.getenv("MIN_MATCH_SCORE_TO_NOTIFY", "60"))
SIMPLE_AUTO_APPLY_MIN_SCORE = int(os.getenv("SIMPLE_AUTO_APPLY_MIN_SCORE", "85"))
HITL_WAIT_TIMEOUT_SECONDS = int(os.getenv("HITL_WAIT_TIMEOUT_SECONDS", "900"))

# Search defaults (Foco exclusivo Gupy)
DEFAULT_SEARCH_TERMS = [
    "Advogado Sênior",
    "Advogado Pleno",
    "Advogado Contencioso Cível",
    "Advogado Bancário",
    "Advogado Legal Ops",
    "Advogado Remoto"
]

DEFAULT_PLATFORMS = ["gupy"]

# Obsidian Vault Synchronization
VAULT_VAGAS_PANEL = DATA_DIR / 'PAINEL_VAGAS_EMPREGO.md'
