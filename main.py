#!/usr/bin/env python3
"""
도메인 분류 어플리케이션 메인 실행 파일

Usage:
    python main.py [옵션]

Options:
    -i, --input PATH         입력 파일 경로 (기본: input/input.xlsx)
    -o, --output PATH        출력 파일 경로 (기본: result/result.xlsx)
    -n, --limit NUMBER       처리할 질문 개수 제한 (기본: all)
    -f, --filter SUCCESS     성공여부 필터 (all/O/X, 기본: all)

Examples:
    python main.py                                    # 전체 처리
    python main.py -n 10                              # 처음 10개만 처리
    python main.py -f X                               # 실패(X)만 재처리
    python main.py -f O                               # 성공(O)만 처리
    python main.py -n 5 -f X                          # 실패 중 5개만 처리
    python main.py -i data/test.xlsx -o result/out.xlsx
"""

import sys
import os
import argparse
import logging
import time
import json
import random
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.excel_handler import ExcelHandler
from src.llm_classifier import LLMClassifier
from src.evaluator import Evaluator


def setup_logging():
    """
    로깅 설정

    Returns:
        로그 파일 경로
    """
    # .env 파일 로드 (로그 레벨 가져오기 위해)
    load_dotenv()

    # 로그 레벨 설정 (.env에서 읽기, 기본값: INFO)
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    log_level = log_level_map.get(log_level_str, logging.INFO)

    # log 디렉토리 생성
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 로그 파일명 (타임스탬프 포함)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'domain_classifier_{timestamp}.log')

    # 로깅 설정
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"로그 파일: {log_file}")
    logger.info(f"로그 레벨: {log_level_str}")

    return log_file


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
        logging.error("도메인 목록이 .env 파일에 정의되지 않았습니다.")
        logging.error("DOMAINS 환경 변수를 설정해주세요.")
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
        logging.error(f"지원하지 않는 LLM_PROVIDER - {llm_provider}")
        logging.error("LLM_PROVIDER는 'qwen3' 또는 'databricks'여야 합니다.")
        sys.exit(1)

    config = {
        'domains': domains,
        'llm_provider': llm_provider,
        'llm_config': llm_config,
        'llm_timeout': int(os.getenv('LLM_TIMEOUT', '30')),
        'max_concurrent_requests': int(os.getenv('MAX_CONCURRENT_REQUESTS', '5')),
        'thinking_time': int(os.getenv('THINKING_TIME', '3'))
    }

    return config


