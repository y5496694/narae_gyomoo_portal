"""Offline validation and plans. Does not import Windows/COM modules."""
import json
import hashlib
import re
from pathlib import Path

VERSION = "0.4.0"
PACK_ID = "narae_gyomoo_portal"
FIELDS = {"expected_title", "title", "body", "body_file", "body_hwp", "task_card",
          "private_reasons", "approver", "recipient", "auto_send", "attachments",
          "save_name", "disclosure", "approval_route"}


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


def attachment_fingerprint(path):
    digest, size = hashlib.sha256(), 0
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"size": size, "sha256": digest.hexdigest()}


def verify_attachment(file):
    actual = attachment_fingerprint(file["path"])
    if any(actual[key] != file[key] for key in ("size", "sha256")):
        raise ValueError("Attachment content changed since config validation: " + file["path"])


def load_config(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=no_duplicates)
    exact_object(data, FIELDS, {"expected_title", "title"}, "config")
    string(data["expected_title"], "expected_title", empty=True)
    string(data["title"], "title")
    if sum(key in data for key in ("body", "body_file", "body_hwp")) > 1:
        raise ValueError("Use only one of body, body_file, or body_hwp")
    if "body_hwp" in data:
        document = data["body_hwp"]
        exact_object(document, {"path", "expected_text"}, {"path", "expected_text"}, "body_hwp")
        source = (path.parent / string(document["path"], "body_hwp.path")).resolve(strict=True)
        string(document["expected_text"], "body_hwp.expected_text")
        if source.suffix.lower() != ".hwp" or not source.is_file() or not 0 < source.stat().st_size <= 32 * 1024 * 1024:
            raise ValueError("body_hwp requires a nonempty HWP file of at most 32 MiB")
        with source.open("rb") as stream:
            if stream.read(8) != bytes.fromhex("d0cf11e0a1b11ae1"):
                raise ValueError("body_hwp requires a binary HWP document")
        data["body_hwp"] = {"path": str(source), "expected_text": document["expected_text"],
                            **attachment_fingerprint(source)}
    if "body_file" in data:
        source = path.parent / string(data.pop("body_file"), "body_file")
        data["body"] = source.read_text(encoding="utf-8-sig")
    if "body" in data:
        string(data["body"], "body", empty=True)
        # A trailing paragraph places the standard body's closing field marker
        # on a new line instead of immediately after the final "끝.".
        data["body"] = data["body"].replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n").rstrip()
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
    if "disclosure" in data:
        if "private_reasons" in data:
            raise ValueError("Use disclosure or private_reasons, not both")
        disclosure = data["disclosure"]
        exact_object(disclosure, {"mode", "reasons"}, {"mode", "reasons"}, "disclosure")
        mode, reasons = disclosure["mode"], disclosure["reasons"]
        if mode not in ("public", "partial", "private") or not isinstance(reasons, list) or any(type(n) is not int or n not in range(1, 9) for n in reasons) or len(reasons) != len(set(reasons)):
            raise ValueError("Invalid disclosure mode/reasons")
        if bool(reasons) != (mode != "public"):
            raise ValueError("Partial/private disclosure requires reasons; public requires none")
        disclosure["reasons"] = sorted(reasons)
    if "approval_route" in data:
        if "approver" in data:
            raise ValueError("Use approval_route or approver, not both")
        route = data["approval_route"]
        if not isinstance(route, list) or not 1 <= len(route) <= 10:
            raise ValueError("approval_route requires 1..10 participants")
        seen = set()
        for index, person in enumerate(route):
            exact_object(person, {"name", "id", "role"}, {"name", "role"}, "approval_route participant")
            for key in ("name", "id"):
                if key in person:
                    string(person[key], "approval_route." + key)
            if person["role"] != ("결재" if index == len(route) - 1 else "검토"):
                raise ValueError("approval_route must end in 결재 after 검토 participants")
            identity = person.get("id", person["name"])
            if identity in seen:
                raise ValueError("Duplicate approval participant")
            seen.add(identity)
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
        resolved.append({"path": str(target), "name": target.name, **attachment_fingerprint(target)})
    data["attachments"] = resolved
    return data


def plan(config):
    steps = ["title"]
    for key in ("body", "body_hwp", "private_reasons", "disclosure", "task_card", "approver", "approval_route", "recipient", "auto_send"):
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


def approval_route_matches(rows, route):
    """The live table may display descending sequence; verify its actual numbers."""
    numbered = {}
    for row in rows:
        match = re.match(r"^\s*(\d+)\s*(.*)$", row, re.S)
        if not match or int(match[1]) in numbered:
            return False
        numbered[int(match[1])] = match[2]
    if set(numbered) != set(range(1, len(route) + 2)) or not numbered[1].startswith("기안"):
        return False
    return all(numbered[index + 2].startswith(person["role"]) and person["name"] in numbered[index + 2]
               for index, person in enumerate(route))


def approval_route_review_matches(rows, route):
    """Only pre-confirm parity for recalled '-' rows; native full IDs/roles
    must still match in approval_route_confirm, then numbered readback is mandatory."""
    if approval_route_matches(rows, route):
        return True
    if len(rows) != len(route) + 1 or any(not re.match(r"^\s*-", row) for row in rows):
        return False
    cleaned = [row.strip()[1:].lstrip() for row in rows]
    return (sum(row.startswith("기안") for row in cleaned) == 1 and
            all(sum(row.startswith(person["role"]) and person["name"] in row for row in cleaned) == 1 for person in route))


def replacement_dialog(text, name):
    # Both the exact quoted title and the observed replacement phrase must match.
    return (f"'{name}'" in text and "임시보관함에 이미" in text and
            "기존 문서를 이 문서로 바꾸시겠습니까?" in text)
