# Feature Specification: Narrative Structural Devices & Scene Modifiers

**Feature Name**: `narrative-structural-devices`  
**Status**: Draft  
**Created**: 2026-10-18  

---

## 1. Executive Summary & Problem Statement

In single-player and AI-driven tabletop roleplaying games, storytelling often suffers from the **"Protagonist-Spotlight Trap"**: the fictional world appears to exist solely in the immediate physical presence of the main character. Antagonists and external factions remain frozen until the player enters their room, long journeys or training periods devolve into dozens of repetitive micro-turns, and rich background lore or political machinations can only be clumsily delivered through exposition dumps from allied NPCs.

In serialized literature (light novels, fantasy sagas, cinematic anime), authors frequently employ dedicated **Structural Narrative Devices**:
- **Interludes & Parallel Scenes**: Temporarily shifting perspective to off-screen antagonists, rivals, or distant allies.
- **Timeskips & Training Montages**: Elegantly skipping months or weeks of routine practice, travel, or recovery while advancing the world state in bulk.
- **In-Universe Special Chapters (Dossiers / Epistolary Logs)**: Presenting intercepted messages, council transcripts, or intelligence dossiers.
- **Flashbacks & Recontextualization**: Temporarily jumping into the past to reveal the emotional anchor of a trauma, oath, or secret technique.
- **Prologues, Epilogues & Post-Credits Stingers**: Framing major narrative arcs before and after the central confrontation.

This feature integrates these specialized scene structures into the RPG narrative engine, providing structured modifiers for the narrator and writer while keeping state and timeline synchronization intact.

---

## 2. User Scenarios & Acceptance Criteria

### User Scenario 1: Experiencing Off-Screen Faction Repercussions (Interlude / Parallel Scene)
* **As a** player whose actions disrupted a major faction's operations,
* **I want** the narrative engine to deliver an interlude cutscene focusing entirely on the enemy leaders or distant allies reacting to my choices,
* **So that** I experience the organic consequences of my decisions and witness the world moving independently of my presence.
* **Acceptance Criteria**:
  - The scene header and text strictly feature the off-screen characters in their own location (`Presentes` without the protagonist).
  - The dialogue and decisions reflect the NPCs' registered drives and private knowledge, without leaking the protagonist's private thoughts.
  - The interlude can advance or trigger corresponding faction threat clocks.

### User Scenario 2: Skipping Routine Downtime (Timeskip & Training Montage)
* **As a** player embarking on extended travel, medical recuperation, or a multi-month training regime,
* **I want** to execute a timeskip montage that condenses weeks or months into a single evocative literary chapter,
* **So that** pacing remains exciting and I don't have to play through 20 repetitive micro-turns of daily routine.
* **Acceptance Criteria**:
  - The in-game calendar advances by the requested duration (days, weeks, or months).
  - Character vitals are restored or updated appropriately.
  - Off-screen faction clocks and world events advance proportionally to the elapsed time.
  - The resulting prose summarizes sensory changes, character growth, and newly arisen tensions before setting up the next active scene.

### User Scenario 3: Immersive Worldbuilding via In-Universe Documents (Special Dossier)
* **As a** player investigating a conspiracy or seeking intelligence on a mysterious organization,
* **I want** the storytelling engine to occasionally deliver a scene formatted as an in-universe classified report, intercepted missive, or council log,
* **So that** lore and strategic intelligence are discovered organically through world artifacts rather than generic exposition.
* **Acceptance Criteria**:
  - The prose adopts editorial/epistolary document formatting (headers, classifications, redactions, official stamps) tailored to the in-universe faction.
  - The document reveals partial, subjective, or biased intelligence based on the authoring organization's limited perspective.

### User Scenario 4: Emotional Anchoring through Flashbacks
* **As a** player facing a critical moral dilemma or encountering a figure from my character's forgotten past,
* **I want** the narrator to seamlessly weave a flashback scene depicting the historical event,
* **So that** the dramatic stakes and emotional resonance of the present choice are elevated.
* **Acceptance Criteria**:
  - The narrative clearly marks the temporal departure and return to the present.
  - The flashback grounds established traits, vows, or weaknesses without contradicting canonical timeline facts.

### User Scenario 5: Framing Major Milestones (Prologue, Epilogue & Post-Credits Stingers)
* **As a** player completing or initiating an overarching campaign arc,
* **I want** prologue and epilogue scene formats to frame the beginning and resolution of the saga, with optional post-credits teasers,
* **So that** the campaign feels structured like a high-tier serialized novel or prestige series.
* **Acceptance Criteria**:
  - Prologues establish overarching mysteries or ancient precedents prior to the protagonist's active involvement.
  - Epilogues summarize the long-term societal and personal aftermath following an arc climax.
  - Post-credits stingers deliver a punchy cliffhanger or glimpse of an emergent threat.

