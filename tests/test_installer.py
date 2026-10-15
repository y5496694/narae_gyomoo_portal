"""Install/update against isolated directories; never touch actual user skills."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe')
SKILLS = ('narae-gyomu-work-portal', 'narae-gyomu-neis', 'narae-gyomu-edufine', 'wxs-cli')


@unittest.skipUnless(POWERSHELL, 'Windows PowerShell is required')
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.skills = self.root / 'skills with spaces'

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, update=False):
        command = [POWERSHELL, '-NoProfile', '-NonInteractive', '-File', str(ROOT / 'install.ps1'),
                   '-SkillsDirectory', str(self.skills)]
        if update:
            command.append('-Update')
        return subprocess.run(command, capture_output=True)

    def assert_pack_matches(self):
        for name in SKILLS:
            for source in (ROOT / 'skills' / name).rglob('*'):
                if not source.is_file() or '__pycache__' in source.parts or source.suffix == '.pyc':
                    continue
                relative = source.relative_to(ROOT / 'skills' / name)
                self.assertEqual(source.read_bytes(), (self.skills / name / relative).read_bytes())

    def test_new_install_and_identical_repeat(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr.decode(errors='replace'))
        self.assert_pack_matches()
        self.assertFalse((self.skills / 'gyomunarae-neis-edufine').exists())
        repeated = self.install()
        self.assertEqual(repeated.returncode, 0, repeated.stderr.decode(errors='replace'))
        self.assertFalse((self.root / 'skill-backups').exists())

    def test_conflict_preflight_leaves_other_skills_uninstalled(self):
        target = self.skills / 'wxs-cli'
        target.mkdir(parents=True)
        (target / 'SKILL.md').write_text('user version', encoding='utf-8')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertEqual((target / 'SKILL.md').read_text(), 'user version')
        self.assertFalse((self.skills / SKILLS[0]).exists())

    def test_update_preserves_backup_and_extra_local_files(self):
        self.assertEqual(self.install().returncode, 0)
        changed = self.skills / 'wxs-cli/SKILL.md'
        changed.write_text('older local version', encoding='utf-8')
        extra = self.skills / 'wxs-cli/local-note.txt'
        extra.write_text('local note', encoding='utf-8')
        result = self.install(update=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assert_pack_matches()
        backups = list((self.root / 'skill-backups').glob('*/wxs-cli/SKILL.md'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'older local version')
        self.assertEqual(extra.read_text(), 'local note')
        self.assertFalse((self.skills / 'skill-backups').exists())

    def test_legacy_install_becomes_forwarding_guide_after_backup(self):
        legacy = self.skills / 'gyomunarae-neis-edufine'
        legacy.mkdir(parents=True)
        (legacy / 'SKILL.md').write_text('legacy guide', encoding='utf-8')
        self.assertNotEqual(self.install().returncode, 0)
        self.assertFalse((self.skills / SKILLS[0]).exists())
        updated = self.install(update=True)
        self.assertEqual(updated.returncode, 0, updated.stderr.decode(errors='replace'))
        self.assertEqual((legacy / 'SKILL.md').read_bytes(),
                         (ROOT / 'compat/gyomunarae-neis-edufine/SKILL.md').read_bytes())
        backup = list((self.root / 'skill-backups').glob('*/gyomunarae-neis-edufine/SKILL.md'))
        self.assertEqual(len(backup), 1)
        self.assertEqual(backup[0].read_text(), 'legacy guide')
