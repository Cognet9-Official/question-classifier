#!/usr/bin/env python3
"""실험 20 결과 분석 스크립트"""

import json
from collections import defaultdict

# result.json 읽기
with open('result/result.json', 'r', encoding='utf-8') as f:
    results = json.load(f)

total = len(results)
print(f"총 테스트 케이스: {total}개\n")

# 기본 통계
success_count = sum(1 for r in results if r.get('success') == 'O')
fail_count = sum(1 for r in results if r.get('success') == 'X')

print(f"=== 전체 정확도 ===")
print(f"성공: {success_count}개 ({success_count/total*100:.2f}%)")
print(f"실패: {fail_count}개 ({fail_count/total*100:.2f}%)\n")

# GT가 '미분류-기타'인 케이스 제외 정확도
gt_unclassified = [r for r in results if r.get('ground_truth', '').strip() == '미분류-기타']
gt_classified = [r for r in results if r.get('ground_truth', '').strip() != '미분류-기타']

print(f"=== GT 미분류 제외 정확도 ===")
print(f"GT 미분류 케이스: {len(gt_unclassified)}개")
print(f"GT 설정된 케이스: {len(gt_classified)}개")

success_in_classified = sum(1 for r in gt_classified if r.get('success') == 'O')
print(f"GT 설정된 케이스 중 성공: {success_in_classified}개 ({success_in_classified/len(gt_classified)*100:.2f}%)\n")

# Hit@K 분포
hit_rank_dist = defaultdict(int)
for r in results:
    hit_rank = r.get('hit_rank')
    if hit_rank and hit_rank != -1:
        hit_rank_dist[hit_rank] += 1
    elif r.get('success') == 'X':
        hit_rank_dist['Miss'] += 1

print(f"=== Hit@K 분포 ===")
for rank in sorted([k for k in hit_rank_dist.keys() if isinstance(k, int)]):
    print(f"Hit@{rank}: {hit_rank_dist[rank]}건")
print(f"Miss: {hit_rank_dist['Miss']}건\n")

# classified_domains 개수 분포
domain_count_dist = defaultdict(int)
for r in results:
    domains = r.get('classified_domains', [])
    if domains:
        domain_count_dist[len(domains)] += 1

print(f"=== Top-K 반환 현황 ===")
for count in sorted(domain_count_dist.keys()):
    print(f"{count}개 반환: {domain_count_dist[count]}건")
print()

# 미분류 케이스 분석
unclassified_cases = []
for r in results:
    classified_domain = r.get('classified_domain', '')
    if classified_domain.startswith('미분류-'):
        unclassified_cases.append(r)

print(f"=== 미분류 케이스 ===")
print(f"총 미분류: {len(unclassified_cases)}건")

# 미분류 원인 분석 (LLM이 반환한 원본 값)
unclassified_reasons = defaultdict(int)
for r in unclassified_cases:
    classified = r.get('classified_domain', '')
    # '미분류-' 다음의 원본 값 추출
    if classified.startswith('미분류-'):
        reason = classified.replace('미분류-', '')
        unclassified_reasons[reason] += 1

print(f"\n미분류 원인 (LLM이 반환한 값) Top 10:")
for reason, count in sorted(unclassified_reasons.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  '{reason}': {count}건")
print()

# 실험 19와 비교를 위한 주요 지표
print(f"=== 실험 19 대비 주요 지표 ===")
print(f"전체 정확도: {success_count/total*100:.2f}%")
print(f"GT 미분류 제외 정확도: {success_in_classified/len(gt_classified)*100:.2f}%")
print(f"미분류 케이스: {len(unclassified_cases)}건 ({len(unclassified_cases)/total*100:.2f}%)")
print(f"Top-1만 반환: {domain_count_dist.get(1, 0)}건")
print(f"Top-2 반환: {domain_count_dist.get(2, 0)}건")
print(f"Top-3 반환: {domain_count_dist.get(3, 0)}건")
