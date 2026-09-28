/*
 * ESP32 듀얼 코어 (FreeRTOS) 병렬 처리 예제 - "조끼" MCU용 (수정됨)
 * 기능: PulseSensor + Temp + BLE + MQTT + [NEW] ESP-NOW Receiver
 */

// --- 라이브러리 임포트 ---
#include <PulseSensorPlayground.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_MLX90614.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <stdio.h>
#include <string.h>
#include <esp_now.h> // [추가됨] ESP-NOW 라이브러리
#include <esp_wifi.h>

// --- 1. WiFi 및 MQTT 정보 ---
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_BROKER_HOST = "broker.hivemq.com";
const uint16_t MQTT_BROKER_PORT = 1883;
const char* MQTT_PUB_TOPIC = "vest/data";
const char* MQTT_SUB_TOPIC_PREFIX = "vest/alert/"; 

// --- [추가됨] ESP-NOW 데이터 구조체 ---
// 송신측(IMU 센서 등)과 구조가 정확히 일치해야 합니다.
typedef struct struct_message {
  int msgType;   // 1: 낙상 발생
  float impact;  // 충격량
} struct_message;

struct_message myData;

// --- 2. BLE 타겟 UUID ---
const char* TARGET_IBEACON_UUIDS[] = {
}; // << target UUIDs를 여기에 추가하세요
const int NUM_TARGET_UUIDS = sizeof(TARGET_IBEACON_UUIDS) / sizeof(TARGET_IBEACON_UUIDS[0]);

// --- 3. 핀 및 변수 ---
const int PulseWire = A0; // GPIO 34/36 등 ADC 핀 확인 필요
const int LED13 = 13;
const int buzzerPin = 10;
int Threshold = 550;
PulseSensorPlayground pulseSensor;

// --- 4. 센서 및 클라이언트 객체 ---
WiFiClient net;
PubSubClient mqtt(net);
Adafruit_MLX90614 mlx = Adafruit_MLX90614();
BLEScan* pBLEScan;

// --- 5. RTOS 및 공유 변수 ---
TaskHandle_t h_pulseSensorTask;
TaskHandle_t h_networkAndBleTask;
TaskHandle_t h_buzzerTask;

volatile int global_BPM = 0;
volatile bool global_BuzzerOn = false;
volatile unsigned long global_LastAlertTime = 0;
const long BUZZER_TIMEOUT_MS = 15000;

// [추가됨] 낙상 감지 공유 변수 (ESP-NOW Callback -> Task 2)
volatile int global_IsFell = 0; 

String myAlertTopic = "";

// ----------------------------------------------------------------------
// [수정됨] ESP-NOW 수신 콜백 함수 (디버깅 추가)
// ----------------------------------------------------------------------
void OnDataRecv(const esp_now_recv_info_t * info, const uint8_t *incomingData, int len) {
  // 데이터 복사
  memcpy(&myData, incomingData, sizeof(myData));
  
  // --- [디버깅] 수신된 데이터 출력 시작 ---
  Serial.println("\n>>> [ESP-NOW] Packet Received! <<<");
  
  // 1. 보낸 사람 MAC 주소 출력
  Serial.print("Sender MAC: ");
  for (int i = 0; i < 6; i++) {
    Serial.printf("%02X", info->src_addr[i]);
    if (i < 5) Serial.print(":");
  }
  Serial.println();

  // 2. 데이터 길이 및 내용 출력
  Serial.print("Bytes: "); Serial.println(len);
  Serial.print("MsgType: "); Serial.println(myData.msgType);
  Serial.print("Impact: "); Serial.println(myData.impact);
  Serial.println("----------------------------------");
  // --- [디버깅] 끝 ---

  // msgType이 1이면 낙상으로 판단
  if (myData.msgType == 1) {
    Serial.println("!!! 낙상 신호 감지 (is_fell -> 1) !!!"); // 확인용 로그
    global_IsFell = 1; // 낙상 상태 업데이트
    
    // 낙상 시 즉시 부저 활성화
    global_BuzzerOn = true; 
    global_LastAlertTime = millis();
  }
}

