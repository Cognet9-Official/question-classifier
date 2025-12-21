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
        
        # 키워드 규칙 적용 여부 (.env에서 로드, 기본값 True)
        import os
        self.enable_keyword_rules = os.getenv('ENABLE_KEYWORD_RULES', 'true').lower() == 'true'

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

    def _apply_keyword_rules(self, question: str) -> Optional[str]:
        """
        키워드 기반 강제 분류 규칙 적용 (Experiment 9)
        확실한 패턴만 적용하고, 문맥 판단이 필요한 모호한 키워드는 제거함.

        Args:
            question: 질문 텍스트

        Returns:
            매칭된 도메인 또는 None
        """
        q = question.replace(" ", "")  # 띄어쓰기 무시

        # 1. 계약해지 (제지급 혼동 방지) - 청약철회는 무조건 해지
        if "청약철회" in q or "청약취소" in q:
            return "계약해지"

        # 2. 법 제도 (보험금/해지 혼동 방지) - 소멸시효는 법적 기간 문제
        if "소멸시효" in q:
            return "법 제도"

        # 3. 채널 표기 코드 (보험료납입 혼동 방지) - 시스템 표기 관련
        if "RTB" in q or "EWS" in q or "통장표기" in q or "적요" in q:
            return "채널 표기 코드"
            
        # 4. 대출 (명확한 상품명)
        if "약관대출" in q or "보험계약대출" in q or "APL" in q or "자동대출납입" in q:
            return "대출"

        # 납입중지, 부활, 증명서 등은 문맥에 따라 도메인이 달라질 수 있어 LLM에 위임

        return None

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
        # 1. 규칙 기반 분류 우선 적용 (옵션이 켜져있을 때만)
        if self.enable_keyword_rules:
            rule_domain = self._apply_keyword_rules(question)
            if rule_domain:
                logging.info(f"Rule-based 분류 적용: {question} -> {rule_domain}")
                return rule_domain, "키워드 규칙에 의한 강제 분류", "정확히 분류됨"

        # 2. LLM 분류 수행
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
        LLM 프롬프트 생성 (도메인 정의 포함)

        Args:
            question: 분류할 질문

        Returns:
            생성된 프롬프트
        """
        prompt = f"""당신은 RAG(검색 증강 생성)를 위한 문서 카테고리 분류 전문가입니다.

【목표】 사용자의 질문을 분석하여, 답변을 찾을 수 있는 "문서 카테고리"를 선택하세요.
- 질문의 의도보다는 "어느 매뉴얼(문서)을 펼쳐야 하는가"를 생각하십시오.

질문: {question}

=== 문서 카테고리 정의 (총 21개) ===

1. 보험금 보장
   📁 문서 내용: 질병/수술/상해 보장 여부, 진단코드(ICD), 수술명 설명, '청구 가능 조건', 특정 질병의 청구 필요 서류
   ✅ 답변 가능: "백내장 수술 보장되나요?", "C50 코드가 뭔가요?", "실손 통원 청구 시 필요한 병원 서류는?"(보장 조건 확인)
   ❌ 답변 불가: "지급 계좌 변경?"(제지급), "일반적인 청구 서류 접수 방법?"(제지급)
   ⚠️ 핵심: 의료 용어, 질병명, 수술명, "보장 되나요?"

2. 제지급
   📁 문서 내용: 보험금 지급 절차, 지급 방법(계좌/분할), 수익자 확인, 일반적인 청구 서류 접수 방법, 휴면/중도보험금
   ✅ 답변 가능: "지급 계좌 바꾸려면?", "분할 지급 가능한가요?", "미성년자 수익자 서류는?", "청구서류 접수 방법은?"
   ❌ 답변 불가: "청약철회 가능한가요?"(계약해지), "백내장 수술 보장?"(보험금 보장)
   ⚠️ 핵심: "어떻게 받나요?", "절차", "방법", "계좌", "수익자 확인" (단, 청약철회는 제외)

