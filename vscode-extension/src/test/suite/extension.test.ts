import * as assert from 'assert';
import * as vscode from 'vscode';

suite('Estensione Git Activity Reports', () => {
    test('si attiva e registra i comandi previsti', async () => {
        const ext = vscode.extensions.getExtension('minnoit.git-activity-reports');
        assert.ok(ext, 'Estensione non trovata (id publisher.name inatteso?)');

        await ext!.activate();

        const commands = await vscode.commands.getCommands(true);
        assert.ok(
            commands.includes('git-activity.analyzeProject'),
            'Comando git-activity.analyzeProject non registrato'
        );
        assert.ok(
            commands.includes('git-activity.analyzeWorkspace'),
            'Comando git-activity.analyzeWorkspace non registrato'
        );
    });
});
