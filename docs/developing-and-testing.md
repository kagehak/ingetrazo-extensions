# Developing and testing extensions

This repo holds the extension *source*. To try an extension out, you run it
inside a separate checkout of the [IngeTrazo](https://github.com/kagehak/ingetrazo)
app, which is the runtime that actually loads and executes plugins.

## 1. Set up the IngeTrazo test runtime

Clone `kagehak/ingetrazo` somewhere else on disk — it is not part of this
repo and is only used here as a test runtime:

```powershell
git clone https://github.com/kagehak/ingetrazo.git
cd ingetrazo
```

Create its Python virtual environment and install its own dependencies, per
that repo's `requirements.txt`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Link your extension into IngeTrazo's plugins folder

Back in this repo, run `scripts\dev-link.ps1` with the extension's name
(its file or folder name at this repo's root):

```powershell
cd path\to\ingetrazo-extensions
scripts\dev-link.ps1 -Name standalone-3d-html-viewer
```

This creates a symlink (falling back to a directory junction, or a hard
link for a single file, if your machine doesn't allow symlinks without
elevated permissions) from IngeTrazo's user plugins folder
(`%APPDATA%\ingetrazo\plugins\`) back to the extension's file(s) in this
repo. Edits you make here are picked up the next time IngeTrazo starts —
no copying needed.

Other useful invocations:

```powershell
# Show what's currently linked, and whether it points back to this repo
scripts\dev-link.ps1 -List

# Remove a link (only removes entries this script created; never touches a
# real, non-linked installed extension)
scripts\dev-link.ps1 -Name standalone-3d-html-viewer -Unlink
```

IngeTrazo only discovers two shapes in its plugins folder: a loose
`<name>.py` file, or a `<name>\__init__.py` package. `dev-link.ps1`
understands this repo's folder convention (a folder containing a README.md
and a same-named `<name>.py`, like `standalone-3d-html-viewer/`) and links
just the inner `.py` file, so it still shows up correctly as `<name>.py` in
the plugins folder.

## 3. Launch IngeTrazo and test

From the IngeTrazo checkout, with its venv active:

```powershell
python main.py
```

Your extension's tool(s) should appear in the **Extensions** menu. Restart
IngeTrazo to pick up changes that add/remove tools or change `setup(app)`
wiring; some edits (e.g. inside an already-open dialog) may need a restart
too — when in doubt, restart.

## Conventions for new extensions

- Each extension lives in its own folder or single file at this repo's
  root, matching the existing `standalone-3d-html-viewer/` convention: a
  folder named after the extension, containing a same-named `.py` file and
  a `README.md` describing install/use instructions.
- When starting a **new** extension, a reasonable workflow is one
  branch/session per extension, so unrelated extensions don't get tangled
  into the same change set.
