import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

from blog_mvp.store import Store


@unittest.skipIf(AppTest is None, "Install dashboard dependencies")
class WritingDeskTests(unittest.TestCase):
    def test_demo_to_approved_copy_view(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "BLOG_DB": str(Path(folder) / "desk.sqlite3"), "BLOG_DEPLOYED": "false",
            "ALLOW_PAID_GENERATION": "false",
        }):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
            self.assertFalse(app.exception)
            self.assertTrue(next(b for b in app.button if b.label == "오늘의 글 만들기").disabled)
            next(b for b in app.button if b.label == "완성 글 예시 보기").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.warning)
            self.assertTrue(next(b for b in app.button if b.label == "이 글 승인").disabled)
            next(c for c in app.checkbox if c.label.startswith("출처와")).check().run()
            next(b for b in app.button if b.label == "이 글 승인").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(Store(os.environ["BLOG_DB"]).list("approved")), 1)
            app.radio[0].set_value("발행할 글").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get("iframe")), 2)
            self.assertTrue(any(b.label == "다시 수정하기" for b in app.button))
            next(b for b in app.button if b.label == "다시 수정하기").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(Store(os.environ["BLOG_DB"]).list("approved")), 0)

    def test_hold_and_resume(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            "BLOG_DB": str(Path(folder) / "desk.sqlite3"), "BLOG_DEPLOYED": "false",
        }):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
            next(b for b in app.button if b.label == "완성 글 예시 보기").click().run()
            next(b for b in app.button if b.label == "지금은 보류").click().run()
            app.radio[0].set_value("보류한 글").run()
            self.assertFalse(app.exception)
            self.assertTrue(any(b.label == "이 글 승인" for b in app.button))
