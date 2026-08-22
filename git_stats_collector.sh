#!/bin/bash

# ===============================================
# GIT STATS COLLECTOR - Singolo Repository
# ===============================================
#
# DESCRIZIONE:
#   Analizza l'attività Git di un singolo repository con dettaglio giornaliero.
#   Genera statistiche su commit, righe modificate e file distinti per autore.
#
# UTILIZZO:
#   ./git_stats_collector.sh [--repo <path|url>] <DATA_INIZIO> <DATA_FINE> [formato] [autore]
#
# PARAMETRI:
#   DATA_INIZIO    Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
#   DATA_FINE      Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
#   formato        Formato output: 'text' o 'json' (default: text)
#   autore         Filtra per autore specifico (default: tutti, modalità TOTALE)
#                  Il match è ESATTO sul nome autore (non più una sottostringa).
#
# OWNERSHIP (--no-ownership per disattivare):
#   Solo con formato 'json': calcola, via `git blame`, quante righe del repository al
#   commit di riferimento sono "possedute" da ciascun autore. È una FOTOGRAFIA dello
#   stato dell'albero, non una serie temporale come il resto — vedi il commento sopra
#   collect_ownership_tsv per i dettagli (riferimento, costo, nessuna esclusione).
#   Costo misurato: un git blame per file è inevitabile; su un repository reale da 3133
#   file, ~15-17s in parallelo (fino a `nproc` processi) contro ~98s in sequenza. Su
#   repository molto grandi puo' comunque essere significativo: --no-ownership salta
#   il calcolo.
#
# METODO DI RACCOLTA:
#   - Un SOLO `git log` per repository (non uno per giorno/autore): il raggruppamento
#     per autore e giorno avviene in awk. Oltre a essere molto più rapido, evita il
#     doppio conteggio che `--author=<nome>` causava quando un nome autore era
#     sottostringa di un altro (es. "Luca" catturava anche "Luca Bianchi").
#   - I giorni sono assegnati in base alla AUTHOR-DATE, non alla committer-date: un
#     rebase/cherry-pick non sposta più il lavoro nel periodo sbagliato. Per questo
#     `--since` viene esteso di 31 giorni indietro e il filtro esatto sul periodo è
#     applicato in awk (git non sa filtrare per author-date).
#   - `files` conta i file DISTINTI toccati nel giorno, non le righe di --numstat:
#     lo stesso file modificato in 3 commit conta 1, non 3.
#   - Gli alias autore (git-activity-aliases.json) sono applicati QUI, prima di
#     qualsiasi aggregazione, così le identità multiple dello stesso sviluppatore
#     vengono unite sui dati grezzi.
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
# OUTPUT:
#   - Formato TEXT: Tabella giornaliera con commit, righe aggiunte/rimosse, file
#   - Formato JSON: metadata + array di oggetti con statistiche giornaliere per autore
#
# FORMATO JSON:
#   {
#     "metadata": {
#       "start_date": "2025-11-01",
#       "end_date": "2025-11-30",
#       "project": "backend",
#       "date_basis": "author"
#     },
#     "data": [
#       {
#         "author": "Nome Autore",
#         "total_commits": 15,
#         "daily_data": [
#           {
#             "day": "Monday",
#             "date": "2025-11-04",
#             "commits": 3,
#             "lines": 450,
#             "added": 280,
#             "deleted": 170,
#             "files": 6
#           }
#         ],
#         "punch_card": [
#           { "weekday": 1, "hour": 10, "commits": 2 }
#         ]
#       }
#     ],
#     "ownership": {
#       "ref_commit": "abcdef0123...",
#       "ref_date": "2025-11-30",
#       "total_lines": 48213,
#       "by_author": [
#         { "author": "Nome Autore", "lines": 30112, "pct": 62.45 }
#       ]
#     }
#   }
#
#   Sono elencati solo i giorni/celle con attività: il plotter ricostruisce i giorni vuoti
#   dal range in metadata. Per retrocompatibilità `plot_git.py` accetta ancora anche
#   il vecchio formato (array JSON senza metadata, senza punch_card/ownership).
#
#   `punch_card`: distribuzione dei commit per giorno della settimana (0=lunedì..6=domenica,
#   convenzione Python `date.weekday()`) e ora (0-23, ora locale registrata nel commit —
#   nessuna conversione a un fuso comune), aggregata su tutto il periodo richiesto.
#
#   `ownership` (assente se --no-ownership o se non c'è alcun commit ≤ DATA_FINE): righe
#   possedute per autore all'ULTIMO COMMIT ≤ DATA_FINE (non HEAD, per riproducibilità),
#   secondo `git blame` — chi ha scritto per ultimo ogni riga ancora presente nell'albero.
#   Include anche autori mai attivi nel periodo richiesto, se hanno ancora codice presente.
#   Nessuna esclusione di file generati/vendorizzati (stessa scelta fatta per il churn).
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
# NOTE:
#   - Lo script deve essere eseguito all'interno di un repository Git (salvo --repo)
#   - I merge commits sono esclusi dalle statistiche
#   - `lines` = aggiunte + eliminate (indicatore di volume, non di valore)
#   - I file binari contano come file toccati ma non contribuiscono alle righe
#   - Richiede GNU date (su macOS: brew install coreutils, usa gdate)
#   - Di default, il repository non viene aggiornato con git fetch (usa --fetch per abilitare)
#
# REQUISITI:
#   - Bash 4.0+
#   - Git installato e configurato
#   - GNU coreutils (comando date con opzione -d)
#   - python3 (solo per leggere i file di configurazione JSON)
#
# AUTORE: Michele Innocenti
# VERSIONE: 2.0
# DATA: Agosto 2026
# ===============================================

