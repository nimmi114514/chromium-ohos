/*
 * Copyright (c) 2023-2025 Huawei Device Co., Ltd.
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 * this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation
 * and/or other materials provided with the distribution.
 *
 * 3. Neither the name of the copyright holder nor the names of its contributors
 * may be used to endorse or promote products derived from this software without
 * specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
 * ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "ui/base/pointer/pointer_device.h"
#include "base/check_op.h"
#include "ui/events/devices/device_data_manager.h"

namespace ui {
const int kMaxTouchPointerOhos = 2;
namespace {

bool IsTouchDevicePresent() {
  return !DeviceDataManager::GetInstance()->GetTouchscreenDevices().empty();
}

bool IsMouseOrTouchpadPresent() {
  DeviceDataManager* device_data_manager = DeviceDataManager::GetInstance();
  for (const ui::InputDevice& device :
       device_data_manager->GetTouchpadDevices()) {
    if (device.enabled) {
        return true;
    }
  }
  // We didn't find a touchpad then let's look if there is a mouse connected.
  for (const ui::InputDevice& device : device_data_manager->GetMouseDevices()) {
    if (device.enabled) {
        return true;
    }
  }
  // We didn't find a mouse then let's look if there is a pointing stick
  // connected.
  for (const ui::InputDevice& device :
       device_data_manager->GetPointingStickDevices()) {
    if (device.enabled) {
      return true;
    }
  }
  return false;
}

}  // namespace

int GetAvailablePointerTypes() {
  int available_pointer_types = 0;
  if (IsMouseOrTouchpadPresent()) {
    available_pointer_types |= POINTER_TYPE_FINE;
  }

  if (IsTouchDevicePresent()) {
    available_pointer_types |= POINTER_TYPE_COARSE;
  }

  if (available_pointer_types == 0) {
    available_pointer_types = POINTER_TYPE_NONE;
  }

  DCHECK(available_pointer_types);
  return available_pointer_types;
}

int GetAvailableHoverTypes() {
  if (IsMouseOrTouchpadPresent()) {
    return HOVER_TYPE_HOVER;
  }

  return HOVER_TYPE_NONE;
}

TouchScreensAvailability GetTouchScreensAvailability() {
  if (!IsTouchDevicePresent()) {
    return TouchScreensAvailability::NONE;
  }

  return DeviceDataManager::GetInstance()->AreTouchscreensEnabled()
             ? TouchScreensAvailability::ENABLED
             : TouchScreensAvailability::DISABLED;
}

int MaxTouchPoints() {
    return kMaxTouchPointerOhos;
}

PointerType GetPrimaryPointerType(int available_pointer_types) {
  if (available_pointer_types & POINTER_TYPE_FINE) {
    return POINTER_TYPE_FINE;
  }
  if (available_pointer_types & POINTER_TYPE_COARSE) {
    return POINTER_TYPE_COARSE;
  }
  DCHECK_EQ(available_pointer_types, POINTER_TYPE_NONE);
  return POINTER_TYPE_NONE;
}

HoverType GetPrimaryHoverType(int available_hover_types) {
  if (available_hover_types & HOVER_TYPE_HOVER) {
    return HOVER_TYPE_HOVER;
  }
  DCHECK_EQ(available_hover_types, HOVER_TYPE_NONE);
  return HOVER_TYPE_NONE;
}

std::optional<PointerDevice> GetPointerDevice(PointerDevice::Key key) {
  return std::nullopt;
}

std::vector<PointerDevice> GetPointerDevices() {
  return {};
}

}  // namespace ui