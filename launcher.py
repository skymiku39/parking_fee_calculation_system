import os
import sys
import threading
import time
import webbrowser
from urllib.request import urlopen
from urllib.error import URLError


DEFAULT_PORT = int(os.getenv("PORT", "5000"))
SERVER_URL = f"http://127.0.0.1:{DEFAULT_PORT}/"


def is_server_up(url: str, timeout: float = 1.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as resp:  # nosec B310
            return resp.status < 500
    except Exception:
        return False


def open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        pass


def run_server() -> None:
    # 確保日誌與必要資料夾
    os.makedirs("log", exist_ok=True)
    # 啟動 Flask（不使用 reloader，避免多進程）
    from app import app  # 延遲載入，確保當前工作目錄已就緒
    app.run(host="127.0.0.1", port=DEFAULT_PORT, debug=False, use_reloader=False)


def main() -> int:
    # 將工作目錄設成可寫的當前位置（對便攜式打包較友善）
    try:
        base_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
        if base_dir:
            os.chdir(base_dir)
    except Exception:
        pass

    if is_server_up(SERVER_URL, timeout=1.0):
        open_browser(SERVER_URL)
        return 0

    # 尚未啟動：開一個執行緒跑 Flask，再等待存活後開瀏覽器
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # 等待最多 10 秒確認啟動
    for _ in range(100):
        if is_server_up(SERVER_URL, timeout=0.5):
            open_browser(SERVER_URL)
            break
        time.sleep(0.1)

    # 主執行緒阻塞，讓服務常駐
    try:
        while t.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