# Parsing delle opzioni
START_DATE=""
END_DATE=""
OUTPUT_FORMAT="text"
CLI_AUTHOR_FILTER=""
FETCH_ENABLED=false
REPO_ARG=""
OWNERSHIP_ENABLED=true

# Parse positional and optional arguments
TEMP_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --fetch)
            FETCH_ENABLED=true
            shift
            ;;
        --no-ownership)
            OWNERSHIP_ENABLED=false
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
  --no-ownership   Salta il calcolo dell'ownership (git blame per file, solo formato json)
  -h, --help       Mostra questo help

PARAMETRI:
  DATA_INIZIO      Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
  DATA_FINE        Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
  formato          Formato output: 'text' o 'json' (default: text)
  autore           Filtra per autore specifico, match ESATTO (default: tutti)

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
    # vive accanto agli script nel repo clonato, ma il collector si esegue DENTRO il repo
    # da analizzare, dove "." è un'altra cartella. Senza questo fallback un file messo
    # accanto agli script non verrebbe mai trovato.
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
# Nessun pathspec di esclusione: DELIBERATO, non un'omissione.
# -----------------------------------------------
# Fino alla v2.x, un pathspec (":(exclude)**/old/*", gli attributi .gitattributes
# linguist-generated/-vendored, node_modules/dist/vendor/lock ecc.) veniva passato
# direttamente a questo `git log`. Rimosso dopo aver misurato che qualunque pathspec di
# DIRECTORY applicato a `git log --numstat` rompe il rilevamento rename quando il lato
# SORGENTE di un file rinominato-con-modifiche cade sotto il pathspec e la destinazione
# no: git non trova più il file "prima" nel diff filtrato e conta l'intera destinazione
# come aggiunta pura. Misurato su un caso reale: un file da 431 righe di diff reale
# veniva riportato come 6001 (14x), e un'intera giornata di lavoro passava da 2.066 a
# 19.973 di churn (9.7x) — il trigger era `**/old/*`, un'esclusione di default, non
# quelle "sofisticate" per Prisma/TCPDF che pure ne soffrivano.
#
# Nessun tool esaminato (statistiche di GitHub stesso, git-fame, GitStats) risolve questo
# in modo robusto: GitHub non esclude affatto codice generato/vendorizzato dai suoi grafici
# di additions/deletions; git-fame lascia un `--excl` manuale opzionale senza tentare il
# rilevamento automatico; un maintainer di GitStats, alla stessa richiesta di funzionalità,
# ha risposto che l'esclusione automatica "non è banale da implementare" — coerente con
# quanto misurato qui. La scelta è quindi CONTARE TUTTO, senza pathspec: elimina il bug per
# costruzione (nessuna directory è più esclusa, quindi nessun rename può romperla), al
# prezzo di includere anche codice generato/vendorizzato nel churn. Per questo `churn` è
# trattato come la meno indicativa delle tre metriche (vedi plot_git.py) e non più la prima
# in evidenza: repository con lock file o client generati molto voluminosi lo mostreranno,
# ed è la ragione per non affidarsi al solo churn per leggere l'attività di un repository.
# find_generated_candidates.sh resta nel progetto come strumento diagnostico indipendente
# (utile per etichettare `.gitattributes` a beneficio di GitHub — collassare i diff nelle
# PR — non più per pilotare le statistiche di questo tool).
#
# DAILY_CHURN_CAP nei plotter resta quindi l'UNICA protezione contro un outlier estremo
# (es. un node_modules committato per errore): più importante di prima, non meno.

