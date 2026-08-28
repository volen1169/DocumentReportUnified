from __future__ import annotations

import importlib
import sys
import types
import unittest
from unittest.mock import Mock


if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    requests_stub.RequestException = RequestException
    requests_stub.post = None
    sys.modules["requests"] = requests_stub


service = importlib.import_module("services.bitdefender_service")


def endpoint(
    endpoint_id: str,
    *,
    name: str = "",
    hostname: str = "",
    fqdn: str = "",
    usernames: list[str] | None = None,
    policy_name: str = "Policy A",
    **extra,
):
    value = {
        "endpoint_id": endpoint_id,
        "endpoint_name": name,
        "hostname": hostname,
        "fqdn": fqdn,
        "usernames": usernames or [],
        "managed": True,
        "last_seen": "2026-08-28T00:00:00Z",
        "policy_id": "policy-1" if policy_name else "",
        "policy_name": policy_name,
        "policy_applied": True if policy_name else None,
        "normalized_endpoint_name": service.normalize_text(name),
        "normalized_hostname": service.normalize_hostname(hostname or fqdn),
        "normalized_usernames": [
            service.normalize_username(username) for username in usernames or []
        ],
    }
    value.update(extra)
    return value


class BitdefenderMappingTests(unittest.TestCase):
    def map_one(self, asset, endpoints):
        return service.map_computers_to_bitdefender([asset], endpoints)[0]

    def test_exact_hostname_match(self):
        result = self.map_one(
            {"field_3": "Employee", "field_6": "PC-001"},
            [endpoint("1", name="Endpoint 1", hostname="PC-001")],
        )
        self.assertTrue(result["matched"])
        self.assertEqual(result["match_status"], "Hostname Exact")
        self.assertEqual(result["match_confidence"], "high")

    def test_exact_hostname_is_case_insensitive(self):
        result = self.map_one(
            {"field_6": "pc-001"},
            [endpoint("1", hostname="PC-001")],
        )
        self.assertEqual(result["match_status"], "Hostname Exact")

    def test_fqdn_normalization_match(self):
        result = self.map_one(
            {"field_6": "PC-001"},
            [endpoint("1", fqdn="PC-001.optimalgroup.com")],
        )
        self.assertEqual(result["match_status"], "Hostname Normalized")

    def test_unique_username_match(self):
        result = self.map_one(
            {"LoginAccount": "alice"},
            [endpoint("1", usernames=["alice"])],
        )
        self.assertEqual(result["match_status"], "Username Match")
        self.assertEqual(result["match_confidence"], "medium")

    def test_domain_username_normalization(self):
        result = self.map_one(
            {"LoginAccount": r"OPTIMALGROUP\alice"},
            [endpoint("1", usernames=["alice"])],
        )
        self.assertEqual(result["match_status"], "Username Match")

    def test_upn_username_normalization(self):
        result = self.map_one(
            {"LoginAccount": "alice@optimalgroup.com"},
            [endpoint("1", usernames=[r"OPTIMALGROUP\alice"])],
        )
        self.assertEqual(result["match_status"], "Username Match")

    def test_duplicate_hostname_requires_manual_review(self):
        result = self.map_one(
            {"field_6": "PC-001"},
            [endpoint("1", hostname="PC-001"), endpoint("2", hostname="pc-001")],
        )
        self.assertFalse(result["matched"])
        self.assertEqual(result["match_status"], "Duplicate Hostname")
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["match_confidence"], "manual_review")

    def test_ambiguous_username_requires_manual_review(self):
        result = self.map_one(
            {"LoginAccount": "alice"},
            [endpoint("1", usernames=["alice"]), endpoint("2", usernames=["alice"])],
        )
        self.assertFalse(result["matched"])
        self.assertEqual(result["match_status"], "Ambiguous Username")
        self.assertEqual(result["candidate_count"], 2)

    def test_no_match(self):
        result = self.map_one(
            {"field_6": "PC-404", "LoginAccount": "nobody"},
            [endpoint("1", hostname="PC-001", usernames=["alice"])],
        )
        self.assertEqual(result["match_status"], "Not Found")
        self.assertEqual(result["match_confidence"], "none")

    def test_missing_hostname_can_use_login_account(self):
        result = self.map_one(
            {"field_6": "", "LoginAccount": "alice"},
            [endpoint("1", usernames=["alice"])],
        )
        self.assertEqual(result["match_status"], "Username Match")

    def test_missing_hostname_and_login_is_insufficient(self):
        result = self.map_one(
            {"field_3": "Display Only", "field_6": "", "LoginAccount": ""},
            [endpoint("1", hostname="Display Only")],
        )
        self.assertEqual(result["match_status"], "Insufficient Asset Data")
        self.assertFalse(result["matched"])

    def test_matched_endpoint_can_have_missing_policy(self):
        result = self.map_one(
            {"field_6": "PC-001"},
            [endpoint("1", hostname="PC-001", policy_name="")],
        )
        self.assertTrue(result["matched"])
        self.assertEqual(result["match_status"], "Hostname Exact")
        self.assertTrue(result["policy_missing"])
        self.assertEqual(result["policy_name"], "")

    def test_endpoint_name_is_exact_hostname_fallback(self):
        result = self.map_one(
            {"field_6": "PC-001"},
            [endpoint("1", name="PC-001")],
        )
        self.assertEqual(result["match_status"], "Hostname Exact")

    def test_duplicate_endpoint_name_does_not_auto_match(self):
        result = self.map_one(
            {"field_6": "PC-001"},
            [endpoint("1", name="PC-001"), endpoint("2", name="pc-001")],
        )
        self.assertEqual(result["match_status"], "Duplicate Hostname")
        self.assertFalse(result["matched"])

    def test_inventory_loader_is_called_once_per_mapping_operation(self):
        loader = Mock(return_value=[endpoint("1", hostname="PC-001")])
        results = service.map_computers_with_inventory_loader(
            [{"field_6": "PC-001"}, {"field_6": "PC-002"}],
            loader,
        )
        loader.assert_called_once_with()
        self.assertEqual(len(results), 2)

    def test_candidate_payload_excludes_sensitive_fields(self):
        endpoints = [
            endpoint(
                "1",
                hostname="PC-001",
                authorization="Basic SHOULD_NOT_APPEAR",
                api_key="SHOULD_NOT_APPEAR",
                raw_headers={"Authorization": "Basic SHOULD_NOT_APPEAR"},
            ),
            endpoint("2", hostname="PC-001", secret="SHOULD_NOT_APPEAR"),
        ]
        result = self.map_one({"field_6": "PC-001"}, endpoints)
        allowed = {
            "endpoint_id",
            "endpoint_name",
            "hostname",
            "policy_name",
            "managed",
            "last_seen",
        }
        self.assertTrue(result["candidates"])
        self.assertTrue(all(set(candidate) == allowed for candidate in result["candidates"]))
        self.assertNotIn("SHOULD_NOT_APPEAR", repr(result["candidates"]))

    def test_mapping_diagnostics(self):
        mappings = [
            self.map_one({"field_6": "PC-001"}, [endpoint("1", hostname="PC-001")]),
            self.map_one({"field_6": "PC-404"}, []),
            self.map_one({"field_6": ""}, []),
        ]
        diagnostics = service.build_mapping_diagnostics(mappings)
        self.assertEqual(diagnostics["total_computer_assets"], 3)
        self.assertEqual(diagnostics["matched"], 1)
        self.assertEqual(diagnostics["not_found"], 1)
        self.assertEqual(diagnostics["insufficient_asset_data"], 1)


if __name__ == "__main__":
    unittest.main()
