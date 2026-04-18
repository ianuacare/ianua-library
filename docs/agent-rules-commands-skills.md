# Regole, comandi e skill per l’agente (Cursor e Claude Code)

Questo documento descrive **cosa c’è oggi** nel repository sotto `.cursor/` e `.claude/`, e **come usarlo** quando lavori con l’assistente AI.

---

## Dove si trova cosa

| Percorso | Ruolo |
|----------|--------|
| `.cursor/rules/*.mdc` | **Regole** applicate da Cursor (alcune sempre attive, altre per glob). |
| `.cursor/commands/*.md` | **Comandi slash** (es. `/build`): istruzioni che l’agente carica quando invochi quel comando. |
| `.cursor/skills/**/SKILL.md` | **Skill** strutturate: file lunghi con attivazione, limiti e verifiche. |
| `.claude/commands/*.md` | Copia/parallelo dei comandi per **Claude Code** (stesso set di file rispetto a `.cursor/commands/` in questo repo). |
| `.claude/settings.json` | Configurazione **Claude Code** (status line e hook shell). |

---

## Regole (`.cursor/rules/`)

Le regole sono file Markdown con frontmatter YAML. In Cursor, `alwaysApply: true` significa che valgono **sempre**; altrimenti possono essere limitate da `globs` (solo certi file).

### `project-conventions.mdc` (sempre attiva)

- **Contenuto**: stack **Python 3.12+**, packaging Hatchling, layout `src/ianuacare/`, extras opzionali; dove mettere logica (`core/`), adapter (`infrastructure/`), AI (`ai/`), bootstrap (`presets/`); typing e test; aggiornare `docs/` e API pubblica.
- **Come usarla**: quando scrivi o rivedi codice, rispetta la separazione delle cartelle e aggiorna documentazione se cambi API esportate.

### `git-conventions.mdc` (sempre attiva)

- **Contenuto**: **Conventional Commits** (`feat`, `fix`, …), scope consigliati (`core`, `ai`, `infrastructure`, …), branch `tipo/issue-desc`, PR con squash su `main`, Commitizen / `CHANGELOG`.
- **Come usarla**: titoli commit e branch coerenti con il tipo di modifica; scope allineato all’area toccata.

### `ci-pipeline.mdc` (solo file sotto `.github/**`, `alwaysApply: false`)

- **Contenuto**: modello CI atteso (Python, `ruff`, `mypy`, `pytest`, coverage); non saltare gate; segreti da GitHub; merge solo con CI verde.
- **Come usarla**: quando modifichi workflow GitHub Actions, mantieni lint + tipi + test come gate obbligatori.

### `security-standards.mdc` (solo `src/**/*.py`, `alwaysApply: false`)

- **Contenuto**: sanità dati sanitari/PII, segreti, validazione input, query parametrizzate, dipendenze.
- **Come usarla**: in codice che tocca dati sensibili o integrazioni esterne, verifica logging, errori e confini di fiducia.

### `mkdocs-documentation.mdc` (solo `src/ianuacare/**/*.py`, `alwaysApply: false`)

- **Contenuto**: quando modifichi API pubblica o comportamento documentato, aggiorna le pagine in `docs/` (vedi `mkdocs.yml`) nello stesso changeset; verifica con `mkdocs build --strict`.
- **Come usarla**: dopo refactor di `Pipeline` / `Orchestrator` / `InputDataParser` / `OutputDataParser` o export in `ianuacare`, controlla `docs/api-reference.md`, `docs/architecture.md`, ecc.

---

## Comandi (`.cursor/commands/` e `.claude/commands/`)

In Cursor puoi invocare un comando digitando **`/`** nella chat e scegliendo il nome (es. `/build`). I file in `.claude/commands/` sono l’equivalente per **Claude Code** (stesso testo, stesso uso concettuale).