# -----------------------------------------------
# Raccolta dati: UN SOLO git log, aggregazione in awk
# -----------------------------------------------
# Emette TSV: autore \t data \t ora \t commits \t added \t deleted \t files_distinti
# "ora" (0-23) è l'ora locale registrata nel commit (fuso dell'autore, quello che git log
# mostra di default) — nessuna conversione a un fuso comune, per restare semplice e
# coerente con l'author-date già usata ovunque. Serve per il punch card giorno×ora nel
# report; il giorno della settimana si deriva da "data" più a valle (python), non qui.
collect_daily_tsv() {
    local alias_tsv="$1"
    # --since esteso indietro: filtriamo per author-date in awk, e la committer-date
    # di un commit rebasato è successiva alla sua author-date. Nessun --until, per non
    # perdere lavoro autorato nel periodo ma committato (rebasato) dopo la fine.
    local since_margin
    since_margin=$(date -d "$START_DATE -31 days" +%Y-%m-%d 2>/dev/null || echo "$START_DATE")

    git log --no-merges --since="$since_margin" \
        --pretty=format:'%x01%H%x09%an%x09%ad' --date=format:'%Y-%m-%d %H' --numstat 2>/dev/null \
    | awk -v start="$START_DATE" -v end="$END_DATE" -v aliasfile="$alias_tsv" '
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
        # Riga di intestazione commit: \x01<hash>\t<autore>\t<author-date> <ora>
        substr($0, 1, 1) == "\001" {
            a = $2
            split($3, dt, " ")
            d = dt[1]; hour = dt[2] + 0
            # Filtro esatto sul periodo per AUTHOR-DATE (confronto lessicografico su YYYY-MM-DD)
            if (d >= start && d <= end) {
                if (a in alias) a = alias[a]
                cur = a SUBSEP d SUBSEP hour
                commits[cur]++
                authors[a] = 1
                active = 1
            } else {
                active = 0
            }
            next
        }
        !active { next }
        # Righe --numstat: added \t deleted \t path
        NF >= 3 {
            if ($1 ~ /^[0-9]+$/) {
                added[cur] += $1
                deleted[cur] += $2
            }
            # I file binari ("-") contano come file toccati, con 0 righe
            fkey = cur SUBSEP $3
            if (!(fkey in seenfile)) { seenfile[fkey] = 1; files[cur]++ }
            next
        }
        END {
            for (k in commits) {
                split(k, kk, SUBSEP)
                print kk[1], kk[2], kk[3], commits[k], added[k] + 0, deleted[k] + 0, files[k] + 0
            }
        }' \
    | sort -t$'\t' -k1,1 -k2,2 -k3,3n
}

# -----------------------------------------------
# Ownership del codice (git blame) — SOLO per formato json, disattivabile con --no-ownership
# -----------------------------------------------
# Risponde a una domanda diversa dal resto del report: non "chi ha lavorato nel periodo"
# (serie temporale sui commit) ma "di chi è il codice presente nell'albero in un dato
# momento" (fotografia). Tre scelte deliberate:
#
#   1. Riferimento = ULTIMO COMMIT ≤ DATA_FINE, non HEAD. Rieseguendo lo stesso report in
#      futuro con la stessa DATA_FINE si ottiene lo stesso risultato, coerente con "cosa
#      mostrava il repository alla fine del periodo". A differenza del bucketing
#      giornaliero sopra (AUTHOR-DATE, rebase-safe), qui conta l'ordine del DAG dei commit
#      (`git rev-list --before`, che segue la commit-date/l'ordine topologico): l'ownership
#      riguarda lo STATO dei file nell'albero, non quando qualcuno ha scritto una riga.
#   2. Nessuna esclusione automatica di file generati/vendorizzati — stessa scelta fatta
#      per il churn sopra. Verificato (ricerca web) essere anche il comportamento di
#      default di git-fame: l'esclusione lì è un flag manuale opt-in (--excl), non
#      un'euristica automatica basata su .gitattributes/linguist-generated. Non è quindi
#      una scorciatoia presa qui, è lo standard di riferimento del genere di tool.
#   3. Un `git blame` per file è INEVITABILE: git non offre un comando che restituisca
#      l'ownership per riga su tutto l'albero in una sola invocazione. Misurato su un
#      repository reale da 3133 file: ~98s in sequenza, ~15-17s parallelizzando con
#      `xargs -P` (fino a `nproc` processi) sullo stesso repository.
#      ATTENZIONE se si modifica questa funzione: l'aggregazione per-autore deve avvenire
#      DENTRO ogni processo figlio, che emette sul flusso condiviso solo poche righe corte
#      (autore\tconteggio) — scritture brevi restano atomiche a livello di pipe (< PIPE_BUF).
#      L'output multi-riga crudo di `git blame` invece NO: misurato, `xargs -P` su quell'
#      output concatenato produce righe corrotte da interleaving fra processi concorrenti
#      (scritture spezzate a metà riga), verificato confrontando byte-per-byte con la stessa
#      raccolta eseguita in sequenza — un bug silenzioso se non fosse stato verificato così.

