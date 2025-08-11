# 區段選擇器關鍵問題修復報告

## 🚨 問題根源
經過調試發現，用戶看不到「基本方案資訊」中的區段類型選擇器是因為JavaScript中的CSS選擇器錯誤導致的。

### 原始問題代碼
在`updateGlobalCapForFullDay()`函數中，使用了不精確的CSS選擇器：
```javascript
const segmentCapsDiv = document.querySelector(".col-md-4:nth-child(2)");
const capPriorityDiv = document.querySelector(".col-md-4:nth-child(3)");

// 隱藏區段上限和優先級設定（全天模式下不需要）
if (segmentCapsDiv) segmentCapsDiv.style.display = "none";
if (capPriorityDiv) capPriorityDiv.style.display = "none";
```

### 問題分析
1. **CSS選擇器過於寬泛**：`.col-md-4:nth-child(2)`和`.col-md-4:nth-child(3)`會選擇到頁面中所有符合條件的元素
2. **意外影響**：這些選擇器不僅選擇到了「全域收費上限設定」區塊中的元素，還選擇到了「基本方案資訊」區塊中的：
   - 區段類型選擇器（第2個.col-md-4）
   - 節假日類型選擇器（第3個.col-md-4）
3. **觸發時機**：當頁面初始化時，JavaScript會執行`updateSegmentBuilder()`，由於預設是全天模式，會觸發`updateGlobalCapForFullDay()`，導致基本方案資訊被隱藏

### 修復方案
將不精確的CSS選擇器改為更精確的選擇器：

```javascript
// 修復前（錯誤）
const segmentCapsDiv = document.querySelector(".col-md-4:nth-child(2)");
const capPriorityDiv = document.querySelector(".col-md-4:nth-child(3)");

// 修復後（正確）
const globalCapContainer = document.querySelector('#global-daily-cap').closest('div.row');
const segmentCapsDiv = globalCapContainer ? globalCapContainer.querySelector(".col-md-4:nth-child(2)") : null;
const capPriorityDiv = globalCapContainer ? globalCapContainer.querySelector(".col-md-4:nth-child(3)") : null;
```

## 🔧 修復內容

### 1. 修復 updateGlobalCapForFullDay() 函數
- 使用更精確的CSS選擇器，只選擇全域收費上限區塊中的元素
- 避免意外選擇到基本方案資訊區塊中的元素

### 2. 修復 resetGlobalCapDisplay() 函數
- 同樣使用精確的CSS選擇器
- 確保恢復顯示時不會影響其他區塊

## 🧪 測試結果
修復後的預期行為：
1. ✅ 頁面載入時，基本方案資訊區塊正常顯示
2. ✅ 區段類型選擇器可見且可操作
3. ✅ 節假日類型選擇器可見且可操作
4. ✅ 切換區段類型時，時間區段設定正確更新
5. ✅ 全天模式下，全域收費上限區塊的功能正常

## 📋 影響範圍
- **修復文件**：`templates/rate_plan_designer.html`
- **修復函數**：`updateGlobalCapForFullDay()`、`resetGlobalCapDisplay()`
- **不影響**：其他頁面和功能

## 🎯 用戶體驗改善
- 用戶現在可以正常看到並使用基本方案資訊區塊
- 區段類型切換功能完全恢復正常
- 不再需要特殊的調試模式或測試頁面

---
**修復時間**：2025年6月20日  
**問題嚴重度**：關鍵（影響核心功能）  
**修復狀態**：已完成，待用戶確認 