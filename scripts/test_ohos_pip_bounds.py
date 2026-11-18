#!/usr/bin/env python3
"""Exercise production PiP minimum-size selection with mocked native limits."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from test_hwc_window_lifecycle import method
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'src/chrome/browser/ui/views/overlay/video_overlay_window_views.cc').read_text()
assert 'KeepWindowWithinWorkArea' not in source
harness=r'''
#include <algorithm>
#include <cassert>
#define BUILDFLAG(x) 1
namespace gfx {
struct Size {
 int w=0,h=0;
 Size()=default;Size(int width,int height):w(width),h(height){}
 void SetToMax(Size other){w=std::max(w,other.w);h=std::max(h,other.h);}
 Size operator+(Size other)const{return {w+other.w,h+other.h};}
 bool operator==(const Size&)const=default;
};
}
namespace ohos::adapter::xcomponent {
struct Limits {int min_width=0,min_height=0;};
struct WindowAdapter {
 Limits limits;
 static WindowAdapter& GetInstance(){static WindowAdapter a;return a;}
 Limits GetSystemWindowLimits()const{return limits;}
};
}
const gfx::Size kOverlayViewPadding(64,46);
struct Overlay {gfx::Size bubble;gfx::Size GetBubbleSize()const{return bubble;}};
struct VideoOverlayWindowViews {
 gfx::Size min_size_{284,160};Overlay view;Overlay* overlay_view_=&view;bool shown=false;
 bool IsOverlayViewShown()const{return shown;}
 gfx::Size GetMinimumSize()const;
};
'''
harness+=method(source,'gfx::Size VideoOverlayWindowViews::GetMinimumSize() const')
harness+=r'''
int main(){
 auto& a=ohos::adapter::xcomponent::WindowAdapter::GetInstance();VideoOverlayWindowViews w;
 assert((w.GetMinimumSize()==gfx::Size{284,160}));
 a.limits={360,240};assert((w.GetMinimumSize()==gfx::Size{360,240}));
 a.limits={120,200};assert((w.GetMinimumSize()==gfx::Size{284,200}));
 a.limits={360,240};w.shown=true;w.view.bubble={200,180};
 assert((w.GetMinimumSize()==gfx::Size{360,240}));
 w.view.bubble={500,300};assert((w.GetMinimumSize()==gfx::Size{564,346}));
 w.min_size_={800,600};assert((w.GetMinimumSize()==gfx::Size{800,600}));
 for(int i=0;i<100;i++)assert((w.GetMinimumSize()==gfx::Size{800,600}));
}
'''
with tempfile.TemporaryDirectory(prefix='ohos-pip-minimum-') as d:
 p=Path(d);(p/'test.cc').write_text(harness);compiler=os.environ.get('CXX') or shutil.which('g++')
 subprocess.run([compiler,'-std=c++20','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(p/'test.cc'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: production PiP minimum size honors system limits and overlay constraints; no resize callback correction')
