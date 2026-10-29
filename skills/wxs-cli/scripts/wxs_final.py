"""Explicit, document-bound final actions through observed native WXS controls.

A click is NOT proof of server completion. Receipts are exclusive, durable and
never authorize retrying a submission whose outcome is unknown.
"""
import hashlib
import json
from pathlib import Path

LABELS = {"submit": ("상신", "결재올림"), "approve": ("결재", "결재승인", "승인")}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def prepare(session, operation, expected_title, button_label):
    if operation not in LABELS or button_label.replace(" ", "") not in LABELS[operation]:
        raise ValueError("Choose an observed submit/approve button for this operation")
    session.check_window()
    if session.frame_errors:
        raise ValueError("Frames could not be inspected; final action stopped")
    status = session.status()
    title = status.get("title") or status.get("hwp_title")
    if not expected_title.strip() or title != expected_title:
        raise ValueError("Current title differs from expected_title")
    if status.get("processed") is not False:
        raise ValueError("Document is processed or its processing state is unknown")
    if operation == "submit" and status.get("app_type") != "sancgian":
        raise ValueError("Submit requires an unprocessed sancgian draft")
    if operation == "approve" and status.get("app_type") != "sanckyul":
        raise ValueError("Approve requires the observed sanckyul approval form")
    if not str(status.get("document_text", "")).strip():
        raise ValueError("Read the document body before a final action")
    buttons = session.action("final_buttons")
    matches = [b for b in buttons if b["label"] == button_label and not b["disabled"]]
    if len(matches) != 1:
        raise ValueError("Expected one visible enabled final button with the exact label")
    binding = {"operation": operation, "expected_title": expected_title,
               "window": session.window, "origin": session.origin_path.geturl(),
               "document": status, "button": matches[0]}
    return {"applied": False, "status": "prepared", "fingerprint": fingerprint(binding),
            "binding": binding, "requires_explicit_authorization": True,
            "completed": False}


def apply(session, plan, expected_fingerprint, receipt_path, authorized):
    if authorized is not True:
        raise ValueError("Final action requires --confirm-final-action and explicit user authorization")
    if expected_fingerprint != plan["fingerprint"]:
        raise ValueError("Document, approval line, attachments or button changed; review a new preview")
    receipt_path = Path(receipt_path)
    receipt = {"status": "attempting", "completed": False, "retry_allowed": False,
               "fingerprint": plan["fingerprint"], "operation": plan["binding"]["operation"],
               "expected_title": plan["binding"]["expected_title"], "window": session.window}
    # Exclusive creation + flush/fsync precede the application's click.
    import os
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    # A persistent per-document attempt lock also blocks a fresh receipt name.
    directory = receipt_path.parent / ".wxs-final-attempts"
    directory.mkdir(exist_ok=True)
    identity = fingerprint({"window": session.window, "origin": session.origin_path.geturl(),
                            "title": receipt["expected_title"], "operation": receipt["operation"]})
    with (directory / (identity + ".json")).open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    session.action("final_click", {"button": plan["binding"]["button"],
                                  "expected_title": plan["binding"]["expected_title"],
                                  "operation": receipt["operation"]})
    receipt["status"] = "verification_required"
    receipt["receipt"] = str(receipt_path.resolve())
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt


def inspect_dialog(receipt_path, native_runtime):
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if receipt.get("status") != "verification_required":
        raise ValueError("Only the attempted final action's receipt may inspect its confirmation")
    candidates = [w for w in native_runtime.process_windows(receipt["window"]["pid"])
                  if w["title"] == "웹 페이지 메시지"]
    if len(candidates) > 1:
        raise ValueError("Multiple site messages; stop and inspect the application")
    message = native_runtime.alert_details(candidates[0])[0] if candidates else None
    return {"present": bool(candidates), "message": message, "completed": False,
            "verification_required": True, "untrusted": True}


def confirm(receipt_path, expected_message, authorized, native_runtime):
    if authorized is not True or not expected_message.strip():
        raise ValueError("Exact observed message and --confirm-final-action are required")
    path = Path(receipt_path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("status") != "verification_required" or receipt.get("confirmation_attempted"):
        raise ValueError("Receipt does not permit another confirmation; inspect the current state")
    candidates = [w for w in native_runtime.process_windows(receipt["window"]["pid"])
                  if w["title"] == "웹 페이지 메시지"]
    if len(candidates) != 1:
        raise ValueError("Expected exactly one observed WXS site message")
    window = candidates[0]
    message, children = native_runtime.alert_details(window)
    if message != expected_message:
        raise ValueError("Site message changed; no confirmation applied")
    import re
    # Do not confirm signatures, deletion, rejection, sending or unrelated prompts.
    compact = re.sub(r"\s+", "", message)
    allowed = (r"(?:상신|결재올림)(?:을)?(?:하시겠습니까|하겠습니까)\??" if receipt["operation"] == "submit"
               else r"(?:결재|승인)(?:를|을)?(?:하시겠습니까|하겠습니까)\??")
    if not re.fullmatch(allowed, compact):
        raise ValueError("This message is not a supported operation-specific confirmation")
    receipt["confirmation_attempted"] = True
    # Claim atomically before pressing any native button.
    with path.with_suffix(path.suffix + ".confirmed").open("x", encoding="utf-8") as stream:
        stream.write(receipt["fingerprint"])
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    native_runtime.press_dialog_button(window, children, "확인")
    return dict(receipt, completed=False, status="verification_required",
                evidence="Exact native confirmation accepted; verify server document status separately")
