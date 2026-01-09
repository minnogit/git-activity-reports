# Git Stats Collector - Documentazione Completa

Sistema completo per analizzare e visualizzare statistiche Git, disponibile in due versioni: **singolo repository** e **multi-repository**.

## Componenti

### Versione Singolo Repository

- **`git_stats_collector.sh`** - Analizza un repository alla volta con dettaglio giornaliero
- **`plot_git.py`** - Genera grafico stacked bar per singolo progetto

### Versione Multi-Repository

- **`git_multiproject_stats_collector.sh`** - Analizza più repository contemporaneamente
- **`plot_multiproject.py`** - Genera 3 grafici comparativi tra progetti

---

## Requisiti

### Script Bash

- Bash 4.0+
- Git installato e configurato
- Accesso ai repository da analizzare
- `date` command con supporto `-d` (GNU coreutils)

### Script Python

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

---

## 📊 Versione Singolo Repository

### Panoramica

Analizza un singolo repository Git con dettaglio **giornaliero**, ideale per:

- Report personali di attività
- Analisi sprint su un progetto specifico
- Monitoraggio giornaliero del team su un repository

### Sintassi

```bash
./git_stats_collector.sh <DATA_INIZIO> <DATA_FINE> [formato] [autore]
```

### Parametri

| Posizione | Parametro | Obbligatorio | Descrizione | Default |
|-----------|-----------|--------------|-------------|---------|
| 1 | `DATA_INIZIO` | ✓ | Data inizio (YYYY-MM-DD) | - |
| 2 | `DATA_FINE` | ✓ | Data fine (YYYY-MM-DD) | - |
| 3 | `formato` | ✗ | Formato output: `text` o `json` | `text` |
| 4 | `autore` | ✗ | Filtra per autore specifico | tutti |

### Opzioni Disponibili

| Opzione | Argomento | Descrizione |
|---------|-----------|-------------|
| `--fetch` | - | Abilita l'aggiornamento del repository con git fetch |
| `-h, --help` | - | Mostra l'help |

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

### Sintassi Completa

```bash
./git_multiproject_stats_collector.sh [OPZIONI] <DATA_INIZIO> <DATA_FINE> [percorsi...]
```

### Opzioni Disponibili

| Opzione | Argomento | Descrizione |
|---------|-----------|-------------|
| `--file` | `<file>` | Legge i percorsi dei repository da file (uno per riga) |
| `--start` | `<data>` | Data di inizio periodo (formato: YYYY-MM-DD) |
| `--end` | `<data>` | Data di fine periodo (formato: YYYY-MM-DD) |
| `--fetch` | - | Abilita l'aggiornamento dei repository con git fetch |
| `-h, --help` | - | Mostra l'help |

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

| Caratteristica | Singolo Repository | Multi-Repository |
|----------------|-------------------|------------------|
| **Granularità** | Giornaliera | Aggregata per progetto |
| **Scope** | Un repository alla volta | Multipli contemporaneamente |
| **Formato output** | text/json | json (solo) |
| **Filtro autore** | Sì, via parametro | No (mostra tutti) |
| **Grafici generati** | 1 (stacked bar) | 3 (bar, donut, ranking) |
| **Uso tipico** | Sprint review, analisi personale | Portfolio review, confronto progetti |
| **Esecuzione** | Nella cartella del repo | Da qualsiasi posizione |

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

**Nota:** I dati raccolti da questi percorsi vengono elaborati dallo script Python `plot_multiproject.py` che calcola un Impact Score basato sui campi `added` e `files` secondo la formula: `ln(min(added, 1000) + 1) * ln(files + 1)`.

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

**Nota:** Lo script Python `plot_multiproject.py` calcola un campo aggiuntivo `relevance` (Impact Score) utilizzando la formula: `ln(min(added, 1000) + 1) * ln(files + 1)` quando `commits` e `files` sono maggiori di zero.

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

Questa metrica fornisce un'indicazione dell'impatto relativo del lavoro, considerando sia la quantità di codice aggiunto che il numero di file interessati, con una capatura a 1000 righe aggiunte per evitare che singoli grandi commit dominino la metrica.

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

## 📚 Quick Reference

### Comandi Più Comuni

```bash
# Report testuale veloce (ultimo mese)
cd ~/progetto && ./git_stats_collector.sh 2025-11-01 2025-11-30

# Grafico singolo repo
cd ~/progetto && ./git_stats_collector.sh 2025-11-01 2025-11-30 json | python3 plot_git.py

# Grafico multi-repo
./git_multiproject_stats_collector.sh --file repos.txt 2025-11-01 2025-11-30 | python3 plot_multiproject.py

# Report autore specifico
cd ~/progetto && ./git_stats_collector.sh 2025-11-01 2025-11-30 text "Nome Cognome"

# Salva dati per dopo
cd ~/progetto && ./git_stats_collector.sh 2025-11-01 2025-11-30 json > backup.json
```

### Shortcuts Utili

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

## 🚀 Comandi Semplificati

Per semplificare ulteriormente l'uso degli strumenti, puoi installare gli script autonomi che nascondono i percorsi complessi.

### Installazione

Dopo aver copiato o linkato gli script principali in `/usr/local/bin`, puoi creare questi comandi semplificati:

