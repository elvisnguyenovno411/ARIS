#include "guard_state.h"

#include "hardware_config.h"

GuardEvent GuardStateMachine::arm(unsigned long now_ms) {
  if (state_ != GuardState::kOff) {
    return GuardEvent::kNone;
  }
  state_ = GuardState::kArming;
  arming_started_ms_ = now_ms;
  consecutive_near_samples_ = 0;
  return GuardEvent::kArmingStarted;
}

GuardEvent GuardStateMachine::disarm() {
  if (state_ == GuardState::kOff) {
    return GuardEvent::kNone;
  }
  state_ = GuardState::kOff;
  consecutive_near_samples_ = 0;
  return GuardEvent::kDisarmed;
}

GuardEvent GuardStateMachine::update(unsigned long now_ms, float distance_cm) {
  if (state_ == GuardState::kArming &&
      now_ms - arming_started_ms_ >= aris_hardware::kArmingDelayMs) {
    state_ = GuardState::kArmed;
    consecutive_near_samples_ = 0;
    return GuardEvent::kArmed;
  }

  if (state_ != GuardState::kArmed || distance_cm <= 0.0F) {
    return GuardEvent::kNone;
  }

  if (distance_cm <= aris_hardware::kAlertDistanceCm) {
    consecutive_near_samples_++;
  } else {
    consecutive_near_samples_ = 0;
  }

  if (consecutive_near_samples_ < aris_hardware::kNearSamplesRequired) {
    return GuardEvent::kNone;
  }
  state_ = GuardState::kAlert;
  consecutive_near_samples_ = 0;
  return GuardEvent::kAlertStarted;
}

GuardState GuardStateMachine::state() const {
  return state_;
}
