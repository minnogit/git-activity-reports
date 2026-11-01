# Git Activity Reports

**English** · [Italiano](README.it.md)

Generate charts and statistics of Git activity (commits, changed lines, active days, authors)
from VS Code, for one repository or a whole workspace, over a date range of your choice.

![Single-repository report](https://raw.githubusercontent.com/minnogit/git-activity-reports/main/docs/images/single-repo-report-en.png)

*Report generated from a synthetic repository (fictional authors).*

## Features

- **Analyze Current Project**: activity chart of the repository you are working in.
- **Analyze Whole Workspace (Multi-Repo)**: comparative report of every Git repository found in
  the workspace (up to 3 levels deep).
- **Analyze My Work**: the same reports, but only for you (identity from `git config user.email`
  or from the `git-activity.author` setting).
- **Configurable date range**, absolute or relative (`30 days ago`, `last monday`).
- **Integrated viewer**: the chart opens in a panel and is saved as a PNG; from the final
  notification you can save a copy or reveal it in its folder.
- Authors with several Git identities can be merged with `git-activity-aliases.json` (see the
  [project README](https://github.com/minnogit/git-activity-reports#readme)).

The numbers are indicators, not absolute measures: how to read the charts is explained in the
[project README](https://github.com/minnogit/git-activity-reports#readme).

![Multi-repository report](https://raw.githubusercontent.com/minnogit/git-activity-reports/main/docs/images/multi-repo-report-en.png)

## Requirements

- **Linux or macOS with bash and GNU `date`** (on macOS you need GNU coreutils: BSD `date -d`
  does not work). Native Windows is not supported: use WSL.
- **Git** on the `PATH`.
- **Python 3 with `pandas` and `matplotlib`**: without them the chart is not generated.
- VS Code 1.80 or later, with a **trusted workspace** on a real filesystem (the extension runs
  local scripts: it does not work in virtual workspaces).

Commands, settings, messages and the text inside the charts follow the VS Code display
language: Italian if VS Code is in Italian, English otherwise.

## Installation

The extension contains no analysis logic of its own: when you run a command it calls the
collector and the plotter of this project (`git_stats_collector.sh` / `plot_git.py`, or their
multi-repository variants) as a pipe of two child processes. Their paths are resolved in this
order (`resolveScriptPaths` in `src/extension.ts`):

1. `bundled/` inside the extension itself, filled by `npm run copy-bundled` during
   `vscode:prepublish` and therefore present in every packaged `.vsix`: this is what makes a
   VSIX/Marketplace installation self-contained.
2. The parent folder of `vscode-extension/` (the repository checkout): development mode, when
   the extension runs from there and `copy-bundled` has never been run.
3. The same script names on the `PATH`, as installed by the project's `.deb` package.

### From a VSIX

```bash
cd vscode-extension
npm install
npx vsce package      # runs copy-bundled + compile, produces git-activity-reports-<version>.vsix
code --install-extension git-activity-reports-<version>.vsix
```

Alternatively, from VS Code: Extensions (Ctrl+Shift+X) → "…" menu → "Install from VSIX...".

### Development mode

1. Clone the repository (the extension must stay in `vscode-extension/`, next to the
   collector and plotter scripts).
2. `cd vscode-extension && npm install && npm run compile`.
3. Press `F5` in VS Code: an "Extension Development Host" window opens with the extension
   active, using the scripts of the checkout.

### Marketplace

The extension is not (yet) published on the VS Code Marketplace.

## Usage

1. Open a Git project or workspace in VS Code.
2. Press `Ctrl+Shift+P` to open the Command Palette.
3. Run:
   - **Git Activity: Analyze Current Project** for a single repository.
   - **Git Activity: Analyze Whole Workspace (Multi-Repo)** for several repositories.
   - **Git Activity: Analyze My Work** to see only your own work (see below).
4. A progress notification is shown while the analysis runs.
5. When it finishes, a panel shows the chart and a notification gives the file path, with
   **Save as…** and **Show in folder** buttons.

### Analyze my work

**Git Activity: Analyze My Work** produces the same report with only your commits. The identity is, in order:

1. the `git-activity.author` setting (a name as it appears in the reports, or an email), if set;
2. the email from `git config user.email` in the current repository.

If the workspace has more than one repository, a menu asks whether to analyze the current project or the whole workspace. The collector applies the filter: with an email the comparison is exact and case-insensitive, and it also includes the other identities that your `git-activity-aliases.json` file merges with that email (or that a repository `.mailmap` merges). If you commit under several emails and have not merged them, set `git-activity.author` or add email aliases (see the [project README](https://github.com/minnogit/git-activity-reports#readme)). The single-repository report has no ownership panel in this mode, because it would show the other authors.

### Where the PNG is saved

The file name is the same on every analysis (`git_stats.png` for a single repository): a new
analysis overwrites the previous one, so save a copy if you want to keep it. The folder is, in
order:

1. the `git-activity.outputDir` setting, if set;
2. for multi-repo, the first workspace folder (normally the one that contains the repos);
3. for a single repository, the extension's storage folder — not the repository, so the PNG
   does not show up as an untracked file in `git status`.

The multi-repo report is named `git_activity_multi_project_report_<start>_<end>.png`.

### Settings

Open Settings (`Ctrl+,`) and search for "Git Activity":

- `Start Date`: start of the range (e.g. `2026-01-01` or `30 days ago`).
- `End Date`: end of the range (e.g. `now` or `2026-12-31`).
- `Output Dir`: folder of the generated PNG (empty = see above; a leading `~` is supported).
- `Author`: name or email used by "Analyze My Work" (empty = `git config user.email` of the repository).

Dates can be absolute (`YYYY-MM-DD`) or any relative expression understood by GNU `date -d`
(`yesterday`, `2 weeks ago`, `last monday`, ...). The extension resolves them to an absolute
date before each analysis, so the defaults (`30 days ago` / `now`) always mean "the last
month", not a fixed pair of dates. An unrecognized value produces an error instead of being
passed on to the scripts.

## Development

### Project structure

- `src/extension.ts`: main extension code (TypeScript).
- `package.json`: extension metadata and configuration. User-visible texts live in
  `package.nls.json` (English) and `package.nls.it.json`; runtime messages in
  `l10n/bundle.l10n.it.json` (the key is the English string passed to `vscode.l10n.t`).
- `images/icon.png`: icon (128×128, placeholder). `CHANGELOG.md`: changes per version.
- `out/`: compiled JavaScript.
- `scripts/copy-bundled.js`: copies the 4 collector/plotter scripts from the repository root
  into `bundled/` (run by `npm run copy-bundled`, part of `vscode:prepublish`). It is a build
  step only and is not part of the package (`.vscodeignore`).
- `bundled/`: scripts copied by `copy-bundled.js` and included in the `.vsix`; a build
  artifact, not committed.

### Scripts

- `npm run compile`: compile TypeScript.
- `npm run watch`: compile on change.
- `npm run lint`: ESLint.
- `npm test`: smoke test inside a real VS Code (downloads about 330 MB the first time).

## License

MIT, see [LICENSE](LICENSE).

## Contact

For problems or suggestions open an issue on the
[repository](https://github.com/minnogit/git-activity-reports/issues).
