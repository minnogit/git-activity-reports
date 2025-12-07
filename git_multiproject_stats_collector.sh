#!/bin/bash

# ===============================================
# Script per raccogliere statistiche aggregate (righe e commit)
# per tutti gli autori in più repository Git.
#
# Utilizzo: ./git_stats_collector.sh <DATA_INIZIO> <DATA_FINE> <percorso_progetto1> [percorso_progetto2...]
# Esempio: ./git_stats_collector.sh 2025-11-01 2025-11-30 ~/progetti/repoA ~/progetti/repoB
# ===============================================

START_DATE="$1"
END_DATE="$2"
# Rimuoviamo i primi due parametri ($1 e $2) e consideriamo il resto come percorsi
shift 2
PROJECT_PATHS=("$@") 

# Inizializzazione della variabile JSON
FULL_JSON="[\n"
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

    echo "Analisi di $project_name ($project_path)..." >&2

    # 2. Ottieni tutti gli autori unici nel periodo
    AUTHORS=$(git log --since="$START_DATE 00:00:00" --until="$END_DATE 23:59:59" --pretty=format:'%an' | sort | uniq)
    
    # 3. Iterazione sugli autori per ottenere le statistiche totali
    local IFS=$'\n' # Imposta separatore di campo su newline per gestire gli spazi nei nomi
    for AUTHOR_NAME in $AUTHORS; do
        if [[ -z "$AUTHOR_NAME" ]]; then continue; fi
        
        # Ignoriamo i commit di merge per una metrica più pulita (come discusso)
        # Usiamo --no-merges per escluderli
        
        # a) Ottieni righe aggiunte/eliminate e totale
        local LINE_METRICS=$(git log --no-merges --since="$START_DATE" --until="$END_DATE" --author="$AUTHOR_NAME" --pretty='format:' --numstat | awk '
            BEGIN {OFS=":"; sum_added=0; sum_deleted=0}
            {
                sum_added += $1;
                sum_deleted += $2
            }
            END {
                print (sum_added + sum_deleted), $1, $2 # Righe totali, aggiunte, rimosse
            }')
            
        local TOTAL_LINES=$(echo $LINE_METRICS | cut -d ':' -f 1)
        # Controlla e imposta a 0 se vuoto
        TOTAL_LINES=${TOTAL_LINES:-0}
        
        # Salta l'autore se non ha contributo in quel periodo (dovrebbe essere filtrato da get_all_authors ma per sicurezza)
        if [[ "$TOTAL_LINES" -eq 0 ]]; then continue; fi

        # b) Ottieni il numero totale di commit
        local TOTAL_COMMITS=$(git log --no-merges --since="$START_DATE" --until="$END_DATE" --author="$AUTHOR_NAME" --oneline | wc -l | tr -d ' ')

        # 4. Aggiungi il blocco JSON all'output principale
        local JSON_ENTRY="  {\n"
        JSON_ENTRY+="    \"project\": \"$project_name\",\n"
        JSON_ENTRY+="    \"author\": \"$AUTHOR_NAME\",\n"
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
        echo "Utilizzo: $0 <DATA_INIZIO> <DATA_FINE> <percorso_progetto1> [percorso_progetto2...]" >&2
        exit 1
    fi
    
    # Processa tutti i percorsi forniti
    for path in "${PROJECT_PATHS[@]}"; do
        analyze_project "$path"
    done
    
    # Stampa il JSON finale completo
    FULL_JSON+="\n]"
    echo -e "$FULL_JSON"
}

main