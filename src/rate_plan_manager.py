"""
費率方案管理器
提供統一的費率方案設計、配置、驗證和管理功能
支援多種計費模式和費率方案類型
"""

import json
import os
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import shutil


class PlanType(Enum):
    """費率方案類型"""

    TRADITIONAL = "traditional"
    MULTIDIMENSIONAL = "multidimensional"
    UNIFIED = "unified"


class PlanStatus(Enum):
    """費率方案狀態"""

    ACTIVE = "active"
    DRAFT = "draft"
    DISABLED = "disabled"
    ARCHIVED = "archived"


@dataclass
class RatePlanMetadata:
    """費率方案元數據"""

    plan_id: str
    name: str
    description: str
    plan_type: PlanType
    status: PlanStatus
    created_at: datetime
    updated_at: datetime
    created_by: str
    version: str
    tags: List[str]
    coverage_scope: str  # 覆蓋範圍：全時段、特定時段等


@dataclass
class PlanValidationResult:
    """方案驗證結果"""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    coverage_gaps: List[str]
    suggestions: List[str]


class RatePlanManager:
    """費率方案管理器"""

    def __init__(self, config_directory: str = "config"):
        self.config_dir = Path(config_directory)
        self.config_dir.mkdir(exist_ok=True)

        # 配置檔案路徑
        self.traditional_plans_path = self.config_dir / "rate_plans.json"
        self.multidimensional_plans_path = (
            self.config_dir / "multidimensional_rate_plans.json"
        )
        self.unified_plans_path = self.config_dir / "unified_rate_plans.json"
        self.plan_metadata_path = self.config_dir / "plan_metadata.json"
        self.system_templates_path = self.config_dir / "system_templates.json"

        # 初始化數據結構
        self.traditional_plans = {}
        self.multidimensional_plans = {}
        self.unified_plans = {}
        self.plan_metadata = {}
        self.system_templates = {}

        # 載入所有配置
        self.load_all_configurations()

    def load_all_configurations(self):
        """載入所有費率方案配置"""
        try:
            # 載入傳統方案
            if self.traditional_plans_path.exists():
                with open(self.traditional_plans_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.traditional_plans = {
                        plan["rate_plan_id"]: plan
                        for plan in data.get("rate_plans", [])
                    }

            # 載入多維度方案
            if self.multidimensional_plans_path.exists():
                with open(self.multidimensional_plans_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.multidimensional_plans = {
                        template["template_id"]: template
                        for template in data.get("rate_plan_templates", [])
                    }

            # 載入統一方案
            if self.unified_plans_path.exists():
                with open(self.unified_plans_path, "r", encoding="utf-8") as f:
                    self.unified_plans = json.load(f)

            # 載入方案元數據
            if self.plan_metadata_path.exists():
                with open(self.plan_metadata_path, "r", encoding="utf-8") as f:
                    metadata_data = json.load(f)
                    self.plan_metadata = {
                        plan_id: RatePlanMetadata(**data)
                        for plan_id, data in metadata_data.items()
                    }

            # 載入系統範本
            if self.system_templates_path.exists():
                with open(self.system_templates_path, "r", encoding="utf-8") as f:
                    self.system_templates = json.load(f)
            else:
                self.create_default_system_templates()

        except Exception as e:
            print(f"載入費率方案配置失敗: {e}")

    def create_default_system_templates(self):
        """創建預設系統範本"""
        self.system_templates = {
            "templates": {
                "basic_hourly": {
                    "name": "基本時段費率範本",
                    "description": "適用於一般停車場的基本時段計費",
                    "template_type": "traditional",
                    "time_slots": [
                        {
                            "time_slot_id": "day",
                            "label": "日間時段",
                            "start": "08:00",
                            "end": "22:00",
                            "unit_minutes": 60,
                            "default_unit_price": 30,
                            "grace_minutes": 15,
                            "grace_enabled": True,
                        },
                        {
                            "time_slot_id": "night",
                            "label": "夜間時段",
                            "start": "22:00",
                            "end": "08:00",
                            "unit_minutes": 60,
                            "default_unit_price": 20,
                            "grace_minutes": 0,
                            "grace_enabled": False,
                        },
                    ],
                },
                "progressive_pricing": {
                    "name": "累進計費範本",
                    "description": "適用於商場等需要累進計費的場所",
                    "template_type": "traditional",
                    "time_slots": [
                        {
                            "time_slot_id": "all_day",
                            "label": "全天時段",
                            "start": "00:00",
                            "end": "24:00",
                            "unit_minutes": 30,
                            "progressive_enabled": True,
                            "progressive_rates": [
                                {
                                    "start_min": 0,
                                    "end_min": 120,
                                    "unit_minutes": 30,
                                    "unit_price": 25,
                                },
                                {
                                    "start_min": 120,
                                    "end_min": 240,
                                    "unit_minutes": 30,
                                    "unit_price": 30,
                                },
                                {
                                    "start_min": 240,
                                    "end_min": None,
                                    "unit_minutes": 30,
                                    "unit_price": 35,
                                },
                            ],
                        }
                    ],
                },
                "multidimensional_basic": {
                    "name": "基本多維度範本",
                    "description": "多維度標籤計費基本範本",
                    "template_type": "multidimensional",
                    "time_segment_types": ["全天", "兩段", "三段", "四段"],
                    "holiday_types": ["無假日費率", "六日費率", "國定假費率"],
                },
            },
            "validation_rules": {
                "time_coverage": "必須覆蓋24小時",
                "price_range": {"min": 0, "max": 1000},
                "time_slot_min_duration": 15,
                "max_time_slots_per_plan": 10,
            },
            "default_settings": {
                "currency": "NT$",
                "precision": 0,
                "round_up": True,
                "grace_period_max": 30,
                "daily_cap_max": 500,
            },
        }
        self.save_system_templates()

    def save_system_templates(self):
        """儲存系統範本"""
        try:
            with open(self.system_templates_path, "w", encoding="utf-8") as f:
                json.dump(self.system_templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"儲存系統範本失敗: {e}")

    def get_all_plans(self) -> Dict[str, Any]:
        """獲取所有費率方案"""
        all_plans = {}

        # 整合傳統方案
        for plan_id, plan_data in self.traditional_plans.items():
            all_plans[plan_id] = {
                **plan_data,
                "plan_type": "traditional",
                "metadata": self.plan_metadata.get(plan_id),
            }

        # 整合多維度方案
        for plan_id, plan_data in self.multidimensional_plans.items():
            all_plans[plan_id] = {
                **plan_data,
                "plan_type": "multidimensional",
                "metadata": self.plan_metadata.get(plan_id),
            }

        # 整合統一方案
        for plan_id, plan_data in self.unified_plans.items():
            all_plans[plan_id] = {
                **plan_data,
                "plan_type": "unified",
                "metadata": self.plan_metadata.get(plan_id),
            }

        return all_plans

    def create_plan_from_template(
        self, template_name: str, plan_config: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """從範本創建費率方案"""
        try:
            if template_name not in self.system_templates.get("templates", {}):
                return False, f"範本 {template_name} 不存在"

            template = self.system_templates["templates"][template_name]
            plan_id = plan_config.get("plan_id")

            if not plan_id:
                return False, "必須指定方案ID"

            # 檢查ID是否已存在
            if self.plan_exists(plan_id):
                return False, f"方案ID {plan_id} 已存在"

            # 根據範本類型創建方案
            if template["template_type"] == "traditional":
                success = self.create_traditional_plan(plan_id, template, plan_config)
            elif template["template_type"] == "multidimensional":
                success = self.create_multidimensional_plan(
                    plan_id, template, plan_config
                )
            else:
                return False, f"不支援的範本類型: {template['template_type']}"

            if success:
                self.create_plan_metadata(
                    plan_id, plan_config, template["template_type"]
                )
                return True, f"成功創建費率方案: {plan_id}"
            else:
                return False, "創建費率方案失敗"

        except Exception as e:
            return False, f"創建費率方案時發生錯誤: {str(e)}"

    def create_traditional_plan(
        self, plan_id: str, template: Dict, config: Dict
    ) -> bool:
        """創建傳統費率方案"""
        try:
            plan_data = {
                "rate_plan_id": plan_id,
                "label": config.get("label", template["name"]),
                "description": config.get("description", template["description"]),
                "date_type": config.get("date_type", "weekday"),
                "apply_on_holiday": config.get("apply_on_holiday", False),
                "daily_cap_enabled": config.get("daily_cap_enabled", False),
                "daily_cap_amount": config.get("daily_cap_amount"),
                "split_by_timeslot_enabled": True,
                "split_by_day_enabled": True,
                "night_cross_day_split": True,
                "enable_zero_fee": True,
                "round_up_enabled": True,
                "skip_fee_when_total_free": True,
                "manual_override_enabled": True,
                "time_slots": [],
            }

            # 處理時段配置
            for slot_template in template.get("time_slots", []):
                time_slot = {
                    **slot_template,
                    "cap_enabled": config.get("cap_enabled", False),
                    "cap_amount": config.get("cap_amount", 100),
                }
                plan_data["time_slots"].append(time_slot)

            # 保存到傳統方案
            self.traditional_plans[plan_id] = plan_data
            self.save_traditional_plans()
            return True

        except Exception as e:
            print(f"創建傳統方案失敗: {e}")
            return False

    def create_multidimensional_plan(
        self, plan_id: str, template: Dict, config: Dict
    ) -> bool:
        """創建多維度費率方案"""
        try:
            # 多維度方案創建邏輯
            plan_data = {
                "template_id": plan_id,
                "label": config.get("label", template["name"]),
                "description": config.get("description", template["description"]),
                "time_segment_type": config.get("time_segment_type", "兩段"),
                "holiday_type": config.get("holiday_type", "無假日費率"),
                "dimension_combination": f"{config.get('time_segment_type', '兩段')}_{config.get('holiday_type', '無假日費率')}",
            }

            # 保存到多維度方案
            self.multidimensional_plans[plan_id] = plan_data
            self.save_multidimensional_plans()
            return True

        except Exception as e:
            print(f"創建多維度方案失敗: {e}")
            return False

    def create_plan_metadata(self, plan_id: str, config: Dict, plan_type: str):
        """創建方案元數據"""
        metadata = RatePlanMetadata(
            plan_id=plan_id,
            name=config.get("label", "未命名方案"),
            description=config.get("description", ""),
            plan_type=PlanType(plan_type),
            status=PlanStatus(config.get("status", "draft")),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            created_by=config.get("created_by", "system"),
            version="1.0",
            tags=config.get("tags", []),
            coverage_scope=config.get("coverage_scope", "全時段"),
        )

        self.plan_metadata[plan_id] = metadata
        self.save_plan_metadata()

    def validate_plan(self, plan_id: str) -> PlanValidationResult:
        """驗證費率方案"""
        errors = []
        warnings = []
        coverage_gaps = []
        suggestions = []

        try:
            plan_data = self.get_plan_by_id(plan_id)
            if not plan_data:
                return PlanValidationResult(
                    is_valid=False,
                    errors=["方案不存在"],
                    warnings=[],
                    coverage_gaps=[],
                    suggestions=[],
                )

            plan_type = plan_data.get("plan_type", "traditional")

            if plan_type == "traditional":
                return self.validate_traditional_plan(plan_data)
            elif plan_type == "multidimensional":
                return self.validate_multidimensional_plan(plan_data)
            else:
                errors.append(f"不支援的方案類型: {plan_type}")

        except Exception as e:
            errors.append(f"驗證過程中發生錯誤: {str(e)}")

        return PlanValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            coverage_gaps=coverage_gaps,
            suggestions=suggestions,
        )

    def validate_traditional_plan(self, plan_data: Dict) -> PlanValidationResult:
        """驗證傳統費率方案"""
        errors = []
        warnings = []
        coverage_gaps = []
        suggestions = []

        time_slots = plan_data.get("time_slots", [])

        # 檢查時段覆蓋
        if not time_slots:
            errors.append("至少需要一個時段")
        else:
            # 檢查24小時覆蓋
            covered_minutes = set()
            for slot in time_slots:
                start_time = self.parse_time_str(slot.get("start", "00:00"))
                end_time = self.parse_time_str(slot.get("end", "00:00"))

                # 計算覆蓋的分鐘數
                if end_time <= start_time:  # 跨日
                    # 從start到24:00
                    for minute in range(
                        start_time.hour * 60 + start_time.minute, 24 * 60
                    ):
                        covered_minutes.add(minute)
                    # 從00:00到end
                    for minute in range(0, end_time.hour * 60 + end_time.minute):
                        covered_minutes.add(minute)
                else:
                    for minute in range(
                        start_time.hour * 60 + start_time.minute,
                        end_time.hour * 60 + end_time.minute,
                    ):
                        covered_minutes.add(minute)

            # 檢查是否完整覆蓋24小時
            total_day_minutes = set(range(24 * 60))
            uncovered_minutes = total_day_minutes - covered_minutes

            if uncovered_minutes:
                coverage_gaps.append(f"未覆蓋的時間段: {len(uncovered_minutes)} 分鐘")

        # 檢查價格合理性
        for slot in time_slots:
            price = slot.get("default_unit_price", 0)
            if price < 0:
                errors.append(f"時段 {slot.get('label', 'unknown')} 的價格不能為負數")
            elif price > 1000:
                warnings.append(
                    f"時段 {slot.get('label', 'unknown')} 的價格過高: {price}"
                )

        return PlanValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            coverage_gaps=coverage_gaps,
            suggestions=suggestions,
        )

    def validate_multidimensional_plan(self, plan_data: Dict) -> PlanValidationResult:
        """驗證多維度費率方案"""
        errors = []
        warnings = []
        coverage_gaps = []
        suggestions = []

        # 多維度方案的驗證邏輯
        time_segment_type = plan_data.get("time_segment_type")
        holiday_type = plan_data.get("holiday_type")

        if not time_segment_type:
            errors.append("必須指定時段類型")

        if not holiday_type:
            errors.append("必須指定假日類型")

        return PlanValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            coverage_gaps=coverage_gaps,
            suggestions=suggestions,
        )

    def parse_time_str(self, time_str: str) -> time:
        """解析時間字串"""
        try:
            hour, minute = map(int, time_str.split(":"))
            return time(hour, minute)
        except:
            return time(0, 0)

    def plan_exists(self, plan_id: str) -> bool:
        """檢查方案是否存在"""
        return (
            plan_id in self.traditional_plans
            or plan_id in self.multidimensional_plans
            or plan_id in self.unified_plans
        )

    def get_plan_by_id(self, plan_id: str) -> Optional[Dict]:
        """根據ID獲取方案"""
        if plan_id in self.traditional_plans:
            return {**self.traditional_plans[plan_id], "plan_type": "traditional"}
        elif plan_id in self.multidimensional_plans:
            return {
                **self.multidimensional_plans[plan_id],
                "plan_type": "multidimensional",
            }
        elif plan_id in self.unified_plans:
            return {**self.unified_plans[plan_id], "plan_type": "unified"}
        return None

    def delete_plan(self, plan_id: str) -> Tuple[bool, str]:
        """刪除費率方案"""
        try:
            if not self.plan_exists(plan_id):
                return False, "方案不存在"

            # 刪除方案數據
            if plan_id in self.traditional_plans:
                del self.traditional_plans[plan_id]
                self.save_traditional_plans()
            elif plan_id in self.multidimensional_plans:
                del self.multidimensional_plans[plan_id]
                self.save_multidimensional_plans()
            elif plan_id in self.unified_plans:
                del self.unified_plans[plan_id]
                self.save_unified_plans()

            # 刪除元數據
            if plan_id in self.plan_metadata:
                del self.plan_metadata[plan_id]
                self.save_plan_metadata()

            return True, f"成功刪除方案: {plan_id}"

        except Exception as e:
            return False, f"刪除方案失敗: {str(e)}"

    def save_traditional_plans(self):
        """儲存傳統費率方案"""
        try:
            data = {
                "description": "傳統停車費率方案配置",
                "version": "1.0",
                "rate_plans": list(self.traditional_plans.values()),
            }

            # 備份現有檔案
            if self.traditional_plans_path.exists():
                backup_path = self.traditional_plans_path.with_suffix(".json.backup")
                shutil.copy2(self.traditional_plans_path, backup_path)

            with open(self.traditional_plans_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"儲存傳統方案失敗: {e}")

    def save_multidimensional_plans(self):
        """儲存多維度費率方案"""
        try:
            data = {
                "description": "多維度停車費率方案配置",
                "version": "1.0",
                "rate_plan_templates": list(self.multidimensional_plans.values()),
            }

            # 備份現有檔案
            if self.multidimensional_plans_path.exists():
                backup_path = self.multidimensional_plans_path.with_suffix(
                    ".json.backup"
                )
                shutil.copy2(self.multidimensional_plans_path, backup_path)

            with open(self.multidimensional_plans_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"儲存多維度方案失敗: {e}")

    def save_unified_plans(self):
        """儲存統一費率方案"""
        try:
            # 備份現有檔案
            if self.unified_plans_path.exists():
                backup_path = self.unified_plans_path.with_suffix(".json.backup")
                shutil.copy2(self.unified_plans_path, backup_path)

            with open(self.unified_plans_path, "w", encoding="utf-8") as f:
                json.dump(self.unified_plans, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"儲存統一方案失敗: {e}")

    def save_plan_metadata(self):
        """儲存方案元數據"""
        try:
            # 轉換為可序列化格式
            serializable_metadata = {}
            for plan_id, metadata in self.plan_metadata.items():
                data = asdict(metadata)
                # 轉換日期時間為字串
                data["created_at"] = metadata.created_at.isoformat()
                data["updated_at"] = metadata.updated_at.isoformat()
                # 轉換枚舉為字串
                data["plan_type"] = metadata.plan_type.value
                data["status"] = metadata.status.value
                serializable_metadata[plan_id] = data

            with open(self.plan_metadata_path, "w", encoding="utf-8") as f:
                json.dump(serializable_metadata, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"儲存方案元數據失敗: {e}")

    def get_system_templates(self) -> Dict[str, Any]:
        """獲取系統範本"""
        return self.system_templates

    def get_plan_statistics(self) -> Dict[str, Any]:
        """獲取方案統計資訊"""
        total_plans = (
            len(self.traditional_plans)
            + len(self.multidimensional_plans)
            + len(self.unified_plans)
        )

        status_counts = {}
        for metadata in self.plan_metadata.values():
            status = metadata.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_plans": total_plans,
            "traditional_plans": len(self.traditional_plans),
            "multidimensional_plans": len(self.multidimensional_plans),
            "unified_plans": len(self.unified_plans),
            "status_distribution": status_counts,
            "last_updated": datetime.now().isoformat(),
        }


def main():
    """主程式 - 示範覆蓋分析功能"""
    manager = RatePlanManager()

    # 生成覆蓋率報告
    report = manager.generate_coverage_report(2024)

    print("=== 停車費率方案覆蓋率分析報告 ===")
    print(f"分析年度: {report['analyzed_year']}")
    print(f"總計畫數: {report['plan_summary']['total_plans']}")
    print(f"覆蓋率: {report['coverage_statistics']['coverage_percentage']:.1f}%")
    print(f"完整覆蓋天數: {report['coverage_statistics']['full_coverage_days']}")
    print(f"部分覆蓋天數: {report['coverage_statistics']['partial_coverage_days']}")
    print(f"無覆蓋天數: {report['coverage_statistics']['no_coverage_days']}")

    if report["improvement_suggestions"]:
        print("\n=== 改進建議 ===")
        for suggestion in report["improvement_suggestions"]:
            print(f"- {suggestion['suggestion']}")

    # 將報告寫入檔案
    os.makedirs("log", exist_ok=True)
    with open("log/rate_plan_coverage_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n詳細報告已儲存到: log/rate_plan_coverage_report.json")


if __name__ == "__main__":
    main()
