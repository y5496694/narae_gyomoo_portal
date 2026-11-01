import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/wxs-cli/scripts'))
from wxs_startup import prepare, apply, task_readback, select_task_once

class StartupTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(app_type='sancgian', processed=False, title='', hwp_title='', body='', attachments=[], is_modified=False)
        self.notices = [dict(hwnd=2, title='웹 페이지 메시지')]
        self.message = '현재 서식의 자동저장문서가 존재합니다.\n(마지막 저장: 합성 날짜)\n\n자동저장문서를 읽어오시겠습니까?'
        owner = self
        class Session:
            window = dict(hwnd=1, pid=9)
            def check_window(self): pass
            def status(self): return owner.state
        class Runtime:
            def process_windows(self, pid): return owner.notices
            def alert_details(self, window): return owner.message, [dict(text=t, **{'class':'Button'}) for t in ['확인','취소']]
            def press_dialog_button(self, *args): owner.clicked = args[-1]
        self.session, self.runtime = Session(), Runtime()
    def test_declines_only_unchanged_blank_draft_notices(self):
        preview = prepare(self.session,self.runtime)
        self.assertFalse(preview['ready'])
        self.assertTrue(apply(self.session,self.runtime,preview['fingerprint'])['existing_editor_preserved'])
        self.assertEqual(self.clicked,'취소')
    def test_unknown_changed_or_modified_draft_cannot_be_cancelled(self):
        preview = prepare(self.session,self.runtime)
        self.state['body'] = '기존 문서'
        with self.assertRaises(ValueError): apply(self.session,self.runtime,preview['fingerprint'])
        self.state['body'] = ''
        self.message = '상신하시겠습니까?'
        with self.assertRaises(ValueError): prepare(self.session,self.runtime)

    def test_task_selection_rebinds_after_access_denial_without_mutating_again(self):
        calls = []
        class ReloadingError(Exception): hresult = -2147024891
        def create(window):
            calls.append(window)
            if len(calls) == 1: raise ReloadingError('synthetic MSHTML transition')
            return self.session
        self.state['task_card'] = '[합성과제] 합성과제'
        self.assertEqual(task_readback(self.session.window,'','[합성과제] 합성과제',create,lambda _:None)['task_card'],self.state['task_card'])
        self.assertEqual(len(calls),2)
        self.state['title'] = '다른 문서'
        with self.assertRaises(ValueError): task_readback(self.session.window,'','[합성과제] 합성과제',create,lambda _:None)

    def test_task_dialog_closing_before_its_com_ack_is_verified_without_reselecting(self):
        calls = []
        class ClosingError(Exception): hresult = -2147024891
        def action(*args):
            calls.append(args)
            self.state['task_card'] = '[합성과제] 합성과제'
            raise ClosingError('dialog already closed before COM attribute read')
        self.session.action = action
        self.session.wait_closed = lambda window: calls.append(('closed', window))
        result = select_task_once(self.session, {'root': 'observed-root', 'window': {'hwnd': 2}},
                                  '', '[합성과제] 합성과제', lambda window: self.session)
        self.assertTrue(result['applied'])
        self.assertTrue(result['acknowledgment_lost'])
        self.assertEqual(len([call for call in calls if call[0] == 'task_select']), 1)
        self.assertEqual(result['status']['task_card'], '[합성과제] 합성과제')

    def test_task_validation_errors_are_not_interpreted_as_a_lost_com_ack(self):
        def action(*args): raise ValueError('ambiguous candidates')
        self.session.action = action
        self.session.wait_closed = lambda window: self.fail('validation failure must stop')
        with self.assertRaisesRegex(ValueError, 'ambiguous candidates'):
            select_task_once(self.session, {'root': 'observed-root', 'window': {'hwnd': 2}},
                             '', '[합성과제] 합성과제', lambda window: self.session)
