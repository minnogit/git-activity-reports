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
./git_stats_collector.sh 2025-11-01 2025-11-30 json mario@example.com   # filtro per email
./git_stats_collector.sh -h

# Multi-repository (eseguibile da qualsiasi directory)
./git_multiproject_stats_collector.sh --file project_list.txt 2025-11-01 2025-11-30 | python3 plot_multiproject.py
./git_multiproject_stats_collector.sh --start 2025-11-01 --end 2025-11-30 ~/repoA ~/repoB
./git_multiproject_stats_collector.sh --author mario@example.com 2025-11-01 2025-11-30 ~/repoA ~/repoB
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
  (flag posizionale), filtro opzionale per autore (match **esatto**, per nome oppure per email se il
  valore contiene `@`: vedi «Alias autori»), `--repo <path|url>` per analizzare
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
  Con un filtro autore l'ownership NON viene calcolata (il pannello mostrerebbe gli altri autori e i
  `git blame` sarebbero un costo senza beneficio).
- **`git_multiproject_stats_collector.sh`** → più repo, per progetto+autore **con dettaglio giornaliero**.
  Sorgente repo: argomenti posizionali, oppure `--file <path>` (uno per riga, `#` = commento, supporta `~`
  e spazi). `--author <nome|email>` filtra su una persona (stessa semantica del collector singolo; il
  parser accetta solo la forma `--author <valore>`, non `--author=<valore>`). Output: `{metadata, data:
  [{project, author, commits, added, deleted, lines, files, active_days, daily_data: [...]}]}`.
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
   Non c'è alcun tetto sul churn (vedi «Metriche» sotto): un outlier estremo compare per intero.

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
  interpretazione in README.it.md prima di aggiungere nuove metriche "KPI").

### Plotter Python

Entrambi leggono JSON da stdin, quindi vanno sempre invocati in pipe da uno dei collector (o con un file
JSON salvato precedentemente), non da soli. Entrambi accettano anche il formato JSON precedente (array
senza `metadata`) per poter rielaborare file vecchi.

