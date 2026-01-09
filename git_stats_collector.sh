#!/bin/bash

# ===============================================
# GIT STATS COLLECTOR - Singolo Repository
# ===============================================
#
# DESCRIZIONE:
#   Analizza l'attività Git di un singolo repository con dettaglio giornaliero.
#   Genera statistiche su commit e righe modificate per autore.
#
# UTILIZZO:
#   ./git_stats_collector.sh <DATA_INIZIO> <DATA_FINE> [formato] [autore]
#
# PARAMETRI:
#   DATA_INIZIO    Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
#   DATA_FINE      Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
#   formato        Formato output: 'text' o 'json' (default: text)
#   autore         Filtra per autore specifico (default: tutti, modalità TOTALE)
#
# ESEMPI:
#   # Report testuale per tutti gli autori (aggregato)
#   ./git_stats_collector.sh 2025-11-01 2025-11-30
#
#   # Report testuale per autore specifico
#   ./git_stats_collector.sh 2025-11-01 2025-11-30 text "Mario Rossi"
#
#   # JSON per visualizzazione grafica
#   ./git_stats_collector.sh 2025-11-01 2025-11-30 json | python3 plot_git.py
#
#   # JSON per singolo autore
#   ./git_stats_collector.sh 2025-11-01 2025-11-30 json "Laura Bianchi"
#
# OUTPUT:
#   - Formato TEXT: Tabella giornaliera con commit, righe aggiunte/rimosse
#   - Formato JSON: Array di oggetti con statistiche giornaliere per autore
#
# FORMATO JSON:
#   [
#     {
#       "author": "Nome Autore",
#       "total_commits": 15,
#       "daily_data": [
#         {
#           "day": "Monday",
#           "date": "2025-11-04",
#           "commits": 3,
#           "lines": 450,
#           "added": 280,
#           "deleted": 170
#         }
#       ]
#     }
#   ]
#
# NOTE:
#   - Lo script deve essere eseguito all'interno di un repository Git
#   - I merge commits sono esclusi dalle statistiche
#   - Le righe totali sono calcolate come: aggiunte + eliminate
#   - Richiede GNU date (su macOS: brew install coreutils, usa gdate)
#   - Di default, il repository non viene aggiornato con git fetch (usa --fetch per abilitare)
#   - In caso di problemi di rete, vengono analizzati solo i commit locali
#
# REQUISITI:
#   - Bash 4.0+
#   - Git installato e configurato
#   - GNU coreutils (comando date con opzione -d)
#
# AUTORE: Michele Innocenti
# VERSIONE: 1.0
# DATA: Dicembre 2025
# ===============================================

# Parsing delle opzioni
START_DATE=""
END_DATE=""
OUTPUT_FORMAT="text"
CLI_AUTHOR_FILTER=""
FETCH_ENABLED=false

# Parse positional and optional arguments
TEMP_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --fetch)
            FETCH_ENABLED=true
            shift
            ;;
        -h|--help)
            cat << 'EOF'
UTILIZZO:
  ./git_stats_collector.sh [OPZIONI] <DATA_INIZIO> <DATA_FINE> [formato] [autore]

OPZIONI:
  --fetch          Abilita l'aggiornamento del repository con git fetch
  -h, --help       Mostra questo help

PARAMETRI:
  DATA_INIZIO      Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
  DATA_FINE        Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
  formato          Formato output: 'text' o 'json' (default: text)
  autore           Filtra per autore specifico (default: tutti, modalità TOTALE)

ESEMPI:
  # Report testuale per tutti gli autori (aggregato)
  ./git_stats_collector.sh 2025-11-01 2025-11-30
  
  # Report testuale per autore specifico
  ./git_stats_collector.sh 2025-11-01 2025-11-30 text "Mario Rossi"
  
  # JSON per visualizzazione grafica
  ./git_stats_collector.sh 2025-11-01 2025-11-30 json | python3 plot_git.py
  
  # Con aggiornamento esplicito del repository
  ./git_stats_collector.sh --fetch 2025-11-01 2025-11-30 json
EOF
            exit 0
            ;;
        -*)
            echo "Opzione non valida: $1" >&2
            exit 1
            ;;
        *)
            TEMP_ARGS+=("$1")
            shift
            ;;
    esac
done

