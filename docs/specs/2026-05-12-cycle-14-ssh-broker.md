# Cycle 14 — Persistent SSH broker for OTP-protected hosts

> Spec for cycle 14. Adds a small "SSH broker" daemon so the
> user authenticates **once in their own terminal before
> launching the AI target**, and Claude Code (and any other AI
> consumer of the metplot MCP) reuses the authenticated SFTP
> channel without ever seeing the credential.

## 0. Why this spec is shaped this way

The cycle-13 dogfood session against ORNL OLCF surfaced two
problems with the current SSH path:

1. **Credentials enter the AI's context.** The cycle-12 MCP
   responds to an `ssh_auth_needed` envelope by asking the
   caller (Claude Code) to retry with `ssh_config={..., auth:
   {password: <passcode>}}`. That means the user types an
   8-digit RSA SecurID passcode into the chat — captured in
   AI-side logs, prompt-cache, telemetry pipes, etc. Users
   reasonably consider this unsafe even when the channel is
   "trusted".
2. **OLCF enforces `MaxSessions=1`** on `home.ccs.ornl.gov`.
   Standard SSH ControlMaster cannot solve the credential
   problem: even though the local socket reuses one TCP
   connection, every subsequent `exec`/`sftp`/`scp` channel is
   refused by the remote sshd. Confirmed in dogfood — master
   running but `mux_client_request_session: Session open
   refused by peer` on every additional channel.

The architectural insight that unlocks both problems: paramiko
opens **one** SSH session channel at a time (SFTP subsystem OR
exec — never both concurrently), and SFTP multiplexes all file
operations at the **protocol** level inside that one channel. So
a long-lived paramiko process serializing through a single session
slot serves many file requests through a single OLCF-acceptable
connection. We just need that paramiko process to live **outside**
Claude Code.

**Channel state machine (one slot, two uses):**

- Default state: SFTP channel held open.
- `exec` request: close SFTP → open exec → run command → close exec.
- Next SFTP request: lazily reopens SFTP.
- All channel transitions serialize through one mutex inside the
  broker. The on-disk JSON-RPC clients see a uniform interface; the
  broker hides the channel multiplexing.

This adds a meaningful capability: the MCP can run `ncdump -h
/path/to/file.nc` on the remote host and receive a ~10 KB CDL
header instead of transferring a 5 GB NetCDF just to inspect it.

**Exec is read-only by contract.** Built-in tool allowlist:
`ncdump`, `ls`, `cat`, `head`, `tail`, `wc`, `file`, `stat`. The
`--allow-exec=NAME[,NAME...]` CLI flag extends this set at
broker-start (e.g. `--allow-exec=ncks,find`); the user accepts
responsibility for additions. `argv` is always a **list of
strings** at the JSON-RPC layer — each element is `shlex.quote`d
on the broker before joining for `exec_command`, blocking shell
injection. No redirections, pipes, command chaining, or write
operations (`rm`, `mv`, `cp`, `mkdir`, `chmod`, `dd`, `tee`, `>`,
`>>`, `|`, `&&`, `;`). Two high-level methods wrap the most common
read-only commands so the MCP doesn't have to construct argv:
`dump_header(path)` (→ `ncdump -h <path>`) and `dump_metadata(path)`
(→ `ncks -m <path>` when ncks is on PATH).

The cycle-14 design:

```
┌────────────────┐  one TCP, one session channel    ┌─────────────────┐
│  metplot-ssh-  │  at-a-time:                       │ remote sshd     │
│  broker        │    [SFTP] ←→ [exec read-only]    │ (OLCF, generic) │
│  (Python CLI)  │  serialized via SessionHolder    └─────────────────┘
│                │  mutex; keepalive 30s on TCP
│  paramiko      │
│  SSHClient +   │
│  SessionHolder │
└────────────────┘
        ▲
        │ JSON-RPC over UNIX domain socket
        │ $XDG_RUNTIME_DIR/metplot-ssh/<host>.sock  (mode 0600)
        │ methods: listdir, stat, glob, get_chunk, get_full,
        │          ping, dump_header, dump_metadata, exec
        ▼
┌────────────────┐
│ Claude Code +  │   no SSH knowledge, no credential
│ metplot MCP    │   only knows the socket path
└────────────────┘
```

