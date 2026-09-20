
import json,urllib.request,urllib.error,boto3
sm=boto3.client('secretsmanager',region_name='us-east-1')
def handler(event,ctx):
    s=json.loads(sm.get_secret_value(SecretId='wecare/elevenlabs').get('SecretString') or '{}')
    key=s.get('api_key')
    body={'conversation_initiation_client_data_webhook':{'url':'https://ppq3shpmbd.execute-api.us-east-1.amazonaws.com/init','request_headers':{}}}
    req=urllib.request.Request('https://api.elevenlabs.io/v1/convai/settings',
      data=json.dumps(body).encode(),method='PATCH',
      headers={'xi-api-key':key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            data=json.loads(r.read().decode() or '{}')
        cfg=data.get('conversation_initiation_client_data_webhook') or {}
        return {'ok':True,'status':r.status,'init_url':cfg.get('url'),'can_use_mcp_servers':data.get('can_use_mcp_servers')}
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        return {'ok':False,'status':e.code,'error':raw[:1000]}
