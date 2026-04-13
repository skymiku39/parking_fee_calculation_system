/* ============================================
   載入狀態管理
   ============================================ */

class LoadingManager {
  constructor() {
    this.overlay = null;
    this.init();
  }

  init() {
    // 建立全螢幕 loading overlay
    if (!document.getElementById('loading-overlay')) {
      this.overlay = document.createElement('div');
      this.overlay.id = 'loading-overlay';
      this.overlay.className = 'loading-overlay';
      this.overlay.style.display = 'none';
      this.overlay.innerHTML = `
        <div class="loading-content">
          <div class="spinner-border text-primary mb-3" role="status" style="width: 3rem; height: 3rem;">
            <span class="visually-hidden">載入中...</span>
          </div>
          <div class="loading-message text-muted">載入中...</div>
        </div>
      `;
      document.body.appendChild(this.overlay);
    } else {
      this.overlay = document.getElementById('loading-overlay');
    }
  }

  /**
   * 顯示全螢幕載入動畫
   */
  show(message = '載入中...') {
    if (this.overlay) {
      const messageEl = this.overlay.querySelector('.loading-message');
      if (messageEl) {
        messageEl.textContent = message;
      }
      this.overlay.style.display = 'flex';
    }
  }

  /**
   * 隱藏全螢幕載入動畫
   */
  hide() {
    if (this.overlay) {
      this.overlay.style.display = 'none';
    }
  }

  /**
   * 更新載入訊息
   */
  updateMessage(message) {
    if (this.overlay) {
      const messageEl = this.overlay.querySelector('.loading-message');
      if (messageEl) {
        messageEl.textContent = message;
      }
    }
  }

  /**
   * 為按鈕添加載入狀態
   * @param {HTMLElement} button - 按鈕元素
   * @param {boolean} loading - 是否載入中
   */
  setButtonLoading(button, loading) {
    if (!button) return;

    if (loading) {
      // 保存原始內容
      button.dataset.originalContent = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `
        <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
        處理中...
      `;
    } else {
      button.disabled = false;
      if (button.dataset.originalContent) {
        button.innerHTML = button.dataset.originalContent;
        delete button.dataset.originalContent;
      }
    }
  }

  /**
   * 為元素添加骨架屏
   * @param {HTMLElement} element - 目標元素
   * @param {string} type - 骨架屏類型：text, title, button, card
   */
  showSkeleton(element, type = 'card') {
    if (!element) return;

    const skeletonHTML = this.getSkeletonHTML(type);
    element.dataset.originalContent = element.innerHTML;
    element.innerHTML = skeletonHTML;
  }

  /**
   * 移除骨架屏，恢復原始內容
   */
  hideSkeleton(element) {
    if (!element) return;

    if (element.dataset.originalContent) {
      element.innerHTML = element.dataset.originalContent;
      delete element.dataset.originalContent;
    }
  }

  getSkeletonHTML(type) {
    const skeletons = {
      text: `
        <div class="skeleton skeleton-text" style="width: 100%; height: 1em;"></div>
        <div class="skeleton skeleton-text" style="width: 80%; height: 1em;"></div>
      `,
      title: `
        <div class="skeleton skeleton-title"></div>
      `,
      button: `
        <div class="skeleton skeleton-button"></div>
      `,
      card: `
        <div class="skeleton skeleton-card"></div>
      `,
      table: `
        <div class="skeleton skeleton-text mb-2" style="width: 100%;"></div>
        <div class="skeleton skeleton-text mb-2" style="width: 100%;"></div>
        <div class="skeleton skeleton-text mb-2" style="width: 100%;"></div>
        <div class="skeleton skeleton-text" style="width: 60%;"></div>
      `
    };
    return skeletons[type] || skeletons.card;
  }

  /**
   * 包裝 async 函數，自動顯示/隱藏載入狀態
   * @param {Function} asyncFn - 異步函數
   * @param {string} message - 載入訊息
   * @returns {Promise}
   */
  async wrap(asyncFn, message = '處理中...') {
    this.show(message);
    try {
      const result = await asyncFn();
      return result;
    } finally {
      this.hide();
    }
  }

  /**
   * 包裝 API 請求，自動處理載入和錯誤
   * @param {Function} apiFn - API 函數
   * @param {Object} options - 選項
   * @returns {Promise}
   */
  async wrapAPI(apiFn, options = {}) {
    const {
      loadingMessage = '載入中...',
      successMessage = null,
      errorMessage = '操作失敗',
      showLoading = true,
      showSuccess = false,
      showError = true
    } = options;

    if (showLoading) {
      this.show(loadingMessage);
    }

    try {
      const result = await apiFn();
      
      if (showSuccess && successMessage) {
        window.notify.success(successMessage);
      }
      
      return result;
    } catch (error) {
      console.error('API Error:', error);
      
      if (showError) {
        const message = error.message || errorMessage;
        window.notify.error(message);
      }
      
      throw error;
    } finally {
      if (showLoading) {
        this.hide();
      }
    }
  }
}

// 建立全域實例
window.loading = new LoadingManager();

// 提供簡潔的全域方法
window.showLoading = (message) => window.loading.show(message);
window.hideLoading = () => window.loading.hide();

/**
 * 通用的 fetch 包裝器，自動處理載入和錯誤
 * @param {string} url - API URL
 * @param {Object} options - fetch 選項
 * @param {Object} loadingOptions - 載入選項
 * @returns {Promise}
 */
window.fetchWithLoading = async (url, options = {}, loadingOptions = {}) => {
  return window.loading.wrapAPI(
    async () => {
      const response = await fetch(url, options);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || errorData.error || `HTTP ${response.status}`);
      }
      
      return response.json();
    },
    loadingOptions
  );
};
