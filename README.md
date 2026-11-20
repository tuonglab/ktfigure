# ktfigure
<p align="center">
  <img src="src/ktfigure/images/ktfigure_logo.png" alt="ktfigure logo" width="300"/>
</p>

<h1 align="center">ktfigure</h1>

<p align="center">
  <a href="https://github.com/tuonglab/ktfigure/actions/workflows/ci.yml">
    <img src="https://github.com/tuonglab/ktfigure/actions/workflows/ci.yml/badge.svg?branch=master" alt="CI"/>
  </a>
</p>

<p align="center">
  A GUI tool for researchers to create publication-quality seaborn/matplotlib plots — no coding required.
</p>

---

## Overview

**ktfigure** is a desktop GUI application that lets researchers visually design and export figures built on top of [seaborn](https://seaborn.pydata.org/) and [matplotlib](https://matplotlib.org/). You drag plot regions onto an A4 artboard, load your CSV/TSV data, configure plot types and aesthetics through point-and-click dialogs, and export to PNG, PDF, or SVG.

### Supported plot types

`scatter` · `line` · `bar` · `barh` · `box` · `violin` · `strip` · `swarm` · `histogram` · `kde` · `heatmap` · `count` · `regression`

### Key features

- **Drag-to-create plot regions** on an A4 canvas (794 × 1123 px at 96 DPI)
- **Live plot preview** while configuring data columns and aesthetics
- **Column mapping** for X, Y, Hue (color grouping), and Size (scatter)
- **Shape and text annotation** tools (lines, rectangles, circles, free text)
- **Multi-object selection** with alignment and distribution tools
- **Undo / Redo** (50-level history)
- **Light / dark theme** (auto-switches by time of day, or toggle manually)
- **Export** to PNG, PDF (vector), and SVG (vector)

---

## Installation

### Download the desktop app

Download the archive for your computer from the
[latest GitHub release](https://github.com/tuonglab/ktfigure/releases/latest).
No Python or Git installation is needed.

| Computer | Download | Open |
|---|---|---|
| Windows 64-bit | `ktfigure-windows-x64.zip` | Extract the zip, then double-click `ktfigure/ktfigure.exe`. |
| macOS Apple silicon | `ktfigure-macos-arm64.zip` | Extract the zip, then double-click `ktfigure.app`. |
| macOS Intel | `ktfigure-macos-x64.zip` | Extract the zip, then double-click `ktfigure.app`. |
| Linux x86-64 | `ktfigure-linux-x64.tar.gz` | Extract the archive, then open `ktfigure/ktfigure`. A graphical desktop is required. |

Keep the extracted application and its accompanying files together. These builds are unsigned and not notarized, so Windows SmartScreen or macOS
Gatekeeper may warn when opening them. On macOS, if the app is blocked, open **System Settings
→ Privacy & Security** and use **Open Anyway** after verifying the download.
On Linux, if the file manager will not launch the app, allow it to run as a
program in its properties or run `./ktfigure/ktfigure` from a terminal.

### Install from source

**Requirements:** Python 3.10 or higher, Git and Tkinter.

```bash
git clone https://github.com/tuonglab/ktfigure.git
cd ktfigure
pip install .
```

> **Note:** On some systems, Tkinter must be installed separately.
> - **Ubuntu/Debian:** `sudo apt-get install python3-tk`
> - **Fedora:** `sudo dnf install python3-tkinter`
> - **macOS/Windows:** Tkinter is included with the standard Python installer from [python.org](https://www.python.org/).

---

## Quick Start

For a step-by-step guide with screenshots and styling examples, see the
[ktfigure tutorial](https://tuonglab.github.io/ktfigure/).

### 1. Launch the application

Open the downloaded app as described above. If you installed from source, run
either of the following commands:

```bash
ktfigure
# or
plot
```

Or run directly from source:

```bash
python -m ktfigure
```

### 2. Create a plot

1. In the toolbar, click **Plot** mode.
2. Click and drag on the white artboard to define the plot region.
3. A configuration dialog will open — go to the **Data** tab and load a CSV or TSV file.
4. Switch to the **Plot** tab, select your plot type, and map your data columns to X, Y, and (optionally) Hue.
5. Click **Apply** to render the plot on the canvas.

> **Data format:** ktfigure accepts tabular data in **CSV** or **TSV** files. Put variables in columns and observations in rows. Excel, JSON and database connections are not supported.

For large scatterplots, **GPU scatter preview** opens a separate interactive
OpenGL window for numeric X and Y. Drag to pan and use the mouse wheel to zoom.
Its axes are normalized to 0–1 (the original ranges appear above the plot), and
its points use one colour; configured hue, size and other styling are not applied.
Non-finite pairs are omitted and counted above the plot. This preview does not
change the artboard or exports: those still use all data and Matplotlib on the
CPU. The small configuration thumbnail samples 20,000 rows for large
scatterplots. OpenGL may use a software renderer when a GPU is unavailable.

The desktop builds include the preview dependencies. For a source installation,
install them separately with `pip install ".[gpu]"` from the cloned repository.
If OpenGL is unavailable, the normal CPU plotting workflow remains available.

### 3. Annotate (optional)

Use the **Line**, **Rectangle**, **Circle**, and **Text** toolbar modes to add annotations to your figure.

### 4. Export

Click **PNG**, **PDF**, or **SVG** in the toolbar.

---

### Keyboard shortcuts

| Action | macOS | Windows / Linux |
|---|---|---|
| Undo | `Cmd Z` | `Ctrl Z` |
| Redo | `Cmd Shift Z` | `Ctrl Y` |
| Cut / Copy / Paste | `Cmd X/C/V` | `Ctrl X/C/V` |
| Select All | `Cmd A` | `Ctrl A` |
| Delete selected | `Delete` / `Backspace` | `Delete` / `Backspace` |

---

## Tutorial website

The static tutorial lives in `docs/`. To publish it, set **Settings → Pages →
Build and deployment → Source** to **GitHub Actions**. The `Publish tutorial`
workflow deploys changes to `docs/` pushed to `master`; it can also be run
manually from the Actions tab. Repository administrators may need to enable
Pages and approve the `github-pages` environment.

To regenerate the screenshots on Linux, install the package and run:

```bash
xvfb-run -a -s "-screen 0 1600x1000x24" python .github/scripts/generate_tutorial_screenshots.py
```

To regenerate the synthetic six-panel showcase illustrations, run:

```bash
python .github/scripts/generate_showcase_figures.py
```

### Desktop releases

Push a version tag such as `v1.0.2` to run **Build desktop apps**. It builds
and smoke-tests the four archives on their target platforms, then publishes them
in a GitHub release only after all builds succeed. The workflow can also be run
manually to build downloadable Actions artifacts without publishing a release.
The release links above and on the tutorial site become available once the
first desktop release is published. Builds are unsigned; signing and macOS
notarization require separate credentials and configuration.

### Community gallery

The [community gallery](https://tuonglab.github.io/ktfigure/community.html)
embeds public X and LinkedIn posts. Its Formspree form sends submissions
privately to the maintainer; no images are uploaded to GitHub. Configure and
verify the form's recipient and delivery in Formspree. Embeds load third-party
content, and posts may later become unavailable.

After reviewing a submission and confirming permission, a maintainer with
repository write access can run **Actions → Manage community gallery** on the
default branch. Choose `add` or `remove`, enter the public post URL, and
optionally add a public description. The workflow commits the link directly
to the default branch and explicitly dispatches Pages deployment; branch rules
still apply. It accepts X status links and LinkedIn posts containing an activity,
share or ugcPost ID, as well as `lnkd.in` links that resolve to these posts.
Short-link resolution requires access to LinkedIn's redirect service. Some
LinkedIn links or posts may not support embedding;
use the original post link shown on each card. The gallery retains the latest
200 posts. Submissions are not screened with AI; GitHub Actions runner usage may
incur charges. For a local preview, serve `docs/` over HTTP.

---

## Contributing

Contributions are welcome and appreciated. If you encounter a bug, have a feature request, or want to improve the code:

- **Bug reports & feature requests:** [Open an issue](https://github.com/tuonglab/ktfigure/issues) and describe the problem or idea with as much detail as possible.
- **Pull requests:** Fork the repository, make your changes on a new branch, and submit a PR against `master`. Please include a clear description of what the change does and why.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

