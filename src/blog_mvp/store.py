"""SQLite repository with atomic imports, optimistic locking and audit events."""
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .drafts import CHECKS, TARGETS, approval_errors, generate
from .keywords import iso_date, valid_url


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Store:
    def __init__(self, path="data/blog.sqlite3"):
        if os.getenv("BLOG_DEPLOYED", "").lower() == "true":
            raise RuntimeError("배포 모드는 MVP에서 차단됩니다. OIDC와 지속 저장소를 먼저 연결하세요.")
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS drafts (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, revision INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, draft_id TEXT NOT NULL,
                    action TEXT NOT NULL, at TEXT NOT NULL, details TEXT NOT NULL);
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def list(self, status=None):
        with closing(self.connect()) as db:
            result = [self._decode(row) for row in db.execute("SELECT * FROM drafts ORDER BY id")]
        result = [d for d in result if status is None or d["status"] == status]
        return sorted(result, key=lambda d: (-d["score"]["total"], d["keyword"], d["platform"]))

    @staticmethod
    def _decode(row):
        if row is None:
            raise ValueError("원고를 찾을 수 없습니다.")
        return {**json.loads(row["payload"]), "revision": row["revision"]}

    def get(self, draft_id):
        with closing(self.connect()) as db:
            return self._decode(db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone())

    def ingest(self, items, dry_run=False):
        candidates = [generate(item, platform) for item in items for platform in TARGETS]
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = {row[0] for row in db.execute("SELECT id FROM drafts")}
            unique = {d["id"]: d for d in candidates}
            new = [d for key, d in unique.items() if key not in existing]
            if not dry_run:
                for draft in new:
                    draft["created_at"] = now()
                    draft["updated_at"] = draft["created_at"]
                    db.execute("INSERT INTO drafts VALUES (?, ?, 1)", (draft["id"], encode(draft)))
                    db.execute("INSERT INTO events (draft_id, action, at, details) VALUES (?, ?, ?, ?)",
                               (draft["id"], "draft_created", now(), "{}"))
        return {"created": len(new), "skipped": len(candidates) - len(new), "dry_run": dry_run}

    def _save(self, db, draft, revision, action):
        draft["updated_at"] = now()
        payload = {k: v for k, v in draft.items() if k != "revision"}
        changed = db.execute("UPDATE drafts SET payload=?, revision=revision+1 WHERE id=? AND revision=?",
                             (encode(payload), draft["id"], revision)).rowcount
        if changed != 1:
            raise ValueError("다른 화면에서 수정되었습니다. 새로고침 후 다시 검토해 주세요.")
        db.execute("INSERT INTO events (draft_id, action, at, details) VALUES (?, ?, ?, ?)",
                   (draft["id"], action, now(), encode({
                       "revision": revision + 1, "reviewer": draft["reviewer"],
                       "note": draft["review_note"], "status": draft["status"]})))

    def edit(self, draft_id, revision, *, title, body, sources, checks, reviewer, review_note):
        if not title.strip() or not body.strip() or len(body) > 100_000 or len(title) > 200:
            raise ValueError("제목(1~200자)과 본문(1~100000자)을 확인해 주세요.")
        if len(sources) > 50:
            raise ValueError("출처는 최대 50개입니다.")
        for source in sources:
            if not valid_url(source.get("url", "")):
                raise ValueError("출처는 HTTP(S) URL이어야 합니다.")
            iso_date(source.get("published_at") or "")
            if not isinstance(source.get("verified"), bool):
                raise ValueError("출처 확인 값은 참/거짓이어야 합니다.")
        if set(checks) != set(CHECKS) or any(not isinstance(v, bool) for v in checks.values()):
            raise ValueError("검토 체크 값이 올바르지 않습니다.")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            draft = self._decode(db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone())
            if draft["status"] in {"scheduled", "published"}:
                raise ValueError("예약·발행 기록이 있는 원고는 직접 수정할 수 없습니다.")
            draft.update(title=title.strip(), body=body.strip(), sources=sources, checks=checks,
                         reviewer=reviewer.strip(), review_note=review_note.strip(), status="review")
            self._save(db, draft, revision, "edited_for_review")

    def transition(self, draft_id, revision, target, *, scheduled_for=None, published_url=None):
        allowed = {"draft": {"review"}, "review": {"draft", "approved"},
                   "approved": {"review", "scheduled", "published"},
                   "scheduled": {"review", "published"}, "published": set()}
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            draft = self._decode(db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone())
            if target not in allowed[draft["status"]]:
                raise ValueError("허용하지 않는 상태 전환입니다.")
            if target == "approved":
                others = [self._decode(r) for r in db.execute("SELECT * FROM drafts WHERE id != ?", (draft_id,))]
                sibling = next((d for d in others if d["keyword"].casefold() == draft["keyword"].casefold()
                                and d["platform"] != draft["platform"]
                                and d.get("job_key") == draft.get("job_key")), None)
                errors = approval_errors(draft, sibling)
                if errors:
                    raise ValueError(" / ".join(errors))
            if target == "scheduled":
                try:
                    when = datetime.fromisoformat(scheduled_for or "")
                    if when.tzinfo is None or when <= datetime.now(timezone.utc):
                        raise ValueError()
                except ValueError as exc:
                    raise ValueError("예약일은 시간대가 포함된 미래 ISO 날짜여야 합니다.") from exc
                draft["scheduled_for"] = when.isoformat()
            if target == "published":
                if not valid_url(published_url or ""):
                    raise ValueError("수동 발행한 글의 URL을 입력해 주세요.")
                from urllib.parse import urlsplit
                actual, expected = urlsplit(published_url), urlsplit(draft["target"])
                if actual.hostname != expected.hostname:
                    raise ValueError("대상 블로그의 발행 URL이어야 합니다.")
                if draft["platform"] == "naver" and not actual.path.startswith("/lovethursday/"):
                    raise ValueError("lovethursday 블로그의 글 주소를 입력해 주세요.")
                if actual.path in {"", "/", expected.path, expected.path + "/"}:
                    raise ValueError("블로그 홈이 아닌 글 주소를 입력해 주세요.")
                draft["published_url"] = published_url
            if target == "review":
                draft["checks"] = {key: False for key in CHECKS}
                draft["scheduled_for"] = None
            draft["status"] = target
            self._save(db, draft, revision, f"status:{target}")

    def events(self, draft_id):
        with closing(self.connect()) as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM events WHERE draft_id=? ORDER BY id", (draft_id,))]
