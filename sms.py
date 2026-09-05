import os
import sqlite3
import csv
import json
import urllib.request
import urllib.error
import getpass
import re

DB_FILE = 'contacts.db'

def init_db():
    # Ensure secure permissions if file doesn't exist
    if not os.path.exists(DB_FILE):
        open(DB_FILE, 'a').close()
        os.chmod(DB_FILE, 0o600) # Read/write for owner only
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            group_name TEXT
        )
    ''')
    conn.commit()
    return conn

def load_env():
    env_path = '.env'
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip('"\' ')

def get_credentials():
    load_env()
    api_key = os.environ.get('TEXTBEE_API_KEY')
    device_id = os.environ.get('TEXTBEE_DEVICE_ID')
    
    if not api_key:
        api_key = getpass.getpass("Enter your Textbee API Key (input is hidden): ")
    if not device_id:
        device_id = input("Enter your Textbee Device ID: ")
        
    return api_key, device_id

def send_sms(api_key, device_id, recipients, message):
    url = f"https://api.textbee.dev/api/v1/gateway/devices/{device_id}/send-sms"
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    data = {
        'recipients': recipients,
        'message': message
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- false positive: url is built from a fixed https://api.textbee.dev host template; only device_id (a path segment) is interpolated, so the scheme/host can't be attacker-controlled.
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("Successfully sent message to API queue!")
            print(result)
            return True
    except urllib.error.URLError as e:
        print(f"Failed to send SMS: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))
        return False

def import_csv(conn):
    file_path = input("Enter the path to the CSV file: ")
    if not os.path.exists(file_path):
        print("File not found.")
        return
        
    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                 print("CSV file is empty or invalid.")
                 return
                 
            # Expecting columns: Name, Phone, Group (optional)
            fieldnames = [field.lower() for field in reader.fieldnames]
            
            if 'name' not in fieldnames or 'phone' not in fieldnames:
                print("CSV must contain 'Name' and 'Phone' columns.")
                return
                
            cursor = conn.cursor()
            count = 0
            for row in reader:
                row_lower = {k.lower(): v for k, v in row.items()}
                name = row_lower.get('name')
                phone = row_lower.get('phone')
                clean_phone = clean_phone_number(phone) if phone else ''
                group = row_lower.get('group', '')
                
                cursor.execute('INSERT INTO contacts (name, phone, group_name) VALUES (?, ?, ?)', (name, clean_phone, group))
                count += 1
                
            conn.commit()
            print(f"Successfully imported {count} contacts.")
    except Exception as e:
        print(f"Error reading CSV: {e}")

def list_contacts(conn):
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, phone, group_name FROM contacts')
    rows = cursor.fetchall()
    
    if not rows:
        print("No contacts found.")
        return
        
    print("\nContacts:")
    print(f"{'ID':<4} | {'Name':<20} | {'Phone':<15} | {'Group'}")
    print("-" * 60)
    for row in rows:
        print(f"{row[0]:<4} | {row[1]:<20} | {row[2]:<15} | {row[3]}")
    print()

def clean_phone_number(phone):
    phone_str = phone.strip()
    has_plus = phone_str.startswith('+')
    digits = re.sub(r'\D', '', phone_str)
    if digits:
        if has_plus:
            return '+' + digits
        else:
            if len(digits) == 10:
                return '+1' + digits
            elif len(digits) == 11 and digits.startswith('1'):
                return '+' + digits
            return digits
    return phone_str

def add_contact(conn):
    print("\nAdd New Contact")
    name = input("Enter Name: ").strip()
    if not name:
        print("Name cannot be empty.")
        return
        
    phone = input("Enter Phone: ").strip()
    if not phone:
        print("Phone cannot be empty.")
        return
        
    clean_phone = clean_phone_number(phone)
    group = input("Enter Group (optional): ").strip()
    
    cursor = conn.cursor()
    cursor.execute('INSERT INTO contacts (name, phone, group_name) VALUES (?, ?, ?)', (name, clean_phone, group))
    conn.commit()
    print(f"Contact '{name}' added successfully!")

def update_contact(conn):
    print("\nUpdate Contact")
    list_contacts(conn)
    contact_id = input("Enter the ID of the contact to update: ").strip()
    if not contact_id:
        return
        
    cursor = conn.cursor()
    cursor.execute('SELECT name, phone, group_name FROM contacts WHERE id = ?', (contact_id,))
    row = cursor.fetchone()
    if not row:
        print("Contact not found.")
        return
        
    current_name, current_phone, current_group = row
    print(f"Current details - Name: {current_name}, Phone: {current_phone}, Group: {current_group or '(None)'}")
    
    new_name = input(f"Enter new Name (leave empty to keep '{current_name}'): ").strip()
    if not new_name:
        new_name = current_name
        
    new_phone = input(f"Enter new Phone (leave empty to keep '{current_phone}'): ").strip()
    if not new_phone:
        new_phone = current_phone
    else:
        new_phone = clean_phone_number(new_phone)
        
    new_group = input(f"Enter new Group (leave empty to keep '{current_group or '(None)'}'): ").strip()
    if not new_group:
        new_group = current_group
        
    cursor.execute('''
        UPDATE contacts 
        SET name = ?, phone = ?, group_name = ? 
        WHERE id = ?
    ''', (new_name, new_phone, new_group, contact_id))
    conn.commit()
    print("Contact updated successfully!")

def delete_contact(conn):
    print("\nDelete Contact")
    list_contacts(conn)
    contact_id = input("Enter the ID of the contact to delete: ").strip()
    if not contact_id:
        return
        
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM contacts WHERE id = ?', (contact_id,))
    row = cursor.fetchone()
    if not row:
        print("Contact not found.")
        return
        
    name = row[0]
    confirm = input(f"Are you sure you want to delete contact '{name}'? (y/n): ").strip().lower()
    if confirm == 'y':
        cursor.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
        conn.commit()
        print(f"Contact '{name}' deleted successfully.")
    else:
        print("Deletion cancelled.")

def manage_contacts_menu(conn):
    while True:
        print("\nManage Contacts Menu:")
        print("1. Add Contact (Create)")
        print("2. List Contacts (Read)")
        print("3. Update Contact (Update)")
        print("4. Delete Contact (Delete)")
        print("5. Back to Main Menu")
        
        choice = input("Select an option: ")
        
        if choice == '1':
            add_contact(conn)
        elif choice == '2':
            list_contacts(conn)
        elif choice == '3':
            update_contact(conn)
        elif choice == '4':
            delete_contact(conn)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")

def get_message_content():
    choice = input("Do you want to (1) type a message directly or (2) read from a Markdown file? (1/2): ")
    if choice == '1':
        message = input("Enter your message: ")
        return message
    elif choice == '2':
        file_path = input("Enter the path to the Markdown file: ")
        if not os.path.exists(file_path):
            print("File not found.")
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        print("Invalid choice.")
        return None

def send_menu(conn, api_key, device_id):
    print("\nSend Message Menu")
    print("1. Send to Individual (from DB)")
    print("2. Send to Group (from DB)")
    print("3. Enter phone number manually")
    choice = input("Select an option: ")
    
    recipients = []
    
    if choice == '1':
        list_contacts(conn)
        contact_id = input("Enter the ID of the contact: ")
        cursor = conn.cursor()
        cursor.execute('SELECT phone FROM contacts WHERE id = ?', (contact_id,))
        row = cursor.fetchone()
        if not row:
            print("Contact not found.")
            return
        recipients.append(row[0])
        
    elif choice == '2':
        group_name = input("Enter the group name: ")
        cursor = conn.cursor()
        cursor.execute('SELECT phone FROM contacts WHERE group_name = ?', (group_name,))
        rows = cursor.fetchall()
        if not rows:
            print("No contacts found in that group.")
            return
        recipients = [row[0] for row in rows]
        print(f"Found {len(recipients)} contacts in group '{group_name}'.")
        
    elif choice == '3':
        phone = input("Enter the phone number: ")
        recipients.append(phone)
        
    else:
        print("Invalid choice.")
        return

    message = get_message_content()
    if not message:
        print("Message cannot be empty.")
        return
        
    print(f"Sending message to: {', '.join(recipients)}")
    send_sms(api_key, device_id, recipients, message)


def main():
    print("Welcome to Interactive SMS App")
    conn = init_db()
    api_key, device_id = get_credentials()
    
    while True:
        print("\nMain Menu:")
        print("1. Manage Contacts")
        print("2. Import Contacts from CSV")
        print("3. Send Message")
        print("4. Exit")
        
        choice = input("Select an option: ")
        
        if choice == '1':
            manage_contacts_menu(conn)
        elif choice == '2':
            import_csv(conn)
        elif choice == '3':
            send_menu(conn, api_key, device_id)
        elif choice == '4':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