Single-phase, theme-sequenced. Brokers ship as a new
plugin-bundled CLI entry-point; MCP adapter shim picks the
broker up automatically when present.

| Theme | What | Builds on |
|---|---|---|
| A | Broker daemon + JSON-RPC protocol over UNIX socket | New surface |
| B | `BrokerSFTPAdapter` in MCP; auto-detects socket; falls back to direct paramiko if absent | Cycle 12 `paths/ssh.py` |
| C | Remote glob expansion (closes cycle-13 §finding `paths/classify.py:48-62`) — broker handles the `*.nc` pattern remotely | Cycle 13 dogfood finding |
| D | Skill + docs for "OLCF workflow"; new error subcode `broker_required` guides users to set up before retrying | Cycle 10 SSH skill |

## 1. Scope and success criteria

### Phase shape: single-phase, theme-sequenced

Themes ship in order A → B → C → D. One commit per theme;
final commit for docs + gate. Cycle-14 ships **no new MCP
tools** — `list_tool_names()` count stays at netcdf-reader 14,
plot-renderer 4. The broker is infrastructure, not a tool.

### Success criteria

Cycle 14 is successful when all of the following hold:

#### Theme A — Broker daemon

1. **`metplot-ssh-broker` CLI** is a new plugin-bundled
   entry-point (registered in
   `build/claude-code/metplot/pyproject.toml`). Invocation:
   `metplot-ssh-broker <host> [--user U] [--port 22]
   [--socket-dir DIR]`. Defaults `--user` from
   `~/.ssh/config`; defaults `--socket-dir` to
   `${XDG_RUNTIME_DIR:-/tmp}/metplot-ssh/`.
2. **Auth happens in the user's terminal, never in the AI.**
   Broker prompts via `getpass.getpass()` (or honors a
   keyboard-interactive callback for RSA SecurID prompts);
   passes the credential to `paramiko.SSHClient.connect()`
   exactly once; immediately drops it (variable falls out of
   scope, no log, no env, no disk).
3. **One session channel at a time per broker.** `SessionHolder`
   owns the SSH transport and arbitrates a single session-channel
   slot via an internal mutex. Default state holds SFTP open. On
   an `exec` request: close SFTP → open exec → run → close exec
   → next SFTP request lazily reopens SFTP. Never two session
   channels concurrently. Compatible with `MaxSessions=1`
   servers. Connection-level invariant; no per-request paramiko
   reconnects.
4. **UNIX socket exposes JSON-RPC.** Broker listens at
   `${socket_dir}/<host>.sock` with mode `0600`, owned by
   `$UID`. JSON-RPC 2.0 over newline-delimited JSON. Nine
   methods:
   - **File-op methods (SFTP-backed):**
     - `listdir(path)` → list of `{name, size, mode, mtime,
       is_dir, is_link}` entries
     - `stat(path)` → single entry of same shape, or
       `{error: not_found}`
     - `glob(pattern)` → list of absolute paths matching shell
       glob (`*`, `?`, `[...]`); broker walks the parent dir
       and filters with `fnmatch`
     - `get_chunk(path, offset, length)` → base64-encoded bytes
     - `get_full(remote_path, local_path)` → `{bytes_copied,
       sha256}`; broker uses `SFTPClient.get()`
   - **Exec methods (session-channel backed, read-only):**
     - `dump_header(path)` → `{cdl: str, exit_code: int}`;
       internally runs `ncdump -h <path>`. No user-supplied
       flags. Closes SFTP → opens exec → runs → closes exec.
     - `dump_metadata(path)` → `{ncks_m: str, exit_code: int}`;
       internally runs `ncks -m <path>`. Same channel cycle.
       Returns `error.code = -32002` if `ncks` not on remote
       PATH.
     - `exec(argv, timeout=60)` → `{stdout_b64, stderr_b64,
       exit_code}`. Generic escape hatch. `argv` is a list of
       strings (never one shell string). Each element is
       `shlex.quote`d on the broker side and joined for
       `transport.exec_command()`. `argv[0]` must be in the
       built-in read-only allowlist (`ncdump`, `ls`, `cat`,
       `head`, `tail`, `wc`, `file`, `stat`) or in the
       additional list passed at broker-start via
       `--allow-exec`. Anything else: `error.code = -32003,
       message: "tool not in exec allowlist: <name>"`.
   - **Lifecycle:**
     - `ping()` → `{alive: true, host, connected_at,
       sftp_open: bool, allowed_exec_tools: list[str]}`
