import io


def test_contacts_page_loads(auth_client):
    response = auth_client.get('/contacts/')
    assert response.status_code == 200


def test_add_contact(auth_client):
    response = auth_client.post('/contacts/add', data={
        'name': 'Alice Smith',
        'phone': '5551234567',
        'group_name': 'Friends',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Alice Smith' in response.data


def test_add_contact_normalizes_phone(auth_client):
    auth_client.post('/contacts/add', data={
        'name': 'Bob Jones',
        'phone': '5559876543',
        'group_name': '',
    })
    response = auth_client.get('/contacts/')
    assert b'+15559876543' in response.data


def test_delete_contact(auth_client, app):
    auth_client.post('/contacts/add', data={'name': 'ContactToDelete', 'phone': '5550001111', 'group_name': ''})
    with app.app_context():
        from web_app.db import get_db
        db = get_db()
        contact_id = db.execute("SELECT id FROM contacts WHERE name='ContactToDelete'").fetchone()[0]
    response = auth_client.post(f'/contacts/delete/{contact_id}', follow_redirects=True)
    assert response.status_code == 200
    assert b'ContactToDelete' not in response.data


def test_update_contact(auth_client, app):
    auth_client.post('/contacts/add', data={'name': 'Old Name', 'phone': '5550002222', 'group_name': ''})
    with app.app_context():
        from web_app.db import get_db
        db = get_db()
        contact_id = db.execute("SELECT id FROM contacts WHERE name='Old Name'").fetchone()[0]
    response = auth_client.post(f'/contacts/edit/{contact_id}', data={
        'name': 'New Name', 'phone': '5550002222', 'group_name': 'Team'
    }, follow_redirects=True)
    assert b'New Name' in response.data


def test_import_csv(auth_client):
    csv_content = b"Name,Phone,Group\nCarol White,5553334444,Work\nDave Black,5555556666,Work\n"
    data = {'file': (io.BytesIO(csv_content), 'contacts.csv')}
    response = auth_client.post('/contacts/import', data=data,
                           content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    assert b'Carol White' in response.data


def test_empty_name_rejected(auth_client):
    response = auth_client.post('/contacts/add', data={
        'name': '', 'phone': '5551234567', 'group_name': ''
    }, follow_redirects=True)
    assert b'Name is required' in response.data


def test_empty_phone_rejected(auth_client):
    response = auth_client.post('/contacts/add', data={
        'name': 'No Phone', 'phone': '', 'group_name': ''
    }, follow_redirects=True)
    assert b'Phone is required' in response.data
