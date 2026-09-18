"""Modal contracts, native form fields and actual handlers with external services mocked."""
from contextlib import ExitStack
from pathlib import Path
import importlib
import inspect
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup
from flask import Flask, g, render_template, request
from flask_wtf.csrf import CSRFProtect, generate_csrf
from jinja2 import FileSystemLoader
from werkzeug.exceptions import Forbidden

from system.modal_forms import form_error, form_success

ROOT = Path(__file__).resolve().parents[1]
FORM_TEMPLATES = [
    'listadd.html', 'listedit.html', 'allowedlistadd.html', 'allowedlistedit.html',
    'disallowedlistadd.html', 'disallowedlistedit.html', 'documentation_edit.html',
    'qrcodeadd.html', 'qrcodeedit.html', 'urlshortneradd.html', 'urlshortneredit.html',
    'usersadd.html', 'usersedit.html', 'nro_form.html', 'apikey_generate_form.html',
]
HEADERS = {'X-Modal-Form': '1'}


@pytest.fixture
def app():
    app = Flask(__name__)
    app.secret_key = 'test-only'
    app.config['TESTING'] = True
    app.jinja_loader = FileSystemLoader([str(ROOT / 'templates')] +
        [str(path) for path in (ROOT / 'modules').glob('*/templates')])
    app.jinja_env.globals.update(csrf_token=lambda: 'test-csrf', url_for=lambda endpoint, **kw: '/' + endpoint)
    @app.before_request
    def nonce():
        g.nonce = 'test-nonce'
    return app


@pytest.mark.parametrize('template', FORM_TEMPLATES)
def test_modal_fragments_preserve_real_forms_without_page_chrome(app, template):
    with app.test_request_context('/form', headers=HEADERS):
        html = render_template(template, ngo={'id': 'one', 'name': 'Example'}, users={'id': 'one'},
                               nros=[], counters=[], apikeys=[], nro=None, title='Docs', summary='', content='Body')
    doc = BeautifulSoup(html, 'html.parser')
    fragment = doc.select_one('[data-modal-fragment]')
    assert fragment is not None
    assert len(fragment.select('form')) == 1
    assert fragment.select_one('input[name=csrf_token]')['value'] == 'test-csrf'
    assert not doc.select('html, #sidebar-menu, script')


def test_response_contract_csrf_errors_and_fallback(app):
    CSRFProtect(app)
    app.add_url_rule('/list', endpoint='list', view_func=lambda: '')
    app.add_url_rule('/csrf', view_func=lambda: {'token': generate_csrf()})
    @app.post('/save')
    def save():
        if request.form.get('fail'):
            return form_error(Forbidden('Not allowed'), 'list')
        return form_success('list')
    client = app.test_client()
    assert client.post('/save', headers=HEADERS).status_code == 400
    token = client.get('/csrf').json['token']
    headers = dict(HEADERS, **{'X-CSRFToken': token})
    assert client.post('/save', headers=headers).json['success'] is True
    response = client.post('/save', data={'fail': 'yes'}, headers=headers)
    assert response.status_code == 403
    assert response.json == {'success': False, 'error': 'Not allowed'}
    response = client.post('/save', data={'csrf_token': token})
    assert response.status_code == 302
    assert response.location == '/list'


@pytest.fixture
def modules(monkeypatch):
    for secret in ('QRCODE_BUCKET_NAME', 'URLSHORTNER_STATS_DATASET_ID', 'URLSHORTNER_STATS_TABLE_ID'):
        monkeypatch.setenv('PIXELCOUNTER_SECRET_' + secret, 'test-only')
    with patch('google.cloud.logging.Client'), patch('google.cloud.bigquery.Client'):
        return {name: importlib.import_module(f'modules.{name}.{name}')
                for name in ['pixelcounter', 'nro', 'urlshortner', 'qrcode', 'users', 'apikey']}


HANDLERS = [
    ('pixelcounter', 'createlist'), ('pixelcounter', 'updateform'),
    ('pixelcounter', 'allowedlistcreate'), ('pixelcounter', 'allowedlistupdate'),
    ('pixelcounter', 'disallowedlistcreate'), ('pixelcounter', 'disallowedlistupdate'),
    ('pixelcounter', 'documentation_edit'), ('nro', 'nro_add'), ('nro', 'nro_edit'),
    ('urlshortner', 'urlshortnercreate'), ('urlshortner', 'urlshortnerupdate'),
    ('qrcode', 'qrcodecreate'), ('qrcode', 'qrcodeupdate'),
    ('users', 'users_create'), ('users', 'users_update'),
]


