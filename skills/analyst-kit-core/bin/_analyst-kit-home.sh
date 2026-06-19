# _analyst-kit-home.sh — resolve the Analyst Kit data home. Sourced (never executed) by every
# analyst-kit-* script so relocation works uniformly across the runtime.
#
# Precedence: explicit $AK_HOME env  >  ~/.analyst-kit/home-path pointer  >  ~/.analyst-kit.
#
# The fixed bootstrap dir (~/.analyst-kit) always exists and, once the user relocates
# their data via `analyst-kit-setup home`, may hold ONLY the pointer files (core-path,
# home-path) — everything else lives under the resolved data home. Callers MUST
# still apply the final default themselves with
#   AK_HOME="${AK_HOME:-$HOME/.analyst-kit}"
# so that a missing copy of this file degrades to the legacy fixed location
# instead of breaking the skill (the runtime's never-fail contract).
if [ -z "${AK_HOME:-}" ] && [ -f "$HOME/.analyst-kit/home-path" ]; then
  __ak_p="$(tr -d '[:space:]' < "$HOME/.analyst-kit/home-path" 2>/dev/null)"
  [ -n "$__ak_p" ] && AK_HOME="$__ak_p"
  unset __ak_p
fi
