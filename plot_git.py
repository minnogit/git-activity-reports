#!/usr/bin/env python3
"""Report di attività Git per singolo repository (granularità temporale adattiva).

Legge da stdin il JSON prodotto da git_stats_collector.sh e genera git_stats.png.

METRICHE
--------
Non esiste un singolo numero che misuri il "valore" del lavoro di sviluppo, quindi
questo report mostra TRE metriche affiancate invece di un punteggio unico:

  churn          = aggiunte + 0.4 * rimozioni
                   Le rimozioni contano: cancellare codice morto è lavoro reale.
                   Il peso < 1 riflette che rimuovere costa in genere meno che scrivere.
  commit         Numero di commit (esclusi i merge).
  giorni attivi  Giorni distinti con almeno un commit. È la metrica più robusta:
                 non è gonfiabile né da un singolo commit enorme né da tanti micro-commit.

L'indice composito resta disponibile come metrica SECONDARIA (solo in tabella):

  indice = somma sui giorni di [ 1.0 * ln(1 + min(churn_giorno, 1000))
                               + 0.5 * ln(1 + file_distinti_giorno) ]

È ADDITIVO e non moltiplicativo di proposito: nella forma a prodotto un fattore a
zero azzerava tutto (una giornata di sole cancellazioni valeva 0) e i due termini si
amplificavano a vicenda, tanto che un find/replace su 100 file superava di ~6x un fix
profondo in un solo file. Il tetto di 1000 righe è applicato PER GIORNO: applicarlo a
un aggregato di periodo lo saturava, appiattendo tutti gli autori sullo stesso valore.

ATTENZIONE: sono indicatori di attività, non misure di produttività o di qualità.
Code review, design, mentoring e debugging difficile sono strutturalmente invisibili.
"""

import json
import os
import subprocess
import sys
from datetime import date, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.ticker
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Parametri delle metriche (mantenere allineati con plot_multiproject.py)
# -----------------------------------------------------------------------------
DELETED_WEIGHT = 0.4      # quanto pesa una riga rimossa rispetto a una aggiunta
DAILY_CHURN_CAP = 1000    # tetto anti-outlier, PER GIORNO per autore
W_CHURN = 1.0             # peso del termine di volume nell'indice composito
W_FILES = 0.5             # peso del termine di dispersione su file

# -----------------------------------------------------------------------------
# Palette validata (light surface). Ordine fisso, mai ciclato: dal 9° autore in poi
# si accorpa in "Altro" invece di generare nuove tinte.
# -----------------------------------------------------------------------------
SERIES = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]
MAX_SERIES = len(SERIES)
OTHER_LABEL = "Altro"

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

OUTPUT_FILENAME = "git_stats.png"


