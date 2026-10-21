# Phase 0 Research & Technical Rationale: P0 Runtime & CLI Fixes

**Feature**: `fix-cli-and-runtime-p0`  
**Status**: Completed  
**Created**: 2026-10-21  

---

## 1. CLI Signatures Alignment (`plan`, `clock`, `arc`)

### Decision
Synchronize the documentation in `rpg-showrunner/SKILL.md` to match the exact `argparse` options in `lazy_turn.py`:
- `plan`:
  - Flag `--add` (alias `--beat`) instead of `--add-scene`.
  - Flag `--scene-type` (alias `--scene_type`) instead of `--type`.
  - Flag `--complete <int>` instead of `--complete-scene <ID>`.
  - Remove `--trigger` from `plan` documentation (it belongs to `clock`).
- `clock`:
  - Use `--advance <Nome>` and `--steps <int>` instead of `--advance "<Nome>:1"`.
  - Retain `--add <Nome>`, `--max <int>`, `--trigger <text>`, and `--resolve <Nome>`.
- `arc`:
  - Flag `--resolve-clocks` is a boolean flag (`action="store_true"`), not a string taking arguments.
  - Clarify optional flags `--title`, `--question`, `--stage`, `--scene-name`, `--date`, `--location`, `--present`, `--milestone`.

### Rationale
The CLI arguments parsed by `lazy_turn.py` are the ground truth runtime contract. Any discrepancy causes the Python runtime to abort with exit code 2 and `unrecognized arguments`, interrupting the session and forcing prompt retries.

### Alternatives Considered
- *Modifying the Python CLI to accept the documented aliases*: Rejected because it adds code complexity and technical debt to fix a documentation error. Aligning the documentation with the stable engine CLI adheres to the Ponytail principle (zero unnecessary code).

---

## 2. Literary Mandates for Orphan Scene Types (`prologue`, `epilogue`, `post_credits`)

### Decision
Add dedicated structural dictionary entries to `mandates_by_type` in `lazy_turn.py` (and in `council/writer.py` where applicable) for:
1. **`prologue`**:
   - `why_this_structure`: "Abertura solene de um novo arco ou era. Enquadra o mito fundador, os tabus arcaicos ou a movimentação silenciosa de forças cósmicas/políticas antes da entrada em cena do protagonista."
   - `structure_and_tone`: "Enquadramento Histórico/Cosmológico -> Revelação de um Augúrio ou Conspiração Germinal -> Gancho de Transição para o Ponto de Entrada da Crônica."
   - `dialogue_and_style`: "Tom de crônica épica ou romance histórico. Prosa densa e atmosférica. Conclua ancorando o prenúncio da tempestade que colidirá com o protagonista."
2. **`epilogue`**:
   - `why_this_structure`: "Conclusão e rescaldo após o clímax de um arco. Mostra a poeira baixando, as feridas cicatrizando e o novo equilíbrio de forças no mundo."
   - `structure_and_tone`: "Silêncio após a Tempestade -> Consequências Pessoais e Políticas a Médio Prazo -> Vislumbre do Destino e do Próximo Ciclo."
   - `dialogue_and_style`: "Tom contemplativo, melancólico ou de solene alívio. Diálogos íntimos com travessão entre sobreviventes. Conclua com um sentimento de encerramento de ciclo sem perguntas ao jogador."
3. **`post_credits`**:
   - `why_this_structure`: "Cena rápida e pungente estilo ferrão pós-créditos. Revela uma ameaça nas sombras, a sobrevivência inesperada de um rival ou uma traição silenciosa que muda o sentido da vitória anterior."
   - `structure_and_tone`: "Corte Abrupto para Local Oculto -> Revelação de 1 Detalhe Inquietante -> Gancho Cinematográfico Instantâneo."
   - `dialogue_and_style`: "Ritmo veloz, estritamente em terceira pessoa externa. Zero didatismo. Conclua no choque da revelação."

### Rationale
Previously, these three valid CLI choices fell back silently to `mandates_by_type["standard"]`, instructing the model to follow immediate action and combat beats rather than the reflective, framing prose demanded by an epilogue or prologue.

---

## 3. Disabling Showrunner Auto-Activation

### Decision
Modify `rpg-showrunner/SKILL.md`:
- Change frontmatter `description` to state that it activates **on demand** for macro-planning, arc transitions, and faction clock management, rather than "automaticamente em qualquer turno".
- Explicitly state in the header that the Showrunner does not interfere with turn-by-turn roleplay.

### Rationale
When both skills declare automatic activation, the LLM harness loads ~15 KB of competing prompts into the context window, causing authority confusion over who owns `prepare`, `commit`, and `diario.md`.

---

## 4. Path Relativization in Skill References

### Decision
Replace all occurrences of `file:///C:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-narrative-engine/references/...` in `SKILL.md` with relative markdown links `references/...`.

### Rationale
Absolute paths with drive letters (`C:`) and usernames (`Konor`) break on other machines, git clones, and CI environments. Relative paths are portable across all platforms.