# Ripristina gli argomenti posizionali
set -- "${TEMP_ARGS[@]}"
START_DATE="$1"
END_DATE="$2"
OUTPUT_FORMAT="${3:-text}" # Predefinito a 'text'
CLI_AUTHOR_FILTER="$4"     # Filtro opzionale da riga di comando

# Variabile globale per il filtro corrente
CURRENT_AUTHOR_FILTER="$CLI_AUTHOR_FILTER"

# -----------------------------------------------
# Funzioni Ausiliarie
# -----------------------------------------------

# Calcola righe aggiunte/rimosse e numero di file toccati
get_lines() {
    local date_str="$1"
    
    # Aggiunti: --no-merges e filtri :(exclude) per escludere file non desiderati dai conteggi
    local cmd=(git log --since="$date_str 00:00:00" --until="$date_str 23:59:59" \
        --pretty="format:" --numstat --no-merges \
        -- . ":(exclude)*.lock" \
        ":(exclude)node_modules/*" \
        ":(exclude)dist/*" \
        ":(exclude)vendor/*" \
        ":(exclude)*.min.js" \
        ":(exclude)package-lock.json" \
        ":(exclude)prisma/migrations/*" \
        ":(exclude)prisma/client/*" \
        ":(exclude)**/generated/*")
    
    if [[ -n "$CURRENT_AUTHOR_FILTER" && "$CURRENT_AUTHOR_FILTER" != "TOTALE" ]]; then
        cmd+=(--author="$CURRENT_AUTHOR_FILTER")
    fi

    "${cmd[@]}" | awk '
        BEGIN {OFS=":"; sum_added=0; sum_deleted=0; files_count=0}
        $1 ~ /^[0-9]+$/ { # Considera solo file non binari
            sum_added += $1;
            sum_deleted += $2;
            files_count++;
        }
        END {
            # Restituiamo anche il conteggio dei file per la formula in Python
            print sum_added, sum_deleted, (sum_added + sum_deleted), files_count
        }'
}

get_commits() {
    local date_str="$1"
    # Aggiunto --no-merges per evitare di contare i merge dei rami
    local cmd=(git log --since="$date_str 00:00:00" --until="$date_str 23:59:59" --oneline --no-merges)
    
    if [[ -n "$CURRENT_AUTHOR_FILTER" && "$CURRENT_AUTHOR_FILTER" != "TOTALE" ]]; then
        cmd+=(--author="$CURRENT_AUTHOR_FILTER")
    fi

    "${cmd[@]}" | wc -l | tr -d ' '
}

# Ottiene la lista autori (gestisce spazi nei nomi)
get_all_authors() {
    git log --since="$START_DATE 00:00:00" --until="$END_DATE 23:59:59" --pretty=format:'%an' | sort | uniq
}

# -----------------------------------------------
# Logica Principale del Report per Singolo Autore o Totale
# -----------------------------------------------

