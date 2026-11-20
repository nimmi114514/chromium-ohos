#!/usr/bin/env python3
"""Check production placement methods with host window/WindowStage mocks."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from test_hwc_window_lifecycle import method

ROOT = Path(__file__).resolve().parents[1]
window = (ROOT / "src/ui/ozone/platform/ohos/host/ohos_toplevel_window.cc").read_text()
browser = (ROOT / "src/chrome/browser/ui/views/frame/browser_native_widget_aura_ohos.cc").read_text()
host = (ROOT / "src/chrome/browser/ui/views/frame/browser_desktop_window_tree_host_ohos.cc").read_text()
assert "is_shown_" not in window
harness = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <optional>
namespace gfx {
struct Size {
 int w=0,h=0;
 bool IsEmpty() const { return w<=0 || h<=0; }
 int width()const{return w;} int height()const{return h;}
 void SetToMin(Size o){w=std::min(w,o.w);h=std::min(h,o.h);}
 void SetToMax(Size o){w=std::max(w,o.w);h=std::max(h,o.h);}
 bool operator==(const Size&)const=default;
};
struct Rect {
 int l=0,t=0,w=0,h=0;
 int x()const{return l;} int y()const{return t;}
 int width()const{return w;} int height()const{return h;}
 Size size()const{return {w,h};}
 void set_size(Size s){w=s.w;h=s.h;}
 bool operator==(const Rect&)const=default;
};
struct RectF {
 float l,t,w,h;
 explicit RectF(Rect r):l(r.l),t(r.t),w(r.w),h(r.h){}
 RectF(float x,float y,float width,float height):l(x),t(y),w(width),h(height){}
};
Rect ToRoundedRect(RectF r){
 int l=std::lround(r.l),t=std::lround(r.t);
 return {l,t,static_cast<int>(std::lround(r.l+r.w))-l,
   static_cast<int>(std::lround(r.t+r.h))-t};
}
}
struct WindowRect {int left,top,width,height;};
struct WindowAdapter {
 bool initialized=false;
 static WindowAdapter& GetInstance(){static WindowAdapter a;return a;}
 bool WindowHasInit(int)const{return initialized;}
};
struct AppWindowAdapter {
 int writes=0;
 static AppWindowAdapter& GetInstance(){static AppWindowAdapter a;return a;}
 void SetBounds(int,WindowRect){++writes;}
};
using SystemFloatingWindowAdapter=AppWindowAdapter;
constexpr int kDefaultWidget=0;
struct NodeHandleImpl {
 static NodeHandleImpl& GetInstance(){static NodeHandleImpl n;return n;}
 bool IsSupportNodeHandle()const{return false;}
};
struct OhosWindow {
 void BindNodeHandle(){} void Show(bool){}
};
class OhosToplevelWindow : public OhosWindow {
 public:
 bool need_create_ability_=false,is_split_screen_=false;
 std::optional<gfx::Rect> pending_initial_bounds_in_pixels_;
 int widget=0,notifications=0;bool use_floating_window_=false;
 gfx::Rect bounds_in_pixels_{100,100,900,700},previous_bounds_in_pixels_;
 gfx::Size min_size_in_pixels_{100,100},max_size_in_pixels_;
 int GetWidget()const{return widget;}
 void UpdateMinAndMaxSize(){}
 void Applied(gfx::Rect,gfx::Rect){++notifications;}
 void CreateAndShowInternal(){}
 void Show(bool);
 bool HasInitDone();
 void SetBoundsInPixels(const gfx::Rect&);
};
namespace ohos::adapter {
struct ContextAdapter {
 bool pc=false,free=false;
 static ContextAdapter& GetInstance(){static ContextAdapter a;return a;}
 bool IsPcMode()const{return pc;}bool IsFreeWindowsMode()const{return free;}
};
namespace device_info {
enum class DeviceType {_TABLET,_2IN1};
struct DeviceInfo {
 DeviceType type=DeviceType::_TABLET;
 static DeviceInfo& GetInstance(){static DeviceInfo a;return a;}
 DeviceType GetDeviceType()const{return type;}
};
}
}
namespace ui::mojom {enum class WindowShowState{kNormal,kMaximized};}
struct Transform {
 float scale=1,offset=0;
 std::optional<gfx::RectF> InverseMapRect(gfx::RectF r)const{
  return gfx::RectF{(r.l-offset)/scale,r.t/scale,r.w/scale,r.h/scale};
 }
};
struct NativeHost {
 gfx::Rect pixels{100,110,900,600};Transform transform;
 gfx::Rect GetBoundsInPixels()const{return pixels;}
 const Transform& GetRootTransform()const{return transform;}
};
struct NativeWindow {
 NativeHost host;
 const NativeHost* GetHost()const{return &host;}
};
struct Widget {
 NativeWindow native;
 const NativeWindow* GetNativeWindow()const{return &native;}
 gfx::Rect restored{50,60,800,500},live{100,110,900,600};
 gfx::Rect GetRestoredBounds()const{return restored;}
 gfx::Rect GetWindowBoundsInScreen()const{return live;}
};
class BrowserNativeWidgetAuraOhos {
 public:
 Widget widget;bool maximized=false;
 const Widget* GetWidget()const{return &widget;}
 bool IsMaximized()const{return maximized;}
 bool ShouldSaveWindowPlacement()const;
 void GetWindowPlacement(gfx::Rect*,ui::mojom::WindowShowState*)const;
};

namespace views {
struct DesktopWindowTreeHostOhos {
 bool maximized=false,minimized=false,fullscreen=false;
 gfx::Rect pixels;Transform transform;
 bool IsMaximized()const{return maximized;}
 bool IsMinimized()const{return minimized;}
 bool IsFullscreen()const{return fullscreen;}
 gfx::Rect GetBoundsInPixels()const{return pixels;}
 const Transform& GetRootTransform()const{return transform;}
 gfx::Rect GetRestoredBounds()const{return {50,60,800,500};}
};
}
class BrowserDesktopWindowTreeHostOhos:public views::DesktopWindowTreeHostOhos {
 public:gfx::Rect GetRestoredBounds()const;
};
'''
for source, signature in [
    (window, "bool OhosToplevelWindow::HasInitDone()"),
    (window, "void OhosToplevelWindow::Show(bool inactive)"),
    (window, "void OhosToplevelWindow::SetBoundsInPixels("),
    (browser, "bool BrowserNativeWidgetAuraOhos::ShouldSaveWindowPlacement() const"),
    (browser, "void BrowserNativeWidgetAuraOhos::GetWindowPlacement("),
    (host, "gfx::Rect BrowserDesktopWindowTreeHostOhos::GetRestoredBounds() const"),
]:
    harness += method(source, signature)
harness += r'''
int main(){
 OhosToplevelWindow w;
 auto original=w.bounds_in_pixels_;
 w.SetBoundsInPixels({5,6,700,400});
 assert(w.bounds_in_pixels_==original && w.notifications==0);
 assert((w.pending_initial_bounds_in_pixels_==gfx::Rect{5,6,700,400}));
 w.SetBoundsInPixels({7,8,800,500});
 auto& adapter=WindowAdapter::GetInstance();
 adapter.initialized=true;
 auto& context=ohos::adapter::ContextAdapter::GetInstance();
 context.pc=true;
 w.Show(false);
 assert((w.bounds_in_pixels_==gfx::Rect{7,8,800,500}) && w.notifications==1);
 assert(!w.pending_initial_bounds_in_pixels_);
 w.Show(false);assert(w.notifications==1);
 w.SetBoundsInPixels({5,6,700,400});
 assert((w.bounds_in_pixels_==gfx::Rect{5,6,700,400}) && w.notifications==2);
 adapter.initialized=false;
 w.widget=7;
 w.SetBoundsInPixels({1600,900,640,360});
 assert((w.bounds_in_pixels_==gfx::Rect{1600,900,640,360}));
 w.SetBoundsInPixels({1800,500,360,640});
 assert((w.bounds_in_pixels_==gfx::Rect{1800,500,360,640}));
 w.SetBoundsInPixels({0,0,20,30});
 assert((w.bounds_in_pixels_.size()==gfx::Size{100,100}));
 BrowserNativeWidgetAuraOhos b;
 context.pc=false;
 assert(!b.ShouldSaveWindowPlacement());
 context.pc=true;assert(b.ShouldSaveWindowPlacement());
 context.pc=false;context.free=true;assert(b.ShouldSaveWindowPlacement());
 context.free=false;
 OhosToplevelWindow system_window;
 adapter.initialized=false;
 system_window.SetBoundsInPixels({5,6,700,400});
 adapter.initialized=true;system_window.Show(false);
 assert((system_window.bounds_in_pixels_==gfx::Rect{100,100,900,700}));
 context.free=true;system_window.is_split_screen_=true;
 adapter.initialized=false;system_window.SetBoundsInPixels({5,6,700,400});
 adapter.initialized=true;system_window.Show(false);
 assert((system_window.bounds_in_pixels_==gfx::Rect{100,100,900,700}));
 context.free=false;
 ohos::adapter::device_info::DeviceInfo::GetInstance().type=
   ohos::adapter::device_info::DeviceType::_2IN1;
 assert(b.ShouldSaveWindowPlacement());
 gfx::Rect bounds;ui::mojom::WindowShowState state;
 b.GetWindowPlacement(&bounds,&state);
 assert(bounds==b.widget.live && state==ui::mojom::WindowShowState::kNormal);
 b.maximized=true;b.GetWindowPlacement(&bounds,&state);
 assert(bounds==b.widget.restored && state==ui::mojom::WindowShowState::kMaximized);
 BrowserDesktopWindowTreeHostOhos h;
 for(float scale:{1.f,1.25f,1.5f,2.f,16.f/7.f}){
  h.transform={scale,2000};
  const gfx::Rect original{100,120,850,600};bounds=original;
  for(int i=0;i<100;++i){
   const int l=std::floor(bounds.l*scale+2000),t=std::floor(bounds.t*scale);
   h.pixels={l,t,static_cast<int>(std::ceil((bounds.l+bounds.w)*scale+2000))-l,
     static_cast<int>(std::ceil((bounds.t+bounds.h)*scale))-t};
   bounds=h.GetRestoredBounds();assert(bounds==original);
  }
 }
 h.maximized=true;bounds=h.GetRestoredBounds();
 assert((bounds==gfx::Rect{50,60,800,500}));
}
'''
with tempfile.TemporaryDirectory(prefix="ohos-window-placement-") as directory:
    p = Path(directory)
    (p / "test.cc").write_text(harness)
    compiler = os.environ.get("CXX") or shutil.which("g++")
    subprocess.run([compiler, "-std=c++20", "-g", "-O1",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    str(p / "test.cc"), "-o", str(p / "test")], check=True)
    subprocess.run([str(p / "test")], check=True)
print("PASS: first-window initialization, new/PiP bounds, and placement modes")
