#include <Arduino.h>

constexpr byte TRIGGER_PIN = 9;
constexpr byte ECHO_PIN = 10;

// Cấu hình đúng hai chân sonar và mở log USB phục vụ kiểm tra độc lập.
void setup() {
  Serial.begin(115200);
  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIGGER_PIN, LOW);
  Serial.println(F("SONAR_PROBE|READY"));
}

// Phát xung 10 microsecond rồi in thời lượng echo và khoảng cách centimet.
void loop() {
  digitalWrite(TRIGGER_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIGGER_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIGGER_PIN, LOW);

  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  Serial.print(F("SONAR_PROBE|ECHO_US|"));
  Serial.print(duration);
  Serial.print(F("|DISTANCE_CM|"));
  if (duration == 0) {
    Serial.println(F("INVALID"));
  } else {
    Serial.println(static_cast<float>(duration) * 0.0343F * 0.5F, 1);
  }
  delay(300);
}
