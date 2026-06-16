#!/usr/bin/env bash
# super-board-notify.sh — best-effort Telegram notifier for super-board runs.
# Sends ONE message via the Telegram sendMessage API. Designed so it can never
# break a run: when notifications are unconfigured (no token, channel != telegram,
# or chat_id auto/empty) it prints a one-line note to stderr and exits 0.
#
# SECURITY: the bot token is read ONLY from $TELEGRAM_BOT_TOKEN — never a CLI
# arg (would leak into shell history / ps), never from the committed config, and
# never printed (dry-run and error paths show a redacted `bot<token>` placeholder).
# Message text is passed to the API as a jq --arg (never concatenated into JSON)
# and HTML-escaped, so an issue title or branch name cannot inject markup.
#
# Usage:
#   super-board-notify.sh "<message>" [options]
#   super-board-notify.sh --message "<message>" [options]
#   printf '<message>' | super-board-notify.sh [options]
# Options:
#   --message TEXT    message (alternative to the positional arg)
#   --level LEVEL     info|alert|done — prefixes a light emoji (default: info)
#   --config SLUG|PATH  override the active config (slug or explicit .json path)
#   --chat-id ID      override notifications.chat_id (bypasses the channel gate)
#   --silent          send without a notification sound (disable_notification)
#   --dry-run         print the resolved request (token redacted), send nothing
#   --strict          exit non-zero on any failure/missing-config (for CI/setup)
#   -h, --help        this help
# Exit codes:
#   0   message sent, OR graceful no-op (notifications unconfigured)
#   1   --strict and something prevented a send
#   64  usage error (bad flag, no message, bad --level, two positionals)
set -euo pipefail

usage() { sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'; }

# A value-taking flag must have a following arg; otherwise `shift 2` runs off
# the end and aborts under `set -e` with a confusing error instead of exit 64.
val_or_die() { [ "$2" -ge 2 ] || { printf 'super-board-notify: %s requires a value\n' "$1" >&2; exit 64; }; }

MESSAGE=""; MESSAGE_SET=0
MSG_FLAG=""; LEVEL="info"; CONFIG_ARG=""; CHAT_ID_ARG=""
DRY_RUN=0; STRICT=0; SILENT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --message)  val_or_die "$1" "$#"; MSG_FLAG="$2"; shift 2 ;;
    --level)    val_or_die "$1" "$#"; LEVEL="$2"; shift 2 ;;
    --config)   val_or_die "$1" "$#"; CONFIG_ARG="$2"; shift 2 ;;
    --chat-id)  val_or_die "$1" "$#"; CHAT_ID_ARG="$2"; shift 2 ;;
    --silent)   SILENT=1; shift ;;
    --dry-run)  DRY_RUN=1; shift ;;
    --strict)   STRICT=1; shift ;;
    -h|--help)  usage; exit 0 ;;
    --*)        echo "super-board-notify: unknown flag: $1" >&2; usage >&2; exit 64 ;;
    *)
      if [ "$MESSAGE_SET" -eq 1 ]; then
        echo "super-board-notify: more than one positional message" >&2; exit 64
      fi
      MESSAGE="$1"; MESSAGE_SET=1; shift ;;
  esac
done

# Graceful no-op (exit 0) unless --strict, which flips every skip into exit 1.
noop_or_fail() {
  printf 'super-board-notify: %s\n' "$1" >&2
  [ "$STRICT" -eq 1 ] && exit 1
  exit 0
}

case "$LEVEL" in info|alert|done) ;; *) echo "super-board-notify: bad --level: $LEVEL (info|alert|done)" >&2; exit 64 ;; esac

# Message precedence: positional > --message > stdin.
if [ "$MESSAGE_SET" -eq 0 ]; then
  if [ -n "$MSG_FLAG" ]; then
    MESSAGE="$MSG_FLAG"
  elif [ ! -t 0 ]; then
    MESSAGE="$(cat)"
  fi
elif [ -n "$MSG_FLAG" ]; then
  echo "super-board-notify: pass the message positionally OR via --message, not both" >&2; exit 64
fi
[ -n "$MESSAGE" ] || { echo "super-board-notify: no message (pass an arg, --message, or pipe stdin)" >&2; exit 64; }

# ── Resolve chat_id. An explicit --chat-id wins and bypasses the channel gate.
if [ -n "$CHAT_ID_ARG" ]; then
  CHAT_ID="$CHAT_ID_ARG"
