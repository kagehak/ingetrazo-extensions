# ingetrazo-extensions
Extensions, plugins, and custom scripts for IngeTrazo — the open-source 3D CAD software for architecture and engineering.

## Extensions

- [Gridfinity Generator](gridfinity-generator/): generate editable Gridfinity
  bins and baseplates with custom footprints, dividers, and configurable scoop
  corners.
- [Standalone 3D HTML viewer](standalone-3d-html-viewer/): export a scene as
  one shareable HTML file with an interactive Three.js viewer. Model geometry,
  materials, and textures are embedded; the viewer runtime loads from a CDN.

## Developing and testing

See [`docs/developing-and-testing.md`](docs/developing-and-testing.md) for
the workflow: cloning the IngeTrazo app as a test runtime, linking an
extension from this repo into its plugins folder with
`scripts/dev-link.ps1`, and launching the app to try it out.
