#pragma once

#include <Arduino.h>

enum class RemoteCommand : uint8_t {
  kNone,
  kPower,
  kOk,
  kZero,
  kBack,
  kUnknown,
};

class RemoteInput {
 public:
  // Khởi động mắt nhận IR trên chân đã khai báo trong hardware_config.h.
  void begin();

  // Đọc tối đa một lần bấm mới và bỏ qua frame lặp khi người dùng giữ nút.
  RemoteCommand poll();

  // Trả mã NEC gần nhất để in log khi gặp một nút chưa được ánh xạ.
  uint16_t lastCode() const;

 private:
  uint16_t last_code_ = 0;
};
