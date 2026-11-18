#!/usr/bin/env python3
"""Exercise production HWC callbacks with host mocks, without an OHOS device.

Usage: python3 scripts/test_hwc_window_lifecycle.py --source /path/to/chromium/src
The compiler can be selected with CXX. ASan/UBSan cover callbacks queued across
compositor destruction and window reuse; this does not measure hardware HWC.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def method(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path(__file__).resolve().parents[1] / "src")
    args = parser.parse_args()
    host = args.source / "ui/views/widget/desktop_aura/desktop_window_tree_host_ohos"
    source = host.with_suffix(".cc").read_text()
    header = host.with_suffix(".h").read_text()
    for forbidden in ("observed_compositor_", "ObserveCompositor(",
                      "AddObserver(this)", "RemoveObserver(this)",
                      "surface_finalize_timer_"):
        assert forbidden not in source + header, forbidden
    definitions = "\n".join(method(source, signature) for signature in (
        "DesktopWindowTreeHostOhos::~DesktopWindowTreeHostOhos()",
        "void DesktopWindowTreeHostOhos::CloseNow()",
        "void DesktopWindowTreeHostOhos::OnClosed()",
        "void DesktopWindowTreeHostOhos::OnDidPresentCompositorFrame(",
    ))
    harness = r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace gfx {
struct Timestamp { bool empty = false; bool is_null() const { return empty; } };
struct PresentationFeedback {
  bool failure = false;
  Timestamp timestamp;
  bool failed() const { return failure; }
};
}
namespace ui {
struct Compositor {
  std::set<void*> observers;
  void AddObserver(void* p) { assert(observers.insert(p).second); }
  void RemoveObserver(void* p) { assert(observers.erase(p) == 1); }
};
struct PlatformWindow {
  std::string id = "browser1";
  std::string GetWindowUniqueId() const { return id; }
};
}
namespace ohos::adapter::taskRunner {
struct MainThreadTaskRunner {
  std::vector<std::function<void()>> tasks;
  static auto& GetInstance() { static MainThreadTaskRunner r; return r; }
  void PostTask(std::function<void()> f) { tasks.push_back(std::move(f)); }
  void Drain() {
    auto pending = std::move(tasks); tasks.clear();
    for (auto& f : pending) f();
  }
};
}
namespace ohos::adapter::xcomponent {
struct XComponentManager {
  std::map<std::string, uint32_t> nodes;
  int writes = 0;
  static auto* GetInstance() { static XComponentManager m; return &m; }
  void SetNodeHandleXComponentBackgroundColor(const std::string& id, uint32_t c) {
    auto p = nodes.find(id);
    if (p != nodes.end()) { p->second = c; ++writes; }
  }
};
}
constexpr uint32_t kSurfaceOpaqueBlack = 0xFF000000;
class DesktopWindowTreeHostPlatform {
 public:
  std::unique_ptr<ui::Compositor> compositor = std::make_unique<ui::Compositor>();
  std::unique_ptr<ui::PlatformWindow> window = std::make_unique<ui::PlatformWindow>();
  DesktopWindowTreeHostPlatform() { compositor->AddObserver(this); }
  virtual ~DesktopWindowTreeHostPlatform() { DestroyCompositor(); }
  virtual void OnClosed() { window.reset(); }
  virtual void CloseNow() { DestroyCompositor(); OnClosed(); }
  const ui::PlatformWindow* platform_window() const { return window.get(); }
  void DestroyCompositor() {
    if (compositor) { compositor->RemoveObserver(this); compositor.reset(); }
  }
};
class DesktopWindowTreeHostOhos : public DesktopWindowTreeHostPlatform {
 public:
  ~DesktopWindowTreeHostOhos() override;
  void CloseNow() override;
  void OnClosed() override;
  void OnDidPresentCompositorFrame(ui::Compositor*, uint32_t,
                                   const gfx::PresentationFeedback&);
  void DestroyNonClientEventFilter() {}
  bool surface_finalized_ = false;
  std::shared_ptr<std::atomic_bool> surface_background_cancelled_ =
      std::make_shared<std::atomic_bool>(false);
};
'''
    harness += definitions + r'''
int main() {
  auto& runner = ohos::adapter::taskRunner::MainThreadTaskRunner::GetInstance();
  auto* manager = ohos::adapter::xcomponent::XComponentManager::GetInstance();
  auto reset = [&] { runner.Drain(); manager->nodes = {{"browser1", 0xFFFFFFFF}};
                     manager->writes = 0; };
  // The base registration survives failed feedback and repeated presentations.
  reset();
  {
    DesktopWindowTreeHostOhos h;
    h.OnDidPresentCompositorFrame(h.compositor.get(), 1, {true, {false}});
    h.OnDidPresentCompositorFrame(h.compositor.get(), 2, {false, {true}});
    assert(runner.tasks.empty());
    h.OnDidPresentCompositorFrame(h.compositor.get(), 3, {});
    h.OnDidPresentCompositorFrame(h.compositor.get(), 4, {});
    assert(runner.tasks.size() == 1 && h.compositor->observers.size() == 1);
    runner.Drain();
    assert(manager->writes == 1 && manager->nodes.at("browser1") == kSurfaceOpaqueBlack);
  }
  // Close before any presentation: compositor is destroyed before derived dtor.
  reset();
  { DesktopWindowTreeHostOhos h; h.CloseNow(); assert(!h.compositor); }
  runner.Drain(); assert(manager->writes == 0);
  // A queued ArkUI task must not overwrite the next window reusing the same id.
  reset();
  {
    DesktopWindowTreeHostOhos h;
    h.OnDidPresentCompositorFrame(h.compositor.get(), 1, {});
    h.CloseNow();
    manager->nodes["browser1"] = 0xFF123456;
    runner.Drain(); assert(manager->nodes.at("browser1") == 0xFF123456);
  }
  assert(manager->writes == 0);
  // Direct destruction and external close also cancel outstanding work.
  reset();
  {
    auto h = std::make_unique<DesktopWindowTreeHostOhos>();
    h->OnDidPresentCompositorFrame(h->compositor.get(), 1, {}); h.reset();
  }
  runner.Drain(); assert(manager->writes == 0);
  reset();
  {
    DesktopWindowTreeHostOhos h;
    h.OnDidPresentCompositorFrame(h.compositor.get(), 1, {});
    h.OnClosed(); runner.Drain(); assert(manager->writes == 0);
  }
  // Transparent windows opt out; missing windows/ids never schedule updates.
  reset();
  {
    DesktopWindowTreeHostOhos h; h.surface_finalized_ = true;
    h.OnDidPresentCompositorFrame(h.compositor.get(), 1, {});
    assert(runner.tasks.empty());
    h.surface_finalized_ = false; h.window->id.clear();
    h.OnDidPresentCompositorFrame(h.compositor.get(), 2, {});
    assert(runner.tasks.empty());
    h.window.reset(); h.OnDidPresentCompositorFrame(h.compositor.get(), 3, {});
    assert(runner.tasks.empty());
  }
  // A removed XComponent is safe even when the window has not closed yet.
  reset();
  {
    DesktopWindowTreeHostOhos h;
    h.OnDidPresentCompositorFrame(h.compositor.get(), 1, {});
    manager->nodes.clear(); runner.Drain(); assert(manager->writes == 0);
  }
}
'''
    compiler = os.environ.get("CXX") or shutil.which("g++")
    if not compiler:
        raise RuntimeError("Set CXX to a host C++ compiler with ASan/UBSan")
    with tempfile.TemporaryDirectory(prefix="ohos-hwc-lifecycle-") as tmp:
        src = Path(tmp) / "test.cc"
        binary = Path(tmp) / "test"
        src.write_text(harness)
        subprocess.run([compiler, "-std=c++20", "-g", "-O1",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        str(src), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("PASS: production HWC callbacks, ASan/UBSan, mocked compositor and ArkUI queue")


if __name__ == "__main__":
    main()
