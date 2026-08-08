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
  (flag posizionale), filtro opzionale per autore (match **esatto**), `--repo <path|url>` per analizzare
  un repo diverso dalla cwd. Output JSON: `{metadata: {start_date, end_date, project, date_basis},
  data: [{author, total_commits, daily_data: [{day, date, commits, lines, added, deleted, files}]}]}`.
- **`git_multiproject_stats_collector.sh`** → più repo, per progetto+autore **con dettaglio giornaliero**.
  Sorgente repo: argomenti posizionali, oppure `--file <path>` (uno per riga, `#` = commento, supporta `~`
  e spazi). Output: `{metadata, data: [{project, author, commits, added, deleted, lines, files,
  active_days, daily_data: [...]}]}`.
- Sono elencati **solo i giorni con attività**; i plotter ricostruiscono i giorni vuoti dal range in
  `metadata` (altrimenti il grafico comprimerebbe il tempo e il trend mentirebbe).
- Entrambi gli script escludono i merge commit (`--no-merges`) e per default **non** eseguono `git fetch`
  (serve `--fetch` esplicito) — di proposito, per non introdurre dipendenza dalla rete e non alterare lo
  stato dei repo analizzati a sorpresa.

#### Vincoli di raccolta da non regredire

Queste quattro scelte correggono difetti misurati e hanno tutte un test nel repo sintetico usato in
sviluppo; se si tocca la raccolta dati, verificarle di nuovo:

1. **Un solo `git log` per repo**, con aggregazione in `awk` (`%x01%H%x09%an%x09%ad --date=short
   --numstat`). Prima si lanciava un `git log` per ogni giorno *per ogni autore* (~2.200 invocazioni su
   8 mesi × 10 autori).
2. **Match autore esatto**, mai `--author=<nome>`: quel flag fa match per sottostringa, quindi con
   autori "Luca" e "Luca Bianchi" i commit del secondo venivano contati anche per il primo.
3. **Bucket per author-date, non committer-date.** `--since`/`--until` filtrano la committer-date, che
   il rebase riscrive. Per questo `--since` è esteso di 31 giorni indietro, non c'è `--until`, e il
   filtro esatto sul periodo è fatto in awk (git non sa filtrare per author-date).
4. **`files` = file distinti**, non righe di `--numstat`: lo stesso file in 3 commit conta 1, non 3.
   Contare gli eventi rendeva la metrica un proxy del numero di commit.
- Entrambi accettano anche **URL Git al posto di un path locale** (`--repo <url>` per il singolo repo,
  come percorso posizionale/riga di `--file` per il multi-repo). La risoluzione URL→path locale (funzioni
  `is_repo_url`/`resolve_remote_repo`/`resolve_repo_path`, duplicate identiche in entrambi gli script) clona
  il repo sotto `$GIT_ACTIVITY_REPOS_DIR` (default `~/repos`, cartella visibile e riusabile per sviluppo,
  non un cache dir nascosto) al primo utilizzo, poi lo riusa se il `remote origin` combacia con l'URL
  richiesto (fetch solo con `--fetch`, come per i repo locali). Se il nome di cartella derivato dall'URL
  collide con un repo diverso già presente, lo script si ferma con errore invece di clonare/sovrascrivere:
  la risoluzione va tramite un file di mapping opzionale
  `~/.config/git-activity-reports/git-activity-repos-map.json` (`{"<url>": "<nome-cartella>"}`).
- `lines = added + deleted` resta nel JSON per retrocompatibilità, ma i grafici usano `churn`
  (vedi sotto) — non è mai una misura assoluta, va sempre letta come indicatore (vedi le sezioni di
  interpretazione in README.md prima di aggiungere nuove metriche "KPI").

### Plotter Python

Entrambi leggono JSON da stdin, quindi vanno sempre invocati in pipe da uno dei collector (o con un file
JSON salvato precedentemente), non da soli. Entrambi accettano anche il formato JSON precedente (array
senza `metadata`) per poter rielaborare file vecchi.

- **`plot_git.py`** → `git_stats.png`, 4 pannelli: churn nel tempo per autore (+ trend), commit nel tempo
  per autore, giorni attivi per autore, tabella riepilogo. **Granularità adattiva**: ≤45 giorni →
  giornaliera, ≤250 → settimanale, oltre → mensile (`choose_bucket()`); serve perché una barra al giorno
  è illeggibile su periodi lunghi.
- **`plot_multiproject.py`** → `git_impact_multi_project_report_<start>_<end>.png`, 4 pannelli: churn per
  progetto e autore, distribuzione del churn, giorni attivi per autore, tabella riepilogo per progetto.

#### Metriche (duplicate identiche nei due plotter — modificarle in entrambi)

