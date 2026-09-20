
import json,time,boto3
ddb=boto3.client('dynamodb',region_name='us-east-1')
lam=boto3.client('lambda',region_name='us-east-1')
CTX='stack-wecare-digital-ElevenLabsCallContext'
AGENT='agent_6601m2wb000jfbqs9xfzhmmtvr0y'
SMS='wecare-sms-aws:live'
BODY=("Thanks for contacting WECARE.DIGITAL!\n\n"
"Submit your request here: https://wecare.digital/selfservice "
"or send us a message / voice note on WhatsApp: https://r.wecare.digital/wa.\n\n"
"We'll review it and follow up if needed.")
def sval(m,k):return ((m.get(k) or {}).get('S') or '')
def handler(event,ctx):
    processed=0
    for rec in event.get('Records',[]):
        if rec.get('eventName') not in ('INSERT','MODIFY'):continue
        img=((rec.get('dynamodb') or {}).get('NewImage') or {})
        if not sval(img,'id').startswith('elevenlabs#'):continue
        if sval(img,'event_type')!='post_call_transcription':continue
        if sval(img,'agent_id')!=AGENT:continue
        conv=sval(img,'conversation_id')
        if not conv:continue
        item=ddb.get_item(TableName=CTX,Key={'conversation_id':{'S':conv}},ConsistentRead=True).get('Item') or {}
        phone=sval(item,'caller_phone')
        if not phone:continue
        now=int(time.time())
        try:
            ddb.update_item(TableName=CTX,Key={'conversation_id':{'S':conv}},
              UpdateExpression='SET sms_lock=:n',
              ConditionExpression='attribute_not_exists(sms_sent_at) AND attribute_not_exists(sms_lock)',
              ExpressionAttributeValues={':n':{'N':str(now)}})
        except Exception as e:
            if 'ConditionalCheckFailed' in str(e):continue
            raise
        try:
            digits=''.join(c for c in phone if c.isdigit())
            p='+'+digits[2:] if digits.startswith('00') else ('+'+digits if not phone.startswith('+') else '+'+digits)
            india=digits.startswith('91') and len(digits)==12
            b={'phoneNumber':p,'content':BODY,'messageType':'TRANSACTIONAL','campaignName':'elevenlabs-ivr-follow-up'}
            if india:b['dltTemplateKey']='ivr-default'
            ev={'requestContext':{'http':{'method':'POST','path':'/sms-aws/send'}},
                'headers':{'origin':'https://app.wecare.digital'},'body':json.dumps(b)}
            lam.invoke(FunctionName=SMS,InvocationType='Event',Payload=json.dumps(ev).encode())
            route='ap-south-1' if india else 'us-east-1'
            ddb.update_item(TableName=CTX,Key={'conversation_id':{'S':conv}},
              UpdateExpression='SET sms_sent_at=:n, sms_route=:r REMOVE sms_lock',
              ExpressionAttributeValues={':n':{'N':str(now)},':r':{'S':route}})
            processed+=1
        except Exception:
            try:ddb.update_item(TableName=CTX,Key={'conversation_id':{'S':conv}},UpdateExpression='REMOVE sms_lock')
            except Exception:pass
            raise
    return {'processed':processed}
