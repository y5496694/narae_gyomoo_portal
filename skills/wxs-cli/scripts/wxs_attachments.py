"""Stage exact local replacements through the observed native attachment edit map."""
import hashlib
import json
from pathlib import Path

from wxs_config import verify_attachment
from wxs_final import fingerprint


def load_sources(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if set(data) != {'expected_title', 'files'} or not isinstance(data['expected_title'], str) or not data['expected_title']:
        raise ValueError('Replacement config requires only expected_title and files')
    if not isinstance(data['files'], list) or not data['files']:
        raise ValueError('Expected a nonempty attachment source list')
    files = []
    for item in data['files']:
        if not isinstance(item, dict) or set(item) != {'id', 'name', 'path'} or any(not isinstance(item[k], str) or not item[k] for k in item):
            raise ValueError('Each replacement needs exact id, name and local path')
        source = (path.parent / item['path']).resolve()
        if source.name != item['name'] or not source.is_file() or not 0 < source.stat().st_size <= 32 * 1024 * 1024:
            raise ValueError('Expected a bounded existing source with the same attachment name')
        if item['id'] in [f['id'] for f in files] or item['name'] in [f['name'] for f in files]:
            raise ValueError('Duplicate attachment identity')
        files.append({**item, 'path': str(source), 'size': source.stat().st_size,
                      'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    return data['expected_title'], files


def prepare(session, title, sources):
    state = session.require_draft(title)
    current = session.action('attachment_staging_status')
    if not current['native_modified_upload'] or len(current['files']) != len(sources):
        raise ValueError('Expected the observed native modified-file upload branch and exact file count')
    for old, new in zip(current['files'], sources):
        verify_attachment(new)
        if not old['at_sancbox'] or old['staged'] is not None or old['id'] != new['id'] or old['name'] != new['name']:
            raise ValueError('Existing attachment identity/order differs or replacement is already staged')
    binding = {'document': state, 'current': current, 'sources': sources}
    return {'applied': False, 'fingerprint': fingerprint(binding), 'binding': binding}


def apply(session, title, sources, expected_fingerprint):
    preview = prepare(session, title, sources)
    if not expected_fingerprint or preview['fingerprint'] != expected_fingerprint:
        raise ValueError('Document, current attachments or local source changed')
    for source in sources:
        verify_attachment(source)
    staged = session.action('attachment_stage_replacements', {'expected': preview['binding']['current']['files'], 'files': sources})
    if len(staged['files']) != len(sources):
        raise ValueError('Partial staging may remain; inspect before retrying')
    for actual, source in zip(staged['files'], sources):
        value = actual['staged']
        if not value or value['key'] != source['id'] or value['fileName'] != source['name'] or value['filePath'] != source['path'] or value['size'] != source['size'] or not value['flag']:
            raise ValueError('Partial staging may remain; inspect before retrying')
    if session.require_draft(title) != preview['binding']['document']:
        raise ValueError('Document metadata changed during attachment staging; inspect before continuing')
    return {'applied': True, 'staged': staged, 'sources': sources, 'server_uploaded': False,
            'next': 'Native save/submit must upload these bytes; reopen and download every server attachment and compare hashes'}