3. 계약정보
   📁 문서 내용: 계약 상태 조회, 부활(자동/일반), 감액, 실효, 직무직종 변경, **건강인/비흡연 할인 신청**, 원본 서류(청약서)
   ✅ 답변 가능: "자동부활 조건은?", "지금 내 계약이 실효 상태인가요?", "비흡연 할인 신청하려면?", "청약서 재발행?"
   ❌ 답변 불가: "건강플러스 할인?"(헬스케어서비스), "단순 이체 계좌 변경?"(보험료납입)
   ⚠️ 핵심: "부활", "감액", "실효", "계약 변경", "할인 신청(상품 기능)"

4. 보험료납입
   📁 문서 내용: 보험료 납입 수단(자동이체, 카드, 소액결제), 납입일/출금일 변경, 납입자 변경, 추가납입, 납입중지
   ✅ 답변 가능: "자동이체일 변경하려면?", "카드로 보험료 낼 수 있나요?", "납입중지 신청 가능한가요?"
   ❌ 답변 불가: "납입주기 변경?"(계약정보 - 계약 조건 변경임)
   ⚠️ 핵심: "돈을 내는 수단/방법", "자동이체", "카드", "출금"

5. 헬스케어서비스
   📁 문서 내용: 건강검진 예약, 헬스케어 앱, 건강 상담, 운동/영양 프로그램, 건강플러스 서비스
   ✅ 답변 가능: "건강검진 예약 방법?", "헬스케어 앱 설치?", "건강플러스 할인?"
   ❌ 답변 불가: "비흡연 할인 신청?"(계약정보), "암 수술비 보장?"(보험금 보장)
   ⚠️ 핵심: 보험금/계약과 무관한 '부가 서비스', 앱 사용법

6. 명의변경
   📁 문서 내용: 계약자/수익자 변경, 명의 정정(개명, 주민번호), 지정대리청구인 등록
   ✅ 답변 가능: "계약자를 남편으로 변경하려면?", "수익자 변경 서류?", "이름이 바뀌었어요"
   ⚠️ 핵심: "변경", "정정", "지정대리청구인"

7. 계약해지
   📁 문서 내용: 해지/해약 신청, 해지환급금 조회/수령, 위약금, **청약철회**
   ✅ 답변 가능: "보험 해지하고 싶어요", "해지환급금 얼마인가요?", "청약철회 기간은?"
   ⚠️ 핵심: "해지", "해약", "철회", "환급금"

8. 증명서 안내장
   📁 문서 내용: 소득공제증명서, 납입증명서, 증권 재발행, 각종 안내장 발송
   ✅ 답변 가능: "소득공제증명서 발급?", "보험증권 재발행?"
   ❌ 답변 불가: "청약서 재발행?"(계약정보 - 원본 서류임)
   ⚠️ 핵심: "증명서", "발급", "증권", "안내장"

9. 법 제도
   📁 문서 내용: 비과세 요건, 세금 제도, 성년후견, 재외국민, FATCA, 소멸시효, 상속 법규
   ✅ 답변 가능: "비과세 요건이 뭔가요?", "성년후견인 지정 절차?", "소멸시효가 몇 년인가요?"
   ⚠️ 핵심: "법", "세금(제도)", "상속", "후견", "재외국민"

10. 고객정보
    📁 문서 내용: 주소/연락처 변경, 마케팅 동의/철회, 개인정보 제공
    ✅ 답변 가능: "이사해서 주소 바꿔야 해요", "전화번호 변경?"
    ⚠️ 핵심: "주소", "전화번호", "개인정보"

11. 대출
    📁 문서 내용: 보험계약대출 신청/상환, 이자율, 대출 한도, APL(자동대출납입)
    ✅ 답변 가능: "약관대출 얼마나 가능한가요?", "대출 이자율은?", "APL 신청하려면?"
    ⚠️ 핵심: "대출", "상환", "이자", "APL"

12. 연금
    📁 문서 내용: 연금 전환 신청, 연금 수령 방법, 연금 개시 나이
    ✅ 답변 가능: "연금으로 전환할 수 있나요?", "연금 수령액은 얼마?"
    ⚠️ 핵심: "연금"

13. 변액 펀드
    📁 문서 내용: 펀드 변경, 펀드 수익률, 투입 비율 변경, 펀드 라인업
    ✅ 답변 가능: "펀드 변경 방법?", "수익률 좋은 펀드는?"
    ⚠️ 핵심: "펀드", "수익률", "투자", "변액"

