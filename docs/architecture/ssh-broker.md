# SSH Broker Architecture (cycle-14)

## Goal

Authenticate to an OTP-protected SSH host **once in the user's terminal**, before launching any AI tool, and reuse that authenticated session from inside the metplot MCP. The credential never crosses the AI boundary.

## Components

```
┌────────────────┐  one TCP, one session channel    ┌─────────────────┐
│  metplot-ssh-  │  at-a-time:                       │ remote sshd     │
│  broker        │    [SFTP] ←→ [exec read-only]    │ (e.g. OLCF)     │
│  (Python CLI)  │  serialized via SessionHolder    └─────────────────┘
│                │  mutex; keepalive 30s on TCP
│  paramiko      │
│  SSHClient +   │
│  SessionHolder │
└────────────────┘
        ▲
        │ JSON-RPC 2.0 over UNIX domain socket
        │ $XDG_RUNTIME_DIR/metplot-ssh/<host>.sock  (mode 0600)
        ▼
┌────────────────┐
│ Claude Code +  │   no SSH knowledge, no credential
│ metplot MCP    │   only knows the socket path
└────────────────┘
```

## Protocol

Newline-delimited JSON-RPC 2.0 over `AF_UNIX SOCK_STREAM`.

**Request:**
```json
{"jsonrpc":"2.0","id":N,"method":"...","params":{...}}
```

**Response:**
```json
{"jsonrpc":"2.0","id":N,"result":{...}}
```

**Error:**
```json
{"jsonrpc":"2.0","id":N,"error":{"code":int,"message":str}}
```

### Methods (9)

| Method | Params | Result |
|---|---|---|
| `ping` | `{}` | `{alive, host, connected_at, sftp_open, allowed_exec_tools}` |
| `listdir` | `{path}` | `{entries: [{name, size, mode, mtime, is_dir, is_link}, ...]}` |
| `stat` | `{path}` | `{entry: {...}}` |
| `glob` | `{pattern}` | `{paths: [str, ...]}` |
| `get_chunk` | `{path, offset, length}` | `{data_b64, size}` |
| `get_full` | `{remote_path, local_path}` | `{bytes_copied, sha256}` |
| `dump_header` | `{path}` | `{cdl, stderr, exit_code}` — runs `ncdump -h path` |
| `dump_metadata` | `{path}` | `{ncks_m, stderr, exit_code}` — runs `ncks -m path` |
| `exec` | `{argv: [str,...], timeout?}` | `{stdout_b64, stderr_b64, exit_code}` |

### Error codes

| Code | Meaning |
|---|---|
| -32700 | Parse error (malformed JSON) |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params (missing required field) |
| -32603 | Internal error |
| -32000 | Connection lost (transport dropped) |
| -32001 | SFTP error (remote file ops) |
| -32002 | Tool not found on remote PATH (e.g. ncks missing) |
| -32003 | Tool not in exec allowlist |

## Channel state machine

Single SSH transport, single session-channel slot. The `SessionHolder` class arbitrates:

- **Default state:** SFTP channel held open. Most operations stay in this state.
- **Exec request:** close SFTP → open exec channel → run command → close exec channel. `_sftp` becomes None.
- **Next SFTP request:** lazily reopens SFTP via `client.open_sftp()`.

A `threading.Lock` serializes every public method. Concurrent JSON-RPC clients queue. This is necessary because (a) paramiko's SFTPClient isn't thread-safe per-channel and (b) OLCF `MaxSessions=1` allows only one session at a time on a given TCP connection.

## Read-only exec contract

The `exec(argv, timeout)` method enforces a strict allowlist:

```python
BUILTIN_ALLOWLIST = {"ncdump", "ls", "cat", "head", "tail",
                     "wc", "file", "stat"}
```

