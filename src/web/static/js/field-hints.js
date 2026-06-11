/**
 * 表單欄位與操作提示（Bootstrap Tooltip）
 */
(function () {
  const FIELD_HINTS = {
    plan_id:
      '方案唯一識別碼，用於 API 與試算時的 <code>plan_id</code>。建議使用中文或英數、避免空白。',
    plan_name: '顯示在方案列表與試算結果中的名稱，可與 ID 相同。',
    plan_description: '選填。說明此方案的適用場景、費率特色或注意事項。',
    template_id:
      'MDP 範本唯一 ID，格式建議為「時段類型_假日類型」，例如 <code>二段_平日假日</code>。',
    label: '顯示給使用者的範本名稱，會出現在首頁方案下拉選單。',
    segment_type:
      '一天切分成幾個計費時段：全天、二段、三段或多時段。影響 <code>segments</code> 清單與費率矩陣欄位數。',
    holiday_type:
      '決定費率矩陣的「日期類別」欄：無假日（統一）、平日假日（平日/假日）、完整假日（平日/假日/節慶日）。',
    global_grace:
      '整次停車僅在<strong>第一個計費週期</strong>扣除的免費分鐘數。設為 0 表示不使用全域寬限，改由各格子的時段寬限控制。',
    daily_cap_amount:
      '單一<strong>曆日</strong>最高收費（元）。0 表示不啟用。<br>須 ≥ 當日各時段區段上限之和，否則較晚時段（常為傍晚）可能因日上限用盡而顯示 0 元。<br>跨日停車時，每日 00:00 重新累計。',
    cap_priority:
      '同時啟用日上限與區段上限時，每個計費週期的封頂順序。<br><strong>先區段後日</strong>：先套該時段上限，再套當日總上限（預設）。<br><strong>先日後區段</strong>：順序相反。<br><strong>較低/較高</strong>：兩種順序各算一次，取對當週期較低或較高的結果。',
    segment_cap_enabled:
      '勾選後，該時段在<strong>同一曆日</strong>內累計費用不得超過右側金額。與日上限獨立，兩者皆可能生效。',
    segment_cap_amount:
      '區段（時段）上限金額（元）。僅在勾選「區段上限」時生效；控制單一時段在當日的最高收費。',
    matrix_unit:
      '收費週期長度（分鐘）。停車時間以進場時刻對齊此週期切分（例：60 分 → 14:55 進場的第一週期為 14:55–15:55）。',
    matrix_rate: '每個收費週期的基本單價（元）。若啟用累進費率則以累進表為準。',
    matrix_grace:
      '該格子在<strong>無全域寬限</strong>時，每個計費週期可扣除的免費分鐘數。有設全域寬限時，僅首週期使用全域寬限。',
    matrix_daily_cap:
      '此日期類別子方案的日上限（元）。0 表示不啟用。MDP 可依平日/假日/節慶日分別設定。',
    segment_name: '時段顯示名稱，須與費率矩陣列標題一致（例：上午時段、傍晚時段）。',
    segment_start:
      '時段開始時間（半開區間起點）。相鄰時段建議首尾相接；邊界時刻歸<strong>下一</strong>時段（12:00 歸下午）。',
    segment_end:
      '時段結束時間（半開區間終點，不含此時刻）。跨午夜時段例：22:00–08:00。',
    featured: '勾選後方案會出現在首頁「精選」篩選與推薦清單。',
    active: '未勾選時方案仍保留於設定檔，但不會出現在試算方案列表。',
    validate_segments:
      '檢查所有時段是否合計覆蓋 24 小時（1440 分鐘）。多時段方案建議在儲存前執行。',
    add_segment: '新增一個可自訂名稱與時間的時段列（僅「多時段」模式可刪除時段）。',
    preview_enter: '試算用的進場日期時間，格式須早於出場時間。',
    preview_exit: '試算用的出場日期時間。可測試跨日、跨時段與封頂效果。',
    pm_add_mdp: '開啟 MDP 設計器，建立多維度範本（內建於 multidimensional_rate_plans.json）。',
    pm_add_user: '開啟自訂方案設計器，建立收費週期格式方案（user_defined_plans.json）。',
    pm_export_mdp: '下載所有 MDP 範本 JSON 備份。',
    pm_export_user: '下載所有自訂方案 JSON 備份。',
    pm_refresh: '重新從伺服器載入方案列表。',
    pm_search: '依方案 ID 或顯示名稱篩選卡片。',
    pm_edit: '開啟對應設計器編輯此方案。',
    pm_download: '下載單一方案 JSON 檔案。',
    pm_delete: '永久刪除此方案（無法復原，請先匯出備份）。',
    pm_kind_mdp: '多維度 MDP 範本：依日期類別與時段矩陣計費，適合複雜假日規則。',
    pm_kind_user: '自訂收費週期方案：使用 UnifiedPricingEngine 與 rate_matrix 格式。',
    pm_featured: '此自訂方案已標記為精選。',
    save_plan: '驗證並寫入設定檔；立即生效於試算 API。',
    export_plan: '下載目前編輯中方案的 JSON，不寫入伺服器。',
    delete_plan: '從 user_defined_plans.json 移除此方案。',
    import_mdp: '從 JSON 檔匯入 MDP 範本結構（須含 template_id 與子方案）。',
    delete_mdp: '從 multidimensional_rate_plans.json 刪除此範本。',
    cap_design_summary:
      '<strong>區段上限</strong>：單一時段在當日的累計上限。<br><strong>日上限</strong>：當日所有時段合計上限（含跨午夜後歸屬當日的夜間分鐘）。<br>計費順序：先算週期費 → 區段上限 → 日上限。',
  };

  function hintIcon(key) {
    if (!FIELD_HINTS[key]) return '';
    return (
      '<i class="fas fa-circle-question field-hint-icon" role="img" aria-label="說明" ' +
      `data-hint-key="${key}"></i>`
    );
  }

  function hintLabel(labelHtml, key) {
    return `<span class="field-label-with-hint">${labelHtml}${hintIcon(key)}</span>`;
  }

  function initFieldHints(container) {
    if (typeof bootstrap === 'undefined') return;
    const root = container || document;
    root.querySelectorAll('[data-hint-key]').forEach((el) => {
      const key = el.getAttribute('data-hint-key');
      const text = FIELD_HINTS[key];
      if (!text) return;
      if (bootstrap.Tooltip.getInstance(el)) return;
      el.setAttribute('data-bs-toggle', 'tooltip');
      el.setAttribute('data-bs-placement', 'top');
      el.setAttribute('data-bs-html', 'true');
      el.setAttribute('title', text);
      new bootstrap.Tooltip(el, { html: true, trigger: 'hover focus', container: 'body' });
    });
  }

  const DESIGNER_LABEL_MAP = {
    plan_id: 'plan_id',
    plan_name: 'plan_name',
    plan_description: 'plan_description',
    segment_type: 'segment_type',
    holiday_type: 'holiday_type',
    global_grace: 'global_grace',
    daily_cap_amount: 'daily_cap_amount',
    cap_priority: 'cap_priority',
    featured: 'featured',
    active: 'active',
    template_id: 'template_id',
    label: 'label',
    description: 'plan_description',
    preview_enter: 'preview_enter',
    preview_exit: 'preview_exit',
  };

  function decorateLabelFor(inputId, hintKey) {
    const label = document.querySelector(`label[for="${inputId}"]`);
    if (label && !label.querySelector('[data-hint-key]')) {
      label.insertAdjacentHTML('beforeend', hintIcon(hintKey));
    }
  }

  function decorateDesignerForms() {
    Object.entries(DESIGNER_LABEL_MAP).forEach(([id, key]) => decorateLabelFor(id, key));
    document.querySelectorAll('[data-hint]').forEach((el) => {
      const key = el.getAttribute('data-hint');
      if (!key || el.querySelector('[data-hint-key]')) return;
      el.insertAdjacentHTML('beforeend', hintIcon(key));
    });
    initFieldHints();
  }

  window.FIELD_HINTS = FIELD_HINTS;
  window.hintIcon = hintIcon;
  window.hintLabel = hintLabel;
  window.initFieldHints = initFieldHints;
  window.decorateDesignerForms = decorateDesignerForms;

  document.addEventListener('DOMContentLoaded', () => {
    initFieldHints();
    if (document.getElementById('plan_id') || document.getElementById('template_id')) {
      decorateDesignerForms();
    }
  });
})();
