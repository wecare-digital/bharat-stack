#!/usr/bin/env bash
#
# WECARE.DIGITAL — Google Cloud authorization + credential mirroring
#
# Design decision: AWS Secrets Manager is the SOURCE OF TRUTH. Google Cloud
# Secret Manager is a MIRROR, so a fresh machine (or a reset Kiro session) can
# recover credentials from either side. Values only ever flow AWS -> GCP here,
# never the reverse, so there is exactly one authoritative copy.
#
# Nothing is echoed. Every value moves through stdin or a 0600 temp file that is
# shredded on exit, so no secret lands in argv (visible via `ps`) or in shell
# history.
#
# Requires: gcloud, aws, jq
#
# Usage:
#   ./scripts/google-cloud-setup.sh auth            # activate the service account
#   ./scripts/google-cloud-setup.sh enable-apis     # turn on the APIs we call
#   ./scripts/google-cloud-setup.sh restrict-key    # least-privilege the API key
#   ./scripts/google-cloud-setup.sh mirror-secrets  # AWS -> GCP Secret Manager
#   ./scripts/google-cloud-setup.sh rotate-sa-key   # new SA key, retire the old
#   ./scripts/google-cloud-setup.sh verify          # prove it all works
#   ./scripts/google-cloud-setup.sh all             # auth + enable + restrict + verify
#
#   DRY_RUN=1 ./scripts/google-cloud-setup.sh <cmd>   # print, change nothing

set -euo pipefail

# ── configuration ─────────────────────────────────────────────────────────────
GCP_PROJECT="${GCP_PROJECT:-wecaredigitalbw}"
AWS_PROFILE="${AWS_PROFILE:-wecare-stack}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Secret in AWS holding the Google service-account JSON.
SA_SECRET="wecare/seo/google-oauth"

# APIs this project actually calls. Anything not listed stays off.
REQUIRED_APIS=(
  searchconsole.googleapis.com     # Search Analytics, URL Inspection, Sitemaps
  pagespeedonline.googleapis.com   # PageSpeed Insights v5
  chromeuxreport.googleapis.com    # CrUX field data
  secretmanager.googleapis.com     # the mirror target below
  iamcredentials.googleapis.com    # short-lived token minting
)

# API-key restriction target. The SEO key needs only these two; both accept
# API-key auth. Search Console does NOT (it requires a principal), so it is
# deliberately absent.
API_KEY_TARGETS=(
  pagespeedonline.googleapis.com
  chromeuxreport.googleapis.com
)

# AWS secret -> GCP secret name. Add rows as new credentials appear.
# Left  = AWS Secrets Manager id
# Right = Google Cloud Secret Manager name (no slashes allowed in GCP)
MIRROR_MAP=(
  "wecare/seo/google-oauth:wecare-seo-google-oauth"
  "wecare/google-api-key:wecare-google-api-key"
  "wecare/razorpay-webhook:wecare-razorpay-webhook"
  "wecare/meta-system-user-token:wecare-meta-system-user-token"
  "wecare/wix-api-key:wecare-wix-api-key"
  "wecare/github-pat:wecare-github-pat"
)

DRY_RUN="${DRY_RUN:-0}"

# ── plumbing ──────────────────────────────────────────────────────────────────
RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; DIM=$'\033[2m'; RST=$'\033[0m'
info() { printf '%s\n' "$*"; }
ok()   { printf '%s  OK%s %s\n' "$GRN" "$RST" "$*"; }
warn() { printf '%s  !!%s %s\n' "$YEL" "$RST" "$*"; }
die()  { printf '%s ERROR%s %s\n' "$RED" "$RST" "$*" >&2; exit 1; }
run()  { if [[ "$DRY_RUN" == "1" ]]; then printf '%s  DRY %s%s\n' "$DIM" "$*" "$RST"; else "$@"; fi; }

TMPDIR_SECURE="$(mktemp -d)"
chmod 700 "$TMPDIR_SECURE"
cleanup() {
  if [[ -d "$TMPDIR_SECURE" ]]; then
    find "$TMPDIR_SECURE" -type f -exec sh -c 'command -v shred >/dev/null 2>&1 && shred -u "$1" || rm -f "$1"' _ {} \; 2>/dev/null || true
    rm -rf "$TMPDIR_SECURE"
  fi
}
trap cleanup EXIT INT TERM

need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required but not installed"; }
preflight() {
  need gcloud; need aws; need jq
  aws sts get-caller-identity --profile "$AWS_PROFILE" >/dev/null 2>&1 \
    || die "AWS profile '$AWS_PROFILE' cannot authenticate. Run: aws login --profile $AWS_PROFILE"
}

# Fetch an AWS secret to a 0600 file. Never returns the value on stdout.
fetch_aws_secret_to_file() {
  local secret_id="$1" out="$2"
  ( umask 077; : > "$out" )
  if ! aws secretsmanager get-secret-value \
        --secret-id "$secret_id" \
        --profile "$AWS_PROFILE" --region "$AWS_REGION" \
        --query SecretString --output text > "$out" 2>/dev/null; then
    return 1
  fi
  [[ -s "$out" ]] || return 1
  return 0
}

