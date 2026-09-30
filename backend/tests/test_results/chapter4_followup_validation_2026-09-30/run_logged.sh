#!/bin/bash

set -u
set -o pipefail

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 LOG_FILE WORKING_DIRECTORY COMMAND" >&2
  exit 64
fi

log_file="$1"
working_directory="$2"
command_text="$3"

if [ -e "$log_file" ]; then
  echo "Refusing to overwrite existing log: $log_file" >&2
  exit 73
fi

mkdir -p "$(dirname "$log_file")"

start_epoch="$(date +%s)"
start_time="$(date '+%Y-%m-%d %H:%M:%S %z %Z')"
commit_sha="$(git -C "$working_directory" rev-parse HEAD 2>/dev/null || printf 'UNAVAILABLE')"

{
  echo "PSE Pulse validation command log"
  echo "Command: $command_text"
  echo "Working directory: $working_directory"
  echo "Start time: $start_time"
  echo "Commit SHA: $commit_sha"
  echo "----- stdout/stderr -----"
} > "$log_file"

(
  cd "$working_directory" || exit 72
  if [ -n "${VALIDATION_VENV:-}" ]; then
    # shellcheck disable=SC1090
    source "$VALIDATION_VENV/bin/activate"
  fi
  eval "$command_text"
) 2>&1 | tee -a "$log_file"
exit_code="${PIPESTATUS[0]}"

end_epoch="$(date +%s)"
end_time="$(date '+%Y-%m-%d %H:%M:%S %z %Z')"
elapsed_seconds="$((end_epoch - start_epoch))"

if [ "$exit_code" -eq 0 ]; then
  result="PASS"
else
  result="FAIL"
fi

{
  echo "----- command result -----"
  echo "End time: $end_time"
  echo "Exit code: $exit_code"
  echo "Elapsed seconds: $elapsed_seconds"
  echo "Result: $result"
} >> "$log_file"

exit "$exit_code"