`argv[0]` must be in `BUILTIN_ALLOWLIST` ∪ (the `--allow-exec=...` set passed at broker startup). Anything else → error code -32003 (TOOL_NOT_IN_ALLOWLIST). The argv is always a list of strings; each element is `shlex.quote`d before joining for `transport.exec_command()` — blocks shell-metacharacter injection (`>`, `|`, `;`, `&&`, backticks, etc.).

Writers (`rm`, `mv`, `cp`, `mkdir`, `chmod`, etc.) are not in the built-in list. Users adding them via `--allow-exec` accept the responsibility.

## Lifecycle

1. User invokes `metplot-ssh-broker <host>` in their terminal.
2. `getpass.getpass()` reads the passcode from `/dev/tty` (no echo, no log).
3. `paramiko.SSHClient.connect(password=<passcode>, ...)` opens the TCP transport and authenticates.
4. The passcode local variable falls out of scope. Python str is immutable so we can't zero the buffer; we minimize lifetime instead.
5. `SessionHolder` opens ONE SFTP channel.
6. UNIX socket bound at the discovery path, mode `0600`.
7. Server loop accepts clients; dispatches each request to a method; sends the response.
8. On idle-timeout, `Ctrl-C`, `SIGTERM`, or connection-lost: close SFTP → close SSHClient → unlink socket → exit.

## Threat model

| Threat | Mitigation |
|---|---|
| Credential leaks into AI prompt/log/cache | Credential is never visible to the AI. Read in user's terminal via `getpass`, passed once to paramiko, dropped. |
| Credential persists on disk | No `--save` option, no env var prompt, no log mention. Credential lives only in process memory during `connect()`. |
| Local privilege escalation via socket | Socket mode `0600`, owned by `$UID`, in `$XDG_RUNTIME_DIR` (user-private). Connecting requires the same UID. |
| Replay of in-flight RPC traffic | UNIX-domain socket on the local host. No network exposure. |
| Server-side session multiplexing limits | One session channel at a time. Validated against OLCF `MaxSessions=1`. |
| Shell injection via user-supplied argv | argv is a list of strings; each element `shlex.quote`d before joining. No shell metacharacter interpretation. |
| Write operations via exec | Built-in allowlist contains only read-only tools. Writers explicitly absent. Users adding via `--allow-exec` accept the risk. |
| Connection death undetected by MCP | `transport.is_active()` checked on every request; broker returns CONNECTION_LOST and exits within ~5 seconds. |
| Two brokers race on the same socket path | CLI errors out if the socket already exists. |

## Discovery contract

The MCP looks for a socket at:

1. `$XDG_RUNTIME_DIR/metplot-ssh/<host>.sock` (if `XDG_RUNTIME_DIR` set)
2. `/tmp/metplot-ssh/<host>.sock` (fallback)

The broker creates the socket; the MCP reads it. No registry, no DNS, no service discovery — just convention.

## Inspect optimization

When `inspect()` sees an `ssh://path.nc` URL AND a broker is reachable, it calls `broker.dump_header(remote_path)` FIRST. If `ncdump` is available on the remote and the file is readable, the broker returns the CDL text. The MCP parses it with `src/mcp/netcdf_reader/cdl_parser.py` and returns a shallow envelope with `result.source = "dump_header"`.

If `dump_header` fails (ncdump missing, exit != 0) or the CDL doesn't parse, the MCP falls back to `broker.get(remote, local) → xarray.open_dataset(local)` — the full-transfer path. The fallback is transparent to the caller.

## Non-goals

- Auto-reconnect after `connection_lost` (would require persistent credential storage)
- Remote write operations (`rm`, `mkdir`, etc.) — read-only by contract
- Long-running remote commands (`exec` default timeout 60s)
- Multi-host broker (one process per remote; multi-host is a future cycle)
- Windows named-pipe transport (future cycle if there's demand)
- Globus / GridFTP integration (orthogonal — Globus has its own daemon)
- Encrypted credential cache (explicit non-goal — credential is meant to be ephemeral)
