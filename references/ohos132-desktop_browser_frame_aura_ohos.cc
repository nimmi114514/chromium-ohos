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

#include "chrome/browser/ui/views/frame/desktop_browser_frame_aura_ohos.h"

#include "base/functional/bind.h"
#include "chrome/browser/ui/views/frame/browser_desktop_window_tree_host_ohos.h"
#include "chrome/browser/ui/views/frame/browser_frame.h"
#include "chrome/browser/ui/views/frame/browser_view.h"
#include "chrome/browser/ui/views/frame/native_browser_frame_factory.h"
#include "chrome/browser/ui/web_applications/app_browser_controller.h"
#include "ohos/adapter/device_info/device_info.h"
#include "ohos/adapter/xcomponent/adapter/window_adapter.h"
#include "ui/display/display.h"
#include "ui/display/screen.h"
#include "ui/gfx/geometry/transform.h"
#include "ui/views/widget/widget.h"

using WindowAdapter = ohos::adapter::xcomponent::WindowAdapter;
using DeviceType = ohos::adapter::device_info::DeviceType;
using DeviceInfo = ohos::adapter::device_info::DeviceInfo;

DesktopBrowserFrameAuraOhos::DesktopBrowserFrameAuraOhos(
    BrowserFrame* browser_frame,
    BrowserView* browser_view)
    : DesktopBrowserFrameAura(browser_frame, browser_view) {
  // Register to track when the widget has initialized. If a delegate is not
  // set, then the widget creator is responsible for calling
  // OnWidgetInitialized.
  views::WidgetDelegate* delegate = static_cast<views::WidgetDelegate*>(browser_view);
  if (delegate) {
    delegate->RegisterWidgetInitializedCallback(
        base::BindOnce(&DesktopBrowserFrameAuraOhos::OnWidgetInitialized,
                       base::Unretained(this)));
  }
}

DesktopBrowserFrameAuraOhos::~DesktopBrowserFrameAuraOhos() = default;

views::Widget::InitParams DesktopBrowserFrameAuraOhos::GetWidgetParams() {
  views::Widget::InitParams params(
      views::Widget::InitParams::NATIVE_WIDGET_OWNS_WIDGET);
  params.native_widget = this;

  Browser& browser = *browser_view()->browser();
  if (browser.is_type_devtools() || browser.is_type_popup()) {
    params.remove_standard_frame = false;
  } else {
    params.remove_standard_frame = !UseCustomFrame();
  }

  if ((browser.is_type_app() || browser.is_type_app_popup()) &&
      browser.profile()) {
    web_app::AppBrowserController* app_controller = browser.app_controller();
    if (app_controller) {
      params.app_id = app_controller->app_id();
    } else {
      const char kCrxAppPrefix[] = "_crx_";
      std::string app_id = browser.app_name();
      if (app_id.find(kCrxAppPrefix) != std::string::npos) {
        int length = sizeof(kCrxAppPrefix) / sizeof(char) - 1;
        app_id.replace(app_id.find(kCrxAppPrefix), length, "");
      }
      params.app_id = app_id;
    }
  } else {
    params.app_id = "";
  }

  return params;
}

bool DesktopBrowserFrameAuraOhos::UseCustomFrame() const {
  return false;
}

void DesktopBrowserFrameAuraOhos::OnWidgetInitialized() {
  gfx::AcceleratedWidget widget = host_->GetAcceleratedWidget();
  WindowAdapter::GetInstance().OnWindowInitDone(widget);
}

bool DesktopBrowserFrameAuraOhos::ShouldSaveWindowPlacement() const {
  return DeviceInfo::GetInstance().GetDeviceType() == DeviceType::_2IN1 &&
         !IsMinimized();
}

void DesktopBrowserFrameAuraOhos::GetWindowPlacement(
    gfx::Rect* bounds,
    ui::mojom::WindowShowState* show_state) const {
  *bounds = GetWidget()->GetRestoredBounds();
  if (IsMaximized())
    *show_state = ui::mojom::WindowShowState::kMaximized;
  else
    *show_state = ui::mojom::WindowShowState::kNormal;
}

NativeBrowserFrame* NativeBrowserFrameFactory::Create(
    BrowserFrame* browser_frame,
    BrowserView* browser_view) {
  return new DesktopBrowserFrameAuraOhos(browser_frame, browser_view);
}
