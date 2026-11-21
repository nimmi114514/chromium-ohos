#!/usr/bin/env python3
"""Exercise production OHOS IME methods with separate clients and SDK failures."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
from test_hwc_window_lifecycle import method


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1] / 'src')
    args = parser.parse_args()
    source = (args.source / 'ui/base/ime/ohos/input_method_ohos.cc').read_text()
    signatures = [
        'size_t ClampToPreview(',
        'void InputMethodOHOS::SetPreviewText(',
        'void InputMethodOHOS::CancelPreviewText()',
        'void InputMethodOHOS::CancelComposition(',
        'void InputMethodOHOS::OnDidChangeFocusedClient(',
        'InputMethod_TextInputType InputTypeChromiumToOH(TextInputType ctype,\n                                               TextInputMode cmode) {',
        'void InputMethodOHOSCAPI::UpdateTextInputTask(',
    ]
    definitions = '\n'.join(method(source, signature) for signature in signatures)
    harness = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <utility>
#include <vector>
#define TRACE_EVENT0(...) ((void)0)
#define LOG(...) std::cerr
namespace gfx {
struct Range {
  size_t first=0, last=0;
  Range() = default;
  Range(size_t a, size_t b): first(a), last(b) {}
  size_t start() const { return first; }
  bool is_empty() const { return first==last; }
};
}
using InputMethod_ErrorCode = int;
constexpr int IME_ERR_OK=0, IME_ERR_DETACHED=1, IME_ERR_IMMS=2;
enum InputMethod_TextInputType {
 IME_TEXT_INPUT_TYPE_NUMBER=2, IME_TEXT_INPUT_TYPE_PHONE=3,
 IME_TEXT_INPUT_TYPE_EMAIL_ADDRESS=5, IME_TEXT_INPUT_TYPE_URL=6,
 IME_TEXT_INPUT_TYPE_VISIBLE_PASSWORD=7, IME_TEXT_INPUT_TYPE_NUMBER_DECIMAL=12
};
int OH_InputMethodProxy_NotifyCursorUpdate(int*, int*) { return IME_ERR_OK; }
namespace ohos::adapter {
int OhInputMethodProxyShowTextInput(int*, int*) { return IME_ERR_OK; }
}
namespace ui {
enum TextInputType { TEXT_INPUT_TYPE_NONE, TEXT_INPUT_TYPE_TEXT, TEXT_INPUT_TYPE_PASSWORD };
enum TextInputMode {
 TEXT_INPUT_MODE_DEFAULT, TEXT_INPUT_MODE_NUMERIC, TEXT_INPUT_MODE_DECIMAL,
 TEXT_INPUT_MODE_TEL, TEXT_INPUT_MODE_URL, TEXT_INPUT_MODE_EMAIL
};
enum class RequestKeyboardReason { kNone, kTouch };
struct ImeTextSpan {
 enum class Type { kComposition };
 ImeTextSpan(Type, size_t, size_t) {}
};
struct CompositionText {
 std::u16string text;
 gfx::Range selection;
 std::vector<ImeTextSpan> ime_text_spans;
};
struct TextInputClient {
 std::u16string composition;
 bool HasCompositionText() const { return !composition.empty(); }
 bool GetCompositionTextRange(gfx::Range* r) {
  *r=gfx::Range(0,composition.size());return !composition.empty();
 }
 void SetCompositionText(const CompositionText& text) { composition=text.text; }
 void ClearCompositionText() { composition.clear(); }
};
struct InputMethodBase {
 void OnDidChangeFocusedClient(TextInputClient*,TextInputClient*) {}
};
struct InputMethodOHOS:InputMethodBase {
 TextInputClient* client=nullptr;
 std::u16string preview_text_;
 size_t preview_cursor_=0;
 TextInputType text_input_type_=TEXT_INPUT_TYPE_TEXT;
 int32_t last_keyboard_height_=-1;
 TextInputClient* GetTextInputClient() const { return client; }
 TextInputType GetTextInputType() const { return client?TEXT_INPUT_TYPE_TEXT:TEXT_INPUT_TYPE_NONE; }
 bool IsTextInputClientFocused(const TextInputClient* other) const { return other && other==client; }
 void UpdateContextFocusState() { text_input_type_=GetTextInputType(); }
 void OnCaretBoundsChanged(const TextInputClient*) {}
 void SetPreviewText(const std::u16string&,int32_t,int32_t);
 void CancelPreviewText();
 void CancelComposition(const TextInputClient*);
 void OnDidChangeFocusedClient(TextInputClient*,TextInputClient*);
};
InputMethod_TextInputType InputTypeChromiumToOH(TextInputType) {
 return IME_TEXT_INPUT_TYPE_VISIBLE_PASSWORD;
}
struct InputMethodOHOSCAPI {
 int storage=1;
 int* input_method_proxy_=&storage;
 int* text_editor_proxy_=&storage;
 int* attach_options_=&storage;
 int* cursor_info_=&storage;
 bool is_attach_=true, is_keyboard_shown_=true, synced=false;
 int config_error=IME_ERR_OK, attached=0, options_updated=0;
 RequestKeyboardReason last_reason=RequestKeyboardReason::kNone;
 void AttachTextInputTask(RequestKeyboardReason) { attached++; }
 int* UpdateAttachOptions(RequestKeyboardReason reason) {
  options_updated++; last_reason=reason; return attach_options_;
 }
 void SyncTextConfigSnapshot() {}
 int NotifyConfigurationChanged() { return config_error; }
 int* CreateCursorInfo() { return cursor_info_; }
 void MarkAttachConfigSynced() { synced=true; }
 void UpdateTextInputTask(RequestKeyboardReason);
};
'''
    harness += definitions + r'''
} // namespace ui
int main(int argc,char** argv) {
 assert(argc==2); const int test=std::atoi(argv[1]);
 ui::InputMethodOHOS ime;
 ui::TextInputClient old_client, current;
 ime.client=&current;
 if(test==0) {
  ime.SetPreviewText(u"abc",-1,-1);
  ime.CancelComposition(&old_client);
  assert(ime.preview_text_==u"abc");
  assert(current.composition==u"abc");
  ime.SetPreviewText(u"x",1,2);
  assert(current.composition==u"axc");
  ime.CancelComposition(&current);
  assert(ime.preview_text_.empty() && current.composition.empty());
 } else if(test==1) {
  ime.client=&old_client;ime.SetPreviewText(u"old",-1,-1);
  ime.client=&current;ime.OnDidChangeFocusedClient(&old_client,&current);
  ime.SetPreviewText(u"x",0,0);
  assert(current.composition==u"x");
 } else if(test==2) {
  assert(ui::InputTypeChromiumToOH(ui::TEXT_INPUT_TYPE_TEXT,ui::TEXT_INPUT_MODE_DECIMAL)
         ==IME_TEXT_INPUT_TYPE_NUMBER_DECIMAL);
  assert(ui::InputTypeChromiumToOH(ui::TEXT_INPUT_TYPE_TEXT,ui::TEXT_INPUT_MODE_NUMERIC)
         ==IME_TEXT_INPUT_TYPE_NUMBER);
  assert(ui::InputTypeChromiumToOH(ui::TEXT_INPUT_TYPE_PASSWORD,ui::TEXT_INPUT_MODE_NUMERIC)
         ==IME_TEXT_INPUT_TYPE_VISIBLE_PASSWORD);
 } else if(test==3) {
  ui::InputMethodOHOSCAPI capi;capi.config_error=IME_ERR_IMMS;
  capi.UpdateTextInputTask(ui::RequestKeyboardReason::kTouch);
  assert(!capi.synced);
  capi.config_error=IME_ERR_OK;capi.UpdateTextInputTask(ui::RequestKeyboardReason::kTouch);
  assert(capi.synced);
 } else if(test==4) {
  ui::InputMethodOHOSCAPI capi;capi.is_keyboard_shown_=false;
  capi.UpdateTextInputTask(ui::RequestKeyboardReason::kTouch);
  assert(capi.options_updated>0 && capi.last_reason==ui::RequestKeyboardReason::kTouch);
 } else if(test==5) {
  ime.SetPreviewText(u"abcd",-1,-1);ime.SetPreviewText(u"XY",1,3);
  assert(current.composition==u"aXYd");
  ime.SetPreviewText(u"z",2,2);assert(current.composition==u"aXzYd");
  ime.SetPreviewText(u"",-1,-1);assert(current.composition.empty());
 }
}
'''
    names=['nonfocused-cancel','client-switch','decimal-and-password','failed-config-retry','updated-request-reason','composition-edits']
    failures=[]
    with tempfile.TemporaryDirectory(prefix='ohos-ime-state-') as directory:
        file,binary=Path(directory)/'test.cc',Path(directory)/'test'
        file.write_text(harness)
        subprocess.run([shutil.which('clang++') or 'g++','-std=c++20','-g','-O1',
                        '-fsanitize=address,undefined','-fno-omit-frame-pointer',str(file),'-o',str(binary)],check=True)
        for i,name in enumerate(names):
            p=subprocess.run([str(binary),str(i)],capture_output=True,text=True)
            print(('PASS' if p.returncode==0 else 'FAIL')+': '+name)
            if p.returncode:
                failures.append(name);print(p.stderr[-600:])
    if failures:raise SystemExit('Failed: '+', '.join(failures))


if __name__=='__main__':
    main()