resolve_ownership_ref() {
    git rev-list -1 --before="$END_DATE 23:59:59" HEAD 2>/dev/null
}

# Emette TSV: autore \t righe_possedute, al commit di riferimento $1.
# Alias applicati qui (stesso file usato per le statistiche giornaliere): senza questo,
# identità multiple della stessa persona spezzerebbero l'ownership fra più righe.
collect_ownership_tsv() {
    local rev="$1" alias_tsv="$2" tmpdir="$3"
    local jobs
    jobs=$(nproc 2>/dev/null); jobs="${jobs:-4}"

    local filelist="$tmpdir/ownership_files.lst"
    # -z: percorsi separati da NUL, necessario perché possono contenere spazi (verificato:
    # non è un'ipotesi teorica, capita in repository reali) o altri caratteri "scomodi".
    git ls-tree -r -z "$rev" 2>/dev/null | while IFS= read -r -d '' entry; do
        meta="${entry%%$'\t'*}"
        path="${entry#*$'\t'}"
        type=$(awk '{print $2}' <<< "$meta")
        # Solo blob: esclude strutturalmente i gitlink dei submodule (type "commit"),
        # non è una scelta editoriale di esclusione come quelle rimosse dal churn.
        [[ "$type" == "blob" ]] && printf '%s\0' "$path"
    done > "$filelist"

    local nfiles
    nfiles=$(git ls-tree -r "$rev" 2>/dev/null | awk -F'\t' '{split($1,a," "); if(a[2]=="blob") c++} END{print c+0}')
    echo "Calcolo ownership: git blame su $nfiles file al commit ${rev:0:8} ($jobs processi in parallelo)..." >&2

    xargs -0 -P "$jobs" -I{} bash -c '
        git blame --line-porcelain "$1" -- "$2" 2>/dev/null \
        | awk "/^author /{ sub(/^author /, \"\"); c[\$0]++ } END{ for (a in c) printf \"%s\t%d\n\", a, c[a] }"
    ' _ "$rev" {} < "$filelist" \
    | awk -v aliasfile="$alias_tsv" -F'\t' '
        BEGIN {
            if (aliasfile != "") {
                while ((getline line < aliasfile) > 0) {
                    n = split(line, p, "\t")
                    if (n >= 2 && p[1] != "") alias[p[1]] = p[2]
                }
                close(aliasfile)
            }
        }
        {
            a = $1
            if (a in alias) a = alias[a]
            c[a] += $2
        }
        END {
            for (a in c) print a "\t" c[a]
        }'
}