5. **Keepalive + idle-shutdown.** Broker sends
   `transport.set_keepalive(30)` to keep the OLCF connection
   alive across ClientAliveInterval. If no JSON-RPC request
   arrives for `--idle-timeout` seconds (default 7200), broker
   exits cleanly. Graceful `SIGTERM` / `SIGINT` handlers close
   SFTP + transport before exit.
6. **Connection death is honest.** If paramiko's transport
   reports `is_active() is False`, broker replies to every
   subsequent JSON-RPC call with `{error:
   connection_lost}` and exits within 5 seconds so the user
   can restart. No silent reconnect (would require a new
   passcode, which the broker no longer has).

#### Theme B — MCP adapter

7. **`BrokerSFTPClient`** is a new lightweight class in
   `src/mcp/netcdf_reader/paths/ssh_broker.py`. Constructor
   takes a socket path; methods mirror the subset of
   `paramiko.SFTPClient` the rest of the MCP uses (`listdir`,
   `stat`, `get`, plus the `glob` extension) **and adds the
   three exec-backed methods** (`dump_header`, `dump_metadata`,
   `exec`). All ops issue a JSON-RPC request and parse the
   response.
8. **Adapter dispatch.** `paths/ssh.py` gets a new
   `open_ssh_with_broker_fallback(path, ssh_config=None)`
   that:
   - Parses the URL to extract `host`.
   - Checks for `${XDG_RUNTIME_DIR}/metplot-ssh/<host>.sock`.
   - If present and `ping()` succeeds → returns a
     `BrokerSFTPClient`-backed handle. **No paramiko
     connection opened.**
   - If absent → falls through to existing direct-paramiko
     path (cycle-12 behavior unchanged for users who haven't
     set up a broker).
9. **`adapter.open()`** uses `open_ssh_with_broker_fallback`
   for any `ssh://` path. No call-site changes in `inspect`,
   `read_slice`, `peek`, `compute_stats`, `reduce_variable`,
   or `dump_cdl`.
10. **All cycle-12 SSH tests still pass.** The fallback path
    is unchanged; only the broker-present path is new.
10a. **`inspect()` prefers `dump_header` when broker is present.**
    Cycle-14 optimization: when an `ssh://path.nc` is inspected
    AND a broker is reachable, the MCP calls `broker.dump_header(
    remote_path)` first, parses the CDL into the envelope (cycle-12
    CDL parser already handles this shape), and only falls back to
    `get_full → xarray.open_dataset` if `ncdump` is missing on the
    remote host or returns a non-zero exit. Bandwidth saved: ~10 KB
    vs ~MB-GB per inspect.

#### Theme C — Remote glob expansion

11. **`paths/classify.py` learns SSH globs.** When the URL is
    `ssh://...` AND contains `*`/`?`/`[`, the classifier
    dispatches to the broker's `glob(pattern)` method instead
    of treating the path as a single literal file. Returns
    `PathKind.SSH_MULTI` with a list of resolved absolute
    paths. Closes the cycle-13 §finding (`paths/classify.py:48-62`).
