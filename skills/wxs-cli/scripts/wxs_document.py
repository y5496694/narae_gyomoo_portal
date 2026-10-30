"""Bounded formatted-body insertion and page rendering; wxs_cli.py entrypoint only."""
import base64
import hashlib
from pathlib import Path
import re

from wxs_config import verify_attachment
import wxs_native as native


def restore_export_flags(session, before, after):
    changed = {key for key in before if before[key] != after.get(key)}
    if not changed or not changed <= {"edit_mode", "is_modified"}:
        return after
    if before.get("app_type") == "sancview" and before["edit_mode"] == 0 and not before["is_modified"]:
        session.action("restore_export_readonly")
    elif before.get("app_type") == "sancgian" and before.get("processed") is False and before["edit_mode"] == 2:
        session.action("set_draft_updated", {"modified": before["is_modified"]})
    else:
        return after
    session.editor().EditMode = before["edit_mode"]
    return session.status()


def content_text(value):
    # Table cells and paragraphs use different whitespace in TEXT/field exports.
    return re.sub(r"[\s\ufffc]+", "", str(value))


def export_document(session, expected_title, output, restore_readonly_from=None):
    """Export a comparison/backup copy without saving over the open document."""
    output = Path(output).resolve()
    if output.exists() or output.suffix.lower() != ".hwp" or not output.parent.is_dir():
        raise ValueError("Document export requires a new HWP path in an existing directory")
    session.check_window()
    before = session.status()
    if restore_readonly_from is not None:
        expected_text = Path(restore_readonly_from).read_text(encoding="utf-8-sig")
        if before.get("app_type") != "sancview" or normalize_export_text(before["document_text"]) != normalize_export_text(expected_text) or (before.get("title") or before.get("hwp_title")) != expected_title:
            raise ValueError("Read-only export recovery text or document identity differs")
        session.action("restore_export_readonly")
        session.editor().EditMode = 0
        before = session.status()
    if session.frame_errors or (before.get("title") or before.get("hwp_title")) != expected_title or before["edit_mode"] not in (0, 2):
        raise ValueError("Document identity or editor mode does not match")
    try:
        encoded = str(native.call(session.editor(), "GetTextFile", "HWP", ""))
        data = base64.b64decode(re.sub(r"\s+", "", encoded), validate=True)
        if not data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")) or not 8 < len(data) <= 32 * 1024 * 1024:
            raise ValueError("HwpCtrl did not return a bounded binary HWP document")
    finally:
        after = restore_export_flags(session, before, session.status())
    changed = [key for key in before if before[key] != after.get(key)]
    if changed:
        raise ValueError("Open document changed during export; no file written; fields=" + ",".join(changed))
    with output.open("xb") as stream:
        stream.write(data)
    return {"exported": True, "verified": True, "path": str(output), "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "title": expected_title,
            "source": "selected WXS editor1 HwpCtrl GetTextFile(HWP)", "window": session.window}


def normalize_export_text(value):
    return str(value).replace("\r\n", "\n").replace("\r", "\n")


def replacement_preview(session, expected_title, source, expected_text_file):
    from wxs_final import fingerprint
    state = session.require_draft(expected_title)
    source = Path(source).resolve()
    size = source.stat().st_size
    if source.suffix.lower() != ".hwp" or not 8 < size <= 32 * 1024 * 1024:
        raise ValueError("Replacement requires a bounded full HWP draft copy")
    data = source.read_bytes()
    if not data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        raise ValueError("Replacement source is not binary HWP")
    expected = Path(expected_text_file).read_text(encoding="utf-8-sig")
    if not content_text(expected) or expected_title not in expected:
        raise ValueError("Expected full document text must include its exact title")
    control = session.editor()
    fields = str(native.call(control, "GetFieldList", 0, 0)).split("\x02")
    if fields.count("본문") != 1 or fields.count("결재제목") != 1:
        raise ValueError("Replacement requires one standard body and title field")
    protected = {name: native.call(control, "GetFieldText", name) for name in set(fields) - {"본문", ""}}
    binding = {"document": state, "fields": fields, "protected": protected,
               "source": {"path": str(source), "size": size, "sha256": hashlib.sha256(data).hexdigest()},
               "expected_text": expected}
    return {"applied": False, "fingerprint": fingerprint(binding), "binding": binding}


