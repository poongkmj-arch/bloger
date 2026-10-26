"""Sample public discussions; never treat search hits as verified comments or polls."""
import argparse
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "BlogResearchEditorial/1.0 (public research)"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)

def collect(topic):
    terms = re.findall(r"[가-힣A-Za-z0-9]+", topic.get("title", ""))
    query = " ".join(terms[:5])
    results = []
    errors = []
    # Reddit is the only platform in this stage with public post text retrieved.
    url = "https://www.reddit.com/search.json?" + urllib.parse.urlencode(
        {"q": query, "sort": "new", "t": "month", "limit": 8, "raw_json": 1})
    try:
        payload = get_json(url)
        for child in payload.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = post.get("title", "")
            body = post.get("selftext", "")
            permalink = post.get("permalink", "")
            if title and permalink.startswith("/"):
                results.append({"platform": "Reddit", "type": "공개 게시글",
                                "title": title[:180], "excerpt": body[:550],
                                "url": "https://www.reddit.com" + permalink,
                                "score": post.get("score"),
                                "created_utc": post.get("created_utc")})
    except (OSError, ValueError, KeyError) as exc:
        errors.append("Reddit 공개 게시글 조회 실패: " + type(exc).__name__)
    # Search links for other platforms are research leads, NOT observed opinions.
    searches = {}
    for label, domain in [
        ("네이버 블로그", "blog.naver.com"), ("네이버 카페", "cafe.naver.com"),
        ("네이버 종목토론", "finance.naver.com"), ("다음 카페", "cafe.daum.net")]:
        searches[label] = "https://www.google.com/search?" + urllib.parse.urlencode(
            {"q": query + " site:" + domain})
    return {
        "topic": topic.get("title", ""), "sampled_public_posts": results,
        "research_links_only_not_collected": searches,
        "errors": errors,
        "method_note": "실제 수집된 공개 게시글만 의견 근거로 사용. 검색 링크는 조사 후보일 뿐 내용 수집 증거가 아님.",
        "limits": "댓글, 네이버 종목토론방·카페 본문 및 블로그 의견은 자동 수집하지 않음. 표본이 대표 여론이라는 주장 금지.",
        "editorial_rules": "찬성·반대·조건부 관점은 실제 근거가 있을 때만 요약하고 링크를 표기. "
                           "댓글 원문 장문 복제·닉네임 노출 금지. 의견을 사실처럼 쓰지 말 것. "
                           "표본 부족 시 대중의 반응을 꾸며내지 말 것."
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--topics", required=True)
    p.add_argument("--topic-index", type=int, required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    topics = json.loads(Path(args.topics).read_text(encoding="utf-8"))["topics"]
    if not 0 <= args.topic_index < len(topics):
        raise ValueError("Invalid topic index")
    data = collect(topics[args.topic_index])
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Public discussion posts retrieved: {len(data['sampled_public_posts'])}; not a poll")

if __name__ == "__main__":
    main()