12. **Without a broker, ssh-glob raises a clean envelope** —
    `error.code=ambiguous`, `subcode=broker_required`,
    message: "Remote glob expansion requires the metplot-ssh
    broker. Run `metplot-ssh-broker <host>` in your terminal
    first." No fallthrough to the literal-glob bug.

#### Theme D — Skill + docs

13. **`src/skills/netcdf-remote/SKILL.md`** (NEW) — short
    skill that detects an `ssh://` path in the user's
    request, checks for a broker socket via the MCP's
    `broker_check` helper, and walks the user through one-time
    setup if absent.
14. **`src/skills/netcdf-inspect/SKILL.md`** updated — under
    "Path is local, glob, remote URL, or SSH" line, add
    pointer to `netcdf-remote` for setup-flow guidance.
15. **`README.md`** — new "Remote file access (OLCF and
    other OTP-protected hosts)" subsection under "Targets".

#### Gate

16. **`pytest -ra`** green; **`ruff check`** green; **`mypy
    src tools tests`** green (no new errors beyond the existing
    yaml-stub baseline). Tool counts unchanged.
17. **Bundle smoke test** updated to verify the
    `metplot-ssh-broker` entry-point exists in the built
    plugin's `pyproject.toml` (matches the existing
    `test_pyproject_install_metadata_complete` shape).

## 2. Out of scope this cycle

- **Multi-host broker.** One broker process == one remote
  host. A user wanting to talk to `home.ccs.ornl.gov` AND
  `summit.olcf.ornl.gov` runs two brokers. A pooled broker
  daemon is cycle-15+.
- **Auto-reconnect after credential expiry.** If the OLCF
  server drops the connection (idle kill, daily reboot), the
  broker exits — user starts a new one. Auto-reconnect would
  require storing the passcode, which we explicitly refuse.
- **Remote write operations of any kind.** The `exec` RPC method
  is strictly read-only-by-allowlist. `rm`, `mv`, `cp`, `mkdir`,
  `chmod`, `chown`, `dd`, `tee`, `touch`, `ln`, shell
  redirections (`>`, `>>`), pipes (`|`), and command chaining
  (`&&`, `;`) are not supported — argv is a list, never a shell
  string. Writing-tool names are not added to the built-in
  allowlist and users adding them via `--allow-exec` should
  understand the risk; the broker still `shlex.quote`s every
  argv element so injection through metacharacters is blocked.
- **Long-running remote commands.** `exec` has a default
  timeout of 60 seconds. Anything longer (e.g., remote
  pre-processing) is out of scope; pre-stage with `get_full`
  and run locally instead.
- **Parallel SFTP + exec.** Channels are serialized one at a
  time by the `SessionHolder` mutex. Concurrent JSON-RPC
  requests queue. Acceptable for MCP workloads which are
  inherently sequential per tool call.
- **Globus / GridFTP integration.** Cycle 15+ candidate;
  conceptually orthogonal (Globus has its own daemon model).
- **Windows broker.** UNIX-domain-socket-only this cycle.
  Windows users use Globus or local stage-and-go.
- **Multi-user broker / per-user proxy.** Each user runs their
  own broker; no shared broker process.
- **Encrypted credential cache** for "remember my passcode for
  N seconds." Explicit non-goal — the credential never sits
  anywhere it can be cached.
- **Broker-side data caching.** The broker is a pass-through;
  no LRU of remote bytes. Caching layer (if useful) is a
  later cycle and lives in the MCP, not the broker.

## 3. Affected surface

### 3.1 Broker daemon (NEW component)

