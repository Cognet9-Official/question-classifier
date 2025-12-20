#!/bin/bash
# Domain Detector 설치 스크립트
# 이 스크립트는 모든 소스 코드를 포함하고 있으며, 내부망으로 이전하여 실행할 수 있습니다.

set -e

echo "=========================================="
echo "Domain Detector 설치 시작"
echo "=========================================="

# 프로젝트 디렉토리 생성
PROJECT_DIR="domain-detector"

if [ -d "$PROJECT_DIR" ]; then
    echo "경고: $PROJECT_DIR 디렉토리가 이미 존재합니다."
    read -p "기존 디렉토리를 삭제하고 진행하시겠습니까? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$PROJECT_DIR"
        echo "기존 디렉토리를 삭제했습니다."
    else
        echo "설치를 중단합니다."
        exit 1
    fi
fi

echo "프로젝트 디렉토리 생성 중..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/input"
mkdir -p "$PROJECT_DIR/result"
mkdir -p "$PROJECT_DIR/src"

# requirements.txt 생성
echo "requirements.txt 생성 중..."
cat > "$PROJECT_DIR/requirements.txt" << 'EOF'
openpyxl>=3.1.2
pandas>=2.0.0
python-dotenv>=1.0.0
requests>=2.31.0
EOF

# .env 파일 생성
echo ".env 파일 생성 중..."
cat > "$PROJECT_DIR/.env" << 'EOF'
# 도메인 카테고리 (21개)
DOMAINS=보험금 보장,계약정보,대출,제지급,계약해지,명의변경,보험료납입,증명서 안내장,고객정보,분리보관,변액 펀드,민원,설계사,신계약 미결,채널 표기 코드,채권압류 질권설정,연금,헬스케어서비스,법 제도,바이탈리티,해피콜

# LLM 선택 (qwen3 또는 databricks)
LLM_PROVIDER=qwen3

# Qwen3 설정
QWEN3_HOST=10.232.200.12
QWEN3_PORT=9996
QWEN3_MODEL=qwen3-30b-a3b-instruct

# Databricks 설정
DATABRICKS_URL=https://dbc-0866eb67-6331.cloud.databricks.com/serving-endpoints/databricks-gpt-oss-20b/invocations
DATABRICKS_TOKEN=dapi2a5dd9a1bf7b89e97ee6e9b385aa3cc7
DATABRICKS_MODEL=databricks-gpt-oss-20b

# 공통 설정
LLM_TIMEOUT=30

# 병렬 처리 설정
MAX_CONCURRENT_REQUESTS=5
EOF

# src/__init__.py 생성
echo "src/__init__.py 생성 중..."
cat > "$PROJECT_DIR/src/__init__.py" << 'EOF'
"""
Domain Detector 소스 코드 패키지
"""

__version__ = "1.0.0"
EOF

# src/excel_handler.py 생성
echo "src/excel_handler.py 생성 중..."
cat > "$PROJECT_DIR/src/excel_handler.py" << 'EOF'
"""
엑셀 파일 처리 모듈
입력 엑셀 파일 읽기 및 결과 엑셀 파일 쓰기 기능 제공
"""

import openpyxl
from typing import List, Dict, Any
import os


