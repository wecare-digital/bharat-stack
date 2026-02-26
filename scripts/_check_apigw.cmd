@echo off
aws apigatewayv2 get-apis --query "Items[?Name=='wecare' || contains(Name,'wecare')].{Name:Name,Id:ApiId,Endpoint:ApiEndpoint}" --output json 2>&1
