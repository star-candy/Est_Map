# 강화학습 모델

`q_policy_summer.joblib`은 저장소의 합성 보행 부분 그래프에서 실제 episode를 실행해
학습한 tabular Q-learning Q-table이다. 기본 지원 구간은 `서울시청 → 광화문`, 모드는
`여름`이다. 대응하는 JSON 파일에는 seed, hyperparameter, graph fingerprint 및 학습
전후 평가가 기록된다.

그래프, 모드 또는 출도착이 모델 metadata와 다르거나 추론이 실패하면 앱은 weighted
A*를 사용한다. 이 정책은 합성 지표를 대상으로 하며 실제 경로 안전성을 보장하지 않는다.

재학습:

```powershell
python -m scripts.train_rl
```
