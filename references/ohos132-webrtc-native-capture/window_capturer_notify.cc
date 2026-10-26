/*
 * Copyright (c) 2023-2025 Haitai FangYuan Co., Ltd.
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this list of
 *    conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice, this list
 *    of conditions and the following disclaimer in the documentation and/or other materials
 *    provided with the distribution.
 *
 * 3. Neither the name of the copyright holder nor the names of its contributors may be used
 *    to endorse or promote products derived from this software without specific prior written
 *    permission.
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

#include "modules/desktop_capture/ohos/window_capturer_notify.h"

#include "base/logging.h"
#include "base/memory/singleton.h"

namespace webrtc {

void OnStateChange(struct OH_AVScreenCapture* capture,
                   OH_AVScreenCaptureStateCode stateCode,
                   void* userData) {
  auto callback =
      WindowCapturerNotify::GetInstance()->GetEventCallBack(capture);
  if (callback == nullptr) {
    LOG(ERROR) << "Get capturer callback error,capture=" << capture;
    return;
  }
  callback->OnStateChange(stateCode, userData);
}

void OnError(OH_AVScreenCapture* capture, int32_t errorCode, void* userData) {
  auto callback =
      WindowCapturerNotify::GetInstance()->GetEventCallBack(capture);
  if (callback == nullptr) {
    LOG(ERROR) << "Get capturer callback error,capture=" << capture;
    return;
  }
  callback->OnError(errorCode, userData);
}

void OnBufferAvailable(OH_AVScreenCapture* capture,
                       OH_AVBuffer* buffer,
                       OH_AVScreenCaptureBufferType bufferType,
                       int64_t timestamp,
                       void* userData) {
  auto callback =
      WindowCapturerNotify::GetInstance()->GetEventCallBack(capture);
  if (callback == nullptr) {
    LOG(ERROR) << "Get capturer callback error,capture=" << capture;
    return;
  }
  callback->OnBufferAvailable(buffer, bufferType, timestamp, userData);
}

WindowCapturerNotify* WindowCapturerNotify::GetInstance() {
  return base::Singleton<WindowCapturerNotify>::get();
}

WindowCapturerNotify::WindowCapturerNotify() {}

WindowCapturerNotify::~WindowCapturerNotify() {
  callback_map_.clear();
}

CapturerEventCallBack* WindowCapturerNotify::GetEventCallBack(
    OH_AVScreenCapture* capture) {
  if (callback_map_.find(capture) != callback_map_.end()) {
    return callback_map_[capture].get();
  }

  return nullptr;
}

bool WindowCapturerNotify::RegisterEventCallback(
    OH_AVScreenCapture* capture,
    std::shared_ptr<CapturerEventCallBack> callback,
    void* userData) {
  if (callback_map_.count(capture)) {
    return true;
  }

  OH_AVSCREEN_CAPTURE_ErrCode errCode =
      OH_AVScreenCapture_SetErrorCallback(capture, OnError, userData);
  if (errCode != AV_SCREEN_CAPTURE_ERR_OK) {
    LOG(ERROR) << "screen capture set error callback failed, errCode:"
               << errCode;
    return false;
  }

  errCode =
      OH_AVScreenCapture_SetStateCallback(capture, OnStateChange, userData);
  if (errCode != AV_SCREEN_CAPTURE_ERR_OK) {
    LOG(ERROR) << "screen capture set state callback failed, errCode:"
               << errCode;
    return false;
  }

  errCode =
      OH_AVScreenCapture_SetDataCallback(capture, OnBufferAvailable, userData);
  if (errCode != AV_SCREEN_CAPTURE_ERR_OK) {
    LOG(ERROR) << "screen capture set data callback failed, errCode:"
               << errCode;
    return false;
  }
  callback_map_[capture] = std::move(callback);
  return true;
}

void WindowCapturerNotify::UnRegisterEventCallback(
    OH_AVScreenCapture* capture) {
  if (!callback_map_.count(capture)) {
    return;
  }
  callback_map_.erase(capture);
}

}  // namespace webrtc
