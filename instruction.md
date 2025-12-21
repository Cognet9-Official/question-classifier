# 도메인 분류 어플리케이션 개발 명세서

## 1. 프로젝트 개요

엑셀 파일에서 질문(Question)을 읽어 Small Language Model(sLM)을 사용하여 자동으로 도메인을 분류하고, Ground Truth와 비교하여 성능을 평가하는 어플리케이션을 개발한다.

## 2. 기능 요구사항

### 2.1 핵심 기능
- 엑셀 파일에서 Question 데이터 읽기
- sLM을 활용한 도메인 자동 분류
- Ground Truth와 분류 결과 비교 및 성공 여부 판정
- 분류 의견 자동 생성
- 결과를 엑셀 파일로 출력

### 2.2 도메인 분류
- 도메인 카테고리는 환경 변수(.env) 파일에 정의 (개수는 프로젝트에 따라 변경 가능)
- sLM이 각 Question을 분석하여 가장 적합한 도메인 하나를 선택
- 분류가 모호한 경우 그 이유를 분류 의견에 명시

### 2.3 필터링 및 제한 기능
- E열(성공 여부)을 기준으로 필터링 가능 (all/O/X)
- 처리할 질문 개수 제한 가능 (테스트 목적)
- 필터링 옵션:
  - `all`: 모든 질문 처리 (기본값)
  - `O`: 성공(O)인 질문만 처리
  - `X`: 실패(X)인 질문만 재처리

## 3. 입출력 형식

### 3.1 입력 엑셀 파일 구조
| 열 | 컬럼명 | 설명 | 초기 상태 |
|----|--------|------|-----------|
| A | (Index/기타) | 행 번호 또는 ID | 있을 수 있음 |
| B | Question | 분류 대상 질문 | **필수 입력** |
| C | 도메인 Ground Truth | 정답 도메인 | **필수 입력** |
| D | LLM 도메인 분류 결과 | LLM이 분류한 도메인 | 비어있음 (프로그램이 채움) |
| E | 성공 여부 | Ground Truth와 일치 여부 | 비어있음 (프로그램이 채움) |
| F | 분류 의견 | LLM의 분류 근거 및 의견 | 비어있음 (프로그램이 채움) |
| G | 분류 의견 구분 | 의견 카테고리 분류 | 비어있음 (프로그램이 채움) |

### 3.2 출력 엑셀 파일 구조
입력 파일과 동일한 구조이며, D, E, F, G 열이 프로그램에 의해 채워진 상태

### 3.3 D, E, F, G 열 작성 규칙
- **D열 (LLM 도메인 분류 결과)**: sLM이 선택한 도메인명 (도메인 목록 중 1개)
- **E열 (성공 여부)**:
  - `O`: D열 값과 C열 값이 일치
  - `X`: D열 값과 C열 값이 불일치
- **F열 (분류 의견)**:
  - 분류 근거 및 이유
  - 모호한 경우: "도메인 분류 기준이 모호함", "질문이 명확하지 않음" 등
  - 명확한 경우: "키워드 기반 명확한 분류", "특정 도메인 특징이 뚜렷함" 등
  - 오분류 시: 가능한 원인 및 대안 도메인 제시
  - API 오류 시: 구체적인 오류 메시지 (예: "HTTP 401 오류", "API 호출 타임아웃")
- **G열 (분류 의견 구분)**:
  - `정확히 분류됨`: LLM 분류 결과와 Ground Truth가 일치하는 경우 (E열이 'O'인 경우 자동 설정)
  - `Ground Truth가 잘못됨`: 정답 도메인이 잘못 설정된 경우
  - `Question이 모호함`: 질문이 불명확하거나 여러 도메인에 해당될 수 있는 경우
  - `맞는 도메인이 없음`: 도메인 목록 중 적합한 도메인이 없는 경우
  - `기타의견`: 위 카테고리에 해당하지 않는 기타 의견

### 3.4 JSON 결과 파일 (LLM 분석용)
엑셀 파일과 함께 동일한 경로에 JSON 형식의 결과 파일도 자동 생성됨
- **파일명**: `result.json` (엑셀 파일이 `result.xlsx`인 경우)
- **목적**: LLM이 분류 성능을 분석하고 프롬프트를 개선하는 데 활용
- **형식**: JSON 배열
- **포함 데이터**:
  - `row`: 행 번호
  - `question`: 질문 내용
  - `ground_truth`: 정답 도메인
  - `classified_domain`: LLM이 분류한 도메인
  - `success`: 성공 여부 (O/X)
  - `opinion_category`: 의견 구분
- **제외 데이터**: `분류 의견` (opinion) - 상세한 텍스트 설명은 제외됨

**JSON 파일 예시**:
```json
[
  {
    "row": 2,
    "question": "보험금을 청구하려면 어떤 서류가 필요한가요?",
    "ground_truth": "보험금 보장",
    "classified_domain": "보험금 보장",
    "success": "O",
    "opinion_category": "정확히 분류됨"
  },
  {
    "row": 3,
    "question": "계약자 변경은 어떻게 하나요?",
    "ground_truth": "명의변경",
    "classified_domain": "계약정보",
    "success": "X",
    "opinion_category": "Question이 모호함"
  }
]
```

