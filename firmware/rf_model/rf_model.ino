/*
 * [System A: Sender - ESP32-S3 정품 자동 재장전 버전]
 * 기능: 낙상 감지 -> (즉시) 서보모터 0도 & GPIO 4 HIGH -> 5초 대기 -> 서보모터 180도 복귀 (재장전)
 * 통신: ESP-NOW (Target MAC: AA:BB:CC:DD:EE:01, Channel: 6)
 */

#include <Wire.h>
#include <MPU9250.h>
#include "rf_model_big.h"
#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <ESP32Servo.h>

// [수정됨] 최종 센서 MCU 맥주소 (AA:BB:CC:DD:EE:01)
uint8_t receiverMac[] = {}; // <<<<<< 수신측 ESP32-S3의 MAC 주소를 여기에 입력하세요 (예: {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x01})

// 하드웨어 핀 설정
const int PIN_SDA = 2;       // I2C SDA
const int PIN_SCL = 1;       // I2C SCL
const int PIN_SERVO = 10;    // 서보모터 신호선
const int PIN_TRIGGER = 4;   // 외부 신호용 (낙상 시 HIGH)

// 객체 생성
MPU9250 mpu;
Eloquent::ML::Port::FallClassifier classifier;
Servo myservo;

// 상태 변수
bool isFallDetected = false; // 중복 감지 방지용 플래그

// 데이터 버퍼 설정
const int WINDOW_SIZE = 50;
const int NUM_CHANNELS = 6;
float data_buffer[WINDOW_SIZE * NUM_CHANNELS];

// ESP-NOW 데이터 구조체
typedef struct struct_message {
  int msgType;    // 1: 낙상 경보
  float impact;   // 충격량 (예시 데이터)
} struct_message;

struct_message myData;
esp_now_peer_info_t peerInfo;

// // 콜백 함수
// void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
//   // 디버깅 필요 시 아래 주석 해제
//   // Serial.print("\r\nLast Packet Send Status:\t");
//   // Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Delivery Success" : "Delivery Fail");
// }

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("=== System A (ESP32-S3 Auto-Rearm) Start ===");

  // 정품 ESP32-S3 내장 RGB LED 끄기
  neopixelWrite(38, 0, 0, 0); 
  Serial.println("🌑 RGB LED Force OFF command sent to GPIO 48");

  // 1. 핀 모드 설정
  pinMode(PIN_TRIGGER, OUTPUT); 
  digitalWrite(PIN_TRIGGER, LOW);

  // 2. 서보모터 초기화
  myservo.setPeriodHertz(50);
  // 각도 확보를 위해 펄스 폭을 1000~2000으로 설정 (사용자 최적값)
  myservo.attach(PIN_SERVO, 1000, 2000); 
  
  // 초기 상태: 180도 (잠금 상태)
  myservo.write(180); 
  delay(500); 
  Serial.println("✅ Servo Ready: 180 deg");

  // 3. 센서 초기화 (Wire 핀 지정)
  Wire.begin(PIN_SDA, PIN_SCL);

  if (!mpu.setup(0x68)) {
    Serial.println("❌ MPU Connection Failed. Check Wiring!");
    // while(1) delay(100); // 디버깅 위해 주석 처리
  } else {
    Serial.println("✅ MPU Sensor OK");
  }

  // 4. ESP-NOW 초기화
  WiFi.mode(WIFI_STA);

  // [수정됨] 채널을 6번으로 설정
  // ESP-NOW는 Sender와 Receiver가 동일한 채널에 있어야 통신이 가능합니다.
  esp_wifi_set_channel(6, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    Serial.println("❌ ESP-NOW Init Error");
    return;
  }

  // esp_now_register_send_cb(OnDataSent);

  // Peer 등록
  memcpy(peerInfo.peer_addr, receiverMac, 6);
  // [수정됨] Peer 채널도 6번으로 명시
  peerInfo.channel = 6; 
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("❌ Peer Registration Failed");
    return;
  }
  
  Serial.println("System Armed. Waiting for fall...");
  Serial.println("ESP-NOW Target MAC: AA:BB:CC:DD:EE:01 (Channel 6)");
}

