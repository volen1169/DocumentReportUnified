"""Read-only Bitdefender GravityZone API helpers."""

from __future__ import annotations

import base64
import os
import re
import uuid
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import Any

import requests

DEFAULT_TIMEOUT = 30


class BitdefenderAPIError(RuntimeError):
    pass


def _redact_sensitive_text(value: Any) -> str:
    """Remove configured credentials and Basic auth values from API errors."""
    text = str(value or "")
    api_key = _read_setting("BITDEFENDER_API_KEY")
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
        token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
        text = text.replace(token, "[REDACTED]")
    return re.sub(r"(?i)basic\s+[a-z0-9+/=]+", "Basic [REDACTED]", text)


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
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        suffix = f" (HTTP {status_code})" if status_code else ""
        raise BitdefenderAPIError(f"GravityZone HTTP request failed{suffix}.") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise BitdefenderAPIError("GravityZone returned a non-JSON response.") from exc

    if data.get("error"):
        error = data["error"]
        code = error.get("code", "")
        message = _redact_sensitive_text(error.get("message", "Unknown GravityZone API error"))
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


def normalize_text(value: Any) -> str:
    """Normalize a value for comparison without changing its display value."""
    return str(value or "").strip().casefold()


def normalize_hostname(value: Any) -> str:
    """Normalize an endpoint hostname and remove an optional FQDN suffix."""
    value = str(value or "").strip().rstrip(".")
    if not value:
        return ""
    return value.split(".", 1)[0].strip().casefold()


