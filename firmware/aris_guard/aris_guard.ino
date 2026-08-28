#include <Arduino.h>

#include "guard_state.h"
#include "hardware_config.h"
#include "remote_input.h"
#include "sonar_sensor.h"

GuardStateMachine guard;
RemoteInput remote;
SonarSensor sonar;

unsigned long last_sonar_sample_ms = 0;
unsigned long last_distance_report_ms = 0;
char serial_command[24] = {};
uint8_t serial_command_length = 0;

// In tên trạng thái ổn định để Python có thể đọc mà không cần phân tích câu tự nhiên.
void printState(GuardState state) {
  Serial.print(F("ARIS_HW|STATE|"));
  switch (state) {
    case GuardState::kOff:
      Serial.println(F("OFF"));
      break;
    case GuardState::kArming:
      Serial.println(F("ARMING"));
      break;
    case GuardState::kArmed:
      Serial.println(F("ARMED"));
      break;
    case GuardState::kAlert:
      Serial.println(F("ALERT"));
      break;
  }
}

// Gửi thay đổi trạng thái duy nhất để HUD và TTS không thông báo trùng lặp.
void publishGuardEvent(GuardEvent event) {
  if (event == GuardEvent::kNone) {
    return;
  }
  printState(guard.state());
}

// Bật sonar bằng remote hoặc lệnh từ ARIS và phát thời gian rời vùng cảm biến.
void armGuard() {
  const GuardEvent event = guard.arm(millis());
  publishGuardEvent(event);
  if (event == GuardEvent::kArmingStarted) {
    Serial.println(F("ARIS_HW|ARMING_SECONDS|10"));
  }
}

// Mở khóa cảnh báo và đưa cảm biến về OFF bằng điều khiển vật lý.
void disarmGuard() {
  publishGuardEvent(guard.disarm());
}

// Xử lý các nút IR đã đo trực tiếp từ remote của chủ sở hữu.
void handleRemote() {
  const RemoteCommand command = remote.poll();
  switch (command) {
    case RemoteCommand::kNone:
      return;
    case RemoteCommand::kPower:
      Serial.println(F("ARIS_HW|REMOTE|POWER"));
      armGuard();
      return;
    case RemoteCommand::kOk:
      Serial.println(F("ARIS_HW|REMOTE|OK"));
      disarmGuard();
      return;
    case RemoteCommand::kZero:
      Serial.println(F("ARIS_HW|REMOTE|ZERO"));
      disarmGuard();
      return;
    case RemoteCommand::kBack:
      Serial.println(F("ARIS_HW|REMOTE|BACK"));
      disarmGuard();
      return;
    case RemoteCommand::kUnknown:
      Serial.print(F("ARIS_HW|REMOTE|UNKNOWN|0x"));
      Serial.println(remote.lastCode(), HEX);
      return;
  }
}

// Nhận lệnh ASCII an toàn từ Python; không thực thi nội dung tùy ý trên Arduino.
void processSerialCommand(const char* command) {
  if (strcmp(command, "ARM") == 0) {
    armGuard();
  } else if (strcmp(command, "DISARM") == 0 || strcmp(command, "STOP") == 0) {
    disarmGuard();
  } else if (strcmp(command, "STATUS") == 0) {
    printState(guard.state());
  } else if (strcmp(command, "PING") == 0) {
    Serial.println(F("ARIS_HW|PONG|1"));
  } else {
    Serial.println(F("ARIS_HW|ERROR|UNKNOWN_COMMAND"));
  }
}

// Ghép một dòng Serial có giới hạn kích thước để tránh phân mảnh RAM trên UNO.
void handleSerialInput() {
  while (Serial.available() > 0) {
    const char value = static_cast<char>(Serial.read());
    if (value == '\r') {
      continue;
    }
    if (value == '\n') {
      serial_command[serial_command_length] = '\0';
      if (serial_command_length > 0) {
        processSerialCommand(serial_command);
      }
      serial_command_length = 0;
      continue;
    }
    if (serial_command_length < sizeof(serial_command) - 1) {
      serial_command[serial_command_length++] = value;
    } else {
      serial_command_length = 0;
      Serial.println(F("ARIS_HW|ERROR|COMMAND_TOO_LONG"));
    }
  }
}

// Chỉ đo khoảng cách khi sonar đang ARMING/ARMED/ALERT để trạng thái OFF thật sự nghỉ.
void updateSonar() {
  const unsigned long now_ms = millis();
  if (guard.state() == GuardState::kOff ||
      now_ms - last_sonar_sample_ms < aris_hardware::kSonarSampleIntervalMs) {
    return;
  }
  last_sonar_sample_ms = now_ms;
  const float distance_cm = sonar.readDistanceCm();
  publishGuardEvent(guard.update(now_ms, distance_cm));

  if (now_ms - last_distance_report_ms >= aris_hardware::kDistanceReportIntervalMs) {
    last_distance_report_ms = now_ms;
    Serial.print(F("ARIS_HW|DISTANCE_CM|"));
    Serial.println(distance_cm, 1);
  }
}

// Khởi tạo giao tiếp USB, sonar và IR rồi công bố firmware đã sẵn sàng.
void setup() {
  Serial.begin(115200);
  sonar.begin();
  remote.begin();
  Serial.println(F("ARIS_HW|READY|1"));
  printState(guard.state());
}

// Điều phối Serial, remote và sonar không dùng delay dài để giữ phản hồi nhanh.
void loop() {
  handleSerialInput();
  handleRemote();
  updateSonar();
}
