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
                 Primo pannello, a piena larghezza, come MATRICE DI PRESENZA (autori in
                 ordine alfabetico × periodi, cella = giorni attivi su tutti i progetti):
                 CHI ha lavorato QUANDO, senza ordinare né sommare per persona.
                 Secondo pannello, anch'esso a piena larghezza: matrice PROGETTI × periodi (cella =
                 giorni con attività nel progetto, su tutti gli autori): DOVE va il lavoro nel
                 tempo, a livello di progetto (righe per attività decrescente: sono progetti,
                 non persone). Saltati entrambi se il JSON non ha date né dettaglio giornaliero.
  commit         Numero di commit (esclusi i merge). RIGA 3, interamente sua: barre
                 impilate per progetto e autore, più la ciambella di distribuzione per
                 progetto affiancata (la stessa cosa a due livelli di dettaglio).
  churn          = aggiunte + 0.4 * rimozioni
                   Le rimozioni contano: cancellare codice morto è lavoro reale.
                   È la meno indicativa delle tre: git_multiproject_stats_collector.sh
                   NON esclude codice generato, vendorizzato o lock file (vedi il
                   commento in testa a quello script per il perché — in breve, qualunque
                   esclusione basata su directory può rompere il rilevamento dei rename
                   di git, misurato fino a 9.7x di inflazione su una singola giornata).
                   RIGA 4, stesso trattamento del commit (barre impilate + ciambella
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

Nota storica: fino alla v3 il report aveva anche un INDICE composito (somma sui giorni di
ln(1 + churn_giorno con tetto) e ln(1 + file distinti)), relegato alla tabella. È stato
rimosso: era la parte più simile a un punteggio e invitava a leggere la tabella come una
classifica. Due lezioni misurate restano utili anche senza di lui: una forma moltiplicativa
azzerava le giornate di sole cancellazioni, e un tetto applicato all'aggregato di periodo
(invece che per giorno) si saturava; il valore stesso del tetto (1000, poi 15000) dipendeva
dal modello di sviluppo — vedi CLAUDE.md.

NESSUNA VALUTAZIONE DELLE PERSONE: il report non ha punteggi né totali per persona; gli
autori compaiono in ordine alfabetico e come presenza. Per vedere il lavoro di UNA persona si
filtra per autore al collector. La tabella è per progetto, non per autore.

ATTENZIONE: sono indicatori di attività, non misure di produttività o di qualità.
Code review, design, mentoring e debugging difficile sono strutturalmente invisibili.
"""

import json
import os
import sys
import textwrap
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors
import matplotlib.ticker
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Parametri delle metriche (mantenere allineati con plot_git.py)
# -----------------------------------------------------------------------------
DELETED_WEIGHT = 0.4      # quanto pesa una riga rimossa rispetto a una aggiunta

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
OTHER_LABEL = "Altro"     # reimpostata da set_lang() nella lingua scelta
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
MAX_PROJECT_ROWS = 20        # righe massime della matrice progetti × tempo (oltre: nota)
MAX_MATRIX_ROWS = 30         # righe massime di una matrice di presenza (oltre: nota, mai taglio muto)
MATRIX_CELL_INCHES = 0.30    # altezza di una riga di cella: abbastanza per una cifra da 8 pt
MATRIX_MIN_AXES_INCHES = 0.60
MATRIX_RAMP = ["#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # = PUNCH_RAMP[1:]
EMPTY_CELL = "#efeee8"       # cella senza giorni attivi: quasi invisibile, non una tinta di dato
FIG_WIDTH_INCHES = 17
FIG_HSPACE = 0.5
# Header e footer in POLLICI, non in frazione di figura: da quando l'altezza totale varia
# col numero di progetti, una frazione fissa restringeva lo spazio assoluto sopra e sotto
# (misurato: con 3 progetti il suptitle finiva sopra il titolo del primo pannello). Con
# valori assoluti il margine resta identico a qualunque altezza di figura.
HEADER_INCHES = 0.95      # spazio sopra la prima riga: suptitle + titolo del pannello
SUPTITLE_INCHES = 0.42    # distanza del suptitle dal bordo superiore
# Spazio sotto l'ultima riga: nota della tabella + legenda. La legenda va a capo su più
# righe quando gli autori (fino a 8 + "Altro") superano ncol=6: con un FOOTER fisso
# tarato su una riga sola, la seconda riga finisce sopra il pannello successivo — stesso
# bug misurato e corretto in plot_git.py, stessa costante di altezza per riga (dipende
# solo da fontsize=9, non dal numero di colonne della tabella o dalle metriche mostrate).
LEGEND_ROW1_INCHES = 0.230
LEGEND_EXTRA_ROW_INCHES = 0.1925
LEGEND_BOTTOM_PAD_INCHES = 0.08   # distanza tra il bordo inferiore della figura e la legenda
NOTE_INCHES = 0.30                # spazio per la nota sotto la tabella, sopra la legenda
# Riquadro «cosa non misura» (fra la legenda e il resto): testo da 8 pt a capo automatico.
LIMITS_WRAP_CHARS = 190           # caratteri per riga (la figura è larga 17": ne servono ~13)
LIMITS_LINE_INCHES = 0.155        # una riga a 8 pt con linespacing 1.3
LIMITS_GAP_INCHES = 0.06          # fra la cima della legenda e il riquadro

# -----------------------------------------------------------------------------
# Lingua delle scritte nel grafico (solo il PNG: i messaggi su stdout restano invariati,
# perché l'estensione VS Code li intercetta via regex). Stessa logica di selezione di
# plot_git.py (detect_lang/set_lang duplicate identiche): aggiornarle entrambe.
# -----------------------------------------------------------------------------
STRINGS = {
    "it": {
        "other": "Altro",
        "suptitle": "Attività di sviluppo multi-progetto  ({start} → {end})",
        "buckets": {"D": "giorno", "W-MON": "settimana", "MS": "mese"},
        "presence_title": "Presenza per autore, tutti i progetti (giorni attivi per {bucket})",
        "presence_caption": "Più scuro = più giorni attivi",
        "presence_hidden": "mostrati {shown} autori su {total} (i più attivi)",
        "projects_title": "Attività per progetto nel tempo (giorni attivi per {bucket})",
        "projects_hidden": "mostrati {shown} progetti su {total} (i più attivi)",
        "commits_title": "Commit per progetto e autore",
        "commits_ylabel": "Commit",
        "commits_donut": "Distribuzione dei commit per progetto",
        "commits_share": "Quota dei commit totali (%)",
        "churn_title": "Churn per progetto e autore",
        "churn_ylabel": "Righe (aggiunte + 0.4 × rimosse)",
        "churn_donut": "Distribuzione del churn per progetto",
        "churn_share": "Quota del churn totale (%)",
        "top_n": "  (primi {n} di {total})",
        "no_metric": {"commits": "Nessun commit nel periodo", "churn": "Nessun churn nel periodo"},
        "table_title": "Riepilogo per progetto",
        "table_cols": ["Progetto", "Churn", "Commit", "Giorni att.", "File", "Autori"],
        "table_note": "Churn = aggiunte + 0.4 × rimozioni",
        "table_shown": "Mostrati i primi {shown} di {total} progetti. ",
        "limits_note": "Questi grafici contano commit e righe modificate: misurano la quantità, non la qualità né la difficoltà del lavoro. Il lavoro che non passa da commit git (per esempio attivare servizi a un cliente o migrare database), le assenze e le ferie qui non si vedono.",
        "thousands_sep": ".",
    },
    "en": {
        "other": "Other",
        "suptitle": "Multi-project development activity  ({start} → {end})",
        "buckets": {"D": "day", "W-MON": "week", "MS": "month"},
        "presence_title": "Presence by author, all projects (active days per {bucket})",
        "presence_caption": "Darker = more active days",
        "presence_hidden": "showing {shown} of {total} authors (most active)",
        "projects_title": "Activity by project over time (active days per {bucket})",
        "projects_hidden": "showing {shown} of {total} projects (most active)",
        "commits_title": "Commits by project and author",
        "commits_ylabel": "Commits",
        "commits_donut": "Commit distribution by project",
        "commits_share": "Share of total commits (%)",
        "churn_title": "Churn by project and author",
        "churn_ylabel": "Lines (added + 0.4 × deleted)",
        "churn_donut": "Churn distribution by project",
        "churn_share": "Share of total churn (%)",
        "top_n": "  (top {n} of {total})",
        "no_metric": {"commits": "No commits in the period", "churn": "No churn in the period"},
        "table_title": "Summary by project",
        "table_cols": ["Project", "Churn", "Commits", "Active days", "Files", "Authors"],
        "table_note": "Churn = added + 0.4 × deleted",
        "table_shown": "Showing the top {shown} of {total} projects. ",
        "limits_note": "These charts count commits and changed lines: they measure quantity, not the quality or difficulty of the work. Work that doesn't go through git commits (for example activating services for a customer or migrating databases), absences and holidays are not visible here.",
        "thousands_sep": ",",
    },
}
T = STRINGS["it"]


def detect_lang(argv, environ):
    """Lingua delle scritte del grafico, in ordine: --lang it|en, GIT_ACTIVITY_LANG,
    locale di sistema (LC_ALL > LC_MESSAGES > LANG: "it_*" -> it), altrimenti inglese."""
    for i, arg in enumerate(argv):
        if arg.startswith("--lang="):
            value = arg.split("=", 1)[1]
        elif arg == "--lang" and i + 1 < len(argv):
            value = argv[i + 1]
        else:
            continue
        return "it" if value.lower().startswith("it") else "en"
    value = environ.get("GIT_ACTIVITY_LANG", "")
    if value:
        return "it" if value.lower().startswith("it") else "en"
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = environ.get(var, "")
        if value:
            return "it" if value.lower().startswith("it") else "en"
    return "en"


def set_lang(lang):
    global T, OTHER_LABEL
    T = STRINGS[lang]
    OTHER_LABEL = T["other"]


def fmt_int(v):
    """Intero con separatore delle migliaia della lingua scelta (5.351 / 5,351)."""
    return f"{int(v):,}".replace(",", T["thousands_sep"])


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
    day_rows = []
    for entry in entries:
        author = entry.get("author_name") or entry.get("author") or "Sconosciuto"
        if aliases_needed:
            author = aliases.get(author, author)
        project = entry.get("project", "?")
        days = entry.get("daily_data") or []
        for d in days:
            # Giorni con attività: alimentano le matrici di presenza (autori e progetti nel tempo).
            if d.get("date") and int(d.get("commits", 0) or 0) > 0:
                day_rows.append({"project": project, "author": author,
                                 "date": pd.to_datetime(d["date"])})

        if days:
            active_days = entry.get("active_days")
            if active_days is None:
                active_days = sum(1 for d in days if int(d.get("commits", 0) or 0) > 0)
        else:
            # Formato legacy senza dettaglio giornaliero: restano i soli totali per entry.
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
        })

    if not rows:
        print("Nessun dato di attività trovato nel periodo: niente da rappresentare.")
        sys.exit(0)

    df = pd.DataFrame(rows)
    # Gli alias possono aver unito due identità nello stesso progetto: riaggreghiamo.
    df = (df.groupby(["project", "author"], as_index=False)
            .agg({"commits": "sum", "added": "sum", "deleted": "sum",
                  "files": "sum", "churn": "sum", "active_days": "max"}))
    days_df = pd.DataFrame(day_rows, columns=["project", "author", "date"])
    return df, meta, days_df


def choose_bucket(start, end):
    """Granularità adattiva (stessa regola di plot_git.py): una colonna al giorno diventa
    illeggibile su periodi lunghi."""
    span = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if span <= 45:
        freq = "D"
    elif span <= 250:
        freq = "W-MON"
    else:
        freq = "MS"
    return freq, T["buckets"][freq]


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
                  "files": "sum", "churn": "sum", "active_days": "max"}))
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
        matplotlib.ticker.FuncFormatter(lambda v, _: fmt_int(v))
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
def alpha_order(names):
    """Ordine di VISUALIZZAZIONE degli autori: alfabetico (case-insensitive), "Altro" per
    ultimo. Mai per volume: un elenco ordinato per commit o churn è una classifica."""
    named = sorted((n for n in names if n != OTHER_LABEL), key=lambda n: n.casefold())
    return named + ([OTHER_LABEL] if OTHER_LABEL in names else [])


def bucketed_days(frame, key_col, keys, full_index, freq):
    """Giorni DISTINTI attivi per bucket e per chiave (autore o progetto).

    `frame` ha una riga per (data, chiave) con attività. I bucket sono gli stessi dei
    grafici nel tempo (stesso `full_index` giornaliero e stessa `freq` di resample), così
    le colonne della matrice stanno sotto le stesse etichette."""
    flag = frame.assign(_v=1).pivot_table(index="date", columns=key_col, values="_v",
                                          aggfunc="max")
    flag = flag.reindex(full_index).fillna(0).reindex(columns=keys, fill_value=0)
    return flag.resample(freq).sum()


def panel_matrix(ax, matrix, row_labels, col_labels, title, caption, show_numbers):
    """Matrice righe × bucket temporali: giorni attivi per cella, rampa sequenziale a una
    tinta (più scuro = più giorni). Le celle vuote sono quasi invisibili, così «presente»
    risalta. Con bucket settimanali o mensili il numero sta dentro la cella (nessun valore
    raggiungibile solo col colore); con bucket giornalieri la cella vale 0/1 e non serve."""
    data = np.asarray(matrix, dtype=float)
    vmax = max(float(data.max()) if data.size else 0.0, 3.0)   # 1 giorno = tinta media, non la più scura
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("matrix_blue", MATRIX_RAMP)
    cmap.set_bad(EMPTY_CELL)
    ax.imshow(np.ma.masked_where(data <= 0, data), aspect="auto", cmap=cmap,
              vmin=0, vmax=vmax, interpolation="nearest")
    n_rows, n_cols = data.shape
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(row_labels, fontsize=9, color=INK_SECONDARY)
    step = max(1, int(np.ceil(n_cols / 18)))
    positions = list(range(0, n_cols, step))
    ax.set_xticks(positions)
    ax.set_xticklabels([col_labels[i] for i in positions], rotation=45, ha="right",
                       fontsize=9, color=INK_MUTED)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    # Gap fra le celle nel colore della superficie (stesso trattamento della punch card).
    ax.set_xticks(np.arange(-0.5, n_cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n_rows, 1), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=1.5)
    ax.tick_params(which="minor", length=0)
    if show_numbers:
        for i in range(n_rows):
            for j in range(n_cols):
                v = data[i, j]
                if v > 0:
                    ax.text(j, i, f"{int(v)}", ha="center", va="center", fontsize=8,
                            color="white" if v / vmax > 0.45 else INK_PRIMARY)
    ax.set_title(title, fontsize=12, color=INK_PRIMARY, loc="left", pad=10)
    if caption:
        # Sulla riga del titolo, a destra: sotto l'asse c'è già lo spazio delle etichette x
        # ruotate e una didascalia lì finiva sul titolo del pannello successivo (misurato).
        ax.set_title(caption, fontsize=8, color=INK_MUTED, loc="right", pad=10)


def matrix_inputs(frame, key_col, full_index, freq, max_rows, order_keys=None):
    """Prepara una matrice di presenza per `key_col` ('author' o 'project').

    Ritorna (matrice righe×bucket, etichette righe, nascoste, DataFrame bucket×chiavi).
    Se le chiavi superano `max_rows` si tengono le più attive (solo per il TAGLIO) e si
    segnala quante sono nascoste; l'ordine mostrato è `order_keys(keys)` (alfabetico per gli
    autori, per attività decrescente per i progetti)."""
    active = frame[["date", key_col]].drop_duplicates()
    ranked = active.groupby(key_col)["date"].nunique().sort_values(ascending=False)
    kept = list(ranked.index[:max_rows])
    keys = order_keys(kept) if order_keys else kept
    hidden = len(ranked) - len(kept)
    buckets = bucketed_days(active[active[key_col].isin(kept)], key_col, keys, full_index, freq)
    return buckets.T.to_numpy(), keys, hidden, buckets


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
    # Respiro sopra la barra più alta: senza, il vertice tocca il bordo superiore dell'asse.
    if len(pivot.index) and float(bottom.max()) > 0:
        ax.set_ylim(0, float(bottom.max()) * 1.08)

    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=30, ha="right", fontsize=9)
    if folded:
        title += T["top_n"].format(n=MAX_PROJECT_BARS, total=len(pivot.index) - 1 + folded)
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
        ax.axis("off")
        ax.text(0.5, 0.5, T["no_metric"]["commits" if metric == "commits" else "churn"],
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


def panel_table(ax, df):
    """Tabella riepilogo per progetto.

    È anche il "relief" richiesto dalle tinte a basso contrasto della palette:
    nessun valore è raggiungibile solo tramite il colore.
    """
    ax.axis("off")
    ax.set_title(T["table_title"], fontsize=12, color=INK_PRIMARY,
                 loc="left", pad=10)

    summary = (df.groupby("project")
                 .agg(churn=("churn", "sum"), commit=("commits", "sum"),
                      file=("files", "sum"), giorni=("active_days", "sum"),
                      autori=("author", "nunique"))
                 .sort_values("churn", ascending=False))

    shown = summary.head(MAX_TABLE_ROWS)
    cells = []
    for project, r in shown.iterrows():
        name = project if len(str(project)) <= 20 else str(project)[:19] + "…"
        cells.append([
            name,
            fmt_int(r['churn']),
            fmt_int(r['commit']),
            f"{int(r['giorni'])}",
            fmt_int(r['file']),
            f"{int(r['autori'])}",
        ])

    table = ax.table(
        cellText=cells,
        colLabels=T["table_cols"],
        colWidths=[0.30, 0.16, 0.14, 0.16, 0.14, 0.10],
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

    note = T["table_note"]
    if len(summary) > len(shown):
        note = T["table_shown"].format(shown=len(shown), total=len(summary)) + note
    ax.text(0, -0.04, note, transform=ax.transAxes, fontsize=8,
            color=INK_MUTED, va="top")


FOOTER_GAP_INCHES = 0.12   # aria minima fra il fondo dell'ultimo pannello e la legenda


def fit_footer(fig, last_ax, anchored, footer_inches, suptitle):
    """Allunga la figura se il fondo dell'ultimo pannello (etichetta dell'asse e
    didascalie comprese) scende sotto la cima del footer.

    `anchored` = elementi del footer (legenda, riquadro dei limiti) con la loro distanza in
    POLLICI dal bordo inferiore: `[(artista, pollici), ...]` (i None si ignorano).

    Il footer è dimensionato per la nota della tabella (NOTE_INCHES), ma quando l'ultima
    riga è la punch card o l'ownership sotto l'asse ci sono anche un'etichetta x e una
    didascalia: misurato, con l'ownership in fondo "Righe (git blame)" finiva sotto la
    legenda. Invece di un'altra costante per ogni combinazione di pannelli, si misura il
    contenuto EFFETTIVAMENTE disegnato (bbox reali dopo draw()) e si aggiunge solo lo spazio
    mancante. Header, righe e footer restano alla stessa distanza in POLLICI dai bordi
    (stessa logica delle costanti in testa): cresce solo lo spazio fra l'ultimo pannello e
    il footer, e ogni elemento del footer viene ri-ancorato alla nuova altezza.
    """
    anchored = [(a, y) for a, y in anchored if a is not None]
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    content_bottom = last_ax.get_tightbbox(renderer).y0           # pixel dal basso
    footer_top = max((a.get_window_extent(renderer).y1 for a, _ in anchored), default=0.0)
    overlap_px = footer_top + FOOTER_GAP_INCHES * fig.dpi - content_bottom
    if overlap_px <= 0:
        return
    extra = overlap_px / fig.dpi
    width, height = fig.get_size_inches()
    new_height = height + extra
    fig.set_size_inches(width, new_height)
    fig.subplots_adjust(top=1 - HEADER_INCHES / new_height,
                        bottom=(footer_inches + extra) / new_height)
    suptitle.set_y(1 - SUPTITLE_INCHES / new_height)
    for artist, inches in anchored:
        if hasattr(artist, "set_bbox_to_anchor"):        # legenda
            artist.set_bbox_to_anchor((0.5, inches / new_height), transform=fig.transFigure)
        else:                                            # testo
            artist.set_y(inches / new_height)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    set_lang(detect_lang(sys.argv[1:], os.environ))
    payload = read_payload()
    aliases = load_aliases()
    if aliases and isinstance(payload, list):
        print(f"Caricati {len(aliases)} alias autore (JSON in formato legacy).")
    df, meta, days_df = flatten(payload, aliases)

    start = meta.get("start_date", "N/A")
    end = meta.get("end_date", "N/A")

    by_size = (df.groupby("author")["churn"].sum()
                 .sort_values(ascending=False).index.tolist())
    df, author_order = fold_tail(df, by_size)
    colors = assign_colors(author_order)   # per RANGO (serve al fold), mai per ordine mostrato
    display_authors = alpha_order(author_order)

    # Matrice di presenza per autore (tutti i progetti insieme), stessi bucket temporali
    # del report singolo. Serve metadata con le date e almeno un giorno con attività:
    # con JSON legacy il pannello viene saltato (non lasciato vuoto).
    has_matrix = (not days_df.empty and start not in ("N/A", "") and end not in ("N/A", ""))
    pres_matrix = pres_authors = pres_caption = col_labels = None
    proj_matrix = proj_names = proj_caption = None
    bucket_name = ""
    freq = "D"
    if has_matrix:
        freq, bucket_name = choose_bucket(start, end)
        full = pd.date_range(start=start, end=end, freq="D")
        pres_matrix, pres_authors, pres_hidden, buckets = matrix_inputs(
            days_df, "author", full, freq, MAX_MATRIX_ROWS, order_keys=alpha_order)
        label_fmt = "%Y-%m" if freq == "MS" else "%Y-%m-%d"
        col_labels = [d.strftime(label_fmt) for d in buckets.index]
        pres_caption = T["presence_caption"]
        if pres_hidden:
            pres_caption += " · " + T["presence_hidden"].format(
                shown=len(pres_authors), total=len(pres_authors) + pres_hidden)
        # Asse del tempo a livello di PROGETTO (non di persona): giorni distinti con attività
        # nel progetto, su tutti gli autori. Righe per attività totale decrescente: sono
        # progetti, quindi l'ordinamento è lecito (e fa leggere subito dove va il lavoro).
        proj_matrix, proj_names, proj_hidden, _ = matrix_inputs(
            days_df, "project", full, freq, MAX_PROJECT_ROWS)
        proj_caption = T["presence_caption"]
        if proj_hidden:
            proj_caption += " · " + T["projects_hidden"].format(
                shown=len(proj_names), total=len(proj_names) + proj_hidden)

    apply_style()
    # 5 righe: due matrici nel tempo in cima (presenza per autore, attività per progetto;
    # assenti con JSON legacy), poi UNA RIGA PER METRICA — commit, churn — con dentro barre
    # impilate e ciambella
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
    ratios = [1.0, 1.0, table_ratio]
    if has_matrix:
        matrix_ratio = max(MATRIX_MIN_AXES_INCHES,
                           MATRIX_CELL_INCHES * len(pres_authors)) / ROW_UNIT_INCHES
        proj_ratio = max(MATRIX_MIN_AXES_INCHES,
                         MATRIX_CELL_INCHES * len(proj_names)) / ROW_UNIT_INCHES
        ratios = [matrix_ratio, proj_ratio] + ratios
    # Altezza figura che rende ROW_UNIT_INCHES l'altezza di un'unità di ratio: le righe
    # occupano sum(ratios) unità, più un gap fra righe pari a hspace × altezza media,
    # più header e footer (assoluti, vedi le costanti in testa).
    gaps = (len(ratios) - 1) * FIG_HSPACE / len(ratios)
    rows_height = sum(ratios) * ROW_UNIT_INCHES * (1 + gaps)

    # Righe della legenda: stesso criterio con cui sarà disegnata più sotto (autori,
    # ncol=min(n, 6)) — va saputo PRIMA di creare la figura, perché il footer deve
    # riservare spazio per tutte le righe, non solo la prima.
    n_legend_labels = len(author_order)
    legend_ncol = min(n_legend_labels, 6) or 1
    legend_rows = -(-n_legend_labels // legend_ncol)  # ceiling division
    legend_height = LEGEND_ROW1_INCHES + max(0, legend_rows - 1) * LEGEND_EXTRA_ROW_INCHES
    limits_text = textwrap.fill(T["limits_note"], width=LIMITS_WRAP_CHARS)
    limits_height = LIMITS_GAP_INCHES + LIMITS_LINE_INCHES * (limits_text.count("\n") + 1)
    footer_inches = LEGEND_BOTTOM_PAD_INCHES + legend_height + limits_height + NOTE_INCHES

    fig_height = rows_height + HEADER_INCHES + footer_inches
    fig_top = 1 - HEADER_INCHES / fig_height
    fig_bottom = footer_inches / fig_height

    fig = plt.figure(figsize=(FIG_WIDTH_INCHES, fig_height))
    gs = fig.add_gridspec(len(ratios), 2, height_ratios=ratios,
                           hspace=FIG_HSPACE, wspace=0.28)
    suptitle = fig.suptitle(T["suptitle"].format(start=start, end=end),
                 fontsize=16, color=INK_PRIMARY, x=0.02, ha="left",
                 y=1 - SUPTITLE_INCHES / fig_height)

    row = 0
    if has_matrix:
        ax1 = fig.add_subplot(gs[row, :])
        panel_matrix(ax1, pres_matrix, pres_authors, col_labels,
                     T["presence_title"].format(bucket=bucket_name), pres_caption,
                     show_numbers=(freq != "D"))
        row += 1
        ax1b = fig.add_subplot(gs[row, :])
        panel_matrix(ax1b, proj_matrix, proj_names, col_labels,
                     T["projects_title"].format(bucket=bucket_name), proj_caption,
                     show_numbers=(freq != "D"))
        row += 1

    ax2 = fig.add_subplot(gs[row, 0])
    panel_metric_by_project(ax2, df, colors, display_authors, "commits",
                             T["commits_title"], T["commits_ylabel"])

    ax3 = fig.add_subplot(gs[row, 1])
    panel_donut(ax3, df, "commits", T["commits_donut"], T["commits_share"])
    row += 1

    ax4 = fig.add_subplot(gs[row, 0])
    panel_metric_by_project(ax4, df, colors, display_authors, "churn",
                             T["churn_title"], T["churn_ylabel"])

    ax5 = fig.add_subplot(gs[row, 1])
    panel_donut(ax5, df, "churn", T["churn_donut"], T["churn_share"])
    row += 1

    ax6 = fig.add_subplot(gs[row, :])
    panel_table(ax6, df)

    # Le handle si prendono da ax2 (commit per progetto): il primo pannello che disegna
    # le barre impilate con label=autore, fonte della legenda unica di figura.
    handles, labs = ax2.get_legend_handles_labels()
    legend = None
    if len(labs) >= 2:
        legend = fig.legend(handles, labs, loc="lower center", ncol=min(len(labs), 6),
                            fontsize=9, labelcolor=INK_SECONDARY, frameon=False,
                            bbox_to_anchor=(0.5, LEGEND_BOTTOM_PAD_INCHES / fig_height))

    # Riquadro «cosa non misura»: sopra la legenda, ancorato in pollici dal bordo inferiore
    # come la legenda (fit_footer() li ri-ancora insieme se la figura si allunga).
    limits_y = LEGEND_BOTTOM_PAD_INCHES + legend_height + LIMITS_GAP_INCHES
    limits_artist = fig.text(0.02, limits_y / fig_height, limits_text, fontsize=8,
                             color=INK_MUTED, va="bottom", ha="left", linespacing=1.3)

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
    fit_footer(fig, ax6, [(legend, LEGEND_BOTTOM_PAD_INCHES), (limits_artist, limits_y)],
               footer_inches, suptitle)

    safe_start = str(start).replace(" ", "_").replace("/", "-")
    safe_end = str(end).replace(" ", "_").replace("/", "-")
    output_filename = f"git_activity_multi_project_report_{safe_start}_{safe_end}.png"
    fig.savefig(output_filename, dpi=200)
    # La forma "Report multi-progetto ... generato con successo: <file>" va mantenuta:
    # l'estensione VS Code la intercetta via regex (il testo fra i due estremi è libero).
    print(f"\nReport multi-progetto (indice di attività) generato con successo: {output_filename}")


if __name__ == "__main__":
    main()
