---
name: netcdf-remote
description: Guide users to set up the metplot-ssh-broker when an ssh:// path is requested. Use whenever a NetCDF path starts with ssh:// for the first time in a session, OR when the netcdf-reader MCP returns an envelope with error.subcode = "broker_required" or "ssh_auth_needed". The broker keeps SSH credentials out of the AI's context.
---

# netcdf-remote

## When to use

- The user gives a path starting with `ssh://` and you haven't checked for a broker socket yet this session.
- The MCP returns an envelope with `error.subcode == "broker_required"`.
- The MCP returns `error.subcode == "ssh_auth_needed"`.
- The user is frustrated about being asked for SSH credentials in chat and wants a way to avoid it.

## Why the broker exists

**Without it:** typing an SSH passcode into the chat exposes it to prompt-cache, telemetry, and conversation logs. On OTP-protected hosts (OLCF, ALCF, NERSC) the passcode is single-use, so the next MCP call would prompt again.

**With it:** the user runs `metplot-ssh-broker <host>` in their own terminal **before** launching the AI target, enters the passcode there (`getpass.getpass()` — never echoes, never logs), and the broker authenticates once. The credential is dropped from memory immediately after `paramiko.connect()` returns. All subsequent MCP calls reuse the authenticated SFTP+exec channel via a local 0600 UNIX socket. The credential never crosses the AI boundary.

## Quick reference

1. Parse the host out of the user's `ssh://<user>@<host>[:port]/<path>` URL.
2. Try the MCP tool. If the envelope returns `error.subcode == "broker_required"`, advance to step 3.
3. Surface this short message to the user, verbatim:

   > **Set up the metplot SSH broker once, in your own terminal:**
   >
   > ```
   > metplot-ssh-broker <host>
   > ```
   >
   > You'll enter your passcode there — it stays in your terminal and never enters this chat. Leave the broker running. Then come back and tell me to retry.
   >
   > If you need remote `ncks` (header-only metadata via `ncks -m`), start the broker with `--allow-exec=ncks` to extend the read-only allowlist.

4. After the user confirms the broker is running, retry the original tool call. The MCP auto-detects the socket at `$XDG_RUNTIME_DIR/metplot-ssh/<host>.sock`.

## What the broker can do (capabilities)

- **File operations** (SFTP-backed): listdir, stat, glob, get_chunk (partial reads), get_full (full transfer)
- **Header probes** (exec-backed, read-only): `dump_header(path)` runs `ncdump -h` remotely and returns the CDL text. `inspect()` uses this automatically for ssh://*.nc paths — saves transferring multi-GB files just to read metadata.
- **Allowed remote commands**: built-in read-only allowlist (`ncdump`, `ls`, `cat`, `head`, `tail`, `wc`, `file`, `stat`). Extra tools can be permitted at broker start via `--allow-exec=NAME[,NAME...]`.

## What the broker won't do

- **Write operations.** `rm`, `mv`, `cp`, `mkdir`, `chmod`, shell redirections (`>`), pipes (`|`), and command chaining (`&&`, `;`) are blocked by design. argv is a list of strings; each element is `shlex.quote`d on the broker side so metacharacters can't be interpreted as shell syntax.
- **Auto-reconnect.** If the connection dies (`error.code == -32000` connection_lost), the broker reports it and exits. The user restarts with a fresh passcode.
- **Multi-host.** One broker per host. Run two brokers in two terminals for two remotes.
- **Concurrent operations.** All SFTP/exec ops serialize through a single session-channel slot (OLCF MaxSessions=1 design contract).

## Worked OLCF example

```
# In the user's own terminal, BEFORE launching Claude Code:
$ metplot-ssh-broker home.ccs.ornl.gov
home.ccs.ornl.gov:22 passcode (in-memory only, will be dropped): ********
Connecting to <user>@home.ccs.ornl.gov:22...
Connected. Socket: /run/user/1000/metplot-ssh/home.ccs.ornl.gov.sock
Leave this process running. Press Ctrl-C to exit.
```

Then launch Claude Code. Any `ssh://home.ccs.ornl.gov/path/file.nc` reference is automatically routed through the broker — no credential enters the chat.

## See also

- `netcdf-inspect` — what to do after the broker is set up
- `docs/architecture/ssh-broker.md` — protocol + threat model