def parse_arguments():
    """
    명령행 인자 파싱

    Returns:
        args 객체 (input, output, limit, filter)
    """
    parser = argparse.ArgumentParser(
        description='도메인 분류 어플리케이션',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  python main.py                          # 전체 처리
  python main.py -n 10                    # 처음 10개만 처리
  python main.py -f X                     # 실패(X)만 재처리
  python main.py -f O                     # 성공(O)만 처리
  python main.py -n 5 -f X                # 실패 중 5개만 처리
  python main.py -i data/test.xlsx -o result/out.xlsx
        """
    )

    parser.add_argument(
        '-i', '--input',
        default='input/input.xlsx',
        help='입력 파일 경로 (기본: input/input.xlsx)'
    )

    parser.add_argument(
        '-o', '--output',
        default='result/result.xlsx',
        help='출력 파일 경로 (기본: result/result.xlsx)'
    )

    parser.add_argument(
        '-n', '--limit',
        type=int,
        default=None,
        help='처리할 질문 개수 제한 (기본: all)'
    )

    parser.add_argument(
        '-f', '--filter',
        choices=['all', 'O', 'X'],
        default='all',
        help='성공여부 필터 (all/O/X, 기본: all)'
    )

    return parser.parse_args()


def stratified_sample(questions, limit):
    """
    Ground Truth 비율에 맞춰 층화 추출 (랜덤 샘플링)

    Args:
        questions: 전체 질문 리스트
        limit: 추출할 샘플 개수

    Returns:
        샘플링된 질문 리스트
    """
    total_count = len(questions)
    if limit >= total_count:
        return questions

    # Ground Truth별로 그룹화
    groups = defaultdict(list)
    for q in questions:
        gt = q.get('ground_truth', 'Unknown')
        groups[gt].append(q)

    # 그룹별 할당량 계산
    # 1. 일단 비율대로 정수 할당
    targets = {}
    remaining_limit = limit

    # 비율 계산을 위해 미리 리스트화
    group_items = list(groups.items())
    
    # 소수점 오차 처리를 위한 잔여값 저장 리스트
    remainders = []

    for gt, items in group_items:
        ratio = len(items) / total_count
        exact_target = ratio * limit
        int_target = int(exact_target)
        
        targets[gt] = int_target
        remaining_limit -= int_target
        
        # 소수점 부분 저장 (나중에 남은 limit 배분용)
        remainders.append((gt, exact_target - int_target))

    # 2. 남은 할당량을 소수점 부분이 큰 순서대로 배분
    remainders.sort(key=lambda x: x[1], reverse=True)
    
    for i in range(remaining_limit):
        gt = remainders[i % len(remainders)][0]
        targets[gt] += 1

    # 3. 실제 샘플링 수행
    sampled_questions = []
    for gt, target in targets.items():
        items = groups[gt]
        # target이 실제 아이템 수보다 클 수는 없음 (계산상)
        # 하지만 안전장치로 min 적용
        count = min(target, len(items))
        if count > 0:
            sampled_questions.extend(random.sample(items, count))

    # 결과 리스트 섞기 (도메인별로 뭉쳐있지 않게)
    random.shuffle(sampled_questions)
    
    return sampled_questions


def process_single_question(classifier, item, evaluator, print_lock, thinking_time):
    """
    단일 질문 처리 (스레드에서 실행)

    Args:
        classifier: LLM 분류기
        item: 질문 데이터 딕셔너리
        evaluator: 평가기
        print_lock: 출력 동기화를 위한 Lock
        thinking_time: API 호출 후 대기 시간 (초)

    Returns:
        처리 결과 딕셔너리 (API 오류 시 None)
    """
    row = item['row']
    question = item['question']
    ground_truth = item['ground_truth']

    # LLM을 사용하여 도메인 분류
    classified_domain, opinion, opinion_category = classifier.classify(question)

    # API 호출 실패 감지
    if classified_domain is None:
        with print_lock:
            logging.error("=" * 60)
            logging.error(f"[행: {row}] LLM API 호출 실패")
            logging.error(f"질문: {question}")
            logging.error(f"Ground Truth: {ground_truth}")
            logging.error(f"오류 상세: {opinion}")  # opinion에 상세 오류 메시지 포함
            logging.error("=" * 60)
            logging.error("프로그램을 종료합니다.")
        return None  # API 오류 시 None 반환

    # API 호출 후 대기 (Rate Limiting 방지)
    if thinking_time > 0:
        logging.debug(f"[행: {row}] API 호출 후 {thinking_time}초 대기 중...")
        time.sleep(thinking_time)

    # 결과 평가
    success = evaluator.evaluate(classified_domain, ground_truth)

    # Matched된 경우 의견 구분을 "정확히 분류됨"으로 자동 설정
    if success == 'O':
        opinion_category = "정확히 분류됨"

    # 스레드 안전한 로깅
    with print_lock:
        question_display = f"{question[:50]}..." if len(question) > 50 else question
        logging.info(f"[행: {row}] {question_display}")
        logging.info(f"  정답: {ground_truth} | 분류: {classified_domain} | 결과: {success}")

    return {
        'row': row,
        'classified_domain': classified_domain,
        'success': success,
        'opinion': opinion,
        'opinion_category': opinion_category
    }


def save_json_result(output_path: str, results: list, questions: list) -> bool:
    """
    결과를 JSON 파일로 저장 (LLM 분석용)

    instruction.md 3.4 섹션에 정의된 형식으로 저장:
    - 포함 필드: row, question, ground_truth, classified_domain, success, opinion_category
    - 제외 필드: opinion (분류 의견)

    Args:
        output_path: Excel 출력 파일 경로
        results: 분류 결과 리스트
        questions: 원본 질문 데이터 리스트

    Returns:
        저장 성공 여부
    """
    try:
        # Excel 경로를 기반으로 JSON 경로 생성
        json_path = output_path.replace('.xlsx', '.json')

        # 결과 디렉토리 생성 (존재하지 않는 경우)
        json_dir = os.path.dirname(json_path)
        if json_dir and not os.path.exists(json_dir):
            os.makedirs(json_dir)
            logging.debug(f"JSON 결과 디렉토리 생성: {json_dir}")

        logging.info(f"JSON 결과 파일 작성 중... ({len(results)}개 항목)")

        # 질문 데이터를 딕셔너리로 변환 (빠른 검색을 위해)
        question_dict = {item['row']: item for item in questions}

        # JSON 데이터 구성 (instruction.md 3.4 형식에 따라)
        # 분류 의견(opinion)은 제외하고 핵심 데이터만 포함
        json_data = []
        for result in results:
            row = result['row']
            item = question_dict.get(row, {})

            json_data.append({
                'row': row,
                'question': item.get('question', ''),
                'ground_truth': item.get('ground_truth', ''),
                'classified_domain': result['classified_domain'],
                'success': result['success'],
                'opinion_category': result['opinion_category']
            })

        # JSON 파일 저장 (UTF-8 인코딩, 들여쓰기 2칸)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        logging.info(f"JSON 결과가 {json_path}에 저장되었습니다. (총 {len(json_data)}개 항목)")
        return True

    except Exception as e:
        logging.error(f"JSON 결과 파일 저장 실패: {str(e)}")
        import traceback
        logging.debug(f"스택 트레이스:\n{traceback.format_exc()}")
        return False


def main():
    """메인 실행 함수"""
    # 로깅 설정
    log_file = setup_logging()

    logging.info("=" * 60)
    logging.info("도메인 분류 어플리케이션 시작")
    logging.info("=" * 60)

    # 설정 로드
    config = load_config()
    logging.info(f"LLM Provider: {config['llm_provider']}")
    logging.info(f"사용 모델: {config['llm_config'].get('model', 'Unknown')}")
    if config['llm_provider'] == 'qwen3':
        logging.info(f"LLM 서버: {config['llm_config']['host']}:{config['llm_config']['port']}")
    elif config['llm_provider'] == 'databricks':
        logging.info(f"Databricks URL: {config['llm_config']['url']}")
    logging.info(f"도메인 개수: {len(config['domains'])}개")
    logging.info(f"최대 동시 요청 수: {config['max_concurrent_requests']}")
    logging.info(f"API 호출 대기 시간: {config['thinking_time']}초")

    # 명령행 인자 파싱
    args = parse_arguments()
    logging.info(f"입력 파일: {args.input}")
    logging.info(f"출력 파일: {args.output}")
    logging.info(f"처리 개수 제한: {args.limit if args.limit else '전체'}")
    logging.info(f"성공여부 필터: {args.filter}")

    # 엑셀 핸들러 초기화
    excel_handler = ExcelHandler(args.input)
    if not excel_handler.load():
        logging.error("입력 파일을 로드할 수 없습니다.")
        sys.exit(1)

    # 질문 데이터 읽기 (성공여부 필터 적용)
    questions = excel_handler.read_questions(success_filter=args.filter)
    if not questions:
        logging.error("처리할 질문이 없습니다.")
        excel_handler.close()
        sys.exit(1)

    # 개수 제한 및 층화 추출 적용
    if args.limit and args.limit > 0:
        original_count = len(questions)
        questions = stratified_sample(questions, args.limit)
        logging.info(f"층화 랜덤 샘플링 적용: {original_count}개 중 {len(questions)}개 선택 (도메인 비율 유지)")

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
    logging.info(f"총 {len(questions)}개의 질문 처리 시작 (병렬 처리)...")
    logging.info("-" * 60)

    results = []
    completed_count = 0
    api_error_occurred = False

    try:
        # ThreadPoolExecutor를 사용한 병렬 처리
        with ThreadPoolExecutor(max_workers=config['max_concurrent_requests']) as executor:
            # 모든 작업 제출
            future_to_item = {
                executor.submit(process_single_question, classifier, item, evaluator, print_lock, config['thinking_time']): item
                for item in questions
            }

            # 완료된 작업 처리
            for future in as_completed(future_to_item):
                completed_count += 1
                try:
                    result = future.result()

                    # API 오류 발생 확인
                    if result is None:
                        api_error_occurred = True
                        item = future_to_item[future]
                        logging.error("LLM API 오류가 발생했습니다. 남은 작업을 취소하고 종료합니다.")

                        # 실패한 행도 오류 정보로 추가
                        results.append({
                            'row': item['row'],
                            'classified_domain': 'API오류',
                            'success': 'X',
                            'opinion': 'LLM API 호출 실패',
                            'opinion_category': '기타의견'
                        })

                        # 남은 작업 취소
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                    results.append(result)

                    with print_lock:
                        logging.info(f"진행: {completed_count}/{len(questions)} 완료")

                except Exception as e:
                    item = future_to_item[future]
                    with print_lock:
                        logging.error("=" * 60)
                        logging.error(f"행 {item['row']} 처리 중 예외 발생")
                        logging.error(f"질문: {item['question']}")
                        logging.error(f"오류 메시지: {str(e)}")
                        import traceback
                        logging.debug(f"스택 트레이스:\n{traceback.format_exc()}")
                        logging.error("=" * 60)

                    # 오류가 발생해도 결과에 추가
                    results.append({
                        'row': item['row'],
                        'classified_domain': '처리오류',
                        'success': 'X',
                        'opinion': f'오류 발생: {str(e)}',
                        'opinion_category': '기타의견'
                    })

    except KeyboardInterrupt:
        logging.warning("사용자에 의해 중단되었습니다.")
        classifier.close()
        excel_handler.close()
        sys.exit(0)

    if api_error_occurred:
        logging.info("API 오류로 인해 처리가 중단되었습니다.")
    else:
        logging.info("-" * 60)
        logging.info("모든 질문 처리 완료")

    # 결과를 행 번호 순으로 정렬
    results.sort(key=lambda x: x['row'])

    # 엑셀에 결과 쓰기
    logging.info("결과를 엑셀 파일에 작성 중...")
    for result in results:
        excel_handler.write_result(
            row=result['row'],
            classified_domain=result['classified_domain'],
            success=result['success'],
            opinion=result['opinion'],
            opinion_category=result['opinion_category']
        )

    # 결과 파일 저장
    if excel_handler.save(args.output):
        logging.info(f"결과가 {args.output}에 저장되었습니다.")
    else:
        logging.error("결과 파일 저장에 실패했습니다.")

    # JSON 결과 파일 저장 (LLM 분석용)
    save_json_result(args.output, results, questions)

    # 통계 출력
    evaluator.print_statistics()

    # 오분류 케이스 출력
    evaluator.print_misclassified(limit=10)

    # 정리
    classifier.close()
    excel_handler.close()

    logging.info("프로그램 종료")
    logging.info("=" * 60)

    # API 오류 발생 시 비정상 종료
    if api_error_occurred:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("\n사용자에 의해 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        logging.error(f"예상치 못한 오류 발생 - {e}")
        import traceback
        logging.debug(traceback.format_exc())
        sys.exit(1)
