#!/bin/bash

# ===============================================
# FIND GENERATED CANDIDATES
# ===============================================
#
# DESCRIZIONE:
#   Analizza un repository Git ed elenca i percorsi che dominano il churn e sono
#   candidati a essere marcati come codice generato o vendorizzato in .gitattributes
#   (vedi la sezione "Escludere il codice generato" di README.md).
#
#   NON scrive .gitattributes, NON modifica nulla nel repository: stampa solo un
#   report da verificare a mano. È deliberato — la classificazione generato/scritto
#   a mano/vendorizzato richiede giudizio umano. In sviluppo, un'etichettatura
#   automatica avrebbe marcato "old/" come generato: era codice applicativo
#   archiviato scritto a mano, non output di un tool. Ogni candidato va controllato.
#
# UTILIZZO:
#   ./find_generated_candidates.sh [OPZIONI] [percorso-repo]
#
# OPZIONI:
#   --since <data>      Limita l'analisi a partire da questa data (default: tutta la storia)
#   --threshold <pct>    Quota minima di churn per segnalare un candidato (default: 1.0)
#   --depth <n>          Profondità delle cartelle aggregate, in numero di segmenti (default: 3)
#   --top <n>            Massimo numero di candidati mostrati per sezione (default: 20)
#   -h, --help           Mostra questo help
#
# PARAMETRI POSIZIONALI:
#   percorso-repo        Repository da analizzare (default: cartella corrente)
#
# COSA FA (in due fasi, non una: la prima fase esiste perché leggere solo la
# configurazione ATTUALE di un generatore non basta — se l'output si è spostato nel
# tempo, la posizione attuale può avere churn quasi nullo mentre la storia vera sta
# in una posizione precedente che nessun file di configurazione attuale menziona):
#
#   FASE 1 — Trova i generatori e la LORO storia:
#     - legge il campo "output" di ogni schema.prisma nel repository
#     - per ciascun output, cerca file con lo stesso nome sotto prefissi diversi
#       nella storia (stesso meccanismo delle "posizioni storiche" del README):
#       quei prefissi sono anch'essi output dello stesso generatore, anche se lo
#       schema.prisma attuale non li menziona più
#
#   FASE 2 — Classifica i percorsi che dominano il churn:
#     - dentro un percorso noto dalla Fase 1 -> evidenza FORTE (generatore Prisma)
#     - contiene un marcatore esplicito nel contenuto ("@generated", "DO NOT EDIT") -> FORTE
#     - nome tipico di libreria vendorizzata (vendor, third_party...) -> MEDIA, da confermare
#     - nessuna evidenza -> DEBOLE, solo i numeri: verificare a mano cosa li produce
#
#   Salta i percorsi già coperti da linguist-generated/linguist-vendored in un
#   .gitattributes esistente.
#
# ESEMPI:
#   ./find_generated_candidates.sh
#   ./find_generated_candidates.sh --since 2026-01-01 --threshold 2 ~/Workspace/plservice1
#   ./find_generated_candidates.sh --depth 4 --top 10 ~/Workspace/pls-backend-api
#
# REQUISITI:
#   Bash 4.0+, Git, awk, python3 (risoluzione dei percorsi "output" di Prisma)
#
# AUTORE: Michele Innocenti
# VERSIONE: 1.1
# DATA: Agosto 2026
# ===============================================

SINCE=""
THRESHOLD="1.0"
DEPTH=3
TOP=20
REPO_PATH="."

while [[ $# -gt 0 ]]; do
    case $1 in
        --since)
            SINCE="$2"; shift 2 ;;
        --threshold)
            THRESHOLD="$2"; shift 2 ;;
        --depth)
            DEPTH="$2"; shift 2 ;;
        --top)
            TOP="$2"; shift 2 ;;
        -h|--help)
            sed -n '3,66p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        -*)
            echo "Opzione non valida: $1" >&2; exit 1 ;;
        *)
            REPO_PATH="$1"; shift ;;
    esac
done

if ! cd "$REPO_PATH" 2>/dev/null; then
    echo "Errore: impossibile accedere a $REPO_PATH" >&2
    exit 1
fi
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Errore: $REPO_PATH non è un repository Git." >&2
    exit 1
