# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Cos'è

Toolkit Bash + Python per estrarre statistiche di attività Git (commit, righe modificate, autori) e
generare grafici. Esiste in due varianti indipendenti che condividono lo stesso formato di dati e lo
stesso meccanismo di alias autori, più un'estensione VS Code che le richiama entrambe.

## Comandi comuni

Non c'è build/test automatizzato per gli script: sono bash/python eseguibili direttamente. Verifica
manuale tipica dopo una modifica:

```bash
# Singolo repository (deve essere eseguito dentro un repo git)
./git_stats_collector.sh 2025-11-01 2025-11-30 json | python3 plot_git.py
./git_stats_collector.sh --fetch 2025-11-01 2025-11-30 text "Nome Autore"
./git_stats_collector.sh -h

# Multi-repository (eseguibile da qualsiasi directory)
./git_multiproject_stats_collector.sh --file project_list.txt 2025-11-01 2025-11-30 | python3 plot_multiproject.py
./git_multiproject_stats_collector.sh --start 2025-11-01 --end 2025-11-30 ~/repoA ~/repoB
./git_multiproject_stats_collector.sh -h

# Wrapper semplificati (richiedono che gli script sopra siano nel PATH)
./gitstat.sh 2025-12-01 2025-12-31 ["Autore"]
./gitstat-multi.sh 2025-12-01 2025-12-31 [percorsi...]
```

Sintassi bash quick-check: `bash -n <script>.sh`.

### Estensione VS Code (`vscode-extension/`)

```bash
cd vscode-extension
npm install
npm run compile     # tsc -p ./
npm run watch        # tsc -watch
npm run lint          # eslint src --ext ts
npm test              # compile + lint + node ./out/test/runTest.js
```

### Package Debian

Il workflow `.github/workflows/build-deb.yml` si attiva sui tag `v*` e pacchettizza
`git_stats_collector.sh`, `git_multiproject_stats_collector.sh`, `plot_git.py`, `plot_multiproject.py`
installandoli in `/usr/local/bin`, con `gitstat.sh`/`gitstat-multi.sh` rinominati `gitstats`/`gitstats-multi`.
Se si rinominano o spostano questi file, aggiornare anche quel workflow.

## Architettura

### Pipeline dati: collector (bash) → plotter (python)

Ogni variante segue lo stesso pattern: uno script bash interroga `git log`/`git log --numstat` e produce
JSON su stdout, che viene passato via pipe a uno script Python che lo legge da stdin e genera un PNG.
I due stadi sono disaccoppiati solo dal formato JSON — si può salvare l'output intermedio su file e
rieseguire il plot separatamente (`cat dati.json | python3 plot_git.py`).

- **`git_stats_collector.sh`** → singolo repo, granularità **giornaliera**. Formato output `text` o `json`
  (flag posizionale), filtro opzionale per autore singolo. Output JSON: array di `{author, total_commits,
  daily_data: [{day, date, commits, lines, added, deleted}]}`. Se non filtrato per autore include anche
  una riga aggregata `"author": "TOTALE"`.
- **`git_multiproject_stats_collector.sh`** → più repo, aggregato **per progetto** (non giornaliero).
  Sorgente repo: argomenti posizionali, oppure `--file <path>` (uno per riga, `#` = commento, supporta `~`
  e spazi). Output sempre JSON: array di `{project, author, lines, commits}`, dove `project` è il nome
  della cartella del repo.
- Entrambi gli script escludono i merge commit (`--no-merges`) e per default **non** eseguono `git fetch`
  (serve `--fetch` esplicito) — di proposito, per non introdurre dipendenza dalla rete e non alterare lo
  stato dei repo analizzati a sorpresa.
