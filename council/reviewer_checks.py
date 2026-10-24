"""council/reviewer_checks.py: Sub-auditorias de facções, integridade causal e prosa externa."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from council.factions import (
    normalize_ascii_slug,
    parse_faction_ledger_from_diario,
    parse_factions_from_mundo,
    parse_reputation_from_ficha,
)

FACTION_STOPWORDS = {
    "ordem", "conselho", "guarda", "clã", "clan", "cla", "seita", "culto",
    "irmandade", "matilha", "matilhas", "tribo", "tropas", "tropa", "legiao",
    "legião", "exercito", "exército", "aliança", "alianca", "força", "forcas",
    "forças", "povo", "povos", "habitantes", "sociedade", "guilda", "familia",
    "família", "casa", "livres", "livre", "novo", "nova", "antigo", "antiga",
}


def audit_factions_in_campaign(info: Dict[str, Any], all_npcs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    mundo_path = info.get("mundo")
    factions_in_mundo = (
        parse_factions_from_mundo(mundo_path)
        if mundo_path and Path(mundo_path).exists()
        else []
    )
    ficha_path = info.get("ficha")
    reps_in_ficha = (
        parse_reputation_from_ficha(ficha_path)
        if ficha_path and Path(ficha_path).exists()
        else {}
    )

    if mundo_path and Path(mundo_path).exists():
        mundo_text_low = Path(mundo_path).read_text(encoding="utf-8").lower()
        for f_k, rep_obj in reps_in_ficha.items():
            if f_k == rep_obj["name"].lower():
                r_name = rep_obj["name"].lower()
                matched = False
                for f in factions_in_mundo:
                    f_name = f["name"].lower()
                    f_tag = f["tag"].lower()
                    if r_name in (f_name, f_tag):
                        matched = True
                        break
                    if normalize_ascii_slug(r_name) in (normalize_ascii_slug(f_name), normalize_ascii_slug(f_tag)):
                        matched = True
                        break
                    r_sig = set(re.findall(r"\w{4,}", r_name)) - FACTION_STOPWORDS
                    f_sig = set(re.findall(r"\w{4,}", f_name)) - FACTION_STOPWORDS
                    if r_sig and f_sig and (r_sig & f_sig):
                        matched = True
                        break

                if not matched:
                    r_sig_words = [w for w in re.findall(r"\w{4,}", r_name) if w not in FACTION_STOPWORDS]
                    if r_sig_words and any(w in mundo_text_low for w in r_sig_words):
                        matched = True

                if not matched:
                    issues.append({
                        "type": "FACTION_UNKNOWN",
                        "severity": "HIGH",
                        "detail": (
                            f"A facção '{rep_obj['name']}' consta em ficha.md com reputação "
                            f"({rep_obj['score']}), mas não está cadastrada em mundo.md sob "
                            f"'## 4. Facções, Forças Ativas & Alianças'."
                        ),
                    })

        for npc in all_npcs:
            npc_fac = (npc.get("faction") or "").strip()
            if npc_fac and npc_fac.lower() not in ("nenhuma", "independente", "sem facção", "sem faccao"):
                fac_match = None
                for f in factions_in_mundo:
                    f_name = f["name"].lower()
                    f_tag = f["tag"].lower()
                    if npc_fac.lower() in (f_name, f_tag):
                        fac_match = f
                        break
                    if normalize_ascii_slug(npc_fac) in (normalize_ascii_slug(f_name), normalize_ascii_slug(f_tag)):
                        fac_match = f
                        break
                    n_sig = set(re.findall(r"\w{4,}", npc_fac.lower())) - FACTION_STOPWORDS
                    f_sig = set(re.findall(r"\w{4,}", f_name)) - FACTION_STOPWORDS
                    if n_sig and f_sig and (n_sig & f_sig):
                        fac_match = f
                        break

                if not fac_match:
                    n_sig_words = [w for w in re.findall(r"\w{4,}", npc_fac.lower()) if w not in FACTION_STOPWORDS]
                    if not (n_sig_words and any(w in mundo_text_low for w in n_sig_words)):
                        issues.append({
                            "type": "FACTION_ORPHANED_NPC",
                            "severity": "MEDIUM",
                            "detail": (
                                f"O NPC '{npc['name']}' em npcs.md está afiliado à facção "
                                f"'{npc_fac}', mas esta não consta em mundo.md."
                            ),
                        })
                else:
                    rep_data = (
                        reps_in_ficha.get(fac_match["name"].lower())
                        or reps_in_ficha.get(fac_match["tag"].lower())
                    )
                    if rep_data and rep_data["score"] <= -2:
                        att_low = (npc.get("attitude") or "").lower()
                        weak_low = (npc.get("weakness") or "").lower()
                        will_low = (npc.get("will") or "").lower()
                        exc = any(
                            k in (weak_low + " " + will_low)
                            for k in ["amor", "trai", "leal a", "paixão", "secreto", "rebel"]
                        )
                        if (
                            any(
                                k in att_low
                                for k in ["amigável", "amigavel", "dócil", "docil", "submiss", "lealdade", "servil", "devot"]
                            )
                            and not exc
                        ):
                            issues.append({
                                "type": "FACTION_ATTITUDE_DESYNC",
                                "severity": "HIGH",
                                "detail": (
                                    f"Incongruência de Atitude: O NPC '{npc['name']}' pertence à facção "
                                    f"'{fac_match['name']}', contra a qual o protagonista tem reputação "
                                    f"{rep_data['score']} ({rep_data['tier']}), mas sua atitude é amigável "
                                    f"('{npc['attitude'][:60]}...') sem exceção psicológica justificada em Vontade ou Fraquezas."
                                ),
                            })

    diario_path = info.get("diario")
    faction_ledger = (
        parse_faction_ledger_from_diario(diario_path)
        if diario_path and Path(diario_path).exists()
        else []
    )
    last_ledger_scores: Dict[str, int] = {}
    for entry in faction_ledger:
        fn_low = entry["faction"].lower()
        last_ledger_scores[fn_low] = entry["new_score"]

    for fn_low, l_score in last_ledger_scores.items():
        matched_rep = None
        for r_k, r_obj in reps_in_ficha.items():
            if r_k == fn_low or r_obj["tag"].lower() == fn_low or r_obj["name"].lower() == fn_low:
                matched_rep = r_obj
                break
        if matched_rep and matched_rep["score"] != l_score:
            issues.append({
                "type": "FACTION_REP_MISMATCH",
                "severity": "HIGH",
                "detail": (
                    f"Divergência de Reputação: A reputação com '{matched_rep['name']}' na ficha "
                    f"({matched_rep['score']}) difere do saldo final registrado no diário ({l_score})."
                ),
            })

    return issues


def _read_committed_events_raw(events_dir: Path) -> List[Dict[str, Any]]:
    if not events_dir.exists():
        return []
    committed: List[Dict[str, Any]] = []
    for seg in sorted(events_dir.glob("*.jsonl")):
        current_open = False
        pending: List[Dict[str, Any]] = []
        for line in seg.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                break
            if not isinstance(obj, dict):
                break
            rec = obj.get("record")
            if rec == "batch":
                st = obj.get("state")
                if st == "open":
                    current_open = True
                    pending = []
                elif st == "committed" and current_open:
                    committed.extend(pending)
                    current_open = False
                    pending = []
            elif rec == "event" and current_open:
                pending.append(obj)
    return committed


def check_causal_inconsistencies(campaign_dir: Path | str, campaign_id: str) -> List[Dict[str, str]]:
    """Detecta correções pendentes (CAUSAL_INCONSISTENCY) e artefatos de prosa ausentes/corrompidos (PROSE_MISSING)."""
    c_dir = Path(campaign_dir)
    events_dir = c_dir / "events"
    if not events_dir.exists() and (c_dir / campaign_id / "events").exists():
        c_dir = c_dir / campaign_id
        events_dir = c_dir / "events"
    if not events_dir.exists():
        return []

    committed = _read_committed_events_raw(events_dir)
    issues: List[Dict[str, str]] = []
    pending_corrections: Dict[str, Dict[str, Any]] = {}

    for ev in committed:
        ev_type = ev.get("type")
        payload = ev.get("payload") or {}
        if ev_type == "correction.issued" and payload.get("inconsistency_detected"):
            cor_id = str(payload.get("correction_id", "desconhecida"))
            if payload.get("state") != "concluída":
                pending_corrections[cor_id] = {
                    "event_id": str(ev.get("event_id", "")),
                    "corrects": list(payload.get("corrects", [])),
                    "reason": str(payload.get("reason", "")),
                }
        elif ev_type == "correction.recomputed":
            cor_id = str(payload.get("correction_id", ""))
            outcome = str(payload.get("outcome", ""))
            if outcome == "RESOLVED":
                pending_corrections.pop(cor_id, None)
                for k, v in list(pending_corrections.items()):
                    if cor_id in v.get("corrects", []) or cor_id == v.get("event_id"):
                        pending_corrections.pop(k, None)
        elif ev_type == "prose.recorded":
            rel_path = str(payload.get("text_path", ""))
            expected_hash = str(payload.get("text_hash", "")).removeprefix("sha256:")
            turn_num = payload.get("turn", "?")
            if rel_path:
                target = c_dir / rel_path
                if not target.exists():
                    issues.append({
                        "type": "PROSE_MISSING",
                        "severity": "CRITICAL",
                        "detail": f"Artefato de prosa ausente para o Turno {turn_num}: '{rel_path}'.",
                    })
                elif expected_hash:
                    actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                    if actual_hash != expected_hash:
                        issues.append({
                            "type": "PROSE_MISSING",
                            "severity": "CRITICAL",
                            "detail": (
                                f"Artefato de prosa corrompido para o Turno {turn_num}: '{rel_path}' "
                                f"(hash esperado {expected_hash[:12]}..., obtido {actual_hash[:12]}...)."
                            ),
                        })

    for cor_id, info in pending_corrections.items():
        issues.append({
            "type": "CAUSAL_INCONSISTENCY",
            "severity": "CRITICAL",
            "detail": f"Inconsistência Causal Pendente: A correção '{cor_id}' invalidou premissas posteriores ('{info['reason']}').",
        })

    return issues


__all__ = ["audit_factions_in_campaign", "check_causal_inconsistencies"]
