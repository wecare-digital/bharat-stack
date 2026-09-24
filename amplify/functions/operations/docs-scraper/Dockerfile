# Meta / external documentation scraper — WECARE.DIGITAL
# Playwright + headless Chromium is far larger than the 250MB zip limit,
# so this Lambda is packaged as a container image (deploy via ECR).
#
# Build context is the repository root (see docs-scraper-deploy.yml) because
# handler.py imports amplify/functions/shared/lambda_utils.
FROM mcr.microsoft.com/playwright/python:v1.63.0-jammy

WORKDIR /var/task

COPY amplify/functions/operations/docs-scraper/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt awslambdaric

# Chromium is included in the Playwright image; this keeps the browser version
# aligned with the Python Playwright package.
RUN python -m playwright install chromium

COPY amplify/functions/operations/docs-scraper/handler.py ./handler.py
COPY amplify/functions/shared/lambda_utils ./lambda_utils

ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["handler.lambda_handler"]
