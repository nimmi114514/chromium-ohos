#!/usr/bin/env python3
"""Check that the production default-directory singleton recovers after failure."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'src/chrome/browser/download/download_prefs.cc').read_text()
start = source.index('class DefaultDownloadDirectory {')
end = source.index('DefaultDownloadDirectory& GetDefaultDownloadDirectorySingleton()', start)
harness = r'''
#include <cassert>
#include <string>
#include <utility>
#include <vector>
#define BUILDFLAG(x) 1
namespace base {
struct FilePath {
 std::string value;
 FilePath() = default;explicit FilePath(std::string p):value(std::move(p)){}
 bool empty()const{return value.empty();}
};
template<typename T> struct NoDestructor { T value; };
struct PathService { static bool Get(int,FilePath*) { assert(false);return false; } };
}
namespace chrome {constexpr int DIR_DEFAULT_DOWNLOADS_SAFE=1;}
bool DownloadPathIsDangerous(const base::FilePath&) { return false; }
std::vector<std::string> responses;
int queries=0;
namespace ohos::adapter::ContextPathAdapter {
std::string GetAppDownloadDir() {
 assert(queries < static_cast<int>(responses.size()));return responses[queries++];
}
}
'''
harness += source[start:end]
harness += r'''
int main() {
 const std::string path="/storage/Users/currentUser/Download/com.example.ohos.chromium";
 responses={"","",path};queries=0;
 base::NoDestructor<DefaultDownloadDirectory> delayed;
 assert(queries==1);
 assert(delayed.value.path().empty());assert(queries==2);
 assert(delayed.value.path().value==path);assert(queries==3);
 for(int i=0;i<100;i++)assert(delayed.value.path().value==path);
 assert(queries==3);
 responses={path};queries=0;
 base::NoDestructor<DefaultDownloadDirectory> ready;
 assert(ready.value.path().value==path && queries==1);
}
'''
with tempfile.TemporaryDirectory(prefix='download-directory-recovery-') as directory:
 p=Path(directory);(p/'test.cc').write_text(harness)
 compiler=os.environ.get('CXX') or shutil.which('g++')
 subprocess.run([compiler,'-std=c++20','-g','-O1','-fsanitize=address,undefined',
                 '-fno-omit-frame-pointer',str(p/'test.cc'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: empty default directory is retried; successful path remains stable')
