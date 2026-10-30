"""Acknowledge only the observed informational absence notice for an existing route."""
from wxs_final import fingerprint


def inspect_notices(window, runtime):
    """Read same-process native messages without accepting any of them."""
    notices = []
    for notice in runtime.process_windows(window['pid']):
        if notice['title'] != '웹 페이지 메시지':
            continue
        message, children = runtime.alert_details(notice)
        notices.append({'window': notice, 'message': message,
                        'buttons': [item.get('text', '') for item in children if item.get('class') == 'Button']})
    return {'window': window, 'notices': notices, 'acknowledged': False, 'untrusted': True}


def cancel_editor_switch(session, expected_title, runtime):
    """Cancel only the exact switch-editor prompt, preserving the active editor."""
    session.check_window()
    state = session.status()
    if state.get('title') != expected_title or state.get('hwp_title') != expected_title or state.get('is_modified') is not False:
        raise ValueError('Expected the same unchanged newly opened document')
    notices = inspect_notices(session.window, runtime)['notices']
    if len(notices) != 1 or notices[0]['message'] != '열려있는 기안/결재기를 닫습니다.' or notices[0]['buttons'] != ['확인', '취소']:
        raise ValueError('Expected the exact editor-switch prompt; no other dialog cancelled')
    message, children = runtime.alert_details(notices[0]['window'])
    if message != notices[0]['message']:
        raise ValueError('Editor-switch notice changed')
    runtime.press_dialog_button(notices[0]['window'], children, '취소')
    return {'cancelled': True, 'existing_editor_preserved': True, 'submission': 'not_attempted'}


def read_notice(session, expected_title, expected_message, runtime, expected_fingerprint=None, apply=False):
    """Acknowledge only the known content-change information on a read-only view."""
    session.check_window()
    state = session.status()
    known = '기안자에 의해 문서 내용이 변경되었습니다. 이력보기 버튼을 통해 확인하시기 바랍니다'
    if (expected_message != known or state.get('app_type') != 'sancview' or
            state.get('title') != expected_title or state.get('hwp_title') != expected_title or
            state.get('edit_mode') != 0 or state.get('is_modified') is not False or session.frame_errors):
        raise ValueError('Expected the same unchanged read-only document and known informational message')
    observed = inspect_notices(session.window, runtime)['notices']
    if len(observed) != 1 or observed[0]['message'] != known or observed[0]['buttons'] != ['확인']:
        raise ValueError('Expected one exact content-change notice with one confirmation button')
    binding = {'window': session.window, 'document': state, 'notice': observed[0]}
    preview = {'applied': False, 'fingerprint': fingerprint(binding), 'binding': binding}
    if not apply:
        return preview
    if not expected_fingerprint or preview['fingerprint'] != expected_fingerprint:
        raise ValueError('Document or informational notice changed')
    notice = observed[0]['window']
    message, children = runtime.alert_details(notice)
    if message != known:
        raise ValueError('Native notice changed')
    runtime.press_dialog_button(notice, children, '확인')
    return {'acknowledged': True, 'document_changed': False, 'submission': 'not_attempted', 'message': known}


def prepare(session, expected_title, expected_person, expected_message, runtime):
    session.check_window()
    state = session.status()
    if state.get('app_type') != 'sancgian' or state.get('processed') is not False or state.get('edit_mode') != 2 or state.get('title') != expected_title:
        raise ValueError('Expected the same editable draft')
    expected = ('결재경로에 있는 [' + expected_person + '] 사용자가 현재 부재중입니다.\n'
                '대리결재자를 지정하시려면, 현재 부재중인 사용자를 결재경로에서 삭제 후, 조직도에서 다시 추가하여 주시기 바랍니다.')
    if not expected_person or expected_message != expected or not any(expected_person in row for row in state.get('approval_rows', [])):
        raise ValueError('Notice must name an existing route participant and match the observed informational text')
    alerts = [item for item in runtime.process_windows(session.window['pid']) if item['title'] == '웹 페이지 메시지']
    if len(alerts) != 1:
        raise ValueError('Expected one native informational notice')
    message, children = runtime.alert_details(alerts[0])
    if message != expected:
        raise ValueError('Native notice differs; preserved without acknowledgement')
    buttons = [item for item in children if item.get('class') == 'Button' and item.get('text', '').replace('&', '').strip() == '확인']
    if len(buttons) != 1:
        raise ValueError('Expected one observed confirmation button')
    binding = {'window': session.window, 'document': state, 'notice': alerts[0], 'message': message, 'button': buttons[0]}
    return {'applied': False, 'fingerprint': fingerprint(binding), 'binding': binding}


def acknowledge(session, expected_title, expected_person, expected_message, expected_fingerprint, runtime):
    preview = prepare(session, expected_title, expected_person, expected_message, runtime)
    if not expected_fingerprint or preview['fingerprint'] != expected_fingerprint:
        raise ValueError('Document or informational notice changed')
    notice = preview['binding']['notice']
    message, children = runtime.alert_details(notice)
    if message != expected_message:
        raise ValueError('Native notice changed')
    runtime.press_dialog_button(notice, children, '확인')
    return {'acknowledged': True, 'participant': expected_person, 'route_changed': False,
            'submission': 'not_attempted', 'message': expected_message}
