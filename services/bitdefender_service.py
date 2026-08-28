"""Read-only Bitdefender GravityZone API helpers."""

from __future__ import annotations

import base64
import os
import uuid
from typing import Any

import requests

DEFAULT_TIMEOUT = 30


class BitdefenderAPIError(RuntimeError):
    pass


def _read_setting(name: str, default: str = "") -> str:
    try:
        import streamlit as st
        value = st.secrets.get(name, "")
        if value not in (None, ""):
            return str(value).strip()
    except Exception:
        pass
    return str(os.environ.get(name, default) or "").strip()


def _base_url() -> str:
    value = _read_setting("BITDEFENDER_API_URL")
    if not value:
        raise BitdefenderAPIError("Missing BITDEFENDER_API_URL in Streamlit Secrets.")
    return value.rstrip("/")


def _api_key() -> str:
    value = _read_setting("BITDEFENDER_API_KEY")
    if not value:
        raise BitdefenderAPIError("Missing BITDEFENDER_API_KEY in Streamlit Secrets.")
    return value


def _authorization_header() -> str:
    token = base64.b64encode(f"{_api_key()}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _rpc_url(api_name: str) -> str:
    return f"{_base_url()}/v1.0/jsonrpc/{api_name.strip('/')}"


def _rpc(
    api_name: str,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    payload = {
        "id": str(uuid.uuid4()),
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
    }

    try:
        response = requests.post(
            _rpc_url(api_name),
            json=payload,
            headers={
                "Authorization": _authorization_header(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
            verify=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise BitdefenderAPIError(f"GravityZone HTTP request failed: {exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise BitdefenderAPIError("GravityZone returned a non-JSON response.") from exc

    if data.get("error"):
        error = data["error"]
        code = error.get("code", "")
        message = error.get("message", "Unknown GravityZone API error")
        raise BitdefenderAPIError(f"GravityZone API error {code}: {message}")

    return data.get("result")


def test_connection() -> dict[str, Any]:
    result = _rpc(
        "network",
        "getEndpointsList",
        {"page": 1, "perPage": 1, "isManaged": True},
    ) or {}

    return {
        "ok": True,
        "total": result.get("total", 0),
        "pagesCount": result.get("pagesCount", 0),
        "sample": (result.get("items") or [None])[0],
    }


def get_managed_endpoints(*, per_page: int = 1000) -> list[dict[str, Any]]:
    page = 1
    endpoints: list[dict[str, Any]] = []

    while True:
        result = _rpc(
            "network",
            "getEndpointsList",
            {
                "page": page,
                "perPage": max(1, min(int(per_page), 1000)),
                "isManaged": True,
            },
        ) or {}

        items = result.get("items") or []
        endpoints.extend(items)

        pages_count = int(result.get("pagesCount") or 1)
        has_more = result.get("hasMoreRecords")

        if has_more is False or page >= pages_count or not items:
            break
        page += 1

    return endpoints


def get_endpoint_details(
    endpoint_id: str,
    *,
    include_last_logged_users: bool = True,
) -> dict[str, Any]:
    endpoint_id = str(endpoint_id or "").strip()
    if not endpoint_id:
        raise ValueError("endpoint_id is required")

    result = _rpc(
        "network",
        "getManagedEndpointDetails",
        {
            "endpointId": endpoint_id,
            "options": {
                "includeLastLoggedUsers": bool(include_last_logged_users),
            },
        },
    )
    return result or {}


def get_endpoint_policy(endpoint: dict[str, Any]) -> dict[str, Any]:
    policy = endpoint.get("policy") or {}
    return {
        "id": str(policy.get("id") or "").strip(),
        "name": str(policy.get("name") or "").strip(),
        "applied": policy.get("applied"),
    }


def get_policy_catalog() -> Any:
    return _rpc("policies", "getPoliciesList", {})


def normalize_username(value: Any) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if "\\" in value:
        value = value.rsplit("\\", 1)[-1]
    if "@" in value:
        value = value.split("@", 1)[0]
    return value.strip().casefold()
