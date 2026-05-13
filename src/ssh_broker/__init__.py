"""Persistent SSH/SFTP+exec broker for OTP-protected remote hosts.

Started by the user in their own terminal BEFORE the AI target.
Holds one long-lived paramiko SSH transport; arbitrates a single
session-channel slot (SFTP or exec) via the SessionHolder mutex.
Serves JSON-RPC requests over a 0600 UNIX socket. Credential is
read by getpass in the user's terminal and never crosses the AI
boundary.

See docs/architecture/ssh-broker.md (to be written in a later task).
"""
