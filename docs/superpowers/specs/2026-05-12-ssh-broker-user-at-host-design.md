# `metplot-ssh-broker`: accept `user@host` on the CLI — design

> **Goal:** Let users invoke the broker as `metplot-ssh-broker grnydawn@home.ccs.ornl.gov` (matching `ssh` convention) in addition to the existing `metplot-ssh-broker home.ccs.ornl.gov --user grnydawn` form.

## Motivation

The current CLI takes a positional `host` and an optional `--user` (defaults to `$USER`). Passing `user@host` as the positional argument silently breaks: paramiko receives `hostname=user@host`, DNS rejects it, and the error surfaces only after the user has already entered a passcode at the `getpass` prompt:

```
$ metplot-ssh-broker grnydawn@home.ccs.ornl.gov
Connecting to youngsung@grnydawn@home.ccs.ornl.gov:22...
youngsung@grnydawn@home.ccs.ornl.gov:22 passcode (in-memory only, will be dropped):
ERROR: gaierror: [Errno -2] Name or service not known
```

`ssh user@host` is universal convention; users instinctively reach for it. The fix is a small, additive parsing rule.

## Behavior contract

### Parsing rule

A helper `_split_user_host(host_arg: str, explicit_user: str | None) -> tuple[str, str | None]` runs in `main()` immediately after `argparse` returns the namespace, before the `$USER` fallback. It returns the resolved `(host, user)` pair.

Rules:

| Input `host` arg | `--user` | Resulting `host` | Resulting `user` |
|---|---|---|---|
| `home.ccs.ornl.gov` | unset | `home.ccs.ornl.gov` | `None` (falls through to `$USER`) |
| `home.ccs.ornl.gov` | `alice` | `home.ccs.ornl.gov` | `alice` |
| `grnydawn@home.ccs.ornl.gov` | unset | `home.ccs.ornl.gov` | `grnydawn` |
| `grnydawn@home.ccs.ornl.gov` | `alice` | `home.ccs.ornl.gov` | `alice` (silent override) |
| `a@b@c.example` | unset | `b@c.example` | `a` (first-`@` split) |
| `@home.example` | unset | — | error: empty username before `@`, exit 2 |
| `alice@` | unset | — | error: empty host after `@`, exit 2 |
| `""` | — | — | argparse rejects (positional is required) |

### Conflict semantics

When both `user@host` and explicit `--user` are provided, **`--user` wins silently**. No warning to stderr. Rationale: matches argparse convention (flags override defaults), is predictable, and avoids noise on every startup when the user knowingly chose to use both forms (e.g., scripted invocations).

### Multi-`@` rule

Split on the **first** `@`, matching `ssh`. Edge case in practice; usernames almost never contain `@`. Last-`@` split would diverge from `ssh` and almost never be useful.

### Error reporting

`@host` and `user@` errors are surfaced **before** the password prompt and **before** any network activity. Exit code 2 (argparse convention for invalid args), message to stderr in the form:

```
ERROR: invalid host argument 'alice@': empty host after '@'
```

### Unchanged behavior

- Plain hostnames (no `@`) pass through unchanged. Zero behavioral change for existing users.
- The `Connecting to {user}@{host}:{port}` log line at `src/ssh_broker/cli.py:111` already prints the resolved values correctly; no change needed there.
- The `argparse` schema is unchanged: positional `host` + optional `--user`. Existing 10 tests in `tests/ssh_broker/unit/test_cli_args.py` keep passing.

## Implementation surface

### `src/ssh_broker/cli.py`

Add two functions:

```python
def _split_user_host(host_arg: str, explicit_user: str | None) -> tuple[str, str | None]:
    """Parse `user@host` syntax. --user wins on conflict. Split on first @."""
    if "@" not in host_arg:
        return host_arg, explicit_user
    prefix, _, rest = host_arg.partition("@")
    if not prefix:
        print(f"ERROR: invalid host argument '{host_arg}': "
              f"empty username before '@'", file=sys.stderr)
        raise SystemExit(2)
    if not rest:
        print(f"ERROR: invalid host argument '{host_arg}': "
              f"empty host after '@'", file=sys.stderr)
        raise SystemExit(2)
    return rest, (explicit_user if explicit_user else prefix)


def resolve_user_and_host(ns: argparse.Namespace) -> tuple[str, str]:
    """Final (host, user) after user@host split + $USER fallback."""
    host, user_from_prefix = _split_user_host(ns.host, ns.user)
    user = user_from_prefix or os.environ.get("USER") or "root"
    return host, user
```