class ExcelHandler:
    """엑셀 파일 읽기/쓰기 핸들러"""

    def __init__(self, file_path: str):
        """
        Args:
            file_path: 엑셀 파일 경로
        """
        self.file_path = file_path
        self.workbook = None
        self.worksheet = None

    def load(self) -> bool:
        """
        엑셀 파일 로드

        Returns:
            성공 여부
        """
        try:
            if not os.path.exists(self.file_path):
                print(f"Error: 파일을 찾을 수 없습니다 - {self.file_path}")
                return False

            self.workbook = openpyxl.load_workbook(self.file_path)
            self.worksheet = self.workbook.active
            print(f"엑셀 파일 로드 완료: {self.file_path}")
            return True
        except Exception as e:
            print(f"Error: 엑셀 파일 로드 실패 - {e}")
            return False

    def read_questions(self) -> List[Dict[str, Any]]:
        """
        엑셀 파일에서 Question과 Ground Truth 읽기

        Returns:
            질문 데이터 리스트 [{"row": 행번호, "question": 질문, "ground_truth": 정답도메인}, ...]
        """
        if not self.worksheet:
            print("Error: 워크시트가 로드되지 않았습니다.")
            return []

        questions = []

        # 헤더 행 스킵 (1행은 헤더로 가정)
        for row_idx, row in enumerate(self.worksheet.iter_rows(min_row=2, values_only=False), start=2):
            # B열: Question, C열: Ground Truth
            question_cell = row[1]  # B열 (인덱스 1)
            ground_truth_cell = row[2]  # C열 (인덱스 2)

            question = question_cell.value if question_cell.value else ""
            ground_truth = ground_truth_cell.value if ground_truth_cell.value else ""

            # 빈 행은 스킵
            if not question.strip():
                continue

            questions.append({
                "row": row_idx,
                "question": question.strip(),
                "ground_truth": ground_truth.strip()
            })

        print(f"총 {len(questions)}개의 질문을 읽었습니다.")
        return questions

    def write_result(self, row: int, classified_domain: str, success: str, opinion: str, opinion_category: str = ""):
        """
        분류 결과를 엑셀 파일에 쓰기

        Args:
            row: 행 번호
            classified_domain: LLM이 분류한 도메인
            success: 성공 여부 (O/X)
            opinion: 분류 의견
            opinion_category: 분류 의견 구분
        """
        if not self.worksheet:
            print("Error: 워크시트가 로드되지 않았습니다.")
            return

        # D열: LLM 도메인 분류 결과
        self.worksheet.cell(row=row, column=4, value=classified_domain)
        # E열: 성공 여부
        self.worksheet.cell(row=row, column=5, value=success)
        # F열: 분류 의견
        self.worksheet.cell(row=row, column=6, value=opinion)
        # G열: 분류 의견 구분
        self.worksheet.cell(row=row, column=7, value=opinion_category)

    def save(self, output_path: str) -> bool:
        """
        결과를 파일로 저장

        Args:
            output_path: 저장할 파일 경로

        Returns:
            성공 여부
        """
        try:
            # 출력 디렉토리가 없으면 생성
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

            self.workbook.save(output_path)
            print(f"결과 파일 저장 완료: {output_path}")
            return True
        except Exception as e:
            print(f"Error: 파일 저장 실패 - {e}")
            return False

    def close(self):
        """워크북 닫기"""
        if self.workbook:
            self.workbook.close()
EOF

# src/llm_classifier.py 생성
echo "src/llm_classifier.py 생성 중..."
cat > "$PROJECT_DIR/src/llm_classifier.py" << 'EOF'
"""
LLM 분류 모듈
Qwen3 또는 Databricks GPT-OSS 모델을 사용하여 도메인 분류 수행
"""

