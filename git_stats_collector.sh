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
#   ./git_stats_collector.sh [--repo <path|url>] <DATA_INIZIO> <DATA_FINE> [formato] [autore]
#
# PARAMETRI:
#   DATA_INIZIO    Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
#   DATA_FINE      Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
#   formato        Formato output: 'text' o 'json' (default: text)
#   autore         Filtra per autore specifico (default: tutti, modalità TOTALE)
#
# REPOSITORY REMOTI (--repo):
#   Senza --repo, lo script analizza il repository nella cartella corrente (comportamento storico).
#   Con --repo <url> (es. https://github.com/org/repo.git o git@github.com:org/repo.git), il repository
#   viene clonato (la prima volta) o aggiornato (con --fetch) in una cartella locale sotto
#   $GIT_ACTIVITY_REPOS_DIR (default: ~/repos), poi analizzato normalmente. --repo accetta anche un path
#   locale, equivalente a lanciare lo script da dentro quella cartella.
#   Se una cartella con lo stesso nome esiste già ma non corrisponde all'URL richiesto, lo script si
#   ferma con un errore: definisci un nome dedicato nel file di mapping (vedi git_multiproject_stats_collector.sh
#   per i dettagli, la convenzione è condivisa tra i due script).
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
REPO_ARG=""

# Parse positional and optional arguments
TEMP_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --fetch)
            FETCH_ENABLED=true
            shift
            ;;
        --repo)
            if [[ -z "$2" || "$2" =~ ^- ]]; then
                echo "Errore: --repo richiede un argomento (path locale o URL)." >&2
                exit 1
            fi
            REPO_ARG="$2"
            shift 2
            ;;
        -h|--help)
            cat << 'EOF'
UTILIZZO:
  ./git_stats_collector.sh [OPZIONI] <DATA_INIZIO> <DATA_FINE> [formato] [autore]

OPZIONI:
  --fetch          Abilita l'aggiornamento del repository con git fetch
  --repo <path|url>  Analizza questo repository (path locale o URL) invece della cartella corrente
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

  # Repository remoto (clonato/aggiornato sotto ~/repos, override con GIT_ACTIVITY_REPOS_DIR)
  ./git_stats_collector.sh --repo https://github.com/org/repo.git 2025-11-01 2025-11-30 json
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
# Risoluzione Repository Remoti (URL -> path locale)
# -----------------------------------------------
# GIT_ACTIVITY_REPOS_DIR: cartella (visibile, non nascosta) dove vengono clonati i repository
#   richiesti via URL. Default: ~/repos. Può coincidere con una cartella già usata per sviluppo:
#   se il repository è già presente e il suo remote "origin" corrisponde all'URL richiesto, viene
#   riusato (senza clonare di nuovo).
# GIT_ACTIVITY_REPOS_MAP_FILE (fissato, non configurabile via env): file JSON opzionale
#   {"<url>": "<nome-cartella>"} usato per assegnare un nome di cartella dedicato a un URL, necessario
#   solo per risolvere collisioni di nome (es. due repository diversi che si chiamano entrambi "backend").

REPOS_DIR="${GIT_ACTIVITY_REPOS_DIR:-$HOME/repos}"
REPOS_MAP_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/git-activity-reports/git-activity-repos-map.json"

