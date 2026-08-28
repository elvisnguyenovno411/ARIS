#pragma once

#include <Arduino.h>

class SonarSensor {
 public:
  // Cấu hình chân TRIG là output và ECHO là input của HC-SR04.
  void begin();

  // Đo khoảng cách theo centimet; trả -1 khi không nhận được echo hợp lệ.
  float readDistanceCm();
};
