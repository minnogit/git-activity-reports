#!/usr/bin/env python3
"""Report comparativo di attività Git su più repository.

Legge da stdin il JSON prodotto da git_multiproject_stats_collector.sh e genera un PNG.

METRICHE
--------
Non esiste un singolo numero che misuri il "valore" del lavoro di sviluppo, quindi
questo report mostra TRE metriche affiancate invece di un punteggio unico, in ordine
di quanto sono attendibili — non di quanto sono impressionanti:

  giorni attivi  Giorni distinti con almeno un commit. È la metrica più robusta:
                 non è gonfiabile né da un singolo commit enorme né da tanti micro-commit,
                 e non risente in alcun modo di codice generato o file voluminosi.
                 Primo pannello (da solo, a piena larghezza).
  commit         Numero di commit (esclusi i merge). RIGA 2, interamente sua: barre
                 impilate per progetto e autore, più la ciambella di distribuzione per
                 progetto affiancata (la stessa cosa a due livelli di dettaglio).
  churn          = aggiunte + 0.4 * rimozioni
                   Le rimozioni contano: cancellare codice morto è lavoro reale.
                   È la meno indicativa delle tre: git_multiproject_stats_collector.sh
                   NON esclude codice generato, vendorizzato o lock file (vedi il
                   commento in testa a quello script per il perché — in breve, qualunque
                   esclusione basata su directory può rompere il rilevamento dei rename
                   di git, misurato fino a 9.7x di inflazione su una singola giornata).
                   RIGA 3, stesso trattamento del commit (barre impilate + ciambella
                   affiancate) ma sotto, non sopra: coerenza fra "quanto è attendibile" e
                   "quanto è in evidenza" era assente nelle versioni precedenti, dove il
                   churn occupava DUE pannelli e il commit zero, nascosto nella sola
                   tabella.

Una riga per metrica, non una riga per tipo di grafico. Un layout precedente affiancava
commit e churn sulla stessa riga per permetterne il confronto diretto: non funzionava,
perché ogni pannello ordina i progetti per il PROPRIO totale e la posizione sull'asse x
non corrisponde fra i due (misurato: commit e churn producono ordinamenti completamente
diversi appena un progetto ha commit grossi, es. un client rigenerato) — si finiva per
confrontare progetti diversi. Un confronto commit-vs-churn onesto richiede un pannello
dedicato (es. churn per commit per progetto), non due pannelli affiancati; per ora la
tabella di riepilogo resta il posto dove leggere le due metriche sullo stesso progetto.

L'indice composito resta disponibile come metrica SECONDARIA (solo in tabella):

  indice = somma sui giorni di [ 1.0 * ln(1 + min(churn_giorno, 15000))
                               + 0.5 * ln(1 + file_distinti_giorno) ]

È ADDITIVO e non moltiplicativo di proposito, e il tetto (15000 righe, p99 osservato
su repository reali con AI coding assistant — la cifra originale di 1000 risaliva a
un modello di sviluppo antecedente) è applicato PER GIORNO. Nella versione precedente
il tetto veniva applicato all'aggregato di periodo: su qualsiasi intervallo più lungo
di pochi giorni si saturava, e l'indice finiva per dipendere solo dal numero di file
toccati (tutti gli autori attivi ottenevano lo stesso valore di volume).

ATTENZIONE: sono indicatori di attività, non misure di produttività o di qualità.
Code review, design, mentoring e debugging difficile sono strutturalmente invisibili.
"""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.ticker
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Parametri delle metriche (mantenere allineati con plot_git.py)
# -----------------------------------------------------------------------------
DELETED_WEIGHT = 0.4      # quanto pesa una riga rimossa rispetto a una aggiunta
DAILY_CHURN_CAP = 15000   # tetto anti-outlier, PER GIORNO per autore
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
DONUT_MAX_SLICES = 6      # part-to-whole resta leggibile solo con pochi settori
MAX_PROJECT_BARS = 12     # oltre, le etichette sull'asse X dei progetti si sovrappongono
MAX_TABLE_ROWS = 12       # righe di progetto mostrate in tabella (il resto va nella nota)

