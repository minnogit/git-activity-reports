import * as path from 'path';
import { runTests } from '@vscode/test-electron';

async function main() {
    try {
        // La cartella dell'estensione da testare è la root del progetto (due livelli sopra
        // out/test/), non out/test/ stesso: extensionDevelopmentPath deve puntare a dove
        // sta package.json.
        const extensionDevelopmentPath = path.resolve(__dirname, '../../');
        const extensionTestsPath = path.resolve(__dirname, './suite/index');

        await runTests({ extensionDevelopmentPath, extensionTestsPath });
    } catch (err) {
        console.error('Esecuzione dei test fallita:', err);
        process.exit(1);
    }
}

main();
