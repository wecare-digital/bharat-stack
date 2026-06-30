#!/usr/bin/env bash
# upgrade-latest.sh  —  Move ALL frontend/backend npm deps to their latest versions.
# Run on a machine WITH npm network access (local dev or CI). Idempotent.
#
# Usage:
#   ./upgrade-latest.sh            # bump everything to @latest, audit fix, build, test
#   FORCE=1 ./upgrade-latest.sh    # also run `npm audit fix --force` (may pull new majors)
#   NOTEST=1 ./upgrade-latest.sh   # skip vitest
#
# Does NOT commit, push, or deploy — those are explicit manual steps (see docs/UPGRADE_TO_LATEST.md).
set -euo pipefail
cd "$(dirname "$0")"

PROD=(
  @aws-amplify/backend @aws-amplify/ui-react
  @aws-sdk/client-bedrock @aws-sdk/client-bedrock-runtime
  @capacitor/android @capacitor/app @capacitor/browser @capacitor/cli @capacitor/core
  @capacitor/haptics @capacitor/ios @capacitor/keyboard @capacitor/push-notifications
  @capacitor/splash-screen @capacitor/status-bar
  aws-amplify flag-icons next react react-dom react-router-dom
)
DEV=(
  @aws-amplify/backend-cli @aws-amplify/backend-data @aws-amplify/data-construct
  @aws-amplify/graphql-schema-generator @testing-library/jest-dom @testing-library/react
  @types/node @types/react @types/react-dom @vitejs/plugin-react jsdom typescript vitest
)

step() { printf "\n=== %s ===\n" "$1"; }

step "0. Safety: backup manifests + create upgrade branch"
cp package.json package.json.bak
cp package-lock.json package-lock.json.bak
git checkout -B chore/deps-latest

step "1. Bump production dependencies to @latest"
npm install --save "${PROD[@]/%/@latest}"

step "2. Bump dev dependencies to @latest"
npm install --save-dev "${DEV[@]/%/@latest}"

step "3. Audit fix (transitive vulns)"
npm audit fix
if [ "${FORCE:-0}" = "1" ]; then step "3b. Audit fix --force (may pull new majors)"; npm audit fix --force; fi

step "4. Dedupe + clean install from refreshed lockfile"
npm dedupe
npm install

step "5. Build (verifies nothing broke)"
npm run build

if [ "${NOTEST:-0}" != "1" ]; then step "6. Tests"; npm test; fi

step "DONE"
echo "Review:        git diff package.json"
echo "Residual vulns: npm audit"
echo "Backups at package.json.bak / package-lock.json.bak (delete once happy)."
echo "Next: commit, push, then deploy (see docs/UPGRADE_TO_LATEST.md)."
