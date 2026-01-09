#!/bin/bash

# ===============================================
# GIT MULTI-PROJECT STATS COLLECTOR
# ===============================================
#
# DESCRIZIONE:
#   Analizza l'attività Git su multipli repository contemporaneamente.
#   Genera statistiche aggregate per progetto e autore nel periodo specificato.
#
# UTILIZZO:
#   ./git_multiproject_stats_collector.sh [OPZIONI] <DATA_INIZIO> <DATA_FINE> [percorsi...]
#
# OPZIONI:
#   --file <file>    Legge i percorsi dei repository da file (uno per riga)
#   --start <data>   Data di inizio periodo (alternativa a posizionale)
#   --end <data>     Data di fine periodo (alternativa a posizionale)
#   --fetch          Abilita l'aggiornamento dei repository con git fetch
#   -h, --help       Mostra questo help
#
# PARAMETRI POSIZIONALI:
#   DATA_INIZIO      Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
#   DATA_FINE        Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
#   percorsi...      Percorsi ai repository Git (opzionale se si usa --file)
#
# ESEMPI:
#   # Analisi di repository specifici
#   ./git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 ~/repo1 ~/repo2
#
#   # Repository da file di configurazione
#   ./git_multiproject_stats_collector.sh --file progetti.txt 2025-11-01 2025-11-30
#
#   # Con opzioni per le date
#   ./git_multiproject_stats_collector.sh --start 2025-11-01 --end 2025-11-30 ~/repo1
#
#   # Pipeline completa con visualizzazione
#   ./git_multiproject_stats_collector.sh --file repos.txt 2025-11-01 2025-11-30 \
#     | python3 plot_multiproject.py
#
# FORMATO FILE PERCORSI:
#   Il file specificato con --file deve contenere un percorso per riga:
#
#     # Commenti sono ignorati
#     ~/progetti/backend
#     ~/progetti/frontend
#     /var/www/api-service
#     # Percorsi con spazi sono supportati
#     /home/user/My Projects/mobile-app
#
#   Note sul file:
#   - Un percorso per riga
#   - Supporta tilde (~) per home directory
#   - Linee vuote e commenti (#) sono ignorati
#   - Percorsi con spazi sono supportati
#
# OUTPUT JSON:
#   [
#     {
#       "project": "backend",
#       "author": "Mario Rossi",
#       "lines": 3450,
#       "commits": 24
#     },
#     {
#       "project": "backend",
#       "author": "Laura Bianchi",
#       "lines": 2890,
#       "commits": 18
#     }
#   ]
#
# NOTE:
#   - Lo script può essere eseguito da qualsiasi directory
#   - Ogni percorso deve puntare a un repository Git valido (.git presente)
#   - Repository non validi vengono saltati con warning
#   - I merge commits sono esclusi dalle statistiche
#   - Le righe totali sono calcolate come: aggiunte + eliminate
#   - Il nome del progetto è estratto dal nome della cartella
#   - L'output è sempre in formato JSON (per uso con plot_multiproject.py)
#   - Di default, i repository non vengono aggiornati con git fetch (usa --fetch per abilitare)
#   - In caso di problemi di rete, vengono analizzati solo i commit locali
#
# CASI D'USO:
#   - Confronto attività tra progetti diversi
#   - Report di team distribuiti su più repository
#   - Analisi portfolio completo di progetti
#   - Sprint review multi-progetto
#   - Identificazione di sbilanciamenti nel carico di lavoro
#
# REQUISITI:
#   - Bash 4.0+
#   - Git installato e configurato
#   - Accesso in lettura ai repository da analizzare
#   - GNU coreutils (comando date con opzione -d)
#
# PERFORMANCE:
#   - Repository grandi (>10K commits) richiedono più tempo
#   - Consigliato: max 10-15 repository per esecuzione
#   - Per analisi massive, considerare esecuzioni parallele
#
# TROUBLESHOOTING:
#   - Se un percorso viene saltato, verifica la presenza di .git
#   - Per percorsi con spazi, usa il formato --file
#   - JSON malformato: verifica nomi autori con caratteri speciali
#
# AUTORE: Michele Innocenti
# VERSIONE: 2.0
# DATA: Dicembre 2025
# ===============================================

