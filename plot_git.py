#!/usr/bin/env python3
"""Report di attività Git per singolo repository (granularità temporale adattiva).

Legge da stdin il JSON prodotto da git_stats_collector.sh e genera git_stats.png.

METRICHE
--------
Non esiste un singolo numero che misuri il "valore" del lavoro di sviluppo, quindi
questo report mostra TRE metriche affiancate invece di un punteggio unico, in ordine
di quanto sono attendibili — non di quanto sono impressionanti:

  giorni attivi  Giorni distinti con almeno un commit. È la metrica più robusta:
                 non è gonfiabile né da un singolo commit enorme né da tanti micro-commit,
                 e non risente in alcun modo di codice generato o file voluminosi.
                 Primo pannello, a piena larghezza, come MATRICE DI PRESENZA (autori in
                 ordine alfabetico × periodi, cella = giorni attivi): mostra CHI ha lavorato
                 QUANDO senza ordinare né sommare per persona.
  commit         Numero di commit (esclusi i merge). Secondo pannello (a sinistra).
  churn          = aggiunte + 0.4 * rimozioni
                   Le rimozioni contano: cancellare codice morto è lavoro reale.
                   Il peso < 1 riflette che rimuovere costa in genere meno che scrivere.
                   È la meno indicativa delle tre: git_stats_collector.sh NON esclude
                   codice generato, vendorizzato o lock file (vedi il commento in testa
                   a quello script per il perché — in breve, qualunque esclusione basata
                   su directory può rompere il rilevamento dei rename di git, misurato
                   fino a 9.7x di inflazione su una singola giornata). Terzo pannello
                   (a destra, affiancato al commit per il confronto diretto).

Nota storica: fino alla v3 il report aveva anche un INDICE composito (somma sui giorni di
ln(1 + churn_giorno con tetto) e ln(1 + file distinti)), relegato alla tabella. È stato
rimosso: era la parte più simile a un punteggio e invitava a leggere la tabella come una
classifica. Due lezioni misurate restano utili anche senza di lui: una forma moltiplicativa
azzerava le giornate di sole cancellazioni, e un tetto applicato all'aggregato di periodo
(invece che per giorno) si saturava; il valore stesso del tetto (1000, poi 15000) dipendeva
dal modello di sviluppo — vedi CLAUDE.md.

NESSUNA VALUTAZIONE DELLE PERSONE: il report non ha punteggi né totali per persona; gli
autori compaiono in ordine alfabetico e come presenza. Per vedere il lavoro di UNA persona si
filtra per autore al collector. Il riepilogo numerico è del repository, non per autore.

ATTENZIONE: sono indicatori di attività, non misure di produttività o di qualità.
Code review, design, mentoring e debugging difficile sono strutturalmente invisibili.

PUNCH CARD (pannello opzionale)
----------------------------------------
Un riquadro aggiuntivo mostra QUANDO avvengono i commit (giorno della settimana × ora
locale del commit), aggregato su tutti gli autori del report. Non è una quarta metrica
in competizione con le tre sopra — è descrittivo ("quando"), non valutativo ("quanto" o
"quanto bene"): i timestamp dei commit non sono un proxy affidabile delle ore lavorate,
quindi il pannello non tenta di stimarle. Presente solo se il JSON in input contiene il
campo `punch_card` per almeno un autore (i JSON prodotti da versioni precedenti di
git_stats_collector.sh non lo hanno; in quel caso il pannello viene saltato, non
lasciato vuoto).

OWNERSHIP (pannello opzionale)
----------------------------------------
Un riquadro aggiuntivo mostra, per autore, quante righe del repository sono "possedute"
secondo `git blame` all'ULTIMO COMMIT ≤ end_date (fotografia, non serie temporale: a
differenza di tutto il resto del report non risponde a "chi ha lavorato nel periodo" ma
a "di chi è il codice presente nell'albero in quel momento"). Può includere autori mai
attivi nel periodo richiesto, se hanno ancora codice presente e non toccato da nessuno.
Nessuna esclusione di file generati/vendorizzati (stessa scelta fatta per il churn — vedi
git_stats_collector.sh). Presente solo se il JSON in input contiene la chiave
`ownership` (assente nei JSON prodotti con --no-ownership o da versioni precedenti dello
script; in quel caso il pannello viene saltato, non lasciato vuoto).
"""

