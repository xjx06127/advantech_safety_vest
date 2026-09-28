import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import os
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, classification_report, roc_curve, auc
from matplotlib.colors import ListedColormap

# =============================================================================
# [설정] 파일 경로 및 폰트 설정
# =============================================================================
TRAIN_FILE = "../data/training_dataset.csv"
TEST_FILE = "../data/full_coverage_cases.csv"  # 또는 full_coverage_cases_noisy.csv
MODEL_FILE = "../server/model.joblib"
SCALER_FILE = "../server/scaler.joblib"

# 한글 폰트 설정 (환경에 맞게 수정 필요)
plt.rc("font", family="NanumBarunGothic")
plt.rcParams["axes.unicode_minus"] = False

# =============================================================================
# [로직 복사] mqtt_listener.py의 휴리스틱 함수들 (Raw Data 기준)
# =============================================================================
WIND_CHILL_DATA = {
    25: {
        25: 22.2,
        30: 22.8,
        35: 23.3,
        40: 23.8,
        45: 24.2,
        50: 24.6,
        55: 25.1,
        60: 25.5,
        65: 25.9,
        70: 26.2,
        75: 26.6,
        80: 27.0,
        85: 27.3,
        90: 27.7,
        95: 28.0,
        100: 28.4,
    },
    26: {
        25: 23.1,
        30: 23.7,
        35: 24.2,
        40: 24.7,
        45: 25.2,
        50: 25.6,
        55: 26.0,
        60: 26.5,
        65: 26.9,
        70: 27.2,
        75: 27.6,
        80: 28.0,
        85: 28.4,
        90: 28.7,
        95: 29.1,
        100: 29.4,
    },
    27: {
        25: 24.0,
        30: 24.6,
        35: 25.2,
        40: 25.7,
        45: 26.1,
        50: 26.6,
        55: 26.0,
        60: 27.5,
        65: 27.9,
        70: 28.2,
        75: 28.6,
        80: 29.0,
        85: 29.4,
        90: 29.7,
        95: 30.1,
        100: 30.5,
    },
    28: {
        25: 24.9,
        30: 25.5,
        35: 26.1,
        40: 26.6,
        45: 27.0,
        50: 27.5,
        55: 28.0,
        60: 28.4,
        65: 28.9,
        70: 29.3,
        75: 29.7,
        80: 30.0,
        85: 30.4,
        90: 30.8,
        95: 31.1,
        100: 31.5,
    },
    29: {
        25: 25.8,
        30: 26.5,
        35: 27.0,
        40: 27.6,
        45: 28.1,
        50: 28.6,
        55: 29.0,
        60: 29.4,
        65: 29.9,
        70: 30.3,
        75: 30.7,
        80: 31.1,
        85: 31.4,
        90: 31.8,
        95: 32.2,
        100: 32.6,
    },
    30: {
        25: 26.7,
        30: 27.4,
        35: 28.0,
        40: 28.5,
        45: 29.0,
        50: 29.5,
        55: 30.0,
        60: 30.4,
        65: 30.9,
        70: 31.3,
        75: 31.7,
        80: 32.1,
        85: 32.5,
        90: 32.9,
        95: 33.2,
        100: 33.6,
    },
    31: {
        25: 27.6,
        30: 28.3,
        35: 28.9,
        40: 29.4,
        45: 30.0,
        50: 30.5,
        55: 31.0,
        60: 31.4,
        65: 31.9,
        70: 32.3,
        75: 32.7,
        80: 33.1,
        85: 33.5,
        90: 33.9,
        95: 34.3,
        100: 34.6,
    },
    32: {
        25: 28.5,
        30: 29.2,
        35: 29.8,
        40: 30.4,
        45: 31.0,
        50: 31.5,
        55: 32.0,
        60: 32.4,
        65: 32.9,
        70: 33.3,
        75: 33.7,
        80: 34.1,
        85: 34.5,
        90: 34.9,
        95: 35.3,
        100: 35.7,
    },
    33: {
        25: 29.5,
        30: 30.2,
        35: 30.8,
        40: 31.4,
        45: 32.0,
        50: 32.5,
        55: 33.0,
        60: 33.5,
        65: 33.9,
        70: 34.3,
        75: 34.8,
        80: 35.2,
        85: 35.6,
        90: 36.0,
        95: 36.4,
        100: 36.7,
    },
    34: {
        25: 30.4,
        30: 31.1,
        35: 31.8,
        40: 32.4,
        45: 32.9,
        50: 33.5,
        55: 34.0,
        60: 34.5,
        65: 34.9,
        70: 35.4,
        75: 35.8,
        80: 36.2,
        85: 36.6,
        90: 37.0,
        95: 37.4,
        100: 37.8,
    },
    35: {
        25: 31.3,
        30: 32.0,
        35: 32.7,
        40: 33.3,
        45: 33.9,
        50: 34.5,
        55: 35.0,
        60: 35.5,
        65: 35.9,
        70: 36.4,
        75: 36.8,
        80: 37.2,
        85: 37.7,
        90: 38.1,
        95: 38.5,
        100: 38.9,
    },
    36: {
        25: 32.2,
        30: 33.0,
        35: 33.7,
        40: 34.3,
        45: 34.9,
        50: 35.4,
        55: 36.0,
        60: 36.5,
        65: 36.9,
        70: 37.4,
        75: 37.8,
        80: 38.3,
        85: 38.7,
        90: 39.1,
        95: 39.5,
        100: 40.0,
    },
    37: {
        25: 33.1,
        30: 33.9,
        35: 34.6,
        40: 35.3,
        45: 35.9,
        50: 36.4,
        55: 37.0,
        60: 37.5,
        65: 38.0,
        70: 38.4,
        75: 38.9,
        80: 39.3,
        85: 39.7,
        90: 40.2,
        95: 40.6,
        100: 41.0,
    },
    38: {
        25: 34.0,
        30: 34.8,
        35: 35.6,
        40: 36.2,
        45: 36.9,
        50: 37.4,
        55: 38.0,
        60: 38.5,
        65: 39.0,
        70: 39.5,
        75: 39.9,
        80: 40.4,
        85: 40.8,
        90: 41.2,
        95: 41.6,
        100: 42.0,
    },
    39: {
        25: 35.0,
        30: 35.8,
        35: 36.5,
        40: 37.2,
        45: 37.8,
        50: 38.4,
        55: 39.0,
        60: 39.5,
        65: 40.0,
        70: 40.5,
        75: 40.9,
        80: 41.4,
        85: 41.8,
        90: 42.3,
        95: 42.7,
        100: 43.1,
    },
    40: {
        25: 35.9,
        30: 36.7,
        35: 37.5,
        40: 38.2,
        45: 38.8,
        50: 39.4,
        55: 40.0,
        60: 40.5,
        65: 41.0,
        70: 41.5,
        75: 42.0,
        80: 42.4,
        85: 42.8,
        90: 43.3,
        95: 43.7,
        100: 44.1,
    },
}


