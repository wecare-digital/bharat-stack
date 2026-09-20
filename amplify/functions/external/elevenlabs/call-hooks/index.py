
import os,json,time,hmac,hashlib,boto3,base64
ddb=boto3.client('dynamodb',region_name='us-east-1')
sm=boto3.client('secretsmanager',region_name='us-east-1')
lam=boto3.client('lambda',region_name='us-east-1')
TABLE=os.environ['TABLE_NAME']
SECRET_ID=os.environ.get('SECRET_ID','wecare/elevenlabs')
AGENT_ID=os.environ['AGENT_ID']
SMS_FUNCTION=os.environ.get('SMS_FUNCTION','wecare-sms-aws:live')
PERSIST_FUNCTION=os.environ.get('PERSIST_FUNCTION','wecare-elevenlabs-webhook:live')
SMS_BODY=("Thanks for contacting WECARE.DIGITAL!\n\n"
          "Submit your request here: https://wecare.digital/selfservice "
          "or send us a message / voice note on WhatsApp: https://r.wecare.digital/wa.\n\n"
          "We'll review it and follow up if needed.")
_cache=None
def sec():
    global _cache
    if _cache is None:
        _cache=json.loads(sm.get_secret_value(SecretId=SECRET_ID).get('SecretString') or '{}')
    return _cache
def resp(code,obj):
    return {'statusCode':code,'headers':{'Content-Type':'application/json','Cache-Control':'no-store'},'body':json.dumps(obj,separators=(',',':'))}
def body_text(event):
    raw=event.get('body') or ''
    if event.get('isBase64Encoded'):
        raw=base64.b64decode(raw).decode('utf-8','replace')
    return raw
def headers(event):
    return {str(k).lower():str(v) for k,v in (event.get('headers') or {}).items()}
def init_handler(event):
    token=headers(event).get('x-wecare-call-hook-token','')
    expected=str(sec().get('call_init_token',''))
    if not expected or not hmac.compare_digest(token,expected):
        return resp(401,{'error':'unauthorized'})
    try:d=json.loads(body_text(event) or '{}')
    except Exception:return resp(400,{'error':'invalid_json'})
    conv=str(d.get('conversation_id') or '').strip()
    caller=str(d.get('caller_id') or '').strip()
    called=str(d.get('called_number') or '').strip()
    call_id=str(d.get('call_id') or d.get('call_sid') or '').strip()
    if conv and caller:
        now=int(time.time())
        ddb.put_item(TableName=TABLE,Item={
          'conversation_id':{'S':conv},'caller_phone':{'S':caller},
          'called_number':{'S':called},'call_id':{'S':call_id},
          'created_at':{'N':str(now)},'expires_at':{'N':str(now+172800)}
        })
    return resp(200,{'type':'conversation_initiation_client_data','dynamic_variables':{
      'caller_phone':caller,'called_number':called,'call_id':call_id
    }})
def verify_post(raw,sig):
    secret=str(sec().get('post_call_webhook_secret',''))
    if not secret or not sig:return False
    parts={}
    for p in sig.split(','):
        if '=' in p:
            k,v=p.split('=',1);parts.setdefault(k.strip(),[]).append(v.strip())
    ts=(parts.get('t') or [None])[0]; vals=parts.get('v0') or []
    if not ts or not vals:return False
    try:
        if abs(int(time.time())-int(ts))>1800:return False
    except Exception:return False
    expected=hmac.new(secret.encode(),(ts+'.'+raw).encode(),hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(v,expected) for v in vals)
def forward_persistence(raw):
    old_secret=str(sec().get('webhook_secret',''))
    if not old_secret:return {'ok':False,'error':'missing_persistence_secret'}
    ts=str(int(time.time()))
    digest=hmac.new(old_secret.encode(),(ts+'.'+raw).encode(),hashlib.sha256).hexdigest()
    ev={
      'version':'2.0','rawPath':'/elevenlabs/webhook',
      'requestContext':{'http':{'method':'POST','path':'/elevenlabs/webhook'}},
      'headers':{'content-type':'application/json','elevenlabs-signature':f't={ts},v0={digest}'},
      'body':raw,'isBase64Encoded':False
    }
    r=lam.invoke(FunctionName=PERSIST_FUNCTION,InvocationType='RequestResponse',Payload=json.dumps(ev).encode())
    p=r['Payload'].read().decode('utf-8','replace')
    try:o=json.loads(p)
    except Exception:o={'statusCode':500,'body':p}
    sc=int(o.get('statusCode',500))
    return {'ok':200<=sc<300,'statusCode':sc}