## 4. 기술 스택 및 환경 설정

### 4.1 프로그래밍 언어
- Python 3.x

### 4.2 사용 LLM 모델
선택 가능한 두 가지 LLM:

#### 옵션 1: Qwen3 (기본값)
- **모델명**: qwen3-30B-A3B-Instruct
- **배포 방식**: 온프레미스 서버
- **접속 정보**:
  - IP: 10.232.200.12
  - Port: 9996

#### 옵션 2: Databricks GPT-OSS
- **모델명**: databricks-gpt-oss-20b
- **배포 방식**: Databricks Serving Endpoint
- **접속 정보**:
  - URL: https://dbc-0866eb67-6331.cloud.databricks.com/serving-endpoints/databricks-gpt-oss-20b/invocations
  - 인증: Bearer Token

### 4.3 필수 라이브러리
- `openpyxl` 또는 `pandas`: 엑셀 파일 처리
- `python-dotenv`: 환경 변수 관리
- `requests`: HTTP API 호출
- LLM API 클라이언트 라이브러리 (모델에 따라)

### 4.4 환경 변수 (.env)
```
# 도메인 카테고리
DOMAINS=도메인1,도메인2,도메인3,...

# LLM 선택 (qwen3 또는 databricks)
LLM_PROVIDER=qwen3

# Qwen3 설정
QWEN3_HOST=10.232.200.12
QWEN3_PORT=9996
QWEN3_MODEL=qwen3-30b-a3b-instruct

# Databricks 설정
DATABRICKS_URL=https://dbc-0866eb67-6331.cloud.databricks.com/serving-endpoints/databricks-gpt-oss-20b/invocations
DATABRICKS_TOKEN=your_token_here
DATABRICKS_MODEL=databricks-gpt-oss-20b

# 공통 설정
LLM_TIMEOUT=30

# API 호출 대기 시간 (초)
# 각 API 호출 후 대기할 시간 (Rate Limiting 방지)
THINKING_TIME=3

# 병렬 처리 설정
MAX_CONCURRENT_REQUESTS=5

# 로그 설정
# LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL
# - DEBUG: 모든 로그 (API 요청/응답 본문, 스택 트레이스 포함)
# - INFO: 일반 정보 (기본값, 처리 진행 상황)
# - WARNING: 경고 메시지
# - ERROR: 오류 메시지만
# - CRITICAL: 치명적 오류만
LOG_LEVEL=INFO
```

## 5. 프로젝트 구조

```
domain-detector/
├── .env                    # 환경 변수 설정
├── requirements.txt        # Python 의존성
├── main.py                 # 메인 실행 파일
├── instruction.md          # 프로젝트 명세서
├── input/                  # 입력 파일 디렉토리
│   └── input.xlsx         # 기본 입력 파일
├── result/                 # 출력 파일 디렉토리
│   └── result.xlsx        # 기본 출력 파일
├── log/                    # 로그 파일 디렉토리 (자동 생성)
│   └── domain_classifier_YYYYMMDD_HHMMSS.log
└── src/                    # 소스 코드 디렉토리
    ├── __init__.py        # 패키지 초기화
    ├── excel_handler.py   # 엑셀 처리 모듈
    ├── llm_classifier.py  # LLM 분류 모듈
    └── evaluator.py       # 평가 모듈
```

## 6. 실행 방법

### 6.1 기본 실행
```bash
python main.py
```
- 입력: `input/input.xlsx`
- 출력: `result/result.xlsx`
- 처리 개수: 전체
- 필터: all (모든 질문)

### 6.2 명령행 옵션
```bash
python main.py [옵션]

옵션:
  -h, --help            도움말 표시
  -i, --input PATH      입력 파일 경로 (기본: input/input.xlsx)
  -o, --output PATH     출력 파일 경로 (기본: result/result.xlsx)
  -n, --limit NUMBER    처리할 질문 개수 제한 (기본: all)
  -f, --filter {all,O,X}  성공여부 필터 (기본: all)
```

### 6.3 실행 예제
```bash
# 도움말 보기
python main.py -h

# 전체 처리 (기본값)
python main.py

# 처음 10개만 테스트
python main.py -n 10

# 실패(X)한 것만 재처리
python main.py -f X

# 성공(O)한 것만 처리
python main.py -f O

# 실패 중 5개만 처리
python main.py -n 5 -f X

# 입력/출력 파일 지정
python main.py -i data/test.xlsx -o result/out.xlsx

# 복합 예제: 실패한 것 중 처음 3개만 처리하고 custom 경로로 저장
python main.py -f X -n 3 -o result/reprocess.xlsx
```

## 7. 구현 세부사항

