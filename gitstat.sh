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
    git_stats_collector.sh "$START_DATE" "$END_DATE" json "$AUTHOR_FILTER" | plot_git.py
else
    git_stats_collector.sh "$START_DATE" "$END_DATE" json | plot_git.py
fi