import json
import os
import subprocess
import sys
from datetime import date, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors
import matplotlib.ticker
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Parametri delle metriche (mantenere allineati con plot_multiproject.py)
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

# -----------------------------------------------------------------------------
# Lingua delle scritte nel grafico (solo il PNG: i messaggi su stdout restano invariati,
# perché l'estensione VS Code li intercetta via regex). Tabella duplicata in
# plot_multiproject.py, come le metriche e la palette: aggiornarle entrambe.
# -----------------------------------------------------------------------------
STRINGS = {
    "it": {
        "other": "Altro",
        "buckets": {"D": "giorno", "W-MON": "settimana", "MS": "mese"},
        "suptitle": "Attività di sviluppo",
        "suptitle_range": "{title}  ({start} → {end}, per {bucket})",
        "trend": "Trend (media {n})",
        "presence_title": "Presenza per autore (giorni attivi per {bucket})",
        "presence_caption": "Più scuro = più giorni attivi",
        "presence_hidden": "mostrati {shown} autori su {total} (i più attivi)",
        "commits_title": "Commit per {bucket}, per autore",
        "commits_ylabel": "Commit",
        "churn_title": "Churn per {bucket}, per autore",
        "churn_ylabel": "Righe (aggiunte + 0.4 × rimosse)",
        "table_title": "Riepilogo del periodo",
        "table_cols": ["Commit", "Churn", "File", "Giorni attivi", "Autori"],
        "table_note": "Totali del repository, non per persona. Churn = aggiunte + 0.4 × rimozioni",
        "weekdays": ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
        "punch_title": "Quando avvengono i commit (giorno × ora)",
        "punch_xlabel": "Ora (locale del commit)",
        "punch_cbar": "Commit",
        "punch_caption": "Picco: {wd} alle {h1:02d}-{h2:02d} ({n} commit) · "
                         "Weekend: {pct:.0f}% del totale",
        "own_title": "Righe possedute per autore (fotografia a fine periodo)",
        "own_xlabel": "Righe (git blame)",
        "own_caption": "Istantanea al commit {ref} del {date} · {total} righe totali "
                       "(git blame, nessuna esclusione) · non è una somma sul periodo: può "
                       "includere autori non attivi in questo report",
        "thousands_sep": ".",
    },
    "en": {
        "other": "Other",
        "buckets": {"D": "day", "W-MON": "week", "MS": "month"},
        "suptitle": "Development activity",
        "suptitle_range": "{title}  ({start} → {end}, per {bucket})",
        "trend": "Trend ({n}-period avg)",
        "presence_title": "Presence by author (active days per {bucket})",
        "presence_caption": "Darker = more active days",
        "presence_hidden": "showing {shown} of {total} authors (most active)",
        "commits_title": "Commits per {bucket}, by author",
        "commits_ylabel": "Commits",
        "churn_title": "Churn per {bucket}, by author",
        "churn_ylabel": "Lines (added + 0.4 × deleted)",
        "table_title": "Period summary",
        "table_cols": ["Commits", "Churn", "Files", "Active days", "Authors"],
        "table_note": "Repository totals, not per person. Churn = added + 0.4 × deleted",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "punch_title": "When commits happen (day × hour)",
        "punch_xlabel": "Hour (commit local time)",
        "punch_cbar": "Commits",
        "punch_caption": "Peak: {wd} at {h1:02d}-{h2:02d} ({n} commits) · "
                         "Weekend: {pct:.0f}% of total",
        "own_title": "Lines owned by author (snapshot at end of period)",
        "own_xlabel": "Lines (git blame)",
        "own_caption": "Snapshot at commit {ref} of {date} · {total} total lines "
                       "(git blame, no exclusions) · not a sum over the period: it may "
                       "include authors not active in this report",
        "thousands_sep": ",",
    },
}
T = STRINGS["it"]


def detect_lang(argv, environ):
    """Lingua delle scritte del grafico, in ordine: --lang it|en, GIT_ACTIVITY_LANG,
    locale di sistema (LC_ALL > LC_MESSAGES > LANG: "it_*" -> it), altrimenti inglese.
    Il locale come default lascia invariato l'uso storico da riga di comando su un
    sistema italiano; l'estensione VS Code passa GIT_ACTIVITY_LANG dalla lingua di VS Code."""
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