- Entrambi accettano anche **URL Git al posto di un path locale** (`--repo <url>` per il singolo repo,
  come percorso posizionale/riga di `--file` per il multi-repo). La risoluzione URL→path locale (funzioni
  `is_repo_url`/`resolve_remote_repo`/`resolve_repo_path`, duplicate identiche in entrambi gli script) clona
  il repo sotto `$GIT_ACTIVITY_REPOS_DIR` (default `~/repos`, cartella visibile e riusabile per sviluppo,
  non un cache dir nascosto) al primo utilizzo, poi lo riusa se il `remote origin` combacia con l'URL
  richiesto (fetch solo con `--fetch`, come per i repo locali). Se il nome di cartella derivato dall'URL
  collide con un repo diverso già presente, lo script si ferma con errore invece di clonare/sovrascrivere:
  la risoluzione va tramite un file di mapping opzionale
  `~/.config/git-activity-reports/git-activity-repos-map.json` (`{"<url>": "<nome-cartella>"}`).
- `lines = added + deleted` in entrambe le varianti — non è mai una misura assoluta, va sempre letta come
  indicatore (vedi le sezioni di interpretazione in README.md prima di aggiungere nuove metriche "KPI").

### Plotter Python

- **`plot_git.py`**: 1 grafico stacked bar (attività giornaliera per autore).
- **`plot_multiproject.py`**: 3 grafici comparativi tra progetti (bar, donut, ranking) e calcola un
  "Impact Score" aggiuntivo: `relevance = ln(min(added,1000)+1) * ln(files+1)` se `commits>0 e files>0`,
  altrimenti 0. Il cap a 1000 righe e il doppio log sono voluti (evitano che un commit enorme o un
  find/replace su tanti file domini la metrica) — non rimuoverli senza aggiornare anche README.md.
- Entrambi leggono JSON da stdin, quindi vanno sempre invocati in pipe da uno dei collector (o con un
  file JSON salvato precedentemente), non da soli.

### Alias autori (`git-activity-aliases.json`)

Entrambi i plotter (non i collector) cercano un file di mapping `{"Nome Git": "Nome Visualizzato"}` per
raggruppare autori con identità Git diverse sotto un nome comune. Ordine di ricerca (il primo trovato
vince, nessun merge tra livelli):

1. `./git-activity-aliases.json` (working directory corrente)
2. `$XDG_CONFIG_HOME/git-activity-reports/git-activity-aliases.json` (default `~/.config/...`)
3. `$XDG_CONFIG_HOME/git-activity-git-activity-aliases.json` (percorso legacy, mantenuto per compatibilità)
4. `/etc/git-activity-reports/git-activity-aliases.json`

Se nessun file esiste, i plotter continuano a funzionare senza raggruppamento. Questa logica di ricerca è
duplicata identica in entrambi gli script Python: se la si modifica, va cambiata in entrambi i posti.

### Estensione VS Code (`vscode-extension/src/extension.ts`)

Wrapper GUI che non duplica la logica di analisi: risolve i repo Git nel workspace e invoca
`gitstat.sh`/`gitstat-multi.sh` come processo figlio (`cp.execFile('bash', [scriptPath, ...args], ...)`),
poi mostra il PNG risultante in una webview. Punti chiave:

- `findClosestGitRepo`/`findAllGitRepos` risalgono/scansionano il filesystem per trovare `.git`
  (comando "Analizza Progetto Corrente" vs "Analizza Tutto il Workspace (Multi-Repo)").
- Sceglie `gitstat.sh` o `gitstat-multi.sh` in base al numero di repo trovati (1 vs N).
- Risolve `scriptPath` come `path.join(context.extensionPath, '..', scriptName)` — assume che
  l'estensione sia installata/eseguita da dentro il repo (o accanto agli script), non come pacchetto
  standalone. Se si cambia la disposizione delle cartelle, questo path va aggiornato.
- Trova il PNG generato facendo match via regex sull'output testuale dei collector
  (`"Grafico generato con successo: ..."` / `"Report multi-progetto ... generato con successo: ..."`):
  se si cambia il messaggio di successo negli script bash, aggiornare anche queste regex.

## Note per modifiche

- I due collector bash hanno strutture di parsing argomenti indipendenti (non condividono codice) — una
  fix a uno (es. gestione `--fetch`, help, risoluzione repository remoti) va replicata manualmente
  nell'altro se applicabile.
- Il formato JSON di output è un contratto tra bash e python: cambiare le chiavi in un collector richiede
  aggiornare il plotter corrispondente.
