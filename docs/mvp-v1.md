# 블로그 원고 작업실 — 오프라인 MVP

네이버 **lovethursday**와 티스토리 **zusoozi**의 콘텐츠를 준비하는 Python/Streamlit 도구입니다.
샘플 키워드 CSV 20개 → 서로 다른 플랫폼별 템플릿 초안 40개 → 검토·승인 → 수동 발행용 다운로드 흐름을 제공합니다.

**실제 블로그 발행·로그인·크롤링·유료 API 호출은 구현하지 않았습니다.**
외부 인증 없이 동작하며, 생성 결과는 AI가 조사한 완성 원고가 아닌 **작성용 템플릿**입니다.
본문의 `[작성 필요]`를 채우고 출처를 확인해야 승인할 수 있습니다.

## 빠른 시작 (Python 3.11 이상)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dashboard]'
blog-mvp import-csv samples/keywords.csv --dry-run
streamlit run app.py
```

Windows PowerShell에서는 가상환경 활성화에 `.venv\Scripts\Activate.ps1`을 사용하세요.
브라우저에서 http://localhost:8501 을 엽니다.
`.env.example`은 설정 설명용이며 자동 로드하지 않습니다.
필요할 때 환경 변수 `BLOG_DB`로 SQLite 파일 경로를 지정합니다.

대시보드 없이도 사용할 수 있습니다.

```bash
python -m pip install -e .
blog-mvp import-csv samples/keywords.csv
blog-mvp list
blog-mvp list --status review
blog-mvp export 승인된_원고_ID --out output
```

실제 승인·편집은 대시보드에서 수행합니다. dry-run은 DB 파일도 만들지 않습니다.

## 갤럭시 태블릿 — PC 설치 없이 사용

1. GitHub에서 이 PR이 병합된 저장소를 열고 **Code → Codespaces → Create codespace on main**을 선택합니다.
   병합 전에는 이 PR의 작업 브랜치를 선택해 Codespace를 만들 수 있습니다.
2. 준비가 끝나면 터미널에서 `streamlit run app.py`를 실행합니다.
3. **Ports → 8501 → Open in Browser**를 누릅니다. 포트 공개 범위는 **Private**로 유지합니다.
   GitHub 로그인과 Codespaces 접근 권한이 브라우저 접근을 보호합니다.
4. **샘플 20개로 시작** 또는 CSV 업로드로 초안을 생성합니다.
5. 승인 대기 목록에서 원고를 선택합니다. 네이버/티스토리 내용을 비교하고 본문을 보완합니다.
6. 근거 URL, 발행일(모르면 빈칸), 검토 메모를 입력합니다. 검토 체크를 완료하고 **검토 내용 저장 → 저장된 원고 승인**을 누릅니다.
7. 승인 목록에서 Markdown·HTML·메타데이터 JSON을 내려받습니다. 블로그 편집기에서 직접 작성·발행합니다.
8. 발행 후 실제 글 URL을 입력해 완료를 기록합니다. 이 버튼은 외부 사이트에 접속하지 않습니다.

Codespaces에는 무료 사용량과 유료 한도가 있습니다. 작업 후 중지하세요.
SQLite는 같은 Codespace를 중지/재개하면 남지만, **Codespace 삭제 시 사라질 수 있습니다.**
대시보드를 멈춘 뒤 `data/blog.sqlite3`를 안전한 곳에 백업하세요. Git에는 기본적으로 올리지 않습니다.
휴대기기 화면의 실제 렌더링은 아직 실기기 검증 전이며 Streamlit AppTest로 주요 흐름을 검증합니다.

## CSV와 지표

샘플 파일의 헤더를 그대로 사용하세요. UTF-8/BOM 지원, 최대 1 MB·500행입니다.
빈 키워드, 중복 키워드, 비정상 숫자, 잘못된 날짜/URL은 전체 입력을 거절합니다.
같은 키워드/플랫폼을 재입력하면 기존 원고와 검토 결과를 유지합니다.

| 필드 | 의미 |
| --- | --- |
| keyword | 키워드, 1~100자 |
| monthly_searches | 월 검색량 입력값, 없으면 빈칸 |
| trend_index | 상대 추세 0~100, 검색량과 별도로 보관 |
| ad_competition | 광고 경쟁 지수 0~100, 없으면 빈칸 |
| profitability_score | 수익성 **추정 점수** 0~100, CPC·예상 수익액 아님 |
| persistence_score / ease_score | 지속성 / 작성 용이성 편집 점수 0~100 |
| metric_source_url / measured_at | 지표 출처 URL / 측정일 YYYY-MM-DD |
| metric_kind | sample / measured / estimated (입력자 분류, 앱에서 검증하지 않음) |
| profitability_kind | sample / estimated만 허용 |
| source_url / source_published_at / source_note | 원고 근거 URL / 발행일 / 메모 |

실측·추정 지표는 출처와 측정일이 필수입니다. 샘플 수치는 모두 가상값입니다.
원고 근거는 CSV로 가져와도 **미검증**으로 등록되며, 앱이 URL을 방문하거나 날짜를 추정하지 않습니다.

점수 = 검색량 30% + 경쟁 기회 25% + 수익성 20% + 지속성 15% + 작성 용이성 10%.
검색량 점수는 `min(100, log(1+월검색량)/log(100001)*100)`,
경쟁 기회는 `100-광고경쟁지수`입니다. 누락된 검색량/경쟁도는 보수적으로 0점 처리하며 누락 목록을 표시합니다.
광고 경쟁도는 콘텐츠 경쟁의 대리지표일 뿐입니다. 추세 지수는 월 검색량으로 환산하지 않습니다.

## 상태와 검토

`draft → review → approved → scheduled → published`

- 초안·검토 필요가 승인 대기 목록에 표시됩니다.
- 출처 등록·확인, 본문 보완, 3가지 검토 체크, 검토자·메모가 모두 있어야 승인됩니다.
- 같은 주제의 두 플랫폼 본문이 공백 제거 후 85% 이상 유사하면 승인되지 않습니다.
  이는 단순 문자열 비교이며 의미적 표절이나 사실 정확성을 보장하지 않습니다.
- 승인 후 수정하면 review로 되돌아갑니다. 오래 열린 화면의 수정은 버전 충돌로 차단합니다.
- scheduled는 로컬 저장소의 미래 일정 기록만 지원하며 UI에 예약 실행 기능은 없습니다.
- published는 수동 발행한 글 URL의 기록입니다. 실제 발행 여부는 사람이 확인합니다.
- 변경 이벤트를 SQLite에 보관합니다. 검토자 이름은 직접 입력하는 로컬 기록이며 인증된 서명은 아닙니다.
- 승인된 원고만 Markdown·HTML·JSON을 내보냅니다. HTML은 스크립트 실행을 막는
  텍스트 보존형 문서이므로 Markdown 서식 기호가 보입니다. 발행 전 편집기에서 서식을 조정하세요.

## 테스트

```bash
python -m pip install -e '.[dashboard]'
python -m unittest discover -s tests -v
python -m compileall -q src app.py tests
```

GitHub Actions에서 Python 3.11/3.12의 단위 테스트, CLI dry-run, Streamlit AppTest를 실행합니다.
dashboard 의존성 없이 실행하면 UI 테스트만 건너뜁니다. CI는 UI 테스트도 실행합니다.
테스트 DB는 임시 디렉터리에 만들고 삭제합니다.

## 배포·지속 저장소·API 연결

현재 MVP는 **로컬 또는 비공개 Codespaces 전용**입니다. 공개 배포 인증과 클라우드 DB는 아직 연결하지 않았습니다.
`BLOG_DEPLOYED=true`이면 앱과 저장소가 실행을 거절합니다.
이 설정은 공개 배포를 지원한다는 뜻이 아니며 포트 공개는 금지하세요.

다음 단계, GitHub PR 기반 콘텐츠 승인 설계, 비용 상한/재시도 및
지속 저장소 설계는 [아키텍처와 연결 계획](docs/architecture.md)을 참고하세요.
코드 PR의 승인은 개별 블로그 원고의 승인과 별개입니다.

매일 실행할 수 있는 [샘플 검증 workflow](.github/workflows/sample-schedule.yml)는
기본 비활성화이며 API 호출 없이 CSV dry-run만 수행합니다.
GitHub Actions의 임시 디스크나 만료되는 artifact에 운영 원고를 보관하지 않습니다.
