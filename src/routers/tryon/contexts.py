"""Lightweight dataclasses shared across try-on helpers."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SecurityContext:
    client_ip: Optional[str]
    user_agent: Optional[str]
    is_test_mode: bool
    rate_limit_status: Optional[Dict[str, Any]] = None
    rate_limit_identifier: Optional[str] = None


@dataclass
class UploadResult:
    body_url: str
    garment_urls: List[str]
    uploaded_urls: List[str]


@dataclass
class RecordContext:
    record_id: str
    user_history_record_id: Optional[str]
