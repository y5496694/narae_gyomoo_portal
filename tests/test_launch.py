import base64
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("wxs_launch", Path(__file__).parents[1] / "skills/wxs-cli/scripts/wxs_launch.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def request(target="https://klef.cbe.go.kr/bms/cz/cb/prc/wxsLogin.do?path=SYNTHETIC_PRIVATE", title="가상 표준서식"):
    values = [base64.b64encode(x.encode()).decode() for x in (target, title, "900,900")]
    return {"url": "wxsclient:/open&url:" + values[0] + "&title:" + values[1] + "&windowsize:" + values[2], "source_origin": "https://klef.cbe.go.kr", "format_title": title}


class LaunchTests(unittest.TestCase):
    def test_payload_stays_in_private_ipc_and_review_binds_handler_and_uri(self):
        raw = request()
        handler = lambda: {"executable": "synthetic WXSClient.exe", "executable_sha256": "a", "command_sha256": "b", "signature": "Valid HANDYSOFT"}
        preview = module.launch(raw, handler=handler)
        self.assertNotIn(raw["url"], str(preview))
        self.assertNotIn("SYNTHETIC_PRIVATE", str(preview))
        launched = []
        with self.assertRaises(ValueError):
            module.launch(request(target="https://klef.cbe.go.kr/bms/cz/cb/prc/wxsLogin.do?path=CHANGED"), apply=True, expected_fingerprint=preview["fingerprint"], handler=handler, start=launched.append)
        self.assertEqual(launched, [])
        result = module.launch(raw, apply=True, expected_fingerprint=preview["fingerprint"], handler=handler, start=launched.append)
        self.assertTrue(result["applied"])
        self.assertFalse(result["document_open_verified"])
        self.assertEqual(launched, [raw["url"]])

    def test_other_protocols_origins_authorities_paths_and_titles_are_rejected(self):
        for target in ("http://klef.cbe.go.kr/bms/cz/cb/prc/wxsLogin.do", "https://other.invalid/bms/cz/cb/prc/wxsLogin.do", "https://klef.cbe.go.kr:444/bms/cz/cb/prc/wxsLogin.do", "https://user@klef.cbe.go.kr/bms/cz/cb/prc/wxsLogin.do", "https://klef.cbe.go.kr/other"):
            with self.assertRaises(ValueError):
                module.validate_request(request(target))
        for key, value in (("source_origin", "https://other.invalid"), ("format_title", "다른 서식"), ("url", "other:/open")):
            raw = request()
            raw[key] = value
            with self.assertRaises(ValueError):
                module.validate_request(raw)

    def test_observed_handysoft_protocol_authority_is_supported_without_allowing_other_authorities(self):
        raw = request()
        raw["url"] = raw["url"].replace("wxsclient:/open", "wxsclient://handysoft.co.kr/open")
        self.assertEqual(module.validate_request(raw)["protocol"], "wxsclient")
        raw["url"] = raw["url"].replace("handysoft.co.kr", "other.invalid")
        with self.assertRaises(ValueError):
            module.validate_request(raw)


if __name__ == "__main__":
    unittest.main()