`main()` is rewritten to call `resolve_user_and_host(ns)` in place of the current `user = ns.user or os.environ.get("USER") or "root"` line, and to use the returned `host` instead of `ns.host` downstream (auth, socket path, connect log).

### `tests/ssh_broker/unit/test_cli_args.py`

Add seven new tests (all unit, no fixtures beyond what's already there):

1. `test_split_user_host_no_prefix` — pass-through.
2. `test_split_user_host_prefix_without_explicit_user` — `alice@host`, no `--user` → user=`alice`.
3. `test_split_user_host_explicit_user_overrides_prefix_silently` — `alice@host` + `--user bob` → user=`bob`, no warning to captured stderr.
4. `test_split_user_host_multiple_at_signs_split_on_first` — `a@b@c` → user=`a`, host=`b@c`.
5. `test_split_user_host_empty_username_rejected` — `@host` → `SystemExit(2)`.
6. `test_split_user_host_empty_host_rejected` — `alice@` → `SystemExit(2)`.
7. `test_resolve_user_and_host_falls_back_to_USER` — no prefix, no `--user`, with `$USER=carol` → user=`carol`.

No integration test required. The in-process sshd fixture exercises everything downstream of `resolve_user_and_host()` already; this change is purely upstream.

## Docs scope

In-scope updates:

- **`README.md`**, "Remote file access" section — primary example becomes `metplot-ssh-broker grnydawn@home.ccs.ornl.gov`. One-line note: "Pass username inline as `user@host`, or use `--user grnydawn` separately if you prefer."
- **`docs/user-guide.md` §12** — Quickstart example, worked OLCF examples, and any troubleshooting reference all show the `user@host` form. `--user` retained in one place for completeness.

Out-of-scope (leave alone):

- `docs/architecture/ssh-broker.md` — internal architecture doc, CLI surface isn't its focus.
- `docs/specs/2026-05-12-cycle-14-ssh-broker.md` and the cycle-14 plan — already-merged historical records.

Explicit non-goals (flagged to prevent scope creep):

- Reading `~/.ssh/config` for host aliases — a separate, larger feature.
- Supporting `ssh://user@host` URL form on the broker CLI — overlaps with the MCP's URL parser; clean to keep CLI = hostname/`user@host`, MCP = `ssh://` URLs.
- Multi-host in one process — explicit non-goal per cycle-14 spec.

## File map

- **Modify** `src/ssh_broker/cli.py` (≈ 30 lines added: `_split_user_host`, `resolve_user_and_host`, wire-up in `main()`).
- **Modify** `tests/ssh_broker/unit/test_cli_args.py` (+7 tests, ≈ 35 lines).
- **Modify** `README.md` (~ 3 lines changed).
- **Modify** `docs/user-guide.md` (~ 6 lines changed).

## Acceptance criteria

1. `metplot-ssh-broker grnydawn@home.ccs.ornl.gov` connects with `username=grnydawn`, `hostname=home.ccs.ornl.gov`.
2. `metplot-ssh-broker home.ccs.ornl.gov` (existing form) works identically to before.
3. `metplot-ssh-broker grnydawn@home.ccs.ornl.gov --user alice` connects with `username=alice` and no warning printed.
4. `metplot-ssh-broker @home.example` and `metplot-ssh-broker alice@` exit 2 with a stderr error, before any prompt.
5. All 10 existing `test_cli_args.py` tests still pass.
6. 7 new tests pass.
7. `mypy src/ssh_broker/`, `ruff check src/ssh_broker/ tests/ssh_broker/` clean.
