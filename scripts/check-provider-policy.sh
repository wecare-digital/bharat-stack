#!/usr/bin/env bash
#
# Provider policy gate (spec §44).
#
# The approved provider architecture is:
#
#   normal SMS  (all countries)  -> AWS End User Messaging   ONLY
#   India RCS                    -> Sinch                    ONLY
#   non-India RCS                -> AWS End User Messaging RCS
#   PSTN voice / SIP / IVR       -> Plivo
#   WhatsApp msg + calling       -> Meta
#   Airtel                       -> prohibited entirely
#
# This script fails CI when runtime code violates that. It is deliberately
# scoped to RUNTIME code only:
#
#   scanned:  amplify/functions/**  src/**
#   ignored:  docs/**  .kiro/**  tests/**  scripts/**  *.md  node_modules  .next  out
#
# That scoping is not laziness. The migration documentation, the steering files
# and this script all necessarily NAME the prohibited providers, and historical
# message rows legitimately carry provider='sinch' or provider='airtel' to
# describe traffic that really was sent that way. A gate that flagged those would
# be switched off within a day, and a switched-off gate protects nothing.
#
# Exit codes
#   0  compliant
#   1  one or more violations
#   2  bad invocation
#
# Usage
#   scripts/check-provider-policy.sh              # gate mode
#   scripts/check-provider-policy.sh --verbose    # show every matching line
#   scripts/check-provider-policy.sh --expect-fail  # for migration CI: invert
#                                                   # so a PASS is the failure.
#                                                   # Used while Airtel/Sinch SMS
#                                                   # removal is still in flight.
set -uo pipefail

VERBOSE=0
EXPECT_FAIL=0
for arg in "$@"; do
  case "$arg" in
    --verbose) VERBOSE=1 ;;
    --expect-fail) EXPECT_FAIL=1 ;;
    -h|--help) sed -n '2,36p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$0")/.." || exit 2

