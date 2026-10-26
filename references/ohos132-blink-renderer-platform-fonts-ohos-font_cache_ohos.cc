/*
 * Copyright (c) 2023-2025 Haitai FangYuan Co., Ltd.
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this list of
 *    conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice, this list
 *    of conditions and the following disclaimer in the documentation and/or other materials
 *    provided with the distribution.
 *
 * 3. Neither the name of the copyright holder nor the names of its contributors may be used
 *    to endorse or promote products derived from this software without specific prior written
 *    permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
 * ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "base/logging.h"
#include "base/notimplemented.h"
#include "skia/ext/font_utils.h"
#include "third_party/blink/renderer/platform/fonts/font_cache.h"
#include "third_party/blink/renderer/platform/fonts/font_description.h"
#include "third_party/blink/renderer/platform/fonts/font_face_creation_params.h"
#include "third_party/blink/renderer/platform/fonts/font_fallback_priority.h"
#include "third_party/blink/renderer/platform/fonts/simple_font_data.h"

namespace blink {

static AtomicString DefaultFontFamily(sk_sp<SkFontMgr> font_manager) {
  sk_sp<SkTypeface> typeface(
      font_manager->legacyMakeTypeface(nullptr, SkFontStyle()));
  if (typeface) {
    SkString family_name;
    typeface->getFamilyName(&family_name);
    if (family_name.size()) {
      return ToAtomicString(family_name);
    }
  }

  LOG(WARNING) << __FUNCTION__ << " Getting the default font family failed.";
  return AtomicString();
}

static AtomicString DefaultFontFamily() {
  if (sk_sp<SkFontMgr> font_manager = FontCache::Get().FontManager()) {
    return DefaultFontFamily(font_manager);
  }
  return DefaultFontFamily(skia::DefaultFontMgr());
}

// static
const AtomicString& FontCache::SystemFontFamily() {
  DEFINE_THREAD_SAFE_STATIC_LOCAL(AtomicString, system_font_family,
                                  (DefaultFontFamily()));
  return system_font_family;
}

// static
void FontCache::SetSystemFontFamily(const AtomicString& family_name) {
  NOTIMPLEMENTED_LOG_ONCE();
}

// Reference Android
const SimpleFontData* FontCache::PlatformFallbackFontForCharacter(
    const FontDescription& font_description,
    UChar32 c,
    const SimpleFontData*,
    FontFallbackPriority fallback_priority) {
  sk_sp<SkFontMgr> fm(skia::DefaultFontMgr());

  const char* generic_family_name = nullptr;
  if (font_description.GenericFamily() == FontDescription::kSerifFamily)
    generic_family_name = "serif";

  AtomicString family_name = GetFamilyNameForCharacter(
      fm.get(), c, font_description, generic_family_name, fallback_priority);
  if (family_name.empty())
    return GetLastResortFallbackFont(font_description);

  return FontDataFromFontPlatformData(GetFontPlatformData(
      font_description, FontFaceCreationParams(family_name)));
}
}  // namespace blink
