---
name: docs-sync
description: Aggiorna la documentazione con MkDocs Material quando cambia la libreria.
---

# docs-sync

Usa questa skill ogni volta che vengono introdotti o modificati moduli, classi, metodi, flussi, esempi o comportamento pubblico della libreria.

**Obbligatorio nel workspace:** la regola Cursor `.cursor/rules/mkdocs-documentation.mdc` (`alwaysApply: true`) richiede di aggiornare `docs/` insieme al codice quando cambia l’API o il comportamento documentabile.

## Obiettivo

Mantenere la documentazione in `docs/` sincronizzata con il codice reale, riducendo drift tra implementazione e docs.

## Procedura obbligatoria

1. Individua i cambiamenti lato codice (nuovi moduli, API cambiate, path rinominati, comportamento modificato).
2. Aggiorna i documenti impattati:
   - `docs/api-reference.md` per API pubbliche.
   - `docs/architecture.md` per package boundaries e flussi.
   - `docs/extending.md` per estensioni e integrazioni custom.
   - `docs/getting-started.md` per onboarding/esempi.
3. Se aggiungi una nuova pagina, registra il link in `docs/index.md`.
4. Verifica la navigazione MkDocs in `mkdocs.yml` (voce `nav`) includendo le nuove pagine e mantenendo il tema `material`.
5. Esegui un controllo finale di coerenza:
   - import path e nomi simboli aggiornati;
   - esempi eseguibili o realistici;
   - nessun riferimento a moduli rimossi.

## Output atteso

- Documentazione aggiornata insieme al codice.
- Nuove pagine presenti in `docs/index.md` e in `mkdocs.yml`.
- Nessuna incoerenza evidente tra API reale e docs.