generate_single_author_data() {
    local author_name="$1"
    CURRENT_AUTHOR_FILTER="$author_name"

    local start_ts=$(date -d "$START_DATE" +%s)
    local end_ts=$(date -d "$END_DATE" +%s)
    local current_ts=$start_ts

    local daily_json_items=""
    local day_first=true
    local total_commits=0
    local total_lines=0
    local total_added=0
    local total_deleted=0

    # Intestazione specifica se siamo in modalità TEXT
    if [[ "$OUTPUT_FORMAT" == "text" ]]; then
        printf "\n## Report: %s\n" "$author_name"
        echo "---------------------------------------------------------------------------------------"
        printf "%-10s %-10s %10s %15s %15s %15s\n" "Giorno" "Data" "Commit" "Righe Tot." "Aggiunte" "Rimosse"
        echo "---------------------------------------------------------------------------------------"
    fi

    # Iterazione giorni
    while [[ $current_ts -le $end_ts ]]; do
        local current_date=$(date -d @$current_ts +%Y-%m-%d)
        local day_of_week=$(date -d @$current_ts +%A)

        local commits=$(get_commits "$current_date")
        local line_metrics=$(get_lines "$current_date")
        
        local added=$(echo $line_metrics | cut -d ':' -f 1)
        local deleted=$(echo $line_metrics | cut -d ':' -f 2)
        local lines=$(echo $line_metrics | cut -d ':' -f 3)
        local files_count=$(echo $line_metrics | cut -d ':' -f 4)

        # Gestione valori vuoti se awk non ritorna nulla
        added=${added:-0}
        deleted=${deleted:-0}
        lines=${lines:-0}

        total_commits=$((total_commits + commits))
        total_lines=$((total_lines + lines))
        total_added=$((total_added + added))
        total_deleted=$((total_deleted + deleted))

        # Output Text (Corretto: Stampa sempre se formato è text)
        if [[ "$OUTPUT_FORMAT" == "text" ]]; then
             # Stampa solo se c'è attività o se vuoi vedere anche i giorni vuoti
             if [[ "$commits" -gt 0 ]]; then
                printf "%-10s %-10s %10d %15d %15d %15d\n" "${day_of_week:0:3}" "$current_date" "$commits" "$lines" "$added" "$deleted"
             fi
        fi

        # Output JSON
        if [[ "$OUTPUT_FORMAT" == "json" ]]; then
            if [[ "$day_first" == true ]]; then day_first=false; else daily_json_items+=","; fi
            daily_json_items+="{\"day\":\"$day_of_week\",\"date\":\"$current_date\",\"commits\":$commits,\"lines\":$lines,\"added\":$added,\"deleted\":$deleted,\"files\":${files_count:-0}}"
        fi

        current_ts=$((current_ts + 86400))
    done

    if [[ "$OUTPUT_FORMAT" == "text" ]]; then
        echo "---------------------------------------------------------------------------------------"
        printf "%-21s %10d %15d %15d %15d\n" "TOTALE:" "$total_commits" "$total_lines" "$total_added" "$total_deleted"
    fi

    # Ritorna blocco JSON per questo autore
    if [[ "$OUTPUT_FORMAT" == "json" ]]; then
        echo "{"
        echo "  \"author\": \"$author_name\","
        echo "  \"total_commits\": $total_commits,"
        echo "  \"daily_data\": [$daily_json_items]"
        echo "}"
    fi
}

# -----------------------------------------------
# Main
# -----------------------------------------------

main() {
    # Validazioni base
    if [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
        echo "Errore: specificare date. Uso: $0 <START> <END> [text|json] [autore]" >&2; exit 1
    fi
    
    # Check git
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "Errore: Non sei in un repository Git." >&2; exit 1
    fi

    # Aggiorna le informazioni remote per includere tutti i cambiamenti più recenti
    if [[ "$FETCH_ENABLED" == true ]]; then
        echo "Aggiornamento informazioni remote..." >&2
        if git fetch --quiet 2>/dev/null; then
            echo "Repository aggiornato con successo." >&2
        else
            echo "Avviso: Impossibile aggiornare il repository remoto (problemi di connettività o repository senza remote)." >&2
            echo "Verranno analizzati solo i commit locali disponibili." >&2
        fi
    else
        echo "Skip aggiornamento (usa --fetch per abilitare)." >&2
    fi

    # 1. Output JSON
    if [[ "$OUTPUT_FORMAT" == "json" ]]; then
        echo "[" 
        
        if [[ -n "$CLI_AUTHOR_FILTER" ]]; then
            # Singolo autore richiesto esplicitamente
            generate_single_author_data "$CLI_AUTHOR_FILTER"
        else
            # Tutti gli autori (Automatico)
            # Usiamo un file temporaneo o process substitution per leggere riga per riga (gestione spazi)
            local first_author=true
            
            while IFS= read -r auth; do
                if [[ -z "$auth" ]]; then continue; fi
                
                if [[ "$first_author" == true ]]; then 
                    first_author=false
                else 
                    echo "," 
                fi
                
                generate_single_author_data "$auth"
                
            done < <(get_all_authors)
        fi
        echo "]" 
    
    # 2. Output TEXT
    else
        echo "Generazione report dal $START_DATE al $END_DATE..."
        if [[ -n "$CLI_AUTHOR_FILTER" ]]; then
            generate_single_author_data "$CLI_AUTHOR_FILTER"
        else
            # Modalità TEXT senza autore specifico:
            # Opzione A: Stampare il totale aggregato (comportamento classico)
            generate_single_author_data "TOTALE"
            
            # Opzione B: Se vuoi vedere la lista testuale di tutti gli autori separati, scommenta qui sotto:
            # echo -e "\n=== DETTAGLIO PER AUTORE ==="
            # get_all_authors | while IFS= read -r auth; do generate_single_author_data "$auth"; done
        fi
    fi
}

main
