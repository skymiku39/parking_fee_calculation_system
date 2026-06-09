from src.core.paths import resolve_data_dir
from src.core.system import SmartParkingSystem

# 單例全域系統物件（資料目錄：開發=config/，打包=data/）
parking_system = SmartParkingSystem(base_path=resolve_data_dir())



