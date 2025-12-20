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
8. 통계 및 오분류 케이스 출력

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
- **중요**: API 오류 발생 시 현재까지의 결과를 엑셀에 저장한 후 종료

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

### 현재 버전: 1.0
- 초기 구현 완료
- Qwen3, Databricks LLM 지원
- 병렬 처리 지원
- 로깅 시스템 구현
- 필터링 및 제한 기능 추가
- Databricks API 리스트 응답 형식 처리
- API 오류 시 즉시 종료 및 결과 저장
- argparse 기반 명령행 인터페이스
- 상세한 오류 메시지 및 디버그 모드

### 주요 개선 사항
1. **로깅 시스템**: LOG_LEVEL 환경 변수로 상세도 조절 가능
2. **오류 처리**: API 오류 시 구체적인 오류 메시지 제공
3. **필터링**: E열 기준 재처리 기능
4. **테스트 모드**: -n 옵션으로 소량 데이터 테스트 가능
5. **API 호환성**: Databricks 리스트 응답 형식 자동 처리
