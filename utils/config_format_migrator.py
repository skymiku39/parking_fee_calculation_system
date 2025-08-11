#!/usr/bin/env python3
"""
配置格式遷移工具
將舊格式的費率配置轉換為新格式（移除grace_time，改為全域設定）
"""

import json
import os
from typing import Dict, Any


def migrate_rate_matrix(
    rate_matrix: Dict[str, Any], default_grace_time: int = 15
) -> tuple[Dict[str, Any], int]:
    """
    遷移費率矩陣配置格式

    Args:
        rate_matrix: 原始費率矩陣
        default_grace_time: 預設寬裕時間

    Returns:
        tuple: (遷移後的費率矩陣, 提取的全域寬裕時間)
    """
    migrated_matrix = {}
    extracted_grace_time = default_grace_time

    for key, config in rate_matrix.items():
        new_config = config.copy()

        # 提取grace_time作為全域設定
        if "grace_time" in new_config:
            extracted_grace_time = new_config["grace_time"]
            del new_config["grace_time"]

        migrated_matrix[key] = new_config

    return migrated_matrix, extracted_grace_time


def migrate_user_defined_plans(file_path: str) -> bool:
    """
    遷移用戶自定義方案文件

    Args:
        file_path: 配置文件路徑

    Returns:
        bool: 是否成功遷移
    """
    try:
        # 備份原文件
        backup_path = f"{file_path}.backup_before_migration"
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                backup_data = f.read()
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(backup_data)
            print(f"✅ 已備份原文件至: {backup_path}")

        # 讀取原配置
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        migrated_count = 0

        # 遷移每個方案
        for plan_name, plan_data in data.get("plans", {}).items():
            if "rate_matrix" in plan_data:
                original_matrix = plan_data["rate_matrix"]
                migrated_matrix, extracted_grace_time = migrate_rate_matrix(
                    original_matrix
                )

                # 更新費率矩陣
                plan_data["rate_matrix"] = migrated_matrix

                # 更新全域設定
                if "global_caps" not in plan_data:
                    plan_data["global_caps"] = {}

                plan_data["global_caps"]["global_grace_time"] = extracted_grace_time

                migrated_count += 1
                print(
                    f"✅ 已遷移方案: {plan_name} (寬裕時間: {extracted_grace_time}分鐘)"
                )

        # 保存遷移後的配置
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 遷移完成！共處理 {migrated_count} 個方案")
        return True

    except Exception as e:
        print(f"❌ 遷移失敗: {str(e)}")
        return False


def main():
    """主函數"""
    print("=== 配置格式遷移工具 ===\n")

    # 需要遷移的配置文件
    config_files = [
        "config/user_defined_plans.json",
        # 可以添加其他需要遷移的文件
    ]

    for config_file in config_files:
        if os.path.exists(config_file):
            print(f"正在遷移: {config_file}")
            success = migrate_user_defined_plans(config_file)
            if success:
                print(f"✅ {config_file} 遷移成功\n")
            else:
                print(f"❌ {config_file} 遷移失敗\n")
        else:
            print(f"⚠️  文件不存在: {config_file}\n")

    print("=== 遷移完成 ===")
    print("說明:")
    print("1. 原文件已備份為 .backup_before_migration")
    print("2. grace_time 欄位已從個別費率配置中移除")
    print("3. grace_time 已轉換為 global_caps.global_grace_time")
    print("4. 費率組合矩陣現在應該可以正常編輯")


if __name__ == "__main__":
    main()
