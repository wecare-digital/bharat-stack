#!/usr/bin/env bash
#
# §46: verify the international AWS End User Messaging route (us-east-1).
#
# Dry run by default: AWS validates the origination identity and destination and
# returns a MessageId without delivering and without spending.
#
#   scripts/test-aws-sms.sh
#   scripts/test-aws-sms.sh --to +14255551234
#   scripts/test-aws-sms.sh --live --to +14255551234    # really delivers
#
# Prints no credential values. Destinations are truncated to the last 4 digits.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
exec "$PY" scripts/aws_sms_check.py --intl-only "$@"
