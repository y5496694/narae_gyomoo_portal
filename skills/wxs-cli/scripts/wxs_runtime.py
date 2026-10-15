"""Windows adapter. All writes are bounded draft actions in wxs_actions.js."""
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

import win32con
import win32gui
import win32process

import wxs_native as native
from wxs_config import normalize_text, replacement_dialog


class DraftFailure(RuntimeError):
    def __init__(self, error, completed, attempted):
        super().__init__(str(error))
        self.details = {"error": str(error), "completed_steps": completed,
                        "attempted_step": attempted, "partial_changes_possible": True,
                        "retry": "Inspect draft-status and open dialogs before resuming"}


def process_windows(pid):
    result = []
    def visit(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1] == pid:
            result.append({"hwnd": hwnd, "pid": pid, "title": win32gui.GetWindowText(hwnd)})
    win32gui.EnumWindows(visit, None)
    return result


def alert_details(window):
    children = []
    def visit(hwnd, _):
        children.append({"hwnd": hwnd, "class": win32gui.GetClassName(hwnd),
                         "text": win32gui.GetWindowText(hwnd),
                         "control_id": win32gui.GetDlgCtrlID(hwnd)})
    win32gui.EnumChildWindows(window["hwnd"], visit, None)
    message = " ".join(c["text"] for c in children if c["class"] == "Static").strip()
    return message, children


def press_dialog_button(window, children, label):
    buttons = [c for c in children if c["class"] == "Button" and
               c["text"].replace("&", "").strip() == label]
    if len(buttons) != 1:
        raise ValueError("Expected one observed dialog button: " + label)
    button = buttons[0]
    win32gui.SendMessageTimeout(window["hwnd"], win32con.WM_COMMAND,
                               button["control_id"], button["hwnd"], 2, 2000)


