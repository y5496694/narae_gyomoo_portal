"""Decline stale autosave restore and editor replacement on one new blank draft."""
import re
from wxs_final import fingerprint
from wxs_route_notice import inspect_notices


def prepare(session, runtime):
    session.check_window()
    state = session.status()
    if (state.get('app_type') != 'sancgian' or state.get('processed') is not False
            or state.get('title') or state.get('hwp_title') or state.get('body')
            or state.get('attachments') or state.get('is_modified') is not False):
        raise ValueError('Expected a newly opened unchanged blank draft')
    notices = inspect_notices(session.window, runtime)['notices']
    for item in notices:
        message = item['message']
        restore = re.fullmatch(r'현재 서식의 자동저장문서가 존재합니다\.\s*\(마지막 저장: [^\r\n]{1,150}\)\s*자동저장문서를 읽어오시겠습니까\?', message)
        if (message != '열려있는 기안/결재기를 닫습니다.' and not restore) or item['buttons'] != ['확인', '취소']:
            raise ValueError('Unknown startup notice; preserved without response')
    binding = {'window': session.window, 'document': state, 'notices': notices}
    return {'ready': not notices and session.window.get('enabled', True), 'applied': False, 'fingerprint': fingerprint(binding), 'binding': binding}


def apply(session, runtime, expected):
    preview = prepare(session, runtime)
    if not expected or preview['fingerprint'] != expected:
        raise ValueError('Blank draft or startup notices changed')
    declined = []
    for item in preview['binding']['notices']:
        message, children = runtime.alert_details(item['window'])
        if message != item['message']:
            raise ValueError('Startup message changed')
        runtime.press_dialog_button(item['window'], children, '취소')
        declined.append(item['window']['hwnd'])
    return {'applied': True, 'declined': declined, 'restored_autosave': False,
            'existing_editor_preserved': True, 'submission': 'not_attempted'}
