# 도메인 분류 실험 기록

## 실험 1~17 (요약)

- 기존 21개 Ground Truth(GT)의 모호함으로 인해 정확도 40%대에서 정체.
- 실험 16, 17을 통해 **Micro-Intent(세부 의도)** 방식이 LLM에게 훨씬 효과적임을 입증.
- 이에 따라 전체 데이터셋(695개)의 GT를 42개 Micro-Intent로 전면 재정의함 (`input/input_new_gt.xlsx`).

---

## 실험 18: 새로운 Ground Truth (Micro-Intent) 검증

- **날짜**: 2025-12-21 (진행 예정)
- **목표**: 재정의된 42개 Micro-Intent 체계에서의 분류 정확도 및 재현성 검증.
- **변경 사항**:
  - **입력 데이터**: `input/input.xlsx` (구 GT) -> `input/input_new_gt.xlsx` (신 GT: 42개 의도)
  - **평가 기준**: 기존 21개 도메인이 아닌, 42개 Micro-Intent 일치 여부로 평가.
  - **참고**: GT 자체가 LLM을 통해 생성되었으므로(Distillation), 이번 실험은 일종의 **Self-Consistency(자기 일관성)** 테스트 성격을 가짐. 높은 정확도가 기대됨.
- **예상 이슈**:
  - `미분류-{의도}`로 태깅된 데이터는 오답 처리될 가능성이 높음.
  - LLM의 비결정성으로 인해 GT 생성 시점과 다른 응답이 나올 수 있음.
- **실행 계획**:
  - 샘플링 없이 전체 데이터(혹은 50개 샘플)를 대상으로 테스트 수행.
  - 입력 파일 변경: `python main.py -i input/input.xlsx -n 50`
