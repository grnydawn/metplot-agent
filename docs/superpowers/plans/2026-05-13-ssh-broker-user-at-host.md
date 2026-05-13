# `metplot-ssh-broker` user@host parsing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `user@host` parsing to `metplot-ssh-broker` so `metplot-ssh-broker grnydawn@home.ccs.ornl.gov` works (matching `ssh` convention) alongside the existing `--user` flag.

**Architecture:** Two new pure helper functions in `src/ssh_broker/cli.py` — `_split_user_host(host_arg, explicit_user)` does the `@`-split with edge-case validation, and `resolve_user_and_host(ns)` chains it with the `$USER` fallback. `main()` calls `resolve_user_and_host(ns)` immediately after `argparse` returns, then uses the resolved `(host, user)` pair downstream. The argparse schema is unchanged, so all 10 existing CLI-args tests keep passing.

**Tech Stack:** Python 3.11+, argparse, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-12-ssh-broker-user-at-host-design.md`

**Branch:** `feature/ssh-broker-user-at-host` (off `master`)

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `src/ssh_broker/cli.py` | Modify (+~30 lines) | Add `_split_user_host` + `resolve_user_and_host`; rewire `main()` to use the resolved `(host, user)` |
| `tests/ssh_broker/unit/test_cli_args.py` | Modify (+~40 lines, +7 tests) | Unit tests for the new helpers (6 for `_split_user_host`, 1 for `resolve_user_and_host`) |
| `README.md` | Modify (~3 lines) | "Remote file access" example uses `user@host` form |
| `docs/user-guide.md` | Modify (~6 lines) | §12 Quickstart + worked OLCF examples use `user@host` form |

---

## Task 0: Create feature branch

**Files:** none

- [ ] **Step 1: Verify clean working tree on master**

```bash
git status
git log --oneline -3
```

Expected: `nothing to commit, working tree clean`, and HEAD at `2e59e1b` (the docs PR #26 merge) or later.

- [ ] **Step 2: Create and switch to feature branch**

```bash
git checkout -b feature/ssh-broker-user-at-host
```

Expected: `Switched to a new branch 'feature/ssh-broker-user-at-host'`.

---

## Task 1: TDD `_split_user_host` helper

**Files:**
- Test: `tests/ssh_broker/unit/test_cli_args.py` (add 6 tests + import)
- Modify: `src/ssh_broker/cli.py` (add `_split_user_host` function)

- [ ] **Step 1: Write the 6 failing tests**

Open `tests/ssh_broker/unit/test_cli_args.py`. Change the existing import line (currently `from src.ssh_broker.cli import build_parser, default_socket_path`) to also import `_split_user_host`:

```python
from src.ssh_broker.cli import _split_user_host, build_parser, default_socket_path
```

Append these 6 tests to the end of the file (after `test_parser_help_does_not_crash`):

```python
def test_split_user_host_no_prefix():
    assert _split_user_host("home.example", None) == ("home.example", None)


def test_split_user_host_prefix_without_explicit_user():
    assert _split_user_host("alice@home.example", None) == ("home.example", "alice")


def test_split_user_host_explicit_user_overrides_prefix_silently(capsys):
    result = _split_user_host("alice@home.example", "bob")
    assert result == ("home.example", "bob")
    captured = capsys.readouterr()
    assert captured.err == ""  # no warning
    assert captured.out == ""


def test_split_user_host_multiple_at_signs_split_on_first():
    assert _split_user_host("a@b@c.example", None) == ("b@c.example", "a")


def test_split_user_host_empty_username_rejected(capsys):
    with pytest.raises(SystemExit) as excinfo:
        _split_user_host("@home.example", None)
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "empty username before '@'" in captured.err


