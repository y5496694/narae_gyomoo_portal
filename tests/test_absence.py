import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'skills/wxs-cli/scripts'))
import wxs_absence


def page():
    return {'url': {'location': 'https://example.invalid/retrieveAbsnceCoursInfo.do'},
            'title': '부재자 결재선',
            'text': '* 부재자 가상교장 * 부재자결재직위 교장 * 부재사유 출장 부재자가 복귀 후 결재처리',
            'controls': [{'id': f'absentRdo{i}', 'type': 'radio', 'value': str(i), 'checked': i == 3} for i in range(1, 5)],
            'links': [{'id': '', 'label': '확인'}]}


class AbsenceTests(unittest.TestCase):
    def test_identity_options_and_confirmation_are_required(self):
        for change in ('identity', 'radio', 'links', 'route'):
            current = page()
            if change == 'identity': current['text'] = current['text'].replace('가상교장', '다른 사람')
            if change == 'radio': current['controls'][1]['value'] = '3'
            if change == 'links': current['links'].append({'id': '', 'label': '확인'})
            if change == 'route': current['url']['location'] = 'https://example.invalid/other.do'
            with self.subTest(change=change), self.assertRaises(ValueError):
                wxs_absence.preview_state(current, '가상교장', '교장')

    def test_changed_preview_cannot_click_and_original_approver_is_preserved(self):
        current, calls, exists = page(), [], [True]
        radio, button = SimpleNamespace(checked=False), SimpleNamespace(innerText='확인')
        doc = SimpleNamespace(links=[button])
        def call(obj, method, *args):
            calls.append(method)
            if method == 'getElementById':
                self.assertEqual(args, ('absentRdo2',))
                return radio
            self.assertEqual(method, 'click')
            if obj is radio: radio.checked = True
            else:
                self.assertIs(obj, button)
                exists[0] = False
        native = SimpleNamespace(documents=lambda w: ([((), doc)], []), inspect=lambda docs: {'pages': [current]},
                                 call=call, items=iter, win32gui=SimpleNamespace(IsWindow=lambda hwnd: exists[0]))
        with self.assertRaises(ValueError):
            wxs_absence.run({'hwnd': 1}, '가상교장', '교장', True, 'changed', native)
        self.assertFalse(calls)
        preview = wxs_absence.preview_state(current, '가상교장', '교장')
        result = wxs_absence.run({'hwnd': 1}, '가상교장', '교장', True, preview['fingerprint'], native)
        self.assertEqual(result['mode'], 'after-return')
        self.assertTrue(result['dialog_closed'])
        self.assertEqual(calls, ['getElementById', 'click', 'click'])
