# 한 번 연결하고 버튼으로 쓰기

## 실제 분석을 위한 최초 설정

API 키는 채팅이나 저장소 파일에 붙여넣지 마세요.
GitHub **Settings → Secrets and variables → Codespaces → New repository secret**에서 다음 값을 등록합니다.
계정/플랜에 따라 개인 설정의 [Codespaces secrets](https://github.com/settings/codespaces)에서
이 저장소에 접근을 허용하는 방식으로 설정할 수도 있습니다.

| 이름 | 값 |
| --- | --- |
| NAVER_SEARCHAD_API_KEY | 네이버 검색광고 API 라이선스 키 |
| NAVER_SEARCHAD_SECRET_KEY | 네이버 검색광고 API 비밀 키 |
| NAVER_SEARCHAD_CUSTOMER_ID | 검색광고 고객 ID |
| NAVER_DATALAB_CLIENT_ID | 데이터랩 검색어 트렌드 권한이 있는 앱 Client ID |
| NAVER_DATALAB_CLIENT_SECRET | 같은 앱의 Client Secret |
| OPENAI_API_KEY | 검색 도구를 사용할 수 있는 OpenAI 프로젝트 키 |
| NAVER_TERMS_REVIEWED | 공식 API 이용 자격·약관·계정 권한을 확인한 뒤 true |
| ALLOW_PAID_GENERATION | 유료 AI 사용을 허용하기로 결정한 뒤 true |

Codespaces secret은 Actions secret과 별개입니다. 예약 작업으로 옮길 때는 GitHub Actions Secrets를 사용해야 합니다.
설정을 변경하면 Codespace를 중지했다가 다시 시작합니다.
“연결 설정과 사용량”을 열면 값 자체를 노출하지 않고 준비 여부를 보여줍니다.
그곳에서 **유료 AI 조사·원고 생성에 동의합니다**를 체크한 뒤 실행하세요.
현재 앱은 모델 gpt-4.1-mini, Responses API의 web_search 및 JSON schema를 사용합니다.
해당 계정의 모델·도구 접근 권한과 현재 요금은 활성화 전에 확인해야 합니다.

공식 참고:
- [네이버 검색광고 API](https://naver.github.io/searchad-apidoc/)
- [검색광고 공식 Python 인증 예제](https://github.com/naver/searchad-apidoc/tree/master/python-sample)
- [네이버 데이터랩 검색어 트렌드 API](https://developers.naver.com/docs/serviceapi/datalab/search/search.md)
- [OpenAI Responses](https://platform.openai.com/docs/api-reference/responses)
- [웹 검색](https://platform.openai.com/docs/guides/tools-web-search)
- [OpenAI 요금](https://openai.com/api/pricing/)

공식 인증 예제를 참고해 adapter를 작성했지만 실제 계정으로 인증·이용 자격을 확인한 것은 아닙니다.
약관 확인 설정은 이를 자동으로 검증하는 기능이 아닌 운영자의 명시적 확인입니다.

## 실행 후 보이는 결과

관심 분야는 생활 금융·경제 이해·회계 공부입니다. 기본 개념에 가까운 분야별 seed 5개를 사용합니다.
네이버 연관 키워드 중 seed를 포함하는 후보를 추려 월 검색량 상위 5개까지 분석합니다.
이 범위는 임의의 전체 시장 조사나 블로그 검색 결과 상위 노출 분석을 의미하지 않습니다.

최근 12개 완료 월의 데이터랩 상대 지수를 보관하며 변동계수로 지속성 점수를 계산합니다.
지속성 = 100 × (1 - min(1, 표준편차/평균)), 평균 0이면 0점입니다.
검색량 30%·광고 경쟁 기회 25%·수익성 20%·지속성 15%·작성 용이성 10%를 적용합니다.
광고 경쟁 상/중/하는 85/50/15로 변환한 편집상 대리지표이며 콘텐츠 경쟁 실측값이 아닙니다.
수익성 50점, 작성 용이성 70점은 현재 고정 추정값으로 모든 후보에 동일하게 적용됩니다.
'<10' 검색량은 0이라는 하한으로 정렬하되 원본 구간값을 보관하고 정확한 수치로 표시하지 않습니다.

1위 후보 중 이미 원고가 있는 키워드는 제외합니다. 후보가 없거나 12개월 자료가 부족하면 중단합니다.
선정 후 웹 검색 조사 → 출처 URL 확보 → 조사 내용을 근거로 구조화된 원고 생성의 두 AI 호출을 합니다.
출처 없는 결과, 빈칸/서식 코드가 남은 본문, 짧은 원고, 지나치게 비슷한 두 본문은 거절합니다.
AI가 작성한 발행일과 주장 자체는 사람의 마지막 검증이 필요합니다.
웹 검색 결과에 URL이 있다는 사실이 그 원고의 모든 주장을 증명하는 것은 아닙니다.
뉴스 관련성이 없으면 시의성을 꾸며내지 않고 상시형 글로 기획하도록 지시합니다.

## 원고와 상태

새 화면에서는 평문 본문을 읽고 승인 또는 보류합니다.
기존 Markdown 템플릿은 삭제하지 않고 기존 편집기에 남습니다.
검토 확인은 기존 출처·주장·독창성 체크를 하나의 명시적 확인으로 묶었습니다.
로컬 운영자라는 검토 기록을 남기며 인증 서명을 의미하지 않습니다.

승인 이후에는 제목·본문을 따로 복사할 수 있고 본문 끝에 참고 자료 URL과 발행일을 포함합니다.
클립보드 차단 시 텍스트 선택 복사와 TXT 다운로드로 대체합니다.
승인 후 “다시 수정하기”를 누르면 승인과 검토 체크가 무효화됩니다.
보류한 글은 보류함에서 다시 검토할 수 있습니다.
자동 게시, 블로그 계정 로그인, API를 통한 발행은 구현하지 않습니다.

## 실패·예산·중복 처리

writing_jobs 테이블에 한국 시간 날짜·분야 고유키, 진행 상태, 추정 비용 예약, 성공 결과를 저장합니다.
예약을 먼저 트랜잭션으로 기록해 병렬 클릭과 프로세스 재시작이 예산을 우회하지 못하게 합니다.
동일 날짜/분야에서 실패하면 자동 재시도하지 않습니다. 다음 날 또는 다른 분야에서 새 작업을 시작할 수 있습니다.
실패 상태의 예산도 반환하지 않습니다. 공급자에서 이미 청구했는지 알 수 없기 때문입니다.
예상 비용은 회당 USD 0.50의 고정 보수적 계획값입니다. 실제 토큰 사용량은 성공 작업 결과에 기록합니다.
실제 비용 정산·실제 청구액의 강제 상한은 아직 구현하지 않았습니다.

## 편의 기능과 남은 배포 단계

새 Codespace는 시작 시 Streamlit을 자동 실행합니다. 블로그 발행이나 AI 호출은 자동 실행하지 않습니다.
기존 Codespace는 브랜치 업데이트 후 컨테이너 재빌드가 필요할 수 있습니다.
공개 링크로 언제든 접속하는 서비스는 OIDC와 클라우드 DB 연결 후 별도 배포해야 합니다.
현재는 GitHub 로그인으로 보호되는 비공개 Codespaces에서 사용합니다.
