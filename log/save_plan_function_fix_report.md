# SavePlan函數JavaScript錯誤修復報告

## 🚨 錯誤描述
在費率方案設計器中，點擊「儲存方案」按鈕時出現JavaScript錯誤：

```
rate_plan_designer:1114 Uncaught TypeError: Cannot read properties of null (reading 'value')
    at rate_plan_designer:1114:54
    at NodeList.forEach (<anonymous>)
    at savePlan (rate_plan_designer:1112:52)
    at HTMLButtonElement.onclick (rate_plan_designer:280:71)
```

## 🔍 問題分析

### 根本原因
在`savePlan`函數中，代碼試圖從所有`.segment-item`元素中提取`.segment-name`、`.segment-start`和`.segment-end`的值：

```javascript
// 錯誤的代碼
document.querySelectorAll(".segment-item").forEach((item) => {
  segments.push({
    name: item.querySelector(".segment-name").value,        // 可能為null
    start: item.querySelector(".segment-start").value,      // 可能為null
    end: item.querySelector(".segment-end").value,          // 可能為null
  });
});
```

### 問題場景
在**全天模式**下，`.segment-item`元素使用了不同的HTML結構：
- 全天模式：只有文字說明，沒有`.segment-name`、`.segment-start`、`.segment-end`輸入框
- 其他模式：有完整的時間輸入框

因此在全天模式下，`querySelector`返回`null`，嘗試讀取`.value`屬性時就會拋出錯誤。

## 🛠️ 修復方案

### 1. 條件判斷處理
根據當前選擇的區段類型來決定如何收集區段資訊：

```javascript
// 修復後的代碼
const segments = [];
const segmentType = document.getElementById("segment-type").value;

if (segmentType === "全天") {
  // 全天模式下使用固定的區段資訊
  segments.push({
    name: "全天",
    start: "00:00",
    end: "24:00"
  });
} else {
  // 其他模式下從DOM元素收集資訊
  document.querySelectorAll(".segment-item").forEach((item) => {
    const nameElement = item.querySelector(".segment-name");
    const startElement = item.querySelector(".segment-start");
    const endElement = item.querySelector(".segment-end");
    
    // 只有當元素存在時才添加
    if (nameElement && startElement && endElement) {
      segments.push({
        name: nameElement.value,
        start: startElement.value,
        end: endElement.value,
      });
    }
  });
}
```

### 2. 錯誤處理增強
為`savePlan`函數添加try-catch錯誤處理：

```javascript
function savePlan() {
  try {
    // 原有邏輯...
  } catch (error) {
    console.error("儲存方案時發生錯誤:", error);
    alert("儲存方案時發生錯誤，請檢查控制台以獲取詳細資訊");
  }
}
```

### 3. 初始化錯誤處理
為頁面初始化添加錯誤處理：

```javascript
document.addEventListener("DOMContentLoaded", function () {
  try {
    updateSegmentBuilder();
    updateRateMatrix();
  } catch (error) {
    console.error("初始化過程中發生錯誤:", error);
  }
});
```

## 🧪 測試驗證

### 測試場景
1. **全天模式**：切換到全天模式，點擊「儲存方案」按鈕
2. **二段模式**：切換到二段模式，填入區段資訊，點擊「儲存方案」按鈕
3. **三段模式**：切換到三段模式，填入區段資訊，點擊「儲存方案」按鈕
4. **任意段模式**：添加自訂區段，點擊「儲存方案」按鈕

### 預期結果
- ✅ 所有模式下都不會出現JavaScript錯誤
- ✅ 能正確收集到對應的區段資訊
- ✅ 錯誤時有適當的錯誤提示

## 📋 修復檔案
- `templates/rate_plan_designer.html`：修復`savePlan`函數和初始化邏輯

## 🎯 影響範圍
- **修復功能**：儲存方案功能在所有區段模式下都能正常工作
- **改善體驗**：更好的錯誤處理和用戶提示
- **穩定性**：減少JavaScript運行時錯誤

---
**修復時間**：2025年6月20日  
**錯誤級別**：中等（功能性錯誤）  
**修復狀態**：已完成 