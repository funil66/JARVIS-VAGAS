"""
supabase_repository.py
Sincronização e Repositório Supabase Cloud / VPS para RPA Vagas.
Conecta diretamente na API REST PostgREST do Supabase (tabelas rpa_vagas e rpa_candidaturas).
"""

import os
import requests
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger("rpa_vagas.supabase")

class SupabaseVagasRepository:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation,resolution=merge-duplicates"
        }
        self.enabled = bool(self.url and self.key and "your-supabase" not in self.url)

    def sync_vaga(self, vaga_dict: Dict[str, Any]) -> bool:
        """Sincroniza vaga descoberta para o Supabase (Upsert por platform + external_id)."""
        if not self.enabled:
            return False

        try:
            endpoint = f"{self.url}/rest/v1/rpa_vagas?on_conflict=platform,external_id"
            payload = {
                "platform": vaga_dict.get("platform", "UNKNOWN"),
                "external_id": str(vaga_dict.get("external_id", "")),
                "title": vaga_dict.get("title", ""),
                "company": vaga_dict.get("company", ""),
                "location": vaga_dict.get("location", ""),
                "work_mode": vaga_dict.get("work_mode", "REMOTE"),
                "url": vaga_dict.get("url", ""),
                "description": (vaga_dict.get("description", "") or "")[:0],
                "salary_min": vaga_dict.get("salary_min"),
                "salary_max": vaga_dict.get("salary_max"),
                "currency": vaga_dict.get("currency", "BRL"),
                "match_score": int(vaga_dict.get("match_score", 0)),
                "match_reasoning": vaga_dict.get("match_reasoning", ""),
                "priority": vaga_dict.get("priority", "BAIXA"),
                "status": vaga_dict.get("status", "DISCOVERED")
            }
            res = requests.post(endpoint, json=payload, headers=self.headers, timeout=8)
            return res.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"Falha ao sincronizar vaga com Supabase: {e}")
            return False

    def record_candidatura(self, job_id: int, method: str, cover_letter: str, status: str = "SUCCESS") -> bool:
        """Registra candidatura efetuada no Supabase."""
        if not self.enabled:
            return False
        try:
            endpoint = f"{self.url}/rest/v1/rpa_candidaturas"
            payload = {
                "job_id": job_id,
                "method": method,
                "cover_letter": cover_letter,
                "response_status": status
            }
            res = requests.post(endpoint, json=payload, headers=self.headers, timeout=8)
            return res.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"Falha ao registrar candidatura no Supabase: {e}")
            return False

    def list_top_vagas(self, min_score: int = 70, limit: int = 20) -> List[Dict[str, Any]]:
        """Busca vagas de alta aderência salvas no Supabase."""
        if not self.enabled:
            return []
        try:
            endpoint = f"{self.url}/rest/v1/rpa_vagas?match_score=gte.{min_score}&order=match_score.desc,created_at.desc&limit={limit}"
            res = requests.get(endpoint, headers=self.headers, timeout=8)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return []