# -----------------------------------------------
# Emissione JSON
# -----------------------------------------------
emit_json() {
    local tsv="$1" project="$2" ownership_tsv="$3" ownership_ref="$4" ownership_ref_date="$5"
    # awk gestisce l'aggregazione, python la serializzazione: quest'ultima deve restare
    # corretta anche con nomi autore contenenti virgolette, backslash o accenti.
    python3 -c '
import sys, json, datetime
from collections import defaultdict

start, end, project = sys.argv[1], sys.argv[2], sys.argv[3]
ownership_tsv_path = sys.argv[4] if len(sys.argv) > 4 else ""
ownership_ref = sys.argv[5] if len(sys.argv) > 5 else ""
ownership_ref_date = sys.argv[6] if len(sys.argv) > 6 else ""
# by_author_day: righe per (autore, data), una per ogni ora con attività quel giorno —
# vanno risommate per ricostruire il totale del giorno (daily_data non conosce le ore).
by_author_day = defaultdict(list)
# punch: conteggio commit per (autore, weekday 0=lunedì..6=domenica, ora 0-23), aggregato
# su tutto il periodo — è il "quando" del punch card, non un dettaglio per giorno.
punch = defaultdict(int)

for line in sys.stdin:
    line = line.rstrip("\n")
    if not line:
        continue
    parts = line.split("\t")
    if len(parts) < 7:
        continue
    author, date_s, hour_s, commits, added, deleted, files = parts[:7]
    commits = int(commits)
    by_author_day[(author, date_s)].append({
        "commits": commits, "added": int(added), "deleted": int(deleted), "files": int(files),
    })
    weekday = datetime.date.fromisoformat(date_s).weekday()
    punch[(author, weekday, int(hour_s))] += commits

daily_by_author = defaultdict(list)
for (author, date_s), rows in by_author_day.items():
    daily_by_author[author].append({
        "day": datetime.date.fromisoformat(date_s).strftime("%A"),
        "date": date_s,
        "commits": sum(r["commits"] for r in rows),
        "lines": sum(r["added"] + r["deleted"] for r in rows),
        "added": sum(r["added"] for r in rows),
        "deleted": sum(r["deleted"] for r in rows),
        "files": sum(r["files"] for r in rows),
    })

punch_by_author = defaultdict(list)
for (author, weekday, hour), commits in punch.items():
    if commits > 0:
        punch_by_author[author].append({"weekday": weekday, "hour": hour, "commits": commits})

data = []
for author in sorted(daily_by_author):
    days = sorted(daily_by_author[author], key=lambda r: r["date"])
    punch_cells = sorted(punch_by_author.get(author, []), key=lambda c: (c["weekday"], c["hour"]))
    data.append({
        "author": author,
        "total_commits": sum(r["commits"] for r in days),
        "daily_data": days,
        "punch_card": punch_cells,
    })

# Ownership: fotografia (non serie temporale), letta da un TSV separato prodotto da
# collect_ownership_tsv. Assente (nessuna chiave "ownership") se --no-ownership o se
# non esisteva alcun commit prima di DATA_FINE.
ownership = None
if ownership_tsv_path:
    entries = []
    total = 0
    try:
        with open(ownership_tsv_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                author, lines_n = parts[0], int(parts[1])
                entries.append((author, lines_n))
                total += lines_n
    except OSError:
        entries = []
    if total > 0:
        entries.sort(key=lambda e: e[1], reverse=True)
        ownership = {
            "ref_commit": ownership_ref,
            "ref_date": ownership_ref_date,
            "total_lines": total,
            "by_author": [
                {"author": a, "lines": n, "pct": round(n / total * 100, 2)}
                for a, n in entries
            ],
        }

payload = {
    "metadata": {
        "start_date": start,
        "end_date": end,
        "project": project,
        "date_basis": "author",
    },
    "data": data,
}
if ownership is not None:
    payload["ownership"] = ownership

json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
sys.stdout.write("\n")
' "$START_DATE" "$END_DATE" "$project" "$ownership_tsv" "$ownership_ref" "$ownership_ref_date" < "$tsv"
}

# -----------------------------------------------
# Emissione TEXT
# -----------------------------------------------
emit_text() {
    local tsv="$1" label="$2"
    printf "\n## Report: %s\n" "$label"
    echo "----------------------------------------------------------------------------------------------------"
    printf "%-10s %-12s %8s %12s %12s %12s %8s\n" "Giorno" "Data" "Commit" "Righe Tot." "Aggiunte" "Rimosse" "File"
    echo "----------------------------------------------------------------------------------------------------"

    awk -F'\t' '
        {
            # Campo 3 e` la ora del giorno: qui non serve, la somma per data la assorbe
            # (piu` righe per lo stesso giorno, una per ora con attivita, si aggregano su d).
            d = $2
            commits[d] += $4; added[d] += $5; deleted[d] += $6; files[d] += $7
            if (!(d in seen)) { seen[d] = 1; order[++n] = d }
            tc += $4; ta += $5; td += $6; tf += $7
            if ($4 > 0) activedays[d] = 1
        }
        END {
            # ordina le date (stringhe YYYY-MM-DD)
            for (i = 1; i <= n; i++) for (j = i + 1; j <= n; j++)
                if (order[j] < order[i]) { t = order[i]; order[i] = order[j]; order[j] = t }
            for (i = 1; i <= n; i++) {
                d = order[i]
                cmd = "date -d " d " +%a"
                cmd | getline dn
                close(cmd)
                printf "%-10s %-12s %8d %12d %12d %12d %8d\n", dn, d, commits[d], added[d] + deleted[d], added[d], deleted[d], files[d]
            }
            nd = 0
            for (d in activedays) nd++
            print "----------------------------------------------------------------------------------------------------"
            printf "%-23s %8d %12d %12d %12d %8d\n", "TOTALE:", tc, ta + td, ta, td, tf
            printf "\nGiorni attivi (con almeno 1 commit): %d\n", nd
            printf "Churn ponderato (aggiunte + 0.4 x rimosse): %.0f\n", ta + 0.4 * td
        }' "$tsv"
}

# -----------------------------------------------
# Main
# -----------------------------------------------
main() {
    # Validazioni base
    if [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
        echo "Errore: specificare date. Uso: $0 <START> <END> [text|json] [autore]" >&2; exit 1
    fi

    if ! [[ "$START_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || \
       ! [[ "$END_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        echo "Errore: Date devono essere in formato YYYY-MM-DD" >&2
        exit 1
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

    local project
    project=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)")

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

    # File temporanei
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' EXIT
    local alias_tsv="$tmpdir/aliases.tsv"
    local raw_tsv="$tmpdir/daily.tsv"
    local use_tsv="$tmpdir/filtered.tsv"

    dump_aliases_tsv > "$alias_tsv"
    [[ -s "$alias_tsv" ]] || alias_tsv=""

    collect_daily_tsv "$alias_tsv" > "$raw_tsv"

    # Filtro autore (match ESATTO, non più sottostringa).
    # I dati sono già raggruppati sotto il nome-alias, quindi un filtro espresso col nome
    # Git originale va prima risolto attraverso la mappa, altrimenti non troverebbe nulla.
    if [[ -n "$CLI_AUTHOR_FILTER" ]]; then
        local want="$CLI_AUTHOR_FILTER"
        if [[ -n "$alias_tsv" ]]; then
            local mapped
            mapped=$(awk -F'\t' -v w="$want" '$1 == w { print $2; exit }' "$alias_tsv")
            if [[ -n "$mapped" && "$mapped" != "$want" ]]; then
                echo "Autore \"$want\" risolto in \"$mapped\" tramite gli alias." >&2
                want="$mapped"
            fi
        fi
        awk -F'\t' -v want="$want" '$1 == want' "$raw_tsv" > "$use_tsv"
        if [[ ! -s "$use_tsv" ]]; then
            echo "Avviso: nessun dato per l'autore \"$CLI_AUTHOR_FILTER\" (il match è esatto)." >&2
            echo "Autori disponibili nel periodo:" >&2
            cut -d$'\t' -f1 "$raw_tsv" | sort -u | sed 's/^/  - /' >&2
        fi
    else
        cp "$raw_tsv" "$use_tsv"
    fi

    if [[ "$OUTPUT_FORMAT" == "json" ]]; then
        # Ownership: solo per json (è l'unico consumatore) e solo se non disattivata.
        # Costo non banale (un git blame per file, vedi collect_ownership_tsv): non ha
        # senso pagarlo per un output testuale che non lo usa.
        local ownership_tsv="" ownership_ref="" ownership_ref_date=""
        if [[ "$OWNERSHIP_ENABLED" == true ]]; then
            ownership_ref=$(resolve_ownership_ref)
            if [[ -n "$ownership_ref" ]]; then
                ownership_ref_date=$(git log -1 --format=%cd --date=short "$ownership_ref" 2>/dev/null)
                ownership_tsv="$tmpdir/ownership.tsv"
                collect_ownership_tsv "$ownership_ref" "$alias_tsv" "$tmpdir" > "$ownership_tsv"
            else
                echo "Avviso: nessun commit trovato prima del $END_DATE, ownership non calcolata." >&2
            fi
        fi
        emit_json "$use_tsv" "$project" "$ownership_tsv" "$ownership_ref" "$ownership_ref_date"
    else
        echo "Generazione report dal $START_DATE al $END_DATE..."
        emit_text "$use_tsv" "${CLI_AUTHOR_FILTER:-TOTALE}"
    fi
}

main