# Riconosce URL Git: qualsiasi schema URI (http/https/git/ssh/file/...) oppure forma scp (git@host:percorso)
is_repo_url() {
    [[ "$1" =~ ^[A-Za-z][A-Za-z0-9+.-]*:// ]] || [[ "$1" =~ ^[A-Za-z0-9._-]+@[A-Za-z0-9._-]+: ]]
}

# Normalizza un URL per il confronto (rimuove .git e / finali)
normalize_repo_url() {
    local u="${1%.git}"
    echo "${u%/}"
}

# Cerca nel file di mapping (opzionale) un nome di cartella dedicato per l'URL
lookup_repo_mapping() {
    local url="$1"
    [[ -f "$REPOS_MAP_FILE" ]] || return 0
    python3 -c '
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    print(data.get(sys.argv[2], ""))
except Exception:
    print("")
' "$REPOS_MAP_FILE" "$url"
}

# Clona/aggiorna un repository remoto sotto $REPOS_DIR e stampa su stdout il path locale risultante.
# In caso di errore/collisione non stampa nulla e ritorna 1.
resolve_remote_repo() {
    local url="$1"
    local mapped_name default_name target_name target
    mapped_name=$(lookup_repo_mapping "$url")
    default_name=$(basename "$url")
    default_name="${default_name%.git}"
    target_name="${mapped_name:-$default_name}"
    target="$REPOS_DIR/$target_name"

    mkdir -p "$REPOS_DIR" 2>/dev/null

    if [[ ! -d "$target" ]]; then
        echo "Clonazione di $url in $target..." >&2
        if ! git clone --quiet "$url" "$target"; then
            echo "Errore: clonazione di $url fallita." >&2
            return 1
        fi
    else
        if [[ ! -d "$target/.git" ]]; then
            echo "Errore: $target esiste già ma non è un repository Git (richiesto per $url)." >&2
            echo "Configura un nome di cartella dedicato per questo URL nel file di mapping: $REPOS_MAP_FILE" >&2
            echo "Esempio: { \"$url\": \"nome-cartella-alternativo\" }" >&2
            return 1
        fi

        local existing_origin
        existing_origin=$(git -C "$target" remote get-url origin 2>/dev/null)

        if [[ -z "$existing_origin" ]] || [[ "$(normalize_repo_url "$existing_origin")" != "$(normalize_repo_url "$url")" ]]; then
            echo "Errore: $target esiste già ma corrisponde a un repository diverso da $url" >&2
            echo "  (origin attuale: ${existing_origin:-nessuno})" >&2
            echo "Configura un nome di cartella dedicato per questo URL nel file di mapping: $REPOS_MAP_FILE" >&2
            echo "Esempio: { \"$url\": \"nome-cartella-alternativo\" }" >&2
            return 1
        fi

        if [[ "$FETCH_ENABLED" == true ]]; then
            echo "Aggiornamento repository remoto in $target..." >&2
            git -C "$target" fetch --quiet 2>/dev/null || echo "Avviso: fetch fallito per $target." >&2
        fi
    fi

    echo "$target"
}

# Risolve un argomento "path locale o URL" nel path locale da usare per l'analisi.
resolve_repo_path() {
    local input="$1"
    if is_repo_url "$input"; then
        resolve_remote_repo "$input"
    else
        echo "$input"
    fi
}

# Calcola righe aggiunte/rimosse e numero di file toccati
get_lines() {
    local date_str="$1"
    local git_args=(--since="$date_str 00:00:00" --until="$date_str 23:59:59" --pretty="format:" --numstat --no-merges)
    
    if [[ -n "$CURRENT_AUTHOR_FILTER" && "$CURRENT_AUTHOR_FILTER" != "TOTALE" ]]; then
        git_args+=(--author="$CURRENT_AUTHOR_FILTER")
    fi

    # Mantiene i tuoi exclude personalizzati
    git log "${git_args[@]}" -- . \
        ":(exclude)node_modules/*" \
        ":(exclude)dist/*" \
        ":(exclude)vendor/*" \
        ":(exclude)*.lock" \
        ":(exclude)*.min.js" \
        ":(exclude)bootstrap-italia/*" \
        ":(exclude)bootstrap/*" \
        ":(exclude).*" \
        ":(exclude).*/*" \
        ":(exclude)**/old/*" \
        ":(exclude)**/tmp/*" \
        ":(exclude)**/temp/*" \
        ":(exclude)package-lock.json" \
        ":(exclude)package.json" \
        ":(exclude)prisma/**/internal/*" \
        ":(exclude)prisma/**/client/*" \
        ":(exclude)**/generated/*" | awk '
        BEGIN {sum_added=0; sum_deleted=0; files_count=0}
        {
            if ($1 ~ /^[0-9]+$/) {
                sum_added += $1;
                sum_deleted += $2;
                files_count++;
            }
        }
        END {
            # Restituiamo 3 valori separati da :
            print sum_added ":" sum_deleted ":" files_count
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
        
        # Estrazione corretta basata sui 3 valori restituiti da get_lines
        local added=$(echo $line_metrics | cut -d ':' -f 1)
        local deleted=$(echo $line_metrics | cut -d ':' -f 2)
        local files_count=$(echo $line_metrics | cut -d ':' -f 3)
        
        # Calcolo righe totali per compatibilità
        local lines=$((added + deleted))

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
    
    # Risoluzione --repo (path locale o URL), se specificato
    if [[ -n "$REPO_ARG" ]]; then
        local resolved_repo
        resolved_repo=$(resolve_repo_path "$REPO_ARG")
        if [[ $? -ne 0 || -z "$resolved_repo" ]]; then
            exit 1
        fi
        cd "$resolved_repo" || { echo "Errore: impossibile accedere a $resolved_repo" >&2; exit 1; }
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
