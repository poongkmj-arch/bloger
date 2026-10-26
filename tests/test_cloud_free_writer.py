import io
import json
import os
import unittest
from unittest.mock import patch
import cloud_free_writer as writer

class FakeResponse:
    def __enter__(self):
        return io.BytesIO(json.dumps({
            "candidates": [{"content": {"parts": [{"text": "테스트 초안"}]}}]
        }).encode())
    def __exit__(self, *args):
        return False

class FreeWriterTests(unittest.TestCase):
    def test_no_key_no_request(self):
        with self.assertRaises(ValueError):
            writer.generate("제목", "https://example.org", "")

    def test_confirmation_required(self):
        with patch.dict(os.environ, {"CONFIRM_GEMINI_FREE_TIER": ""}):
            with self.assertRaises(ValueError):
                writer.generate("제목", "https://example.org", "dummy")

    def test_paid_flag_blocks_request(self):
        with patch.dict(os.environ, {"CONFIRM_GEMINI_FREE_TIER": "YES",
                                      "ALLOW_PAID_GENERATION": "true"}):
            with self.assertRaises(ValueError):
                writer.generate("제목", "https://example.org", "dummy")

    def test_one_call_success(self):
        calls = []
        def transport(req, timeout):
            calls.append(req)
            return FakeResponse()
        with patch.dict(os.environ, {"CONFIRM_GEMINI_FREE_TIER": "YES",
                                      "ALLOW_PAID_GENERATION": "false"}):
            result = writer.generate("제목", "https://example.org", "dummy", transport)
        self.assertEqual(result, "테스트 초안")
        self.assertEqual(len(calls), 1)
        self.assertIn(writer.MODEL, calls[0].full_url)

if __name__ == "__main__":
    unittest.main()
