# Módulo 5: Córtex de Memória Persistente & Sincronização (`ai-memory`)

Este documento é a **autoridade única e soberana** sobre a persistência no banco SQLite vetorial (`ai-memory`), o daemon de sincronização em segundo plano e os protocolos de busca semântica anti-alucinação.

---

## 1. Topologia da Memória

O `ai-memory` funciona como um córtex permanente estruturado em SQLite (FTS5 + Embeddings locais), com servidor HTTP escutando localmente:

```
campaigns/<campaign_id>/*.md ──► sync_daemon.py (< 2s) ──► ai-memory (Porta 49374)
                                                                │
                                                                ├── FTS5 (Texto Completo)
                                                                └── Vetores (Embeddings)
```

---

## 2. Classificação Semântica por Tiers de Retenção

O `sync_daemon.py` monitora os arquivos `.md` e classifica-os automaticamente:

| Arquivo | Tier no ai-memory | Kind | Pinned? | Comportamento de Retenção |
| :--- | :--- | :--- | :---: | :--- |
| **`regras.md`** | `PROCEDURAL` | `rule` | Sim | Leis de arbitragem e mecânicas da mesa. Imutável contra decaimento (*decay*). |
| **`ficha.md`** | `SEMANTIC` | `fact` | Sim | Vitais, atributos e habilidades do protagonista. Sempre prioritário na busca. |
| **`mundo.md`** | `SEMANTIC` | `fact` | Não | Conhecimento de cenário, facções e linha do tempo recuperável por similaridade. |
| **`npcs.md`** | `SEMANTIC` | `fact` | Não | Perfis, atitudes e fraquezas de personagens recuperados quando mencionados. |
| **`diario.md`** | `EPISODIC` | `decision` | Não | Histórico de cenas e turnos em ordem cronológica estrita. |

---

## 3. Protocolo de Recuperação do Game Master

1. **Recuperação Automática (`lazy_turn.py prepare`):**
   * A cada ação, o orquestrador consulta o `ai-memory` com base na ação do jogador e injeta os fragmentos mais relevantes no campo `"ai_memory_recall"` do JSON de pré-turno.
2. **Busca Manual por Similaridade Semântica (`search`):**
   * Para investigar fatos de turnos distantes, juramentos esquecidos ou pistas antigas:
   ```powershell
   & "$env:LOCALAPPDATA\ai-memory\ai-memory.exe" search --workspace rpg --project <campaign_id> "termo de busca"
   ```
3. **Leitura Integral de Documento Indexado (`read-page`):**
   ```powershell
   & "$env:LOCALAPPDATA\ai-memory\ai-memory.exe" read-page --workspace rpg --project <campaign_id> --path "npcs.md"
   ```

---

## 4. Garantia Anti-Alucinação

* **Isolamento de Projetos:** Cada campanha opera em seu próprio `--project <campaign_id>`, impedindo contaminação entre mundos distintos.
* **Consistência de Longo Prazo:** Permite resgatar ferimentos antigos, promessas esquecidas e consequências de escolhas mesmo após dezenas de sessões.