| File | Change |
|---|---|
| `src/ssh_broker/__init__.py` (NEW) | Package marker. |
| `src/ssh_broker/cli.py` (NEW) | `metplot-ssh-broker` entry-point: argparse (incl. `--allow-exec`) → prompt for passcode → paramiko connect → `SessionHolder` build → JSON-RPC server loop. Foreground process. |
| `src/ssh_broker/protocol.py` (NEW) | JSON-RPC 2.0 over newline-delimited JSON. `Request`, `Response`, `Error` typed dicts. Error codes: stdlib + broker-specific (`-32000` connection_lost, `-32001` sftp_error, `-32002` tool_not_found, `-32003` tool_not_in_allowlist). |
| `src/ssh_broker/server.py` (NEW) | UNIX-socket server: `socket.AF_UNIX` + `SOCK_STREAM`, mode `0600` enforced via `os.chmod`. Handles concurrent clients via `selectors` (single-threaded; channel ops serialize through `SessionHolder` mutex). |
| `src/ssh_broker/methods.py` (NEW) | The nine JSON-RPC methods: file-op (`listdir`, `stat`, `glob`, `get_chunk`, `get_full`), exec-backed (`dump_header`, `dump_metadata`, `exec`), and `ping`. Each takes the `SessionHolder` + JSON params. Exec methods check the read-only allowlist before opening the exec channel. |
| `src/ssh_broker/session_holder.py` (NEW) | `SessionHolder` — owns the SSH transport; arbitrates a single session-channel slot via a `threading.Lock`. State machine: `sftp_open` ↔ `exec_in_flight`. Methods: `with_sftp(fn)`, `exec_command(argv, timeout)`, `is_alive()`, `close()`. Hard invariant in code: never two concurrent session channels. |
| `src/ssh_broker/exec_policy.py` (NEW) | `BUILTIN_ALLOWLIST = {"ncdump", "ls", "cat", "head", "tail", "wc", "file", "stat"}`. `is_allowed(tool_name, extra_allowed)` returns bool. `quote_argv(argv)` returns a `shlex`-quoted joined string for `transport.exec_command()`. Pure functions; trivially testable. |
| `build/claude-code/metplot/mcp-servers/netcdf_reader/pyproject.toml` | Add `[project.scripts]` entry `metplot-ssh-broker = "src.ssh_broker.cli:main"` alongside the existing `metplot-netcdf-reader` entry. |

### 3.2 MCP adapter (consumer side)

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/paths/ssh_broker.py` (NEW) | `BrokerSFTPClient` — subset of paramiko's `SFTPClient` API surface (`listdir_attr`, `stat`, `get`) plus broker extensions (`glob_remote`, `dump_header`, `dump_metadata`, `exec_argv`). Talks JSON-RPC over the UNIX socket. |
| `src/mcp/netcdf_reader/paths/ssh.py` | Add `open_ssh_with_broker_fallback(path, ssh_config=None)`. Existing `open_sftp_file` becomes the no-broker fallback. |
| `src/mcp/netcdf_reader/paths/classify.py` | When `_has_glob(plain)` AND scheme is ssh, call the broker `glob` method; return new `PathKind.SSH_MULTI`. Clean envelope on broker absent. |
| `src/mcp/netcdf_reader/paths/__init__.py` | Export `PathKind.SSH_MULTI`. |
| `src/mcp/netcdf_reader/adapter.py` | `NetCDFAdapter.open()` routes ssh paths through `open_ssh_with_broker_fallback`. |
| `src/mcp/netcdf_reader/tools/inspect.py` | (a) `broker_required` error subcode in the ambiguous-envelope path (alongside existing `ssh_auth_needed`). (b) When a broker is present for an `ssh://*.nc` path, call `broker.dump_header(remote_path)` first and parse the CDL into the inspect envelope; fall back to the staging path (`broker.get → xarray.open_dataset`) only if `ncdump` is missing on the remote or exits non-zero. |

### 3.3 Skills

| File | Change |
|---|---|
| `src/skills/netcdf-remote/SKILL.md` (NEW) | "When user gives an `ssh://` path, check for a broker socket first; if missing, walk them through `metplot-ssh-broker <host>` setup." Includes a worked OLCF example. |
| `src/skills/netcdf-inspect/SKILL.md` | "Quick reference" step 2: add note on `broker_required` envelope and pointer to `netcdf-remote`. |
| `build/claude-code/metplot/setup.sh` | Add a `--with-broker` line documenting the broker is part of the same install; no separate install step. |

### 3.4 Tests

