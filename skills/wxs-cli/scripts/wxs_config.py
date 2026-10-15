"""Offline validation and plans. Does not import Windows/COM modules."""
import json
from pathlib import Path

VERSION = "0.2.0"
FIELDS = {"expected_title", "title", "body", "body_file", "task_card",
          "private_reasons", "approver", "recipient", "auto_send", "attachments",
          "save_name"}


def exact_object(value, allowed, required, label):
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    unknown = set(value) - set(allowed)
    missing = set(required) - set(value)
    if unknown or missing:
        raise ValueError(f"{label}: unknown={sorted(unknown)}, missing={sorted(missing)}")


def string(value, label, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or "\x00" in value:
        raise ValueError(label + " must be a nonempty string without NUL")
    return value


def no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate JSON key: " + key)
        out[key] = value
    return out


def load_config(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=no_duplicates)
    exact_object(data, FIELDS, {"expected_title", "title"}, "config")
    string(data["expected_title"], "expected_title", empty=True)
    string(data["title"], "title")
    if "body" in data and "body_file" in data:
        raise ValueError("Use either body or body_file")
    if "body_file" in data:
        source = path.parent / string(data.pop("body_file"), "body_file")
        data["body"] = source.read_text(encoding="utf-8-sig")
    if "body" in data:
        string(data["body"], "body", empty=True)
        data["body"] = data["body"].replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    for key in ("task_card", "save_name"):
        if key in data:
            string(data[key], key)
    if "private_reasons" in data:
        reasons = data["private_reasons"]
        if (not isinstance(reasons, list) or not reasons or
                any(type(n) is not int or n not in range(1, 9) for n in reasons) or
                len(reasons) != len(set(reasons))):
            raise ValueError("private_reasons must contain unique integers 1..8")
        data["private_reasons"] = sorted(reasons)
    if "approver" in data:
        exact_object(data["approver"], {"name", "id"}, {"name"}, "approver")
        for key, value in data["approver"].items():
            string(value, "approver." + key)
    if "recipient" in data:
        exact_object(data["recipient"], {"search", "name"}, {"search", "name"}, "recipient")
        for key, value in data["recipient"].items():
            string(value, "recipient." + key)
    if "auto_send" in data and data["auto_send"] is not True:
        raise ValueError("This version supports auto_send: true only; omit to preserve")
    attachments = data.get("attachments", [])
    if not isinstance(attachments, list):
        raise ValueError("attachments must be a list of local file paths")
    resolved, seen = [], set()
    for value in attachments:
        target = (path.parent / string(value, "attachment path")).resolve(strict=True)
        if not target.is_file() or target.stat().st_size == 0:
            raise ValueError("Attachment must be a nonempty file: " + str(target))
        key = str(target).casefold()
        if key in seen:
            raise ValueError("Duplicate attachment path: " + str(target))
        seen.add(key)
        resolved.append({"path": str(target), "name": target.name, "size": target.stat().st_size})
    data["attachments"] = resolved
    return data


def plan(config):
    steps = ["title"]
    for key in ("body", "private_reasons", "task_card", "approver", "recipient", "auto_send"):
        if key in config:
            steps.append(key)
    if config["attachments"]:
        steps.append("attachments")
    if "save_name" in config:
        steps.append("save_draft")
    return {"version": VERSION, "applied": False, "expected_title": config["expected_title"],
            "title": config["title"], "steps": steps,
            "requested_fields": {key: value for key, value in config.items()
                                 if key not in {"expected_title", "attachments", "save_name"}},
            "body_characters": len(config.get("body", "")),
            "attachments": config["attachments"],
            "save_name": config.get("save_name"), "submission": "unsupported"}


def normalize_text(value):
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def replacement_dialog(text, name):
    # Both the exact quoted title and the observed replacement phrase must match.
    return (f"'{name}'" in text and "임시보관함에 이미" in text and
            "기존 문서를 이 문서로 바꾸시겠습니까?" in text)
