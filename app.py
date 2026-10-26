"""Single-button writing desk. Original CSV editor remains in legacy_app.py."""
import os
import html
import streamlit as st
import streamlit.components.v1 as components

from blog_mvp.copybox import copy_html
from blog_mvp.demo import load_demo
from blog_mvp.drafts import CHECKS, export_files
from blog_mvp.store import Store
from blog_mvp.writer import CATEGORIES, plain_package, run_live, setup_problems, usage

st.set_page_config(page_title="오늘의 블로그 글", page_icon="✍️", layout="centered")
st.title("오늘의 블로그 글")
st.caption("수요 조사 → 주제 선정 → 자료 조사·집필 → 내가 읽고 발행 결정")
if os.getenv("BLOG_DEPLOYED", "").lower() == "true":
    st.error("공개 배포에는 인증과 지속 저장소 연결이 필요합니다.")
    st.stop()
store = Store(os.getenv("BLOG_DB", "data/blog.sqlite3"))
problems = setup_problems()
category = st.selectbox("관심 분야", list(CATEGORIES))
consent = False
with st.expander("연결 설정과 사용량", expanded=False):
    if problems:
        st.write("실제 검색 분석을 시작하려면 최초 1회 API 연결이 필요합니다.")
        for problem in problems:
            st.caption(problem)
        st.markdown("[설정 안내](https://github.com/poongkmj-arch/blog/blob/main/docs/writing-desk.md)")
    else:
        st.success("API 설정값이 준비되어 있습니다. 연결 성공 여부는 실행 시 확인합니다.")
    counts = usage(store)
    st.caption(f"오늘 실행 {counts['runs']}회 · 추정 예산 차감 USD {counts['reserved_usd']:.2f} / 2.00")
    st.caption("실행당 추정 예산 USD 0.50 차감 · 최대 네이버 2회, AI 2회와 웹 검색 2회 · 자동 재시도 없음")
    st.caption("예산 차감액은 실제 청구 상한이 아닙니다. 공급자 요금과 프로젝트 한도도 확인하세요.")
    consent = st.checkbox("유료 AI 조사·원고 생성에 동의합니다", disabled=bool(problems))
if problems:
    st.info("실제 검색 분석은 연결 대기 중입니다. 아래에서 완성 글 예시를 먼저 볼 수 있습니다.")
if st.button("오늘의 글 만들기", type="primary", disabled=bool(problems) or not consent):
    try:
        with st.status("오늘의 주제를 찾고 있습니다.", expanded=True) as status:
            result = run_live(store, category, consent=consent, progress=st.write)
            st.session_state["active_ids"] = result["draft_ids"]
            status.update(label="두 플랫폼 원고를 준비했습니다.", state="complete")
    except Exception as exc:
        st.error(str(exc) if isinstance(exc, ValueError) else "작업을 완료하지 못했습니다. 연결 설정을 확인하세요.")
if st.button("완성 글 예시 보기"):
    result = load_demo(store)
    st.session_state["active_ids"] = result["draft_ids"]

drafts = [d for d in store.list() if d.get("generator") in {"researched-ai", "editorial-demo"}]
if not drafts:
    st.write("완성 원고가 여기에 표시됩니다. 빈칸을 채우거나 CSV를 만들 필요가 없습니다.")
    st.stop()
st.divider()
view = st.radio("원고함", ["검토할 글", "발행할 글", "보류한 글", "전체"], horizontal=True)
states = {"검토할 글": {"review"}, "발행할 글": {"approved", "published"},
          "보류한 글": {"draft"}, "전체": {"review", "approved", "published", "draft", "scheduled"}}
drafts = [d for d in drafts if d["status"] in states[view]]
active = st.session_state.get("active_ids", [])
drafts.sort(key=lambda d: (d["id"] not in active, -float(d["score"]["total"]), d["platform"]))
if not drafts:
    st.info("이 원고함에는 아직 글이 없습니다.")
    st.stop()
