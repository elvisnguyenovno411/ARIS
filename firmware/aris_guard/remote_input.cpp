#include "remote_input.h"

#include <IRremote.hpp>

#include "hardware_config.h"

void RemoteInput::begin() {
  IrReceiver.begin(aris_hardware::kIrReceivePin, ENABLE_LED_FEEDBACK);
}

RemoteCommand RemoteInput::poll() {
  if (!IrReceiver.decode()) {
    return RemoteCommand::kNone;
  }

  const bool repeated =
      IrReceiver.decodedIRData.flags & IRDATA_FLAGS_IS_REPEAT;
  last_code_ = IrReceiver.decodedIRData.command;
  IrReceiver.resume();
  if (repeated) {
    return RemoteCommand::kNone;
  }

  switch (last_code_) {
    case aris_hardware::kRemotePower:
      return RemoteCommand::kPower;
    case aris_hardware::kRemoteOk:
      return RemoteCommand::kOk;
    case aris_hardware::kRemoteZero:
      return RemoteCommand::kZero;
    case aris_hardware::kRemoteBack:
      return RemoteCommand::kBack;
    default:
      return RemoteCommand::kUnknown;
  }
}

uint16_t RemoteInput::lastCode() const {
  return last_code_;
}
