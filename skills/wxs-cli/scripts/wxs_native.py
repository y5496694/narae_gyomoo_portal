"""Internal read-only MSHTML/HwpCtrl adapter. Use wxs_cli.py as the entrypoint."""
import json
import re
from urllib.parse import urlsplit, parse_qsl

import pythoncom
import win32com.client
import win32com.client.dynamic
import win32gui
import win32process


def call(obj, name, *args):
    """Invoke by DISPID to avoid MSHTML generated-wrapper signature errors."""
    ole = obj._oleobj_
    result = ole.Invoke(ole.GetIDsOfNames(name), 0,
                        pythoncom.DISPATCH_METHOD, True, *args)
    if hasattr(result, "GetTypeInfo"):
        return win32com.client.dynamic.DumbDispatch(result)
    return result


def items(collection):
    for index in range(collection.length):
        yield call(collection, "item", index)


def windows(include_hidden=False):
    service = win32com.client.GetObject("winmgmts:")
    pids = {int(p.ProcessId) for p in service.ExecQuery(
        "SELECT ProcessId FROM Win32_Process WHERE Name='WXSClient.exe'")}
    result = []

    def visit(hwnd, unused):
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        if (pid in pids and (include_hidden or win32gui.IsWindowVisible(hwnd))
                and win32gui.GetWindowText(hwnd)):
            result.append({"hwnd": hwnd, "pid": pid,
                           "title": win32gui.GetWindowText(hwnd),
                           "visible": bool(win32gui.IsWindowVisible(hwnd)),
                           "enabled": bool(win32gui.IsWindowEnabled(hwnd)),
                           "class": win32gui.GetClassName(hwnd)})
    win32gui.EnumWindows(visit, None)
    return result


def select_window(args):
    candidates = windows(include_hidden=args.hwnd is not None)
    if args.hwnd is not None:
        candidates = [w for w in candidates if w["hwnd"] == args.hwnd]
    if len(candidates) != 1:
        raise ValueError("Expected one WXS window; run windows and select --hwnd. "
                         + json.dumps(candidates, ensure_ascii=False))
    return candidates[0]


def documents(window):
    children = []
    win32gui.EnumChildWindows(window["hwnd"],
                             lambda h, _: children.append(h), None)
    servers = [h for h in children
               if win32gui.GetClassName(h) == "Internet Explorer_Server"]
    if len(servers) != 1:
        raise ValueError("Expected one MSHTML server; found %d" % len(servers))
    message = win32gui.RegisterWindowMessage("WM_HTML_GETOBJECT")
    response = win32gui.SendMessageTimeout(servers[0], message, 0, 0,
                                           2, 2000)  # SMTO_ABORTIFHUNG
    lresult = response[1] if isinstance(response, tuple) else response
    if not lresult:
        raise ValueError("MSHTML did not expose its document")
    root = win32com.client.dynamic.DumbDispatch(
        pythoncom.ObjectFromLresult(lresult, pythoncom.IID_IDispatch, 0))
    result, errors = [], []

    def walk(doc, frame):
        result.append((frame, doc))
        if len(frame) >= 8:
            errors.append({"frame": frame, "error": "Frame depth limit"})
            return
        for index in range(doc.frames.length):
            try:
                walk(call(doc.frames, "item", index).document, frame + [index])
            except Exception as error:
                errors.append({"frame": frame + [index], "error": str(error)})
    walk(root, [])
    return result, errors


def safe_url(value):
    parsed = urlsplit(str(value))
    return {"location": parsed.scheme + "://" + parsed.netloc + parsed.path
            if parsed.netloc else parsed.scheme + ":" + parsed.path,
            "query_keys": sorted({key for key, _ in parse_qsl(parsed.query)})}


def editors(docs):
    for frame, doc in docs:
        for element in items(call(doc, "getElementsByTagName", "object")):
            classid = str(call(element, "getAttribute", "classid") or "")
            if "BD9C32E4-3155-4691-8972-097D53B10052" in classid.upper():
                yield frame, str(element.id), element.object


