@echo off
aws apigatewayv2 get-domain-names --query "Items[?DomainName=='api.wecare.digital']" --output json
