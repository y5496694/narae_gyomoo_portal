/* Fixed internal actions for the observed K-Edufine WXS draft form (ES5/JScript).
 * No generic script execution is exposed by the CLI. No submission action exists.
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
                processed: typeof rInfo === "object" ? !!rInfo.docProcessed : null,
                title: document.getElementById("Sj") ? String(el("Sj").value) : null,
                task_card: txt("referTaskTable"), private: document.getElementById("othbcLmtt3") ? !!el("othbcLmtt3").checked : null,
                private_reasons: reasons, approval_rows: rows, recipient: txt("recpList"),
                auto_send: document.getElementById("autoSendGian") ? !!el("autoSendGian").checked : null};
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
    if (action === "open_approval") { requireDraft(); need(typeof fncReportCours === "function", "Approval handler missing"); return later(function() { fncReportCours(); }); }
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