# ── commands ──────────────────────────────────────────────────────────────────

cmd_auth() {
  info "== activate service account =="
  local kf="$TMPDIR_SECURE/sa.json"
  fetch_aws_secret_to_file "$SA_SECRET" "$kf" \
    || die "could not read $SA_SECRET from AWS Secrets Manager"

  jq -e '.type == "service_account"' "$kf" >/dev/null 2>&1 \
    || die "$SA_SECRET does not contain service-account JSON"

  local email project kid
  email="$(jq -r '.client_email' "$kf")"
  project="$(jq -r '.project_id' "$kf")"
  kid="$(jq -r '.private_key_id' "$kf")"
  info "  client_email   : $email"
  info "  project_id     : $project"
  info "  private_key_id : $kid"

  run gcloud auth activate-service-account "$email" --key-file="$kf" --quiet
  run gcloud config set project "$GCP_PROJECT" --quiet
  ok "authenticated as $email on $GCP_PROJECT"

  info ""
  info "  reminder: Search Console access is NOT granted here. There is no"
  info "  gcloud/API surface for Search Console user management, so this is"
  info "  irreducibly manual:"
  info "    Search Console -> Settings -> Users and permissions -> Add user"
  info "    -> $email -> Restricted"
}

cmd_enable_apis() {
  info "== enable required APIs on $GCP_PROJECT =="
  for api in "${REQUIRED_APIS[@]}"; do
    if gcloud services list --enabled --project "$GCP_PROJECT" \
         --filter="config.name=$api" --format='value(config.name)' 2>/dev/null | grep -q .; then
      ok "$api already enabled"
    else
      run gcloud services enable "$api" --project "$GCP_PROJECT" --quiet
      ok "$api enabled"
    fi
  done
}

cmd_restrict_key() {
  info "== restrict the SEO API key to least privilege =="
  local keys
  keys="$(gcloud services api-keys list --project "$GCP_PROJECT" \
            --format='value(name,displayName)' 2>/dev/null || true)"
  [[ -n "$keys" ]] || { warn "no API keys found in $GCP_PROJECT"; return 0; }

  info "  keys in project:"
  printf '%s\n' "$keys" | while IFS=$'\t' read -r name display; do
    info "    $display  ($name)"
  done

  local target
  target="$(printf '%s\n' "$keys" | awk -F'\t' '/[Ss][Ee][Oo]|[Uu]nified/ {print $1; exit}')"
  [[ -n "$target" ]] || target="$(printf '%s\n' "$keys" | head -n1 | cut -f1)"
  info "  restricting: $target"

  local args=()
  for t in "${API_KEY_TARGETS[@]}"; do args+=( "--api-target=service=$t" ); done

  info "  target set: ${API_KEY_TARGETS[*]}"
  info "  note: this REPLACES the existing allow-list. Anything relying on this"
  info "        key for another API will start failing, by design."
  run gcloud services api-keys update "$target" "${args[@]}" --quiet
  ok "key restricted to ${#API_KEY_TARGETS[@]} APIs"
}

cmd_mirror_secrets() {
  info "== mirror AWS Secrets Manager -> GCP Secret Manager =="
  info "  direction is one-way. AWS stays authoritative."
  info ""
  local created=0 updated=0 skipped=0 missing=0

  for row in "${MIRROR_MAP[@]}"; do
    local aws_id="${row%%:*}" gcp_name="${row##*:}"
    local f="$TMPDIR_SECURE/mirror.bin"

    if ! fetch_aws_secret_to_file "$aws_id" "$f"; then
      warn "$aws_id not present in AWS, skipping"
      missing=$((missing + 1))
      continue
    fi

    # refuse to mirror obvious placeholders
    if grep -qE 'YOUR_|CHANGEME|CHANGE_ME|REPLACE_ME' "$f"; then
      warn "$aws_id looks like a placeholder, refusing to mirror"
      skipped=$((skipped + 1))
      rm -f "$f"
      continue
    fi

    if gcloud secrets describe "$gcp_name" --project "$GCP_PROJECT" >/dev/null 2>&1; then
      # only add a version if the payload actually differs
      local cur="$TMPDIR_SECURE/cur.bin"
      if gcloud secrets versions access latest --secret "$gcp_name" \
           --project "$GCP_PROJECT" > "$cur" 2>/dev/null && cmp -s "$f" "$cur"; then
        ok "$gcp_name unchanged"
        skipped=$((skipped + 1))
      else
        run gcloud secrets versions add "$gcp_name" --project "$GCP_PROJECT" --data-file="$f" --quiet
        ok "$gcp_name new version added"
        updated=$((updated + 1))
      fi
      rm -f "$cur"
    else
      run gcloud secrets create "$gcp_name" --project "$GCP_PROJECT" \
        --replication-policy=automatic --data-file="$f" --quiet
      ok "$gcp_name created"
      created=$((created + 1))
    fi
    rm -f "$f"
  done

  info ""
  info "  created=$created updated=$updated unchanged=$skipped absent=$missing"
  info ""
  info "  to pull a credential back on a fresh machine:"
  info "    gcloud secrets versions access latest --secret wecare-seo-google-oauth \\"
  info "      --project $GCP_PROJECT"
}