selected = st.selectbox("읽을 글", [d["id"] for d in drafts],
                        format_func=lambda key: next(
                            f"{'네이버' if d['platform'] == 'naver' else '티스토리'} · {d['title']}"
                            for d in drafts if d["id"] == key))
draft = store.get(selected)
if draft.get("mode") == "demo":
    st.warning("완성 글 예시입니다. 실시간 검색 분석이나 AI 조사 결과가 아닙니다.")
with st.expander("이 주제를 고른 이유 · 자료 확인"):
    st.write(draft["plan"]["reason"])
    st.write(draft["plan"]["angle"])
    st.write(draft["plan"]["timeliness"])
    if draft.get("mode") == "live":
        metric = draft["metrics"]
        prefix = "구간값을 반영한 하한" if metric.get("volume_is_lower_bound") else "월 검색량"
        st.write(f"{prefix}: {metric['volume']:,.0f} · 지속성 점수: {metric['persistence']}/100")
        st.caption(f"측정일 {metric['measured_at']} · 추세 기간 {' ~ '.join(metric['period'])}")
        st.caption("선택한 분야의 연관 후보 최대 5개 내 비교입니다. 검색량은 예상 방문자 수가 아닙니다.")
        st.caption(metric["profitability_note"] + " · 광고 경쟁도는 콘텐츠 경쟁의 대리값입니다.")
    for source in draft["sources"]:
        st.write(source["url"])
        st.caption("발행일: " + (source.get("published_at") or "미상") + " · " + source.get("note", ""))
    for item in draft["verification_items"]:
        st.write("확인할 내용: " + item)
st.subheader(draft["title"])
for paragraph in draft["body"].split("\n\n"):
    st.markdown(html.escape(paragraph), unsafe_allow_html=False)

if draft["status"] in {"review", "draft"}:
    with st.expander("원고 직접 수정"):
        with st.form("edit-" + selected + "-" + str(draft["revision"])):
            title = st.text_input("제목", draft["title"], max_chars=100)
            body = st.text_area("본문", draft["body"], height=400, max_chars=12000)
            if st.form_submit_button("수정 저장"):
                try:
                    store.edit(selected, draft["revision"], title=title, body=body,
                               sources=[{**s, "verified": False} for s in draft["sources"]],
                               checks={key: False for key in CHECKS}, reviewer="", review_note="")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    confirmed = st.checkbox("출처와 핵심 사실, 두 플랫폼의 차이를 확인했고 이 글을 발행하겠습니다",
                            key=f"confirmed-{selected}-{draft['revision']}")
    if st.button("이 글 승인", type="primary", disabled=not confirmed):
        try:
            store.edit(selected, draft["revision"], title=draft["title"], body=draft["body"],
                       sources=[{**s, "verified": True} for s in draft["sources"]],
                       checks={key: True for key in CHECKS}, reviewer="로컬 운영자",
                       review_note="원고·출처·핵심 사실·플랫폼 차별화를 확인하고 발행용으로 승인")
            store.transition(selected, draft["revision"] + 1, "approved")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if draft["status"] == "review" and st.button("지금은 보류"):
        try:
            store.transition(selected, draft["revision"], "draft")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
else:
    st.success("발행할 글입니다. 제목과 본문을 각각 복사해 블로그에 붙여넣으세요.")
    title, text = plain_package(draft)
    components.html(copy_html(title, "제목 복사"), height=165)
    components.html(copy_html(text, "본문 전체 복사"), height=165)
    st.download_button("본문 TXT 저장", text, f"{selected}.txt", "text/plain")
    with st.expander("추가 다운로드"):
        for suffix, content in export_files(draft).items():
            st.download_button(suffix.upper(), content, f"{selected}.{suffix}")
    if draft["status"] == "approved" and st.button("다시 수정하기"):
        try:
            store.transition(selected, draft["revision"], "review")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
st.caption("발행은 자동으로 진행되지 않습니다. 블로그 편집기에서 붙여넣은 뒤 직접 발행하세요.")