// ----------------------------------------------------------------------
// MQTT 메시지 수신 콜백 (기존 유지)
// ----------------------------------------------------------------------
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("경보 메시지 수신 [");
  Serial.print(topic);
  Serial.print("]: ");
  
  payload[length] = '\0';
  String message = String((char*)payload);
  Serial.println(message);

  if (message == "ALERT") {
    Serial.println(">>> 서버 위험 경보! 부저 ON <<<");
    global_BuzzerOn = true;
    global_LastAlertTime = millis();
  } else if (message == "NORMAL") {
    Serial.println(">>> 정상 신호 수신. 부저 OFF <<<");
    global_BuzzerOn = false;
  }
}

// ----------------------------------------------------------------------
// MQTT 재연결 함수
// ----------------------------------------------------------------------
void reconnectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("[Task 2] MQTT 연결 시도...");
    String clientId = "ESP32Vest-" + String(random(0xffff), HEX);

    if (mqtt.connect(clientId.c_str())) {
      Serial.println("연결됨!");
      if (myAlertTopic != "") {
        mqtt.subscribe(myAlertTopic.c_str());
        Serial.println("경보 토픽 구독 완료: " + myAlertTopic);
      }
    } else {
      Serial.print("실패, rc=");
      Serial.print(mqtt.state());
      Serial.println(" 5초 후 재시도");
      delay(5000); 
    }
  }
}

// ----------------------------------------------------------------------
// [Task 1] Core 0: 실시간 심박수 (기존 유지)
// ----------------------------------------------------------------------
void pulseSensorTask(void* pvParameters) {
  while (1) {
    int currentBPM = pulseSensor.getBeatsPerMinute();
    if (currentBPM > 0) {
      global_BPM = currentBPM;
    }
    vTaskDelay(20 / portTICK_PERIOD_MS);
  }
}

