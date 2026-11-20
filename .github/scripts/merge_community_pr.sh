#!/usr/bin/env bash
set -eu

branch=$1
head_sha=$2
kind=$3

for attempt in 1 2 3 4 5 6; do
  if gh pr merge "$branch" --repo "$GITHUB_REPOSITORY" --squash --match-head-commit "$head_sha"; then
    break
  fi
  if [ "$attempt" -eq 6 ]; then
    echo "Could not merge the community pull request after $attempt attempts." >&2
    exit 1
  fi
  echo "Merge attempt $attempt failed; retrying in 5 seconds." >&2
  sleep 5
done

if [ "$kind" = "submission" ]; then
  gh workflow run community-retention.yml --repo "$GITHUB_REPOSITORY" --ref "$BASE_BRANCH"
fi
gh workflow run pages.yml --repo "$GITHUB_REPOSITORY" --ref "$BASE_BRANCH"
