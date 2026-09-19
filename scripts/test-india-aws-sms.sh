#!/usr/bin/env bash
#
# §46: verify the India AWS End User Messaging route (ap-south-1 + TRAI DLT).
#
# Dry run by default, and that default matters more here than for the
# international route. A real send to an Indian number under an unregistered
# template is a DLT compliance event, not merely a failed message - the operator
# accepts the API call and drops the content, and repeated mismatches put the
# registered sender id at risk. DryRun makes AWS validate the sender id, the
# entity id and the template id without delivering.
#
#   scripts/test-india-aws-sms.sh
#   scripts/test-india-aws-sms.sh --template wd_order
#   scripts/test-india-aws-sms.sh --live --to +919903300044   # really delivers
#
# The body sent is the approved ivr-default content verbatim. Do not edit it:
# it must match the registered DLT template character for character.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
exec "$PY" scripts/aws_sms_check.py --india-only "$@"
