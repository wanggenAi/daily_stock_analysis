#!/usr/bin/env bash

set -euo pipefail

syntax_check() {
  echo "==> backend-gate: Python syntax check"
  python -m py_compile main.py src/config.py src/auth.py src/analyzer.py src/notification.py
  python -m py_compile src/storage.py src/scheduler.py src/search_service.py
  python -m py_compile src/market_analyzer.py src/stock_analyzer.py
  python -m py_compile data_provider/*.py
}

flake8_checks() {
  echo "==> backend-gate: flake8 critical checks"
  flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
}

deterministic_checks() {
  echo "==> backend-gate: local deterministic checks"
  ./scripts/test.sh code
  ./scripts/test.sh yfinance
}

offline_test_suite() {
  echo "==> backend-gate: offline test suite"
  local log_file
  local artifact_dir="${CI_ARTIFACT_DIR:-}"
  local -a junit_args=()

  if [[ -n "$artifact_dir" ]]; then
    mkdir -p "$artifact_dir"
    log_file="$artifact_dir/offline-pytest.log"
    junit_args=("--junitxml=$artifact_dir/offline-pytest.xml")
  else
    log_file="$(mktemp)"
  fi

  set +e
  python -m pytest -m "not network" "${junit_args[@]}" 2>&1 | tee "$log_file"
  local pytest_status=${PIPESTATUS[0]}
  set -e

  if [[ "$pytest_status" -ne 0 ]]; then
    echo "==> backend-gate: structured pytest failure summary"
    local annotated=0
    local summary_lines
    summary_lines="$(grep -E '^(FAILED|ERROR) ' "$log_file" || true)"

    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      echo "::error title=Offline pytest failure::${line}"
      annotated=1
    done <<< "$summary_lines"

    if [[ "$annotated" -eq 0 ]]; then
      echo "::error title=Offline pytest failure::pytest exited with status ${pytest_status}; inspect the offline-test diagnostics artifact"
    fi

    if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
      {
        echo "## Offline pytest failure"
        echo
        echo "pytest exited with status \`${pytest_status}\`."
        echo
        if [[ -n "$summary_lines" ]]; then
          echo '```text'
          printf '%s\n' "$summary_lines"
          echo '```'
        else
          echo "No compact FAILED/ERROR line was emitted. Tail of pytest output:"
          echo
          echo '```text'
          tail -n 80 "$log_file" || true
          echo '```'
        fi
      } >> "$GITHUB_STEP_SUMMARY"
    fi

    if [[ -z "$artifact_dir" ]]; then
      rm -f "$log_file"
    fi
    return "$pytest_status"
  fi

  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    {
      echo "## Offline pytest"
      echo
      echo "Passed."
    } >> "$GITHUB_STEP_SUMMARY"
  fi

  if [[ -z "$artifact_dir" ]]; then
    rm -f "$log_file"
  fi
}

run_all() {
  syntax_check
  flake8_checks
  deterministic_checks
  offline_test_suite
  echo "==> backend-gate: all checks passed"
}

phase="${1:-all}"

case "$phase" in
  all)
    run_all
    ;;
  syntax)
    syntax_check
    ;;
  flake8)
    flake8_checks
    ;;
  deterministic)
    deterministic_checks
    ;;
  offline-tests)
    offline_test_suite
    ;;
  *)
    echo "Usage: $0 [all|syntax|flake8|deterministic|offline-tests]" >&2
    exit 2
    ;;
esac
