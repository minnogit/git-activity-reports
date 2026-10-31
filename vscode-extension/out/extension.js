"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const cp = __importStar(require("child_process"));
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
function activate(context) {
    console.log('L\'estensione "git-activity-reports" è attiva!');
    let disposableProject = vscode.commands.registerCommand('git-activity.analyzeProject', async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('Nessun workspace aperto.');
            return;
        }
        // Tenta di trovare il repo git nella cartella corrente o genitrice
        const activeEditor = vscode.window.activeTextEditor;
        let startPath = workspaceFolders[0].uri.fsPath;
        if (activeEditor) {
            startPath = path.dirname(activeEditor.document.uri.fsPath);
        }
        const repoPath = findClosestGitRepo(startPath);
        if (repoPath) {
            runAnalysis(context, [repoPath]);
        }
        else {
            vscode.window.showErrorMessage('Non è stato possibile trovare un repository Git nel contesto attuale.');
        }
    });
    let disposableWorkspace = vscode.commands.registerCommand('git-activity.analyzeWorkspace', async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('Nessun workspace aperto.');
            return;
        }
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Ricerca repository Git nel workspace...",
            cancellable: false
        }, async () => {
            const allRepos = [];
            for (const folder of workspaceFolders) {
                const reposInFolder = findAllGitRepos(folder.uri.fsPath);
                allRepos.push(...reposInFolder);
            }
            if (allRepos.length === 0) {
                vscode.window.showErrorMessage('Nessun repository Git trovato nel workspace.');
                return;
            }
            if (allRepos.length === 1) {
                runAnalysis(context, [allRepos[0]]);
            }
            else {
                runAnalysis(context, allRepos);
            }
        });
    });
    context.subscriptions.push(disposableProject, disposableWorkspace);
}
function findClosestGitRepo(startPath) {
    let current = startPath;
    const root = path.parse(current).root;
    while (current !== root) {
        if (fs.existsSync(path.join(current, '.git'))) {
            return current;
        }
        current = path.dirname(current);
    }
    // Controlla se ci sono sottocartelle che sono repo (se siamo nella root di una cartella contenitore)
    const subRepos = findAllGitRepos(startPath, 1); // Cerca solo al primo livello di profondità
    return subRepos.length > 0 ? subRepos[0] : null;
}
function findAllGitRepos(basePath, maxDepth = 3, currentDepth = 0) {
    const repos = [];
    if (currentDepth > maxDepth) {
        return repos;
    }
    try {
        if (fs.existsSync(path.join(basePath, '.git'))) {
            repos.push(basePath);
            return repos; // Se questa è una root git, non cerchiamo dentro (solitamente non ci sono repo annidati)
        }
        const files = fs.readdirSync(basePath, { withFileTypes: true });
        for (const file of files) {
            if (file.isDirectory() && file.name !== 'node_modules' && !file.name.startsWith('.')) {
                repos.push(...findAllGitRepos(path.join(basePath, file.name), maxDepth, currentDepth + 1));
            }
        }
    }
    catch (e) {
        // Ignora errori di permessi ecc.
    }
    return repos;
}
// Verifica se un comando è risolvibile dal PATH (es. `git_stats_collector.sh`/`plot_git.py`
// installati dal pacchetto .deb in /usr/local/bin) senza invocare una shell.
function commandExistsOnPath(cmd) {
    try {
        cp.execFileSync('which', [cmd], { stdio: 'ignore' });
        return true;
    }
    catch {
        return false;
    }
}
// Risolve una data in formato libero (qualunque stringa che GNU `date -d` capisca:
// "2025-11-01", "30 days ago", "now", "yesterday", ...) in YYYY-MM-DD. Necessario perché
// git_stats_collector.sh valida le date con un regex rigido YYYY-MM-DD (git non sa
// interpretare date relative), mentre la configurazione di questa estensione — e i suoi
// stessi valori di default, "30 days ago"/"now" — promette di accettare anche forme
// relative: senza questa risoluzione la configurazione di fabbrica fallisce SEMPRE al
// primo utilizzo (verificato). Usa `date -d`, non un parser di date scritto a mano in
// JS/TS: è la stessa dipendenza (GNU coreutils) già richiesta da tutto il resto del
// progetto (vedi README, "Richiede GNU date"), quindi stessa semantica ovunque — un
// parser diverso in TypeScript rischierebbe di accettare/interpretare input in modo
// leggermente diverso da come li interpretano gli script bash a valle.
function resolveDate(value) {
    try {
        const out = cp.execFileSync('date', ['-d', value, '+%Y-%m-%d'], { stdio: ['ignore', 'pipe', 'ignore'] });
        return out.toString().trim();
    }
    catch {
        return null;
    }
}
// Risolve i percorsi di collector e plotter (mai i wrapper gitstat(-multi).sh: l'estensione
// costruisce la pipe da sé in runPipeline, così evita un secondo processo di shell in mezzo
// e i suoi stessi problemi di risoluzione — vedi sotto) in tre modi, in ordine di preferenza:
//   1. Bundled: vscode-extension/bundled/, popolata da "npm run copy-bundled" durante
//      "vscode:prepublish" (scripts/copy-bundled.js) — è ciò che finisce nel .vsix, quindi è
//      l'unico modo che funziona per un'installazione da Marketplace/VSIX senza richiedere
//      anche il pacchetto .deb sul sistema.
//   2. Modalità sviluppo: gli script nella cartella genitrice di vscode-extension/ (il
//      checkout del repo, quando l'estensione gira da lì via F5 e "npm run copy-bundled" non
//      è ancora stato eseguito).
//   3. PATH: gli stessi nomi installati dal pacchetto .deb in /usr/local/bin
//      (.github/workflows/build-deb.yml) — ultimo fallback per chi ha installato il .deb
//      ma non il .vsix ricompilato con gli script più recenti.
function resolveScriptPaths(context, isMulti) {
    const collectorName = isMulti ? 'git_multiproject_stats_collector.sh' : 'git_stats_collector.sh';
    const plotterName = isMulti ? 'plot_multiproject.py' : 'plot_git.py';
    const candidateDirs = [
        path.join(context.extensionPath, 'bundled'),
        path.join(context.extensionPath, '..'),
    ];
    for (const dir of candidateDirs) {
        const collectorPath = path.join(dir, collectorName);
        const plotterPath = path.join(dir, plotterName);
        if (fs.existsSync(collectorPath) && fs.existsSync(plotterPath)) {
            return {
                collector: { cmd: 'bash', args: [collectorPath] },
                plotter: { cmd: 'python3', args: [plotterPath] },
            };
        }
    }
    if (commandExistsOnPath(collectorName) && commandExistsOnPath(plotterName)) {
        return {
            collector: { cmd: collectorName, args: [] },
            plotter: { cmd: plotterName, args: [] },
        };
    }
    return null;
}
// Esegue collector e plotter come farebbe una pipe di shell (`collector ... | plotter`), ma
// collegando i processi direttamente via stdout/stdin invece di invocare bash -c: evita di
// dover quotare argomenti (percorsi, date, nomi progetto) dentro una stringa di shell.
// stderr di entrambi i processi (mai reindirizzato in una pipe di shell reale) è combinato
// nell'ordine collector-poi-plotter, per restare compatibile con l'unico consumatore dei
// messaggi "Avviso:" più sotto in runAnalysis.
function runPipeline(collector, plotter, cwd) {
    return new Promise((resolve, reject) => {
        const collectorArgs = [...collector.args];
        const plotterArgs = [...plotter.args];
        let p1;
        let p2;
        try {
            p1 = cp.spawn(collector.cmd, collectorArgs, { cwd });
            p2 = cp.spawn(plotter.cmd, plotterArgs, { cwd });
        }
        catch (err) {
            reject(err);
            return;
        }
        let stderrCollector = '';
        let stderrPlotter = '';
        let stdoutPlotter = '';
        let settled = false;
        const fail = (err) => {
            if (settled) {
                return;
            }
            settled = true;
            reject(err);
        };
        // Se il plotter termina prima di aver letto tutto (es. dipendenze Python mancanti),
        // la scrittura su p2.stdin genera EPIPE: senza handler sarebbe un errore non gestito
        // nell'extension host. L'esito lo decide comunque p2 al 'close'.
        p2.stdin.on('error', () => { });
        p1.stdout.pipe(p2.stdin);
        p1.stderr.on('data', (d) => { stderrCollector += d.toString(); });
        p2.stderr.on('data', (d) => { stderrPlotter += d.toString(); });
        p2.stdout.on('data', (d) => { stdoutPlotter += d.toString(); });
        p1.on('error', (err) => fail(new Error(`Impossibile avviare ${collector.cmd}: ${err.message}`)));
        p2.on('error', (err) => fail(new Error(`Impossibile avviare ${plotter.cmd}: ${err.message}`)));
        // Se il collector fallisce, p2 riceve EPIPE/stdin chiuso e uscirà anch'esso con
        // errore: è p2 (l'ultimo anello della pipe, come per una pipe di shell) a decidere
        // esito e messaggio, con lo stderr del collector anteposto per non perderlo.
        // Si attende la chiusura di ENTRAMBI i processi: l'ordine dei due 'close' non è
        // garantito, e l'esito dipende da tutti e due i codici di uscita.
        let collectorCode;
        let plotterCode;
        const finish = () => {
            if (collectorCode === undefined || plotterCode === undefined || settled) {
                return;
            }
            settled = true;
            if (plotterCode !== 0 || collectorCode !== 0) {
                reject(new Error(stderrCollector + stderrPlotter ||
                    `Processo terminato con codice ${plotterCode !== 0 ? plotterCode : collectorCode}`));
                return;
            }
            resolve({ stdout: stdoutPlotter, stderr: stderrCollector + stderrPlotter });
        };
        p1.on('close', (code) => { collectorCode = code; finish(); });
        p2.on('close', (code) => { plotterCode = code; finish(); });
    });
}
async function runAnalysis(context, paths) {
    const config = vscode.workspace.getConfiguration('git-activity');
    const startDateRaw = config.get('startDate') || '30 days ago';
    const endDateRaw = config.get('endDate') || 'now';
    const startDate = resolveDate(startDateRaw);
    const endDate = resolveDate(endDateRaw);
    if (!startDate || !endDate) {
        const invalid = !startDate ? startDateRaw : endDateRaw;
        vscode.window.showErrorMessage(`Data non valida nelle impostazioni: "${invalid}". Usa un formato che ` +
            `"date -d" riconosce (es. "2025-11-01", "30 days ago", "now").`);
        return;
    }
    vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: paths.length > 1 ? `Analisi di ${paths.length} repository...` : "Generazione grafico attività Git...",
        cancellable: false
    }, async (progress) => {
        const isMulti = paths.length > 1;
        const scripts = resolveScriptPaths(context, isMulti);
        if (!scripts) {
            const collectorName = isMulti ? 'git_multiproject_stats_collector.sh' : 'git_stats_collector.sh';
            const plotterName = isMulti ? 'plot_multiproject.py' : 'plot_git.py';
            vscode.window.showErrorMessage(`Script non trovati: né in bundled/ (pacchetto .vsix), né accanto all'estensione ` +
                `(modalità sviluppo), né "${collectorName}"/"${plotterName}" nel PATH (pacchetto .deb). ` +
                `Vedi i Prerequisiti nel README.`);
            return;
        }
        const collectorArgs = isMulti
            ? [...scripts.collector.args, startDate, endDate, ...paths]
            : [...scripts.collector.args, startDate, endDate];
        try {
            const { stdout, stderr } = await runPipeline({ cmd: scripts.collector.cmd, args: collectorArgs }, scripts.plotter, paths[0]);
            // Anche in caso di successo, stderr può contenere avvisi utili (es. "nessun
            // commit trovato prima di...", ownership non calcolata, autore non trovato).
            // stderr non è mai vuoto su una run normale (skip fetch, alias caricati, i
            // warning di libreria di Python) — mostrare tutto ad ogni run sarebbe rumore
            // che nasconde l'avviso vero: i collector prefissano SEMPRE con "Avviso:" ciò
            // che è pensato per l'utente (vedi git_stats_collector.sh e
            // git_multiproject_stats_collector.sh), quindi si filtra su quel prefisso.
            const avvisi = stderr
                .split('\n')
                .map(line => line.trim())
                .filter(line => line.startsWith('Avviso:'));
            if (avvisi.length > 0) {
                vscode.window.showWarningMessage(avvisi.join(' '));
            }
            const outputMatch = stdout.match(/Grafico generato con successo: (.*\.png)/) ||
                stdout.match(/Report multi-progetto .* generato con successo: (.*\.png)/);
            if (outputMatch && outputMatch[1]) {
                const pngName = outputMatch[1].trim();
                const pngPath = path.isAbsolute(pngName) ? pngName : path.join(paths[0], pngName);
                showImageInWebview(context, pngPath);
            }
            else {
                vscode.window.showInformationMessage('Analisi completata, ma il file immagine non è stato individuato nel log.');
            }
        }
        catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            vscode.window.showErrorMessage(`Errore nell'esecuzione: ${message}`);
        }
    });
}
function showImageInWebview(context, imagePath) {
    const panel = vscode.window.createWebviewPanel('gitActivityReport', 'Git Activity Report', vscode.ViewColumn.One, {
        // Nessuno script nell'HTML sotto: enableScripts non serve, quindi non lo si
        // concede (permesso non necessario è comunque un permesso da giustificare).
        localResourceRoots: [vscode.Uri.file(path.dirname(imagePath))]
    });
    // Cache-busting: il collector/plotter scrive sempre lo stesso nome file (es.
    // git_stats.png) — è un contratto usato anche da riga di comando, non va cambiato
    // solo per questa estensione. Ma un URI identico a run precedenti rischia di essere
    // servito dalla cache della webview (Chromium) anche se il contenuto del file è
    // cambiato: una query string con il timestamp di generazione rende ogni run un URI
    // diverso, senza toccare il file né il suo nome.
    const imageUri = panel.webview.asWebviewUri(vscode.Uri.file(imagePath))
        .with({ query: `t=${Date.now()}` });
    // CSP raccomandata da VS Code per ogni webview: default-src 'none' nega tutto per
    // default, poi si riapre solo ciò che serve — qui solo l'immagine (dal resource root
    // sopra) e lo <style> inline già presente nell'HTML. Nessun script-src: non ce n'è
    // bisogno, enableScripts non è stato concesso.
    const csp = `default-src 'none'; img-src ${panel.webview.cspSource}; style-src 'unsafe-inline';`;
    panel.webview.html = `
        <!DOCTYPE html>
        <html lang="it">
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="Content-Security-Policy" content="${csp}">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Git Activity Report</title>
            <style>
                body { display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #1e1e1e; margin: 0; }
                img { max-width: 95%; max-height: 95%; box-shadow: 0 0 20px rgba(0,0,0,0.5); border-radius: 8px; }
            </style>
        </head>
        <body>
            <img src="${imageUri}" alt="Git Activity Graph">
        </body>
        </html>
    `;
}
function deactivate() { }
//# sourceMappingURL=extension.js.map