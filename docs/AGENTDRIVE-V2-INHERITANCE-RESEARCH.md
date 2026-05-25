# AgentDrive v2 — Inheritance Research Dossier

> Source material for [`AGENTDRIVE-V2-INHERITANCE.md`](AGENTDRIVE-V2-INHERITANCE.md). Two parallel investigations: Codex on implementation complexity, and a literature survey on how multi-agent systems handle shared experience and inheritance. Both converged on the same recommendation.
>
> Compiled: 2026-05-24.

---

## Part 1 — Codex implementation consult

Asked to evaluate Option B (sideways pull across cousins sharing an ancestor) against Option A (forward-only inheritance).

### Recommended storage shape

**SQLite closure table**, not a graph database. KuzuDB or a real graph DB is overkill at the 10k-agent scale we're targeting; recursive CTEs alone are workable but slower for repeated cousin queries. The closure table trades slightly more write cost for very cheap reads.

Schema:

```sql
CREATE TABLE ancestor_closure (
  ancestor_id   TEXT NOT NULL,
  descendant_id TEXT NOT NULL,
  min_depth     INTEGER NOT NULL,
  PRIMARY KEY (ancestor_id, descendant_id)
);
CREATE INDEX idx_descendant ON ancestor_closure(descendant_id);
```

### Cousin-within-N-hops query

```sql
SELECT c2.descendant_id, MIN(c1.min_depth + c2.min_depth) AS hop_dist
FROM ancestor_closure c1
JOIN ancestor_closure c2
  ON c1.ancestor_id = c2.ancestor_id
WHERE c1.descendant_id = :self
  AND c2.descendant_id != :self
GROUP BY c2.descendant_id
HAVING hop_dist <= 3;
```

At 10k agents with average depth 8 and branching factor 5, the closure table is ~80k rows for tree-ish topologies, "maybe a few hundred thousand" for multi-parent DAGs. SQLite handles that easily. Query cost: **milliseconds with proper indexing**.

### Cycle handling

**Forbid by construction.** Rule: a new agent may only point to already-existing parent agents. No editing parent edges later. Enforces `created_at(parent) < created_at(child)`, making ancestry a DAG automatically.

If later cross-fertilization edges are needed, model them separately (not in ancestry):

```sql
CREATE TABLE knowledge_import (
  importer_agent TEXT NOT NULL,
  source_agent   TEXT NOT NULL,
  genome_hash    TEXT NOT NULL,
  reason         TEXT,
  imported_at    INTEGER NOT NULL
);
```

### Capability shape

Do **not** make cousin reads depend on holding a cap to cousin-B specifically — that doesn't scale. Better:

```
dna:pull:lineage:<ancestor_agent_id>:max_hops=3
```

With optional attenuations: `topic=planning`, `eval>=0.8`, `expires_at`. Minted by the lineage owner (root ancestor agent key, or swarm owner / parent agent acting as delegated issuer). Important trade-off: revocation is hard once descendants have copied content locally.

### Failure modes unique to sideways pull

1. **Poisoned cousin blast radius.** In Option A, poison flows down one branch. In Option B, one bad cousin contaminates *every branch sharing the ancestor*. Mitigation: never auto-activate pulled Genomes; require eval gating, trust scores, quarantine state.
2. **Conflicting Genomes.** Two cousins may solve the same "slot" with incompatible frameworks/tools. Need deterministic conflict handling: `(problem_key, framework_family, eval_score, recency)` ranking, not blind union.
3. **Sybil flooding.** Attacker spawns thousands of descendants under a shared ancestor and floods query results. Mitigation: quotas per issuer, max descendants per lineage window, top-K per ancestor, trust-weighted sampling.

Plus: closure-table bloat, cap leakage, opaque provenance ("why did I inherit this?").

### Implementation cost

| Component | LOC |
|---|---|
| Schema + closure maintenance | 150–250 |
| Query API + tests | 150–250 |
| Cap checks + policy plumbing | 150–300 |
| Conflict/ranking/provenance | 200–400 |
| Migration/invariants/debug tooling | 150–300 |
| **Total** | **800–1500 LOC** |

**5–10 engineer-days for prototype, 2–3 weeks for production-grade.** The graph itself is not the expensive part. **Semantics are.**

