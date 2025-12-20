"""
LLM 분류 모듈
Qwen3 또는 Databricks GPT-OSS 모델을 사용하여 도메인 분류 수행
"""

import requests
import logging
from typing import List, Tuple, Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class LLMClassifier:
    """LLM을 사용한 도메인 분류기 (Connection Pool 지원)"""

    def __init__(
        self,
        provider: str,
        config: Dict[str, Any],
        domains: List[str],
        timeout: int = 30,
    ):
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
            total=10,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
        )

        # HTTPAdapter를 사용하여 Connection Pool 설정
        adapter = HTTPAdapter(
            max_retries=retry_strategy, pool_connections=10, pool_maxsize=10
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def classify(
        self, question: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        질문을 분석하여 도메인 분류

        Args:
            question: 분류할 질문

        Returns:
            (분류된 도메인, 분류 의견, 의견 구분) 튜플
        """
        try:
            prompt = self._build_prompt(question)
            response, error_msg = self._call_llm_api(prompt)

            if response is not None:
                domain, opinion, opinion_category = self._parse_response(response)
                return domain, opinion, opinion_category
            else:
                # API 호출 실패 시 상세 오류 메시지 반환
                return None, f"LLM API 호출 실패: {error_msg}", "기타의견"

        except Exception as e:
            logging.error(f"분류 중 예외 발생: {e}")
            import traceback

            logging.debug(f"스택 트레이스:\n{traceback.format_exc()}")
            return None, f"예외 발생: {str(e)}", "기타의견"

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

    def _call_llm_api(self, prompt: str) -> Tuple[Optional[str], str]:
        """
        LLM API 호출 (provider에 따라 다른 방식)

        Args:
            prompt: 입력 프롬프트

        Returns:
            (LLM 응답 텍스트, 오류 메시지) 튜플
        """
        if self.provider == "qwen3":
            return self._call_qwen3_api(prompt)
        elif self.provider == "databricks":
            return self._call_databricks_api(prompt)
        else:
            error_msg = f"지원하지 않는 LLM provider: {self.provider}"
            logging.error("=" * 60)
            logging.error(f"지원하지 않는 LLM provider")
            logging.error(f"설정된 Provider: {self.provider}")
            logging.error(f"지원 Provider: qwen3, databricks")
            logging.error("=" * 60)
            return None, error_msg

    def _call_qwen3_api(self, prompt: str) -> Tuple[Optional[str], str]:
        """
        Qwen3 API 호출

        Args:
            prompt: 입력 프롬프트

        Returns:
            (LLM 응답 텍스트, 오류 메시지) 튜플
        """
        endpoint = "알 수 없음"  # 오류 로깅을 위한 기본값
        try:
            host = self.config.get("host")
            port = self.config.get("port")
            model = self.config.get("model")

            endpoint = f"http://{host}:{port}/v1/chat/completions"

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            }

            headers = {"Content-Type": "application/json"}

            response = self.session.post(
                endpoint, headers=headers, json=payload, timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]

                    # 빈 문자열 확인
                    if not content or not content.strip():
                        error_msg = "빈 응답 내용"
                        logging.error("=" * 60)
                        logging.error(f"Qwen3 API - {error_msg}")
                        logging.error(f"Endpoint: {endpoint}")
                        logging.debug(f"응답 내용: {result}")
                        logging.error("=" * 60)
                        return None, error_msg

                    logging.debug(f"Qwen3 API 응답 성공: {content[:100]}...")
                    return content, ""
                else:
                    error_msg = f"예상치 못한 응답 형식"
                    logging.error("=" * 60)
                    logging.error(f"Qwen3 API - {error_msg}")
                    logging.error(f"Endpoint: {endpoint}")
                    logging.debug(f"응답 내용: {result}")
                    logging.error("=" * 60)
                    return None, error_msg
            else:
                error_msg = f"HTTP {response.status_code} 오류"
                logging.error("=" * 60)
                logging.error("Qwen3 API 호출 실패")
                logging.error(f"Endpoint: {endpoint}")
                logging.error(f"Status Code: {response.status_code}")
                logging.debug(f"Response Headers: {dict(response.headers)}")
                logging.debug(f"Response Body: {response.text}")
                logging.error("=" * 60)
                return None, error_msg

        except requests.exceptions.Timeout:
            error_msg = f"API 호출 타임아웃 ({self.timeout}초)"
            logging.error("=" * 60)
            logging.error(f"Qwen3 {error_msg}")
            logging.error(f"Endpoint: {endpoint}")
            logging.error("=" * 60)
            return None, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"서버 연결 실패: {str(e)}"
            logging.error("=" * 60)
            logging.error(f"Qwen3 서버 연결 실패")
            logging.error(f"Endpoint: {endpoint}")
            logging.error(f"오류 메시지: {str(e)}")
            logging.error("=" * 60)
            return None, error_msg
        except Exception as e:
            error_msg = f"예외 발생: {str(e)}"
            logging.error("=" * 60)
            logging.error(f"Qwen3 API 호출 중 예외 발생")
            logging.error(f"Endpoint: {endpoint}")
            logging.error(f"오류 메시지: {str(e)}")
            import traceback

            logging.debug(f"스택 트레이스:\n{traceback.format_exc()}")
            logging.error("=" * 60)
            return None, error_msg

    def _call_databricks_api(self, prompt: str) -> Tuple[Optional[str], str]:
        """
        Databricks API 호출

        Args:
            prompt: 입력 프롬프트

        Returns:
            (LLM 응답 텍스트, 오류 메시지) 튜플
        """
        url = "알 수 없음"  # 오류 로깅을 위한 기본값
        try:
            url = self.config.get("url", "알 수 없음")
            token = self.config.get("token")

            payload = {
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 5000,
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = self.session.post(
                url, headers=headers, json=payload, timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]

                    # content가 리스트인 경우 처리 (Databricks API 특성)
                    if isinstance(content, list):
                        # 빈 리스트 확인
                        if not content:
                            error_msg = "빈 응답 리스트"
                            logging.error("=" * 60)
                            logging.error(f"Databricks API - {error_msg}")
                            logging.error(f"URL: {url}")
                            logging.debug(f"응답 내용: {result}")
                            logging.error("=" * 60)
                            return None, error_msg

                        # 리스트의 각 요소를 텍스트로 변환하여 결합
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                text_parts.append(item["text"])
                            elif isinstance(item, str):
                                text_parts.append(item)
                        content = "\n".join(text_parts)

                    # 빈 문자열 확인
                    if not content or not content.strip():
                        error_msg = "빈 응답 내용"
                        logging.error("=" * 60)
                        logging.error(f"Databricks API - {error_msg}")
                        logging.error(f"URL: {url}")
                        logging.debug(f"응답 내용: {result}")
                        logging.error("=" * 60)
                        return None, error_msg

                    logging.debug(f"Databricks API 응답 성공: {content[:100]}...")
                    return content, ""
                else:
                    error_msg = f"예상치 못한 응답 형식"
                    logging.error("=" * 60)
                    logging.error(f"Databricks API - {error_msg}")
                    logging.error(f"URL: {url}")
                    logging.debug(f"응답 내용: {result}")
                    logging.error("=" * 60)
                    return None, error_msg
            else:
                error_msg = f"HTTP {response.status_code} 오류"
                logging.error("=" * 60)
                logging.error("Databricks API 호출 실패")
                logging.error(f"URL: {url}")
                logging.error(f"Status Code: {response.status_code}")
                logging.debug(f"Response Headers: {dict(response.headers)}")
                logging.debug(f"Response Body: {response.text}")
                logging.error("=" * 60)
                return None, error_msg

        except requests.exceptions.Timeout:
            error_msg = f"API 호출 타임아웃 ({self.timeout}초)"
            logging.error("=" * 60)
            logging.error(f"Databricks {error_msg}")
            logging.error(f"URL: {url}")
            logging.error("=" * 60)
            return None, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"서버 연결 실패: {str(e)}"
            logging.error("=" * 60)
            logging.error(f"Databricks 서버 연결 실패")
            logging.error(f"URL: {url}")
            logging.error(f"오류 메시지: {str(e)}")
            logging.error("=" * 60)
            return None, error_msg
        except Exception as e:
            error_msg = f"예외 발생: {str(e)}"
            logging.error("=" * 60)
            logging.error(f"Databricks API 호출 중 예외 발생")
            logging.error(f"URL: {url}")
            logging.error(f"오류 메시지: {str(e)}")
            import traceback

            logging.debug(f"스택 트레이스:\n{traceback.format_exc()}")
            logging.error("=" * 60)
            return None, error_msg

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

            # response가 문자열이 아닌 경우 처리
            if not isinstance(response, str):
                logging.warning("=" * 60)
                logging.warning(f"LLM 응답이 문자열이 아닙니다")
                logging.warning(f"응답 타입: {type(response)}")
                logging.debug(f"응답 값: {response}")
                logging.warning("문자열로 변환하여 처리를 계속합니다.")
                logging.warning("=" * 60)
                response = str(response)

            # LLM 응답 전체 (DEBUG 모드에서만)
            logging.debug(f"LLM 응답 파싱 시작:")
            logging.debug(f"응답 내용: {response}")

            # 의견 구분 카테고리 목록
            valid_categories = [
                "정확히 분류됨",
                "Ground Truth가 잘못됨",
                "Question이 모호함",
                "맞는 도메인이 없음",
                "기타의견",
            ]

            lines = response.strip().split("\n")

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
            logging.error("=" * 60)
            logging.error(f"응답 파싱 중 예외 발생")
            logging.debug(f"응답 내용: {response}")
            logging.error(f"오류 메시지: {str(e)}")
            import traceback

            logging.debug(f"스택 트레이스:\n{traceback.format_exc()}")
            logging.error("=" * 60)
            return (
                self.domains[0] if self.domains else "미분류",
                f"파싱 오류: {str(e)}",
                "기타의견",
            )

    def close(self):
        """Session 객체 정리"""
        if self.session:
            self.session.close()
