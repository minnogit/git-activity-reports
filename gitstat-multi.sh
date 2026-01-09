#!/bin/bash

# ===============================================
# GIT STATS MULTI - Multi Repository
# ===============================================
#
# DESCRIZIONE:
#   Comando semplificato per analizzare e visualizzare statistiche Git
#   di più repository contemporaneamente.
#
# UTILIZZO:
#   gitstats-multi <DATA_INIZIO> <DATA_FINE> [percorso1] [percorso2] ...
#
# PARAMETRI:
#   DATA_INIZIO    Data inizio periodo (YYYY-MM-DD) - OBBLIGATORIO
#   DATA_FINE      Data fine periodo (YYYY-MM-DD) - OBBLIGATORIO
#   percorsoN      Percorsi ai repository Git (opzionali, default: corrente)
#
# ESEMPI:
#   # Analizza repository corrente
#   gitstats-multi 2025-12-01 2025-12-31
#   
#   # Analizza repository specifici
#   gitstats-multi 2025-12-01 2025-12-31 ~/progetti/repo1 ~/progetti/repo2
#   
#   # Con file di configurazione
#   gitstats-multi --file progetti.txt 2025-12-01 2025-12-31
#
# REQUISITI:
#   - git_multiproject_stats_collector.sh e plot_multiproject.py devono essere disponibili globalmente
#   - Python3 con pandas e matplotlib installati
#
# AUTORE: Michele Innocenti
# VERSIONE: 1.0
# DATA: Gennaio 2026
# ===============================================

if [[ $# -lt 2 ]]; then
    echo "Uso: $0 <DATA_INIZIO> <DATA_FINE> [opzioni] [percorsi...]"
    echo "Esempio: $0 2025-12-01 2025-12-31"
    echo "Esempio con repository specifici: $0 2025-12-01 2025-12-31 ~/repo1 ~/repo2"
    echo "Esempio con file: $0 --file repos.txt 2025-12-01 2025-12-31"
    exit 1
fi

# Verifica che gli strumenti siano disponibili
if ! command -v git_multiproject_stats_collector.sh >/dev/null 2>&1; then
    echo "Errore: git_multiproject_stats_collector.sh non trovato globalmente"
    exit 1
fi

if ! command -v plot_multiproject.py >/dev/null 2>&1; then
    echo "Errore: plot_multiproject.py non trovato globalmente"
    exit 1
fi

# Esegui il comando
git_multiproject_stats_collector.sh "$@" | plot_multiproject.py
