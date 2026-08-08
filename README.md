# Git Stats Collector - Documentazione Completa

Sistema completo per analizzare e visualizzare statistiche Git, disponibile in due versioni: **singolo repository** e **multi-repository**.

## Indice

- [📦 Installazione](#-installazione) · [🚀 Guida Rapida](#-guida-rapida)
- [Componenti](#componenti)
- [📊 Versione Singolo Repository](#-versione-singolo-repository) · [🌐 Repository Remoti](#-repository-remoti-analizzare-un-url-git)
- [🗂️ Versione Multi-Repository](#-versione-multi-repository) · [Esempi Pratici Multi-Repository](#esempi-pratici-multi-repository)
- [🔄 Confronto tra le Due Versioni](#-confronto-tra-le-due-versioni)
- [📋 Casi d'Uso Combinati](#-casi-duso-combinati) · [🎨 Interpretazione dei Grafici](#-interpretazione-dei-grafici)
- [🚨 Troubleshooting](#-troubleshooting) · [💡 Tips & Best Practices](#-tips--best-practices)
- [🔧 Personalizzazione](#-personalizzazione) · [📈 Metriche Calcolate](#-metriche-calcolate) · [🎯 Interpretazione dei Dati](#-interpretazione-dei-dati)
- [❓ FAQ](#-faq) · [🚀 Comandi Semplificati (gitstats/gitstats-multi)](#-comandi-semplificati-gitstats--gitstats-multi)

---

## 📦 Installazione

### 1. Scarica il progetto

```bash
git clone https://github.com/minnogit/git-activity-reports.git ~/git-activity-reports
cd ~/git-activity-reports
chmod +x *.sh *.py
```

In alternativa, su Debian/Ubuntu puoi installare il **pacchetto `.deb`** dalla pagina Release del
repository: mette già tutto pronto in `/usr/local/bin` (inclusi i comandi `gitstats`/`gitstats-multi`) —
in tal caso puoi saltare il resto di questa sezione e andare direttamente alla [Guida Rapida](#-guida-rapida).

### 2. Requisiti

**Script Bash:**

- Bash 4.0+
- Git installato e configurato
- Accesso ai repository da analizzare
- `date` command con supporto `-d` (GNU coreutils)

**Script Python** (una delle tre opzioni):

```bash
sudo apt update
sudo apt install python3 python3-pip python3-pandas python3-matplotlib git
```

```bash
pip install pandas matplotlib numpy
```

```bash
python3 -m venv git-activity-env
source git-activity-env/bin/activate
pip install pandas matplotlib
```

### 3. Rendi gli script richiamabili da qualsiasi cartella (consigliato)

Gli script vanno eseguiti **nella cartella del repository che vuoi analizzare** (es. `cd ~/progetti/backend`),
non nella cartella dove li hai scaricati al passo 1 — per questo è comodo aggiungerli al `PATH` invece
di scrivere ogni volta il percorso completo:

```bash
echo 'export PATH="$HOME/git-activity-reports:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Da qui in avanti, da qualsiasi cartella:

```bash
cd ~/progetti/backend
git_stats_collector.sh 2025-11-01 2025-11-30 json | python3 plot_git.py
```

**Senza questo passaggio**, dovrai invocare gli script con il loro percorso completo, es.
`~/git-activity-reports/git_stats_collector.sh ...` (oppure `cd ~/git-activity-reports` e usare `./`,
ma solo se stai analizzando quella stessa cartella).

> ⚠️ **Se hai già installato una versione precedente in `/usr/local/bin`** (a mano o via
> pacchetto `.deb`), quelle sono **copie**: il `PATH` le trova prima del repository, quindi
> continuerai a eseguire il codice vecchio anche dopo un `git pull`. Verifica con
> `command -v plot_git.py` e aggiorna tutti i file insieme — collector e plotter devono
> essere della stessa versione, perché il JSON è un contratto tra loro:
>
> ```bash
> cd ~/git-activity-reports
> sudo install -m 755 git_stats_collector.sh git_multiproject_stats_collector.sh \
>   plot_git.py plot_multiproject.py /usr/local/bin/
> sudo install -m 755 gitstat.sh /usr/local/bin/gitstats
> sudo install -m 755 gitstat-multi.sh /usr/local/bin/gitstats-multi
> ```

### 4. (Opzionale) Comandi ancora più brevi: `gitstats` / `gitstats-multi`

Un ulteriore passo, descritto in [🚀 Comandi Semplificati](#-comandi-semplificati-gitstats--gitstats-multi)
più sotto, installa `gitstats`/`gitstats-multi`: un solo comando al posto della pipe collector + plot
(`gitstats 2025-11-01 2025-11-30` invece di `git_stats_collector.sh 2025-11-01 2025-11-30 json | python3 plot_git.py`).
Sono i comandi usati negli esempi della Guida Rapida qui sotto.

---

## 🚀 Guida Rapida

### Quale comando uso?

| Voglio... | Comando |
| --- | --- |
| Il dettaglio **giorno per giorno** di UN repository, su poche settimane/un mese (sono già dentro la sua cartella) | `git_stats_collector.sh` |
| Il **totale aggregato** di uno o più repository su un periodo lungo (mesi/trimestri) | `git_multiproject_stats_collector.sh` |
| **Confrontare più repository** tra loro (portfolio, team, microservizi) | `git_multiproject_stats_collector.sh` |
| Analizzare un repository che **non ho ancora clonato in locale** (solo l'URL) | entrambi accettano un URL Git — vedi [Repository Remoti](#-repository-remoti-analizzare-un-url-git) |

> Il grafico giornaliero di `git_stats_collector.sh` perde leggibilità su periodi lunghi (una barra per
> giorno) — dettagli e alternative nella sezione [Versione Singolo Repository](#-versione-singolo-repository).

### I comandi che userai più spesso

I comandi qui sotto (`gitstats`, `gitstats-multi`) sono i wrapper installati con il passo 4 di
[📦 Installazione](#-installazione) — se non li hai ancora installati, o hai fatto solo il passo 3
(script nel `PATH`), usa la variante "senza wrapper" più sotto.

**Con `gitstats`/`gitstats-multi` installati:**

```bash
# 1. Report giornaliero di un repository (eseguito dentro la sua cartella), con grafico
cd ~/progetti/backend
gitstats 2025-11-01 2025-11-30
# -> genera git_stats.png

# 2. Stesso report, filtrato per un autore
gitstats 2025-11-01 2025-11-30 "Mario Rossi"

# 3. Confronto tra più repository (locali e/o remoti), con grafico
gitstats-multi 2025-11-01 2025-11-30 ~/progetti/repoA ~/progetti/repoB
# -> genera git_activity_multi_project_report_<inizio>_<fine>.png (es. ..._2025-11-01_2025-11-30.png)

# 4. Stesso confronto, leggendo l'elenco progetti da file invece che da riga di comando
gitstats-multi --file project_list.txt 2025-11-01 2025-11-30
```

**Senza wrapper** (solo script nel `PATH`, passo 3 di Installazione — fa la stessa cosa "a mano",
utile anche per il formato `text` o per salvare il JSON intermedio, non esposti dai wrapper):

```bash
cd ~/progetti/backend
git_stats_collector.sh 2025-11-01 2025-11-30 json | python3 plot_git.py
git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 ~/progetti/repoA ~/progetti/repoB \
  | python3 plot_multiproject.py
```

### Parametri in breve

| | `git_stats_collector.sh` | `git_multiproject_stats_collector.sh` |
| --- | --- | --- |
| Sintassi | `[opzioni] <INIZIO> <FINE> [formato] [autore]` | `[opzioni] <INIZIO> <FINE> [percorsi...]` |
| Dove va eseguito | Dentro la cartella del repo (oppure con `--repo`) | Da qualsiasi cartella |
| `INIZIO` / `FINE` | `YYYY-MM-DD`, obbligatorie | `YYYY-MM-DD`, obbligatorie (anche via `--start`/`--end`) |
| 3° argomento posizionale | `text` (default) o `json` | — (percorso/URL repository) |
| 4° argomento posizionale | nome autore (opzionale, filtra) | — |
| Elenco repository | non applicabile (un solo repo per esecuzione) | percorsi/URL in coda al comando, oppure `--file lista.txt` |
| Aggiornamento da remoto | solo con `--fetch` | solo con `--fetch` |
| Repository via URL | `--repo <url>` | passa l'URL come percorso (posizionale o riga di `--file`) |
| Formato output | `text` o `json` su stdout | sempre `json` su stdout |
| Grafico (in pipe) | `python3 plot_git.py` → report a 4 pannelli | `python3 plot_multiproject.py` → report a 4 pannelli |

Dettagli completi di ogni opzione più sotto: [Versione Singolo Repository](#-versione-singolo-repository), [Versione Multi-Repository](#-versione-multi-repository).

---

## Componenti

### Versione Singolo Repository

- **`git_stats_collector.sh`** - Analizza un repository alla volta con dettaglio giornaliero
- **`plot_git.py`** - Genera un report a 4 pannelli (churn nel tempo, commit nel tempo, giorni attivi, tabella riepilogo)

### Versione Multi-Repository

- **`git_multiproject_stats_collector.sh`** - Analizza più repository contemporaneamente
- **`plot_multiproject.py`** - Genera un report a 4 pannelli comparativi tra progetti (churn per progetto, distribuzione, giorni attivi, tabella riepilogo)

Il raggruppamento degli autori tramite `git-activity-aliases.json` è gestito dai **collector**
(non dai plotter), perché va applicato ai dati grezzi prima di ogni aggregazione.

---

## 📊 Versione Singolo Repository

### Panoramica

Analizza un singolo repository Git con dettaglio **giornaliero**, ideale per:

- Report personali di attività
- Analisi sprint su un progetto specifico
- Monitoraggio giornaliero del team su un repository

**⚠️ Limite del grafico su intervalli lunghi:** `plot_git.py` disegna una barra per ogni giorno del
periodo. Su un intervallo di poche settimane il grafico è leggibile; su diversi mesi (es. un semestre)
le barre diventano troppo strette/numerose e il grafico perde di leggibilità. Per periodi lunghi:

- restringi l'intervallo a poche settimane/un mese per volta, oppure
- usa `git_multiproject_stats_collector.sh` (aggregato, non giornaliero — vedi sezione dedicata più sotto)
  se ti interessa solo il totale del periodo e non il dettaglio giorno per giorno, oppure
- dividi il periodo lungo in più chiamate (una per settimana/mese) e genera un grafico per ciascuna,
  come nell'esempio ["Analisi Mensile Multi-Livello"](#analisi-mensile-multi-livello).

### Sintassi

```bash
./git_stats_collector.sh <DATA_INIZIO> <DATA_FINE> [formato] [autore]
```

**Nota:** Lo script Python `plot_git.py` supporta il raggruppamento degli autori attraverso un file opzionale `git-activity-aliases.json` nella stessa directory. Questo file permette di raggruppare diversi nomi di autori Git sotto un unico nome comune, utile quando lo stesso sviluppatore ha contribuito con nomi diversi. Esempio:

```json
{
  "Mario Rossi": "Mario R.",
  "Rossi M.": "Mario R.",
  "Giulia Verdi": "Giulia V."
}
```

Il file di configurazione può essere posizionato in diverse posizioni e verrà cercato in questo ordine:

1. Nella directory corrente (`./git-activity-aliases.json`)
2. Nella directory di configurazione XDG specifica per l'applicazione (`~/.config/git-activity-reports/git-activity-aliases.json`)
3. Nella directory di configurazione XDG generica (`~/.config/git-activity-git-activity-aliases.json`)
4. **Accanto agli script** (`<cartella-degli-script>/git-activity-aliases.json`) — utile perché il
   collector si esegue *dentro il repository da analizzare*, dove `.` è un'altra cartella: un file
   messo accanto agli script vale così per tutti i repository
5. Nella directory di sistema (`/etc/git-activity-reports/git-activity-aliases.json`)

Se nessun file di configurazione esiste, lo script continuerà a funzionare normalmente senza raggruppare gli autori.

## 🌐 Repository Remoti (analizzare un URL Git)

Sia `git_stats_collector.sh` (via `--repo <url>`) sia `git_multiproject_stats_collector.sh` (come
percorso posizionale o riga di `--file`) accettano, al posto di un path locale, un URL Git qualsiasi
(`https://...`, `git://...`, `ssh://...` o la forma scp `git@host:org/repo.git`).

**Come funziona:**

1. Al primo utilizzo, il repository viene **clonato** in una cartella visibile (non nascosta) sotto
   `$GIT_ACTIVITY_REPOS_DIR` (default: `~/repos`), usando come nome cartella l'ultimo segmento dell'URL
   (senza `.git`).
2. Alle esecuzioni successive, se la cartella corrisponde già a quell'URL (stesso `remote origin`), viene
   **riusata** senza clonare di nuovo — l'aggiornamento (`git fetch`) resta opt-in con `--fetch`, come per
   i repository locali.
3. Poiché la cartella è visibile e normale (non un bare clone nascosto), può coincidere con un repository
   su cui stai già lavorando: se ci clonavi già a mano quel progetto in `~/repos/nome-progetto`, lo script
   lo riconosce e lo riusa (a patto che l'`origin` combaci con l'URL richiesto).

**Esempi:**

```bash
# Singolo repository remoto
./git_stats_collector.sh --repo https://github.com/org/repo.git 2025-11-01 2025-11-30 json | python3 plot_git.py

# Multi-repository: mix di URL e path locali
./git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 \
  https://github.com/org/backend.git ~/progetti/frontend git@github.com:org/mobile.git \
  | python3 plot_multiproject.py

# Cartella di clonazione personalizzata
GIT_ACTIVITY_REPOS_DIR=/data/git-mirrors ./git_multiproject_stats_collector.sh --file progetti.txt 2025-11-01 2025-11-30
```

**Collisioni di nome cartella:** se due URL diversi produrrebbero lo stesso nome di cartella (es. due
repository chiamati entrambi `backend` su host diversi), lo script si **ferma con un errore** invece di
sovrascrivere/confondere i due repository. Per risolvere, assegna un nome di cartella dedicato a uno dei
due URL tramite un file di mapping opzionale (obbligatorio solo in caso di collisione):

`~/.config/git-activity-reports/git-activity-repos-map.json`

```json
{
  "https://github.com/org-a/backend.git": "backend-org-a",
  "https://gitlab.com/org-b/backend.git": "backend-org-b"
}
```

Le chiavi devono combaciare esattamente con l'URL passato sulla riga di comando/nel file `--file`.

### Parametri

| Posizione | Parametro     | Obbligatorio | Descrizione                     | Default |
| --------- | ------------- | ------------ | ------------------------------- | ------- |
| 1         | `DATA_INIZIO` | ✓            | Data inizio (YYYY-MM-DD)        | -       |
| 2         | `DATA_FINE`   | ✓            | Data fine (YYYY-MM-DD)          | -       |
| 3         | `formato`     | ✗            | Formato output: `text` o `json` | `text`  |
| 4         | `autore`      | ✗            | Filtra per autore, **match esatto** sul nome | tutti   |

### Opzioni Disponibili

| Opzione      | Argomento     | Descrizione                                                                                                                     |
| ------------ | ------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `--fetch`    | -             | Abilita l'aggiornamento del repository con git fetch                                                                            |
| `--repo`     | `<path\|url>` | Analizza questo repository invece della cartella corrente (vedi [Repository Remoti](#-repository-remoti-analizzare-un-url-git)) |
| `-h, --help` | -             | Mostra l'help                                                                                                                   |

### Esempi - Singolo Repository

#### 1. Report testuale per tutti gli autori (modalità totale)

```bash
cd ~/progetti/backend
./git_stats_collector.sh 2025-11-01 2025-11-30
```

**Output:**

```txt
Generazione report dal 2025-11-01 al 2025-11-30...

## Report: TOTALE
---------------------------------------------------------------------------------------
Giorno     Data            Commit     Righe Tot.       Aggiunte         Rimosse
---------------------------------------------------------------------------------------
Lun        2025-11-04          3            450            280            170
Mar        2025-11-05          5            892            650            242
Mer        2025-11-06          2            156            100             56
---------------------------------------------------------------------------------------
TOTALE:                       10           1498           1030            468
```

#### 2. Report testuale per autore specifico

```bash
./git_stats_collector.sh 2025-11-01 2025-11-30 text "Mario Rossi"
```

#### 3. JSON per visualizzazione grafica (tutti gli autori)

```bash
./git_stats_collector.sh 2025-11-01 2025-11-30 json | python3 plot_git.py
```

**Genera:** `git_stats.png` con grafico stacked bar giornaliero

#### 4. JSON per singolo autore

```bash
./git_stats_collector.sh 2025-11-01 2025-11-30 json "Laura Bianchi"
```

**Output JSON:**

```json
[
  {
    "author": "Laura Bianchi",
    "total_commits": 15,
    "daily_data": [
      {"day": "Monday", "date": "2025-11-04", "commits": 3, "lines": 450, "added": 280, "deleted": 170},
      {"day": "Tuesday", "date": "2025-11-05", "commits": 5, "lines": 892, "added": 650, "deleted": 242}
    ]
  }
]
```

#### 5. Salvataggio dati per analisi successive

```bash
# Genera e salva JSON
./git_stats_collector.sh 2025-11-01 2025-11-30 json > novembre.json

# Visualizza in seguito
cat novembre.json | python3 plot_git.py

# Oppure ispeziona i dati
cat novembre.json | jq '.[] | {author, total_commits}'
```

#### 6. Con aggiornamento esplicito del repository

```bash
# Esegue git fetch prima dell'analisi
./git_stats_collector.sh --fetch 2025-11-01 2025-11-30 json | python3 plot_git.py

# Con formato testuale
./git_stats_collector.sh --fetch 2025-11-01 2025-11-30 text "Mario Rossi"
```

---

## 🗂️ Versione Multi-Repository

### Panoramica

Analizza più repository contemporaneamente con statistiche **per progetto e autore** (con dettaglio
giornaliero), ideale per:

- Confronto attività tra progetti diversi
- Report di team distribuiti su più repository
- Analisi portfolio completo

**Note importanti:**

- I merge commits sono esclusi dalle statistiche
- File non rilevanti come node_modules, dist, vendor, lock files e file generati sono esclusi dalle statistiche
- Le righe totali sono calcolate come: aggiunte + eliminate

### Sintassi Completa

```bash
./git_multiproject_stats_collector.sh [OPZIONI] <DATA_INIZIO> <DATA_FINE> [percorsi...]
```

### Opzioni Disponibili

| Opzione      | Argomento | Descrizione                                            |
| ------------ | --------- | ------------------------------------------------------ |
| `--file`     | `<file>`  | Legge i percorsi dei repository da file (uno per riga) |
| `--start`    | `<data>`  | Data di inizio periodo (formato: YYYY-MM-DD)           |
| `--end`      | `<data>`  | Data di fine periodo (formato: YYYY-MM-DD)             |
| `--fetch`    | -         | Abilita l'aggiornamento dei repository con git fetch   |
| `-h, --help` | -         | Mostra l'help                                          |

**Nota:** ogni percorso (posizionale o riga di `--file`) può essere anche un URL Git, non solo un path
locale — vedi [Repository Remoti](#-repository-remoti-analizzare-un-url-git).

---

## Esempi Pratici Multi-Repository

### 1. Analisi di repository specifici

```bash
./git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 ~/progetti/repoA ~/progetti/repoB
```

**Risultato:** Analizza `repoA` e `repoB` per tutto novembre 2025.

---

### 2. Repository da file di configurazione

**Crea il file `progetti.txt`:**

```txt
~/progetti/backend
~/progetti/frontend
/var/www/api-service
# Questo è un commento - verrà ignorato
~/workspace/mobile-app
```

**Esegui lo script:**

```bash
./git_multiproject_stats_collector.sh --file progetti.txt 2025-11-01 2025-11-30
```

---

### 3. Date come opzioni (ordine flessibile)

```bash
# Date specificate con flag
./git_multiproject_stats_collector.sh --start 2025-11-01 --end 2025-11-30 ~/repo1 ~/repo2

# Mixando file e date con flag
./git_multiproject_stats_collector.sh --file progetti.txt --start 2025-11-01 --end 2025-11-30
```

---

### 4. Pipeline completa con visualizzazione

```bash
# Genera JSON e crea grafici
./git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 ~/repo1 ~/repo2 | python3 plot_multiproject.py
```

### 5. Con aggiornamento esplicito dei repository

```bash
# Esegue git fetch prima dell'analisi
./git_multiproject_stats_collector.sh --fetch --file progetti.txt 2025-11-01 2025-11-30

# Oppure con repository specifici
./git_multiproject_stats_collector.sh --fetch 2025-11-01 2025-11-30 ~/repo1 ~/repo2
```

**Output:** File `git_activity_multi_project_report_<inizio>_<fine>.png` con 4 pannelli.

---

### 5. Salvataggio intermedio dei dati

```bash
# Salva JSON per analisi successive
./git_multiproject_stats_collector.sh --file progetti.txt 2025-11-01 2025-11-30 > dati_novembre.json

# Usa i dati salvati
cat dati_novembre.json | python3 plot_multiproject.py
```

---

## 🔄 Confronto tra le Due Versioni

| Caratteristica       | Singolo Repository               | Multi-Repository                     |
| -------------------- | -------------------------------- | ------------------------------------ |
| **Granularità**      | Giornaliera                      | Aggregata per progetto               |
| **Scope**            | Un repository alla volta         | Multipli contemporaneamente          |
| **Formato output**   | text/json                        | json (solo)                          |
| **Filtro autore**    | Sì, via parametro                | No (mostra tutti)                    |
| **Grafici generati** | 1 (stacked bar)                  | 3 (bar, donut, ranking)              |
| **Uso tipico**       | Sprint review, analisi personale | Portfolio review, confronto progetti |
| **Esecuzione**       | Nella cartella del repo          | Da qualsiasi posizione               |

### Quando Usare Quale Versione?

**Usa Singolo Repository se:**

- Vuoi vedere l'attività **giorno per giorno**
- Ti interessa un **progetto specifico**
- Vuoi report testuali leggibili
- Necessiti filtrare per autore specifico

**Usa Multi-Repository se:**

- Devi confrontare **più progetti**
- Ti interessa la **distribuzione del lavoro** tra repository
- Vuoi una **visione d'insieme** del team
- Lavori su un ecosistema di microservizi

---

## 📋 Casi d'Uso Combinati

### Sprint Retrospective Completa

```bash
# 1. Overview generale su tutti i progetti del team
./git_multiproject_stats_collector.sh --file team-repos.txt 2025-11-15 2025-11-30 \
  | python3 plot_multiproject.py
  
# 2. Dettaglio giornaliero sul progetto principale
cd ~/progetti/backend
./git_stats_collector.sh 2025-11-15 2025-11-30 json | python3 plot_git.py

# 3. Report testuale per uno sviluppatore specifico
./git_stats_collector.sh 2025-11-15 2025-11-30 text "Mario Rossi"
```

### Analisi Mensile Multi-Livello

```bash
# Novembre: vista generale
./git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 \
  ~/backend ~/frontend ~/mobile > novembre_overview.json

# Dettaglio settimanale su frontend
cd ~/frontend
./git_stats_collector.sh 2025-11-01 2025-07 json > week1.json
./git_stats_collector.sh 2025-11-08 2025-11-14 json > week2.json
./git_stats_collector.sh 2025-11-15 2025-11-21 json > week3.json
./git_stats_collector.sh 2025-11-22 2025-11-30 json > week4.json

# Visualizza settimana per settimana
for week in week*.json; do
  echo "Analisi $week"
  cat $week | python3 plot_git.py
  mv git_stats.png "${week%.json}_chart.png"
done
```

### Confronto Performance Q3 vs Q4

```bash
# Q3: Multi-repo
./git_multiproject_stats_collector.sh --file all-repos.txt 2025-07-01 2025-09-30 \
  | python3 plot_multiproject.py
mv git_activity_multi_project_report_*.png q3_portfolio.png

# Q4: Multi-repo
./git_multiproject_stats_collector.sh --file all-repos.txt 2025-10-01 2025-12-31 \
  | python3 plot_multiproject.py
mv git_activity_multi_project_report_*.png q4_portfolio.png

# Dettaglio Q4 su progetto strategico
cd ~/progetti/strategic-project
./git_stats_collector.sh 2025-10-01 2025-12-31 json | python3 plot_git.py
mv git_stats.png q4_strategic_daily.png
```

---

## 🎨 Interpretazione dei Grafici

Entrambi i report sono composti da **4 pannelli**: tre metriche affiancate più una
tabella con i valori esatti. Non c'è un punteggio unico in primo piano, di proposito
(vedi [Metriche Calcolate](#-metriche-calcolate)).

### Report Singolo Repository (`git_stats.png`)

| Pannello | Cosa mostra |
|---|---|
| 1. Churn nel tempo, per autore | Barre impilate + linea di trend (media mobile). Volume di cambiamento |
| 2. Commit nel tempo, per autore | Barre impilate. Frequenza di consegna, indipendente dalla dimensione |
| 3. Giorni attivi per autore | La metrica più robusta: continuità del contributo |
| 4. Riepilogo per autore | Tabella con churn, commit, giorni attivi, file, indice |

**Granularità adattiva:** l'asse temporale si adatta automaticamente al periodo, perché
una barra al giorno diventa illeggibile su intervalli lunghi:

| Periodo richiesto | Granularità |
|---|---|
| ≤ 45 giorni | giornaliera |
| 46–250 giorni | settimanale |
| > 250 giorni | mensile |

**Insights tipici:** picchi prima dei rilasci, periodi di inattività, distribuzione del
carico. Confrontare i pannelli 1 e 2 è spesso più informativo di ciascuno preso da solo:
molto churn con pochi commit indica cambiamenti grossi e rari, il contrario indica
iterazione a piccoli passi.

### Report Multi-Repository

| Pannello | Cosa mostra |
|---|---|
| 1. Churn per progetto e autore | Barre impilate. Dove si concentra il volume, e chi lavora su cosa |
| 2. Distribuzione del churn | Quota per progetto (ciambella; barra 100% se i progetti sono < 3) |
| 3. Giorni attivi per autore | Continuità del contributo, sommata sui progetti |
| 4. Riepilogo per progetto | Tabella con churn, commit, giorni attivi, file, autori, indice |

Un progetto può avere churn alto e indice basso (pochi commit molto grossi) o il
contrario (attività distribuita su molti giorni): è la differenza che il vecchio
punteggio unico nascondeva.

**Colori:** ogni autore ha un colore fisso, coerente tra tutti i pannelli e assegnato in
ordine di palette, non per rango. Oltre 8 autori la coda viene accorpata in "Altro"
invece di generare tinte nuove (indistinguibili per chi ha deficit di visione dei colori).
La palette è verificata per separazione CVD e contrasto.

---

## 📊 Output Format Details

Il JSON è un **contratto** tra lo script bash e quello Python: se aggiorni un collector
devi aggiornare anche il plotter corrispondente (e viceversa). I plotter accettano anche
il formato precedente, per poter rielaborare file JSON salvati in passato.

### JSON Singolo Repository

```json
{
  "metadata": {
    "start_date": "2025-11-01",
    "end_date": "2025-11-30",
    "project": "backend",
    "date_basis": "author"
  },
  "data": [
    {
      "author": "Mario Rossi",
      "total_commits": 24,
      "daily_data": [
        {
          "day": "Monday",
          "date": "2025-11-04",
          "commits": 3,
          "lines": 450,
          "added": 280,
          "deleted": 170,
          "files": 6
        }
      ]
    }
  ]
}
```

Sono elencati **solo i giorni con attività**: il plotter ricostruisce i giorni vuoti dal
range in `metadata`, quindi il tempo non viene compresso nel grafico.

### JSON Multi-Repository

```json
{
  "metadata": {
    "start_date": "2025-11-01",
    "end_date": "2025-11-30",
    "date_basis": "author"
  },
  "data": [
    {
      "project": "backend",
      "author": "Mario Rossi",
      "commits": 24,
      "added": 3000,
      "deleted": 450,
      "lines": 3450,
      "files": 37,
      "active_days": 12,
      "daily_data": [
        { "date": "2025-11-04", "commits": 3, "added": 280, "deleted": 170, "files": 6 }
      ]
    }
  ]
}
```

**Campi:**

| Campo | Significato |
|---|---|
| `project` | Nome del repository (nome della cartella) |
| `author` | Nome autore Git, con alias già applicati |
| `commits` | Commit esclusi i merge |
| `added` / `deleted` | Righe aggiunte / rimosse |
| `lines` | `added + deleted` (retrocompatibilità) |
| `files` | File **distinti** toccati nel periodo |
| `active_days` | Giorni distinti con almeno 1 commit |
| `daily_data` | Dettaglio giornaliero, con `files` distinti **per giorno** |
| `date_basis` | `"author"`: i giorni sono attribuiti per author-date |

`daily_data` è necessario, non decorativo: senza di esso il tetto anti-outlier
dell'indice si applicherebbe all'aggregato di periodo e saturerebbe (vedi
[Metriche Calcolate](#-metriche-calcolate)).

---

## Formato File dei Percorsi

Il file specificato con `--file` deve seguire queste regole:

```txt
# Percorsi assoluti
/home/utente/progetti/repo1
/var/www/progetto2

# Percorsi con tilde (espansa automaticamente)
~/workspace/backend
~/progetti/frontend

# Linee vuote e commenti sono ignorati
# TODO: aggiungere nuovo-progetto

# ⚠️ Supporto per percorsi con spazi
/home/utente/My Projects/repo name
```

**Nota:** i dati raccolti da questi percorsi vengono elaborati da `plot_multiproject.py`, che calcola
churn, commit e giorni attivi più un indice composito secondario (vedi
[Metriche Calcolate](#-metriche-calcolate)).

Il file `git-activity-aliases.json` permette di raggruppare diversi nomi di autori Git sotto un unico nome comune, utile quando lo stesso sviluppatore ha contribuito con nomi diversi. È letto dai **collector**, che applicano gli alias prima di aggregare. Esempio:

```json
{
  "Mario Rossi": "Mario R.",
  "Rossi M.": "Mario R.",
  "Giulia Verdi": "Giulia V."
}
```

Il file di configurazione può essere posizionato in diverse posizioni e verrà cercato in questo ordine:

1. Nella directory corrente (`./git-activity-aliases.json`)
2. Nella directory di configurazione XDG specifica per l'applicazione (`~/.config/git-activity-reports/git-activity-aliases.json`)
3. Nella directory di configurazione XDG generica (`~/.config/git-activity-git-activity-aliases.json`)
4. **Accanto agli script** (`<cartella-degli-script>/git-activity-aliases.json`) — utile perché il
   collector si esegue *dentro il repository da analizzare*, dove `.` è un'altra cartella: un file
   messo accanto agli script vale così per tutti i repository
5. Nella directory di sistema (`/etc/git-activity-reports/git-activity-aliases.json`)

Se nessun file di configurazione esiste, lo script continuerà a funzionare normalmente senza raggruppare gli autori.

---

## Output JSON e visualizzazioni

Il formato JSON completo di entrambi i collector, con la descrizione di tutti i campi, è
documentato in [Output Format Details](#-output-format-details).
La composizione dei pannelli di ciascun report è descritta in
[Interpretazione dei Grafici](#-interpretazione-dei-grafici).

---

## Casi d'Uso Comuni

### Sprint Review

```bash
# Analisi dello sprint appena concluso (ultimi 14 giorni)
./git_multiproject_stats_collector.sh --start 2025-11-15 --end 2025-11-30 \
  ~/team/backend ~/team/frontend ~/team/mobile | python3 plot_multiproject.py
```

### Report Mensile

```bash
# Tutto il team, tutti i progetti, ultimo mese
./git_multiproject_stats_collector.sh --file team-repos.txt 2025-11-01 2025-11-30 \
  > report_novembre.json

python3 plot_multiproject.py < report_novembre.json
```

### Confronto Trimestrale

```bash
# Q3 vs Q4
./git_multiproject_stats_collector.sh 2025-07-01 2025-09-30 ~/repo1 ~/repo2 > q3.json
./git_multiproject_stats_collector.sh 2025-10-01 2025-12-31 ~/repo1 ~/repo2 > q4.json

# Analizza separatamente
python3 plot_multiproject.py < q3.json  # genera git_activity_multi_project_report_*.png
mv git_activity_multi_project_report_*.png q3_report.png

python3 plot_multiproject.py < q4.json
mv git_activity_multi_project_report_*.png q4_report.png
```

---

## Note Tecniche

### Commit Considerati

- **Inclusi:** Commit standard con modifiche ai file
- **Esclusi:** Merge commits (flag `--no-merges`)
- Un solo `git log` per repository: il raggruppamento per autore e giorno avviene in `awk`.
  Oltre a essere molto più rapido (prima si lanciava un `git log` per ogni giorno *per ogni
  autore*), evita un doppio conteggio reale, descritto sotto.

### Attribuzione all'autore

Il match sul nome autore è **esatto**. `git log --author=<nome>` fa invece un match per
sottostringa: con due autori "Luca" e "Luca Bianchi", i commit di quest'ultimo venivano
contati **anche** per "Luca". Conseguenze pratiche:

- Il parametro `autore` richiede il nome completo esatto; se non trova corrispondenze, lo
  script elenca gli autori disponibili nel periodo
- I nomi con caratteri speciali (parentesi, punti) non vengono più interpretati come regex

### Gestione Date

- Formato richiesto: `YYYY-MM-DD`, range inclusivo su entrambi gli estremi
- I giorni sono attribuiti in base alla **author-date**, non alla committer-date.
  `--since`/`--until` di git filtrano sulla committer-date: un rebase o un cherry-pick
  riscrive quella data, quindi settimane di lavoro potevano finire attribuite al giorno del
  rebase. Il filtro esatto sul periodo è applicato dopo la lettura del log (git non sa
  filtrare per author-date), motivo per cui `--since` viene esteso di 31 giorni indietro.

### File Considerati

- **Inclusi:** File di codice sorgente e altri file rilevanti per le statistiche
- **Esclusi:**
  - Directory `node_modules/*`
  - Directory `dist/*`
  - Directory `vendor/*`
  - File `*.lock` (come package-lock.json, Gemfile.lock, ecc.)
  - File `*.min.js`
  - Directory `prisma/*`
  - Directory `**/generated/*`
- Questi file sono esclusi perché non rappresentano attività di sviluppo significativa

### Gestione Date

- Formato richiesto: `YYYY-MM-DD`
- Range inclusivo: include sia la data di inizio che quella di fine
- Orari considerati: `00:00:00` (inizio) - `23:59:59` (fine)

### Performance

Per repository molto grandi (>10K commits), l'analisi può richiedere alcuni minuti. Considera di:

- Ridurre l'intervallo temporale
- Analizzare i repository in batch separati

### Aggiornamento Repository

Di default, i repository **non vengono aggiornati** automaticamente con git fetch. Per abilitare l'aggiornamento esplicito, usa l'opzione `--fetch`:

**Multi-repository:**

```bash
./git_multiproject_stats_collector.sh --fetch --file repos.txt 2025-11-01 2025-11-30
```

**Singolo repository:**

```bash
./git_stats_collector.sh --fetch 2025-11-01 2025-11-30 json
```

---

## 🚨 Troubleshooting

### Problemi Comuni - Installazione

#### I grafici sembrano identici a prima dopo un aggiornamento

**Causa:** in `/usr/local/bin` ci sono **copie** di una versione precedente (installate a
mano o dal pacchetto `.deb`), e il `PATH` le trova prima del repository. Succede tipicamente
con `gitstats`/`gitstats-multi`, che risolvono collector e plotter dal `PATH`.

**Diagnosi e soluzione:**

```bash
command -v plot_git.py          # se stampa /usr/local/bin/..., stai usando la copia
grep -c DELETED_WEIGHT "$(command -v plot_git.py)"   # 0 = versione vecchia

cd ~/git-activity-reports
sudo install -m 755 git_stats_collector.sh git_multiproject_stats_collector.sh \
  plot_git.py plot_multiproject.py /usr/local/bin/
sudo install -m 755 gitstat.sh /usr/local/bin/gitstats
sudo install -m 755 gitstat-multi.sh /usr/local/bin/gitstats-multi
```

Aggiorna **tutti** i file insieme: il JSON è un contratto tra collector e plotter.

#### `SyntaxWarning: 'return' in a 'finally' block`

**Causa:** avviso emesso da `pyparsing`, una dipendenza di matplotlib, durante l'import.
Non riguarda questi script.

**Soluzione:** nessuna, è innocuo. Se il messaggio dà fastidio, `python3 -W ignore::SyntaxWarning`.
Il comando è andato a buon fine se stampa `Grafico generato con successo: ...`.

### Problemi Comuni - Singolo Repository

#### "Nessun dato per l'autore ... (il match è esatto)"

**Causa:** dalla versione 2.0 il filtro autore richiede il nome **completo ed esatto**; prima
era un match per sottostringa (che però causava doppi conteggi tra nomi annidati).

**Soluzione:** lo script elenca da sé gli autori disponibili nel periodo — copia il nome da
quella lista. Se usi gli alias funziona sia il nome Git originale sia quello visualizzato: il nome
richiesto viene prima risolto attraverso la mappa alias (lo script te lo segnala, es.
`Autore "Michele Innocenti" risolto in "minnogit" tramite gli alias`).

#### "Non sei in un repository Git"

**Causa:** Script eseguito fuori da una cartella Git  
**Soluzione:**

```bash
cd /path/to/your/repo
./git_stats_collector.sh 2025-11-01 2025-11-30
```

#### "L'input non sembra un JSON valido"

**Causa:** Hai usato formato `text` invece di `json` con plot_git.py  
**Soluzione:**

```bash
# ✗ Errato
./git_stats_collector.sh 2025-11-01 2025-11-30 text | python3 plot_git.py

# ✓ Corretto
./git_stats_collector.sh 2025-11-01 2025-11-30 json | python3 plot_git.py
```

#### Autore con spazi non funziona

**Causa:** Nome autore non quotato  
**Soluzione:**

```bash
# ✗ Errato
./git_stats_collector.sh 2025-11-01 2025-11-30 text Mario Rossi

# ✓ Corretto
./git_stats_collector.sh 2025-11-01 2025-11-30 text "Mario Rossi"
```

#### "Nessun dato trovato per generare il grafico"

**Causa:** JSON contiene solo entry "TOTALE" oppure nessuna attività nel periodo  
**Soluzione:**

```bash
# Verifica ci siano commit nel periodo
git log --since="2025-11-01" --until="2025-11-30" --oneline

# Se ci sono commit ma solo totale, rimuovi il filtro autore
./git_stats_collector.sh 2025-11-01 2025-11-30 json
```

### Problemi Comuni - Multi-Repository

#### "Non è una cartella valida o un repository Git"

**Causa:** Il percorso non esiste o non contiene `.git`  
**Soluzione:** Verifica il percorso con `ls -la <percorso>/.git`

#### "Nessun dato ricevuto in input"

**Causa:** Lo script bash non ha prodotto output o la pipe è fallita  
**Soluzione:**

```bash
# Testa lo script bash separatamente
./git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 ~/repo1
# Deve stampare JSON valido
```

#### "Errore nel parsing del JSON"

**Causa:** Output JSON malformato (rare ma possibili con nomi autori strani)  
**Soluzione:** Salva l'output e ispezionalo:

```bash
./git_multiproject_stats_collector.sh [...] > debug.json
cat debug.json  # Cerca caratteri speciali o virgole mancanti
```

#### Percorsi con spazi non funzionano

**Causa:** File di percorsi con split errato  
**Soluzione:** Assicurati che ogni percorso sia su una riga separata nel file:

```txt
# ✓ Corretto
/home/user/My Projects/repo

# ✗ Errato (spazi interpretati come separatori)
/home/user/My Projects/repo1 /home/user/repo2
```

### Problemi con le Date

#### Date non riconosciute

**Causa:** Formato data errato  
**Soluzione:**

```bash
# ✓ Corretto
./git_stats_collector.sh 2025-11-01 2025-11-30

# ✗ Errato
./git_stats_collector.sh 01-11-2025 30-11-2025  # Formato europeo
./git_stats_collector.sh 11/01/2025 11/30/2025  # Con slash
```

---

## 💡 Tips & Best Practices

### Performance

**Singolo Repository:**

- Per periodi lunghi (>3 mesi), considera di suddividere in chunk mensili
- I giorni senza attività vengono omessi nel report text (performance migliorata)

**Multi-Repository:**

- Repository molto grandi (>10K commits) possono richiedere minuti
- Usa il formato `--file` per repository list riutilizzabili
- Considera di eseguire analisi in parallelo su macchine diverse

### Organizzazione File

```txt
git-stats-tools/
├── scripts/
│   ├── git_stats_collector.sh
│   ├── git_multiproject_stats_collector.sh
│   ├── plot_git.py
│   └── plot_multiproject.py
├── configs/
│   ├── team-repos.txt
│   ├── backend-repos.txt
│   └── all-projects.txt
└── reports/
    ├── 2025-11/
    │   ├── week1_single.png
    │   ├── overview_multi.png
    │   └── data.json
    └── 2025-12/
```

### Automazione con Cron

**Report settimanale automatico (ogni lunedì):**

```cron
# /etc/crontab o crontab -e
0 9 * * 1 cd /home/user/progetti/backend && /path/to/git_stats_collector.sh "$(date -d 'last monday' +\%Y-\%m-\%d)" "$(date -d 'yesterday' +\%Y-\%m-\%d)" json | python3 /path/to/plot_git.py && mv git_stats.png ~/reports/week_$(date +\%U).png
```

**Report mensile multi-repo (primo del mese):**

```cron
0 8 1 * * /path/to/git_multiproject_stats_collector.sh --file ~/configs/all-repos.txt "$(date -d 'last month' +\%Y-\%m-01)" "$(date -d 'yesterday' +\%Y-\%m-\%d)" | python3 /path/to/plot_multiproject.py && mv git_activity_multi_project_report_*.png ~/reports/month_$(date -d 'last month' +\%Y-\%m).png
```

### Analisi Avanzate con jq

**Trovare l'autore più produttivo:**

```bash
./git_stats_collector.sh 2025-11-01 2025-11-30 json | \
  jq -r '.[] | select(.author != "TOTALE") | "\(.total_commits) \(.author)"' | \
  sort -rn | head -1
```

**Giorni con più attività:**

```bash
./git_stats_collector.sh 2025-11-01 2025-11-30 json | \
  jq -r '.[] | .daily_data[] | "\(.lines) \(.date)"' | \
  sort -rn | head -5
```

**Estrai solo i commit totali per autore (multi-repo):**

```bash
./git_multiproject_stats_collector.sh --file repos.txt 2025-11-01 2025-11-30 | \
  jq -r 'group_by(.author) | map({author: .[0].author, total_commits: map(.commits) | add}) | sort_by(.total_commits) | reverse'
```

---

## 🔧 Personalizzazione

### File e cartelle da escludere

In entrambi i collector la lista è centralizzata in un unico array `EXCLUDE_PATHSPEC`
(prima era ripetuta in ogni query, con il rischio di modificarne solo una copia):

```bash
EXCLUDE_PATHSPEC=(
    ":(exclude)node_modules/*"
    ":(exclude)dist/*"
    # ... aggiungi qui le tue esclusioni
)
```

Per analizzare **solo** certi tipi di file, sostituisci il `.` nel pathspec del comando
`git log` con i pattern desiderati, es. `-- "*.java" "*.kt" "${EXCLUDE_PATHSPEC[@]}"`.

### Pesi delle metriche

In testa a `plot_git.py` e `plot_multiproject.py` (i due valori vanno tenuti allineati):

```python
DELETED_WEIGHT = 0.4      # quanto pesa una riga rimossa rispetto a una aggiunta
DAILY_CHURN_CAP = 1000    # tetto anti-outlier, PER GIORNO per autore
W_CHURN = 1.0             # peso del volume nell'indice composito
W_FILES = 0.5             # peso della dispersione su file
```

Alzare `W_FILES` premia chi tocca molti file (attenzione: è ciò che rendeva la vecchia
formula favorevole ai find/replace). Abbassare `DAILY_CHURN_CAP` appiattisce le giornate
di alto volume.

### Granularità temporale del report singolo

In `plot_git.py`, funzione `choose_bucket()`: le soglie 45 / 250 giorni decidono quando
passare da giornaliero a settimanale a mensile.

### Colori

In entrambi i plotter, lista `SERIES`. L'ordine **non è cosmetico**: è verificato per
separazione tra colori adiacenti anche in caso di deficit di visione dei colori. Se la
sostituisci con una palette tua, validala invece di scegliere a occhio, e mantieni la
regola di accorpare in "Altro" oltre l'ottava serie anziché generare tinte nuove.

### Escludere/includere i merge commit

I merge sono esclusi con `--no-merges`, presente ora in un solo punto per script (la
singola invocazione di `git log`).

---

## 📈 Metriche Calcolate

Non esiste un singolo numero che misuri il valore del lavoro di sviluppo. Per questo i
report mostrano **tre metriche affiancate** invece di un punteggio unico, e relegano
l'indice composito a metrica secondaria (visibile solo nella tabella di riepilogo).

### 1. Churn — volume di cambiamento

```txt
churn = righe_aggiunte + 0.4 × righe_rimosse
```

Le rimozioni **contano**: cancellare codice morto è lavoro reale. Il peso `0.4 < 1`
riflette il fatto che rimuovere costa in genere meno che scrivere. (Nella versione
precedente la metrica usava solo `added`, quindi un commit di sole cancellazioni
valeva esattamente zero.)

Il campo `lines = aggiunte + rimosse` resta nel JSON per retrocompatibilità.

### 2. Commit

- Ogni commit unico nel periodo, **esclusi i merge commit**
- Attribuiti all'autore con **match esatto** sul nome

### 3. Giorni attivi — la metrica più robusta

Numero di giorni distinti con almeno un commit. È l'indicatore più difficile da
distorcere: non è gonfiabile né da un singolo commit enorme né da tanti micro-commit,
e cattura la continuità del contributo meglio del volume.

### Indice composito (metrica secondaria)

```txt
indice = Σ giorni [ 1.0 × ln(1 + min(churn_giorno, 1000)) + 0.5 × ln(1 + file_distinti_giorno) ]
```

Tre proprietà sono deliberate e non vanno cambiate senza capirne l'effetto:

1. **Additivo, non moltiplicativo.** Nella forma a prodotto `ln(added) × ln(files)` un
   fattore a zero azzerava tutto, e i due termini si amplificavano a vicenda: un
   find/replace su 100 file valeva ~6.7x un fix algoritmico profondo in un solo file.
   Con la forma additiva quel rapporto scende a ~1.4x, e i pesi (`1.0` / `0.5`) rendono
   esplicito quanto conta la dispersione su file.
2. **Il tetto di 1000 righe è PER GIORNO.** Applicato a un aggregato di periodo (come
   faceva la versione precedente nel report multiprogetto) si saturava: su qualsiasi
   intervallo più lungo di pochi giorni `ln(1+1000)` diventava una costante per tutti,
   e l'indice finiva per misurare solo il numero di file toccati.
3. **`file_distinti` sono file, non modifiche.** Lo stesso file modificato in 3 commit
   conta 1, non 3. Prima si contavano le righe di `--numstat`, cioè gli eventi di
   modifica, il che rendeva la metrica in buona parte un proxy del numero di commit.

### Note Importanti

- **Whitespace changes** sono inclusi
- **File rinominati** appaiono come add+delete
- **File binari** contano come file toccati ma non contribuiscono alle righe
- **Refactoring massicci** possono gonfiare le metriche
- Le metriche sono **indicatori**, non misure assolute di produttività

---

## 🎯 Interpretazione dei Dati

### ⚠️ Cosa NON Fare

❌ **Non usare come KPI per valutazione performance**

- Nessuna di queste metriche misura qualità o valore
- Il refactoring appare come alta produttività
- Code review, design, mentoring e debugging difficile sono **strutturalmente invisibili**:
  un fix da 3 righe dopo due giorni di indagine conta come 3 righe

❌ **Non confrontare autori direttamente**

- Complessità delle task varia enormemente
- Bug fix piccoli ≠ feature grandi

❌ **Non trattare l'indice composito come un punteggio oggettivo**

- È un'indicazione **relativa**, con pesi scelti a mano (`1.0` churn / `0.5` file):
  cambiando i pesi cambia la classifica
- Non tiene conto della difficoltà tecnica delle modifiche
- Per questo è relegato alla tabella e non ha un grafico dedicato: se ti serve un solo
  numero, "giorni attivi" è più difficile da distorcere

❌ **Non confrontare valori tra periodi analizzati con versioni diverse dello strumento**

- Le formule sono cambiate (forma additiva, cancellazioni pesate, tetto per giorno):
  i punteggi dei report generati prima non sono confrontabili con quelli nuovi

### ✅ Cosa Fare

✓ **Usa per identificare trend**

- Picchi di attività prima di release
- Periodi di inattività inspiegati
- Distribuzione del carico nel tempo

✓ **Usa per retrospective di team**

- "Perché questo progetto ha richiesto così tanto effort?"
- "Chi ha lavorato su cosa e possiamo bilanciare meglio?"
- "Ci sono colli di bottiglia?"

✓ **Confronta le metriche tra loro, non guardarne una sola**

- Molto churn e pochi commit → cambiamenti grossi e rari
- Molti commit e poco churn → iterazione a piccoli passi
- Molti giorni attivi e churn modesto → contributo continuo (spesso il più prezioso, e
  quello che un punteggio basato sul volume nasconde)

✓ **Usa per planning**

- Velocity storica su progetti simili
- Stima di effort per nuove feature
- Allocazione risorse tra progetti

---

## 🚀 Estensioni Future

### Roadmap Possibili

- [ ] Export in formato CSV per Excel/Google Sheets
- [ ] Supporto per branch specifici (analizza feature branch)
- [ ] Filtri per tipo di file (solo backend, solo test, etc.)
- [ ] Dashboard interattiva HTML/JS
- [ ] Integrazione Slack/Discord per report automatici
- [ ] Analisi linguaggi di programmazione (LoC per linguaggio)
- [ ] Heatmap calendario stile GitHub
- [ ] Confronto velocity tra sprint
- [ ] API REST per query dati storici
- [ ] Support per GitLab/Bitbucket API (oltre a git locale)

---

## 📚 Shortcuts Utili

> I comandi più comuni sono già in cima al documento nella [🚀 Guida Rapida](#-guida-rapida). Qui trovi
> solo alias/funzioni bash opzionali per velocizzare l'uso quotidiano.

```bash
# Alias nel .bashrc
alias gitstats='~/tools/git_stats_collector.sh'
alias gitstats-multi='~/tools/git_multiproject_stats_collector.sh'

# Funzione per ultimo mese
last_month_report() {
  local start=$(date -d "$(date +%Y-%m-01) -1 month" +%Y-%m-%d)
  local end=$(date -d "$(date +%Y-%m-01) -1 day" +%Y-%m-%d)
  ./git_stats_collector.sh "$start" "$end" json | python3 plot_git.py
}

# Funzione per ultima settimana
last_week_report() {
  local start=$(date -d "last monday -7 days" +%Y-%m-%d)
  local end=$(date -d "last sunday" +%Y-%m-%d)
  ./git_stats_collector.sh "$start" "$end" json | python3 plot_git.py
}
```

---

## ❓ FAQ

### Posso usare lo script su Windows?

Gli script bash richiedono un ambiente Unix-like. Opzioni:

- WSL (Windows Subsystem for Linux) ✅ Raccomandato
- Git Bash (limitato, potrebbe non funzionare `date -d`)
- Cygwin

### Gli script funzionano con Git LFS?

Sì, gli script analizzano la storia Git standard. File LFS appaiono come modifiche normali.

### Posso analizzare repository remoti?

No direttamente. Devi prima clonare localmente:

```bash
git clone https://github.com/user/repo.git /tmp/repo
./git_stats_collector.sh 2025-11-01 2025-11-30 json
```

### Come gestire autori con email diverse?

Git usa il nome da `git config user.name`. Se un autore ha commit con nomi diversi, appariranno separati. Soluzione:

```bash
# Unifica con .mailmap nel repository
# File .mailmap:
# Preferred Name <preferred@email.com> Old Name <old@email.com>
```

### Gli script influenzano il repository?

No, sono **read-only**. Eseguono solo `git log`, non modificano nulla.

---

## 🚀 Comandi Semplificati (gitstats / gitstats-multi)

`gitstats` e `gitstats-multi` sono i comandi pensati per l'uso quotidiano — quelli suggeriti nella
[Guida Rapida](#-guida-rapida) in cima a questo documento. Sono wrapper già pronti nel repository
(`gitstat.sh` e `gitstat-multi.sh`) che fanno da soli la pipe collector → plot, così non devi ricordare
la sintassi completa dei due script principali né il simbolo `|`:

- `gitstats <INIZIO> <FINE> [autore]` → equivale a `git_stats_collector.sh ... json | plot_git.py`
- `gitstats-multi <INIZIO> <FINE> [opzioni] [percorsi...]` → equivale a `git_multiproject_stats_collector.sh ... | plot_multiproject.py`

Entrambi supportano `--fetch`; `gitstats` supporta anche `--repo <path|url>` e `gitstats-multi` accetta
URL Git direttamente come percorso (stesse opzioni dei rispettivi script principali — vedi
[Versione Singolo Repository](#-versione-singolo-repository) e [Versione Multi-Repository](#-versione-multi-repository)
per l'elenco completo).

### Installazione

Se hai installato il **pacchetto Debian** (vedi la sezione Release del repository), `gitstats` e
`gitstats-multi` sono già disponibili: salta questa sezione.

Altrimenti, dalla cartella dove hai clonato questo repository:

```bash
sudo ln -sf "$(pwd)/git_stats_collector.sh" /usr/local/bin/git_stats_collector.sh
sudo ln -sf "$(pwd)/git_multiproject_stats_collector.sh" /usr/local/bin/git_multiproject_stats_collector.sh
sudo ln -sf "$(pwd)/plot_git.py" /usr/local/bin/plot_git.py
sudo ln -sf "$(pwd)/plot_multiproject.py" /usr/local/bin/plot_multiproject.py
sudo ln -sf "$(pwd)/gitstat.sh" /usr/local/bin/gitstats
sudo ln -sf "$(pwd)/gitstat-multi.sh" /usr/local/bin/gitstats-multi

chmod +x git_stats_collector.sh git_multiproject_stats_collector.sh plot_git.py plot_multiproject.py gitstat.sh gitstat-multi.sh
```

(i link puntano ai file del repository: aggiornare il repository — `git pull` — aggiorna anche i comandi installati, senza bisogno di reinstallare nulla)

### Utilizzo

```bash
# Singolo repository, nella sua cartella
gitstats 2025-12-01 2025-12-31
gitstats 2025-12-01 2025-12-31 "Mario Rossi"          # filtro autore
gitstats --repo https://github.com/org/repo.git 2025-12-01 2025-12-31  # repository remoto

# Multi-repository, da qualsiasi posizione
gitstats-multi 2025-12-01 2025-12-31 ~/repo1 ~/repo2
gitstats-multi --file repos.txt 2025-12-01 2025-12-31
```