def editor_status(frame, editor_id, control):
    return {"frame": frame, "id": editor_id,
            "edit_mode": int(control.EditMode),
            "page_count": int(control.PageCount),
            "is_modified": bool(control.IsModified)}


def inspect(docs):
    pages = []
    for frame, doc in docs:
        functions, routes, objects, links = set(), set(), [], []
        for script in items(doc.scripts):
            source = str(script.text or "")
            functions.update(re.findall(r"function\s+([\w$]+)\s*\(", source))
            routes.update(re.findall(r"[\w/.-]+\.do\b", source))
        for element in items(call(doc, "getElementsByTagName", "object")):
            objects.append({"id": str(element.id), "classid": str(
                call(element, "getAttribute", "classid") or "")})
        for link in items(doc.links):
            label = str(link.innerText or link.title or "").strip()
            if link.id or label:
                links.append({"id": str(link.id), "label": label})
        page = {"frame": frame, "url": safe_url(doc.url),
                      "title": str(doc.title), "objects": objects,
                      "inline_functions": sorted(functions),
                      "inline_routes": sorted(routes), "links": links}
        if urlsplit(str(doc.url)).path.endswith("retrieveAbsnceCoursInfo.do"):
            clone = call(doc.body, "cloneNode", True)
            for tag in ("script", "style"):
                for node in list(items(call(clone, "getElementsByTagName", tag))):
                    call(node.parentNode, "removeChild", node)
            page["text"] = str(clone.innerText or "")
            page["controls"] = []
            for element in items(call(doc, "querySelectorAll", "input,select,button")):
                kind = str(element.type or "").lower()
                if kind in ("hidden", "password"):
                    continue
                page["controls"].append({"id": str(element.id), "type": kind,
                                         "value": str(element.value or ""),
                                         "checked": bool(element.checked) if kind in ("radio", "checkbox") else None,
                                         "text": str(element.innerText or "")})
        pages.append(page)
    controls = []
    for frame, editor_id, control in editors(docs):
        row = editor_status(frame, editor_id, control)
        info = control._oleobj_.GetTypeInfo()
        row["com_type"] = info.GetDocumentation(-1)[0]
        row["member_names"] = sorted({info.GetNames(
            info.GetFuncDesc(i)[0])[0] for i in range(info.GetTypeAttr().cFuncs)})
        row["document_methods"] = {}
        for index in range(info.GetTypeAttr().cFuncs):
            desc = info.GetFuncDesc(index)
            names = info.GetNames(desc[0])
            if names[0] in {"CreatePageImage", "CreatePageImageEx", "SetTextFile", "MoveToField"}:
                row["document_methods"][names[0]] = {"parameters": list(names[1:]),
                    "documentation": info.GetDocumentation(desc[0])[1]}
        controls.append(row)
    return {"pages": pages, "editors": controls}


def text(docs, editor_id):
    matches = [(frame, name, control) for frame, name, control in editors(docs)
               if name == editor_id]
    if len(matches) != 1:
        raise ValueError("Expected one editor named %s; found %d" %
                         (editor_id, len(matches)))
    frame, name, control = matches[0]
    before = editor_status(frame, name, control)
    value = call(control, "GetTextFile", "TEXT", "")
    if value is None:
        raise ValueError("Editor returned no TEXT data (empty or unavailable)")
    after = editor_status(frame, name, control)
    return {"editor": before, "editor_after": after,
            "characters": len(value), "text": value}


def attachments(docs):
    result = []
    for frame, doc in docs:
        for row in items(call(doc, "getElementsByTagName", "tr")):
            cells = [str(cell.innerText or "").strip() for cell in items(row.cells)]
            # Keep actual table rows, excluding parent tables containing all rows.
            if any(re.search(r"\.(hwp|hwpx|hwx|pdf|docx?|xlsx?|pptx?|zip|png|jpg)\b",
                             cell, re.I) for cell in cells):
                if len(cells) <= 10 and sum(map(len, cells)) < 2000:
                    result.append({"frame": frame, "cells": cells})
    return {"rows": result,
            "coverage": "Visible DOM table metadata; no attachment download"}


