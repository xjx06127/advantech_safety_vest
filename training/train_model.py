"""
[Train Model] 2D AI 모델 훈련 (체온, 심박수)
설명: 정상 데이터셋에서 '체온'과 '심박수'의 정상 패턴만 학습합니다.
환경 변수는 학습하지 않으므로, 낯선 환경에서도 체온/심박이 정상이면 '정상'으로 판단하지만,
환경 적응으로 체온이 변하면 '이상치'로 판단하여 2차 휴리스틱으로 넘깁니다.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
import joblib

print("--- [훈련 시작] 2D AI 모델 (BodyTemp, HeartRate) ---")

# 1. 데이터 로드
try:
    df = pd.read_csv("../data/training_dataset.csv")
    print(f">> 데이터 로드 성공: {len(df)} 행")
except FileNotFoundError:
    print("[오류] '../data/training_dataset.csv' 파일이 없습니다.")
    exit()

# 2. 학습에 사용할 2가지 특징 선택 (환경 변수 제외!)
# mean.WristT_5 -> body_temp
# mean.hr_5     -> heart_rate
train_df = pd.DataFrame()
train_df["body_temp"] = df["mean.WristT_5"]
train_df["heart_rate"] = df["mean.hr_5"]

# 3. 결측치 제거
original_len = len(train_df)
train_df = train_df.dropna()
print(f">> 결측치 제거: {original_len} -> {len(train_df)} 샘플 사용")

if train_df.empty:
    print("[오류] 학습할 유효한 데이터가 없습니다.")
    exit()

# 4. 데이터 스케일링 (StandardScaler)
# 체온(30~36)과 심박(60~100)의 단위 차이를 맞춤
scaler = StandardScaler()
X_train = scaler.fit_transform(train_df)
print(">> 데이터 스케일링 완료")

# 5. Isolation Forest 모델 학습
print(">> 모델 학습 중 (Isolation Forest)...")
model = IsolationForest(n_estimators=200, contamination="auto", random_state=42)
model.fit(X_train)

# 6. 모델 및 스케일러 저장
joblib.dump(scaler, "../server/scaler.joblib")
joblib.dump(model, "../server/model.joblib")

print("\n[훈련 완료]")
print(">> 'scaler.joblib' 저장됨")
print(">> 'model.joblib' 저장됨")
print("이제 mqtt_listener.py를 실행하세요.")
