"""Check: which system user does this token belong to?"""
import json, urllib.request

TOKEN = "EAARZAhquUQtEBQryKXjwfmazTqjiysqrwLStdZAj57DYIe5ZCUd2yN75cauNmcnTXEOu28qvjaOGNdh7kIjx1bi7emQH0o7GRgEULkDoQql3ZCZBYIeU5V3t8Th0aTkS8UKm947jIIYHKhacZBCQxrAZAgZBiANxDnRTKuZAoJp7vhD3uIe6skmKp8vqbhSCZAgAZDZD"
APP2_ID = "1224334845952721"
APP2_SECRET = "c661642ea55355d9abd84105f6ffb236"

# debug_token shows the actual user_id
url = f"https://graph.facebook.com/v20.0/debug_token?input_token={TOKEN}&access_token={APP2_ID}|{APP2_SECRET}"
try:
    with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as resp:
        data = json.loads(resp.read().decode())
        d = data.get('data', {})
        print(f"Token user_id: {d.get('user_id')}")
        print(f"App: {d.get('application')} ({d.get('app_id')})")
        print(f"Type: {d.get('type')}")
        print(f"Valid: {d.get('is_valid')}")
        print(f"Issued: {d.get('issued_at')}")
        print()
        print("Expected system user ID: 100086687697377")
        print(f"Actual system user ID:   {d.get('user_id')}")
        if str(d.get('user_id')) == '100086687697377':
            print("✅ MATCH — token is from the correct system user")
        else:
            print("❌ MISMATCH — token is from a DIFFERENT system user!")
            print("   You have multiple system users named 'Manish Agarwal'.")
            print("   Make sure you generate from the one with ID 100086687697377.")
except Exception as e:
    print(f"Error: {e}")
