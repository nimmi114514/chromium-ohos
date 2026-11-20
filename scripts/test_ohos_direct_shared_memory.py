#!/usr/bin/env python3
"""Exercise the production unsafe-region helper with failing allocation backends."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "src/mojo/core/ipcz_driver/base_shared_memory_service.cc").read_text()
start = source.index("base::UnsafeSharedMemoryRegion CreateUnsafeSharedMemoryRegion(size_t size) {")
opening = source.index("{", start)
depth, end = 1, opening + 1
while depth:
    depth += (source[end] == "{") - (source[end] == "}")
    end += 1
helper = source[start:end]
fixture = r'''
#include <cassert>
#include <cstddef>
#include <utility>
#define BUILDFLAG(flag) flag
#define IS_LINUX 0
#define IS_CHROMEOS 0
#define IS_OHOS 1
#define TRACE_EVENT(...) ((void)0)
bool enabled, direct_available, broker_available;
int direct_calls, broker_calls;
struct Configuration { bool direct_unsafe_shared_memory_allocation; };
Configuration GetConfiguration() { return {enabled}; }
namespace base {
namespace subtle {
struct PlatformSharedMemoryRegion {
  int backend;
  bool IsValid() const { return backend != 0; }
  static PlatformSharedMemoryRegion CreateUnsafe(size_t size) {
    ++direct_calls;
    return {size && direct_available ? 1 : 0};
  }
};
}
struct WritableSharedMemoryRegion {
  int backend;
  bool IsValid() const { return backend != 0; }
};
struct UnsafeSharedMemoryRegion {
  int backend = 0;
  static UnsafeSharedMemoryRegion Deserialize(subtle::PlatformSharedMemoryRegion region) {
    return {region.backend};
  }
};
}
struct WritableRegion : base::WritableSharedMemoryRegion {
  static base::UnsafeSharedMemoryRegion ConvertToUnsafe(WritableRegion region) {
    return {region.backend};
  }
};
WritableRegion CreateWritableSharedMemoryRegion(size_t size) {
  ++broker_calls;
  return {{size && broker_available ? 2 : 0}};
}
'''
helper = helper.replace("base::WritableSharedMemoryRegion::ConvertToUnsafe", "WritableRegion::ConvertToUnsafe")
checks = r'''
void Check(bool flag, bool direct, bool broker, int result, int direct_count, int broker_count) {
  enabled=flag; direct_available=direct; broker_available=broker;
  direct_calls=broker_calls=0;
  assert(CreateUnsafeSharedMemoryRegion(4096).backend == result);
  assert(direct_calls == direct_count && broker_calls == broker_count);
}
int main() {
  Check(true, true, false, 1, 1, 0);   // A missing broker cannot break direct allocation.
  Check(true, false, true, 2, 1, 1);   // Direct allocation failure retains the broker fallback.
  Check(true, false, false, 0, 1, 1);  // Both failing still reports failure.
  Check(false, true, true, 2, 0, 1);   // Other sandbox types retain their original route.
}
'''
with tempfile.TemporaryDirectory(prefix="ohos-shmem-policy-") as directory:
    cpp, binary = Path(directory) / "test.cc", Path(directory) / "test"
    cpp.write_text(fixture + helper + checks)
    subprocess.run([shutil.which("clang++") or "g++", "-std=c++20", "-Wall", "-Wextra",
                    "-Werror", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
report = {"passed": True, "cases": 4,
          "scope": "Production helper with simulated OHOS allocation and broker failures"}
(ROOT / "reports/ohos-direct-shared-memory-tests.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
