"""council: Pacote de Especialistas Cooperativos do RPG Narrative Engine.

Exporta as funções principais de cada domínio:
- helpers: Localização de campanhas e manipulação de tempo
- ssot: Leitura e escrita de ficha.md e diario.md (relógios, arcos e vitais)
- gm: Resolução de dados dos 3 Portões e cálculo de custos
- narrator: Catálogo de NPCs, psicologia, agência e barreira epistêmica
- reviewer: Auditoria de SSOT, paradoxos temporais e estagnação narrativa
- writer: Integração com ai-memory e mandatos de estilo literário
"""

from council.helpers import (
    CAMPAIGN_DIRS,
    TEMPLATES_DIR,
    AIMEMORY_BIN,
    MONTHS_PT,
    MONTHS_MAP,
    CURRENT_SCHEMA_VERSION,
    DEFAULT_RULESET,
    load_ruleset,
    get_available_rulesets,
    get_campaign_system,
    get_campaign_overrides,
    parse_regras_manifest,
    find_campaign,
    init_campaign_from_templates,
    parse_time_increment,
    advance_time_str,
)

from council.ssot import (
    normalize_vital_key,
    parse_ficha_md,
    render_progress_bar,
    upsert_ficha_feature,
    parse_clocks_from_diario,
    parse_arc_from_diario,
    update_arc_in_diario,
    upsert_clock_in_diario,
    parse_plot_from_diario,
    upsert_planned_scene_in_diario,
    parse_diario_md,
    extract_turns_from_diario,
    parse_progression_from_ficha,
    update_progression_in_ficha,
    spend_attribute_point_in_ficha,
    spend_ability_point_in_ficha,
)

from council.quests import (
    parse_quests_from_diario,
    upsert_quest_in_diario,
    format_quest_header,
    parse_reward_xp,
)

from council.gm import (
    roll_3_gates,
    parse_cost_string,
    extract_npc_contest_modifier,
    roll_contest,
)

from council.narrator import (
    extract_md_field,
    parse_npcs_md,
    upsert_npc_to_md,
    split_npc_updates,
    apply_npc_updates_to_md,
    derive_npc_initiative,
    extract_npc_bonds,
    find_scene_relational_tensions,
    extract_epistemic_forbidden_terms,
    derive_situational_scene_structures,
)

from council.reviewer import (
    PT_MONTHS,
    parse_pt_date,
    detect_temporal_paradoxes,
    check_prose_lints,
    cmd_review,
)

from council.writer import (
    query_aimemory,
    MODE_PROSE_MANDATES,
    STRUCTURAL_SCENE_MANDATES,
)
