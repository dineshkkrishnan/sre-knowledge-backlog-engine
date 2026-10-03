# SRE Knowledge & Backlog Engine

A local, dependency-free Python prototype connecting **backlog triage, recurring-ticket discovery and reviewed operational knowledge**. It turns synthetic ticket history into a filterable HTML dashboard and JSON report, and captures structured closure notes as reviewable runbook drafts.

Independent portfolio lab by Dinesh Kumar Krishnan. All tickets, procedures, names and reported metrics are fictional. No Jira/Confluence integration, LLM inference or infrastructure actions.

## Run
Python 3.11+; no packages or cloud account required:

```bash
python3 app.py
python3 demo.py
python3 -m unittest discover -s tests -v
```

Open `output/dashboard.html` in your browser. Change the service selector to filter triage rows; headline metrics and other sections remain global. Machine-readable output is `output/report.json`. A generated example is in [examples/dashboard.html](examples/dashboard.html); download it to view the HTML page, since GitHub's code view does not render the dashboard.

## What works
| Capability | Implementation |
| --- | --- |
| Backlog triage | Severity first, ownership gaps second, oldest work third; explains rank and blockers |
| Recurring candidates | Same service/environment/version plus lexical symptom similarity |
| Knowledge-gap queue | Recurring patterns with open tickets lacking an eligible approved procedure |
| Runbook suggestions | Reviewed, unexpired, exact-context matches with source IDs, prerequisites and stop conditions |
| Resolution capture | Copies structured closure evidence into a **draft**, preserving source ticket IDs |
| Review gate | Requires complete procedure sections, non-placeholder test evidence and separate review/test labels |
| Dependency dashboard | Reported SME involvement/wait hours and runbook suggestion coverage by service |

## Demo: knowledge moves out of one engineer's head
The sample Kafka pattern has two open tickets, one resolved source ticket and only a draft procedure. It remains a knowledge gap.

```bash
python3 knowledge.py draft --ticket-id LAB-006 --author author-d --output output/kafka-draft.json
```

Review and edit the draft. Have another engineer test it in the sandbox and record the evidence. Then apply the local gate:

```bash
python3 knowledge.py approve --input output/kafka-draft.json --reviewer reviewer-e --tested-by tester-f --at 2026-10-03T00:00:00Z --output output/kafka-reviewed.json
```

The CLI writes a new reviewed JSON file; it does **not** automatically merge it into `data/runbooks.json`. To evaluate it, replace the corresponding runbook entry in a copy of that JSON list and pass the list with `--runbooks`. `demo.py` demonstrates that replacement in memory using fictional reviewer/tester labels. A draft does not improve suggestion coverage; the reviewed example does.

An approval field is not proof that a human reviewed a procedure. This file-based lab checks completeness and label separation, not identity, reviewer competence or successful execution. A real integration needs authenticated review permissions, recorded test evidence and version control.

## Data and definitions
[Ticket fixture](data/tickets.json) and [runbook fixture](data/runbooks.json) document the input shape. Tickets require unique IDs, service/environment/version, symptom, priority P0–P4, open/resolved status, timezone-aware creation/resolution dates, owner, blocked/SME flags and nonnegative reported SME wait hours.

The default fixed snapshot is `2026-10-03T00:00:00Z`. Tickets created later are excluded; resolutions after the snapshot still count as open. Ages use whole elapsed 24-hour days. Blocked work is visible but does not override severity. Empty owners are gaps; the tool does not assign people or close tickets.

Similarity is token Jaccard overlap, with thresholds 0.60 for recurring patterns and 0.45 for suggestions. Scores are lexical overlap, **not probabilities or confidence**. Greedy grouping compares each ticket to a stable representative and avoids transitive chaining. Similar symptoms are candidates for review, not confirmed common causes. Service, environment and platform version must match exactly. Changing thresholds changes findings.

Approved runbooks need owner, reviewer, tested-by label, validation evidence, review dates and all six procedure sections: prerequisites, diagnosis, resolution, validation, rollback and stop conditions. Reviews last 30 days in this demonstration. Draft, retired, expired and future-reviewed records cannot be suggested.

**Suggestion coverage** = open tickets with at least one eligible match / all open tickets. This is not successful runbook use. SME wait is the sum of supplied ticket values, not reconstructed event durations; those fields cannot faithfully represent historical snapshots without event history. SME involvement is a reported flag, not an attribution of an engineer's performance. No real dependency or resolution-time reduction is claimed.

## Technical design
- `engine.py`: input validation, snapshot triage, lexical grouping and retrieval.
- `knowledge.py`: closure capture and explicit review gates.
- `app.py`: escaped static HTML, client-side triage filter and JSON reporting.
- `demo.py`: fictional before/draft/after workflow.
- `tests/`: decision boundaries, exclusion rules, capture/review and escaped output.

No external scripts, telemetry or network calls. Procedures are displayed as references; nothing executes them. Ticket notes are untrusted operational inputs. Never place employer/client records in this public repository.

## Limits and next experiments
This version does not extract undocumented knowledge from conversations, perform semantic retrieval, validate technical correctness, infer root causes, model capacity/WIP, enforce SLAs or authenticate approvals. Tests validate software behavior, not operational effectiveness.

Next: independently reviewed ticket patterns, retrieval precision/recall, reopen-event history, authenticated Jira/Confluence import, service ownership inventory, capacity limits and read-only diagnostic tooling. Keep actual workflow measurements separate from this synthetic demo.

Prepared with AI assistance. Review the algorithms and explain their assumptions before presenting this as engineering work.
