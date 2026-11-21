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
#include <cstdint>
#include <optional>
#include <string>
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
enum class WindowStatusType{UNDEFINED,MAXIMIZE};
enum class PlatformWindowState{kNormal,kMaximized,kMinimized,kFullScreen};
struct WindowInitParameter {
  WindowRect bounds{0,0,0,0};
  struct {int a=0,b=0,c=0,d=0;} window_limit;
  WindowStatusType status=WindowStatusType::UNDEFINED;
  void SetBackground(uint32_t){}
  uint32_t background_color_argb=0;
  bool hide_title_bar=false,use_floating_window=false,use_dark_mode=false;
  bool caption_button_visible=true;
  std::string window_id;
  int ability_type=0;
  std::string app_id;
};
struct WindowAdapter {
 bool initialized=false;
 static WindowAdapter& GetInstance(){static WindowAdapter a;return a;}
 bool WindowHasInit(int)const{return initialized;}
};
struct AppWindowAdapter {
 int writes=0;
 static AppWindowAdapter& GetInstance(){static AppWindowAdapter a;return a;}
 void SetBounds(int,WindowRect){++writes;}
 void SetTitle(const std::string&,int){}
};
using SystemFloatingWindowAdapter=AppWindowAdapter;
struct XComponentManager {
 WindowInitParameter created;
 bool created_valid=false;
 static XComponentManager* GetInstance(){static XComponentManager m;return &m;}
 void CreateAndShowAbility(const WindowInitParameter& param,const std::string&){
   created=param;created_valid=true;
 }
};
namespace base {
inline std::string UTF16ToUTF8(const std::u16string&){return {};}
}
constexpr int kDefaultWidget=0;
struct NodeHandleImpl {
 bool support=false;
 static NodeHandleImpl& GetInstance(){static NodeHandleImpl n;return n;}
 bool IsSupportNodeHandle()const{return support;}
};
struct OhosWindow {
 void BindNodeHandle(){} void Show(bool){}
};
class OhosToplevelWindow : public OhosWindow {
 public:
 bool need_create_ability_=false,is_split_screen_=false;
 std::optional<gfx::Rect> pending_initial_bounds_in_pixels_;
 int widget=0,notifications=0;bool use_floating_window_=false;
 bool hide_title_bar_=false,use_dark_mode_=false;
 bool caption_button_visible_=true,use_opaque_surface_background_=true;
 uint32_t init_color_argb_=0;int ability_type_=0;std::string app_id_;
 gfx::Rect bounds_in_pixels_{100,100,900,700},previous_bounds_in_pixels_;
 gfx::Size min_size_in_pixels_{100,100},max_size_in_pixels_;
 PlatformWindowState state_=PlatformWindowState::kNormal;
 WindowInitParameter init_param_;
 std::optional<std::u16string> window_title_;
 int GetWidget()const{return widget;}
 int GetWindowUniqueId()const{return 3;}
 void UpdateMinAndMaxSize(){}
 void Applied(gfx::Rect,gfx::Rect){++notifications;}
 void CreateAndShowInternal();
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
    (window, "void OhosToplevelWindow::CreateAndShowInternal()"),
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
 // WindowKit owns the rect, so the deferred placement is published, not applied.
 assert(w.bounds_in_pixels_==original && w.notifications==1);
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

 // A movable window must start from the rect the system restored, not from the
 // placement Chromium saved: passing Chromium's rect as StartOptions replaced it.
 auto& node_handle=NodeHandleImpl::GetInstance();
 auto* xcomponent=XComponentManager::GetInstance();
 node_handle.support=true;
 OhosToplevelWindow create_window;
 create_window.need_create_ability_=true;
 context.pc=false;context.free=true;
 create_window.Show(false);
 assert(xcomponent->created_valid);
 assert((xcomponent->created.bounds.left==0&&xcomponent->created.bounds.top==0&&
   xcomponent->created.bounds.width==0&&xcomponent->created.bounds.height==0));
 assert(!create_window.need_create_ability_);
 // Any other window (picture-in-picture, new window) starts its own ability and
 // must keep the rect Views calculated for it.
 OhosToplevelWindow pip_window;
 pip_window.need_create_ability_=true;
 pip_window.widget=7;
 pip_window.Show(false);
 assert((xcomponent->created.bounds.left==100&&xcomponent->created.bounds.top==100&&
   xcomponent->created.bounds.width==900&&xcomponent->created.bounds.height==700));
 OhosToplevelWindow split_window;
 split_window.need_create_ability_=true;
 split_window.is_split_screen_=true;
 split_window.Show(false);
 assert((xcomponent->created.bounds.left==100&&xcomponent->created.bounds.width==900));
 OhosToplevelWindow fullscreen_window;
 fullscreen_window.need_create_ability_=true;
 context.free=false;context.pc=false;
 fullscreen_window.Show(false);
 assert((xcomponent->created.bounds.left==100&&xcomponent->created.bounds.width==900));
 OhosToplevelWindow maximized_window;
 maximized_window.need_create_ability_=true;
 maximized_window.state_=PlatformWindowState::kMaximized;
 context.free=true;
 maximized_window.Show(false);
 assert(xcomponent->created.status==WindowStatusType::MAXIMIZE);
 assert((xcomponent->created.bounds.width==0));
 context.free=false;context.pc=false;
 node_handle.support=false;
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
