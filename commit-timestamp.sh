#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./commit-timestamp.sh [--no-push]

Replace the current branch with one signed-off, timestamped root commit
containing all current files and deletions, then force-push to its configured
upstream branch. The force-with-lease check rejects concurrent remote changes.

  --no-push  Replace local history only, without contacting the remote.
  --help     Show this help.
EOF
}

fail() {
    printf 'Snapshot failed: %s\n' "$*" >&2
    exit 1
}

push=true
for argument in "$@"; do
    case "$argument" in
        --no-push) push=false ;;
        --help|-h) usage; exit 0 ;;
        *) usage >&2; fail "Unknown argument: $argument" ;;
    esac
done

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd -- "$script_directory"
repository="$(git rev-parse --show-toplevel)" || fail "The script must be inside its Git worktree"
[[ "$repository" == "$script_directory" ]] || fail "The script must be at the Git worktree root"
branch_ref="$(git symbolic-ref --quiet HEAD)" || fail "Check out a branch before publishing"
[[ "$branch_ref" == refs/heads/* ]] || fail "HEAD must name a local branch"
branch="${branch_ref#refs/heads/}"
old_head="$(git rev-parse --verify HEAD^{commit})" || fail "The branch must already contain a commit"

for operation in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply sequencer; do
    [[ ! -e "$(git rev-parse --git-path "$operation")" ]] || fail "Finish the current Git operation before publishing ($operation)"
done
[[ -z "$(git ls-files --unmerged)" ]] || fail "Resolve the index conflicts before publishing"
git var GIT_AUTHOR_IDENT >/dev/null || fail "Configure a Git author identity before publishing"
committer="$(git var GIT_COMMITTER_IDENT)" || fail "Configure a Git committer identity before publishing"
signoff="${committer%>*}>"

# Check the actual push destination before changing the index or branch. A
# lease tied to this exact remote value also protects against background fetches.
if "$push"; then
    remote="$(git config --get "branch.$branch.remote")" || fail "Configure an upstream remote for $branch"
    remote_ref="$(git config --get "branch.$branch.merge")" || fail "Configure an upstream branch for $branch"
    [[ -n "$remote" && "$remote" != . ]] || fail "The upstream must be a remote repository"
    [[ "$remote_ref" == refs/heads/* ]] || fail "The upstream must name one remote branch"
    git check-ref-format "$remote_ref" || fail "Invalid upstream branch: $remote_ref"
    push_url="$(git remote get-url --push --all "$remote")" || fail "Cannot resolve the upstream push destination"
    [[ -n "$push_url" && "$push_url" != *$'\n'* ]] || fail "Configure exactly one push URL for $remote"
    advertised="$(git ls-remote --refs "$push_url" "$remote_ref")" || fail "Cannot read the upstream branch; local history is unchanged"
    remote_head=
    if [[ -n "$advertised" ]]; then
        [[ "$advertised" != *$'\n'* ]] || fail "The remote returned more than one matching branch"
        IFS=$'\t' read -r remote_head advertised_ref <<< "$advertised"
        [[ "$advertised_ref" == "$remote_ref" ]] || fail "The remote returned an unexpected branch"
    fi
fi

timestamp="$(date '+%Y-%m-%dT%H:%M:%S%z')"
git add --all
tree="$(git write-tree)"
# No -p argument: every snapshot is a root commit, even when HEAD has history.
new_head="$(git commit-tree "$tree" <<EOF
$timestamp

Signed-off-by: $signoff
EOF
)"
git update-ref -m "snapshot: $timestamp" "$branch_ref" "$new_head" "$old_head"
printf 'Replaced %s with one snapshot commit: %s\n' "$branch" "$new_head"

if "$push"; then
    # An explicit refspec and --no-follow-tags keep this push to one branch.
    if ! git push --no-follow-tags --force-with-lease="$remote_ref:$remote_head" -- "$remote" "$new_head:$remote_ref"; then
        fail "The snapshot remains local; the push failed. Inspect the remote before retrying."
    fi
else
    printf 'Local snapshot only; nothing was pushed.\n'
fi
