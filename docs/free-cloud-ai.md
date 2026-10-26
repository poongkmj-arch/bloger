# 무료 클라우드 AI 초안 생성 — 2단계

PR #3의 RSS 수집 코드 위에 추가한 **수동 실행형** Gemini 무료 티어 연동입니다.

## 비용 보호 원칙
- 무료 티어를 사용자가 AI Studio에서 직접 확인해야만 실행됩니다.
- Google AI Studio에서 **결제 연결이 없는 Free Tier 프로젝트**를 사용하세요.
- 이 프로그램은 과금 등급을 API로 독립 검증할 수 없습니다. `CONFIRM_GEMINI_FREE_TIER=YES`는 사용자 확인 기록이지 실제 과금 방지 장치가 아닙니다.
- 모델은 `gemini-3-flash-preview`로 고정합니다. 무료 지원 여부가 변경되면 실행을 중지하고 확인하세요.
- 실행당 최대 AI 요청 1회, 재시도 0회, 유료 대체 모델 없음.
- GitHub Actions workflow_dispatch 수동 실행만 허용합니다. 여러 번 실행하면 그만큼 무료 쿼터가 소진됩니다.
- GitHub Actions, 데이터 전송 및 기타 서비스 자체의 무료 한도는 별개입니다.
- 무료 등급 입력 내용이 제공자의 제품 개선에 이용될 수 있으므로 개인정보/비공개 자료를 넣지 마세요.

## 갤럭시 태블릿 설정
1. [Google AI Studio](https://aistudio.google.com/)에서 무료 등급 프로젝트와 API 키를 만듭니다. 결제 계정 연결은 하지 않습니다.
2. GitHub 저장소 > Settings > Secrets and variables > Actions > Secrets에 `GEMINI_API_KEY`를 저장합니다. 채팅/코드/PR에는 붙여넣지 않습니다.
3. 같은 Actions > Variables에 `CONFIRM_GEMINI_FREE_TIER=YES`를 저장합니다. AI Studio에서 프로젝트의 실제 무료 등급을 확인한 뒤에만 설정합니다.
4. 기존 1단계 `BLOG_RSS_URLS` 변수에 권한 있는 실제 HTTPS RSS 주소를 입력합니다.
5. PR 병합 후 Actions > Free-tier AI draft > Run workflow로 한 번 실행합니다.
6. 실행 결과의 `unverified-ai-draft` artifact를 내려받아 글을 검토합니다. 게시 기능은 없습니다.

## 현재 한계
- RSS 제목만 AI에 전달합니다. 원문 조사나 사실 검증은 아직 하지 않습니다.
- 원고는 AI가 생성한 **검증 전 초안**입니다. 사용자 승인과 출처 검증 없이는 발행하지 않습니다.
- 자동 일일 AI 생성은 아직 켜지 않았습니다. 무료 프로젝트 사용량과 품질을 검증한 다음 활성화합니다.
- 태블릿만으로도 브라우저에서 수동 실행 가능하지만, 24시간 보장되는 무인 생성은 아닙니다.
- GitHub Actions 무료 사용량, 워크플로 활성화 상태, 공급자 무료 API 정책이 바뀔 수 있습니다.
- 테스트는 외부 유료 호출 없는 모의 응답 기반입니다.
