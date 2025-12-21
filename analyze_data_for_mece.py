import pandas as pd
from collections import Counter
import re

def analyze_data():
    # 엑셀 파일 로드
    try:
        df = pd.read_excel('input/input.xlsx')
    except Exception as e:
        print(f"파일 로드 실패: {e}")
        return

    # 컬럼명 매핑
    col_q = 'Question'
    col_gt = '도메인 Ground Truth'
    
    # 21개 도메인별 질문 그룹화
    domains = df[col_gt].unique()
    
    print(f"\n총 {len(domains)}개 Ground Truth 도메인 발견")
    
    domain_analysis = {}

    for domain in domains:
        questions = df[df[col_gt] == domain][col_q].tolist()
        
        # 키워드 추출 (간단하게 명사형 단어 위주로 2글자 이상)
        words = []
        for q in questions:
            if not isinstance(q, str): continue
            # 특수문자 제거 및 공백 기준 분리
            w_list = re.sub(r'[^\w\s]', '', q).split()
            words.extend([w for w in w_list if len(w) >= 2])
            
        common_words = Counter(words).most_common(5)
        
        domain_analysis[domain] = {
            'count': len(questions),
            'samples': questions[:8],  # 8개 샘플 확인
            'keywords': common_words
        }

    # 분석 결과 출력 (도메인 이름순 정렬)
    print("="*80)
    for domain in sorted(domain_analysis.keys()):
        info = domain_analysis[domain]
        print(f"\n[{domain}] (총 {info['count']}건)")
        print(f"  Top Keywords: {', '.join([f'{w}({c})' for w, c in info['keywords']])}")
        print("  Sample Questions:")
        for i, q in enumerate(info['samples'], 1):
            print(f"    {i}. {q}")
            
if __name__ == "__main__":
    analyze_data()