### 7.1 데이터 처리 흐름
1. 로깅 시스템 초기화 (LOG_LEVEL 설정 적용)
2. 환경 변수(.env)에서 도메인 목록, LLM 설정, 병렬 처리 설정 로드
3. 명령행 인자 파싱 (입력/출력 파일, 필터, 개수 제한)
4. 입력 엑셀 파일 읽기:
   - B열(Question), C열(Ground Truth), E열(성공 여부) 읽기
   - 필터 옵션 적용 (all/O/X)
   - 개수 제한 적용
5. Connection Pool을 사용하여 병렬로 LLM API 호출:
   - 최대 동시 호출 수는 MAX_CONCURRENT_REQUESTS 환경 변수로 제어
   - ThreadPoolExecutor를 사용하여 동시에 여러 질문 처리
   - 각 스레드에서:
     - sLM에게 도메인 분류 요청
     - API 응답 처리 (Databricks의 경우 리스트 형식 처리)
     - **THINKING_TIME 만큼 대기 (Rate Limiting 방지)**
     - 결과 수집
   - **API 오류 발생 시 즉시 중단하고 현재까지 결과 저장**
6. 모든 분류 결과를 엑셀에 작성:
   - D열에 분류 결과 작성
   - E열에 성공 여부 판정 (O/X)
   - F열에 분류 의견 작성 (API 오류 시 상세 오류 메시지 포함)
   - G열에 분류 의견 구분 작성 (성공 시 자동으로 "정확히 분류됨")
7. 결과를 출력 엑셀 파일로 저장
8. **JSON 결과 파일 생성 (LLM 분석용)**:
   - 엑셀 파일과 동일한 경로에 JSON 파일 자동 생성
   - 분류 의견(opinion)을 제외한 핵심 데이터만 포함
   - 향후 LLM이 성능 분석 및 프롬프트 개선에 활용
9. 통계 및 오분류 케이스 출력

### 7.2 LLM 프롬프트 설계
프롬프트에 포함되어야 할 정보:
- 도메인 목록 (환경 변수에서 로드)
- 분류할 Question
- 분류 근거 요청
- 단일 도메인 선택 지시
- 의견 구분 카테고리 설명
- 응답 형식 지정 (도메인:, 이유:, 의견구분:)

### 7.3 에러 처리

#### 7.3.1 파일 관련 오류
- 파일이 존재하지 않는 경우: 명확한 오류 메시지 출력 후 종료
- 엑셀 형식이 올바르지 않은 경우: 오류 로그 기록 후 종료
- 도메인 목록이 로드되지 않는 경우: 오류 로그 기록 후 종료

#### 7.3.2 LLM API 오류
- **HTTP 오류 (4xx, 5xx)**: 상태 코드와 응답 본문 로그 기록, 프로그램 즉시 종료
- **타임아웃**: 설정된 timeout 값과 함께 로그 기록, 프로그램 즉시 종료
- **연결 오류**: 엔드포인트 정보와 함께 로그 기록, 프로그램 즉시 종료
- **응답 형식 오류**: 예상치 못한 응답 형식 로그 기록, 프로그램 즉시 종료
- **빈 응답 처리**:
  - Databricks API가 빈 리스트 `[]`를 반환하는 경우 "빈 응답 리스트" 오류로 처리
  - API가 빈 문자열 또는 공백만 반환하는 경우 "빈 응답 내용" 오류로 처리
- **중요**: API 오류 발생 시:
  - 실패한 행을 결과에 "API오류"로 기록
  - 현재까지의 결과를 엑셀 및 JSON 파일에 저장
  - 남은 작업을 취소하고 프로그램 종료

#### 7.3.3 Databricks API 특수 처리
- Databricks API는 `content` 필드가 리스트로 반환될 수 있음
- 리스트 내 각 요소가 딕셔너리인 경우 `text` 필드 추출
- 리스트 내 각 요소가 문자열인 경우 직접 사용
- 모든 텍스트를 결합하여 최종 응답 생성

### 7.4 로깅 시스템

#### 7.4.1 로그 레벨
- **DEBUG**: 모든 상세 로그 (API 요청/응답 본문, 스택 트레이스 포함)
- **INFO**: 일반 정보 (기본값, 처리 진행 상황, 통계)
- **WARNING**: 경고 메시지
- **ERROR**: 오류 메시지만
- **CRITICAL**: 치명적 오류만

#### 7.4.2 로그 출력
- 콘솔 + 파일 동시 출력
- 로그 파일명: `log/domain_classifier_YYYYMMDD_HHMMSS.log`
- 타임스탬프 자동 포함
- UTF-8 인코딩

#### 7.4.3 로그 내용
- 프로그램 시작/종료 시간
- 설정 정보 (LLM provider, 도메인 개수, 병렬 처리 수 등)
- 처리 중인 행 번호 및 질문 (INFO 레벨)
- 분류 결과 및 성공 여부 (INFO 레벨)
- API 요청/응답 상세 (DEBUG 레벨)
- 오류 상세 정보 (ERROR 레벨)
- 스택 트레이스 (DEBUG 레벨)
- 최종 통계 (정확도, 총 처리 건수, 성공/실패 카운트)
- 오분류 케이스 (최대 10건)

