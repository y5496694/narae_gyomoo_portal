import hashlib
import base64
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/wxs-cli/scripts'
sys.path.insert(0, str(SCRIPTS))
from wxs_document import insert_body, capture_pages, export_document, replacement_preview, replace_document


class DocumentTests(unittest.TestCase):
    def test_export_restores_only_known_export_flags_and_preserves_dirty_draft(self):
        for kind, mode, modified in [('sancview', 0, False), ('sancgian', 2, True)]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                session = self.session(); session.frame_errors = []
                state = {**session.status(), 'app_type': kind, 'processed': False, 'edit_mode': mode, 'is_modified': modified}
                session.status = unittest.mock.Mock(side_effect=[state, {**state, 'edit_mode': 1, 'is_modified': True}, state])
                session.action = unittest.mock.Mock()
                control = unittest.mock.Mock(); session.editor = lambda: control
                data = bytes.fromhex('d0cf11e0a1b11ae1') + b'copy'
                with patch('wxs_document.native.call', return_value=base64.b64encode(data).decode()):
                    self.assertTrue(export_document(session, '가상 제목', Path(temp)/'copy.hwp')['verified'])
                self.assertEqual(control.EditMode, mode)
                session.action.assert_called_once_with('restore_export_readonly') if kind == 'sancview' else session.action.assert_called_once_with('set_draft_updated', {'modified': True})

    def test_replacement_is_full_load_and_rejects_changed_preview_or_protected_fields(self):
        for failure in ('none', 'fingerprint', 'protected', 'text'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                source = Path(temp)/'edited.hwp'; expected = Path(temp)/'expected.txt'
                source.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1')+b'edited')
                expected.write_text('가상 제목\n수정 본문\n끝.', encoding='utf-8')
                session = self.session(); control = unittest.mock.Mock(); session.editor = lambda: control
                state = session.status(); values = {'본문':'원래 본문', '결재제목':'가상 제목', '수신':'내부결재'}
                session.require_draft = lambda title: state.copy()
                session.action = unittest.mock.Mock()
                def call(ctrl, name, *args):
                    if name == 'GetFieldList': return '본문\x02결재제목\x02수신'
                    if name == 'GetFieldText': return values[args[0]]
                    if name == 'SetTextFile':
                        self.assertEqual(args[1:], ('HWP', ''))
                        state['document_text'] = '잘못된 내용' if failure == 'text' else expected.read_text(encoding='utf-8')
                        if failure == 'protected': values['수신'] = '다른 수신'
                        return True
                    raise AssertionError(name)
                with patch('wxs_document.native.call', side_effect=call) as mock:
                    preview = replacement_preview(session, '가상 제목', source, expected)
                    mock.reset_mock()
                    if failure == 'none':
                        self.assertTrue(replace_document(session, preview, preview['fingerprint'])['verified'])
                    else:
                        with self.assertRaises(ValueError): replace_document(session, preview, 'changed' if failure == 'fingerprint' else preview['fingerprint'])
                    if failure == 'fingerprint': mock.assert_not_called()

    def test_export_copy_preserves_open_state_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'copy.hwp';session=self.session()
            session.frame_errors=[]
            data=bytes.fromhex('d0cf11e0a1b11ae1')+b'mock-hwp-document'
            with patch('wxs_document.native.call',return_value=base64.b64encode(data).decode('ascii')) as call:
                self.assertTrue(export_document(session,'가상 제목',path)['verified'])
                self.assertEqual(path.read_bytes(),data)
                with self.assertRaises(ValueError):export_document(session,'가상 제목',path)
                self.assertEqual(call.call_count,1)

    def test_export_rejects_invalid_data_changed_state_and_wrong_title(self):
        for problem in ('data','state','title'):
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'copy.hwp';session=self.session()
                session.frame_errors=[]
                if problem=='state':
                    state=session.status();session.status=unittest.mock.Mock(side_effect=[state,{**state,'body':'changed'}])
                encoded=base64.b64encode(b'invalid' if problem=='data' else bytes.fromhex('d0cf11e0a1b11ae1')+b'valid').decode('ascii')
                with patch('wxs_document.native.call',return_value=encoded),self.assertRaises(ValueError):export_document(session,'다른 제목' if problem=='title' else '가상 제목',path)
                self.assertFalse(path.exists())

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