**Nessuna valutazione delle persone** (principio di design dei due plotter, non un dettaglio
estetico): niente punteggi, niente ordinamenti né totali per persona nella vista predefinita.
Le persone compaiono come PRESENZA (chi ha lavorato quando), non come volume: gli autori sono
sempre in ordine ALFABETICO (legenda, impilamento, righe delle matrici; «Altro» ultimo — i colori
restano assegnati per rango perché serve al fold dei primi 8, ma l'ordine mostrato non è quello) e
le tabelle sono di repository o di progetto, mai per autore. Il «modo personale» è il filtro per
autore al collector, non un'altra versione dei grafici. L'ownership (pannello opzionale del
singolo) resta ordinata per righe possedute perché risponde a una domanda di concentrazione della
conoscenza (rischio da dipendenza da una persona), non di merito. Un indice composito per autore
c'era ed è stato tolto per questo (vedi «Metriche»): non reintrodurlo, né sotto forma di tabella
per persona con commit e churn, anche se in ordine alfabetico.

- **`plot_git.py`** → `git_stats.png`, griglia a righe **in ordine di attendibilità, non di prima
  impressione**: **matrice di presenza** per autore (riga 1, piena larghezza; al posto delle vecchie
  barre di «giorni attivi per autore», che ordinate per valore erano una classifica), poi commit e
  churn nel tempo per autore affiancati (riga 2, quest'ultimo con la linea di trend — churn non è il
  primo pannello, vedi "Vincoli di raccolta", punto 5), **riepilogo del periodo** (riga 3: UNA riga di
  totali del repository — commit, churn, file, giorni attivi, autori — mai per persona; `panel_table()`
  ha costanti diverse dal multi-repo, vedi sotto), poi i pannelli opzionali. **Granularità
  adattiva**: ≤45 giorni → giornaliera, ≤250 → settimanale, oltre → mensile (`choose_bucket()`, ora
  presente anche nel multi-repo); serve perché una barra al giorno è illeggibile su periodi lunghi.
  **Quinto pannello opzionale** (striscia larga sotto le prime tre righe, `panel_punch_card()`):
  heatmap giorno×ora di quando avvengono i commit, sequenziale a una tinta (rampa blu di
  `palette.md`), presente solo se il JSON ha `punch_card`. Deliberatamente descrittivo ("quando"),
  non valutativo ("quanto si è lavorato") — i timestamp dei commit non sono un proxy affidabile delle
  ore lavorate, quindi non è una quarta metrica nell'ordine di attendibilità sopra. Margini: **non** si
  usa mai `fig.tight_layout()` (nemmeno per il layout base, punch card/ownership assenti) — un
  gridspec a >2 righe di altezze disomogenee e/o un asse aggiuntivo "incompatibile" (la colorbar del
  punch card, la legenda a livello di figura) fa avvisare "Axes that are not compatible" e poi NON
  calcola nulla: lascia i margini di default di matplotlib (0.125/0.9/0.11, verificato stampando
  `fig.subplotpars`), abbastanza larghi da non tagliare "Gabriele Stringano" per coincidenza ma molto
  più dello spazio realmente necessario (misurato: margini vistosamente sproporzionati). Si misura
  invece SEMPRE lo spazio EFFETTIVAMENTE occupato dall'etichetta y più lunga dopo `fig.canvas.draw()`
  (bbox del testo già renderizzato via `get_window_extent()`, non una stima) e si calcola da lì il
  margine sinistro minimo che la ospita, con `fig.subplots_adjust()`; right/top/bottom/hspace/wspace
  restano fissi (valori già verificati sul contenuto del report). Verificato anche con un nome
  sintetico da 47 caratteri: margine adattato correttamente, nessun taglio. **Sesto pannello
  opzionale** (`panel_ownership()`, striscia larga sotto gli altri): barre orizzontali con le righe
  possedute per autore secondo `ownership` nel JSON — FOTOGRAFIA a fine periodo (git blame all'ultimo
  commit ≤ end_date), non una serie temporale come tutto il resto: può includere autori mai attivi nel
  periodo. Stessa palette/assegnazione colori degli altri pannelli (chi non è tra i primi 8 per
  attività nel periodo si accorpa in "Altro", mai una tinta nuova). Il numero di righe extra
  (`extra_rows` in `main()`) si adatta a quali dei due pannelli opzionali (punch card, ownership) sono
  presenti nel JSON — 0, 1 o 2 righe in più sotto le prime tre. **Altezza adattiva** (stesso criterio
  del multi-repo, costanti misurate indipendentemente): la riga del riepilogo ha altezza fissa per
  UNA riga (`TABLE_ROW_INCHES=0.267` per riga, `TABLE_PAD_INCHES=0.30`, `TABLE_RATIO_MIN=0.25`), la
  matrice di presenza si dimensiona sul numero di autori mostrati, e **il footer si adatta** a
  legenda (autori + "Trend", quest'ultimo presente solo se `len(labels) >= 3`) e riquadro dei limiti
  (vedi `fit_footer()`). `FIG_HSPACE=0.72` (era 0.6): con la matrice sottile l'altezza media degli
  assi scende e il gap fra righe, che è una frazione di quella media, si restringeva fino a far
  toccare la didascalia della punch card col titolo del pannello sotto (misurato).
- **`plot_multiproject.py`** → `git_activity_multi_project_report_<start>_<end>.png`, griglia a 2
  colonne: **due matrici nel tempo** a piena larghezza (presenza per autore su tutti i progetti, poi
  **attività per progetto nel tempo**: progetti × bucket, giorni distinti con attività nel progetto su
  tutti gli autori, righe per attività decrescente — sono progetti, non persone, quindi l'ordinamento è
  lecito), poi **una riga per metrica**: commit (barre impilate per progetto/autore via
  `panel_metric_by_project()` + ciambella di distribuzione via `panel_donut()`, entrambe generiche
  sulla metrica; barra 100% se i progetti sono < 3, via `_share_bar()`), churn (stessi due pannelli
  sulla metrica churn), tabella per progetto (churn, commit, giorni attivi, file, numero di autori). Le
  due matrici richiedono `metadata.start_date/end_date` e `daily_data` (le date dei giorni attivi
  arrivano da lì, `flatten()` le restituisce come `days_df`): con JSON legacy si SALTANO senza errori,
  non si lasciano vuote. Due vincoli da non regredire: (1) il churn sta SOTTO il commit, non accanto —
  le versioni più vecchie gli davano DUE pannelli e al commit zero (solo in tabella), incoerente con
  l'ordine di attendibilità dichiarato nel docstring del modulo; (2) **non** riaffiancare commit e
  churn sulla stessa riga "per confrontarli": è stato provato e NON funziona, perché ogni pannello
  riordina i progetti per il PROPRIO totale (`sort_values` in entrambe le funzioni) — misurato su dati
  sintetici, commit e churn producono ordinamenti completamente diversi appena un progetto ha commit
  grossi (un client rigenerato finisce ultimo per commit e primo per churn), quindi "prima barra a
  sinistra vs prima barra a destra" confrontava progetti DIVERSI; le scale y sono anche incommensurabili
  (es. 560 commit vs 420.000 righe). Un confronto commit-vs-churn onesto richiede un pannello dedicato
  (es. churn per commit per progetto), non due pannelli affiancati. Margini: stesso approccio di
  `plot_git.py` (misurare il testo renderizzato per il margine sinistro, mai un valore fisso —
  altrimenti tronca nomi lunghi come "Gabriele Stringano", misurato). **Altezza della figura
  adattiva**: le celle della tabella sono dimensionate dal FONT e non dall'asse che le contiene
  (misurato: 0.289" per riga header incluso, `TABLE_ROW_INCHES`, con l'asse fermo a 4.627" a qualunque
  conteggio di righe), quindi un `height_ratio` fisso sulla riga della tabella lasciava ~3.5" di banda
  vuota con 3 progetti e rischiava lo sforo con 12. Il ratio della tabella si calcola dal numero di
  progetti effettivamente mostrati (`MAX_TABLE_ROWS`), quello delle matrici dal numero di righe
  (`MATRIX_CELL_INCHES`), e l'altezza della figura segue, mantenendo `ROW_UNIT_INCHES` costante — così
  le righe dei grafici conservano la stessa dimensione assoluta a ogni conteggio. Corollario da NON
  regredire: header e footer sono in POLLICI (`HEADER_INCHES`/`SUPTITLE_INCHES`/
  `LEGEND_BOTTOM_PAD_INCHES`), non in frazione di figura — con frazioni fisse, accorciando la figura
  il suptitle finiva sopra il titolo del primo pannello (misurato con 3 progetti). Se si cambiano
  fontsize o `table.scale` in `panel_table`, rimisurare `TABLE_ROW_INCHES` (due render con conteggi
  diversi bastano: l'altezza è lineare nelle righe). **Il footer si adatta al numero di righe della
  legenda**: con più di `ncol=6` voci (8 autori + "Altro") la legenda va a capo su una seconda riga —
  con un footer fisso tarato su una riga sola, la seconda riga finiva sopra il pannello successivo
  (misurato: 9 autori sintetici, 2 righe di legenda, sovrapposte alla tabella). Il numero di righe
  (`legend_rows`, calcolato PRIMA di creare la figura da `len(author_order)` con lo stesso `ncol` con
  cui la legenda verrà poi disegnata) determina l'altezza riservata: 0.230" la prima riga, +0.1925" per
  ognuna successiva (`LEGEND_ROW1_INCHES`/`LEGEND_EXTRA_ROW_INCHES`, misurate via
  `get_window_extent()`, non un'ipotesi). Stesso bug e stesso fix in `plot_git.py`, dove alle
  voci-autore si aggiunge "Trend".

**Matrici** (`panel_matrix()`, `bucketed_days()`, `matrix_inputs()`, `alpha_order()`, duplicate
identiche nei due plotter): righe × bucket temporali, valore della cella = giorni DISTINTI con
attività nel bucket, calcolati con gli stessi bucket dei grafici nel tempo (stesso `full` giornaliero e
stessa `freq` di `resample`, così le colonne stanno sotto le stesse etichette). Celle vuote quasi
invisibili (`EMPTY_CELL`) perché «presente» risalti; rampa blu sequenziale a una tinta; numero dentro
la cella quando il bucket non è giornaliero (nessun valore raggiungibile solo col colore). La scala
ha `vmax` minimo 3: con `vmax=1` tutte le celle giornaliere (0/1) erano nere come "il massimo"
(misurato). La didascalia («Più scuro = più giorni attivi», più l'eventuale «mostrati N su M») sta
sulla RIGA DEL TITOLO, a destra: sotto l'asse ci sono già le etichette x a 45° e una didascalia lì
finiva sul titolo del pannello seguente (misurato). Tetto di righe (`MAX_MATRIX_ROWS=30` autori,
`MAX_PROJECT_ROWS=20` progetti): oltre, si tengono i più attivi — solo per il TAGLIO, l'ordine
mostrato resta quello della matrice — e la nota lo dichiara: mai un taglio muto. Altezza in POLLICI
(`MATRIX_CELL_INCHES=0.30` per riga, minimo `MATRIX_MIN_AXES_INCHES=0.60`).

**Lingua delle scritte nei grafici** (duplicata identica nei due plotter: `STRINGS`,
`detect_lang()`, `set_lang()`, `fmt_int()`). Ogni testo disegnato nel PNG passa da `T[...]`, mai
una stringa letterale nel codice dei pannelli: aggiungendo un testo, va messo in ENTRAMBE le
lingue di `STRINGS` in entrambi i file. Ordine di scelta: `--lang it|en`, `GIT_ACTIVITY_LANG`,
locale (`LC_ALL` > `LC_MESSAGES` > `LANG`, `it*` → italiano), altrimenti inglese — il locale come
default lascia invariato l'uso storico su un sistema italiano. Anche il separatore delle migliaia
segue la lingua (`5.351` / `5,351`). `OTHER_LABEL` ("Altro"/"Other") è reimpostata da `set_lang()`
prima di qualunque aggregazione. I messaggi su stdout/stderr restano in italiano: "Grafico generato
con successo"/"Report multi-progetto ... generato con successo" sono intercettati via regex
dall'estensione, che passa `GIT_ACTIVITY_LANG` dalla lingua di VS Code.

**`fit_footer()`** (duplicata nei due plotter): dopo il disegno misura il fondo reale dell'ultimo
pannello (`get_tightbbox`, etichette e didascalie comprese) e la cima di TUTTO il footer —
legenda e riquadro «cosa non misura» (`limits_note` in `STRINGS`, a capo con `textwrap` a
`LIMITS_WRAP_CHARS`, ancorato in pollici sopra la legenda) — e se si sovrappongono allunga la figura
solo del necessario, ri-ancorando ogni elemento del footer (`anchored = [(artista, pollici), ...]`)
alla nuova altezza e tenendo header/righe alla stessa distanza in pollici. Serve perché il footer
(`NOTE_INCHES`) è tarato sulla nota della tabella, ma in `plot_git.py` l'ultima riga può essere la
punch card o l'ownership, con etichetta x e didascalia sotto l'asse: misurato, con l'ownership in
fondo "Righe (git blame)" finiva sotto la legenda. Non sostituirla con un'altra costante per
combinazione di pannelli. Le barre impilate hanno inoltre un 8% di respiro sopra il massimo
(`set_ylim`), altrimenti il vertice toccava il bordo.

#### Metriche (duplicate identiche nei due plotter — modificarle in entrambi)

```python
DELETED_WEIGHT = 0.4
churn = added + DELETED_WEIGHT * deleted
```

Il report mostra **giorni attivi (matrice di presenza), commit e churn, in quest'ordine di
attendibilità**. Non c'è nessun tetto sul churn (i grafici usano il valore grezzo): un
`node_modules` committato per errore compare per intero.

**Nessun indice composito.** C'era (somma sui giorni di `ln(1+min(churn_giorno, cap))` e
`ln(1+file_distinti)`, solo in tabella) ed è stato tolto: era la parte più simile a un punteggio per
persona e invitava a leggere la tabella come una classifica. Tre lezioni misurate valgono per
qualunque metrica composita se mai se ne reintroducesse una:

- **Additivo, non moltiplicativo.** La vecchia forma `ln(added)*ln(files)` azzerava tutto se un fattore
  era 0 (una giornata di sole cancellazioni valeva 0) e premiava lo spread: un find/replace su 100 file
  valeva ~6.7x un fix profondo in 1 file. Con la forma additiva quel rapporto era ~1.4x.
- **Un tetto è PER GIORNO.** Applicato a un aggregato di periodo (come faceva `plot_multiproject.py`)
  saturava: diventava costante per tutti e la metrica misurava solo i file toccati.
- **Le cancellazioni pesano.** `deleted` entra nel churn; prima era ignorato.

**Una soglia calibrata sui dati va ricalibrata quando i dati cambiano.** Il tetto giornaliero del
churn, quando c'era, fissato a 1000 il 9 gennaio 2026, misurato di nuovo ad agosto 2026 (repository
reali con uso di agenti di coding AI) risultava al **90° percentile** della distribuzione — troncava
il 72% del churn di giornate normali (gen-mag: 44%), non solo di outlier. Un commit reale da 336
file/22.180 churn ("CRUD per tutte le tabelle") ha confermato che non era rumore da attenuare. Era
stato alzato a 15000 (p99 osservato). Per misurare la distribuzione vedi README.it.md, sezione "Pesi
delle metriche".

#### Grafica

Palette fissa `SERIES` (8 tinte, validata per separazione CVD e contrasto): l'**ordine non è cosmetico**.
Oltre 8 autori la coda va in "Altro", mai generare tinte nuove. Il colore segue l'entità e resta lo
stesso in tutti i pannelli, non dipende dal rango. Griglie e assi sono hairline **solide** (non
tratteggiate); il "gap" tra segmenti impilati è tracciato nel colore della superficie, non come bordo.
Il ripiego di accessibilità richiesto dalle tinte a basso contrasto (aqua/yellow/magenta) — nessun
valore raggiungibile solo tramite il colore — oggi è: i numeri dentro le celle delle matrici con
bucket non giornalieri, la riga di totali del repository (singolo) e la tabella per progetto
(multi). Non c'è più una tabella con i valori per autore: i colori degli autori nelle barre
impilate dicono CHI, i totali per persona non sono raggiungibili da nessuna parte, di proposito.

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

**Chiavi email.** Una chiave che contiene `@` è un'EMAIL: `dump_aliases_tsv` la normalizza in
minuscolo (match case-insensitive), le altre chiavi restano nomi. Priorità: alias per email > alias per
nome > nome così com'è (`resolve()` nell'awk dei collector, stessa regola nell'ownership). Nome ed email
vengono da `%aN`/`%aE` di `git log` e dalle righe `author`/`author-mail` di `git blame --line-porcelain`:
tutte rispettano un `.mailmap` del repository, che quindi unisce le identità già prima degli alias.
**Nessun merge automatico «stessa email = stessa persona»**, scelta deliberata: email condivise,
indirizzi `noreply` e bot unirebbero persone diverse; l'unione resta esplicita (alias o `.mailmap`).

**Filtro autore** (4° argomento posizionale del singolo, `--author` del multi). Un valore con `@` è
un'email: confronto esatto e case-insensitive sull'email dopo il `.mailmap`; se gli alias associano
quell'email a un nome visualizzato D, il filtro include TUTTI i commit risolti a D (altrimenti si
perderebbero le altre identità della stessa persona), altrimenti solo i commit con quell'email — non
quelli con lo stesso nome, perché due email possono stare sotto lo stesso nome. Un valore senza `@` è il
nome visualizzato esatto, o il nome git originale risolto dalla mappa per nome (comportamento storico).
Il filtro agisce in awk sui commit grezzi, PRIMA dell'aggregazione: il TSV aggrega per nome visualizzato,
quindi un filtro per email non si può applicare dopo. Se non c'è nessun dato: `Avviso: nessun dato per
l'autore ...` con l'elenco dei nomi visti nel periodo (l'awk li accoda a un file temporaneo).

**Gli alias vanno applicati nel collector, sui dati grezzi, prima di ogni aggregazione** — non nel
plotter. Sommare metriche calcolate separatamente per ogni identità non equivale a calcolarle sui dati
uniti: con la vecchia formula uno sviluppatore con 2 identità git otteneva un punteggio ~1.5x superiore
a quello che avrebbe avuto con una sola identità.

Questa logica di ricerca è duplicata identica nei due collector (`find_aliases_file`/`dump_aliases_tsv`)
e in forma ridotta nei due plotter, dove serve solo a rielaborare JSON in formato legacy: se la si
modifica, va cambiata in tutti i posti.

### Estensione VS Code (`vscode-extension/src/extension.ts`)

Wrapper GUI che non duplica la logica di analisi: risolve i repo Git nel workspace e invoca
collector e plotter (mai i wrapper `gitstat(-multi).sh`, che restano solo per l'uso a riga di
comando) come una pipe di due processi figli collegati direttamente via stdout/stdin (mai
`bash -c` con una stringa: evita di dover quotare percorsi/date/nomi progetto), poi mostra il
PNG risultante in una webview. Punti chiave:

- `findClosestGitRepo`/`findAllGitRepos` risalgono/scansionano il filesystem per trovare `.git`
  (comando "Analizza Progetto Corrente" vs "Analizza Tutto il Workspace (Multi-Repo)").
- Sceglie la coppia collector+plotter per singolo repo o multi-repo in base al numero di repo
  trovati (1 vs N).
- `git-activity.analyzeMyWork` («Analyze My Work»): stessi report, filtrati su una persona. Identità:
  impostazione `git-activity.author` (nome o email), altrimenti `git config user.email` del repo corrente
  (`resolveAuthor()`, `execFile`, mai shell). Con più repo nel workspace un QuickPick chiede progetto
  corrente o intero workspace. L'autore arriva a `runAnalysis(context, paths, author)`: collector singolo =
  4° argomento posizionale DOPO `json`, multi = `--author <valore>` PRIMA delle date. L'estensione non
  risolve alias né `.mailmap`: passa l'identità così com'è e il collector fa il resto. Col filtro il report
  singolo non ha ownership (il plotter salta il pannello se la chiave manca).
- `resolveScriptPaths()` risolve i percorsi di collector e plotter in tre modi, in ordine: (1)
  `bundled/` dentro l'estensione stessa, popolata da `npm run copy-bundled`
  (`scripts/copy-bundled.js`) durante `vscode:prepublish` e quindi già presente in ogni `.vsix`
  impacchettato — è ciò che rende un'installazione da VSIX/Marketplace autosufficiente, senza
  bisogno del pacchetto `.deb` sul sistema (prima di questo fix l'estensione dipendeva SEMPRE
  da `gitstats`/`gitstats-multi` nel `PATH`, perché `vsce package` impacchetta solo i file
  dentro `vscode-extension/`, mai script della cartella genitrice — `bundled/` risolve questo
  copiandoli DENTRO `vscode-extension/` a build-time, non cambiando cosa `vsce` impacchetta);
  (2) la cartella genitrice di `context.extensionPath` (modalità sviluppo/checkout del repo,
  quando `bundled/` non è ancora stata popolata); (3) fallback sugli stessi nomi di script
  risolti dal `PATH` (`which`) — come installati dal pacchetto `.deb`. Se nessuno dei tre è
  risolvibile, messaggio d'errore esplicito invece di un path non trovato silenzioso.
  `runPipeline()` fa da `bash -c 'collector | plotter'` senza shell: `spawn` sui due processi,
  `p1.stdout.pipe(p2.stdin)`, stderr di entrambi concatenato nell'ordine collector-poi-plotter
  (stesso ordine che avrebbe una pipe di shell reale, dove nessuno dei due stderr è
  rediretto) — l'esito/errore finale segue quello del plotter (ultimo anello della pipe), con
  lo stderr del collector anteposto per non perderlo se è il collector a fallire.
- **Cartella di output e cwd** (`resolveOutputDir`/`runPipeline`): il plotter scrive il PNG nella
  PROPRIA cwd, quindi collector e plotter hanno cwd diverse. Plotter: sempre la cartella di output
  (impostazione `git-activity.outputDir`; altrimenti workspace per il multi-repo, `globalStorageUri`
  per il singolo — mai il repo analizzato, dove il PNG finirebbe come file non tracciato). Collector
  singolo: cwd = il repo (analizza "il repo nella cartella corrente" e trova un eventuale
  `./git-activity-aliases.json` al suo interno); multi-repo: cwd = cartella di output (riceve percorsi
  assoluti). Il collector singolo va invocato con `json` ESPLICITO (default `text`, il plotter rifiuta
  testo): lo faceva `gitstat.sh`, bypassato dall'estensione — regressione già avvenuta una volta.
- **Localizzazione**: i messaggi a runtime usano `vscode.l10n.t()` con l'inglese come chiave; le
  traduzioni sono in `l10n/bundle.l10n.it.json` (chiave = stringa inglese esatta, vanno tenute
  allineate a mano). Titoli comandi/impostazioni stanno in `package.nls*.json`. Gli avvisi "Avviso:" dei
  collector restano in italiano (vengono dallo script bash, non dall'estensione).
- `package.json` dichiara `capabilities` (workspace non attendibili/virtuali non supportati): l'estensione
  esegue script bash/Python sui repo del workspace. `images/icon.png` è un segnaposto e l'unico PNG
  tracciato (eccezione in `.gitignore`, che altrimenti esclude `*.png`).
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
- **README bilingue**: `README.md` (inglese, pagina di GitHub/Marketplace) e `README.it.md` (italiano, la
  fonte originale) esistono sia nella root sia in `vscode-extension/`, con la stessa struttura e lo
  stesso ordine di intestazioni — vanno aggiornati entrambi. I rimandi a sezioni per nome (qui, in
  `find_generated_candidates.sh`, in `extension.ts`) usano i titoli italiani, quindi puntano a
  `README.it.md`. Gli screenshot in `docs/images/` sono generati da repository SINTETICI (autori
  fittizi), mai da repository reali: non sostituirli con grafici di dati veri.
- Il formato JSON di output è un contratto tra bash e python: cambiare le chiavi in un collector richiede
  aggiornare il plotter corrispondente. **Attenzione in fase di test**: se esistono copie in
  `/usr/local/bin`, il `PATH` le trova prima del working tree, e i wrapper `gitstats`/`gitstats-multi`
  risolvono collector e plotter dal `PATH` — quindi eseguono le copie, non le modifiche appena fatte.
  Verificare con `command -v plot_git.py`.
- I messaggi di successo dei plotter (`"Grafico generato con successo: ..."` /
  `"Report multi-progetto ... generato con successo: ..."`) sono intercettati via regex
  dall'estensione VS Code: non cambiarli senza aggiornare `vscode-extension/src/extension.ts`.
- Prima di modificare le metriche, leggere le sezioni "Metriche Calcolate" e "Interpretazione dei Dati"
  del README (italiano: `README.it.md`): le proprietà della formula (additiva, cap per giorno, cancellazioni pesate) sono
  correzioni di difetti misurati, non preferenze estetiche.
