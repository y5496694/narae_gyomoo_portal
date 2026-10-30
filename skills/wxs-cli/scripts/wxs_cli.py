"""WXS (공문서 에디터) CLI: read open documents and prepare standard drafts without Computer Use."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

from wxs_config import PACK_ID, VERSION, load_config, plan, string, approval_route_matches


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--version", action="version", version=VERSION)
    commands = root.add_subparsers(dest="command", required=True)
    resume = commands.add_parser("final-resume", help="Resume the same receipt once after a proven native route-review rejection")
    resume.add_argument("--receipt", type=Path, required=True)
    resume.add_argument("--expected-fingerprint")
    resume.add_argument("--apply", action="store_true")
    resume.add_argument("--confirm-final-action", action="store_true")
    resume.add_argument("--out", type=Path)
    commands.add_parser("doctor", help="Report prerequisites without opening/logging in to applications")
    windows = commands.add_parser("windows", help="List open WXS windows")
    windows.add_argument("--include-hidden", action="store_true", help="Include windows hidden for background reading")
    for name in ("read-next", "read-open"):
        read = commands.add_parser(name, help="Read and close one read-only document (new window, or explicit existing HWND)")
        read.add_argument("--expected-title", required=True)
        read.add_argument("--out", type=Path, required=True, help="New JSON body/attachment result file")
        read.add_argument("--timeout", type=int, default=90)
        read.add_argument("--background", action="store_true", help="Hide the matched window while reading; initial activation can still occur")
        read.add_argument("--cancel-file", type=Path, help="Stop waiting when this local marker exists; preserve the current document")
        read.add_argument("--attachments-dir", type=Path, help="New directory for every attachment, exported through the current app handler")
        if name == "read-open":
            read.add_argument("--hwnd", type=lambda value: int(value, 0), required=True)
    close = commands.add_parser("close-readonly", help="Close one unchanged read-only WXS window")
    close.add_argument("--hwnd", type=lambda value: int(value, 0), required=True)
    close.add_argument("--expected-title", required=True)
    capture = commands.add_parser("capture", help="Render actual draft body pages without changing the document")
    capture.add_argument("--hwnd", type=lambda value: int(value, 0), required=True)
    capture.add_argument("--expected-title", required=True)
    capture.add_argument("--directory", type=Path, required=True)
    capture.add_argument("--dpi", type=int, default=150)
    capture.add_argument("--out", type=Path)
    export = commands.add_parser("export-document", help="Export a verified HWP comparison copy without changing the open document")
    export.add_argument("--hwnd", type=lambda value: int(value, 0), required=True)
    export.add_argument("--expected-title", required=True)
    export.add_argument("--path", type=Path, required=True)
    export.add_argument("--out", type=Path)
    export.add_argument("--restore-readonly-from", type=Path, help="Recover only export flags after matching the earlier full TEXT extraction")
    replace = commands.add_parser("replace-document", help="Preview or apply a Narae-edited full draft copy while preserving standard fields and metadata")
    replace.add_argument("--hwnd", type=lambda value: int(value, 0), required=True)
    replace.add_argument("--expected-title", required=True)
    replace.add_argument("--source", type=Path, required=True)
    replace.add_argument("--expected-text-file", type=Path, required=True)
    replace.add_argument("--expected-fingerprint")
    replace.add_argument("--apply", action="store_true")
    replace.add_argument("--out", type=Path)
    options = commands.add_parser("draft-options", help="Observe draft disclosure controls or open the approval selector without selecting people")
    options.add_argument("--hwnd", type=lambda value: int(value, 0), required=True)
    options.add_argument("--expected-title", required=True)
    options.add_argument("--section", choices=("approval", "disclosure", "task"), required=True)
    options.add_argument("--dialog-hwnd", type=lambda value: int(value, 0), help="Observe the already open approval dialog from a previous result")
    options.add_argument("--close", action="store_true", help="Close only the observed unchanged drafter-only approval selector")
    options.add_argument("--task-card", help="Select this exact candidate in the observed open task dialog, with --apply")
    options.add_argument("--confirm-route", type=Path, help="Confirm only an already selected route matching this draft config; never add people")
    options.add_argument("--apply", action="store_true")
    options.add_argument("--out", type=Path)
    for name in ("inspect", "text", "attachments", "attachment-status", "export-attachments", "draft-status", "draft", "save-draft"):
        command = commands.add_parser(name)
        command.add_argument("--hwnd", type=lambda value: int(value, 0),
                             help="Actual HWND from windows, required for applying changes")
        command.add_argument("--out", type=Path, help="New UTF-8 result file; existing files preserved")
        if name == "text":
            command.add_argument("--editor", default="editor1")
        if name == "export-attachments":
            command.add_argument("--directory", type=Path, required=True)
            command.add_argument("--expected-title", required=True)
        if name == "draft":
            command.add_argument("--config", type=Path, required=True)
        if name == "save-draft":
            command.add_argument("--name", required=True)
            command.add_argument("--expected-title", required=True)
        if name in ("draft", "save-draft"):
            command.add_argument("--apply", action="store_true", help="Apply the requested draft operations")
            command.add_argument("--replace-existing", action="store_true", help="Permit replacing this exact temporary-draft name")
    final = commands.add_parser("final-action", help="Preview or explicitly apply one observed submit/approve button")
    final.add_argument("--hwnd", type=lambda value: int(value, 0), required=True)
    final.add_argument("--operation", choices=("submit", "approve"), required=True)
    final.add_argument("--expected-title", required=True)
    final.add_argument("--button-label", required=True)
    final.add_argument("--apply", action="store_true")
    final.add_argument("--confirm-final-action", action="store_true")
    final.add_argument("--expected-fingerprint")
    final.add_argument("--receipt", type=Path)
    final.add_argument("--out", type=Path)
    dialog = commands.add_parser("final-dialog", help="Read the attempted final action's actual native message without accepting it")
    dialog.add_argument("--receipt", type=Path, required=True)
    dialog.add_argument("--out", type=Path)
    confirm = commands.add_parser("final-confirm", help="Accept one exact observed operation-specific native confirmation")
    confirm.add_argument("--receipt", type=Path, required=True)
    confirm.add_argument("--expected-message", required=True)
    confirm.add_argument("--expected-fingerprint", help="The reviewed final-dialog document preview after the site's draft preparation")
    confirm.add_argument("--confirm-final-action", action="store_true")
    processing = commands.add_parser("final-process", help="Review or explicitly confirm the same attempted submission's observed document-processing form")
    processing.add_argument("--receipt", type=Path, required=True)
    processing.add_argument("--apply", action="store_true")
    processing.add_argument("--expected-fingerprint")
    processing.add_argument("--confirm-final-action", action="store_true")
    processing.add_argument("--out", type=Path)
    processing.add_argument("--audit-rejection", action="store_true", help="Prove only an unchanged legacy array guard rejected before click; preserve the original attempt lock")
    ack = commands.add_parser("final-ack", help="Dismiss only the exact observed completion notice, without making a decision")
    ack.add_argument("--receipt", type=Path, required=True)
    ack.add_argument("--expected-message", required=True)
    return root


def run(args):
    if getattr(args, "out", None) and args.out.exists():
        raise ValueError("Output already exists; no operations run")
    if getattr(args, "attachments_dir", None) and args.attachments_dir.exists():
        raise ValueError("Attachment destination already exists; no operations run")
    if args.command == "doctor":
        return {"pack": PACK_ID, "version": VERSION, "windows": os.name == "nt", "python": platform.python_version(),
                "python_bits": 64 if sys.maxsize > 2**32 else 32,
                "dependencies": {name: importlib.util.find_spec(name) is not None for name in ("pythoncom", "win32gui", "win32com")},
                "requires": "Installed WXS Client, logged-in session, and an open document on the same Windows desktop"}
    if args.command == "final-action" and args.apply:
        if not args.confirm_final_action or not args.expected_fingerprint or not args.receipt:
            raise ValueError("Applying a final action requires --confirm-final-action, --expected-fingerprint and --receipt")
    if args.command == "final-confirm" and not args.confirm_final_action:
        raise ValueError("Native final confirmation requires --confirm-final-action")
    if args.command == "final-process" and args.apply and (not args.confirm_final_action or not args.expected_fingerprint):
        raise ValueError("Processing confirmation requires --confirm-final-action and --expected-fingerprint")
    if args.command == "final-resume" and args.apply and (not args.confirm_final_action or not args.expected_fingerprint):
        raise ValueError("Route-review resume requires --confirm-final-action and --expected-fingerprint")
    if args.command == "final-process" and args.audit_rejection and args.apply:
        raise ValueError("Rejection audit cannot click or be combined with --apply")
    if args.command == "draft-options" and (args.task_card or args.confirm_route or args.apply):
        task_apply = args.section == "task" and args.task_card and not args.confirm_route
        route_apply = args.section == "approval" and args.confirm_route and not args.task_card
        if not (task_apply or route_apply) or not args.apply or not args.dialog_hwnd or args.close:
            raise ValueError("Selection requires the matching section, observed --dialog-hwnd, one task-card/confirm-route and --apply")
    config = load_config(args.config) if args.command == "draft" else None
    if args.command == "save-draft":
        string(args.name, "name")
        string(args.expected_title, "expected_title", empty=True)
    if args.command == "draft" and not args.apply:
        return plan(config)
    if args.command == "save-draft" and not args.apply:
        return {"applied": False, "name": args.name, "expected_title": args.expected_title,
                "replace_existing": args.replace_existing, "submission": "unsupported"}
    if args.command in ("draft", "save-draft") and args.hwnd is None:
        raise ValueError("Applying changes requires explicit --hwnd from windows")
    if os.name != "nt":
        raise ValueError("Live WXS operations require Windows")
    import pythoncom
    import wxs_native as native
    pythoncom.CoInitialize()
    try:
        if args.command == "windows":
            return {"windows": native.windows(include_hidden=args.include_hidden)}
        if args.command in ("read-next", "read-open", "close-readonly"):
            from wxs_read import read_next, close_readonly
            string(args.expected_title, "expected_title")
            if args.command in ("read-next", "read-open"):
                return read_next(args, native)
            window = native.select_window(args)
            return close_readonly(window, args.expected_title, native)
        if args.command == "final-dialog":
            import wxs_runtime
            from wxs_final import inspect_dialog
            return inspect_dialog(args.receipt, wxs_runtime)
        if args.command == "final-resume":
            import wxs_runtime
            from wxs_final import resume_route_review
            return resume_route_review(args.receipt, args.expected_fingerprint, args.confirm_final_action, wxs_runtime, args.apply)
        if args.command == "final-process":
            import wxs_runtime
            from wxs_final import processing_preview, process, audit_processing_rejection
            if args.audit_rejection:
                return audit_processing_rejection(args.receipt, wxs_runtime)
            preview = processing_preview(args.receipt, wxs_runtime)
            if not args.apply:
                return preview
            return process(args.receipt, preview, args.expected_fingerprint, args.confirm_final_action, wxs_runtime)
        if args.command == "final-ack":
            import wxs_runtime
            from wxs_final import acknowledge
            return acknowledge(args.receipt, args.expected_message, wxs_runtime)
        if args.command == "final-confirm":
            import wxs_runtime
            from wxs_final import confirm
            return confirm(args.receipt, args.expected_message, args.confirm_final_action, wxs_runtime, args.expected_fingerprint)
        window = native.select_window(args)
        if args.command == "draft-options":
            from wxs_runtime import Session
            session = Session(window)
            if args.dialog_hwnd:
                status = session.status()
                if args.section not in ("approval", "task") or status["title"] != args.expected_title or status["app_type"] != "sancgian" or status["processed"] is not False or status["edit_mode"] != 2 or session.frame_errors:
                    raise ValueError("Expected the same editable draft")
                from wxs_runtime import process_windows
                matches = [item for item in process_windows(window["pid"]) if item["hwnd"] == args.dialog_hwnd and (args.section == "task" or "결재경로" in item["title"])]
                if len(matches) != 1:
                    raise ValueError("Expected the observed approval dialog in the same process")
                docs, errors = native.documents(matches[0])
                root = docs[0][1]
                from urllib.parse import urlsplit
                parsed = urlsplit(str(root.url))
                kind = "open_task" if args.section == "task" else "open_approval"
                if errors or parsed.netloc != session.origin_path.netloc or (args.section == "task" and not parsed.path.endswith("taskChoiseTaskNexacroRP.do")) or not session.action("ready", {"kind": kind}, root):
                    raise ValueError("Approval dialog identity or controls changed")
                if args.section == "task":
                    if args.close:
                        raise ValueError("Closing task selectors is unsupported")
                    if args.apply:
                        session.action("task_select", {"name": args.task_card}, root)
                        session.wait_closed(matches[0])
                        after = session.status()
                        if args.task_card not in after["task_card"]:
                            raise ValueError("Task card readback mismatch")
                        return {"applied": True, "status": after}
                    return {"window": matches[0], "options": session.action("task_options", root=root)}
                if args.confirm_route:
                    config = load_config(args.confirm_route)
                    if set(config) - {"expected_title", "title", "approval_route", "attachments"} or config["attachments"] or "approval_route" not in config or config["expected_title"] != args.expected_title or config["title"] != args.expected_title:
                        raise ValueError("Route confirmation requires the same document and a route-only config")
                    if len(status["approval_rows"]) != 1 and not approval_route_matches(status["approval_rows"], config["approval_route"]):
                        raise ValueError("Existing approval route differs; no replacement or confirmation applied")
                    session.action("approval_route_confirm", {"route": config["approval_route"]}, root)
                    session.wait_closed(matches[0])
                    after = session.status()
                    rows = after["approval_rows"]
                    if not approval_route_matches(rows, config["approval_route"]):
                        raise ValueError("Approval route readback mismatch")
                    return {"applied": True, "status": after}
                if args.close:
                    session.action("approval_cancel", root=root)
                    session.wait_closed(matches[0])
                    return {"closed": True, "status": session.status()}
                return {"window": matches[0], "options": session.action("approval_options", root=root)}
            if args.close:
                raise ValueError("Closing requires the observed --dialog-hwnd")
            session.require_draft(args.expected_title)
            if args.section == "disclosure":
                return {"controls": session.action("disclosure_options")}
            if args.section == "task":
                modal, root = session.open_modal("open_task", path_suffix="taskChoiseTaskNexacroRP.do")
                return {"window": modal, "options": session.action("task_options", root=root)}
            modal, root = session.open_modal("open_approval", title_contains="결재경로")
            return {"window": modal, "options": session.action("approval_options", root=root)}
        if args.command == "final-action":
            from wxs_runtime import Session
            from wxs_final import prepare, apply
            session = Session(window)
            preview = prepare(session, args.operation, args.expected_title, args.button_label)
            if not args.apply:
                return preview
            return apply(session, preview, args.expected_fingerprint, args.receipt, args.confirm_final_action)
        if args.command == "capture":
            from wxs_document import capture_pages
            from wxs_runtime import Session
            return capture_pages(Session(window), args.expected_title, args.directory, args.dpi)
        if args.command == "export-document":
            from wxs_document import export_document
            from wxs_runtime import Session
            return export_document(Session(window), args.expected_title, args.path, args.restore_readonly_from)
        if args.command == "replace-document":
            from wxs_runtime import Session
            from wxs_document import replacement_preview, replace_document
            session = Session(window)
            preview = replacement_preview(session, args.expected_title, args.source, args.expected_text_file)
            return replace_document(session, preview, args.expected_fingerprint) if args.apply else preview
        if args.command == "export-attachments":
            from wxs_read import export_attachments
            return export_attachments(window, args.expected_title, args.directory, native)
        if args.command in ("attachment-status", "draft-status", "draft", "save-draft"):
            from wxs_runtime import Session
            session = Session(window)
            if args.command == "attachment-status":
                return {"files": session.action("attachment_manifest")}
            if args.command == "draft-status":
                return session.status()
            if args.command == "draft":
                return session.draft(config, args.replace_existing)
            session.require_draft(args.expected_title)
            return session.save(args.name, args.replace_existing)
        docs, errors = native.documents(window)
        if args.command == "inspect":
            result = native.inspect(docs)
        elif args.command == "attachments":
            result = native.attachments(docs)
        else:
            result = native.text(docs, args.editor)
            if result["editor"] != result["editor_after"]:
                raise ValueError("Editor state changed during text extraction; inspect before continuing")
        result.update({"window": window, "frame_errors": errors})
        return result
    finally:
        pythoncom.CoUninitialize()


def main():
    args = parser().parse_args()
    try:
        result = run(args)
        if getattr(args, "out", None) and args.command not in ("read-next", "read-open"):
            content = result.pop("text") if args.command == "text" else json.dumps(result, ensure_ascii=False, indent=2)
            with args.out.open("x", encoding="utf-8", newline="") as target:
                target.write(content)
            result["output"] = str(args.out.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") == "authentication_required" else 0
    except Exception as error:
        details = getattr(error, "details", {"error": str(error)})
        print(json.dumps(details, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
