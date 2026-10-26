"""Zero-paid-API topic collection and optional Ollama draft generation.

Runs with Python 3.11 standard library. Never publishes content.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

FEEDS = {
    "economy": "https://www.google.com/alerts/feeds/00000000000000000000/00000000000000000000",
}
# Google News search RSS supplements existing operator-configured feeds.
# These are discovery feeds, not verified original reporting.
SEARCH_QUERIES = {
    "stocks": "주가 OR 증시 OR 반도체 실적 OR 금리",
    "housing": "서울 아파트 OR 부동산 규제 OR 주택담보대출 OR 청약",
    "tax": "양도소득세 OR 종합부동산세 OR 상속세 OR 증여세 OR 세법 개정",
}

def discovery_urls():
    return [
        "https://news.google.com/rss/search?" +
        urllib.parse.urlencode({"q": query + " when:3d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
        for query in SEARCH_QUERIES.values()
    ]

# Operator must configure approved RSS URLs; no placeholder is queried.
def collect(urls):
    items = []
    for url in urls:
        if not url.startswith("https://"):
            raise ValueError("Only HTTPS RSS URLs are allowed")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BlogWorkbench/0.1"})
            with urllib.request.urlopen(req, timeout=12) as response:
                data = response.read(1_000_001)
            if len(data) > 1_000_000:
                raise ValueError("RSS too large")
            root = ET.fromstring(data)
            for item in root.findall(".//item")[:15]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                description = html.unescape(re.sub(r"<[^>]+>", " ", item.findtext("description") or ""))
                description = re.sub(r"\s+", " ", description).strip()[:1200]
                published = (item.findtext("pubDate") or "").strip()[:100]
                if title and link.startswith("https://"):
                    items.append({"title": title[:180], "source_url": link, "summary": description, "published": published})
        except (OSError, ET.ParseError, ValueError) as exc:
            print(f"Feed skipped: {type(exc).__name__}")
    unique = {i["source_url"]: i for i in items}
    return list(unique.values())[:90]


CATEGORIES = {
 "stocks": ("주가","증시","코스피","코스닥","주식","급등","급락","실적","영업이익","삼성전자","하이닉스","엔비디아","반도체","환율","금리","배당","관세","공매도","상장","FOMC"),
 "housing": ("부동산","아파트","집값","주택","전세","월세","청약","재건축","재개발","분양","대출","주담대","DSR","LTV","공급대책"),
 "tax": ("세금","세제","세법","국세청","양도세","종부세","상속세","증여세","소득세","법인세","연말정산","공제","세율","과세"),
}
IMPACT = ("인상","인하","상승","하락","급등","급락","변경","개편","발표","시행","규제","완화","확대","축소","폐지","실적","전망","동결")
HIGH_VALUE = ("전략적 제휴","파트너십","공급계약","수주","계약금액","실적발표","분기실적","영업이익","전년 대비","매출액","합작","인수합병","공시","고객사","협력")
LOW_VALUE = ("행사","축제","공모전","봉사","기부","캠페인","인사","수상","업무협약","기념식")

def rank_topics(items):
    ranked = []
    for item in items:
        title = item["title"].casefold()
        counts = {cat: sum(word.casefold() in title for word in words) for cat, words in CATEGORIES.items()}
        category = max(counts, key=counts.get)
        relevant = counts[category]
        score = min(relevant, 4)*5 + min(sum(w in title for w in IMPACT),3)*3 + min(sum(w.casefold() in title for w in HIGH_VALUE),3)*5 - sum(w in title for w in LOW_VALUE)*7
        if not relevant:
            category = "other"
            score -= 12
        ranked.append({**item, "category": category, "interest_score": score})
    return sorted(ranked, key=lambda item: item["interest_score"], reverse=True)


def apply_naver_trends(topics):
    """Optional legacy free-tier Datalab check. Never calls the metered API HUB."""
    client_id = os.getenv("NAVER_DATALAB_CLIENT_ID", "").strip()
    secret = os.getenv("NAVER_DATALAB_CLIENT_SECRET", "").strip()
    if os.getenv("ENABLE_NAVER_DATALAB", "NO") != "YES" or not client_id or not secret:
        print("Naver Datalab: disabled (no legacy credentials or explicit opt-in)")
        return topics
    today = dt.date.today()
    groups = [
        ("stocks", ["주식", "코스피", "삼성전자", "반도체"]),
        ("housing", ["부동산", "아파트", "서울 집값", "주택담보대출"]),
        ("tax", ["세금", "양도소득세", "상속세", "종합부동산세"]),
    ]
    payload = {"startDate": (today - dt.timedelta(days=27)).isoformat(),
               "endDate": today.isoformat(), "timeUnit": "date",
               "keywordGroups": [{"groupName": category, "keywords": keywords}
                                 for category, keywords in groups]}
    request = urllib.request.Request(
        "https://openapi.naver.com/v1/datalab/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "X-Naver-Client-Id": client_id,
                 "X-Naver-Client-Secret": secret},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            result = json.load(response)
    except (OSError, ValueError) as exc:
        print(f"Naver Datalab unavailable ({type(exc).__name__}); RSS ranking retained")
        return topics
    trends = {}
    for series in result.get("results", []):
        points = [float(p["ratio"]) for p in series.get("data", []) if "ratio" in p]
        if len(points) >= 14:
            recent = sum(points[-7:]) / 7
            previous = sum(points[-14:-7]) / 7
            # Small capped bonus: cross-category direction, not search-volume comparison.
            trends[series["title"]] = max(-3, min(3, round((recent - previous) / max(previous, 1) * 3)))
    for topic in topics:
        category = topic.get("category", "other")
        topic["naver_trend_change_bonus"] = trends.get(category, 0)
        topic["interest_score"] += topic["naver_trend_change_bonus"]
    print("Naver Datalab: relative 7-day change applied; NOT absolute search volume")
    return sorted(topics, key=lambda t: t["interest_score"], reverse=True)

def ollama_generate(topic, url, endpoint, model):
    # Local/private endpoint only: do not send untrusted RSS text to arbitrary hosts.
    if not (endpoint.startswith("http://127.0.0.1:") or endpoint.startswith("http://localhost:")):
        raise ValueError("Only local Ollama endpoints are supported")
    prompt = (
        "다음은 검증 전 참고 주제입니다. 제공된 제목과 URL만으로 사실을 확정하지 마세요. "
        "확인되지 않은 수치, 인용, 정책을 만들어내지 마세요. "
        "한국어 블로그 초안 600자 이상을 작성하되 첫 줄은 '검증 전 초안'으로 시작하세요. "
        "마지막에 반드시 '출처 확인 필요'를 적으세요.\n"
        f"주제: {topic}\n참고 URL: {url}"
    )
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(endpoint.rstrip("/") + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as response:
        result = json.load(response)
    return result.get("response", "").strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/stage1")
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    urls = [u.strip() for u in os.getenv("BLOG_RSS_URLS", "").split(",") if u.strip()]
    if os.getenv("ENABLE_DISCOVERY_RSS", "YES").upper() == "YES":
        urls += discovery_urls()
    candidates = apply_naver_trends(rank_topics(collect(urls)))
    # Keep coverage across stocks, housing and tax instead of letting one feed dominate.
    selected = []
    seen = set()
    for category in ("stocks", "housing", "tax"):
        for item in candidates:
            if item["category"] == category and item["source_url"] not in seen:
                selected.append(item)
                seen.add(item["source_url"])
                if sum(t["category"] == category for t in selected) >= 5:
                    break
    for item in candidates:
        if len(selected) >= 30:
            break
        if item["source_url"] not in seen:
            selected.append(item)
            seen.add(item["source_url"])
    topics = sorted(selected, key=lambda t: t["interest_score"], reverse=True)
    print("Discovery: category-balanced RSS candidates; scores are heuristics, NOT Naver search volume")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (output / f"topics-{stamp}.json").write_text(
        json.dumps({"collected_at_utc": stamp, "topics": topics}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    for index, topic in enumerate(topics[:5], 1):
        print(f"TOP {index}: [{topic['category']}] score={topic['interest_score']} {topic['title'][:90]}")
    if args.generate and topics:
        endpoint = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        model = os.getenv("OLLAMA_MODEL", "qwen3:4b")
        for index, topic in enumerate(topics[:3], 1):
            draft = ollama_generate(topic["title"], topic["source_url"], endpoint, model)
            if draft:
                safe_title = re.sub(r"[\r\n]", " ", topic["title"])
                text = (f"# {safe_title}\n\n> 검증 전 초안 — 게시 금지\n\n"
                        f"{draft}\n\n원문 링크(주장 검증 전): {topic['source_url']}\n")
                (output / f"draft-{stamp}-{index}.md").write_text(text, encoding="utf-8")
    print(f"Collected {len(topics)} topics. Draft generation: {'on' if args.generate else 'off'}")

if __name__ == "__main__":
    main()
