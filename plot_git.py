#!/usr/bin/env python3

import sys
import json
import subprocess
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates # Importiamo il modulo per la gestione delle date
import numpy as np

def get_git_project_name():
    """Estrae il nome del progetto git dalla directory corrente."""
    try:
        # Ottieni il path della directory root del repository git
        result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], 
                              capture_output=True, text=True, check=True)
        repo_path = result.stdout.strip()
        
        # Estrai il nome della directory dal path
        project_name = os.path.basename(repo_path)
        return project_name
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Se git non è disponibile o non siamo in un repository git
        return None

def main():
    # Legge tutto l'input da stdin
    raw_input = sys.stdin.read().strip()

    if not raw_input:
        print("Errore: Nessun dato ricevuto in input.")
        sys.exit(1)

    if not raw_input.startswith('[') and not raw_input.startswith('{'):
        print("Errore: L'input non sembra un JSON valido.")
        print("SUGGERIMENTO: Hai forse lanciato g.sh con l'opzione 'text' invece di 'json'?")
        print(f"Inizio dell'input ricevuto: {raw_input[:50]}...")
        sys.exit(1)

    try:
        data = json.loads(raw_input)
    except json.JSONDecodeError as e:
        print(f"Errore nel parsing del JSON: {e}")
        sys.exit(1)

    flattened_data = []
    
    MAX_LINES_PER_DAY = 1000  # Tetto massimo per riga di codice al giorno per autore

    for entry in data:
        author = entry.get('author', 'Unknown')
        if author == "TOTALE": continue
            
        for day in entry.get('daily_data', []):
            added = day.get('added', 0)
            files = day.get('files', 0)
            
            # 1. Applicazione della strategia di tetto massimo (Ceiling)
            # Se le linee aggiunte superano il tetto, le limitiamo per non falsare il grafico
            capped_added = min(added, MAX_LINES_PER_DAY)
            
            # 2. Calcolo della Rilevanza (Impact Score)
            # Formula: log(linee_aggiunte + 1) * numero_file_modificati
            # Usiamo np.log1p che calcola log(1+x) in modo accurato
            relevance = np.log1p(capped_added) * files

            flattened_data.append({
                'date': day['date'],
                'author': author,
                'relevance': relevance, # Usiamo questa come metrica principale
                'commits': day.get('commits', 0)
            })

    if not flattened_data:
        print("Nessun dato trovato per generare il grafico.")
        sys.exit(0)

    # Creazione DataFrame
    df = pd.DataFrame(flattened_data)
    # Converti in datetime per l'ordinamento
    df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d')
    
    # Pivot dei dati: ora usiamo 'relevance' invece di 'lines'
    pivot_df = df.pivot_table(
        index='date', 
        columns='author', 
        values='relevance',
        aggfunc='sum'
    ).fillna(0)

    # Configurazione Plot
    fig, ax = plt.subplots(figsize=(14, 8)) # Creiamo figura e assi separatamente
    
    # Stacked Bar Chart
    pivot_df.plot(
        kind='bar', 
        stacked=True, 
        width=0.8, 
        colormap='tab10',
        ax=ax # Disegna sul nostro asse
    )
    
    # Formatta le etichette delle date per mostrare solo YYYY-MM-DD
    ax.set_xticks(range(len(pivot_df.index)))
    ax.set_xticklabels([d.strftime('%Y-%m-%d') for d in pivot_df.index], rotation=45, ha='right')

    # Rimuove l'etichetta "date" dall'asse X
    ax.set_xlabel('Data') 

    # Titoli e Legenda
    project_name = get_git_project_name()
    title = 'Modifiche Git per Autore'
    if project_name:
        title = f'Progetto {project_name} - {title}'
    ax.set_ylabel('Impact Score (Log lines * Files)')
    ax.set_title('Impatto Sviluppo per Autore (Dati Filtrati)')
    ax.legend(title='Autore', bbox_to_anchor=(1.02, 1), loc='upper left')
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()

    # Salvataggio
    output_filename = "git_stats.png"
    plt.savefig(output_filename)
    print(f"Grafico generato con successo: {output_filename}")

if __name__ == "__main__":
    main()