### 7.5 병렬 처리 구현
- **Connection Pool**: requests.Session 객체를 재사용하여 연결 풀 활용
- **HTTPAdapter**: Retry 전략 설정 (최대 10회, backoff_factor=2)
  - Retry 대상: HTTP 429, 500, 502, 503, 504
  - pool_connections=10, pool_maxsize=10
- **ThreadPoolExecutor**: concurrent.futures 모듈의 ThreadPoolExecutor 사용
- **동시성 제어**: MAX_CONCURRENT_REQUESTS 환경 변수로 최대 워커 수 설정
- **스레드 안전성**: threading.Lock을 사용한 동기화 (로그 출력, 결과 수집)
- **성능 향상**: 순차 처리 대비 N배 빠른 처리 속도 (N = 동시 요청 수)
- **에러 처리**:
  - **LLM API 오류 시**: 즉시 프로그램 중단, 현재까지 결과 저장
  - **기타 예외**: 해당 질문만 "처리오류"로 기록하고 계속 진행

## 8. 추가 고려사항

### 8.1 성능 최적화
- Connection Pool을 통한 병렬 API 호출로 처리 속도 향상
- 최대 동시 요청 수 조정으로 서버 부하 제어
  - 권장: 5~10 (서버 성능에 따라 조정)
  - 테스트: 1 (순차 처리)
- **THINKING_TIME 설정으로 Rate Limiting 방지**
  - API 호출 후 지정된 시간만큼 대기
  - 기본값: 3초 (서버 정책에 따라 조정)
  - 0으로 설정 시 대기하지 않음
- Retry 전략을 통한 일시적 오류 자동 복구
- ThreadPoolExecutor를 통한 I/O 바운드 작업 최적화
- Session 재사용으로 연결 오버헤드 감소

### 8.2 확장 가능성
- 다양한 LLM 모델 지원 (현재: Qwen3, Databricks)
- 도메인 개수 변경 가능 (환경 변수로 관리)
- 추가 평가 지표 확장 가능
- 필터링 옵션 확장 가능 (현재: all/O/X)
- 로그 레벨 유연한 설정 (DEBUG/INFO/WARNING/ERROR/CRITICAL)

### 8.3 운영 가이드

#### 8.3.1 일반 사용
```bash
# 전체 데이터 처리
python main.py

# 로그는 log/domain_classifier_YYYYMMDD_HHMMSS.log에 저장됨
```

#### 8.3.2 테스트 및 디버깅
```bash
# 소량 데이터로 테스트
python main.py -n 5

# 실패한 것만 재처리
python main.py -f X

# 디버그 모드 (상세 로그)
# .env에서 LOG_LEVEL=DEBUG로 설정 후 실행
python main.py -n 5
```

#### 8.3.3 성능 튜닝
```bash
# .env 파일에서 병렬 처리 수 조정
MAX_CONCURRENT_REQUESTS=10  # 서버 성능이 좋은 경우
MAX_CONCURRENT_REQUESTS=5   # 기본값
MAX_CONCURRENT_REQUESTS=1   # 순차 처리 (디버깅용)

# API 호출 대기 시간 조정
THINKING_TIME=0   # 대기하지 않음 (최고 속도, Rate Limiting 위험)
THINKING_TIME=3   # 기본값 (권장)
THINKING_TIME=5   # 보수적 설정 (Rate Limiting 엄격한 경우)
THINKING_TIME=10  # 매우 보수적 설정
```

#### 8.3.4 오류 대응
- API 오류 발생 시: 로그 파일에서 상세 오류 확인
- DEBUG 모드로 재실행하여 API 요청/응답 확인
- 타임아웃이 빈번한 경우: LLM_TIMEOUT 값 증가
- 연결 오류: 네트워크 및 엔드포인트 확인

### 8.4 제한사항
- Excel 파일 형식: .xlsx만 지원
- 입력 파일 구조: B/C/E 열 고정 (변경 불가)
- LLM API: OpenAI 호환 형식 (Qwen3, Databricks 검증됨)
- 병렬 처리: I/O 바운드 작업에 최적화 (CPU 바운드 작업에는 부적합)

## 9. 버전 정보 및 변경 이력

### 현재 버전: 1.1
- 초기 구현 완료
- Qwen3, Databricks LLM 지원
- 병렬 처리 지원
- 로깅 시스템 구현
- 필터링 및 제한 기능 추가
- Databricks API 리스트 응답 형식 처리
- API 오류 시 즉시 종료 및 결과 저장
- argparse 기반 명령행 인터페이스
- 상세한 오류 메시지 및 디버그 모드
- **JSON 결과 파일 자동 생성 (LLM 분석용)**
- **빈 응답 처리 로직 개선**
- **API 오류 시 실패 행도 결과에 기록**