def get_wind_chill(env_temp, env_humidity):
    rounded_temp = int(round(env_temp))
    if rounded_temp < 25 or rounded_temp > 40:
        return None
    temp_data = WIND_CHILL_DATA.get(rounded_temp, {})

    rounded_humidity = int(round(env_humidity / 5.0) * 5)
    if rounded_humidity < 25:
        return None
    if rounded_humidity > 100:
        rounded_humidity = 100
    return temp_data.get(rounded_humidity)


def get_effective_env_temp(env_temp, env_humidity):
    if env_temp >= 25.0:
        wind_chill = get_wind_chill(env_temp, env_humidity)
        return wind_chill if wind_chill is not None else env_temp
    else:
        return env_temp


def analyze_risk_heuristics(row):
    """Raw Data 기준 판단"""
    b_temp = row["body_temp"]
    hr = row["heart_rate"]
    e_temp = row["env_temp"]
    e_humi = row["env_humidity"]

    # [설정] 원래의 고정 임계값 (33.0 / 35.0)
    LOW_TEMP_TH_FIXED = 33.0
    HIGH_TEMP_TH_FIXED = 35.0

    effective_env_temp = get_effective_env_temp(e_temp, e_humi)
    LOW_ENV_TEMP_THRESHOLD = 4.0
    HIGH_EFFECTIVE_ENV_THRESHOLD = 31.0

    # 1. 저체온증 위험 (동적 기준)
    min_safe_wrist_temp = (0.09073 * e_temp) + LOW_TEMP_TH_FIXED
    if e_temp <= LOW_ENV_TEMP_THRESHOLD and b_temp <= min_safe_wrist_temp:
        return "이상"  # (세부: 저체온증 위험)

    # 2. 일사병 위험 (동적 기준)
    max_safe_wrist_temp = (0.09073 * effective_env_temp) + HIGH_TEMP_TH_FIXED
    if (
        effective_env_temp >= HIGH_EFFECTIVE_ENV_THRESHOLD
        and b_temp >= max_safe_wrist_temp
    ):
        return "이상"  # (세부: 일사병 위험)

    # 3. 복합/단일 위험 (고정 기준)
    if b_temp <= LOW_TEMP_TH_FIXED or b_temp >= HIGH_TEMP_TH_FIXED:
        return "이상"

    if hr < 50 or hr > 100:
        return "이상"

    return "정상"


