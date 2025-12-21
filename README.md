# 도메인 분류 어플리케이션

엑셀 파일의 질문을 읽어 LLM(qwen3-30B-A3B-Instruct)을 사용하여 자동으로 도메인을 분류하고, Ground Truth와 비교하여 성능을 평가하는 어플리케이션입니다.

## 설치

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 열어 도메인 목록과 LLM 서버 정보를 설정합니다.

```bash
# .env 파일 예시
DOMAINS=일반상식,과학기술,의료건강,법률법규,금융경제,교육학습,역사문화,지리여행,스포츠레저,음식요리,패션뷰티,IT인터넷,비즈니스,예술문학,정치사회,환경자연,엔터테인먼트

LLM_HOST=10.232.200.12
LLM_PORT=9996
LLM_MODEL=qwen3-30B-A3B-Instruct
LLM_TIMEOUT=30
```

## 사용 방법

### 기본 실행

```bash
python main.py
```

- 입력: `input/input.xlsx`
- 출력: `result/result.xlsx`

### 사용자 지정 경로 실행

```bash
python main.py <입력파일경로> <출력파일경로>
```

예시:
```bash
python main.py data/questions.xlsx output/classified.xlsx
```

### Ground Truth 업데이트 (42개 Micro-Intent)

기존의 21개 Ground Truth 도메인 대신, LLM이 분류한 42개 Micro-Intent (초세분화 의도)로 `input/input.xlsx` 파일의 `도메인 Ground Truth` 컬럼을 업데이트합니다. 이를 통해 RAG 시스템의 검색 정확도를 높일 수 있습니다.

```bash
python update_ground_truth.py
```

- **입력**: `input/input.xlsx` (원본 질문 데이터)
- **출력**: `input/input_new_gt.xlsx` (업데이트된 Ground Truth를 포함한 새 파일)

**컬럼 업데이트 방식**:
- `도메인 Ground Truth` 컬럼이 LLM이 예측한 42개 Micro-Intent 중 하나로 업데이트됩니다.
- LLM의 예측 확신도가 낮은 경우 (`Confidence Score < 0.6`), `미분류-{LLM_예측_의도}` 형식으로 저장되어 수동 검토가 필요함을 알립니다.

### Micro-Intent 목록 관리

`update_ground_truth.py` 및 도메인 분류기는 `src/micro_intents.json` 파일에 정의된 Micro-Intent 목록을 사용하여 **동적으로 프롬프트를 생성**하고 분류를 수행합니다.

- **파일 경로**: `src/micro_intents.json`
- **형식**: JSON 객체. 키(Key)는 Micro-Intent 이름이며, 값(Value)은 다음 정보를 포함하는 객체입니다.
  - `gt`: 매핑될 기존 Ground Truth 도메인
  - `category`: 프롬프트 상에서 보여질 상위 카테고리 그룹명
  - `desc`: 프롬프트 상에서 보여질 해당 의도에 대한 설명

- **예시**:
  ```json
  {
      "주소/연락처 변경": {
          "gt": "고객정보",
          "category": "정보/명의 변경",
          "desc": "이사, 전화번호 변경"
      },
      "새로운 의도 이름": {
          "gt": "매핑될_GT_도메인",
          "category": "새로운_카테고리",
          "desc": "이 의도에 대한 설명"
      }
  }
  ```

  **주의**: `micro_intents.json`을 수정하면 도메인 분류기의 프롬프트가 자동으로 변경됩니다. 수정 후에는 반드시 `update_ground_truth.py`를 다시 실행하여 데이터셋의 정합성을 맞춰주세요.


## 입력 파일 형식

엑셀 파일은 다음과 같은 구조여야 합니다:

| 열 | 컬럼명 | 설명 | 초기 상태 |
|----|--------|------|-----------|
| A | (Index/기타) | 행 번호 또는 ID | 선택사항 |
| B | Question | 분류 대상 질문 | **필수** |
| C | 도메인 Ground Truth | 정답 도메인 | **필수** |
| D | LLM 도메인 분류 결과 | LLM이 분류한 도메인 | 비어있음 |
| E | 성공 여부 | Ground Truth와 일치 여부 | 비어있음 |
| F | 분류 의견 | LLM의 분류 근거 및 의견 | 비어있음 |

## 출력 결과

프로그램 실행 후:
- D열: LLM이 분류한 도메인
- E열: 성공 여부 (O/X)
- F열: 분류 의견 및 근거

실행 완료 시 콘솔에 통계 정보가 출력됩니다:
- 총 처리 건수
- 성공/실패 건수
- 정확도
- 오분류 케이스 목록

## 프로젝트 구조

```
domain-detector/
├── .env                    # 환경 변수 설정
├── requirements.txt        # Python 의존성
├── main.py                 # 메인 실행 파일
├── README.md               # 프로젝트 설명서
├── instruction.md          # 개발 명세서
├── input/                  # 입력 파일 디렉토리
│   └── input.xlsx         # 기본 입력 파일
├── result/                 # 출력 파일 디렉토리
│   └── result.xlsx        # 기본 출력 파일
└── src/                    # 소스 코드 디렉토리
    ├── __init__.py        # 패키지 초기화
    ├── excel_handler.py   # 엑셀 처리 모듈
    ├── llm_classifier.py  # LLM 분류 모듈
    └── evaluator.py       # 평가 모듈
```

## 주요 모듈 설명

### excel_handler.py
- 엑셀 파일 읽기/쓰기 기능
- Question과 Ground Truth 데이터 추출
- 분류 결과 저장

### llm_classifier.py
- LLM API 호출
- 도메인 분류 프롬프트 생성
- 응답 파싱 및 도메인 추출

### evaluator.py
- 분류 결과와 Ground Truth 비교
- 통계 정보 생성 (정확도, 성공/실패 건수)
- 오분류 케이스 분석

## 문제 해결

### LLM 서버 연결 실패
- `.env` 파일의 `LLM_HOST`와 `LLM_PORT`가 올바른지 확인
- 네트워크 연결 상태 확인
- 방화벽 설정 확인

### 도메인 목록 오류
- `.env` 파일의 `DOMAINS` 값이 쉼표로 구분되어 있는지 확인
- 17개의 도메인이 모두 정의되어 있는지 확인

### 엑셀 파일 로드 실패
- 입력 파일 경로가 올바른지 확인
- 엑셀 파일이 열려있지 않은지 확인 (다른 프로그램에서 사용 중인 경우)
- 엑셀 파일 형식이 .xlsx인지 확인

## 라이선스

이 프로젝트는 내부 사용 목적으로 개발되었습니다.
