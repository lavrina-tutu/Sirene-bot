# File delivery

## Deliverable Mode: verify actual file delivery

The gateway scans absolute file paths in agent responses and uploads them as native attachments (images inline, other files as documents). The agent need not write a `MEDIA:` tag manually: create the file and include its absolute path.

Telegram has had confirmed failure modes in which a local path is echoed as text instead of uploaded, or a send returns a message ID but the file never arrives. A reported success alone does not reliably prove delivery.

After sending a file, archive or document through this mechanism, ask the user to confirm that it arrived as an attachment. Include the absolute path in the same message as a fallback for scp or direct access. Do not consider delivery complete until receipt is confirmed.

## Historical context

The failure modes above were observed in upstream Telegram file/document delivery; check actual receipt even if the gateway reports success.
