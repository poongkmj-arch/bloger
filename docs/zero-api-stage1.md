# 추가 AI API 비용 없는 자동화 — 1단계

이 브랜치는 기존 Streamlit 앱을 변경하지 않고 독립적인 **RSS 주제 수집** 경로를 추가합니다.

## 현재 구현된 것
- GitHub Actions에서 매일 UTC 23:15(한국 08:15)에 공개 HTTPS RSS의 제목과 URL을 수집
- JSON 파일을 7일간 Actions artifact로 보관
- 로컬 Ollama가 실행 중인 컴퓨터에서는 선택적으로 최대 3개 검증 전 초안 생성
- 유료 OpenAI API 호출 없음, 자동 발행 없음, 무인 AI 생성 서버 없음

## 태블릿에서 설정
1. GitHub 저장소 Settings > Secrets and variables > Actions > Variables에서 `BLOG_RSS_URLS`를 등록합니다. 사용 권한을 확인한 실제 RSS HTTPS URL을 쉼표로 구분해 입력합니다.
2. Actions 탭에서 `Zero API topic collection` > Run workflow를 실행합니다.
3. 실행 결과의 `topic-candidates` artifact를 내려받아 확인합니다.
4. RSS URL이 없으면 빈 목록이 정상 출력됩니다. 예시·가짜 검색량을 생성하지 않습니다.

## 로컬 AI 테스트 (컴퓨터가 있을 때만)
Ollama를 실행하고 `ollama pull qwen3:4b`를 수행한 뒤:
```bash
BLOG_RSS_URLS=https://example.org/real-feed.xml python automation_stage1.py --generate
```
실제 URL로 교체해야 합니다. 로컬 모델 다운로드 및 실행에는 별도 컴퓨터 자원이 필요합니다.

## 제약과 다음 단계
- 갤럭시 태블릿만 사용하고 GPU가 없으며 PC도 켜두지 않는 경우, **무료로 항상 실행되는 로컬 AI는 존재하지 않습니다.** 지속적인 AI 생성에는 외부 상시 서버나 무료 할당량이 있는 서비스가 필요하며 한도·중단 가능성이 있습니다.
- GitHub 호스팅 Actions에서 모델을 내려받아 추론하는 방식은 시간/메모리/쿼터 문제로 이번 단계에 포함하지 않습니다.
- GitHub Actions 스케줄은 정시에 실행된다는 보장이 없으며, 비활성화 정책과 사용량 제한이 적용됩니다.
- 네이버·티스토리 자동 발행은 공식 지원 수단과 이용 정책을 확인한 뒤 별도 구현합니다. 기존 앱의 승인/수동 복사 기능은 유지됩니다.
- RSS 제목과 링크는 사실 검증이 아니며, 생성 초안은 사용자 승인 전 게시하면 안 됩니다.
- GitHub Actions 무료 할당량과 Codespaces 사용량은 별도 확인해야 합니다.