### 주요 개선 사항
1. **로깅 시스템**: LOG_LEVEL 환경 변수로 상세도 조절 가능
2. **오류 처리**: API 오류 시 구체적인 오류 메시지 제공
3. **필터링**: E열 기준 재처리 기능
4. **테스트 모드**: -n 옵션으로 소량 데이터 테스트 가능
5. **API 호환성**: Databricks 리스트 응답 형식 자동 처리
6. **JSON 출력**: 엑셀과 함께 JSON 파일 자동 생성 (분류 의견 제외)
7. **빈 응답 감지**: 빈 리스트, 빈 문자열 응답 시 명확한 오류 처리
8. **결과 완전성**: API 오류 발생 시에도 실패한 행을 결과에 기록

### 버전 1.1 변경사항 (2025-12-20)
- **JSON 결과 파일 생성**:
  - Excel 파일과 동일한 경로에 JSON 파일 자동 생성
  - LLM 분석 및 프롬프트 개선에 활용할 수 있도록 핵심 데이터만 포함
  - 분류 의견(opinion)은 제외하여 파일 크기 최소화
- **빈 응답 처리 개선**:
  - Databricks API가 빈 리스트를 반환하는 경우 감지 및 오류 처리
  - API가 빈 문자열 또는 공백만 반환하는 경우 감지 및 오류 처리
  - `if response:` 조건을 `if response is not None:`으로 변경하여 falsy 값 처리
- **API 오류 처리 개선**:
  - 오류 발생 시 실패한 행을 "API오류"로 결과에 추가
  - 남은 작업을 취소하고 현재까지 결과를 엑셀 및 JSON으로 저장
  - 병렬 처리 중 오류 발생 시에도 이미 완료된 결과 보존

## 10. 프롬프트 개선 액션 플랜

### 10.1 현재 상태 분석 (2025-12-20 기준)

**현재 정확도**: 48% (334/694)

**주요 문제점**:
1. **도메인 정의 부족**: 도메인 이름만 나열되어 있어 LLM이 각 도메인의 의미와 경계를 이해하지 못함
2. **주요 오분류 패턴**:
   - 질병/수술 관련 질문을 "헬스케어서비스"로 오분류 (실제: "보험금 보장")
   - 질병 분류 코드(C50, D37 등)를 "헬스케어서비스"로 오분류 (실제: "보험금 보장")
   - 수익자/지급 절차에서 "보험금 보장" vs "제지급" vs "채권압류 질권설정" 혼동
3. **컨텍스트 이해 부족**: Few-shot 예제가 없어 질문의 의도(보험금 지급 여부 vs 헬스케어 서비스)를 파악하지 못함

**주요 오분류 사례**:
- "치루 절제술은 몇 종 수술인가요?" → LLM: 헬스케어서비스 ❌ | 정답: 보험금 보장 ✅
- "A형 간염은 질병인가요?" → LLM: 헬스케어서비스 ❌ | 정답: 보험금 보장 ✅
- "C50 코드는 무슨 질병?" → LLM: 헬스케어서비스 ❌ | 정답: 보험금 보장 ✅
- "뇌졸증이 뭐지?" → LLM: 헬스케어서비스 ❌ | 정답: 보험금 보장 ✅

### 10.2 개선 로드맵

| 단계 | 개선 항목 | 예상 정확도 | 개선 폭 | 우선순위 |
|-----|----------|-----------|--------|---------|
| 현재 | 기본 프롬프트 | 48% | - | - |
| 1단계 | 도메인 정의 명확화 | 63~68% | +15~20% | ⭐⭐⭐ 최우선 |
| 2단계 | Few-shot 예제 추가 | 73~83% | +10~15% | ⭐⭐⭐ 높음 |
| 3단계 | 판단 기준 명시 | 78~93% | +5~10% | ⭐⭐ 중간 |
| 4단계 | Chain-of-Thought 유도 | 81~98% | +3~5% | ⭐ 낮음 |
| 5단계 | 도메인 키워드 매핑 | 84~103% | +3~5% | ⭐ 낮음 |

**목표 정확도**: 75~85% (100%는 ground truth 오류 등으로 현실적으로 불가능)

### 10.3 1단계: 도메인 정의 명확화 ⭐⭐⭐

**목표**: 각 도메인의 의미, 범위, 경계를 명확히 정의하여 LLM이 도메인을 올바르게 이해하도록 함

**액션 아이템**:

#### A. 도메인 정의 작성 (도메인 전문가 필요)

21개 도메인 각각에 대해 다음 정보 작성:

1. **도메인 설명**: 해당 도메인이 다루는 주제 범위 (1-2문장)
2. **포함 사례**: 이 도메인에 속하는 질문 유형 (구체적으로)
3. **제외 사례**: 혼동되기 쉽지만 이 도메인이 아닌 경우
4. **대표 예시**: 실제 질문 예시 2-3개

**도메인 정의 템플릿**:
```
도메인: [도메인명]
설명: [1-2문장으로 범위 설명]
포함: [이 도메인에 속하는 질문 유형]
제외: [비슷하지만 다른 도메인에 속하는 경우]
예시:
  - "[예시 질문 1]"
  - "[예시 질문 2]"
  - "[예시 질문 3]"
```

