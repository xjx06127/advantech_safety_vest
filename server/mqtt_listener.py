# mqtt_listener.py (최종: 15초 위치 고정 + 2D/4D 진단 + 로그 저장)

import os
import paho.mqtt.client as mqtt
import json
import joblib
import pandas as pd
import numpy as np
import time
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
import mysql.connector
from mysql.connector import Error

# =============================================================================
# [설정] AWS MySQL 데이터베이스 정보
# =============================================================================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "safety"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": "safety_db",
    "port": 3306,
}
# 환경 변수 DB_HOST, DB_USER, DB_PASSWORD 로 접속 정보를 지정한다.

GLOBAL_DB_CONNECTION = None

# =============================================================================
# [설정] 위치 고정(Lock) 설정
# =============================================================================
# 작업자별 위치 잠금 상태 저장 { "mcu_id": {"name": "환경1", "temp": 25.0, "humi": 60.0, "expiry": 12345678} }
location_locks = {}
LOCK_DURATION = 15.0  # 한번 위치 잡히면 15초 동안은 절대 안 바뀜

WORKER_NAME_MAP = {
    "AA:BB:CC:DD:EE:01": "작업자 1",  # 실제 MAC 주소로 변경
    "AA:BB:CC:DD:EE:02": "작업자 2",
    "AA:BB:CC:DD:EE:03": "작업자 3",
}


