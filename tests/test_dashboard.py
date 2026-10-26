import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None


@unittest.skipIf(AppTest is None, "Install .[dashboard] for UI tests")
class DashboardTests(unittest.TestCase):
    def test_sample_import_and_pending_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"BLOG_DB": str(Path(folder) / "ui.sqlite3"),
                                         "BLOG_DEPLOYED": "false"}):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "legacy_app.py"), default_timeout=30).run()
                self.assertFalse(app.exception)
                next(b for b in app.button if b.label == "샘플 20개로 시작").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.dataframe[0].value), 40)
                next(b for b in app.button if b.label == "검토 필요로 이동").click().run()
                self.assertFalse(app.exception)
                approve = next(b for b in app.button if b.label == "저장된 원고 승인")
                self.assertTrue(approve.disabled)
                next(w for w in app.text_area if w.label == "Markdown 본문").set_value(
                    "생활 속 회계 질문을 가상의 사례로 정리했습니다. 사실과 의견을 구분합니다.")
                next(w for w in app.text_area if w.label == "근거 출처").set_value(
                    "https://example.com/evidence | 2026-10-24 | 테스트 출처")
                next(w for w in app.text_area if w.label.startswith("검토 메모")).set_value("확인 완료")
                next(w for w in app.text_input if w.label == "검토자").set_value("테스트 검토자")
                for checkbox in app.checkbox:
                    checkbox.check()
                next(b for b in app.button if b.label == "검토 내용 저장").click().run()
                self.assertFalse(app.exception)
                next(b for b in app.button if b.label == "저장된 원고 승인").click().run()
                self.assertFalse(app.exception)
                from blog_mvp.store import Store
                self.assertEqual(len(Store(Path(folder) / "ui.sqlite3").list("approved")), 1)
                next(w for w in app.selectbox if w.label == "상태").select("승인").run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.get("download_button")), 4)

    def test_deployed_app_blocks_access(self):
        with patch.dict(os.environ, {"BLOG_DEPLOYED": "true"}):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "legacy_app.py")).run()
            self.assertFalse(app.exception)
            self.assertIn("공개 배포", app.error[0].value)
            self.assertEqual(len(app.file_uploader) if hasattr(app, "file_uploader") else 0, 0)
