"""One-request, free-tier-only Gemini draft generator. No publishing.

Standard library only. Fail closed when configuration is missing.
"""
import argparse
import json
import os
import re
import html
import xml.etree.ElementTree as ET
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

MODEL = "gemini-3.5-flash-lite"
BASE = "https://generativelanguage.googleapis.com/v1beta/models/"

# Numeric facts are extracted from the selected RSS item only, never invented.
NUMERIC_FACT_RE = re.compile(
    r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?\s*(?:%|퍼센트|%p|bp|bps|조\s*원|억\s*원|만\s*원|천\s*원|원|달러|억\s*달러|만\s*명|명|개|건|배|MW|GW|kWh|년|월|일|분기|호|위)?",
    re.IGNORECASE,
)

def rss_numeric_evidence(title, summary):
    """Return distinct source snippets containing numeric tokens with local context."""
    raw = html.unescape(re.sub(r"<[^>]+>", " ", title + ". " + summary))
    snippets = []
    for sentence in re.split(r"(?<=[.!?。])\s+|\n+", raw):
        sentence = " ".join(sentence.split())
        if NUMERIC_FACT_RE.search(sentence) and sentence not in snippets:
            snippets.append(sentence[:350])
    return snippets[:15]

def generate(topic, source_url, api_key, transport=None, summary='', published='', research='', community=''):
    if not api_key:
        raise ValueError("GEMINI_API_KEY missing")
    if os.getenv("CONFIRM_GEMINI_FREE_TIER") != "YES":
        raise ValueError("Free-tier verification required (CONFIRM_GEMINI_FREE_TIER=YES)")
    if os.getenv("ALLOW_PAID_GENERATION", "").lower() in ("true", "1", "yes"):
        raise ValueError("Paid generation must remain disabled")
    numeric_evidence = rss_numeric_evidence(topic, summary)
    evidence_block = "\n".join("- " + item for item in numeric_evidence) or "선택된 RSS 제목·요약에서 수치 미검출"
    prompt = (
        "당신은 경제·산업·투자·부동산을 쉽게 풀어 쓰는 블로그 '생각의 빈자리'의 칼럼니스트다. 뉴스 내용을 다시 나열하는 대신 사람의 선택과 그 이유를 이야기하고, 확인된 숫자를 바탕으로 자신만의 관점을 전한다.\n"
        "최우선 문체: 친한 동네 형이 동생에게 경제 이야기를 차근차근 들려주는 느낌이다. 독자를 무시하거나 가르치지 않는다. 친근하고 솔직하지만 가볍거나 유치하지 않다. '~다', '~이다', '~한다' 중심의 자연스러운 평서체를 사용한다. 필요한 곳에 '한번 생각해 보자', '그런데 여기서 중요한 게 있다', '이럴 때 사람들은 어떻게 할까?' 같은 표현을 문맥에 맞게 사용하되 반복하지 않는다. '~답니다', '~랍니다'와 회사 보고서·신문 사설 같은 딱딱한 문투는 쓰지 않는다.\n"
        "구성: (1) 첫 2~4문장에는 생활 속 상황과 독자가 생각해 볼 핵심 질문, 필자의 문제의식을 넣는다. (2) 중간에는 중학생도 이해할 쉬운 단어, 구체적인 사례와 일상 비유로 무슨 일이 벌어졌고 왜 그런지 설명한다. (3) 질문을 던졌으면 곧바로 실제 근거로 답한다. (4) 마지막 2~4문단에서 근거와 반론을 차례로 쌓아 필자의 생각을 밝히고, 마지막 문장에는 기억에 남는 통찰을 남긴다. 억지로 정해진 형식에 맞추지 않는다.\n"
        "어려운 경제 용어는 꼭 필요할 때만 사용하고 처음 등장하면 쉬운 말로 뜻을 풀어라. 예: '환금성이 낮다'보다 '나중에 팔고 싶어도 사겠다는 사람이 없을 수 있다'. '수급 구조 변화'보다 '집을 찾는 사람과 팔려는 사람의 숫자가 달라졌다'. 구체적인 사례가 없는 추상적 주장, 과장된 명언, 반복되는 결론, 딱딱한 소제목은 피한다.\n"
        "중요: 아래 예시는 오직 문체와 글의 호흡을 배우기 위한 가상 사례다. 예시 속 금액, 수치, 시장 동향을 현재 기사에 관한 사실로 옮겨 쓰거나 인용하지 않는다. 예시 문장을 그대로 베끼지 않는다.\n"
        "--- 문체 참고 예시 시작 ---\n"
        "# 아파트를 못 사면 사람들은 어디로 갈까?\n"
        "집을 사고 싶은 사람에게 가장 답답한 순간은 마음에 드는 집을 발견하고도 살 수 없다는 사실을 깨달을 때다. 그런데 여기서 한 가지 궁금한 점이 생긴다. 사람들은 집을 사는 걸 포기할까, 아니면 다른 집을 찾을까?\n"
        "### 대출이 막히면 선택도 달라진다\n"
        "한번 생각해 보자. 어떤 사람이 집을 사려고 돈을 모았는데 대출이 생각보다 적게 나온다고 치자. 그 사람은 처음부터 원했던 집 대신 조금 저렴한 집을 알아볼 수 있다. 이런 선택이 여러 사람에게서 동시에 나타나면 다른 주택을 찾는 사람이 늘어날 수 있다.\n"
        "### 가격보다 먼저 봐야 할 것\n"
        "나는 이런 이야기를 들으면 가격이 올랐다는 말보다 실제로 거래가 늘었는지부터 확인하고 싶다. 관심을 보이는 사람과 돈을 내고 집을 산 사람은 다르기 때문이다. 결국 중요한 건 사람들이 어디로 움직였느냐보다 왜 그곳을 선택했느냐는 질문이다.\n"
        "--- 문체 참고 예시 끝 ---\n"
        "사실 검증 원칙: RSS 제목·요약·발행일·출처와 실제로 수집된 공개 커뮤니티 글만 확인된 입력이다. 원문, 공시, 법률 조문, 뉴스 댓글을 직접 읽지 않았으면 읽었다고 주장하지 마라. 커뮤니티 검색 링크는 의견 수집 결과가 아니다. 근거가 없는 대중 반응, 특정 인물의 속마음, 시장 전망을 지어내지 마라.\n"
        "숫자는 핵심 근거다. 아래 'RSS 수치 근거' 중 현재 주제와 직접 관련된 금액·비율·기간·거래량·규모를 빠뜨리지 말고 본문에서 그 의미와 비교 기준을 쉽게 설명하라. 확인되지 않은 수치, 실제 통계처럼 보이는 가상 수치를 넣지 마라. 꼭 가정 사례가 필요하다면 '가상의 예시'임을 같은 문단에서 명확히 표시하라. 기사 게시일을 실적 수치로 오인하지 마라.\n"
        "정책·세금은 확정된 현행 제도와 제안·발의·시행 예정 사항을 구분하고, 실제 조문이나 세율이 입력되지 않았다면 구체적 변경 폭을 단정하지 마라. 기업 실적은 기간·매출·이익·증감률의 출처와 기준을 확인할 수 있을 때만 사용하라. 의견은 사실과 구분하라.\n"
        "커뮤니티 반응은 실제로 수집된 게시글에 근거가 있을 때만 찬성·반대·유보 논리를 소개하고, 소수 표본을 전체 여론으로 일반화하지 마라. 본문은 사람과 사건을 설명하고 결론에서 자신의 판단을 근거에 따라 차근차근 쌓아라.\n"
        "출력: 첫 줄은 '# 제목'. 독자의 호기심을 자극하지만 과장하지 않는 제목을 쓰고, 4~6개 자연스럽고 쉬운 소제목을 사용한다. 마지막 소제목은 딱딱한 '결론'보다 실제 주장이나 질문을 담는다. 표보다는 짧은 문단을 사용한다. 출처 링크는 맨 끝에 간결하게 표기한다. AI 제작 과정이나 'RSS 데이터의 한계' 같은 메타 표현은 본문에 쓰지 않는다. 작성 후 중복·어려운 단어·근거 없는 숫자·질문에 대한 답이 빠진 곳을 자체 점검하라.\n"
        f"RSS 제목: {topic[:180]}\nRSS 링크: {source_url[:500]}\n"
        f"RSS 수치 근거:\n{evidence_block}\nRSS 요약: {summary[:1200]}\n"
        f"RSS 발행일: {published[:100]}\n공식자료 탐색 결과: {research[:2400]}\n"
        f"공개 커뮤니티 조사: {community[:4000]}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"maxOutputTokens": 2300, "temperature": 0.65}}
    req = urllib.request.Request(
        BASE + MODEL + ":generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST")
    sender = transport or urllib.request.urlopen
    try:
        with sender(req, timeout=60) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini request failed (HTTP {exc.code}); no retry") from None
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    result = "\n".join(p.get("text", "") for p in parts).strip()
    if not result:
        raise RuntimeError("Gemini returned no text; no retry")
    return result

def verify_draft(draft_path, topics_path, topic_index=0):
    """Conservative evidence audit: unsupported claims are NOT marked verified."""
    draft = Path(draft_path).read_text(encoding="utf-8")
    topics = json.loads(Path(topics_path).read_text(encoding="utf-8"))["topics"]
    if topic_index < 0 or topic_index >= len(topics):
        raise ValueError("Topic index out of range for evidence audit")
    source = topics[topic_index]
    evidence = " ".join([source.get("title", ""), source.get("summary", "")])
    # Figures in the article must occur literally in the supplied RSS evidence.
    pattern = r"(?<![\w])\d[\d,.]*(?:%|원|억원|조원|만명|명|배|년|월|일|분기)?"
    figures = list(dict.fromkeys(re.findall(pattern, draft)))
    unsupported = [n for n in figures if n not in evidence and len(n) >= 2]
    rss_figures = list(dict.fromkeys(re.findall(pattern, evidence)))
    omitted = [n for n in rss_figures if n not in draft and len(n) >= 2]
    report = [
        "# 자동 근거 점검 보고서",
        "",
        "**상태: 사람의 사실 확인 필요 — 자동 검증 완료가 아님**",
        "",
        "검증 범위: 제공된 RSS 제목과 요약에 등장하는 수치의 문자열 일치 여부만 검사했습니다.",
        "RSS 자체의 진위, 계약 내용, 인과관계, 전망, 공식 공시 일치 여부는 확인하지 못합니다.",
        "",
        f"원자료: {source.get('source_url', '')}",
        f"검출된 수치 표현: {len(figures)}개",
        f"RSS 근거에서 일치하지 않는 수치 표현: {len(unsupported)}개",
        f"RSS에 있지만 초안에 빠진 수치 표현(날짜 등 포함): {len(omitted)}개",
        "",
        "## 근거에서 확인되지 않은 수치",
    ]
    report += [f"- {n}: 원자료와 공식 공시에서 재확인 필요" for n in unsupported] or ["- 검출된 불일치 없음. 사실 확인 완료를 의미하지 않습니다."]
    report += ["", "## RSS에서 누락된 수치 후보 (주제 관련성 확인)",]
    report += [f"- {n}: 기사 관련 핵심 수치인지 검토 후 본문 반영" for n in omitted] or ["- 문자열 기준 누락 없음. 수치의 맥락과 정확성은 별도 확인 필요."]
    report += ["", "## 발행 전 필수 확인", "- 기업 실적: DART 공시 또는 기업 IR 원문과 기간·수치 대조",
               "- 전략적 제휴: 당사자 공식 발표, 계약금액·기간·독점 여부 확인",
               "- 정책: 정부 공식 보도자료 및 시행일 확인",
               "- 분석 의견: 사실과 가정·전망 구분", "",
               "자동 게시 금지. 사람이 확인한 뒤 승인하세요."]
    path = Path(draft_path).with_name("fact-check-report.md")
    path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Evidence audit saved: {path}; unmatched figures: {len(unsupported)}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topics", required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--topic-index", type=int, default=0)
    parser.add_argument("--research-file", default="")
    parser.add_argument("--community-file", default="")
    parser.add_argument("--output", default="output/free-draft.md")
    args = parser.parse_args()
    if args.verify:
        verify_draft(args.output, args.topics, args.topic_index)
        return
    obj = json.loads(Path(args.topics).read_text(encoding="utf-8"))
    topics = obj.get("topics", [])
    if not topics:
        raise RuntimeError("No topics available; draft not generated")
    if args.topic_index < 0 or args.topic_index >= len(topics):
        raise ValueError(f"Topic index out of range: {args.topic_index} (total {len(topics)})")
    first = topics[args.topic_index]
    title = first.get("title", "").strip()
    url = first.get("source_url", "").strip()
    if not title or not url.startswith("https://"):
        raise ValueError("Invalid topic entry")
    research = Path(args.research_file).read_text(encoding="utf-8") if args.research_file else ""
    community = Path(args.community_file).read_text(encoding="utf-8") if args.community_file else ""
    body = generate(title, url, os.getenv("GEMINI_API_KEY", ""), summary=first.get("summary", ""), published=first.get("published", ""), research=research, community=community)
    if not body.lstrip().startswith("# "):
        raise RuntimeError("AI output missing Markdown title; draft not saved")
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("> AI 검증 전 초안 · 자동 발행 금지\n\n" + body + "\n", encoding="utf-8")
    print(f"Draft generated: {path} (one AI request, not published)")

if __name__ == "__main__":
    main()
