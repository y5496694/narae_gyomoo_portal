import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/wxs-cli/scripts'))
from wxs_startup import prepare, apply

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
