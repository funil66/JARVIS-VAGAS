#!/usr/bin/env python3
"""
CLI Orchestrator for RPA Vagas (Automated Job Search & Application Bot)
"""
import sys
import time
import logging
import argparse
from pathlib import Path

# Set up module path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from .database.repository import VagasRepository
    from .engine.orchestrator import VagasOrchestrator
    from .engine.evaluator import JobEvaluator
    from .config import MIN_MATCH_SCORE_TO_APPLY
except (ImportError, ValueError):
    from database.repository import VagasRepository
    from engine.orchestrator import VagasOrchestrator
    from engine.evaluator import JobEvaluator
    from config import MIN_MATCH_SCORE_TO_APPLY

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
console = Console()

def cmd_search(args):
    terms = [t.strip() for t in args.terms.split(",")] if args.terms else None
    platforms = [p.strip() for p in args.platforms.split(",")] if args.platforms else None
    
    console.print(f"[bold cyan]🔍 Iniciando busca de vagas...[/bold cyan]")
    orch = VagasOrchestrator()
    jobs = orch.run_search(terms=terms, location=args.location, limit_per_source=args.limit, platforms=platforms)
    console.print(f"[bold green]✨ Busca concluída! {len(jobs)} vagas coletadas e avaliadas.[/bold green]")

def cmd_evaluate(args):
    orch = VagasOrchestrator()
    count = orch.evaluate_pending_jobs()
    console.print(f"[bold green]✅ {count} vagas avaliadas com sucesso.[/bold green]")

def cmd_list(args):
    repo = VagasRepository()
    jobs = repo.list_jobs(
        status=args.status,
        min_score=args.min_score,
        work_mode=args.mode,
        platform=args.platform,
        limit=args.limit
    )

    if not jobs:
        console.print("[yellow]Nenhuma vaga encontrada para os filtros especificados.[/yellow]")
        return

    table = Table(title=f"📋 Vagas Jurídicas ({len(jobs)} exibidas)", header_style="bold magenta")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Match", justify="center")
    table.add_column("Modalidade", justify="center")
    table.add_column("Cargo", style="white")
    table.add_column("Empresa", style="green")
    table.add_column("Local", style="blue")
    table.add_column("Plataforma", justify="center", style="yellow")
    table.add_column("Status", justify="center")

    for j in jobs:
        mode_badge = "🏠 Remoto" if j.work_mode == "REMOTE" else ("🏢/🏠 Híbrido" if j.work_mode == "HYBRID" else "🏢 Presencial")
        score_badge = f"[bold green]{j.match_score}%[/bold green]" if j.match_score >= 80 else (f"[yellow]{j.match_score}%[/yellow]" if j.match_score >= 50 else f"[red]{j.match_score}%[/red]")
        status_badge = f"[bold blue]{j.status}[/bold blue]" if j.status == "APPLIED" else f"{j.status}"

        table.add_row(
            str(j.id),
            score_badge,
            mode_badge,
            j.title[:35],
            j.company[:25],
            j.location[:20],
            j.platform.upper(),
            status_badge
        )

    console.print(table)

def cmd_stats(args):
    repo = VagasRepository()
    stats = repo.get_stats()

    content = (
        f"[bold]Total de Vagas Mapeadas:[/bold] {stats['total_vagas']}\n"
        f"[bold]Top Matches (Score ≥ 80%):[/bold] [green]{stats['top_matches_80plus']}[/green]\n"
        f"[bold]Candidaturas Enviadas:[/bold] [cyan]{stats['candidaturas_enviadas']}[/cyan]\n\n"
        f"[bold]Por Status:[/bold] {stats['por_status']}\n"
        f"[bold]Por Modalidade:[/bold] {stats['por_modalidade']}\n"
        f"[bold]Por Plataforma:[/bold] {stats['por_plataforma']}"
    )

    console.print(Panel(content, title="📊 Estatísticas do RPA de Vagas", border_style="cyan"))

