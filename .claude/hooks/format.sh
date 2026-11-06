#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): format the edited file with this project's formatter, then lint it;
# lint errors go back to Claude (exit 2). A tool runs only if the project is configured for it, so
# nothing gets reformatted by a tool the project doesn't use. Adjust the cases for this stack.
PATH="$HOME/.local/bin:$PATH:/opt/homebrew/bin:/usr/local/bin"
command -v jq >/dev/null || exit 0
file=$(jq -r '.tool_input.file_path // empty')
root="${CLAUDE_PROJECT_DIR:-$PWD}"
case "$file" in "$root"/*) ;; *) exit 0 ;; esac                       # only files inside this project
[ -f "$file" ] || exit 0
cd "$root" || exit 0
has() { compgen -G "$1" >/dev/null; }                                  # does a glob match anything?
bin=node_modules/.bin
lint=""

case "$file" in
  *.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs|*.vue|*.svelte|*.json|*.css|*.scss|*.md|*.yaml|*.yml|*.html)
    if [ -x "$bin/prettier" ] && { has '.prettierrc*' || has 'prettier.config.*' || grep -q '"prettier"' package.json 2>/dev/null; }; then
      "$bin/prettier" --write "$file" >/dev/null 2>&1
    fi
    case "$file" in
      *.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs|*.vue|*.svelte)
        if [ -x "$bin/eslint" ] && { has 'eslint.config.*' || has '.eslintrc*'; }; then
          lint=$("$bin/eslint" --quiet "$file" 2>&1)                   # --quiet: errors only
        fi ;;
    esac ;;
  *.py)
    ruff=$(command -v .venv/bin/ruff || command -v ruff)
    if [ -n "$ruff" ] && { [ -f ruff.toml ] || [ -f .ruff.toml ] || grep -q '^\[tool\.ruff' pyproject.toml 2>/dev/null; }; then
      "$ruff" format --quiet "$file"
      lint=$("$ruff" check --quiet "$file" 2>&1)
    fi ;;
  *.go) command -v gofmt >/dev/null && gofmt -w "$file" ;;
  *.sh) command -v shellcheck >/dev/null && lint=$(shellcheck "$file" 2>&1) ;;
esac

[ -z "$lint" ] && exit 0
printf 'Lint issues in %s (fix the ones in code you wrote; some may clear once you finish the edit):\n%s\n' "$file" "$lint" >&2
exit 2
