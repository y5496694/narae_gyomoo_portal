"""WXS (공문서 에디터) CLI: read open documents and prepare standard drafts without Computer Use."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

from wxs_config import VERSION, load_config, plan, string


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--version", action="version", version=VERSION)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Report prerequisites without opening/logging in to applications")
    commands.add_parser("windows", help="List open WXS windows")
    for name in ("inspect", "text", "attachments", "draft-status", "draft", "save-draft"):
        command = commands.add_parser(name)
        command.add_argument("--hwnd", type=lambda value: int(value, 0),
                             help="Actual HWND from windows, required for applying changes")
        command.add_argument("--out", type=Path, help="New UTF-8 result file; existing files preserved")
        if name == "text":
            command.add_argument("--editor", default="editor1")
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
    if args.command == "doctor":
        return {"version": VERSION, "windows": os.name == "nt", "python": platform.python_version(),
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
            return {"windows": native.windows()}
        window = native.select_window(args)
        if args.command in ("draft-status", "draft", "save-draft"):
            from wxs_runtime import Session
            session = Session(window)
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
        if getattr(args, "out", None):
            content = result.pop("text") if args.command == "text" else json.dumps(result, ensure_ascii=False, indent=2)
            with args.out.open("x", encoding="utf-8", newline="") as target:
                target.write(content)
            result["output"] = str(args.out.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        details = getattr(error, "details", {"error": str(error)})
        print(json.dumps(details, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