14. 채권압류 질권설정
    📁 문서 내용: 법원 압류, 질권 설정, 지급 정지/해제
    ✅ 답변 가능: "압류 들어왔는데 해지하려면?", "질권 설정된 계약 대출 되나요?"
    ⚠️ 핵심: "압류", "질권", "법원", "지급정지"

15. 분리보관
    📁 문서 내용: 휴면 계약의 분리 보관, 분리 보관된 계약 조회
    ✅ 답변 가능: "분리보관 안내를 받았어요", "분리보관된 계약 찾고 싶어요"
    ⚠️ 핵심: "분리보관"

16. 민원
    📁 문서 내용: 민원 접수 절차, 불만 접수, 위법계약 해지, 품질보증 해지
    ✅ 답변 가능: "불만 접수 어디서 하나요?", "위법계약 해지하고 싶어요", "품질보증 해지 기간은?"
    ⚠️ 핵심: "민원", "불만", "이의 제기", "위법계약", "품질보증"

17. 설계사
    📁 문서 내용: 설계사(MP) 정보, 수수료, 이관, 담당자 변경
    ✅ 답변 가능: "담당 설계사 연락처?", "설계사 수수료는 어떻게 되나요?"
    ⚠️ 핵심: "설계사", "모집인", "MP", "담당자"

18. 신계약 미결
    📁 문서 내용: 청약 후 승낙 전 상태, 반송/보완(M2), 부담보, 재고지, 인수 심사
    ✅ 답변 가능: "심사 결과 나왔나요?", "부담보 잡혔는데 무슨 뜻?", "재고지 하라고 연락 왔어요"
    ⚠️ 핵심: "심사", "청약 중", "미결", "보완", "부담보", "재고지"

19. 채널 표기 코드
    📁 문서 내용: AIA+, 보이는 ARS, RTB, EWS, 키오스크 이용 방법, 통장 표기(적요), ARS 번호 안내
    ✅ 답변 가능: "앱 로그인이 안 돼요", "통장에 AIA05라고 찍혔는데 뭔가요?", "1588-XXXX 번호 확인"
    ⚠️ 핵심: "앱", "홈페이지", "ARS", "시스템", "오류", "로그인", "통장 표기"

20. 바이탈리티
    📁 문서 내용: 바이탈리티 멤버십, 등급, 리워드, 회비, 앱 연동
    ✅ 답변 가능: "바이탈리티 등급 어떻게 올리나요?", "통신비 할인?"
    ⚠️ 핵심: "바이탈리티", "걷기", "리워드"

21. 해피콜
    📁 문서 내용: 완전판매 모니터링, 해피콜 전화 일정, 해피콜 진행 방법
    ✅ 답변 가능: "해피콜 언제 오나요?", "해피콜 못 받았어요"
    ⚠️ 핵심: "해피콜", "모니터링"

=== 혼동 주의 가이드 (Rule of Thumb) ===

1. [헬스케어서비스] vs [계약정보]
   👉 '건강검진', '건강플러스' 등 서비스 문의는 [헬스케어서비스]입니다.
   👉 '건강인 할인', '비흡연 할인' 등 보험료 할인 신청은 [계약정보]입니다.

2. [보험료납입] vs [계약정보]
   👉 단순히 돈을 내는 수단/일자 변경은 [보험료납입]입니다.
   👉 '납입주기(월납/연납)' 등 계약의 조건을 변경하는 것은 [계약정보]입니다.

3. [제지급] vs [계약해지]
   👉 돈을 돌려받더라도 '청약철회'는 [계약해지]입니다.

=== 응답 형식 ===
도메인: [선택한 도메인]
이유: [선택 이유 (1문장)]
의견구분: [위 5가지 중 하나]
"""
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
                "max_tokens": 1000,
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
                "max_tokens": 3000,
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
                            if isinstance(item, dict):
                                # 'reasoning' 타입 처리 (nested summary)
                                if item.get("type") == "reasoning" and "summary" in item:
                                    for summary_item in item["summary"]:
                                        if isinstance(summary_item, dict) and "text" in summary_item:
                                            text_parts.append(summary_item["text"])
                                # 일반 'text' 필드
                                elif "text" in item:
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
