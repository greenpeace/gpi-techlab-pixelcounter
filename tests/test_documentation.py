import ast
import inspect
from pathlib import Path
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from system.documentation import documentation_urls, google_doc_id

ROOT = Path(__file__).resolve().parents[1]
DOC_ID = '1Sample_Document_ID_1234567890'
HEADERS = {'X-Modal-Form': '1'}


@pytest.mark.parametrize('value', [DOC_ID, '  ' + DOC_ID + '\n',
    f'https://docs.google.com/document/d/{DOC_ID}/edit?tab=t.0#heading=h.example',
    f'https://docs.google.com/document/d/{DOC_ID}/preview',
    f'https://docs.google.com/document/u/0/d/{DOC_ID}/edit',
])
def test_accepts_doc_id_and_normalizes_google_docs_links(value):
    assert google_doc_id(value) == DOC_ID
    assert documentation_urls(value) == {'id': DOC_ID,
        'view': f'https://docs.google.com/document/d/{DOC_ID}/edit',
        'embed': f'https://docs.google.com/document/d/{DOC_ID}/preview'}


@pytest.mark.parametrize('value', ['', None, '<iframe src="https://example.org">',
    'javascript:alert(1)', '../etc/passwd', f'https://evil.example/document/d/{DOC_ID}/edit',
    f'https://docs.google.com.evil.example/document/d/{DOC_ID}/edit',
    f'https://docs.google.com@evil.example/document/d/{DOC_ID}/edit',
    f'http://docs.google.com/document/d/{DOC_ID}/edit',
    f'https://docs.google.com/spreadsheets/d/{DOC_ID}/edit',
    f'https://docs.google.com/document/d/e/{DOC_ID}/pub', 'x' * 201,
])
def test_rejects_other_sources_and_unsafe_input(value):
    with pytest.raises(ValueError):
        google_doc_id(value)
    assert documentation_urls(value) is None


@pytest.fixture
def module():
    with patch('google.cloud.logging.Client'):
        from modules.pixelcounter import pixelcounter
    return pixelcounter


@pytest.fixture
def app(module):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    app.config['TESTING'] = True
    app.jinja_loader = ChoiceLoader([
        DictLoader({'base.html': '{% block content %}{% endblock %}{% block script %}{% endblock %}'}),
        FileSystemLoader([str(ROOT / 'templates'), str(ROOT / 'modules/pixelcounter/templates')]),
    ])
    app.jinja_env.globals['csrf_token'] = lambda: 'test-token'
    app.add_url_rule('/documentation', endpoint='pixelcounterblue.documentation', view_func=inspect.unwrap(module.documentation))
    app.add_url_rule('/settings/documentation', endpoint='pixelcounterblue.documentation_settings',
                     view_func=inspect.unwrap(module.documentation_edit), methods=['GET', 'POST'])
    return app


def test_saves_normalized_id_without_overwriting_old_content(app, module):
    with patch.object(module, 'documentation_ref') as reference, \
            patch.object(module, 'get_user_data_from_token', return_value={'email': 'admin@example.org'}), \
            patch.object(module, 'log_activity'):
        response = app.test_client().post('/settings/documentation', headers=HEADERS,
            data={'google_doc_id': f'https://docs.google.com/document/d/{DOC_ID}/edit?usp=sharing'})
        assert response.status_code == 200
        assert response.json['success'] is True
        assert response.json['saved_document_id'] == DOC_ID
        write = reference.document.return_value.set.call_args
        assert write.kwargs == {'merge': True}
        assert write.args[0]['google_doc_id'] == DOC_ID
        assert write.args[0]['updated_by'] == 'admin@example.org'
        assert 'content' not in write.args[0]


def test_invalid_setting_and_failed_save_return_errors(app, module):
    with patch.object(module, 'documentation_ref') as reference, \
            patch.object(module, 'get_user_data_from_token', return_value={}):
        client = app.test_client()
        response = client.post('/settings/documentation', headers=HEADERS, data={'google_doc_id':'https://evil.example/doc'})
        assert response.status_code == 400
        assert not response.json['success']
        reference.document.return_value.set.assert_not_called()
        reference.document.return_value.set.side_effect = RuntimeError('database unavailable')
        response = client.post('/settings/documentation', headers=HEADERS, data={'google_doc_id':DOC_ID})
        assert response.status_code == 500
        assert not response.json['success']


def test_documentation_embeds_saved_source_and_has_external_fallback(app, module):
    with patch.object(module, 'documentation_ref') as reference:
        reference.document.return_value.get.return_value.to_dict.return_value = {'google_doc_id': DOC_ID}
        response = app.test_client().get('/documentation')
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        html = BeautifulSoup(response.data, 'html.parser')
        iframe = html.select_one('iframe')
        assert iframe['src'] == f'https://docs.google.com/document/d/{DOC_ID}/preview'
        assert iframe['title']
        assert html.select_one('a[target=_blank]')['href'].endswith('/edit')
        assert html.select_one('#refresh-documentation')
        assert not html.select_one('a[data-modal-form]')  # Admin configuration is not shown to regular readers.


