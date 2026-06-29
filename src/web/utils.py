from typing import Dict

from flask import jsonify


def error_response(code: str, message: str, http_status: int = 400, extra: Dict = None):
    payload = {"success": False, "code": code, "message": message, "error": message}
    if isinstance(extra, dict):
        payload.update(extra)
    return jsonify(payload), http_status



