---
name: brief-mode
description: "PM briefing: one decision at a time"
version: "1.1.0"
platforms: [linux, macos, windows]
triggers:
  - "любой бриф"
  - "серия решений PM"
  - "разметка unclear-очереди"
  - "архитектурные выборы"
tools: [clarify]
metadata:
  hermes:
    tags: [brief, pm, decisions, workflow]
---

# PM briefing

Use this mode for a sequence of PM decisions, including classification of unclear meetings. Preserve the user's requested scope and mode. Historical examples are evidence for their particular meetings, not a routing dictionary or a substitute for reading the source.

## Question and decision protocol

1. State the total number of questions when known. Ask exactly one question; wait for the answer and record it before asking the next.
2. Give a short context, numbered options, a specific recommendation and the reason for it. Explain a relevant trade-off. Do not use `clarify()` without a recommendation.
3. Record each answer as it arrives in the appropriate decision source, file or report. Do not wait until the end of the briefing. Distinguish decisions from proposals.
4. If the next decision is unclear, ask one concrete open question rather than inventing the PM's answer. Respect an explicit switch of mode by the PM.

## Meeting classification and modes

Read the meeting's summary or available content before recommending a classification; a title, participant name, previous similar case or LLM hint is only a clue. Show title, date, reason for unclear, participants, a short account of the content, a proposed route and its rationale. Use the applicable contacts source to resolve identities; do not promote historical examples of names to mandatory aliases.

If the PM requests «поштучно» or «идём по саммари», present exactly one meeting at a time and wait for its answer. If the summary is missing, disclose that and ask about the missing evidence; do not guess a default route. Where applicable, options include `project=<slug>`, `1on1=<login>`, trash and adm.

For a large list, read the available summaries and group candidates for preparation. Grouping alone does not authorize multiple questions or batch decisions. Use a grouped or hybrid confirmation only when the PM explicitly chooses it. If the PM supplies several explicit answers at once, accept and record every answer, then show the remaining unresolved items; do not silently discard any. Return to one-at-a-time questions for unresolved cases unless batch mode was selected.

After a round, report remaining entries and meaningful reasons such as a missing alias or uncertain project. Keep an actual decision distinct from the proposed classification. The examples and former mode-specific patterns are in [brief modes](references/brief-modes.md).

## Aggregate reconciliation

Bootstrap historically classifies from `classification_memory.json`, not `unclear_registry.md`; verify the implementation in use. Record approved decisions in the classifier's actual source as well as the PM decision registry when each is required. An update to a report alone does not apply a decision. For Bootstrap, preserve exact filenames for applicable manual overrides and verify that the route is supported.

Reconcile `unclear_queue.md` against recorded decisions programmatically after a run; recognize both summary and Action items entries and exclude system files such as `_log_meet.md` and `_registry_meet.md`. Check the real unresolved entries rather than treating the queue heading as a count of new decisions. Rerun and reconcile where authorized. Details and historical causes: [unclear reconciliation](references/aggregate-unclear-reconciliation.md).

For exact meeting decisions, aliases and the sequence of the 2026-06-22 rounds, consult [decision history](references/aggregate-brief-decisions-20260622.md). Similar titles, Zoom/Daily/Untitled, training and recordings can have different outcomes; do not generalize a particular route to all dates or meetings.

## Mobile review

When reviewing files on mobile, prepare a review note with Obsidian wiki-links and deliver it through the requested channel. Do not assume a Telegram `obsidian://` link will open reliably. See [mobile review](references/mobile-obsidian-review.md).
