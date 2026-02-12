import boto3

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Check SystemConfig table
table_name = 'base-wecare-digital-SystemConfigTable'
try:
    table = dynamodb.Table(table_name)
    
    # Check auto_pickup config
    result = table.get_item(Key={'id': 'whatsapp_calling_auto_pickup'})
    item = result.get('Item')
    print(f"auto_pickup config: {item}")
    
    # Check auto_pickup_mode
    result2 = table.get_item(Key={'id': 'whatsapp_calling_auto_pickup_mode'})
    item2 = result2.get('Item')
    print(f"auto_pickup_mode config: {item2}")
    
    # Check IVR URL
    result3 = table.get_item(Key={'id': 'whatsapp_calling_ivr_url'})
    item3 = result3.get('Item')
    print(f"ivr_url config: {item3}")
    
    # Scan all items to see what's there
    scan = table.scan(Limit=20)
    print(f"\nAll config items ({scan.get('Count', 0)}):")
    for i in scan.get('Items', []):
        print(f"  {i.get('id')}: {i.get('configValue')}")
        
except Exception as e:
    print(f"Error: {e}")
    # Try listing tables to find the right name
    client = boto3.client('dynamodb', region_name='us-east-1')
    tables = client.list_tables()['TableNames']
    config_tables = [t for t in tables if 'config' in t.lower() or 'system' in t.lower()]
    print(f"Config-related tables: {config_tables}")
    all_calling = [t for t in tables if 'calling' in t.lower() or 'whatsapp' in t.lower()]
    print(f"Calling-related tables: {all_calling}")
