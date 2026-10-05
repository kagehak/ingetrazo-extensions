# Standalone 3D HTML viewer

Export the current IngeTrazo scene as a single `.html` file that can be opened
in a modern desktop browser.

## Install

In IngeTrazo, choose **Extensions → Open plugins folder**. Copy this entire
`standalone-3d-html-viewer` folder into the plugins folder, then restart
IngeTrazo. Alternatively, copy `__init__.py` there as
`standalone_3d_html_viewer.py` and restart. The user plugins folder is
`%APPDATA%\ingetrazo\plugins\` on Windows and
`~/.local/share/ingetrazo/plugins/` on Linux (honouring `XDG_DATA_HOME`).

## Use

Choose **Extensions → Export standalone 3D HTML…**, select a destination, and
open the resulting file in a browser. The viewer supports orbiting by dragging,
zooming by scrolling, **Reset view**, and **Fullscreen**.

The model's geometry, materials, and textures are embedded in the HTML as GLB
data. The viewer loads the pinned Three.js 0.160.0 runtime from jsDelivr when
the HTML is opened, so a network connection to that CDN is required; the model
data itself is not fetched separately. Use a current browser with ES module and
import-map support plus WebGL enabled. The file can be opened directly from
disk; no local server or extra browser plugin is needed.
