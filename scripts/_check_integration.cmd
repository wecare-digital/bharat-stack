@echo off
aws apigatewayv2 get-integration --api-id zllr9lrg7j --integration-id vlz7fmp --query "{IntegrationUri:IntegrationUri,IntegrationType:IntegrationType}" --output json 2>&1
