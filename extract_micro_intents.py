import pandas as pd
from collections import Counter
import re

def extract_intents():
    try:
        df = pd.read_excel('input/input.xlsx')
    except Exception as e:
        print(f"파일 로드 실패: {e}")
        return

    col_q = 'Question'
    questions = df[col_q].dropna().tolist()
    
    # 2글자 이상 명사/동사 추출을 위한 간단한 토크나이징 (정교하지 않아도 됨)
    words = []
    for q in questions:
        # 특수문자 제거
        clean_q = re.sub(r'[^\w\s]', '', q)
        # 어절 단위 분리
        tokens = clean_q.split()
        # 2-gram (연속된 두 단어) 생성하여 문맥 파악
        if len(tokens) >= 2:
            for i in range(len(tokens)-1):
                words.append(f"{tokens[i]} {tokens[i+1]}")
        words.extend(tokens)

    # 빈도수 상위 키워드/구문 추출
    common_phrases = Counter(words).most_common(100)
    
    print("=== 상위 빈도 키워드/구문 (Micro-Intent 후보) ===")
    for phrase, count in common_phrases:
        print(f"{phrase}: {count}")

if __name__ == "__main__":
    extract_intents()
