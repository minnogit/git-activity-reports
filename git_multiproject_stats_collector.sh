#!/bin/bash

# ===============================================
# GIT MULTI-PROJECT STATS COLLECTOR
# ===============================================
#
# DESCRIZIONE:
#   Analizza l'attività Git su multipli repository contemporaneamente.
#   Genera statistiche per progetto e autore, con dettaglio giornaliero.
#
# UTILIZZO:
#   ./git_multiproject_stats_collector.sh [OPZIONI] <DATA_INIZIO> <DATA_FINE> [percorsi...]
#
# OPZIONI:
#   --file <file>    Legge i percorsi/URL dei repository da file (uno per riga)
#   --start <data>   Data di inizio periodo (alternativa a posizionale)
#   --end <data>     Data di fine periodo (alternativa a posizionale)
#   --fetch          Abilita l'aggiornamento dei repository con git fetch
#   -h, --help       Mostra questo help
#
# PARAMETRI POSIZIONALI:
#   DATA_INIZIO      Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
#   DATA_FINE        Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
#   percorsi...      Percorsi locali o URL Git (opzionale se si usa --file)
#
# METODO DI RACCOLTA:
#   - Un SOLO `git log` per repository (non uno per autore): il raggruppamento per
#     autore e giorno avviene in awk. Evita anche il doppio conteggio che
#     `--author=<nome>` causava quando un nome era sottostringa di un altro
#     (es. "Luca" catturava anche "Luca Bianchi").
#   - I giorni sono assegnati per AUTHOR-DATE, non per committer-date: un rebase o un
#     cherry-pick non sposta più il lavoro nel periodo sbagliato.
#   - `files` conta i file DISTINTI toccati, non le righe di --numstat.
#   - Gli alias autore sono applicati QUI, prima di ogni aggregazione.
#   - L'output include `daily_data`: senza granularità giornaliera il tetto anti-outlier
#     applicato dal plotter saturava su periodi lunghi, appiattendo tutti gli autori.
#
# REPOSITORY REMOTI:
#   Ogni "percorso" (posizionale o riga del file --file) può essere un path locale oppure un URL
#   Git (es. https://github.com/org/repo.git o git@github.com:org/repo.git). Gli URL vengono clonati
#   (la prima volta) o aggiornati (con --fetch) in una cartella locale visibile sotto
#   $GIT_ACTIVITY_REPOS_DIR (default: ~/repos), poi analizzati come un repository locale qualsiasi.
#   Se quella cartella corrisponde già a un checkout locale su cui stai lavorando (stesso remote
#   "origin" dell'URL richiesto), viene riusata senza clonare di nuovo.
#   In caso di collisione di nome tra URL diversi, lo script si ferma con un errore: assegna un nome
#   di cartella dedicato all'URL nel file di mapping opzionale
#   ${XDG_CONFIG_HOME:-~/.config}/git-activity-reports/git-activity-repos-map.json, formato:
#     { "https://github.com/org/repo.git": "nome-cartella-dedicato" }
#
# FORMATO FILE PERCORSI:
#   Il file specificato con --file deve contenere un percorso o un URL Git per riga:
#
#     # Commenti sono ignorati
#     ~/progetti/backend
#     /var/www/api-service
#     https://github.com/org/repo-remoto.git
#     git@github.com:org/altro-repo.git
#     # Percorsi con spazi sono supportati
#     /home/user/My Projects/mobile-app
#
# OUTPUT JSON:
#   {
#     "metadata": { "start_date": "...", "end_date": "...", "date_basis": "author" },
#     "data": [
#       {
#         "project": "backend",
#         "author": "Mario Rossi",
#         "commits": 24,
#         "added": 3000, "deleted": 450, "lines": 3450,
#         "files": 37,             // file DISTINTI toccati nel periodo
#         "active_days": 12,       // giorni distinti con almeno 1 commit
#         "daily_data": [
#           { "date": "2025-11-04", "commits": 3, "added": 280, "deleted": 170, "files": 6 }
#         ]
#       }
#     ]
#   }
#
#   I campi top-level (project, author, lines, commits, added, files) sono mantenuti per
#   retrocompatibilità; `deleted`, `active_days` e `daily_data` sono nuovi.
#
# NOTE:
#   - Lo script può essere eseguito da qualsiasi directory
#   - Ogni percorso deve puntare a un repository Git valido (.git presente), oppure essere un URL Git
#   - Repository locali non validi vengono saltati con warning; errori di risoluzione URL (es.
#     collisione di nome cartella) interrompono l'intera esecuzione
#   - I merge commits sono esclusi dalle statistiche
#   - `lines` = aggiunte + eliminate (indicatore di volume, non di valore)
#   - Il nome del progetto è estratto dal nome della cartella
#
# REQUISITI:
#   - Bash 4.0+, Git, GNU coreutils (date -d), python3
#
# AUTORE: Michele Innocenti
# VERSIONE: 3.0
# DATA: Agosto 2026
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
  --file <file>    Legge i percorsi/URL dei repository da file (uno per riga)
  --start <data>   Data di inizio periodo (alternativa a posizionale)
  --end <data>     Data di fine periodo (alternativa a posizionale)
  --fetch          Abilita l'aggiornamento dei repository con git fetch
  -h, --help       Mostra questo help

