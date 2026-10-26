#!/usr/bin/env python3
"""Check the production privacy-owner method against a simulated window API."""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "src/ohos/adapter/xcomponent/adapter/window_adapter.cc").read_text()
start = source.index("void WindowAdapter::SetWindowPrivacyMode(")
body = source.index("{", start)
depth = 1
end = body + 1
while depth:
    depth += (source[end] == "{") - (source[end] == "}")
    end += 1
method = source[start:end]
stub = r'''
#include <algorithm>
#include <cassert>
#include <map>
#include <mutex>
#include <unordered_map>
#include <vector>
#include <cstdint>
#define LOGI(...) ((void)0)
#define LOGE(...) ((void)0)
std::map<int32_t, bool> window_state;
int api_calls = 0;
int OH_WindowManager_SetWindowPrivacyMode(int32_t id, bool enabled) {
  ++api_calls; window_state[id] = enabled; return 0;
}
using WindowWidgetType = int32_t;
struct AppWindowAdapter {
  std::map<int32_t,int32_t> widget_to_window;
  static AppWindowAdapter& GetInstance() { static AppWindowAdapter a; return a; }
  std::vector<int32_t> GetOriginWindowIds(std::vector<int32_t> widgets) {
    auto it = widget_to_window.find(widgets.front());
    return it == widget_to_window.end() ? std::vector<int32_t>{}
                                      : std::vector<int32_t>{it->second};
  }
};
struct WindowAdapter {
  std::mutex privacy_mutex_;
  std::unordered_map<const void*, int32_t> privacy_window_owners_;
  void SetWindowPrivacyMode(WindowWidgetType, bool, const void*);
};
'''
cases = r'''
int main() {
  int owner_a, owner_b;
  auto& mapping = AppWindowAdapter::GetInstance().widget_to_window;
  mapping = {{1,42},{2,42},{3,77}};
  WindowAdapter a;
  a.SetWindowPrivacyMode(1,true,&owner_a); assert(window_state[42]);
  a.SetWindowPrivacyMode(2,true,&owner_b); assert(window_state[42]);
  a.SetWindowPrivacyMode(0,false,&owner_a); assert(window_state[42]);
  a.SetWindowPrivacyMode(0,false,&owner_b); assert(!window_state[42]);
  int old_calls=api_calls;
  a.SetWindowPrivacyMode(0,false,&owner_b); assert(api_calls==old_calls);
  a.SetWindowPrivacyMode(1,true,&owner_a);
  a.SetWindowPrivacyMode(3,true,&owner_b);
  a.SetWindowPrivacyMode(0,false,&owner_a);
  assert(!window_state[42] && window_state[77]);
  a.SetWindowPrivacyMode(1,true,&owner_a);
  a.SetWindowPrivacyMode(3,true,&owner_a);
  assert(!window_state[42] && window_state[77]);
  mapping.clear();  // Widget disappears before its owner's destructor.
  a.SetWindowPrivacyMode(0,false,&owner_a); assert(window_state[77]);
  a.SetWindowPrivacyMode(0,false,&owner_b); assert(!window_state[77]);
  a.SetWindowPrivacyMode(99,true,&owner_a);
  assert(a.privacy_window_owners_.empty());
}
'''
with tempfile.TemporaryDirectory(prefix="privacy-owner-check-") as directory:
    directory = Path(directory)
    cpp, executable = directory / "check.cc", directory / "check"
    cpp.write_text(stub + method + cases)
    subprocess.run(["c++", "-std=c++20", "-pthread", str(cpp), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
report = {
    "productionMethodExecuted": True,
    "windowApiSimulated": True,
    "deviceScreenshotVerified": False,
    "passed": True,
    "cases": ["enable", "shared-window-owner-release", "last-owner-release",
              "duplicate-release", "independent-windows", "owner-window-move",
              "release-after-widget-destruction", "unknown-widget"],
}
(ROOT / "reports/native106-window-privacy-lifecycle.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
