/*
 * ESP32 환경 센서 (DHT22) - MQTT 발행용
 *
 * 역할:
 * 1. 5초마다 DHT22 센서에서 온/습도를 측정합니다.
 * 2. 이 환경 센서의 위치를 식별하는 '비콘 ID' (Major/Minor)를 포함합니다.
 * 3. 'env/data' 토픽으로 JSON 데이터를 발행합니다.

 (환경 mcu id, 온도, 습도, major, minor 보냄)

 이 코드는 major와 minor 값을 다르게 하여 3개의 환경 mcu에 각각 업로드 해줘야함
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h> 

// --- 1. WiFi 및 MQTT 정보 설정 (필수 수정) ---
const char* WIFI_SSID = "YOUR_WIFI_SSID";         // <<<<<< 사용하시는 WiFi 이름으로 수정하세요
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";     // <<<<<< 사용하시는 WiFi 비밀번호로 수정하세요

const char* MQTT_BROKER_HOST = "broker.hivemq.com"; // HiveMQ 공용 브로커
const uint16_t MQTT_BROKER_PORT = 1883;             
const char* MQTT_PUB_TOPIC = "env/data"; // '환경' 데이터 전용 토픽

// --- 2. DHT22 센서 설정 ---
#define DHTPIN 10     // 데이터 핀: ESP32의 GPIO 10 핀 (D7)
#define DHTTYPE DHT22 // 센서 타입 정의

// --- 3. [중요] 이 환경 센서의 고유 비콘 ID 설정 ---
// (이 MCU를 다른 환경(예: 저온)에 설치할 경우, 이 값을 서버가 아는 다른 값으로 변경하세요)
const uint16_t MY_BEACON_MAJOR = "YOUR_BEACON_MAJOR";; // <<<<<< 사용하시는 beacon major으로 수정하세요
const uint16_t MY_BEACON_MINOR = "YOUR_BEACON_MINOR"; // <<<<<< 사용하시는 beacon minor으로 수정하세요

// --- 4. 객체 생성 ---
WiFiClient net;
PubSubClient mqtt(net);
DHT dht(DHTPIN, DHTTYPE);

unsigned long lastPublishMillis = 0; // 마지막 데이터 발행 시간
const unsigned long publishInterval = 5000; // 5초 (5000ms) 간격으로 발행

// --- 5. MQTT 재연결 함수 ---
void reconnectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("Attempting MQTT connection...");
    // 랜덤 클라이언트 ID 생성
    String clientId = "ESP32EnvSensor-";
    clientId += String(random(0xffff), HEX);

    if (mqtt.connect(clientId.c_str())) {
      Serial.println("connected!");
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqtt.state());
      Serial.println(" -> Retrying in 5 seconds...");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  randomSeed(analogRead(0)); // 랜덤 시드 초기화

  // --- DHT 센서 초기화 ---
  dht.begin();
  Serial.println("DHT22 센서 초기화 완료");

  // --- WiFi 연결 시도 (20초 타임아웃 적용) ---
  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  const int maxAttempts = 40; // 0.5초 * 40회 = 20초
  
  while (WiFi.status() != WL_CONNECTED && attempts < maxAttempts) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    // --- MQTT 브로커 설정 ---
    mqtt.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  } else {
    // 20초 후에도 연결 실패
    Serial.println("\nWiFi connection FAILED after 20 seconds.");
    Serial.println(">>> SSID/Password, 2.4GHz 대역, 핫스팟 설정 등을 확인하세요. <<<");
    // 여기서는 loop()에서 MQTT 연결 시도가 계속되도록 남겨둡니다.
  }
}

void loop() {
  // 1. MQTT 연결 유지
  if (!mqtt.connected()) {
    reconnectMQTT();
  }
  mqtt.loop(); 

  // 2. 5초 간격으로 데이터 발행
  if (millis() - lastPublishMillis >= publishInterval) {
    lastPublishMillis = millis();

    // --- 3. DHT22 센서 데이터 읽기 ---
    float h = dht.readHumidity();    // 습도 (%)
    float t = dht.readTemperature(); // 온도 (섭씨, °C)

    // 읽기 실패 검사
    if (isnan(h) || isnan(t)) {
      Serial.println("[DHT ERR] DHT22에서 데이터를 읽지 못했습니다. 회로를 확인하세요.");
      return;
    }

    // --- 4. JSON 객체 생성 ---
    StaticJsonDocument<256> doc; // JSON 문서 크기 최적화

    doc["mcu_id"] = WiFi.macAddress();
    doc["temperature"] = t;
    doc["humidity"] = h;
    
    // [수정됨] 이 환경의 고유 비콘 ID 추가
    doc["beacon_major"] = MY_BEACON_MAJOR;
    doc["beacon_minor"] = MY_BEACON_MINOR;

    // JSON을 문자열로 변환
    char jsonBuffer[256];
    serializeJson(doc, jsonBuffer);

    // --- 5. MQTT 토픽으로 JSON 문자열 발행 ---
    if (mqtt.state() == MQTT_CONNECTED) {
      Serial.print("Publishing to ");
      Serial.print(MQTT_PUB_TOPIC);
      Serial.print(" -> ");
      Serial.println(jsonBuffer);

      mqtt.publish(MQTT_PUB_TOPIC, jsonBuffer);
    } else {
      Serial.println("WiFi는 연결되었으나, MQTT 브로커에 연결되지 않았습니다. 재시도 중...");
    }
  }
}