PARAMETRI POSIZIONALI:
  DATA_INIZIO      Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
  DATA_FINE        Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
  percorsi...      Percorsi locali o URL Git (opzionale se si usa --file)

ESEMPI:
  # Analisi di repository specifici
  ./git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 ~/repo1 ~/repo2

  # Repository da file di configurazione
  ./git_multiproject_stats_collector.sh --file progetti.txt 2025-11-01 2025-11-30

  # Con opzioni per le date
  ./git_multiproject_stats_collector.sh --start 2025-11-01 --end 2025-11-30 ~/repo1

  # Con aggiornamento esplicito dei repository
  ./git_multiproject_stats_collector.sh --fetch --file repos.txt 2025-11-01 2025-11-30

  # Repository remoto (clonato/aggiornato sotto ~/repos, override con GIT_ACTIVITY_REPOS_DIR)
  ./git_multiproject_stats_collector.sh 2025-11-01 2025-11-30 https://github.com/org/repo.git ~/repo2

NOTE:
  - I giorni sono attribuiti per author-date (rebase-safe), non per committer-date
  - `files` conta i file distinti toccati, non le modifiche per file
  - Gli alias autore sono applicati prima dell'aggregazione
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

# -----------------------------------------------
# Alias autori
# -----------------------------------------------
# Stessa logica di ricerca dei plotter (il primo file trovato vince, nessun merge).
# Applicare gli alias QUI e non nel plotter è essenziale: sommare metriche calcolate
# separatamente per ogni identità non equivale a calcolarle sui dati uniti.

find_aliases_file() {
    local xdg="${XDG_CONFIG_HOME:-$HOME/.config}"
    # Cartella dello script stesso (risolvendo eventuali symlink): il file alias spesso
    # vive accanto agli script nel repo clonato, mentre "." è la cartella da cui si lancia
    # l'analisi. Senza questo fallback un file messo accanto agli script non verrebbe
    # mai trovato.
    local self script_dir
    self=$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")
    script_dir=$(dirname "$self")
    local candidates=(
        "./git-activity-aliases.json"
        "$xdg/git-activity-reports/git-activity-aliases.json"
        "$xdg/git-activity-git-activity-aliases.json"
        "$script_dir/git-activity-aliases.json"
        "/etc/git-activity-reports/git-activity-aliases.json"
    )
    local c
    for c in "${candidates[@]}"; do
        [[ -f "$c" ]] && { echo "$c"; return 0; }
    done
    return 0
}

# Scrive su stdout righe "nome-git<TAB>nome-visualizzato" leggibili da awk
dump_aliases_tsv() {
    local f
    f=$(find_aliases_file)
    [[ -z "$f" ]] && return 0
    python3 -c '
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        for k, v in data.items():
            k = str(k).replace("\t", " ").replace("\n", " ")
            v = str(v).replace("\t", " ").replace("\n", " ")
            print(f"{k}\t{v}")
except Exception:
    pass
' "$f"
    echo "Alias autori caricati da $f" >&2
}

