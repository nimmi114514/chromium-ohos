#!/usr/bin/env python3
"""Exercise OHOS tab-drag ownership and synthetic touch releases with SDK mocks."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
from test_hwc_window_lifecycle import method


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1]/'src')
    args=parser.parse_args()
    folder=args.source/'ui/ozone/platform/ohos'
    header=(folder/'drag/ohos_window_drag_manager.h').read_text()
    body=(folder/'drag/ohos_window_drag_manager.cc').read_text()
    events=(folder/'host/ohos_event_source_node_handle.cc').read_text()
    decl=header[header.index('namespace ui {'):header.rindex('#endif')]
    definitions=body[body.index('namespace ui {'):]
    base=(folder/'host/ohos_event_source_base.cc').read_text()
    dispatch=method(base,'void OhosEventSourceBase::SetTargetAndDispatchEvent(')
    start_touch=method(base,'bool OhosEventSourceBase::StartTabDraggingByTouch(')
    send=method(events,'void OhosEventSourceNodeHandle::SendWindowTouchEventForTabDragNodeHandle(')
    harness=r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#define LOG(...) std::cerr
constexpr int UI_TOUCH_EVENT_ACTION_DOWN=0,UI_TOUCH_EVENT_ACTION_UP=1,
 UI_TOUCH_EVENT_ACTION_CANCEL=3,UI_MOUSE_EVENT_ACTION_PRESS=1,UI_MOUSE_EVENT_ACTION_RELEASE=2,
 OH_NATIVEXCOMPONENT_UP=1,OH_NATIVEXCOMPONENT_DOWN=0,
 OH_NATIVEXCOMPONENT_MOUSE_PRESS=1,OH_NATIVEXCOMPONENT_MOUSE_RELEASE=2;
namespace gfx { using AcceleratedWidget=int32_t; }
namespace ohos::adapter::window {
struct WindowEventFilterAdapter {
 int dragging=-1;
 static WindowEventFilterAdapter& GetInstance(){ static WindowEventFilterAdapter s;return s; }
 void SetDraggingTabWidgetId(int id){dragging=id;}
 int GetDraggingTabWidgetId(){return dragging;}
 bool IsTabDragging(){return dragging>=0;}
 void ClearShiftEventWindowIds(){}
 void CacheShiftEventWindowIds(int,int){}
};
struct AppWindowAdapter {
 int mice=0,touches=0,last_finger=-1;
 bool succeeds=true;
 static AppWindowAdapter& GetInstance(){static AppWindowAdapter s;return s;}
 bool ShiftWindowMouseEvent(int,int){mice++;return succeeds;}
 bool ShiftWindowTouchEvent(int,int,int finger){touches++;last_finger=finger;return succeeds;}
};
}
namespace ohos::adapter::nodeHandle {
struct NodeHandleImpl {
 static NodeHandleImpl& GetInstance(){static NodeHandleImpl s;return s;}
 bool IsSupportNodeHandle(){return true;}
};
}
'''
    harness+=decl+definitions+r'''
namespace ui {
struct NodeHandleTouchEventData {
 int touch_action=0,id=7,display_id=0;float display_x=0,display_y=0;
};
struct OhosEventSourceNodeHandle {
 OhosWindowDragManager* window_drag_manager_;
 int delivered=0;
 void EndTabDragging(){window_drag_manager_->ClearDraggingTabParams();}
 void PrepareXcomponentPointForTouchEvent(int,NodeHandleTouchEventData&,float,float){}
 void OnTouchEvent(int,NodeHandleTouchEventData&,int){delivered++;}
 void SendWindowTouchEventForTabDragNodeHandle(gfx::AcceleratedWidget,NodeHandleTouchEventData&);
};
'''+send+r'''
enum class EventType { kTouchPressed,kTouchReleased,kTouchCancelled,kMouseMoved };
struct PointerDetails { int id; };
struct Event {
 EventType event_type;int id;
 bool IsTouchEvent() const {return event_type!=EventType::kMouseMoved;}
 EventType type() const {return event_type;}
 Event* AsTouchEvent(){return this;}
 PointerDetails pointer_details() const {return {id};}
 struct DispatcherApi {explicit DispatcherApi(Event*){} void set_target(void*){}};
};
struct WindowManager {int window=1;int* GetWindow(int){return &window;}};
struct OhosEventSourceBase {
 WindowManager windows;WindowManager* window_manager_=&windows;
 OhosWindowDragManager* manager;int active_touch_id_=-1;
 explicit OhosEventSourceBase(OhosWindowDragManager* m):manager(m){}
 void DispatchEvent(Event*){}
 void SetTargetAndDispatchEvent(gfx::AcceleratedWidget,Event&);
 bool StartTabDraggingByTouch(gfx::AcceleratedWidget);
 void StartTabDraggingByTouch(gfx::AcceleratedWidget w,int id){manager->StartTabDraggingByTouch(w,id);}
};
'''+dispatch+start_touch+r'''
}
int main(int argc,char** argv){
 assert(argc==2);const int test=std::atoi(argv[1]);
 auto& filter=ohos::adapter::window::WindowEventFilterAdapter::GetInstance();
 auto& api=ohos::adapter::window::AppWindowAdapter::GetInstance();
 ui::OhosWindowDragManager manager;
 ui::OhosEventSourceNodeHandle source{&manager};
 if(test==0){
  manager.StartTabDraggingByTouch(10,7);assert(manager.ShiftWindowEvent(10,20));
  assert(api.touches==1 && api.mice==0 && api.last_finger==7);
  ui::NodeHandleTouchEventData simulated_up{UI_TOUCH_EVENT_ACTION_UP,7};
  source.SendWindowTouchEventForTabDragNodeHandle(10,simulated_up);
  assert(filter.GetDraggingTabWidgetId()==20);
  assert(source.delivered==0);
  source.SendWindowTouchEventForTabDragNodeHandle(20,simulated_up);
  assert(!filter.IsTabDragging());assert(source.delivered==1);
 }else if(test==1){
  manager.StartTabDraggingByTouch(10,7);
  ui::NodeHandleTouchEventData other_up{UI_TOUCH_EVENT_ACTION_UP,9};
  source.SendWindowTouchEventForTabDragNodeHandle(10,other_up);
  assert(filter.IsTabDragging());assert(source.delivered==0);
 }else if(test==2){
  manager.StartTabDragging(10);api.succeeds=false;
  assert(!manager.ShiftWindowEvent(10,20));assert(filter.GetDraggingTabWidgetId()==10);
  api.succeeds=true;assert(manager.ShiftWindowEvent(10,20));
  assert(filter.GetDraggingTabWidgetId()==20 && api.mice==2);
  manager.ClearDraggingTabParams();assert(!filter.IsTabDragging());
 }else if(test==3){
  manager.StartTabDraggingByTouch(10,7);
  ui::NodeHandleTouchEventData cancel{UI_TOUCH_EVENT_ACTION_CANCEL,7};
  source.SendWindowTouchEventForTabDragNodeHandle(10,cancel);
  assert(!filter.IsTabDragging());
 }else if(test==4){
  ui::OhosEventSourceBase base(&manager);assert(!base.StartTabDraggingByTouch(10));
  ui::Event down{ui::EventType::kTouchPressed,7};base.SetTargetAndDispatchEvent(10,down);
  ui::Event other_down{ui::EventType::kTouchPressed,9};base.SetTargetAndDispatchEvent(10,other_down);
  assert(base.StartTabDraggingByTouch(10));assert(manager.ShiftWindowEvent(10,20));
  assert(api.touches==1 && api.mice==0 && api.last_finger==7);
  ui::Event other_up{ui::EventType::kTouchReleased,9};base.SetTargetAndDispatchEvent(10,other_up);
  assert(base.active_touch_id_==7);
  ui::Event up{ui::EventType::kTouchReleased,7};base.SetTargetAndDispatchEvent(20,up);
  assert(base.active_touch_id_==-1);
 }
}
'''
    names=['synthetic-source-up','secondary-finger','shift-failure-and-retry','touch-cancel','active-touch-routing']
    failures=[]
    with tempfile.TemporaryDirectory(prefix='ohos-tab-drag-') as directory:
        file,binary=Path(directory)/'test.cc',Path(directory)/'test'
        file.write_text(harness)
        subprocess.run([shutil.which('clang++') or 'g++','-std=c++20','-g','-O1',
                        '-fsanitize=address,undefined','-fno-omit-frame-pointer',str(file),'-o',str(binary)],check=True)
        for i,name in enumerate(names):
            p=subprocess.run([str(binary),str(i)],capture_output=True,text=True)
            print(('PASS' if p.returncode==0 else 'FAIL')+': '+name)
            if p.returncode:failures.append(name);print(p.stderr[-700:])
    if failures:raise SystemExit('Failed: '+', '.join(failures))


if __name__=='__main__':main()
