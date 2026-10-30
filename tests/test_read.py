"""Read/close safety checks with fake documents and no live window operations."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/wxs-cli/scripts'
sys.path.insert(0, str(SCRIPTS))
import wxs_read


class ReadTests(unittest.TestCase):
    def test_cancelling_a_prepared_reader_never_claims_or_closes_a_window(self):
        with tempfile.TemporaryDirectory() as temp:
            marker, output = Path(temp)/'cancel', Path(temp)/'result.json'
            def baseline(**_kwargs):
                marker.write_text('cancel', encoding='utf-8')
                return []
            native = SimpleNamespace(windows=Mock(side_effect=baseline))
            args = SimpleNamespace(timeout=5, expected_title='합성 공문', background=True,
                                   cancel_file=marker, out=output)
            with patch('wxs_read.win32gui.ShowWindow') as show, patch('wxs_read.win32gui.PostMessage') as close:
                result = wxs_read.read_next(args, native)
                self.assertEqual(result['status'], 'cancelled')
                self.assertEqual(native.windows.call_count, 1)
                show.assert_not_called(); close.assert_not_called()
            saved = json.loads(output.read_text(encoding='utf-8'))
            self.assertFalse(saved['body']['body_read'])
            self.assertTrue(saved['preserved']); self.assertFalse(saved['closed'])

    def test_title_matching_only_collapses_rendered_whitespace(self):
        self.assertTrue(wxs_read.title_matches('[안내]  예시\n문서', '[안내] 예시 문서'))
        self.assertFalse(wxs_read.title_matches('[수정] 예시 문서', '[안내] 예시 문서'))
        self.assertFalse(wxs_read.title_matches('예시 문서 추가', '예시 문서'))

    def test_new_certificate_challenge_is_preserved_without_hide_or_close(self):
        existing = {'hwnd': 1, 'pid': 42, 'title': '기존 사용자 창'}
        certificate = {'hwnd': 2, 'pid': 43, 'title': '인증서 로그인 -- 웹 페이지 대화 상자'}
        native = SimpleNamespace(windows=Mock(side_effect=[[existing], [existing, certificate]]))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'result.json'
            args = SimpleNamespace(timeout=5, expected_title='보안 문서', background=True, out=output)
            with patch('wxs_read.win32gui.ShowWindow') as show, patch('wxs_read.win32gui.PostMessage') as close:
                result = wxs_read.read_next(args, native)
                self.assertEqual(result['status'], 'authentication_required')
                self.assertTrue(result['preserved']); self.assertFalse(result['closed'])
                show.assert_not_called(); close.assert_not_called()
            saved = json.loads(output.read_text(encoding='utf-8'))
            self.assertFalse(saved['body']['body_read'])
            self.assertEqual(saved['authentication_windows'], [certificate])

    def native(self, mode=0, modified=False, frames=None):
        return SimpleNamespace(documents=Mock(return_value=([object()], frames or [])),
                               editors=Mock(return_value=[([], 'editor1', object())]),
                               editor_status=Mock(return_value={'edit_mode': mode, 'is_modified': modified, 'page_count': 1}))

    def test_read_open_preserves_existing_certificate_for_the_selected_process(self):
        main = {'hwnd': 1, 'pid': 42, 'title': '보안 문서'}
        certificate = {'hwnd': 2, 'pid': 42, 'title': '인증서 로그인 -- 웹 페이지 대화 상자'}
        native = SimpleNamespace(windows=Mock(return_value=[main, certificate]))
        with tempfile.TemporaryDirectory() as temp:
            args = SimpleNamespace(command='read-open', hwnd=1, timeout=5, expected_title='보안 문서',
                                   background=True, out=Path(temp)/'result.json')
            with patch('wxs_read.win32gui.ShowWindow') as show, patch('wxs_read.win32gui.PostMessage') as close:
                result = wxs_read.read_next(args, native)
                self.assertEqual(result['status'], 'authentication_required')
                show.assert_not_called(); close.assert_not_called()

    def test_attachment_export_failure_preserves_body_without_closing(self):
        main = {'hwnd': 1, 'pid': 42, 'title': '가상 문서'}
        native = self.native()
        native.windows = Mock(side_effect=[[], [main]])
        state = {'edit_mode': 0, 'is_modified': False, 'page_count': 1}
        native.text = Mock(return_value={'text': '보존할 본문', 'characters': 7, 'editor': state, 'editor_after': state})
        native.attachments = Mock(return_value={'files': [{'name': '예시.pdf'}]})
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            close = self.fake_window(stack)
            stack.enter_context(patch('wxs_read.win32gui.ShowWindow'))
            stack.enter_context(patch('wxs_read.export_attachments', side_effect=ValueError('App timeout')))
            args = SimpleNamespace(timeout=5, expected_title='가상 문서', background=True,
                                   attachments_dir=Path(temp)/'files', out=Path(temp)/'result.json')
            with self.assertRaisesRegex(ValueError, 'App timeout'):
                wxs_read.read_next(args, native)
            saved = json.loads(args.out.read_text(encoding='utf-8'))
            self.assertEqual(saved['body']['text'], '보존할 본문')
            self.assertFalse(saved['closed']); self.assertEqual(saved['attachment_export_error'], 'App timeout')
            close.assert_not_called()

    def fake_window(self, stack, title='가상 문서', pid=42):
        stack.enter_context(patch('wxs_read.win32gui.IsWindow', return_value=True))
        stack.enter_context(patch('wxs_read.win32gui.GetWindowText', return_value=title))
        stack.enter_context(patch('wxs_read.win32process.GetWindowThreadProcessId', return_value=(1, pid)))
        return stack.enter_context(patch('wxs_read.win32gui.PostMessage'))

    def test_wrong_title_or_reused_handle_never_closes(self):
        for title, pid in [('다른 문서', 42), ('가상 문서', 43)]:
            with self.subTest(title=title, pid=pid), ExitStack() as stack:
                post = self.fake_window(stack, title, pid)
                with self.assertRaisesRegex(ValueError, 'identity/title'):
                    wxs_read.close_readonly({'hwnd': 1, 'pid': 42}, '가상 문서', self.native())
                post.assert_not_called()

    def test_drafts_modified_documents_and_incomplete_frames_never_close(self):
        for native in [self.native(mode=1), self.native(modified=True), self.native(frames=[{'error': 'unavailable'}])]:
            with ExitStack() as stack:
                post = self.fake_window(stack)
                with self.assertRaises(ValueError):
                    wxs_read.close_readonly({'hwnd': 1, 'pid': 42}, '가상 문서', native)
                post.assert_not_called()

    def test_existing_hidden_window_and_ambiguous_new_windows_are_not_claimed(self):
        old = {'hwnd': 1, 'pid': 42, 'title': '가상 문서'}
        new = [dict(old, hwnd=2), dict(old, hwnd=3)]
        native = SimpleNamespace(windows=Mock(side_effect=[[old], [old] + new]))
        args = SimpleNamespace(timeout=5, expected_title='가상 문서', background=True)
        with patch('wxs_read.win32gui.ShowWindow') as show:
            with self.assertRaisesRegex(ValueError, 'Multiple new windows'):
                wxs_read.read_next(args, native)
            show.assert_not_called()
        native.windows.assert_called_with(include_hidden=True)


if __name__ == '__main__':
    unittest.main()
