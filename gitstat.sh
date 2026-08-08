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
#   gitstats [--fetch] [--repo <path|url>] <DATA_INIZIO> <DATA_FINE> [autore]
#
# PARAMETRI:
#   DATA_INIZIO    Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
#   DATA_FINE      Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
#   autore         Filtra per autore specifico (opzionale)
#
# OPZIONI:
#   --fetch            Abilita l'aggiornamento del repository con git fetch (passata a git_stats_collector.sh)
#   --repo <path|url>  Analizza questo repository (path locale o URL) invece della cartella corrente
#
# ESEMPI:
#   # Report per tutti gli autori
#   gitstats 2025-12-01 2025-12-31
#
#   # Report per autore specifico
#   gitstats 2025-12-01 2025-12-31 "Mario Rossi"
#
#   # Repository remoto
#   gitstats --repo https://github.com/org/repo.git 2025-12-01 2025-12-31
#
# REQUISITI:
#   - git_stats_collector.sh e plot_git.py devono essere disponibili globalmente
#   - Python3 con pandas e matplotlib installati
#   - Essere in una cartella di repository Git (salvo che si usi --repo)
#
# AUTORE: Michele Innocenti
# VERSIONE: 1.1
# DATA: Gennaio 2026
# ===============================================

FETCH_ARG=""
REPO_ARG=""
TEMP_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --fetch)
            FETCH_ARG="--fetch"
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
        *)
            TEMP_ARGS+=("$1")
            shift
            ;;
    esac
done
set -- "${TEMP_ARGS[@]}"

if [[ $# -lt 2 ]]; then
    echo "Uso: $0 [--fetch] [--repo <path|url>] <DATA_INIZIO> <DATA_FINE> [autore]"
    echo "Esempio: $0 2025-12-01 2025-12-31"
    echo "Esempio con autore: $0 2025-12-01 2025-12-31 'Mario Rossi'"
    echo "Esempio con repository remoto: $0 --repo https://github.com/org/repo.git 2025-12-01 2025-12-31"
    exit 1
fi

START_DATE="$1"
END_DATE="$2"
AUTHOR_FILTER="${3:-}"

# Verifica che siamo in un repository git (solo se non stiamo puntando a un repository remoto/altrove)
if [[ -z "$REPO_ARG" ]] && ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
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

# Costruisce gli argomenti per git_stats_collector.sh
COLLECTOR_ARGS=()
[[ -n "$FETCH_ARG" ]] && COLLECTOR_ARGS+=("$FETCH_ARG")
[[ -n "$REPO_ARG" ]] && COLLECTOR_ARGS+=(--repo "$REPO_ARG")
COLLECTOR_ARGS+=("$START_DATE" "$END_DATE" json)
[[ -n "$AUTHOR_FILTER" ]] && COLLECTOR_ARGS+=("$AUTHOR_FILTER")

git_stats_collector.sh "${COLLECTOR_ARGS[@]}" | plot_git.py