**우선 정의가 필요한 도메인** (혼동이 많은 순서):
1. **보험금 보장** ↔ **헬스케어서비스** (가장 많이 혼동)
   - 보험금 보장: 보험금 지급 대상 여부, 보장되는 질병/수술/상해, 질병 코드, 보장 범위
   - 헬스케어서비스: 건강 관리 부가 서비스, 건강검진, 건강 상담, 운동/영양 프로그램

2. **보험금 보장** ↔ **제지급**
   - 보험금 보장: "무엇이" 보장되는가? (대상)
   - 제지급: "어떻게" 받는가? (절차, 서류, 수익자)

3. **제지급** ↔ **채권압류 질권설정**
   - 제지급: 일반적인 보험금 지급 절차
   - 채권압류 질권설정: 법적 제한이 있는 경우의 지급

4. **계약정보** ↔ **명의변경**
   - 계약정보: 조회, 확인
   - 명의변경: 변경, 정정

5. 나머지 17개 도메인

**작업 산출물**:
- `domain_definitions.md`: 21개 도메인 정의 문서
- 프롬프트 템플릿에 삽입할 형식으로 정리

**예상 소요 시간**: 4-8시간 (도메인 전문가 작업)

#### B. 프롬프트 수정

`src/llm_classifier.py`의 `_build_prompt()` 메서드 수정:

**현재**:
```python
도메인 목록: {domains_str}
```

**개선**:
```python
도메인별 정의:

1. 보험금 보장
   설명: 보험금 지급 대상 여부, 보장되는 질병/수술/상해, 질병 분류 코드, 보장 범위 관련 질문
   포함: 질병명, 수술명, 진단코드(C50, D37 등), ~종 수술, 보장 여부, 급여/비급여
   제외: 건강 관리 서비스(헬스케어), 지급 절차/서류(제지급)
   예시:
     - "백내장 수술은 보장되나요?"
     - "C50 코드는 무슨 질병인가요?"
     - "뇌졸증은 몇 종 질병인가요?"

2. 헬스케어서비스
   설명: 보험 상품과 별개의 건강 관리 부가 서비스 관련 질문
   포함: 건강검진, 건강 상담, 운동 프로그램, 영양 관리, 헬스케어 앱
   제외: 보험금 지급 대상 질병/수술(보험금 보장)
   예시:
     - "건강검진 예약하는 방법은?"
     - "헬스케어 앱 사용법 알려주세요"
     - "운동 처방 프로그램 신청하고 싶어요"

3. 제지급
   설명: 보험금 지급 절차, 수익자 확인, 지급 방법, 필요 서류 관련 질문
   포함: 청구 방법, 필요 서류, 수익자, 지급 계좌, 신청 절차
   제외: 무엇이 보장되는가(보험금 보장), 법적 제한(채권압류 질권설정)
   예시:
     - "보험금 청구 시 필요한 서류는?"
     - "미성년자 수익자 통장으로 입금 가능한가요?"
     - "보험금 지급 절차를 알려주세요"

... (21개 도메인 모두)
```

**예상 효과**: 정확도 +15~20%

### 10.4 2단계: Few-shot 예제 추가 ⭐⭐⭐

**목표**: 실제 성공 사례를 통해 LLM이 도메인별 질문 유형을 학습하도록 함

**액션 아이템**:

#### A. 성공 사례 수집

각 도메인별로 **실제 정확히 분류된 사례** 2-3개 수집:

1. JSON 결과 파일에서 `success: "O"`인 항목 추출
2. 도메인별로 그룹화
3. 각 도메인당 대표성 있는 2-3개 선택
   - 명확한 사례
   - 다양한 질문 패턴 포함
   - 짧고 이해하기 쉬운 질문 우선

**작업 방법**:
```bash
# JSON 파일에서 성공 사례 추출
jq '.[] | select(.success == "O") | {domain: .classified_domain, question: .question}' result.json | less

# 도메인별로 그룹화하여 분석
jq 'group_by(.classified_domain) | map({domain: .[0].classified_domain, count: length})' result.json
```

**작업 산출물**:
- `few_shot_examples.md`: 도메인별 성공 사례 모음 (21개 도메인 × 2-3개 = 42-63개 예시)

**예상 소요 시간**: 2-3시간

#### B. 프롬프트에 Few-shot 예제 추가

`_build_prompt()` 메서드에 예제 섹션 추가:

```python
분류 예시:

[예시 1 - 보험금 보장]
질문: "백내장 수술은 보장되나요?"
도메인: 보험금 보장
이유: 수술의 보험금 지급 대상 여부를 묻는 질문

[예시 2 - 헬스케어서비스]
질문: "건강검진 예약하는 방법은?"
도메인: 헬스케어서비스
이유: 건강 관리 부가 서비스 이용 방법 문의

[예시 3 - 제지급]
질문: "보험금 청구 시 필요한 서류는?"
도메인: 제지급
이유: 보험금 지급 절차 및 필요 서류 문의

... (총 10-15개, 주요 도메인 위주)
```

**주의사항**:
- 프롬프트 길이 제한 고려 (토큰 수)
- 너무 많으면 비용 증가 및 성능 저하 가능
- 10-15개가 적정 (주요 혼동 도메인 위주)