@pytest.mark.parametrize('stored', [{}, {'content':'Legacy content must not be rendered'}, {'google_doc_id':'javascript:alert(1)'}])
def test_missing_or_invalid_configuration_shows_empty_state(app, module, stored):
    with patch.object(module, 'documentation_ref') as reference:
        reference.document.return_value.get.return_value.to_dict.return_value = stored
        response = app.test_client().get('/documentation')
        assert b'Documentation is not connected yet' in response.data
        assert b'<iframe' not in response.data
        assert b'Legacy content must not be rendered' not in response.data


def test_settings_modal_uses_new_field_instead_of_static_editor(app, module):
    with patch.object(module, 'documentation_ref') as reference:
        reference.document.return_value.get.return_value.to_dict.return_value = {'google_doc_id': DOC_ID}
        response = app.test_client().get('/settings/documentation', headers=HEADERS)
        html = BeautifulSoup(response.data, 'html.parser')
        assert html.select_one('[data-modal-fragment]')
        assert html.select_one('input[name=google_doc_id]')['value'] == DOC_ID
        assert html.select_one('[data-documentation-id]').text == DOC_ID
        assert 'hidden' not in html.select_one('[data-documentation-saved]').attrs
        assert response.headers['Cache-Control'] == 'no-store'
        assert html.select_one('form')['action'] == '/settings/documentation'
        assert not html.select('textarea')


def test_unconfigured_settings_show_empty_input(app, module):
    with patch.object(module, 'documentation_ref') as reference:
        reference.document.return_value.get.return_value.exists = False
        response = app.test_client().get('/settings/documentation', headers=HEADERS)
        html = BeautifulSoup(response.data, 'html.parser')
        assert html.select_one('input[name=google_doc_id]')['value'] == ''
        assert 'No document ID is set yet.' in html.text
        assert 'hidden' in html.select_one('[data-documentation-saved]').attrs


def test_save_without_javascript_returns_to_settings_with_saved_id(app, module):
    with patch.object(module, 'documentation_ref') as reference, \
            patch.object(module, 'get_user_data_from_token', return_value={}), \
            patch.object(module, 'log_activity'):
        reference.document.return_value.get.return_value.to_dict.return_value = {'google_doc_id': DOC_ID}
        client = app.test_client()
        response = client.post('/settings/documentation', data={'google_doc_id': DOC_ID})
        assert response.location == '/settings/documentation'
        html = BeautifulSoup(client.get(response.location).data, 'html.parser')
        assert html.select_one('[data-documentation-id]').text == DOC_ID
        assert 'Document ID saved successfully.' in html.text


def test_settings_route_aliases_keep_authentication(module):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    app.register_blueprint(module.pixelcounterblue)
    app.add_url_rule('/logout', endpoint='authsblue.logout', view_func=lambda: '')
    for path in ['/settings/documentation', '/documentation/edit']:
        for method in ['get', 'post']:
            response = getattr(app.test_client(), method)(path, headers=HEADERS)
            assert response.status_code == 302
            assert response.location == '/logout'


@pytest.mark.parametrize('production', [False, True])
def test_security_headers_finalize_success_and_error_responses(production):
    # Use app.py's real Flask imports, so a missing request import cannot be
    # masked by injecting it from this test. Avoid starting external services.
    tree = ast.parse((ROOT / 'app.py').read_text())
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == 'flask']
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'add_security_headers')
    function.decorator_list = []
    namespace = {'is_production': production}
    exec(compile(ast.Module(body=imports + [function], type_ignores=[]), 'app.py', 'exec'), namespace)
    app = Flask(__name__)
    app.after_request(namespace['add_security_headers'])
    app.add_url_rule('/documentation', endpoint='pixelcounterblue.documentation', view_func=lambda: '')
    app.add_url_rule('/list', endpoint='pixelcounterblue.read', view_func=lambda: '')

    @app.route('/broken')
    def broken():
        raise RuntimeError('Simulated route failure')

    client = app.test_client()
    for path, status in [('/documentation', 200), ('/list', 200), ('/missing', 404), ('/broken', 500)]:
        response = client.get(path)
        assert response.status_code == status
        policy = response.headers['Content-Security-Policy']
        assert ('https://docs.google.com' in policy) == (path == '/documentation')
        assert "frame-ancestors 'none'" in policy
        assert response.headers['X-Frame-Options'] == 'DENY'
        assert ('Strict-Transport-Security' in response.headers) is production