def normalize_phone(phone):
    s=str(phone or '').strip(); digits=''.join(c for c in s if c.isdigit())
    if s.startswith('+'):return '+'+digits
    if digits.startswith('00'):return '+'+digits[2:]
    if len(digits)>=10:return '+'+digits
    return ''
def queue_sms(phone):
    p=normalize_phone(phone)
    if not p:return {'ok':False,'error':'invalid_phone'}
    digits=''.join(c for c in p if c.isdigit())
    india=digits.startswith('91') and len(digits)==12
    b={'phoneNumber':p,'content':SMS_BODY,'messageType':'TRANSACTIONAL','campaignName':'elevenlabs-ivr-follow-up'}
    if india:b['dltTemplateKey']='ivr-default'
    ev={'requestContext':{'http':{'method':'POST','path':'/sms-aws/send'}},
        'headers':{'origin':'https://app.wecare.digital'},'body':json.dumps(b)}
    lam.invoke(FunctionName=SMS_FUNCTION,InvocationType='Event',Payload=json.dumps(ev).encode())
    return {'ok':True,'route':'ap-south-1' if india else 'us-east-1'}
def post_handler(event):
    raw=body_text(event)
    if not verify_post(raw,headers(event).get('elevenlabs-signature','')):
        return resp(401,{'error':'invalid_signature'})
    persisted=forward_persistence(raw)
    if not persisted.get('ok'):
        return resp(500,{'error':'transcript_persist_failed'})
    try:e=json.loads(raw or '{}')
    except Exception:return resp(400,{'error':'invalid_json'})
    if e.get('type')!='post_call_transcription':
        return resp(200,{'status':'persisted_ignored'})
    d=e.get('data') or {}
    if d.get('agent_id')!=AGENT_ID:
        return resp(200,{'status':'persisted_ignored_agent'})
    conv=str(d.get('conversation_id') or '').strip()
    if not conv:return resp(200,{'status':'persisted_missing_conversation'})
    got=ddb.get_item(TableName=TABLE,Key={'conversation_id':{'S':conv}},ConsistentRead=True).get('Item') or {}
    phone=(got.get('caller_phone') or {}).get('S','')
    if not phone:
        ci=d.get('conversation_initiation_client_data') or {}
        dv=ci.get('dynamic_variables') or {}
        phone=dv.get('caller_phone') or dv.get('system__caller_id') or ''
    if not phone:return resp(200,{'status':'persisted_no_caller_phone'})
    now=int(time.time())
    try:
        ddb.update_item(TableName=TABLE,Key={'conversation_id':{'S':conv}},
          UpdateExpression='SET sms_lock=:n',
          ConditionExpression='attribute_not_exists(sms_sent_at) AND attribute_not_exists(sms_lock)',
          ExpressionAttributeValues={':n':{'N':str(now)}})
    except Exception as ex:
        if 'ConditionalCheckFailed' in str(ex):return resp(200,{'status':'already_processed'})
        raise
    try:
        result=queue_sms(phone)
        ddb.update_item(TableName=TABLE,Key={'conversation_id':{'S':conv}},
          UpdateExpression='SET sms_sent_at=:n, sms_route=:r REMOVE sms_lock',
          ExpressionAttributeValues={':n':{'N':str(now)},':r':{'S':result.get('route','')}})
        return resp(200,{'status':'sms_queued','route':result.get('route')})
    except Exception:
        try:ddb.update_item(TableName=TABLE,Key={'conversation_id':{'S':conv}},UpdateExpression='REMOVE sms_lock')
        except Exception:pass
        return resp(500,{'error':'sms_queue_failed'})
def handler(event,ctx):
    path=event.get('rawPath') or event.get('path') or '/'
    method=((event.get('requestContext') or {}).get('http') or {}).get('method') or event.get('httpMethod') or 'POST'
    if method=='GET' and path=='/health':return resp(200,{'ok':True,'service':'wecare-elevenlabs-call-hooks','account':'775261844268'})
    if method=='POST' and path=='/init':return init_handler(event)
    if method=='POST' and path=='/post-call':return post_handler(event)
    return resp(404,{'error':'not_found'})
