@echo off
aws apigatewayv2 get-routes --api-id zllr9lrg7j --query "Items[?contains(RouteKey,'whatsapp')].{RouteKey:RouteKey,Target:Target}" --output json 2>&1
