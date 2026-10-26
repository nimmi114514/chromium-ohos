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

#ifndef CHROME_BROWSER_UI_VIEWS_FRAME_DESKTOP_BROWSER_FRAME_AURA_OHOS_H_
#define CHROME_BROWSER_UI_VIEWS_FRAME_DESKTOP_BROWSER_FRAME_AURA_OHOS_H_

#include "base/memory/raw_ptr.h"
#include "chrome/browser/ui/views/frame/desktop_browser_frame_aura.h"

class BrowserDesktopWindowTreeHostOhos;

// Provides the window frame for the Chrome browser window on Desktop ohos.
class DesktopBrowserFrameAuraOhos : public DesktopBrowserFrameAura {
 public:
  DesktopBrowserFrameAuraOhos(BrowserFrame* browser_frame,
                              BrowserView* browser_view);

  DesktopBrowserFrameAuraOhos(const DesktopBrowserFrameAuraOhos&) = delete;
  DesktopBrowserFrameAuraOhos& operator=(const DesktopBrowserFrameAuraOhos&) =
      delete;

  void set_host(BrowserDesktopWindowTreeHostOhos* host) { host_ = host; }

 protected:
  ~DesktopBrowserFrameAuraOhos() override;

  views::Widget::InitParams GetWidgetParams() override;
  bool UseCustomFrame() const override;
  bool ShouldSaveWindowPlacement() const override;
  void GetWindowPlacement(
      gfx::Rect* bounds,
      ui::mojom::WindowShowState* show_state) const override;

 private:
  void OnWidgetInitialized();

  raw_ptr<BrowserDesktopWindowTreeHostOhos> host_ = nullptr;
};

#endif  // CHROME_BROWSER_UI_VIEWS_FRAME_DESKTOP_BROWSER_FRAME_AURA_OHOS_H_
