function escapePreviewHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatPreviewDuration(duration) {
  if (typeof duration === "number") {
    if (duration >= 60) {
      const hours = Math.floor(duration / 60);
      const minutes = duration % 60;
      return minutes ? `${hours} 小時 ${minutes} 分` : `${hours} 小時`;
    }
    return `${duration} 分鐘`;
  }
  return duration || "";
}

function getPreviewSessionTitle(session) {
  if (session.period) return session.period;
  if (session.time_slot) return session.time_slot;
  const label = session.label || session.segment_label || "時段";
  if (session.start && session.end) {
    return `${label} (${session.start}-${session.end})`;
  }
  return label;
}

function renderPreviewDetails(result) {
  const sessions = Array.isArray(result.session_details) ? result.session_details : [];
  const detailsHtml = sessions.length
    ? `
      <div class="mt-3">
        <div class="fw-semibold mb-2">
          <i class="fas fa-list-ul me-1"></i>計費明細
          <span class="text-muted fw-normal">（${sessions.length} 個時段）</span>
        </div>
        <div class="d-grid gap-2">
          ${sessions
            .map((session, index) => {
              const title = getPreviewSessionTitle(session);
              const duration = formatPreviewDuration(session.duration);
              const rate = session.rate ?? session.unit_price ?? "";
              const amount = session.amount ?? session.fee ?? 0;
              const cycles =
                session.cycles_count > 1
                  ? `<span class="badge bg-light text-dark border ms-1">${session.cycles_count} 個計費週期</span>`
                  : "";
              return `
                <div class="p-2 border rounded bg-white small">
                  <div class="d-flex justify-content-between align-items-start gap-2">
                    <div>
                      <div class="mb-1">
                        <span class="badge bg-secondary me-1">#${index + 1}</span>
                        <strong>${escapePreviewHtml(title)}</strong>
                        ${cycles}
                      </div>
                      <div class="text-muted">
                        ${escapePreviewHtml(duration)}
                        ${rate !== "" ? ` · ${escapePreviewHtml(rate)}` : ""}
                      </div>
                    </div>
                    <strong class="text-nowrap">${amount} 元</strong>
                  </div>
                </div>`;
            })
            .join("")}
        </div>
      </div>`
    : `<div class="mt-2 small text-muted">無可顯示的時段明細（可能為免費時段或尚未設定費率）</div>`;

  const summary = result.calculation_summary
    ? `<div class="small text-muted mt-2">${escapePreviewHtml(result.calculation_summary)}</div>`
    : "";

  const durationText = result.total_duration_display
    ? `<span class="ms-2 text-muted">（${escapePreviewHtml(result.total_duration_display)}）</span>`
    : "";

  return `
    <div>
      <strong>合計 ${result.total_amount ?? 0} 元</strong>${durationText}
      ${summary}
      ${detailsHtml}
    </div>`;
}