else
  # Resolve the active config exactly like super-board-run.sh.
  if [ -n "$CONFIG_ARG" ]; then
    case "$CONFIG_ARG" in
      *.json) CONFIG_PATH="$CONFIG_ARG" ;;
      *)      CONFIG_PATH=".claude/super-board/configs/${CONFIG_ARG}.json" ;;
    esac
  elif [ -f .claude/super-board/active ]; then
    CONFIG_PATH=".claude/super-board/configs/$(cat .claude/super-board/active).json"
  else
    noop_or_fail "no active config (.claude/super-board/active missing); pass --config or --chat-id"
  fi
  [ -f "$CONFIG_PATH" ] || noop_or_fail "config not found: $CONFIG_PATH"

  CHANNEL=$(jq -r '.notifications.channel // ""' "$CONFIG_PATH")
  [ "$CHANNEL" = "telegram" ] || noop_or_fail "channel is '${CHANNEL:-unset}', not telegram"
  CHAT_ID=$(jq -r '.notifications.chat_id // ""' "$CONFIG_PATH")
  case "$CHAT_ID" in
    ""|auto|null) noop_or_fail "chat_id is '${CHAT_ID:-empty}' — set notifications.chat_id" ;;
  esac
fi

# ── Token: env only, never logged.
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
[ -n "$TOKEN" ] || noop_or_fail "TELEGRAM_BOT_TOKEN not set"

# ── Compose. Level adds a light prefix; messages may carry their own emoji.
case "$LEVEL" in alert) PREFIX="⚠️ " ;; done) PREFIX="✅ " ;; *) PREFIX="" ;; esac
TEXT="${PREFIX}${MESSAGE}"

# Truncate (chars) BEFORE escaping so we never split a multibyte char or an HTML
# entity. Telegram counts text length AFTER entity parsing (&amp; -> & is one
# char), so a <=4000-char pre-escape cap keeps the parsed message under the 4096
# hard limit no matter how many chars get escaped.
if [ "${#TEXT}" -gt 4000 ]; then TEXT="${TEXT:0:3999}…"; fi

# HTML-escape (safest mode for arbitrary machine text): & first, then < >.
# NOTE: bash 5.2 treats a bare & in the replacement as the matched text, so the
# entity's & must be written \& to stay literal.
TEXT="${TEXT//&/\&amp;}"; TEXT="${TEXT//</\&lt;}"; TEXT="${TEXT//>/\&gt;}"

[ "$SILENT" -eq 1 ] && DISABLE_NOTIF=true || DISABLE_NOTIF=false
BODY=$(jq -nc --arg cid "$CHAT_ID" --arg txt "$TEXT" --argjson dn "$DISABLE_NOTIF" \
  '{chat_id:$cid, text:$txt, parse_mode:"HTML", disable_notification:$dn,
    link_preview_options:{is_disabled:true}}')

URL="https://api.telegram.org/bot${TOKEN}/sendMessage"
REDACTED="https://api.telegram.org/bot<token>/sendMessage"

if [ "$DRY_RUN" -eq 1 ]; then
  printf 'POST %s\n' "$REDACTED" >&2   # endpoint to stderr; stdout stays pure JSON
  printf '%s\n' "$BODY" | jq .
  exit 0
fi

# ── Send (best-effort). One retry on 429 honoring retry_after (capped).
attempt=0
while :; do
  attempt=$((attempt + 1))
  # Token lives in $URL; feed it to curl via --config on stdin so it never lands
  # in argv (ps / /proc/<pid>/cmdline). printf is a bash builtin, so the URL
  # never reaches a process arg list. The JSON body is not secret → argv is fine.
  set +e
  RESP=$(printf 'url = "%s"\n' "$URL" \
    | curl -sS -m 10 --config - -X POST -H 'Content-Type: application/json' -d "$BODY" 2>/dev/null)
  rc=$?
  set -e
  [ "$rc" -eq 0 ] || noop_or_fail "network error (curl rc=$rc)"

  OK=$(printf '%s' "$RESP" | jq -r '.ok // false' 2>/dev/null || echo false)
  [ "$OK" = "true" ] && exit 0

  CODE=$(printf '%s' "$RESP" | jq -r '.error_code // empty' 2>/dev/null)
  if [ "$CODE" = "429" ] && [ "$attempt" -lt 2 ]; then
    RA=$(printf '%s' "$RESP" | jq -r '.parameters.retry_after // 1' 2>/dev/null || echo 1)
    case "$RA" in ''|*[!0-9]*) RA=1 ;; esac
    [ "$RA" -gt 5 ] && RA=5
    sleep "$RA"
    continue
  fi
  DESC=$(printf '%s' "$RESP" | jq -r '.description // "unknown error"' 2>/dev/null)
  noop_or_fail "telegram api ok:false — ${DESC}"
done
