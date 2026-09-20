
import os,json,hmac,boto3
sm=boto3.client('secretsmanager',region_name='us-east-1')
lam=boto3.client('lambda',region_name='us-east-1')
SECRET_ID=os.environ.get('SECRET_ID','wecare/elevenlabs')
SMS_FUNCTION=os.environ.get('SMS_FUNCTION','wecare-sms-aws:live')
_cache=None
def get_secret():
    global _cache
    if _cache is None:
        _cache=json.loads(sm.get_secret_value(SecretId=SECRET_ID).get('SecretString') or '{}')
    return _cache
def resp(code,obj=None):
    r={'statusCode':code,'headers':{'Content-Type':'application/json','Cache-Control':'no-store'}}
    if obj is not None:r['body']=json.dumps(obj,separators=(',',':'))
    return r
def auth(event):
    h={str(k).lower():str(v) for k,v in (event.get('headers') or {}).items()}
    s=get_secret()
    return hmac.compare_digest(h.get('x-wecare-api-key',''),str(s.get('mcp_api_key',''))) and hmac.compare_digest(h.get('x-wecare-secret-key',''),str(s.get('mcp_secret_key','')))
def invoke_sms(a):
    phone=str(a.get('destination_phone_number') or a.get('phone') or a.get('to') or '').strip()
    content=str(a.get('content') or a.get('message') or '').strip()
    template=str(a.get('template_key') or a.get('templateKey') or 'ivr-default').strip()
    dry=bool(a.get('dry_run') if 'dry_run' in a else a.get('dryRun',False))
    if not phone:return {'ok':False,'statusCode':400,'error':'destination_phone_number is required'}
    if not content:return {'ok':False,'statusCode':400,'error':'content is required'}
    b={'phone':phone,'to':phone,'content':content,'templateKey':template,'template_key':template,'dryRun':dry,'dry_run':dry}
    ev={'httpMethod':'POST','requestContext':{'http':{'method':'POST','path':'/'}},'body':json.dumps(b)}
    x=lam.invoke(FunctionName=SMS_FUNCTION,InvocationType='RequestResponse',Payload=json.dumps(ev).encode())
    raw=x['Payload'].read().decode('utf-8','replace')
    try:o=json.loads(raw)
    except Exception:o={'statusCode':500,'body':raw}
    sc=int(o.get('statusCode',500)); body=o.get('body')
    if isinstance(body,str):
        try:body=json.loads(body)
        except Exception:pass
    return {'ok':200<=sc<300,'statusCode':sc,'result':body}
def handler(event,ctx):
    http=((event.get('requestContext') or {}).get('http') or {})
    method=http.get('method') or event.get('httpMethod') or 'POST'
    path=event.get('rawPath') or event.get('path') or '/'
    if method=='GET' and path in ('/','/health'):
        return resp(200,{'ok':True,'service':'wecare-elevenlabs-mcp','version':'1.1.0'})
    try:req=json.loads(event.get('body') or '{}')
    except Exception:return resp(400,{'error':'invalid_json'})
    m=req.get('method'); rid=req.get('id'); p=req.get('params') or {}
    if m=='initialize':
        pv=p.get('protocolVersion') or '2025-03-26'
        return resp(200,{'jsonrpc':'2.0','id':rid,'result':{'protocolVersion':pv,'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'wecare-aws-mcp','version':'1.1.0'}}})
    if m in ('notifications/initialized','notifications/cancelled'):
        return {'statusCode':202,'headers':{'Cache-Control':'no-store'}}
    if m=='ping':return resp(200,{'jsonrpc':'2.0','id':rid,'result':{}})
    if m=='tools/list':
        t={'name':'send_sms','description':'Validate or send WECARE.DIGITAL SMS through existing AWS routing. Without AWS MCP credentials only dry_run=true is permitted. India +91 uses ap-south-1 DLT; other numbers use us-east-1.','inputSchema':{'type':'object','properties':{'destination_phone_number':{'type':'string'},'content':{'type':'string'},'template_key':{'type':'string','default':'ivr-default'},'dry_run':{'type':'boolean','default':True}},'required':['destination_phone_number','content']}}
        return resp(200,{'jsonrpc':'2.0','id':rid,'result':{'tools':[t]}})
    if m=='tools/call':
        if p.get('name')!='send_sms':return resp(200,{'jsonrpc':'2.0','id':rid,'error':{'code':-32601,'message':'Unknown tool'}})
        a=p.get('arguments') or {}
        dry=bool(a.get('dry_run') if 'dry_run' in a else a.get('dryRun',True))
        if not dry and not auth(event):
            return resp(200,{'jsonrpc':'2.0','id':rid,'result':{'content':[{'type':'text','text':'Live SMS requires authenticated MCP headers.'}],'structuredContent':{'ok':False,'statusCode':401,'error':'live_send_requires_auth'},'isError':True}})
        a['dry_run']=dry
        r=invoke_sms(a)
        return resp(200,{'jsonrpc':'2.0','id':rid,'result':{'content':[{'type':'text','text':json.dumps(r,separators=(',',':'))}],'structuredContent':r,'isError':not r.get('ok',False)}})
    return resp(200,{'jsonrpc':'2.0','id':rid,'error':{'code':-32601,'message':'Method not found'}})
