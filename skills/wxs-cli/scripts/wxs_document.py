"""Bounded formatted-body insertion and page rendering; wxs_cli.py entrypoint only."""
import base64
import hashlib
from pathlib import Path
import re

from wxs_config import verify_attachment
import wxs_native as native


def content_text(value):
    # Table cells and paragraphs use different whitespace in TEXT/field exports.
    return re.sub(r"[\s\ufffc]+", "", str(value))


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
