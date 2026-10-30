import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/wxs-cli/scripts'))
from wxs_route_notice import prepare, acknowledge, inspect_notices, read_notice


class RouteNoticeTests(unittest.TestCase):
    def setUp(self):
        self.title = '합성 기안'
        self.person = '합성교장'
        self.message = ('결재경로에 있는 [합성교장] 사용자가 현재 부재중입니다.\n'
                        '대리결재자를 지정하시려면, 현재 부재중인 사용자를 결재경로에서 삭제 후, 조직도에서 다시 추가하여 주시기 바랍니다.')
        self.session = Mock(window={'hwnd': 1, 'pid': 2})
        self.session.status.return_value = {'app_type': 'sancgian', 'processed': False, 'edit_mode': 2,
                                            'title': self.title, 'approval_rows': ['3결재교장합성교장대기']}
        self.notice = {'hwnd': 3, 'pid': 2, 'title': '웹 페이지 메시지'}
        self.children = [{'class': 'Button', 'text': '확인', 'hwnd': 4, 'control_id': 1}]
        self.runtime = SimpleNamespace(process_windows=Mock(return_value=[self.notice]),
            alert_details=Mock(return_value=(self.message, self.children)), press_dialog_button=Mock())

    def test_read_notices_only_observes_same_process_web_messages(self):
        self.runtime.process_windows.return_value = [self.notice, {'hwnd': 5, 'title': '결재경로'}]
        result = inspect_notices(self.session.window, self.runtime)
        self.assertEqual([n['message'] for n in result['notices']], [self.message])
        self.assertFalse(result['acknowledged'])
        self.runtime.process_windows.assert_called_once_with(2)
        self.runtime.alert_details.assert_called_once_with(self.notice)
        self.runtime.press_dialog_button.assert_not_called()

    def test_exact_notice_acknowledgement_preserves_route(self):
        preview = prepare(self.session, self.title, self.person, self.message, self.runtime)
        result = acknowledge(self.session, self.title, self.person, self.message, preview['fingerprint'], self.runtime)
        self.assertTrue(result['acknowledged'])
        self.assertFalse(result['route_changed'])
        self.runtime.press_dialog_button.assert_called_once_with(self.notice, self.children, '확인')

    def test_changed_message_identity_multiple_dialogs_and_fingerprint_refuse(self):
        for change in ('message', 'title', 'participant', 'multiple', 'fingerprint'):
            with self.subTest(change=change):
                self.setUp()
                preview = prepare(self.session, self.title, self.person, self.message, self.runtime)
                if change == 'message': self.runtime.alert_details.return_value = ('다른 안내', self.children)
                if change == 'title': self.session.status.return_value['title'] = '다른 기안'
                if change == 'participant': self.session.status.return_value['approval_rows'] = ['다른 사용자']
                if change == 'multiple': self.runtime.process_windows.return_value = [self.notice, self.notice]
                fingerprint = 'changed' if change == 'fingerprint' else preview['fingerprint']
                with self.assertRaises(ValueError):
                    acknowledge(self.session, self.title, self.person, self.message, fingerprint, self.runtime)
                self.runtime.press_dialog_button.assert_not_called()

    def test_readonly_content_change_notice_cannot_accept_editable_or_changed_document(self):
        message = '기안자에 의해 문서 내용이 변경되었습니다. 이력보기 버튼을 통해 확인하시기 바랍니다'
        self.runtime.alert_details.return_value = (message, self.children)
        self.session.frame_errors = []
        state = dict(app_type='sancview', title=self.title, hwp_title=self.title, edit_mode=0, is_modified=False)
        self.session.status.return_value = state.copy()
        preview = read_notice(self.session, self.title, message, self.runtime)
        for change in ({'edit_mode': 2}, {'is_modified': True}, {'title': '다른 문서'}, {'app_type': 'sancgian'}):
            self.session.status.return_value = {**state, **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                read_notice(self.session, self.title, message, self.runtime, preview['fingerprint'], True)
        self.session.status.return_value = state
        with self.assertRaises(ValueError):
            read_notice(self.session, self.title, message, self.runtime, 'changed', True)
        self.runtime.press_dialog_button.assert_not_called()
        result = read_notice(self.session, self.title, message, self.runtime, preview['fingerprint'], True)
        self.assertTrue(result['acknowledged'])
        self.assertFalse(result['document_changed'])
        self.runtime.press_dialog_button.assert_called_once()


if __name__ == '__main__':
    unittest.main()
