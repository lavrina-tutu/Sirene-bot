"""Thin Confluence REST client for gantt-chart-planner pages."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from env import CONFLUENCE_BASE, get_token


class ConfluenceError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"Confluence HTTP {status}: {body[:500]}")
        self.status = status
        self.body = body


class ConfluenceClient:
    def __init__(self, token: str | None = None, base_url: str = CONFLUENCE_BASE):
        self.base_url = base_url.rstrip("/")
        self.token = token or get_token()

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        hdrs = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if headers:
            hdrs.update(headers)
        req = Request(url, data=data, headers=hdrs, method=method)
        try:
            with urlopen(req, timeout=120) as resp:
                raw = resp.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ConfluenceError(exc.code, body) from exc
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))

    def get_page(self, page_id: str | int, expand: str = "body.storage,version,space") -> dict:
        return self._request(
            "GET",
            f"/rest/api/content/{page_id}",
            query={"expand": expand},
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
        )

    def put_page(self, page_id: str | int, title: str, storage: str, version: int) -> dict:
        payload = {
            "id": str(page_id),
            "type": "page",
            "title": title,
            "version": {"number": version},
            "body": {"storage": {"value": storage, "representation": "storage"}},
        }
        data = json.dumps(payload).encode("utf-8")
        return self._request(
            "PUT",
            f"/rest/api/content/{page_id}",
            data=data,
            headers={"Content-Type": "application/json", "X-Atlassian-Token": "no-check"},
        )

    def create_page(
        self,
        title: str,
        space_key: str,
        storage: str,
        parent_id: str | int,
    ) -> dict:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "ancestors": [{"id": int(parent_id)}],
            "body": {"storage": {"value": storage, "representation": "storage"}},
        }
        data = json.dumps(payload).encode("utf-8")
        return self._request(
            "POST",
            "/rest/api/content",
            data=data,
            headers={"Content-Type": "application/json", "X-Atlassian-Token": "no-check"},
        )

    def list_attachments(self, page_id: str | int) -> list[dict]:
        out = []
        start = 0
        while True:
            data = self._request(
                "GET", f"/rest/api/content/{page_id}/child/attachment",
                query={"limit": "200", "start": str(start), "expand": "version"},
                headers={"Cache-Control": "no-cache"},
            )
            results = data.get("results", []) if data else []
            out.extend(results)
            if not data or not data.get("_links", {}).get("next"):
                return out
            if not results:
                raise ValueError("attachment pagination did not advance")
            start += len(results)

    def get_attachment(self, attach_id: str | int, version: int | None = None) -> dict:
        query = {"expand": "version,container"}
        if version is not None:
            if type(version) is not int or version < 1:
                raise ValueError("exact attachment version required")
            # `any` includes the just-written current version as well as
            # historical content. The returned version is checked below.
            query.update({"status": "any", "version": str(version)})
        return self._request(
            "GET", f"/rest/api/content/{attach_id}", query=query,
            headers={"Cache-Control": "no-cache"},
        )

    def download_attachment_version(
        self, page_id: str | int, attachment_id: str, filename: str, version: int,
    ) -> bytes:
        """Resolve the exact ID/version before downloading; never substitute latest."""
        metadata = self.get_attachment(attachment_id, version=version)
        if (str(metadata.get("id")) != str(attachment_id)
                or metadata.get("title") != filename
                or metadata.get("version", {}).get("number") != version
                or str(metadata.get("container", {}).get("id")) != str(page_id)):
            raise ValueError("attachment ID/version/page metadata mismatch")
        return self.download_attachment(page_id, filename, version)

    def list_attachment_versions(self, attachment_id: str | int, limit: int = 200) -> list[dict]:
        """Полная пагинация истории версий вложения (P1.W1.10/11, R-011)."""
        out: list[dict] = []
        start = 0
        while True:
            data = self._request(
                "GET",
                f"/rest/experimental/content/{attachment_id}/version",
                query={"limit": str(limit), "start": str(start)},
            )
            if not data:
                break
            results = data.get("results", [])
            out.extend(results)
            if len(results) < limit or not data.get("_links", {}).get("next"):
                break
            start += limit
        return out

    def download_attachment(self, page_id: str | int, filename: str, version: int | None = None) -> bytes:
        query = {"api": "v2"}
        if version is not None:
            query["version"] = str(version)
        url = f"{self.base_url}/download/attachments/{page_id}/{quote(filename, safe='')}"
        if query:
            url = f"{url}?{urlencode(query)}"
        req = Request(url, headers={"Authorization": f"Bearer {self.token}", "Cache-Control": "no-cache"}, method="GET")
        try:
            with urlopen(req, timeout=120) as resp:
                return resp.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ConfluenceError(exc.code, body) from exc
