# Lorekiln Product Marketing Context

This file guides future AI agents that maintain Lorekiln's public product language.

## Positioning

Lorekiln is an open-source, local-first persistent memory plugin for Codex agents. It separates deterministic conversation capture, requested experience distillation, governed long-term memory, and human-authorized capability evolution.

## Primary audience

1. Codex power users who need memory across sessions.
2. AI agent, Skill, and plugin developers who need provenance and rollback.
3. Privacy-conscious users who prefer local storage.
4. Teams exploring agent learning without silent self-modification.

## Core promise

Keep the original evidence, turn only reviewed evidence into experience, and never change agent behavior without a separate human decision.

## Defensible claims

- Mechanical dialogue capture uses deterministic local scripts rather than model calls.
- Semantic analysis starts only after an explicit user request.
- Experience approval and capability-change authorization are separate states.
- Runtime journals and SQLite data remain local to the plugin environment.
- Capability evolution includes baseline, evaluation, rollback, and final acceptance gates.

Do not claim universal platform compatibility, guaranteed token savings, autonomous self-improvement, perfect crash recovery, or security certification.

## Search language

Use these phrases naturally where they answer real user questions:

- AI agent memory
- Codex memory plugin
- persistent memory for Codex
- local conversation memory
- conversation journaling
- long-term experience memory
- token-efficient context management
- auditable agent learning
- human-in-the-loop agent improvement
- controlled agent self-improvement

Do not repeat keyword lists in multiple sections or hide keywords. Prefer explicit definitions, comparison tables, FAQ questions, installation commands, and evidence-backed limitations.

## Voice

Precise, calm, technically credible, and privacy-aware. Lead with the user problem and concrete behavior. Avoid hype such as “revolutionary,” “best,” “zero-token,” “fully autonomous,” or “remembers everything.”

## Conversion path

The public README should let a new reader answer, in order:

1. Is this the kind of memory tool I searched for?
2. What problem does it solve?
3. How is it different from chat history, RAG, summarization, or self-improvement loops?
4. Does it keep my data local and behavior under my control?
5. Can I install and verify it quickly?
