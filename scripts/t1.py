import json,hmac,hashlib,urllib.request,urllib.error,urllib.parse,time,boto3
T="EAAf0L77jdagBQppO7QZCuPoaiL4G76snYzvw0e8PlTjiSsKrdXKQhXcZA34xJCkFasl2LqMGkCIwru4ThtxXqOUcmYUlkmicUTsnHFg1wWbDqp0xfEuYdr92BGSB0d07iRZBY17ZCCHPwIhl19C3buqpQXxkxHEcpReI9T63xT2KF61SXrgyZCJLVPggsmwZDZD"
S="9c146c26b6adc338472ac205b158b3d5"
A="2238810740192680"
P="960395407161423"
W="1912405516040025"
CB="https://api.wecare.digital/whatsapp-calling"
VT="wecare_calling_verify_2026"
FIELDS=["account_alerts","account_review_update","account_settings_update","account_update","automatic_events","business_capability_update","business_status_update","calls","flows","group_lifecycle_update","group_participants_update","group_settings_update","group_status_update","history","message_echoes","message_template_components_update","message_template_quality_update","message_template_status_update","messages","messaging_handovers","partner_solutions","payment_configuration_update","phone_number_name_update","phone_number_quality_update","security","smb_app_state_sync","smb_message_echoes","template_category_update","template_correct_category_detection","tracking_events","user_preferences"]

def api(url,method='GET',payload=None):
    proof=hmac.new(S.encode(),T.encode(),hashlib.sha256).hexdigest()
    sep='&' if '?' in url else '?'
    h={'Authorization':f'Bearer {T}','Content-Type':'application/json'}
    d=json.dumps(payload).encode() if payload else None
    req=urllib.request.Request(f"{url}{sep}appsecret_proof={proof}",data=d,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=15) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e: return {'error':e.code,'detail':e.read().decode()[:300]}

# 1. debug_token
print("1. debug_token:")
url=f"https://graph.facebook.com/v20.0/debug_token?input_token={T}&access_token={A}|{S}"
try:
    with urllib.request.urlopen(urllib.request.Request(url),timeout=15) as r:
        d=json.loads(r.read().decode())['data']
        print(f"   user_id={d.get('user_id')} app={d.get('application')}")
        for gs in d.get('granular_scopes',[]):
            t=gs.get('target_ids')
            print(f"   {gs['scope']}: {t if t else 'ALL'}")
except Exception as e: print(f"   {e}")

# 2. phone access
print("\n2. Phone access:")
print(f"   {api(f'https://graph.facebook.com/v20.0/{P}?fields=display_phone_number,verified_name')}")

# 3. send message
print("\n3. Send message:")
r=api(f'https://graph.facebook.com/v20.0/{P}/messages','POST',{'messaging_product':'whatsapp','to':'919330994400','type':'text','text':{'body':'test'}})
print(f"   {r}")
ok_msg='error' not in r or r.get('error')!=403
print(f"   {'OK' if ok_msg else 'FAIL 403'}")

# 4. pre_accept
print("\n4. pre_accept:")
r=api(f'https://graph.facebook.com/v20.0/{P}/calls','POST',{'messaging_product':'whatsapp','call_id':'fake','action':'pre_accept'})
print(f"   {r}")
if r.get('error')==403 and 'permissions' in str(r.get('detail','')).lower():
    print("   ❌ 403 PERMISSION ERROR")
else:
    print("   ✅ PERMISSIONS OK")

# 5. Subscribe webhooks
print("\n5. WABA subscribe:")
r=api(f'https://graph.facebook.com/v20.0/{W}/subscribed_apps','POST')
print(f"   {r}")

print("\n6. App-level webhooks:")
url=f"https://graph.facebook.com/oauth/access_token?client_id={A}&client_secret={S}&grant_type=client_credentials"
try:
    with urllib.request.urlopen(urllib.request.Request(url),timeout=15) as r:
        at=json.loads(r.read().decode())['access_token']
except: at=None; print("   no app token")
if at:
    ok,fail=[],[]
    for f in FIELDS:
        d=urllib.parse.urlencode({'object':'whatsapp_business_account','callback_url':CB,'verify_token':VT,'fields':f}).encode()
        req=urllib.request.Request(f"https://graph.facebook.com/v20.0/{A}/subscriptions",data=d,headers={'Authorization':f'Bearer {at}','Content-Type':'application/x-www-form-urlencoded'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=15) as r:
                rr=json.loads(r.read().decode())
                (ok if rr.get('success') else fail).append(f)
        except: fail.append(f)
        time.sleep(0.2)
    print(f"   {len(ok)}/{len(FIELDS)} subscribed")
    if fail: print(f"   Failed: {', '.join(fail)}")
