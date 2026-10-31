#!/usr/bin/env node
// Copia i 4 script collector/plotter dalla root del repository dentro
// vscode-extension/bundled/, cosicché `vsce package` (che impacchetta SOLO i file dentro
// vscode-extension/, mai la cartella genitrice — vedi README) li includa nel .vsix.
// Eseguito da "npm run copy-bundled" / "vscode:prepublish" (vedi package.json), MAI a mano
// dall'estensione stessa: resolveScriptPaths in src/extension.ts si limita a leggere
// questa cartella se esiste, senza mai scriverci.
//
// vscode-extension/bundled/ è un artefatto di build (vedi .gitignore) rigenerato ad ogni
// prepublish/packaging: non richiede di restare sincronizzato a mano con la root.

const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.join(__dirname, '..', '..');
const DEST_DIR = path.join(__dirname, '..', 'bundled');

// Stessi nomi installati dal pacchetto .deb in /usr/local/bin (vedi
// .github/workflows/build-deb.yml) — nessuna rinomina, per restare un unico contratto di
// nomi in tutte e tre le modalità di risoluzione (bundled, sviluppo, PATH).
const FILES = [
    'git_stats_collector.sh',
    'git_multiproject_stats_collector.sh',
    'plot_git.py',
    'plot_multiproject.py',
];

fs.mkdirSync(DEST_DIR, { recursive: true });

for (const name of FILES) {
    const src = path.join(REPO_ROOT, name);
    const dest = path.join(DEST_DIR, name);
    if (!fs.existsSync(src)) {
        console.error(`copy-bundled: file sorgente mancante: ${src}`);
        process.exit(1);
    }
    fs.copyFileSync(src, dest);
    fs.chmodSync(dest, 0o755);
}

console.log(`copy-bundled: copiati ${FILES.length} script in ${DEST_DIR}`);
