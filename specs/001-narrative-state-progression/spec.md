# Feature Specification: Narrative State & Progression Engine

**Feature Name**: `narrative-state-progression`  
**Status**: Draft  
**Created**: 2026-10-18  

---

## 1. Executive Summary & Problem Statement

In long-running AI-driven tabletop roleplaying games (TTRPGs), a critical failure mode is **narrative stagnation**: scenes deliver rich, immersive prose and visceral dialogue, yet the underlying story state remains frozen in place. 

Current observations in ongoing campaigns reveal that:
1. Conversations between characters recur across multiple turns without altering goals, loyalties, or leverage.
2. Looming antagonist threats and deadlines are discussed repeatedly as distant future events while the calendar advances past them, because no active pressure mechanism forces crises to trigger.
3. The narrative engine operates almost exclusively at the micro-level (the immediate scene room), leaving the macro-level (overall arc goals) and world-level (off-screen faction agendas) unmanaged.

This feature introduces an integrated **Narrative State & Progression Framework** operating across three distinct scales (Scene, Arc, and World). It mandates an explicit state-progression cycle (Objective → Resistance → Decision → Consequence → New State) and introduces deterministic narrative clocks for faction agendas and deadlines.

---

## 2. User Scenarios & Acceptance Criteria

### User Scenario 1: Preventing Dialogue Stagnation in Social Scenes
* **As a** player engaging in multi-character strategy or negotiation scenes,
* **I want** the characters' interactions to produce concrete shifts in position, leverage, or demands rather than repeating pleasantries or circular arguments,
* **So that** every turn moves the story forward and changes what options remain viable.
* **Acceptance Criteria**:
  - Every scene turn must introduce or advance at least one concrete development: a conceded point, an ultimatum delivered, a relationship shift, a lost resource, or a new constraint.
  - A turn cannot conclude leaving the narrative board identical to how it started.

### User Scenario 2: Active Off-Screen World & Faction Agendas
* **As a** player spending in-game time investigating, resting, or debating plans,
* **I want** off-screen factions, allies, and villains to advance their own goals in parallel,
* **So that** the world feels alive and indifferent to player hesitation, preventing indefinite postponement of consequences.
* **Acceptance Criteria**:
  - Significant advances in the game calendar (hours/days spent) or turns without direct disruption advance the progress of active faction agendas.
  - When a faction's countdown expires or reaches its threshold, a concrete world event, complication, or crisis directly impacts the campaign.

### User Scenario 3: Pacing Pressure via Ticking Clocks
* **As a** player navigating an escalating mystery or impending crisis,
* **I want** visible or deterministic countdowns tied to imminent deadlines (e.g. an impending ritual, a political vote, a hostage execution),
* **So that** time management becomes a meaningful strategic dilemma where choosing to pursue one path inevitably closes or complicates another.
* **Acceptance Criteria**:
  - Impending deadlines are explicitly tracked as progression segments.
  - Passing time deducts from remaining intervals; when intervals reach zero, the event triggers without waiting for player initiation.

### User Scenario 4: Tri-Scale Progression Awareness
* **As a** player progressing through a multi-chapter campaign,
* **I want** the storytelling system to maintain awareness of three synchronized layers:
  1. *Scene Scale*: What is at stake in this exact moment?
  2. *Arc Scale*: Which overarching conflict is currently escalating, and what milestone determines its resolution?
  3. *World Scale*: What macro forces and external agendas are in motion?
* **So that** tactical scene outcomes organically resolve or redirect the overarching story arc.
* **Acceptance Criteria**:
  - The storytelling engine identifies the active Arc conflict and ensures scene outcomes directly feed into or branch the Arc's trajectory.

---

## 3. Functional Requirements

### 3.1 Tri-Scale State Architecture
* **FR-01 (Scene Scale Tracking)**: The system must track the immediate scene objective, present stakeholders, immediate physical/emotional stakes, and the specific state shift produced when the scene concludes or transitions.
* **FR-02 (Arc Scale Tracking)**: The system must define the active story arc, its central dramatic question, the current escalation stage (Preparation, Confrontation, or Climax), and the pending revelation or turning point required to close the arc.
* **FR-03 (World Scale Tracking)**: The system must track active faction agendas, independent NPC goals, and off-screen developments that progress without requiring direct protagonist observation.

### 3.2 State-Progression Turn Cycle
* **FR-04 (Mandatory State Shift)**: Every completed narrative turn must transition through five discrete functional stages:
  1. *Active Situation*: A clear tension, obstacle, or question currently demanding resolution.
  2. *Resistance*: Physical, social, emotional, or environmental friction opposing easy resolution.
  3. *Player Agency*: An unforced player decision or action.
  4. *Consequential Impact*: Irreversible consequences applied to the world, character vitals, relationships, or information asymmetry.
  5. *Altered State*: A newly established status quo that opens new possibilities while permanently closing or altering prior paths.