| File | Status |
|---|---|
| `tests/ssh_broker/unit/test_protocol.py` (NEW) | JSON-RPC envelope shapes; round-trip `Request` ↔ wire ↔ `Response`. |
| `tests/ssh_broker/unit/test_methods.py` (NEW) | The nine methods against a `MagicMock` `SessionHolder`. |
| `tests/ssh_broker/unit/test_session_holder.py` (NEW) | `SessionHolder` channel state machine — SFTP held by default, exec closes SFTP then reopens, mutex serializes concurrent ops, `is_alive()` honest. |
| `tests/ssh_broker/unit/test_exec_policy.py` (NEW) | `BUILTIN_ALLOWLIST` content, `is_allowed()` accepts built-in + extra, rejects writers (`rm`, `mv`, `cp`, etc.). `quote_argv()` blocks shell injection (e.g. `argv=["ls", ">foo"]` → quoted, not redirected). |
| `tests/ssh_broker/unit/test_socket_permissions.py` (NEW) | Socket is created with mode `0600`; non-owner connect attempts fail. |
| `tests/ssh_broker/integration/test_inproc_sshd.py` (NEW) | Spins an **in-process paramiko sshd** (paramiko ships `paramiko.ServerInterface` for this), starts the broker against it, runs a round-trip listdir + get_chunk + dump_header. No real network. |
| `tests/ssh_broker/integration/test_channel_state_machine.py` (NEW) | After a `dump_header` exec, the next `listdir` succeeds (SFTP gets lazily reopened). Verifies the state machine end-to-end against the in-proc sshd. |
| `tests/ssh_broker/integration/test_exec_allowlist_enforcement.py` (NEW) | `exec(argv=["rm","-rf","/"])` → `tool_not_in_allowlist` even when wrapped in a single string. `--allow-exec=ncks` lets `argv=["ncks","-m","/path"]` through but still rejects `argv=["rm",...]`. |
| `tests/ssh_broker/integration/test_idle_shutdown.py` (NEW) | Broker exits within 5s of `--idle-timeout 2`. |
| `tests/ssh_broker/integration/test_connection_lost.py` (NEW) | Kill the in-proc sshd mid-session; broker reports `connection_lost` and exits. |
| `tests/mcp/netcdf_reader/unit/test_ssh_broker_client.py` (NEW) | `BrokerSFTPClient` against a mock UNIX-socket server; verifies it speaks the JSON-RPC protocol; covers `dump_header` / `dump_metadata` / `exec_argv`. |
| `tests/mcp/netcdf_reader/unit/test_ssh_classify_glob.py` (NEW) | `ssh://host/path/*.nc` with a mock broker returns `SSH_MULTI`; same URL without broker returns `broker_required` envelope. |
| `tests/mcp/netcdf_reader/unit/test_inspect_dump_header_path.py` (NEW) | When broker is present, `inspect()` calls `dump_header` (not `get_full`); falls back to `get_full` when `dump_header` returns non-zero. |
| `tests/mcp/netcdf_reader/integration/test_inspect_via_broker.py` (NEW) | `inspect()` with `ssh://` path + in-proc broker + in-proc sshd; full round-trip via the header-only path. |
| `tests/targets/claude_code/test_mcp_smoke.py` | Verify `metplot-ssh-broker` is registered as an entry-point in the built plugin pyproject. |

### 3.5 Documentation

| File | Change |
|---|---|
| `README.md` | New "Remote file access (OLCF and other OTP-protected hosts)" subsection. Worked ORNL example. |
| `docs/architecture/ssh-broker.md` (NEW) | Short design doc — protocol, lifecycle, threat model. |

## 4. Cross-cutting principles

1. **Credential never crosses the AI boundary.** Passcode is
   read by `getpass.getpass()` in the user's terminal,
   passed to `paramiko` exactly once, dropped. No env var, no
   file, no log, no prompt-cache, no telemetry.
2. **TDD per theme.** Theme A's in-process paramiko sshd
   fixture lands first so theme B / C tests can use it.
