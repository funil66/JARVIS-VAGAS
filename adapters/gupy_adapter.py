"""
Gupy Portal Adapter - Scrapes Gupy jobs for Brazil Legal & Lawyer vacancies
"""
import logging
import hashlib
import urllib.parse
from typing import List
from playwright.sync_api import sync_playwright

try:
    from .base import BaseJobAdapter
    from ..database.models import JobPosting
except (ImportError, ValueError):
    from adapters.base import BaseJobAdapter
    from database.models import JobPosting

logger = logging.getLogger("rpa_vagas.adapters.gupy")

class GupyAdapter(BaseJobAdapter):
    name: str = "gupy"

    def search_jobs(
        self,
        search_term: str = "advogado",
        location: str = "Brasil",
        limit: int = 20
    ) -> List[JobPosting]:
        results: List[JobPosting] = []
        encoded_term = urllib.parse.quote(search_term)
        url = f"https://portal.gupy.io/job-search/term={encoded_term}"
        
        logger.info(f"Iniciando raspagem Gupy Portal: {url}...")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()
                page.goto(url, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(2000)
                try:
                    live_shot = Path(__file__).resolve().parent.parent / "logs" / "screenshots" / "live_latest.png"
                    live_shot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(live_shot), full_page=False)
                except Exception:
                    pass

                # Query job cards
                cards = page.query_selector_all('[data-testid="job-card-list-item"]')
                if not cards:
                    cards = page.query_selector_all('li a[href*="/job/"]')

                logger.info(f"Encontrados {len(cards)} cards no Gupy.")

                for card in cards[:limit]:
                    try:
                        href = card.get_attribute("href")
                        if not href:
                            continue
                        
                        if not href.startswith("http"):
                            href = urllib.parse.urljoin("https://portal.gupy.io", href)

                        card_text = card.inner_text()
                        lines = [line.strip() for line in card_text.split("\n") if line.strip()]

                        company = lines[0] if lines else "Gupy Enterprise"
                        title = lines[1] if len(lines) > 1 else search_term
                        full_info = " | ".join(lines)

                        mode = "PRESENTIAL"
                        if "remoto" in full_info.lower() or "remote" in full_info.lower():
                            mode = "REMOTE"
                        elif "híbrido" in full_info.lower() or "hibrido" in full_info.lower():
                            mode = "HYBRID"

                        loc = "Brasil"
                        for line in lines:
                            if " - " in line and len(line.split(" - ")[-1]) == 2:
                                loc = line
                                break

                        job_id = hashlib.md5(f"gupy:{href}".encode()).hexdigest()[:16]

                        job = JobPosting(
                            platform="gupy",
                            external_id=job_id,
                            title=title,
                            company=company,
                            location=loc,
                            work_mode=mode,
                            url=href,
                            description=full_info,
                            status="DISCOVERED"
                        )
                        results.append(job)
                    except Exception as e:
                        logger.warning(f"Erro ao extrair card individual Gupy: {e}")

                browser.close()

        except Exception as ex:
            logger.error(f"Erro ao raspar Gupy Portal: {ex}")

        logger.info(f"Gupy retornou {len(results)} vagas.")
        return results