// ----------------------------------------------------------------------
// [Task 2] Core 1: 네트워크, BLE, [수정] ESP-NOW 상태 전송
// ----------------------------------------------------------------------
void networkAndBleTask(void* pvParameters) {
  Serial.print("[Task 2] Network Task running on Core: ");
  Serial.println(xPortGetCoreID());

  unsigned long lastMillis = 0;
  unsigned long interval = 5000; // [변경] 기본 전송 주기는 5초

  while (1) {
    // 1. MQTT 연결 유지
    if (!mqtt.connected()) {
      reconnectMQTT();
    }
    mqtt.loop();

    unsigned long currentMillis = millis(); // 현재 시간 저장

    // 2. 5초 주기 데이터 발행
    if ((currentMillis - lastMillis >= interval) || (global_IsFell == 1)) {
      
      lastMillis = currentMillis;

      // --- JSON 데이터 생성 ---
      StaticJsonDocument<1024> doc;
      float body_temp = mlx.readObjectTempC();
      int hr = global_BPM;

      doc["mcu_id"] = WiFi.macAddress();
      doc["body_temp"] = body_temp;
      doc["hr"] = hr;

      JsonArray beaconArray = doc.createNestedArray("beacons");

      // --- BLE 스캔 (Blocking 3초) ---
      Serial.println("[Task 2] BLE Scan start...");
      BLEScanResults* foundDevices = pBLEScan->start(3, false);
      int deviceCount = foundDevices->getCount();
      
      for (int i = 0; i < deviceCount; i++) {
        BLEAdvertisedDevice dev = foundDevices->getDevice(i);
        if (dev.haveManufacturerData() && dev.getManufacturerData().length() == 25) {
          String mfg = dev.getManufacturerData();
          const uint8_t* mfgData = (const uint8_t*)mfg.c_str();
          
          // UUID 확인 로직 (간소화: 실제 UUID 비교는 원본 참조)
          char scannedUUID[37];
          sprintf(scannedUUID, "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
                  mfgData[4], mfgData[5], mfgData[6], mfgData[7],
                  mfgData[8], mfgData[9], mfgData[10], mfgData[11],
                  mfgData[12], mfgData[13], mfgData[14], mfgData[15],
                  mfgData[16], mfgData[17], mfgData[18], mfgData[19]);
          
          bool foundTarget = false;
          for (int j = 0; j < NUM_TARGET_UUIDS; j++) {
            if (strcasecmp(scannedUUID, TARGET_IBEACON_UUIDS[j]) == 0) {
              foundTarget = true;
              break;
            }
          }

          if (foundTarget) {
            JsonObject beacon = beaconArray.createNestedObject();
            beacon["major"] = (mfgData[20] << 8) | mfgData[21];
            beacon["minor"] = (mfgData[22] << 8) | mfgData[23];
            beacon["rssi"] = dev.getRSSI();
          }
        }
      }
      pBLEScan->clearResults();

      doc["is_fell"] = global_IsFell;


      // --- MQTT 발행 ---
      char jsonBuffer[1024];
      serializeJson(doc, jsonBuffer);
      Serial.print("[Task 2] Publishing: ");
      Serial.println(jsonBuffer);
      mqtt.publish(MQTT_PUB_TOPIC, jsonBuffer);
      
      bool isFallEvent = (global_IsFell == 1);      
      // 한 번 전송했으므로 낙상 플래그 리셋 (다음 신호 대기)
      if (isFallEvent) {
          Serial.println("!!! 낙상 데이터 전송 완료. 15초간 대기합니다. !!!");
          global_IsFell = 0; // 플래그 리셋
          interval = 15000;  // 다음 번 실행은 15초 뒤로 설정
      } else {
          interval = 5000;   // 평상시엔 5초 주기로 복귀
      }
      
      Serial.println("-----------------------------------\n");
    }
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}

// ----------------------------------------------------------------------
// [Task 3] Core 0: 부저 제어 (기존 유지)
// ----------------------------------------------------------------------
void buzzerTask(void* pvParameters) {
  pinMode(buzzerPin, OUTPUT);
  while (1) {
    if (global_BuzzerOn && (millis() - global_LastAlertTime > BUZZER_TIMEOUT_MS)) {
        global_BuzzerOn = false;
        Serial.println("[Buzzer] 타임아웃. 중지.");
    }
    if (global_BuzzerOn) {
      digitalWrite(buzzerPin, HIGH);
      vTaskDelay(1 / portTICK_PERIOD_MS);
      digitalWrite(buzzerPin, LOW);
      vTaskDelay(1 / portTICK_PERIOD_MS);
    } else {
      digitalWrite(buzzerPin, LOW);
      vTaskDelay(50 / portTICK_PERIOD_MS);
    }
  }
}

// ----------------------------------------------------------------------
// SETUP
// ----------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- Vest System Initializing ---");

  // 1. 센서 초기화
  pinMode(LED13, OUTPUT);
  pulseSensor.analogInput(PulseWire);
  pulseSensor.blinkOnPulse(LED13);
  pulseSensor.setThreshold(Threshold);
  if (!pulseSensor.begin()) Serial.println("PulseSensor Init Failed!");

  if (!mlx.begin()) Serial.println("MLX Sensor Init Failed!");

  // 2. WiFi 연결 (ESP-NOW를 위해 먼저 연결 필수)
  WiFi.mode(WIFI_STA); // Station 모드
  int fixed_channel = 6; 
  esp_wifi_set_promiscuous(true); // 채널 고정을 위해 프로미스큐어스 모드 활성화
  esp_wifi_set_channel(fixed_channel, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false); // 다시 비활성화
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");

  Serial.print("Current WiFi Channel: ");
  Serial.println(WiFi.channel());
  Serial.println("Sender must match this channel!");

  // 3. [추가됨] ESP-NOW 초기화
  // 주의: WiFi 연결 후에 초기화해야 채널이 맞습니다.
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
  } else {
    Serial.println("ESP-NOW Initialized!");
    // 수신 콜백 등록
    esp_now_register_recv_cb(OnDataRecv);
  }

  // 4. MQTT 설정
  myAlertTopic = String(MQTT_SUB_TOPIC_PREFIX) + WiFi.macAddress();
  mqtt.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  mqtt.setCallback(mqttCallback);

  // 5. BLE 초기화
  BLEDevice::init("ESP32_Vest");
  pBLEScan = BLEDevice::getScan();
  pBLEScan->setActiveScan(false);
  pBLEScan->setInterval(100);
  pBLEScan->setWindow(80);

  // 6. RTOS Task 생성
  xTaskCreatePinnedToCore(pulseSensorTask, "PulseSensorTask", 4096, NULL, 2, &h_pulseSensorTask, 0);
  xTaskCreatePinnedToCore(networkAndBleTask, "NetworkBLETask", 8192, NULL, 1, &h_networkAndBleTask, 1);
  xTaskCreatePinnedToCore(buzzerTask, "BuzzerTask", 1024, NULL, 0, &h_buzzerTask, 0);

  Serial.println("System Ready.");
}

void loop() {
  vTaskDelay(1000 / portTICK_PERIOD_MS);
}