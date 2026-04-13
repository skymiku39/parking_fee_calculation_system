/* ============================================
   表單驗證
   ============================================ */

class FormValidator {
  constructor() {
    this.rules = {
      required: (value) => value !== null && value !== undefined && value.toString().trim() !== '',
      email: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
      number: (value) => !isNaN(parseFloat(value)) && isFinite(value),
      min: (value, min) => parseFloat(value) >= parseFloat(min),
      max: (value, max) => parseFloat(value) <= parseFloat(max),
      minLength: (value, length) => value.toString().length >= length,
      maxLength: (value, length) => value.toString().length <= length,
      pattern: (value, pattern) => new RegExp(pattern).test(value),
      date: (value) => !isNaN(Date.parse(value)),
      datetime: (value) => !isNaN(Date.parse(value)),
      url: (value) => {
        try {
          new URL(value);
          return true;
        } catch {
          return false;
        }
      }
    };

    this.messages = {
      required: '此欄位為必填',
      email: '請輸入有效的電子郵件地址',
      number: '請輸入有效的數字',
      min: '數值不能小於 {min}',
      max: '數值不能大於 {max}',
      minLength: '長度不能少於 {length} 個字元',
      maxLength: '長度不能超過 {length} 個字元',
      pattern: '格式不正確',
      date: '請輸入有效的日期',
      datetime: '請輸入有效的日期時間',
      url: '請輸入有效的網址'
    };
  }

  /**
   * 驗證單一欄位
   * @param {HTMLElement} field - 表單欄位
   * @param {Object} rules - 驗證規則
   * @returns {Object} { valid: boolean, message: string }
   */
  validateField(field, rules = {}) {
    const value = field.value;
    
    for (const [ruleName, ruleValue] of Object.entries(rules)) {
      if (!this.rules[ruleName]) continue;

      let isValid = false;
      if (ruleValue === true) {
        isValid = this.rules[ruleName](value);
      } else {
        isValid = this.rules[ruleName](value, ruleValue);
      }

      if (!isValid) {
        let message = this.messages[ruleName] || '驗證失敗';
        // 替換佔位符
        message = message.replace('{' + ruleName + '}', ruleValue);
        return { valid: false, message };
      }
    }

    return { valid: true, message: '' };
  }

  /**
   * 為欄位添加即時驗證
   * @param {HTMLElement} field - 表單欄位
   * @param {Object} rules - 驗證規則
   */
  addLiveValidation(field, rules) {
    if (!field) return;

    // 移除舊的驗證訊息
    this.clearFieldError(field);

    // 在 blur 時驗證
    field.addEventListener('blur', () => {
      this.validateAndShowError(field, rules);
    });

    // 在 input 時清除錯誤（如果有的話）
    field.addEventListener('input', () => {
      if (field.classList.contains('is-invalid')) {
        const result = this.validateField(field, rules);
        if (result.valid) {
          this.clearFieldError(field);
          field.classList.remove('is-invalid');
          field.classList.add('is-valid');
        }
      }
    });
  }

  /**
   * 驗證並顯示錯誤
   */
  validateAndShowError(field, rules) {
    const result = this.validateField(field, rules);
    
    if (!result.valid) {
      this.showFieldError(field, result.message);
      return false;
    } else {
      this.clearFieldError(field);
      field.classList.remove('is-invalid');
      field.classList.add('is-valid');
      return true;
    }
  }

  /**
   * 顯示欄位錯誤
   */
  showFieldError(field, message) {
    field.classList.add('is-invalid');
    field.classList.remove('is-valid');

    // 尋找或建立錯誤訊息元素
    let errorElement = field.parentElement.querySelector('.form-error-text');
    if (!errorElement) {
      errorElement = document.createElement('div');
      errorElement.className = 'form-error-text';
      field.parentElement.appendChild(errorElement);
    }
    errorElement.textContent = message;
  }

  /**
   * 清除欄位錯誤
   */
  clearFieldError(field) {
    field.classList.remove('is-invalid', 'is-valid');
    const errorElement = field.parentElement.querySelector('.form-error-text');
    if (errorElement) {
      errorElement.remove();
    }
  }

  /**
   * 驗證整個表單
   * @param {HTMLFormElement} form - 表單元素
   * @param {Object} fieldsRules - 欄位規則對象 { fieldName: rules }
   * @returns {boolean}
   */
  validateForm(form, fieldsRules) {
    if (!form) return false;

    let isValid = true;
    const firstInvalidField = null;

    for (const [fieldName, rules] of Object.entries(fieldsRules)) {
      const field = form.elements[fieldName];
      if (!field) continue;

      const fieldValid = this.validateAndShowError(field, rules);
      if (!fieldValid) {
        isValid = false;
        if (!firstInvalidField) {
          // 聚焦到第一個錯誤欄位
          field.focus();
        }
      }
    }

    return isValid;
  }

  /**
   * 為表單添加驗證
   * @param {HTMLFormElement} form - 表單元素
   * @param {Object} fieldsRules - 欄位規則
   * @param {Function} onSubmit - 提交回調
   */
  setupForm(form, fieldsRules, onSubmit) {
    if (!form) return;

    // 為每個欄位添加即時驗證
    for (const [fieldName, rules] of Object.entries(fieldsRules)) {
      const field = form.elements[fieldName];
      if (field) {
        this.addLiveValidation(field, rules);
      }
    }

    // 處理表單提交
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      // 驗證表單
      const isValid = this.validateForm(form, fieldsRules);
      
      if (isValid && onSubmit) {
        try {
          await onSubmit(e);
        } catch (error) {
          console.error('Form submission error:', error);
          if (window.notify) {
            window.notify.error('提交失敗：' + error.message);
          }
        }
      }
    });
  }

  /**
   * 自定義驗證規則
   * @param {string} name - 規則名稱
   * @param {Function} validator - 驗證函數
   * @param {string} message - 錯誤訊息
   */
  addRule(name, validator, message) {
    this.rules[name] = validator;
    this.messages[name] = message;
  }
}

// 建立全域實例
window.validator = new FormValidator();

/**
 * 快速驗證表單的輔助函數
 */
window.validateForm = (form, fieldsRules) => {
  return window.validator.validateForm(form, fieldsRules);
};

/**
 * 快速設置表單驗證
 */
window.setupFormValidation = (formSelector, fieldsRules, onSubmit) => {
  const form = typeof formSelector === 'string' 
    ? document.querySelector(formSelector) 
    : formSelector;
  
  if (form) {
    window.validator.setupForm(form, fieldsRules, onSubmit);
  }
};
