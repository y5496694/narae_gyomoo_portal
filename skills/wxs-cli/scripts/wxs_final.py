"""Explicit, document-bound final actions through observed native WXS controls.

A click is NOT proof of server completion. Receipts are exclusive, durable and
never authorize retrying a submission whose outcome is unknown.
"""
import hashlib
import json
from pathlib import Path

LABELS = {"submit": ("상신", "결재올림"), "approve": ("결재", "결재승인", "승인")}
INTERNAL_CONFIRM = "수신자를 지정하지 않으면 내부결재로 처리됩니다. 계속하시겠습니까?"
COMPLETION_NOTICE = "정상적으로 처리되었습니다.\n결재완료후 결재완료한 문서가 그대로 보이는 경우, 목록 새로고침을 하시기 바랍니다."
ROUTE_REVIEW = "결재경로를 확인해 주시기 바랍니다."


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
    result = {"present": bool(candidates), "message": message, "completed": False,
              "verification_required": True, "untrusted": True}
    if message == ROUTE_REVIEW and receipt["operation"] == "submit":
        result["route_review"] = native_runtime.Session(receipt["window"]).action("route_review_status")
    if message == INTERNAL_CONFIRM and receipt["operation"] == "submit":
        session = native_runtime.Session(receipt["window"])
        labels = [b["label"] for b in session.action("final_buttons") if b["label"] in LABELS["submit"] and not b["disabled"]]
        if len(labels) == 1:
            result["document_preview"] = prepare(session, "submit", receipt["expected_title"], labels[0])
    return result


def processing_preview(receipt_path, native_runtime, audit=False):
    from urllib.parse import urlsplit
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if receipt.get("status") != "verification_required" or receipt["operation"] != "submit" or (receipt.get("processing_attempted") and not receipt.get("processing_rejected_before_click") and not audit):
        raise ValueError("Receipt does not permit a document-processing confirmation")
    session = native_runtime.Session(receipt["window"])
    session.check_window()
    status = session.status()
    if session.frame_errors or status.get("title") != receipt["expected_title"] or status.get("app_type") != "sancgian" or status.get("processed") is not False:
        raise ValueError("Original draft identity or processing state changed")
    windows = [w for w in native_runtime.process_windows(receipt["window"]["pid"]) if "문서처리" in w["title"]]
    if len(windows) != 1:
        raise ValueError("Expected one observed document-processing dialog")
    docs, errors = native_runtime.native.documents(windows[0])
    root = docs[0][1]
    origin = urlsplit(str(root.url))
    if errors or origin.netloc != session.origin_path.netloc or not origin.path.endswith("/retrieveDocSanctn.do"):
        raise ValueError("Document-processing dialog origin or route changed")
    state = session.action("processing_status", root=root)
    binding = {"document": status, "window": windows[0], "origin": origin.geturl(), "form": state, "original_attempt": receipt["fingerprint"]}
    return {"applied": False, "completed": False, "fingerprint": fingerprint(binding), "binding": binding}


