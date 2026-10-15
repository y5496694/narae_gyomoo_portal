"""Offline package integrity and portability checks."""
import ast
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class PackTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self):
        for doc in ROOT.rglob('*.md'):
            text = doc.read_text(encoding='utf-8-sig')
            for target in re.findall(r'\]\(([^)]+)\)', text):
                parsed = urlsplit(target)
                if parsed.scheme or target.startswith('#'):
                    continue
                self.assertTrue((doc.parent / unquote(parsed.path)).is_file(), f'{doc.relative_to(ROOT)} -> {target}')

    def test_skill_names_match_folders_and_have_descriptions(self):
        skills = list((ROOT / 'skills').glob('*/SKILL.md'))
        self.assertEqual(len(skills), 4)
        for doc in skills + list((ROOT / 'compat').glob('*/SKILL.md')):
            text = doc.read_text(encoding='utf-8-sig')
            self.assertTrue(text.startswith('---\n'))
            front = text.split('---', 2)[1]
            name = re.search(r'^name: (.+)$', front, re.M).group(1)
            self.assertEqual(name, doc.parent.name)
            self.assertRegex(name, r'^[a-z0-9-]{1,63}$')
            self.assertRegex(front, r'(?m)^description: ".+"$')
            self.assertTrue((doc.parent / 'agents/openai.yaml').is_file())

    def test_python_sources_parse_without_live_imports(self):
        for source in ROOT.rglob('*.py'):
            ast.parse(source.read_text(encoding='utf-8-sig'), filename=str(source.relative_to(ROOT)))

    def test_public_default_region_and_sample_are_portable(self):
        config = json.loads((ROOT / 'skills/narae-gyomu-work-portal/references/portal.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(set(config), {'region', 'portal_url'})
        self.assertEqual(config['region'], '충북')
        self.assertEqual(urlsplit(config['portal_url']).hostname, 'cbe.eduptl.kr')
        sample = json.loads((ROOT / 'examples/wxs-draft.sample.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(sample['attachments'], [])
        self.assertNotIn('save_name', sample)
        for file in ROOT.rglob('*'):
            if not file.is_file() or '__pycache__' in file.parts:
                continue
            self.assertNotIn(b'C:\\Users\\USER', file.read_bytes(), str(file.relative_to(ROOT)))