def test_split_user_host_empty_host_rejected(capsys):
    with pytest.raises(SystemExit) as excinfo:
        _split_user_host("alice@", None)
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "empty host after '@'" in captured.err
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest tests/ssh_broker/unit/test_cli_args.py -v
```

Expected: ImportError or 7 failures referring to `_split_user_host` (the existing 10 tests should still collect and pass — the import error may prevent collection of the whole module; that's expected since the new tests live in the same file).

If pytest reports a collection error rather than a clean fail, that confirms the symbol is missing — proceed to Step 3.

- [ ] **Step 3: Implement `_split_user_host` in `src/ssh_broker/cli.py`**

Insert the function below the `default_socket_path` function and above `_authenticate`:

```python
def _split_user_host(
    host_arg: str, explicit_user: str | None
) -> tuple[str, str | None]:
    """Parse `user@host` syntax. --user wins on conflict. Split on first @.

    Returns (host, user). user may be None if no prefix and no explicit_user.
    Exits with code 2 on empty username or empty host.
    """
    if "@" not in host_arg:
        return host_arg, explicit_user
    prefix, _, rest = host_arg.partition("@")
    if not prefix:
        print(
            f"ERROR: invalid host argument '{host_arg}': "
            f"empty username before '@'",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if not rest:
        print(
            f"ERROR: invalid host argument '{host_arg}': "
            f"empty host after '@'",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return rest, (explicit_user if explicit_user else prefix)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/ssh_broker/unit/test_cli_args.py -v
```

Expected: 16 tests pass (10 existing + 6 new in this task).

- [ ] **Step 5: Commit**

```bash
git add src/ssh_broker/cli.py tests/ssh_broker/unit/test_cli_args.py
git commit -m "$(cat <<'EOF'
feat(ssh-broker): add _split_user_host helper

Pure helper that parses `user@host` positional argument. --user
wins silently on conflict; splits on first @; rejects empty
username/host with exit 2 and a stderr message before any prompt.

Six unit tests cover the table in the design spec, including the
silent-override contract (asserts captured stderr is empty when
both forms are given).

The helper is not yet wired into main(); that comes in Task 3.
EOF
)"
```

---

## Task 2: TDD `resolve_user_and_host` wrapper

**Files:**
- Test: `tests/ssh_broker/unit/test_cli_args.py` (add 1 test)
- Modify: `src/ssh_broker/cli.py` (add `resolve_user_and_host` function)

- [ ] **Step 1: Write the failing test**

Update the import line in `tests/ssh_broker/unit/test_cli_args.py` to add `resolve_user_and_host`:

```python
from src.ssh_broker.cli import (
    _split_user_host,
    build_parser,
    default_socket_path,
    resolve_user_and_host,
)
```

Append this test to the end of the file:

```python
def test_resolve_user_and_host_falls_back_to_USER(monkeypatch):
    monkeypatch.setenv("USER", "carol")
    p = build_parser()
    ns = p.parse_args(["home.example"])
    host, user = resolve_user_and_host(ns)
    assert host == "home.example"
    assert user == "carol"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest tests/ssh_broker/unit/test_cli_args.py -v
```

Expected: ImportError on `resolve_user_and_host` (or collection error of the same kind as Task 1).

- [ ] **Step 3: Implement `resolve_user_and_host` in `src/ssh_broker/cli.py`**

Insert directly below `_split_user_host`:

```python
def resolve_user_and_host(ns: argparse.Namespace) -> tuple[str, str]:
    """Final (host, user) after user@host split + $USER fallback.

    The returned `user` is always a non-empty string (defaults to
    $USER, then 'root' if $USER is unset).
    """
    host, user_from_prefix = _split_user_host(ns.host, ns.user)
    user = user_from_prefix or os.environ.get("USER") or "root"
    return host, user
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/ssh_broker/unit/test_cli_args.py -v
```

Expected: 17 tests pass (10 existing + 6 from Task 1 + 1 from this task).

- [ ] **Step 5: Commit**

```bash
git add src/ssh_broker/cli.py tests/ssh_broker/unit/test_cli_args.py
git commit -m "$(cat <<'EOF'
feat(ssh-broker): add resolve_user_and_host wrapper

Chains _split_user_host with the existing $USER fallback. Returns
(host, user) where user is always a non-empty string. One new unit
test covers the $USER fallback path; the prefix-extraction and
--user-override paths are already covered at the helper level
(test_split_user_host_*).

Not yet wired into main(); that comes in Task 3.
EOF
)"
```

---

## Task 3: Wire `resolve_user_and_host` into `main()`

**Files:**
- Modify: `src/ssh_broker/cli.py:96-119` (the head of `main()`)

- [ ] **Step 1: Read current main() head to confirm exact lines**

```bash
sed -n '96,120p' src/ssh_broker/cli.py
```

Expected current content:

```python
def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    user = ns.user or os.environ.get("USER") or "root"
    sock_path = default_socket_path(ns.host, ns.socket_dir)

    if Path(sock_path).exists():
        print(f"ERROR: {sock_path} already exists. Another broker may "
              f"be running for this host.", file=sys.stderr)
        return 3

    extra_allowed: set[str] = set()
    if ns.allow_exec:
        extra_allowed = {s.strip() for s in ns.allow_exec.split(",")
                          if s.strip()}

    print(f"Connecting to {user}@{ns.host}:{ns.port}...", file=sys.stderr)
    try:
        holder = _authenticate(ns.host, user, ns.port, ns.keepalive)
    except paramiko.AuthenticationException:
        print("ERROR: authentication failed.", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 5
```

- [ ] **Step 2: Rewire main() to use resolve_user_and_host**

Replace the three lines:

```python
    ns = build_parser().parse_args(argv)
    user = ns.user or os.environ.get("USER") or "root"
    sock_path = default_socket_path(ns.host, ns.socket_dir)
```

with:

```python
    ns = build_parser().parse_args(argv)
    host, user = resolve_user_and_host(ns)
    sock_path = default_socket_path(host, ns.socket_dir)
```

Then update the `Connecting to ...` log line and the `_authenticate` call to use the resolved `host`:

Change:

```python
    print(f"Connecting to {user}@{ns.host}:{ns.port}...", file=sys.stderr)
    try:
        holder = _authenticate(ns.host, user, ns.port, ns.keepalive)
```

To:

```python
    print(f"Connecting to {user}@{host}:{ns.port}...", file=sys.stderr)
    try:
        holder = _authenticate(host, user, ns.port, ns.keepalive)
```

No other references to `ns.host` in `main()` need to change (they don't exist after this point — verify with `grep -n 'ns\.host' src/ssh_broker/cli.py`; expected: zero matches after the edit).

- [ ] **Step 3: Verify no other `ns.host` references remain in `main()`**

```bash
grep -n 'ns\.host' src/ssh_broker/cli.py
```

Expected: no output (empty result).

- [ ] **Step 4: Run all ssh_broker tests to confirm no regression**

```bash
pytest tests/ssh_broker/ -v
```

Expected: all tests pass (existing CLI tests + new ones + integration + unit). No new tests for this task — the wire-up is a small refactor whose correctness is established by the helpers already being unit-tested and the integration tests still passing.

- [ ] **Step 5: Manual smoke test (no network)**

```bash
.venv/bin/python -c "
import sys
from src.ssh_broker.cli import build_parser, resolve_user_and_host
ns = build_parser().parse_args(['grnydawn@home.ccs.ornl.gov'])
host, user = resolve_user_and_host(ns)
print(f'host={host} user={user}')
"
```

Expected output: `host=home.ccs.ornl.gov user=grnydawn`.

- [ ] **Step 6: Commit**

```bash
git add src/ssh_broker/cli.py
git commit -m "$(cat <<'EOF'
feat(ssh-broker): wire user@host parsing into main()

main() now calls resolve_user_and_host(ns) immediately after
argparse returns. Downstream code (socket path, connect log,
_authenticate call) uses the resolved (host, user) pair instead
of ns.host + inline $USER fallback. argparse schema unchanged.
EOF
)"
```

---

## Task 4: Update README "Remote file access" section

**Files:**
- Modify: `README.md:40-72` (the "Remote file access" section)

- [ ] **Step 1: Read the section to confirm current content**

```bash
sed -n '40,72p' README.md
```

Expected: section starts with `## Remote file access (OLCF and other OTP-protected hosts)` and contains the example `metplot-ssh-broker home.ccs.ornl.gov` on a single line in a fenced block around line 47.

