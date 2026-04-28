#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Docker compose command for the community stack
DC=(docker compose -f "$REPO_ROOT/docker/local/docker-compose.yml")

# Track results
declare -a SUITES=()
declare -a RESULTS=()
OVERALL=0

run_suite() {
  local name="$1"
  shift
  SUITES+=("$name")
  echo -e "\n${CYAN}${BOLD}━━━ $name ━━━${NC}\n"
  if "$@"; then
    RESULTS+=("pass")
    echo -e "\n${GREEN}✓ $name passed${NC}"
  else
    RESULTS+=("fail")
    OVERALL=1
    echo -e "\n${RED}✗ $name failed${NC}"
  fi
}

# Files that require enterprise-only deps (pandas comes via bingo-csv-connector).
# Skip them by default; --with-plugin-deps overrides.
DEFAULT_DESELECTS=(
  "--ignore=/app/tests/unit/backend/test_dataset_profiler.py"
)

run_backend() {
  # Tests and test deps aren't in the prod image — mount them in a disposable container
  run_suite "Backend Unit + Integration" \
    "${DC[@]}" run --rm -T \
      -v "$REPO_ROOT/tests:/app/tests" \
      -v "$REPO_ROOT/requirements-dev.txt:/app/requirements-dev.txt" \
      backend sh -c "pip install -q -r /app/requirements-dev.txt && \
                     python -m pytest /app/tests/unit /app/tests/integration ${DEFAULT_DESELECTS[*]} --tb=short"
}

run_frontend() {
  run_suite "Frontend Unit Tests" \
    bash -c "cd '$REPO_ROOT/frontend' && npx vitest run"
}

# Parse flags
RUN_BACKEND=false
RUN_FRONTEND=false
RUN_ALL=true

for arg in "$@"; do
  case "$arg" in
    --backend)  RUN_BACKEND=true;  RUN_ALL=false ;;
    --frontend) RUN_FRONTEND=true; RUN_ALL=false ;;
    --help|-h)
      echo "Usage: $(basename "$0") [--backend] [--frontend]"
      echo "  No flags = run all suites"
      echo ""
      echo "Notes:"
      echo "  - Requires the community Docker stack to be reachable (uses 'docker compose run --rm')."
      echo "  - test_dataset_profiler.py is skipped (pandas ships with the enterprise csv-connector plugin)."
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

echo -e "${BOLD}Running tests from:${NC} $REPO_ROOT"

if $RUN_ALL || $RUN_BACKEND;  then run_backend;  fi
if $RUN_ALL || $RUN_FRONTEND; then run_frontend; fi

# Summary
echo -e "\n${BOLD}━━━ Summary ━━━${NC}"
for i in "${!SUITES[@]}"; do
  if [[ "${RESULTS[$i]}" == "pass" ]]; then
    echo -e "  ${GREEN}✓${NC} ${SUITES[$i]}"
  else
    echo -e "  ${RED}✗${NC} ${SUITES[$i]}"
  fi
done

exit $OVERALL
