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
    ) -> Tuple[List[str], Optional[str], Optional[str]]:
        """
        질문을 분석하여 42개 Micro-Intent 중 Top-3를 분류 (실험20: 강제 매칭 제거, Threshold 0.3)

        Args:
            question: 분류할 질문

        Returns:
            (분류된 Micro-Intent 리스트, 분류 의견, 의견 구분) 튜플
        """
        # 42개 표준 의도 목록
        STANDARD_INTENTS = list(self.micro_intents_data.keys())

        # LLM 분류 수행
        try:
            prompt = self._build_prompt(question)
            response, error_msg = self._call_llm_api(prompt)

            if response is not None:
                # LLM 응답에서 Micro-Intent 리스트 파싱
                micro_intents, opinion, opinion_category = self._parse_response(response)

                # 각 도메인에 대해 Fuzzy Matching 수행
                matched_intents = []
                match_details = []

                for micro_intent in micro_intents:
                    # 1. Exact Match 확인
                    if micro_intent in STANDARD_INTENTS:
                        matched_intents.append(micro_intent)
                        match_details.append(f"{micro_intent} (Exact)")
                        continue

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

                    # Threshold 설정 (0.3 이상이면 인정 - 실험20: 강제 매칭 제거)
                    THRESHOLD = 0.3

                    if best_match and highest_ratio >= THRESHOLD:
                        matched_intents.append(best_match)
                        match_details.append(f"{best_match} (Fuzzy: {highest_ratio:.2f})")
                        logging.info(f"Fuzzy Match: '{micro_intent}' -> '{best_match}' (Score: {highest_ratio:.2f})")
                    else:
                        # 유사도 미달 시 미분류 처리 (강제 매칭 제거)
                        matched_intents.append(f"미분류-{micro_intent}")
                        match_details.append(f"{micro_intent} (No Match: {highest_ratio:.2f})")
                        logging.warning(f"No Match (Below Threshold): '{micro_intent}' (Best: '{best_match}', Score: {highest_ratio:.2f})")

                # 중복 제거
                matched_intents = list(dict.fromkeys(matched_intents))

                # 매칭 상세 정보를 의견에 추가
                detailed_opinion = f"{opinion} [매칭: {', '.join(match_details)}]"

                return matched_intents, detailed_opinion, opinion_category

            else:
                return [None], f"LLM API 호출 실패: {error_msg}", "API Error"

        except Exception as e:
            logging.error(f"분류 중 예외 발생: {e}")
            return [None], f"예외 발생: {str(e)}", "Error"

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
고객의 질문을 분석하여, 아래 **{len(self.micro_intents_data)}개 세부 의도(Micro-Intent)** 중 가능성이 높은 순서대로 **최대 3개**를 나열하세요.

질문: {question}

=== 세부 의도 목록 ===
{intents_description}
=== ⚠️ 절대 금지 사항 ===
- **"기타", "없음", "알 수 없음" 같은 답변 절대 금지!**
- **위 목록에 없는 값을 절대 입력하지 마세요!**
- **반드시 위 목록에서만 선택하세요!**

=== 중요 지침 ===
1. 질문을 주의 깊게 읽고, 위 세부 의도 목록에서 가장 관련성이 높은 것을 1순위로 선택하세요.
2. 완전히 일치하지 않더라도, **가장 가까운 의도**를 선택하세요.
3. 애매하거나 중복 가능성이 있다면 2순위, 3순위도 제시하세요.
4. 확실하게 하나만 해당된다면 1개만 제시해도 됩니다.
5. 최대 3개까지만 나열하세요.

=== 분류 예시 ===

예시 1:
질문: 주소를 변경하고 싶어요
도메인1: 주소/연락처 변경
이유: 주소 변경 문의로 명확함
의견구분: 정확히 분류됨

예시 2:
질문: 보험금 청구 서류가 뭔가요?
도메인1: 청구 서류 안내
도메인2: 청구 절차 문의
이유: 청구 서류 안내가 가장 적합하며, 절차 문의도 관련됨
의견구분: 정확히 분류됨

예시 3:
질문: 앱으로 보험금 청구할 때 최대 금액이 얼마인가요?
도메인1: 보장 여부 확인
도메인2: 청구 절차 문의
이유: 보험금 청구 한도를 묻는 것으로 보장 범위 확인에 해당함
의견구분: 정확히 분류됨

=== 응답 형식 (반드시 정확히 따르세요) ===
도메인1: [위 목록에서 선택]
도메인2: [위 목록에서 선택, 없으면 생략]
도메인3: [위 목록에서 선택, 없으면 생략]
이유: [도메인1을 선택한 이유 1문장]
의견구분: [정확히 분류됨/모호함 중 택1]

**주의**: 도메인1, 도메인2, 도메인3에는 세부 의도 목록에 있는 정확한 이름을 기재하세요.
괄호나 설명문을 추가하지 말고, 목록의 의도 이름만 정확히 입력하세요.
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
    ) -> Tuple[List[str], str, str]:
        """
        LLM 응답 파싱 (실험20: Top-3 다중 의도)

        Returns:
            (도메인 리스트, 의견, 의견 구분) 튜플
        """
        domains = []
        opinion = ""
        opinion_category = "기타의견"

        try:
            lines = response.strip().split('\n')
            for line in lines:
                # 도메인1, 도메인2, 도메인3 파싱
                if "도메인1:" in line:
                    domain1 = line.split("도메인1:")[1].strip()
                    domain1 = re.sub(r'^\d+\.\s*', '', domain1)
                    domain1 = re.sub(r'\[.*?\]', '', domain1).strip()
                    if domain1 and domain1 != "":
                        domains.append(domain1)
                elif "도메인2:" in line:
                    domain2 = line.split("도메인2:")[1].strip()
                    domain2 = re.sub(r'^\d+\.\s*', '', domain2)
                    domain2 = re.sub(r'\[.*?\]', '', domain2).strip()
                    if domain2 and domain2 != "":
                        domains.append(domain2)
                elif "도메인3:" in line:
                    domain3 = line.split("도메인3:")[1].strip()
                    domain3 = re.sub(r'^\d+\.\s*', '', domain3)
                    domain3 = re.sub(r'\[.*?\]', '', domain3).strip()
                    if domain3 and domain3 != "":
                        domains.append(domain3)
                # 하위 호환성: 기존 "도메인:" 형식도 지원
                elif "도메인:" in line and "도메인1:" not in line and "도메인2:" not in line and "도메인3:" not in line:
                    domain = line.split("도메인:")[1].strip()
                    domain = re.sub(r'^\d+\.\s*', '', domain)
                    domain = re.sub(r'\[.*?\]', '', domain).strip()
                    if domain and domain != "" and domain not in domains:
                        domains.append(domain)
                elif "이유:" in line:
                    opinion = line.split("이유:")[1].strip()
                elif "의견구분:" in line:
                    opinion_category = line.split("의견구분:")[1].strip()

            # 도메인이 하나도 파싱되지 않았으면 기본값
            if not domains:
                domains = ["기타"]

            return domains, opinion, opinion_category

        except Exception as e:
            logging.error(f"응답 파싱 오류: {e}")
            return ["기타"], opinion, opinion_category