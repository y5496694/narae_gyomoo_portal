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
from wxs_final import prepare, apply, confirm
from wxs_cli import parser, run


class FinalTests(unittest.TestCase):
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

    def test_cli_missing_authorization_fails_before_native_initialization(self):
        args = parser().parse_args(['final-action', '--hwnd', '10', '--operation', 'submit',
                                    '--expected-title', '합성 문서', '--button-label', '상신', '--apply'])
        with self.assertRaisesRegex(ValueError, 'confirm-final-action'): run(args)


if __name__ == '__main__': unittest.main()