**예상 효과**: 정확도 +10~15%

### 10.5 3단계: 판단 기준 명시 ⭐⭐

**목표**: LLM이 질문의 의도를 파악하고 도메인을 선택하는 명확한 기준 제공

**액션 아이템**:

#### A. 판단 기준 문서화

다음 내용을 프롬프트에 추가:

```python
분류 기준 가이드:

1. 질문의 핵심 의도 파악
   - 단순히 키워드만 보지 말고 질문자가 무엇을 알고 싶어하는지 파악
   - "~이 뭔가요?" 형태의 질문:
     * 의료 용어 → 대부분 "보험금 보장" (보험 지급 대상인지 확인)
     * 절차/서류 용어 → "제지급", "명의변경" 등 해당 업무 도메인
     * 보험 용어 → "계약정보", "연금" 등 해당 상품 도메인

2. 도메인 간 우선순위 (혼동 방지)
   - 질병, 수술, 진단코드(C50, D37 등) 언급 → "보험금 보장" (헬스케어 아님!)
   - 보험금 "받는" 방법, 서류, 수익자 → "제지급"
   - 계약자/피보험자 "변경" → "명의변경"
   - 계약 "조회", "확인" → "계약정보"
   - 법원, 압류, 질권 언급 → "채권압류 질권설정"

3. 중요한 키워드 힌트
   - "보장", "지급대상", "~종" → 보험금 보장
   - "청구", "서류", "신청" → 제지급
   - "검진", "상담", "프로그램" → 헬스케어서비스
   - "변경", "정정" → 명의변경
   - "해지", "해약" → 계약해지

4. 애매한 경우 처리
   - 두 도메인 사이에서 고민될 때는 질문의 최종 목적에 집중
   - 보험금과 관련된 모든 질문은 "보험금 보장" 또는 "제지급" 우선 고려
```

**예상 효과**: 정확도 +5~10%

### 10.6 4단계: Chain-of-Thought 유도 ⭐

**목표**: LLM이 단계별 추론 과정을 거치도록 하여 정확도 향상

**액션 아이템**:

응답 형식을 단계별 사고 과정으로 변경:

```python
응답 형식:
[1단계] 핵심 키워드: [질문에서 중요한 단어들]
[2단계] 질문 의도: [질문자가 알고 싶은 것]
[3단계] 후보 도메인: [가능한 도메인 2-3개와 각각의 이유]
[4단계] 최종 선택: [선택한 도메인과 선택 이유]

도메인: [최종 선택한 도메인]
이유: [1-4단계 사고 과정 요약]
의견구분: [카테고리]
```

**주의사항**:
- 응답 파싱 로직 수정 필요 (`_parse_response()` 메서드)
- 응답이 길어져 API 비용 증가 가능
- 토큰 제한 확인 필요

**예상 효과**: 정확도 +3~5%

### 10.7 5단계: 도메인 키워드 매핑 ⭐

**목표**: 각 도메인의 전형적인 키워드를 명시하여 분류 정확도 향상

**액션 아이템**:

#### A. 키워드 수집

각 도메인별로 자주 등장하는 키워드 추출:

1. JSON 결과에서 성공 사례의 질문 텍스트 분석
2. 도메인별 공통 키워드 추출
3. TF-IDF 또는 빈도 분석 활용

**작업 방법**:
```python
# 간단한 키워드 분석 스크립트
import json
from collections import defaultdict

# 도메인별 키워드 빈도
domain_keywords = defaultdict(lambda: defaultdict(int))

with open('result.json') as f:
    data = json.load(f)
    for item in data:
        if item['success'] == 'O':
            domain = item['classified_domain']
            question = item['question']
            # 간단한 토큰화 (실제로는 더 정교한 방법 사용)
            for word in question.split():
                domain_keywords[domain][word] += 1

# 도메인별 상위 키워드 출력
for domain in domain_keywords:
    print(f"\n{domain}:")
    top_keywords = sorted(domain_keywords[domain].items(),
                         key=lambda x: x[1], reverse=True)[:20]
    print(", ".join([k for k, v in top_keywords]))
```

#### B. 프롬프트에 키워드 추가

```python
도메인별 핵심 키워드:

1. 보험금 보장: 보장, 지급대상, 질병, 수술, 상해, 진단코드, ~종, 암, 뇌졸중, 수술명, C코드, D코드, 급여, 비급여
2. 제지급: 청구, 서류, 수익자, 지급절차, 입금, 계좌, 신청, 제출, 필요서류, 지급, 받기
3. 계약해지: 해지, 해약, 중도해지, 위약금, 환급금, 해지환급금, 취소
4. 명의변경: 변경, 정정, 명의, 계약자변경, 양도, 승계
5. 헬스케어서비스: 건강검진, 검진, 상담, 헬스케어, 앱, 프로그램, 운동, 영양
... (21개 도메인 모두)

주의: 키워드는 참고용이며, 반드시 질문의 의도와 문맥을 종합적으로 고려해야 합니다.
```

