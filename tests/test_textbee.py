import json
import pytest
from unittest.mock import patch, MagicMock
from web_app.textbee import send_sms, normalize_phone


def test_normalize_phone_10_digits():
    assert normalize_phone('5551234567') == '+15551234567'


def test_normalize_phone_11_digits_leading_1():
    assert normalize_phone('15551234567') == '+15551234567'


def test_normalize_phone_already_e164():
    assert normalize_phone('+15551234567') == '+15551234567'


def test_normalize_phone_with_dashes():
    assert normalize_phone('555-123-4567') == '+15551234567'


def test_normalize_phone_with_parens():
    assert normalize_phone('(555) 123-4567') == '+15551234567'


def test_send_sms_success():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({'success': True}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch('urllib.request.urlopen', return_value=mock_response):
        result = send_sms('api-key', 'device-id', ['+15551234567'], 'Hello!')

    assert result['success'] is True
    assert result['error'] is None


def test_send_sms_network_failure():
    import urllib.error
    with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('timeout')):
        result = send_sms('api-key', 'device-id', ['+15551234567'], 'Hello!')

    assert result['success'] is False
    assert 'timeout' in result['error']
