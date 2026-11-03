import pytest
import json
from unittest.mock import MagicMock
from pathlib import Path
from browser.session_manager import GupySessionManager, validate_page_auth

def test_session_manager_initialization(tmp_path):
    fake_session_file = tmp_path / "gupy_session.json"
    manager = GupySessionManager(session_path=fake_session_file)
    assert not manager.has_session()
    assert not manager.is_session_valid()

def test_session_manager_with_empty_file(tmp_path):
    fake_session_file = tmp_path / "gupy_session.json"
    fake_session_file.write_text("{}")
    manager = GupySessionManager(session_path=fake_session_file)
    assert not manager.has_session()

def test_validate_page_auth_detects_signin_url():
    fake_page = MagicMock()
    fake_page.url = "https://login.gupy.io/candidates/signin"
    is_auth, reason = validate_page_auth(fake_page)
    assert is_auth is False
    assert "signin" in reason.lower()

def test_validate_page_auth_detects_subdomain_signin():
    fake_page = MagicMock()
    fake_page.url = "https://empresa.gupy.io/candidates/signin"
    is_auth, reason = validate_page_auth(fake_page)
    assert is_auth is False
    assert "signin" in reason.lower()

def test_validate_page_auth_detects_public_home_redirect():
    fake_page = MagicMock()
    fake_page.url = "https://empresa.gupy.io/jobs"
    is_auth, reason = validate_page_auth(fake_page)
    assert is_auth is False
    assert "institucional" in reason.lower() or "publica" in reason.lower()
