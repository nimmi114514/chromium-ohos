#!/usr/bin/env python3
"""Check OHOS scheme routing against the production shell integration methods."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from test_hwc_window_lifecycle import method

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "src/chrome/browser/shell_integration_ohos.cc").read_text()
harness = r'''
#include <cassert>
#include <string>
#include <vector>
namespace url {
constexpr char kHttpScheme[] = "http";
constexpr char kHttpsScheme[] = "https";
}
namespace base {
std::u16string UTF8ToUTF16(const std::string& s) { return {s.begin(), s.end()}; }
}
struct GURL {
 std::string value;
 std::string GetScheme() const { return value.substr(0, value.find(':')); }
};
enum DefaultWebClientState { NOT_DEFAULT, IS_DEFAULT, UNKNOWN_DEFAULT };
DefaultWebClientState browser_state = NOT_DEFAULT;
int browser_queries = 0;
DefaultWebClientState GetDefaultBrowser() { ++browser_queries; return browser_state; }
'''
harness += method(source, "std::u16string GetApplicationNameForScheme(")
harness += method(source, "DefaultWebClientState IsDefaultClientForScheme(")
harness += r'''
int main() {
 for (auto state : {NOT_DEFAULT, IS_DEFAULT, UNKNOWN_DEFAULT}) {
  browser_state = state;
  for (const std::string scheme : {"http", "https"}) {
   assert(IsDefaultClientForScheme(scheme) == state);
  }
  const int queries = browser_queries;
  for (const std::string scheme : {"clash", "clashmeta", "flclash", "clashbox", "mailto", "tel", "unknown-app"}) {
   assert(IsDefaultClientForScheme(scheme) == UNKNOWN_DEFAULT);
   // The native dialog suppresses empty names. No handler lookup on an ArkTS
   // callback is needed from the shell worker thread: the OS resolves on launch.
   auto label = GetApplicationNameForScheme(GURL{scheme + "://install-config?url=private-token"});
   assert(!label.empty());
   assert(label == base::UTF8ToUTF16(scheme));
  }
  assert(browser_queries == queries);
 }
}
'''
with tempfile.TemporaryDirectory(prefix="ohos-external-protocol-") as directory:
    p = Path(directory)
    (p / "test.cc").write_text(harness)
    compiler = os.environ.get("CXX") or shutil.which("g++")
    subprocess.run([compiler, "-std=c++20", "-g", "-O1",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    str(p / "test.cc"), "-o", str(p / "test")], check=True)
    subprocess.run([str(p / "test")], check=True)
print("PASS: custom schemes retain confirmation regardless of default browser state")
