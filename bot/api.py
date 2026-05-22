"""Minimal HTTP client for ProxyBox admin API — stdlib urllib only."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class ProxyBoxAPI:
    def __init__(
        self,
        base_url: str,
        admin_token: str,
        timeout: int = 10,
        internal_secret: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.token = admin_token
        self.timeout = timeout
        self.internal_secret = internal_secret

    def _url(self, path: str) -> str:
        return f"{self.base_url}/admin/{self.token}{path}"

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = self._url(path)
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        if self.internal_secret:
            headers["X-ProxyBox-Bot-Secret"] = self.internal_secret
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                payload = r.read().decode()
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode()).get("detail", str(e))
            except Exception:
                detail = str(e)
            return {"_error": True, "_status": e.code, "_detail": detail}
        except urllib.error.URLError as e:
            return {"_error": True, "_status": 0, "_detail": str(e.reason)}
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {"_error": True, "_status": 0, "_detail": "non-JSON response"}

    def get(self, path: str) -> dict:
        return self._request("GET", path)

    def post(self, path: str, body: dict | None = None) -> dict:
        return self._request("POST", path, body or {})