OUTPUT_FILENAME = "git_stats.png"

# -----------------------------------------------------------------------------
# Geometria della figura (vedi il commento sul layout in main())
# -----------------------------------------------------------------------------
# Stesso problema, stessa causa e stesso fix già misurati e applicati in
# plot_multiproject.py: le celle della tabella sono dimensionate dal FONT, non
# dall'asse che le contiene, quindi un height_ratio fisso lascia una banda vuota con
# pochi autori (il caso comune per un singolo repo) e rischia lo sforo con molti.
# Misurato per QUESTA tabella (6 colonne, fontsize 9, table.scale(1, 1.45) — diverso
# dalle 7 colonne di plot_multiproject.py, da qui la costante diversa): 0.267 pollici
# per riga, header incluso, indipendente dall'altezza dell'asse.
MAX_MATRIX_ROWS = 30         # righe massime di una matrice di presenza (oltre: nota, mai taglio muto)
MATRIX_CELL_INCHES = 0.30    # altezza di una riga di cella: abbastanza per una cifra da 8 pt
MATRIX_MIN_AXES_INCHES = 0.60
MATRIX_RAMP = ["#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # = PUNCH_RAMP[1:]
EMPTY_CELL = "#efeee8"       # cella senza giorni attivi: quasi invisibile, non una tinta di dato
TABLE_ROW_INCHES = 0.267
TABLE_PAD_INCHES = 0.30     # una sola riga di totali: poco respiro, la nota sta subito sotto
ROW_UNIT_INCHES = 2.846   # altezza in pollici di UNA unità di height_ratio: mantenerla
                          # costante lascia giorni-attivi e commit/churn della stessa
                          # dimensione assoluta qualunque sia l'altezza della tabella
TABLE_RATIO_MIN = 0.25
FIG_WIDTH_INCHES = 17
FIG_HSPACE = 0.72      # i pannelli sono più bassi di prima (matrice sottile): più aria fra le righe
HEADER_INCHES = 0.95      # spazio sopra la prima riga: suptitle + titolo del pannello
SUPTITLE_INCHES = 0.40
# Spazio sotto l'ultima riga: nota della tabella + legenda. La legenda va a capo su più
# righe quando gli autori (fino a 8 + "Altro") più "Trend" superano ncol=6: con un
# FOOTER fisso tarato su una riga sola, la seconda riga finiva sopra il pannello
# successivo (misurato: 9 autori reali + Trend = 10 voci, 2 righe, sovrapposte alla
# punch card sotto). Altezza di una riga di legenda misurata via get_window_extent():
# 0.230" la prima, +0.1925" per ogni riga aggiuntiva — lineare, non un'ipotesi.
LEGEND_ROW1_INCHES = 0.230
LEGEND_EXTRA_ROW_INCHES = 0.1925
LEGEND_BOTTOM_PAD_INCHES = 0.08   # distanza tra il bordo inferiore della figura e la legenda
NOTE_INCHES = 0.30                # spazio per la nota sotto la tabella, sopra la legenda


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
    # Punch card (giorno della settimana × ora): aggregata su TUTTI gli autori del report,
    # non serve per-autore, quindi si accumula qui indipendentemente da fold_tail/alias.
    # Assente nel formato legacy (JSON senza metadata) e in JSON prodotti da versioni
    # precedenti: resta a zero, il pannello viene saltato più a valle (vedi main()).
    punch = np.zeros((7, 24), dtype=int)
    for entry in entries:
        author = entry.get("author_name") or entry.get("author") or "Sconosciuto"
        if aliases_needed:
            author = aliases.get(author, author)
        if author == "TOTALE":       # riga aggregata del formato testuale storico
            continue
        for cell in entry.get("punch_card", []) or []:
            wd, hr, c = cell.get("weekday"), cell.get("hour"), cell.get("commits", 0)
            if wd is not None and hr is not None and 0 <= wd < 7 and 0 <= hr < 24:
                punch[wd, hr] += int(c or 0)
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
            })

    if not rows:
        print("Nessun dato di attività trovato nel periodo: niente da rappresentare.")
        sys.exit(0)

    df = pd.DataFrame(rows)
    if not meta.get("start_date"):
        meta["start_date"] = df["date"].min().strftime("%Y-%m-%d")
    if not meta.get("end_date"):
        meta["end_date"] = df["date"].max().strftime("%Y-%m-%d")
    return df, meta, punch


