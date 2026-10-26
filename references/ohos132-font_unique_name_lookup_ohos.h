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

#ifndef THIRD_PARTY_BLINK_RENDERER_PLATFORM_FONTS_LINUX_FONT_UNIQUE_NAME_LOOKUP_OHOS_H_
#define THIRD_PARTY_BLINK_RENDERER_PLATFORM_FONTS_LINUX_FONT_UNIQUE_NAME_LOOKUP_OHOS_H_

#include "base/sequence_checker.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "third_party/blink/public/common/font_unique_name_lookup/font_table_matcher.h"
#include "third_party/blink/public/mojom/android_font_lookup/android_font_lookup.mojom-blink.h"
#include "third_party/blink/public/mojom/font_unique_name_lookup/font_unique_name_lookup.mojom-blink.h"
#include "third_party/blink/renderer/platform/fonts/font_unique_name_lookup.h"
#include "third_party/blink/renderer/platform/wtf/deque.h"

namespace blink {

class FontUniqueNameLookupOhos : public FontUniqueNameLookup {
 public:
  FontUniqueNameLookupOhos() = default;
  FontUniqueNameLookupOhos(const FontUniqueNameLookupOhos&) = delete;
  FontUniqueNameLookupOhos& operator=(const FontUniqueNameLookupOhos&) = delete;
  ~FontUniqueNameLookupOhos() override;

  bool IsFontUniqueNameLookupReadyForSyncLookup() override;

  void PrepareFontUniqueNameLookup(
      NotifyFontUniqueNameLookupReady callback) override;

  sk_sp<SkTypeface> MatchUniqueName(const String& font_unique_name) override;

  void Init() override;

 private:
  void EnsureServiceConnected();

  void ReceiveReadOnlySharedMemoryRegion(
      base::ReadOnlySharedMemoryRegion shared_memory_region);

  mojo::Remote<mojom::blink::FontUniqueNameLookup> ohos_font_lookup_service_;
  WTF::Deque<NotifyFontUniqueNameLookupReady> pending_callbacks_;
  std::optional<bool> sync_available_;

  SEQUENCE_CHECKER(sequence_checker_);
};

}  // namespace blink

#endif  // THIRD_PARTY_BLINK_RENDERER_PLATFORM_FONTS_LINUX_FONT_UNIQUE_NAME_LOOKUP_OHOS_H_
