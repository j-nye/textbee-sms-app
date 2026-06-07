def test_templates_page_loads(client):
    response = client.get('/templates/')
    assert response.status_code == 200


def test_create_template(client):
    response = client.post('/templates/create', data={
        'name': 'Game Reminder',
        'body_markdown': '**Reminder:** Game is at 7pm tonight!',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Game Reminder' in response.data


def test_delete_template(client, app):
    client.post('/templates/create', data={
        'name': 'To Delete', 'body_markdown': 'bye'
    }, follow_redirects=True)  # consume create flash
    with app.app_context():
        from web_app.db import get_db
        db = get_db()
        tmpl_id = db.execute("SELECT id FROM msg_templates WHERE name='To Delete'").fetchone()[0]
    response = client.post(f'/templates/delete/{tmpl_id}', follow_redirects=True)
    assert b'To Delete' not in response.data


def test_empty_name_rejected(client):
    response = client.post('/templates/create', data={
        'name': '', 'body_markdown': 'hello'
    }, follow_redirects=True)
    assert b'Name is required' in response.data


def test_template_preview_endpoint(client, app):
    client.post('/templates/create', data={
        'name': 'Bold Test', 'body_markdown': '**hello**'
    })
    with app.app_context():
        from web_app.db import get_db
        db = get_db()
        tmpl_id = db.execute("SELECT id FROM msg_templates WHERE name='Bold Test'").fetchone()[0]
    response = client.get(f'/templates/preview/{tmpl_id}')
    assert response.status_code == 200
    assert b'<strong>' in response.data or b'hello' in response.data
