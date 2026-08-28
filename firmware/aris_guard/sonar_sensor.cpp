#include "sonar_sensor.h"

#include "hardware_config.h"

void SonarSensor::begin() {
  pinMode(aris_hardware::kSonarTriggerPin, OUTPUT);
  pinMode(aris_hardware::kSonarEchoPin, INPUT);
  digitalWrite(aris_hardware::kSonarTriggerPin, LOW);
}

float SonarSensor::readDistanceCm() {
  digitalWrite(aris_hardware::kSonarTriggerPin, LOW);
  delayMicroseconds(2);
  digitalWrite(aris_hardware::kSonarTriggerPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(aris_hardware::kSonarTriggerPin, LOW);

  const unsigned long echo_duration =
      pulseIn(aris_hardware::kSonarEchoPin, HIGH, 30000UL);
  if (echo_duration == 0) {
    return -1.0F;
  }
  return static_cast<float>(echo_duration) * 0.0343F * 0.5F;
}
