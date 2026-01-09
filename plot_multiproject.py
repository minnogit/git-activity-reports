#!/usr/bin/env python3

import sys
import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def main():
    # Legge l'input JSON dallo standard input (pipe)
    raw_input = sys.stdin.read().strip()

    if not raw_input:
        print("Errore: Nessun dato ricevuto in input. Assicurati di usare la pipe (|) con git_stats_collector.sh.")
        sys.exit(1)

    # Caricamento opzionale da file
    if os.path.exists("aliases.json"):
        with open("aliases.json", "r") as f:
            author_mapping = json.load(f)
        print(f"Caricati {len(author_mapping)} alias da aliases.json")
    else:
        author_mapping = {}
        print("Nessun file aliases.json trovato, nessun raggruppamento autori effettuato")

    try:
        data = json.loads(raw_input)
        
        # Gestione del nuovo formato con metadata
        if isinstance(data, dict) and 'data' in data and 'metadata' in data:
            start_date = data['metadata']['start_date']
            end_date = data['metadata']['end_date']
            df_data = data['data']
        elif isinstance(data, list):
            # Formato legacy senza metadata
            start_date = "N/A"
            end_date = "N/A"
            df_data = data
        else:
            raise ValueError("Formato JSON non riconosciuto")
            
        # CALCOLO IMPACT SCORE (RELEVANCE) E RAGGRUPPAMENTO ALIAS
        processed_data = []
        for entry in df_data:
            # Recuperiamo il nome originale dal JSON
            raw_author = entry.get('author_name', entry.get('author', 'Unknown'))
            
            # RAGGRUPPAMENTO: Se il nome è nella mappa, lo sostituiamo,
            # altrimenti teniamo quello originale
            author = author_mapping.get(raw_author, raw_author)
            
            added = entry.get('added', 0)
            files = entry.get('files', 0)
            commits = entry.get('commits', 0)
            
            if commits == 0 or files == 0:
                relevance = 0
            else:
                # Formula: Impact Score = ln(min(added, 1000) + 1) * ln(files + 1)
                capped_added = min(added, 1000)
                relevance = np.log1p(capped_added) * np.log1p(files)
            
            # Aggiorniamo l'autore con il nome mappato
            entry['author'] = author
            entry['relevance'] = relevance
            processed_data.append(entry)

        df = pd.DataFrame(processed_data)
        
        if df.empty:
            print("Nessun dato valido nel JSON per generare i grafici.")
            sys.exit(0)
            
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Errore nel parsing del JSON: {e}")
        sys.exit(1)

    # Controlli essenziali
    if df['relevance'].sum() == 0:
        print("Nessun impatto trovato nel periodo specificato. Impossibile generare i grafici.")
        sys.exit(0)

    # -----------------------------------------------------
    # Preparazione dei dati per i 3 grafici
    # I dati contengono già gli autori con nomi mappati tramite aliases.json
    # -----------------------------------------------------

    # 1. Grafico a barre (Progetto vs Autore)
    pivot_project_author = df.pivot_table(index='project', columns='author', values='relevance', aggfunc='sum').fillna(0)
    
    # 2. Grafico a torta (Distribuzione per Progetto)
    project_totals = df.groupby('project')['relevance'].sum().sort_values(ascending=False)

    # Accorpamento valori piccoli in "Altro" per migliorare leggibilità
    total_relevance = project_totals.sum()
    project_percent = project_totals / total_relevance
    threshold = 0.02  # Soglia del 2% per considerare un progetto "piccolo"
    small_projects = project_percent <= threshold
    if small_projects.any():
        altro_value = project_totals[small_projects].sum()
        project_totals = project_totals[~small_projects]
        project_totals['Altro'] = altro_value
        project_totals = project_totals.sort_values(ascending=False)

    # 3. Grafico a barre (Classifica Autori)
    author_totals = df.groupby('author')['relevance'].sum().sort_values(ascending=False)

    # -----------------------------------------------------
    # Disegno dei 3 grafici
    # -----------------------------------------------------
    
    # Creazione di una figura con 3 sotto-grafici
    fig = plt.figure(figsize=(18, 16))
    
    # I grafici utilizzeranno i nomi degli autori già mappati tramite aliases.json
    # Titolo con range di date
    title = f'Analisi Impatto Sviluppo Multi-Progetto e Autore ({start_date} → {end_date})'
    plt.suptitle(title, fontsize=18, y=0.95)

    # Grafico 1: Contributo per Progetto e Autore (Stacked Bar)
    ax1 = fig.add_subplot(2, 2, 1)
    pivot_project_author.plot(
        kind='bar', 
        stacked=True, 
        ax=ax1, 
        colormap='tab20', 
        width=0.8
    )
    ax1.set_title('1. Impatto Sviluppo per Progetto e Autore', fontsize=14)
    ax1.set_xlabel('Progetto')
    ax1.set_ylabel('Impact Score (Log lines * Files)')
    ax1.tick_params(axis='x', rotation=45)
    ax1.legend(title='Autore', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid(axis='y', linestyle='--', alpha=0.5)

    # Grafico 2: Distribuzione per Progetto (Donut Chart)
    ax2 = fig.add_subplot(2, 2, 2)
    wedges, texts, autotexts = ax2.pie(
        project_totals,
        labels=project_totals.index,
        autopct='%1.1f%%',
        startangle=90,
        wedgeprops=dict(width=0.4), # Trasforma il Pie in Donut
        pctdistance=0.75,
        colors=plt.cm.tab20.colors
    )
    ax2.set_title('2. Distribuzione Lavoro per Progetto (Impact)', fontsize=14)
    ax2.axis('equal') # Assicura che la torta sia circolare

    # Grafico 3: Classifica Autori (Bar Chart)
    ax3 = fig.add_subplot(2, 1, 2) # Occupando tutta la riga inferiore
    author_totals.plot(
        kind='bar',
        ax=ax3,
        color=plt.cm.viridis(np.linspace(0, 1, len(author_totals))),
        width=0.7
    )
    ax3.set_title('3. Impact Score Totale per Autore (Tutti i Progetti)', fontsize=14)
    ax3.set_xlabel('Autore')
    ax3.set_ylabel('Impact Score Totale')
    ax3.tick_params(axis='x', rotation=45)
    ax3.grid(axis='y', linestyle='--', alpha=0.5)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96]) # Regola layout per fare spazio al suptitle
    
    # Salvataggio
    # Crea un nome file dinamico che includa il range delle date
    # Sostituisce caratteri non validi per i nomi file
    safe_start_date = start_date.replace('→', '_to_').replace(' ', '_')
    safe_end_date = end_date.replace('→', '_to_').replace(' ', '_')
    
    output_filename = f"git_impact_multi_project_report_{safe_start_date}_{safe_end_date}.png"
    plt.savefig(output_filename)
    print(f"\nReport multi-progetto (Impact Score) generato con successo: {output_filename}")

if __name__ == "__main__":
    main()