# -----------------------------------------------------------------------------
# Geometria della figura (vedi il commento sul layout in main())
# -----------------------------------------------------------------------------
# L'altezza della tabella di riepilogo NON dipende dall'altezza dell'asse che la
# contiene: le celle sono dimensionate dal font, non dai limiti dell'asse. Misurato
# (fontsize 9 + `table.scale(1, 1.45)` in panel_table): 0.289 pollici per riga, header
# incluso, e l'altezza dell'asse resta 4.627" a prescindere dal numero di righe. Con un
# height_ratio fisso, un report con 3 progetti lasciava quindi ~3.5" di banda vuota sotto
# la tabella. Se si cambiano fontsize o scale in panel_table, questa costante va rimisurata
# (bastano due render con conteggi di righe diversi: l'altezza è lineare nelle righe).
TABLE_ROW_INCHES = 0.289
TABLE_PAD_INCHES = 0.45   # respiro sotto l'ultima riga, prima della nota e della legenda
ROW_UNIT_INCHES = 3.427   # altezza in pollici di UNA unità di height_ratio: mantenerla
                          # costante lascia le prime tre righe della stessa dimensione
                          # assoluta qualunque sia l'altezza della tabella
TABLE_RATIO_MIN = 0.30    # una tabella con una riga sola non deve collassare
FIG_WIDTH_INCHES = 17
FIG_HSPACE = 0.5
# Header e footer in POLLICI, non in frazione di figura: da quando l'altezza totale varia
# col numero di progetti, una frazione fissa restringeva lo spazio assoluto sopra e sotto
# (misurato: con 3 progetti il suptitle finiva sopra il titolo del primo pannello). Con
# valori assoluti il margine resta identico a qualunque altezza di figura.
HEADER_INCHES = 0.95      # spazio sopra la prima riga: suptitle + titolo del pannello
FOOTER_INCHES = 0.75      # spazio sotto l'ultima riga: nota della tabella + legenda
SUPTITLE_INCHES = 0.42    # distanza del suptitle dal bordo superiore
LEGEND_INCHES = 0.21      # distanza della legenda dal bordo inferiore

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"


