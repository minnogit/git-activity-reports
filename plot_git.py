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
            commits = day.get('commits', 0)

            # Se non ci sono commit, l'impatto è zero
            if commits == 0 or files == 0:
                relevance = 0
            else:
                # 1. Tetto massimo alle righe (outlier)
                capped_added = min(added, MAX_LINES_PER_DAY)
                
                # 2. DOPPIO LOGARITMO (Scala logaritmica su entrambi)
                # Questo risolve il problema dei trova/sostituisci su molti file
                relevance = np.log1p(capped_added) * np.log1p(files)

            flattened_data.append({
                'date': day['date'],
                'author': author,
                'relevance': relevance
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

    # 1. Calcoliamo l'Impact Score Totale giornaliero (somma di tutti gli autori)
    daily_total = pivot_df.sum(axis=1)

    # 2. Calcoliamo la Media Mobile a 7 giorni
    # min_periods=1 serve a mostrare la linea anche nei primi giorni del grafico
    moving_avg = daily_total.rolling(window=7, min_periods=1).mean()

    # Configurazione Plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # DISEGNO 1: Stacked Bar Chart (Dati reali)
    pivot_df.plot(
        kind='bar', 
        stacked=True, 
        width=0.8, 
        colormap='tab10',
        ax=ax,
        alpha=0.7 # Leggera trasparenza per far risaltare la linea
    )
    
    # DISEGNO 2: Linea della Media Mobile
    # Usiamo 'zorder' per assicurarci che la linea sia sopra le barre
    ax.plot(
        range(len(moving_avg)), 
        moving_avg.values, 
        color='red', 
        linewidth=3, 
        label='Trend (Media Mobile 7gg)',
        marker='o',
        markersize=4,
        zorder=5 
    )

    # Aggiorniamo la legenda per includere la Trendline
    ax.legend(title="Autori / Trend", bbox_to_anchor=(1.05, 1), loc='upper left')
    
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
    ax.legend(title="Autori / Trend", bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()

    # Salvataggio
    output_filename = "git_stats.png"
    plt.savefig(output_filename)
    print(f"Grafico generato con successo: {output_filename}")

if __name__ == "__main__":
    main()
