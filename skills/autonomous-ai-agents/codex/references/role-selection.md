

## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

## Model selection for agent roles (ChatGPT Business/Enterprise login)

Codex's native models are OpenAI's own family (Claude/Grok/Composer are NOT in
the picker — bringing them in means a Responses-API gateway, a new entity).
Catalog and reasoning are two independent axes: pick an ID, then an effort.
Choose by role, not by "the strongest model":

| Role | Model ID | reasoning effort |
|---|---|---|
| Architect (TZ/plan/judgment) | `gpt-6.1-sol` | high (xhigh on a fat TZ/plan) |
| Architect escalation (only on proven gaps) | `gpt-6-astra` | high |
| Executor (bulk code) | `gpt-6.1-sol` | medium (high on multi-file) |
| Executor LIGHT (≤3 files) | `gpt-6-luna` | high |
| Reviewer (if OpenAI) | `gpt-6.1-sol` | high |

**Verify the actual model catalog on the host before proposing a specific model**
as a candidate — do not assume a generation/nickname exists. On the VM the
useful list lives in `~/.codex/models_cache.json` (fields `slug`,
`default_reasoning_level`, `supported_reasoning_levels`); e.g. `gpt-5.6-terra`
and `gpt-6-luna` are real while `gpt-6-terra` is rejected by the API ("not
supported when using Codex with a ChatGPT account") even though it accepts the
name — a requested id absent from the catalog either falls back to generic
metadata or errors with a confusing 400. Read the cache, not the wishlist, when
answering "is model X a candidate".

Default the architect to Sol, not Astra: Astra ≈5× Sol's credit rate on the
same windowed allowance, while Sol sits within ~1 index point of Astra and
above the frontier non-OpenAI models it replaces — escalation to Astra is for a
specific `TZ:patch`/plan where a reviewer keeps catching gaps Sol missed, not a
standing choice. Don't use Ultra (sub-agents can't be driven by a single
invoke) and don't put transition models (gpt-5.6.*) in a role config; Luna is
extract/classify-class, never an architect or reviewer.

**Judge a role model by its class, not by "the slot it filled before".** A model
that occupied the same role on a different stack is not thereby equal in class
— compare by benchmark and by the kind of work the role does (spec/plan/judgment
vs bulk code). Conversely, a reviewer's required strength is calibrated to the
**output** it must criticize (the TZ/plan on disk) and to the review norms, not
to the benchmark of the author model: a weaker author does not license a weaker
reviewer — a weaker author produces MORE gaps, and a weak reviewer lets them
through.

**Compare a candidate role model against the model it actually REPLACES, not
against another candidate in the same selection.** When a role's model moves to
a new harness/lineage, its fair benchmark is the incumbent occupant of that slot
(e.g. swap Cursor composer into Codex Terra is judged against composer, NOT
against the architect's Sol). A candidate is adequate if it is not weaker than
whom it replaces; comparing it to a stronger, differently-scoped model of another
role yields a false rejection. A weak result from this mistake surfaces as
"the candidate is too weak" when the real issue is a mismatched baseline — check
which model fills the role today before arguing class.

**Reviewer within Codex is `gpt-6-astra`, never the author's own id.** The
independent-vendor reviewer exists only while an OpenRouter/Tutu gateway is
affordable; when it is not, the least-bad in-Codex reviewer is the model that is
stronger than the author AND a different id — e.g. author `gpt-6.1-sol`,
reviewer `gpt-6-astra` at high. Reusing the author's own id is a twin pass, not a
review: it smooths the same family's gaps (missed `[NEW-ENTITY]`, watered-down
"don't touch", extract drift). `codex-auto-review` is a hidden auto-approval
model for the sandbox, NOT a usable reviewer role. Many VMs expose Astra's
default reasoning as low, so always pin `-c model_reasoning_effort` to high, or
the reviewer judges weaker than the author. When both architect and reviewer
must sit on OpenAI, independence is consciously traded: the residual risk from a
shared prior is acceptable only if author and reviewer are different ids AND
the reviewer effort is pinned high. Effort per call:
`codex exec -C <ABS> -m gpt-6.1-sol -c model_reasoning_effort='"high"' --skip-git-repo-check --json "…"`.

**Reviewer verdict files (dev-workflow REV-*.md): keep reviewing sections as
H2 (`## `), never H3 (`###`).** The downstream `rev_verdict()` parser takes the
block from `## Вердикт` to the *next H2 header*; if the reviewer writes its
narrative/argumentation as H3 sections, the verdict block is never terminated
and swallows the whole file — so any body mention of the OTHER verdict word
(e.g. explaining a past `REQUEST-CHANGES` round) makes the parser return
CONFLICT against the explicit `verdict=APPROVE`, and `complete-phase` fails
"REV verdict unknown or conflict" even though the verdict is genuinely
approve and the full test suite is green. When you (or a Codex reviewer) write
the review, put each reasoning section at `## ` level and keep the verdict
assertion as the first line under `## Вердикт`, away from any stray
`REQUEST-CHANGES` string above the next H2.

If a reviewer must stay on an independent vendor (different family from the
architect's), run it through an OpenRouter/Tutu gateway instead of Codex — the
two roles then come from different providers, not different Codex models.
