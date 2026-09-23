# Meta / external documentation scraper — WECARE.DIGITAL
# Playwright + headless Chromium is far larger than the 250MB zip limit,
# so this Lambda is packaged as a container image (deploy via ECR).
FROM mcr.microsoft.com/playwright/python:v1.63.0-jammy

# AWS Lambda Runtime Interface Client so the container works as a Lambda.
WORKDIR /var/task
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt awslambdaric

# Chromium is already installed in the base image; ensure it's present.
RUN python -m playwright install chromium

COPY handler.py .

# Lambda entrypoint -> handler.lambda_handler
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["handler.lambda_handler"]
