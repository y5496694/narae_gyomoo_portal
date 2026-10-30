"""Sequential read-only capture. This module is used only through wxs_cli.py."""
import json
import hashlib
from pathlib import Path
import re
import time

import win32gui
import win32process


def title_matches(actual, expected):
    # Browser innerText collapses spaces that the native window title preserves.
    # No substring, punctuation, or case folding is allowed.
    return ' '.join(actual.split()) == ' '.join(expected.split())


def identity(window, expected_title):
    hwnd = window["hwnd"]
    if (not win32gui.IsWindow(hwnd)
            or win32process.GetWindowThreadProcessId(hwnd)[1] != window["pid"]
            or not title_matches(win32gui.GetWindowText(hwnd), expected_title)):
        raise ValueError("WXS window identity/title changed; no further action")


def readonly(docs, native):
    states = [native.editor_status(frame, name, control)
              for frame, name, control in native.editors(docs)]
    if not states or any(s["edit_mode"] != 0 or s["is_modified"]
                         or s["page_count"] < 1 for s in states):
        raise ValueError("Expected loaded, unchanged read-only editors; no close")
    return states


def close_readonly(window, expected_title, native):
    identity(window, expected_title)
    docs, errors = native.documents(window)
    for _ in range(2):
        if not errors:
            break
        time.sleep(.3)
        identity(window, expected_title)
        docs, errors = native.documents(window)
    if errors:
        raise ValueError("Could not verify every frame; no close")
    readonly(docs, native)
    identity(window, expected_title)
    if not win32gui.IsWindowEnabled(window["hwnd"]):
        raise ValueError("WXS is blocked by a dialog; no close")
    win32gui.PostMessage(window["hwnd"], 0x0010, 0, 0)  # WM_CLOSE, no dialog acceptance
    deadline = time.monotonic() + 5
    while win32gui.IsWindow(window["hwnd"]) and time.monotonic() < deadline:
        time.sleep(.1)
    if win32gui.IsWindow(window["hwnd"]):
        raise ValueError("WXS did not close; inspect it manually. No prompt accepted")
    return {"window": window, "closed": True}


def safe_attachment_names(manifest):
    names = []
    for entry in manifest:
        name = entry["name"]
        if (not name or name in (".", "..") or re.search(r'[\\/:*?"<>|\x00-\x1f]', name)
                or name.endswith((".", " "))
                or name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(1, 10)}, *{f"LPT{i}" for i in range(1, 10)}}):
            raise ValueError("Unsafe attachment filename; export stopped")
        if name.casefold() in names:
            raise ValueError("Duplicate attachment filename; export stopped")
        names.append(name.casefold())


