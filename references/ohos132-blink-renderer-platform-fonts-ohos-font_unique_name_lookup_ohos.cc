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

#include "third_party/blink/renderer/platform/fonts/ohos/font_unique_name_lookup_ohos.h"

#include "base/files/file.h"
#include "base/logging.h"
#include "base/metrics/histogram_macros.h"
#include "base/timer/elapsed_timer.h"
#include "third_party/blink/public/common/features.h"
#include "third_party/blink/public/common/font_unique_name_lookup/icu_fold_case_util.h"
#include "third_party/blink/public/common/thread_safe_browser_interface_broker_proxy.h"
#include "third_party/blink/public/platform/platform.h"
#include "third_party/blink/renderer/platform/instrumentation/histogram.h"
#include "third_party/blink/renderer/platform/runtime_enabled_features.h"
#include "third_party/skia/include/core/SkData.h"
#include "third_party/skia/include/core/SkRefCnt.h"
#include "third_party/skia/include/core/SkTypeface.h"
#include "skia/ext/font_utils.h"
#include "third_party/skia/include/core/SkFontMgr.h"

#include "base/logging.h"

namespace blink {

FontUniqueNameLookupOhos::~FontUniqueNameLookupOhos() = default;

sk_sp<SkTypeface> FontUniqueNameLookupOhos::MatchUniqueName(
    const String& font_unique_name) {
  if (!IsFontUniqueNameLookupReadyForSyncLookup())
    return nullptr;
  std::optional<FontTableMatcher::MatchResult> match_result =
      font_table_matcher_->MatchName(font_unique_name.Utf8().c_str());
  if (!match_result)
    return nullptr;
  return skia::DefaultFontMgr()->makeFromFile(match_result->font_path.c_str(),
                                              match_result->ttc_index);
}

void FontUniqueNameLookupOhos::Init() {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);

  if (!base::FeatureList::IsEnabled(features::kPrefetchFontLookupTables))
    return;

  EnsureServiceConnected();
}

bool FontUniqueNameLookupOhos::IsFontUniqueNameLookupReadyForSyncLookup() {
  if (!RuntimeEnabledFeatures::FontSrcLocalMatchingEnabled())
    return true;

  EnsureServiceConnected();

  if (font_table_matcher_.get())
    return true;

  if (sync_available_.has_value())
    return sync_available_.value();

  bool sync_available_from_mojo = false;
  base::ReadOnlySharedMemoryRegion shared_memory_region;
  ohos_font_lookup_service_->GetUniqueNameLookupTableIfAvailable(
      &sync_available_from_mojo, &shared_memory_region);
  sync_available_ = sync_available_from_mojo;

  if (*sync_available_) {
    DCHECK_EQ(pending_callbacks_.size(), 0u);
    ReceiveReadOnlySharedMemoryRegion(std::move(shared_memory_region));
  }

  return *sync_available_;
}

void FontUniqueNameLookupOhos::PrepareFontUniqueNameLookup(
    NotifyFontUniqueNameLookupReady callback) {
  DCHECK(!font_table_matcher_.get());
  DCHECK(RuntimeEnabledFeatures::FontSrcLocalMatchingEnabled());

  pending_callbacks_.push_back(std::move(callback));

  if (pending_callbacks_.size() > 1)
    return;

  EnsureServiceConnected();

  ohos_font_lookup_service_->GetUniqueNameLookupTable(base::BindOnce(
      &FontUniqueNameLookupOhos::ReceiveReadOnlySharedMemoryRegion,
      base::Unretained(this)));
}

void FontUniqueNameLookupOhos::EnsureServiceConnected() {
  if (!ohos_font_lookup_service_) {
    Platform::Current()->GetBrowserInterfaceBroker()->GetInterface(
        ohos_font_lookup_service_.BindNewPipeAndPassReceiver());
  }
}

void FontUniqueNameLookupOhos::ReceiveReadOnlySharedMemoryRegion(
    base::ReadOnlySharedMemoryRegion shared_memory_region) {
  font_table_matcher_ =
      std::make_unique<FontTableMatcher>(shared_memory_region.Map());
  while (!pending_callbacks_.empty()) {
    NotifyFontUniqueNameLookupReady callback = pending_callbacks_.TakeFirst();
    std::move(callback).Run();
  }
}

}  // namespace blink