void run_inference() {
  // 이미 낙상이 감지되어 처리 중이면 패스
  if (isFallDetected) return;

  int fall_votes = classifier.predict(data_buffer);

  // 11표 이상이면 낙상으로 판단
  if (fall_votes >= 15) {
    // --- 시간 측정 시작 ---
    unsigned long timeStart = micros(); 

    // 1. 물리적 트리거 신호 ON
    digitalWrite(PIN_TRIGGER, HIGH); 

    // 2. 서보 모터 즉시 동작 (에어백 전개) -> 0도로 이동
    myservo.write(0);

    // --- 시간 측정 끝 ---
    unsigned long timeEnd = micros();
    
    // 상태 잠금 (중복 실행 방지)
    isFallDetected = true; 

    // 3. 결과 출력
    Serial.println("\n\n🚨 FALL DETECTED! SERVO ACTIVATED! 🚨");
    Serial.println("------------------------------------------------");
    Serial.print("⏱️ Reaction Time (Detection -> Servo Command): ");
    Serial.print(timeEnd - timeStart);
    Serial.println(" us (microseconds)");
    Serial.print("   = ");
    Serial.print((timeEnd - timeStart) / 1000.0, 3);
    Serial.println(" ms (milliseconds)");
    Serial.println("------------------------------------------------");

    // 4. ESP-NOW 알림 전송
    myData.msgType = 1; 
    myData.impact = 99.9; // 필요 시 실제 충격량 계산값으로 대체 가능
    
    // 데이터 전송
    esp_err_t result = esp_now_send(receiverMac, (uint8_t *) &myData, sizeof(myData));
    
    if (result == ESP_OK) {
      Serial.println("✅ Alert Sent via ESP-NOW");
    } else {
      Serial.println("❌ Error sending the data");
    }

    // 5초 대기 (에어백 전개 상태 유지)
    Serial.println("5초간 전개 상태 유지...");
    delay(5000); 

    // ====================================================
    // [추가된 부분] 5초 후 자동 재장전 로직
    // ====================================================
    Serial.println("5초 경과! 시스템 자동 재장전 중...");
    
    // 1. 서보모터 원위치 (180도)
    myservo.write(180);
    
    // 2. 트리거 신호 끄기
    digitalWrite(PIN_TRIGGER, LOW);
    
    // 3. 서보 이동 시간 확보 및 센서 안정화
    delay(1000); 
    
    // 4. 감지 잠금 해제 (다시 감지 시작)
    isFallDetected = false; 
    Serial.println("시스템 재장전 완료: 다시 낙상 감지 대기 중...");
    // ====================================================
  }
}

void loop() {
  static int sample_count = 0;
  static uint32_t prev_ms = millis();

  if (mpu.update()) {
    // FIFO 방식으로 데이터 시프트
    for (int i = 0; i < (WINDOW_SIZE - 1) * NUM_CHANNELS; i++) {
      data_buffer[i] = data_buffer[i + NUM_CHANNELS];
    }
    
    int last = (WINDOW_SIZE - 1) * NUM_CHANNELS;
    data_buffer[last + 0] = mpu.getAccX() * 9.8; 
    data_buffer[last + 1] = mpu.getAccY() * 9.8;
    data_buffer[last + 2] = mpu.getAccZ() * 9.8;
    data_buffer[last + 3] = mpu.getGyroX();
    data_buffer[last + 4] = mpu.getGyroY();
    data_buffer[last + 5] = mpu.getGyroZ();

    sample_count++;

    if (millis() > prev_ms + 10) {
      prev_ms = millis();
      // 데이터가 충분히 쌓이고(WINDOW_SIZE), 10샘플마다 추론 실행
      if (sample_count >= WINDOW_SIZE && sample_count % 10 == 0) {
         run_inference();
      }
    }
  }
}