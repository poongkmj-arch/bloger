import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from blog_mvp.cli import main
from blog_mvp.drafts import CHECKS, export_files, generate, similarity
from blog_mvp.keywords import FIELDS, OfficialApiCollector, parse_csv, score
from blog_mvp.store import Store

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples/keywords.csv"


def csv_bytes(**changes):
    row = dict(zip(FIELDS, ["테스트 주제", "100000", "50", "20", "80", "90", "70",
                            "", "", "sample", "estimated", "", "", ""]))
    row.update(changes)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerow(row)
    return out.getvalue().encode("utf-8")


class KeywordTests(unittest.TestCase):
    def test_sample_20_and_labels(self):
        items = parse_csv(SAMPLE.read_bytes())
        self.assertEqual(len(items), 20)
        self.assertTrue(all(i.metric_kind == "sample" for i in items))
        self.assertTrue(all(not i.source_url for i in items))

    def test_bom_and_quoted_csv(self):
        item = parse_csv(b"\xef\xbb\xbf" + csv_bytes(keyword="금리, 환율"))[0]
        self.assertEqual(item.keyword, "금리, 환율")

    def test_weights(self):
        result = score(parse_csv(csv_bytes())[0])
        self.assertEqual(result["total"], 86.5)
        self.assertEqual(sum(result["weights"].values()), 1)

    def test_missing_is_not_low_competition(self):
        item = parse_csv(csv_bytes(monthly_searches="", ad_competition=""))[0]
        result = score(item)
        self.assertEqual(result["components"]["opportunity"], 0)
        self.assertEqual(result["components"]["volume"], 0)
        self.assertEqual(len(result["missing"]), 2)

    def test_trend_is_not_search_volume(self):
        item = parse_csv(csv_bytes())[0]
        self.assertEqual(score(item), score(replace(item, trend_index=99)))

    def test_invalid_inputs(self):
        cases = [
            {"monthly_searches": "-1"}, {"monthly_searches": "NaN"},
            {"monthly_searches": "inf"}, {"trend_index": "101"},
            {"ad_competition": "-1"}, {"profitability_score": "101"},
            {"ease_score": ""}, {"metric_kind": "actual"},
            {"profitability_kind": "measured"}, {"metric_kind": "measured"},
            {"source_url": "javascript:alert(1)"}, {"source_url": "https://a b"},
            {"source_url": "https://user:password@example.com"},
            {"measured_at": "2026-02-30"}, {"source_published_at": "2026-01-01"},
            {"keyword": ""}, {"keyword": "bad\nkeyword"},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                parse_csv(csv_bytes(**case))

    def test_verified_metric_requires_provenance(self):
        item = parse_csv(csv_bytes(metric_kind="measured", metric_source_url="https://example.com/report",
                                   measured_at="2026-10-24"))[0]
        self.assertEqual(item.metric_kind, "measured")

    def test_csv_limits_and_duplicate(self):
        raw = csv_bytes()
        for data in (b"", b"\xff", b"x" * 1_000_001, b"keyword\nhello\n",
                     raw + raw.splitlines(keepends=True)[1],
                     raw.splitlines(keepends=True)[0] + raw.splitlines(keepends=True)[1] * 501):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                parse_csv(data)

    def test_external_collector_disabled(self):
        with self.assertRaises(RuntimeError):
            OfficialApiCollector().collect()

    def test_platforms_differ(self):
        item = parse_csv(csv_bytes())[0]
        naver, tistory = generate(item, "naver"), generate(item, "tistory")
        self.assertIn("생활 속 질문", naver["body"])
        self.assertIn("반례와 민감도", tistory["body"])
        self.assertLess(similarity(naver["body"], tistory["body"]), .85)
        self.assertFalse(naver["sources"])
        self.assertEqual(naver["generator"], "offline-template")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "blog.sqlite3"
        self.store = Store(self.path)
        self.items = parse_csv(SAMPLE.read_bytes())
        self.store.ingest(self.items)
        self.draft = self.store.list()[0]

    def tearDown(self):
        self.temp.cleanup()

    def ready(self, draft=None, body=None):
        draft = draft or self.draft
        self.store.edit(
            draft["id"], draft["revision"], title="검토된 제목",
            body=body or "가상의 예산을 검토하는 학습용 사례입니다. 원문과 적용 조건을 확인했습니다.",
            sources=[{"url": "https://example.com/source", "published_at": None,
                      "note": "테스트용 근거", "verified": True}],
            checks={key: True for key in CHECKS}, reviewer="테스트 검토자", review_note="근거 대조 완료")
        return self.store.get(draft["id"])

    def approve(self):
        draft = self.ready()
        self.store.transition(draft["id"], draft["revision"], "approved")
        return self.store.get(draft["id"])

    def test_atomic_import_and_persistence(self):
        self.assertEqual(len(self.store.list()), 40)
        self.assertEqual(len(Store(self.path).list()), 40)
        draft = self.ready()
        result = self.store.ingest(self.items)
        self.assertEqual(result, {"created": 0, "skipped": 40, "dry_run": False})
        self.assertEqual(self.store.get(draft["id"])["body"], draft["body"])

    def test_dry_run_has_no_writes(self):
        before = self.store.list()
        result = self.store.ingest([replace(self.items[0], keyword="새 키워드")], dry_run=True)
        self.assertEqual(result["created"], 2)
        self.assertEqual(self.store.list(), before)

    def test_reject_direct_approval_and_unapproved_export(self):
        with self.assertRaises(ValueError):
            self.store.transition(self.draft["id"], self.draft["revision"], "approved")
        with self.assertRaises(ValueError):
            export_files(self.draft)

    def test_incomplete_review_cannot_approve(self):
        d = self.draft
        self.store.transition(d["id"], d["revision"], "review")
        d = self.store.get(d["id"])
        with self.assertRaises(ValueError):
            self.store.transition(d["id"], d["revision"], "approved")

    def test_placeholders_block_approval(self):
        d = self.ready(body="아직 [작성 필요] 항목이 있습니다.")
        with self.assertRaisesRegex(ValueError, "작성 필요"):
            self.store.transition(d["id"], d["revision"], "approved")

    def test_sources_and_checks_required(self):
        d = self.ready()
        self.store.edit(d["id"], d["revision"], title=d["title"], body=d["body"],
                        sources=[], checks={key: False for key in CHECKS},
                        reviewer="", review_note="")
        d = self.store.get(d["id"])
        with self.assertRaises(ValueError):
            self.store.transition(d["id"], d["revision"], "approved")

    def test_duplicate_platform_body_blocks_approval(self):
        d = self.ready()
        sibling = next(x for x in self.store.list()
                       if x["keyword"] == d["keyword"] and x["id"] != d["id"])
        self.ready(sibling, body=d["body"])
        with self.assertRaisesRegex(ValueError, "유사"):
            self.store.transition(d["id"], d["revision"], "approved")

    def test_edit_revokes_approval(self):
        d = self.approve()
        d = self.ready(d, body="본문 변경 후 다시 검토해야 합니다.")
        self.assertEqual(d["status"], "review")
        with self.assertRaises(ValueError):
            export_files(d)

    def test_stale_edit_rejected(self):
        self.ready()
        with self.assertRaisesRegex(ValueError, "다른 화면"):
            self.ready(self.draft)
        self.assertEqual(len(self.store.events(self.draft["id"])), 2)

    def test_stale_approval_rejected(self):
        d = self.ready()
        self.ready(d, body="다른 화면에서 수정된 내용")
        with self.assertRaisesRegex(ValueError, "다른 화면"):
            self.store.transition(d["id"], d["revision"], "approved")

    def test_export_escapes_html_and_retains_korean(self):
        d = self.ready(body='검토된 본문 <script>alert("x")</script>')
        self.store.transition(d["id"], d["revision"], "approved")
        files = export_files(self.store.get(d["id"]))
        self.assertIn("검토된 본문", files["md"])
        self.assertNotIn("<script>", files["html"])
        self.assertIn("&lt;script&gt;", files["html"])
        self.assertIn("미상", files["md"])
        self.assertEqual(json.loads(files["json"])["status"], "approved")

    def test_schedule_is_manual_record_only(self):
        d = self.approve()
        with self.assertRaises(ValueError):
            self.store.transition(d["id"], d["revision"], "scheduled", scheduled_for="2099-01-01T09:00:00")
        self.store.transition(d["id"], d["revision"], "scheduled", scheduled_for="2099-01-01T09:00:00+09:00")
        scheduled = self.store.get(d["id"])
        self.assertEqual(scheduled["status"], "scheduled")
        self.assertIsNone(scheduled["published_url"])

    def test_record_manual_publish(self):
        d = self.approve()
        with self.assertRaises(ValueError):
            self.store.transition(d["id"], d["revision"], "published", published_url=d["target"])
        with self.assertRaises(ValueError):
            self.store.transition(d["id"], d["revision"], "published", published_url="https://evil.example/post")
        url = d["target"] + "/123"
        self.store.transition(d["id"], d["revision"], "published", published_url=url)
        published = self.store.get(d["id"])
        self.assertEqual(published["published_url"], url)
        with self.assertRaises(ValueError):
            self.ready(published)

    def test_deployment_fails_closed(self):
        with patch.dict(os.environ, {"BLOG_DEPLOYED": "true"}), self.assertRaises(RuntimeError):
            Store(self.path)

    def test_cli_end_to_end(self):
        output = subprocess.run([sys.executable, "-m", "blog_mvp.cli", "--db", str(self.path),
                                 "list"], capture_output=True, text=True, check=True)
        self.assertEqual(len(json.loads(output.stdout)), 40)
        d = self.approve()
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(main(["--db", str(self.path), "export", d["id"],
                                   "--out", self.temp.name]), 0)
        self.assertTrue(Path(self.temp.name, d["id"] + ".html").exists())

    def test_cli_dry_run_does_not_create_database(self):
        path = Path(self.temp.name) / "does-not-exist.sqlite3"
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(main(["--db", str(path), "import-csv", str(SAMPLE), "--dry-run"]), 0)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
