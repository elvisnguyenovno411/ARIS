#pragma once

#include <Arduino.h>

namespace aris_hardware {

constexpr uint8_t kIrReceivePin = 2;
constexpr uint8_t kSonarTriggerPin = 9;
constexpr uint8_t kSonarEchoPin = 10;

constexpr uint8_t kRemotePower = 0x45;
constexpr uint8_t kRemoteOk = 0x40;
constexpr uint8_t kRemoteZero = 0x16;
constexpr uint8_t kRemoteBack = 0x44;

constexpr float kAlertDistanceCm = 80.0F;
constexpr unsigned long kArmingDelayMs = 10000UL;
constexpr unsigned long kSonarSampleIntervalMs = 100UL;
constexpr unsigned long kDistanceReportIntervalMs = 500UL;
constexpr uint8_t kNearSamplesRequired = 3;

}  // namespace aris_hardware
