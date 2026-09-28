import pandas as pd
import numpy as np
import random

# -----------------------------------------------------------------------------
# 1. 설정 및 데이터 로드
# -----------------------------------------------------------------------------
TRAIN_FILE = "../data/training_dataset.csv"
OUTPUT_FILE = "../data/full_coverage_cases.csv"

# 랜덤 시드 고정
np.random.seed(42)
random.seed(42)

# -----------------------------------------------------------------------------
# 2. mqtt_listener.py의 로직 그대로 가져오기 (WIND_CHILL_DATA 포함)
# -----------------------------------------------------------------------------
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
    temp_data = WIND_CHILL_DATA.get(rounded_temp)
    if temp_data is None:
        return None
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


# -----------------------------------------------------------------------------
# 3. 데이터 생성 로직
# -----------------------------------------------------------------------------

try:
    df_train = pd.read_csv(TRAIN_FILE)
    # 정상 데이터 분포 추출
    real_temp_mean = df_train["mean.WristT_5"].mean() + 1
    real_temp_std = df_train["mean.WristT_5"].std() - 1
    real_hr_mean = df_train["mean.hr_5"].mean()
    real_hr_std = df_train["mean.hr_5"].std()
    print(
        f">> [학습 통계] 체온: {real_temp_mean:.2f}±{real_temp_std:.2f}, 심박: {real_hr_mean:.2f}±{real_hr_std:.2f}"
    )
except FileNotFoundError:
    print(f"[오류] '{TRAIN_FILE}' 없음. 기본값 사용.")
    real_temp_mean, real_temp_std = 33.0, 1.5
    real_hr_mean, real_hr_std = 75.0, 10.0


def generate_normal(n=100):
    """정상 데이터: 학습 데이터 분포 + 쾌적한 환경"""
    data = []
    for _ in range(n):
        bt = np.random.normal(real_temp_mean, real_temp_std)
        hr = np.random.normal(real_hr_mean, real_hr_std)
        et = np.random.uniform(18.0, 26.0)
        eh = np.random.uniform(30.0, 60.0)
        data.append([bt, hr, et, eh, "정상"])
    return data


