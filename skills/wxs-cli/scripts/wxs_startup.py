"""Decline stale autosave restore and editor replacement on one new blank draft."""
import re
import time
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


def task_readback(window, expected_title, task_card, create_session, pause=time.sleep):
    """Task selection can reload MSHTML. Rebind for reads, never select again."""
    for attempt in range(20):
        try:
            state = create_session(window).status()
        except Exception as error:
            if (getattr(error, 'hresult', None) != -2147024891 and
                    not any(text in str(error) for text in ('Expected one editor1 HwpCtrl', 'Selected WXS page navigated'))):
                raise
        else:
            if (state.get('title') != expected_title or state.get('app_type') != 'sancgian'
                    or state.get('processed') is not False):
                raise ValueError('Task selection returned a different document')
            if task_card in state.get('task_card', ''):
                return state
        if attempt < 19:
            pause(.2)
    raise ValueError('Task selection was attempted; readback is unconfirmed. Do not select again.')


def select_task_once(session, dialog, expected_title, task_card, create_session):
    """The zero-delay close can invalidate the action's COM acknowledgment.

    A missing acknowledgment never repeats selection. Only closure and a fresh
    read of the exact same draft can establish the requested resulting state.
    """
    acknowledgment_lost = False
    try:
        session.action('task_select', {'name': task_card}, dialog['root'])
    except Exception as error:
        if getattr(error, 'hresult', None) != -2147024891:
            raise
        acknowledgment_lost = True
    session.wait_closed(dialog['window'])
    state = task_readback(session.window, expected_title, task_card, create_session)
    return {'applied': True, 'status': state,
            'acknowledgment_lost': acknowledgment_lost, 'selection_attempts': 1}
