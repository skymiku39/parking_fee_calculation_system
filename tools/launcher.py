import os
import threading
import time
import webbrowser
from urllib.request import urlopen

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


def _prepare_runtime() -> None:
    from src.core.paths import DATA_ENV_VAR, ensure_data_dir, executable_dir

    os.chdir(executable_dir())
    data_dir = ensure_data_dir(seed_if_missing=True)
    os.environ[DATA_ENV_VAR] = str(data_dir)
    os.makedirs("log", exist_ok=True)


def run_server() -> None:
    from app import app

    app.run(host="127.0.0.1", port=DEFAULT_PORT, debug=False, use_reloader=False)


def main() -> int:
    try:
        _prepare_runtime()
    except Exception:
        pass

    if is_server_up(SERVER_URL, timeout=1.0):
        open_browser(SERVER_URL)
        return 0

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    for _ in range(100):
        if is_server_up(SERVER_URL, timeout=0.5):
            open_browser(SERVER_URL)
            break
        time.sleep(0.1)

    try:
        while t.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