def _first_value(endpoint: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = endpoint.get(name)
        if value not in (None, "", [], {}):
            return value
    return ""


def _extract_usernames(endpoint: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    direct = _first_value(
        endpoint,
        "username",
        "userName",
        "lastLoggedInUser",
        "lastLoggedUser",
    )
    if direct:
        values.append(direct)

    users = endpoint.get("users") or endpoint.get("userNames") or []
    if isinstance(users, dict):
        users = [users]
    elif not isinstance(users, (list, tuple, set)):
        users = [users]

    for user in users:
        if isinstance(user, dict):
            value = _first_value(user, "username", "userName", "name", "email", "upn")
        else:
            value = user
        if value not in (None, ""):
            values.append(value)

    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        display = str(value).strip()
        key = display.casefold()
        if display and key not in seen:
            unique.append(display)
            seen.add(key)
    return unique


def normalize_endpoint(endpoint: dict[str, Any]) -> dict[str, Any]:
    """Select safe mapping fields from one GravityZone endpoint."""
    endpoint_name = str(_first_value(endpoint, "name", "endpointName", "label") or "").strip()
    hostname = str(_first_value(endpoint, "hostname", "hostName", "machineName", "computerName") or "").strip()
    fqdn = str(_first_value(endpoint, "fqdn", "fullyQualifiedDomainName") or "").strip()
    usernames = _extract_usernames(endpoint)
    policy = endpoint.get("policy") if isinstance(endpoint.get("policy"), dict) else {}

    return {
        "endpoint_id": str(_first_value(endpoint, "id", "endpointId") or "").strip(),
        "endpoint_name": endpoint_name,
        "hostname": hostname,
        "fqdn": fqdn,
        "usernames": usernames,
        "domain": str(_first_value(endpoint, "domain", "domainName") or "").strip(),
        "managed": _first_value(endpoint, "isManaged", "managed"),
        "status": _first_value(endpoint, "status", "state"),
        "last_seen": _first_value(endpoint, "lastSeen", "lastSeenAt", "lastUpdate"),
        "policy_id": str(policy.get("id") or "").strip(),
        "policy_name": str(policy.get("name") or "").strip(),
        "policy_applied": policy.get("applied"),
        "normalized_endpoint_name": normalize_text(endpoint_name),
        "normalized_hostname": normalize_hostname(hostname or fqdn),
        "normalized_usernames": [name for name in (normalize_username(v) for v in usernames) if name],
    }


def get_managed_endpoint_inventory(*, per_page: int = 1000) -> list[dict[str, Any]]:
    """Return paginated managed endpoints reduced to read-only mapping fields."""
    return [normalize_endpoint(endpoint) for endpoint in get_managed_endpoints(per_page=per_page)]


def build_endpoint_diagnostics(endpoints: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize mapping coverage and safe duplicate-hostname details."""
    hostname_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for endpoint in endpoints:
        hostname = str(endpoint.get("normalized_hostname") or "")
        if hostname:
            hostname_groups[hostname].append(endpoint)

    duplicate_hostnames = []
    for hostname, matches in sorted(hostname_groups.items()):
        if len(matches) < 2:
            continue
        duplicate_hostnames.append(
            {
                "normalized_hostname": hostname,
                "count": len(matches),
                "endpoint_names": sorted(
                    {str(item.get("endpoint_name") or "") for item in matches if item.get("endpoint_name")}
                ),
                "policy_names": sorted(
                    {str(item.get("policy_name") or "") for item in matches if item.get("policy_name")}
                ),
            }
        )

    return {
        "total_managed_endpoints": len(endpoints),
        "endpoints_with_hostname": sum(bool(item.get("normalized_hostname")) for item in endpoints),
        "endpoints_with_username": sum(bool(item.get("normalized_usernames")) for item in endpoints),
        "endpoints_with_policy_name": sum(bool(item.get("policy_name")) for item in endpoints),
        "endpoints_missing_policy": sum(not bool(item.get("policy_name")) for item in endpoints),
        "duplicate_normalized_hostnames": len(duplicate_hostnames),
        "duplicate_hostnames": duplicate_hostnames,
    }


def _endpoint_identity(endpoint: Mapping[str, Any]) -> tuple[str, ...]:
    endpoint_id = str(endpoint.get("endpoint_id") or "").strip()
    if endpoint_id:
        return ("id", endpoint_id)
    return (
        "fields",
        str(endpoint.get("endpoint_name") or ""),
        str(endpoint.get("hostname") or ""),
        str(endpoint.get("fqdn") or ""),
        str(endpoint.get("policy_id") or ""),
    )


def _append_index(
    index: dict[str, list[dict[str, Any]]],
    key: str,
    endpoint: dict[str, Any],
) -> None:
    if not key:
        return
    identity = _endpoint_identity(endpoint)
    if all(_endpoint_identity(item) != identity for item in index[key]):
        index[key].append(endpoint)


def build_endpoint_indexes(endpoints: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build deterministic in-memory indexes without making an API request."""
    inventory = list(endpoints)
    exact_hostname: dict[str, list[dict[str, Any]]] = defaultdict(list)
    normalized_hostname: dict[str, list[dict[str, Any]]] = defaultdict(list)
    username: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for endpoint in inventory:
        for value in (
            endpoint.get("hostname"),
            endpoint.get("fqdn"),
            endpoint.get("endpoint_name"),
        ):
            _append_index(exact_hostname, normalize_text(value), endpoint)
            _append_index(normalized_hostname, normalize_hostname(value), endpoint)

        normalized_usernames = endpoint.get("normalized_usernames") or [
            normalize_username(value) for value in endpoint.get("usernames") or []
        ]
        for value in normalized_usernames:
            _append_index(username, normalize_username(value), endpoint)

    return {
        "inventory": inventory,
        "exact_hostname": dict(exact_hostname),
        "normalized_hostname": dict(normalized_hostname),
        "username": dict(username),
    }


def _asset_value(asset: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = asset.get(name)
        if value not in (None, ""):
            return value
    return ""


def _safe_candidate(endpoint: Mapping[str, Any]) -> dict[str, Any]:
    """Return only fields approved for manual mapping review."""
    return {
        "endpoint_id": str(endpoint.get("endpoint_id") or ""),
        "endpoint_name": str(endpoint.get("endpoint_name") or ""),
        "hostname": str(endpoint.get("hostname") or endpoint.get("fqdn") or ""),
        "policy_name": str(endpoint.get("policy_name") or ""),
        "managed": endpoint.get("managed", ""),
        "last_seen": endpoint.get("last_seen", ""),
    }


def _mapping_base(asset: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "employee_name": str(_asset_value(asset, "field_3", "Employee Name", "Employee", "User") or "").strip(),
        "computer_hostname": str(_asset_value(asset, "field_6", "Hostname", "Computer Name") or "").strip(),
        "login_account": str(_asset_value(asset, "LoginAccount", "Login Account", "Username") or "").strip(),
        "company": str(_asset_value(asset, "Company", "field_1") or "").strip(),
        "matched": False,
        "match_status": "Not Found",
        "match_method": "",
        "match_confidence": "none",
        "endpoint_id": "",
        "endpoint_name": "",
        "endpoint_hostname": "",
        "policy_id": "",
        "policy_name": "",
        "policy_applied": None,
        "policy_missing": False,
        "candidate_count": 0,
        "candidates": [],
    }


def _matched_mapping(
    result: dict[str, Any],
    endpoint: Mapping[str, Any],
    *,
    status: str,
    method: str,
    confidence: str,
) -> dict[str, Any]:
    policy_name = str(endpoint.get("policy_name") or "")
    result.update(
        {
            "matched": True,
            "match_status": status,
            "match_method": method,
            "match_confidence": confidence,
            "endpoint_id": str(endpoint.get("endpoint_id") or ""),
            "endpoint_name": str(endpoint.get("endpoint_name") or ""),
            "endpoint_hostname": str(endpoint.get("hostname") or endpoint.get("fqdn") or ""),
            "policy_id": str(endpoint.get("policy_id") or ""),
            "policy_name": policy_name,
            "policy_applied": endpoint.get("policy_applied"),
            "policy_missing": not bool(policy_name),
            "candidate_count": 1,
        }
    )
    return result


def _ambiguous_mapping(
    result: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    status: str,
    method: str,
) -> dict[str, Any]:
    result.update(
        {
            "match_status": status,
            "match_method": method,
            "match_confidence": "manual_review",
            "candidate_count": len(candidates),
            "candidates": [_safe_candidate(endpoint) for endpoint in candidates],
        }
    )
    return result


def match_computer_to_endpoint(
    asset: Mapping[str, Any],
    indexes: Mapping[str, Any],
) -> dict[str, Any]:
    """Match one Computer Asset using deterministic, non-fuzzy priorities."""
    result = _mapping_base(asset)
    hostname = result["computer_hostname"]
    login_account = result["login_account"]

    if not hostname and not login_account:
        result["match_status"] = "Insufficient Asset Data"
        return result

    if hostname:
        exact_key = normalize_text(hostname)
        exact_candidates = list(indexes.get("exact_hostname", {}).get(exact_key, []))
        if len(exact_candidates) > 1:
            return _ambiguous_mapping(
                result,
                exact_candidates,
                status="Duplicate Hostname",
                method="hostname",
            )
        if len(exact_candidates) == 1:
            return _matched_mapping(
                result,
                exact_candidates[0],
                status="Hostname Exact",
                method="hostname",
                confidence="high",
            )

        normalized_key = normalize_hostname(hostname)
        normalized_candidates = list(indexes.get("normalized_hostname", {}).get(normalized_key, []))
        if len(normalized_candidates) > 1:
            return _ambiguous_mapping(
                result,
                normalized_candidates,
                status="Duplicate Hostname",
                method="hostname",
            )
        if len(normalized_candidates) == 1:
            return _matched_mapping(
                result,
                normalized_candidates[0],
                status="Hostname Normalized",
                method="hostname",
                confidence="high",
            )

    normalized_login = normalize_username(login_account)
    if normalized_login:
        username_candidates = list(indexes.get("username", {}).get(normalized_login, []))
        if len(username_candidates) > 1:
            return _ambiguous_mapping(
                result,
                username_candidates,
                status="Ambiguous Username",
                method="username",
            )
        if len(username_candidates) == 1:
            return _matched_mapping(
                result,
                username_candidates[0],
                status="Username Match",
                method="username",
                confidence="medium",
            )

    return result


def map_computers_to_bitdefender(
    computers: Iterable[Mapping[str, Any]],
    endpoint_inventory: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map all computers using one set of in-memory endpoint indexes."""
    indexes = build_endpoint_indexes(endpoint_inventory)
    return [match_computer_to_endpoint(asset, indexes) for asset in computers]


def map_computers_with_inventory_loader(
    computers: Iterable[Mapping[str, Any]],
    inventory_loader: Callable[[], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Load GravityZone inventory exactly once, then map all computers in memory."""
    inventory = inventory_loader()
    return map_computers_to_bitdefender(computers, inventory)


def build_mapping_diagnostics(mappings: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Summarize Computer Asset to GravityZone matching outcomes."""
    rows = list(mappings)
    statuses = defaultdict(int)
    for row in rows:
        statuses[str(row.get("match_status") or "Not Found")] += 1
    return {
        "total_computer_assets": len(rows),
        "matched": sum(bool(row.get("matched")) for row in rows),
        "hostname_exact": statuses["Hostname Exact"],
        "hostname_normalized": statuses["Hostname Normalized"],
        "username_match": statuses["Username Match"],
        "duplicate_hostname": statuses["Duplicate Hostname"],
        "ambiguous_username": statuses["Ambiguous Username"],
        "not_found": statuses["Not Found"],
        "insufficient_asset_data": statuses["Insufficient Asset Data"],
        "missing_policy": sum(bool(row.get("matched")) and bool(row.get("policy_missing")) for row in rows),
    }