- [ ] **Step 2: Edit the primary example**

Change line 47 from:

```bash
metplot-ssh-broker home.ccs.ornl.gov
```

To:

```bash
metplot-ssh-broker grnydawn@home.ccs.ornl.gov
```

Then add a single sentence immediately after the closing ``` of that code block (i.e., between the code block and `You'll be prompted for your passcode.`):

> Pass the username inline as `user@host` (like `ssh`), or use `--user grnydawn` separately if you prefer.

- [ ] **Step 3: Verify the change renders cleanly**

```bash
grep -n 'grnydawn@home' README.md
grep -n 'Pass the username inline' README.md
```

Expected: each match exactly once.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs(readme): show user@host form as primary broker example

Updates the "Remote file access" section to use
`metplot-ssh-broker grnydawn@home.ccs.ornl.gov` and adds a single
sentence pointing out that --user is also accepted.
EOF
)"
```

---

## Task 5: Update `docs/user-guide.md` §12

**Files:**
- Modify: `docs/user-guide.md:530-566` (Quickstart + worked OLCF examples)

- [ ] **Step 1: Read §12 Quickstart and the worked examples to confirm exact content**

```bash
sed -n '530,570p' docs/user-guide.md
```

Expected: the Quickstart fenced block contains `metplot-ssh-broker home.ccs.ornl.gov`, followed by a `command not found?` blockquote (added earlier), followed by `You'll be prompted...`. The two worked-example blockquotes that follow reference `ssh://home.ccs.ornl.gov/...` paths.