# =============================================================================
# [DB 함수] 테이블 생성 및 데이터 저장
# =============================================================================
def init_db():
    """프로그램 시작 시 테이블 초기화"""
    global GLOBAL_DB_CONNECTION  # 전역 변수 사용 선언
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            cursor = conn.cursor()

            # 1. 현재 상태 저장용 (덮어쓰기)
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS worker_status (
                mcu_id VARCHAR(50) PRIMARY KEY,
                env_location VARCHAR(50),
                env_temp FLOAT,
                env_humidity FLOAT,
                body_temp FLOAT,
                heart_rate INT,
                is_fell BOOLEAN,
                analysis_result VARCHAR(100),
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
            )

            # 2. 이력 저장용 (계속 쌓기, 온습도 포함)
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS vest_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                mcu_id VARCHAR(50),
                env_location VARCHAR(50),
                env_temp FLOAT,
                env_humidity FLOAT,
                body_temp FLOAT,
                heart_rate INT,
                is_fell BOOLEAN,
                analysis_result VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            )
            conn.commit()
            print(">> [DB] 테이블 초기화 완료 (worker_status, vest_log)")
    except Error as e:
        print(f"[DB 초기화 오류] {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

    # 2. 전역 연결을 생성하고 유지
    try:
        GLOBAL_DB_CONNECTION = mysql.connector.connect(**DB_CONFIG)
        print(">> [DB] 영구 연결 생성 성공.")
    except Error as e:
        print(f"[DB 치명적 오류] 영구 연결 실패: {e}")
        exit()  # 연결 없이는 프로그램 종료


def save_worker_status_to_db(conn, mcu_id, location, et, eh, bt, hr, fell, result):
    """[현재 상태] worker_status 테이블에 Upsert"""
    try:
        if conn.is_connected():
            cursor = conn.cursor()
            sql = """
            INSERT INTO worker_status 
            (mcu_id, env_location, env_temp, env_humidity, body_temp, heart_rate, is_fell, analysis_result)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                env_location = VALUES(env_location),
                env_temp = VALUES(env_temp),
                env_humidity = VALUES(env_humidity),
                body_temp = VALUES(body_temp),
                heart_rate = VALUES(heart_rate),
                is_fell = VALUES(is_fell),
                analysis_result = VALUES(analysis_result),
                last_updated = CURRENT_TIMESTAMP
            """
            val = (mcu_id, location, et, eh, bt, hr, fell, result)
            cursor.execute(sql, val)
            conn.commit()
    except Error as e:
        print(f"[DB 상태 저장 오류] {e}")
    finally:
        if "cursor" in locals() and cursor:  # cursor가 정의되고 존재할 때만 닫기
            cursor.close()


def save_vest_log_to_db(conn, mcu_id, location, et, eh, bt, hr, fell, result):
    """[과거 이력] vest_log 테이블에 Insert (온습도 포함)"""
    try:
        if conn.is_connected():
            cursor = conn.cursor()
            sql = """
            INSERT INTO vest_log 
            (mcu_id, env_location, env_temp, env_humidity, body_temp, heart_rate, is_fell, analysis_result)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            val = (mcu_id, location, et, eh, bt, hr, fell, result)
            cursor.execute(sql, val)
            conn.commit()
    except Error as e:
        print(f"[DB 로그 저장 오류] {e}")
    finally:
        if "cursor" in locals() and cursor:
            cursor.close()


print("--- [서버 시작] 하이브리드 위험 예측 시스템 (위치 고정 Ver) ---")
print(">> 모델과 스케일러를 로드합니다...")


# =============================================================================
# 파트 1: 휴리스틱 진단 로직 (2차 필터)
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


def analyze_risk_heuristics(row):
    b_temp = row["body_temp"]
    hr = row["heart_rate"]
    e_temp = row["env_temp"]
    e_humi = row["env_humidity"]
    effective_env_temp = get_effective_env_temp(e_temp, e_humi)
    min_safe_wrist_temp = (0.09073 * e_temp) + 33.0
    LOW_ENV_TEMP_THRESHOLD = 4.0

    if e_temp <= LOW_ENV_TEMP_THRESHOLD and b_temp <= min_safe_wrist_temp:
        return f"저체온증 위험"

    max_safe_wrist_temp = (0.09073 * effective_env_temp) + 35.0
    HIGH_EFFECTIVE_ENV_THRESHOLD = 31.0

    if (
        effective_env_temp >= HIGH_EFFECTIVE_ENV_THRESHOLD
        and b_temp >= max_safe_wrist_temp
    ):
        return f"일사병 위험"

    if b_temp <= 33 and hr < 50:
        return f"저체온 및 서맥 위험"
    elif b_temp >= 35 and hr > 100:
        return f"고체온 및 빈맥 위험"

    if b_temp <= 33:
        return f"저체온"
    elif b_temp >= 35:
        return f"고체온"

    if hr > 100:
        return f"빈맥 위험"
    elif hr < 50:
        return f"서맥 위험"

    return "SAFE_ADAPTATION"


# =============================================================================
# 파트 2: 하이브리드 예측 함수
# =============================================================================
def predict_hybrid(data_list, fitted_scaler, fitted_model):
    results = []
    df_full = pd.DataFrame(
        data_list, columns=["body_temp", "heart_rate", "env_temp", "env_humidity"]
    )

    for col in df_full.columns:
        if df_full[col].isnull().any() or not np.all(np.isfinite(df_full[col])):
            print(f"[예측 오류] 데이터에 Null/NaN 포함됨: {data_list}")
            return ["DATA_ERROR"]

    X_ai_input = df_full[["body_temp", "heart_rate"]]
    data_scaled = fitted_scaler.transform(X_ai_input)
    anomaly_predictions = fitted_model.predict(data_scaled)

    for i in range(len(df_full)):
        if anomaly_predictions[i] == 1:
            results.append("정상")
        else:
            row = df_full.iloc[i]
            risk_diagnosis = analyze_risk_heuristics(row)
            if risk_diagnosis == "SAFE_ADAPTATION":
                results.append("정상")
            else:
                results.append(risk_diagnosis)
    return results


# =============================================================================
# 파트 3: 저장된 모델 로드
# =============================================================================
try:
    scaler = joblib.load("scaler.joblib")
    model = joblib.load("model.joblib")
    print(">> scaler.joblib, model.joblib 로드 성공.")
except FileNotFoundError:
    print("[치명적 오류] 모델 파일이 없습니다.")
    exit()


# =============================================================================
# 파트 4: 서버 상태 및 MQTT 핸들러
# =============================================================================
BEACON_TO_ENV_MAP = {
    "40011-55612": "환경 1",
    "40011-55581": "환경 2",
    "40011-55583": "환경 3",
}
environment_state = {}
ENV_DATA_TIMEOUT = 300.0


def handle_env_message(data):
    try:
        major = data.get("beacon_major")
        minor = data.get("beacon_minor")
        if major is None or minor is None:
            return
        beacon_key = f"{major}-{minor}"
        env_name = BEACON_TO_ENV_MAP.get(beacon_key)
        if env_name is None:
            return

        temp = data.get("temperature")
        humi = data.get("humidity")
        if temp is None or humi is None:
            return

        environment_state[env_name] = {
            "env_temp": temp,
            "env_humi": humi,
            "last_updated": time.time(),
        }
        print(f"[환경 갱신] {env_name}: T={temp}°C, H={humi}%")
    except Exception as e:
        print(f"[환경 처리 오류] {e}")


def handle_vest_message(client, data):
    global GLOBAL_DB_CONNECTION  # 전역 변수 사용 선언
    try:
        # start_time = time.time()
        mcu_id = data.get("mcu_id")
        body_temp = data.get("body_temp")
        hr = data.get("hr")
        is_fell = data.get("is_fell")
        scanned_beacons = data.get("beacons", [])
        db_save_name = WORKER_NAME_MAP.get(mcu_id)

        if mcu_id is None:
            return
        if body_temp is None or hr is None:
            return

        print(f"\n[조끼 수신: {db_save_name}] T:{body_temp}, HR:{hr}, Fell:{is_fell}")

        # ---------------------------------------------------------
        # [Step 1] 위치 결정 로직 (15초 강제 고정)
        # ---------------------------------------------------------
        current_time = time.time()
        lock_info = location_locks.get(mcu_id)

        final_env_name = "Unknown"
        final_env_temp = 0.0
        final_env_humi = 0.0

        # 1-1. 잠금(Lock)이 걸려있고 유효한지 확인
        if lock_info and current_time < lock_info["expiry"]:
            # [잠금 상태] 비콘 스캔 무시하고 저장된 위치 사용
            final_env_name = lock_info["name"]
            final_env_temp = lock_info["temp"]
            final_env_humi = lock_info["humi"]
            remaining_time = int(lock_info["expiry"] - current_time)
            # print(f" >> [위치 고정 중] {final_env_name} (남은 시간: {remaining_time}초)")

        else:
            # 1-2. 잠금 없음 또는 만료됨 -> 새로운 비콘 스캔 시도
            found_new_location = False

            if scanned_beacons:
                strongest_beacon = max(scanned_beacons, key=lambda b: b["rssi"])
                beacon_key = (
                    f"{strongest_beacon.get('major')}-{strongest_beacon.get('minor')}"
                )
                found_name = BEACON_TO_ENV_MAP.get(beacon_key)

                if found_name:
                    env_data = environment_state.get(found_name)
                    # 환경 데이터 유효성 체크
                    if env_data and (
                        time.time() - env_data["last_updated"] <= ENV_DATA_TIMEOUT
                    ):
                        # [새 위치 발견] -> 15초간 잠금(Lock) 설정
                        final_env_name = found_name
                        final_env_temp = env_data["env_temp"]
                        final_env_humi = env_data["env_humi"]

                        location_locks[mcu_id] = {
                            "name": final_env_name,
                            "temp": final_env_temp,
                            "humi": final_env_humi,
                            "expiry": current_time + LOCK_DURATION,
                        }
                        found_new_location = True
                        print(
                            f" >> [새 위치 고정] {final_env_name} (15초간 유지)"
                        )  # 비콘 값 손실을 막기 위함

            if not found_new_location:
                print(" >> [위치 미확인] 잠금 만료되었으나 신호 없음. (Unknown)")
        # print(f"위치 결정 소요 시간: {time.time() - start_time:.4f}s")  # 확인 1
        # ---------------------------------------------------------
        # [Step 2] 낙상 감지 처리 (긴급 우선)
        # ---------------------------------------------------------
        if is_fell == 1:
            print(f" >> [긴급] 낙상 감지! 저장 위치: {final_env_name}")
            client.publish(f"vest/alert/{mcu_id}", "경보")

            # 고정된 위치 정보로 저장
            save_worker_status_to_db(
                GLOBAL_DB_CONNECTION,
                db_save_name,
                final_env_name,
                final_env_temp,
                final_env_humi,
                body_temp,
                hr,
                is_fell,
                "낙상 사고",
            )
            save_vest_log_to_db(
                GLOBAL_DB_CONNECTION,
                db_save_name,
                final_env_name,
                final_env_temp,
                final_env_humi,
                body_temp,
                hr,
                is_fell,
                "낙상 사고",
            )
            return

        # ---------------------------------------------------------
        # [Step 3] AI 위험 예측
        # ---------------------------------------------------------
        # ai_start = time.time()
        if final_env_name == "Unknown":
            print(" >> 위치 데이터 부족으로 AI 분석 스킵")
            return

        input_data = [[body_temp, hr, final_env_temp, final_env_humi]]
        result = predict_hybrid(input_data, scaler, model)
        final_status = result[0]
        print(f" >> 분석 결과: {final_status}")
        # print(f"AI 분석 소요 시간: {time.time() - ai_start:.4f}s")  # 확인 2
        # ---------------------------------------------------------
        # [Step 4] 결과 전송 및 저장
        # ---------------------------------------------------------
        alert_topic = f"vest/alert/{mcu_id}"
        if final_status != "정상" and final_status != "DATA_ERROR":
            client.publish(alert_topic, "ALERT")
            print(f" >> 조치: 경보 전송 ")
        else:
            client.publish(alert_topic, "NORMAL")

        # db_start = time.time()

        save_worker_status_to_db(
            GLOBAL_DB_CONNECTION,
            db_save_name,
            final_env_name,
            final_env_temp,
            final_env_humi,
            body_temp,
            hr,
            is_fell,
            final_status,
        )
        save_vest_log_to_db(
            GLOBAL_DB_CONNECTION,
            db_save_name,
            final_env_name,
            final_env_temp,
            final_env_humi,
            body_temp,
            hr,
            is_fell,
            final_status,
        )
        # print(f"DB 저장 소요 시간: {time.time() - db_start:.4f}s")  # 확인 3
    except Exception as e:
        print(f"[조끼 처리 오류] {e}")


# =============================================================================
# 파트 5: MQTT 연결 및 실행
# =============================================================================
init_db()

MQTT_BROKER_HOST = "broker.hivemq.com"
MQTT_BROKER_PORT = 1883
MQTT_TOPICS = [("vest/data", 0), ("env/data", 0)]


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f">> 브로커 연결 성공 ({MQTT_BROKER_HOST})")
        client.subscribe(MQTT_TOPICS)
    else:
        print(f">> 연결 실패 (Code: {rc})")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        if msg.topic == "env/data":
            handle_env_message(payload)
        elif msg.topic == "vest/data":
            handle_vest_message(client, payload)
    except Exception:
        pass


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    print(">> MQTT 루프 시작...")
    client.loop_forever()
except KeyboardInterrupt:
    print("\n>> 종료합니다.")
except Exception as e:
    print(f"\n>> 실행 오류: {e}")
