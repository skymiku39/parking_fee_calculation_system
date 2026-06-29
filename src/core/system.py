import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.application.fee_strategies import build_fee_strategies
from src.application.user_defined_billing import UserDefinedBillingService
from src.core.calendar_resolver import HolidayCalendar
from src.core.events import (
    CalendarPersisted,
    EventBus,
    MdpConfigSaved,
    ParkingFeeCalculated,
    SystemConfigUpdated,
    UserPlanDeleted,
    UserPlanSaved,
)
from src.core.repositories import (
    CalendarRepository,
    MdpConfigRepository,
    SystemConfigRepository,
    UserPlansRepository,
)
from src.core.subscribers import register_default_subscribers
from src.core.utils import (
    format_duration_display,
    get_rate_description,
    merge_system_config,
)
from src.core.validation import (
    ConfigValidationError,
    validate_multidimensional_config_json,
    validate_plan_v2_json,
)
from src.domain.multidimensional_calculator import (
    MultidimensionalParkingCalculator,
)
from src.domain.segment_utils import find_active_segment_at

logger = logging.getLogger(__name__)


class SmartParkingSystem:
    """Composition root: orchestrates repositories, billing services, and pub/sub."""

    def __init__(
        self,
        base_path: Optional[Union[str, Path]] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.base_path = Path(base_path) if base_path is not None else Path(".")
        self.event_bus = event_bus or EventBus()
        self.multidimensional_calculator: Optional[MultidimensionalParkingCalculator] = None
        self.system_config: Dict[str, Any] = {}
        self.persisted_system_config: Dict[str, Any] = {}
        self.holiday_calendar: Optional[HolidayCalendar] = None

        self._system_config_repo = SystemConfigRepository(self.base_path)
        self._calendar_repo = CalendarRepository(self.base_path)
        self._mdp_repo = MdpConfigRepository(self.base_path)
        self._user_plans_repo = UserPlansRepository(self.base_path)
        self._billing = UserDefinedBillingService(self)
        self._fee_strategies = build_fee_strategies(self)

        register_default_subscribers(self, self.event_bus)

        self.load_system_config()
        self.refresh_runtime_state(calendar=True, mdp=True)

    def _config_path(self, *parts: str) -> Path:
        return self.base_path.joinpath(*parts)

    # ----- Runtime state (Pub/Sub subscribers call this) -----

    def refresh_runtime_state(self, *, calendar: bool = False, mdp: bool = False) -> None:
        if calendar:
            self.reload_holiday_calendar()
        if mdp:
            self.init_multidimensional_calculator()

    # ----- System config -----

    def load_system_config(self) -> None:
        try:
            self.persisted_system_config = self._system_config_repo.load_persisted()
            self.system_config = self._system_config_repo.load_runtime(
                self.persisted_system_config
            )
        except Exception as e:
            logger.exception("載入系統配置失敗: %s", e)
            self.persisted_system_config = {}
            self.system_config = {}

    def save_system_config(self) -> None:
        try:
            self._system_config_repo.save(self.persisted_system_config)
        except Exception as e:
            logger.exception("Failed to save system config: %s", e)

    def update_system_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        from src.core.utils import validate_and_normalize_system_config

        merged_config = merge_system_config(self.persisted_system_config, new_config)
        self.persisted_system_config = validate_and_normalize_system_config(
            merged_config,
            include_env_overrides=False,
        )
        self.system_config = validate_and_normalize_system_config(
            self.persisted_system_config
        )
        self.save_system_config()
        self.event_bus.publish(
            SystemConfigUpdated(changed_keys=tuple(new_config.keys()))
        )
        return self.system_config

    # ----- Calendar (repository + events) -----

    def load_calendar(self) -> Dict[str, Any]:
        return self._calendar_repo.load()

    def save_calendar(self, data: Dict[str, Any], *, source: str = "manual") -> None:
        self._calendar_repo.save(data)
        self.event_bus.publish(CalendarPersisted(source=source))

    @property
    def calendar_path(self) -> Path:
        return self._calendar_repo.path

    def reload_holiday_calendar(self) -> None:
        try:
            self.holiday_calendar = HolidayCalendar(self._calendar_repo.path)
        except Exception as e:
            logger.exception("載入假日日曆失敗: %s", e)
            self.holiday_calendar = HolidayCalendar(self._calendar_repo.path)

    # ----- MDP config (repository + events) -----

    def load_mdp_config(self) -> Dict[str, Any]:
        return self._mdp_repo.load()

    def save_mdp_config(
        self,
        data: Dict[str, Any],
        *,
        template_id: Optional[str] = None,
        action: str = "save",
    ) -> None:
        self._mdp_repo.save(data)
        self.event_bus.publish(MdpConfigSaved(template_id=template_id, action=action))

    @property
    def mdp_config_path(self) -> Path:
        return self._mdp_repo.path

    def init_multidimensional_calculator(self) -> None:
        try:
            cfg_path = self._mdp_repo.path
            if cfg_path.exists():
                import json

                with open(cfg_path, "r", encoding="utf-8") as f:
                    _cfg = json.load(f)
                validate_multidimensional_config_json(_cfg)

            calendar = self.holiday_calendar
            if calendar is None:
                self.reload_holiday_calendar()
                calendar = self.holiday_calendar

            self.multidimensional_calculator = MultidimensionalParkingCalculator(
                str(cfg_path),
                holiday_calendar=calendar,
            )
            logger.info("多維度標籤計算器載入成功")
        except Exception as e:
            logger.exception("多維度標籤計算器載入失敗: %s", e)

    # ----- User-defined plans (repository + events) -----

    def user_plans_path(self) -> Path:
        return self._user_plans_repo.path

    def load_user_defined_plans_config(self) -> Dict[str, Any]:
        return self._user_plans_repo.load()

    def _save_user_defined_plans_config(self, config_obj: Dict[str, Any]) -> None:
        self._user_plans_repo.save(config_obj)

    @staticmethod
    def _is_plan_featured(plan_data: Dict[str, Any]) -> bool:
        if plan_data.get("featured") is True:
            return True
        tags = plan_data.get("tags") or []
        return "featured" in tags or "推薦" in tags

    def list_user_defined_plans(self, *, apply_ui_filters: bool = True) -> List[Dict[str, Any]]:
        try:
            config_obj = self.load_user_defined_plans_config()
        except (FileNotFoundError, ConfigValidationError):
            return []

        plans = config_obj.get("plans", {})
        items: List[Dict[str, Any]] = []
        for plan_id, plan_data in plans.items():
            if plan_data.get("active") is False:
                continue
            items.append(
                {
                    "rate_plan_id": plan_id,
                    "plan_id": plan_id,
                    "label": plan_data.get("name", plan_id),
                    "description": plan_data.get("description", ""),
                    "type": "user_defined",
                    "segment_type": plan_data.get("segment_type"),
                    "holiday_type": plan_data.get("holiday_type"),
                    "featured": self._is_plan_featured(plan_data),
                    "active": plan_data.get("active", True),
                }
            )

        if not apply_ui_filters:
            return sorted(items, key=lambda x: (not x["featured"], x["label"]))

        ui_settings = self.system_config.get("ui_settings") or {}
        if ui_settings.get("show_only_featured_user_plans"):
            items = [item for item in items if item["featured"]]

        items.sort(key=lambda x: (not x["featured"], x["label"]))
        max_display = ui_settings.get("max_user_plans_display")
        if isinstance(max_display, int) and max_display > 0:
            items = items[:max_display]
        return items

    def get_user_defined_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        try:
            config_obj = self.load_user_defined_plans_config()
        except (FileNotFoundError, ConfigValidationError):
            return None
        return config_obj.get("plans", {}).get(plan_id)

    def save_user_defined_plan(self, plan_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        if not plan_id or not str(plan_id).strip():
            raise ValueError("plan_id 不可為空")

        validate_plan_v2_json(plan_data)
        plan_id = str(plan_id).strip()

        try:
            config_obj = self.load_user_defined_plans_config()
        except FileNotFoundError:
            config_obj = {"plans": {}, "metadata": {}}
        except ConfigValidationError as exc:
            raise ValueError(
                f"現有自訂方案配置不合法: {', '.join(exc.errors) if exc.errors else str(exc)}"
            ) from exc

        plans = config_obj.setdefault("plans", {})
        now = datetime.now().isoformat()
        existing = plans.get(plan_id)
        action = "update" if existing else "create"
        if existing:
            plan_data.setdefault("created_date", existing.get("created_date", now))
        else:
            plan_data.setdefault("created_date", now)
        plan_data["modified_date"] = now
        plan_data.setdefault("version", "1.0")
        plan_data.setdefault("active", True)
        if "name" not in plan_data or not plan_data["name"]:
            plan_data["name"] = plan_id

        plans[plan_id] = plan_data
        metadata = config_obj.setdefault("metadata", {})
        metadata["last_modified"] = now
        metadata.setdefault("version", "1.0")

        self._save_user_defined_plans_config(config_obj)
        self.event_bus.publish(UserPlanSaved(plan_id=plan_id, action=action))
        return plan_data

    def delete_user_defined_plan(self, plan_id: str) -> bool:
        try:
            config_obj = self.load_user_defined_plans_config()
        except (FileNotFoundError, ConfigValidationError):
            return False

        plans = config_obj.get("plans", {})
        if plan_id not in plans:
            return False

        del plans[plan_id]
        metadata = config_obj.setdefault("metadata", {})
        metadata["last_modified"] = datetime.now().isoformat()
        self._save_user_defined_plans_config(config_obj)
        self.event_bus.publish(UserPlanDeleted(plan_id=plan_id))
        return True

    def is_multidimensional_plan(self, plan_id: str) -> bool:
        calc = self.multidimensional_calculator
        if not calc:
            return False
        return plan_id in calc.rate_plan_templates

    def is_user_defined_plan(self, plan_id: str) -> bool:
        return self.get_user_defined_plan(plan_id) is not None

    # ----- Fee calculation (strategy pattern + pub/sub audit event) -----

    def calculate_parking_fee(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: Optional[str] = None,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            if not plan_id:
                raise ValueError("請提供 plan_id 或使用 plan_inline 進行即時試算")

            for strategy in self._fee_strategies:
                if strategy.supports(plan_id):
                    result = strategy.calculate(
                        enter_time, exit_time, plan_id, manual_adjustment, context
                    )
                    if result.get("success"):
                        self.event_bus.publish(
                            ParkingFeeCalculated(
                                plan_id=plan_id,
                                engine=str(result.get("calculation_engine", "")),
                                total_amount=int(result.get("total_amount", 0)),
                            )
                        )
                    return result

            raise ValueError(f"找不到費率方案: {plan_id}")
        except Exception as e:
            return {"success": False, "error": str(e), "calculation_engine": "none"}

    def calculate_with_user_defined_plan(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_id: str,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            plan_data = self.get_user_defined_plan(plan_id)
            if not plan_data:
                raise ValueError(f"找不到用戶自訂方案: {plan_id}")

            return self.calculate_fee_by_billing_cycles(
                enter_time=enter_time,
                exit_time=exit_time,
                plan_data=plan_data,
                manual_adjustment=manual_adjustment,
            )
        except Exception as e:
            return {
                "success": False,
                "error": f"用戶自訂方案計算失敗: {str(e)}",
                "calculation_engine": "user_defined_billing_cycle",
            }

    def calculate_fee_by_billing_cycles(
        self,
        enter_time: datetime,
        exit_time: datetime,
        plan_data: dict,
        manual_adjustment: int = 0,
    ) -> Dict[str, Any]:
        return self._billing.calculate(
            enter_time, exit_time, plan_data, manual_adjustment
        )

    # ----- Date / segment resolution (DateCategoryResolver port) -----

    def determine_segment_date_category(
        self, current_time: datetime, segment: dict, holiday_type: str
    ) -> str:
        segment_start = segment["start"]
        segment_end = segment["end"]
        if segment_start > segment_end or segment_end == "24:00":
            current_time_only = current_time.time()
            segment_start_time = datetime.strptime(segment_start, "%H:%M").time()
            if current_time_only >= segment_start_time:
                return self.determine_date_category(current_time, holiday_type)
            previous_day = current_time - timedelta(days=1)
            return self.determine_date_category(previous_day, holiday_type)
        return self.determine_date_category(current_time, holiday_type)

    def find_active_segment_at_time(
        self, check_time: datetime, segments: List[dict]
    ) -> Optional[dict]:
        return find_active_segment_at(check_time, segments)

    def get_rate_description(self, rate_config: dict) -> str:
        return get_rate_description(rate_config)

    def calculate_with_multidimensional(
        self,
        enter_time: datetime,
        exit_time: datetime,
        template_id: str,
        manual_adjustment: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            result = self.multidimensional_calculator.calculate_parking_fee(
                enter_time, exit_time, template_id
            )
            return {
                "success": True,
                "calculation_engine": "multidimensional",
                "total_amount": result.total_amount + manual_adjustment,
                "original_amount": result.original_amount,
                "manual_adjustment": manual_adjustment,
                "date_category": result.date_category.value,
                "applied_rate_plan": result.applied_rate_plan,
                "segment_type": result.segment_type,
                "time_segment_type": result.segment_type,
                "holiday_type": result.holiday_type,
                "session_details": result.session_details,
                "calculation_summary": result.calculation_summary,
                "dimension_tags": result.dimension_tags,
                "enter_time": enter_time,
                "exit_time": exit_time,
                "total_duration_minutes": int((exit_time - enter_time).total_seconds() / 60),
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"多維度計算失敗: {str(e)}",
                "calculation_engine": "multidimensional",
            }

    def format_duration_display(self, minutes: int) -> str:
        return format_duration_display(minutes)

    def determine_date_category(self, check_time: datetime, holiday_type: str) -> str:
        if self.holiday_calendar is None:
            self.reload_holiday_calendar()
        calendar = self.holiday_calendar
        if calendar is not None:
            return calendar.classify_user_defined_date(check_time.date(), holiday_type)

        weekday = check_time.weekday()
        if holiday_type == "無假日":
            return "統一"
        if holiday_type == "平日假日":
            return "平日" if weekday < 5 else "假日"
        if holiday_type == "完整假日":
            return "節慶日" if weekday == 6 else ("假日" if weekday == 5 else "平日")
        return "統一"
