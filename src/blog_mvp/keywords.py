"""Strict CSV contract: measurements are never presented as verified by this app."""
import csv
import io
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from typing import Protocol
from urllib.parse import urlsplit

MAX_BYTES = 1_000_000
MAX_ROWS = 500
WEIGHTS = {"volume": .30, "opportunity": .25, "profitability": .20,
           "persistence": .15, "ease": .10}
FIELDS = [
    "keyword", "monthly_searches", "trend_index", "ad_competition",
    "profitability_score", "persistence_score", "ease_score",
    "metric_source_url", "measured_at", "metric_kind", "profitability_kind",
    "source_url", "source_published_at", "source_note",
]


def valid_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and not any(c.isspace() or c in '<>"' for c in value))
    except ValueError:
        return False


def iso_date(value: str) -> str:
    if value and date.fromisoformat(value).isoformat() != value:
        raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다.")
    return value


def clean_keyword(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    if any(unicodedata.category(c).startswith("C") for c in value):
        raise ValueError("키워드에 제어 문자를 사용할 수 없습니다.")
    value = re.sub(r"\s+", " ", value)
    if not 1 <= len(value) <= 100:
        raise ValueError("키워드는 1~100자여야 합니다.")
    return value


@dataclass(frozen=True)
class Keyword:
    keyword: str
    monthly_searches: float | None
    trend_index: float | None
    ad_competition: float | None
    profitability_score: float
    persistence_score: float
    ease_score: float
    metric_source_url: str
    measured_at: str
    metric_kind: str
    profitability_kind: str
    source_url: str
    source_published_at: str
    source_note: str

    def to_dict(self) -> dict:
        return asdict(self)


class KeywordCollector(Protocol):
    def collect(self) -> list[Keyword]: ...


class CsvCollector:
    def __init__(self, data: bytes):
        self.data = data

    def collect(self) -> list[Keyword]:
        return parse_csv(self.data)


class OfficialApiCollector:
    def collect(self) -> list[Keyword]:
        raise RuntimeError("공식 API 인증·약관 검토 전에는 수집을 활성화할 수 없습니다.")


def parse_csv(data: bytes) -> list[Keyword]:
    if len(data) > MAX_BYTES:
        raise ValueError("CSV는 1 MB 이하여야 합니다.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("UTF-8 CSV 파일을 사용해 주세요.") from exc
    reader = csv.DictReader(io.StringIO(text), strict=True)
    try:
        headers = reader.fieldnames
        if not headers or len(set(headers)) != len(headers) or set(headers) != set(FIELDS):
            raise ValueError("CSV 헤더가 다릅니다. samples/keywords.csv 양식을 사용해 주세요.")
        items, seen = [], set()
        for index, row in enumerate(reader, start=2):
            if len(items) >= MAX_ROWS:
                raise ValueError("한 번에 최대 500개 키워드까지 입력할 수 있습니다.")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{index}행: 열 개수가 맞지 않습니다.")
            row = {key: value.strip() for key, value in row.items()}
            try:
                keyword = clean_keyword(row["keyword"])
                key = keyword.casefold()
                if key in seen:
                    raise ValueError("중복 키워드입니다.")
                seen.add(key)

                def number(name, maximum, optional=False):
                    raw = row[name]
                    if not raw and optional:
                        return None
                    value = float(raw)
                    if not math.isfinite(value) or not 0 <= value <= maximum:
                        raise ValueError(f"{name}: 0~{maximum} 범위여야 합니다.")
                    return value

                kind = row["metric_kind"]
                if kind not in {"sample", "measured", "estimated"}:
                    raise ValueError("metric_kind: sample/measured/estimated 중 하나여야 합니다.")
                # Ad bids are not publisher revenue; never label this score as actual earnings.
                if row["profitability_kind"] not in {"sample", "estimated"}:
                    raise ValueError("수익성 점수는 sample 또는 estimated만 허용합니다.")
                for field in ("metric_source_url", "source_url"):
                    if row[field] and not valid_url(row[field]):
                        raise ValueError(f"{field}: HTTP(S) URL이어야 합니다.")
                iso_date(row["measured_at"])
                iso_date(row["source_published_at"])
                if kind != "sample" and not (row["metric_source_url"] and row["measured_at"]):
                    raise ValueError("실측·추정 지표에는 출처 URL과 측정일이 필요합니다.")
                if row["source_published_at"] and not row["source_url"]:
                    raise ValueError("발행일에는 근거 URL이 필요합니다.")
                if len(row["source_note"]) > 2000:
                    raise ValueError("출처 메모는 2000자 이하여야 합니다.")
                items.append(Keyword(
                    keyword, number("monthly_searches", 1e12, True),
                    number("trend_index", 100, True), number("ad_competition", 100, True),
                    number("profitability_score", 100), number("persistence_score", 100),
                    number("ease_score", 100), row["metric_source_url"], row["measured_at"],
                    kind, row["profitability_kind"], row["source_url"],
                    row["source_published_at"], row["source_note"],
                ))
            except ValueError as exc:
                raise ValueError(f"{index}행: {exc}") from exc
        if not items:
            raise ValueError("CSV에 키워드가 없습니다.")
        return items
    except csv.Error as exc:
        raise ValueError("CSV 형식을 해석할 수 없습니다.") from exc


def score(item: Keyword) -> dict:
    # Fixed log scale: 100,000 monthly searches = 100; no cohort-dependent ranking.
    volume = min(100.0, math.log1p(item.monthly_searches or 0) / math.log1p(100000) * 100)
    opportunity = 0 if item.ad_competition is None else 100 - item.ad_competition
    components = {
        "volume": volume, "opportunity": opportunity,
        "profitability": item.profitability_score,
        "persistence": item.persistence_score, "ease": item.ease_score,
    }
    return {
        "total": round(sum(components[k] * v for k, v in WEIGHTS.items()), 2),
        "components": {k: round(v, 2) for k, v in components.items()},
        "weights": WEIGHTS,
        "missing": [k for k in ("monthly_searches", "ad_competition") if getattr(item, k) is None],
        "note": "광고 경쟁도의 역수 점수는 콘텐츠 경쟁의 대리지표입니다. 수익성은 추정이며 수익을 보장하지 않습니다.",
    }
