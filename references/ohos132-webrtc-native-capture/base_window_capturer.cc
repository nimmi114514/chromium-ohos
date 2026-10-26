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

#include "modules/desktop_capture/ohos/base_window_capturer.h"

#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

#include <limits>
#include <string>
#include <utility>

#include "absl/memory/memory.h"
#include "base/logging.h"
#include "base/memory/platform_shared_memory_region.h"
#include "base/memory/ptr_util.h"
#include "base/memory/read_only_shared_memory_region.h"
#include "base/ohos/task_scheduler/task_runner_ohos.h"
#include "base/task/single_thread_task_runner.h"
#include "modules/desktop_capture/desktop_capture_options.h"
#include "modules/desktop_capture/desktop_capturer.h"
#include "modules/desktop_capture/ohos/capturer_event_callback.h"
#include "modules/desktop_capture/ohos/desktop_capture_utils.h"
#include "modules/desktop_capture/ohos/window_capturer_notify.h"
#include "ohos/adapter/screen_capture/screen_capture_adapter.h"
#include "rtc_base/checks.h"
#include "rtc_base/logging.h"
#include "rtc_base/string_encode.h"
#include "rtc_base/string_to_number.h"
#include "rtc_base/time_utils.h"
#include "system_wrappers/include/sleep.h"

namespace webrtc {
namespace {
constexpr int32_t kVideoFrameWidth = 1024;
constexpr int32_t kVideoFrameHeight = 1080;
constexpr int32_t kVideoBitrate = 2000000;
constexpr int32_t kVideoFrameRate = 30;

void OnCaptureContentChanged(OH_AVScreenCapture* capture,
                             OH_AVScreenCaptureContentChangedEvent event,
                             OH_Rect* area,
                             void* user_data) {
  if (!user_data) {
    LOG(ERROR) << "OnCaptureContentChanged failed, userData is nullptr";
    return;
  }
  if (event == OH_SCREEN_CAPTURE_CONTENT_UNAVAILABLE) {
    base::TaskRunnerOHOS::GetUIThreadTaskRunner()->PostTask(
        FROM_HERE,
        base::BindOnce(&BaseWindowCapturer::StopCapture,
                       ((BaseWindowCapturer*)(user_data))->GetWeakPtr()));
  }
}

class SharedMemoryImpl : public webrtc::SharedMemory {
 public:
  static std::unique_ptr<SharedMemoryImpl> Create(size_t size, int id) {
    webrtc::SharedMemory::Handle handle = webrtc::SharedMemory::kInvalidHandle;
    base::MappedReadOnlyRegion region_mapping =
        base::ReadOnlySharedMemoryRegion::Create(size);
    base::ReadOnlySharedMemoryRegion read_only_region =
        std::move(region_mapping.region);
    base::WritableSharedMemoryMapping mapping =
        std::move(region_mapping.mapping);
    if (!mapping.IsValid())
      return nullptr;
    // The SharedMemoryImpl ctor is private, so std::make_unique can't be
    // used.
    return base::WrapUnique(new SharedMemoryImpl(
        std::move(read_only_region), std::move(mapping), handle, id));
  }

  SharedMemoryImpl(const SharedMemoryImpl&) = delete;
  SharedMemoryImpl& operator=(const SharedMemoryImpl&) = delete;

  ~SharedMemoryImpl() override {}

  const base::ReadOnlySharedMemoryRegion& region() const { return region_; }

 private:
  SharedMemoryImpl(base::ReadOnlySharedMemoryRegion region,
                   base::WritableSharedMemoryMapping mapping,
                   webrtc::SharedMemory::Handle handle,
                   int id)
      : SharedMemory(mapping.memory(), mapping.size(), handle, id) {
    region_ = std::move(region);
    mapping_ = std::move(mapping);
  }

  base::ReadOnlySharedMemoryRegion region_;
  base::WritableSharedMemoryMapping mapping_;
};

class SharedMemoryFactoryImpl : public webrtc::SharedMemoryFactory {
 public:
  explicit SharedMemoryFactoryImpl() {}

  SharedMemoryFactoryImpl(const SharedMemoryFactoryImpl&) = delete;
  SharedMemoryFactoryImpl& operator=(const SharedMemoryFactoryImpl&) = delete;

  std::unique_ptr<webrtc::SharedMemory> CreateSharedMemory(
      size_t size) override {
    std::unique_ptr<SharedMemoryImpl> buffer =
        SharedMemoryImpl::Create(size, next_shared_buffer_id_);
    if (buffer) {
      next_shared_buffer_id_ += 2;
    }
    return std::move(buffer);
  }