import requests
from typing import List, Tuple, Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class LLMClassifier:
    """LLM을 사용한 도메인 분류기 (Connection Pool 지원)"""

    def __init__(self, provider: str, config: Dict[str, Any], domains: List[str], timeout: int = 30):
        """
        Args:
            provider: LLM 제공자 ('qwen3' 또는 'databricks')
            config: LLM 설정 딕셔너리
            domains: 도메인 목록
            timeout: API 타임아웃 (초)
        """
        self.provider = provider.lower()
        self.config = config
        self.domains = domains
        self.timeout = timeout

        # Connection Pool을 위한 Session 객체 생성
        self.session = requests.Session()

        # Retry 전략 설정
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        # HTTPAdapter를 사용하여 Connection Pool 설정
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def classify(self, question: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        질문을 분석하여 도메인 분류

        Args:
            question: 분류할 질문

        Returns:
            (분류된 도메인, 분류 의견, 의견 구분) 튜플
        """
        try:
            prompt = self._build_prompt(question)
            response = self._call_llm_api(prompt)

            if response:
                domain, opinion, opinion_category = self._parse_response(response)
                return domain, opinion, opinion_category
            else:
                return None, "LLM API 호출 실패", "기타의견"

        except Exception as e:
            print(f"Error: 분류 중 오류 발생 - {e}")
            return None, f"오류 발생: {str(e)}", "기타의견"

    def _build_prompt(self, question: str) -> str:
        """
        LLM 프롬프트 생성

        Args:
            question: 분류할 질문

        Returns:
            생성된 프롬프트
        """
        domains_str = ", ".join(self.domains)

        prompt = f"""다음 질문을 분석하여 가장 적합한 도메인 하나를 선택하고, 선택 이유 및 의견 구분을 제시하세요.

질문: {question}

도메인 목록: {domains_str}

의견 구분 카테고리:
1. "Ground Truth가 잘못됨" - 정답 도메인이 잘못 설정된 경우
2. "Question이 모호함" - 질문이 불명확하거나 여러 도메인에 해당될 수 있는 경우
3. "맞는 도메인이 없음" - 도메인 목록 중 적합한 도메인이 없는 경우
4. "기타의견" - 위 카테고리에 해당하지 않는 기타 의견

응답 형식:
도메인: [선택한 도메인]
이유: [선택 이유 및 분류 의견]
의견구분: [위 4가지 중 하나]

요구사항:
1. 반드시 위의 도메인 목록 중 하나를 선택해야 합니다.
2. 도메인 분류가 명확한 경우, 해당 이유를 설명하세요.
3. 도메인 분류가 모호한 경우, 그 이유와 가능한 대안 도메인을 제시하세요.
4. 질문이 불명확한 경우, 그 점을 지적하세요.
5. 의견구분은 반드시 위 4가지 카테고리 중 하나를 정확히 선택해야 합니다.
6. 응답은 반드시 "도메인:", "이유:", "의견구분:"으로 시작하는 형식을 따라야 합니다."""

        return prompt

    def _call_llm_api(self, prompt: str) -> Optional[str]:
        """
        LLM API 호출 (provider에 따라 다른 방식)

        Args:
            prompt: 입력 프롬프트

        Returns:
            LLM 응답 텍스트
        """
        if self.provider == "qwen3":
            return self._call_qwen3_api(prompt)
        elif self.provider == "databricks":
            return self._call_databricks_api(prompt)
        else:
            print(f"Error: 지원하지 않는 LLM provider - {self.provider}")
            return None

    def _call_qwen3_api(self, prompt: str) -> Optional[str]:
        """
        Qwen3 API 호출

        Args:
            prompt: 입력 프롬프트

        Returns:
            LLM 응답 텍스트
        """
        try:
            host = self.config.get('host')
            port = self.config.get('port')
            model = self.config.get('model')

            endpoint = f"http://{host}:{port}/v1/chat/completions"

            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            }

            headers = {
                "Content-Type": "application/json"
            }

            response = self.session.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    print(f"Error: 예상치 못한 응답 형식 - {result}")
                    return None
            else:
                print(f"Error: API 호출 실패 (status code: {response.status_code})")
                print(f"Response: {response.text}")
                return None

        except requests.exceptions.Timeout:
            print(f"Error: API 호출 타임아웃 ({self.timeout}초)")
            return None
        except requests.exceptions.ConnectionError:
            print(f"Error: LLM 서버 연결 실패 ({endpoint})")
            return None
        except Exception as e:
            print(f"Error: API 호출 중 오류 - {e}")
            return None

    def _call_databricks_api(self, prompt: str) -> Optional[str]:
        """
        Databricks API 호출

        Args:
            prompt: 입력 프롬프트

        Returns:
            LLM 응답 텍스트
        """
        try:
            url = self.config.get('url')
            token = self.config.get('token')

            payload = {
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    print(f"Error: 예상치 못한 응답 형식 - {result}")
                    return None
            else:
                print(f"Error: API 호출 실패 (status code: {response.status_code})")
                print(f"Response: {response.text}")
                return None

        except requests.exceptions.Timeout:
            print(f"Error: API 호출 타임아웃 ({self.timeout}초)")
            return None
        except requests.exceptions.ConnectionError:
            print(f"Error: Databricks 서버 연결 실패 ({url})")
            return None
        except Exception as e:
            print(f"Error: API 호출 중 오류 - {e}")
            return None

    def _parse_response(self, response: str) -> Tuple[Optional[str], str, str]:
        """
        LLM 응답 파싱

        Args:
            response: LLM 응답 텍스트

        Returns:
            (도메인, 의견, 의견구분) 튜플
        """
        try:
            domain = None
            opinion = ""
            opinion_category = "기타의견"

            # 의견 구분 카테고리 목록
            valid_categories = ["정확히 분류됨", "Ground Truth가 잘못됨", "Question이 모호함", "맞는 도메인이 없음", "기타의견"]

            lines = response.strip().split('\n')

            for line in lines:
                line = line.strip()
                if line.startswith("도메인:"):
                    domain_text = line.replace("도메인:", "").strip()
                    # 도메인 목록에서 매칭되는 것 찾기
                    for d in self.domains:
                        if d in domain_text:
                            domain = d
                            break
                    if not domain:
                        domain = domain_text

                elif line.startswith("이유:"):
                    opinion = line.replace("이유:", "").strip()

                elif line.startswith("의견구분:"):
                    category_text = line.replace("의견구분:", "").strip()
                    # 의견 구분 카테고리 매칭
                    for cat in valid_categories:
                        if cat in category_text:
                            opinion_category = cat
                            break

            # 의견이 없으면 전체 응답을 의견으로 사용
            if not opinion:
                opinion = response.strip()

            # 도메인이 파싱되지 않았으면 도메인 목록에서 첫 번째로 발견되는 것 사용
            if not domain:
                for d in self.domains:
                    if d in response:
                        domain = d
                        break

            # 그래도 없으면 첫 번째 도메인을 기본값으로
            if not domain:
                domain = self.domains[0] if self.domains else "미분류"
                opinion = f"도메인 파싱 실패. 원본 응답: {response}"

            return domain, opinion, opinion_category

        except Exception as e:
            print(f"Error: 응답 파싱 중 오류 - {e}")
            return self.domains[0] if self.domains else "미분류", f"파싱 오류: {str(e)}", "기타의견"

    def close(self):
        """Session 객체 정리"""
        if self.session:
            self.session.close()
EOF

# src/evaluator.py 생성
echo "src/evaluator.py 생성 중..."
cat > "$PROJECT_DIR/src/evaluator.py" << 'EOF'
"""
평가 모듈
LLM 분류 결과와 Ground Truth 비교 및 통계 생성
"""

from typing import Dict, List


class Evaluator:
    """분류 결과 평가기"""

    def __init__(self):
        """평가기 초기화"""
        self.total_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.results = []

    def evaluate(self, classified_domain: str, ground_truth: str) -> str:
        """
        분류 결과와 정답 비교

        Args:
            classified_domain: LLM이 분류한 도메인
            ground_truth: 정답 도메인

        Returns:
            성공 여부 ('O' 또는 'X')
        """
        self.total_count += 1

        # 대소문자 구분 없이, 공백 제거하여 비교
        classified = classified_domain.strip().lower()
        truth = ground_truth.strip().lower()

        if classified == truth:
            self.success_count += 1
            result = 'O'
        else:
            self.fail_count += 1
            result = 'X'

        self.results.append({
            'classified': classified_domain,
            'ground_truth': ground_truth,
            'result': result
        })

        return result

    def get_accuracy(self) -> float:
        """
        정확도 계산

        Returns:
            정확도 (0.0 ~ 1.0)
        """
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count

    def get_statistics(self) -> Dict:
        """
        통계 정보 반환

        Returns:
            통계 딕셔너리
        """
        accuracy = self.get_accuracy()
        return {
            'total': self.total_count,
            'success': self.success_count,
            'fail': self.fail_count,
            'accuracy': accuracy,
            'accuracy_percent': f"{accuracy * 100:.2f}%"
        }

    def print_statistics(self):
        """통계 정보 출력"""
        stats = self.get_statistics()
        print("\n" + "=" * 50)
        print("분류 결과 통계")
        print("=" * 50)
        print(f"총 처리 건수: {stats['total']}")
        print(f"성공: {stats['success']}")
        print(f"실패: {stats['fail']}")
        print(f"정확도: {stats['accuracy_percent']}")
        print("=" * 50)

    def get_confusion_info(self) -> Dict[str, List[Dict]]:
        """
        오분류 정보 반환

        Returns:
            오분류 케이스 딕셔너리
        """
        misclassified = [r for r in self.results if r['result'] == 'X']
        return {
            'count': len(misclassified),
            'cases': misclassified
        }

    def print_misclassified(self, limit: int = 10):
        """
        오분류 케이스 출력

        Args:
            limit: 출력할 최대 개수
        """
        confusion = self.get_confusion_info()
        if confusion['count'] == 0:
            print("\n오분류된 케이스가 없습니다.")
            return

        print(f"\n오분류 케이스 (총 {confusion['count']}건 중 {min(limit, confusion['count'])}건 표시):")
        print("-" * 50)

        for i, case in enumerate(confusion['cases'][:limit], 1):
            print(f"{i}. 정답: {case['ground_truth']} | 분류: {case['classified']}")

        if confusion['count'] > limit:
            print(f"... 외 {confusion['count'] - limit}건")
EOF

# main.py 생성
echo "main.py 생성 중..."
cat > "$PROJECT_DIR/main.py" << 'EOF'
#!/usr/bin/env python3
"""
도메인 분류 어플리케이션 메인 실행 파일

Usage:
    python main.py [입력파일경로] [출력파일경로]

Default:
    입력: input/input.xlsx
    출력: result/result.xlsx
"""

import sys
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.excel_handler import ExcelHandler
from src.llm_classifier import LLMClassifier
from src.evaluator import Evaluator


def load_config():
    """
    환경 변수에서 설정 로드

    Returns:
        설정 딕셔너리
    """
    # .env 파일 로드
    load_dotenv()

    # 도메인 목록 로드
    domains_str = os.getenv('DOMAINS', '')
    domains = [d.strip() for d in domains_str.split(',') if d.strip()]

    if not domains:
        print("Error: 도메인 목록이 .env 파일에 정의되지 않았습니다.")
        print("DOMAINS 환경 변수를 설정해주세요.")
        sys.exit(1)

    # LLM Provider 선택
    llm_provider = os.getenv('LLM_PROVIDER', 'qwen3').lower()

    # LLM 설정 로드
    llm_config = {}
    if llm_provider == 'qwen3':
        llm_config = {
            'host': os.getenv('QWEN3_HOST', '10.232.200.12'),
            'port': int(os.getenv('QWEN3_PORT', '9996')),
            'model': os.getenv('QWEN3_MODEL', 'qwen3-30b-a3b-instruct')
        }
    elif llm_provider == 'databricks':
        llm_config = {
            'url': os.getenv('DATABRICKS_URL'),
            'token': os.getenv('DATABRICKS_TOKEN'),
            'model': os.getenv('DATABRICKS_MODEL', 'databricks-gpt-oss-20b')
        }
    else:
        print(f"Error: 지원하지 않는 LLM_PROVIDER - {llm_provider}")
        print("LLM_PROVIDER는 'qwen3' 또는 'databricks'여야 합니다.")
        sys.exit(1)

    config = {
        'domains': domains,
        'llm_provider': llm_provider,
        'llm_config': llm_config,
        'llm_timeout': int(os.getenv('LLM_TIMEOUT', '30')),
        'max_concurrent_requests': int(os.getenv('MAX_CONCURRENT_REQUESTS', '5'))
    }

    return config


def parse_arguments():
    """
    명령행 인자 파싱

    Returns:
        (입력파일경로, 출력파일경로) 튜플
    """
    if len(sys.argv) >= 3:
        input_path = sys.argv[1]
        output_path = sys.argv[2]
    elif len(sys.argv) == 2:
        input_path = sys.argv[1]
        output_path = 'result/result.xlsx'
    else:
        input_path = 'input/input.xlsx'
        output_path = 'result/result.xlsx'

    return input_path, output_path


def process_single_question(classifier, item, evaluator, print_lock):
    """
    단일 질문 처리 (스레드에서 실행)

    Args:
        classifier: LLM 분류기
        item: 질문 데이터 딕셔너리
        evaluator: 평가기
        print_lock: 출력 동기화를 위한 Lock

    Returns:
        처리 결과 딕셔너리
    """
    row = item['row']
    question = item['question']
    ground_truth = item['ground_truth']

    # LLM을 사용하여 도메인 분류
    classified_domain, opinion, opinion_category = classifier.classify(question)

    if classified_domain is None:
        classified_domain = "분류실패"
        opinion = opinion or "LLM 분류 실패"
        opinion_category = opinion_category or "기타의견"

    # 결과 평가
    success = evaluator.evaluate(classified_domain, ground_truth)

    # Matched된 경우 의견 구분을 "정확히 분류됨"으로 자동 설정
    if success == 'O':
        opinion_category = "정확히 분류됨"

    # 스레드 안전한 출력
    with print_lock:
        question_display = f"{question[:50]}..." if len(question) > 50 else question
        print(f"[행: {row}] {question_display}")
        print(f"  정답: {ground_truth} | 분류: {classified_domain} | 결과: {success}")

    return {
        'row': row,
        'classified_domain': classified_domain,
        'success': success,
        'opinion': opinion,
        'opinion_category': opinion_category
    }


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("도메인 분류 어플리케이션 시작")
    print("=" * 60)

    # 설정 로드
    config = load_config()
    print(f"\nLLM Provider: {config['llm_provider']}")
    print(f"사용 모델: {config['llm_config'].get('model', 'Unknown')}")
    if config['llm_provider'] == 'qwen3':
        print(f"LLM 서버: {config['llm_config']['host']}:{config['llm_config']['port']}")
    elif config['llm_provider'] == 'databricks':
        print(f"Databricks URL: {config['llm_config']['url']}")
    print(f"도메인 개수: {len(config['domains'])}개")
    print(f"최대 동시 요청 수: {config['max_concurrent_requests']}")

    # 명령행 인자 파싱
    input_path, output_path = parse_arguments()
    print(f"입력 파일: {input_path}")
    print(f"출력 파일: {output_path}")

    # 엑셀 핸들러 초기화
    excel_handler = ExcelHandler(input_path)
    if not excel_handler.load():
        print("\nError: 입력 파일을 로드할 수 없습니다.")
        sys.exit(1)

    # 질문 데이터 읽기
    questions = excel_handler.read_questions()
    if not questions:
        print("\nError: 처리할 질문이 없습니다.")
        excel_handler.close()
        sys.exit(1)

    # LLM 분류기 초기화
    classifier = LLMClassifier(
        provider=config['llm_provider'],
        config=config['llm_config'],
        domains=config['domains'],
        timeout=config['llm_timeout']
    )

    # 평가기 초기화
    evaluator = Evaluator()

    # 출력 동기화를 위한 Lock
    print_lock = threading.Lock()

    # 병렬 처리로 질문 분류
    print(f"\n총 {len(questions)}개의 질문 처리 시작 (병렬 처리)...")
    print("-" * 60)

    results = []
    completed_count = 0

    try:
        # ThreadPoolExecutor를 사용한 병렬 처리
        with ThreadPoolExecutor(max_workers=config['max_concurrent_requests']) as executor:
            # 모든 작업 제출
            future_to_item = {
                executor.submit(process_single_question, classifier, item, evaluator, print_lock): item
                for item in questions
            }

            # 완료된 작업 처리
            for future in as_completed(future_to_item):
                completed_count += 1
                try:
                    result = future.result()
                    results.append(result)

                    with print_lock:
                        print(f"진행: {completed_count}/{len(questions)} 완료")

                except Exception as e:
                    item = future_to_item[future]
                    with print_lock:
                        print(f"Error: 행 {item['row']} 처리 중 오류 - {e}")

                    # 오류가 발생해도 결과에 추가
                    results.append({
                        'row': item['row'],
                        'classified_domain': '처리오류',
                        'success': 'X',
                        'opinion': f'오류 발생: {str(e)}',
                        'opinion_category': '기타의견'
                    })

    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        classifier.close()
        excel_handler.close()
        sys.exit(0)

    print("\n" + "-" * 60)
    print("모든 질문 처리 완료")

    # 결과를 행 번호 순으로 정렬
    results.sort(key=lambda x: x['row'])

    # 엑셀에 결과 쓰기
    print("\n결과를 엑셀 파일에 작성 중...")
    for result in results:
        excel_handler.write_result(
            row=result['row'],
            classified_domain=result['classified_domain'],
            success=result['success'],
            opinion=result['opinion'],
            opinion_category=result['opinion_category']
        )

    # 결과 파일 저장
    if excel_handler.save(output_path):
        print(f"\n결과가 {output_path}에 저장되었습니다.")
    else:
        print("\nError: 결과 파일 저장에 실패했습니다.")

    # 통계 출력
    evaluator.print_statistics()

    # 오분류 케이스 출력
    evaluator.print_misclassified(limit=10)

    # 정리
    classifier.close()
    excel_handler.close()

    print("\n프로그램 종료")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError: 예상치 못한 오류 발생 - {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
EOF

# 실행 권한 부여
chmod +x "$PROJECT_DIR/main.py"

echo ""
echo "=========================================="
echo "설치 완료!"
echo "=========================================="
echo ""
echo "프로젝트 경로: $PROJECT_DIR"
echo ""
echo "다음 단계:"
echo "1. cd $PROJECT_DIR"
echo "2. Python 가상환경 생성 (선택사항):"
echo "   python3 -m venv venv"
echo "   source venv/bin/activate"
echo "3. 의존성 설치:"
echo "   pip install -r requirements.txt"
echo "4. .env 파일 수정 (필요시)"
echo "5. input/input.xlsx 파일 준비"
echo "6. 실행:"
echo "   python main.py"
echo ""
echo "=========================================="
