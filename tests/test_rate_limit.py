from flask import Flask
from google.api_core.exceptions import InvalidArgument

from modules.auth import auth


class _MissingSnapshot:
    exists = False

    def to_dict(self):
        return None


class _Document:
    def get(self, transaction):
        return _MissingSnapshot()


class _Transaction:
    def set(self, document, data):
        self.data = data


class _Database:
    def __init__(self):
        self.transactions = []

    def transaction(self):
        transaction = _Transaction()
        self.transactions.append(transaction)
        return transaction


def test_rate_limit_retries_expired_transaction_with_a_fresh_transaction(monkeypatch):
    database = _Database()
    document = _Document()
    attempts = 0

    def transactional(func):
        def wrapper(transaction):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise InvalidArgument(
                    'The referenced transaction has expired or is no longer valid.'
                )
            return func(transaction)
        return wrapper

    monkeypatch.setattr(auth, 'db', database)
    monkeypatch.setattr(auth.rate_limit_ref, 'document', lambda key: document)
    monkeypatch.setattr(auth.firestore, 'transactional', transactional)

    app = Flask(__name__)

    @app.get('/limited')
    @auth.rate_limit()
    def limited():
        return 'ok'

    response = app.test_client().get('/limited')

    assert response.status_code == 200
    assert len(database.transactions) == 2
    assert database.transactions[0] is not database.transactions[1]


def test_rate_limit_does_not_retry_other_invalid_arguments(monkeypatch):
    database = _Database()

    def transactional(func):
        def wrapper(transaction):
            raise InvalidArgument('A different invalid argument')
        return wrapper

    monkeypatch.setattr(auth, 'db', database)
    monkeypatch.setattr(auth.rate_limit_ref, 'document', lambda key: _Document())
    monkeypatch.setattr(auth.firestore, 'transactional', transactional)

    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.get('/limited')
    @auth.rate_limit()
    def limited():
        return 'ok'

    try:
        app.test_client().get('/limited')
    except InvalidArgument:
        pass
    else:
        raise AssertionError('Unexpected InvalidArgument should propagate')

    assert len(database.transactions) == 1
