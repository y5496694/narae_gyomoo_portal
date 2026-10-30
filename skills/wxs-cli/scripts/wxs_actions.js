/* Fixed internal actions for the observed K-Edufine WXS draft form (ES5/JScript).
 * No generic script execution is exposed. Final actions use a document-bound preview.
 */
function wxsAction(action, p) {
    function need(ok, message) { if (!ok) throw Error(message); }
    function el(id) { var e = document.getElementById(id); need(e, "Missing element: " + id); return e; }
    function txt(id) { var e = document.getElementById(id); return e ? String(e.innerText || "").replace(/^\s+|\s+$/g, "") : ""; }
    function later(fn) { setTimeout(fn, 0); return {scheduled: true}; }
    function requireDraft() {
        need(typeof rInfo === "object" && rInfo.appType === "sancgian" && !rInfo.docProcessed,
             "Expected an unprocessed sancgian draft");
    }
    if (action === "restore_export_readonly") {
        need(typeof rInfo === "object" && rInfo.appType === "sancview", "Only a read-only document copy may restore export flags");
        need(typeof IMPL_SetDocumentUpdated === "function", "Observed clean-state helper unavailable");
        IMPL_SetDocumentUpdated("editor1", false);
        return {restored: true};
    }
    if (action === "set_draft_updated") {
        requireDraft();
        need(typeof p.modified === "boolean" && typeof IMPL_SetDocumentUpdated === "function", "Observed draft update helper unavailable");
        IMPL_SetDocumentUpdated("editor1", p.modified);
        return {updated: true};
    }
    if (action === "processing_status" || action === "processing_click" || action === "processing_preflight") {
        need(/\/retrieveDocSanctn\.do$/.test(String(location.pathname)), "Expected the observed document-processing route");
        var fields = [], processingInputs = document.querySelectorAll("input,select,textarea"), submit = el("aSubmit");
        for (var pf = 0; pf < processingInputs.length; pf++) {
            var input = processingInputs[pf], rect = input.getBoundingClientRect(), style = input.currentStyle || {};
            if (String(input.type).toLowerCase() === "hidden") continue;
            fields.push({id: String(input.id), name: String(input.name), type: String(input.type), value: input.type === "password" ? "[비밀번호]" : String(input.value), checked: !!input.checked, disabled: !!input.disabled,
                         visible: rect.right > rect.left && rect.bottom > rect.top && style.display !== "none" && style.visibility !== "hidden"});
        }
        var sr = submit.getBoundingClientRect();
        need(sr.right > sr.left && sr.bottom > sr.top, "Processing confirmation is not visible");
        var displayClone = document.body.cloneNode(true), nonDisplay = displayClone.querySelectorAll("script,style,noscript,object");
        for (var nd = nonDisplay.length - 1; nd >= 0; nd--) nonDisplay[nd].parentNode.removeChild(nonDisplay[nd]);
        var state = {title: String(document.title), text: String(displayClone.innerText || displayClone.textContent).replace(/^\s+|\s+$/g, "").slice(0, 20000), fields: fields, button: {id: "aSubmit", label: String(submit.innerText).replace(/^\s+|\s+$/g, ""), disabled: !!submit.disabled}};
        if (action === "processing_status") return state;
        var exactState = JSON.stringify(wxsPlain(state)) === JSON.stringify(wxsPlain(p.expected));
        if (action === "processing_preflight") return {exact_state: exactState, legacy_gate_passed: JSON.stringify(wxsPlain(state)) === JSON.stringify(p.expected)};
        need(exactState, "Processing form changed after preview");
        need(state.button.label === "확인" && !state.button.disabled, "Observed processing confirmation changed");
        for (var sp = 0; sp < fields.length; sp++) {
            need(fields[sp].type !== "password" || !fields[sp].visible, "A password control requires direct user authentication");
            need(fields[sp].id !== "enfcmtRules" || !fields[sp].checked, "Public notice posting is outside this processing confirmation");
        }
        return later(function() { submit.click(); });
    }
    if (action === "final_buttons" || action === "final_click") {
        var controls = document.getElementsByTagName("*"), finalButtons = [], targets = [];
        for (var fi = 0; fi < controls.length; fi++) {
            var control = controls[fi], tag = String(control.tagName || "").toLowerCase();
            if (tag !== "button" && tag !== "a" && !(tag === "input" && /^(button|submit)$/.test(control.type))) continue;
            var label = String(control.getAttribute("aria-label") || control.innerText || control.value || control.title || "").replace(/^\s+|\s+$/g, "");
            if (!/^(상신|결재올림|결재|결재\s*승인|승인)$/.test(label)) continue;
            var rect = control.getBoundingClientRect(), style = control.currentStyle || {};
            if (rect.right <= rect.left || rect.bottom <= rect.top || style.display === "none" || style.visibility === "hidden") continue;
            finalButtons.push({index: fi, label: label, disabled: !!control.disabled || control.getAttribute("aria-disabled") === "true"});
            targets.push(control);
        }
        if (action === "final_buttons") return finalButtons;
        need(typeof rInfo === "object" && (rInfo.docProcessed === false || rInfo.docProcessed === 0), "Document processing state changed or unknown");
        need((p.operation === "submit" && rInfo.appType === "sancgian") || (p.operation === "approve" && rInfo.appType === "sanckyul"), "Operation does not match this form");
        if (document.getElementById("Sj")) need(String(el("Sj").value) === p.expected_title, "Title changed before final click");
        var selected = null;
        for (var fj = 0; fj < finalButtons.length; fj++) {
            if (JSON.stringify(finalButtons[fj]) === JSON.stringify(p.button) && !finalButtons[fj].disabled) selected = targets[fj];
        }
        need(selected, "Observed final button changed");
        return later(function() { if ((rInfo.docProcessed === false || rInfo.docProcessed === 0) && !selected.disabled) selected.click(); });
    }
    if (action === "read_kind") {
        need(typeof rInfo === "object", "Document metadata unavailable");
        return {non_electronic: String(rInfo.externalflag) === "2" && String(rInfo.draftsrc) === "4"};
    }
    if (action === "attachment_manifest" || action === "attachment_export") {
        need(typeof Attach !== "undefined" && Attach.fileBox && typeof Attach.fileBox.fileListAtGroup === "function", "Attachment file list unavailable");
        var files = Attach.fileBox.fileListAtGroup(), manifest = [];
        for (var ai = 0; ai < files.length; ai++) manifest.push({name: String(files[ai].fileName), size: Number(files[ai].size)});
        if (action === "attachment_manifest") return manifest;
        need(JSON.stringify(manifest) === JSON.stringify(p.expected), "Attachment list changed; export stopped");
        need(typeof Attach.saveFilesAs === "function", "Observed app attachment-save handler unavailable");
        var saved = [];
        Attach.saveFilesAs(p.directory, function(path) { saved.push(String(path)); });
        return {saved: saved};
    }
    if (action === "ready") {
        try {
            if (p.kind === "open_task") {
                if (typeof nexacro === "undefined") return false;
                var readyForm = nexacro.getApplication().mainframe.QuickViewFrame.form;
                return !!(readyForm.dsAList && readyForm.dsAList.rowcount > 0 && typeof readyForm.Tab00_Tabpage1_divAuth_btnAuthC01_onclick === "function");
            }
            if (p.kind === "open_approval") return typeof PrtcpList !== "undefined" && frames.length > 1 && frames[1].document.readyState === "complete" && typeof fncVerify === "function";
            if (p.kind === "open_recipient") return typeof RecptList !== "undefined" && typeof onTabRecpChange === "function" && !!document.getElementById("orgnztNm");
            if (p.kind === "open_auto_send") return !!document.getElementById("ocslRadio0") && typeof fncVerify === "function";
            if (p.kind === "open_save") return !!document.getElementById("svrFileNm") && typeof fncSave === "function";
            return false;
        } catch (loading) { return false; }
    }
    if (action === "status") {
        var rows = [], tables = document.getElementsByTagName("table"), reasons = [];
        for (var i = 0; i < tables.length; i++) {
            if (String(tables[i].innerText || "").indexOf("결재경로표-") === 0) {
                for (var j = 1; j < tables[i].rows.length; j++) rows.push(String(tables[i].rows[j].innerText));
            }
        }
        for (i = 1; i <= 8; i++) if (document.getElementById("othbcAt" + i) && el("othbcAt" + i).checked) reasons.push(i);
        return {app_type: typeof rInfo === "object" ? String(rInfo.appType) : "",
                processed: typeof rInfo === "object" && rInfo.docProcessed != null ? !!rInfo.docProcessed : null,
                title: document.getElementById("Sj") ? String(el("Sj").value) : null,
                task_card: txt("referTaskTable"), private: document.getElementById("othbcLmtt3") ? !!el("othbcLmtt3").checked : null,
                disclosure: document.getElementById("othbcLmtt1") && el("othbcLmtt1").checked ? "public" : document.getElementById("othbcLmtt2") && el("othbcLmtt2").checked ? "partial" : document.getElementById("othbcLmtt3") && el("othbcLmtt3").checked ? "private" : null,
                private_reasons: reasons, approval_rows: rows, recipient: txt("recpList"),
                auto_send: document.getElementById("autoSendGian") ? !!el("autoSendGian").checked : null,
                final_buttons: wxsAction("final_buttons", {})};
    }
    if (action === "private") {
        requireDraft();
        if (!el("othbcLmtt3").checked) el("othbcLmtt3").click();
        for (var n = 1; n <= 8; n++) {
            var want = false;
            for (var k = 0; k < p.reasons.length; k++) if (p.reasons[k] === n) want = true;
            if (!!el("othbcAt" + n).checked !== want) el("othbcAt" + n).click();
        }
        return wxsAction("status", {});
    }
    if (action === "disclosure") {
        requireDraft();
        var disclosureIds = {"public": "othbcLmtt1", "partial": "othbcLmtt2", "private": "othbcLmtt3"};
        need(disclosureIds[p.mode], "Unsupported disclosure mode");
        var disclosureRadio = el(disclosureIds[p.mode]);
        if (!disclosureRadio.checked) disclosureRadio.click();
        for (var dr = 1; dr <= 8; dr++) {
            var requested = false;
            for (var dk = 0; dk < p.reasons.length; dk++) if (p.reasons[dk] === dr) requested = true;
            if (!!el("othbcAt" + dr).checked !== requested) el("othbcAt" + dr).click();
        }
        return wxsAction("status", {});
    }
    if (action === "open_task") { requireDraft(); need(typeof fncChooseTkcrd === "function", "Task handler missing"); return later(function() { fncChooseTkcrd(); }); }
    if (action === "task_select") {
        need(typeof nexacro !== "undefined", "Nexacro task form not loaded");
        var form = nexacro.getApplication().mainframe.QuickViewFrame.form, ds = form.dsAList, matches = [], names = [];
        need(ds && typeof form.fnSelectUnitTkcrd === "function", "Task dataset unavailable");
        for (var r = 0; r < ds.rowcount; r++) {
            var name = String(ds.getColumn(r, "tkcrdNm")); names.push(name);
            if (name === p.name) matches.push(r);
        }
        need(matches.length === 1, "Expected exact unique task card; candidates=" + names.join(" | "));
        form.fnSelectUnitTkcrd(matches[0]);
        need(typeof form.Tab00_Tabpage1_divAuth_btnAuthC01_onclick === "function", "Task confirmation handler missing");
        return later(function() { form.Tab00_Tabpage1_divAuth_btnAuthC01_onclick(); });
    }
    if (action === "task_options") {
        need(typeof nexacro !== "undefined", "Nexacro task form not loaded");
        var taskForm = nexacro.getApplication().mainframe.QuickViewFrame.form, taskNames = [];
        need(taskForm.dsAList, "Task dataset unavailable");
        for (var ti = 0; ti < taskForm.dsAList.rowcount; ti++) taskNames.push(String(taskForm.dsAList.getColumn(ti, "tkcrdNm")));
        return {candidates: taskNames};
    }
    if (action === "open_approval") { requireDraft(); need(typeof fncReportCours === "function", "Approval handler missing"); return later(function() { fncReportCours(); }); }
    if (action === "approval_options") {
        need(typeof PrtcpList !== "undefined", "Approval form unavailable");
        var options = [], people = [];
        for (var af = 0; af <= frames.length; af++) {
            var ad = af === frames.length ? document : frames[af].document;
            var inputs = ad.getElementsByTagName("input"), selects = ad.getElementsByTagName("select");
            for (var ap = 0; ap < inputs.length; ap++) {
                var input = inputs[ap];
                if (input.type === "radio" && input.name === "partSelRadio") people.push({name: String(input.value), id: String(input.id), row: String(input.parentNode.parentNode.innerText)});
                else if (input.type === "radio") options.push({tag: "input", id: String(input.id), name: String(input.name), value: String(input.value), checked: !!input.checked, text: String(input.parentNode.innerText)});
            }
            for (var as = 0; as < selects.length; as++) {
                var select = selects[as], choices = [];
                for (var ao = 0; ao < select.options.length; ao++) choices.push({text: String(select.options[ao].text), value: String(select.options[ao].value)});
                options.push({tag: "select", id: String(select.id), name: String(select.name), value: String(select.value), options: choices});
            }
        }
        var existing = PrtcpList.toArray(), summary = [];
        for (var ep = 0; ep < existing.length; ep++) summary.push({id: String(existing[ep].ID), name: String(existing[ep].name), position: String(existing[ep].positionName), role: String(existing[ep].hoxDisplayString)});
        return {participants: summary, candidates: people, controls: options};
    }
    if (action === "approval_cancel") {
        need(typeof PrtcpList !== "undefined" && PrtcpList.toArray().length === 1 && typeof closeWnd === "function", "Only an unchanged drafter-only selector can close");
        return later(function() { closeWnd(); });
    }
    if (action === "approval_route") {
        need(typeof rInfo === "object" && rInfo.appType === "sancgian", "Expected a draft approval selector");
        need(typeof PrtcpList !== "undefined" && typeof fncAdd === "function" && typeof fncVerify === "function", "Approval form unavailable");
        var original = PrtcpList.toArray();
        need(original.length === 1, "Only a drafter-only line is supported; existing line preserved");
        need(p.route && p.route.length > 0 && p.route.length <= 10, "Expected a bounded approval route");
        var resolved = [], seen = {};
        for (var ri = 0; ri < p.route.length; ri++) {
            var person = p.route[ri], hits = [];
            need(person.role === (ri === p.route.length - 1 ? "결재" : "검토"), "Route must end in one approver after reviewers");
            for (var rf = 0; rf < frames.length; rf++) {
                var radios = frames[rf].document.getElementsByTagName("input");
                for (var rr = 0; rr < radios.length; rr++) {
                    var candidate = radios[rr];
                    if (candidate.type === "radio" && candidate.name === "partSelRadio" && String(candidate.value) === person.name && (!person.id || String(candidate.id) === person.id)) hits.push(candidate);
                }
            }
            need(hits.length === 1 && hits[0].id && hits[0].id !== original[0].ID && !seen[hits[0].id], "Expected unique distinct route candidates before any add");
            seen[hits[0].id] = true; resolved.push(hits[0]);
        }
        for (var ai = 0; ai < resolved.length; ai++) {
            resolved[ai].click(); fncAdd();
            var current = PrtcpList.toArray();
            need(current.length === ai + 2 && current[0].ID === original[0].ID, "Unexpected approval line after add; inspect selector before resuming");
            for (var pi = 0; pi <= ai; pi++) need(current[pi + 1].ID === resolved[pi].id, "Approval order changed; inspect selector before resuming");
        }
        var confirmedRoute = [];
        for (var cr = 0; cr < resolved.length; cr++) confirmedRoute.push({name: p.route[cr].name, id: resolved[cr].id, role: p.route[cr].role});
        return wxsAction("approval_route_confirm", {route: confirmedRoute});
    }
    if (action === "approval_route_confirm") {
        need(typeof rInfo === "object" && rInfo.appType === "sancgian" && typeof PrtcpList !== "undefined" && typeof fncVerify === "function", "Expected a draft approval selector");
        need(p.route && p.route.length > 0 && p.route.length <= 10, "Expected a bounded approval route");
        var selectedRoute = PrtcpList.toArray();
        need(selectedRoute.length === p.route.length + 1, "Selected route length differs; no confirmation applied");
        for (var si = 0; si < p.route.length; si++) {
            need(p.route[si].id && selectedRoute[si + 1].ID === p.route[si].id && selectedRoute[si + 1].name === p.route[si].name, "Selected route identity/order differs; no confirmation applied");
            need(p.route[si].role === (si === p.route.length - 1 ? "결재" : "검토"), "Route must end in one approver after reviewers");
            var selectRole = el("draft" + (si + 1)), exactRoles = [];
            need(String(selectRole.parentNode.parentNode.innerText).indexOf(p.route[si].name) >= 0, "Role control does not match participant");
            for (var oi = 0; oi < selectRole.options.length; oi++) if (String(selectRole.options[oi].text) === p.route[si].role) exactRoles.push(String(selectRole.options[oi].value));
            need(exactRoles.length === 1, "Requested role is not a unique observed option");
            need(String(selectRole.value) === exactRoles[0], "Native role differs from requested role; selector preserved");
        }
        return later(function() { fncVerify(); });
    }
    if (action === "disclosure_options") {
        requireDraft();
        var disclosure = [], all = document.getElementsByTagName("input");
        for (var di = 0; di < all.length; di++) if (/^othbc(Lmtt|At)/.test(String(all[di].id)))
            disclosure.push({id: String(all[di].id), type: String(all[di].type), value: String(all[di].value), checked: !!all[di].checked, text: String(all[di].parentNode.innerText)});
        return disclosure;
    }
    if (action === "approval_select") {
        need(typeof PrtcpList !== "undefined" && typeof fncAdd === "function" && typeof fncVerify === "function", "Approval form unavailable");
        need(PrtcpList.toArray().length === 1, "Only a drafter-only line is supported; existing line preserved");
        var found = [], candidates = [];
        for (var f = 0; f < frames.length; f++) {
            var radios = frames[f].document.getElementsByTagName("input");
            for (var a = 0; a < radios.length; a++) {
                var radio = radios[a];
                if (radio.type === "radio" && radio.name === "partSelRadio" && String(radio.value) === p.name) {
                    candidates.push({name: String(radio.value), id: String(radio.id), row: String(radio.parentNode.parentNode.innerText)});
                    if (!p.id || String(radio.id) === p.id) found.push(radio);
                }
            }
        }
        need(found.length === 1, "Expected exact unique approver in current organization; matches=" + JSON.stringify(wxsPlain(candidates)));
        found[0].click(); fncAdd();
        need(PrtcpList.toArray().length === 2, "Unexpected approval line after add");
        return later(function() { fncVerify(); });
    }
    if (action === "open_recipient") { requireDraft(); need(typeof fncRcverAppn === "function", "Recipient handler missing"); return later(function() { fncRcverAppn(); }); }
    if (action === "recipient_search") {
        need(typeof onTabRecpChange === "function" && typeof fncOrgnztSearch2 === "function", "Recipient form unavailable");
        need(typeof RecptList !== "undefined" && RecptList.all.length === 0, "Only an empty recipient list is supported");
        onTabRecpChange("RecpOrgTree", "tabarea01");
        el("orgnztNm").value = p.search;
        return later(function() { fncOrgnztSearch2(); });
    }
    if (action === "recipient_candidates") {
        var nodes = document.getElementsByTagName("input"), out = [];
        for (var x = 0; x < nodes.length; x++) if (nodes[x].name === "orgnztChk") out.push(String(nodes[x].title));
        return out;
    }
    if (action === "recipient_select") {
        need(RecptList.all.length === 0, "Recipient list changed");
        var nodes2 = document.getElementsByTagName("input"), hits = [];
        for (var y = 0; y < nodes2.length; y++) if (nodes2[y].name === "orgnztChk" && String(nodes2[y].title) === p.name) hits.push(nodes2[y]);
        need(hits.length === 1, "Expected exact unique recipient");
        if (!hits[0].checked) hits[0].click();
        fncAdd(); need(RecptList.all.length === 1, "Unexpected recipient count after add");
        return later(function() { fncVerify(); });
    }
    if (action === "open_auto_send") {
        requireDraft(); need(typeof get_text === "function" && typeof popup === "function", "Automatic send handlers unavailable");
        var sender = get_text(domHox1, "/hox/docInfo/content/receiptInfo/senderName");
        var enforce = get_text(domHox1, "/hox/docInfo/enforceType");
        need(sender && enforce === "enforcetype_external", "Only external recipients with a selected sender are supported");
        need(!el("autoSendGian").checked, "Automatic send already selected; inspect its existing settings first");
        el("autoSendGian").checked = true; rInfo.senderNameAto = sender;
        return later(function() { popup("/cz/cb/snd/retrieveDocSndngScrinAto.do?flag=1&pType=doccrdMain", 600, 650, "modal", null, {scrollbars: "no"}); });
    }
    if (action === "auto_send_confirm") {
        need(el("signSe2").checked && el("ocslRadio0").checked, "Expected the default official seal selection");
        var sealCount = 0, inputs = document.getElementsByTagName("input");
        for (var s = 0; s < inputs.length; s++) if (String(inputs[s].id).indexOf("ocslRadio") === 0) sealCount++;
        need(sealCount === 1, "Multiple official seals require explicit handling; settings preserved");
        need(typeof fncVerify === "function", "Seal confirmation handler missing");
        return later(function() { fncVerify(); });
    }
    if (action === "attachment_status") {
        need(typeof Attach !== "undefined" && Attach.fileBox, "Attachment control unavailable");
        var files = Attach.fileBox.files(), metadata = [];
        for (var z = 0; z < files.length; z++) metadata.push({name: String(files[z].name), size: Number(files[z].size)});
        return metadata;
    }
    if (action === "attach") {
        requireDraft(); need(typeof HsFile === "function" && typeof Attach !== "undefined", "Attachment handlers unavailable");
        need(Attach.fileBox.files().length === p.expected_count, "Attachment list changed");
        // Keep the site's native _assertFiles/extension/size checks enabled.
        Attach.addFiles([new HsFile(p.path, p.name, p.size)]); Attach.onrefresh();
        var actual = wxsAction("attachment_status", {});
        need(actual.length === p.expected_count + 1, "Native attachment control rejected the file");
        return actual;
    }
    if (action === "open_save") { requireDraft(); need(typeof fncSaveTmpr === "function", "Temporary save handler missing"); return later(function() { fncSaveTmpr(); }); }
    if (action === "save_name") {
        need(typeof fncSave === "function", "Temporary save dialog unavailable");
        el("svrFileNm").value = p.name;
        return later(function() { fncSave(); });
    }
    throw Error("Unsupported bundled action: " + action);
}

function wxsPlain(value) {
    // Prototype.js adds Array.prototype.toJSON. Shadow it on our own arrays only.
    if (value === null || typeof value !== "object") return value;
    var out, i;
    if (Object.prototype.toString.call(value) === "[object Array]") {
        out = []; out.toJSON = null;
        for (i = 0; i < value.length; i++) out.push(wxsPlain(value[i]));
    } else {
        out = {};
        for (i in value) if (Object.prototype.hasOwnProperty.call(value, i)) out[i] = wxsPlain(value[i]);
    }
    return out;
}