# -----------------------------------------------------------------------------
# Granularità adattiva: un grafico con una barra al giorno diventa illeggibile
# su periodi lunghi, quindi aggreghiamo automaticamente.
# -----------------------------------------------------------------------------
def choose_bucket(start, end):
    span = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if span <= 45:
        freq, window = "D", 7
    elif span <= 250:
        freq, window = "W-MON", 4
    else:
        freq, window = "MS", 3
    return freq, T["buckets"][freq], window


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
        matplotlib.ticker.FuncFormatter(lambda v, _: fmt_int(v))
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
    # Respiro sopra la barra più alta: senza, il vertice tocca il bordo superiore dell'asse.
    if len(pivot.index):
        top = float(bottom.max())
        if top > 0:
            ax.set_ylim(0, top * 1.08)

    if trend_window and len(pivot.index) >= 3:
        total = pivot.sum(axis=1)
        trend = total.rolling(window=trend_window, min_periods=1).mean()
        ax.plot(
            x, trend.to_numpy(), color=INK_PRIMARY, linewidth=2,
            label=T["trend"].format(n=trend_window), zorder=5,
            solid_capstyle="round", solid_joinstyle="round",
        )

    ax.set_title(title, fontsize=12, color=INK_PRIMARY, loc="left", pad=10)
    ax.set_ylabel(ylabel, fontsize=9)
    style_axes(ax)
    thin_ticks(ax, labels)
    thousands(ax)


def panel_table(ax, totals):
    """Riepilogo del periodo: UNA riga di totali del repository, mai per persona.

    Rende leggibili i valori esatti delle metriche aggregate (nessun valore raggiungibile
    solo tramite il colore). I totali per autore sono stati tolti di proposito: una tabella
    con commit e churn per persona, anche in ordine alfabetico, è una classifica."""
    ax.axis("off")
    ax.set_title(T["table_title"], fontsize=12, color=INK_PRIMARY,
                 loc="left", pad=10)

    cells = [[
        fmt_int(totals["commits"]),
        fmt_int(totals["churn"]),
        fmt_int(totals["files"]),
        f"{totals['active_days']}",
        f"{totals['authors']}",
    ]]
    table = ax.table(
        cellText=cells,
        colLabels=T["table_cols"],
        colWidths=[0.16, 0.16, 0.16, 0.16, 0.16],
        cellLoc="center", loc="upper center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.45)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(GRIDLINE)
        cell.set_linewidth(0.6)
        cell.set_facecolor(SURFACE)
        if row == 0:
            cell.set_text_props(color=INK_SECONDARY, weight="semibold")
        else:
            cell.set_text_props(color=INK_PRIMARY)

    ax.text(0, -0.04, T["table_note"], transform=ax.transAxes, fontsize=8,
            color=INK_MUTED, va="top", wrap=True)


# Rampa sequenziale blu (passi 100→700 di palette.md, la stessa usata per la ciambella
# multiprogetto): una tinta, chiaro→scuro, mai un arcobaleno.
PUNCH_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def panel_punch_card(ax, punch):
    """Punch card: quando avvengono i commit (giorno della settimana × ora locale del
    commit, nessuna conversione a un fuso comune). Sequenziale a una tinta — la magnitudine
    è quello che conta, non l'identità di una categoria. Nessuna etichetta per cella (la
    regola è mai un numero su ogni punto): solo la cella di massimo, selettivamente. Essendo
    un PNG statico senza hover, il ripiego di accessibilità per la scala di colore continua
    è la riga di testo con i fatti salienti, aggiunta da chi chiama questa funzione.
    """
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("punch_blue", PUNCH_RAMP)
    im = ax.imshow(punch, aspect="auto", cmap=cmap, interpolation="nearest")

    ax.set_yticks(range(7))
    ax.set_yticklabels(T["weekdays"], fontsize=9, color=INK_SECONDARY)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 3)], fontsize=9, color=INK_MUTED)
    ax.set_xlabel(T["punch_xlabel"], fontsize=9)
    ax.set_title(T["punch_title"], fontsize=12,
                 color=INK_PRIMARY, loc="left", pad=10)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)

    # Gap fra le celle nel colore della superficie: stesso trattamento delle barre
    # impilate, mai un bordo scuro attorno alla cella.
    ax.set_xticks(np.arange(-0.5, 24, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 7, 1), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=1.5)
    ax.tick_params(which="minor", length=0)

    if punch.max() > 0:
        wd, hr = np.unravel_index(np.argmax(punch), punch.shape)
        ax.text(hr, wd, f"{int(punch[wd, hr])}", ha="center", va="center",
                fontsize=9, color="white")

    cbar = plt.colorbar(im, ax=ax, fraction=0.025, pad=0.012)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(length=0, labelsize=8, colors=INK_MUTED)
    cbar.set_label(T["punch_cbar"], fontsize=8, color=INK_MUTED)


