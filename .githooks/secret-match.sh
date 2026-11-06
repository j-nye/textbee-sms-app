# Sourced, not run. Matches paths against a secret-files list (see secret-files); bash 3.2 compatible.
#   secret_match_any LIST PATH   exit 0 if PATH's base name matches a glob in LIST and no !glob exemption
#   secret_filter LIST           reads paths on stdin, prints the matching ones
# Matching ignores case (.ENV is .env on macOS's and Windows' file systems); a caller's nocasematch is kept.
secret_match_any() {
  local list=$1 base=${2##*/} line hit=1 nc=""
  [ -r "$list" ] || return 1
  shopt -q nocasematch && nc=1
  shopt -s nocasematch
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    case $line in
      '' | '#'*) ;;
      '!'*) case $base in ${line#!}) hit=1; break ;; esac ;;
      *) case $base in $line) hit=0 ;; esac ;;
    esac
  done < "$list"
  [ -n "$nc" ] || shopt -u nocasematch
  return $hit
}

secret_filter() {
  local p
  while IFS= read -r p || [ -n "$p" ]; do
    if secret_match_any "$1" "$p"; then printf '%s\n' "$p"; fi
  done
}
