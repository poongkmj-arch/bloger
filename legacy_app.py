"""Run with: streamlit run app.py --server.address 127.0.0.1"""
import os
from pathlib import Path

import streamlit as st

from blog_mvp.drafts import CHECKS, approval_errors, export_files
from blog_mvp.keywords import parse_csv
from blog_mvp.store import Store

st.set_page_config(page_title="블로그 원고 작업실", page_icon="📝", layout="centered")
st.title("블로그 원고 작업실")
st.caption("네이버 lovethursday · 티스토리 zusoozi | 사람 검토 후 수동 발행")
if os.getenv("BLOG_DEPLOYED", "").lower() == "true":
    st.error("공개 배포는 아직 지원하지 않습니다. OIDC 인증과 지속 저장소 연결이 필요합니다.")
    st.stop()

store = Store(os.getenv("BLOG_DB", "data/blog.sqlite3"))
st.info("오프라인 MVP · 외부 API 호출 0회 · 예상 비용 $0 · 비용 상한 $0 · 재시도 0회")
st.caption("샘플 점수는 예시입니다. 원고는 AI 원고가 아닌 작성용 템플릿이며 자동 발행하지 않습니다.")

with st.expander("1. 키워드 CSV 입력", expanded=True):
    sample = Path(__file__).parent.joinpath("samples/keywords.csv").read_bytes()
    st.download_button("샘플 CSV 20개 내려받기", sample, "keywords.csv", "text/csv")
    upload = st.file_uploader("UTF-8 CSV 업로드 (최대 1 MB, 500개)", type=["csv"])
    use_sample = st.button("샘플 20개로 시작")
    use_upload = st.button("업로드한 CSV로 초안 생성", disabled=upload is None)
    if use_sample or use_upload:
        try:
            data = sample if use_sample else upload.getvalue()
            result = store.ingest(parse_csv(data))
            st.success(f"초안 {result['created']}개 생성 · 기존 원고 {result['skipped']}개 유지")
        except ValueError as exc:
            st.error(str(exc))

st.subheader("2. 승인 대기 목록")
labels = {"draft": "초안", "review": "검토 필요", "approved": "승인",
          "scheduled": "수동 발행 예정", "published": "발행 완료"}
selection = st.selectbox("상태", ["승인 대기", "전체", *labels.values()])
all_drafts = store.list()
visible = [d for d in all_drafts if
           selection == "전체" or
           (selection == "승인 대기" and d["status"] in {"draft", "review"}) or
           labels[d["status"]] == selection]
st.write(f"전체 {len(all_drafts)}개 · 현재 목록 {len(visible)}개")
if not visible:
    st.info("목록이 비어 있습니다. 샘플을 불러오거나 상태 필터를 바꿔 주세요.")
    st.stop()
st.dataframe([{"주제": d["keyword"], "플랫폼": d["platform"], "상태": labels[d["status"]],
               "점수": d["score"]["total"], "지표": d["metrics"]["metric_kind"],
               "수익성": d["metrics"]["profitability_kind"]} for d in visible],
             hide_index=True, use_container_width=True)
selected = st.selectbox("검토할 원고", [d["id"] for d in visible],
                        format_func=lambda i: next(f"{d['keyword']} · {d['platform']}" for d in visible if d["id"] == i))
draft = store.get(selected)
sibling = next((d for d in all_drafts if d["keyword"] == draft["keyword"] and d["id"] != selected), None)
with st.expander("지표·출처 메타데이터"):
    st.write("월 검색량은 CSV 입력값이며 이 앱이 검증하지 않습니다. 상대 추세는 0~100 별도 지표입니다.")
    st.write("광고 경쟁도는 콘텐츠 경쟁도의 대리값입니다. 수익성 점수는 수익액이나 CPC가 아닙니다.")
    st.json({"metrics": draft["metrics"], "score": draft["score"], "sources": draft["sources"]})
st.markdown(draft["body"], unsafe_allow_html=False)
if sibling:
    with st.expander("다른 플랫폼 원고 비교"):
        st.markdown(sibling["body"], unsafe_allow_html=False)
st.write("검증 필요 항목")
for item in draft["verification_items"]:
    st.write("• " + item)

if draft["status"] not in {"scheduled", "published"}:
    with st.form(f"editor-{selected}-{draft['revision']}"):
        title = st.text_input("제목", draft["title"], max_chars=200)
        body = st.text_area("Markdown 본문", draft["body"], height=420, max_chars=100000)
        st.caption("출처 URL | 발행일 YYYY-MM-DD (미상은 빈칸) | 메모 — 한 줄에 한 출처")
        source_text = st.text_area("근거 출처", "\n".join(
            f"{s['url']} | {s.get('published_at') or ''} | {s.get('note', '')}" for s in draft["sources"]))
        # Deliberately unchecked on every saved revision: user reconfirms after edits.
        checked = {
            CHECKS[0]: st.checkbox("모든 출처 원문과 발행일 또는 미상 여부를 직접 확인했습니다"),
            CHECKS[1]: st.checkbox("숫자·주장·적용 조건을 검증하고 사실과 의견을 구분했습니다"),
            CHECKS[2]: st.checkbox("플랫폼별 차별화와 저작권을 검토했습니다"),
        }
        reviewer = st.text_input("검토자", draft["reviewer"])
        note = st.text_area("검토 메모 (미상 날짜·검증 결과 등)", draft["review_note"])
        save = st.form_submit_button("검토 내용 저장")
    if save:
        try:
            sources = []
            for line in source_text.splitlines():
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split("|", 2)]
                if len(parts) != 3:
                    raise ValueError("출처는 URL | 발행일 | 메모 형식으로 입력해 주세요.")
                sources.append({"url": parts[0], "published_at": parts[1] or None,
                                "note": parts[2], "verified": checked[CHECKS[0]]})
            store.edit(selected, draft["revision"], title=title, body=body, sources=sources,
                       checks=checked, reviewer=reviewer, review_note=note)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

if draft["status"] == "review":
    errors = approval_errors(draft, sibling)
    for error in errors:
        st.warning(error)
    if st.button("저장된 원고 승인", disabled=bool(errors)):
        try:
            store.transition(selected, draft["revision"], "approved")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
elif draft["status"] == "draft":
    if st.button("검토 필요로 이동"):
        try:
            store.transition(selected, draft["revision"], "review")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

if draft["status"] in {"approved", "scheduled", "published"}:
    st.subheader("3. 수동 발행용 다운로드")
    for suffix, content in export_files(draft).items():
        st.download_button(f"{suffix.upper()} 내려받기", content,
                           f"{selected}.{suffix}", key=f"download-{suffix}")
    st.caption("HTML은 안전한 텍스트 보존 형식입니다. 블로그 편집기에서 서식을 확인해 주세요.")
    if draft["status"] != "published":
        url = st.text_input("직접 발행한 글 URL")
        if st.button("수동 발행 완료 기록"):
            try:
                store.transition(selected, draft["revision"], "published", published_url=url)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
with st.expander("변경 이력"):
    st.json(store.events(selected))
