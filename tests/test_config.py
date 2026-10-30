import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/wxs-cli/scripts'
sys.path.insert(0, str(SCRIPTS))
from wxs_config import load_config, plan, replacement_dialog, approval_route_matches, approval_route_review_matches


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
        self.assertEqual(config['attachments'][0], {'path': str(attachment.resolve()), 'name': attachment.name, 'size': 8,
                                                  'sha256': hashlib.sha256(b'mock-pdf').hexdigest()})

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

    def test_body_ends_at_final_text_preserving_internal_layout(self):
        expected = '1. 관련: 합성 근거\r\n2. 합성 내용\r\n  가. 세부 내용\r\n\r\n붙임  합성 문서 1부.  끝.'
        self.assertEqual(self.load(body=expected + '  \t\r\n\r\n')['body'], expected)
        (self.root / '본문.txt').write_bytes((expected + '\r\n').encode('utf-8'))
        self.assertEqual(self.load(body_file='본문.txt')['body'], expected)

    def test_formatted_body_fingerprint_and_exclusivity(self):
        source = self.root / 'body.hwp'
        source.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1') + b'fake-document')
        spec = {'path': source.name, 'expected_text': '가상 본문'}
        config = self.load(body_hwp=spec)
        self.assertEqual(config['body_hwp']['sha256'], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(plan(config)['steps'], ['title', 'body_hwp'])
        with self.assertRaises(ValueError): self.load(body_hwp=spec, body='text')
        with self.assertRaises(ValueError): self.load(body_hwp={'path': source.name})
        source.write_bytes(b'not-a-hwp-file')
        with self.assertRaises(ValueError): self.load(body_hwp=spec)

    def test_exact_recipient_and_approver_schema(self):
        with self.assertRaises(ValueError): self.load(recipient={'search': 'a'})
        with self.assertRaises(ValueError): self.load(approver={'name': 'x', 'send': True})
        self.assertEqual(self.load(approver={'name': '가상교사', 'id': 'mock-1'})['approver']['id'], 'mock-1')

    def test_auto_send_only_true(self):
        for value in (False, 'true', 1, None):
            with self.subTest(value=value), self.assertRaises(ValueError): self.load(auto_send=value)

    def test_explicit_disclosure_modes_and_reason_consistency(self):
        self.assertEqual(self.load(disclosure={'mode': 'partial', 'reasons': [6]})['disclosure']['mode'], 'partial')
        for disclosure in ({'mode': 'partial', 'reasons': []}, {'mode': 'public', 'reasons': [6]}, {'mode': 'private', 'reasons': [True]}, {'mode': 'private', 'reasons': [6, 6]}, {'mode': 'unknown', 'reasons': []}):
            with self.subTest(disclosure=disclosure), self.assertRaises(ValueError): self.load(disclosure=disclosure)
        with self.assertRaises(ValueError): self.load(disclosure={'mode': 'partial', 'reasons': [6]}, private_reasons=[6])

    def test_approval_route_roles_duplicates_and_conflicting_legacy_field(self):
        route = [{'name': '가상 연구부장', 'role': '검토'}, {'name': '가상 교장', 'role': '결재'}]
        self.assertIn('approval_route', plan(self.load(approval_route=route))['steps'])
        invalid = [[], [route[0]], [route[1], route[1]], [{'name': 'x', 'role': '검토'}, {'name': 'x', 'role': '결재'}]]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError): self.load(approval_route=value)
        with self.assertRaises(ValueError): self.load(approval_route=route, approver={'name': '가상 교장'})

    def test_approval_readback_uses_sequence_numbers_in_either_display_order(self):
        route = [{'name': '가상 부장', 'role': '검토'}, {'name': '가상 교장', 'role': '결재'}]
        rows = ['1기안교사기안자 대기', '2검토부장가상 부장 대기', '3결재교장가상 교장 대기']
        self.assertTrue(approval_route_matches(rows, route))
        self.assertTrue(approval_route_matches(list(reversed(rows)), route))
        offset = [str(int(row[0]) + 3) + row[1:] for row in rows]
        self.assertTrue(approval_route_matches(list(reversed(offset)), route))
        self.assertFalse(approval_route_matches([offset[0], offset[1], '7' + offset[2][1:]], route))
        for invalid in ([rows[0], rows[1], rows[1]], [rows[0], rows[1], '3검토교장가상 교장 대기'], [rows[0], '3검토부장가상 부장 대기', '2결재교장가상 교장 대기']):
            self.assertFalse(approval_route_matches(invalid, route))

    def test_recalled_dash_rows_only_allow_preconfirmation_parity(self):
        route = [{'name': '가상 부장', 'role': '검토'}, {'name': '가상 교장', 'role': '결재'}]
        rows = ['-기안교사기안자 대기', '-검토부장가상 부장 대기', '-결재교장가상 교장 대기']
        self.assertTrue(approval_route_review_matches(rows, route))
        self.assertTrue(approval_route_review_matches(list(reversed(rows)), route))
        self.assertFalse(approval_route_matches(rows, route))
        for invalid in (rows[:2], rows + [rows[0]],
                        [rows[0], rows[1], rows[1]],
                        [rows[0], rows[1], '-검토교장가상 교장 대기'],
                        [rows[0], rows[1], '-결재교장다른 사람 대기'],
                        ['1기안교사기안자 대기', *rows[1:]]):
            with self.subTest(invalid=invalid):
                self.assertFalse(approval_route_review_matches(invalid, route))

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
