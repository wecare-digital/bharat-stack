@echo off
aws apigatewayv2 get-routes --api-id zllr9lrg7j --query "Items[?RouteKey=='POST /whatsapp/send']" --output json