# -----------------------------------------------
# Esclusioni (centralizzate: prima erano ripetute in ogni query)
# -----------------------------------------------
EXCLUDE_PATHSPEC=(
    # Esclusione dichiarativa: salta i percorsi che il repository stesso marca in
    # .gitattributes. Due attributi distinti, entrambi standard GitHub Linguist:
    #   linguist-generated  -> codice PRODOTTO da un tool (client OpenAPI, migrazioni)
    #   linguist-vendored   -> codice di TERZE PARTI copiato nel repo (una libreria)
    # Usare l'etichetta giusta conta: sono la stessa cosa per git, ma per GitHub sono due
    # segnali diversi nei diff delle PR. Serve la forma BOOLEANA di entrambi gli attributi:
    # "linguist-generated=true" non viene intercettato dal pathspec magic di git (verificato).
    # Attenzione: git confronta il pattern col percorso COME ERA in ogni commit, quindi se
    # i file sono stati spostati vanno dichiarati anche i percorsi storici — dichiarare solo
    # la destinazione peggiora il risultato (la sorgente riemerge come cancellazione intera).
    # Nei repository senza .gitattributes questo pathspec non ha alcun effetto.
    ":(exclude,attr:linguist-generated)"
    ":(exclude,attr:linguist-vendored)"
    ":(exclude)node_modules/*"
    ":(exclude)dist/*"
    ":(exclude)vendor/*"
    ":(exclude)*.lock"
    ":(exclude)*.min.js"
    ":(exclude)bootstrap-italia/*"
    ":(exclude)bootstrap/*"
    ":(exclude).*"
    ":(exclude).*/*"
    ":(exclude)**/old/*"
    ":(exclude)**/tmp/*"
    ":(exclude)**/temp/*"
    ":(exclude)package-lock.json"
    ":(exclude)package.json"
    ":(exclude)prisma/**/internal/*"
    ":(exclude)prisma/**/client/*"
    ":(exclude)**/generated/*"
)

# -----------------------------------------------
# Analisi di un singolo progetto
# -----------------------------------------------
# Emette TSV: progetto \t autore \t data \t commits \t added \t deleted \t files_giorno \t files_periodo
analyze_project() {
    local input_path="$1" alias_tsv="$2"
    local project_path
    project_path=$(resolve_repo_path "$input_path")
    if [[ $? -ne 0 || -z "$project_path" ]]; then
        # Errore di risoluzione (es. collisione di nome): non è un caso "repo non valido" da
        # saltare, richiede una correzione di configurazione, quindi interrompiamo tutta l'analisi.
        exit 1
    fi
    local project_name
    project_name=$(basename "$project_path")

    if [ ! -d "$project_path" ] || [ ! -d "$project_path/.git" ]; then
        echo "Avviso: $input_path non è una cartella valida o un repository Git. Saltato." >&2
        return
    fi

    if [[ "$FETCH_ENABLED" == true ]]; then
        echo "Aggiornamento remote per $project_name..." >&2
        if git -C "$project_path" fetch --quiet 2>/dev/null; then
            echo "$project_name aggiornato con successo." >&2
        else
            echo "Avviso: Impossibile aggiornare $project_name (problemi di connettività o repository senza remote)." >&2
        fi
    else
        echo "Skip aggiornamento per $project_name (usa --fetch per abilitare)." >&2
    fi

    echo "Analisi di $project_name ($project_path)..." >&2

    local since_margin
    since_margin=$(date -d "$START_DATE -31 days" +%Y-%m-%d 2>/dev/null || echo "$START_DATE")

    git -C "$project_path" log --no-merges --since="$since_margin" \
        --pretty=format:'%x01%H%x09%an%x09%ad' --date=short --numstat \
        -- . "${EXCLUDE_PATHSPEC[@]}" 2>/dev/null \
    | awk -v start="$START_DATE" -v end="$END_DATE" -v aliasfile="$alias_tsv" -v project="$project_name" '
        BEGIN {
            FS = "\t"; OFS = "\t"
            if (aliasfile != "") {
                while ((getline line < aliasfile) > 0) {
                    n = split(line, p, "\t")
                    if (n >= 2 && p[1] != "") alias[p[1]] = p[2]
                }
                close(aliasfile)
            }
            active = 0
        }
        substr($0, 1, 1) == "\001" {
            a = $2; d = $3
            if (d >= start && d <= end) {
                if (a in alias) a = alias[a]
                cur_a = a
                cur = a SUBSEP d
                commits[cur]++
                active = 1
            } else {
                active = 0
            }
            next
        }
        !active { next }
        NF >= 3 {
            if ($1 ~ /^[0-9]+$/) {
                added[cur] += $1
                deleted[cur] += $2
            }
            # file distinti nel giorno
            fkey = cur SUBSEP $3
            if (!(fkey in seenday)) { seenday[fkey] = 1; files[cur]++ }
            # file distinti nel periodo (per la tabella di riepilogo)
            pkey = cur_a SUBSEP $3
            if (!(pkey in seenperiod)) { seenperiod[pkey] = 1; pfiles[cur_a]++ }
            next
        }
        END {
            for (k in commits) {
                split(k, kk, SUBSEP)
                print project, kk[1], kk[2], commits[k], added[k] + 0, deleted[k] + 0, files[k] + 0, pfiles[kk[1]] + 0
            }
        }'
}

