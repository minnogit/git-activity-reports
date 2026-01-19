import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

export function activate(context: vscode.ExtensionContext) {
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
        } else {
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
            const allRepos: string[] = [];
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
            } else {
                runAnalysis(context, allRepos);
            }
        });
    });

    context.subscriptions.push(disposableProject, disposableWorkspace);
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
    if (currentDepth > maxDepth) return repos;

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

async function runAnalysis(context: vscode.ExtensionContext, paths: string[]) {
    const config = vscode.workspace.getConfiguration('git-activity');
    const startDate = config.get<string>('startDate') || '30 days ago';
    const endDate = config.get<string>('endDate') || 'now';

    vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: paths.length > 1 ? `Analisi di ${paths.length} repository...` : "Generazione grafico attività Git...",
        cancellable: false
    }, async (progress) => {
        return new Promise<void>((resolve, reject) => {
            const isMulti = paths.length > 1;
            const scriptName = isMulti ? 'gitstat-multi.sh' : 'gitstat.sh';
            const scriptPath = path.join(context.extensionPath, '..', scriptName);

            if (!fs.existsSync(scriptPath)) {
                vscode.window.showErrorMessage(`Script non trovato: ${scriptPath}`);
                resolve();
                return;
            }

            const args = isMulti ? [startDate, endDate, ...paths] : [startDate, endDate];
            
            cp.execFile('bash', [scriptPath, ...args], { cwd: paths[0] }, (error, stdout, stderr) => {
                if (error) {
                    vscode.window.showErrorMessage(`Errore nell'esecuzione: ${stderr || error.message}`);
                    resolve();
                    return;
                }

                const outputMatch = stdout.match(/Grafico generato con successo: (.*\.png)/) || 
                                   stdout.match(/Report multi-progetto .* generato con successo: (.*\.png)/);
                
                if (outputMatch && outputMatch[1]) {
                    const pngName = outputMatch[1].trim();
                    const pngPath = path.isAbsolute(pngName) ? pngName : path.join(paths[0], pngName);
                    showImageInWebview(context, pngPath);
                } else {
                    vscode.window.showInformationMessage('Analisi completata, ma il file immagine non è stato individuato nel log.');
                }
                resolve();
            });
        });
    });
}

function showImageInWebview(context: vscode.ExtensionContext, imagePath: string) {
    const panel = vscode.window.createWebviewPanel(
        'gitActivityReport',
        'Git Activity Report',
        vscode.ViewColumn.One,
        {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.file(path.dirname(imagePath))]
        }
    );

    const imageUri = panel.webview.asWebviewUri(vscode.Uri.file(imagePath));

    panel.webview.html = `
        <!DOCTYPE html>
        <html lang="it">
        <head>
            <meta charset="UTF-8">
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