# =============================================================================
# [함수] 모델 학습 또는 로드
# =============================================================================
def get_model_and_scaler():
    if os.path.exists(MODEL_FILE) and os.path.exists(SCALER_FILE):
        print(f">> [System] 기존 모델({MODEL_FILE})을 로드합니다.")
        model = joblib.load(MODEL_FILE)
        scaler = joblib.load(SCALER_FILE)
    else:
        print(f">> [System] 모델 파일이 없습니다. '{TRAIN_FILE}'로 새로 학습합니다.")
        try:
            train_df = pd.read_csv(TRAIN_FILE)
            X_train = train_df[["mean.WristT_5", "mean.hr_5"]].copy()
            X_train.columns = ["body_temp", "heart_rate"]

            # [변경] Offset 제거: 있는 그대로 학습
            X_train = X_train.dropna()

            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)

            # Isolation Forest (contamination=0.01 가정)
            model = IsolationForest(contamination=0.01, random_state=42)
            model.fit(X_train_scaled)

            # 저장 (선택 사항)
            # joblib.dump(model, MODEL_FILE)
            # joblib.dump(scaler, SCALER_FILE)
            print(">> [System] 학습 완료.")
        except FileNotFoundError:
            print(f"[Error] '{TRAIN_FILE}' 파일이 없어 학습할 수 없습니다.")
            exit()
    return model, scaler


# =============================================================================
# [함수] 하이브리드 예측 (Binary Class: 정상/비정상)
# =============================================================================
def predict_binary(df, model, scaler):
    # 테스트 데이터 준비 (Offset 제거)
    X_test = df[["body_temp", "heart_rate"]].copy()
    X_scaled = scaler.transform(X_test)

    # AI 점수
    ai_raw_scores = model.decision_function(X_scaled)
    ai_preds = model.predict(X_scaled)  # 1: 정상, -1: 이상

    final_preds = []
    risk_scores = []

    for i in range(len(df)):
        row = df.iloc[i]
        base_score = -ai_raw_scores[i]  # 높을수록 이상치

        # 1. AI 판단
        if ai_preds[i] == 1:
            final_status = "정상"
            final_score = base_score
        else:
            # AI 이상 -> 2. 휴리스틱 체크
            heuristic_result = analyze_risk_heuristics(row)
            final_status = heuristic_result  # "정상" 또는 "비정상"

            if final_status == "정상":
                final_score = base_score - 2.0
            else:
                final_score = base_score + 2.0

        final_preds.append(final_status)
        risk_scores.append(final_score)

    return final_preds, risk_scores


