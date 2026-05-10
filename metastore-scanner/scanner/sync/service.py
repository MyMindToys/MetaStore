"""Sync scan batches to server with offline queue."""

from __future__ import annotations

import logging
from typing import Any

from scanner import __version__
from scanner.api.client import ApiClientConfig, MetaStoreApiClient
from scanner.cache.db import ScannerCache
from scanner.models.dto import ScanBatch

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, cache: ScannerCache, client: MetaStoreApiClient) -> None:
        self.cache = cache
        self.client = client

    def enqueue_batch(self, batch: ScanBatch) -> int:
        payload = batch.to_json_dict()
        return self.cache.enqueue_sync({"type": "scan_upload", "payload": payload})

    def flush_queue(self, limit: int = 20) -> tuple[int, int]:
        """Returns (success_count, error_count)."""
        pending = self.cache.pending_sync_batch(limit=limit)
        ok = 0
        err = 0
        for qid, item in pending:
            try:
                if item.get("type") == "scan_upload":
                    self.client.upload_scan_results(item["payload"])
                else:
                    raise ValueError(f"Unknown queue item type: {item.get('type')}")
                self.cache.mark_sync_done(qid)
                ok += 1
            except Exception as exc:
                logger.warning("sync failed id=%s: %s", qid, exc)
                self.cache.mark_sync_error(qid, str(exc))
                err += 1
        return ok, err


def build_client(server_url: str, token: str | None) -> MetaStoreApiClient:
    return MetaStoreApiClient(ApiClientConfig(base_url=server_url, scanner_token=token))


def default_scanner_version() -> str:
    return __version__
