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
# -> genera git_impact_multi_project_report.png

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
| Grafico (in pipe) | `python3 plot_git.py` → 1 grafico | `python3 plot_multiproject.py` → 3 grafici |

Dettagli completi di ogni opzione più sotto: [Versione Singolo Repository](#-versione-singolo-repository), [Versione Multi-Repository](#-versione-multi-repository).

---

## Componenti

### Versione Singolo Repository

- **`git_stats_collector.sh`** - Analizza un repository alla volta con dettaglio giornaliero
- **`plot_git.py`** - Genera grafico stacked bar per singolo progetto. Supporta anche il raggruppamento degli autori tramite un file opzionale `git-activity-aliases.json`.

### Versione Multi-Repository

- **`git_multiproject_stats_collector.sh`** - Analizza più repository contemporaneamente
- **`plot_multiproject.py`** - Genera 3 grafici comparativi tra progetti. Supporta anche il raggruppamento degli autori tramite un file opzionale `git-activity-aliases.json`.

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
4. Nella directory di sistema (`/etc/git-activity-reports/git-activity-aliases.json`)

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
| 4         | `autore`      | ✗            | Filtra per autore specifico     | tutti   |

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

Analizza più repository contemporaneamente con statistiche **aggregate per progetto** utilizzando l'Impact Score come metrica principale (calcolato come log(lines + 1) * log(files + 1)), ideale per:

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

**Output:** File `git_impact_multi_project_report.png` con 3 grafici.

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
mv git_impact_multi_project_report.png q3_portfolio.png

# Q4: Multi-repo
./git_multiproject_stats_collector.sh --file all-repos.txt 2025-10-01 2025-12-31 \
  | python3 plot_multiproject.py
mv git_impact_multi_project_report.png q4_portfolio.png

# Dettaglio Q4 su progetto strategico
cd ~/progetti/strategic-project
./git_stats_collector.sh 2025-10-01 2025-12-31 json | python3 plot_git.py
mv git_stats.png q4_strategic_daily.png
```

---

## 🎨 Interpretazione dei Grafici

### Grafico Singolo Repository (Stacked Bar Chart)

![Esempio: Attività giornaliera]

**Come leggerlo:**

- **Asse X:** Date (granularità giornaliera)
- **Asse Y:** Righe totali modificate (aggiunte + eliminate)
- **Colori:** Ogni autore ha un colore diverso
- **Altezza barra:** Attività totale del giorno
- **Sezioni colorate:** Contributo di ogni autore

**Insights:**

- Giorni con picchi di attività (rilasci, refactoring)
- Distribuzione del carico di lavoro
- Periodi di inattività (weekend, festività)
- Contributo relativo degli sviluppatori

### Grafici Multi-Repository

#### 1. Contributo per Progetto e Autore (Stacked Bar)

- Confronto diretto tra progetti in termini di Impact Score
- Chi lavora su cosa (basato sull'Impact Score)
- Identificazione progetti "hot" (ad alto impatto)

#### 2. Distribuzione per Progetto (Donut)

- Percentuale di Impact Score per repository
- Sbilanciamenti nel portfolio
- Focus del team in termini di impatto

#### 3. Classifica Autori (Bar)

- Impact Score totale per ciascun autore
- Contributo totale di ogni membro in termini di impatto
- Identificazione top contributors in termini di impatto

---

## 📊 Output Format Details

### JSON Singolo Repository

```json
[
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
        "deleted": 170
      }
    ]
  }
]
```

### JSON Multi-Repository

```json
[
  {
    "project": "backend",
    "author": "Mario Rossi",
    "lines": 3450,
    "commits": 24
  },
  {
    "project": "backend",
    "author": "Laura Bianchi",
    "lines": 2890,
    "commits": 18
  }
]
```

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

**Nota:** I dati raccolti da questi percorsi vengono elaborati dallo script Python `plot_multiproject.py` che:

1) Calcola un Impact Score basato sui campi `added` e `files` secondo la formula: `ln(min(added, 1000) + 1) * ln(files + 1)`
2) Supporta il raggruppamento degli autori attraverso un file opzionale `git-activity-aliases.json` nella stessa directory

Il file `git-activity-aliases.json` permette di raggruppare diversi nomi di autori Git sotto un unico nome comune, utile quando lo stesso sviluppatore ha contribuito con nomi diversi. Esempio:

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
4. Nella directory di sistema (`/etc/git-activity-reports/git-activity-aliases.json`)

Se nessun file di configurazione esiste, lo script continuerà a funzionare normalmente senza raggruppare gli autori.

---

## Output JSON

Lo script bash produce un array JSON con questa struttura:

```json
[
  {
    "project": "repoA",
    "author": "Mario Rossi",
    "lines": 1250,
    "commits": 15,
    "added": 800,
    "files": 12
  },
  {
    "project": "repoA",
    "author": "Laura Bianchi",
    "lines": 890,
    "commits": 12,
    "added": 650,
    "files": 8
  },
  {
    "project": "repoB",
    "author": "Mario Rossi",
    "lines": 450,
    "commits": 8,
    "added": 300,
    "files": 5
  }
]
```

**Campi:**

- `project`: Nome del repository (estratto dal nome della cartella)
- `author`: Nome dell'autore Git (da `git config user.name`)
- `lines`: Righe totali modificate (aggiunte + eliminate)
- `commits`: Numero di commit (escludendo merge commits)
- `added`: Righe aggiunte (usato per calcolare l'Impact Score)
- `files`: Numero di file modificati (usato per calcolare l'Impact Score)

**Nota:** Gli script Python `plot_multiproject.py` e `plot_git.py` supportano il raggruppamento degli autori attraverso un file opzionale `git-activity-aliases.json` che permette di mappare diversi nomi di autori Git sotto un unico nome comune. Se presente il campo `author_name` nel JSON, verrà utilizzato come priorità rispetto al campo `author`. Inoltre, lo script `plot_multiproject.py` calcola un campo aggiuntivo `relevance` (Impact Score) utilizzando la formula: `ln(min(added, 1000) + 1) * ln(files + 1)` quando `commits` e `files` sono maggiori di zero.

---

## Visualizzazioni Generate

Lo script Python crea 3 grafici in un'unica immagine:

### 1. **Contributo per Progetto e Autore** (Stacked Bar)

- Mostra la distribuzione dell'Impact Score (calcolato come log(lines + 1) * log(files + 1))
- Ogni barra rappresenta un progetto
- I colori distinguono gli autori

### 2. **Distribuzione per Progetto** (Donut Chart)

- Percentuale dell'Impact Score totale per progetto
- Utile per identificare i repository con maggiore impatto

### 3. **Classifica Autori** (Bar Chart)

- Impact Score totale per ogni autore
- Somma di tutti i progetti
- Ordinamento decrescente

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
python3 plot_multiproject.py < q3.json  # genera git_multi_project_report.png
mv git_multi_project_report.png q3_report.png

python3 plot_multiproject.py < q4.json
mv git_multi_project_report.png q4_report.png
```

