# _hfa-home.sh — resolve the HFA data home. Sourced (never executed) by every
# hfa-* script so relocation works uniformly across the runtime.
#
# Precedence: explicit $HFA_HOME env  >  ~/.hfa/home-path pointer  >  ~/.hfa.
#
# The fixed bootstrap dir (~/.hfa) always exists and, once the user relocates
# their data via `hfa-setup home`, may hold ONLY the pointer files (core-path,
# home-path) — everything else lives under the resolved data home. Callers MUST
# still apply the final default themselves with
#   HFA_HOME="${HFA_HOME:-$HOME/.hfa}"
# so that a missing copy of this file degrades to the legacy fixed location
# instead of breaking the skill (the runtime's never-fail contract).
if [ -z "${HFA_HOME:-}" ] && [ -f "$HOME/.hfa/home-path" ]; then
  __hfa_p="$(tr -d '[:space:]' < "$HOME/.hfa/home-path" 2>/dev/null)"
  [ -n "$__hfa_p" ] && HFA_HOME="$__hfa_p"
  unset __hfa_p
fi