def punch_card_caption(punch):
    """Ripiego di accessibilità in testo: la scala di colore continua non è raggiungibile
    da chi non distingue le tinte, e questo è un PNG statico senza hover/tooltip."""
    total = int(punch.sum())
    if total == 0:
        return ""
    wd, hr = np.unravel_index(np.argmax(punch), punch.shape)
    weekend = int(punch[5:7, :].sum())  # Sab (5) + Dom (6)
    return T["punch_caption"].format(wd=T["weekdays"][wd], h1=hr, h2=(hr + 1) % 24,
                                     n=int(punch[wd, hr]), pct=weekend / total * 100)


def panel_ownership(ax, ownership, colors):
    """Righe possedute per autore (git blame), FOTOGRAFIA a fine periodo, non serie
    temporale come gli altri pannelli: risponde a "di chi è il codice oggi", non "chi ha
    lavorato quando". Può includere autori mai attivi nel periodo del report (hanno
    scritto codice ancora presente, nessuno lo ha più toccato) — stesso trattamento
    cromatico di ogni pannello: chi non è tra i primi 8 per attività nel periodo si
    accorpa in "Altro", mai una tinta nuova generata solo per l'ownership.
    """
    folded = {}
    for entry in ownership.get("by_author", []):
        name = entry["author"] if entry["author"] in colors else OTHER_LABEL
        folded[name] = folded.get(name, 0) + entry.get("lines", 0)

    names = sorted(folded, key=lambda n: folded[n])   # ascendente: barh mette il max in alto
    values = [folded[n] for n in names]
    total = sum(values) or 1

    y = np.arange(len(names))
    ax.barh(
        y, values, height=0.6, color=[colors[n] for n in names],
        edgecolor=SURFACE, linewidth=0.6,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=9, color=INK_SECONDARY)
    ax.set_title(T["own_title"], fontsize=12,
                 color=INK_PRIMARY, loc="left", pad=10)
    ax.set_xlabel(T["own_xlabel"], fontsize=9)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRIDLINE, linewidth=0.8, linestyle="-")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(length=0, labelsize=9)
    thousands(ax, axis="x")
    for yi, v in zip(y, values):
        pct = v / total * 100
        label = f" {fmt_int(v)} ({pct:.0f}%)"
        ax.text(v, yi, label, va="center", ha="left", fontsize=9, color=INK_SECONDARY)


def ownership_caption(ownership):
    """Ripiego testuale: chiarisce che questo pannello è un'istantanea (git blame a un
    commit preciso), non un'aggregazione sul periodo come tutti gli altri — altrimenti
    la lettura più naturale (percentuali che sommano sempre esattamente al periodo) è
    quella sbagliata."""
    ref = (ownership.get("ref_commit") or "")[:8]
    ref_date = ownership.get("ref_date") or "?"
    total = int(ownership.get("total_lines", 0))
    return T["own_caption"].format(ref=ref, date=ref_date, total=fmt_int(total))


FOOTER_GAP_INCHES = 0.12   # aria minima fra il fondo dell'ultimo pannello e la legenda


