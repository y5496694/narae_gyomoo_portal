import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/wxs-cli/scripts'))
from wxs_attachments import load_sources, prepare, apply


class AttachmentReplacementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'synthetic.pdf').write_bytes(b'synthetic source')
        self.config = self.root / 'sources.json'
        self.config.write_text(json.dumps({'expected_title': 'Synthetic recalled draft', 'files': [
            {'id': 'synthetic-id', 'name': 'synthetic.pdf', 'path': 'synthetic.pdf'}]}), encoding='utf-8')
        self.title, self.sources = load_sources(self.config)
        self.current = {'native_modified_upload': True, 'files': [{'id': 'synthetic-id', 'name': 'synthetic.pdf',
            'size': 16, 'at_sancbox': True, 'path': 'synthetic remote', 'staged': None}]}
        self.session = Mock()
        self.session.require_draft.return_value = {'title': self.title, 'body': 'Protected body', 'private_reasons': [6]}
        def action(name, params=None):
            if name == 'attachment_staging_status':
                return copy.deepcopy(self.current)
            self.assertEqual(name, 'attachment_stage_replacements')
            self.assertEqual(params['expected'], self.current['files'])
            staged = copy.deepcopy(self.current)
            source = self.sources[0]
            staged['files'][0]['staged'] = dict(key=source['id'], fileName=source['name'],
                filePath=source['path'], size=source['size'], flag=True, lastModifiedDate=1)
            return staged
        self.session.action.side_effect = action

    def test_exact_replacement_stages_without_claiming_server_upload(self):
        preview = prepare(self.session, self.title, self.sources)
        result = apply(self.session, self.title, self.sources, preview['fingerprint'])
        self.assertTrue(result['applied'])
        self.assertFalse(result['server_uploaded'])
        self.assertEqual([call.args[0] for call in self.session.action.call_args_list].count('attachment_stage_replacements'), 1)

    def test_changed_source_document_identity_and_preexisting_edits_never_stage(self):
        for issue in ('source', 'document', 'id', 'name', 'order-count', 'staged', 'native', 'fingerprint'):
            with self.subTest(issue=issue):
                self.setUp()
                preview = prepare(self.session, self.title, self.sources)
                self.session.action.reset_mock()
                if issue == 'source': (self.root / 'synthetic.pdf').write_bytes(b'changed---source')
                if issue == 'document': self.session.require_draft.return_value['body'] = 'Changed'
                if issue == 'id': self.current['files'][0]['id'] = 'other'
                if issue == 'name': self.current['files'][0]['name'] = 'other.pdf'
                if issue == 'order-count': self.current['files'].append(copy.deepcopy(self.current['files'][0]))
                if issue == 'staged': self.current['files'][0]['staged'] = {'flag': True}
                if issue == 'native': self.current['native_modified_upload'] = False
                with self.assertRaises(ValueError):
                    apply(self.session, self.title, self.sources, 'wrong' if issue == 'fingerprint' else preview['fingerprint'])
                self.assertNotIn('attachment_stage_replacements', [call.args[0] for call in self.session.action.call_args_list])

    def test_config_rejects_extra_actions_and_duplicate_id(self):
        data = json.loads(self.config.read_text())
        data['submit'] = True
        self.config.write_text(json.dumps(data))
        with self.assertRaises(ValueError): load_sources(self.config)
        del data['submit']
        data['files'].append(data['files'][0])
        self.config.write_text(json.dumps(data))
        with self.assertRaises(ValueError): load_sources(self.config)


if __name__ == '__main__':
    unittest.main()
