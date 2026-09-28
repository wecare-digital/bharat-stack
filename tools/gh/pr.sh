#!/usr/bin/env bash
#
# pr.sh - create or update a pull request without letting the shell eat the body.
#
# WHY THIS EXISTS. A PR was created with a wrecked description because its Markdown body was passed
# inline to `gh api -f body="..."`. Markdown is full of backticks, and inside a double-quoted shell
# string a backtick is COMMAND SUBSTITUTION. The body contained `rgb(26,58,42)` and `lime`, so the
# shell tried to run them:
#
#   /bin/sh: command substitution: line 1: syntax error near unexpected token `26,58,42'
#   /bin/sh: line 2: lime: command not found
#
# The PR was still created - with half its body missing and shell errors where the tables should
# have been. Nothing failed loudly; the request succeeded.
#
# THE FIX IS NEVER TO PUT A BODY IN AN ARGUMENT. `gh api -F body=@file` reads the file directly, so
# no shell quoting applies to its contents at all. Same for titles, which can contain backticks too.
#
# Usage:
#   tools/gh/pr.sh create <branch> <base> <title-file> <body-file>
#   tools/gh/pr.sh update <number> <body-file> [<title-file>]
#
# Titles and bodies are FILES, not arguments. That is the whole point - passing a title inline is
# the same hazard in miniature.

set -euo pipefail

# Strip a trailing .git BEFORE extracting owner/repo. Doing it in one regex with an optional
# (\.git)? group silently left the suffix on, so every API call 404'd - and the 404 body then got
# treated as a PR number, producing "PR #{"message":"Github returned a client error."} is already
# MERGED". Two steps, no cleverness.
origin_url=$(git remote get-url origin)
origin_url=${origin_url%.git}
repo=$(printf '%s' "$origin_url" | sed -E 's#.*[:/]([^/]+/[^/]+)$#\1#')
owner=${repo%%/*}

die() { printf '%s\n' "$*" >&2; exit 1; }

# A body file that does not exist would otherwise become an empty PR description.
need_file() { [ -s "$1" ] || die "pr.sh: '$1' is missing or empty - a body file must have content"; }

case "${1:-}" in
  create)
    [ $# -eq 5 ] || die "usage: pr.sh create <branch> <base> <title-file> <body-file>"
    branch=$2; base=$3; titlefile=$4; bodyfile=$5
    need_file "$titlefile"; need_file "$bodyfile"

    # Refuse if the branch's PR is already merged - pushing and PRing a merged branch is the other
    # mistake this directory exists to prevent. See tools/audit/branchstate.js.
    #
    # THE RESULT IS VALIDATED AS A NUMBER, because the first version of this check did not. When the
    # API call failed the error BODY was substituted into the message and compared as if it were a
    # PR id, so a 404 read as "already merged" and blocked a perfectly good PR. A check that cannot
    # tell an error from an answer is worse than no check.
    if ! existing=$(gh api "repos/$repo/pulls?head=$owner:$branch&state=all&per_page=5" \
        --jq '[.[] | select(.merged_at != null) | .number] | first // empty' 2>/dev/null); then
      printf 'pr.sh: warning - could not query existing PRs for %s; skipping the merged-branch check\n' "$branch" >&2
      existing=''
    fi
    case "$existing" in
      ''            ) : ;;
      *[!0-9]*      ) printf 'pr.sh: warning - unexpected PR lookup result %s; skipping the merged-branch check\n' "$existing" >&2 ;;
      *             ) die "pr.sh: PR #$existing for '$branch' is already MERGED. Branch off origin/$base and use a new branch." ;;
    esac

    gh api "repos/$repo/pulls" \
      -F title=@"$titlefile" \
      -F body=@"$bodyfile" \
      -f head="$branch" \
      -f base="$base" \
      --jq '"#\(.number) \(.html_url)"'
    ;;

  update)
    [ $# -ge 3 ] || die "usage: pr.sh update <number> <body-file> [<title-file>]"
    number=$2; bodyfile=$3; titlefile=${4:-}
    need_file "$bodyfile"
    if [ -n "$titlefile" ]; then
      need_file "$titlefile"
      gh api -X PATCH "repos/$repo/pulls/$number" -F title=@"$titlefile" -F body=@"$bodyfile" \
        --jq '"#\(.number) updated - \(.body|length) chars  \(.html_url)"'
    else
      gh api -X PATCH "repos/$repo/pulls/$number" -F body=@"$bodyfile" \
        --jq '"#\(.number) updated - \(.body|length) chars  \(.html_url)"'
    fi
    ;;

  *)
    die "usage: pr.sh create <branch> <base> <title-file> <body-file>
       pr.sh update <number> <body-file> [<title-file>]

Bodies and titles are FILES. Never pass Markdown as a shell argument - backticks in it
become command substitution and the PR is created with a mangled description."
    ;;
esac
