"""
Database models and dataclasses for RPA Vagas
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class JobPosting:
    id: Optional[int] = None
    platform: str = ""                    # 'gupy', 'linkedin', 'indeed', 'glassdoor', 'catho', 'email'
    external_id: str = ""                # ID on the source platform or hash
    title: str = ""
    company: str = ""
    location: str = ""
    work_mode: str = "REMOTE"            # 'REMOTE', 'HYBRID', 'PRESENTIAL', 'UNKNOWN'
    url: str = ""
    description: str = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: str = "BRL"
    seniority: str = "PLENO"
    specialties: str = ""
    match_score: int = 0                 # 0 - 100
    match_reasoning: str = ""
    priority: str = "BAIXA"              # 'ALTA', 'MEDIA', 'BAIXA'
    status: str = "DISCOVERED"           # 'DISCOVERED', 'EVALUATED', 'APPLIED', 'FAILED', 'SKIPPED', 'INTERVIEW', 'REJECTED'
    applied_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform,
            "external_id": self.external_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "work_mode": self.work_mode,
            "url": self.url,
            "description": self.description,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "currency": self.currency,
            "seniority": self.seniority,
            "specialties": self.specialties,
            "match_score": self.match_score,
            "match_reasoning": self.match_reasoning,
            "priority": self.priority,
            "status": self.status,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

@dataclass
class ApplicationRecord:
    id: Optional[int] = None
    job_id: int = 0
    method: str = "EMAIL"                # 'EMAIL', 'PLAYWRIGHT_FORM', 'GUPY_PORTAL', 'LINKEDIN_EASY'
    cover_letter: str = ""
    cv_path: str = ""
    response_status: str = "SUCCESS"    # 'SUCCESS', 'FAILED', 'PENDING'
    response_details: str = ""
    applied_at: datetime = field(default_factory=datetime.now)
