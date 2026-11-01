import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';

// Messaggi in inglese come lingua sorgente, tradotti tramite l10n/bundle.l10n.<lingua>.json
// (vedi "l10n" in package.json): la chiave del bundle è la stringa inglese esatta.
const t = vscode.l10n.t;

export function activate(context: vscode.ExtensionContext) {
    console.log('L\'estensione "git-activity-reports" è attiva!');

    let disposableProject = vscode.commands.registerCommand('git-activity.analyzeProject', async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage(t('No workspace is open.'));
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
        } else {
            vscode.window.showErrorMessage(t('Could not find a Git repository in the current context.'));
        }
    });

    let disposableWorkspace = vscode.commands.registerCommand('git-activity.analyzeWorkspace', async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage(t('No workspace is open.'));
            return;
        }

        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: t('Searching for Git repositories in the workspace...'),
            cancellable: false
        }, async () => {
            const allRepos = findReposInWorkspace(workspaceFolders);

            if (allRepos.length === 0) {
                vscode.window.showErrorMessage(t('No Git repository found in the workspace.'));
                return;
            }

            if (allRepos.length === 1) {
                runAnalysis(context, [allRepos[0]]);
            } else {
                runAnalysis(context, allRepos);
            }
        });
    });

    // "Analizza il mio lavoro": stessi report degli altri due comandi, filtrati su una persona
    // (impostazione git-activity.author, altrimenti `git config user.email` del repo). Il
    // filtro lo applica il collector (vedi --author / 4° argomento posizionale): l'estensione
    // non conosce né alias né .mailmap, e passa l'identità così com'è.
    let disposableMine = vscode.commands.registerCommand('git-activity.analyzeMyWork', async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage(t('No workspace is open.'));
            return;
        }

        const allRepos = findReposInWorkspace(workspaceFolders);
        if (allRepos.length === 0) {
            vscode.window.showErrorMessage(t('No Git repository found in the workspace.'));
            return;
        }

        // Il repo "corrente" è quello del file aperto (o della prima cartella), come per
        // "Analizza Progetto Corrente"; se non si trova, il primo repo del workspace.
        const activeEditor = vscode.window.activeTextEditor;
        const startPath = activeEditor
            ? path.dirname(activeEditor.document.uri.fsPath)
            : workspaceFolders[0].uri.fsPath;
        const currentRepo = findClosestGitRepo(startPath) || allRepos[0];

        const author = await resolveAuthor(currentRepo);
        if (!author) {
            vscode.window.showErrorMessage(
                t('Could not determine your Git identity. Set "git-activity.author" in the settings, or run "git config user.email" in the repository.')
            );
            return;
        }

        let repos = [currentRepo];
        if (allRepos.length > 1) {
            const currentLabel = t('Current project');
            const workspaceLabel = t('Whole workspace ({0} repositories)', allRepos.length);
            const choice = await vscode.window.showQuickPick(
                [
                    { label: currentLabel, description: path.basename(currentRepo) },
                    { label: workspaceLabel },
                ],
                { placeHolder: t('Analyze the work of {0} on:', author) }
            );
            if (!choice) {
                return;
            }
            if (choice.label === workspaceLabel) {
                repos = allRepos;
            }
        }
        runAnalysis(context, repos, author);
    });

    context.subscriptions.push(disposableProject, disposableWorkspace, disposableMine);
}

// Repository Git trovati nelle cartelle del workspace (scansione fino a 3 livelli).
function findReposInWorkspace(folders: readonly vscode.WorkspaceFolder[]): string[] {
    const repos: string[] = [];
    for (const folder of folders) {
        repos.push(...findAllGitRepos(folder.uri.fsPath));
    }
    return repos;
}

// Identità di chi lancia "Analizza il mio lavoro": prima l'impostazione git-activity.author
// (nome o email), poi l'email di `git config user.email` nel repo (rispetta gli override
// locali). `execFile`, mai una shell: nessun problema di quoting. Stringa vuota se non c'è.
function resolveAuthor(repoPath: string): Promise<string> {
    const configured = (vscode.workspace.getConfiguration('git-activity').get<string>('author') || '').trim();
    if (configured) {
        return Promise.resolve(configured);
    }
    return new Promise((resolve) => {
        cp.execFile('git', ['config', 'user.email'], { cwd: repoPath }, (error, stdout) => {
            resolve(error ? '' : stdout.toString().trim());
        });
    });
}

function findClosestGitRepo(startPath: string): string | null {
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

function findAllGitRepos(basePath: string, maxDepth: number = 3, currentDepth: number = 0): string[] {
    const repos: string[] = [];
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
    } catch (e) {
        // Ignora errori di permessi ecc.
    }

    return repos;
}