* **FR-05 (Zero-Loop Gate)**: The system must disallow endings where no state change occurred. If a player action achieves only a neutral conversation or observation, the environment or an active NPC must introduce an external rupture or new development before the scene freezes.

### 3.3 Deterministic Narrative Clocks & Deadlines
* **FR-06 (Narrative Clock Structure)**: The system must support configurable progression clocks (divided into segmented steps, e.g. 4, 6, or 8 segments) representing impending threats, faction schemes, or environmental shifts.
* **FR-07 (Clock Advancement Triggers)**: Narrative clocks must advance based on:
  - Passage of in-game time (e.g., spending hours on investigation or travel).
  - High-consequence player failures or partial successes resulting in ticking penalties.
  - Deliberate neglect of known developing situations.
* **FR-08 (Threshold Breach & Rupture)**: When a clock fills all segments, the associated catastrophe, escalation, or faction strike must immediately trigger as an active scene rupture.

### 3.4 Dynamic Character & Relationship Vectors
* **FR-09 (Event-Grounded Relationship Evolution)**: NPCs' interpersonal attitudes (trust, rivalry, fear, resentment, loyalty) must update based on concrete witnessed events, broken promises, or shared trauma, rather than arbitrary narrative fiat.
* **FR-10 (Independent Off-Screen Agendas)**: NPCs not present in the current scene must be capable of changing locations, acquiring resources, or taking initiative aligned with their registered personal drives.

### 3.5 Pre-Turn Anti-Inertia Evaluation
* **FR-11 (Inertia Detection)**: Before generating any turn response, the system must evaluate recent turn history to determine if the primary objective has remained unresolved or stagnant for more than 2 consecutive interactions.
* **FR-12 (Inertia Breaking Directive)**: If narrative inertia is flagged, the system must instruct the storytelling engine to introduce a sudden complication, an ultimatum, a ticking clock escalation, or an off-screen consequence to force decisive action.

---

## 4. Key Entities & Domain Concepts

```
┌─────────────────────────────────────────────────────────────┐
│                       WORLD SCALE                           │
│  • Factions & External Agendas                              │
│  • Off-Screen Timelines & Events                            │
│  • Narrative Clocks (e.g., Threat Countdown: [3/6])        │
└──────────────────────────────┬──────────────────────────────┘
                               │ influences
┌──────────────────────────────▼──────────────────────────────┐
│                        ARC SCALE                            │
│  • Active Dramatic Question                                 │
│  • Escalation Stage (Preparation → Confrontation → Climax)  │
│  • Macro Milestones & Mystery Layers                        │
└──────────────────────────────┬──────────────────────────────┘
                               │ grounds
┌──────────────────────────────▼──────────────────────────────┐
│                       SCENE SCALE                           │
│  • Immediate Objective & Local Resistance                   │
│  • Present Characters & Interpersonal Tensions              │
│  • 5-Step Cycle: Situation → Resistance → Choice → Impact   │
│  • Resulting New State (Anti-Inertia Gate)                  │
└─────────────────────────────────────────────────────────────┘
```

* **Narrative Clock**: A discrete, multi-step tracker representing the progress toward an inevitable crisis, deadline, or faction objective.
* **Dramatic Arc**: A thematic container for a series of scenes centered around answering a single major dramatic question.
* **State Shift**: The tangible delta between the world before a turn and after a turn (e.g., alliance broken, secret revealed, clock ticked, location compromised).
* **Epistemic Horizon**: The strict boundary between what characters know and what exists only in the world scale or off-screen clocks.

---

## 5. Success Criteria

1. **Measurable Elimination of Stagnation**: 100% of generated narrative turns produce a documented state shift (resource expenditure, relationship update, clock advance, or fact revelation). Zero turns finish with identical situational parameters.
2. **Deterministic Deadline Enforcement**: 100% of active narrative clocks advance when corresponding time intervals pass. Deadlines cannot be artificially bypassed or postponed without deliberate character intervention.
3. **Tri-Scale Continuity**: When queried, the system can instantly report the current state of all three layers (active scene tension, active arc question, and pending world clocks).
4. **Preservation of Player Agency**: While external events and NPC demands escalate, 0% of player actions or internal psychological decisions are dictated or assumed by the narrative engine (adherence to strict anti-puppeteering).
5. **Agnostic Applicability**: The progression engine operates universally across any campaign setting (fantasy, sci-fi, horror, supernatural) without hardcoded genre assumptions.

---

## 6. Assumptions & Scope Boundaries

### Assumptions
- Campaigns maintain an accurate canonical timeline (date, hour) that serves as the temporal baseline for clock progression.
- The player retains sole discretion over character intentions and reactions.
- Faction agendas operate deterministically according to established NPC/faction drives documented in campaign lore.

### Out of Scope (What this feature does NOT do)
- Does not replace or alter dice mechanics (the 3-Gate mechanical arbitration remains intact).
- Does not dictate fixed prose word counts beyond existing narrative discipline guidelines.
- Does not force players onto a linear path; all choices, successes, or failures are valid, provided they yield irrevocable consequences.
