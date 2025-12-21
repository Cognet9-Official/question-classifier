import os
import logging
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import List, Dict, Tuple, Optional, Any
import re
import json
from collections import defaultdict
import difflib

# Dummy mapping for backward compatibility (main.py imports this)
HIERARCHICAL_DOMAIN_MAPPING = {}

def map_to_hierarchical_domain(detail_domain: str) -> Optional[str]:
    """
    Dummy function for backward compatibility.
    Experiment 16 uses direct Micro-Intent to GT mapping.
    """
    return None


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

        # 키워드 규칙 적용 여부 (Experiment 16: False)
        self.enable_keyword_rules = False

        # Micro-Intent 매핑 파일 로드
        try:
            script_dir = os.path.dirname(__file__)
            json_path = os.path.join(script_dir, 'micro_intents.json')
            with open(json_path, 'r', encoding='utf-8') as f:
                self.micro_intents_data = json.load(f)
            logging.info(f"Micro-Intents loaded from {json_path}: {len(self.micro_intents_data)} intents.")
        except Exception as e:
            logging.error(f"Micro-Intents 파일 로드 실패 ({json_path}): {e}")
            self.micro_intents_data = {}

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

    def close(self):
        """세션 종료"""
        if self.session:
            self.session.close()

    def _apply_keyword_rules(self, question: str) -> Optional[str]:
        """
        키워드 기반 강제 분류 규칙 (Experiment 16: 미사용)
        """
        return None

    def classify(
        self,
        question: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        질문을 분석하여 42개 Micro-Intent 중 하나로 분류 (Ground Truth 생성용)

        Args:
            question: 분류할 질문

        Returns:
            (분류된 Micro-Intent, 분류 의견, 의견 구분) 튜플
        """
        # 42개 표준 의도 목록
        STANDARD_INTENTS = list(self.micro_intents_data.keys())

        # LLM 분류 수행
        try:
            prompt = self._build_prompt(question)
            response, error_msg = self._call_llm_api(prompt)

            if response is not None:
                # LLM 응답에서 Micro-Intent 파싱
                micro_intent, opinion, opinion_category = self._parse_response(response)
                
                # 1. Exact Match 확인
                if micro_intent in STANDARD_INTENTS:
                    return micro_intent, opinion, "Exact Match"

                # 2. Fuzzy Match (유사도 계산)
                best_match = None
                highest_ratio = 0.0
                
                for standard in STANDARD_INTENTS:
                    # 노이즈 제거 후 비교 (공백, 특수문자)
                    norm_intent = re.sub(r'[^\w]', '', micro_intent)
                    norm_standard = re.sub(r'[^\w]', '', standard)
                    
                    ratio = difflib.SequenceMatcher(None, norm_intent, norm_standard).ratio()
                    
                    # 부분 문자열 포함 시 가산점
                    if norm_standard in norm_intent or norm_intent in norm_standard:
                        ratio += 0.2
                        if ratio > 1.0: ratio = 1.0

                    if ratio > highest_ratio:
                        highest_ratio = ratio
                        best_match = standard
                
                # Threshold 설정 (0.6 이상이면 인정)
                THRESHOLD = 0.6
                
                if best_match and highest_ratio >= THRESHOLD:
                    logging.info(f"Fuzzy Match: '{micro_intent}' -> '{best_match}' (Score: {highest_ratio:.2f})")
                    return best_match, f"{opinion} (유사도: {highest_ratio:.2f})", "Fuzzy Match"
                else:
                    logging.warning(f"Low Confidence: '{micro_intent}' (Best: {best_match}, Score: {highest_ratio:.2f})")
                    return f"미분류-{micro_intent}", f"{opinion} (유사도 미달: {highest_ratio:.2f})", "Low Confidence"

            else:
                return None, f"LLM API 호출 실패: {error_msg}", "API Error"

        except Exception as e:
            logging.error(f"분류 중 예외 발생: {e}")
            return None, f"예외 발생: {str(e)}", "Error"

    def _build_prompt(self, question: str) -> str:
        """
        LLM 프롬프트 생성 (Experiment 16: 42개 Micro-Intent, 동적 생성)

        Args:
            question: 분류할 질문

        Returns:
            생성된 프롬프트
        """
        # 그룹화 (동적)
        grouped_intents = defaultdict(list)
        
        for intent, info in self.micro_intents_data.items():
            category = info.get('category', '기타')
            desc = info.get('desc', '')
            grouped_intents[category].append(f"{intent} ({desc})")
        
        # 프롬프트 텍스트 조합
        intents_description = ""
        intent_number = 1
        
        # 카테고리 순서 고정을 위해 정렬
        sorted_categories = sorted(grouped_intents.keys())
        
        for category in sorted_categories:
            intents_description += f"\n[{category}]\n"
            for intent_str in grouped_intents[category]:
                intents_description += f"{intent_number}. {intent_str}\n"
                intent_number += 1

        prompt = f"""당신은 보험사 고객 센터 AI입니다.
고객의 질문을 분석하여, 아래 **{len(self.micro_intents_data)}개 세부 의도(Micro-Intent)** 중 가장 정확한 하나를 선택하세요.

질문: {question}

=== 세부 의도 목록 (하나만 선택) ===
{intents_description}
=== 응답 형식 ===
도메인: [위 목록 중 하나를 정확히 기재, 예: 주소/연락처 변경]
이유: [선택 이유 1문장]
의견구분: [정확히 분류됨/모호함/없음/기타 중 택1]
"""
        return prompt

    def _call_llm_api(self, prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """
        LLM API 호출 (Databricks 또는 Qwen)
        """
        try:
            if self.provider == "qwen3":
                # Qwen3 API 호출 로직 (생략 - 기존 코드 유지 필요 시 구현)
                pass
            elif self.provider == "databricks":
                # Databricks API 호출
                api_url = self.config.get("url")
                access_token = self.config.get("token")
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                
                payload = {
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."}, 
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.0,
                }
                
                response = self.session.post(
                    api_url, headers=headers, json=payload, timeout=self.timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    # content가 리스트인 경우 (Reasoning step 포함 시) 처리
                    if isinstance(content, list):
                        text_content = ""
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_content += item.get("text", "")
                        content = text_content
                        
                    return content, None
                else:
                    return None, f"Status Code: {response.status_code}, Response: {response.text}"
            
            return None, "지원하지 않는 Provider"

        except Exception as e:
            return None, str(e)

    def _parse_response(
        self,
        response: str
    ) -> Tuple[str, str, str]:
        """
        LLM 응답 파싱
        """
        domain = "기타"
        opinion = ""
        opinion_category = "기타의견"

        try:
            lines = response.strip().split('\n')
            for line in lines:
                if "도메인:" in line:
                    domain = line.split("도메인:")[1].strip()
                    # 괄호나 번호 제거 (예: "1. 주소 변경" -> "주소 변경")
                    domain = re.sub(r'^\d+\.\s*', '', domain)
                    domain = re.sub(r'\[.*?\]', '', domain).strip()
                elif "이유:" in line:
                    opinion = line.split("이유:")[1].strip()
                elif "의견구분:" in line:
                    opinion_category = line.split("의견구분:")[1].strip()
            
            return domain, opinion, opinion_category

        except Exception as e:
            logging.error(f"응답 파싱 오류: {e}")
            return domain, opinion, opinion_category