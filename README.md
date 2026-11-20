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

**ktfigure** is a desktop GUI application that lets researchers visually design and export figures built on top of [seaborn](https://seaborn.pydata.org/) and [matplotlib](https://matplotlib.org/). You drag plot regions onto an A4 artboard, load your CSV/TSV data, configure plot types and aesthetics through point-and-click dialogs, and export to PNG, PDF, or SVG — all without writing a single line of code.

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

**Requirements:** Python 3.10 or higher

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

After installation, run either of the following commands:

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

> **Data format:** ktfigure only accepts tabular data stored in **CSV** or **TSV** files. Each column should represent a variable and each row an observation. Other formats (Excel, JSON, databases, etc.) are not supported.

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

### Community gallery

The [community gallery](https://tuonglab.github.io/ktfigure/community.html)
uses GitHub issues for submissions and comment threads. The issue form and its
attachments are public, including the submitter's GitHub username, even when
the gallery display name is anonymous. Only share material you can publish.

The `Prepare community figure` workflow validates GitHub-hosted JPEG/PNG
attachments, strips image metadata, resizes and compresses a copy, and opens a
pull request for review. Repository administrators must enable **Settings →
Actions → General → Workflow permissions → Allow GitHub Actions to create and
approve pull requests**. A workflow-created pull request using `GITHUB_TOKEN`
does not automatically start the usual pull-request workflows; maintainers
should review and validate it before merging. If preparation fails, check the
Actions run and rerun it after the problem is addressed.

The gallery displays at most 200 approved figures. Submission pull requests
remove the oldest files when necessary; a separate retention workflow proposes
cleanup if concurrent merges exceed the limit. Those deletions require review
and do not remove files from Git history or attachments from their issues.
The Pages workflow builds `docs/community/entries.json` from the individual
metadata files. For a local preview, install
`.github/scripts/gallery-requirements.txt`, run
`python .github/scripts/community_gallery.py build`, then serve `docs/` over HTTP.

---

## Contributing

Contributions are welcome and appreciated. If you encounter a bug, have a feature request, or want to improve the code:

- **Bug reports & feature requests:** [Open an issue](https://github.com/tuonglab/ktfigure/issues) and describe the problem or idea with as much detail as possible.
- **Pull requests:** Fork the repository, make your changes on a new branch, and submit a PR against `master`. Please include a clear description of what the change does and why.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

