"""MCP 2026-07-28 (stateless) served beside the handshake-era revisions."""
import unittest

from je_web_runner.mcp_server.server import make_default_server

_META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
}


def _request(method, params=None, request_id=1):
    body = dict(params or {})
    body["_meta"] = dict(_META)
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body}


class TestDiscover(unittest.TestCase):

    def setUp(self):
        self.server = make_default_server()

    def test_discover_lists_both_eras_and_identifies_the_server(self):
        result = self.server.handle(_request("server/discover"))["result"]
        self.assertEqual(result["supportedVersions"][0], "2026-07-28")
        self.assertIn("2024-11-05", result["supportedVersions"])
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], "webrunner-mcp")
        self.assertIn("webrunner_list_commands", result["instructions"])
        self.assertEqual(result["resultType"], "complete")
        self.assertGreater(result["ttlMs"], 0)
        self.assertEqual(result["cacheScope"], "private")

    def test_discover_without_meta_is_invalid_params(self):
        response = self.server.handle({"jsonrpc": "2.0", "id": 2, "method": "server/discover", "params": {}})
        self.assertEqual(response["error"]["code"], -32602)


class TestStatelessRequests(unittest.TestCase):

    def setUp(self):
        self.server = make_default_server()

    def test_tools_list_is_shaped_as_a_complete_cacheable_result(self):
        result = self.server.handle(_request("tools/list"))["result"]
        self.assertTrue(result["tools"])
        self.assertEqual(result["resultType"], "complete")
        self.assertIn("ttlMs", result)
        self.assertIn("io.modelcontextprotocol/serverInfo", result["_meta"])

    def test_tools_call_works_without_initialize(self):
        result = self.server.handle(_request("tools/call", {
            "name": "webrunner_locator_strength", "arguments": {"strategy": "ID", "value": "submit"},
        }))["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["resultType"], "complete")
        self.assertNotIn("ttlMs", result)

    def test_unsupported_version_is_minus_32022_with_the_supported_list(self):
        request = _request("tools/list")
        request["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] = "2099-01-01"
        error = self.server.handle(request)["error"]
        self.assertEqual(error["code"], -32022)
        self.assertEqual(error["data"]["requested"], "2099-01-01")
        self.assertIn("2026-07-28", error["data"]["supported"])

    def test_missing_client_capabilities_is_invalid_params(self):
        request = _request("tools/list")
        del request["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"]
        self.assertEqual(self.server.handle(request)["error"]["code"], -32602)

    def test_methods_removed_in_2026_07_28_are_not_found(self):
        self.assertEqual(self.server.handle(_request("ping"))["error"]["code"], -32601)

    def test_initialize_is_always_the_handshake(self):
        # A dual-era server serves initialize the old way even if it carries _meta.
        request = _request("initialize", {"protocolVersion": "2025-11-25"})
        self.assertEqual(self.server.handle(request)["result"]["protocolVersion"], "2025-11-25")

    def test_handshake_era_still_works_after_a_stateless_request(self):
        self.server.handle(_request("server/discover"))
        response = self.server.handle({"jsonrpc": "2.0", "id": 9, "method": "initialize",
                                       "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual(response["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(self.server.handle({"id": 10, "method": "ping"})["result"], {})


if __name__ == "__main__":
    unittest.main()