**예상 효과**: 정확도 +3~5%

### 10.8 실행 계획

#### Phase 1: 기초 개선 (목표: 75% 정확도)
**우선순위**: 최우선
**예상 기간**: 1-2주

1. **1단계 완료**: 21개 도메인 정의 작성
   - 담당: 도메인 전문가 (보험 업무 담당자)
   - 산출물: `domain_definitions.md`
   - 소요 시간: 4-8시간

2. **프롬프트 수정**: 도메인 정의 적용
   - 담당: 개발자
   - 파일: `src/llm_classifier.py`
   - 소요 시간: 1-2시간

3. **테스트 실행**: 소량 데이터로 테스트
   ```bash
   python main.py -n 100
   ```

4. **결과 분석**: JSON 파일로 정확도 확인

5. **전체 실행**: 전체 데이터셋 재실행
   ```bash
   python main.py
   ```

#### Phase 2: 추가 개선 (목표: 80% 정확도)
**우선순위**: 높음
**예상 기간**: 1주

1. **2단계 완료**: Few-shot 예제 수집 및 추가
   - 성공 사례에서 대표 예시 선정
   - 프롬프트에 10-15개 예제 추가

2. **테스트 및 평가**

#### Phase 3: 고도화 (목표: 85% 정확도)
**우선순위**: 중간
**예상 기간**: 1주

1. **3단계 완료**: 판단 기준 명시
2. **선택적 4-5단계**: 필요시 추가 개선

### 10.9 평가 및 모니터링

#### A. 평가 지표

각 단계별 개선 후 다음 지표 측정:

1. **전체 정확도**: `성공 건수 / 전체 건수`
2. **도메인별 정확도**: 각 도메인의 Precision, Recall, F1-score
3. **혼동 행렬**: 어떤 도메인 쌍이 자주 혼동되는지
4. **의견 구분 분포**: Ground Truth 오류, Question 모호함 등의 비율

#### B. 분석 스크립트

프롬프트 개선 효과를 측정하는 스크립트 작성:

```python
# analyze_results.py
import json
from collections import defaultdict

def analyze_json_results(json_path):
    with open(json_path) as f:
        data = json.load(f)

    # 전체 정확도
    total = len(data)
    success = sum(1 for item in data if item['success'] == 'O')
    accuracy = success / total * 100

    # 도메인별 통계
    domain_stats = defaultdict(lambda: {'total': 0, 'correct': 0})
    for item in data:
        gt = item['ground_truth']
        pred = item['classified_domain']
        domain_stats[gt]['total'] += 1
        if item['success'] == 'O':
            domain_stats[gt]['correct'] += 1

    # 혼동 행렬
    confusion = defaultdict(lambda: defaultdict(int))
    for item in data:
        if item['success'] == 'X':
            confusion[item['ground_truth']][item['classified_domain']] += 1

    # 출력
    print(f"전체 정확도: {accuracy:.2f}% ({success}/{total})")
    print("\n도메인별 정확도:")
    for domain in sorted(domain_stats.keys()):
        stats = domain_stats[domain]
        dom_acc = stats['correct'] / stats['total'] * 100
        print(f"  {domain}: {dom_acc:.2f}% ({stats['correct']}/{stats['total']})")

    print("\n주요 혼동 패턴 (Top 10):")
    all_confusions = [(gt, pred, count)
                     for gt, preds in confusion.items()
                     for pred, count in preds.items()]
    all_confusions.sort(key=lambda x: x[2], reverse=True)
    for gt, pred, count in all_confusions[:10]:
        print(f"  {gt} → {pred}: {count}건")

if __name__ == '__main__':
    analyze_json_results('result/result.json')
```

사용법:
```bash
# 개선 전
python main.py
python analyze_results.py

# 개선 후
python main.py
python analyze_results.py

# 결과 비교
```

#### C. 지속적 개선

1. **주기적 재평가**: 매월 또는 분기별로 정확도 측정
2. **새로운 오분류 패턴 분석**: JSON 결과에서 실패 사례 분석
3. **프롬프트 업데이트**: 새로운 패턴 발견 시 도메인 정의 및 예제 보강
4. **Ground Truth 검증**: "Ground Truth가 잘못됨" 의견이 많은 경우 정답 재검토

### 10.10 참고 자료

**프롬프트 엔지니어링 베스트 프랙티스**:
- Few-shot Learning: 예제를 통한 학습
- Chain-of-Thought: 단계별 추론 유도
- Role Prompting: "당신은 보험 도메인 분류 전문가입니다"
- Constraint Specification: 명확한 제약 조건 제시

**관련 파일**:
- `src/llm_classifier.py`: 프롬프트 코드 위치 (84-118줄)
- `result/result.json`: 평가 데이터
- `.env`: LLM 모델 설정

**다음 단계**:
1. 도메인 전문가와 협업하여 `domain_definitions.md` 작성
2. 1단계 프롬프트 개선 적용
3. 테스트 실행 및 효과 측정
4. 결과에 따라 2-5단계 순차 진행
