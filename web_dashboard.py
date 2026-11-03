"""
JARVIS RPA VAGAS - Visual Live Web Dashboard
Front-end interativo em tempo real para monitorar a execução do robô Gupy no PC2.
Porta padrão: 8888
"""
import os
import sys
import time
import json
import sqlite3
import asyncio
import subprocess
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

ROOT_DIR = Path(__file__).resolve().parent
SCREENSHOTS_DIR = ROOT_DIR / "logs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = ROOT_DIR / "data" / "rpa_vagas.db"

app = FastAPI(title="JARVIS RPA Vagas Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EXECUTION_STATE = {
    "is_running_cycle": False,
    "last_cycle_started": None,
    "last_cycle_finished": None,
    "current_action": "Aguardando próximo ciclo agendado"
}

def get_db_stats():
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM vagas")
    total_vagas = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM vagas WHERE match_score >= 80")
    top_matches = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM candidaturas WHERE application_status = 'in_process'")
    ativas = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM candidaturas")
    total_apps = cur.fetchone()[0]
    
    cur.execute("SELECT work_mode, count(*) as c FROM vagas GROUP BY work_mode")
    modalidades = {r["work_mode"]: r["c"] for r in cur.fetchall()}

    cur.execute("""
        SELECT title, company, location, work_mode, match_score, url, updated_at 
        FROM vagas 
        ORDER BY match_score DESC, updated_at DESC 
        LIMIT 15
    """ )
    top_vagas = [dict(r) for r in cur.fetchall()]
    conn.close()

    return {
        "total_vagas": total_vagas,
        "top_matches": top_matches,
        "candidaturas_ativas": ativas,
        "total_candidaturas": total_apps,
        "modalidades": modalidades,
        "recent_jobs": top_vagas
    }

@app.get("/api/status")
def get_status():
    stats = get_db_stats()
    session_file = ROOT_DIR / "data" / "gupy_session.json"
    return {
        "service_state": EXECUTION_STATE,
        "gupy_session_present": session_file.exists(),
        "stats": stats
    }

@app.get("/api/screenshot/live")
def get_live_screenshot():
    latest = SCREENSHOTS_DIR / "live_latest.png"
    if latest.exists():
        return FileResponse(latest, media_type="image/png", headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
    
    all_pngs = sorted(SCREENSHOTS_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if all_pngs:
        return FileResponse(all_pngs[0], media_type="image/png")

    placeholder = SCREENSHOTS_DIR / "placeholder.png"
    if not placeholder.exists():
        import base64
        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        with open(placeholder, "wb") as f:
            f.write(png_data)
    return FileResponse(placeholder, media_type="image/png")

@app.get("/api/screenshots/list")
def list_screenshots():
    all_pngs = sorted(SCREENSHOTS_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "mtime": p.stat().st_mtime, "size": p.stat().st_size} for p in all_pngs[:25]]

DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "")

def verify_dashboard_auth(authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)):
    if not DASHBOARD_API_KEY:
        return True
    token = x_api_key or (authorization.replace("Bearer ", "") if authorization else "")
    if token != DASHBOARD_API_KEY:
        raise HTTPException(status_code=401, detail="Não autorizado")
    return True

@app.get("/api/screenshot/{filename}")
def get_screenshot(filename: str):
    clean_name = Path(filename).name
    file_path = (SCREENSHOTS_DIR / clean_name).resolve()
    try:
        if not file_path.is_relative_to(SCREENSHOTS_DIR.resolve()) or not file_path.exists():
            raise HTTPException(status_code=404, detail="Screenshot não encontrado")
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=404, detail="Screenshot não encontrado")
    return FileResponse(file_path, media_type="image/png")

async def log_stream_generator() -> AsyncGenerator[str, None]:
    cmd = ["journalctl", "--user", "-u", "gupy-vagas.service", "-f", "-n", "35", "--no-pager"]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    try:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                yield f"data: {json.dumps({'log': text})}\n\n"
    except asyncio.CancelledError:
        process.kill()
        raise

@app.get("/api/stream/logs")
async def stream_logs(_: bool = Depends(verify_dashboard_auth)):
    return StreamingResponse(log_stream_generator(), media_type="text/event-stream")

def run_cycle_background():
    EXECUTION_STATE["is_running_cycle"] = True
    EXECUTION_STATE["last_cycle_started"] = time.strftime("%H:%M:%S")
    EXECUTION_STATE["current_action"] = "Mineração e Avaliação no Portal Gupy em andamento..."
    try:
        venv_python = ROOT_DIR / ".venv" / "bin" / "python"
        subprocess.run(
            [str(venv_python), "gupy_service.py", "cycle"],
            cwd=str(ROOT_DIR),
            check=True
        )
    except Exception as e:
        EXECUTION_STATE["current_action"] = f"Erro no ciclo: {e}"
    finally:
        EXECUTION_STATE["is_running_cycle"] = False
        EXECUTION_STATE["last_cycle_finished"] = time.strftime("%H:%M:%S")
        EXECUTION_STATE["current_action"] = "Ciclo concluído. Aguardando próximo agendamento."

@app.post("/api/actions/run-cycle")
def trigger_cycle(background_tasks: BackgroundTasks, _: bool = Depends(verify_dashboard_auth)):
    if EXECUTION_STATE["is_running_cycle"]:
        return JSONResponse({"status": "already_running", "message": "Ciclo já está em execução no momento."})
    background_tasks.add_task(run_cycle_background)
    return {"status": "triggered", "message": "Ciclo avulso disparado com sucesso no PC2."}

@app.get("/", response_class=HTMLResponse)
def index_page():
    index_html = ROOT_DIR / "static" / "index.html"
    if index_html.exists():
        with open(index_html, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>JARVIS Dashboard</h1>"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