// Verifica se un comando è risolvibile dal PATH (es. `git_stats_collector.sh`/`plot_git.py`
// installati dal pacchetto .deb in /usr/local/bin) senza invocare una shell.
function commandExistsOnPath(cmd: string): boolean {
    try {
        cp.execFileSync('which', [cmd], { stdio: 'ignore' });
        return true;
    } catch {
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
// progetto (vedi README.it.md, "Richiede GNU date"), quindi stessa semantica ovunque — un
// parser diverso in TypeScript rischierebbe di accettare/interpretare input in modo
// leggermente diverso da come li interpretano gli script bash a valle.
function resolveDate(value: string): string | null {
    try {
        const out = cp.execFileSync('date', ['-d', value, '+%Y-%m-%d'], { stdio: ['ignore', 'pipe', 'ignore'] });
        return out.toString().trim();
    } catch {
        return null;
    }
}

interface RunnableScript {
    cmd: string;       // interprete: 'bash' o 'python3'
    args: string[];    // [percorso script, ...argomenti]
}

interface ScriptPair {
    collector: RunnableScript;
    plotter: RunnableScript;
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
function resolveScriptPaths(context: vscode.ExtensionContext, isMulti: boolean): ScriptPair | null {
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
function runPipeline(collector: RunnableScript, plotter: RunnableScript, collectorCwd: string, plotterCwd: string):
    Promise<{ stdout: string; stderr: string }> {
    return new Promise((resolve, reject) => {
        const collectorArgs = [...collector.args];
        const plotterArgs = [...plotter.args];

        let p1: cp.ChildProcessWithoutNullStreams;
        let p2: cp.ChildProcessWithoutNullStreams;
        try {
            p1 = cp.spawn(collector.cmd, collectorArgs, { cwd: collectorCwd });
            // Lingua delle scritte nel grafico: quella dell'interfaccia di VS Code (italiano o,
            // per qualunque altra lingua, inglese). Senza, il plotter userebbe il locale del
            // sistema, che non è detto coincida con la lingua scelta in VS Code.
            const chartLang = vscode.env.language.toLowerCase().startsWith('it') ? 'it' : 'en';
            p2 = cp.spawn(plotter.cmd, plotterArgs, {
                cwd: plotterCwd,
                // Nome di variabile d'ambiente, non una proprietà TS: la regola camelCase non si applica.
                // eslint-disable-next-line @typescript-eslint/naming-convention
                env: { ...process.env, GIT_ACTIVITY_LANG: chartLang },
            });
        } catch (err) {
            reject(err as Error);
            return;
        }

        let stderrCollector = '';
        let stderrPlotter = '';
        let stdoutPlotter = '';
        let settled = false;

        const fail = (err: Error) => {
            if (settled) { return; }
            settled = true;
            reject(err);
        };

        // Se il plotter termina prima di aver letto tutto (es. dipendenze Python mancanti),
        // la scrittura su p2.stdin genera EPIPE: senza handler sarebbe un errore non gestito
        // nell'extension host. L'esito lo decide comunque p2 al 'close'.
        p2.stdin.on('error', () => { /* ignorato di proposito */ });
        p1.stdout.pipe(p2.stdin);
        p1.stderr.on('data', (d) => { stderrCollector += d.toString(); });
        p2.stderr.on('data', (d) => { stderrPlotter += d.toString(); });
        p2.stdout.on('data', (d) => { stdoutPlotter += d.toString(); });

        p1.on('error', (err) => fail(new Error(t('Could not start {0}: {1}', collector.cmd, err.message))));
        p2.on('error', (err) => fail(new Error(t('Could not start {0}: {1}', plotter.cmd, err.message))));

        // Se il collector fallisce, p2 riceve EPIPE/stdin chiuso e uscirà anch'esso con
        // errore: è p2 (l'ultimo anello della pipe, come per una pipe di shell) a decidere
        // esito e messaggio, con lo stderr del collector anteposto per non perderlo.
        // Si attende la chiusura di ENTRAMBI i processi: l'ordine dei due 'close' non è
        // garantito, e l'esito dipende da tutti e due i codici di uscita.
        let collectorCode: number | null | undefined;
        let plotterCode: number | null | undefined;
        const finish = () => {
            if (collectorCode === undefined || plotterCode === undefined || settled) { return; }
            settled = true;
            if (plotterCode !== 0 || collectorCode !== 0) {
                reject(new Error(
                    stderrCollector + stderrPlotter ||
                    t('Process exited with code {0}', String(plotterCode !== 0 ? plotterCode : collectorCode))
                ));
                return;
            }
            resolve({ stdout: stdoutPlotter, stderr: stderrCollector + stderrPlotter });
        };
        p1.on('close', (code) => { collectorCode = code; finish(); });
        p2.on('close', (code) => { plotterCode = code; finish(); });
    });
}

async function runAnalysis(context: vscode.ExtensionContext, paths: string[], author?: string) {
    const config = vscode.workspace.getConfiguration('git-activity');
    const startDateRaw = config.get<string>('startDate') || '30 days ago';
    const endDateRaw = config.get<string>('endDate') || 'now';

    const startDate = resolveDate(startDateRaw);
    const endDate = resolveDate(endDateRaw);
    if (!startDate || !endDate) {
        const invalid = !startDate ? startDateRaw : endDateRaw;
        vscode.window.showErrorMessage(
            t('Invalid date in settings: "{0}". Use a format that "date -d" understands (e.g. "2025-11-01", "30 days ago", "now").', invalid)
        );
        return;
    }

    vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: paths.length > 1 ? t('Analyzing {0} repositories...', paths.length) : t('Generating Git activity chart...'),
        cancellable: false
    }, async (progress) => {
        const isMulti = paths.length > 1;
        const scripts = resolveScriptPaths(context, isMulti);

        if (!scripts) {
            const collectorName = isMulti ? 'git_multiproject_stats_collector.sh' : 'git_stats_collector.sh';
            const plotterName = isMulti ? 'plot_multiproject.py' : 'plot_git.py';
            vscode.window.showErrorMessage(
                t('Scripts not found: neither in bundled/ (.vsix package), next to the extension (development mode), nor "{0}"/"{1}" on the PATH (.deb package). See the Requirements in the README.', collectorName, plotterName)
            );
            return;
        }

        // Il collector singolo ha 'text' come formato di default, ma il plotter legge solo
        // JSON: va chiesto esplicitamente (lo faceva gitstat.sh, che ora non è più in mezzo).
        // Il multi-repo produce sempre JSON, senza argomento di formato.
        let outputDir: string;
        try {
            outputDir = resolveOutputDir(context, isMulti);
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            vscode.window.showErrorMessage(t('Execution error: {0}', message));
            return;
        }

        // Con un autore: il multi-repo lo riceve come opzione PRIMA delle date (--author), il
        // singolo come 4° argomento posizionale dopo 'json' (vedi gli help dei collector).
        const collectorArgs = isMulti
            ? [...scripts.collector.args, ...(author ? ['--author', author] : []), startDate, endDate, ...paths]
            : [...scripts.collector.args, startDate, endDate, 'json', ...(author ? [author] : [])];

        try {
            const { stdout, stderr } = await runPipeline(
                { cmd: scripts.collector.cmd, args: collectorArgs },
                scripts.plotter,
                // Il collector singolo analizza "il repo nella cartella corrente": cwd = repo (e
                // così trova anche un ./git-activity-aliases.json al suo interno). Il multi-repo
                // riceve percorsi assoluti: cwd = cartella di output (workspace).
                isMulti ? outputDir : paths[0],
                // Il plotter scrive il PNG nella propria cwd: mai dentro un repo analizzato.
                outputDir
            );

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
                const pngPath = path.isAbsolute(pngName) ? pngName : path.join(outputDir, pngName);
                showImageInWebview(context, pngPath);
                notifySavedReport(pngPath);
            } else {
                vscode.window.showInformationMessage(t('Analysis completed, but the image file was not found in the log.'));
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            vscode.window.showErrorMessage(t('Execution error: {0}', message));
        }
    });
}

// Cartella dove il plotter scrive il PNG. In ordine: impostazione `git-activity.outputDir`
// (supporta `~`); altrimenti, per il multi-repo, la prima cartella del workspace (di norma
// quella che CONTIENE i repo, non un repo scelto a caso); per il singolo repo la cartella di
// storage dell'estensione, perché la cartella del workspace coinciderebbe col repo stesso e
// il PNG comparirebbe come file non tracciato in `git status`.
function resolveOutputDir(context: vscode.ExtensionContext, isMulti: boolean): string {
    const configured = (vscode.workspace.getConfiguration('git-activity').get<string>('outputDir') || '').trim();
    let dir: string;
    if (configured) {
        dir = configured.startsWith('~') ? path.join(os.homedir(), configured.slice(1)) : configured;
    } else if (isMulti && vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
        dir = vscode.workspace.workspaceFolders[0].uri.fsPath;
    } else {
        dir = path.join(context.globalStorageUri.fsPath, 'reports');
    }
    fs.mkdirSync(dir, { recursive: true });
    return dir;
}

// Il PNG può stare in una cartella nascosta (storage dell'estensione): dice dove e permette di
// salvarne una copia con un nome a scelta (il nome del file è sempre lo stesso a ogni run).
function notifySavedReport(pngPath: string) {
    const saveAs = t('Save as…');
    const reveal = t('Show in folder');
    vscode.window.showInformationMessage(t('Report saved to {0}', pngPath), saveAs, reveal).then(async (choice) => {
        if (choice === saveAs) {
            const target = await vscode.window.showSaveDialog({
                defaultUri: vscode.Uri.file(path.join(os.homedir(), path.basename(pngPath))),
                filters: { [t('PNG image')]: ['png'] }
            });
            if (target) {
                fs.copyFileSync(pngPath, target.fsPath);
            }
        } else if (choice === reveal) {
            vscode.commands.executeCommand('revealFileInOS', vscode.Uri.file(pngPath));
        }
    });
}

function showImageInWebview(context: vscode.ExtensionContext, imagePath: string) {
    const panel = vscode.window.createWebviewPanel(
        'gitActivityReport',
        'Git Activity Report',
        vscode.ViewColumn.One,
        {
            // Nessuno script nell'HTML sotto: enableScripts non serve, quindi non lo si
            // concede (permesso non necessario è comunque un permesso da giustificare).
            localResourceRoots: [vscode.Uri.file(path.dirname(imagePath))]
        }
    );

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
        <html lang="en">
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

export function deactivate() {}
