#!/usr/bin/env bash

set -euo pipefail

timestamp="$(date '+%Y-%m-%dT%H:%M:%S%z')"

git add -A
git commit -s -m "$timestamp"