| Comando | Cosa fa | Come usarlo |
|---------|---------|-------------|
| `/build` | Implementazione incrementale Python: slice piccole, `pytest` / `ruff` / `mypy`, niente auto-commit. | Chiedi una feature o modifica concreta; dopo, usa `/test` e `/review` prima di committare. |
| `/debug` | Triage bug: riproduzione → localizzazione → fix → test di regressione. Carica `debugging-and-error-recovery` + `backend-py-expert`. | Incolla stack trace o indica test rotto; non mescolare refactor grossi nello stesso step. |
| `/test` | “Quality gate” Python: suite test, lint, mypy, coverage da `pyproject.toml`. | Dopo modifiche sostanziali o prima di aprire PR. |
| `/review` | Revisione su più assi (correttezza, leggibilità, architettura, sicurezza, performance) senza modificare il codice. | Con diff pronta o elenco file; utile pre-merge. |
| `/code-simplify` | Refactor **senza cambiare comportamento**: Chesterton, test prima/dopo, un commit per semplificazione. Carica `code-simplification` + `backend-py-expert`. | Quando il codice funziona ma è troppo complesso; non per feature nuove o fix bug “veri”. |
| `/commit-files` | Suddivide e committa le modifiche secondo la skill **commit-manager** (vedi nota sotto). | Solo quando vuoi commit mirati; l’agente non deve pushare da solo. |

### Flusso consigliato

1. Nuova funzionalità → `/build` → `/test` → `/review` → commit manuale o `/commit-files`.
2. Test rosso o errore → `/debug` → `/test` → commit.
3. Solo pulizia → `/code-simplify` → `/test` → commit.

---

## Skill (`.cursor/skills/**/SKILL.md`)

Una **skill** è un documento che definisce *quando* applicarla, *cosa* è permesso/vietato e *come* verificare. In questo repository ci sono **tre** file `SKILL.md` attivi:

### `backend-py-expert`

- **Ruolo**: disciplina da “backend Python production-grade” (typing, test, logging, confini, verifiche).
- **Quando**: implementazione o revisione di codice Python in `src/`, test, integrazione con tool del progetto.
- **Riferimenti**: cartella `references/` accanto alla skill (pattern API, DB, test, sicurezza, ecc.).
- **Config opzionale**: `backend-py-config.json` in root (esempio: `backend-py-config.example.json` nella stessa cartella skill).

### `code-simplification`

- **Ruolo**: processo per refactoring che **non** cambia comportamento.
- **Quando**: richieste di semplificazione, deduplicazione, leggibilità senza nuove feature.
- **Nota**: nel testo interno cita anche `incremental-implementation` come skill complementare per le feature; vedi sezione “Note operative”.

### `debugging-and-error-recovery`

- **Ruolo**: processo di debug (riproduzione, causa radice, test di regressione, stop-the-line).
- **Quando**: fallimenti di test, CI, eccezioni, comportamenti inattesi.

### Cartelle sotto `.cursor/skills/` senza `SKILL.md`

Nel repo esistono ancora directory (es. `backend-ts-expert/`, `devops-aws-expert/`, template PM/SEO, ecc.) con **solo** file di riferimento o esempi, **senza** `SKILL.md`. Non sono skill “attivabili” come le tre sopra; restano materiale di riferimento eventualmente riutilizzabile se in futuro si ripristinano altri `SKILL.md`.

---

## Note operative e discrepanze da conoscere

1. **`/build`** nel file `build.md` chiede di caricare `.cursor/skills/incremental-implementation/SKILL.md`, ma in questo repository **non** è presente un tale `SKILL.md`. Per implementazioni incrementali, usa comunque il testo del comando `/build` (slice piccole + verifiche) e la skill `backend-py-expert`.
2. **`/commit-files`** rimanda a `.cursor/skills/commit-manager/SKILL.md`, che **non** è presente tra i `SKILL.md` attuali. Per i commit, segui `git-conventions.mdc` e, se usi Commitizen, `cz commit` come da regola.
3. **`debug.md`** menziona `commit-manager` come “non auto-commit”; l’intento resta: **nessun commit automatico** senza tua richiesta esplicita.
4. **`.claude/settings.json`** configura hook su script in `.scaffold/hooks/`. Se quella cartella **non** esiste nel clone, gli hook non verranno eseguiti finché non vengono aggiunti o aggiornati i path.

---

## Riepilogo rapido

| Tipo | Elementi nel repo |
|------|-------------------|
| **Regole** | `project-conventions`, `git-conventions`, `ci-pipeline`, `security-standards`, `mkdocs-documentation` |
| **Comandi** | `build`, `debug`, `test`, `review`, `code-simplify`, `commit-files` (stessi 6 in `.cursor/commands` e `.claude/commands`) |
| **Skill attive (`SKILL.md`)** | `backend-py-expert`, `code-simplification`, `debugging-and-error-recovery` |

Per domande su come estendere di nuovo skill o comandi, modifica i file sotto `.cursor/` (e allinea `.claude/commands/` se usi Claude Code in parallelo).
