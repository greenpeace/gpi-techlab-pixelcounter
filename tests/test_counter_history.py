from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask_wtf.csrf import CSRFProtect, generate_csrf

from system.counter_history import HISTORY_HOURS, history_enabled, hour_key, record_hour, usage_series

NOW = datetime(2026, 9, 18, 12, 35, tzinfo=timezone.utc)


def test_hourly_aggregation_retention_and_separate_amounts():
    old = hour_key(NOW.replace(minute=0) - timedelta(hours=HISTORY_HOURS))
    history = {old: {'uses': 99, 'amount': 99}}
    history = record_hour(history, 50, NOW)
    history = record_hour(history, 1, NOW + timedelta(minutes=2))
    assert old not in history
    assert history['2026-09-18T12:00:00Z'] == {'uses': 2, 'amount': 51}
    series = usage_series(history, 24, NOW)
    assert len(series) == 24
    assert series[-1]['amount'] == 51
    assert all(row['uses'] == 0 for row in series[:-1])


def test_storage_remains_bounded_and_reads_exclude_expired_history():
    history = {}
    for i in range(800):
        history = record_hour(history, 1, NOW + timedelta(hours=i))
    assert len(history) == HISTORY_HOURS
    later = NOW + timedelta(hours=1600)
    assert not any(row['uses'] for row in usage_series(history, 720, later))


@pytest.mark.parametrize('value, expected', [(None, False), ('false', False), ('off', False),
                                            (False, False), (True, True), ('on', True), ('true', True)])
def test_opt_in(value, expected):
    assert history_enabled(value) is expected


@pytest.fixture
def counter_module():
    with patch('google.cloud.logging.Client'):
        from modules.pixelcounter import pixelcounter
    return pixelcounter


@pytest.mark.parametrize('enabled', [True, False])
def test_count_and_history_share_transaction(counter_module, enabled):
    transaction = MagicMock()
    ref = MagicMock()
    ref.get.return_value.to_dict.return_value = {'history_enabled': enabled, 'count': 200}
    assert counter_module._increment_counter_transaction.to_wrap(transaction, ref, 25)
    updates = transaction.update.call_args.args[1]
    assert updates['count'].value == 25
    assert 'last_count_at' in updates
    assert ('history_hours' in updates) is enabled
    if enabled:
        assert list(updates['history_hours'].values()) == [{'uses': 1, 'amount': 25}]
    ref.get.assert_called_once_with(transaction=transaction)
    transaction.update.assert_called_once()


@pytest.fixture
def usage_app(counter_module):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    CSRFProtect(app)
    # Exercise the actual resource authorization and CSRF handling independently
    # of the application's external identity provider.
    app.add_url_rule('/usage/<counter_id>', view_func=counter_module.counter_usage.__wrapped__)
    app.add_url_rule('/clear/<counter_id>', view_func=counter_module.clear_counter_usage.__wrapped__, methods=['POST'])
    app.add_url_rule('/csrf', view_func=lambda: {'token': generate_csrf()})
    return app


def test_usage_global_visible_but_clear_requires_management(counter_module, usage_app):
    ref = MagicMock()
    ref.get.return_value.to_dict.return_value = {'type': 'global', 'name': 'campaign', 'count': 99}
    with patch.object(counter_module, 'counter_ref') as counters, \
            patch('system.authorization.get_user_data_from_token', return_value={'google_id': 'other'}):
        counters.document.return_value = ref
        client = usage_app.test_client()
        response = client.get('/usage/campaign?hours=24')
        assert response.status_code == 200
        assert response.json['enabled'] is False
        assert response.json['can_manage'] is False
        assert response.headers['Cache-Control'] == 'no-store'
        token = client.get('/csrf').json['token']
        assert client.post('/clear/campaign', headers={'X-CSRFToken': token}).status_code == 403
        ref.update.assert_not_called()
        ref.get.return_value.to_dict.return_value = {'type': 'local', 'uuid': 'owner'}
        assert client.get('/usage/campaign').status_code == 403


def test_clear_preserves_count_and_toggle_and_requires_csrf(counter_module, usage_app):
    ref = MagicMock()
    ref.get.return_value.to_dict.return_value = {'uuid': 'owner', 'count': 55, 'history_enabled': True}
    with patch.object(counter_module, 'counter_ref') as counters, \
            patch.object(counter_module, 'log_activity'), \
            patch('system.authorization.get_user_data_from_token', return_value={'google_id': 'owner'}):
        counters.document.return_value = ref
        client = usage_app.test_client()
        assert client.post('/clear/campaign').status_code == 400
        ref.update.assert_not_called()
        token = client.get('/csrf').json['token']
        assert client.post('/clear/campaign', headers={'X-CSRFToken': token}).status_code == 200
        ref.update.assert_called_once_with({'history_hours': {}})
        for hours in ('no', '-1', '100000'):
            assert client.get('/usage/campaign?hours=' + hours).status_code == 400
        ref.get.return_value.exists = False
        assert client.get('/usage/missing').status_code == 404


def test_duplicate_and_rejected_requests_do_not_record_activity(counter_module):
    app = Flask(__name__)
    with app.test_request_context('/count?id=test'), \
            patch.object(counter_module, 'get_request_context', return_value=('', '', '', '')), \
            patch.object(counter_module, 'is_allowed_request', return_value=(True, None)), \
            patch.object(counter_module, 'process_email_hash', return_value=('duplicate', 'already counted')), \
            patch.object(counter_module, 'increment_counter') as increment:
        assert counter_module.handle_count_request()[1] == 200
        increment.assert_not_called()
    with app.test_request_context('/count?id=test'), \
            patch.object(counter_module, 'get_request_context', return_value=('', '', '', '')), \
            patch.object(counter_module, 'is_allowed_request', return_value=(False, 'blocked')), \
            patch.object(counter_module, 'increment_counter') as increment:
        assert counter_module.handle_count_request()[1] == 400
        increment.assert_not_called()


def test_setup_and_edit_persist_switch(counter_module):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    app.add_url_rule('/list', endpoint='pixelcounterblue.read', view_func=lambda: '')
    app.add_url_rule('/addlist', endpoint='pixelcounterblue.addlist', view_func=lambda: '')
    app.add_url_rule('/edit', endpoint='pixelcounterblue.listedit', view_func=lambda: '')
    app.add_url_rule('/create', view_func=counter_module.createlist.__wrapped__, methods=['POST'])
    app.add_url_rule('/update', view_func=counter_module.updateform.__wrapped__, methods=['POST'])
    with patch.object(counter_module, 'counter_ref') as counters, \
            patch.object(counter_module, 'log_activity'), \
            patch.object(counter_module, 'get_user_data_from_token', return_value={'google_id': 'owner'}), \
            patch('system.authorization.get_user_data_from_token', return_value={'google_id': 'owner'}):
        counters.where.return_value.get.return_value = []
        ref = counters.document.return_value
        ref.get.return_value.to_dict.return_value = {'uuid': 'owner', 'history_enabled': True}
        client = app.test_client()
        for enabled in (True, False):
            payload = {'name': 'campaign', 'count': '10', 'id': 'campaign'}
            if enabled:
                payload['history_enabled'] = 'on'
            assert client.post('/create', data=payload).status_code == 302
            assert ref.create.call_args.args[0]['history_enabled'] is enabled
            assert client.post('/update', data=payload).status_code == 302
            assert ref.update.call_args.args[0]['history_enabled'] is enabled
            assert 'history_hours' not in ref.update.call_args.args[0]
