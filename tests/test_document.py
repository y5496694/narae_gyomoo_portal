import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/wxs-cli/scripts'
sys.path.insert(0, str(SCRIPTS))
from wxs_document import insert_body, capture_pages


class DocumentTests(unittest.TestCase):
    def test_insert_preserves_fields_and_compares_all_body_text(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'body.hwp'
            path.write_bytes(b'fake')
            spec = {'path': str(path), 'size': 4, 'sha256': hashlib.sha256(b'fake').hexdigest(),
                    'expected_text': '문장\n열1\n열2\n내용1\n내용2'}
            values = {'본문': '', '결재제목': '기존 제목', '수신': '내부결재'}
            def call(control, name, *args):
                if name == 'GetFieldList': return '본문\x02결재제목\x02수신'
                if name == 'GetFieldText': return values[args[0]]
                if name == 'GetTextFile': return '기존 제목\n' + values['본문'] + '\n내부결재'
                if name == 'MoveToField':
                    self.assertEqual(args, ('본문', True, True, False))
                    return True
                if name == 'SetTextFile':
                    self.assertEqual(args[1:], ('HWP', 'insertfile'))
                    values['본문'] = '문장\r\n열1\t열2\r\n내용1\t내용2'
                    return True
                raise AssertionError(name)
            with patch('wxs_document.native.call', side_effect=call):
                self.assertTrue(insert_body(object(), spec)['verified'])
                with self.assertRaisesRegex(ValueError, 'empty body'): insert_body(object(), spec)
            values['본문'] = ''
            spec['expected_text'] = '다른 내용'
            with patch('wxs_document.native.call', side_effect=call):
                with self.assertRaisesRegex(ValueError, 'readback mismatch'): insert_body(object(), spec)

    def test_changed_source_stops_before_any_control_call(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'body.hwp'
            path.write_bytes(b'new')
            spec = {'path': str(path), 'size': 3, 'sha256': hashlib.sha256(b'old').hexdigest()}
            with patch('wxs_document.native.call') as call:
                with self.assertRaisesRegex(ValueError, 'changed'): insert_body(object(), spec)
                call.assert_not_called()

    def session(self, changed=False):
        state = dict(title='가상 제목', hwp_title='가상 제목', body='가상 본문', document_text='가상 본문과 표', page_count=2,
                     is_modified=False, edit_mode=2, approval_rows=['기안자'], attachments=[])
        class Fake:
            window = {'hwnd': 1, 'pid': 2}
            def require_draft(self, title):
                if title != state['title']: raise ValueError('title mismatch')
                return state.copy()
            def editor(self): return object()
            def check_window(self): pass
            def status(self): return {**state, 'body': 'changed'} if changed else state.copy()
        return Fake()

    def test_all_rendered_pages_and_unchanged_state_are_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'capture'
            def render(control, name, path, page, dpi, depth, fmt):
                self.assertEqual((name, dpi, depth, fmt), ('CreatePageImage', 150, 24, 'bmp'))
                Image.new('RGB', (400, 600), 'white').save(path)
                return True
            with patch('wxs_document.native.call', side_effect=render) as call:
                result = capture_pages(self.session(), '가상 제목', directory, 150)
                self.assertTrue(result['verified'])
                self.assertEqual(len(result['pages']), 2)
                self.assertEqual(call.call_count, 2)
                self.assertEqual(len(list(directory.glob('*.png'))), 2)
                self.assertFalse(list(directory.glob('*.bmp')))
                with self.assertRaisesRegex(ValueError, 'new directory'):
                    capture_pages(self.session(), '가상 제목', directory, 150)
                self.assertEqual(call.call_count, 2)

    def test_wrong_title_and_changed_document_are_never_success(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'capture'
            with patch('wxs_document.native.call') as call:
                with self.assertRaisesRegex(ValueError, 'title mismatch'):
                    capture_pages(self.session(), '다른 제목', directory, 150)
                call.assert_not_called()
            def render(control, name, path, *args):
                Image.new('RGB', (400, 600)).save(path)
                return True
            with patch('wxs_document.native.call', side_effect=render):
                with self.assertRaisesRegex(ValueError, 'state changed'):
                    capture_pages(self.session(True), '가상 제목', directory, 150)


if __name__ == '__main__': unittest.main(verbosity=2)