# Parsing delle opzioni
PROJECT_FILE=""
START_DATE=""
END_DATE=""
FETCH_ENABLED=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --file)
            if [[ -z "$2" || "$2" =~ ^- ]]; then
                echo "Errore: --file richiede un argomento." >&2
                exit 1
            fi
            PROJECT_FILE="$2"
            shift 2
            ;;
        --start)
            START_DATE="$2"
            shift 2
            ;;
        --end)
            END_DATE="$2"
            shift 2
            ;;
        --fetch)
            FETCH_ENABLED=true
            shift
            ;;
        -h|--help)
            cat << 'EOF'
UTILIZZO:
  ./git_multiproject_stats_collector.sh [OPZIONI] <DATA_INIZIO> <DATA_FINE> [percorsi...]

OPZIONI:
  --file <file>    Legge i percorsi dei repository da file (uno per riga)
  --start <data>   Data di inizio periodo (alternativa a posizionale)
  --end <data>     Data di fine periodo (alternativa a posizionale)
  --fetch          Abilita l'aggiornamento dei repository con git fetch
  -h, --help       Mostra questo help

PARAMETRI POSIZIONALI:
  DATA_INIZIO      Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
  DATA_FINE        Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
  percorsi...      Percorsi ai repository Git (opzionale se si usa --file)

ESEMPI:
  # Analisi di repository specifici
  ./git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 ~/repo1 ~/repo2

  # Repository da file di configurazione
  ./git_multiproject_stats_collector.sh --file progetti.txt 2025-11-01 2025-11-30

  # Con opzioni per le date
  ./git_multiproject_stats_collector.sh --start 2025-11-01 --end 2025-11-30 ~/repo1

  # Con aggiornamento esplicito dei repository
  ./git_multiproject_stats_collector.sh --fetch --file repos.txt 2025-11-01 2025-11-30
EOF
            exit 0
            ;;
        -*)
            echo "Opzione non valida: $1" >&2
            exit 1
            ;;
        *)
            # Resto sono percorsi
            break
            ;;
    esac
done

# Se date non specificate con --start/--end, usa i primi due argomenti
if [[ -z "$START_DATE" ]]; then
    START_DATE="$1"
    shift
fi
if [[ -z "$END_DATE" ]]; then
    END_DATE="$1"
    shift
fi

PROJECT_PATHS=("$@")

# Lettura file con gestione corretta degli spazi
if [ -n "$PROJECT_FILE" ]; then
    if [ ! -f "$PROJECT_FILE" ]; then
        echo "Errore: File $PROJECT_FILE non trovato." >&2
        exit 1
    fi
    while IFS= read -r line || [ -n "$line" ]; do
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        # Espansione tilde e aggiunta come elemento singolo
        path="${line/#\~/$HOME}"
        PROJECT_PATHS+=("$path")
    done < "$PROJECT_FILE"
fi

