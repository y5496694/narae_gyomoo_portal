from pathlib import Path
import sys
import unittest
import tempfile
import hashlib
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/wxs-cli/scripts'
sys.path.insert(0, str(SCRIPTS))
from wxs_runtime import Session, DraftFailure


class RuntimeTests(unittest.TestCase):
    def fake(self):
        session = Session.__new__(Session)
        session.window = {'pid': 999999, 'hwnd': 1}
        session.open_modal = lambda *args, **kwargs: ({'hwnd': 2}, object())
        session.action = lambda *args, **kwargs: None
        return session

    def test_save_requires_observed_success_message(self):
        session = self.fake()
        alert = {'hwnd': 3, 'title': '웹 페이지 메시지'}
        with patch('wxs_runtime.process_windows', return_value=[alert]), patch('wxs_runtime.alert_details', return_value=('정상적으로 처리되었습니다.', [])), patch('wxs_runtime.press_dialog_button') as press:
            result = session.save('가상 초안')
            self.assertTrue(result['saved'])
            press.assert_called_once_with(alert, [], '확인')

    def test_name_collision_cancelled_by_default(self):
        session = self.fake()
        alert = {'hwnd': 3, 'title': '웹 페이지 메시지'}
        text = "임시보관함에 이미 '가상 초안' 문서가 있습니다. 기존 문서를 이 문서로 바꾸시겠습니까?"
        with patch('wxs_runtime.process_windows', return_value=[alert]), patch('wxs_runtime.alert_details', return_value=(text, [])), patch('wxs_runtime.press_dialog_button') as press:
            with self.assertRaisesRegex(ValueError, 'save cancelled'): session.save('가상 초안')
            press.assert_called_once_with(alert, [], '취소')

    def test_authorized_exact_name_replacement_then_success(self):
        session = self.fake()
        alert = {'hwnd': 3, 'title': '웹 페이지 메시지'}
        text = "임시보관함에 이미 '가상 초안' 문서가 있습니다. 기존 문서를 이 문서로 바꾸시겠습니까?"
        with patch('wxs_runtime.process_windows', return_value=[alert]), patch('wxs_runtime.alert_details', side_effect=[(text, []), ('정상적으로 처리되었습니다.', [])]), patch('wxs_runtime.press_dialog_button') as press, patch('wxs_runtime.time.sleep'):
            self.assertTrue(session.save('가상 초안', True)['replacement_confirmed'])
            self.assertEqual(press.call_count, 2)

    def test_other_name_or_submission_prompt_never_confirmed(self):
        texts = ["임시보관함에 이미 '다른 초안' 문서가 있습니다. 기존 문서를 이 문서로 바꾸시겠습니까?", '결재올림하시겠습니까?']
        for text in texts:
            with self.subTest(text=text), patch('wxs_runtime.process_windows', return_value=[{'hwnd': 3, 'title': '웹 페이지 메시지'}]), patch('wxs_runtime.alert_details', return_value=(text, [])), patch('wxs_runtime.press_dialog_button') as press:
                with self.assertRaisesRegex(ValueError, 'Unknown site message'): self.fake().save('가상 초안', True)
                press.assert_not_called()

    def test_wrong_target_fails_before_any_write(self):
        session = self.fake()
        session.require_draft = lambda _: (_ for _ in ()).throw(ValueError('title mismatch'))
        with patch('wxs_runtime.native.call') as call:
            with self.assertRaises(DraftFailure) as failure: session.draft({'expected_title': '', 'title': '가상', 'attachments': []})
            self.assertEqual(failure.exception.details['completed_steps'], [])
            self.assertEqual(failure.exception.details['attempted_step'], 'preflight')
            call.assert_not_called()

    def test_same_size_replaced_attachment_fails_before_any_draft_write(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'same-name.txt'
            path.write_bytes(b'original')
            file = {'path': str(path), 'name': path.name, 'size': 8,
                    'sha256': hashlib.sha256(b'original').hexdigest()}
            path.write_bytes(b'replaced')
            session = self.fake()
            session.require_draft = lambda _: {}
            with patch('wxs_runtime.native.call') as call:
                with self.assertRaises(DraftFailure) as failure:
                    session.draft({'expected_title': '', 'title': '가상', 'attachments': [file]})
                self.assertEqual(failure.exception.details['attempted_step'], 'preflight')
                self.assertIn('content changed', str(failure.exception))
                call.assert_not_called()

    def test_existing_approval_line_fails_before_title_change(self):
        session = self.fake()
        session.require_draft = lambda _: {'approval_rows': ['drafter', 'existing approver']}
        with patch('wxs_runtime.native.call') as call:
            with self.assertRaises(DraftFailure) as failure: session.draft({'expected_title': '', 'title': '가상', 'attachments': [], 'approver': {'name': '가상교사'}})
            self.assertEqual(failure.exception.details['attempted_step'], 'preflight')
            call.assert_not_called()


if __name__ == '__main__': unittest.main(verbosity=2)
