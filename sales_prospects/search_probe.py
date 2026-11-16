"""Opt-in provider diagnostics; no prospect or contact records are changed."""
import hashlib
import json
import logging
import os
from pathlib import Path
from tempfile import gettempdir
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOG = logging.getLogger(__name__)
CASES = (
    ("paris-current-web", {"q": "paris evening dress", "num": 20, "page": 1, "hl": "en"}),
    ("paris-current-instagram", {"q": "site:instagram.com paris evening dress boutique shop", "num": 20, "page": 1, "hl": "en"}),
    ("paris-local-web", {"q": "paris evening dress boutique", "num": 10, "page": 1, "hl": "fr", "gl": "fr"}),
    ("berlin-local-web", {"q": "berlin evening dress boutique", "num": 10, "page": 1, "hl": "de", "gl": "de"}),
    ("paris-simple-instagram", {"q": "site:instagram.com paris evening dress", "num": 10, "page": 1, "hl": "fr", "gl": "fr"}),
)


def probe_if_requested():
    run = os.environ.get("MOLI_SEARCH_PROBE", "").strip()
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if not run or not key:
        return
    token = hashlib.sha256(run.encode()).hexdigest()[:20]
    for index, (label, payload) in enumerate(CASES):
        marker = Path(gettempdir()) / ("moli-search-probe-" + token + "-" + str(index))
        try:
            fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            continue
        os.close(fd)
        request = Request("https://google.serper.dev/search", data=json.dumps(payload).encode(),
                          headers={"X-API-KEY": key, "Content-Type": "application/json",
                                   "Accept": "application/json", "User-Agent": "MoliApp/1.0"}, method="POST")
        report = {"probe": label, "query": payload["q"]}
        try:
            with urlopen(request, timeout=8) as response:
                data = json.loads(response.read(1_000_001))
                report["http"] = response.status
            rows = data.get("organic", []) if isinstance(data, dict) else []
            report["returned"] = len(rows) if isinstance(rows, list) else None
            report["sample"] = [{"title": str(x.get("title", ""))[:150],
                                  "url": str(x.get("link", ""))[:300]}
                                 for x in rows[:6] if isinstance(x, dict)] if isinstance(rows, list) else []
        except HTTPError as exc:
            report["http"] = exc.code
            raw = exc.read(2048).decode("utf-8", "replace").replace(key, "[redacted]")
            try:
                data = json.loads(raw)
                report["error"] = str(data.get("message", data.get("error", "Provider error")))[:300]
            except (ValueError, AttributeError):
                report["error"] = "Non-JSON provider error"
        except (URLError, TimeoutError, ValueError, OSError) as exc:
            report["error"] = type(exc).__name__
        LOG.warning("MOLI_SEARCH_PROBE %s", json.dumps(report, ensure_ascii=True))
        return report