def cmd_letter(args):
    repo = VagasRepository()
    job = repo.get_job(args.id)
    if not job:
        console.print(f"[red]Vaga com ID {args.id} não encontrada.[/red]")
        return

    evaluator = JobEvaluator()
    letter = evaluator.generate_cover_letter(job)
    console.print(Panel(letter, title=f"✉️ Carta de Apresentação: {job.title} ({job.company})", border_style="green"))

def cmd_apply(args):
    orch = VagasOrchestrator()
    dry_run = not args.prod
    mode_text = "[yellow]SIMULAÇÃO (DRY-RUN)[/yellow]" if dry_run else "[bold red]PRODUÇÃO REAL[/bold red]"
    console.print(f"🚀 Iniciando candidaturas em modo {mode_text} (Score Mínimo: {args.min_score}%)...")

    results = orch.apply_to_top_jobs(min_score=args.min_score, dry_run=dry_run, max_applications=args.limit)

    for r in results:
        status_color = "green" if r["status"] == "SUCCESS" else "red"
        console.print(f"[{status_color}]• Vaga #{r['job_id']}: {r['title']} ({r['company']}) - {r['details']}[/{status_color}]")

def cmd_sync_vault(args):
    orch = VagasOrchestrator()
    path = orch.obsidian_sync.sync()
    console.print(f"[bold green]✅ Painel Obsidian atualizado com sucesso em: {path}[/bold green]")

def cmd_crawler(args):
    from bots.advancer import AdvancerBot
    advancer = AdvancerBot()

    if getattr(args, "check", False):
        console.print("[bold cyan]🔍 Verificando integridade da sessão Gupy em tempo real...[/bold cyan]")
        valid, reason = advancer.session_mgr.verify_session_detail()
        if valid:
            console.print(f"[bold green]✅ Sessão Autenticada e Válida![/bold green] ({reason})")
        else:
            console.print(f"[bold red]❌ Sessão Inválida / Deslogada:[/bold red] {reason}")
            console.print("[yellow]💡 Dica: Execute 'python cli.py crawler --login' para autenticar.[/yellow]")
        return

    if getattr(args, "login", False):
        console.print("[bold cyan]🔑 Iniciando autenticação interativa no Google Chrome...[/bold cyan]")
        success = advancer.session_mgr.interactive_login()
        if success:
            console.print("[bold green]🎉 Login concluído e sessão confirmada em tempo real![/bold green]")
        else:
            console.print("[bold red]❌ Falha na autenticação ou timeout excedido.[/bold red]")
        return

    console.print(f"[bold cyan]🔍 Executando avanço multimodal Set-of-Mark (Limite: {args.limit}, Produção: {args.prod})...[/bold cyan]")
    advancer.run_pipeline(limit=args.limit, dry_run=(not args.prod), visible=args.visible)

def cmd_daemon(args):
    console.print(f"[bold cyan]🤖 Iniciando RPA Vagas Daemon Bimodal (Hunter + Advancer) (Intervalo: {args.interval} minutos)...[/bold cyan]")
    from bots.hunter import HunterBot
    from bots.advancer import AdvancerBot

    hunter = HunterBot()
    orch = VagasOrchestrator()
    advancer = AdvancerBot()

    while True:
        try:
            console.print(f"\n[bold yellow]⏰ [{time.strftime('%Y-%m-%d %H:%M:%S')}] Executando ciclo de monitoramento & descoberta (Hunter)...[/bold yellow]")
            hunter.discover_jobs()
            if args.auto_apply:
                orch.apply_to_top_jobs(min_score=args.min_score, dry_run=(not args.prod))

            if getattr(args, "crawl_steps", True):
                try:
                    console.print("[cyan]🔄 Verificando e avançando etapas via Visão Computacional (Advancer Set-of-Mark)...[/cyan]")
                    advancer.run_pipeline(limit=10, dry_run=(not args.prod), visible=False)
                except Exception as adv_err:
                    console.print(f"[yellow]Aviso no avanço de etapas: {adv_err}[/yellow]")
            console.print(f"💤 Aguardando {args.interval} minutos até a próxima varredura...")
            time.sleep(args.interval * 60)
        except KeyboardInterrupt:
            console.print("\n[red]Daemon finalizado pelo operador.[/red]")
            break
        except Exception as e:
            console.print(f"[red]Erro no ciclo do daemon: {e}[/red]")
            time.sleep(60)

