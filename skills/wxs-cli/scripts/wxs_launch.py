"""Launch only a browser-observed WXS URI through its signed registered handler.

The URI is private stdin IPC. Never include it in exceptions, argv or results.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


def validate_request(request):
    if not isinstance(request, dict) or set(request) != {"url", "source_origin", "format_title"}:
        raise ValueError("Expected a private browser WXS launch request")
    if request["source_origin"] != "https://klef.cbe.go.kr":
        raise ValueError("Launch source is not the observed K-Ed ufine HTTPS origin")
    uri = request["url"]
    match = re.fullmatch(r"wxsclient:(?://handysoft\.co\.kr/|/{1,3})open&url:([^&]+)&title:([^&]+)&windowsize:([^&]+)", uri, flags=re.I) if isinstance(uri, str) and len(uri) <= 32768 else None
    if not match:
        raise ValueError("Unsupported registered WXS launch URI")
    try:
        target, title, size = [base64.b64decode(unquote(value), validate=True).decode("utf-8") for value in match.groups()]
        parsed = urlsplit(target)
        valid = parsed.scheme == "https" and parsed.hostname == "klef.cbe.go.kr" and parsed.port in (None, 443) and not parsed.username and not parsed.password and parsed.path == "/bms/cz/cb/prc/wxsLogin.do" and not parsed.fragment
    except Exception:
        raise ValueError("Invalid private WXS launch payload") from None
    if not valid or title != request["format_title"] or not title.strip() or len(title) > 200 or not re.fullmatch(r"\d{3,4},\d{3,4}", size):
        raise ValueError("WXS target, observed format title or window size differs")
    return {"protocol": "wxsclient", "format_title": title, "source_origin": request["source_origin"]}


def registered_handler():
    if os.name != "nt":
        raise ValueError("Registered WXS launch requires Windows")
    import winreg
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"wxsclient\shell\open\command") as key:
        command = winreg.QueryValueEx(key, "")[0]
    match = re.fullmatch(r'"([^"\r\n]+\\WXSClient\.exe)"\s+"%1"', command, flags=re.I)
    if not match or not Path(match[1]).is_file():
        raise ValueError("Expected the existing registered WXSClient.exe handler")
    executable = Path(match[1])
    script = "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security');$s=Get-AuthenticodeSignature -LiteralPath ([Console]::In.ReadToEnd());@{status=[string]$s.Status;signer=$s.SignerCertificate.Subject}|ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], input=str(executable), capture_output=True, text=True, encoding="utf-8", timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        signature = json.loads(result.stdout.lstrip("\ufeff"))
    except Exception:
        raise ValueError("Could not verify the registered WXS signature") from None
    if result.returncode or signature.get("status") != "Valid" or "HANDYSOFT" not in signature.get("signer", "").upper():
        raise ValueError("Registered WXS handler does not have a valid HANDYSOFT signature")
    return {"executable": str(executable), "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(), "command_sha256": hashlib.sha256(command.encode()).hexdigest(), "signature": "Valid HANDYSOFT"}


def launch(request, *, apply=False, expected_fingerprint=None, handler=registered_handler, start=None):
    preview = {**validate_request(request), **handler()}
    fingerprint = hashlib.sha256(json.dumps({**preview, "uri_sha256": hashlib.sha256(request["url"].encode()).hexdigest()}, sort_keys=True).encode()).hexdigest()
    result = {"ready": True, "applied": False, **preview, "fingerprint": fingerprint, "document_open_verified": False}
    if not apply:
        return result
    if fingerprint != expected_fingerprint:
        raise ValueError("Registered WXS launch changed after review")
    # ShellExecute resolves the freshly reviewed registered handler. This only
    # opens the existing native client; no business API or final action runs.
    try:
        (start or os.startfile)(request["url"])
    except Exception:
        raise ValueError("Registered WXS launch result is unconfirmed; do not repeat") from None
    return {**result, "applied": True}