 private:
  int next_shared_buffer_id_ = 1;
};
}  // namespace

class OHOSScreenCaptureCallback final : public webrtc::CapturerEventCallBack {
 public:
  explicit OHOSScreenCaptureCallback(base::WeakPtr<BaseWindowCapturer> capturer)
      : capturer_(capturer) {
    DCHECK(capturer_);
  }

  OHOSScreenCaptureCallback(const OHOSScreenCaptureCallback&) = delete;
  OHOSScreenCaptureCallback& operator=(const OHOSScreenCaptureCallback&) =
      delete;

  ~OHOSScreenCaptureCallback() = default;

  void OnStateChange(OH_AVScreenCaptureStateCode stateCode,
                     void* userData) override {
    capturer_->HandleStateChange(stateCode, userData);
  }

  void OnError(int32_t errorCode, void* userData) override {
    capturer_->HandleError(errorCode, userData);
  }

  void OnBufferAvailable(OH_AVBuffer* buffer,
                         OH_AVScreenCaptureBufferType bufferType,
                         int64_t timestamp,
                         void* userData) override {
    capturer_->HandleBuffer(buffer, bufferType, timestamp, userData);
  }

 private:
  base::WeakPtr<BaseWindowCapturer> capturer_;
};

void BaseWindowCapturer::SetSharedMemoryFactory(
    std::unique_ptr<SharedMemoryFactory> shared_memory_factory) {
  shared_memory_factory_ = std::move(shared_memory_factory);
}

BaseWindowCapturer::BaseWindowCapturer(CaptureSourceType source_type)
    : capture_source_type_(source_type) {}

BaseWindowCapturer::~BaseWindowCapturer() {
  if (screen_capture_) {
    webrtc::WindowCapturerNotify::GetInstance()->UnRegisterEventCallback(
        screen_capture_);
    OH_AVScreenCapture_StopScreenCapture(screen_capture_);
    OH_AVScreenCapture_Release(screen_capture_);
    screen_capture_ = nullptr;
  }
  SetState(false);
  queue_.Reset();
}

bool BaseWindowCapturer::Init(const DesktopCaptureOptions& options) {
  if (!options.use_system_picker()) {
    return true;
  }

  options_ = options;

  ohos::adapter::ScreenAdapter::GetInstance().GetPrimaryDisplay(ohos_screen_);
  int32_t videoFrameWidth =
      ohos_screen_.width > 0 ? ohos_screen_.width : kVideoFrameWidth;
  int32_t videoFrameHeight =
      ohos_screen_.height > 0 ? ohos_screen_.height : kVideoFrameHeight;

  screen_capture_ = OH_AVScreenCapture_Create();
  if (!screen_capture_) {
    LOG(ERROR) << __func__ << " [WebRTC] Create screen capture adapter failed";
    return false;
  }

  OH_VideoCaptureInfo videoCapInfo = {
      .videoFrameWidth = videoFrameWidth,
      .videoFrameHeight = videoFrameHeight,
      .videoSource = OH_VideoSourceType::OH_VIDEO_SOURCE_SURFACE_RGBA};
  OH_VideoEncInfo videoEncInfo = {.videoCodec = OH_VideoCodecFormat::OH_H264,
                                  .videoBitrate = kVideoBitrate,
                                  .videoFrameRate = kVideoFrameRate};
  OH_VideoInfo videoInfo = {.videoCapInfo = videoCapInfo,
                            .videoEncInfo = videoEncInfo};

  OH_AVSCREEN_CAPTURE_ErrCode ret =
      ohos::adapter::ScreenCaptureAdapter::GetInstance()
          .SetCaptureContentChanged(screen_capture_, OnCaptureContentChanged,
                                    this);
  if (ret != AV_SCREEN_CAPTURE_ERR_OK) {
    LOG(ERROR) << "[WebRTC] Failed to set capture content change,result: "
               << ret;
  }

  OH_AVScreenCaptureConfig config = {
      .captureMode = OH_CAPTURE_SPECIFIED_WINDOW,
      .dataType = OH_DataType::OH_ORIGINAL_STREAM,
      .videoInfo = videoInfo};

  if (options.prefer_cursor_embedded()) {
    ret = ohos::adapter::ScreenCaptureAdapter::GetInstance().ShowCursor(
        screen_capture_);
    if (ret != AV_SCREEN_CAPTURE_ERR_OK) {
      LOG(ERROR) << "[WebRTC] Failed to set show cursor,result: " << ret;
    }
  }

  // Whether the auto-rotation setting is successful or not, you should proceed.
  if (!ohos::adapter::ScreenCaptureAdapter::GetInstance().SetAutoRotation(
          screen_capture_)) {
    LOG(ERROR) << "[WebRTC] Failed to set automatic screen rotation for shared "
                  "screen.";
  }

  auto callback =
      std::make_shared<OHOSScreenCaptureCallback>(weak_factory_.GetWeakPtr());
  if (!webrtc::WindowCapturerNotify::GetInstance()->RegisterEventCallback(
          screen_capture_, callback, this)) {
    return false;
  }

  OH_AVSCREEN_CAPTURE_ErrCode errCode =
      OH_AVScreenCapture_Init(screen_capture_, config);
  if (errCode != AV_SCREEN_CAPTURE_ERR_OK) {
    LOG(ERROR) << __func__
               << " [WebRTC] Screen capture init failed, errCode:" << errCode;
    return false;
  }
  return true;
}

void BaseWindowCapturer::HandleStateChange(
    OH_AVScreenCaptureStateCode stateCode,
    void* userData) {
  switch (stateCode) {
    case OH_SCREEN_CAPTURE_STATE_STARTED:
      SetState(true);
      break;
    case OH_SCREEN_CAPTURE_STATE_CANCELED:
    case OH_SCREEN_CAPTURE_STATE_STOPPED_BY_USER:
    case OH_SCREEN_CAPTURE_STATE_INTERRUPTED_BY_OTHER:
      StopCapture();
      break;
    default:
      break;
  }
}

void BaseWindowCapturer::HandleError(int32_t errorCode, void* userData) {}

void BaseWindowCapturer::HandleBuffer(OH_AVBuffer* buffer,
                                      OH_AVScreenCaptureBufferType bufferType,
                                      int64_t timestamp,
                                      void* userData) {
  if (bufferType != OH_SCREEN_CAPTURE_BUFFERTYPE_VIDEO) {
    LOG(WARNING) << __func__ << " [WebRTC] Buffer type not correct: "
                 << static_cast<int>(bufferType);
    return;
  }

  webrtc::MutexLock lock(&current_frame_lock_);

  std::unique_ptr<NativeFrame> native_frame = NativeFrame::Create(buffer);
  if (!native_frame) {
    LOG(ERROR) << " [WebRTC] Acquire video buffer failed";
    StopCapture();
    return;
  }

  int32_t image_width = native_frame->image_width();
  int32_t image_height = native_frame->image_height();
  int32_t image_stride = native_frame->image_stride();

  queue_.MoveToNextFrame();
  if (queue_.current_frame() && queue_.current_frame()->frame() &&
      queue_.current_frame()->frame()->IsShared()) {
    LOG(WARNING) << __func__
                 << " [WebRTC] Overwriting frame that is still shared.";
  }

  DesktopSize image_size(image_width, image_height);
  if (!queue_.current_frame()) {
    queue_.ReplaceCurrentFrame(
        std::make_unique<DesktopCaptureFrame>(shared_memory_factory_.get()));
  }

  DesktopCaptureFrame* frame = queue_.current_frame();
  if (!frame->Prepare(image_size)) {
    LOG(ERROR) << __func__ << " [WebRTC] Cannot create a new DesktopFrame";
    return;
  }
  frame->frame()->mutable_updated_region()->Clear();

  uint8_t* src_data = native_frame->GetBuffer();
  if (!src_data) {
    LOG(ERROR) << __func__ << " [WebRTC] Get native buffer failed";
    return;
  }

  DesktopFrame* current_frame = frame->frame();
  current_frame->CopyPixelsFrom(src_data, image_stride,
                                DesktopRect::MakeSize(current_frame->size()));
  // The format of frame captured by OH is RGBA
  RGBAtoBGRAportable(
      reinterpret_cast<uint32_t*>(current_frame->data()),
      reinterpret_cast<uint32_t*>(current_frame->data()),
      current_frame->size().width() * current_frame->size().height());
  current_frame->mutable_updated_region()->SetRect(
      DesktopRect::MakeSize(current_frame->size()));

  return;
}

void BaseWindowCapturer::Start(Callback* callback) {
  RTC_DCHECK(!callback_);
  RTC_DCHECK(callback);
  (void)capture_source_type_;
  callback_ = callback;

  if (is_start_) {
    LOG(INFO) << __func__
              << " [WebRTC] Already started, no need to start again";
    return;
  }

  OH_AVSCREEN_CAPTURE_ErrCode errCode =
      OH_AVScreenCapture_StartScreenCapture(screen_capture_);
  if (errCode != AV_SCREEN_CAPTURE_ERR_OK) {
    LOG(ERROR) << __func__
               << " [WebRTC] Start capture failed, errCode:" << errCode;
    return;
  }
  SetState(true);
}

void BaseWindowCapturer::CaptureFrame() {
  if (!is_start_) {
    LOG(ERROR) << __func__
               << " [WebRTC] Failed to capture frame, no start pipeline";
    callback_->OnCaptureResult(Result::ERROR_PERMANENT, nullptr);
    return;
  }

  if (options_.allow_sync_capturer()) {
    return DoCaptureSync();
  }

  DoCapture();
}

bool BaseWindowCapturer::GetSourceList(SourceList* sources) {
  switch (capture_source_type_) {
    case BaseWindowCapturer::CaptureSourceType::kScreen:
      RTC_DCHECK(sources->size() == 0);
      sources->push_back({ohos_screen_.id, ohos_screen_.name});
      return true;
    case BaseWindowCapturer::CaptureSourceType::kWindow:
      LOG(WARNING) << __func__
                   << " [WebRTC] Capture window frame not supported";
      break;
    default:
      break;
  }

  return false;
}

bool BaseWindowCapturer::SelectSource(SourceId id) {
  select_source_id_ = id;
  return true;
}

void BaseWindowCapturer::DoCapture() {
  webrtc::MutexLock lock(&current_frame_lock_);
  if (!queue_.current_frame() || !queue_.current_frame()->frame()) {
    LOG(WARNING) << __func__ << " [WebRTC] No frames with a temporary error";
    callback_->OnCaptureResult(Result::ERROR_TEMPORARY, nullptr);
    return;
  }

  // Emit the current frame.
  std::unique_ptr<DesktopFrame> frame =
      queue_.current_frame()->frame()->Share();
  if (!frame) {
    LOG(ERROR) << __func__ << " [WebRTC] Failed to capture screen.";
    callback_->OnCaptureResult(Result::ERROR_PERMANENT, nullptr);
    return;
  }
  callback_->OnCaptureResult(Result::SUCCESS, std::move(frame));
}

bool BaseWindowCapturer::EnsureFrameCaptured() {
  // On a modern system, the FPS / monitor refresh rate is usually larger than
  // or equal to 60. So 17 milliseconds is enough to capture at least one frame.
  const int64_t ms_per_frame = 17;
  const int64_t timeout_ms = std::numeric_limits<int>::max();

  const int64_t start_ms = rtc::TimeMillis();
  while (is_start_) {
    if (queue_.current_frame() && queue_.current_frame()->frame()) {
      break;
    }

    if (rtc::TimeMillis() - start_ms > timeout_ms) {
      LOG(ERROR) << "Failed to capture frames within " << timeout_ms
                 << " milliseconds.";
      return false;
    }

    // Sleep `ms_per_frame` before attempting to capture the next frame to
    // ensure the video adapter has time to update the screen.
    webrtc::SleepMs(ms_per_frame);
  }
  return true;
}

void BaseWindowCapturer::DoCaptureSync() {
  if (!EnsureFrameCaptured()) {
    callback_->OnCaptureResult(Result::ERROR_PERMANENT, nullptr);
    return;
  }
  DoCapture();
}

void BaseWindowCapturer::StopCapture() {
  if (screen_capture_) {
    OH_AVScreenCapture_StopScreenCapture(screen_capture_);
  }

  SetState(false);
}

base::WeakPtr<BaseWindowCapturer> BaseWindowCapturer::GetWeakPtr() {
  return weak_factory_.GetWeakPtr();
}

// static
std::unique_ptr<DesktopCapturer> BaseWindowCapturer::CreateRawCapturer(
    const DesktopCaptureOptions& options,
    const BaseWindowCapturer::CaptureSourceType& type) {
  std::unique_ptr<BaseWindowCapturer> capturer =
      std::make_unique<BaseWindowCapturer>(type);
  if (!capturer.get()->Init(options)) {
    return nullptr;
  }

  return std::move(capturer);
}

}  // namespace webrtc
