import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/wxs-cli/scripts'
sys.path.insert(0, str(SCRIPTS))
from wxs_config import load_config, plan, replacement_dialog


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / 'draft.json'

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, **extra):
        data = dict(expected_title='', title='테스트', **extra)
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return load_config(self.path)

    def test_plan_is_offline_and_ordered(self):
        config = self.load(body='a\nb', private_reasons=[6], save_name='시험')
        self.assertEqual(config['body'], 'a\r\nb')
        self.assertEqual(plan(config)['steps'], ['title', 'body', 'private_reasons', 'save_draft'])
        self.assertFalse(plan(config)['applied'])

    def test_reject_submission_or_unknown_key(self):
        for key in ('submit', 'send', 'script', 'aprover'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.load(**{key: True})

    def test_requires_expected_title(self):
        self.path.write_text('{"title":"x"}', encoding='utf-8')
        with self.assertRaises(ValueError): load_config(self.path)

    def test_duplicate_json_key_rejected(self):
        self.path.write_text('{"title":"x","title":"y","expected_title":""}', encoding='utf-8')
        with self.assertRaises(ValueError): load_config(self.path)

    def test_reason_types_ranges_and_duplicates(self):
        for reasons in ([], [0], [9], [True], [6, 6], ['6']):
            with self.subTest(reasons=reasons), self.assertRaises(ValueError):
                self.load(private_reasons=reasons)

    def test_relative_attachment_size_and_unicode(self):
        attachment = self.root / '시험 첨부.pdf'
        attachment.write_bytes(b'mock-pdf')
        config = self.load(attachments=[attachment.name])
        self.assertEqual(config['attachments'][0], {'path': str(attachment.resolve()), 'name': attachment.name, 'size': 8})

    def test_attachment_missing_empty_duplicate_rejected(self):
        with self.assertRaises(FileNotFoundError): self.load(attachments=['missing.pdf'])
        attachment = self.root / 'empty.pdf'
        attachment.touch()
        with self.assertRaises(ValueError): self.load(attachments=[attachment.name])
        attachment.write_bytes(b'X')
        with self.assertRaises(ValueError): self.load(attachments=[attachment.name, attachment.name])

    def test_body_file_bom_and_exclusivity(self):
        (self.root / '본문.txt').write_text('한글\n본문', encoding='utf-8-sig')
        self.assertEqual(self.load(body_file='본문.txt')['body'], '한글\r\n본문')
        with self.assertRaises(ValueError): self.load(body_file='본문.txt', body='x')

    def test_exact_recipient_and_approver_schema(self):
        with self.assertRaises(ValueError): self.load(recipient={'search': 'a'})
        with self.assertRaises(ValueError): self.load(approver={'name': 'x', 'send': True})
        self.assertEqual(self.load(approver={'name': '가상교사', 'id': 'mock-1'})['approver']['id'], 'mock-1')

    def test_auto_send_only_true(self):
        for value in (False, 'true', 1, None):
            with self.subTest(value=value), self.assertRaises(ValueError): self.load(auto_send=value)

    def test_exact_replacement_prompt(self):
        message = "임시보관함에 이미 '가상 초안' 문서가 있습니다.\n기존 문서를 이 문서로 바꾸시겠습니까?"
        self.assertTrue(replacement_dialog(message, '가상 초안'))
        self.assertFalse(replacement_dialog(message, '다른 초안'))
        self.assertFalse(replacement_dialog("'가상 초안'을 결재올림하시겠습니까?", '가상 초안'))

    def test_apply_needs_explicit_hwnd_before_com(self):
        self.load()
        result = subprocess.run([sys.executable, str(SCRIPTS / 'wxs_cli.py'), 'draft', '--config', str(self.path), '--apply'], capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 1)
        self.assertIn('explicit --hwnd', json.loads(result.stderr)['error'])

    def test_existing_output_stops_before_mutation(self):
        self.load()
        target = self.root / 'result.json'
        target.write_text('keep', encoding='utf-8')
        result = subprocess.run([sys.executable, str(SCRIPTS / 'wxs_cli.py'), 'draft', '--config', str(self.path), '--apply', '--hwnd', '1', '--out', str(target)], capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(target.read_text(encoding='utf-8'), 'keep')
        self.assertIn('Output already exists', json.loads(result.stderr)['error'])


if __name__ == '__main__': unittest.main(verbosity=2)
