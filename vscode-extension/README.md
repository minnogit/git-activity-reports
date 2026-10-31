# Git Activity Reports

Genera da VS Code grafici e statistiche sull'attività Git (commit, righe modificate, giorni
attivi, autori) di un repository o di un intero workspace, a partire da un intervallo di date.

## Funzionalità

- **Analizza Progetto Corrente**: grafico di attività del repository in cui stai lavorando.
- **Analizza Tutto il Workspace (Multi-Repo)**: report comparativo di tutti i repository Git
  trovati nel workspace (fino a 3 livelli di profondità).
- **Intervallo di date configurabile**, anche relativo (`30 days ago`, `last monday`).
- **Grafico integrato** in un pannello, salvato come PNG; dalla notifica finale puoi
  salvarne una copia o mostrarlo nella cartella.
- Gli autori con più identità Git si raggruppano con `git-activity-aliases.json` (vedi il
  [README del progetto](../README.md)).

I numeri sono indicatori, non misure assolute: la lettura dei grafici è spiegata nel
[README del progetto](../README.md).

## Requisiti

- **Linux o macOS con bash e GNU `date`** (su macOS serve GNU coreutils: `date -d` di BSD non
  funziona). Windows nativo non è supportato: usa WSL.
- **Git** nel `PATH`.
- **Python 3 con `pandas` e `matplotlib`**: senza, il grafico non viene generato.
- VS Code 1.80 o superiore, con un **workspace attendibile** e su filesystem reale
  (l'estensione esegue script locali: non funziona in workspace virtuali).

## Installazione

L'estensione non contiene la logica di analisi: al momento di eseguire un comando invoca
direttamente il collector e il plotter (`git_stats_collector.sh`/`plot_git.py` o le loro
varianti multi-repo) come una pipe di due processi figli, MAI i wrapper `gitstat(-multi).sh`
— quelli restano solo per l'uso a riga di comando. Il codice risolve i loro percorsi in
questo ordine (`resolveScriptPaths` in `src/extension.ts`):

1. `bundled/` dentro l'estensione stessa — popolata da `npm run copy-bundled` durante
   `vscode:prepublish` e quindi già presente in ogni `.vsix` impacchettato: è ciò che rende
   un'installazione da VSIX/Marketplace autosufficiente, senza bisogno del pacchetto `.deb`.
2. La cartella genitrice di `vscode-extension/` (il checkout del repo) — modalità sviluppo,
   quando l'estensione gira da lì senza che `copy-bundled` sia mai stato eseguito.
3. Gli stessi nomi di script nel `PATH` — come installati dal pacchetto `.deb`, per chi ha
   installato quello ma un `.vsix` non ricompilato con gli script più recenti.

### Prerequisiti (in tutti i casi)

- [Visual Studio Code](https://code.visualstudio.com/) versione 1.80.0 o superiore.
- Git installato sul sistema.
- **Python 3 con `pandas` e `matplotlib`** — la pipe verso `plot_git.py`/
  `plot_multiproject.py` fallisce senza queste dipendenze anche se il resto funziona.
- [Node.js](https://nodejs.org/) solo se compili l'estensione da sorgente.

### Opzione A — Installazione da VSIX (autosufficiente)

Questa è l'opzione per un utilizzo "normale" (non da sviluppatore dell'estensione): il
`.vsix` include già gli script necessari (`bundled/`, vedi sopra), non serve installare
nient'altro sul sistema oltre a Python e le sue librerie.

```bash
cd vscode-extension
npm install -g vsce   # se non l'hai già
npm install
vsce package          # esegue copy-bundled + compile, genera git-activity-reports-<versione>.vsix
code --install-extension git-activity-reports-<versione>.vsix
```

In alternativa, da VS Code: Extensions (Ctrl+Shift+X) → icona ingranaggio →
"Install from VSIX..." → seleziona il file generato.

Chi preferisce comunque gli strumenti da riga di comando (`gitstats`/`gitstats-multi`) può
installare anche il pacchetto `.deb` del repository principale (workflow
`.github/workflows/build-deb.yml`) — l'estensione non ne ha più bisogno, ma resta un
fallback valido (punto 3 sopra) se un giorno un `.vsix` più vecchio non avesse ancora gli
script più recenti in `bundled/`.

### Opzione B — Modalità sviluppo (esecuzione da dentro il checkout del repo)

Utile se stai modificando l'estensione o non vuoi installare nulla stabilmente:

1. Clona il repository (l'estensione deve restare nella sua posizione, `vscode-extension/`,
   accanto a `git_stats_collector.sh`/`git_multiproject_stats_collector.sh`/`plot_git.py`/
   `plot_multiproject.py`).
2. `cd vscode-extension && npm install && npm run compile`.
3. Premi `F5` in VS Code: si apre una finestra "Extension Development Host" con
   l'estensione già attiva, che userà gli script del checkout (punto 2 della risoluzione
   sopra) senza bisogno di `bundled/` né del `PATH`.

### Marketplace

L'estensione non è (ancora) pubblicata su VS Code Marketplace.

## Uso

1. Apri un progetto o workspace Git in VSCode.
2. Premi `Ctrl+Shift+P` per aprire la Command Palette.
3. Cerca e seleziona:
   - **Git Activity: Analizza Progetto Corrente** per analizzare il progetto singolo.
   - **Git Activity: Analizza Tutto il Workspace (Multi-Repo)** per analizzare multi-repository.
4. L'estensione mostrerà una barra di progresso durante l'elaborazione.
5. Una volta completato, si aprirà un pannello con il grafico e una notifica col percorso del
   file, da cui puoi **salvarne una copia** o **mostrarlo nella cartella**.

I titoli dei comandi seguono la lingua di VS Code (inglese o italiano).

### Dove viene salvato il PNG

Il nome del file è sempre lo stesso a ogni analisi (`git_stats.png` per il singolo repo): una
nuova analisi sovrascrive la precedente, quindi salvane una copia se vuoi conservarla. La
cartella è, in ordine:

1. l'impostazione `git-activity.outputDir`, se valorizzata;
2. per il multi-repo, la prima cartella del workspace (di norma quella che contiene i repo);
3. per il singolo repo, la cartella di storage dell'estensione — non quella del repo, per
   non far comparire il PNG come file non tracciato in `git status`.

Il report multi-repo si chiama `git_activity_multi_project_report_<inizio>_<fine>.png`.

### Configurazione

Puoi personalizzare le date di analisi nelle impostazioni di VSCode:

- Vai su File > Preferences > Settings.
- Cerca "Git Activity".
- Modifica:
  - `Start Date`: Data di inizio (es. "2023-01-01" o "30 days ago").
  - `End Date`: Data di fine (es. "now" o "2023-12-31").
  - `Output Dir`: cartella del PNG generato (vuota = vedi sopra; supporta `~`).

Il valore può essere sia una data assoluta (`YYYY-MM-DD`) sia un'espressione relativa —
qualunque cosa capisca `date -d` (GNU date): "yesterday", "2 weeks ago", "last monday",
ecc. L'estensione la risolve in una data assoluta prima di ogni analisi, quindi rimane
sempre riferita al giorno in cui lanci il comando (i default "30 days ago"/"now" indicano
sempre l'ultimo mese, non una coppia di date fissa). Se il valore non è riconosciuto,
l'estensione mostra un errore invece di passarlo comunque agli script sottostanti.

## Sviluppo

### Struttura del Progetto

- `src/extension.ts`: Codice principale dell'estensione in TypeScript.
- `package.json`: Metadati e configurazione dell'estensione. Testi visibili all'utente in
  `package.nls.json` (inglese) e `package.nls.it.json`; messaggi a runtime in
  `l10n/bundle.l10n.it.json` (la chiave è la stringa inglese passata a `vscode.l10n.t`).
- `images/icon.png`: icona (128×128, segnaposto). `CHANGELOG.md`: modifiche per versione.
- `out/`: File JavaScript compilati (generati da TypeScript).
- `scripts/copy-bundled.js`: copia i 4 script collector/plotter dalla root del repo dentro
  `bundled/` (invocato da `npm run copy-bundled`, parte di `vscode:prepublish`) — non fa
  parte del pacchetto (`.vscodeignore`), è solo un passo di build.
- `bundled/`: script collector/plotter copiati da `copy-bundled.js`, inclusi nel `.vsix` —
  artefatto di build, non committato (vedi `.gitignore` nella root).
- Script bash nella directory genitrice dell'estensione (`git_stats_collector.sh`,
  `git_multiproject_stats_collector.sh`, `plot_git.py`, `plot_multiproject.py`) — usati in
  modalità sviluppo se `bundled/` non è ancora stata popolata (`resolveScriptPaths` in
  `extension.ts`, vedi "Installazione" sopra per l'ordine di risoluzione completo).

### Come Contribuire

1. Clona il repository.
2. Installa le dipendenze:

   ```bash
   npm install
   ```

3. Compila e testa in modalità debug (F5 in VSCode).
4. Modifica il codice in `src/extension.ts`.
5. Ricompila:

   ```bash
   npm run compile
   ```

6. Testa i cambiamenti.

### Script Disponibili

- `npm run compile`: Compila TypeScript.
- `npm run watch`: Compila automaticamente durante le modifiche.
- `npm run lint`: Controlla il codice con ESLint.
- `npm run test`: Esegue i test.

## Dipendenze

- `@types/vscode`: Tipi per l'API di VSCode.
- `@types/node`: Tipi per Node.js.
- `typescript`: Compilatore TypeScript.
- `eslint`: Linter per codice.

## Licenza

MIT, vedi [LICENSE](LICENSE).

## Contatti

Per problemi o suggerimenti, contatta [michele-innocenti] o apri un issue nel repository.
