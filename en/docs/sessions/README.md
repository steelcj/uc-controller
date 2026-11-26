---
title: Session File Names
description: How files in the sessions directory are named, by creation time, repository, piece of work and kind of record, and what goes in their front matter.
version: 0.1.4
status: provisional
date: 2026-11-25
language: en-CA
---

# Session File Names

This directory holds the records of working sessions on uc-controller with Claude: the plan and kickoff prompt that start a piece of work, and the reports written at each stop along the way.

## The pattern

Every file is named after the time it was created, the repository, the piece of work, and the kind of record, in lower case with words separated by hyphens:

```text
YYYY-MM-DD--HH-MM-SS-<repo-name>-<work>-<kind>.md
```

For example:

```text
2026-11-23--20-16-45-uc-controller-platforms-plan-and-kickoff.md
2026-11-23--21-58-10-uc-controller-platforms-phase-one-report.md
2026-11-23--22-29-05-uc-controller-platforms-phase-two-report.md
```

Written this way, an alphabetical listing of the directory is also in order of time. Pieces of work done in the same period interleave in that listing. To see one piece of work on its own, list it by name:

```sh
ls en/docs/sessions/*-platforms-*
```

### The timestamp

| Part | Meaning | Example |
| :-- | :-- | :-- |
| `YYYY-MM-DD` | The date: four-digit year, month, day | `2026-11-23` |
| `--` | Two hyphens between the date and the time | `--` |
| `HH-MM-SS` | The time: hours on the 24-hour clock, minutes, seconds | `20-16-45` |

- The time is local time on the workstation, taken when the file is created. The time zone is not recorded, so names made on another machine, or across a change to or from daylight saving time, may not sort in true order.
- Every part is zero-padded, so `2026-01-05--07-03-09`, not `2026-1-5--7-3-9`.
- Hyphens are used instead of colons, because colons cause trouble in file names on some systems and in URLs.
- The timestamp is when the file was created, and it never changes, even when the file is revised.

### The rest of the name

| Part | Meaning | Example |
| :-- | :-- | :-- |
| `<repo-name>` | The repository, so a file still says where it belongs when it is copied elsewhere | `uc-controller` |
| `<work>` | A short name for the piece of work, the same in every file that belongs to it | `platforms` |
| `<kind>` | What the file records | `plan-and-kickoff` |

### The kinds of record

| Kind | What it holds | Written by |
| :-- | :-- | :-- |
| `plan-and-kickoff` | Where the repository stands, the plan in phases, and the kickoff prompt for Claude Code | Claude, in chat, before the work starts |
| `phase-<number>-report` | What one phase changed, the checks it ran and their results, and what to know before the next phase | Claude Code, at the end of that phase |
| `session` | The record of a working session that is not split into phases | Whoever runs the session |

Phase numbers are written as words, `phase-one`, `phase-two`, to match the headings inside the files.

## Making the timestamp

Whoever creates the file, Claude Code included, takes the timestamp from the workstation's clock at the moment the file is created:

```sh
date +%Y-%m-%d--%H-%M-%S
```

Output example:

```text
2026-11-23--20-16-45
```

To create a file with the whole name in one step:

```sh
touch "en/docs/sessions/$(date +%Y-%m-%d--%H-%M-%S)-uc-controller-platforms-phase-three-report.md"
```

## Front matter

Every file starts with the same front matter as the other documents under `en/docs/`:

```yaml
---
title: Platforms for uc-controller, Phase One Report
description: What phase one of the platforms work changed, the checks it passed, and what to know before phase two.
version: 0.1.0
status: provisional
date: 2026-11-23
language: en-CA
---
```

| Field | Meaning |
| :-- | :-- |
| `title` | The title, in the form `<Work> for <repo-name>, <Kind>` |
| `description` | One sentence on what the file holds |
| `version` | The document's own version, bumped by hand whenever the file changes, independent of the repository's `VERSION` |
| `status` | `provisional` while the work is under way, then `final` when the piece of work is merged |
| `date` | The date of the latest change, in ISO 8601 |
| `language` | `en-CA` |

The timestamp in the name records when the file was created, and `date` in the front matter records when it last changed. Because the name never changes, every link to the file keeps working when it is revised.

## Older files

Files written before the timestamp was added to this convention keep their names, because other documents may link to them. New files follow the pattern above.

## What never goes in a session record

Session records are published with the repository, so they follow the same rule as the rest of it: no secrets, password hashes, private keys or tokens, real IP addresses, client names, or other private information. Examples use the documentation address ranges, `192.0.2.0/24`, `198.51.100.0/24` and `203.0.113.0/24`, and the domain `example.org`. A repository can add its own items to this list, such as real node definitions.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.4 | 2026-11-25 | Filled in the repository's name, uc-controller, in the prose and the examples. The pattern and the field definitions keep the placeholder `<repo-name>` |
| 0.1.3 | 2026-11-23 | Fixed the order of the examples, so the plan comes first. Gave the rest of the name its own heading, and used `\| :-- \|` alignment in every table. Added how to make the timestamp, that the timestamp never changes, the note on time zones, how to list one piece of work, and a section on older files. Reworded the front matter section to match the timestamped names. Made the list of what never goes in a session record general |
| 0.1.2 | 2026-11-23 | Added the creation timestamp to the start of every file name |
| 0.1.1 | 2026-11-23 | Replaced the repository's name with the placeholder `<repo-name>`, so the convention can be used in any repository |
| 0.1.0 | 2026-11-23 | First version, adapted from the timestamped session naming convention to the names used by the repository's session records |