def generate_risk_cases(n_per_case=20):
    data = []

    # ---------------------------------------------------------
    # 1. 저체온증 위험
    # 조건: e_temp <= 4.0 AND b_temp <= (0.09073 * e_temp) + 33.0
    # ---------------------------------------------------------
    for _ in range(n_per_case):
        et = np.random.uniform(-10.0, 4.0)
        eh = np.random.uniform(20.0, 60.0)
        limit_bt = (0.09073 * et) + 33.0
        # 조건 만족
        bt = np.random.uniform(limit_bt - 6.0, limit_bt - 0.1)
        hr = np.random.normal(real_hr_mean, 5)  # 심박은 정상
        data.append([bt, hr, et, eh, "저체온증 위험"])

    # ---------------------------------------------------------
    # 2. 일사병 위험
    # 조건: effective_env_temp >= 31.0 AND b_temp >= (0.09073 * effective_env_temp) + 35.0
    # ※ 주의: get_wind_chill 내부의 round() 로직을 고려하여 생성해야 함
    # ---------------------------------------------------------
    count = 0
    while count < n_per_case:
        # 테이블에 존재하는 Key(온도)와 Key(습도)를 랜덤 선택
        t_key = random.choice(list(WIND_CHILL_DATA.keys()))  # 25~40
        h_key = random.choice(list(WIND_CHILL_DATA[t_key].keys()))  # 25~100 (5단위)

        # 해당 조합의 체감온도 조회
        eff_temp = WIND_CHILL_DATA[t_key][h_key]

        # 체감온도가 31도 이상인 조합만 사용
        if eff_temp >= 31.0:
            # 실제 입력값은 round()되어 키값이 되도록 노이즈 추가
            et = float(t_key) + np.random.uniform(-0.4, 0.4)
            eh = float(h_key) + np.random.uniform(-2.0, 2.0)

            # 체온 임계값 계산 (정확한 함수 호출)
            calculated_eff_temp = get_effective_env_temp(et, eh)
            limit_bt = (0.09073 * calculated_eff_temp) + 35.0

            # 조건 만족: 임계값보다 높게 설정
            bt = np.random.uniform(limit_bt + 0.1, limit_bt + 2.0)
            hr = np.random.normal(90, 5)  # 심박은 약간 높음

            data.append([bt, hr, et, eh, "일사병 위험"])
            count += 1

    # ---------------------------------------------------------
    # 3. 저체온 및 서맥 (우선순위 높음)
    # 조건: b_temp <= 33 AND hr < 50
    # ---------------------------------------------------------
    for _ in range(n_per_case):
        bt = np.random.uniform(25.0, 33.0)
        hr = np.random.uniform(30.0, 49.9)
        et = 20.0
        eh = 50.0
        data.append([bt, hr, et, eh, "저체온 및 서맥 위험"])

    # ---------------------------------------------------------
    # 4. 고체온 및 빈맥
    # 조건: b_temp >= 35 AND hr > 100
    # ---------------------------------------------------------
    for _ in range(n_per_case):
        bt = np.random.uniform(35.0, 39.0)
        hr = np.random.uniform(100.1, 150.0)
        et = 25.0
        eh = 50.0
        data.append([bt, hr, et, eh, "고체온 및 빈맥 위험"])

    # ---------------------------------------------------------
    # 5. 단순 저체온 (위 조건들 통과 후)
    # 조건: b_temp <= 33
    # ---------------------------------------------------------
    for _ in range(n_per_case):
        bt = np.random.uniform(25.0, 33.0)
        hr = np.random.uniform(60.0, 90.0)  # 심박 정상
        et = 15.0
        eh = 50.0
        data.append([bt, hr, et, eh, "저체온"])

    # ---------------------------------------------------------
    # 6. 단순 고체온
    # 조건: b_temp >= 35
    # ---------------------------------------------------------
    for _ in range(n_per_case):
        bt = np.random.uniform(35.0, 38.0)
        hr = np.random.uniform(60.0, 90.0)  # 심박 정상
        et = 25.0
        eh = 50.0
        data.append([bt, hr, et, eh, "고체온"])

    # ---------------------------------------------------------
    # 7. 빈맥 위험
    # 조건: hr > 100
    # ---------------------------------------------------------
    for _ in range(n_per_case):
        bt = np.random.normal(real_temp_mean, 0.5)
        if bt <= 33 or bt >= 35:
            bt = 34.0  # 다른 조건 간섭 방지
        hr = np.random.uniform(100.1, 140.0)
        et = 25.0
        eh = 50.0
        data.append([bt, hr, et, eh, "빈맥 위험"])

    # ---------------------------------------------------------
    # 8. 서맥 위험
    # 조건: hr < 50
    # ---------------------------------------------------------
    for _ in range(n_per_case):
        bt = np.random.normal(real_temp_mean, 0.5)
        if bt <= 33 or bt >= 35:
            bt = 34.0  # 다른 조건 간섭 방지
        hr = np.random.uniform(35.0, 49.9)
        et = 25.0
        eh = 50.0
        data.append([bt, hr, et, eh, "서맥 위험"])

    return data


# ---------------------------------------------------------
# 4. 저장
# ---------------------------------------------------------
normal_data = generate_normal(n=2000)
risk_data = generate_risk_cases(n_per_case=300)

all_data = normal_data + risk_data
df_result = pd.DataFrame(
    all_data,
    columns=["body_temp", "heart_rate", "env_temp", "env_humidity", "true_label"],
)
df_result = df_result.sample(frac=1).reset_index(drop=True)

df_result.to_csv(OUTPUT_FILE, index=False)
print(f"\n>> [생성 완료] {OUTPUT_FILE}")
print(f">> 총 {len(df_result)}개 데이터")
print(df_result["true_label"].value_counts())
