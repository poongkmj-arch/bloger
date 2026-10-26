"""Deterministic offline templates, not fabricated researched articles."""
import hashlib
import html
import json
import re
from difflib import SequenceMatcher

from .keywords import Keyword, score

TARGETS = {"naver": "https://blog.naver.com/lovethursday",
           "tistory": "https://zusoozi.tistory.com"}
CHECKS = ("sources_verified", "claims_verified", "originality_reviewed")
PLACEHOLDER = "[작성 필요]"


def markdown_text(value: str) -> str:
    value = html.escape(value)
    for char in "\\*_{}[]()#+.!|>~-" + chr(96):
        value = value.replace(char, "\\" + char)
    return value


def draft_id(keyword: str, platform: str) -> str:
    return hashlib.sha256(f"{keyword.casefold()}\0{platform}".encode()).hexdigest()[:24]


def generate(item: Keyword, platform: str) -> dict:
    if platform not in TARGETS:
        raise ValueError("지원하지 않는 플랫폼입니다.")
    topic = markdown_text(item.keyword)
    if platform == "naver":
        title = f"{item.keyword}, 일상 사례로 시작하는 이해"
        body = f"""# {markdown_text(title)}

> 오프라인 템플릿 초안입니다. 실제 조사·AI 생성·경험담이 아닙니다.

## 생활 속 질문으로 시작하기
{topic}에 관해 독자가 궁금해할 질문을 먼저 정리해 보겠습니다.
{PLACEHOLDER}: 독자의 상황과 질문을 작성해 주세요.

## 가상의 생활 사례
{PLACEHOLDER}: 실제 경험으로 오해되지 않도록 가정임을 밝힌 사례를 작성해 주세요.

## 사례를 이해하는 핵심 개념
{PLACEHOLDER}: 확인한 근거를 연결하고 사실과 의견을 구분해 주세요.

## 독자가 확인할 체크리스트
- 적용 조건과 예외를 확인했나요?
- 숫자와 기준일을 확인했나요?
- {PLACEHOLDER}: 주제에 맞는 질문을 추가해 주세요.

## 함께 생각해 볼 질문
{PLACEHOLDER}: 독자의 경험을 묻는 질문을 작성해 주세요.
"""
    else:
        title = f"{item.keyword} 분석 노트: 정의·조건·회계 연결"
        body = f"""# {markdown_text(title)}

> 검토용 구조 초안입니다. 확인되지 않은 수치나 투자 판단을 제공하지 않습니다.

## 분석 범위와 용어 정의
{topic}의 범위를 먼저 한정하겠습니다.
{PLACEHOLDER}: 정의와 적용 기준을 출처와 함께 작성해 주세요.

## 경제·산업에서 확인할 변수
| 변수 | 관찰할 자료 | 해석의 한계 |
| --- | --- | --- |
| {PLACEHOLDER} | 공식 통계 또는 공시 | 기준일과 범위 확인 |

## 중급회계 개념과의 연결
{PLACEHOLDER}: 관련 기준과 가정, 분개가 적용되는 조건을 설명해 주세요.
관련성이 없다면 억지로 연결하지 말고 이 절을 다른 분석 관점으로 바꿔 주세요.

## 반례와 민감도
{PLACEHOLDER}: 가정이 달라지는 사례와 결론의 한계를 검토해 주세요.

## 근거와 해석을 분리한 정리
{PLACEHOLDER}: 확인한 사실과 필자의 의견을 별도로 정리해 주세요.
"""
    sources = []
    if item.source_url:
        sources.append({"url": item.source_url, "published_at": item.source_published_at or None,
                        "note": item.source_note, "verified": False})
    return {
        "id": draft_id(item.keyword, platform), "keyword": item.keyword,
        "platform": platform, "target": TARGETS[platform], "title": title, "body": body,
        "tags": [item.keyword, "경제학습" if platform == "naver" else "회계분석"],
        "scheduled_for": None, "status": "draft",
        "template_version": "1", "generator": "offline-template",
        "metrics": item.to_dict(), "score": score(item), "sources": sources,
        "verification_items": [
            "근거 URL의 실제 내용을 열어 주장과 일치하는지 확인",
            "발행일·기준일 확인; 알 수 없으면 미상임을 명시",
            "금액·세율·회계 기준·투자 관련 표현과 적용 조건 확인",
            "가상 사례를 실제 경험처럼 쓰지 않았는지 확인",
            "플랫폼 간 구성과 문장 중복, 저작권 확인",
        ],
        "checks": {key: False for key in CHECKS}, "reviewer": "", "review_note": "",
        "published_url": None,
    }


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, re.sub(r"\s+", "", left),
                           re.sub(r"\s+", "", right), autojunk=False).ratio()


def approval_errors(draft: dict, sibling: dict | None = None) -> list[str]:
    errors = []
    if PLACEHOLDER in draft["body"]:
        errors.append("작성 필요 표시를 완성된 내용으로 바꿔 주세요.")
    if not draft["sources"] or not all(s.get("verified") for s in draft["sources"]):
        errors.append("근거를 등록하고 모든 출처를 확인해야 합니다.")
    if not all(draft["checks"].get(key) for key in CHECKS):
        errors.append("출처·주장·독창성 검토를 모두 완료해야 합니다.")
    if not draft["reviewer"].strip() or not draft["review_note"].strip():
        errors.append("검토자와 검토 메모가 필요합니다.")
    if sibling and similarity(draft["body"], sibling["body"]) >= .85:
        errors.append("다른 플랫폼 원고와 지나치게 유사합니다. 구성을 수정해 주세요.")
    return errors


def export_files(draft: dict) -> dict[str, str]:
    if draft["status"] not in {"approved", "scheduled", "published"}:
        raise ValueError("승인된 원고만 내보낼 수 있습니다.")
    sources = "\n".join(f"- {s['url']} (발행일: {s['published_at'] or '미상'})"
                        for s in draft["sources"])
    md = draft["body"] + "\n\n## 참고 출처\n" + sources + "\n"
    document = ('<!doctype html><html lang="ko"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{html.escape(draft["title"])}</title>'
                '<body><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'
                f'{html.escape(md)}</pre></body></html>')
    metadata = {k: draft[k] for k in ("id", "title", "platform", "target", "tags",
                                      "scheduled_for", "status", "sources")}
    return {"md": md, "html": document,
            "json": json.dumps(metadata, ensure_ascii=False, indent=2)}
