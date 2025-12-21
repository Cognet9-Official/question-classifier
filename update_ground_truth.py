import os
import sys
import pandas as pd
from dotenv import load_dotenv
import logging
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm_classifier import LLMClassifier

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_config():
    load_dotenv()
    llm_provider = os.getenv('LLM_PROVIDER', 'databricks').lower()
    
    llm_config = {}
    if llm_provider == 'databricks':
        llm_config = {
            'url': os.getenv('DATABRICKS_URL'),
            'token': os.getenv('DATABRICKS_TOKEN'),
            'model': os.getenv('DATABRICKS_MODEL', 'databricks-gpt-oss-20b')
        }
    
    return {
        'llm_provider': llm_provider,
        'llm_config': llm_config,
        'domains': [] # 사용 안함
    }

def main():
    print("=== Ground Truth 업데이트 시작 ===")
    
    # 1. Config 로드 & 분류기 초기화
    config = load_config()
    classifier = LLMClassifier(
        provider=config['llm_provider'],
        config=config['llm_config'],
        domains=[],
        timeout=30
    )
    
    # 2. 엑셀 파일 로드
    input_file = 'input/input.xlsx'
    try:
        df = pd.read_excel(input_file)
        print(f"파일 로드 완료: {len(df)}건")
    except Exception as e:
        print(f"파일 로드 실패: {e}")
        return

    # 3. 분류 실행 (전수 조사)
    results = []
    
    total_count = len(df)
    for index, row in df.iterrows():
        question = row['Question']
        
        # 분류 실행
        domain, opinion, opinion_category = classifier.classify(question)
        
        # 결과 저장
        results.append(domain)
        
        # 진행상황 로그
        if (index + 1) % 10 == 0:
            print(f"진행 중: {index + 1}/{total_count} ({(index + 1)/total_count*100:.1f}%)")

    # 4. 데이터프레임 업데이트
    df['도메인 Ground Truth'] = results
    
    # 5. 저장
    output_file = 'input/input_new_gt.xlsx'
    df.to_excel(output_file, index=False)
    print(f"저장 완료: {output_file}")
    
    classifier.close()

if __name__ == "__main__":
    main()
