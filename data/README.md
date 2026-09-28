# data

`full_coverage_cases.csv`는 `testing/make_tc.py`가 만든 합성 검증 세트이고 저장소에 포함되어 있다.

`training_dataset.csv`는 제3자 연구 데이터셋이라 포함하지 않는다.
`training/`과 `testing/` 스크립트를 돌리려면 원 출처에서 내려받아 이 디렉터리에 같은 이름으로 두면 된다.

코드가 실제로 참조하는 컬럼은 네 개다.

| 컬럼 | 용도 |
|---|---|
| `mean.WristT_5` | 손목 온도. Isolation Forest 학습 입력 |
| `mean.hr_5` | 심박. Isolation Forest 학습 입력 |
| `mean.Temperature_60` | 환경 온도. 회귀 분석 |
| `mean.Humidity_60` | 환경 습도. 회귀 분석 |
