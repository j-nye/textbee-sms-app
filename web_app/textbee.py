from __future__ import annotations

import json
import re
import urllib.request
import urllib.error

TEXTBEE_URL = "https://api.textbee.dev/api/v1/gateway/devices/{device_id}/send-sms"


def normalize_phone(phone: str) -> str:
    """Normalize a phone number to E.164 format (+1XXXXXXXXXX for US numbers)."""
    phone_str = phone.strip()
    has_plus = phone_str.startswith('+')
    digits = re.sub(r'\D', '', phone_str)
    if not digits:
        return phone_str
    if has_plus:
        return '+' + digits
    if len(digits) == 10:
        return '+1' + digits
    if len(digits) == 11 and digits.startswith('1'):
        return '+' + digits
    return digits


def send_sms(api_key: str, device_id: str, recipients: list[str], message: str) -> dict:
    """
    Send an SMS via Textbee API.

    Returns:
        dict with keys:
            success (bool)
            error (str or None)
            data (dict or None)
    """
    url = TEXTBEE_URL.format(device_id=device_id)
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json',
        'User-Agent': 'SMS-WebApp/1.0',
    }
    payload = json.dumps({'recipients': recipients, 'message': message}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {'success': True, 'error': None, 'data': result}
    except urllib.error.URLError as e:
        error_msg = str(e.reason) if hasattr(e, 'reason') else str(e)
        return {'success': False, 'error': error_msg}
