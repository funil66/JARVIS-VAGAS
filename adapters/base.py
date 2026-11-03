"""
Base adapter interface for job scrapers and aggregators
"""
from abc import ABC, abstractmethod
from typing import List

try:
    from ..database.models import JobPosting
except (ImportError, ValueError):
    from database.models import JobPosting

class BaseJobAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def search_jobs(self, search_term: str, location: str = "Brasil", limit: int = 15) -> List[JobPosting]:
        """Scrapes or queries jobs matching terms"""
        pass
