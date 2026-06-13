---
title: "Memory Systems Research for AgentDrive"
description: "Research-grounded requirements behind AgentDrive memory triage and Experience Graph context packs."
---

# Memory Systems Research for AgentDrive

This note maps human memory research and current LLM memory work into concrete AgentDrive design requirements.

## Research Inputs

- Human memory is not one flat store. Squire and Wixted summarize evidence for multiple memory systems, including immediate memory, declarative memory, consolidation, medial temporal structures, and long-term neocortical storage: https://doi.org/10.1146/annurev-neuro-061010-113720
- Forgetting is a measurable decay signal, not just deletion. Ebbinghaus measured relearning savings across time and found rapid early loss followed by slower decline: https://psychclassics.yorku.ca/Ebbinghaus/memory7.htm
- Retrieval can reopen memory for update. Nader, Schafe, and LeDoux showed that reactivated consolidated fear memories became labile and required reconsolidation: https://doi.org/10.1038/35021052
- Transformer attention gives models a powerful but bounded active context, not durable autobiographical memory: https://arxiv.org/abs/1706.03762
- Retrieval-augmented generation combines parametric model knowledge with explicit non-parametric memory, but still depends on good retrieval, ranking, provenance, and updating: https://arxiv.org/abs/2005.11401
- RETRO showed that retrieval from a very large external corpus can materially improve language models, making external memory a first-class model primitive rather than an afterthought: https://arxiv.org/abs/2112.04426
- Generative Agents used observation, retrieval, reflection, and planning over stored experiences to create believable long-running behavior: https://arxiv.org/abs/2304.03442
- MemGPT framed LLM memory as tiered context management, with data movement between fast active memory and slower external stores: https://arxiv.org/abs/2310.08560
- Long context alone is not reliable memory. "Lost in the Middle" found that models can fail to use relevant information depending on where it sits in the prompt: https://arxiv.org/abs/2307.03172

## Requirements

AgentDrive should treat memory as a control system, not a bag of notes.

- Keep a scarce working set. The Experience Graph should choose what deserves immediate context instead of dumping every recent memory into the model.
- Preserve multiple memory kinds. Episodic traces, semantic continuations, and procedural densification patterns should be scored differently but exposed through one interface.
- Use decay and rehearsal. Old material should weaken unless it has been reactivated, cited, or converted into durable structure.
- Treat conflict as reconsolidation work. Low-coherence or contradictory graph material should be reopened and updated before being trusted as precedent.
- Consolidate high-signal material. Novel, salient, useful traces should become durable graph/DNA abstractions instead of remaining isolated observations.
- Keep provenance visible. Every selected item should explain why it was routed so models can reason about trust and use.

## Implemented Slice

`human-inspired-memory-triage-v1` is a deterministic triage layer that scores memory candidates on retention, working relevance, consolidation value, and reconsolidation pressure.

It routes candidates into:

- `working_set`: high relevance and salience; keep in scarce model context.
- `consolidate`: high-signal material that should become durable structure.
- `reconsolidate`: important but unstable or conflicting material that needs update before reuse.
- `archive`: addressable material that should stay out of active context.

`experience_graph_get_context_pack` now exposes `memory_systems_triage` so agents get a usable memory-control surface every time they request the structural briefing.
