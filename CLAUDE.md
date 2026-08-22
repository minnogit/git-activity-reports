# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Cos'è

Toolkit Bash + Python per estrarre statistiche di attività Git (commit, righe modificate, autori) e
generare grafici. Esiste in due varianti indipendenti che condividono lo stesso formato di dati e lo
stesso meccanismo di alias autori, più un'estensione VS Code che le richiama entrambe. Un terzo script,
`find_generated_candidates.sh`, non fa parte della pipeline dati: è uno strumento diagnostico standalone
che assiste la scrittura del `.gitattributes` di un repository da analizzare (vedi sezione dedicata).

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

`npm run lint` richiede `.eslintrc.json` (ESLint 8.x, formato classico non flat-config — la
versione installata non supporta `eslint.config.js`). `npm test` scarica un VS Code reale via
`@vscode/test-electron` (~330 MB, la prima volta) per lanciarci dentro l'estensione e i test
Mocha in `src/test/suite/`; in un ambiente con banda limitata o rete non raggiungibile può
fallire per timeout sul download, non per un problema nel codice — verificare la banda prima di
sospettare una regressione nei test stessi. Struttura minima: `src/test/runTest.ts` (avvia
`@vscode/test-electron`), `src/test/suite/index.ts` (raccoglie ed esegue con Mocha i file
`*.test.js` compilati, senza il pacchetto `glob` — una ricerca ricorsiva manuale basta per pochi
file e evita di legare il progetto a un'API cambiata più volte tra le sue major), `src/test/
suite/extension.test.ts` (fumo: l'estensione si attiva e registra i comandi previsti).

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
  data: [{author, total_commits, daily_data: [{day, date, commits, lines, added, deleted, files}],
  punch_card: [{weekday, hour, commits}]}], ownership: {ref_commit, ref_date, total_lines,
  by_author: [{author, lines, pct}]}}`. `punch_card` (0=lunedì..6=domenica, ora locale del
  commit) alimenta il quinto pannello "quando" di `plot_git.py`; assente nei JSON di versioni precedenti,
  nel qual caso il pannello viene saltato (non lasciato vuoto). `ownership` (solo formato `json`,
  disattivabile con `--no-ownership`) alimenta il sesto pannello: righe possedute per autore secondo
  `git blame` all'**ultimo commit ≤ end_date** (non HEAD, per riproducibilità) — una fotografia, non
  una serie temporale come il resto, quindi può includere autori mai attivi nel periodo. Nessuna
  esclusione automatica di file generati/vendorizzati (stessa scelta del churn, coerente col default
  di git-fame). Un `git blame` per file è inevitabile; parallelizzato con `xargs -P` (fino a `nproc`
  processi) — l'aggregazione per-autore deve avvenire DENTRO ogni processo figlio prima di scrivere
  sullo stdout condiviso: solo righe corte restano atomiche a livello di pipe, l'output multi-riga
  crudo di `git blame` concatenato da processi concorrenti si corrompe per interleaving (misurato).
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
5. **Nessun pathspec di esclusione passato a `git log`** — scelta deliberata, non un'omissione. Fino
   alla v2.x veniva passato un `EXCLUDE_PATHSPEC` (`.gitattributes` `linguist-generated`/`-vendored`,
   `node_modules/`, `dist/`, `vendor/`, `old/`, lock file...). **Rimosso** dopo aver misurato che
   qualunque pathspec di DIRECTORY applicato a `git log --numstat` rompe il rilevamento rename quando
   il lato SORGENTE di un file rinominato-con-modifiche cade sotto il pathspec e la destinazione no:
   git non trova più il "prima" nel diff filtrato e conta l'intera destinazione come aggiunta pura.
   Misurato: un file con 431 righe di diff reale riportato come 6.001 (14×), una giornata di lavoro da
   2.066 a 19.973 di churn (9,7×) — il trigger era `**/old/*`, un'esclusione di default presente da
   sempre, non solo quelle costruite su misura per Prisma/OpenAPI. Nessuno strumento comparabile
   esaminato (i grafici di GitHub, git-fame, GitStats) risolve questo in modo robusto — coerentemente,
   la scelta è contare tutto: elimina il bug per costruzione, e sposta `churn` a metrica meno
   indicativa delle tre (non più il primo pannello dei report — vedi "Plotter Python" sotto).
   `DAILY_CHURN_CAP` (vedi sotto) resta quindi l'unica protezione contro un outlier estremo.

### `find_generated_candidates.sh` — diagnostico, indipendente dalle statistiche del tool

Script standalone (non chiamato da collector/plotter, non condivide codice con essi): analizza un
repository e propone percorsi candidati a `linguist-generated`/`linguist-vendored`, con un livello di
evidenza (FORTE/MEDIA/DEBOLE). **Non pilota più le statistiche di questo tool** (vedi punto 5 sopra) —
resta utile solo per chi vuole popolare `.gitattributes` a beneficio di GitHub stesso (collassa i diff
nelle PR, percentuali di linguaggio del repo). **Non scrive `.gitattributes`, non modifica nulla** —
vincolo di design deliberato: durante lo sviluppo di questo stesso meccanismo una cartella di codice
archiviato scritto a mano (`old/`) è stata classificata come "generata" per errore, lo stesso genere di
errore che, applicato automaticamente, avrebbe anche innescato il bug dei rename del punto 5.

Logica in due fasi (non una sola: leggere solo la configurazione ATTUALE di un generatore non basta se
l'output si è spostato nel tempo — la posizione attuale può avere churn quasi nullo mentre la storia vera
sta in una posizione precedente che nessun file di configurazione attuale menziona):

1. Legge il campo `output` di ogni `schema.prisma` nel repo, poi espande ogni output alle sue posizioni
   storiche cercando file con lo stesso nome sotto prefissi diversi nella storia.
2. Classifica i percorsi ad alto churn: dentro una posizione nota dalla fase 1 → FORTE; marcatore
   `@generated`/`DO NOT EDIT` nel contenuto → FORTE; nome tipico di libreria vendorizzata → MEDIA
   (da confermare, non riconosce nomi di librerie specifiche come "TCPDF"); altrimenti DEBOLE.

Bug corretto in sviluppo, da non reintrodurre: la ricerca delle posizioni storiche per nome-file può
incrociare due generatori diversi che condividono nomi di output generici (Prisma genera sempre
`browser.ts`, `client.ts`, `enums.ts` a prescindere dal datasource). La funzione di attribuzione
(`lookup_generated_source`) raccoglie l'UNIONE di tutte le fonti che matchano un candidato — mai la
"più specifica" per lunghezza di percorso: un candidato può cadere sotto più voci registrate a
profondità diverse (radice del generatore E una sua sottocartella come `.../models`, aggiunte
entrambe dalla ricerca storica, che registra il genitore immediato di ogni file trovato). Scartare le
voci "meno specifiche" perdeva ambiguità reali tra le due radici invece di segnalarle.

Due trappole da conoscere se in futuro si passa di nuovo un pathspec a `git log` (es. per un uso mirato,
non per le statistiche di default — vedi punto 5 sopra):

- **I pattern si applicano al percorso come era in OGNI commit.** Escludere solo la posizione attuale
  di file spostati *peggiora* il risultato: la sorgente dello spostamento riemerge come cancellazione
  integrale (misurato: 2002 righe con filtro incompleto contro 1002 senza filtro). Per enumerare le
  posizioni storiche serve `--name-only --no-renames`, altrimenti git comprime i percorsi come
  `{vecchio => nuovo}` e le posizioni storiche restano invisibili.
- **Gli spostamenti puri NON gonfiano il churn quando NESSUN pathspec è applicato** (verificato: 0
  righe) — ma **qualunque pathspec di directory può romperlo** (punto 5 sopra): non basta escludere
  "anche i percorsi storici", perché una directory esclusa può essere l'origine di una promozione
  (un file che ne esce modificandosi) verso una destinazione non esclusa, in un punto della storia
  imprevedibile in anticipo.

Limite noto e non risolvibile per percorso: i commit da **squash/rebase merge** hanno un solo genitore,
quindi `--no-merges` non li esclude e riportano il lavoro di altri sotto un solo autore (in un caso
reale: 139.719 righe in un commit).
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

- **`plot_git.py`** → `git_stats.png`, 4 pannelli **in ordine di attendibilità, non di prima impressione**:
  commit nel tempo per autore, churn nel tempo per autore (+ trend), giorni attivi per autore, tabella
  riepilogo. Churn non è più il primo pannello (vedi "Vincoli di raccolta", punto 5). **Granularità
  adattiva**: ≤45 giorni → giornaliera, ≤250 → settimanale, oltre → mensile (`choose_bucket()`); serve
  perché una barra al giorno è illeggibile su periodi lunghi. **Quinto pannello opzionale** (striscia
  larga sotto la griglia 2×2, `panel_punch_card()`): heatmap giorno×ora di quando avvengono i commit,
  sequenziale a una tinta (rampa blu di `palette.md`), presente solo se il JSON ha `punch_card`.
  Deliberatamente descrittivo ("quando"), non valutativo ("quanto si è lavorato") — i timestamp dei
  commit non sono un proxy affidabile delle ore lavorate, quindi non è una quarta metrica nell'ordine
  di attendibilità sopra. Margini: quando almeno un pannello opzionale è presente, **non** si usa
  `fig.tight_layout()` — con un asse aggiuntivo "incompatibile" presente (la colorbar del punch
  card, o anche solo la legenda a livello di figura) avvisa "Axes that are not compatible" e poi
  NON calcola nulla: lascia i margini di default di matplotlib (0.125/0.9/0.11, verificato
  stampando `fig.subplotpars`), abbastanza larghi da non tagliare "Gabriele Stringano" per
  coincidenza ma molto più dello spazio realmente necessario (misurato: margini vistosamente
  sproporzionati). Si misura invece lo spazio EFFETTIVAMENTE occupato dall'etichetta y più lunga
  dopo `fig.canvas.draw()` (bbox del testo già renderizzato via `get_window_extent()`, non una
  stima) e si calcola da lì il margine sinistro minimo che la ospita, con `fig.subplots_adjust()`;
  right/top/bottom/hspace/wspace restano fissi (valori già verificati sul contenuto del report).
  Verificato anche con un nome sintetico da 47 caratteri: margine adattato correttamente, nessun
  taglio. **Sesto pannello opzionale** (`panel_ownership()`, striscia larga sotto gli altri):
  barre orizzontali con le righe possedute per autore secondo `ownership` nel JSON — FOTOGRAFIA a
  fine periodo (git blame all'ultimo commit ≤ end_date), non una serie temporale come tutto il resto:
  può includere autori mai attivi nel periodo. Stessa palette/assegnazione colori degli altri
  pannelli (chi non è tra i primi 8 per attività nel periodo si accorpa in "Altro", mai una tinta
  nuova). Il numero di righe extra (`extra_rows` in `main()`) si adatta a quali dei due pannelli
  opzionali (punch card, ownership) sono presenti nel JSON — 0, 1 o 2 righe in più sotto la griglia 2×2.
- **`plot_multiproject.py`** → `git_activity_multi_project_report_<start>_<end>.png`, 4 pannelli: giorni
  attivi per autore (primo), churn per progetto e autore, distribuzione del churn, tabella riepilogo per
  progetto.

#### Metriche (duplicate identiche nei due plotter — modificarle in entrambi)

```python
DELETED_WEIGHT = 0.4 ; DAILY_CHURN_CAP = 15000 ; W_CHURN = 1.0 ; W_FILES = 0.5
churn  = added + DELETED_WEIGHT * deleted
indice = Σ giorni [ W_CHURN*ln(1+min(churn_giorno, DAILY_CHURN_CAP)) + W_FILES*ln(1+file_distinti) ]
```

Il report mostra **giorni attivi, commit e churn affiancati, in quest'ordine di attendibilità**;
l'indice composito è deliberatamente relegato alla sola tabella. Tre proprietà da non regredire:

- **Additivo, non moltiplicativo.** La vecchia forma `ln(added)*ln(files)` azzerava tutto se un fattore
  era 0 (una giornata di sole cancellazioni valeva 0) e premiava lo spread: un find/replace su 100 file
  valeva ~6.7x un fix profondo in 1 file. Ora quel rapporto è ~1.4x.
- **Il cap è PER GIORNO.** Applicato a un aggregato di periodo (come faceva `plot_multiproject.py`)
  saturava: `ln(1+1000)` diventava costante per tutti e l'indice misurava solo i file toccati (esempio
  storico con il valore dell'epoca; il valore attuale del cap è 15000, vedi sotto).
- **Le cancellazioni pesano.** `deleted` entra nel churn; prima era ignorato.

**`DAILY_CHURN_CAP` non è una costante fissa per sempre.** Fissato a 1000 il 9 gennaio 2026, misurato
di nuovo ad agosto 2026 (repository reali con uso di agenti di coding AI) risultava al **90° percentile**
della distribuzione — troncava il 72% del churn di giornate normali (gen-mag: 44%), non solo di outlier.
Un commit reale da 336 file/22.180 churn ("CRUD per tutte le tabelle") ha confermato che non era rumore
da attenuare. Alzato a 15000 (p99 osservato). Se il modello di sviluppo cambia ancora, ricontrollare la
distribuzione (vedi README.md, sezione "Pesi delle metriche") prima di assumere che il valore attuale
resti corretto — non è una scelta estetica, è calibrata sui dati e va rifatta quando i dati cambiano.

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
`gitstat.sh`/`gitstat-multi.sh` (o i loro equivalenti da PATH) come processo figlio, poi mostra
il PNG risultante in una webview. Punti chiave:

- `findClosestGitRepo`/`findAllGitRepos` risalgono/scansionano il filesystem per trovare `.git`
  (comando "Analizza Progetto Corrente" vs "Analizza Tutto il Workspace (Multi-Repo)").
- Sceglie `gitstat.sh`/`gitstat-multi.sh` (o `gitstats`/`gitstats-multi`) in base al numero di
  repo trovati (1 vs N).
- `resolveRunner()` risolve lo script eseguibile in due modi, in ordine: (1) `gitstat(-multi).sh`
  accanto a `context.extensionPath` (modalità sviluppo/checkout del repo), (2) fallback su
  `gitstats`/`gitstats-multi` risolti dal `PATH` (`which`) — necessario perché un'estensione
  installata da `.vsix` finisce in `~/.vscode/extensions/...`, scollegata dal checkout: senza
  questo fallback l'installazione da VSIX/Marketplace non può funzionare (verificato: `vsce
  package` impacchetta solo i file dentro `vscode-extension/`, mai script della cartella
  genitrice). Se nessuno dei due è risolvibile, messaggio d'errore esplicito invece di un path
  non trovato silenzioso.
- Trova il PNG generato facendo match via regex sull'output testuale dei collector
  (`"Grafico generato con successo: ..."` / `"Report multi-progetto ... generato con successo: ..."`):
  se si cambia il messaggio di successo negli script bash, aggiornare anche queste regex.
- I default di configurazione `git-activity.startDate`/`endDate` sono date RELATIVE ("30 days
  ago"/"now"), mentre gli script a valle validano con un regex rigido `YYYY-MM-DD` (git non sa
  interpretare date relative): `resolveDate()` le risolve con `date -d <valore> +%Y-%m-%d`
  PRIMA di invocare lo script, per ogni valore configurato (non solo i default) — usa `date -d`
  e non un parser scritto a mano in TS, per restare sulla stessa semantica di GNU date già
  richiesta da tutto il resto del progetto. Senza questa risoluzione, la configurazione di
  fabbrica falliva SEMPRE al primo utilizzo (era così fino a che non è stato corretto: verificare
  di nuovo se si tocca `resolveDate`/`runAnalysis`). Se `date -d` non riconosce il valore
  configurato, messaggio d'errore esplicito invece di passarlo comunque al collector.
- `showImageInWebview()`: il PNG generato ha sempre lo stesso nome (`git_stats.png` ecc. — un
  contratto usato anche da riga di comando, non cambiato per questa estensione, vedi
  "Nessun pathspec di esclusione"/metriche sopra per lo stesso principio applicato altrove).
  Un URI identico a run precedenti rischia però di essere servito dalla cache della webview
  anche se il contenuto del file è cambiato: l'URI passato a `<img src>` porta quindi una query
  string col timestamp di generazione (`imageUri.with({ query: 't=' + Date.now() })`), che rende
  ogni run un URI diverso senza toccare il file né il suo nome. Nessun `enableScripts` (l'HTML
  non ne ha bisogno) e CSP esplicita (`default-src 'none'; img-src <cspSource>; style-src
  'unsafe-inline'`) — nessun permesso concesso senza che serva.
- `runAnalysis()`: stderr non è mai vuoto su una run riuscita (skip fetch, alias caricati,
  warning di libreria Python) — mostrarlo integralmente ad ogni run sarebbe rumore che nasconde
  un avviso vero. I collector prefissano SEMPRE con `"Avviso:"` ciò che è pensato per l'utente
  (vedi `git_stats_collector.sh`/`git_multiproject_stats_collector.sh`): l'estensione filtra
  stderr su quel prefisso e mostra solo quelle righe con `showWarningMessage`, anche quando il
  processo termina con successo. Se si aggiunge un nuovo avviso in un collector pensato per
  l'utente finale, usare lo stesso prefisso o non verrà mai mostrato nella webview.

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
