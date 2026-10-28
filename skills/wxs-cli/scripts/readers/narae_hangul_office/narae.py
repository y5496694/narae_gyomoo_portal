"""Locate the installed Narae Hangul Office CLI; never use the retired engine."""
import json
import os
from pathlib import Path
import subprocess
import sys


def office_root():
    configured = os.environ.get('NARAE_OFFICE_ROOT')
    if configured:
        candidates = [Path(configured)]
    else:
        configs = [Path(__file__).resolve().parents[1] / 'runtime.json',
                   Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'skills/narae-hangul-office/runtime.json']
        registered = []
        for config in configs:
            if config.is_file():
                saved = json.loads(config.read_text(encoding='utf-8-sig')).get('officeRoot')
                if saved:
                    registered.append(Path(saved))
        candidates = [*registered,
                      Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Programs/NaraeHangulOffice',
                      *Path(__file__).resolve().parents]
    for root in candidates:
        if (root / 'src/cli.cjs').is_file() and (root / 'package.json').is_file():
            return root
    raise ValueError('나래 한글 오피스 설치.cmd를 실행하세요. 별도 설치 위치는 NARAE_OFFICE_ROOT로 지정합니다.')


def main():
    try:
        root = office_root()
        node = root / 'runtime/node/node.exe'
        if not node.is_file():
            import shutil
            found = shutil.which('node')
            if not found:
                raise ValueError('앱 Node 런타임이 없습니다. 설치.cmd를 실행하세요.')
            node = Path(found)
        return subprocess.run([str(node), str(root / 'src/cli.cjs'), *sys.argv[1:]],
                              creationflags=0x08000000 if os.name == 'nt' else 0).returncode
    except (ValueError, OSError) as error:
        print(json.dumps({'success': False, 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
