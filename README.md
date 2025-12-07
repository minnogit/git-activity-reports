# 📊 git-activity-reports

**Analizzatore di attività Git multi-progetto che genera report di produttività aggregati (righe di codice, commit) e dashboard grafiche tramite Bash e Python.**

Questo set di script offre due modalità di analisi per misurare la produttività e la distribuzione del carico di lavoro nel tempo e tra diversi progetti Git.

## 🚀 Caratteristiche Principali

  * **Analisi Giornaliera Dettagliata (`git_stats_collector.sh`):** Calcola righe aggiunte/eliminate e commit per giorno e per autore in un singolo repository.
  * **Analisi Aggregata Multi-Progetto (`git_multiproject_stats_collector.sh`):** Raccoglie le statistiche totali di righe e commit per autore su una serie di repository in un dato intervallo.
  * **Visualizzazione Grafica:** Genera grafici a barre impilate, grafici a torta e classifiche per autore, rendendo l'analisi immediata.

-----

## 🛠️ Requisiti

Per eseguire gli script è necessario avere installato:

1.  **Bash** (Sistema operativo Linux o macOS).
2.  **Git** (il comando `git` deve essere disponibile nel PATH).
3.  **Python 3.x**.
4.  **Librerie Python** (installabili tramite `pip`):
    ```bash
    pip install pandas matplotlib
    ```

### Installazione su Linux Debian

Se stai utilizzando Debian o una distribuzione basata su Debian (come Ubuntu), puoi installare tutti i pacchetti necessari utilizzando `apt`:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-pandas python3-matplotlib git
```

Questo installerà Python 3, pip, le librerie pandas e matplotlib, e git. Le librerie Python sono disponibili come pacchetti Debian, quindi non è necessario utilizzare `pip` per questo progetto.

#### Opzione alternativa: Utilizzo di un ambiente virtuale

Se preferisci isolare le dipendenze o utilizzare versioni più recenti delle librerie, puoi creare un ambiente virtuale Python:

```bash
python3 -m venv git-activity-env
source git-activity-env/bin/activate
pip install pandas matplotlib
```

Quando vuoi disattivare l'ambiente virtuale, usa `deactivate`.

-----

## 💻 Istruzioni per l'Uso

Tutte le analisi si basano sul concetto di **pipeline** (`|`), dove l'output JSON dello script Bash viene passato direttamente allo script Python per la visualizzazione.

### 1\. Modalità: Dettaglio Giornaliero (Singolo Progetto)

Questa modalità usa gli script originali e genera un grafico a barre dove ogni barra è un giorno ed è suddivisa per autore.

| Script di Raccolta | Script di Visualizzazione | Output |
| :--- | :--- | :--- |
| `git_stats_collector.sh` | `plot_git.py` | `git_stats.png` |

#### 1.1 Esecuzione

Spostati nella directory del progetto Git che vuoi analizzare ed esegui il comando, specificando l'intervallo e il formato **`json`**:

```bash
# Sintassi: ./git_stats_collector.sh <DATA_INIZIO> <DATA_FINE> json
./g.sh 2025-11-20 2025-11-28 json | python3 plot_git.py
```

### 2\. Modalità: Report Aggregato (Multi-Progetto)

Questa modalità raccoglie le statistiche totali (non giornaliere) da più repository e le consolida in un unico report grafico.

| Script di Raccolta | Script di Visualizzazione | Output |
| :--- | :--- | :--- |
| `git_multiproject_stats_collector.sh` | `plot_multiproject.py` | `git_multi_project_report.png` |

#### 2.1 Esecuzione

Esegui il comando dalla root del tuo ambiente di lavoro, specificando l'intervallo di tempo e i **percorsi completi** di tutti i repository da analizzare:

```bash
# Sintassi: ./git_stats_collector.sh <START> <END> /percorso/a/repo1 /percorso/a/repo2
./git_multiproject_stats_collector.sh 2025-01-01 2025-03-31 ~/Workspace/progetto-web ~/Workspace/progetto-api | python3 plot_multiproject.py
```

#### 2.2 Grafici Generati

Lo script `plot_multiproject.py` genera un'unica immagine con tre sotto-grafici:

1.  **Stacked Bar Chart:** Contributo di righe per autore, suddiviso per progetto.
2.  **Donut Chart:** Percentuale di righe modificate per progetto (distribuzione del carico di lavoro).
3.  **Bar Chart:** Righe modificate totali per autore (Classifica di produttività).

-----

## 📝 Note sulla Configurazione

  * **Permessi:** Assicurati che gli script Bash (`.sh`) abbiano i permessi di esecuzione:
    ```bash
    chmod +x *.sh
    ```
  * **Gestione Autori:** Gli script gestiscono automaticamente i nomi degli autori contenenti spazi (es. "Mario Rossi").
  * **Merge Commit:** Per default, tutti i calcoli di righe (`--numstat`) **ignorano i commit di merge** (`--no-merges`) per evitare il doppio conteggio e mantenere metriche di sviluppo pulite.

-----

## 📜 Licenza

Questo progetto è rilasciato sotto la Licenza **MIT**. Vedi il file `LICENSE` per maggiori dettagli.