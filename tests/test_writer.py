import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from blog_mvp.copybox import copy_html
from blog_mvp.demo import load_demo
from blog_mvp.drafts import CHECKS
from blog_mvp.store import Store
from blog_mvp.writer import (
    REQUIRED, NaverMarket, plain_package, researched_urls, run_live,
    search_volume, setup_problems, usage, validate_package,
)


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "db.sqlite3")
        self.package = load_demo(self.store)
        self.settings = {key: "test-only" for key in REQUIRED}
        self.settings.update(NAVER_TERMS_REVIEWED="true", ALLOW_PAID_GENERATION="true")

    def tearDown(self):
        self.tmp.cleanup()

    def test_demo_is_complete_and_honest(self):
        package = validate_package(self.package, {self.package["articles"][0]["sources"][0]["url"]})
        self.assertEqual(package["mode"], "demo")
        self.assertIsNone(package["candidate"]["volume"])
        self.assertTrue(all(len(a["body"]) > 600 for a in package["articles"]))
        self.assertTrue(all("[작성 필요]" not in a["body"] for a in package["articles"]))
        load_demo(self.store)
        self.assertEqual(len(self.store.list()), 2)

    def test_volume_interval_not_invented(self):
        self.assertEqual(search_volume("< 10"), (0, True))
        self.assertEqual(search_volume("100"), (100, False))
        for value in (None, "NaN", -1, "bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                search_volume(value)

    def test_setup_requires_both_permission_and_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(setup_problems())
        with patch.dict(os.environ, self.settings):
            self.assertFalse(setup_problems())

    def market_transport(self, url, headers, payload=None):
        if "keywordstool" in url:
            self.assertIn("X-Signature", headers)
            return {"keywordList": [
                {"relKeyword": "예금 금리", "monthlyPcQcCnt": 1000,
                 "monthlyMobileQcCnt": 2000, "compIdx": "중간"},
                {"relKeyword": "적금 계산", "monthlyPcQcCnt": "< 10",
                 "monthlyMobileQcCnt": 100, "compIdx": "낮음"},
                {"relKeyword": "관련 없는 상품", "monthlyPcQcCnt": 999999,
                 "monthlyMobileQcCnt": 999999, "compIdx": "낮음"}]}
        self.assertEqual(payload["timeUnit"], "month")
        self.assertEqual(len(payload["keywordGroups"]), 2)
        return {"results": [
            {"title": "예금 금리", "data": [{"period": f"2025-{i + 1:02d}-01", "ratio": 50} for i in range(12)]},
            {"title": "적금 계산", "data": [{"period": f"2025-{i + 1:02d}-01", "ratio": 50 if i == 0 else 1} for i in range(12)]},
        ]}

    def test_market_uses_separate_volume_and_twelve_month_trends(self):
        transport = Mock(side_effect=self.market_transport)
        with patch.dict(os.environ, self.settings):
            rows = NaverMarket(transport).collect("생활 금융")
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(rows[0]["keyword"], "예금 금리")
        self.assertEqual(rows[0]["volume"], 3000)
        self.assertEqual(rows[0]["persistence"], 100)
        self.assertTrue(rows[1]["volume_is_lower_bound"])
        self.assertLess(rows[1]["persistence"], rows[0]["persistence"])

    def test_incomplete_trend_fails_not_sample(self):
        def incomplete(url, headers, payload=None):
            if payload:
                return {"results": []}
            return self.market_transport(url, headers)
        with patch.dict(os.environ, self.settings), self.assertRaises(ValueError):
            NaverMarket(incomplete).collect("생활 금융")

    def test_missing_evidence_and_duplicate_writing_blocked(self):
        urls = {self.package["articles"][0]["sources"][0]["url"]}
        for mutation in ("source", "duplicate", "placeholder", "short"):
            p = copy.deepcopy(self.package)
            if mutation == "source":
                p["articles"][0]["sources"][0]["url"] = "https://invented.example"
            elif mutation == "duplicate":
                p["articles"][1]["body"] = p["articles"][0]["body"]
            elif mutation == "placeholder":
                p["articles"][0]["body"] += "[작성 필요]"
            else:
                p["articles"][0]["body"] = "너무 짧음"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_package(p, urls)

    def test_citations_must_come_from_tool_results(self):
        result = {"output": [{"type": "web_search_call",
                              "action": {"sources": [{"url": "https://example.org/evidence"}]}},
                             {"type": "message", "content": [{"annotations": [
                                 {"type": "url_citation", "url": "https://example.org/other"},
                                 {"type": "url_citation", "url": "javascript:bad"}]}]}]}
        self.assertEqual(researched_urls(result), {"https://example.org/evidence", "https://example.org/other"})

    def test_live_idempotency_and_persistent_budget(self):
        market = Mock()
        market.collect.return_value = [self.package["candidate"]]
        writer = Mock()
        writer.write.return_value = copy.deepcopy(self.package)
        with patch.dict(os.environ, self.settings):
            result = run_live(self.store, "생활 금융", consent=True, market=market, writer=writer)
            again = run_live(Store(self.store.path), "생활 금융", consent=True, market=market, writer=writer)
        self.assertEqual(result["draft_ids"], again["draft_ids"])
        self.assertEqual(writer.write.call_count, 1)
        self.assertEqual(usage(self.store)["runs"], 1)
        self.assertEqual(usage(self.store)["reserved_usd"], .5)
        self.assertEqual(len(self.store.list()), 4)

    def test_failure_keeps_reservation_and_cannot_retry(self):
        market = Mock()
        market.collect.side_effect = ValueError("연결 실패")
        with patch.dict(os.environ, self.settings):
            with self.assertRaises(ValueError):
                run_live(self.store, "생활 금융", consent=True, market=market)
            with self.assertRaisesRegex(ValueError, "중복 과금"):
                run_live(self.store, "생활 금융", consent=True, market=market)
        self.assertEqual(market.collect.call_count, 1)
        self.assertEqual(usage(self.store)["reserved_usd"], .5)

    def test_no_consent_means_no_calls(self):
        market = Mock()
        with self.assertRaises(ValueError):
            run_live(self.store, "생활 금융", market=market)
        market.collect.assert_not_called()

    def test_copy_requires_approval_and_contains_no_internal_notes(self):
        draft = self.store.get(self.package["draft_ids"][0])
        with self.assertRaises(ValueError):
            plain_package(draft)
        self.store.edit(draft["id"], draft["revision"], title=draft["title"], body=draft["body"],
                        sources=[{**s, "verified": True} for s in draft["sources"]],
                        checks={key: True for key in CHECKS}, reviewer="운영자", review_note="확인")
        self.store.transition(draft["id"], draft["revision"] + 1, "approved")
        title, text = plain_package(self.store.get(draft["id"]))
        self.assertEqual(title, draft["title"])
        self.assertNotIn("작성 필요", text)
        self.assertIn("참고 자료", text)

    def test_clipboard_escapes_untrusted_html(self):
        output = copy_html('</textarea><script>alert(1)</script>', "복사")
        self.assertNotIn("</textarea><script>alert", output)
        self.assertIn("&lt;/textarea&gt;", output)
        self.assertIn("clipboard.writeText", output)
        self.assertIn("setSelectionRange", output)


    def test_budget_cap_prevents_provider_calls(self):
        from blog_mvp.writer import init_jobs, today
        from contextlib import closing
        init_jobs(self.store)
        with closing(self.store.connect()) as db, db:
            db.execute("INSERT INTO writing_jobs VALUES (?, ?, 'failed', 2.0, '{}')",
                       ("fixture-budget", str(today())))
        market = Mock()
        with patch.dict(os.environ, self.settings), self.assertRaisesRegex(ValueError, "한도"):
            run_live(self.store, "경제 이해", consent=True, market=market)
        market.collect.assert_not_called()

    def test_openai_adapter_research_then_write_with_no_retries(self):
        try:
            import openai
        except ImportError:
            self.skipTest("Install dashboard dependencies")
        from blog_mvp.writer import OpenAIWriter
        source = self.package["articles"][0]["sources"][0]["url"]
        research = Mock()
        research.output_text = "공식 원리를 확인한 조사 결과"
        research.model_dump.return_value = {
            "status": "completed", "usage": {"input_tokens": 20, "output_tokens": 10},
            "output": [{"type": "web_search_call", "action": {"sources": [{"url": source}]}}],
        }
        writing = Mock()
        writing.status = "completed"
        import json
        mock_package = copy.deepcopy(self.package)
        keyword = self.package["candidate"]["keyword"]
        for article in mock_package["articles"]:
            article["title"] = keyword + " " + article["title"]
            article["body"] = keyword + " 관련 핵심 내용을 살펴봅니다.\\n\\n" + article["body"]
        writing.output_text = json.dumps(mock_package, ensure_ascii=False)
        writing.model_dump.return_value = {"usage": {"input_tokens": 100, "output_tokens": 200}}
        with patch.dict(os.environ, self.settings), patch.object(openai, "OpenAI") as factory:
            client = factory.return_value
            client.responses.create.side_effect = [research, writing]
            result = OpenAIWriter().write(self.package["candidate"])
        self.assertEqual(factory.call_args.kwargs["max_retries"], 0)
        self.assertEqual(client.responses.create.call_count, 2)
        self.assertEqual(client.responses.create.call_args_list[0].kwargs["max_tool_calls"], 2)
        self.assertEqual(len(result["articles"]), 2)