def audit_processing_rejection(receipt_path, native_runtime):
    """Prove the legacy array-serialization guard rejected this unchanged form.

    This narrowly migrates an old receipt without erasing either attempt lock.
    Unknown click outcomes and different documents remain nonretryable.
    """
    path = Path(receipt_path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not receipt.get("processing_attempted") or receipt.get("processing_rejection_audited") or receipt.get("processing_gate_version", 1) != 1:
        raise ValueError("No unaudited legacy processing attempt")
    preview = processing_preview(path, native_runtime, audit=True)
    if preview["fingerprint"] != receipt.get("processing_fingerprint"):
        raise ValueError("Processing form differs from the recorded attempt; outcome stays unknown")
    docs, errors = native_runtime.native.documents(preview["binding"]["window"])
    if errors:
        raise ValueError("Processing frames could not be inspected")
    proof = native_runtime.Session(receipt["window"]).action("processing_preflight", {"expected": preview["binding"]["form"]}, root=docs[0][1])
    if proof != {"exact_state": True, "legacy_gate_passed": False}:
        raise ValueError("The legacy guard does not prove rejection before click")
    with path.with_suffix(path.suffix + ".processing-rejection-audited").open("x", encoding="utf-8") as stream:
        json.dump({"fingerprint": preview["fingerprint"], "proof": proof}, stream)
    receipt.update(processing_rejection_audited=True, processing_rejected_before_click=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(receipt, completed=False, evidence="Unchanged form and deterministic legacy serialization guard prove no click was dispatched")


def process(receipt_path, preview, expected_fingerprint, authorized, native_runtime):
    if authorized is not True or preview["fingerprint"] != expected_fingerprint:
        raise ValueError("Processing confirmation requires authorization and the reviewed fingerprint")
    fresh = processing_preview(receipt_path, native_runtime)
    if fresh["fingerprint"] != expected_fingerprint:
        raise ValueError("Document or processing options changed after preview")
    path = Path(receipt_path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    suffix = ".processing-confirmed-after-rejection" if receipt.get("processing_rejected_before_click") else ".processing-confirmed"
    with path.with_suffix(path.suffix + suffix).open("x", encoding="utf-8") as stream:
        stream.write(expected_fingerprint)
    receipt["processing_attempted"] = True
    receipt["processing_gate_version"] = 2
    receipt["processing_rejected_before_click"] = False
    receipt["processing_fingerprint"] = expected_fingerprint
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    docs, errors = native_runtime.native.documents(fresh["binding"]["window"])
    if errors:
        raise ValueError("Processing frames changed; attempt retained without retry")
    native_runtime.Session(receipt["window"]).action("processing_click", {"expected": fresh["binding"]["form"]}, root=docs[0][1])
    return dict(receipt, completed=False, evidence="Observed processing confirmation clicked once; verify server document status")


def confirm(receipt_path, expected_message, authorized, native_runtime, expected_fingerprint=None):
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
    if message == ROUTE_REVIEW and receipt["operation"] == "submit":
        session = native_runtime.Session(receipt["window"])
        state, proof = session.status(), session.action("route_review_status")
        if state.get("title") != receipt["expected_title"] or state.get("processed") is not False or session.frame_errors or proof != {"reviewed": False, "message": ROUTE_REVIEW, "guard": True, "processing_gate": True}:
            raise ValueError("Route validation does not prove rejection before document processing")
        with path.with_suffix(path.suffix + ".route-review-requested").open("x", encoding="utf-8") as stream:
            json.dump({"document": state, "proof": proof}, stream, ensure_ascii=False)
        receipt.update(status="route_review_required", route_validation_document=state, route_validation_proof=proof)
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        native_runtime.press_dialog_button(window, children, "확인")
        return dict(receipt, completed=False, evidence="Native validation returned before processing; confirm the existing route before final-resume")
    if message == INTERNAL_CONFIRM and receipt["operation"] == "submit":
        if receipt.get("internal_confirmation_attempted"):
            raise ValueError("Internal approval confirmation already attempted")
        # Re-observe the original document, including route and recipient, while
        # its native modal is open. The receipt's window identity stays fixed.
        session = native_runtime.Session(receipt["window"])
        status = session.status()
        if status.get("recipient") != "내부결재":
            raise ValueError("Internal approval confirmation requires the observed internal recipient")
        buttons = session.action("final_buttons")
        labels = [b["label"] for b in buttons if b["label"] in LABELS["submit"] and not b["disabled"]]
        reviewed_fingerprint = expected_fingerprint or receipt["fingerprint"]
        if len(labels) != 1 or prepare(session, "submit", receipt["expected_title"], labels[0])["fingerprint"] != reviewed_fingerprint:
            raise ValueError("Document changed before internal approval confirmation")
        with path.with_suffix(path.suffix + ".internal-confirmed").open("x", encoding="utf-8") as stream:
            stream.write(receipt["fingerprint"])
        receipt["internal_confirmation_attempted"] = True
        receipt["internal_confirmation_fingerprint"] = reviewed_fingerprint
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        native_runtime.press_dialog_button(window, children, "확인")
        return dict(receipt, completed=False, evidence="Exact internal approval prompt accepted; inspect the next dialog and server status")
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


def resume_route_review(receipt_path, expected_fingerprint, authorized, native_runtime, apply=False):
    path = Path(receipt_path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("status") != "route_review_required" or receipt.get("operation") != "submit" or any(receipt.get(k) for k in ("confirmation_attempted", "processing_attempted", "internal_confirmation_attempted")):
        raise ValueError("Only a proven route-validation rejection may resume")
    session = native_runtime.Session(receipt["window"])
    proof = session.action("route_review_status")
    if proof != {"reviewed": True, "message": ROUTE_REVIEW, "guard": True, "processing_gate": True}:
        raise ValueError("Existing approval route has not been confirmed")
    labels = [b["label"] for b in session.action("final_buttons") if b["label"] in LABELS["submit"] and not b["disabled"]]
    if len(labels) != 1:
        raise ValueError("Expected one observed submit control")
    preview = prepare(session, "submit", receipt["expected_title"], labels[0])
    old, current = receipt["route_validation_document"], preview["binding"]["document"]
    if any(value != current.get(key) for key, value in old.items() if key not in {"approval_rows", "is_modified", "document_text"}):
        raise ValueError("Document changed outside the approval-route confirmation")
    if old["document_text"] != current["document_text"]:
        from wxs_document import normalize_export_text
        drafter = session.action("route_review_drafter")
        before_text, after_text = normalize_export_text(old["document_text"]), normalize_export_text(current["document_text"])
        marker = "\n" + drafter + "\n"
        if before_text.count(marker) != 1 or before_text.replace(marker, "\n\n", 1) != after_text or native_runtime.native.call(session.editor(), "GetFieldText", "서명.1") != "":
            raise ValueError("Document changed outside the native drafter-signature reset")
    if not apply:
        return preview
    if authorized is not True or expected_fingerprint != preview["fingerprint"]:
        raise ValueError("Resume requires explicit authorization and a reviewed fingerprint")
    with path.with_suffix(path.suffix + ".route-review-resumed").open("x", encoding="utf-8") as stream:
        stream.write(expected_fingerprint)
    receipt.update(status="verification_required", route_review_original_fingerprint=receipt["fingerprint"], fingerprint=expected_fingerprint, route_review_resumed=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    session.action("final_click", {"button": preview["binding"]["button"], "expected_title": receipt["expected_title"], "operation": "submit"})
    return dict(receipt, completed=False, evidence="Resumed once after the original route-validation rejection; verify subsequent dialogs")


def acknowledge(receipt_path, expected_message, native_runtime):
    """Dismiss only the observed completion notice, never a decision prompt."""
    path = Path(receipt_path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("status") != "verification_required" or not receipt.get("processing_attempted") or receipt.get("completion_notice_acknowledged"):
        raise ValueError("Receipt does not permit a completion-notice acknowledgment")
    if expected_message != COMPLETION_NOTICE:
        raise ValueError("Only the exact supported completion notice can be acknowledged")
    windows = [w for w in native_runtime.process_windows(receipt["window"]["pid"]) if w["title"] == "웹 페이지 메시지"]
    if len(windows) != 1:
        raise ValueError("Expected one completion notice")
    message, children = native_runtime.alert_details(windows[0])
    if message != expected_message:
        raise ValueError("Completion notice changed")
    with path.with_suffix(path.suffix + ".notice-acknowledged").open("x", encoding="utf-8") as stream:
        stream.write(receipt["fingerprint"])
    receipt["completion_notice_acknowledged"] = True
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    native_runtime.press_dialog_button(windows[0], children, "확인")
    return dict(receipt, completed=False, evidence="Completion notice dismissed; server-list verification is still required")


def acknowledge_failure(receipt_path, expected_message, native_runtime):
    """Dismiss one observed failure notice; never unlock or retry the attempt."""
    path = Path(receipt_path)
    receipt = json.loads(path.read_text(encoding='utf-8'))
    if (receipt.get('status') != 'verification_required' or not receipt.get('processing_attempted') or
            receipt.get('failure_notice_acknowledged') or expected_message != '에러가 발생했습니다.'):
        raise ValueError('Receipt does not permit this exact failure-notice acknowledgement')
    session = native_runtime.Session(receipt['window'])
    session.check_window()
    state = session.status()
    if state.get('title') != receipt['expected_title'] or state.get('processed') is not False:
        raise ValueError('Original draft identity or processing state changed')
    windows = [w for w in native_runtime.process_windows(receipt['window']['pid']) if w['title'] == '웹 페이지 메시지']
    if len(windows) != 1:
        raise ValueError('Expected one native failure notice')
    message, children = native_runtime.alert_details(windows[0])
    if message != expected_message or [c.get('text', '').replace('&', '').strip() for c in children if c.get('class') == 'Button'] != ['확인']:
        raise ValueError('Failure notice changed or includes a decision')
    with path.with_suffix(path.suffix + '.failure-acknowledged').open('x', encoding='utf-8') as stream:
        stream.write(receipt['fingerprint'])
    receipt['failure_notice_acknowledged'] = True
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    native_runtime.press_dialog_button(windows[0], children, '확인')
    return dict(receipt, completed=False, retry_allowed=False,
                evidence='Failure notice dismissed; original attempt lock preserved; verify actual server state before recovery')
