import * as path from 'path';
import * as fs from 'fs';
import Mocha = require('mocha');

// Niente dipendenza da `glob`: pochi file di test, una ricerca ricorsiva manuale evita
// di legare il progetto all'API (cambiata più volte tra le major) di quel pacchetto.
function collectTestFiles(dir: string): string[] {
    const results: string[] = [];
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            results.push(...collectTestFiles(full));
        } else if (entry.isFile() && entry.name.endsWith('.test.js')) {
            results.push(full);
        }
    }
    return results;
}

export function run(): Promise<void> {
    const mocha = new Mocha({ ui: 'tdd', color: true });
    const testsRoot = path.resolve(__dirname);

    return new Promise((resolve, reject) => {
        try {
            collectTestFiles(testsRoot).forEach(f => mocha.addFile(f));
            mocha.run(failures => {
                if (failures > 0) {
                    reject(new Error(`${failures} test falliti.`));
                } else {
                    resolve();
                }
            });
        } catch (err) {
            reject(err);
        }
    });
}