cmd_rotate_sa_key() {
  info "== rotate the service-account key =="
  local kf="$TMPDIR_SECURE/sa.json"
  fetch_aws_secret_to_file "$SA_SECRET" "$kf" || die "cannot read $SA_SECRET"

  local email old_kid
  email="$(jq -r '.client_email' "$kf")"
  old_kid="$(jq -r '.private_key_id' "$kf")"
  info "  service account : $email"
  info "  current key id  : $old_kid"

  local new="$TMPDIR_SECURE/new-sa.json"
  ( umask 077; : > "$new" )

  if [[ "$DRY_RUN" == "1" ]]; then
    printf '%s  DRY would create a new key, push to AWS, then delete %s%s\n' "$DIM" "$old_kid" "$RST"
    return 0
  fi

  gcloud iam service-accounts keys create "$new" \
    --iam-account "$email" --project "$GCP_PROJECT" --quiet
  jq -e '.type == "service_account"' "$new" >/dev/null || die "new key looks malformed"
  local new_kid; new_kid="$(jq -r '.private_key_id' "$new")"
  ok "created key $new_kid"

  # push new value FIRST, so the old key is only removed once the
  # replacement is durably stored
  aws secretsmanager put-secret-value --secret-id "$SA_SECRET" \
    --secret-string "fileb://$new" \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --query VersionId --output text >/dev/null
  ok "stored in AWS $SA_SECRET (previous kept as AWSPREVIOUS)"

  # prove the new key works before destroying the old one
  gcloud auth activate-service-account "$email" --key-file="$new" --quiet
  gcloud auth print-access-token >/dev/null 2>&1 \
    || die "new key cannot mint a token — NOT deleting the old key"
  ok "new key verified"

  gcloud iam service-accounts keys delete "$old_kid" \
    --iam-account "$email" --project "$GCP_PROJECT" --quiet
  ok "old key $old_kid deleted"

  info "  re-run 'mirror-secrets' to refresh the GCP copy."
}

cmd_verify() {
  info "== verify =="
  info "-- active gcloud identity --"
  gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null || warn "none"

  info ""
  info "-- enabled APIs (of the ones we need) --"
  for api in "${REQUIRED_APIS[@]}"; do
    if gcloud services list --enabled --project "$GCP_PROJECT" \
         --filter="config.name=$api" --format='value(config.name)' 2>/dev/null | grep -q .; then
      ok "$api"
    else
      warn "$api NOT enabled"
    fi
  done

  info ""
  info "-- API key restrictions --"
  gcloud services api-keys list --project "$GCP_PROJECT" \
    --format='table(displayName, restrictions.apiTargets[].service:label=ALLOWED_APIS)' 2>/dev/null \
    || warn "cannot list keys"

  info ""
  info "-- Search Console reachability (the real test) --"
  local tok
  if tok="$(gcloud auth print-access-token 2>/dev/null)"; then
    local n
    n="$(curl -s -H "Authorization: Bearer $tok" \
          https://searchconsole.googleapis.com/webmasters/v3/sites \
          | jq '(.siteEntry // []) | length')"
    if [[ "$n" == "0" ]]; then
      warn "0 properties visible — the service account has not been added as a"
      warn "     Search Console user yet. Everything else is configured."
    else
      ok "$n property(ies) visible"
      curl -s -H "Authorization: Bearer $tok" \
        https://searchconsole.googleapis.com/webmasters/v3/sites \
        | jq -r '.siteEntry[] | "     \(.siteUrl)  \(.permissionLevel)"'
    fi
  else
    warn "no access token; run '$0 auth' first"
  fi

  info ""
  info "-- mirrored secrets in GCP --"
  gcloud secrets list --project "$GCP_PROJECT" \
    --format='table(name, createTime)' 2>/dev/null || warn "cannot list secrets"
}

usage() {
  sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

main() {
  [[ $# -ge 1 ]] || usage
  preflight
  info "project=$GCP_PROJECT aws_profile=$AWS_PROFILE dry_run=$DRY_RUN"
  info ""
  case "$1" in
    auth)           cmd_auth ;;
    enable-apis)    cmd_enable_apis ;;
    restrict-key)   cmd_restrict_key ;;
    mirror-secrets) cmd_mirror_secrets ;;
    rotate-sa-key)  cmd_rotate_sa_key ;;
    verify)         cmd_verify ;;
    all)            cmd_auth; info ""; cmd_enable_apis; info ""; cmd_restrict_key; info ""; cmd_verify ;;
    *)              usage ;;
  esac
}

main "$@"