```bash
# Script per singolo repository
sudo tee /usr/local/bin/gitstats > /dev/null << 'EOF'
#!/bin/bash

# ===============================================
# GIT STATS - Singolo Repository
# ===============================================
#
# DESCRIZIONE:
#   Comando semplificato per analizzare e visualizzare statistiche Git
#   di un singolo repository con dettaglio giornaliero.
#
# UTILIZZO:
#   gitstats <DATA_INIZIO> <DATA_FINE> [autore]
#
# PARAMETRI:
#   DATA_INIZIO    Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
#   DATA_FINE      Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
#   autore         Filtra per autore specifico (opzionale)
#
# ESEMPI:
#   # Report per tutti gli autori
#   gitstats 2025-12-01 2025-12-31
#
#   # Report per autore specifico
#   gitstats 2025-12-01 2025-12-31 "Mario Rossi"
#
# REQUISITI:
#   - git_stats_collector.sh e plot_git.py devono essere disponibili globalmente
#   - Python3 con pandas e matplotlib installati
#   - Essere in una cartella di repository Git
#
# AUTORE: Michele Innocenti
# VERSIONE: 1.0
# DATA: Gennaio 2026
# ===============================================

if [[ $# -lt 2 ]]; then
    echo "Uso: $0 <DATA_INIZIO> <DATA_FINE> [autore]"
    echo "Esempio: $0 2025-12-01 2025-12-31"
    echo "Esempio con autore: $0 2025-12-01 2025-12-31 'Mario Rossi'"
    exit 1
fi

START_DATE="$1"
END_DATE="$2"
AUTHOR_FILTER="${3:-}"

# Verifica che siamo in un repository git
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Errore: Non sei in un repository Git"
    exit 1
fi

# Verifica che gli strumenti siano disponibili
if ! command -v git_stats_collector.sh >/dev/null 2>&1; then
    echo "Errore: git_stats_collector.sh non trovato globalmente"
    exit 1
fi

if ! command -v plot_git.py >/dev/null 2>&1; then
    echo "Errore: plot_git.py non trovato globalmente"
    exit 1
fi

# Esegui il comando con o senza filtro autore
if [[ -n "$AUTHOR_FILTER" ]]; then
    git_stats_collector.sh "$START_DATE" "$END_DATE" json "$AUTHOR_FILTER" | python3 plot_git.py
else
    git_stats_collector.sh "$START_DATE" "$END_DATE" json | python3 plot_git.py
fi
EOF

sudo chmod +x /usr/local/bin/gitstats
```

E per il multi-repository:

```bash
# Script per multi repository
sudo tee /usr/local/bin/gitstats-multi > /dev/null << 'EOF'
#!/bin/bash

# ===============================================
# GIT STATS MULTI - Multi Repository
# ===============================================
#
# DESCRIZIONE:
#   Comando semplificato per analizzare e visualizzare statistiche Git
#   di più repository contemporaneamente.
#
# UTILIZZO:
#   gitstats-multi <DATA_INIZIO> <DATA_FINE> [percorso1] [percorso2] ...
#
# PARAMETRI:
#   DATA_INIZIO    Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
#   DATA_FINE      Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
#   percorsoN      Percorsi ai repository Git (opzionali, default: corrente)
#
# ESEMPI:
#   # Analizza repository corrente
#   gitstats-multi 2025-12-01 2025-12-31
#
#   # Analizza repository specifici
#   gitstats-multi 2025-12-01 2025-12-31 ~/progetti/repo1 ~/progetti/repo2
#
#   # Con file di configurazione
#   gitstats-multi --file progetti.txt 2025-12-01 2025-12-31
#
# REQUISITI:
#   - git_multiproject_stats_collector.sh e plot_multiproject.py devono essere disponibili globalmente
#   - Python3 con pandas e matplotlib installati
#
# AUTORE: Michele Innocenti
# VERSIONE: 1.0
# DATA: Gennaio 2026
# ===============================================

if [[ $# -lt 2 ]]; then
    echo "Uso: $0 <DATA_INIZIO> <DATA_FINE> [opzioni] [percorsi...]"
    echo "Esempio: $0 2025-12-01 2025-12-31"
    echo "Esempio con repository specifici: $0 2025-12-01 2025-12-31 ~/repo1 ~/repo2"
    echo "Esempio con file: $0 --file repos.txt 2025-12-01 2025-12-31"
    exit 1
fi

# Verifica che gli strumenti siano disponibili
if ! command -v git_multiproject_stats_collector.sh >/dev/null 2>&1; then
    echo "Errore: git_multiproject_stats_collector.sh non trovato globalmente"
    exit 1
fi

if ! command -v plot_multiproject.py >/dev/null 2>&1; then
    echo "Errore: plot_multiproject.py non trovato globalmente"
    exit 1
fi

# Esegui il comando
git_multiproject_stats_collector.sh "$@" | python3 plot_multiproject.py
EOF

sudo chmod +x /usr/local/bin/gitstats-multi
```

### Utilizzo

Dopo l'installazione, puoi usare i comandi semplificati:

#### Singolo Repository

```bash
# Nella cartella di un repository Git
gitstats 2025-12-01 2025-12-31
```

```bash
# Con filtro autore
gitstats 2025-12-01 2025-12-31 "Mario Rossi"
```

#### Multi-Repository

```bash
# Da qualsiasi posizione
gitstats-multi 2025-12-01 2025-12-31 ~/repo1 ~/repo2
```

```bash
# Con file di configurazione
gitstats-multi --file repos.txt 2025-12-01 2025-12-31
```

Questi comandi nascondono la complessità dei percorsi relativi e forniscono un'interfaccia pulita per l'uso quotidiano degli strumenti di analisi Git.