fi
REPO_PATH="$(git rev-parse --show-toplevel)"
cd "$REPO_PATH"

# Formattazione numerica indipendente dalla locale: con LC_NUMERIC che usa la virgola
# come separatore decimale, il printf builtin di bash rifiuta un numero come "63.28"
# prodotto da awk (punto). Facciamo fare ad awk anche l'arrotondamento per la stampa,
# e in bash trattiamo tutto come stringa (%s), mai come numero (%f).
fmt1() { awk -v n="$1" 'BEGIN{printf "%.1f", n}'; }

# Stessa lista di esclusioni di default dei collector (duplicata di proposito, come il
# resto del progetto: vedi CLAUDE.md). Qui NON includiamo gli :(exclude,attr:...) — è
# proprio quello che stiamo cercando di scoprire.
EXCLUDE_PATHSPEC=(
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

SINCE_ARGS=()
[[ -n "$SINCE" ]] && SINCE_ARGS=(--since="$SINCE")

echo "Repository: $REPO_PATH"
if [[ -n "$SINCE" ]]; then echo "Periodo: da $SINCE a oggi"; else echo "Periodo: intera storia"; fi
echo "Soglia: ${THRESHOLD}% del churn totale (dopo le esclusioni di default) · profondità cartelle: $DEPTH"
echo

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# -----------------------------------------------
# Percorsi già coperti in .gitattributes: da non riproporre
# -----------------------------------------------
is_already_declared() {
    local path="$1" probe
    [[ -f .gitattributes ]] || return 1
    probe="$path"
    [[ -d "$path" ]] && probe="$path/__probe__"
    git check-attr linguist-generated linguist-vendored -- "$probe" 2>/dev/null | grep -qv ": unspecified"
}

# -----------------------------------------------
# Trova, per un percorso CHE ESISTE ORA, altri prefissi nella storia che hanno
# contenuto file con lo stesso nome (indizio di spostamento di una directory intera:
# lo stesso meccanismo di scoperta usato a mano nel README per i client OpenAPI/Prisma).
# -----------------------------------------------
historical_positions_for() {
    local candidate="$1"
    local names hits
    names=$(git ls-tree -r HEAD --name-only -- "$candidate" 2>/dev/null | xargs -n1 basename 2>/dev/null | sort -u | head -6)
    [[ -z "$names" ]] && return 0
    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        hits=$(git log --pretty=format: --name-only --no-renames -- "**/$name" 2>/dev/null | grep -F "/$name")
        [[ -z "$hits" ]] && continue
        while IFS= read -r hit; do
            local dir="${hit%/*}"
            [[ "$dir" == "$hit" ]] && continue
            printf '%s\n' "$dir"
        done <<< "$hits"
    done <<< "$names"
}

# -----------------------------------------------
# FASE 1 — Generatori Prisma e le loro posizioni storiche
# -----------------------------------------------
# GENERATED_ROOTS: un prefisso di percorso PER RIGA, ciascuno associato (in un file
# separato con lo stesso indice) alla fonte che lo giustifica.
GEN_PATHS="$TMPDIR/gen_paths.txt"
GEN_SOURCES="$TMPDIR/gen_sources.txt"
: > "$GEN_PATHS"; : > "$GEN_SOURCES"

add_generated_root() {
    local path="$1" source="$2"
    printf '%s\n' "$path" >> "$GEN_PATHS"
    printf '%s\t%s\n' "$path" "$source" >> "$GEN_SOURCES"
}

while IFS= read -r schema; do
    out=$(sed -n '/^generator/,/^}/p' "$schema" | sed -n 's/^[[:space:]]*output[[:space:]]*=[[:space:]]*"\(.*\)"/\1/p')
    [[ -z "$out" ]] && continue
    resolved=$(python3 -c "
import os, sys
schema_dir = os.path.dirname(sys.argv[1])
print(os.path.normpath(os.path.join(schema_dir, sys.argv[2])))
" "$schema" "$out" 2>/dev/null)
    [[ -z "$resolved" ]] && continue
    [[ -d "$resolved" ]] || continue   # posizione attuale: deve esistere per enumerare i nomi file

    add_generated_root "$resolved" "generatore Prisma ($schema)"
    while IFS= read -r histdir; do
        [[ -z "$histdir" ]] && continue
        [[ "$histdir" == "$resolved" ]] && continue
        add_generated_root "$histdir" "generatore Prisma ($schema) — posizione storica"
    done < <(historical_positions_for "$resolved")
done < <(find . -name "schema.prisma" -not -path "*/node_modules/*" 2>/dev/null)

sort -u -o "$GEN_PATHS" "$GEN_PATHS"

lookup_generated_source() {
    # Prisma genera nomi di file generici (browser.ts, client.ts...) identici per ogni
    # datasource: la ricerca storica per nome-file può incrociare due generatori diversi
    # che condividono quei nomi. Quando succede, non scegliamo arbitrariamente una delle
    # due fonti come "quella giusta" — le elenchiamo entrambe e lasciamo la verifica a chi
    # legge, coerente con il resto dello script (non affermare come certo ciò che non lo è).
    #
    # Nota: NON si sceglie il match "più lungo/specifico" — un candidato può cadere sotto
    # più voci di GEN_SOURCES a profondità diverse (la posizione radice di un generatore
    # E una sua sottocartella come .../models, entrambe aggiunte da historical_positions_for,
    # che registra il genitore immediato di ogni file trovato, non solo la radice comune).
    # Scartare i match "meno specifici" perdeva così ambiguità reali tra le due radici.
    local candidate="$1" p src found=0 sources=""
    [[ -s "$GEN_SOURCES" ]] || return 1
    while IFS=$'\t' read -r p src; do
        if [[ "$candidate" == "$p" || "$candidate" == "$p"/* || "$p" == "$candidate"/* ]]; then
            found=1
            [[ "$sources" == *"$src"* ]] || sources+="${sources:+$'\n'}$src"
        fi
    done < "$GEN_SOURCES"
    [[ $found -eq 1 ]] || return 1
    if [[ "$sources" == *$'\n'* ]]; then
        # paste -d cicla i CARATTERI del delimitatore su righe successive (non la stringa
        # intera): con un delimitatore multi-carattere come "; " alterna ';' e ' ' invece
        # di ripetere "; " ogni volta. Sostituzione bash diretta invece di paste.
        echo "possibile ambiguità tra generatori — verificare quale: ${sources//$'\n'/; }"
    else
        echo "$sources"
    fi
    return 0
}

# -----------------------------------------------
# Evidenza: marcatore "generated" nel contenuto (campione di file)
# -----------------------------------------------
content_marker_evidence_for() {
    local candidate="$1" f
    while IFS= read -r f; do
        head -c 2000 "$f" 2>/dev/null | grep -qiE '@generated|do not edit|generated by|automatically generated|code generated' \
            && { echo "$f"; return 0; }
    done < <(find "$candidate" -maxdepth 3 -type f 2>/dev/null | head -8)
    return 1
}

# -----------------------------------------------
# Evidenza debole: nome tipico di libreria vendorizzata
# -----------------------------------------------
vendored_name_evidence_for() {
    local base
    base=$(basename "$1")
    [[ "$base" =~ ^(vendor|vendored|third[-_]?party|external|libs?|3rdparty)$ ]]
}

# -----------------------------------------------
# Raccolta churn (un solo git log)
# -----------------------------------------------
RAW="$TMPDIR/raw.tsv"
git log --no-merges "${SINCE_ARGS[@]}" --pretty=format: --numstat -- . "${EXCLUDE_PATHSPEC[@]}" 2>/dev/null \
    | awk -F'\t' 'NF>=3 && $1 ~ /^[0-9]+$/ {print $1"\t"$2"\t"$3}' > "$RAW"

if [[ ! -s "$RAW" ]]; then
    echo "Nessun dato di churn trovato (repository vuoto o periodo senza attività)."
    exit 0
fi
TOTAL_CHURN=$(awk -F'\t' '{a+=$1; d+=$2} END{printf "%.0f", a+0.4*d}' "$RAW")
if [[ "$TOTAL_CHURN" == "0" ]]; then
    echo "Churn totale nullo: niente da analizzare."
    exit 0
fi

FILES_CANDIDATES="$TMPDIR/files.tsv"
awk -F'\t' -v total="$TOTAL_CHURN" -v thr="$THRESHOLD" '
    { churn[$3] += $1 + 0.4*$2 }
    END {
        for (p in churn) {
            pct = churn[p] * 100 / total
            if (pct >= thr) printf "%.4f\t%.0f\t%s\n", pct, churn[p], p
        }
    }' "$RAW" | sort -t$'\t' -k1,1 -rn > "$FILES_CANDIDATES"

DIRS_CANDIDATES="$TMPDIR/dirs.tsv"
awk -F'\t' -v total="$TOTAL_CHURN" -v thr="$THRESHOLD" -v depth="$DEPTH" '
    {
        n = split($3, parts, "/")
        lim = (n < depth) ? n : depth
        key = parts[1]
        for (i = 2; i <= lim; i++) key = key "/" parts[i]
        churn[key] += $1 + 0.4*$2
    }
    END {
        for (p in churn) {
            pct = churn[p] * 100 / total
            if (pct >= thr) printf "%.4f\t%.0f\t%s\n", pct, churn[p], p
        }
    }' "$RAW" | sort -t$'\t' -k1,1 -rn > "$DIRS_CANDIDATES"

# -----------------------------------------------
# FASE 2 — Report
# -----------------------------------------------
report_section() {
    local title="$1" file="$2"
    echo "════════════════════════════════════════════════════════════"
    echo "$title"
    echo "════════════════════════════════════════════════════════════"
    local shown=0
    while IFS=$'\t' read -r pct churn path; do
        [[ $shown -ge $TOP ]] && break
        is_already_declared "$path" && continue

        local evidence="" tag="DEBOLE" suggestion="" gensrc marker
        if gensrc=$(lookup_generated_source "$path"); then
            evidence="$gensrc"
            tag="FORTE"; suggestion="linguist-generated"
        elif marker=$(content_marker_evidence_for "$path"); then
            evidence="marcatore 'generated' trovato in $marker"
            tag="FORTE"; suggestion="linguist-generated"
        elif vendored_name_evidence_for "$path"; then
            evidence="nome tipico di libreria vendorizzata — DA CONFERMARE"
            tag="MEDIA"; suggestion="linguist-vendored"
        else
            evidence="nessuna evidenza automatica — verificare a mano cosa produce questi numeri"
        fi

        printf "\n[%s] %s\n" "$tag" "$path"
        printf "    churn: %s (%s%% del totale)\n" "$churn" "$(fmt1 "$pct")"
        printf "    evidenza: %s\n" "$evidence"
        [[ -n "$suggestion" ]] && printf "    riga suggerita:  %s/**    %s\n" "$path" "$suggestion"
        shown=$((shown+1))
    done < "$file"
    [[ $shown -eq 0 ]] && echo "(nessun candidato sopra la soglia, o già tutti dichiarati in .gitattributes)"
    echo
}

if [[ -s "$GEN_PATHS" ]]; then
    echo "════════════════════════════════════════════════════════════"
    echo "GENERATORI RILEVATI (Prisma) — posizione attuale + storiche"
    echo "════════════════════════════════════════════════════════════"
    echo "(solo le posizioni con almeno una riga di churn nel periodo analizzato)"
    while IFS= read -r p; do
        c=$(awk -F'\t' -v p="$p" '$3==p || index($3,p"/")==1{s+=$1+0.4*$2} END{printf "%.0f", s+0}' "$RAW")
        [[ "$c" == "0" ]] && continue
        src=$(lookup_generated_source "$p")
        printf "\n%s\n    churn: %s — %s\n" "$p" "$c" "$src"
    done < "$GEN_PATHS"
    echo
fi

report_section "CANDIDATI — FILE SINGOLI" "$FILES_CANDIDATES"
report_section "CANDIDATI — CARTELLE AGGREGATE (profondità $DEPTH)" "$DIRS_CANDIDATES"

echo "Nota: questo script non modifica nulla. Verifica ogni candidato — in particolare"
echo "quelli senza evidenza FORTE — prima di aggiungerlo a .gitattributes. Vedi la sezione"
echo "'Escludere il codice generato' del README per il formato e le trappole note"
echo "(percorsi storici, forma booleana dell'attributo, linguist-generated vs -vendored)."
