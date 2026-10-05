# SPDX-License-Identifier: GPL-3.0-or-later
"""Export the current IngeTrazo scene as a standalone HTML 3D viewer."""
from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from formats.gltf import save_glb
from views.filedialogs import file_dialogs


_THREE_VERSION = "0.160.0"
_THREE_CDN = f"https://cdn.jsdelivr.net/npm/three@{_THREE_VERSION}"


def _viewer_html(glb: bytes) -> str:
    """Build a complete HTML document with the GLB encoded inline."""
    model = base64.b64encode(glb).decode("ascii")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Interactive 3D model exported from IngeTrazo">
  <title>IngeTrazo 3D model</title>
  <style>
    :root {{ color-scheme: dark; font: 14px system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    html, body {{ width: 100%; height: 100%; margin: 0; overflow: hidden; }}
    body {{ background: #171b22; color: #f2f4f8; }}
    #viewer {{ position: fixed; inset: 0; }}
    #toolbar {{
      position: fixed; z-index: 1; top: 12px; right: 12px;
      display: flex; gap: 8px;
    }}
    button {{
      border: 1px solid #697386; border-radius: 6px; padding: 8px 12px;
      background: #252c37; color: inherit; font: inherit; cursor: pointer;
    }}
    button:hover {{ background: #354052; }}
    #status {{
      position: fixed; z-index: 1; left: 50%; top: 50%;
      max-width: min(90vw, 640px); transform: translate(-50%, -50%);
      padding: 12px 16px; border-radius: 6px;
      background: #252c37; text-align: center;
    }}
    #disclosure {{
      position: fixed; left: 12px; bottom: 10px; color: #c4cbd6;
      text-shadow: 0 1px 3px #000; font-size: 12px;
    }}
  </style>
  <script type="importmap">
    {{
      "imports": {{
        "three": "{_THREE_CDN}/build/three.module.js",
        "three/addons/": "{_THREE_CDN}/examples/jsm/"
      }}
    }}
  </script>
</head>
<body>
  <div id="viewer" aria-label="Interactive 3D model"></div>
  <div id="toolbar">
    <button id="reset" type="button">Reset view</button>
    <button id="fullscreen" type="button">Fullscreen</button>
  </div>
  <div id="status" role="status">Loading model…</div>
  <div id="disclosure">Three.js { _THREE_VERSION } loads from jsDelivr; an internet connection is required.</div>
  <script id="glb-data" type="application/octet-stream">{model}</script>
  <script type="module">
    import * as THREE from "three";
    import {{ GLTFLoader }} from "three/addons/loaders/GLTFLoader.js";
    import {{ OrbitControls }} from "three/addons/controls/OrbitControls.js";

    const viewer = document.getElementById("viewer");
    const status = document.getElementById("status");
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x171b22);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000000);
    camera.up.set(0, 1, 0);

    let renderer;
    let controls;
    let homePosition;
    let homeTarget;

    function resetView() {{
      if (!homePosition || !homeTarget) return;
      camera.position.copy(homePosition);
      controls.target.copy(homeTarget);
      controls.update();
    }}

    function resize() {{
      if (!renderer) return;
      const width = viewer.clientWidth;
      const height = viewer.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    }}

    function showError(error) {{
      status.textContent = "Unable to display this model. Check the network connection, browser WebGL support, and browser console.";
      status.title = String(error);
      console.error("Standalone IngeTrazo viewer:", error);
    }}

    try {{
      renderer = new THREE.WebGLRenderer({{ antialias: true }});
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.setSize(viewer.clientWidth, viewer.clientHeight);
      viewer.appendChild(renderer.domElement);

      scene.add(new THREE.HemisphereLight(0xffffff, 0x667080, 2));
      const keyLight = new THREE.DirectionalLight(0xffffff, 2.5);
      keyLight.position.set(5, 8, 6);
      scene.add(keyLight);

      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;

      const encoded = document.getElementById("glb-data").textContent.trim();
      const binary = atob(encoded);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

      new GLTFLoader().parse(bytes.buffer, "", (gltf) => {{
        scene.add(gltf.scene);
        const bounds = new THREE.Box3().setFromObject(gltf.scene);
        const center = bounds.isEmpty()
          ? new THREE.Vector3()
          : bounds.getCenter(new THREE.Vector3());
        const sphere = bounds.isEmpty()
          ? {{ radius: 1 }}
          : bounds.getBoundingSphere(new THREE.Sphere());
        const radius = Math.max(sphere.radius, 0.001);
        const distance = radius * 1.7 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
        const direction = new THREE.Vector3(1, 0.8, 1).normalize();

        camera.position.copy(center).addScaledVector(direction, distance);
        camera.near = Math.max(radius / 10000, 0.00001);
        camera.far = Math.max(radius * 100, distance * 10);
        camera.updateProjectionMatrix();
        controls.target.copy(center);
        controls.minDistance = radius * 0.005;
        controls.maxDistance = radius * 100;
        controls.update();
        homePosition = camera.position.clone();
        homeTarget = controls.target.clone();
        status.hidden = true;
      }}, undefined, showError);

      document.getElementById("reset").addEventListener("click", resetView);
      document.getElementById("fullscreen").addEventListener("click", async () => {{
        try {{
          if (document.fullscreenElement) await document.exitFullscreen();
          else await document.documentElement.requestFullscreen();
        }} catch (error) {{
          status.hidden = false;
          status.textContent = "Fullscreen is unavailable in this browser.";
          status.title = String(error);
        }}
      }});
      document.addEventListener("fullscreenchange", () => {{
        document.getElementById("fullscreen").textContent =
          document.fullscreenElement ? "Exit fullscreen" : "Fullscreen";
        resize();
      }});
      window.addEventListener("resize", resize);
      renderer.setAnimationLoop(() => {{
        controls.update();
        renderer.render(scene, camera);
      }});
    }} catch (error) {{
      showError(error);
    }}
  </script>
</body>
</html>
"""


def setup(app) -> None:
    """Register the HTML export command in the Extensions menu."""
    def export_html() -> None:
        temporary_glb = None
        temporary_html = None
        try:
            path, _selected_filter = file_dialogs.getSaveFileName(
                app.window,
                "Export standalone 3D HTML",
                "model.html",
                "HTML files (*.html)",
            )
            if not path:
                return

            destination = Path(path)
            if destination.suffix.lower() != ".html":
                destination = destination.with_name(destination.name + ".html")

            with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
                temporary_glb = f.name
            save_glb(app.scene, temporary_glb)
            html = _viewer_html(Path(temporary_glb).read_bytes())

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                suffix=".tmp",
                dir=destination.parent,
                delete=False,
            ) as f:
                temporary_html = f.name
                f.write(html)
            os.replace(temporary_html, destination)
            temporary_html = None
        except Exception as exc:
            QMessageBox.critical(
                app.window,
                "Standalone HTML export failed",
                str(exc),
            )
        finally:
            for temporary_path in (temporary_glb, temporary_html):
                if temporary_path:
                    try:
                        os.unlink(temporary_path)
                    except FileNotFoundError:
                        pass

    app.add_menu_action(
        "Export standalone 3D HTML…",
        export_html,
        tip="Export the current scene as one HTML file with an interactive 3D viewer.",
    )