### Recommended hybrid

Forward-only inheritance for base behavior, plus optional `lineage_share` grants scoped by ancestor/swarm/topic. Cousin reads allowed only within an explicitly-granted bucket. Cheaper than full Option B because access is based on explicit grant membership, not arbitrary common-ancestor search.

> **"If your hybrid still says 'shared ancestor within N hops,' you've already paid most of Option B's complexity."**

### Three things that will bite in production

1. **Closure-table correctness under multi-parent inserts** — off-by-one depth and duplicate-path bugs.
2. **Trust/blast-radius problems** from poisoned or low-quality cousin Genomes.
3. **Capability semantics** — especially revocation, provenance, and explaining to users why a given agent could read a given lineage.

---

## Part 2 — Literature survey

### Academic MAS

**Blackboard architectures** (HEARSAY-II, CMU ~1973). Established the canonical blackboard: global hierarchical data structure read/written by independent knowledge sources, coordinated by an opportunistic scheduler. The swarm-shared-memory archetype. Died — or never scaled past medium-sized systems — for three reasons in the literature:

1. **Consistency cost.** Global consistency requires locking, which becomes the bottleneck.
2. **Conflict resolution.** Specialists post mutually inconsistent hypotheses; the arbiter must encode global semantic knowledge, defeating modularity.
3. **Observability collapse.** With N writers, "why does the blackboard say X?" becomes intractable.

Direct descendant: **tuple space / Linda** (Gelernter & Carriero, Yale 1986). Lost to MPI / message-passing for the same reasons. Modern echoes: Redis pub/sub, Ray's object store, and recent LLM blackboard revivals (arXiv 2510.01285) which reintroduce the pattern because LLMs are robust to noisy context.

