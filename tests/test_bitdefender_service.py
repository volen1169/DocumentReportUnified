from __future__ import annotations

import ast
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    requests_stub.RequestException = RequestException
    requests_stub.post = None
    sys.modules["requests"] = requests_stub


service = importlib.import_module("services.bitdefender_service")


class BitdefenderServiceTests(unittest.TestCase):
    def test_pagination_uses_read_only_managed_endpoint_method(self):
        calls = []
        pages = {
            1: {"items": [{"id": "1"}], "pagesCount": 2, "hasMoreRecords": True},
            2: {"items": [{"id": "2"}], "pagesCount": 2, "hasMoreRecords": False},
        }

        def fake_rpc(api_name, method, params):
            calls.append((api_name, method, params.copy()))
            return pages[params["page"]]

        with patch.object(service, "_rpc", side_effect=fake_rpc):
            result = service.get_managed_endpoints(per_page=50)

        self.assertEqual([item["id"] for item in result], ["1", "2"])
        self.assertEqual([call[0:2] for call in calls], [("network", "getEndpointsList")] * 2)
        self.assertTrue(all(call[2]["isManaged"] is True for call in calls))
        self.assertEqual([call[2]["page"] for call in calls], [1, 2])

    def test_safe_normalization(self):
        self.assertEqual(service.normalize_text("  Pc 001  "), "pc 001")
        self.assertEqual(service.normalize_username(r"OPTIMALGROUP\Some.User"), "some.user")
        self.assertEqual(service.normalize_username("Some.User@optimalgroup.com"), "some.user")
        self.assertEqual(service.normalize_hostname(" PC001.optimalgroup.com. "), "pc001")

    def test_missing_policy_and_duplicate_hostnames(self):
        raw = [
            {
                "id": "1",
                "name": "PC001",
                "fqdn": "PC001.optimalgroup.com",
                "users": [{"userName": r"OPTIMALGROUP\alice"}],
                "isManaged": True,
                "policy": {"id": "p1", "name": "Standard", "applied": True},
            },
            {"id": "2", "name": "PC001", "hostname": "pc001", "isManaged": True},
        ]
        endpoints = [service.normalize_endpoint(item) for item in raw]
        summary = service.build_endpoint_diagnostics(endpoints)

        self.assertEqual(endpoints[1]["policy_id"], "")
        self.assertEqual(endpoints[1]["policy_name"], "")
        self.assertEqual(summary["endpoints_missing_policy"], 1)
        self.assertEqual(summary["duplicate_normalized_hostnames"], 1)
        self.assertEqual(summary["duplicate_hostnames"][0]["normalized_hostname"], "pc001")
        self.assertEqual(summary["duplicate_hostnames"][0]["count"], 2)
        self.assertNotIn("endpoint_id", summary["duplicate_hostnames"][0])

    def test_inventory_normalizes_all_paginated_results(self):
        raw = [{"id": "1", "machineName": "PC001", "policy": {"name": "Policy A"}}]
        with patch.object(service, "get_managed_endpoints", return_value=raw) as fetch:
            result = service.get_managed_endpoint_inventory(per_page=25)
        fetch.assert_called_once_with(per_page=25)
        self.assertEqual(result[0]["normalized_hostname"], "pc001")
        self.assertEqual(result[0]["policy_name"], "Policy A")

    def test_api_errors_redact_credentials(self):
        api_key = "super-secret-api-key"
        with patch.object(service, "_read_setting", return_value=api_key):
            message = service._redact_sensitive_text(
                f"Authorization: Basic abc123; key={api_key}"
            )
        self.assertNotIn(api_key, message)
        self.assertNotIn("abc123", message)
        self.assertIn("[REDACTED]", message)

    def test_rpc_api_error_does_not_leak_secret(self):
        api_key = "TEST_KEY_FOR_REDACTION"

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"error": {"code": -1, "message": f"bad key {api_key}"}}

        with (
            patch.object(service, "_api_key", return_value=api_key),
            patch.object(service, "_base_url", return_value="https://example.invalid"),
            patch.object(service, "_read_setting", return_value=api_key),
            patch.object(service.requests, "post", return_value=Response()),
        ):
            with self.assertRaises(service.BitdefenderAPIError) as captured:
                service._rpc("network", "getEndpointsList", {})
        self.assertNotIn(api_key, str(captured.exception))

    def test_http_error_does_not_echo_request_exception(self):
        class Response:
            status_code = 401

        error = service.requests.RequestException("Authorization: Basic TEST_CREDENTIAL")
        error.response = Response()
        with (
            patch.object(service, "_rpc_url", return_value="https://example.invalid"),
            patch.object(service, "_authorization_header", return_value="Basic TEST_CREDENTIAL"),
            patch.object(service.requests, "post", side_effect=error),
        ):
            with self.assertRaises(service.BitdefenderAPIError) as captured:
                service._rpc("network", "getEndpointsList", {})
        self.assertEqual(str(captured.exception), "GravityZone HTTP request failed (HTTP 401).")
        self.assertNotIn("TEST_CREDENTIAL", str(captured.exception))

    def test_source_contains_no_mutation_api_methods(self):
        source_path = Path(service.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        string_values = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertIn("getEndpointsList", string_values)
        forbidden = {
            "assignPolicy",
            "deleteEndpoint",
            "deleteEndpoints",
            "updatePolicy",
            "deletePolicy",
        }
        self.assertFalse(string_values.intersection(forbidden))


if __name__ == "__main__":
    unittest.main()
