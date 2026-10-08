import inspect
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict

from test_counter_history import counter_module


@pytest.mark.parametrize('value,expected', [(None, True), (True, True), (False, False),
    ('true', True), ('false', False), ('', True), (0, True)])
def test_default_is_enabled(counter_module, value, expected):
    assert counter_module.allowed_list_check_enabled(value) is expected


@pytest.mark.parametrize('enabled', [True, False])
@pytest.mark.parametrize('path,blocked', [('/thanks', False), ('/preview/thanks', True)])
def test_only_allowed_list_is_bypassed(counter_module, enabled, path, blocked):
    app = Flask(__name__)
    pattern = MagicMock()
    pattern.to_dict.return_value = {'pattern': '/preview'}
    with app.test_request_context('/count'), \
            patch.object(counter_module, 'allowedorigion_ref') as allowed, \
            patch.object(counter_module, 'disallowedorigion_ref') as denied:
        allowed.stream.return_value = []
        denied.stream.return_value = [pattern]
        result, _ = counter_module.is_allowed_request('other.org', '192.0.2.1', path, enabled)
        assert result is (not enabled and not blocked)
        if not enabled:
            allowed.stream.assert_not_called()


@pytest.mark.parametrize('stored,expected', [({}, 400), ({'allowed_list_check_enabled': True}, 400),
    ({'allowed_list_check_enabled': False}, 200), ({'whitelist_check_enabled': False}, 200)])
@pytest.mark.parametrize('referer', [None, 'https://other.org/thanks'])
def test_handler_uses_saved_setting(counter_module, stored, expected, referer):
    app = Flask(__name__)
    headers = {'Referer': referer} if referer else {}
    with app.test_request_context('/count?id=test&allowed_list_check_enabled=false', headers=headers), \
            patch.object(counter_module, 'counter_ref') as counters, \
            patch.object(counter_module, 'allowedorigion_ref') as allowed, \
            patch.object(counter_module, 'disallowedorigion_ref') as denied, \
            patch.object(counter_module, 'process_email_hash', return_value=('ok', None)), \
            patch.object(counter_module, 'increment_counter', return_value=True) as increment:
        doc = MagicMock()
        doc.to_dict.return_value = stored
        counters.where.return_value.limit.return_value.get.return_value = [doc]
        allowed.stream.return_value = denied.stream.return_value = []
        assert counter_module.handle_count_request()[1] == expected
        assert increment.called is (expected == 200)


@pytest.mark.parametrize('query,status,result', [
    ('donation=0', None, 422), ('donation=1000001', None, 422),
    ('email_hash=bad', ('invalid_hash', 'invalid'), 422),
    ('email_hash=duplicate', ('duplicate', 'duplicate'), 200),
    ('', ('invalid_counter', 'missing'), 404),
])
def test_other_checks_remain(counter_module, query, status, result):
    app = Flask(__name__)
    with app.test_request_context('/count?id=test&' + query), \
            patch.object(counter_module, 'counter_ref') as counters, \
            patch.object(counter_module, 'disallowedorigion_ref') as denied, \
            patch.object(counter_module, 'process_email_hash', return_value=status), \
            patch.object(counter_module, 'increment_counter') as increment:
        doc = MagicMock()
        doc.to_dict.return_value = {'allowed_list_check_enabled': False}
        counters.where.return_value.limit.return_value.get.return_value = [doc]
        denied.stream.return_value = []
        assert counter_module.handle_count_request()[1] == result
        increment.assert_not_called()


@pytest.mark.parametrize('handler', ['create', 'createset', 'createlist', 'create_counter', 'update', 'updateform'])
@pytest.mark.parametrize('setting', [None, True, False])
def test_all_writes_persist_setting(counter_module, handler, setting):
    app = Flask(__name__)
    app.secret_key = 'test'
    for endpoint in ('read', 'addlist', 'listedit'):
        app.add_url_rule('/' + endpoint, endpoint='pixelcounterblue.' + endpoint, view_func=lambda: '')
    app.add_url_rule('/save', view_func=inspect.unwrap(getattr(counter_module, handler)), methods=['POST'])
    payload = {'name': 'test', 'id': 'test', 'count': 0}
    if setting is not None:
        payload['allowed_list_check_enabled'] = setting
    kwargs = {'json': payload}
    if handler in ('createlist', 'updateform'):
        form = MultiDict(payload)
        form.pop('allowed_list_check_enabled', None)
        if setting is True:
            form.add('allowed_list_check_enabled', 'true')
        if setting is not None:
            form.add('allowed_list_check_enabled', 'false')
        kwargs = {'data': form}
    with patch.object(counter_module, 'counter_ref') as counters, \
            patch.object(counter_module, 'log_activity'), \
            patch.object(counter_module, 'get_user_data_from_token', return_value={'google_id': 'owner'}), \
            patch('system.authorization.get_user_data_from_token', return_value={'google_id': 'owner'}):
        counters.where.return_value.get.return_value = []
        counters.where.return_value.limit.return_value.get.return_value = []
        ref = counters.document.return_value
        ref.get.return_value.to_dict.return_value = {'uuid': 'owner'}
        response = app.test_client().post('/save', **kwargs)
        assert response.status_code in (200, 201, 302), response.data
        write = ref.update if handler in ('update', 'updateform') else ref.create
        saved = write.call_args.args[0]
        if handler == 'update' and setting is None:
            assert 'allowed_list_check_enabled' not in saved
        else:
            assert saved['allowed_list_check_enabled'] is (setting is not False)


@pytest.mark.parametrize('enabled', [True, False])
def test_api_key_override_still_blocks_patterns(counter_module, enabled):
    app = Flask(__name__)
    pattern = MagicMock()
    pattern.to_dict.return_value = {'pattern': '/preview'}
    with app.test_request_context('/count', headers={'X-API-Key': 'test'}), \
            patch.object(counter_module, 'allowedorigion_ref') as allowed, \
            patch.object(counter_module, 'disallowedorigion_ref') as denied, \
            patch.object(counter_module, 'validate_api_key', return_value=(True, None)):
        allowed.stream.return_value = []
        denied.stream.return_value = [pattern]
        assert counter_module.is_allowed_request('other.org', '192.0.2.1', '/thanks', enabled)[0]
        assert not counter_module.is_allowed_request('other.org', '192.0.2.1', '/preview', enabled)[0]


@pytest.mark.parametrize('record,checked', [({}, True), ({'allowed_list_check_enabled': True}, True),
    ({'allowed_list_check_enabled': False}, False)])
def test_edit_switch_reflects_saved_default(record, checked):
    from pathlib import Path
    from jinja2 import Template
    source = Path('modules/pixelcounter/templates/listedit.html').read_text()
    start = source.index('    <div class="form-check form-switch mb-3">')
    end = source.index('    <div class="form-check form-switch my-3">', start)
    rendered = Template(source[start:end]).render(ngo=record)
    assert ('checked' in rendered) is checked


@pytest.mark.parametrize('record,expected', [
    ({}, True),
    ({'whitelist_check_enabled': False}, False),
    ({'whitelist_check_enabled': True}, True),
    ({'whitelist_check_enabled': False, 'allowed_list_check_enabled': True}, True),
    ({'whitelist_check_enabled': True, 'allowed_list_check_enabled': False}, False),
])
def test_saved_older_settings_and_current_field_precedence(counter_module, record, expected):
    assert counter_module.counter_allowed_list_enabled(record) is expected
