"""WXS (공문서 에디터) CLI: read open documents and prepare standard drafts without Computer Use."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

from wxs_config import PACK_ID, VERSION, load_config, plan, string


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--version", action="version", version=VERSION)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Report prerequisites without opening/logging in to applications")
    windows = commands.add_parser("windows", help="List open WXS windows")
    windows.add_argument("--include-hidden", action="store_true", help="Include windows hidden for background reading")
    for name in ("read-next", "read-open"):
        read = commands.add_parser(name, help="Read and close one read-only document (new window, or explicit existing HWND)")
        read.add_argument("--expected-title", required=True)
        read.add_argument("--out", type=Path, required=True, help="New JSON body/attachment result file")
        read.add_argument("--timeout", type=int, default=90)
        read.add_argument("--background", action="store_true", help="Hide the matched window while reading; initial activation can still occur")
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
        window = native.select_window(args)
        if args.command == "capture":
            from wxs_document import capture_pages
            from wxs_runtime import Session
            return capture_pages(Session(window), args.expected_title, args.directory, args.dpi)
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
