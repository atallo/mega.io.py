"""Offline unit tests: no network and no MEGA account required.

These exercise the client's logic by replacing ``requests.post`` with a stub,
so they are safe to run in CI on every push.
"""
import json
from unittest.mock import patch

import pytest
from tenacity import wait_none

from mega import Mega
from mega.errors import RequestError


@pytest.fixture(autouse=True)
def _no_retry_wait():
    """Make retries instant so tests don't sleep on the backoff."""
    original = Mega._api_request.retry.wait
    Mega._api_request.retry.wait = wait_none()
    yield
    Mega._api_request.retry.wait = original


class _Resp:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


def _post_recording(calls, responses=None):
    """Return a ``requests.post`` replacement.

    It records each request's action in ``calls`` and replies with the next
    item from ``responses`` (if given) or a canned reply per action.
    """
    def fake_post(url, params=None, data=None, timeout=None):
        action = json.loads(data)[0].get('a')
        calls.append(action)
        if responses:
            return responses.pop(0)
        if action == 'f':
            return _Resp(json.dumps([{'f': [], 'ok': [], 's': []}]))
        return _Resp(json.dumps([0]))
    return fake_post


# --- URL parsing -----------------------------------------------------------

@pytest.mark.parametrize('url, expected', [
    ('https://mega.nz/#!Ue5VRSIQ!kC2E4a4JwfWWCWYNJovGFHlbz8FN-ISsBAGPzvTjT6k',
     'Ue5VRSIQ!kC2E4a4JwfWWCWYNJovGFHlbz8FN-ISsBAGPzvTjT6k'),
    ('https://mega.nz/file/cH51DYDR#qH7QOfRcM-7N9riZWdSjsRq5VDTLfIhThx1capgVA30',
     'cH51DYDR!qH7QOfRcM-7N9riZWdSjsRq5VDTLfIhThx1capgVA30'),
])
def test_parse_url(url, expected):
    assert Mega()._parse_url(url) == expected


# --- node-tree caching -----------------------------------------------------

def test_get_files_is_cached():
    m = Mega()
    calls = []
    with patch('mega.mega.requests.post', side_effect=_post_recording(calls)):
        m.get_files()
        m.get_files()
        m.get_files()
    assert calls.count('f') == 1


def test_mutation_invalidates_cache():
    m = Mega()
    calls = []
    with patch('mega.mega.requests.post', side_effect=_post_recording(calls)):
        m.get_files()
        m._api_request({'a': 'd', 'n': 'x', 'i': 'y'})  # delete -> invalidate
        m.get_files()
    assert calls.count('f') == 2


def test_force_refresh_bypasses_cache():
    m = Mega()
    calls = []
    with patch('mega.mega.requests.post', side_effect=_post_recording(calls)):
        m.get_files()
        m.get_files(force=True)
    assert calls.count('f') == 2


# --- retry / error handling ------------------------------------------------

def test_eagain_is_retried_then_succeeds():
    m = Mega()
    calls = []
    responses = [_Resp('-3'),
                 _Resp(json.dumps([{'f': [], 'ok': [], 's': []}]))]
    with patch('mega.mega.requests.post',
               side_effect=_post_recording(calls, responses)):
        m.get_files()
    assert len(calls) == 2  # one -3, one success


def test_ratelimit_minus4_is_retried():
    m = Mega()
    calls = []
    responses = [_Resp('-4'),
                 _Resp(json.dumps([{'f': [], 'ok': [], 's': []}]))]
    with patch('mega.mega.requests.post',
               side_effect=_post_recording(calls, responses)):
        m.get_files()
    assert len(calls) == 2


def test_persistent_eagain_eventually_raises():
    from tenacity import RetryError
    m = Mega()

    def always_eagain(url, params=None, data=None, timeout=None):
        return _Resp('-3')

    with patch('mega.mega.requests.post', side_effect=always_eagain):
        with pytest.raises(RetryError):
            m.get_files(force=True)


def test_other_error_code_raises_request_error():
    m = Mega()

    def enoent(url, params=None, data=None, timeout=None):
        return _Resp('-9')  # ENOENT, not retryable

    with patch('mega.mega.requests.post', side_effect=enoent):
        with pytest.raises(RequestError):
            m.get_files(force=True)


# --- path resolution -------------------------------------------------------

def test_find_by_path():
    m = Mega()
    m.root_id = 'ROOT'
    m._nodes = {  # prime the cache so get_files() needs no network
        'A': {'t': 1, 'h': 'A', 'p': 'ROOT', 'a': {'n': 'folder'}},
        'B': {'t': 0, 'h': 'B', 'p': 'A', 'a': {'n': 'file.txt'}},
    }
    found = m.find('folder/file.txt')
    assert found is not None and found[0] == 'B'


def test_find_missing_returns_none():
    m = Mega()
    m.root_id = 'ROOT'
    m._nodes = {'A': {'t': 1, 'h': 'A', 'p': 'ROOT', 'a': {'n': 'folder'}}}
    assert m.find('folder/nope.txt') is None


# --- folder export is a clear, documented failure --------------------------

def test_export_folder_raises_not_implemented():
    m = Mega()
    m.master_key = (1, 2, 3, 4)
    folder = ('H', {'t': 1, 'h': 'H', 'k': (1, 2, 3, 4), 'a': {'n': 'f'}})
    m._nodes = {'H': folder[1]}
    m.find = lambda path=None, **kw: folder

    def _not_exported(node):
        raise KeyError('not exported')

    m.get_folder_link = _not_exported
    with pytest.raises(NotImplementedError):
        m.export('f')


# --- 2FA (TOTP) login ------------------------------------------------------

def _stub_login(m, seen):
    from mega.crypto import a32_to_base64

    def fake_api(data):
        seen.append(data)
        if data.get('a') == 'us0':
            return {'s': a32_to_base64((1, 2, 3, 4))}  # has salt -> v2 path
        return {'ok': 1}  # 'us' response (consumed by the stubbed process)

    m._api_request = fake_api
    m._login_process = lambda resp, password: None


def test_login_sends_mfa_code():
    m = Mega()
    seen = []
    _stub_login(m, seen)
    m._login_user('user@example.com', 'pw', mfa_code='123456')
    us = next(r for r in seen if r.get('a') == 'us')
    assert us.get('mfa') == '123456'


def test_login_without_mfa_omits_field():
    m = Mega()
    seen = []
    _stub_login(m, seen)
    m._login_user('user@example.com', 'pw')
    us = next(r for r in seen if r.get('a') == 'us')
    assert 'mfa' not in us


# --- file-like upload/download --------------------------------------------

def test_stream_size():
    import io
    assert Mega._stream_size(io.BytesIO(b'x' * 1234)) == 1234


def test_upload_stream_requires_dest_filename():
    import io
    m = Mega()
    m.root_id = 'ROOT'
    with pytest.raises(ValueError):
        m.upload(io.BytesIO(b'data'), dest='ROOT')


# --- hashcash proof-of-work (HTTP 402) -------------------------------------

def test_http_402_raises_hashcash_error():
    from mega.errors import HashcashError
    m = Mega()

    def needs_pow(url, params=None, data=None, timeout=None):
        return _Resp('proof-of-work challenge', status_code=402)

    with patch('mega.mega.requests.post', side_effect=needs_pow):
        with pytest.raises(HashcashError):
            m.get_files(force=True)