SCAN_DIRS=()
[ -d amplify/functions ] && SCAN_DIRS+=(amplify/functions)
[ -d src ] && SCAN_DIRS+=(src)
if [ ${#SCAN_DIRS[@]} -eq 0 ]; then
  echo "nothing to scan (no amplify/functions or src)" >&2
  exit 2
fi

# Sinch RCS is APPROVED for India. These paths are where it is allowed to live.
# Anything Sinch outside them is a violation.
RCS_ALLOWED_RE='(sinch_rcs\.py|/rcs-send/|/rcs-dlr/|providers/sinch/rcs/|services/rcs/sinch/)'

VIOLATIONS=0
declare -a FAILED_RULES=()

# rule <id> <description> <extended-regex> [extra-filter-regex-to-EXCLUDE]
rule() {
  local id="$1" desc="$2" pattern="$3" exclude="${4:-}"
  local hits

  hits=$(grep -rIn --extended-regexp "$pattern" "${SCAN_DIRS[@]}" \
           --include='*.py' --include='*.ts' --include='*.tsx' --include='*.js' \
           --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=out \
           --exclude-dir=__pycache__ --exclude-dir=.venv 2>/dev/null || true)

  if [ -n "$exclude" ] && [ -n "$hits" ]; then
    hits=$(printf '%s\n' "$hits" | grep -vE "$exclude" || true)
  fi

  local count
  count=$(printf '%s' "$hits" | grep -c . || true)

  if [ "$count" -gt 0 ]; then
    printf '  FAIL  %-28s %s\n' "$id" "$desc"
    printf '        %s violation(s) in:\n' "$count"
    printf '%s\n' "$hits" | awk -F: '{print $1}' | sort -u | sed 's/^/          /'
    if [ "$VERBOSE" -eq 1 ]; then
      printf '%s\n' "$hits" | sed 's/^/          | /'
    fi
    VIOLATIONS=$((VIOLATIONS + count))
    FAILED_RULES+=("$id")
  else
    printf '  ok    %-28s %s\n' "$id" "$desc"
  fi
}

echo
echo "PROVIDER POLICY GATE"
echo "  scanning: ${SCAN_DIRS[*]}"
echo "  rule set: spec §44 / docs/provider-policy.md"
echo

# ─── Airtel: prohibited entirely (§2) ────────────────────────────────────────
# Matches the API hosts and the credential/config identifiers, not the word
# "airtel" in prose, so a comment explaining the removal does not trip it.
rule "airtel-runtime" \
     "no Airtel host, secret or client in runtime code" \
     '(iqmessaging\.airtel\.in|iqvoice\.airtel\.in|openapi\.airtel\.in|wecare/airtel|AIRTEL_IQ_|AIRTEL_SMS_|AIRTEL_KONG_|AIRTEL_C2C_|AIRTEL_OBD_|_send_airtel|_try_airtel|_call_airtel)'

# The Lightsail Airtel SMS proxy. Its only purpose is to give Airtel a
# whitelisted static IP, so a reference to it IS an Airtel reference.
rule "airtel-sms-proxy" \
     "no Lightsail Airtel SMS proxy (52.3.44.165:8899)" \
     '(52\.3\.44\.165|SMS_PROXY_URL)'

# ─── Sinch: India RCS only (§10) ─────────────────────────────────────────────
rule "sinch-sms-sender" \
     "no Sinch SMS sender" \
     '(jumbo\.aclgateway\.com|_send_sinch_sms|sendSinchSms|_load_sinch_sms_creds|wecare/sinch/sms|SINCH_SMS_)'

rule "sinch-voice-whatsapp" \
     "no Sinch voice or WhatsApp provider" \
     '(SINCH_VOICE_|SINCH_WHATSAPP_|sinch[_-]?voice|sinch[_-]?whatsapp)'

# The Sinch TRANSPORT — vendor hosts and credentials — must sit inside the
# approved RCS paths. Note this checks the transport, not its callers: §10 says
# "Sinch runtime modules should live only under clearly scoped RCS paths", so a
# Lambda importing `sinch_rcs` or reading SINCH_RCS_ENABLED is compliant. It is
# talking to the approved module, which is the whole point of having one. Only
# the module itself may hold the vendor endpoint and secret.
rule "sinch-outside-rcs" \
     "Sinch transport confined to the approved India RCS paths" \
     '(convapi\.aclwhatsapp\.com|auth\.aclwhatsapp\.com|wecare/sinch/rcs)' \
     "$RCS_ALLOWED_RE"

# ─── Plivo: voice only, never SMS (§6) ──────────────────────────────────────
rule "plivo-sms" \
     "no Plivo SMS sender" \
     '(PLIVO_SMS_|plivo.*send_message|Message/.*plivo|plivo.*/Message/)'

# ─── SMS must resolve to AWS (§38) ──────────────────────────────────────────
# Legacy AWS SMS transports. SNS SMS and classic Pinpoint send_messages are not
# AWS End User Messaging; only pinpoint-sms-voice-v2 is.
rule "legacy-aws-sms" \
     "no SNS SMS or classic Pinpoint send_messages for SMS" \
     '(AWS\.SNS\.SMS\.|pinpoint\.send_messages|PINPOINT_APP_ID)'

# A provider literal being assigned for an SMS send.
rule "sms-provider-literal" \
     "no SMS path assigning a non-AWS provider" \
     "(provider *= *['\"](sinch|airtel|plivo)['\"]|provider: *['\"](sinch|airtel|plivo)['\"])"

echo
if [ "$EXPECT_FAIL" -eq 1 ]; then
  if [ "$VIOLATIONS" -gt 0 ]; then
    echo "EXPECTED-FAIL MODE: $VIOLATIONS violation(s) present, as expected."
    echo "  failing rules: ${FAILED_RULES[*]}"
    echo "  This is the pre-migration baseline. Flip CI to gate mode once"
    echo "  Stage 3 of docs/migration-plan.md completes."
    exit 0
  fi
  echo "EXPECTED-FAIL MODE: no violations found."
  echo "  The migration is complete — remove --expect-fail and gate for real."
  exit 1
fi

if [ "$VIOLATIONS" -gt 0 ]; then
  echo "PROVIDER POLICY VIOLATED: $VIOLATIONS finding(s) across ${#FAILED_RULES[@]} rule(s)."
  echo "  failing rules: ${FAILED_RULES[*]}"
  echo
  echo "  AWS End User Messaging is the normal SMS provider for every country."
  echo "  Sinch is India RCS only. Plivo is voice only. Airtel is prohibited."
  echo "  See docs/provider-policy.md and docs/migration-plan.md."
  exit 1
fi

echo "PROVIDER POLICY OK — no violations."
exit 0
