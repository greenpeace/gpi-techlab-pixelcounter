from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import AlreadyExists

from system.email_hash import normalize_email_hash, historical_hash_values
from test_counter_history import counter_module

OLD = 'zn+946yDl9gbgfnXoMO6gCKSCGKPJtsME5NN2KXhIaU='
NEW = 'zn-946yDl9gbgfnXoMO6gCKSCGKPJtsME5NN2KXhIaU'


@pytest.mark.parametrize('value', [OLD, OLD.replace('+', ' '), NEW + '=', NEW])
def test_legacy_normalizes_equivalent_values(value):
    assert normalize_email_hash(value, 'legacy') == NEW


@pytest.mark.parametrize('value', [OLD, OLD.replace('+', ' '), NEW + '='])
def test_strict_rejects_old_format(value):
    assert normalize_email_hash(value, 'strict') is None


@pytest.mark.parametrize('mode', ['strict', 'legacy'])
@pytest.mark.parametrize('value', ['short', 'a' * 129, 'a' * 16 + '===', 'a' * 16 + '\n', 'a' * 16 + '%', '=aaaaaaaaaaaaaaaa'])
def test_invalid_values_still_rejected(mode, value):
    assert normalize_email_hash(value, mode) is None


def test_historical_variants_include_padding_slashes_and_decoded_plus():
    values = historical_hash_values('abcdefghijklmno-_')
    assert 'abcdefghijklmno+/==' in values
    assert 'abcdefghijklmno /==' in values
    assert 'abcdefghijklmno-_' in values
    assert len(values) <= 9


@pytest.mark.parametrize('mode,value,expected', [(None, OLD, 'ok'), ('legacy', OLD, 'ok'),
    ('strict', OLD, 'invalid_hash'), ('strict', NEW, 'ok')])
def test_saved_mode_controls_validation(counter_module, mode, value, expected):
    with patch.object(counter_module, 'counter_ref') as counters, patch.object(counter_module, 'emailhash_ref') as hashes:
        doc = MagicMock()
        doc.to_dict.return_value = {} if mode is None else {'email_hash_mode': mode}
        counters.where.return_value.limit.return_value.get.return_value = [doc]
        hashes.where.return_value.where.return_value.limit.return_value.get.return_value = []
        assert counter_module.process_email_hash('petition', value)[0] == expected
        if expected == 'ok':
            assert hashes.document.return_value.create.call_args.args[0]['email_hash'] == NEW
        else:
            hashes.document.assert_not_called()


@pytest.mark.parametrize('mode,value', [('legacy', OLD), ('legacy', NEW), ('strict', NEW)])
def test_historical_duplicates_are_not_written(counter_module, mode, value):
    with patch.object(counter_module, 'counter_ref') as counters, patch.object(counter_module, 'emailhash_ref') as hashes:
        doc = MagicMock()
        doc.to_dict.return_value = {'email_hash_mode': mode}
        counters.where.return_value.limit.return_value.get.return_value = [doc]
        hashes.where.return_value.where.return_value.limit.return_value.get.return_value = [MagicMock()]
        assert counter_module.process_email_hash('petition', value)[0] == 'duplicate'
        hashes.where.assert_called_once_with('name', '==', 'petition')
        variants = hashes.where.return_value.where.call_args.args[2]
        assert OLD in variants and NEW in variants and OLD.replace('+', ' ') in variants
        hashes.document.assert_not_called()


def test_equivalent_requests_share_atomic_document_id(counter_module):
    with patch.object(counter_module, 'counter_ref') as counters, patch.object(counter_module, 'emailhash_ref') as hashes:
        doc = MagicMock()
        doc.to_dict.return_value = {}
        counters.where.return_value.limit.return_value.get.return_value = [doc]
        hashes.where.return_value.where.return_value.limit.return_value.get.return_value = []
        assert counter_module.process_email_hash('petition', OLD)[0] == 'ok'
        first_id = hashes.document.call_args.args[0]
        hashes.document.return_value.create.side_effect = AlreadyExists('already counted')
        assert counter_module.process_email_hash('petition', NEW)[0] == 'duplicate'
        assert hashes.document.call_args.args[0] == first_id


@pytest.mark.parametrize('handler', ['create', 'createset', 'createlist', 'create_counter', 'update', 'updateform'])
@pytest.mark.parametrize('mode', [None, 'strict', 'legacy'])
def test_mode_persisted_on_all_write_routes(counter_module, handler, mode):
    import inspect
    from flask import Flask
    app = Flask(__name__)
    app.secret_key = 'test'
    for endpoint in ('read', 'addlist', 'listedit'):
        app.add_url_rule('/' + endpoint, endpoint='pixelcounterblue.' + endpoint, view_func=lambda: '')
    app.add_url_rule('/save', view_func=inspect.unwrap(getattr(counter_module, handler)), methods=['POST'])
    payload = {'name': 'petition', 'id': 'petition', 'count': 0}
    if mode is not None:
        payload['email_hash_mode'] = mode
    with patch.object(counter_module, 'counter_ref') as counters, \
            patch.object(counter_module, 'log_activity'), \
            patch.object(counter_module, 'get_user_data_from_token', return_value={'google_id': 'owner'}), \
            patch('system.authorization.get_user_data_from_token', return_value={'google_id': 'owner'}):
        counters.where.return_value.get.return_value = []
        counters.where.return_value.limit.return_value.get.return_value = []
        ref = counters.document.return_value
        ref.get.return_value.to_dict.return_value = {'uuid': 'owner'}
        kind = 'data' if handler in ('createlist', 'updateform') else 'json'
        response = app.test_client().post('/save', **{kind: payload})
        assert response.status_code in (200, 201, 302), response.data
        write = ref.update if handler in ('update', 'updateform') else ref.create
        saved = write.call_args.args[0]
        if handler == 'update' and mode is None:
            assert 'email_hash_mode' not in saved
        else:
            default = 'legacy' if handler == 'updateform' else 'strict'
            assert saved['email_hash_mode'] == (mode or default)
