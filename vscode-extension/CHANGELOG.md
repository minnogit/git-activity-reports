# Changelog

## [Non rilasciato]

### Aggiunto
- Comando «Analizza il Mio Lavoro» e impostazione `git-activity.author`: gli stessi report filtrati su una persona (nome o email; con l'email sono incluse le identità unite dagli alias o da un `.mailmap`). Con il filtro il report del singolo repository non include l'ownership.
- I collector riconoscono l'identità per email: alias per email nel file degli alias e `.mailmap` del repository (vedi il README del progetto).
- Le scritte nei grafici seguono la lingua di VS Code (italiano o inglese).
- Gli script collector/plotter sono inclusi nel `.vsix` (`bundled/`): non serve più il pacchetto `.deb`.
- Impostazione `git-activity.outputDir` e notifica "Report salvato in…" con i pulsanti "Salva con nome…" e "Mostra nella cartella".
- Messaggi e impostazioni localizzati (inglese come lingua sorgente, traduzione italiana).
- Icona, parole chiave e dichiarazione delle capability (workspace non attendibili e virtuali non supportati).

### Modificato
- Il PNG non viene più scritto dentro il repository analizzato: workspace per il multi-repo, cartella di storage dell'estensione per il singolo repo.
- Collector e plotter sono collegati direttamente in pipe, senza i wrapper `gitstat*.sh`.

## [0.1.0]

- Comandi "Analizza Progetto Corrente" e "Analizza Tutto il Workspace (Multi-Repo)", intervallo di date da impostazioni.
