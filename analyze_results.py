#!/usr/bin/env python3
"""
결과 분석 스크립트
프롬프트 개선을 위한 도메인별 성공/실패 사례 분석
"""

import json
from collections import defaultdict
import sys
import os

# src 모듈 import를 위한 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from llm_classifier import map_to_hierarchical_domain


def analyze_json_results(json_path):
    """JSON 결과 파일 분석"""
    with open(json_path, encoding='utf-8') as f:
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
    print("=" * 80)
    print(f"전체 정확도: {accuracy:.2f}% ({success}/{total})")
    print("=" * 80)

    print("\n도메인별 정확도:")
    print("-" * 80)
    for domain in sorted(domain_stats.keys()):
        stats = domain_stats[domain]
        if stats['total'] > 0:
            dom_acc = stats['correct'] / stats['total'] * 100
            print(f"  {domain:20s}: {dom_acc:5.2f}% ({stats['correct']:3d}/{stats['total']:3d})")

    print("\n주요 혼동 패턴 (Top 20):")
    print("-" * 80)
    all_confusions = [(gt, pred, count)
                     for gt, preds in confusion.items()
                     for pred, count in preds.items()]
    all_confusions.sort(key=lambda x: x[2], reverse=True)
    for i, (gt, pred, count) in enumerate(all_confusions[:20], 1):
        print(f"  {i:2d}. {gt:20s} → {pred:20s}: {count:3d}건")

    return data, domain_stats, confusion


def analyze_hierarchical_results(json_path):
    """13개 LLM 친화적 도메인 레벨에서의 결과 분석"""
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    # 21개 도메인을 13개 도메인으로 변환
    hierarchical_data = []
    for item in data:
        gt_detail = item['ground_truth']
        pred_detail = item['classified_domain']

        # 13개 도메인으로 매핑
        gt_hierarchical = map_to_hierarchical_domain(gt_detail)
        pred_hierarchical = map_to_hierarchical_domain(pred_detail)

        if gt_hierarchical and pred_hierarchical:
            hierarchical_data.append({
                'question': item['question'],
                'ground_truth_detail': gt_detail,
                'ground_truth_hierarchical': gt_hierarchical,
                'classified_detail': pred_detail,
                'classified_hierarchical': pred_hierarchical,
                'success_detail': item['success'],
                'success_hierarchical': 'O' if gt_hierarchical == pred_hierarchical else 'X'
            })

    # 전체 정확도 (13개 도메인 레벨)
    total = len(hierarchical_data)
    success = sum(1 for item in hierarchical_data if item['success_hierarchical'] == 'O')
    accuracy = success / total * 100 if total > 0 else 0

    # 도메인별 통계 (13개 도메인)
    domain_stats = defaultdict(lambda: {'total': 0, 'correct': 0})
    for item in hierarchical_data:
        gt = item['ground_truth_hierarchical']
        domain_stats[gt]['total'] += 1
        if item['success_hierarchical'] == 'O':
            domain_stats[gt]['correct'] += 1

    # 혼동 행렬 (13개 도메인)
    confusion = defaultdict(lambda: defaultdict(int))
    for item in hierarchical_data:
        if item['success_hierarchical'] == 'X':
            confusion[item['ground_truth_hierarchical']][item['classified_hierarchical']] += 1

    # 출력
    print("\n" + "=" * 80)
    print("【13개 LLM 친화적 도메인 레벨 분석】")
    print("=" * 80)
    print(f"전체 정확도: {accuracy:.2f}% ({success}/{total})")
    print("=" * 80)

    print("\n13개 도메인별 정확도:")
    print("-" * 80)
    for domain in sorted(domain_stats.keys()):
        stats = domain_stats[domain]
        if stats['total'] > 0:
            dom_acc = stats['correct'] / stats['total'] * 100
            print(f"  {domain:30s}: {dom_acc:5.2f}% ({stats['correct']:3d}/{stats['total']:3d})")

    print("\n주요 혼동 패턴 (13개 도메인, Top 15):")
    print("-" * 80)
    all_confusions = [(gt, pred, count)
                     for gt, preds in confusion.items()
                     for pred, count in preds.items()]
    all_confusions.sort(key=lambda x: x[2], reverse=True)
    for i, (gt, pred, count) in enumerate(all_confusions[:15], 1):
        print(f"  {i:2d}. {gt:30s} → {pred:30s}: {count:3d}건")

    # 세부 도메인 vs 상위 도메인 정확도 비교
    detail_success = sum(1 for item in hierarchical_data if item['success_detail'] == 'O')
    detail_accuracy = detail_success / total * 100 if total > 0 else 0

    print("\n" + "=" * 80)
    print("정확도 비교:")
    print("-" * 80)
    print(f"  21개 세부 도메인 레벨 정확도:  {detail_accuracy:.2f}% ({detail_success}/{total})")
    print(f"  13개 상위 도메인 레벨 정확도:  {accuracy:.2f}% ({success}/{total})")
    print(f"  향상도:                        +{accuracy - detail_accuracy:.2f}%p")
    print("=" * 80)

    return hierarchical_data, domain_stats, confusion, accuracy