Sources: [Blackboard Architecture for MAS](https://callsphere.ai/blog/blackboard-architecture-multi-agent-systems-shared-knowledge-spaces), [LLM-based Multi-Agent Blackboard System](https://arxiv.org/html/2510.01285v1), [Tuple space — Wikipedia](https://en.wikipedia.org/wiki/Tuple_space), [Linda — Wikipedia](https://en.wikipedia.org/wiki/Linda_(coordination_language)).

**BDI agents** (Rao & Georgeff, 1995). Classical model is *intra-agent*: beliefs / desires / intentions live inside one agent. Distributed BDI was studied (BDICTL) but never specified inheritance — only social commitments between concurrently-living agents. **No "ancestral belief pull" in BDI literature.** Gap, not a settled answer.

Sources: [BDI Agents: From Theory to Practice](https://www.academia.edu/30608557/BDI_Agents_From_Theory_to_Practice), [Modal logic for BDI in distributed environments](https://ieeexplore.ieee.org/document/699226).

**KQML / FIPA-ACL.** Field's verdict: agents communicate via **performatives over messages**, not shared state. Reasons: formal semantics, locatability across networks, no global consistency needed, provenance baked into the envelope. Message-passing won because **every message carries identity** — you know who said what. Blackboards lose this.

Sources: [Agent Communication Languages Comparison (SmythOS)](https://smythos.com/developers/agent-development/agent-communication-languages-and-protocols-comparison/), [Bellifemine on FIPA/JADE](https://jmvidal.cse.sc.edu/library/bellifemine01a.pdf).

**Stigmergy** (Grassé; swarm robotics). Indirect coordination via environmental traces. Formalized in pheromone models, works at swarm scale (300+ Kilobots). Critical property: **pheromones decay**. Trails are not permanent inheritance; they're rolling, lossy, self-pruning shared memory. Pure stigmergy is forward-only in time and spatially local. **No literature describes cross-colony pheromone sharing — colonies are sealed.**

Sources: [Testing pheromone stigmergy in robot swarms (Royal Society)](https://royalsocietypublishing.org/doi/10.1098/rsos.190225), [Phormica photochromic stigmergy (Frontiers)](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2020.591402/full).

### MARL — PBT and AlphaStar's league

**Centralized Training, Decentralized Execution (CTDE).** Dominant pattern. During training a critic sees global state + joint actions; at execution each actor sees only local observation. MADDPG, QMIX, MAPPO. Typically share a *replay buffer* of joint transitions — but this is per-training-run, not cross-population. The [MAC-PO paper (AAMAS 2023)](https://www.ifaamas.org/Proceedings/aamas2023/pdfs/p466.pdf) explicitly notes that uniform sampling across agents poorly reflects multi-agent non-stationarity.

**Population-Based Training (PBT).** Agents periodically *exploit* (copy weights from a better-performing population member) and *explore* (perturb hyperparameters). Inheritance is **lateral within a generation** — siblings copy from siblings, not strictly forward through ancestors.

**AlphaStar's league** (DeepMind). Three classes: **main agents**, **main exploiters**, **league exploiters**. New competitors are "branched from existing competitors" — a snapshot-and-mutate operation. This is a **DAG**, not a tree. Frozen agents preserved as permanent opponents forever. Crucially: **all live agents play against all frozen ancestors regardless of lineage.** AlphaStar effectively allows sideways/cousin influence — but only as adversarial pressure, not as direct weight inheritance.

> **Pattern: forward-only weight inheritance, sideways-everyone adversarial exposure. Cousins influence each other's *gradient* but not each other's *parameters*.**

**Hindsight + inter-agent.** HMADDPG and AgentHER demonstrate one agent's failed trajectory becoming another's training data via goal-relabeling. AgentHER's core insight: *"a trajectory failing goal A is often a correct demonstration for an alternative goal B."* Justifies sharing failure traces sideways — but as **relabeled data**, not as authoritative memory.

Sources: [MADDPG TorchRL tutorial](https://docs.pytorch.org/rl/stable/tutorials/multiagent_competitive_ddpg.html), [Survey on Population-Based Deep RL (MDPI)](https://www.mdpi.com/2227-7390/11/10/2234), [AlphaStar DeepMind blog](https://deepmind.google/blog/alphastar-grandmaster-level-in-starcraft-ii-using-multi-agent-reinforcement-learning/), [AlphaStar Evolutionary Perspective (arXiv 1902.01724)](https://arxiv.org/pdf/1902.01724), [HMADDPG](https://link.springer.com/article/10.1007/s13042-022-01505-x), [AgentHER](https://arxiv.org/abs/2603.21357).

### Production multi-agent frameworks

**OpenAI Swarm.** Deliberately **stateless.** Each Agent has `instructions` + `functions`. State carried in `context_variables` passed in messages; handoffs transfer control by returning an `Agent` object. **No shared memory primitive.** They punted on the problem.

**Microsoft AutoGen.** `GroupChat` is the central primitive: a shared conversation log all agents read. State sharing = message history. `Memory` abstraction for cross-session persistence, but per-agent. Community building custom "shared specification" objects because pure conversation history loses structure. **Uses a single shared blackboard (the chat log); no inheritance model.**

**CrewAI.** Most relevant comparator. Recent versions unified memory into a single `Memory()` class with **hierarchical paths** like `/crew/research/agent/analyst`. All agents in a crew share crew memory by default. Path structure provides scoped views. Recall uses composite scoring (semantic + recency + importance). **Essentially AgentDrive's Personal+Swarm tiers already, minus the DNA tier.** No cross-crew inheritance primitive.

**LangGraph.** State is a typed dict that flows through the graph. Subgraphs **inherit the parent graph's checkpointer**. Parallel nodes that touch the same field require an explicit **reducer** (merge function) — the framework forces you to declare conflict-resolution semantics. **Key engineering lesson for AgentDrive: any shared/inherited state needs a declared reducer.**

**ROS / ROS 2 multi-robot.** Robots exchange **local pose graphs**, not policies. Maps merged via loop closure detection — a structured reconciliation step. Learned policies trained once and *replicated* across the fleet — forward-only deployment, no in-fleet evolution. ROS 2 namespace isolation is default; sharing is explicit topic remapping. **Robotics verdict: sharing is opt-in, structured, reconciled at semantic boundaries, not raw memory dumps.**

**MetaGPT / ChatDev.** MetaGPT encodes Standard Operating Procedures as prompt sequences; agents communicate via **structured documents** (PRDs, design docs) rather than free dialogue. Neither has cross-project memory inheritance.

Sources: [OpenAI Swarm guide (Morph)](https://www.morphllm.com/openai-swarm), [AutoGen Memory docs](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/memory.html), [CrewAI Memory Configuration (DeepWiki)](https://deepwiki.com/crewAIInc/crewAI/7.2-memory-configuration-and-storage), [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs), [Swarm-SLAM](https://arxiv.org/html/2301.06230v3), [MetaGPT (ICLR 2024)](https://proceedings.iclr.cc/paper_files/paper/2024/file/6507b115562bb0a305f1958ccc87355a-Paper-Conference.pdf).

### Memory poisoning is real and recent

[MemoryGraft (arXiv 2512.16962)](https://arxiv.org/abs/2512.16962) and [A-MEMGUARD (arXiv 2510.02373)](https://arxiv.org/pdf/2510.02373): poisoned memories inserted at up to **95% success**, trigger attacker-intended actions in **89% of retrievals**. **Any sideways memory channel is an attack channel.**

### Biology — vertical vs horizontal gene transfer

Vertical inheritance is the default in eukaryotes. High fidelity, slow, perfect provenance.

**Horizontal gene transfer (HGT)** in bacteria: conjugation (plasmids), transduction (phages), transformation (free DNA uptake). **Primary driver of antibiotic resistance.**

Two findings transfer directly:

1. **HGT is often driven by selfish mobile genetic elements** that spread even when they harm the host. The biological analog of memory poisoning is **transposons and resistance plasmids that hitchhike**. **Bacteria evolved CRISPR specifically as an immune system against HGT.**
2. **Bacteria evolved ratiometric quorum sensing to throttle HGT**: vertical transfer favored under low mating likelihood; horizontal only activates under high mating likelihood. **Sideways transfer is gated by context, not always-on.**

When HGT wins: rapid adaptation to novel selective pressure (antibiotics, new environments). When it backfires: spread of antibiotic resistance across species; fitness costs from incompatible gene interactions.

> **Biological verdict: vertical inheritance is the trunk; horizontal is a costly, gated, defended channel that nature opens only under environmental stress and closes again with immune systems.**

Sources: [HGT — Wikipedia](https://en.wikipedia.org/wiki/Horizontal_gene_transfer), [Role of HGT in Antibiotic Resistance (Lake Forest)](https://www.lakeforest.edu/live/files/the-role-of-horizontal-gene-transfer-in-antibiotic.pdf), [Ratiometric quorum sensing & HGT tradeoff (PMC7449403)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7449403/), [Selfish MGEs driving HGT (PMC9393566)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9393566/).

---

## Convergence

Codex (engineering analysis) and the literature survey (academic + production + biological) reached the **same conclusion through entirely different reasoning paths**:

| | Codex | Literature |
|---|---|---|
| **Base inheritance** | Forward-only DAG | Forward-only (biology: vertical; MARL: forward-only weights; ROS: replicate fleet-wide) |
| **Sideways access** | Explicit `lineage_share` grants, signed, scoped | Explicit, signed, scoped, TTL (KQML provenance; bacterial quorum gating) |
| **No cycles** | Forbid by construction (timestamp invariant) | No literature supports arbitrary cousin graphs |
| **Storage** | SQLite closure table | (engineering — not literature-addressed) |
| **Cost** | 800–1500 LOC if full sideways; ~2× forward-only for hybrid | (engineering) |
| **Defense** | Quarantine, eval gating, quotas | CRISPR-as-immune-system; A-MEMGUARD; explicit-grant patterns |

Both stop at exactly the same line: **build the forward-only DAG. Make sideways flow possible but never the default.** Nature stopped at this line. The production frameworks stopped at this line. The MARL literature stopped at this line. The implementation cost says this line is the right place to stop.

### Uncertainty flags

- MARL literature treats lateral inheritance as a *training-time* construct (PBT), not a *deployment-time* persistent graph. AgentDrive enters partially uncharted territory at the DNA tier — but the direction (gated, explicit) is well-supported.
- The biological analogy treats DNA as single inheritable traits. AgentDrive's Genome is closer to a narrative episode. Whether to split Genomes into smaller recombinable units (genes) is a product question the literature does not resolve.
- ProtonDrive's open clients don't re-encrypt on share-member removal, leaving a known revocation gap. Our `lineage_share` model has the same limit unless we accept the re-encryption cost. Document explicitly in `SECURITY.md`.

Word count: ~2,400.
