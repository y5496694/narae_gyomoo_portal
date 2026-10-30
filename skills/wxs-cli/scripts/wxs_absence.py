"""Preserve the named approver using the observed return-after-absence option."""
import hashlib
import json
import re


def preview_state(page, person, position):
    if not page["url"]["location"].endswith("/retrieveAbsnceCoursInfo.do") or page["title"] != "부재자 결재선":
        raise ValueError("Expected the observed absence-route dialog")
    text = re.sub(r"\s+", " ", page["text"]).strip()
    if not re.search(r"\* 부재자 " + re.escape(person) + r" \* 부재자결재직위 " + re.escape(position) + r" \* 부재사유 ", text):
        raise ValueError("Absent approver identity differs")
    if "부재자가 복귀 후 결재처리" not in text:
        raise ValueError("Return-after-absence option missing")
    radios = page["controls"]
    if len(radios) != 4 or {r["id"] for r in radios} != {"absentRdo1", "absentRdo2", "absentRdo3", "absentRdo4"}:
        raise ValueError("Absence controls changed")
    if any(r["type"] != "radio" or r["value"] != r["id"][-1] for r in radios):
        raise ValueError("Absence option values changed")
    if len([r for r in radios if r["checked"]]) != 1 or page["links"] != [{"id": "", "label": "확인"}]:
        raise ValueError("Absence selection or confirmation control is ambiguous")
    state = {"person": person, "position": position, "mode": "after-return", "page": page}
    fingerprint = hashlib.sha256(json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {"applied": False, "fingerprint": fingerprint, **state}


def run(window, person, position, apply, fingerprint, native):
    docs, errors = native.documents(window)
    if errors or len(docs) != 1:
        raise ValueError("Expected one fully inspected absence page")
    doc = docs[0][1]
    page = native.inspect(docs)["pages"][0]
    preview = preview_state(page, person, position)
    if not apply:
        return preview
    if fingerprint != preview["fingerprint"]:
        raise ValueError("Absence dialog changed after preview")
    radio = native.call(doc, "getElementById", "absentRdo2")
    native.call(radio, "click")
    if not bool(radio.checked):
        raise ValueError("Return-after-absence option readback mismatch")
    links = [link for link in native.items(doc.links) if str(link.innerText or "").strip() == "확인"]
    if len(links) != 1:
        raise ValueError("Absence confirmation control changed")
    try:
        native.call(links[0], "click")
    except Exception:
        if native.win32gui.IsWindow(window["hwnd"]):
            raise
    return {"applied": True, "person": person, "position": position, "mode": "after-return",
            "dialog_closed": not bool(native.win32gui.IsWindow(window["hwnd"])),
            "next": "Verify the original draft's approval route after the pending add operation returns"}