# -----------------------------------------------
# Logica Principale
# -----------------------------------------------
main() {
    if [ ${#PROJECT_PATHS[@]} -eq 0 ] || [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
        echo "Errore: Specificare date e almeno un percorso progetto." >&2
        echo "Utilizzo:" >&2
        echo "  $0 <DATA_INIZIO> <DATA_FINE> <percorso_progetto1> [percorso_progetto2...]" >&2
        echo "  $0 --file <file_percorsi> <DATA_INIZIO> <DATA_FINE>" >&2
        echo "Nota: Il file deve contenere un percorso (o URL) per riga." >&2
        exit 1
    fi

    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' EXIT
    local alias_tsv="$tmpdir/aliases.tsv"
    local all_tsv="$tmpdir/all.tsv"

    dump_aliases_tsv > "$alias_tsv"
    [[ -s "$alias_tsv" ]] || alias_tsv=""

    : > "$all_tsv"
    local path
    for path in "${PROJECT_PATHS[@]}"; do
        analyze_project "$path" "$alias_tsv" >> "$all_tsv"
    done

    sort -t$'\t' -k1,1 -k2,2 -k3,3 "$all_tsv" | python3 -c '
import sys, json

start, end = sys.argv[1], sys.argv[2]
groups = {}
for line in sys.stdin:
    line = line.rstrip("\n")
    if not line:
        continue
    parts = line.split("\t")
    if len(parts) < 8:
        continue
    project, author, date_s, commits, added, deleted, files_day, files_period = parts[:8]
    key = (project, author)
    g = groups.setdefault(key, {"days": [], "files_period": int(files_period)})
    g["days"].append({
        "date": date_s,
        "commits": int(commits),
        "added": int(added),
        "deleted": int(deleted),
        "files": int(files_day),
    })

data = []
for (project, author) in sorted(groups):
    g = groups[(project, author)]
    days = sorted(g["days"], key=lambda r: r["date"])
    added = sum(r["added"] for r in days)
    deleted = sum(r["deleted"] for r in days)
    data.append({
        "project": project,
        "author": author,
        "commits": sum(r["commits"] for r in days),
        "added": added,
        "deleted": deleted,
        "lines": added + deleted,
        "files": g["files_period"],
        "active_days": sum(1 for r in days if r["commits"] > 0),
        "daily_data": days,
    })

json.dump({
    "metadata": {"start_date": start, "end_date": end, "date_basis": "author"},
    "data": data,
}, sys.stdout, ensure_ascii=False, indent=2)
sys.stdout.write("\n")
' "$START_DATE" "$END_DATE"
}

main
