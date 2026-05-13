/* ============================================
   Toast 通知系統
   使用 Bootstrap 5 Toast 元件
   ============================================ */

class NotificationSystem {
  constructor() {
    this.container = null;
    this.init();
  }

  init() {
    // 建立 toast 容器
    if (!document.getElementById('toast-container')) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.className = 'toast-container position-fixed top-0 end-0 p-3';
      this.container.style.zIndex = '9999';
      document.body.appendChild(this.container);
    } else {
      this.container = document.getElementById('toast-container');
    }
  }

  /**
   * 顯示通知
   * @param {string} message - 通知訊息
   * @param {string} type - 通知類型：success, error, warning, info
   * @param {number} duration - 顯示時間（毫秒），0 表示不自動關閉
   */
  show(message, type = 'info', duration = 3000) {
    const toast = this.createToast(message, type, duration);
    this.container.appendChild(toast);

    // 使用 Bootstrap Toast API
    const bsToast = new bootstrap.Toast(toast, {
      autohide: duration > 0,
      delay: duration
    });
    bsToast.show();

    // 自動移除 DOM 元素
    toast.addEventListener('hidden.bs.toast', () => {
      toast.remove();
    });

    return bsToast;
  }

  createToast(message, type, duration) {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center border-0 fade`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    // 設定顏色樣式
    const colorClasses = {
      success: 'text-bg-success',
      error: 'text-bg-danger',
      warning: 'text-bg-warning',
      info: 'text-bg-primary'
    };
    toast.classList.add(colorClasses[type] || colorClasses.info);

    // 設定圖示
    const icons = {
      success: 'fa-check-circle',
      error: 'fa-exclamation-circle',
      warning: 'fa-exclamation-triangle',
      info: 'fa-info-circle'
    };
    const icon = icons[type] || icons.info;

    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2">
          <i class="fas ${icon}"></i>
          <span>${this.escapeHtml(message)}</span>
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="關閉"></button>
      </div>
    `;

    return toast;
  }

  /**
   * 顯示成功通知
   */
  success(message, duration = 3000) {
    return this.show(message, 'success', duration);
  }

  /**
   * 顯示錯誤通知
   */
  error(message, duration = 5000) {
    return this.show(message, 'error', duration);
  }

  /**
   * 顯示警告通知
   */
  warning(message, duration = 4000) {
    return this.show(message, 'warning', duration);
  }

  /**
   * 顯示資訊通知
   */
  info(message, duration = 3000) {
    return this.show(message, 'info', duration);
  }

  /**
   * 顯示載入通知（不自動關閉）
   * @returns {Object} 返回 toast 實例，可用於之後關閉
   */
  loading(message = '處理中...') {
    const toast = this.createLoadingToast(message);
    this.container.appendChild(toast);

    const bsToast = new bootstrap.Toast(toast, {
      autohide: false
    });
    bsToast.show();

    return {
      toast: bsToast,
      close: () => {
        bsToast.hide();
        setTimeout(() => toast.remove(), 300);
      },
      update: (newMessage) => {
        const messageElement = toast.querySelector('.toast-body span');
        if (messageElement) {
          messageElement.textContent = newMessage;
        }
      }
    };
  }

  createLoadingToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast align-items-center text-bg-primary border-0 fade';
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2">
          <div class="spinner-border spinner-border-sm" role="status">
            <span class="visually-hidden">載入中...</span>
          </div>
          <span>${this.escapeHtml(message)}</span>
        </div>
      </div>
    `;

    return toast;
  }

  /**
   * 顯示確認對話框（使用通知樣式）
   */
  confirm(message, onConfirm, onCancel) {
    const toast = this.createConfirmToast(message, onConfirm, onCancel);
    this.container.appendChild(toast);

    const bsToast = new bootstrap.Toast(toast, {
      autohide: false
    });
    bsToast.show();

    return bsToast;
  }

  createConfirmToast(message, onConfirm, onCancel) {
    const toast = document.createElement('div');
    toast.className = 'toast align-items-center text-bg-warning border-0 fade';
    toast.setAttribute('role', 'alert');

    const toastId = 'toast-' + Date.now();
    toast.id = toastId;

    toast.innerHTML = `
      <div class="toast-body">
        <div class="mb-2">
          <i class="fas fa-question-circle me-2"></i>
          <span>${this.escapeHtml(message)}</span>
        </div>
        <div class="d-flex gap-2 justify-content-end">
          <button type="button" class="btn btn-sm btn-light" data-action="cancel">取消</button>
          <button type="button" class="btn btn-sm btn-dark" data-action="confirm">確認</button>
        </div>
      </div>
    `;

    // 綁定按鈕事件
    setTimeout(() => {
      const confirmBtn = toast.querySelector('[data-action="confirm"]');
      const cancelBtn = toast.querySelector('[data-action="cancel"]');
      const bsToast = bootstrap.Toast.getInstance(toast);

      if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
          if (onConfirm) onConfirm();
          if (bsToast) bsToast.hide();
          setTimeout(() => toast.remove(), 300);
        });
      }

      if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
          if (onCancel) onCancel();
          if (bsToast) bsToast.hide();
          setTimeout(() => toast.remove(), 300);
        });
      }
    }, 100);

    return toast;
  }

  /**
   * HTML 轉義，防止 XSS
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * 清除所有通知
   */
  clearAll() {
    const toasts = this.container.querySelectorAll('.toast');
    toasts.forEach(toast => {
      const bsToast = bootstrap.Toast.getInstance(toast);
      if (bsToast) {
        bsToast.hide();
      }
      setTimeout(() => toast.remove(), 300);
    });
  }
}

// 建立全域實例
window.notify = new NotificationSystem();

// 提供簡潔的全域方法
window.showSuccess = (message) => window.notify.success(message);
window.showError = (message) => window.notify.error(message);
window.showWarning = (message) => window.notify.warning(message);
window.showInfo = (message) => window.notify.info(message);
window.showLoading = (message) => window.notify.loading(message);
