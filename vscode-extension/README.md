# Git Activity Reports

## Descrizione

Questa estensione per Visual Studio Code genera report visivi sull'attività Git dei tuoi progetti. Permette di visualizzare grafici di commit, contributi e statistiche in base a date personalizzabili, utilizzando script bash per l'analisi.

## Funzionalità

- **Analizza Progetto Corrente**: Genera un grafico di attività per il progetto attualmente aperto in VSCode.
- **Analizza Tutto il Workspace**: Supporta l'analisi multi-repository per progetti complessi.
- **Configurazione Personalizzata**: Imposta date di inizio e fine per l'analisi tramite le impostazioni di VSCode.
- **Visualizzazione Integrata**: I grafici vengono mostrati direttamente in un Webview all'interno di VSCode.

## Installazione

L'estensione non contiene la logica di analisi: al momento di eseguire un comando invoca
gli script bash/Python del repository come processo figlio. Non basta installare
l'estensione da sola — serve anche che questi script siano raggiungibili, in uno dei due
modi descritti sotto. Il codice li cerca in quest'ordine (`resolveRunner` in
`src/extension.ts`): prima accanto alla cartella dell'estensione (modalità sviluppo),
poi `gitstats`/`gitstats-multi` nel `PATH` (modalità installata via pacchetto).

### Prerequisiti (in entrambi i casi)

- [Visual Studio Code](https://code.visualstudio.com/) versione 1.80.0 o superiore.
- Git installato sul sistema.
- **Python 3 con `pandas` e `matplotlib`** — i comandi `gitstat(-multi).sh`/
  `gitstats(-multi)` sono una pipe verso `plot_git.py`/`plot_multiproject.py`: senza
  queste dipendenze la generazione del grafico fallisce anche se il resto funziona.
- [Node.js](https://nodejs.org/) solo se compili l'estensione da sorgente.

### Opzione A — Pacchetto CLI installato sul sistema + estensione da VSIX

Questa è l'opzione per un utilizzo "normale" (non da sviluppatore dell'estensione):

1. Installa gli script sul sistema con il pacchetto `.deb` del repository principale
   (workflow `.github/workflows/build-deb.yml`, si attiva sui tag `v*`), oppure copiando
   a mano `git_stats_collector.sh`, `git_multiproject_stats_collector.sh`, `plot_git.py`,
   `plot_multiproject.py` in una cartella nel `PATH` e rinominando `gitstat.sh`/
   `gitstat-multi.sh` in `gitstats`/`gitstats-multi` nella stessa cartella.
2. Verifica che siano raggiungibili: `command -v gitstats && command -v gitstats-multi`.
3. Impacchetta e installa l'estensione:

   ```bash
   cd vscode-extension
   npm install -g vsce   # se non l'hai già
   npm install
   npm run compile
   vsce package          # genera git-activity-reports-<versione>.vsix
   code --install-extension git-activity-reports-<versione>.vsix
   ```

   In alternativa, da VS Code: Extensions (Ctrl+Shift+X) → icona ingranaggio →
   "Install from VSIX..." → seleziona il file generato.

**Nota importante:** il file `.vsix` contiene SOLO i file dell'estensione stessa — `vsce
package` non può includere script che vivono nella cartella genitrice del repository, e
un'estensione installata da VSIX finisce in `~/.vscode/extensions/...`, scollegata dal
checkout. Per questo il passo 1 (script raggiungibili dal `PATH`) è necessario, non
opzionale: senza di esso l'estensione mostra l'errore "Script non trovato" al primo
utilizzo.

### Opzione B — Modalità sviluppo (esecuzione da dentro il checkout del repo)

Utile se stai modificando l'estensione o non vuoi installare nulla stabilmente:

1. Clona il repository (l'estensione deve restare nella sua posizione, `vscode-extension/`,
   accanto a `gitstat.sh`/`gitstat-multi.sh`).
2. `cd vscode-extension && npm install && npm run compile`.
3. Premi `F5` in VS Code: si apre una finestra "Extension Development Host" con
   l'estensione già attiva, che userà gli script del checkout senza bisogno del `PATH`.

### Marketplace

L'estensione non è pubblicata su VS Code Marketplace.

## Uso

1. Apri un progetto o workspace Git in VSCode.
2. Premi `Ctrl+Shift+P` per aprire la Command Palette.
3. Cerca e seleziona:
   - **Git Activity: Analizza Progetto Corrente** per analizzare il progetto singolo.
   - **Git Activity: Analizza Tutto il Workspace** per analizzare multi-repository.
4. L'estensione mostrerà una barra di progresso durante l'elaborazione.
5. Una volta completato, si aprirà un pannello Webview con il grafico PNG generato.

### Configurazione

Puoi personalizzare le date di analisi nelle impostazioni di VSCode:

- Vai su File > Preferences > Settings.
- Cerca "Git Activity".
- Modifica:
  - `Start Date`: Data di inizio (es. "2023-01-01" o "30 days ago").
  - `End Date`: Data di fine (es. "now" o "2023-12-31").

Il valore può essere sia una data assoluta (`YYYY-MM-DD`) sia un'espressione relativa —
qualunque cosa capisca `date -d` (GNU date): "yesterday", "2 weeks ago", "last monday",
ecc. L'estensione la risolve in una data assoluta prima di ogni analisi, quindi rimane
sempre riferita al giorno in cui lanci il comando (i default "30 days ago"/"now" indicano
sempre l'ultimo mese, non una coppia di date fissa). Se il valore non è riconosciuto,
l'estensione mostra un errore invece di passarlo comunque agli script sottostanti.

## Sviluppo

### Struttura del Progetto

- `src/extension.ts`: Codice principale dell'estensione in TypeScript.
- `package.json`: Metadati e configurazione dell'estensione.
- `out/`: File JavaScript compilati (generati da TypeScript).
- Script bash: `gitstat.sh` e `gitstat-multi.sh`, nella directory genitore dell'estensione
  — usati in modalità sviluppo (vedi Opzione B sopra); in produzione si usa invece il
  fallback su `gitstats`/`gitstats-multi` nel `PATH` (`resolveRunner` in `extension.ts`).

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

[Specifica la licenza, es. MIT]

## Contatti

Per problemi o suggerimenti, contatta [michele-innocenti] o apri un issue nel repository.
