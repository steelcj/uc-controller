---
title: "Session file names"
date: 2026-11-15
author: "Christopher Steel"
status: "Convention"
description: "How files in the sessions directory are named: a timestamp prefix, then a short description."
---

# Session file names

Every file in this directory starts with a timestamp, followed by a short description:

```text
YYYY-MM-DD--HH-MM-SS-<description>.md
```

For example:

```text
2026-11-15--20-56-38-session.md
2026-11-15--20-16-45-kickoff-make-uc-ventoy-fulfil-raw-node-contract.md
```

## The timestamp

| Part | Meaning | Example |
| --- | --- | --- |
| `YYYY-MM-DD` | The date: four-digit year, month, day | `2026-11-15` |
| `--` | Two hyphens between the date and the time | `--` |
| `HH-MM-SS` | The time: hours on the 24-hour clock, minutes, seconds | `20-56-38` |

- The time is local time on the workstation, taken when the file is created.
- Every part is zero-padded, so `2026-01-05--07-03-09`, not `2026-1-5--7-3-9`.
- Hyphens are used instead of colons, because colons cause trouble in file names on some systems and in URLs.

Written this way, an alphabetical listing of the directory is also in order of time.

## The description

After the timestamp comes one hyphen and a description in lower case, with words separated by hyphens:

- `session` for the record of a working session.
- `kickoff-<what the session is for>` for the note that starts a session.

## Generating the timestamp

```sh
date +%Y-%m-%d--%H-%M-%S
```

Output example:

```text
2026-11-15--20-56-38
```

To create a new session record with the current time in its name:

```sh
#!/bin/sh
# Print the session timestamp, or with a description as the first argument,
# a complete file name: session-name kickoff-new-target
timestamp="$(date +%Y-%m-%d--%H-%M-%S)"
if [ "$#" -gt 0 ]; then
    echo "$timestamp-$1.md"
else
    echo "$timestamp"
fi
```

Used directly in the shell:

```sh
touch "en/docs/sessions/$(date +%Y-%m-%d--%H-%M-%S)-session.md"
```

## Older files

`2026-11-14-session.md` was written before this convention and carries only a date. It is left as it is, because other documents may link to it.
