# 方案屬性清單（自動產生）

本清單依據 `log/plan_inventory.json` 產生，列出目前用戶自訂方案的關鍵屬性，方便檢視與比對。

> 若要更新本表，請執行：
>
> ```powershell
> python tools/organize_plans.py
> ```

## 方案列表

```json
{
  "plans": [
    {
      "plan_id": "跨日測試方案",
      "name": "跨日測試方案",
      "segment_type": "二段",
      "holiday_type": "無假日",
      "active": true,
      "tags": [
        "二段",
        "全局寬裕:15分",
        "單一",
        "推薦",
        "無假日",
        "無分段上限",
        "無日上限"
      ],
      "has_daily_cap": false,
      "has_segment_cap": false,
      "progressive": false,
      "global_grace_time": 15
    },
    {
      "plan_id": "測試方案2",
      "name": "測試方案2",
      "segment_type": "二段",
      "holiday_type": "無假日",
      "active": true,
      "tags": [
        "二段",
        "全局寬裕:15分",
        "單一",
        "無假日",
        "無分段上限",
        "無日上限"
      ],
      "has_daily_cap": false,
      "has_segment_cap": false,
      "progressive": false,
      "global_grace_time": 15
    },
    {
      "plan_id": "全天無上限",
      "name": "全天無上限",
      "segment_type": "全天",
      "holiday_type": "無假日",
      "active": true,
      "tags": [
        "全天",
        "全局寬裕:15分",
        "單一",
        "無假日",
        "無分段上限",
        "無日上限"
      ],
      "has_daily_cap": false,
      "has_segment_cap": false,
      "progressive": false,
      "global_grace_time": 15
    },
    {
      "plan_id": "全天有上限",
      "name": "全天有上限",
      "segment_type": "全天",
      "holiday_type": "無假日",
      "active": true,
      "tags": [
        "全天",
        "全局寬裕:15分",
        "單一",
        "日上限",
        "無假日",
        "無分段上限"
      ],
      "has_daily_cap": true,
      "has_segment_cap": false,
      "progressive": false,
      "global_grace_time": 15
    },
    {
      "plan_id": "兩段無上限",
      "name": "兩段無上限",
      "segment_type": "二段",
      "holiday_type": "無假日",
      "active": true,
      "tags": [
        "二段",
        "全局寬裕:15分",
        "單一",
        "無假日",
        "無分段上限",
        "無日上限"
      ],
      "has_daily_cap": false,
      "has_segment_cap": false,
      "progressive": false,
      "global_grace_time": 15
    },
    {
      "plan_id": "兩段有上限",
      "name": "兩段有上限",
      "segment_type": "二段",
      "holiday_type": "無假日",
      "active": true,
      "tags": [
        "二段",
        "全局寬裕:15分",
        "單一",
        "日上限",
        "無假日",
        "無分段上限"
      ],
      "has_daily_cap": true,
      "has_segment_cap": false,
      "progressive": false,
      "global_grace_time": 15
    },
    {
      "plan_id": "兩段有分段上限",
      "name": "兩段有分段上限",
      "segment_type": "二段",
      "holiday_type": "無假日",
      "active": true,
      "tags": [
        "二段",
        "全局寬裕:15分",
        "分段上限",
        "單一",
        "無假日",
        "無日上限"
      ],
      "has_daily_cap": false,
      "has_segment_cap": true,
      "progressive": false,
      "global_grace_time": 15
    },
    {
      "plan_id": "全天累進費率無上限",
      "name": "全天累進費率無上限",
      "segment_type": "全天",
      "holiday_type": "無假日",
      "active": true,
      "tags": [
        "全天",
        "全局寬裕:15分",
        "無假日",
        "無分段上限",
        "無日上限",
        "累進"
      ],
      "has_daily_cap": false,
      "has_segment_cap": false,
      "progressive": true,
      "global_grace_time": 15
    },
    {
      "plan_id": "萬華西園",
      "name": "萬華西園",
      "segment_type": "二段",
      "holiday_type": "平日假日",
      "active": true,
      "tags": [
        "二段",
        "分段上限",
        "單一",
        "平日假日",
        "推薦",
        "無全局寬裕",
        "無日上限"
      ],
      "has_daily_cap": false,
      "has_segment_cap": true,
      "progressive": false,
      "global_grace_time": 0
    },
    {
      "plan_id": "全局寬裕時間測試",
      "name": "全局寬裕時間測試",
      "segment_type": "二段",
      "holiday_type": "無假日",
      "active": true,
      "tags": [
        "二段",
        "全局寬裕:20分",
        "單一",
        "無假日",
        "無分段上限",
        "無日上限"
      ],
      "has_daily_cap": false,
      "has_segment_cap": false,
      "progressive": false,
      "global_grace_time": 20
    },
    {
      "plan_id": "billing_cycle_test",
      "name": "計費週期測試方案",
      "segment_type": "多時段",
      "holiday_type": "平日假日",
      "active": true,
      "tags": [
        "單一",
        "多時段",
        "平日假日",
        "無全局寬裕",
        "無分段上限",
        "無日上限"
      ],
      "has_daily_cap": false,
      "has_segment_cap": false,
      "progressive": false,
      "global_grace_time": 0
    }
  ]
}
``
