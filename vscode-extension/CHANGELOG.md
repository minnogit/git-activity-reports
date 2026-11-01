# Changelog

## [Non rilasciato]

### Aggiunto
- Comando «Analizza il Mio Lavoro» e impostazione `git-activity.author`: gli stessi report filtrati su una persona (nome o email; con l'email sono incluse le identità unite dagli alias o da un `.mailmap`). Con il filtro il report del singolo repository non include l'ownership.
- I collector riconoscono l'identità per email: alias per email nel file degli alias e `.mailmap` del repository (vedi il README del progetto).
- Le scritte nei grafici seguono la lingua di VS Code (italiano o inglese).
- Report: matrice di presenza per autore (giorni attivi per periodo) al posto delle barre di «giorni attivi per autore»; nel report multi-repo anche una matrice progetti × periodi (asse del tempo); riquadro «cosa non misura» in fondo ai grafici.
- Gli script collector/plotter sono inclusi nel `.vsix` (`bundled/`): non serve più il pacchetto `.deb`.
- Impostazione `git-activity.outputDir` e notifica "Report salvato in…" con i pulsanti "Salva con nome…" e "Mostra nella cartella".
- Messaggi e impostazioni localizzati (inglese come lingua sorgente, traduzione italiana).
- Icona, parole chiave e dichiarazione delle capability (workspace non attendibili e virtuali non supportati).

### Modificato
- Il PNG non viene più scritto dentro il repository analizzato: workspace per il multi-repo, cartella di storage dell'estensione per il singolo repo.
- Collector e plotter sono collegati direttamente in pipe, senza i wrapper `gitstat*.sh`.
- Grafici senza valutazione delle persone: l'indice composito è stato rimosso, gli autori sono in ordine alfabetico e il riepilogo è per repository o per progetto, non per autore.

## [0.1.0]

- Comandi "Analizza Progetto Corrente" e "Analizza Tutto il Workspace (Multi-Repo)", intervallo di date da impostazioni.
