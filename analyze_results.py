#!/usr/bin/env python3
"""
결과 분석 스크립트
프롬프트 개선을 위한 도메인별 성공/실패 사례 분석
"""

import json
from collections import defaultdict


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

    # 기본 분석
    data, domain_stats, confusion = analyze_json_results(json_path)

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
