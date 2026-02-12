"""Try token WITHOUT appsecret_proof, and also try direct POST to /calls"""
import json,urllib.request,urllib.error,hmac,hashlib

T="EAAf0L77jdagBQppO7QZCuPoaiL4G76snYzvw0e8PlTjiSsKrdXKQhXcZA34xJCkFasl2LqMGkCIwru4ThtxXqOUcmYUlkmicUTsnHFg1wWbDqp0xfEuYdr92BGSB0d07iRZBY17ZCCHPwIhl19C3buqpQXxkxHEcpReI9T63xT2KF61SXrgyZCJLVPggsmwZDZD"
S="9c146c26b6adc338472ac205b158b3d5"
P="960395407161423"

# 1. WITHOUT appsecret_proof
print("1. Send message WITHOUT appsecret_proof:")
url=f"https://graph.facebook.com/v20.0/{P}/messages"
payload=json.dumps({'messaging_product':'whatsapp','to':'919330994400','type':'text','text':{'body':'test no proof'}}).encode()
req=urllib.request.Request(url,data=payload,headers={'Authorization':f'Bearer {T}','Content-Type':'application/json'},method='POST')
try:
    with urllib.request.urlopen(req,timeout=15) as r: print(f"   OK: {r.read().decode()}")
except urllib.error.HTTPError as e: print(f"   {e.code}: {e.read().decode()[:300]}")

# 2. WITH appsecret_proof
print("\n2. Send message WITH appsecret_proof:")
proof=hmac.new(S.encode(),T.encode(),hashlib.sha256).hexdigest()
url2=f"https://graph.facebook.com/v20.0/{P}/messages?appsecret_proof={proof}"
req2=urllib.request.Request(url2,data=payload,headers={'Authorization':f'Bearer {T}','Content-Type':'application/json'},method='POST')
try:
    with urllib.request.urlopen(req2,timeout=15) as r: print(f"   OK: {r.read().decode()}")
except urllib.error.HTTPError as e: print(f"   {e.code}: {e.read().decode()[:300]}")

# 3. pre_accept WITHOUT proof
print("\n3. pre_accept WITHOUT appsecret_proof:")
url3=f"https://graph.facebook.com/v20.0/{P}/calls"
p2=json.dumps({'messaging_product':'whatsapp','call_id':'fake','action':'pre_accept'}).encode()
req3=urllib.request.Request(url3,data=p2,headers={'Authorization':f'Bearer {T}','Content-Type':'application/json'},method='POST')
try:
    with urllib.request.urlopen(req3,timeout=15) as r: print(f"   OK: {r.read().decode()}")
except urllib.error.HTTPError as e: print(f"   {e.code}: {e.read().decode()[:300]}")

# 4. pre_accept WITH proof
print("\n4. pre_accept WITH appsecret_proof:")
url4=f"https://graph.facebook.com/v20.0/{P}/calls?appsecret_proof={proof}"
req4=urllib.request.Request(url4,data=p2,headers={'Authorization':f'Bearer {T}','Content-Type':'application/json'},method='POST')
try:
    with urllib.request.urlopen(req4,timeout=15) as r: print(f"   OK: {r.read().decode()}")
except urllib.error.HTTPError as e: print(f"   {e.code}: {e.read().decode()[:300]}")

# 5. Try via AWS Social Messaging SDK instead of Graph API
print("\n5. Check if this WABA is on Cloud API hosted by Meta or via AWS EUM:")
url5=f"https://graph.facebook.com/v20.0/{P}?fields=display_phone_number,verified_name,platform_type,account_mode,messaging_limit_tier"
proof5=hmac.new(S.encode(),T.encode(),hashlib.sha256).hexdigest()
req5=urllib.request.Request(f"{url5}&appsecret_proof={proof5}",headers={'Authorization':f'Bearer {T}'})
try:
    with urllib.request.urlopen(req5,timeout=15) as r: print(f"   {r.read().decode()}")
except urllib.error.HTTPError as e: print(f"   {e.code}: {e.read().decode()[:300]}")

# 6. Check if phone is registered on Cloud API
print("\n6. Check WABA phone numbers:")
url6=f"https://graph.facebook.com/v20.0/1912405516040025/phone_numbers?fields=display_phone_number,verified_name,id"
req6=urllib.request.Request(f"{url6}&appsecret_proof={proof5}",headers={'Authorization':f'Bearer {T}'})
try:
    with urllib.request.urlopen(req6,timeout=15) as r: print(f"   {r.read().decode()}")
except urllib.error.HTTPError as e: print(f"   {e.code}: {e.read().decode()[:300]}")