def fit_footer(fig, last_ax, legend, footer_inches, suptitle):
    """Allunga la figura se il fondo dell'ultimo pannello (etichetta dell'asse e
    didascalia comprese) scende sotto la cima della legenda.

    Il footer è dimensionato per la nota della tabella (NOTE_INCHES), ma quando l'ultima
    riga è la punch card o l'ownership sotto l'asse ci sono anche un'etichetta x e una
    didascalia: misurato, con l'ownership in fondo "Righe (git blame)" finiva sotto la
    legenda. Invece di un'altra costante per ogni combinazione di pannelli, si misura il
    contenuto EFFETTIVAMENTE disegnato (bbox reali dopo draw()) e si aggiunge solo lo spazio
    mancante. Header, righe e legenda restano alla stessa distanza in POLLICI dai bordi
    (stessa logica delle costanti in testa): cresce solo il footer.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    content_bottom = last_ax.get_tightbbox(renderer).y0           # pixel dal basso
    legend_top = legend.get_window_extent(renderer).y1 if legend else 0.0
    overlap_px = legend_top + FOOTER_GAP_INCHES * fig.dpi - content_bottom
    if overlap_px <= 0:
        return
    extra = overlap_px / fig.dpi
    width, height = fig.get_size_inches()
    new_height = height + extra
    fig.set_size_inches(width, new_height)
    fig.subplots_adjust(top=1 - HEADER_INCHES / new_height,
                        bottom=(footer_inches + extra) / new_height)
    suptitle.set_y(1 - SUPTITLE_INCHES / new_height)
    if legend:
        legend.set_bbox_to_anchor((0.5, LEGEND_BOTTOM_PAD_INCHES / new_height),
                                  transform=fig.transFigure)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    set_lang(detect_lang(sys.argv[1:], os.environ))
    payload = read_payload()
    aliases = load_aliases()
    if aliases and isinstance(payload, list):
        print(f"Caricati {len(aliases)} alias autore (JSON in formato legacy).")
    df, meta, punch = flatten(payload, aliases)

    start, end = meta["start_date"], meta["end_date"]
    project = meta.get("project") or git_project_name()

    # Ordine degli autori per churn totale: definisce l'assegnazione dei colori,
    # che poi resta la stessa in tutti i pannelli.
    by_size = (df.groupby("author")["churn"].sum()
                 .sort_values(ascending=False).index.tolist())
    # Totali del REPOSITORY e matrice di presenza usano i dati PRIMA del fold in "Altro":
    # nessun totale per persona, e gli autori compaiono uno per uno.
    totals = {
        "commits": int(df["commits"].sum()),
        "churn": float(df["churn"].sum()),
        "files": int(df["files"].sum()),
        "active_days": int(df[df["commits"] > 0]["date"].nunique()),
        "authors": int(df["author"].nunique()),
    }
    df_people = df
    df, author_order = fold_tail(df, by_size)
    colors = assign_colors(author_order)   # per RANGO (serve al fold), mai per ordine mostrato
    display_authors = alpha_order(author_order)

    freq, bucket_name, trend_window = choose_bucket(start, end)

    # Reindicizzazione sul range completo: i periodi senza attività devono comparire
    # come vuoti, altrimenti il grafico comprime il tempo e il trend mente.
    full = pd.date_range(start=start, end=end, freq="D")
    grid = (df.pivot_table(index="date", columns="author",
                           values=["churn", "commits"], aggfunc="sum")
              .reindex(full).fillna(0))

    churn_pivot = grid["churn"].resample(freq).sum()
    commits_pivot = grid["commits"].resample(freq).sum()
    # Colonne in ordine alfabetico (stack e legenda): l'ordine per rango resta solo ai colori
    cols = [a for a in display_authors if a in churn_pivot.columns]
    churn_pivot = churn_pivot[cols]
    commits_pivot = commits_pivot[cols]

    label_fmt = "%Y-%m-%d" if freq == "D" else ("%Y-%m-%d" if freq == "W-MON" else "%Y-%m")
    labels = [d.strftime(label_fmt) for d in churn_pivot.index]

    # Matrice di presenza: giorni attivi per autore e bucket, stessi bucket dei grafici.
    # Si usano le righe con commit; se non ce ne fossero (JSON anomalo) tutte quelle presenti.
    people_rows = df_people[df_people["commits"] > 0]
    if people_rows.empty:
        people_rows = df_people
    pres_matrix, pres_authors, pres_hidden, _ = matrix_inputs(
        people_rows, "author", full, freq, MAX_MATRIX_ROWS, order_keys=alpha_order)
    pres_caption = T["presence_caption"]
    if pres_hidden:
        pres_caption += " · " + T["presence_hidden"].format(
            shown=len(pres_authors), total=len(pres_authors) + pres_hidden)

    ownership = payload.get("ownership") if isinstance(payload, dict) else None
    has_ownership = bool(ownership and ownership.get("total_lines"))

    apply_style()
    # Layout a righe, non più una griglia 2x2 semplice: i giorni attivi (la metrica più
    # robusta, vedi METRICHE sopra) stanno da soli in cima a piena larghezza — la stessa
    # priorità visiva già data alla metrica più affidabile nel report multi-progetto —
    # non più affiancati alla tabella in una posizione meno prominente di commit/churn,
    # che pure sono meno attendibili. Punch card e ownership restano righe AGGIUNTIVE
    # sotto, assenti nei JSON che non le hanno (legacy, o prodotti con --no-ownership).
    has_punch = punch.sum() > 0
    extra_rows = []
    if has_punch:
        extra_rows.append(("punch", 0.7))
    if has_ownership:
        extra_rows.append(("ownership", 0.6))

    n_extra = len(extra_rows)
    # L'altezza della riga tabella si ADATTA al numero di autori effettivamente mostrati,
    # invece di essere fissata sul caso peggiore (12 righe): vedi il commento sulle
    # costanti sopra. La figura si accorcia di conseguenza, quindi header/footer sono
    # espressi in pollici (non in frazione di figura) — altrimenti, accorciando la
    # figura, il suptitle rischia di finire sopra il titolo del primo pannello (misurato
    # con lo stesso bug in plot_multiproject.py prima del fix).
    table_ratio = max(
        TABLE_RATIO_MIN,
        (TABLE_ROW_INCHES * 2 + TABLE_PAD_INCHES) / ROW_UNIT_INCHES,   # intestazione + 1 riga
    )
    matrix_ratio = max(MATRIX_MIN_AXES_INCHES, MATRIX_CELL_INCHES * len(pres_authors)) / ROW_UNIT_INCHES
    ratios = [matrix_ratio, 1.05, table_ratio] + [r for _, r in extra_rows]
    gaps = (len(ratios) - 1) * FIG_HSPACE / len(ratios)
    rows_height = sum(ratios) * ROW_UNIT_INCHES * (1 + gaps)

    # Righe della legenda: stesso criterio con cui sarà disegnata più sotto (autori +
    # "Trend" se disegnato, ncol=min(n, 6)) — va saputo PRIMA di creare la figura, perché
    # il footer deve riservare spazio per tutte le righe, non solo la prima.
    n_legend_labels = len(author_order) + (1 if trend_window and len(labels) >= 3 else 0)
    legend_ncol = min(n_legend_labels, 6) or 1
    legend_rows = -(-n_legend_labels // legend_ncol)  # ceiling division
    legend_height = LEGEND_ROW1_INCHES + max(0, legend_rows - 1) * LEGEND_EXTRA_ROW_INCHES
    footer_inches = LEGEND_BOTTOM_PAD_INCHES + legend_height + NOTE_INCHES

    fig_height = rows_height + HEADER_INCHES + footer_inches
    fig_top = 1 - HEADER_INCHES / fig_height
    fig_bottom = footer_inches / fig_height

    fig = plt.figure(figsize=(FIG_WIDTH_INCHES, fig_height))
    gs = fig.add_gridspec(3 + n_extra, 2, height_ratios=ratios,
                          hspace=FIG_HSPACE, wspace=0.22)

    title = T["suptitle"]
    if project:
        title = f"{project} — {title}"
    suptitle = fig.suptitle(T["suptitle_range"].format(title=title, start=start, end=end,
                                            bucket=bucket_name),
                 fontsize=16, color=INK_PRIMARY, x=0.02, ha="left",
                 y=1 - SUPTITLE_INCHES / fig_height)

    ax0 = fig.add_subplot(gs[0, :])
    panel_matrix(ax0, pres_matrix, pres_authors, labels,
                 T["presence_title"].format(bucket=bucket_name), pres_caption,
                 show_numbers=(freq != "D"))

    # Commit per primo, churn per secondo (fra i due): churn è la meno indicativa delle
    # tre metriche (include codice generato/vendorizzato/lock file — nessuna esclusione,
    # vedi git_stats_collector.sh).
    ax1 = fig.add_subplot(gs[1, 0])
    panel_stacked_over_time(
        ax1, commits_pivot, colors, labels,
        T["commits_title"].format(bucket=bucket_name), T["commits_ylabel"],
    )

    ax2 = fig.add_subplot(gs[1, 1])
    panel_stacked_over_time(
        ax2, churn_pivot, colors, labels,
        T["churn_title"].format(bucket=bucket_name),
        T["churn_ylabel"], trend_window,
    )

    ax4 = fig.add_subplot(gs[2, :])
    panel_table(ax4, totals)
    last_ax = ax4   # pannello più in basso: serve a fit_footer() per evitare la legenda

    row = 3
    if has_punch:
        ax5 = fig.add_subplot(gs[row, :])
        panel_punch_card(ax5, punch)
        last_ax = ax5
        caption = punch_card_caption(punch)
        if caption:
            ax5.text(0, -0.34, caption, transform=ax5.transAxes, fontsize=8,
                     color=INK_MUTED, va="top")
        row += 1

    if has_ownership:
        ax6 = fig.add_subplot(gs[row, :])
        panel_ownership(ax6, ownership, colors)
        last_ax = ax6
        ax6.text(0, -0.28, ownership_caption(ownership), transform=ax6.transAxes,
                 fontsize=8, color=INK_MUTED, va="top")
        row += 1

    # Una sola legenda per tutta la figura: l'identità autore è la stessa in ogni pannello.
    # Gli autori vengono prima, il trend per ultimo (non è una serie di dati). Le handle si
    # prendono da ax2 (churn), l'unico pannello con la linea di trend disegnata sopra.
    handles, labs = ax2.get_legend_handles_labels()
    paired = sorted(zip(labs, handles), key=lambda p: p[0].startswith("Trend"))
    labs = [p[0] for p in paired]
    handles = [p[1] for p in paired]
    legend = fig.legend(handles, labs, loc="lower center", ncol=min(len(labs), 6),
                        fontsize=9, labelcolor=INK_SECONDARY, frameon=False,
                        bbox_to_anchor=(0.5, LEGEND_BOTTOM_PAD_INCHES / fig_height))

    # tight_layout() qui NON funziona: con un gridspec a >2 righe di altezze disomogenee
    # (già vero per il layout base ora, non solo con punch card/ownership) e/o un asse
    # aggiuntivo "incompatibile" (la colorbar del punch card, la legenda a livello di
    # figura) avvisa "Axes that are not compatible" e poi NON calcola nulla — lascia i
    # margini di default di matplotlib (0.125/0.9/0.11, verificato stampando
    # fig.subplotpars), che non sono tarati sul contenuto: abbastanza larghi da non
    # tagliare "Gabriele Stringano" per coincidenza, ma molto più dello spazio realmente
    # necessario. Si misura quindi lo spazio EFFETTIVAMENTE occupato dall'etichetta y più
    # lunga (bbox del testo già renderizzato, non una stima) e si calcola il margine
    # sinistro minimo che la ospita — right/hspace/wspace restano fissi: valori già
    # verificati sul contenuto di questo report; top/bottom sono quelli calcolati sopra
    # in pollici (adattivi all'altezza della figura, vedi il commento sulle costanti).
    fig.subplots_adjust(left=0.055, right=0.97, top=fig_top, bottom=fig_bottom,
                         hspace=FIG_HSPACE, wspace=0.22)
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
    label_span = current_left - min_x0   # larghezza dell'etichetta più lunga, in frazione di figura
    left_margin = max(0.035, label_span + 0.015)   # + un piccolo margine di sicurezza
    fig.subplots_adjust(left=left_margin)
    fit_footer(fig, last_ax, legend, footer_inches, suptitle)
    fig.savefig(OUTPUT_FILENAME, dpi=200)
    # Messaggio invariato: l'estensione VS Code lo intercetta via regex.
    print(f"Grafico generato con successo: {OUTPUT_FILENAME}")


if __name__ == "__main__":
    main()