3. **No new third-party deps.** Paramiko is already a
   dependency. JSON-RPC is stdlib `json`.
4. **Backwards compatibility.** Without a broker, every
   cycle-12 SSH code path still works (with the same
   per-call passcode prompt as today). The broker is purely
   additive opt-in.
5. **Honest about limits.** SFTP + short-lived read-only exec;
   one host per broker; no auto-reconnect. The error envelope
   on connection loss tells the user exactly what happened.
6. **One session channel at a time.** Hard invariant — at most
   one session channel open on the broker's SSH transport
   (either SFTP or exec). Transitions go through the
   `SessionHolder` mutex. OLCF `MaxSessions=1` compatibility is
   a design contract.
7. **Exec is read-only by allowlist.** Hard invariant — the
   broker rejects any `exec(argv)` whose `argv[0]` isn't in
   `BUILTIN_ALLOWLIST` ∪ `--allow-exec` set at startup. Writers
   (`rm`, `mv`, `cp`, `mkdir`, etc.) are never in the built-in
   list; users adding them via `--allow-exec` accept the risk.
   `shlex.quote` blocks shell-metacharacter injection through
   user-supplied `argv` elements.

## 5. Open risks

- **OLCF idle-kill interval unknown.** ORNL may set
  `ClientAliveInterval` aggressively (e.g. 600s). Keepalive
  every 30s should handle it, but real-world dogfood will
  tell. Mitigation: make `--keepalive` a CLI flag with default
  30, document tuning in the OLCF SKILL.
- **Paramiko ServerInterface fidelity.** Our in-process sshd
  fixture must speak enough of the SFTP subsystem to be a
  faithful target. Paramiko's own test suite has examples we
  can copy. If it turns out to be flaky, fall back to a
  Docker-based real sshd in CI (`linuxserver/openssh-server`).
- **OLCF keyboard-interactive callback shape.** RSA SecurID
  prompts are keyboard-interactive PAM, not plain password.
  Paramiko's `connect(password=...)` covers the common case
  via the PAM module's password fallback, but for sites that
  insist on the `kbdint` protocol we need
  `transport.auth_interactive_dumb()`. Test this against
  ORNL in dogfood before declaring theme A green.
- **Socket-path collisions.** Two brokers for the same host
  would race on `<host>.sock`. Mitigation: broker holds an
  `flock` on the socket file; second invocation exits with
  "broker already running for <host>".
- **Concurrent JSON-RPC requests.** Broker serializes through
  a single SFTPClient (paramiko's SFTPClient isn't
  thread-safe per-channel). Concurrent client requests get
  serialized — acceptable for MCP workloads that are
  inherently sequential per tool call.
- **AI consumers that aren't Claude Code.** The MCP boundary
  is the seam — any MCP client (Cursor, Cline, etc.) gets
  broker support automatically. No client-side changes.

## 6. Out-of-scope follow-ons (cycle 15+ candidates)

- Multi-host broker (one process serves several remotes)
- Globus / GridFTP integration for high-throughput transfers
- Windows broker (named pipe transport)
- Broker-side LRU cache of remote file chunks
- Long-running remote commands (>60s) via the broker — would
  need streaming exec output, channel-level cancellation, and
  progress reporting; current `exec` is short-lived only.
- Remote write operations via any path — the broker is
  read-only-exec by contract; this is a sustained non-goal.
- Auto-restart of broker after connection loss (would require
  the very credential persistence we explicitly refuse)
- Shared broker daemon across multiple user sessions on the
  same workstation
- Broker-mediated `rsync --partial` for resumable transfers
- Compression negotiation (`Compression yes` in transport)
- Cycle-15+: ELM PFT / column-level rendering (carry from
  cycle-13)
- Cycle-15+: CPL multi-domain overlay (carry from cycle-13)
- Cycle-15+: cross-section linear interpolation (carry from
  cycle-13)
- Cycle-15+: `render_section` style-by-reference (carry from
  cycle-13)
