import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/wxs-cli/scripts'))
from wxs_final import prepare, apply, confirm, INTERNAL_CONFIRM, processing_preview, process, audit_processing_rejection, acknowledge, COMPLETION_NOTICE, ROUTE_REVIEW, resume_route_review
from wxs_cli import parser, run
from wxs_final import acknowledge_failure


class FinalTests(unittest.TestCase):
    def test_failure_acknowledgement_keeps_attempt_locks_and_never_allows_retry(self):
        for issue in ('none', 'message', 'title', 'processed', 'buttons', 'multiple'):
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'receipt.json'
                receipt = {'status':'verification_required', 'processing_attempted':True, 'retry_allowed':False,
                           'fingerprint':'synthetic', 'expected_title':'합성 문서', 'window':{'hwnd':10,'pid':20}}
                path.write_text(json.dumps(receipt), encoding='utf-8')
                lock = Path(tmp)/'.wxs-final-attempts'/'attempt.json'
                lock.parent.mkdir(); lock.write_text('keep', encoding='utf-8')
                s = self.session()
                if issue == 'title': s.status.return_value['title'] = '다른 문서'
                if issue == 'processed': s.status.return_value['processed'] = True
                notice = {'title':'웹 페이지 메시지', 'hwnd':30}
                buttons = [{'class':'Button','text':'확인'}] + ([{'class':'Button','text':'취소'}] if issue == 'buttons' else [])
                runtime = SimpleNamespace(Session=lambda window:s,
                    process_windows=lambda pid:[notice, notice] if issue == 'multiple' else [notice],
                    alert_details=lambda window:('다른 안내' if issue == 'message' else '에러가 발생했습니다.', buttons),
                    press_dialog_button=Mock())
                if issue == 'none':
                    result = acknowledge_failure(path, '에러가 발생했습니다.', runtime)
                    self.assertFalse(result['completed']); self.assertFalse(result['retry_allowed'])
                    self.assertTrue(result['failure_notice_acknowledged'])
                    with self.assertRaises(ValueError): acknowledge_failure(path, '에러가 발생했습니다.', runtime)
                    runtime.press_dialog_button.assert_called_once()
                else:
                    with self.assertRaises(ValueError): acknowledge_failure(path, '에러가 발생했습니다.', runtime)
                    runtime.press_dialog_button.assert_not_called()
                self.assertEqual(lock.read_text(encoding='utf-8'), 'keep')

    def test_native_drafter_signature_clear_is_the_only_allowed_text_change_after_review(self):
        s=self.session();s.status.return_value['document_text']='머리\n가상 기안자\n본문'
        p=prepare(s,'submit','합성 문서','상신');button=s.action.return_value
        proof={'reviewed':False,'message':ROUTE_REVIEW,'guard':True,'processing_gate':True}
        runtime=SimpleNamespace(Session=lambda w:s,process_windows=lambda pid:[{'hwnd':30,'title':'웹 페이지 메시지'}],alert_details=lambda w:(ROUTE_REVIEW,[]),press_dialog_button=Mock(),native=SimpleNamespace(call=Mock(return_value='')))
        s.editor=Mock(return_value=object())
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'r.json';apply(s,p,p['fingerprint'],f,True)
            s.action.side_effect=lambda action,*args:proof if action=='route_review_status' else '가상 기안자' if action=='route_review_drafter' else button
            confirm(f,ROUTE_REVIEW,True,runtime);proof['reviewed']=True
            s.status.return_value['document_text']='머리\n\n본문'
            self.assertFalse(resume_route_review(f,None,False,runtime)['applied'])
            s.status.return_value['document_text']='머리\n\n다른 본문'
            with self.assertRaisesRegex(ValueError,'signature reset'):resume_route_review(f,None,False,runtime)

    def test_route_validation_keeps_original_attempt_and_resumes_once_only_after_review(self):
        s = self.session(); p = prepare(s, 'submit', '합성 문서', '상신')
        button = s.action.return_value
        proof = {'reviewed': False, 'message': ROUTE_REVIEW, 'guard': True, 'processing_gate': True}
        runtime = SimpleNamespace(Session=Mock(return_value=s), process_windows=Mock(return_value=[{'hwnd':30,'title':'웹 페이지 메시지'}]),
                                  alert_details=Mock(return_value=(ROUTE_REVIEW, [])), press_dialog_button=Mock())
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp)/'receipt.json'; apply(s, p, p['fingerprint'], f, True)
            s.action.side_effect = lambda action, *args: proof if action == 'route_review_status' else button
            result = confirm(f, ROUTE_REVIEW, True, runtime)
            self.assertEqual(result['status'], 'route_review_required')
            runtime.press_dialog_button.assert_called_once()
            with self.assertRaisesRegex(ValueError, 'not been confirmed'): resume_route_review(f, None, True, runtime)
            proof['reviewed'] = True
            preview = resume_route_review(f, None, False, runtime)
            with self.assertRaises(ValueError): resume_route_review(f, 'changed', True, runtime, True)
            result = resume_route_review(f, preview['fingerprint'], True, runtime, True)
            self.assertFalse(result['completed']); self.assertTrue(result['route_review_resumed'])
            self.assertTrue(list((Path(tmp)/'.wxs-final-attempts').glob('*.json')))
            with self.assertRaises(ValueError): resume_route_review(f, preview['fingerprint'], True, runtime, True)

    def test_route_validation_does_not_ack_unknown_guard_or_allow_body_change(self):
        for changed in ('guard', 'body'):
            s = self.session(); p = prepare(s, 'submit', '합성 문서', '상신'); button = s.action.return_value
            proof = {'reviewed':False,'message':ROUTE_REVIEW,'guard':changed!='guard','processing_gate':True}
            runtime = SimpleNamespace(Session=lambda w:s, process_windows=lambda pid:[{'hwnd':30,'title':'웹 페이지 메시지'}], alert_details=lambda w:(ROUTE_REVIEW,[]),press_dialog_button=Mock())
            with tempfile.TemporaryDirectory() as tmp:
                f=Path(tmp)/'receipt.json';apply(s,p,p['fingerprint'],f,True)
                s.action.side_effect=lambda action,*args:proof if action=='route_review_status' else '가상 기안자' if action=='route_review_drafter' else button
                if changed=='guard':
                    with self.assertRaises(ValueError):confirm(f,ROUTE_REVIEW,True,runtime)
                    runtime.press_dialog_button.assert_not_called()
                else:
                    confirm(f,ROUTE_REVIEW,True,runtime);proof['reviewed']=True;s.status.return_value['document_text']='다른 본문'
                    with self.assertRaisesRegex(ValueError,'outside'):resume_route_review(f,None,True,runtime)

    def session(self, operation='submit'):
        status = {'title': '합성 문서', 'processed': False,
                  'app_type': 'sancgian' if operation == 'submit' else 'sanckyul',
                  'document_text': '합성 문서 본문', 'approval_rows': ['기안자', '합성 결재자'],
                  'attachments': [], 'recipient': '합성 기관'}
        button = {'index': 1, 'label': '상신' if operation == 'submit' else '결재', 'disabled': False}
        return SimpleNamespace(check_window=Mock(), frame_errors=[], window={'hwnd': 10, 'pid': 20},
                               origin_path=urlsplit('https://synthetic.invalid/draft'),
                               status=Mock(return_value=status), action=Mock(return_value=[button]))

    def test_preview_is_read_only_for_submit_and_approve(self):
        for op, label in [('submit', '상신'), ('approve', '결재')]:
            s = self.session(op)
            p = prepare(s, op, '합성 문서', label)
            self.assertFalse(p['applied'])
            self.assertEqual(len(p['fingerprint']), 64)
            s.action.assert_called_once_with('final_buttons')

    def test_wrong_title_processed_unknown_and_wrong_form_rejected(self):
        for changes in [{'title': '다른 문서'}, {'processed': True}, {'processed': None},
                        {'app_type': 'sanckyul'}, {'document_text': ''}]:
            s = self.session(); s.status.return_value.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                prepare(s, 'submit', '합성 문서', '상신')
            s.action.assert_not_called()

    def test_duplicate_or_disabled_button_rejected(self):
        for buttons in [[], [{'index': 1, 'label': '상신', 'disabled': True}],
                        [{'index': i, 'label': '상신', 'disabled': False} for i in range(2)]]:
            s = self.session(); s.action.return_value = buttons
            with self.assertRaises(ValueError): prepare(s, 'submit', '합성 문서', '상신')

    def test_content_route_and_attachment_changes_invalidate_fingerprint(self):
        s = self.session(); old = prepare(s, 'submit', '합성 문서', '상신')['fingerprint']
        for field, value in [('document_text', '변경'), ('approval_rows', ['다른 결재자']), ('attachments', ['추가'])]:
            original = copy.deepcopy(s.status.return_value)
            s.status.return_value[field] = value
            p = prepare(s, 'submit', '합성 문서', '상신')
            with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'changed'):
                apply(s, p, old, Path(tmp) / 'receipt.json', True)
            s.status.return_value = original

    def test_authorization_required_without_click(self):
        s = self.session(); p = prepare(s, 'submit', '합성 문서', '상신')
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, 'authorization'):
            apply(s, p, p['fingerprint'], Path(tmp) / 'receipt.json', False)
        self.assertEqual(s.action.call_count, 1)

    def test_once_only_click_and_unknown_result_not_reported_completed(self):
        s = self.session(); p = prepare(s, 'submit', '합성 문서', '상신')
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'receipt.json'
            result = apply(s, p, p['fingerprint'], f, True)
            self.assertFalse(result['completed']); self.assertFalse(result['retry_allowed'])
            self.assertEqual(result['status'], 'verification_required')
            with self.assertRaises(FileExistsError): apply(s, p, p['fingerprint'], f, True)
            with self.assertRaises(FileExistsError): apply(s, p, p['fingerprint'], Path(tmp) / 'fresh.json', True)
            self.assertEqual([c.args[0] for c in s.action.call_args_list].count('final_click'), 1)

    def test_unknown_click_outcome_retains_durable_attempt(self):
        s = self.session(); p = prepare(s, 'submit', '합성 문서', '상신')
        s.action.side_effect = TimeoutError('unknown')
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'receipt.json'
            with self.assertRaises(TimeoutError): apply(s, p, p['fingerprint'], f, True)
            self.assertEqual(json.loads(f.read_text(encoding='utf-8'))['status'], 'attempting')
            with self.assertRaises(FileExistsError): apply(s, p, p['fingerprint'], Path(tmp) / 'new.json', True)

    def test_confirmation_message_is_observed_without_clicking(self):
        from wxs_final import inspect_dialog
        s = self.session(); p = prepare(s, 'submit', '합성 문서', '상신')
        runtime = SimpleNamespace(process_windows=Mock(return_value=[{'hwnd':30,'title':'웹 페이지 메시지'}]),
                                  alert_details=Mock(return_value=('상신하시겠습니까?', [])), press_dialog_button=Mock())
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'r.json'; apply(s, p, p['fingerprint'], f, True)
            observed = inspect_dialog(f, runtime)
            self.assertEqual(observed['message'], '상신하시겠습니까?')
            self.assertFalse(observed['completed'])
            runtime.press_dialog_button.assert_not_called()
            runtime.process_windows.return_value=[]
            self.assertFalse(inspect_dialog(f, runtime)['present'])

    def test_exact_operation_specific_confirmation_only_once(self):
        s = self.session(); p = prepare(s, 'submit', '합성 문서', '상신')
        runtime = SimpleNamespace(process_windows=Mock(return_value=[{'hwnd': 30, 'title': '웹 페이지 메시지'}]),
                                  alert_details=Mock(return_value=('상신하시겠습니까?', [])), press_dialog_button=Mock())
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'receipt.json'; apply(s, p, p['fingerprint'], f, True)
            with self.assertRaises(ValueError): confirm(f, '다른 문구', True, runtime)
            runtime.press_dialog_button.assert_not_called()
            self.assertFalse(confirm(f, '상신하시겠습니까?', True, runtime)['completed'])
            with self.assertRaises(ValueError): confirm(f, '상신하시겠습니까?', True, runtime)
            runtime.press_dialog_button.assert_called_once()

    def test_delete_send_and_signature_messages_are_not_confirmed(self):
        s = self.session(); p = prepare(s, 'submit', '합성 문서', '상신')
        for message in ['삭제하시겠습니까?', '발송하시겠습니까?', '인증서 암호 입력', '정상적으로 처리되었습니다.']:
            runtime = SimpleNamespace(process_windows=Mock(return_value=[{'hwnd': 30, 'title': '웹 페이지 메시지'}]),
                                      alert_details=Mock(return_value=(message, [])), press_dialog_button=Mock())
            with tempfile.TemporaryDirectory() as tmp:
                f = Path(tmp) / 'r.json'; apply(s, p, p['fingerprint'], f, True)
                with self.assertRaises(ValueError): confirm(f, message, True, runtime)
                runtime.press_dialog_button.assert_not_called()

    def test_internal_prompt_requires_same_document_and_internal_recipient_then_allows_final_prompt(self):
        s = self.session(); s.status.return_value['recipient'] = '내부결재'
        p = prepare(s, 'submit', '합성 문서', '상신')
        runtime = SimpleNamespace(Session=Mock(return_value=s), process_windows=Mock(return_value=[{'hwnd': 30, 'title': '웹 페이지 메시지'}]),
                                  alert_details=Mock(return_value=(INTERNAL_CONFIRM, [])), press_dialog_button=Mock())
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'receipt.json'; apply(s,p,p['fingerprint'],f,True)
            self.assertFalse(confirm(f,INTERNAL_CONFIRM,True,runtime)['completed'])
            with self.assertRaises(ValueError): confirm(f,INTERNAL_CONFIRM,True,runtime)
            self.assertEqual(runtime.press_dialog_button.call_count,1)
            runtime.alert_details.return_value=('결재올림하시겠습니까?',[])
            confirm(f,'결재올림하시겠습니까?',True,runtime)
            self.assertEqual(runtime.press_dialog_button.call_count,2)

    def test_internal_prompt_rejects_external_recipient_or_changed_route(self):
        for changed in ('recipient','approval_rows'):
            s=self.session(); s.status.return_value['recipient']='내부결재'
            p=prepare(s,'submit','합성 문서','상신')
            runtime=SimpleNamespace(Session=Mock(return_value=s),process_windows=Mock(return_value=[{'hwnd':30,'title':'웹 페이지 메시지'}]),alert_details=Mock(return_value=(INTERNAL_CONFIRM,[])),press_dialog_button=Mock())
            with tempfile.TemporaryDirectory() as tmp:
                f=Path(tmp)/'receipt.json'; apply(s,p,p['fingerprint'],f,True)
                s.status.return_value[changed]='외부기관' if changed=='recipient' else ['다른 결재자']
                with self.assertRaises(ValueError): confirm(f,INTERNAL_CONFIRM,True,runtime)
                runtime.press_dialog_button.assert_not_called()

    def test_site_preparation_requires_reviewed_new_preview_and_keeps_original_attempt(self):
        from wxs_final import inspect_dialog
        s=self.session();s.status.return_value['recipient']='내부결재'
        p=prepare(s,'submit','합성 문서','상신')
        runtime=SimpleNamespace(Session=Mock(return_value=s),process_windows=Mock(return_value=[{'hwnd':30,'title':'웹 페이지 메시지'}]),alert_details=Mock(return_value=(INTERNAL_CONFIRM,[])),press_dialog_button=Mock())
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'receipt.json';apply(s,p,p['fingerprint'],f,True)
            s.status.return_value['document_text'] += '\n기관 기본 연락처'
            with self.assertRaises(ValueError):confirm(f,INTERNAL_CONFIRM,True,runtime)
            preview=inspect_dialog(f,runtime)['document_preview']
            with self.assertRaises(ValueError):confirm(f,INTERNAL_CONFIRM,True,runtime,'wrong-preview')
            result=confirm(f,INTERNAL_CONFIRM,True,runtime,preview['fingerprint'])
            self.assertEqual(result['fingerprint'],p['fingerprint'])
            self.assertEqual(result['internal_confirmation_fingerprint'],preview['fingerprint'])
            runtime.press_dialog_button.assert_called_once()

    def test_processing_form_is_bound_to_document_state_and_clicked_once(self):
        s=self.session();p=prepare(s,'submit','합성 문서','상신')
        form={'title':'문서처리','text':'결재올림 확인','fields':[],'button':{'id':'aSubmit','label':'확인','disabled':False}}
        root=SimpleNamespace(url='https://synthetic.invalid/bms/cz/cb/snd/retrieveDocSanctn.do')
        runtime=SimpleNamespace(Session=Mock(return_value=s),native=SimpleNamespace(documents=Mock(return_value=([([],root)],[]))),process_windows=Mock(return_value=[{'hwnd':30,'pid':20,'title':'문서처리'}]))
        def action(name,*args,**kwargs):
            if name=='final_buttons':return [{'index':1,'label':'상신','disabled':False}]
            if name=='processing_status':return copy.deepcopy(form)
            return {'scheduled':True}
        s.action.side_effect=action
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'receipt.json';apply(s,p,p['fingerprint'],f,True)
            preview=processing_preview(f,runtime)
            form['fields'].append({'id':'changed','value':'x'})
            with self.assertRaisesRegex(ValueError,'changed'):process(f,preview,preview['fingerprint'],True,runtime)
            self.assertFalse(json.loads(f.read_text('utf-8')).get('processing_attempted'))
            form['fields'].clear()
            self.assertFalse(process(f,preview,preview['fingerprint'],True,runtime)['completed'])
            with self.assertRaises(ValueError):process(f,preview,preview['fingerprint'],True,runtime)
            self.assertEqual([call.args[0] for call in s.action.call_args_list].count('processing_click'),1)

    def test_processing_dialog_wrong_origin_is_not_usable(self):
        s=self.session();p=prepare(s,'submit','합성 문서','상신')
        root=SimpleNamespace(url='https://other.invalid/bms/cz/cb/snd/retrieveDocSanctn.do')
        runtime=SimpleNamespace(Session=Mock(return_value=s),native=SimpleNamespace(documents=Mock(return_value=([([],root)],[]))),process_windows=Mock(return_value=[{'hwnd':30,'pid':20,'title':'문서처리'}]))
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'receipt.json';apply(s,p,p['fingerprint'],f,True)
            with self.assertRaisesRegex(ValueError,'origin'):processing_preview(f,runtime)

    def test_legacy_rejection_audit_requires_unchanged_state_and_cannot_reset_new_attempts(self):
        root=SimpleNamespace(url='https://synthetic.invalid/retrieveDocSanctn.do')
        s=self.session();s.action.return_value={'exact_state':True,'legacy_gate_passed':False}
        runtime=SimpleNamespace(Session=Mock(return_value=s),native=SimpleNamespace(documents=Mock(return_value=([([],root)],[]))))
        preview={'fingerprint':'original','binding':{'window':{'hwnd':30},'form':{}}}
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'receipt.json'
            receipt={'window':{'hwnd':10},'processing_attempted':True,'processing_fingerprint':'original'}
            f.write_text(json.dumps(receipt),'utf-8')
            with patch('wxs_final.processing_preview',return_value=preview):
                result=audit_processing_rejection(f,runtime)
            self.assertTrue(result['processing_rejected_before_click'])
            receipt['processing_gate_version']=2;f.write_text(json.dumps(receipt),'utf-8')
            with self.assertRaises(ValueError):audit_processing_rejection(f,runtime)
            receipt.pop('processing_gate_version');f.write_text(json.dumps(receipt),'utf-8')
            preview['fingerprint']='changed'
            with patch('wxs_final.processing_preview',return_value=preview),self.assertRaises(ValueError):audit_processing_rejection(f,runtime)

    def test_completion_acknowledgment_only_closes_exact_notice_once(self):
        runtime=SimpleNamespace(process_windows=Mock(return_value=[{'hwnd':30,'title':'웹 페이지 메시지'}]),alert_details=Mock(return_value=(COMPLETION_NOTICE,[])),press_dialog_button=Mock())
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'receipt.json';f.write_text(json.dumps({'status':'verification_required','processing_attempted':True,'window':{'pid':20},'fingerprint':'original'}),'utf-8')
            with self.assertRaises(ValueError):acknowledge(f,'상신하시겠습니까?',runtime)
            runtime.press_dialog_button.assert_not_called()
            self.assertFalse(acknowledge(f,COMPLETION_NOTICE,runtime)['completed'])
            with self.assertRaises(ValueError):acknowledge(f,COMPLETION_NOTICE,runtime)
            runtime.press_dialog_button.assert_called_once()

    def test_cli_missing_authorization_fails_before_native_initialization(self):
        args = parser().parse_args(['final-action', '--hwnd', '10', '--operation', 'submit',
                                    '--expected-title', '합성 문서', '--button-label', '상신', '--apply'])
        with self.assertRaisesRegex(ValueError, 'confirm-final-action'): run(args)


if __name__ == '__main__': unittest.main()