- [ ] **Step 2: Update the Quickstart fenced block**

Change:

```bash
metplot-ssh-broker home.ccs.ornl.gov
```

To:

```bash
metplot-ssh-broker grnydawn@home.ccs.ornl.gov
```

(The `command not found?` blockquote below it already documents the `--user` flag indirectly via the verification step; no further change there.)

- [ ] **Step 3: Add a one-sentence note immediately after the Quickstart fenced block**

Insert this paragraph between the closing ``` of the fenced block and the `command not found?` blockquote:

> The `grnydawn@` prefix is the recommended way to pass your remote username — same form as `ssh user@host`. You can also use `--user grnydawn` if you prefer; if both are given, `--user` wins.

- [ ] **Step 4: Verify the changes**

```bash
grep -n 'grnydawn@home' docs/user-guide.md
grep -n 'same form as `ssh user@host`' docs/user-guide.md
```

Expected: at least one match each.

- [ ] **Step 5: Commit**

```bash
git add docs/user-guide.md
git commit -m "$(cat <<'EOF'
docs(user-guide): §12 Quickstart shows user@host form

Updates the broker Quickstart example to use
`grnydawn@home.ccs.ornl.gov` and adds a paragraph explaining
that --user is also accepted and wins on conflict.
EOF
)"
```

---

## Task 6: Final verification — full test suite + lint + typecheck

**Files:** none (verification only)

- [ ] **Step 1: Run the full ssh_broker test suite**

```bash
pytest tests/ssh_broker/ -v
```

Expected: all tests pass. Confirm count: 10 existing CLI tests + 6 (Task 1) + 1 (Task 2) = 17 tests in `test_cli_args.py`, plus the unchanged unit and integration tests.

- [ ] **Step 2: Run the full repo test suite to catch any cross-package fallout**

```bash
pytest
```

Expected: all tests pass. Cycle-14 left the baseline at 1385 tests passing; this change should add 7 (6 + 1) for a new baseline of 1392.

- [ ] **Step 3: Type-check the broker package**

```bash
mypy src/ssh_broker/
```

Expected: `Success: no issues found` (or the same pre-existing-baseline result as before the change — no new errors introduced).

- [ ] **Step 4: Lint the changed files**

```bash
ruff check src/ssh_broker/ tests/ssh_broker/
```

Expected: no errors.

- [ ] **Step 5: Verify acceptance criteria 1–4 by code inspection**

Read `src/ssh_broker/cli.py` and confirm:

1. `metplot-ssh-broker grnydawn@home.ccs.ornl.gov` → `_split_user_host` returns `("home.ccs.ornl.gov", "grnydawn")`, then `_authenticate("home.ccs.ornl.gov", "grnydawn", ...)`. ✓
2. `metplot-ssh-broker home.ccs.ornl.gov` → `_split_user_host` returns `("home.ccs.ornl.gov", None)`, `$USER` fallback supplies user. ✓
3. `metplot-ssh-broker grnydawn@host --user alice` → `_split_user_host` returns `("host", "alice")` (silent override). ✓
4. `metplot-ssh-broker @host` and `metplot-ssh-broker alice@` → `SystemExit(2)` with stderr message, before any prompt (the `_authenticate` call is never reached). ✓

- [ ] **Step 6: No-op commit only if necessary**

This task is verification only; if all checks pass, no commit. If a check fails, fix it and amend or add a new commit before proceeding.

---

## Out of scope (do NOT add to this plan)

- Reading `~/.ssh/config` for host aliases
- Supporting `ssh://user@host` URL form on the broker CLI
- Multi-host in one process
- Refactoring `main()` beyond the small wire-up in Task 3