---

## Note Tecniche

### Commit Considerati

- **Inclusi:** Commit standard con modifiche ai file
- **Esclusi:** Merge commits (flag `--no-merges`)
- **Metrica:** Somma di righe aggiunte + righe eliminate

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

### Problemi Comuni - Singolo Repository

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
0 8 1 * * /path/to/git_multiproject_stats_collector.sh --file ~/configs/all-repos.txt "$(date -d 'last month' +\%Y-\%m-01)" "$(date -d 'yesterday' +\%Y-\%m-\%d)" | python3 /path/to/plot_multiproject.py && mv git_multi_project_report.png ~/reports/month_$(date -d 'last month' +\%Y-\%m).png
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

### Escludere Merge Commits

Gli script già escludono i merge commits di default. Per includerli, rimuovi `--no-merges` nei comandi git:

```bash
# In git_multiproject_stats_collector.sh, linea ~93
git log --since="$START_DATE" --until="$END_DATE" --author="$AUTHOR_NAME" ...
# Rimuovi --no-merges se vuoi includerli
```

### Filtrare per Tipo di File

Modifica `get_lines()` in `git_stats_collector.sh`:

```bash
get_lines() {
    local date_str="$1"
    local cmd=(git log --since="$date_str 00:00:00" --until="$date_str 23:59:59" --pretty="format:" --numstat -- "*.java" "*.kt")  # Solo Java/Kotlin
    # ... resto della funzione
}
```

