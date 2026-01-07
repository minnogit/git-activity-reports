#!/usr/bin/env python3
import sys
import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def main():
    # Legge l'input JSON dallo standard input (pipe)
    raw_input = sys.stdin.read().strip()

    if not raw_input:
        print("Errore: Nessun dato ricevuto in input. Assicurati di usare la pipe (|) con git_stats_collector.sh.")
        sys.exit(1)

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
            
        df = pd.DataFrame(df_data)
        
        if df.empty:
            print("Nessun dato valido nel JSON per generare i grafici.")
            sys.exit(0)
            
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Errore nel parsing del JSON: {e}")
        sys.exit(1)

    # Controlli essenziali
    if df['lines'].sum() == 0:
        print("Nessuna riga modificata trovata nel periodo specificato. Impossibile generare i grafici.")
        sys.exit(0)

    # -----------------------------------------------------
    # Preparazione dei dati per i 3 grafici
    # -----------------------------------------------------

    # 1. Grafico a barre (Progetto vs Autore)
    pivot_project_author = df.pivot_table(index='project', columns='author', values='lines', aggfunc='sum').fillna(0)
    
    # 2. Grafico a torta (Distribuzione per Progetto)
    project_totals = df.groupby('project')['lines'].sum().sort_values(ascending=False)

    # Accorpamento valori piccoli in "Altro" per migliorare leggibilità
    total_lines = project_totals.sum()
    project_percent = project_totals / total_lines
    threshold = 0.05  # Soglia del 5% per considerare un progetto "piccolo"
    small_projects = project_percent <= threshold
    if small_projects.any():
        altro_value = project_totals[small_projects].sum()
        project_totals = project_totals[~small_projects]
        project_totals['Altro'] = altro_value
        project_totals = project_totals.sort_values(ascending=False)

    # 3. Grafico a barre (Classifica Autori)
    author_totals = df.groupby('author')['lines'].sum().sort_values(ascending=False)

    # -----------------------------------------------------
    # Disegno dei 3 grafici
    # -----------------------------------------------------
    
    # Creazione di una figura con 3 sotto-grafici
    fig = plt.figure(figsize=(18, 16))
    
    # Titolo con range di date
    title = f'Analisi Git Multi-Progetto e Autore ({start_date} → {end_date})'
    plt.suptitle(title, fontsize=18, y=0.95)

    # Grafico 1: Contributo per Progetto e Autore (Stacked Bar)
    ax1 = fig.add_subplot(2, 2, 1)
    pivot_project_author.plot(
        kind='bar', 
        stacked=True, 
        ax=ax1, 
        colormap='tab10', 
        width=0.8
    )
    ax1.set_title('1. Righe Modificate per Progetto e Autore', fontsize=14)
    ax1.set_xlabel('Progetto')
    ax1.set_ylabel('Righe Totali Modificate (Add + Del)')
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
        colors=plt.cm.Set3.colors
    )
    ax2.set_title('2. Distribuzione Lavoro per Progetto (Righe)', fontsize=14)
    ax2.axis('equal') # Assicura che la torta sia circolare

    # Grafico 3: Classifica Autori (Bar Chart)
    ax3 = fig.add_subplot(2, 1, 2) # Occupando tutta la riga inferiore
    author_totals.plot(
        kind='bar', 
        ax=ax3, 
        color=plt.cm.viridis(np.linspace(0, 1, len(author_totals))),
        width=0.7
    )
    ax3.set_title('3. Righe Modificate Totali per Autore (Tutti i Progetti)', fontsize=14)
    ax3.set_xlabel('Autore')
    ax3.set_ylabel('Righe Modificate Totali')
    ax3.tick_params(axis='x', rotation=45)
    ax3.grid(axis='y', linestyle='--', alpha=0.5)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96]) # Regola layout per fare spazio al suptitle
    
    # Salvataggio
    # Crea un nome file dinamico che includa il range delle date
    # Sostituisce caratteri non validi per i nomi file
    safe_start_date = start_date.replace('→', '_to_').replace(' ', '_')
    safe_end_date = end_date.replace('→', '_to_').replace(' ', '_')
    
    output_filename = f"git_multi_project_report_{safe_start_date}_{safe_end_date}.png"
    plt.savefig(output_filename)
    print(f"\nReport multi-progetto generato con successo: {output_filename}")

if __name__ == "__main__":
    main()