# =============================================================================
# [Main] 실행
# =============================================================================
if __name__ == "__main__":
    # 1. 모델 준비 (로드 또는 학습)
    model, scaler = get_model_and_scaler()

    # 2. TC 로드
    if not os.path.exists(TEST_FILE):
        print(f"[Error] TC 파일({TEST_FILE})이 없습니다.")
        exit()

    test_df = pd.read_csv(TEST_FILE)
    print(f">> [Test] {len(test_df)}개 데이터 진단 중...")

    # 3. 정답 라벨 이진화 (정상 vs 비정상)
    y_true_binary = test_df["true_label"].apply(
        lambda x: "정상" if x == "정상" else "이상"
    )

    # 4. 예측 수행
    y_pred, y_scores = predict_binary(test_df, model, scaler)

    # =========================================================================
    # 5. [커스텀] Confusion Matrix 시각화 (Reference 1.png 스타일)
    # =========================================================================
    labels = ["정상", "이상"]
    cm = confusion_matrix(y_true_binary, y_pred, labels=labels)
    # cm 구조: [[TN, FP], [FN, TP]] (정상=0, 비정상=1 기준)

    # 레퍼런스 이미지 컬러 (파랑, 노랑, 분홍, 파랑)
    # 1행 1열(TN): 파랑, 1행 2열(FP): 노랑
    # 2행 1열(FN): 분홍, 2행 2열(TP): 파랑
    color_matrix = np.array(
        [
            [
                [0 / 255, 84 / 255, 159 / 255],
                [255 / 255, 210 / 255, 165 / 255],
            ],  # Row 1: TN(Blue), FP(Yellow)
            [
                [210 / 255, 160 / 255, 166 / 255],
                [0 / 255, 84 / 255, 159 / 255],
            ],  # Row 2: FN(Pink), TP(Blue)
        ]
    )

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(color_matrix, aspect="auto")

    # 숫자 텍스트 추가 (배경색에 따라 글자색 조정)
    for i in range(2):
        for j in range(2):
            count = cm[i, j]
            # TN(0,0)과 TP(1,1)은 파란배경이므로 흰색 텍스트가 잘 보일 수 있으나
            # 레퍼런스 이미지는 흰색 숫자로 보임.
            text_color = "white" if (i == j) else "black"
            ax.text(
                j,
                i,
                str(count),
                ha="center",
                va="center",
                color=text_color,
                fontsize=24,
                fontweight="bold",
            )

    # 타이틀
    ax.set_title("Confusion Matrix (혼동 행렬)", fontsize=16, fontweight="bold", pad=20)

    # 축 눈금 제거
    ax.set_xticks([])
    ax.set_yticks([])

    # 외부 라벨 (Reference 스타일)
    # 좌측 (True Label 설명)
    plt.text(
        -0.8,
        0,
        "정상을\n정상으로 판단",
        fontsize=14,
        color="#00549F",
        ha="center",
        va="center",
        fontweight="bold",
    )
    plt.text(
        -0.8,
        1,
        "이상을\n정상으로 판단",
        fontsize=14,
        color="#E74C3C",
        ha="center",
        va="center",
        fontweight="bold",
    )

    # 우측 (Prediction 설명)
    plt.text(
        1.8,
        0,
        "정상을\n이상으로 판단",
        fontsize=14,
        color="#F39C12",
        ha="center",
        va="center",
        fontweight="bold",
    )
    plt.text(
        1.8,
        1,
        "이상을\n정상으로 판단",
        fontsize=14,
        color="#00549F",
        ha="center",
        va="center",
        fontweight="bold",
    )

    plt.tight_layout()
    plt.savefig("../docs/confusion_matrix.png")
    print("\n>> [1] Confusion Matrix (Custom Style) 저장 완료.")

    # =========================================================================
    # 6. [커스텀] ROC Curve 시각화 (Reference 2.png 스타일)
    # =========================================================================
    y_true_num = [0 if label == "정상" else 1 for label in y_true_binary]
    fpr, tpr, thresholds = roc_curve(y_true_num, y_scores)
    roc_auc = auc(fpr, tpr)

    # 최적 임계값 (Youden Index) 찾기 - 빨간 점 표시용
    optimal_idx = np.argmax(tpr - fpr)
    optimal_threshold = thresholds[optimal_idx]
    opt_fpr = fpr[optimal_idx]
    opt_tpr = tpr[optimal_idx]

    plt.figure(figsize=(8, 6))

    # 메인 ROC 커브 (주황색, 두껍게)
    plt.plot(
        fpr, tpr, color="darkorange", lw=4, label=f"Hybrid AI (AUC = {roc_auc:.3f})"
    )

    # 랜덤 챈스 대각선 (남색, 점선)
    plt.plot([0, 1], [0, 1], color="navy", lw=2, linestyle="--", label="Random Chance")

    # 선택된 임계값 지점 (빨간 점)
    plt.scatter(
        opt_fpr, opt_tpr, color="red", s=200, zorder=10, label="Selected Threshold"
    )

    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.02])

    # 축 라벨 (굵고 크게)
    plt.xlabel("오경보율(FPR)", fontsize=16, fontweight="bold", labelpad=10)
    plt.ylabel("감지 성공률 (TPR)", fontsize=16, fontweight="bold", labelpad=10)

    # 타이틀
    plt.title("ROC Curve", fontsize=20, fontweight="bold", pad=20)

    # 범례
    plt.legend(loc="lower right", fontsize=12, framealpha=0.9)

    # 그리드 (연하게)
    plt.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig("../docs/roc_curve.png")
    print(">> [2] ROC Curve (Custom Style) 저장 완료.")

    print("\n--- Classification Report ---")
    print(classification_report(y_true_binary, y_pred, target_names=labels))