### Modificare Colori dei Grafici

In `plot_git.py` o `plot_multiproject.py`:

```python
# Cambia colormap
pivot_df.plot(kind='bar', stacked=True, colormap='viridis')  # Invece di 'tab10'

# Colori personalizzati
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
pivot_df.plot(kind='bar', stacked=True, color=colors)
```

---

## 📈 Metriche Calcolate

### Righe Modificate

```txt
lines = righe_aggiunte + righe_eliminate
```

- Riflette il volume totale di cambiamento
- Non distingue tra aggiunte e rimozioni nel totale
- Include file binari convertiti in numstat

### Impact Score (Relevance)

Nello script `plot_multiproject.py`, viene calcolato un Impact Score aggiuntivo utilizzando la formula:

```txt
relevance = ln(min(added, 1000) + 1) * ln(files + 1) se commits > 0 e files > 0
relevance = 0 altrimenti
```

Dove:

- `added`: righe aggiunte (da git log --numstat)
- `files`: numero di file modificati in quel periodo
- `commits`: numero di commit effettuati

Questa metrica fornisce un'indicazione dell'impatto relativo del lavoro, considerando sia la quantità di codice aggiunto che il numero di file interessati. Sono stati implementati due importanti accorgimenti per migliorare la qualità della metrica:

1. **Tetto massimo alle righe**: Viene applicato un limite massimo di 1000 righe aggiunte per periodo per evitare che singoli grandi commit dominino la metrica
2. **Doppio logaritmo**: Vengono applicate trasformazioni logaritmiche sia al numero di righe che al numero di file interessati, per ridurre l'impatto di operazioni di trova/sostituisci su molti file

### Commit

- Ogni commit SHA unico nel periodo
- **Esclude merge commits** per evitare duplicazioni
- Include sia commit pushed che locali

### Note Importanti

- **Whitespace changes** sono inclusi
- **File rinominati** appaiono come add+delete
- **Refactoring massicci** possono gonfiare le metriche
- Le metriche sono **indicatori**, non misure assolute di produttività

---

## 🎯 Interpretazione dei Dati

### ⚠️ Cosa NON Fare

❌ **Non usare come KPI per valutazione performance**

- Le righe di codice e l'Impact Score non misurano qualità o valore
- Refactoring appare come alta produttività
- Deletion di codice legacy è positivo ma riduce metriche

❌ **Non confrontare autori direttamente**

- Complessità delle task varia enormemente
- Bug fix piccoli ≠ feature grandi
- Code review e mentoring non appare

❌ **Non considerare l'Impact Score come indicatore assoluto**

- L'Impact Score è un'indicazione relativa, non una misura di qualità del codice
- Non tiene conto della difficoltà tecnica delle modifiche
- Può essere influenzato da fattori esterni non correlati alla produttività

### ✅ Cosa Fare

✓ **Usa per identificare trend**

- Picchi di attività prima di release
- Periodi di inattività inspiegati
- Distribuzione del carico nel tempo

✓ **Usa per retrospective di team**

- "Perché questo progetto ha richiesto così tanto effort?"
- "Chi ha lavorato su cosa e possiamo bilanciare meglio?"
- "Ci sono colli di bottiglia?"

✓ **Usa l'Impact Score per confronti relativi**

- Identificare progetti con maggiore attività di sviluppo
- Capire dove si concentrano gli sforzi del team
- Supportare decisioni di allocazione risorse

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