class Session:
    def __init__(self, window):
        self.window = window
        self.docs, self.frame_errors = native.documents(window)
        self.root = self.docs[0][1]
        self.origin_path = urlsplit(str(self.root.url))
        self.script = Path(__file__).with_name("wxs_actions.js").read_text(encoding="utf-8")

    def check_window(self):
        if (not win32gui.IsWindow(self.window["hwnd"]) or
                win32process.GetWindowThreadProcessId(self.window["hwnd"])[1] != self.window["pid"]):
            raise ValueError("Selected WXS window closed or changed process")

    def action(self, action, params=None, root=None):
        self.check_window()
        doc = root if root is not None else self.root
        if root is None:
            current = urlsplit(str(doc.url))
            if (current.scheme, current.netloc, current.path) != (self.origin_path.scheme, self.origin_path.netloc, self.origin_path.path):
                raise ValueError("Selected WXS page navigated; inspect the new page")
        # Parameter JSON is data in a fixed bundled function, never shell code.
        script = "(function(){" + self.script + "\ntry {var result = wxsAction(" + json.dumps(action) + "," + json.dumps(params or {}, ensure_ascii=True) + "); document.documentElement.setAttribute('data-wxs-cli-result', JSON.stringify(wxsPlain({ok:true,value:result})));} catch(e) {document.documentElement.setAttribute('data-wxs-cli-result',JSON.stringify({ok:false,error:String(e.message||e)}));}})();"
        native.call(doc.documentElement, "removeAttribute", "data-wxs-cli-result")
        native.call(doc.parentWindow, "execScript", script, "JScript")
        raw = native.call(doc.documentElement, "getAttribute", "data-wxs-cli-result")
        native.call(doc.documentElement, "removeAttribute", "data-wxs-cli-result")
        if not raw:
            raise ValueError("No response from bundled WXS action")
        result = json.loads(raw)
        if not result["ok"]:
            raise ValueError(result["error"])
        return result["value"]

    def editor(self):
        matches = [c for _, name, c in native.editors(self.docs) if name == "editor1"]
        if len(matches) != 1:
            raise ValueError("Expected one editor1 HwpCtrl")
        return matches[0]

    def status(self):
        status = self.action("status")
        control = self.editor()
        status.update({"edit_mode": int(control.EditMode), "is_modified": bool(control.IsModified),
                       "hwp_title": native.call(control, "GetFieldText", "결재제목"),
                       "body": native.call(control, "GetFieldText", "본문"),
                       "page_count": int(control.PageCount),
                       "attachments": native.attachments(self.docs)["rows"],
                       "window": self.window, "frame_errors": self.frame_errors})
        return status

    def require_draft(self, expected_title):
        self.check_window()
        if not win32gui.IsWindowEnabled(self.window["hwnd"]):
            raise ValueError("The main WXS window is blocked by a dialog; resolve it first")
        if self.frame_errors:
            raise ValueError("Frames could not be inspected; draft changes stopped")
        status = self.status()
        if status["app_type"] != "sancgian" or status["processed"] or status["edit_mode"] != 2:
            raise ValueError("Expected an editable, unprocessed standard draft (sancgian, EditMode=2)")
        if status["title"] != expected_title:
            raise ValueError("Current title differs from expected_title; no changes applied")
        # Both named fields are mandatory; GetFieldText(empty) alone is insufficient.
        fields = str(native.call(self.editor(), "GetFieldList", 0, 0)).split("\x02")
        if not {"본문", "결재제목"}.issubset(set(fields)):
            raise ValueError("Expected standard HWP fields 본문 and 결재제목")
        return status

    def open_modal(self, action, title_contains=None, path_suffix=None):
        baseline = {w["hwnd"] for w in process_windows(self.window["pid"])}
        self.action(action)
        deadline, last_error = time.monotonic() + 25, "No matching dialog appeared"
        while time.monotonic() < deadline:
            self.check_window()
            candidates = [w for w in process_windows(self.window["pid"])
                          if w["hwnd"] not in baseline and w["title"]]
            for window in candidates:
                if window["title"] == "웹 페이지 메시지":
                    message, _ = alert_details(window)
                    raise ValueError("Site validation dialog (left open): " + message)
            candidates = [w for w in candidates if not title_contains or title_contains in w["title"]]
            if len(candidates) > 1:
                raise ValueError("Multiple new WXS dialogs; selection stopped")
            if len(candidates) == 1:
                try:
                    docs, errors = native.documents(candidates[0])
                    root = docs[0][1]
                    parsed = urlsplit(str(root.url))
                    if parsed.netloc != self.origin_path.netloc:
                        raise ValueError("Dialog origin differs from the selected WXS page")
                    if path_suffix and not parsed.path.endswith(path_suffix):
                        raise ValueError("Dialog not yet at the expected application route")
                    if errors:
                        raise ValueError("Dialog frames not fully accessible")
                    if not self.action("ready", {"kind": action}, root):
                        raise ValueError("Expected dialog controls are still loading")
                    return candidates[0], root
                except Exception as error:
                    last_error = str(error)
            time.sleep(0.25)
        raise TimeoutError("WXS dialog unavailable: " + last_error)

    def wait_closed(self, window):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if not win32gui.IsWindow(window["hwnd"]):
                return
            alerts = [w for w in process_windows(self.window["pid"]) if w["title"] == "웹 페이지 메시지"]
            if alerts:
                message, _ = alert_details(alerts[0])
                raise ValueError("Site validation dialog (left open): " + message)
            time.sleep(0.25)
        raise TimeoutError("Application dialog did not close; inspect it before retrying")

    def save(self, name, replace_existing=False):
        window, root = self.open_modal("open_save", title_contains="임시저장")
        self.action("save_name", {"name": name}, root)
        deadline = time.monotonic() + 45
        replacement_confirmed = False
        while time.monotonic() < deadline:
            alerts = [w for w in process_windows(self.window["pid"]) if w["title"] == "웹 페이지 메시지"]
            if len(alerts) > 1:
                raise ValueError("Multiple native message dialogs; save result unknown")
            if alerts:
                alert = alerts[0]
                message, children = alert_details(alert)
                if message == "정상적으로 처리되었습니다.":
                    press_dialog_button(alert, children, "확인")
                    return {"saved": True, "name": name, "replacement_confirmed": replacement_confirmed,
                            "evidence": message}
                if replacement_dialog(message, name):
                    if not replace_existing:
                        press_dialog_button(alert, children, "취소")
                        raise ValueError("Draft name already exists; save cancelled. Use --replace-existing only when intended")
                    if replacement_confirmed:
                        raise ValueError("Repeated replacement prompt; stopped")
                    press_dialog_button(alert, children, "확인")
                    replacement_confirmed = True
                else:
                    raise ValueError("Unknown site message (left open; save result unknown): " + message)
            time.sleep(0.25)
        raise TimeoutError("No temporary-save success message observed; save result unknown, do not blindly retry")

    def draft(self, config, replace_existing=False):
        completed, attempted = [], "preflight"
        try:
            before = self.require_draft(config["expected_title"])
            if "approver" in config and len(before["approval_rows"]) != 1:
                raise ValueError("Expected a drafter-only approval line before changes")
            if "recipient" in config and before["recipient"]:
                raise ValueError("Expected an empty recipient list before changes")
            if "auto_send" in config and before["auto_send"]:
                raise ValueError("Automatic send is already selected; inspect its existing settings first")
            if config["attachments"] and self.action("attachment_status"):
                raise ValueError("Expected an empty attachment list before changes")
            control = self.editor()
            attempted = "title"
            title = native.call(self.root, "getElementById", "Sj")
            title.value = config["title"]
            native.call(title, "fireEvent", "onchange")
            if str(title.value) != config["title"] or normalize_text(str(native.call(control, "GetFieldText", "결재제목"))) != normalize_text(config["title"]):
                raise ValueError("Title/HWP readback mismatch")
            completed.append(attempted)
            if "body" in config:
                attempted = "body"
                native.call(control, "PutFieldText", "본문", config["body"])
                if normalize_text(str(native.call(control, "GetFieldText", "본문"))) != normalize_text(config["body"]):
                    raise ValueError("Body readback mismatch")
                completed.append(attempted)
            if "private_reasons" in config:
                attempted = "private_reasons"
                status = self.action("private", {"reasons": config["private_reasons"]})
                if not status["private"] or status["private_reasons"] != config["private_reasons"]:
                    raise ValueError("Non-disclosure reasons readback mismatch")
                completed.append(attempted)
            if "task_card" in config:
                attempted = "task_card"
                window, root = self.open_modal("open_task", path_suffix="taskChoiseTaskNexacroRP.do")
                self.action("task_select", {"name": config["task_card"]}, root)
                self.wait_closed(window)
                if config["task_card"] not in self.action("status")["task_card"]:
                    raise ValueError("Task card readback mismatch")
                completed.append(attempted)
            if "approver" in config:
                attempted = "approver"
                window, root = self.open_modal("open_approval", title_contains="결재경로")
                self.action("approval_select", config["approver"], root)
                self.wait_closed(window)
                rows = self.action("status")["approval_rows"]
                if len(rows) != 2 or sum(config["approver"]["name"] in row for row in rows) != 1:
                    raise ValueError("Expected the drafter and one approver in readback")
                completed.append(attempted)
            if "recipient" in config:
                attempted = "recipient"
                window, root = self.open_modal("open_recipient", title_contains="수신자지정", path_suffix="retrieveRcverSetup.do")
                self.action("recipient_search", config["recipient"], root)
                deadline, candidates = time.monotonic() + 20, []
                while time.monotonic() < deadline:
                    candidates = self.action("recipient_candidates", root=root)
                    if candidates:
                        break
                    time.sleep(0.25)
                if candidates.count(config["recipient"]["name"]) != 1:
                    raise ValueError("Expected exact unique recipient; candidates=" + json.dumps(candidates, ensure_ascii=False))
                self.action("recipient_select", config["recipient"], root)
                self.wait_closed(window)
                if not self.action("status")["recipient"]:
                    raise ValueError("Recipient readback is empty")
                completed.append(attempted)
            if "auto_send" in config:
                attempted = "auto_send"
                window, root = self.open_modal("open_auto_send", title_contains="자동발송", path_suffix="retrieveDocSndngScrinAto.do")
                self.action("auto_send_confirm", root=root)
                self.wait_closed(window)
                if not self.action("status")["auto_send"]:
                    raise ValueError("Automatic send readback mismatch")
                completed.append(attempted)
            if config["attachments"]:
                attempted = "attachments"
                existing = self.action("attachment_status")
                if existing:
                    raise ValueError("Attachment list is not empty; existing files preserved")
                for file in config["attachments"]:
                    if Path(file["path"]).stat().st_size != file["size"]:
                        raise ValueError("Attachment size changed since config validation")
                    existing = self.action("attach", dict(file, expected_count=len(existing)))
                    if existing[-1] != {"name": file["name"], "size": file["size"]}:
                        raise ValueError("Attachment metadata readback mismatch")
                completed.append(attempted)
            save_result = None
            if "save_name" in config:
                attempted = "save_draft"
                save_result = self.save(config["save_name"], replace_existing)
                completed.append(attempted)
            return {"applied": True, "completed_steps": completed, "save": save_result,
                    "submission": "unsupported", "status": self.status()}
        except Exception as error:
            raise DraftFailure(error, completed, attempted) from error
