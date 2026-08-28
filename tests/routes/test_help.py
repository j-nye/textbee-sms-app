def test_help_page_returns_200(auth_client):
    response = auth_client.get('/help/')
    assert response.status_code == 200


def test_help_page_contains_getting_started(auth_client):
    response = auth_client.get('/help/')
    assert b'Getting Started' in response.data


def test_help_page_contains_all_sections(auth_client):
    response = auth_client.get('/help/')
    for section in [b'Send a Message', b'Contacts', b'Templates', b'History', b'Settings', b'CLI App']:
        assert section in response.data, f"Missing section: {section}"
