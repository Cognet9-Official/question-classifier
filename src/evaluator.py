"""
평가 모듈
LLM 분류 결과와 Ground Truth 비교 및 통계 생성
"""

from typing import Dict, List
import logging


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
        logging.info("\n" + "=" * 50)
        logging.info("분류 결과 통계")
        logging.info("=" * 50)
        logging.info(f"총 처리 건수: {stats['total']}")
        logging.info(f"성공: {stats['success']}")
        logging.info(f"실패: {stats['fail']}")
        logging.info(f"정확도: {stats['accuracy_percent']}")
        logging.info("=" * 50)

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
            logging.info("\n오분류된 케이스가 없습니다.")
            return

        logging.info(f"\n오분류 케이스 (총 {confusion['count']}건 중 {min(limit, confusion['count'])}건 표시):")
        logging.info("-" * 50)

        for i, case in enumerate(confusion['cases'][:limit], 1):
            logging.info(f"{i}. 정답: {case['ground_truth']} | 분류: {case['classified']}")

        if confusion['count'] > limit:
            logging.info(f"... 외 {confusion['count'] - limit}건")
