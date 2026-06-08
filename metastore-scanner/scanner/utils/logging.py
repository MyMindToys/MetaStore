"""Structured logging helpers."""

from __future__ import annotations

import logging
import sys
from typing import Any


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_extra(logger: logging.Logger, msg: str, **fields: Any) -> None:
    if fields:
        suffix = " ".join(f"{k}={fields[k]!r}" for k in sorted(fields))
        logger.info("%s | %s", msg, suffix)
    else:
        logger.info(msg)