```python
DELETED_WEIGHT = 0.4 ; DAILY_CHURN_CAP = 1000 ; W_CHURN = 1.0 ; W_FILES = 0.5
churn  = added + DELETED_WEIGHT * deleted
indice = Σ giorni [ W_CHURN*ln(1+min(churn_giorno, DAILY_CHURN_CAP)) + W_FILES*ln(1+file_distinti) ]
```

Il report mostra **churn, commit e giorni attivi affiancati**; l'indice composito è deliberatamente
relegato alla sola tabella. Tre proprietà da non regredire:

- **Additivo, non moltiplicativo.** La vecchia forma `ln(added)*ln(files)` azzerava tutto se un fattore
  era 0 (una giornata di sole cancellazioni valeva 0) e premiava lo spread: un find/replace su 100 file
  valeva ~6.7x un fix profondo in 1 file. Ora quel rapporto è ~1.4x.
- **Il cap è PER GIORNO.** Applicato a un aggregato di periodo (come faceva `plot_multiproject.py`)
  saturava: `ln(1+1000)` diventava costante per tutti e l'indice misurava solo i file toccati.
- **Le cancellazioni pesano.** `deleted` entra nel churn; prima era ignorato.

#### Grafica

Palette fissa `SERIES` (8 tinte, validata per separazione CVD e contrasto): l'**ordine non è cosmetico**.
Oltre 8 autori la coda va in "Altro", mai generare tinte nuove. Il colore segue l'entità e resta lo
stesso in tutti i pannelli, non dipende dal rango. Griglie e assi sono hairline **solide** (non
tratteggiate); il "gap" tra segmenti impilati è tracciato nel colore della superficie, non come bordo.
La tabella di riepilogo non è decorativa: è il ripiego di accessibilità richiesto dalle tinte a basso
contrasto (aqua/yellow/magenta), perché nessun valore sia raggiungibile solo tramite il colore.

### Alias autori (`git-activity-aliases.json`)

I **collector** (non i plotter) cercano un file di mapping `{"Nome Git": "Nome Visualizzato"}` per
raggruppare autori con identità Git diverse sotto un nome comune. Ordine di ricerca (il primo trovato
vince, nessun merge tra livelli):

1. `./git-activity-aliases.json` (working directory corrente)
2. `$XDG_CONFIG_HOME/git-activity-reports/git-activity-aliases.json` (default `~/.config/...`)
3. `$XDG_CONFIG_HOME/git-activity-git-activity-aliases.json` (percorso legacy, mantenuto per compatibilità)
4. `<dir dello script>/git-activity-aliases.json` (risolvendo i symlink) — necessario perché il
   collector singolo si esegue **dentro il repo da analizzare**, dove `.` non è la cartella del tool:
   senza questo fallback un file alias messo accanto agli script non veniva mai trovato
5. `/etc/git-activity-reports/git-activity-aliases.json`

**Gli alias vanno applicati nel collector, sui dati grezzi, prima di ogni aggregazione** — non nel
plotter. Sommare metriche calcolate separatamente per ogni identità non equivale a calcolarle sui dati
uniti: con la vecchia formula uno sviluppatore con 2 identità git otteneva un punteggio ~1.5x superiore
a quello che avrebbe avuto con una sola identità.

Questa logica di ricerca è duplicata identica nei due collector (`find_aliases_file`/`dump_aliases_tsv`)
e in forma ridotta nei due plotter, dove serve solo a rielaborare JSON in formato legacy: se la si
modifica, va cambiata in tutti i posti.

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
  fix a uno (es. gestione `--fetch`, help, risoluzione repository remoti, raccolta dati) va replicata
  manualmente nell'altro se applicabile. Lo stesso vale per le costanti delle metriche e la palette nei
  due plotter. La duplicazione è una scelta del progetto: gli script devono restare eseguibili
  standalone (finiscono singolarmente in `/usr/local/bin` via pacchetto `.deb`), quindi non c'è un
  modulo condiviso da importare.
- Il formato JSON di output è un contratto tra bash e python: cambiare le chiavi in un collector richiede
  aggiornare il plotter corrispondente. **Attenzione in fase di test**: se esistono copie in
  `/usr/local/bin`, il `PATH` le trova prima del working tree, e i wrapper `gitstats`/`gitstats-multi`
  risolvono collector e plotter dal `PATH` — quindi eseguono le copie, non le modifiche appena fatte.
  Verificare con `command -v plot_git.py`.
- I messaggi di successo dei plotter (`"Grafico generato con successo: ..."` /
  `"Report multi-progetto ... generato con successo: ..."`) sono intercettati via regex
  dall'estensione VS Code: non cambiarli senza aggiornare `vscode-extension/src/extension.ts`.
- Prima di modificare le metriche, leggere le sezioni "Metriche Calcolate" e "Interpretazione dei Dati"
  del README: le proprietà della formula (additiva, cap per giorno, cancellazioni pesate) sono
  correzioni di difetti misurati, non preferenze estetiche.
