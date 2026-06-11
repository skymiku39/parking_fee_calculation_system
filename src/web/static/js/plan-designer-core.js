/**
 * 方案設計器共用邏輯（MDP / 自訂方案）。
 * 依賴頁面全域變數：segments、matrix；可選 dailyCapsByCategory（MDP 日上限）
 */
(function () {
  if (typeof window.dailyCapsByCategory === 'undefined') {
    window.dailyCapsByCategory = {};
  }

  function hi(key) {
    return typeof hintIcon === 'function' ? hintIcon(key) : '';
  }

  function defaultCell() {
    return { unit: 60, rate: 0, grace: 0, capEnabled: false, capAmount: 0 };
  }

  function currentCategories() {
    const el = document.getElementById('holiday_type');
    const ht = el ? el.value : '平日假日';
    if (ht === '無假日') return ['統一'];
    if (ht === '完整假日') return ['平日', '假日', '節慶日'];
    return ['平日', '假日'];
  }

  function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  function escapeAttr(s) {
    return (s || '').replace(/"/g, '&quot;');
  }

  function getDailyCap(cat) {
    return window.dailyCapsByCategory[cat] || 0;
  }

  function setDailyCap(cat, val) {
    window.dailyCapsByCategory[cat] = parseInt(val, 10) || 0;
  }

  function renderMatrixCellFields(key, cell) {
    return `
      <div class="rate-matrix-fields">
        <div class="rate-matrix-field">
          <input class="form-control form-control-sm" type="number" min="1" value="${cell.unit}" onchange="setCell('${escapeAttr(key)}','unit',this.value)">
          <small>單位(分)${hi('matrix_unit')}</small>
        </div>
        <div class="rate-matrix-field">
          <input class="form-control form-control-sm" type="number" min="0" value="${cell.rate}" onchange="setCell('${escapeAttr(key)}','rate',this.value)">
          <small>單價(元)${hi('matrix_rate')}</small>
        </div>
        <div class="rate-matrix-field">
          <input class="form-control form-control-sm" type="number" min="0" value="${cell.grace}" onchange="setCell('${escapeAttr(key)}','grace',this.value)">
          <small>免費(分)${hi('matrix_grace')}</small>
        </div>
        <div class="rate-matrix-field rate-matrix-field-cap">
          <div class="rate-matrix-cap-head">
            <input type="checkbox" class="form-check-input m-0" ${cell.capEnabled ? 'checked' : ''} onclick="setCell('${escapeAttr(key)}','capEnabled',this.checked)">
            <small>區段上限(元)${hi('segment_cap_amount')}</small>
          </div>
          <input class="form-control form-control-sm" type="number" min="0" value="${cell.capAmount}" onchange="setCell('${escapeAttr(key)}','capAmount',this.value)">
        </div>
      </div>`;
  }

  function renderMatrix() {
    const host = document.getElementById('matrixHost');
    if (!host || typeof segments === 'undefined' || typeof matrix === 'undefined') return;
    const cats = currentCategories();
    let html = '<table class="table table-bordered table-sm align-middle"><thead><tr><th>日期類別 \\ 時段</th>';
    segments.forEach((seg) => {
      html += `<th>${escapeHtml(seg.name)}<br/><small>${escapeHtml(seg.start)}-${escapeHtml(seg.end)}</small></th>`;
    });
    const perCatDailyCap = window.matrixDailyCapMode === 'per_category';
    if (perCatDailyCap) {
      html += '<th class="matrix-daily-cap-col">' + (typeof hintLabel === 'function' ? hintLabel('日上限', 'matrix_daily_cap') : '日上限') + '</th>';
    }
    html += '</tr></thead><tbody>';
    cats.forEach((cat) => {
      html += `<tr><th style="white-space:nowrap">${cat}</th>`;
      segments.forEach((seg) => {
        const key = `${seg.name}_${cat}`;
        const cell = matrix[key] || defaultCell();
        html += `<td class="rate-matrix-cell">${renderMatrixCellFields(key, cell)}</td>`;
      });
      if (perCatDailyCap) {
        const capVal = getDailyCap(cat);
        html += `<td class="matrix-daily-cap-cell">
          <input class="form-control form-control-sm" type="number" min="0" value="${capVal}" placeholder="0"
            title="此日期類別的曆日總上限" onchange="setDailyCap('${escapeAttr(cat)}', this.value)" />
          <small class="text-muted">元/日</small>
        </td>`;
      }
      html += '</tr>';
    });
    html += '</tbody></table>';
    host.innerHTML = html;
    if (typeof initFieldHints === 'function') initFieldHints(host);
  }

  function setCell(key, field, val) {
    const cur = matrix[key] || defaultCell();
    if (field === 'unit' || field === 'rate' || field === 'grace' || field === 'capAmount') {
      val = parseInt(val, 10) || 0;
    }
    matrix[key] = { ...cur, [field]: val };
  }

  function segEdit(i, k, v) {
    segments[i] = { ...segments[i], [k]: v };
    renderMatrix();
  }

  function segRemove(i) {
    segments.splice(i, 1);
    if (typeof renderSegments === 'function') renderSegments();
    renderMatrix();
  }

  function addSegment() {
    segments.push({ name: '新時段', start: '09:00', end: '18:00' });
    if (typeof renderSegments === 'function') renderSegments();
    renderMatrix();
  }

  async function validateSegments() {
    const segTypeEl = document.getElementById('segment_type');
    const t = segTypeEl ? segTypeEl.value : '';
    if (t === '全天' || t === '一段') {
      alert('全天模式不需驗證');
      return;
    }
    try {
      const resp = await fetch('/api/enhanced/segments/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ segments }),
      });
      const data = await resp.json();
      if (data.success) {
        if (data.total_minutes === 1440) alert('✅ 驗證成功：完整覆蓋 24 小時');
        else alert('⚠️ 覆蓋不足：目前 ' + data.total_minutes + ' 分鐘');
      } else {
        alert('❌ 驗證失敗：' + (data.message || '未知錯誤'));
      }
    } catch (e) {
      alert('驗證錯誤：' + (e.message || e));
    }
  }

  window.currentCategories = currentCategories;
  window.escapeHtml = escapeHtml;
  window.escapeAttr = escapeAttr;
  window.renderMatrixCellFields = renderMatrixCellFields;
  window.renderMatrix = renderMatrix;
  window.setCell = setCell;
  window.getDailyCap = getDailyCap;
  window.setDailyCap = setDailyCap;
  window.segEdit = segEdit;
  window.segRemove = segRemove;
  window.addSegment = addSegment;
  window.validateSegments = validateSegments;
})();