# -----------------------------------------------------------------------------
# Configurazione (alias autori: solo per retrocompatibilità con JSON vecchi)
# -----------------------------------------------------------------------------
def find_aliases_file():
    """Ordine di ricerca del file alias; il primo trovato vince (nessun merge).

    Nota: i collector applicano già gli alias sui dati grezzi, che è il punto
    corretto per farlo. Questa funzione resta solo per rielaborare file JSON
    prodotti da versioni precedenti.
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
              "git_multiproject_stats_collector.sh --file repos.txt 2025-11-01 2025-11-30 "
              "| plot_multiproject.py")
        sys.exit(1)
    if raw[0] not in "[{":
        print("Errore: L'input non sembra un JSON valido.")
        print(f"Inizio dell'input ricevuto: {raw[:60]}...")
        sys.exit(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Errore nel parsing del JSON: {exc}")
        sys.exit(1)


def flatten(payload, aliases):
    """Restituisce (DataFrame per progetto/autore, metadata)."""
    if isinstance(payload, dict) and "data" in payload:
        entries = payload["data"]
        meta = payload.get("metadata", {}) or {}
        aliases_needed = False
    elif isinstance(payload, list):
        entries = payload
        meta = {}
        aliases_needed = True
    else:
        print("Errore: formato JSON non riconosciuto.")
        sys.exit(1)

    rows = []
    legacy_aggregate = False
    for entry in entries:
        author = entry.get("author_name") or entry.get("author") or "Sconosciuto"
        if aliases_needed:
            author = aliases.get(author, author)
        project = entry.get("project", "?")
        days = entry.get("daily_data") or []

        if days:
            index = sum(
                daily_index(int(d.get("added", 0) or 0),
                            int(d.get("deleted", 0) or 0),
                            int(d.get("files", 0) or 0))
                for d in days
            )
            active_days = entry.get("active_days")
            if active_days is None:
                active_days = sum(1 for d in days if int(d.get("commits", 0) or 0) > 0)
        else:
            # Formato legacy senza dettaglio giornaliero: l'indice va calcolato
            # sull'aggregato, dove il tetto anti-outlier satura. Lo segnaliamo.
            legacy_aggregate = True
            index = daily_index(int(entry.get("added", 0) or 0),
                                int(entry.get("deleted", 0) or 0),
                                int(entry.get("files", 0) or 0))
            active_days = entry.get("active_days") or 0

        added = int(entry.get("added", 0) or 0)
        deleted = int(entry.get("deleted", 0) or 0)
        if not added and not deleted and entry.get("lines"):
            # legacy: solo `lines` disponibile, non separabile in aggiunte/rimozioni
            added = int(entry["lines"])

        rows.append({
            "project": project,
            "author": author,
            "commits": int(entry.get("commits", 0) or 0),
            "added": added,
            "deleted": deleted,
            "files": int(entry.get("files", 0) or 0),
            "churn": churn_of(added, deleted),
            "active_days": int(active_days or 0),
            "index": index,
        })

    if legacy_aggregate:
        print("Avviso: JSON senza dettaglio giornaliero (formato precedente). "
              "L'indice composito è calcolato sull'aggregato di periodo e non è "
              "confrontabile con quello dei report nuovi.")

    if not rows:
        print("Nessun dato di attività trovato nel periodo: niente da rappresentare.")
        sys.exit(0)

    df = pd.DataFrame(rows)
    # Gli alias possono aver unito due identità nello stesso progetto: riaggreghiamo.
    df = (df.groupby(["project", "author"], as_index=False)
            .agg({"commits": "sum", "added": "sum", "deleted": "sum",
                  "files": "sum", "churn": "sum", "active_days": "max",
                  "index": "sum"}))
    return df, meta


def assign_colors(authors_by_size):
    colors = {}
    for i, author in enumerate(authors_by_size):
        colors[author] = SERIES[i] if i < MAX_SERIES else INK_MUTED
    colors[OTHER_LABEL] = INK_MUTED
    return colors


def fold_tail(df, authors_by_size):
    if len(authors_by_size) <= MAX_SERIES:
        return df, authors_by_size
    keep = set(authors_by_size[:MAX_SERIES])
    df = df.copy()
    df["author"] = df["author"].where(df["author"].isin(keep), OTHER_LABEL)
    df = (df.groupby(["project", "author"], as_index=False)
            .agg({"commits": "sum", "added": "sum", "deleted": "sum",
                  "files": "sum", "churn": "sum", "active_days": "max",
                  "index": "sum"}))
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


def integer_axis(ax, axis="y"):
    target = ax.yaxis if axis == "y" else ax.xaxis
    target.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True, nbins="auto"))
    target.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v):,}".replace(",", "."))
    )


def bar_width(n, plot_px=780, max_px=56):
    """Larghezza barra in unità dati, con un tetto in pixel.

    Con poche categorie una width fissa (0.7-0.8) produce blocchi enormi che riempiono
    tutta la banda: il resto della banda deve restare aria.
    """
    if n <= 0:
        return 0.7
    return min(0.7, max_px * n / plot_px)


def recessive_spines(ax, keep=("left", "bottom")):
    """Griglia e assi come hairline SOLIDE e recessive (mai tratteggiate)."""
    ax.set_axisbelow(True)
    for side in ("top", "right", "left", "bottom"):
        if side in keep:
            ax.spines[side].set_color(BASELINE)
            ax.spines[side].set_linewidth(0.8)
        else:
            ax.spines[side].set_visible(False)
    ax.tick_params(length=0, labelsize=9)


# -----------------------------------------------------------------------------
# Pannelli
# -----------------------------------------------------------------------------
def panel_metric_by_project(ax, df, colors, author_order, metric, title, ylabel):
    """Barre impilate per progetto×autore, generica sulla metrica (churn o commit):
    stesso trattamento visivo per entrambe, cambia solo la colonna aggregata."""
    pivot = (df.pivot_table(index="project", columns="author", values=metric,
                            aggfunc="sum").fillna(0))
    pivot = pivot.reindex(columns=[a for a in author_order if a in pivot.columns])
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]

    # Tetto al numero di barre: con decine di progetti le etichette sull'asse X si
    # sovrappongono. Stessa strategia già usata per la ciambella e per la tabella,
    # e la coda resta visibile aggregata invece di sparire.
    folded = 0
    if len(pivot.index) > MAX_PROJECT_BARS:
        folded = len(pivot.index) - MAX_PROJECT_BARS
        head = pivot.iloc[:MAX_PROJECT_BARS]
        tail = pivot.iloc[MAX_PROJECT_BARS:].sum()
        tail.name = f"{OTHER_LABEL} ({folded})"
        pivot = pd.concat([head, tail.to_frame().T])

    x = np.arange(len(pivot.index))
    bottom = np.zeros(len(pivot.index))
    width = bar_width(len(pivot.index))
    for author in pivot.columns:
        vals = pivot[author].to_numpy(dtype=float)
        ax.bar(x, vals, bottom=bottom, width=width, color=colors[author],
               label=author, edgecolor=SURFACE, linewidth=0.6)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=30, ha="right", fontsize=9)
    if folded:
        title += f"  (primi {MAX_PROJECT_BARS} di {len(pivot.index) - 1 + folded})"
    ax.set_title(title, fontsize=12, color=INK_PRIMARY, loc="left", pad=10)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, linestyle="-")
    recessive_spines(ax)
    integer_axis(ax)


def _share_bar(ax, totals, colors, title, xlabel):
    """Part-to-whole come singola barra orizzontale al 100% (alternativa alla
    ciambella quando i settori sarebbero troppo pochi perché una torta abbia senso)."""
    total = totals.sum()
    left = 0.0
    for (name, value), color in zip(totals.items(), colors):
        share = value / total * 100.0
        ax.barh([0], [share], left=[left], height=0.32, color=color,
                edgecolor=SURFACE, linewidth=1.2)
        if share >= 8:  # etichetta interna solo se ci sta con respiro
            ax.text(left + share / 2, 0, f"{name}\n{share:.0f}%",
                    ha="center", va="center", color="white", fontsize=9)
        left += share

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_title(title, fontsize=12, color=INK_PRIMARY, loc="left", pad=10)
    recessive_spines(ax, keep=("bottom",))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v)}%"))


def panel_donut(ax, df, metric, title, xlabel):
    """Distribuzione per progetto (quota del totale), generica sulla metrica
    (churn o commit): stesso trattamento visivo per entrambe."""
    totals = df.groupby("project")[metric].sum().sort_values(ascending=False)
    # Accorpiamo per RANGO, non per soglia percentuale: con una soglia, un portfolio
    # di 20 progetti equivalenti finiva interamente in "Altro" (torta al 100%).
    if len(totals) > DONUT_MAX_SLICES:
        head = totals.iloc[:DONUT_MAX_SLICES - 1]
        totals = pd.concat([head, pd.Series({OTHER_LABEL: totals.iloc[DONUT_MAX_SLICES - 1:].sum()})])

    if totals.sum() <= 0:
        metric_label = "commit" if metric == "commits" else "churn"
        ax.axis("off")
        ax.text(0.5, 0.5, f"Nessun {metric_label} nel periodo",
                ha="center", va="center", color=INK_MUTED, fontsize=10, transform=ax.transAxes)
        return

    # Sequenziale a una tinta (magnitudine), non categorico: qui i settori sono
    # ordinati per grandezza, quindi il blu più scuro = quota maggiore.
    ramp = ["#104281", "#1c5cab", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"]
    colors = [ramp[min(i, len(ramp) - 1)] for i in range(len(totals))]

    # Con meno di 3 progetti una ciambella è una torta a 2 fette: forma sbagliata.
    # Il part-to-whole si legge meglio come singola barra 100%.
    if len(totals) < 3:
        _share_bar(ax, totals, colors, title, xlabel)
        return

    total = totals.sum()
    # Percentuale scritta dentro la fetta solo se c'è spazio per leggerla: sotto questa
    # soglia il testo di più fette minuscole finisce per sovrapporsi (visto con progetti
    # di dimensione molto disomogenea: una fetta al 40% accanto a una allo 0,01%).
    # Non è clipping silenzioso — il valore resta comunque nella tabella di riepilogo.
    MIN_SHARE_FOR_LABEL = 4.0

    def autopct(pct):
        return f"{pct:.0f}%" if pct >= MIN_SHARE_FOR_LABEL else ""

    wedges, _texts, autotexts = ax.pie(
        totals.to_numpy(), labels=None, autopct=autopct, startangle=90,
        counterclock=False, colors=colors,
        wedgeprops=dict(width=0.42, edgecolor=SURFACE, linewidth=1.2),
        pctdistance=0.78,
        textprops=dict(fontsize=9, color=INK_SECONDARY),
    )
    for t in autotexts:
        # Il testo dentro un riempimento colorato è l'unico caso in cui può portare
        # il colore: scegliamo bianco per restare leggibile sui blu scuri.
        t.set_color("white")
        t.set_fontsize(9)

    # I nomi vanno in legenda, non accanto alla fetta: con fette di dimensione molto
    # disomogenea l'etichettatura diretta di matplotlib le sovrapponeva. Percentuale
    # sempre in legenda, anche per le fette troppo piccole per portarla scritta sopra.
    legend_labels = [f"{name}  ({v/total*100:.1f}%)" for name, v in totals.items()]
    ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1.02, 0.5),
              fontsize=9, labelcolor=INK_SECONDARY, frameon=False)

    ax.set_title(title, fontsize=12, color=INK_PRIMARY, loc="left", pad=10)
    ax.axis("equal")


def panel_active_days(ax, df, colors):
    data = (df.groupby("author")["active_days"].sum()
              .sort_values(ascending=True))
    y = np.arange(len(data))
    ax.barh(y, data.to_numpy(), height=0.6,
            color=[colors.get(a, INK_MUTED) for a in data.index],
            edgecolor=SURFACE, linewidth=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(data.index, fontsize=9, color=INK_SECONDARY)
    ax.set_title("Giorni attivi per autore (somma sui progetti)", fontsize=12,
                 color=INK_PRIMARY, loc="left", pad=10)
    ax.set_xlabel("Giorni con almeno 1 commit", fontsize=9)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, linestyle="-")
    recessive_spines(ax, keep=("bottom",))
    integer_axis(ax, axis="x")
    for yi, v in zip(y, data.to_numpy()):
        ax.text(v, yi, f" {int(v)}", va="center", ha="left",
                fontsize=9, color=INK_SECONDARY)


def panel_table(ax, df):
    """Tabella riepilogo per progetto.

    È anche il "relief" richiesto dalle tinte a basso contrasto della palette:
    nessun valore è raggiungibile solo tramite il colore.
    """
    ax.axis("off")
    ax.set_title("Riepilogo per progetto", fontsize=12, color=INK_PRIMARY,
                 loc="left", pad=10)

    summary = (df.groupby("project")
                 .agg(churn=("churn", "sum"), commit=("commits", "sum"),
                      file=("files", "sum"), giorni=("active_days", "sum"),
                      autori=("author", "nunique"), indice=("index", "sum"))
                 .sort_values("churn", ascending=False))

    shown = summary.head(MAX_TABLE_ROWS)
    cells = []
    for project, r in shown.iterrows():
        name = project if len(str(project)) <= 20 else str(project)[:19] + "…"
        cells.append([
            name,
            f"{int(r['churn']):,}".replace(",", "."),
            f"{int(r['commit']):,}".replace(",", "."),
            f"{int(r['giorni'])}",
            f"{int(r['file']):,}".replace(",", "."),
            f"{int(r['autori'])}",
            f"{r['indice']:.1f}",
        ])

    table = ax.table(
        cellText=cells,
        colLabels=["Progetto", "Churn", "Commit", "Giorni att.", "File", "Autori", "Indice"],
        colWidths=[0.26, 0.14, 0.12, 0.14, 0.12, 0.10, 0.12],
        cellLoc="right", loc="upper center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.45)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(GRIDLINE)
        cell.set_linewidth(0.6)
        cell.set_facecolor(SURFACE)
        if col == 0:
            cell.set_text_props(ha="left")
        if row == 0:
            cell.set_text_props(color=INK_SECONDARY, weight="semibold")
        else:
            cell.set_text_props(color=INK_PRIMARY)

    note = ("Churn = aggiunte + 0.4 × rimozioni · Indice = metrica secondaria, "
            "additiva, con tetto giornaliero")
    if len(summary) > len(shown):
        note = f"Mostrati i primi {len(shown)} di {len(summary)} progetti. " + note
    ax.text(0, -0.04, note, transform=ax.transAxes, fontsize=8,
            color=INK_MUTED, va="top")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    payload = read_payload()
    aliases = load_aliases()
    if aliases and isinstance(payload, list):
        print(f"Caricati {len(aliases)} alias autore (JSON in formato legacy).")
    df, meta = flatten(payload, aliases)

    start = meta.get("start_date", "N/A")
    end = meta.get("end_date", "N/A")

    by_size = (df.groupby("author")["churn"].sum()
                 .sort_values(ascending=False).index.tolist())
    df, author_order = fold_tail(df, by_size)
    colors = assign_colors(author_order)

    apply_style()
    # 4 righe: giorni attivi da solo (il più affidabile, in cima), poi UNA RIGA PER
    # METRICA — commit (riga 2), churn (riga 3) — con dentro barre impilate e ciambella
    # della stessa metrica affiancate. Due ragioni, entrambe misurate:
    #
    #   1. Barre e ciambella della stessa metrica raccontano la stessa cosa a due livelli
    #      di dettaglio (dove si concentra, e la quota sul totale): appaiarle è la lettura
    #      naturale. Churn interamente sulla riga sotto lo rende anche meno prominente del
    #      commit, coerente con l'ordine di attendibilità (vedi METRICHE sopra).
    #   2. Il layout precedente affiancava commit e churn sulla stessa riga per il
    #      "confronto diretto" fra le due metriche. NON funziona, ed era peggio che
    #      inutile: ogni pannello ordina i progetti per il PROPRIO totale
    #      (`sort_values` in panel_metric_by_project/panel_donut), quindi la posizione
    #      sull'asse x non corrisponde fra i due. Misurato su dati sintetici realistici:
    #      commit -> [app-frontend, core-lib, docs, api-generated] mentre
    #      churn  -> [api-generated, core-lib, app-frontend, docs]. Confrontare "prima
    #      barra a sinistra vs prima barra a destra" confrontava due progetti DIVERSI (e
    #      lo stesso vale per il fold in "Altro" delle ciambelle, calcolato per metrica).
    #      Con scale y incommensurabili (es. 560 commit vs 420.000 righe) non restava
    #      nemmeno un confronto di forma valido.
    #
    # Un confronto commit-vs-churn onesto richiederebbe un pannello dedicato (es. churn
    # per commit per progetto), non due pannelli affiancati: non è stato aggiunto qui.
    #
    # L'altezza della riga della tabella si ADATTA al numero di progetti effettivamente
    # mostrati, invece di essere fissata sul caso peggiore (12 righe): le celle sono
    # dimensionate dal font e non dall'asse (vedi TABLE_ROW_INCHES), quindi un ratio fisso
    # lasciava una banda vuota di ~3.5" con pochi progetti e rischiava lo sforo con 12.
    # Anche la figura si accorcia di conseguenza, così le prime tre righe conservano la
    # stessa dimensione assoluta (ROW_UNIT_INCHES costante) e il PNG non porta con sé
    # spazio bianco inutile.
    n_table_rows = min(df["project"].nunique(), MAX_TABLE_ROWS)
    table_ratio = max(
        TABLE_RATIO_MIN,
        (TABLE_ROW_INCHES * (n_table_rows + 1) + TABLE_PAD_INCHES) / ROW_UNIT_INCHES,
    )
    ratios = [0.75, 1.0, 1.0, table_ratio]
    # Altezza figura che rende ROW_UNIT_INCHES l'altezza di un'unità di ratio: le righe
    # occupano sum(ratios) unità, più un gap fra righe pari a hspace × altezza media,
    # più header e footer (assoluti, vedi le costanti in testa).
    gaps = (len(ratios) - 1) * FIG_HSPACE / len(ratios)
    rows_height = sum(ratios) * ROW_UNIT_INCHES * (1 + gaps)
    fig_height = rows_height + HEADER_INCHES + FOOTER_INCHES
    fig_top = 1 - HEADER_INCHES / fig_height
    fig_bottom = FOOTER_INCHES / fig_height

    fig = plt.figure(figsize=(FIG_WIDTH_INCHES, fig_height))
    gs = fig.add_gridspec(4, 2, height_ratios=ratios,
                           hspace=FIG_HSPACE, wspace=0.28)
    fig.suptitle(f"Attività di sviluppo multi-progetto  ({start} → {end})",
                 fontsize=16, color=INK_PRIMARY, x=0.02, ha="left",
                 y=1 - SUPTITLE_INCHES / fig_height)

    ax1 = fig.add_subplot(gs[0, :])
    panel_active_days(ax1, df, colors)

    ax2 = fig.add_subplot(gs[1, 0])
    panel_metric_by_project(ax2, df, colors, author_order, "commits",
                             "Commit per progetto e autore", "Commit")

    ax3 = fig.add_subplot(gs[1, 1])
    panel_donut(ax3, df, "commits", "Distribuzione dei commit per progetto",
                "Quota dei commit totali (%)")

    ax4 = fig.add_subplot(gs[2, 0])
    panel_metric_by_project(ax4, df, colors, author_order, "churn",
                             "Churn per progetto e autore",
                             "Righe (aggiunte + 0.4 × rimosse)")

    ax5 = fig.add_subplot(gs[2, 1])
    panel_donut(ax5, df, "churn", "Distribuzione del churn per progetto",
                "Quota del churn totale (%)")

    ax6 = fig.add_subplot(gs[3, :])
    panel_table(ax6, df)

    # Le handle si prendono da ax2 (commit per progetto): il primo pannello che disegna
    # le barre impilate con label=autore, fonte della legenda unica di figura.
    handles, labs = ax2.get_legend_handles_labels()
    if len(labs) >= 2:
        fig.legend(handles, labs, loc="lower center", ncol=min(len(labs), 6),
                   fontsize=9, labelcolor=INK_SECONDARY, frameon=False,
                   bbox_to_anchor=(0.5, LEGEND_INCHES / fig_height))

    # tight_layout non gestisce bene le legende dentro le ciambelle (bbox_to_anchor
    # fuori asse) su un gridspec a 4 righe disomogenee: margini espliciti invece di
    # tight_layout. Right/top/bottom fissi (già verificati sul contenuto di questo
    # report), ma il margine sinistro è misurato dal testo EFFETTIVAMENTE renderizzato
    # (bbox reale via get_window_extent(), non una stima) — un valore fisso tronca le
    # etichette y più lunghe del previsto (misurato: "Gabriele Stringano" e altri nomi
    # tagliati con un left fisso; stesso bug già corretto in plot_git.py).
    fig.subplots_adjust(left=0.055, right=0.86, top=fig_top, bottom=fig_bottom,
                         hspace=FIG_HSPACE, wspace=0.28)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    current_left = fig.subplotpars.left
    min_x0 = 1.0
    for ax in fig.axes:
        for label in ax.get_yticklabels():
            if not label.get_text():
                continue
            bbox = label.get_window_extent(renderer).transformed(fig.transFigure.inverted())
            min_x0 = min(min_x0, bbox.x0)
    label_span = current_left - min_x0
    left_margin = max(0.035, label_span + 0.015)
    fig.subplots_adjust(left=left_margin)

    safe_start = str(start).replace(" ", "_").replace("/", "-")
    safe_end = str(end).replace(" ", "_").replace("/", "-")
    output_filename = f"git_activity_multi_project_report_{safe_start}_{safe_end}.png"
    fig.savefig(output_filename, dpi=200)
    # La forma "Report multi-progetto ... generato con successo: <file>" va mantenuta:
    # l'estensione VS Code la intercetta via regex (il testo fra i due estremi è libero).
    print(f"\nReport multi-progetto (indice di attività) generato con successo: {output_filename}")


if __name__ == "__main__":
    main()
