
import json,time,boto3
ddb=boto3.client('dynamodb',region_name='us-east-1')
TABLE='stack-wecare-digital-ElevenLabsCallContext'
TARGET='918031830030'
def response(c,o):return {'statusCode':c,'headers':{'Content-Type':'application/json','Cache-Control':'no-store'},'body':json.dumps(o,separators=(',',':'))}
def handler(event,ctx):
    if ((event.get('requestContext') or {}).get('http') or {}).get('method')!='POST':return response(405,{'error':'method_not_allowed'})
    try:d=json.loads(event.get('body') or '{}')
    except Exception:return response(400,{'error':'invalid_json'})
    conv=str(d.get('conversation_id') or '').strip()
    caller=str(d.get('caller_id') or '').strip()
    called=str(d.get('called_number') or '').strip()
    call_id=str(d.get('call_id') or d.get('call_sid') or '').strip()
    digits=''.join(c for c in called if c.isdigit())
    if not conv or not caller:return response(400,{'error':'missing_context'})
    if digits and not digits.endswith(TARGET):return response(403,{'error':'wrong_destination'})
    now=int(time.time())
    ddb.put_item(TableName=TABLE,Item={
      'conversation_id':{'S':conv},'caller_phone':{'S':caller},'called_number':{'S':called},
      'call_id':{'S':call_id},'created_at':{'N':str(now)},'expires_at':{'N':str(now+172800)}
    })
    return response(200,{'type':'conversation_initiation_client_data','dynamic_variables':{
      'caller_phone':caller,'called_number':called,'call_id':call_id}})