# -----------------------------------------------------------------------------
# Configurazione (alias autori: solo per retrocompatibilità con JSON vecchi)
# -----------------------------------------------------------------------------
def find_aliases_file():
    """Ordine di ricerca del file alias; il primo trovato vince (nessun merge).

    Nota: i collector applicano già gli alias sui dati grezzi, che è il punto
    corretto per farlo (sommare metriche calcolate per identità separate non
    equivale a calcolarle sui dati uniti). Questa funzione resta solo per
    rielaborare file JSON prodotti da versioni precedenti.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    script_dir = os.path.dirname(os.path.realpath(__file__))
    for path in (
        "git-activity-aliases.json",
        os.path.join(xdg, "git-activity-reports", "git-activity-aliases.json"),
        os.path.join(xdg, "git-activity-git-activity-aliases.json"),
        os.path.join(script_dir, "git-activity-aliases.json"),
        "/etc/git-activity-reports/git-activity-aliases.json",
    ):
        if os.path.exists(path):
            return path
    return None


def load_aliases():
    path = find_aliases_file()
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            mapping = json.load(fh)
        return mapping if isinstance(mapping, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def git_project_name():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return os.path.basename(out.stdout.strip()) or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# -----------------------------------------------------------------------------
# Metriche
# -----------------------------------------------------------------------------
def churn_of(added, deleted):
    return added + DELETED_WEIGHT * deleted


def daily_index(added, deleted, files):
    """Indice composito di un singolo giorno (additivo, cap per giorno)."""
    if files <= 0:
        return 0.0
    churn = min(churn_of(added, deleted), DAILY_CHURN_CAP)
    return W_CHURN * np.log1p(churn) + W_FILES * np.log1p(files)


# -----------------------------------------------------------------------------
# Lettura input
# -----------------------------------------------------------------------------
def read_payload():
    raw = sys.stdin.read().strip()
    if not raw:
        print("Errore: Nessun dato ricevuto in input.")
        print("SUGGERIMENTO: questo script va usato in pipe, es. "
              "git_stats_collector.sh 2025-11-01 2025-11-30 json | plot_git.py")
        sys.exit(1)
    if raw[0] not in "[{":
        print("Errore: L'input non sembra un JSON valido.")
        print("SUGGERIMENTO: hai lanciato il collector con formato 'text' invece di 'json'?")
        print(f"Inizio dell'input ricevuto: {raw[:60]}...")
        sys.exit(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Errore nel parsing del JSON: {exc}")
        sys.exit(1)


def flatten(payload, aliases):
    """Restituisce (DataFrame per-giorno-per-autore, metadata)."""
    if isinstance(payload, dict) and "data" in payload:
        entries = payload["data"]
        meta = payload.get("metadata", {}) or {}
        aliases_needed = False   # i collector nuovi hanno già applicato gli alias
    elif isinstance(payload, list):
        entries = payload
        meta = {}
        aliases_needed = True    # formato legacy: alias non ancora applicati
    else:
        print("Errore: formato JSON non riconosciuto.")
        sys.exit(1)

    rows = []
    for entry in entries:
        author = entry.get("author_name") or entry.get("author") or "Sconosciuto"
        if aliases_needed:
            author = aliases.get(author, author)
        if author == "TOTALE":       # riga aggregata del formato testuale storico
            continue
        for day in entry.get("daily_data", []) or []:
            added = int(day.get("added", 0) or 0)
            deleted = int(day.get("deleted", 0) or 0)
            files = int(day.get("files", 0) or 0)
            commits = int(day.get("commits", 0) or 0)
            if commits == 0 and added == 0 and deleted == 0:
                continue         # giorno vuoto: lo ricostruiamo dal range
            rows.append({
                "date": pd.to_datetime(day["date"]),
                "author": author,
                "commits": commits,
                "added": added,
                "deleted": deleted,
                "files": files,
                "churn": churn_of(added, deleted),
                "index": daily_index(added, deleted, files),
            })

    if not rows:
        print("Nessun dato di attività trovato nel periodo: niente da rappresentare.")
        sys.exit(0)

    df = pd.DataFrame(rows)
    if not meta.get("start_date"):
        meta["start_date"] = df["date"].min().strftime("%Y-%m-%d")
    if not meta.get("end_date"):
        meta["end_date"] = df["date"].max().strftime("%Y-%m-%d")
    return df, meta


# -----------------------------------------------------------------------------
# Granularità adattiva: un grafico con una barra al giorno diventa illeggibile
# su periodi lunghi, quindi aggreghiamo automaticamente.
# -----------------------------------------------------------------------------
def choose_bucket(start, end):
    span = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if span <= 45:
        return "D", "giorno", 7
    if span <= 250:
        return "W-MON", "settimana", 4
    return "MS", "mese", 3


def assign_colors(authors_by_size):
    """Colore per entità, in ordine fisso di palette. Il colore non dipende dal rango
    all'interno di un singolo grafico: è assegnato una volta e riusato in tutti i pannelli.
    """
    colors = {}
    for i, author in enumerate(authors_by_size):
        colors[author] = SERIES[i] if i < MAX_SERIES else INK_MUTED
    colors[OTHER_LABEL] = INK_MUTED
    return colors


def fold_tail(df, authors_by_size):
    """Oltre 8 autori accorpa la coda in 'Altro' invece di generare nuove tinte."""
    if len(authors_by_size) <= MAX_SERIES:
        return df, authors_by_size
    keep = set(authors_by_size[:MAX_SERIES])
    df = df.copy()
    df["author"] = df["author"].where(df["author"].isin(keep), OTHER_LABEL)
    return df, authors_by_size[:MAX_SERIES] + [OTHER_LABEL]


# -----------------------------------------------------------------------------
# Stile
# -----------------------------------------------------------------------------
def apply_style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Liberation Sans", "sans-serif"],
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": BASELINE,
        "axes.labelcolor": INK_SECONDARY,
        "text.color": INK_PRIMARY,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "axes.grid": False,
        "legend.frameon": False,
    })


def style_axes(ax, ygrid=True):
    """Griglia e assi come hairline SOLIDE e recessive (mai tratteggiate)."""
    ax.set_axisbelow(True)
    if ygrid:
        ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, linestyle="-")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(length=0, labelsize=9)


def thin_ticks(ax, labels, max_labels=18):
    """Diradare le etichette invece di sovrapporle."""
    n = len(labels)
    step = max(1, int(np.ceil(n / max_labels)))
    positions = list(range(0, n, step))
    ax.set_xticks(positions)
    ax.set_xticklabels([labels[i] for i in positions], rotation=45, ha="right")


def thousands(ax, axis="y"):
    """Migliaia con separatore, e solo tick interi: i commit e i giorni sono conteggi,
    un tick a 0.5 li farebbe leggere come frazioni (e arrotondandolo si ottengono
    etichette duplicate)."""
    target = ax.yaxis if axis == "y" else ax.xaxis
    target.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True, nbins="auto"))
    target.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", "."))
    )


# -----------------------------------------------------------------------------
# Pannelli
# -----------------------------------------------------------------------------
def bar_width(n, plot_px=780, max_px=56):
    """Larghezza barra in unità dati, con un tetto in pixel.

    Con poche categorie una width fissa (0.7-0.8) produce blocchi enormi che riempiono
    tutta la banda: il resto della banda deve restare aria.
    """
    if n <= 0:
        return 0.78
    return min(0.78, max_px * n / plot_px)


def panel_stacked_over_time(ax, pivot, colors, labels, title, ylabel, trend_window=None):
    bottom = np.zeros(len(pivot.index))
    x = np.arange(len(pivot.index))
    width = bar_width(len(pivot.index))
    for author in pivot.columns:
        vals = pivot[author].to_numpy(dtype=float)
        ax.bar(
            x, vals, bottom=bottom, width=width,
            color=colors[author], label=author,
            # Il "gap" fra segmenti è tracciato nel colore della superficie: separa
            # senza aggiungere inchiostro (mai un bordo scuro attorno alla barra).
            edgecolor=SURFACE, linewidth=0.6,
        )
        bottom += vals

    if trend_window and len(pivot.index) >= 3:
        total = pivot.sum(axis=1)
        trend = total.rolling(window=trend_window, min_periods=1).mean()
        ax.plot(
            x, trend.to_numpy(), color=INK_PRIMARY, linewidth=2,
            label=f"Trend (media {trend_window})", zorder=5,
            solid_capstyle="round", solid_joinstyle="round",
        )

    ax.set_title(title, fontsize=12, color=INK_PRIMARY, loc="left", pad=10)
    ax.set_ylabel(ylabel, fontsize=9)
    style_axes(ax)
    thin_ticks(ax, labels)
    thousands(ax)


def panel_active_days(ax, summary, colors):
    """Giorni attivi per autore: la metrica più robusta del report."""
    data = summary.sort_values("giorni_attivi", ascending=True)
    y = np.arange(len(data))
    ax.barh(
        y, data["giorni_attivi"].to_numpy(), height=0.6,
        color=[colors[a] for a in data.index],
        edgecolor=SURFACE, linewidth=0.6,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(data.index, fontsize=9, color=INK_SECONDARY)
    ax.set_title("Giorni attivi per autore", fontsize=12, color=INK_PRIMARY,
                 loc="left", pad=10)
    ax.set_xlabel("Giorni con almeno 1 commit", fontsize=9)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, linestyle="-")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(length=0, labelsize=9)
    thousands(ax, axis="x")
    # Poche barre: l'etichetta diretta al vertice è leggibile e non affolla.
    for yi, v in zip(y, data["giorni_attivi"].to_numpy()):
        ax.text(v, yi, f" {int(v)}", va="center", ha="left",
                fontsize=9, color=INK_SECONDARY)


def panel_table(ax, summary):
    """Tabella riepilogo: rende leggibili i valori esatti di tutte le metriche.

    È anche il "relief" richiesto dalle tinte a basso contrasto della palette
    (aqua/yellow/magenta): nessun valore è raggiungibile solo tramite il colore.
    """
    ax.axis("off")
    ax.set_title("Riepilogo per autore", fontsize=12, color=INK_PRIMARY,
                 loc="left", pad=10)

    shown = summary.head(12)
    cells = []
    for author, r in shown.iterrows():
        cells.append([
            author if len(author) <= 22 else author[:21] + "…",
            f"{int(r['churn']):,}".replace(",", "."),
            f"{int(r['commit']):,}".replace(",", "."),
            f"{int(r['giorni_attivi'])}",
            f"{int(r['file']):,}".replace(",", "."),
            f"{r['indice']:.1f}",
        ])

    table = ax.table(
        cellText=cells,
        colLabels=["Autore", "Churn", "Commit", "Giorni att.", "File", "Indice"],
        colWidths=[0.34, 0.14, 0.12, 0.14, 0.12, 0.12],
        cellLoc="right", loc="upper center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.45)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(GRIDLINE)
        cell.set_linewidth(0.6)
        if col == 0:
            cell.set_text_props(ha="left")
        if row == 0:
            cell.set_text_props(color=INK_SECONDARY, weight="semibold")
            cell.set_facecolor(SURFACE)
        else:
            cell.set_text_props(color=INK_PRIMARY)
            cell.set_facecolor(SURFACE)

    note = ("Churn = aggiunte + 0.4 × rimozioni · Indice = metrica secondaria, "
            "additiva, con tetto giornaliero")
    if len(summary) > len(shown):
        note = f"Mostrati i primi {len(shown)} di {len(summary)} autori. " + note
    ax.text(0, -0.04, note, transform=ax.transAxes, fontsize=8,
            color=INK_MUTED, va="top", wrap=True)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    payload = read_payload()
    aliases = load_aliases()
    if aliases and isinstance(payload, list):
        print(f"Caricati {len(aliases)} alias autore (JSON in formato legacy).")
    df, meta = flatten(payload, aliases)

    start, end = meta["start_date"], meta["end_date"]
    project = meta.get("project") or git_project_name()

    # Ordine degli autori per churn totale: definisce l'assegnazione dei colori,
    # che poi resta la stessa in tutti i pannelli.
    by_size = (df.groupby("author")["churn"].sum()
                 .sort_values(ascending=False).index.tolist())
    df, author_order = fold_tail(df, by_size)
    colors = assign_colors(author_order)

    freq, bucket_name, trend_window = choose_bucket(start, end)

    # Reindicizzazione sul range completo: i periodi senza attività devono comparire
    # come vuoti, altrimenti il grafico comprime il tempo e il trend mente.
    full = pd.date_range(start=start, end=end, freq="D")
    grid = (df.pivot_table(index="date", columns="author",
                           values=["churn", "commits"], aggfunc="sum")
              .reindex(full).fillna(0))

    churn_pivot = grid["churn"].resample(freq).sum()
    commits_pivot = grid["commits"].resample(freq).sum()
    # Colonne nell'ordine dei colori assegnati
    cols = [a for a in author_order if a in churn_pivot.columns]
    churn_pivot = churn_pivot[cols]
    commits_pivot = commits_pivot[cols]

    label_fmt = "%Y-%m-%d" if freq == "D" else ("%Y-%m-%d" if freq == "W-MON" else "%Y-%m")
    labels = [d.strftime(label_fmt) for d in churn_pivot.index]

    summary = pd.DataFrame({
        "churn": df.groupby("author")["churn"].sum(),
        "commit": df.groupby("author")["commits"].sum(),
        "giorni_attivi": df[df["commits"] > 0].groupby("author")["date"].nunique(),
        "file": df.groupby("author")["files"].sum(),
        "indice": df.groupby("author")["index"].sum(),
    }).fillna(0).sort_values("churn", ascending=False)

    apply_style()
    fig = plt.figure(figsize=(17, 11))
    title = "Attività di sviluppo"
    if project:
        title = f"{project} — {title}"
    fig.suptitle(f"{title}  ({start} → {end}, per {bucket_name})",
                 fontsize=16, color=INK_PRIMARY, x=0.02, ha="left", y=0.975)

    ax1 = fig.add_subplot(2, 2, 1)
    panel_stacked_over_time(
        ax1, churn_pivot, colors, labels,
        f"Churn per {bucket_name}, per autore",
        "Righe (aggiunte + 0.4 × rimosse)", trend_window,
    )

    ax2 = fig.add_subplot(2, 2, 2)
    panel_stacked_over_time(
        ax2, commits_pivot, colors, labels,
        f"Commit per {bucket_name}, per autore", "Commit",
    )

    ax3 = fig.add_subplot(2, 2, 3)
    panel_active_days(ax3, summary, colors)

    ax4 = fig.add_subplot(2, 2, 4)
    panel_table(ax4, summary)

    # Una sola legenda per tutta la figura: l'identità autore è la stessa in ogni pannello.
    # Gli autori vengono prima, il trend per ultimo (non è una serie di dati).
    handles, labs = ax1.get_legend_handles_labels()
    paired = sorted(zip(labs, handles), key=lambda p: p[0].startswith("Trend"))
    labs = [p[0] for p in paired]
    handles = [p[1] for p in paired]
    fig.legend(handles, labs, loc="lower center", ncol=min(len(labs), 6),
               fontsize=9, labelcolor=INK_SECONDARY, frameon=False,
               bbox_to_anchor=(0.5, 0.005))

    fig.tight_layout(rect=[0, 0.05, 1, 0.955])
    fig.savefig(OUTPUT_FILENAME, dpi=110)
    # Messaggio invariato: l'estensione VS Code lo intercetta via regex.
    print(f"Grafico generato con successo: {OUTPUT_FILENAME}")


if __name__ == "__main__":
    main()