@pytest.mark.parametrize('module_name,handler', HANDLERS)
def test_add_edit_handlers_return_explicit_modal_success(app, modules, module_name, handler):
    module = modules[module_name]
    reference = MagicMock()
    reference.document.return_value.id = 'one'
    reference.where.return_value.get.return_value = []
    reference.where.return_value.limit.return_value.get.return_value = []
    record = {'id': 'one', 'name': 'Example', 'uuid': 'owner', 'date': 'today', 'filename': 'example.png'}
    reference.document.return_value.get.return_value.to_dict.return_value = record
    with ExitStack() as stack:
        for attr in ['counter_ref', 'allowedorigion_ref', 'disallowedorigion_ref', 'documentation_ref',
                     'nro_ref', 'molnurl_ref', 'qrcode_ref', 'users_ref']:
            if hasattr(module, attr): stack.enter_context(patch.object(module, attr, reference))
        for attr in ['get_user_data_from_token', 'decode_jwt_token']:
            if hasattr(module, attr): stack.enter_context(patch.object(module, attr, return_value={'google_id':'owner', 'role':'Administrator'}))
        for attr in ['log_activity']:
            if hasattr(module, attr): stack.enter_context(patch.object(module, attr))
        stack.enter_context(patch('system.authorization.get_user_data_from_token', return_value={'google_id':'owner'}))
        stack.enter_context(patch('system.firstoredb.apikeys_ref'))
        stack.enter_context(patch('google.cloud.storage.Client'))
        stack.enter_context(patch('qrcode.QRCode'))
        if module_name == 'urlshortner':
            stack.enter_context(patch.object(module, 'fetch_public_html', return_value='<title>Test</title>'))
        view = inspect.unwrap(getattr(module, handler))
        if handler == 'nro_edit':
            app.add_url_rule('/save', view_func=lambda: view('one'), methods=['POST'])
        else:
            app.add_url_rule('/save', view_func=view, methods=['POST'])
        response = app.test_client().post('/save', headers=HEADERS, data={
            'id':'one', 'name':'example', 'count':'10', 'history_enabled':'on', 'url':'https://example.org',
            'domain':'', 'qrcodename':'example', 'qrcode':'hello', 'version':'1', 'boxsize':'10', 'border':'4',
            'fill_color':'black', 'back_color':'white', 'google_doc_id':'1Sample_Document_ID_1234567890', 'title':'Documentation', 'content':'Body', 'given_name':'Test', 'last_name':'User',
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.json['success'] is True


def test_duplicate_counter_stays_an_error_and_does_not_write(app, modules):
    module = modules['pixelcounter']
    app.add_url_rule('/save', view_func=inspect.unwrap(module.createlist), methods=['POST'])
    with patch.object(module, 'counter_ref') as ref, patch.object(module, 'get_user_data_from_token', return_value={}):
        ref.where.return_value.get.return_value = [MagicMock()]
        response = app.test_client().post('/save', data={'name':'duplicate','count':'0'}, headers=HEADERS)
        assert response.status_code == 400
        assert response.json['success'] is False
        ref.document.assert_not_called()


def test_nro_validation_and_switch_values(app, modules):
    module = modules['nro']
    app.add_url_rule('/save', view_func=inspect.unwrap(module.nro_add), methods=['POST'])
    with patch.object(module, 'nro_ref') as ref:
        client = app.test_client()
        assert client.post('/save', data={'name':' '}, headers=HEADERS).status_code == 400
        ref.document.assert_not_called()
        for active in (True, False):
            data = {'name':'Sweden'}
            if active: data['active'] = 'on'
            assert client.post('/save', data=data, headers=HEADERS).status_code == 200
            assert ref.document.return_value.set.call_args.args[0]['active'] is active


def test_api_key_generation_shows_once_and_does_not_store_plaintext(app, modules):
    module = modules['apikey']
    app.add_url_rule('/generate', view_func=inspect.unwrap(module.generateapikey), methods=['GET','POST'])
    with patch.object(module, '_get_decoded_jwt', return_value={'uuid':'owner'}), \
            patch.object(module, 'apikeys_ref') as ref:
        client = app.test_client()
        assert b'data-modal-fragment' in client.get('/generate', headers=HEADERS).data
        ref.document.assert_not_called()
        response = client.post('/generate', headers=HEADERS)
        assert response.json['success'] is True
        assert 'data-modal-fragment' in response.json['result_html']
        assert response.headers['Cache-Control'] == 'no-store'
        stored = ref.document.return_value.set.call_args.args[0]
        assert 'api_key_hash' in stored and 'api_key' not in stored


@pytest.mark.parametrize('module_name,handler', HANDLERS)
def test_modal_header_does_not_bypass_login(app, modules, module_name, handler):
    app.add_url_rule('/logout', endpoint='authsblue.logout', view_func=lambda: '')
    view = getattr(modules[module_name], handler)
    if handler == 'nro_edit':
        app.add_url_rule('/save', view_func=lambda: view('one'), methods=['POST'])
    else:
        app.add_url_rule('/save', view_func=view, methods=['POST'])
    response = app.test_client().post('/save', headers=HEADERS)
    assert response.status_code == 302
    assert response.location == '/logout'


@pytest.mark.parametrize('module_name,handler', [
    ('users', 'users_create'), ('users', 'users_update'),
    ('nro', 'nro_add'), ('pixelcounter', 'documentation_edit'),
])
def test_modal_header_does_not_bypass_admin_permission(app, modules, module_name, handler):
    # Keep the real admin wrapper; bypass only external login for this unit test.
    view = getattr(modules[module_name], handler).__wrapped__
    app.add_url_rule('/save', view_func=view, methods=['POST'])
    app.add_url_rule('/home', endpoint='frontpageblue.index', view_func=lambda: '')
    @app.before_request
    def current_user():
        g.current_user = {'role': 'User'}
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['role'] = 'User'
            session['jwt_token'] = 'test-token'
        response = client.post('/save', headers=HEADERS)
        assert response.status_code in (302, 403)
        if response.status_code == 302:
            assert response.location == '/home'