def extract_success_examples(json_path, output_path='domain_success_examples.txt'):
    """도메인별 성공 사례 추출"""
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    # 도메인별 성공 사례 그룹화
    success_by_domain = defaultdict(list)
    for item in data:
        if item['success'] == 'O':
            success_by_domain[item['classified_domain']].append(item['question'])

    # 파일로 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("도메인별 성공 사례 (프롬프트 개선용)\n")
        f.write("=" * 80 + "\n\n")

        for domain in sorted(success_by_domain.keys()):
            examples = success_by_domain[domain]
            f.write(f"\n{'='*80}\n")
            f.write(f"도메인: {domain} (성공 사례 {len(examples)}개)\n")
            f.write(f"{'='*80}\n")

            # 처음 10개만 출력 (대표 예시)
            for i, question in enumerate(examples[:10], 1):
                f.write(f"{i:2d}. {question}\n")

            if len(examples) > 10:
                f.write(f"    ... 외 {len(examples) - 10}개\n")

    print(f"\n성공 사례가 {output_path}에 저장되었습니다.")
    return success_by_domain


def extract_failure_examples(json_path, output_path='domain_failure_examples.txt'):
    """도메인별 실패 사례 추출 (혼동 패턴 분석용)"""
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    # Ground Truth → 잘못 분류된 도메인별 그룹화
    failures = defaultdict(lambda: defaultdict(list))
    for item in data:
        if item['success'] == 'X':
            gt = item['ground_truth']
            pred = item['classified_domain']
            failures[gt][pred].append(item['question'])

    # 파일로 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("도메인별 실패 사례 (혼동 패턴 분석용)\n")
        f.write("=" * 80 + "\n\n")

        for gt in sorted(failures.keys()):
            f.write(f"\n{'='*80}\n")
            f.write(f"정답 도메인: {gt}\n")
            f.write(f"{'='*80}\n")

            for pred in sorted(failures[gt].keys(), key=lambda x: len(failures[gt][x]), reverse=True):
                examples = failures[gt][pred]
                f.write(f"\n  → 잘못 분류된 도메인: {pred} ({len(examples)}건)\n")
                f.write(f"  {'-'*76}\n")

                for i, question in enumerate(examples[:5], 1):
                    f.write(f"    {i}. {question}\n")

                if len(examples) > 5:
                    f.write(f"       ... 외 {len(examples) - 5}개\n")

    print(f"실패 사례가 {output_path}에 저장되었습니다.")
    return failures


if __name__ == '__main__':
    json_path = 'result/result.json'

    print("\n" + "=" * 80)
    print("도메인 분류 결과 분석")
    print("=" * 80 + "\n")

    # 기본 분석 (21개 세부 도메인)
    data, domain_stats, confusion = analyze_json_results(json_path)

    # 13개 LLM 친화적 도메인 레벨 분석
    hierarchical_data, hier_stats, hier_confusion, hier_accuracy = analyze_hierarchical_results(json_path)

    print("\n" + "=" * 80)
    print("상세 사례 추출 중...")
    print("=" * 80 + "\n")

    # 성공 사례 추출
    success_by_domain = extract_success_examples(json_path)

    # 실패 사례 추출
    failures = extract_failure_examples(json_path)

    print("\n" + "=" * 80)
    print("분석 완료!")
    print("=" * 80)
    print("\n다음 파일이 생성되었습니다:")
    print("  - domain_success_examples.txt: 도메인별 성공 사례")
    print("  - domain_failure_examples.txt: 도메인별 실패 사례 (혼동 패턴)")
    print(f"\n💡 13개 LLM 친화적 도메인 레벨 정확도: {hier_accuracy:.2f}%")
