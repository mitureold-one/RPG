import os
import sys
import time
import hashlib
import subprocess
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

AIMEMORY_BIN = os.path.expandvars(r"%LOCALAPPDATA%\ai-memory\ai-memory.exe")
WORKSPACE = "rpg"

WATCH_DIRS = [
    Path(r"c:\Users\Konor\Documents\RPGPRO\campaigns"),
]

file_hashes = {}

def load_auth_token():
    if "AI_MEMORY_AUTH_TOKEN" not in os.environ:
        token_path = Path(os.path.expandvars(r"%LOCALAPPDATA%\ai-memory\auth-token"))
        if token_path.exists():
            try:
                os.environ["AI_MEMORY_AUTH_TOKEN"] = token_path.read_text(encoding="utf-8").strip()
            except Exception:
                pass

def ensure_server_running():
    load_auth_token()
    req = urllib.request.Request("http://127.0.0.1:49374/admin/pages?limit=1")
    if "AI_MEMORY_AUTH_TOKEN" in os.environ:
        req.add_header("Authorization", f"Bearer {os.environ['AI_MEMORY_AUTH_TOKEN']}")
    try:
        with urllib.request.urlopen(req, timeout=1.5):
            return True
    except Exception:
        pass

    print("[AUTOMAÇÃO] Iniciando servidor ai-memory (http://127.0.0.1:49374)...")
    lock_file = Path(os.path.expandvars(r"%LOCALAPPDATA%\ai-memory\.serve.lock"))
    lock_holder = Path(os.path.expandvars(r"%LOCALAPPDATA%\ai-memory\.serve.lock.holder"))
    try:
        if lock_file.exists():
            lock_file.unlink(missing_ok=True)
        if lock_holder.exists():
            lock_holder.unlink(missing_ok=True)
    except Exception:
        pass

    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen([AIMEMORY_BIN, "serve", "--transport", "http"], creationflags=flags)

    for _ in range(10):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(req, timeout=1):
                print("[AUTOMAÇÃO] Servidor ai-memory conectado com sucesso!")
                return True
        except Exception:
            continue
    print("[AVISO] Servidor ai-memory ainda inicializando...", file=sys.stderr)
    return False

def get_file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def extract_title(content: str, default: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return default

def classify_page(rel_path: str):
    filename = Path(rel_path).name.lower()
    if "regra" in filename or "rules" in filename:
        return {
            "kind": "rule",
            "tier": "procedural",
            "pinned": True,
            "tags": ["regras", "sistema", "arbitragem"]
        }
    elif "ficha" in filename or "char" in filename or "state" in filename:
        return {
            "kind": "fact",
            "tier": "semantic",
            "pinned": True,
            "tags": ["personagem", "ficha", "estado"]
        }
    elif "diario" in filename or "archive" in filename or "cronica" in filename:
        return {
            "kind": "decision",
            "tier": "episodic",
            "pinned": False,
            "tags": ["diario", "cronica", "historico"]
        }
    elif "npc" in filename:
        return {
            "kind": "fact",
            "tier": "semantic",
            "pinned": False,
            "tags": ["npcs", "elenco", "ameacas"]
        }
    elif "mundo" in filename or "cenario" in filename or "lore" in filename or "location" in filename:
        return {
            "kind": "fact",
            "tier": "semantic",
            "pinned": False,
            "tags": ["cenario", "lore", "locais"]
        }
    else:
        return {
            "kind": "fact",
            "tier": "semantic",
            "pinned": False,
            "tags": ["lore", "campanha"]
        }

def sync_file_to_aimemory(campaign_id: str, file_path: Path, rel_path: str):
    load_auth_token()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"[ERRO] Falha ao ler {file_path}: {e}", file=sys.stderr)
        return False

    title = extract_title(content, file_path.stem)
    meta = classify_page(rel_path)

    cmd = [
        AIMEMORY_BIN, "write-page",
        "--workspace", WORKSPACE,
        "--project", campaign_id,
        "--path", rel_path.replace("\\", "/"),
        "--title", title,
        "--kind", meta["kind"],
        "--tier", meta["tier"],
        "--body", "-"
    ]
    if meta["pinned"]:
        cmd.append("--pinned")
    for t in meta["tags"]:
        cmd.extend(["--tag", t])

    try:
        proc = subprocess.run(cmd, input=content, text=True, capture_output=True, encoding="utf-8")
        if proc.returncode == 0:
            tier_info = f"{meta['tier'].upper()} ({meta['kind']})" + (" [PINNED]" if meta['pinned'] else "")
            print(f"[SYNC OK] {campaign_id} / {rel_path} -> ai-memory ('{title}') [{tier_info}]")
            return True
        else:
            print(f"[ERRO SYNC] {rel_path}: {proc.stderr.strip()}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[ERRO SYNC] Exceção ao executar ai-memory: {e}", file=sys.stderr)
        return False

def scan_and_sync():
    for base_dir in WATCH_DIRS:
        if not base_dir.exists():
            continue

        # 1. Estrutura por subpastas: <base_dir>/<campaign_id>/*.md
        for entry in base_dir.iterdir():
            if entry.is_dir():
                campaign_id = entry.name
                for file_path in entry.rglob("*.md"):
                    if not file_path.is_file() or "backup" in str(file_path).lower():
                        continue
                    rel_path = file_path.relative_to(entry).as_posix()
                    try:
                        current_hash = get_file_hash(file_path)
                    except Exception:
                        continue
                    full_key = f"{campaign_id}:{rel_path}"
                    if file_hashes.get(full_key) != current_hash:
                        if sync_file_to_aimemory(campaign_id, file_path, rel_path):
                            file_hashes[full_key] = current_hash

def main():
    print("=" * 60)
    print("Iniciando Ambiente RPG: ai-memory (SSOT Markdown RPGPRO)")
    print(f"Pastas monitoradas: {[str(d) for d in WATCH_DIRS]}")
    print("=" * 60)
    sys.stdout.flush()

    ensure_server_running()
    scan_and_sync()
    sys.stdout.flush()

    while True:
        try:
            time.sleep(2)
            scan_and_sync()
            sys.stdout.flush()
        except KeyboardInterrupt:
            print("\nDaemon finalizado pelo usuário.")
            break
        except Exception as e:
            print(f"[AVISO] Erro no loop de sync: {e}", file=sys.stderr)
            time.sleep(2)

if __name__ == "__main__":
    main()
