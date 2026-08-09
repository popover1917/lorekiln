---
name: distill-dialogue-experience
description: Analyze explicitly selected memory anchors, conversations, transcripts, or project histories to extract and store evidence-backed lessons in a domain-organized experience pool. Use only when the user explicitly asks to classify, brainstorm, analyze, review, distill, or discuss experience. Never trigger from mechanical capture, lifecycle hooks, or a request merely to save dialogue.
---

# Distill Dialogue Experience

Produce reviewable candidates, not automatic truth.

## Workflow

1. Identify the explicitly requested anchor IDs or source scope. Never analyze the entire backlog by default.
   Mark selected anchors `in_review`; leave all unselected anchors `pending`.
2. Reconstruct the source context before interpreting it. Separate direct evidence, inference, and open questions.
3. Group observations by domain, such as collaboration, software development, documentation, mathematical modeling, environment, or user preference.
4. Brainstorm multiple plausible lessons or explanations before converging. Include alternatives that would lead to different conclusions.
5. Extract:
   - successful patterns worth repeating;
   - recurring failures and cognitive biases;
   - constraints or preferences that should persist;
   - unresolved hypotheses that need another test.
6. For each proposed lesson, state supporting evidence, counterevidence, applicability, and at least one boundary or counterexample.
7. Present a compact analysis report to the user. Distinguish agreement, uncertainty, and disagreement.
8. Present a reviewable report. An explicit analysis request may produce `candidate` records, but
   candidate creation never authorizes a capability edit.
9. Mark an anchor `distilled` only after producing the requested analysis; otherwise restore it to
   `pending` or mark it `skipped` at the user's direction.
10. Assign every retained candidate a hierarchical `domain_path`, optional `project_scope`, compact
    title, tags, counterexamples, source anchor IDs, importance, and freshness policy. Preserve raw
    evidence pointers instead of replacing them with the interpretation.

Distillation is read-only with respect to every target capability. Do not edit a Skill, plugin,
`AGENTS.md`, hook, config, or memory control surface while extracting or routing experience.
Routing names a possible destination only; it is not authorization to change that destination.

Read [references/experience-schema.md](references/experience-schema.md) before writing structured records.
Read [references/collaborative-analysis.md](references/collaborative-analysis.md) before analyzing
memory anchors or proposing capability lessons.

## Routing

- Short-lived task state: keep in the current task.
- Helpful personal context: prefer Codex Memories.
- Mandatory personal or repository rule: propose an `AGENTS.md` change.
- Repeatable procedure: route to a Skill.
- Multiple Skills, Hooks, or MCP components: route to a plugin.
- Domain-specific knowledge: route to that domain's Skill or plugin.

Do not put mathematical-modeling or paper-writing experience into generic development skills.

## Token-efficient retrieval

When the user asks to recall or discuss historical experience, use progressive disclosure:

1. `index` — return only IDs, titles, domains, statuses, confidence, importance, and short statements.
2. `timeline` or `related` — load chronology and relations for the selected domain or IDs.
3. `show` — load full evidence only for records the user or analysis actually needs.

Never bulk-load the whole pool before filtering. Search and filtering are deterministic SQLite
operations; model reasoning begins only after the relevant records have been selected.

## Quality gates

- Reject unsupported generalizations.
- Mark one-off observations as provisional.
- Never store secrets, credentials, or large raw tool outputs.
- Preserve disagreement between old and new evidence.
- Prefer a small number of high-value candidates over exhaustive logging.
- Never interpret approval of an experience statement as approval to edit its proposed destination.
- Never let automatic capture, `SessionStart`, `Stop`, or `SessionEnd` trigger intelligent analysis.
- Never infer a request to modify a Skill or plugin from analysis, discussion, approval, routing,
  or candidate creation.
