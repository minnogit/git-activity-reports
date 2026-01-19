# Git Activity Reports

## Descrizione

Questa estensione per Visual Studio Code genera report visivi sull'attività Git dei tuoi progetti. Permette di visualizzare grafici di commit, contributi e statistiche in base a date personalizzabili, utilizzando script bash per l'analisi.

## Funzionalità

- **Analizza Progetto Corrente**: Genera un grafico di attività per il progetto attualmente aperto in VSCode.
- **Analizza Tutto il Workspace**: Supporta l'analisi multi-repository per progetti complessi.
- **Configurazione Personalizzata**: Imposta date di inizio e fine per l'analisi tramite le impostazioni di VSCode.
- **Visualizzazione Integrata**: I grafici vengono mostrati direttamente in un Webview all'interno di VSCode.

## Installazione

### Prerequisiti

- [Visual Studio Code](https://code.visualstudio.com/) versione 1.80.0 o superiore.
- [Node.js](https://nodejs.org/) per la compilazione (se stai sviluppando).
- Strumenti Git installati sul sistema.
- Script bash (`gitstat.sh` e `gitstat-multi.sh`) posizionati nella directory genitore dell'estensione (vedi sezione Sviluppo).

### Installazione dall'Estensione Compilata

1. **Compila l'Estensione** (se non l'hai già fatto):
   - Nella root del progetto, esegui:

     ```bash
     npm install
     npm run compile
     ```

2. **Impacchetta l'Estensione**:
   - Installa `vsce` se non l'hai già:

     ```bash
     npm install -g vsce
     ```

   - Crea il pacchetto `.vsix`:

     ```bash
     vsce package
     ```

     Questo genera un file come `git-activity-reports-0.1.0.vsix`.

3. **Installa in VSCode**:
   - Apri VSCode.
   - Vai su Extensions (Ctrl+Shift+X).
   - Clicca sull'icona ingranaggio > "Install from VSIX...".
   - Seleziona il file `.vsix` creato.
   - Riavvia VSCode.

   Alternativa da terminale:

   ```bash
   code --install-extension percorso/del/file.vsix
   ```

### Installazione dal Marketplace (se pubblicata)

Se l'estensione è pubblicata su VSCode Marketplace, cercala come "Git Activity Reports" e installala direttamente dalle Extensions.

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

## Sviluppo

### Struttura del Progetto

- `src/extension.ts`: Codice principale dell'estensione in TypeScript.
- `package.json`: Metadati e configurazione dell'estensione.
- `out/`: File JavaScript compilati (generati da TypeScript).
- Script bash: `gitstat.sh` e `gitstat-multi.sh` (devono essere nella directory genitore dell'estensione per il funzionamento).

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
