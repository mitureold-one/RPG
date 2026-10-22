# Quickstart Validation Guide: P2 Separação de Sistema e Motor

**Feature**: `separate-system-engine-p2`  
**Status**: Ready for Validation  
**Created**: 2026-10-21  

This guide provides runnable commands to verify that all P2 requirements function correctly end-to-end.

---

## 1. Verifying Modular Ruleset Extraction

Test that `rulesets.d20_3gates` is directly importable and operable without relying on `council.gm`:

```powershell
python -c "import rulesets.d20_3gates as r; print(r.roll_3_gates('Ataque', variant='normal', dc=15, stat_name='FOR', stat_val=14))"
```

**Expected Outcome**:
Prints a valid roll result dict containing `natural`, `modifier: 2`, `total`, `tier`, and `summary`.

---

## 2. Verifying Loud Failure on Missing or Invalid `schema_version`

Test that `find_campaign` fails loudly with an explicit `ValueError` or `FileNotFoundError` when a campaign lacks `schema_version`:

```powershell
# 1. Test against a campaign without schema_version (temporary fixture or inline check):
python -c "from council.helpers import find_campaign; import tempfile, pathlib; d = pathlib.Path('campaigns/_invalid_test'); d.mkdir(exist_ok=True); (d/'diario.md').write_text('# Sem Schema', encoding='utf-8'); 
try:
    find_campaign('_invalid_test')
    print('FAIL: Deveria ter falhado')
except ValueError as e:
    print('SUCCESS (Falhou ruidoso):', e)
finally:
    import shutil; shutil.rmtree(d, ignore_errors=True)
"
```

**Expected Outcome**:
Output contains: `SUCCESS (Falhou ruidoso): Campanha '_invalid_test' inválida: 'diario.md' não declara 'schema_version'`.

---

## 3. Verifying Valid Loading of Active Campaigns

Verify that all three canonical active campaigns load cleanly with valid schema versioning:

```powershell
python -c "from council.helpers import find_campaign; print([c for c in ['dinastia_cinzas', 'imperio_valiria', 'perpetuos_terra_incognita'] if find_campaign(c)])"
```

**Expected Outcome**:
Returns all three campaign names without any exceptions.

---

## 4. Verifying CLI Sanitization & Absence of Franchise Leaks

Verify that `--help` does not contain any hardcoded franchise/campaign names:

```powershell
python lazy_turn.py --help
python lazy_turn.py prepare --help
python lazy_turn.py commit --help
python lazy_turn.py arc --help
python lazy_turn.py init-campaign --help
```

Search across CLI output for forbidden words:
```powershell
python -c "import lazy_turn; p = lazy_turn.build_cli(); text = p.format_help(); assert 'Shinjuku' not in text and 'Kenjaku' not in text; print('CLI Sanitization: CLEAN')"
```

---

## 5. Running the Complete Automated Test Suite

Run all project unit tests:

```powershell
python -m unittest discover tests
```

**Expected Outcome**:
All tests pass with `OK`.