def replace_document(session, preview, expected_fingerprint):
    from wxs_final import fingerprint
    binding = preview["binding"]
    if not expected_fingerprint or expected_fingerprint != preview["fingerprint"] or fingerprint(binding) != expected_fingerprint:
        raise ValueError("Draft or replacement changed; inspect a new replacement preview")
    if session.require_draft(binding["document"]["title"]) != binding["document"]:
        raise ValueError("Draft changed after preview")
    verify_attachment(binding["source"])
    control = session.editor()
    data = Path(binding["source"]["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != binding["source"]["sha256"]:
        raise ValueError("Replacement source changed before apply")
    try:
        if not native.call(control, "SetTextFile", base64.b64encode(data).decode("ascii"), "HWP", ""):
            raise ValueError("HwpCtrl rejected the full draft copy")
        control.EditMode = 2
        session.action("set_draft_updated", {"modified": True})
        if str(native.call(control, "GetFieldList", 0, 0)).split("\x02") != binding["fields"]:
            raise ValueError("Standard field list changed")
        for name, value in binding["protected"].items():
            if native.call(control, "GetFieldText", name) != value:
                raise ValueError("A field outside the body changed: " + name)
        after = session.require_draft(binding["document"]["title"])
        allowed = {"body", "document_text", "page_count", "is_modified"}
        if any(value != after.get(key) for key, value in binding["document"].items() if key not in allowed):
            raise ValueError("Draft metadata changed")
        if content_text(after["document_text"]) != content_text(binding["expected_text"]):
            raise ValueError("Full document text differs from the Narae-edited copy")
    except Exception as error:
        raise ValueError("Replacement may have partially changed the draft; inspect before retrying: " + str(error)) from error
    return {"applied": True, "verified": True, "source": binding["source"], "status": after,
            "submission": "not_attempted", "font_verification": "Export and inspect the loaded copy with Narae Hangul Office"}


def insert_body(control, document):
    verify_attachment(document)
    fields = str(native.call(control, "GetFieldList", 0, 0)).split("\x02")
    if fields.count("본문") != 1 or fields.count("결재제목") != 1:
        raise ValueError("Formatted insertion requires one standard body and title field")
    if content_text(native.call(control, "GetFieldText", "본문")):
        raise ValueError("Formatted insertion requires an empty body; existing content is preserved")
    protected = {field: native.call(control, "GetFieldText", field)
                 for field in set(fields) - {"본문", ""}}
    before_text = content_text(native.call(control, "GetTextFile", "TEXT", ""))
    data = Path(document["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != document["sha256"]:
        raise ValueError("Body document changed before insertion")
    if not native.call(control, "MoveToField", "본문", True, True, False):
        raise ValueError("Could not move inside the body field")
    if not native.call(control, "SetTextFile", base64.b64encode(data).decode("ascii"), "HWP", "insertfile"):
        raise ValueError("HwpCtrl rejected the formatted body document")
    after_fields = str(native.call(control, "GetFieldList", 0, 0)).split("\x02")
    if fields != after_fields:
        raise ValueError("Standard field list changed during body insertion; inspect the draft")
    for field, text in protected.items():
        if native.call(control, "GetFieldText", field) != text:
            raise ValueError("A field outside the body changed: " + field)
    body = str(native.call(control, "GetTextFile", "TEXT", ""))
    actual, expected = content_text(body), content_text(document["expected_text"])
    if actual.count(expected) != 1 or actual.replace(expected, "", 1) != before_text:
        raise ValueError("Formatted body text readback mismatch; inspect before retrying")
    return {"verified": True, "source_sha256": document["sha256"], "body_characters": len(body)}


def capture_pages(session, expected_title, directory, dpi):
    from PIL import Image
    directory = Path(directory).resolve()
    if directory.exists() or not directory.parent.is_dir():
        raise ValueError("Capture requires a new directory inside an existing parent")
    if type(dpi) is not int or not 96 <= dpi <= 300:
        raise ValueError("Capture DPI must be an integer from 96 to 300")
    before = session.require_draft(expected_title)
    if not 1 <= before["page_count"] <= 50:
        raise ValueError("Capture supports 1 to 50 pages")
    control = session.editor()
    directory.mkdir()
    pages = []
    for page in range(before["page_count"]):
        session.check_window()
        bitmap = directory / f"page-{page + 1:03d}.bmp"
        output = directory / f"page-{page + 1:03d}.png"
        if not native.call(control, "CreatePageImage", str(bitmap), page, dpi, 24, "bmp"):
            raise ValueError("HwpCtrl page rendering failed; partial images remain in " + str(directory))
        with Image.open(bitmap) as image:
            image.load()
            width, height = image.size
            if width < 100 or height < 100:
                raise ValueError("HwpCtrl returned an incomplete page image")
            image.convert("RGB").save(output, "PNG")
        bitmap.unlink()
        with Image.open(output) as image:
            image.verify()
        pages.append({"page": page + 1, "path": str(output), "width": width, "height": height,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
    after = session.status()
    keys = ("title", "hwp_title", "body", "document_text", "page_count", "is_modified", "edit_mode", "approval_rows", "attachments")
    if any(before[key] != after[key] for key in keys):
        raise ValueError("Document state changed during rendering; images are unverified")
    return {"captured": True, "verified": True, "title": expected_title, "dpi": dpi,
            "source": "selected WXS editor1 HwpCtrl page rendering", "pages": pages,
            "body_sha256": hashlib.sha256(before["body"].encode("utf-8")).hexdigest(),
            "document_sha256": hashlib.sha256(before["document_text"].encode("utf-8")).hexdigest(),
            "window": session.window, "submission": "unsupported"}