---

## 3. Functional Requirements

### 3.1 Structural Scene Modifiers
* **FR-01 (Scene Type Selection)**: The narrative engine must support explicit structural scene types:
  - `standard`: The regular 5-stage interactive protagonist scene.
  - `interlude` / `parallel`: Perspective shift to off-screen characters/factions.
  - `timeskip` / `montage`: Condensed temporal progression over days/weeks/months.
  - `dossier` / `epistolary`: In-universe intelligence document, transcript, or letter.
  - `flashback`: Temporal retrospection contextualizing a present element.
  - `prologue` / `epilogue` / `post_credits`: Arc-level boundary and thematic framing.
* **FR-02 (Protagonist Exemption for Cutscenes)**: When generating an `interlude`, `parallel`, or `dossier`, the system must waive protagonist presence checks and disable the requirement for immediate protagonist action, focusing entirely on secondary actors and world developments.

### 3.2 Timeskip & Batch World Progression
* **FR-03 (Calendar Batch Jump)**: The system must advance the in-game calendar by arbitrary intervals (e.g. `+14d`, `+2m`, or explicit target date) in a single atomic update.
* **FR-04 (Proportional Faction Clock Advancement)**: During timeskips, active threat clocks must advance proportionally to the elapsed time unless character precautions or off-screen interventions stalled them.
* **FR-05 (Resource Restoration on Extended Rest)**: Character vitals and resources must automatically replenish to full or appropriate rest thresholds during significant timeskips.

### 3.3 Epistolary Formatting & Epistemic Boundaries
* **FR-06 (Document Presentation)**: When `dossier` is active, the writer must output stylized in-universe epistolary typography (organizational headers, clearance levels, author signatures) instead of standard narrative prose.
* **FR-07 (Subjective Faction Perspective)**: In-universe documents and interludes must adhere strictly to the authoring faction's limited perspective, containing potential misinformation, prejudices, or blind spots.

### 3.4 Arc Framing & Pacing
* **FR-08 (Arc Transition Recording)**: Prologues and epilogues must update the active arc container (`arc_scale`) in the chronicle ledger, recording arc conclusions and milestone achievements.
* **FR-09 (Post-Credits Stinger Gate)**: Post-credits scenes must deliver a brief, high-tension revelation or teaser that sets up the next arc's central dramatic question.

---

## 4. Key Entities & Structural Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                    NARRATIVE SCENE TYPES                    │
├───────────────────┬─────────────────────────────────────────┤
│ Standard Turn     │ Protagonist active, 5-step state cycle  │
├───────────────────┼─────────────────────────────────────────┤
│ Interlude /       │ Third-party POV, off-screen agendas,    │
│ Parallel Scene    │ faction clock advancement               │
├───────────────────┼─────────────────────────────────────────┤
│ Timeskip /        │ Extended duration jump, bulk calendar,  │
│ Montage           │ resource replenishment, pacing reset    │
├───────────────────┼─────────────────────────────────────────┤
│ Special Dossier / │ In-universe epistolary document,        │
│ Epistolary Log    │ classified intelligence, biased lore    │
├───────────────────┼─────────────────────────────────────────┤
│ Flashback         │ Temporal retrospection, vow/trauma lore │
├───────────────────┼─────────────────────────────────────────┤
│ Prologue /        │ Saga & Arc framing, long-term aftermath,│
│ Epilogue / Stinger│ teaser for subsequent conflict          │
└───────────────────┴─────────────────────────────────────────┘
```

---

## 5. Success Criteria

1. **Elimination of Protagonist-Centric Blindness**: Players can view and experience off-screen developments without artificial contrivances or forced encounters.
2. **Zero-Friction Pacing Jumps**: Extended time periods (travel, multi-month training) can be executed in a single command without narrative stutter or desynchronized timelines.
3. **Format Variety & Immersion**: The storytelling system dynamically transitions between cinematic prose, epistolary reports, and retrospective scenes based on dramatic need.
4. **Strict Timeline & Clock Synchronization**: 100% of timeskips and interludes update the game calendar and advance associated narrative threat clocks deterministically.
5. **Campaign-Agnostic Utility**: All structural devices operate universally across any campaign genre (modern fantasy, space opera, grimdark, historical).

---

## 6. Assumptions & Scope Boundaries

### Assumptions
- The player or GM triggers special scene types deliberately when pacing or dramatic context calls for them.
- Cutscenes and interludes respect established NPC personalities and factions recorded in campaign files.

### Out of Scope
- This feature does not permanently remove the protagonist from the campaign; interludes are temporary vignettes.
- Does not alter core dice arbitration rules when active challenges occur.
