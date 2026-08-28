#pragma once

#include <Arduino.h>

enum class GuardState : uint8_t {
  kOff,
  kArming,
  kArmed,
  kAlert,
};

enum class GuardEvent : uint8_t {
  kNone,
  kArmingStarted,
  kArmed,
  kAlertStarted,
  kDisarmed,
};

class GuardStateMachine {
 public:
  // Bắt đầu đếm ngược kích hoạt nếu hệ thống đang tắt.
  GuardEvent arm(unsigned long now_ms);

  // Tắt sonar và xóa cảnh báo đã chốt bằng chìa IR hoặc lệnh Serial.
  GuardEvent disarm();

  // Cập nhật đếm ngược và xác nhận vật thể gần qua nhiều mẫu liên tiếp.
  GuardEvent update(unsigned long now_ms, float distance_cm);

  // Trả trạng thái hiện tại để firmware gửi đồng bộ sang ứng dụng ARIS.
  GuardState state() const;

 private:
  GuardState state_ = GuardState::kOff;
  unsigned long arming_started_ms_ = 0;
  uint8_t consecutive_near_samples_ = 0;
};
