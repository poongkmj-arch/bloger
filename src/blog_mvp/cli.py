import argparse
import json
import os
import sys
from pathlib import Path

from .drafts import export_files
from .keywords import parse_csv
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description="오프라인 블로그 검토 파이프라인")
    parser.add_argument("--db", default=os.getenv("BLOG_DB", "data/blog.sqlite3"))
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("import-csv")
    ingest.add_argument("csv")
    ingest.add_argument("--dry-run", action="store_true")
    listing = sub.add_parser("list")
    listing.add_argument("--status", choices=["draft", "review", "approved", "scheduled", "published"])
    export = sub.add_parser("export")
    export.add_argument("id")
    export.add_argument("--out", default="output")
    args = parser.parse_args(argv)
    try:
        if args.command == "import-csv":
            # Validate all rows before opening the database.
            items = parse_csv(Path(args.csv).read_bytes())
            if args.dry_run:
                # Dry-run must not create a SQLite file or alter data.
                print(json.dumps({"keywords": len(items), "candidate_drafts": len(items) * 2,
                                  "api_calls": 0, "estimated_cost_usd": 0, "dry_run": True}))
                return 0
            result = Store(args.db).ingest(items)
        elif args.command == "list":
            result = [{k: d[k] for k in ("id", "keyword", "platform", "status", "revision")}
                      for d in Store(args.db).list(args.status)]
        else:
            draft = Store(args.db).get(args.id)
            files = export_files(draft)
            folder = Path(args.out)
            folder.mkdir(parents=True, exist_ok=True)
            for suffix, content in files.items():
                (folder / f"{draft['id']}.{suffix}").write_text(content, encoding="utf-8")
            result = {"exported": draft["id"], "directory": str(folder)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
