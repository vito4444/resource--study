"""HTTP client: polite User-Agent, retries with backoff, rate limiting, streamed downloads."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 ships with requests; Retry import path is stable
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover - extremely defensive
    Retry = None  # type: ignore

from . import __version__
from .ratelimit import RateLimiter


class HttpClient:
    def __init__(
        self,
        contact_email: str = "anonymous@example.com",
        timeout: int = 60,
        retries: int = 4,
        rate_limit_seconds: float = 0.0,
    ) -> None:
        self.contact_email = contact_email
        self.timeout = timeout
        self.limiter = RateLimiter(rate_limit_seconds)
        self.user_agent = (
            f"resource-study-harvester/{__version__} "
            f"(+https://github.com/vito4444/resource--study; mailto:{contact_email})"
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        if Retry is not None:
            retry = Retry(
                total=retries,
                connect=retries,
                read=retries,
                status=retries,
                backoff_factor=1.0,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET", "HEAD"}),
                respect_retry_after_header=True,
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> requests.Response:
        self.limiter.wait()
        resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        return self.get(url, params=params, headers=headers).json()

    def get_text(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> str:
        return self.get(url, params=params, headers=headers).text

    def get_bytes(self, url: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        return self.get(url, params=params).content

    def download(self, url: str, dest: Path, overwrite: bool = False) -> Tuple[int, str]:
        """Stream ``url`` to ``dest`` (atomic via .part), returning (bytes, sha256).

        Skips the download and returns the existing file's stats when the file
        already exists and ``overwrite`` is False.
        """
        dest = Path(dest)
        if dest.exists() and not overwrite and dest.stat().st_size > 0:
            return dest.stat().st_size, _sha256_file(dest)

        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        self.limiter.wait()
        hasher = hashlib.sha256()
        total = 0
        with self.session.get(url, stream=True, timeout=self.timeout) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    hasher.update(chunk)
                    total += len(chunk)
        os.replace(tmp, dest)
        return total, hasher.hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
