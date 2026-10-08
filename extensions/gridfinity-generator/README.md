# Gridfinity Generator

Generate Gridfinity-compatible storage bins and baseplates directly in
IngeTrazo.

## Features

- Create storage, parts, and blank bins, plus plain and magnetized baseplates.
- Edit grid dimensions and use a custom cell-by-cell footprint.
- Configure bin and baseplate settings, then select a generated model to reload
  its saved settings and update it in place.
- Add parts-bin dividers with adjustable count, height, and thickness.
- Add finger scoops with rounded ends that follow the inside corners, or choose
  straight ends for the legacy style.
- Configure stacking lips, magnet pockets, recessed blank-bin tops, and label
  shelves.

## Install

In IngeTrazo, choose **Extensions → Open plugins folder**. Copy this entire
`gridfinity-generator` directory into the plugins folder, then restart
IngeTrazo. Alternatively, copy `gridfinity-generator.py` directly into the
plugins folder and restart. The user plugins folder is
`%APPDATA%\ingetrazo\plugins\` on Windows and
`${XDG_DATA_HOME:-~/.local/share}/ingetrazo/plugins/` on Linux.

## Use

Open **Extensions → Gridfinity Generator** to show the sidebar. Choose a bin
or baseplate variant, adjust its settings and footprint, then select **Create
model**. Select a generated model to edit its saved settings and update it.

## Requirements

Run the plugin inside a supported IngeTrazo installation. It uses the
application's PySide6 UI and internal `core` and `formats` APIs; it is not a
standalone Python script.

The plugin loads NumPy and `manifold3d` when geometry operations need them.
They are required for boolean-based features such as footprints with omitted
cells, magnetized or screw-together baseplates, and rounded scoop ends that
follow the bin corners. Ensure both packages are available in IngeTrazo's
Python environment if they are not already included. The boolean dependency
is not needed for full rectangular footprints, plain baseplates without
screw-together holes, or straight-ended scoops.