# Validazione date (formato base)
if ! [[ "$START_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || \
   ! [[ "$END_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "Errore: Date devono essere in formato YYYY-MM-DD" >&2
    exit 1
fi

# Inizializzazione della variabile JSON
FULL_JSON="{\n"
FULL_JSON+="  \"metadata\": {\n"
FULL_JSON+="    \"start_date\": \"$START_DATE\",\n"
FULL_JSON+="    \"end_date\": \"$END_DATE\"\n"
FULL_JSON+="  },\n"
FULL_JSON+="  \"data\": [\n"
FIRST_PROJECT=true

# -----------------------------------------------
# Funzione per analizzare un singolo progetto
# -----------------------------------------------
analyze_project() {
    local project_path="$1"
    local project_name=$(basename "$project_path")
    
    # 1. Spostati nella directory
    if [ ! -d "$project_path" ] || [ ! -d "$project_path/.git" ]; then
        echo "Avviso: $project_path non è una cartella valida o un repository Git. Saltato." >&2
        return
    fi
    
    cd "$project_path" || return

    if [[ "$FETCH_ENABLED" == true ]]; then
        echo "Aggiornamento remote per $project_name..." >&2
        if git fetch --quiet 2>/dev/null; then
            echo "$project_name aggiornato con successo." >&2
        else
            echo "Avviso: Impossibile aggiornare $project_name (problemi di connettività o repository senza remote)." >&2
            echo "Verranno analizzati solo i commit locali disponibili." >&2
        fi
    else
        echo "Skip aggiornamento per $project_name (usa --fetch per abilitare)." >&2
    fi

    echo "Analisi di $project_name ($project_path)..." >&2

    # 2. Ottieni tutti gli autori unici nel periodo
    AUTHORS=$(git log --since="$START_DATE 00:00:00" --until="$END_DATE 23:59:59" --pretty=format:'%an' | sort | uniq)
    
    # 3. Iterazione sugli autori per ottenere le statistiche totali
    local IFS=$'\n' # Imposta separatore di campo su newline per gestire gli spazi nei nomi
    for AUTHOR_NAME in $AUTHORS; do
        if [[ -z "$AUTHOR_NAME" ]]; then continue; fi
        
        # Ignoriamo i commit di merge per una metrica più pulita (come discusso)
        # Usiamo --no-merges per escluderli
        
        # a) Ottieni righe aggiunte/eliminate e numero di file toccati
        local LINE_METRICS=$(git log --no-merges --since="$START_DATE" --until="$END_DATE" --author="$AUTHOR_NAME" --pretty='format:' --numstat | awk '
            BEGIN {sum_added=0; sum_deleted=0; files_count=0}
            {
                if ($1 ~ /^[0-9]+$/) {
                    sum_added += $1;
                    sum_deleted += $2;
                    files_count++;
                }
            }
            END {
                # Restituiamo added, deleted e files_count separati da :
                print sum_added ":" sum_deleted ":" files_count
            }')
            
        local ADDED=$(echo $LINE_METRICS | cut -d ':' -f 1)
        local DELETED=$(echo $LINE_METRICS | cut -d ':' -f 2)
        local FILES_COUNT=$(echo $LINE_METRICS | cut -d ':' -f 3)

        # Gestione valori vuoti e calcolo righe totali per retrocompatibilità
        ADDED=${ADDED:-0}
        DELETED=${DELETED:-0}
        FILES_COUNT=${FILES_COUNT:-0}
        local TOTAL_LINES=$((ADDED + DELETED))
        
        if [[ "$TOTAL_LINES" -eq 0 ]]; then continue; fi

        # b) Ottieni il numero totale di commit
        local TOTAL_COMMITS=$(git log --no-merges --since="$START_DATE" --until="$END_DATE" --author="$AUTHOR_NAME" --oneline | wc -l | tr -d ' ')

        # 4. Aggiungi il blocco JSON con i nuovi campi added e files
        local JSON_ENTRY="  {\n"
        JSON_ENTRY+="    \"project\": \"$project_name\",\n"
        JSON_ENTRY+="    \"author\": \"$AUTHOR_NAME\",\n"
        JSON_ENTRY+="    \"added\": $ADDED,\n"
        JSON_ENTRY+="    \"files\": $FILES_COUNT,\n"
        JSON_ENTRY+="    \"lines\": $TOTAL_LINES,\n"
        JSON_ENTRY+="    \"commits\": $TOTAL_COMMITS\n"
        JSON_ENTRY+="  }"
        
        if [[ "$FIRST_PROJECT" == true ]]; then
            FULL_JSON+="$JSON_ENTRY"
            FIRST_PROJECT=false
        else
            FULL_JSON+=",\n$JSON_ENTRY"
        fi
        
    done
    unset IFS
    
    # Torna alla directory originale (dove risiede lo script)
    cd - > /dev/null
}

# -----------------------------------------------
# Logica Principale
# -----------------------------------------------
main() {
    # Validazioni iniziali
    if [ ${#PROJECT_PATHS[@]} -eq 0 ] || [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
        echo "Errore: Specificare date e almeno un percorso progetto." >&2
        echo "Utilizzo:" >&2
        echo "  $0 <DATA_INIZIO> <DATA_FINE> <percorso_progetto1> [percorso_progetto2...]" >&2
        echo "  $0 --file <file_percorsi> <DATA_INIZIO> <DATA_FINE>" >&2
        echo "Nota: Il file deve contenere un percorso per riga." >&2
        exit 1
    fi
    
    # Processa tutti i percorsi forniti
    for path in "${PROJECT_PATHS[@]}"; do
        analyze_project "$path"
    done
    
    # Stampa il JSON finale completo
    FULL_JSON+="\n  ]\n"
    FULL_JSON+="}\n"
    echo -e "$FULL_JSON"
}

main