def main():
    parser = argparse.ArgumentParser(description="RPA Vagas - Automação de Busca e Candidatura de Empregos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search
    p_search = subparsers.add_parser("search", help="Busca vagas nas plataformas")
    p_search.add_argument("--terms", help="Termos separados por vírgula")
    p_search.add_argument("--location", default="Brasil", help="Localização de busca")
    p_search.add_argument("--platforms", help="Plataformas: gupy,indeed,linkedin,glassdoor")
    p_search.add_argument("--limit", type=int, default=15, help="Limite por plataforma")

    # Evaluate
    subparsers.add_parser("evaluate", help="Avalia e calcula match score de vagas pendentes")

    # List
    p_list = subparsers.add_parser("list", help="Lista vagas salvas")
    p_list.add_argument("--status", help="Filtrar por status (DISCOVERED, EVALUATED, APPLIED)")
    p_list.add_argument("--min-score", type=int, help="Score mínimo de compatibilidade")
    p_list.add_argument("--mode", help="Modalidade: REMOTE, HYBRID, PRESENTIAL")
    p_list.add_argument("--platform", help="Filtrar por plataforma")
    p_list.add_argument("--limit", type=int, default=30, help="Limite de resultados")

    # Stats
    subparsers.add_parser("stats", help="Exibe estatísticas consolidadas")

    # Letter
    p_letter = subparsers.add_parser("letter", help="Gera carta de apresentação para uma vaga")
    p_letter.add_argument("--id", type=int, required=True, help="ID da vaga")

    # Apply
    p_apply = subparsers.add_parser("apply", help="Envia candidaturas para as melhores vagas")
    p_apply.add_argument("--min-score", type=int, default=MIN_MATCH_SCORE_TO_APPLY, help="Score mínimo")
    p_apply.add_argument("--limit", type=int, default=5, help="Número máximo de candidaturas")
    p_apply.add_argument("--prod", action="store_true", help="Executa envio real (sem dry-run)")

    # Sync Vault
    subparsers.add_parser("sync-vault", help="Sincroniza notas e painel no Obsidian")

    # Crawler Gupy
    p_crawler = subparsers.add_parser("crawler", help="Varre e avança etapas de testes e questionários na Gupy")
    p_crawler.add_argument("--limit", type=int, default=10, help="Limite de candidaturas a processar")
    p_crawler.add_argument("--prod", action="store_true", help="Avança e submete de fato (sem dry-run)")
    p_crawler.add_argument("--visible", action="store_true", help="Navegador visível")
    p_crawler.add_argument("--check", action="store_true", help="Valida em tempo real se a sessão está autenticada")
    p_crawler.add_argument("--login", action="store_true", help="Abre o Chrome oficial via CDP para efetuar login")

    # Daemon
    p_daemon = subparsers.add_parser("daemon", help="Executa serviço contínuo em segundo plano")
    p_daemon.add_argument("--interval", type=int, default=60, help="Intervalo em minutos")
    p_daemon.add_argument("--auto-apply", action="store_true", help="Candidata automaticamente")
    p_daemon.add_argument("--crawl-steps", action="store_true", default=True, help="Avança etapas ativas na Gupy")
    p_daemon.add_argument("--prod", action="store_true", help="Produção real no daemon")
    p_daemon.add_argument("--min-score", type=int, default=80, help="Score mínimo para auto-apply")

    args = parser.parse_args()
    cmds = {
        "search": cmd_search,
        "evaluate": cmd_evaluate,
        "list": cmd_list,
        "stats": cmd_stats,
        "letter": cmd_letter,
        "apply": cmd_apply,
        "sync-vault": cmd_sync_vault,
        "daemon": cmd_daemon,
        "crawler": cmd_crawler,
    }

    cmds[args.command](args)

if __name__ == "__main__":
    main()
