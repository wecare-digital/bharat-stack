#!/bin/bash
# Deploy ai-generate-response Lambda function

FUNCTION_NAME="wecare-ai-generate-response"
HANDLER_PATH="amplify/functions/ai/ai-generate-response"

echo "Creating deployment package..."
cd $HANDLER_PATH
zip -r function.zip handler.py

echo "Deploying to AWS Lambda..."
aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb://function.zip \
  --region us-east-1

echo "Cleaning up..."
rm function.zip

echo "Deployment complete!"