def export_attachments(window, expected_title, directory, native):
    from wxs_runtime import Session
    identity(window, expected_title)
    session = Session(window)
    if session.frame_errors:
        raise ValueError("Some document frames are unavailable")
    before = readonly(session.docs, native)
    manifest = session.action("attachment_manifest")
    safe_attachment_names(manifest)
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    identity(window, expected_title)
    result = session.action("attachment_export", {"directory": str(directory), "expected": manifest})
    files = []
    if len(result["saved"]) != len(manifest):
        raise ValueError("App did not report every attachment saved")
    for entry, saved in zip(manifest, result["saved"]):
        path = Path(saved).resolve()
        if path.parent != directory or path.name != entry["name"]:
            raise ValueError("App returned an unexpected attachment destination")
        if not path.is_file() or path.stat().st_size == 0:
            files.append({"name": entry["name"], "path": str(path), "listed_size": entry["size"],
                          "exported": False, "error": "App save handler did not produce a nonempty file"})
            continue
        size = path.stat().st_size
        files.append({"name": path.name, "path": str(path), "size": size, "exported": True,
                      "listed_size": entry["size"], "size_matches": not entry["size"] or size == entry["size"],
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if readonly(session.docs, native) != before:
        raise ValueError("Editor state changed during attachment export")
    return {"files": files, "all_exported": all(f["exported"] for f in files),
            "coverage": "App Attach.saveFilesAs attempted for every attachment; file contents still require readers"}


def read_next(args, native):
    if not 5 <= args.timeout <= 300:
        raise ValueError("timeout must be between 5 and 300 seconds")
    # Hidden windows are also excluded: existing user documents are never claimed.
    existing = native.windows(include_hidden=True)
    baseline = {w["hwnd"] for w in existing}
    if getattr(args, "command", None) == "read-open":
        selected = [w for w in existing if w["hwnd"] == args.hwnd and title_matches(w["title"], args.expected_title)]
        if len(selected) != 1:
            raise ValueError("Explicit existing HWND/title does not match")
        baseline.remove(args.hwnd)
    print(json.dumps({"ready": True, "existing_windows": len(existing)}), flush=True)
    deadline = time.monotonic() + args.timeout
    window, hidden, last_error = None, False, "No matching new window"
    try:
        while time.monotonic() < deadline:
            cancel_file = getattr(args, "cancel_file", None)
            if cancel_file and cancel_file.exists():
                result = {"status": "cancelled", "expected_title": args.expected_title,
                          "closed": False, "preserved": True,
                          "body": {"text": "", "body_read": False},
                          "attachments": {"files": [], "all_exported": False}}
                with args.out.open("x", encoding="utf-8") as target:
                    json.dump(result, target, ensure_ascii=False, indent=2)
                return {"status": "cancelled", "output": str(args.out.resolve()),
                        "closed": False, "preserved": True}
            current = native.windows(include_hidden=True)
            selected_pids = {w["pid"] for w in current if w["hwnd"] not in baseline
                             and title_matches(w["title"], args.expected_title)}
            authentication = [w for w in current if ((w["hwnd"] not in baseline
                              and w["pid"] not in {old["pid"] for old in existing})
                                   or w["pid"] in selected_pids)
                              and w["title"] == "인증서 로그인 -- 웹 페이지 대화 상자"]
            if authentication:
                # A security-document challenge is not proof of an expired portal session.
                # Preserve it for the user; never enter a password, dismiss it, or close it.
                result = {"status": "authentication_required", "expected_title": args.expected_title,
                          "authentication_windows": authentication, "closed": False, "preserved": True,
                          "body": {"text": "", "body_read": False, "source": "certificate_required"},
                          "attachments": {"files": [], "all_exported": False},
                          "instruction": "Notify the user that additional certificate authentication is required; preserve the window and continue other documents"}
                with args.out.open("x", encoding="utf-8") as target:
                    json.dump(result, target, ensure_ascii=False, indent=2)
                return {"status": "authentication_required", "output": str(args.out.resolve()),
                        "closed": False, "preserved": True}
            candidates = [w for w in current
                          if w["hwnd"] not in baseline
                          and title_matches(w["title"], args.expected_title)]
            if len(candidates) > 1:
                raise ValueError("Multiple new windows match; select none")
            if candidates:
                if window and window["hwnd"] != candidates[0]["hwnd"]:
                    raise ValueError("The selected new window disappeared; no replacement selected")
                window = candidates[0]
                identity(window, args.expected_title)
                if args.background and not hidden:
                    win32gui.ShowWindow(window["hwnd"], 0)  # SW_HIDE
                    hidden = True
                try:
                    docs, errors = native.documents(window)
                    if errors:
                        raise ValueError("Some document frames are unavailable")
                    before = readonly(docs, native)
                    try:
                        body = native.text(docs, "editor1")
                    except ValueError:
                        from wxs_runtime import Session
                        if not Session(window).action("read_kind")["non_electronic"]:
                            raise
                        body = {"text": "", "characters": 0, "editor": before,
                                "editor_after": before, "source": "non_electronic_attachment", "body_read": False}
                    attachments = native.attachments(docs)
                    after = readonly(docs, native)
                    if before != after or body["editor"] != body["editor_after"]:
                        raise ValueError("Editor state changed during capture")
                    if not body["text"].strip() and body.get("source") != "non_electronic_attachment":
                        raise ValueError("Document body is not loaded")
                except Exception as error:
                    last_error = str(error)
                    time.sleep(.3)
                    continue
                identity(window, args.expected_title)
                result = {"window": window, "body": body,
                          "attachments": attachments, "frame_errors": errors,
                          "background": hidden, "closed": False}
                # Save the body before an attachment handler can fail or block.
                with args.out.open("x", encoding="utf-8") as target:
                    json.dump(result, target, ensure_ascii=False, indent=2)
                if getattr(args, "attachments_dir", None):
                    try:
                        result["attachments"] = export_attachments(window, args.expected_title, args.attachments_dir, native)
                    except Exception as error:
                        result["attachment_export_error"] = str(error)
                        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                        raise
                    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                close_readonly(window, args.expected_title, native)
                result["closed"] = True
                args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"output": str(args.out.resolve()), "characters": body["characters"],
                        "closed": True, "background": hidden}
            time.sleep(.2)
        raise ValueError("Timed out waiting for a loaded matching document: " + last_error)
    finally:
        # A failed capture must not strand a hidden window. Never force focus.
        if hidden and window and win32gui.IsWindow(window["hwnd"]):
            try:
                if win32process.GetWindowThreadProcessId(window["hwnd"])[1] == window["pid"]:
                    win32gui.ShowWindow(window["hwnd"], 4)  # SW_SHOWNOACTIVATE
            except Exception:
                pass
