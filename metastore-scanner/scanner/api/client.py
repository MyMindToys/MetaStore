"""HTTP client for MetaStore server API (requests + timeouts + retries)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ApiClientConfig:
    base_url: str
    scanner_token: str | None = None
    timeout_connect: float = 5.0
    timeout_read: float = 60.0
    retries: int = 3
    backoff_factor: float = 0.5


class MetaStoreApiClient:
    def __init__(self, config: ApiClientConfig) -> None:
        self.config = config
        self.session = requests.Session()
        retry = Retry(
            total=config.retries,
            backoff_factor=config.backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if self.config.scanner_token:
            h["Authorization"] = f"Scanner {self.config.scanner_token}"
        return h

    def _url(self, path: str) -> str:
        base = self.config.base_url.rstrip("/")
        p = path if path.startswith("/") else f"/{path}"
        return f"{base}{p}"

    def register_device(
        self,
        machine_uid: str,
        hostname: str,
        os_name: str,
        platform_name: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "machine_uid": machine_uid,
            "hostname": hostname,
            "os_name": os_name,
            "platform_name": platform_name,
            "display_name": display_name,
        }
        r = self.session.post(
            self._url("/api/v1/devices/register/"),
            json=payload,
            headers={**self._headers(), "Content-Type": "application/json"},
            timeout=(self.config.timeout_connect, self.config.timeout_read),
        )
        r.raise_for_status()
        return r.json()

    def upload_scan_results(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = self.session.post(
            self._url("/api/v1/scans/upload/"),
            json=payload,
            headers={**self._headers(), "Content-Type": "application/json"},
            timeout=(self.config.timeout_connect, self.config.timeout_read),
        )
        r.raise_for_status()
        return r.json()

    def send_heartbeat(self, machine_uid: str, scanner_version: str) -> dict[str, Any]:
        payload = {"machine_uid": machine_uid, "scanner_version": scanner_version}
        r = self.session.post(
            self._url("/api/v1/heartbeat/"),
            json=payload,
            headers={**self._headers(), "Content-Type": "application/json"},
            timeout=(self.config.timeout_connect, self.config.timeout_read),
        )
        r.raise_for_status()
        return r.json()

    def get_server_status(self) -> dict[str, Any]:
        r = self.session.get(
            self._url("/api/v1/status/"),
            headers=self._headers(),
            timeout=(self.config.timeout_connect, self.config.timeout_read),
        )
        r.raise_for_status()
        return r.json()
