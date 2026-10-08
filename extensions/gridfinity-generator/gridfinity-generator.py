# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Generate Gridfinity-compatible storage bins and socket baseplates.

Geometry helpers accept millimetres for readable design dimensions and convert
to the application's metre-based mesh coordinates at their boundaries. The
panel only gathers settings; the builders return detached Groups, and history
commands perform all scene mutations so creation and replacement are undoable.
"""
from __future__ import annotations

from math import atan2, cos, hypot, pi, sin, tan

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QMatrix4x4,
    QPainter,
    QPen,
    QPixmap,
    QVector3D,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from core.group import Group
from core.history import Command
from core.mesh import Mesh


_PITCH_MM = 42.0
_MODULE_MM = 41.5
_BODY_MM = 41.5
_BASE_HEIGHT_MM = 4.75
_UNIT_HEIGHT_MM = 7.0
_STACK_LIP_MM = 4.4
_ROUNDED_SEGMENTS = 12
_LIP_CLEARANCE_MM = 0.25
_LIP_TOP_LEDGE_MM = 0.4
_LIP_BOTTOM_CHAMFER_MM = 0.7
_LIP_VERTICAL_SECTION_MM = 1.8
_LIP_TOP_CHAMFER_MM = 2.15 - _LIP_CLEARANCE_MM - _LIP_TOP_LEDGE_MM
_PROFILE = (
    (35.6, 0.0),
    (37.2, 0.8),
    (37.2, 2.6),
    (41.5, 4.75),
)
_FOOT_TOP_CLEARANCE_MM = 0.3
_BASEPLATE_HEIGHT_MM = 5.7
_BASEPLATE_CHAMFER_MM = 0.7
_BASEPLATE_PROFILE_BOTTOM_CHAMFER_MM = 0.8
_BASEPLATE_PROFILE_TOP_CHAMFER_MM = 1.75
_BASEPLATE_TOP_LEDGE_MM = 0.4
_BASEPLATE_SOCKET_Z_OFFSET_MM = _BASEPLATE_HEIGHT_MM - _BASE_HEIGHT_MM
_MAGNET_BASEPLATE_SOCKET_HEIGHT_MM = 4.65
_BASEPLATE_DEFAULT_BASE_MM = (
    _BASEPLATE_HEIGHT_MM - _MAGNET_BASEPLATE_SOCKET_HEIGHT_MM
)
_MAGNET_BASEPLATE_SOCKET_LEVELS_MM = (0.0, 0.7, 2.5, 4.65)
_BASEPLATE_SOCKET_PROFILE = tuple(
    (size, round(z + _BASEPLATE_SOCKET_Z_OFFSET_MM, 2),
     round(7.75 - (_MODULE_MM - size) / 2, 2))
    for size, z in _PROFILE
)
_MAGNET_DIAMETER_DEFAULT_MM = 6.0
_MAGNET_DIAMETER_TOLERANCE_MM = 0.5
_MAGNET_HEIGHT_DEFAULT_MM = 2.0
_MAGNET_HEIGHT_TOLERANCE_MM = 0.5
_MAGNET_BASE_DEFAULT_MM = 2.0
_MAGNET_BASE_BORE_DIAMETER_MM = 3.0
_BASEPLATE_MAGNET_CHAMFER_DEFAULT_MM = 0.0
_BASEPLATE_MAGNET_BASE_BORE_MIN_MM = 0.0
_BASEPLATE_MAGNET_BASE_BORE_MAX_MM = 8.0
_BASEPLATE_MAGNET_BASE_CHAMFER_DEFAULT_MM = 0.0
_SCREW_HOLE_DEFAULT_DIAMETER_MM = 3.2
_SCREW_HOLE_MINIMUM_BELOW_MM = 1.0
_SCREW_HOLE_MINIMUM_ABOVE_MM = 0.5
_MAGNET_SUPPORT_WEB_MM = 1.2
_MAGNET_EDGE_OFFSET_MM = 8.0
_MAGNET_DIAMETER_MM = 6.5
_MAGNET_DEPTH_MM = 2.4
_BIN_MAGNET_DIAMETER_MIN_MM = 4.0
_BIN_MAGNET_DIAMETER_MAX_MM = 10.0
_BIN_MAGNET_DEPTH_MIN_MM = 1.0
_BIN_MAGNET_DEPTH_MAX_MM = 5.0
_BIN_CRUSH_RIBS_DEFAULT_COUNT = 12
_BIN_CRUSH_RIBS_DEFAULT_WAVINESS = 0.5
_BIN_RECESSED_TOP_MAX_MM = 10.0
_BIN_INSIDE_FILLET_DEFAULT_MM = 1.85
_BIN_DIVIDER_THICKNESS_DEFAULT_MM = 1.2
_BIN_DIVIDER_THICKNESS_MIN_MM = 0.6
_BIN_DIVIDER_THICKNESS_MAX_MM = 3.0
_BIN_SCOOP_RADIUS_DEFAULT_MM = 21.0
_LABEL_SHELF_WIDTH_DEFAULT_MM = 12.0
_LABEL_SHELF_LENGTH_DEFAULT_MM = 42.0
_LABEL_SHELF_ANGLE_DEFAULT_DEGREES = 45.0
_LABEL_SHELF_THICKNESS_DEFAULT_MM = 2.0
_SCREW_DIAMETER_MM = 3.0
_SCREW_DEPTH_MM = 6.0


class _CreateGridfinityCommand(Command):
    """Insert or replace a generated group and persist its editable settings."""

    _DATA_KEY = "gridfinity_generator"
    _PARAMETERS_SCHEMA = 3

    def __init__(self, group: Group, parameters: dict,
                 old_group: Group | None = None) -> None:
        """Capture immutable command inputs; snapshot scene state on first run."""
        import json

        self.group = group
        self.parameters = json.loads(json.dumps(parameters))
        self.old_group = old_group
        self._before_groups = None
        self._before_selection = None
        self._before_data = None
        self._after_data = None

    def do(self, scene) -> None:
        """Install the group and its document-persisted parameter record."""
        import json

        if self._before_groups is None:
            self._before_groups = list(scene.groups)
            self._before_selection = set(scene.selection)
            self._before_data = json.loads(json.dumps(scene.plugin_data))
            plugin_state = self._before_data.get(self._DATA_KEY, {})
            if not isinstance(plugin_state, dict):
                plugin_state = {}
            else:
                plugin_state = dict(plugin_state)
            models = plugin_state.get("models", {})
            if not isinstance(models, dict):
                models = {}
            models = dict(models)
            if self.old_group is not None:
                models.pop(self.old_group.uid, None)
            models[self.group.uid] = self.parameters
            plugin_state["models"] = models
            self._after_data = dict(self._before_data)
            self._after_data[self._DATA_KEY] = plugin_state

        if self.old_group is not None:
            if self.old_group not in scene.groups:
                raise ValueError("The selected Gridfinity model is no longer in the scene.")
            scene.groups.remove(self.old_group)
        scene.groups.append(self.group)
        scene.plugin_data = json.loads(json.dumps(self._after_data))
        scene.selection.clear()
        scene.selection.add(self.group)
        scene.version += 1

    def undo(self, scene) -> None:
        """Restore the former groups, selection, and plugin metadata."""
        import json

        scene.groups = list(self._before_groups or ())
        scene.selection = set(self._before_selection or ())
        scene.plugin_data = json.loads(json.dumps(self._before_data or {}))
        scene.version += 1


def _rounded_rect(cx: float, cy: float, width: float, depth: float,
                  radius: float, z: float) -> list:
    """Return a counter-clockwise rounded rectangle as metre-space points."""
    hx, hy = width / 2000.0, depth / 2000.0
    r = radius / 1000.0
    if r == 0:
        return [
            QVector3D(cx / 1000.0 - hx, cy / 1000.0 - hy, z / 1000.0),
            QVector3D(cx / 1000.0 + hx, cy / 1000.0 - hy, z / 1000.0),
            QVector3D(cx / 1000.0 + hx, cy / 1000.0 + hy, z / 1000.0),
            QVector3D(cx / 1000.0 - hx, cy / 1000.0 + hy, z / 1000.0),
        ]
    corners = (
        (cx / 1000.0 + hx - r, cy / 1000.0 - hy + r, -pi / 2),
        (cx / 1000.0 + hx - r, cy / 1000.0 + hy - r, 0),
        (cx / 1000.0 - hx + r, cy / 1000.0 + hy - r, pi / 2),
        (cx / 1000.0 - hx + r, cy / 1000.0 - hy + r, pi),
    )
    points = []
    for x, y, start in corners:
        for i in range(_ROUNDED_SEGMENTS + 1):
            angle = start + (pi / 2) * i / _ROUNDED_SEGMENTS
            points.append(QVector3D(x + r * cos(angle),
                                    y + r * sin(angle), z / 1000.0))
    return points


def _grid_centres(nx: int, ny: int, centered: bool) -> list[tuple[float, float]]:
    """Return cell centers in millimetres, optionally around the origin."""
    offset_x = nx * _PITCH_MM / 2 if centered else 0.0
    offset_y = ny * _PITCH_MM / 2 if centered else 0.0
    return [
        ((x + 0.5) * _PITCH_MM - offset_x,
         (y + 0.5) * _PITCH_MM - offset_y)
        for y in range(ny)
        for x in range(nx)
    ]


def _normalize_grid_layout(
        nx: int, ny: int, layout: list[list[bool]] | None
        ) -> list[list[bool]]:
    """Validate a row-major layout and ensure at least one cell is active."""
    if layout is None:
        return [[True] * nx for _ in range(ny)]
    if (len(layout) != ny
            or any(len(row) != nx for row in layout)
            or not any(any(row) for row in layout)):
        raise ValueError(
            "Custom layout must match the grid size and contain an active cell.")
    if any(not isinstance(cell, bool) for row in layout for cell in row):
        raise ValueError("Custom layout cells must be true or false.")
    return [list(row) for row in layout]


def _layout_cutters(layout: list[list[bool]], pitch_mm: float,
                    z_min_mm: float, z_max_mm: float,
                    centered: bool) -> list[Group]:
    """Make box cutters for inactive cells in a row-major cell layout."""
    ny, nx = len(layout), len(layout[0])
    centers = _grid_centres(nx, ny, centered)
    cutters = []
    for y, row in enumerate(layout):
        for x, active in enumerate(row):
            if active:
                continue
            cx, cy = centers[y * nx + x]
            half_pitch = pitch_mm / 2000
            cutters.append(Group(
                _box_mesh(
                    cx / 1000 - half_pitch,
                    cy / 1000 - half_pitch,
                    z_min_mm / 1000,
                    cx / 1000 + half_pitch,
                    cy / 1000 + half_pitch,
                    z_max_mm / 1000),
                name="Empty layout cell"))
    return cutters


def _circle(cx: float, cy: float, diameter: float, z: float,
            segments: int = 32) -> list:
    """Return a circular contour in metre-space coordinates."""
    return [
        QVector3D(
            (cx + diameter / 2 * cos(2 * pi * i / segments)) / 1000.0,
            (cy + diameter / 2 * sin(2 * pi * i / segments)) / 1000.0,
            z / 1000.0)
        for i in range(segments)
    ]


def _add_sides(mesh: Mesh, lower: list, upper: list, reverse: bool = False):
    """Connect matching polygon rings with quad faces."""
    for i, a in enumerate(lower):
        j = (i + 1) % len(lower)
        face = [a, lower[j], upper[j], upper[i]]
        mesh.add_face(list(reversed(face)) if reverse else face)


def _add_rounded_sides(mesh: Mesh, lower: list, upper: list,
                       reverse: bool = False) -> None:
    """Connect rounded-rectangle rings and mark their corner edges soft."""
    _add_sides(mesh, lower, upper, reverse)
    if len(lower) != (_ROUNDED_SEGMENTS + 1) * 4:
        return
    points_per_corner = _ROUNDED_SEGMENTS + 1
    for corner in range(4):
        start = corner * points_per_corner
        for index in range(start, start + points_per_corner):
            edge = mesh.find_edge(
                mesh.vertex(lower[index]), mesh.vertex(upper[index]))
            if edge is not None:
                edge.soft = True


def _stacking_lip_sections(inner_width: float, inner_depth: float,
                           inner_radius: float, wall_mm: float,
                           body_top_z: float) -> list[list]:
    """Build the rounded inside profile from the documented lip section."""
    x1 = _LIP_CLEARANCE_MM
    x2 = x1 + _LIP_TOP_LEDGE_MM
    x3 = x2 + _LIP_TOP_CHAMFER_MM
    x4 = x3 + _LIP_BOTTOM_CHAMFER_MM
    x5 = x1 + wall_mm
    z_start = (body_top_z - _LIP_VERTICAL_SECTION_MM
               - _LIP_TOP_LEDGE_MM - _LIP_TOP_CHAMFER_MM
               - _LIP_BOTTOM_CHAMFER_MM + wall_mm)
    sections = (
        (z_start, x5),
        (body_top_z - _LIP_VERTICAL_SECTION_MM, x4),
        (body_top_z, x4),
        (body_top_z + _LIP_BOTTOM_CHAMFER_MM, x3),
        (body_top_z + _LIP_BOTTOM_CHAMFER_MM + _LIP_VERTICAL_SECTION_MM, x3),
        (body_top_z + _LIP_BOTTOM_CHAMFER_MM + _LIP_VERTICAL_SECTION_MM
         + _LIP_TOP_CHAMFER_MM, x2),
        (body_top_z + _STACK_LIP_MM, x2),
    )
    if z_start >= body_top_z - _LIP_VERTICAL_SECTION_MM:
        raise ValueError(
            "Wall thickness must be below 2.6 mm for the standard stacking lip.")
    loops = []
    for z, offset_from_outer in sections:
        radial_offset = x5 - offset_from_outer
        section_width = inner_width + 2 * radial_offset
        section_depth = inner_depth + 2 * radial_offset
        radius = inner_radius + radial_offset
        if (section_width <= 2 * radius or section_depth <= 2 * radius
                or radius <= 0):
            raise ValueError("The bin dimensions leave no usable stacking lip.")
        loops.append(_rounded_rect(
            0, 0, section_width, section_depth, radius, z))
    return loops


def _arc_points(start: tuple[float, float], through: tuple[float, float],
                end: tuple[float, float],
                segments: int = 8) -> list[tuple[float, float]]:
    """Sample a circular arc through three points, excluding its start."""
    ax, ay = start
    bx, by = through
    cx, cy = end
    determinant = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(determinant) < 1e-9:
        return [
            (ax + (cx - ax) * step / segments,
             ay + (cy - ay) * step / segments)
            for step in range(1, segments + 1)
        ]
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    center_x = (a2 * (by - cy) + b2 * (cy - ay)
                + c2 * (ay - by)) / determinant
    center_y = (a2 * (cx - bx) + b2 * (ax - cx)
                + c2 * (bx - ax)) / determinant
    start_angle = atan2(ay - center_y, ax - center_x)
    through_angle = atan2(by - center_y, bx - center_x)
    end_angle = atan2(cy - center_y, cx - center_x)
    ccw_sweep = (end_angle - start_angle) % (2 * pi)
    ccw_through = (through_angle - start_angle) % (2 * pi)
    sweep = ccw_sweep if ccw_through <= ccw_sweep else ccw_sweep - 2 * pi
    radius = hypot(ax - center_x, ay - center_y)
    return [
        (center_x + radius * cos(start_angle + sweep * step / segments),
         center_y + radius * sin(start_angle + sweep * step / segments))
        for step in range(1, segments + 1)
    ]


def _magnet_grid_opening(cx: float, cy: float, grid_width: float,
                         grid_depth: float, magnet_diameter: float,
                         z: float) -> list:
    """Profile the central through-opening around four reinforced magnet pads."""
    half_x, half_y = grid_width / 2, grid_depth / 2
    frame = (_BASEPLATE_PROFILE_TOP_CHAMFER_MM
             + _BASEPLATE_PROFILE_BOTTOM_CHAMFER_MM
             + _BASEPLATE_TOP_LEDGE_MM)
    x_frame, y_frame = half_x - frame, half_y - frame
    magnet_radius = magnet_diameter / 2
    x_magnet_edge = (
        half_x - _MAGNET_EDGE_OFFSET_MM - magnet_radius
        - _MAGNET_SUPPORT_WEB_MM)
    y_magnet_edge = (
        half_y - _MAGNET_EDGE_OFFSET_MM - magnet_radius
        - _MAGNET_SUPPORT_WEB_MM)
    magnet_center_x = _PITCH_MM / 2 - _MAGNET_EDGE_OFFSET_MM
    magnet_center_y = magnet_center_x
    fillet = 1.0
    x_frame_fillet, y_frame_fillet = x_frame - fillet, y_frame - fillet
    x_magnet_fillet = x_magnet_edge - fillet
    y_magnet_fillet = y_magnet_edge - fillet
    magnet_outer_radius = magnet_radius + _MAGNET_SUPPORT_WEB_MM
    magnet_mid = _PITCH_MM / 2 - _MAGNET_EDGE_OFFSET_MM - (
        magnet_outer_radius * sin(pi / 4))

    p1 = (0.0, -y_frame)
    p2 = (-x_magnet_fillet, -y_frame)
    p3 = (-x_magnet_edge, -y_frame_fillet)
    p4 = (-x_magnet_edge, -magnet_center_y)
    p5 = (-magnet_center_x, -y_magnet_edge)
    p6 = (-x_frame_fillet, -y_magnet_edge)
    p7 = (-x_frame, -y_magnet_fillet)
    p8 = (-x_frame, 0.0)
    arc1_mid = (
        -x_magnet_fillet - fillet * sin(pi / 4),
        -y_frame_fillet - fillet * sin(pi / 4))
    arc2_mid = (-magnet_mid, -magnet_mid)
    arc3_mid = (
        -x_frame_fillet - fillet * sin(pi / 4),
        -y_magnet_fillet - fillet * sin(pi / 4))

    quarter = [p1, p2]
    quarter.extend(_arc_points(p2, arc1_mid, p3))
    quarter.append(p4)
    quarter.extend(_arc_points(p4, arc2_mid, p5))
    quarter.append(p6)
    quarter.extend(_arc_points(p6, arc3_mid, p7))
    quarter.append(p8)

    loop = []
    for rotation in range(4):
        angle = -rotation * pi / 2
        cos_a, sin_a = cos(angle), sin(angle)
        points = quarter if rotation == 0 else (
            quarter[1:-1] if rotation == 3 else quarter[1:])
        loop.extend(QVector3D(
            (cx + x * cos_a - y * sin_a) / 1000.0,
            (cy + x * sin_a + y * cos_a) / 1000.0,
            z / 1000.0) for x, y in points)
    return loop


def _place_group(group: Group, dx: float, dy: float) -> Group:
    """Translate a generated group in metres and mark it as an instance."""
    if dx or dy:
        group.xform = QMatrix4x4()
        group.xform.translate(dx, dy, 0.0)
        group.component = False
    return group


def _box_mesh(x0: float, y0: float, z0: float,
              x1: float, y1: float, z1: float) -> Mesh:
    """Create a closed axis-aligned box from metre-space bounds."""
    mesh = Mesh()
    lo = (x0, y0, z0)
    hi = (x1, y1, z1)
    corners = [
        QVector3D(x, y, z)
        for x, y, z in (
            (lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]),
            (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
            (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]),
            (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2]),
        )
    ]
    for indices in (
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (1, 2, 6, 5),
        (2, 3, 7, 6), (3, 0, 4, 7),
    ):
        mesh.add_face([corners[i] for i in indices])
    return mesh


def _loft_solid(sections: list[list]) -> Mesh:
    """Create a watertight solid by joining equal-vertex-count profile rings."""
    if len(sections) < 2 or any(
            len(section) != len(sections[0]) for section in sections):
        raise ValueError("Loft profiles must have matching vertex counts.")
    mesh = Mesh()
    mesh.add_face(list(reversed(sections[0])))
    mesh.add_face(sections[-1])
    for lower, upper in zip(sections, sections[1:]):
        _add_rounded_sides(mesh, lower, upper)
    return mesh


def _cylinder_mesh(start: tuple[float, float, float],
                   end: tuple[float, float, float],
                   diameter: float, segments: int = 32) -> Mesh:
    """Make a closed cylinder between two points (coordinates in metres)."""
    axis = QVector3D(*(end[i] - start[i] for i in range(3)))
    if axis.length() <= 1e-12 or diameter <= 0:
        raise ValueError("Cylinder dimensions must be positive.")
    axis.normalize()
    reference = QVector3D(0, 0, 1)
    if abs(QVector3D.dotProduct(axis, reference)) > 0.95:
        reference = QVector3D(0, 1, 0)
    u = QVector3D.crossProduct(axis, reference)
    u.normalize()
    v = QVector3D.crossProduct(axis, u)
    radius = diameter / 2

    def ring(center):
        """Generate one circular ring perpendicular to the cylinder axis."""
        return [
            QVector3D(*center) + radius * (
                u * cos(2 * pi * i / segments)
                + v * sin(2 * pi * i / segments))
            for i in range(segments)
        ]

    lower, upper = ring(start), ring(end)
    mesh = Mesh()
    mesh.add_face(list(reversed(lower)))
    mesh.add_face(upper)
    for i, point in enumerate(lower):
        following = (i + 1) % segments
        mesh.add_face([point, lower[following],
                       upper[following], upper[i]])
    return mesh


def _mesh_to_manifold(mesh: Mesh):
    """Convert triangulated faces to a consistently oriented Manifold solid."""
    import manifold3d as m3d
    import numpy as np

    index = {}
    vertices = []
    triangles = []

    def vertex_id(point):
        """Reuse a mesh vertex index for an identical point."""
        key = (point.x(), point.y(), point.z())
        if key not in index:
            index[key] = len(vertices)
            vertices.append(key)
        return index[key]

    for face in mesh.faces:
        for triangle in face.triangulate(face.normal()):
            triangles.append(tuple(vertex_id(point) for point in triangle))
    vertex_array = np.asarray(vertices, dtype=np.float64)
    triangle_array = np.asarray(triangles, dtype=np.uint32)
    a, b, c = vertex_array[triangle_array[:, 0]], \
        vertex_array[triangle_array[:, 1]], vertex_array[triangle_array[:, 2]]
    if np.einsum("ij,ij->i", a, np.cross(b, c)).sum() < 0:
        triangle_array = triangle_array[:, ::-1].copy()
    result = m3d.Manifold(m3d.Mesh64(
        vert_properties=vertex_array,
        tri_verts=triangle_array,
        face_id=np.zeros(len(triangle_array), dtype=np.uint32)))
    if result.status() != m3d.Error.NoError:
        raise ValueError("The Gridfinity cutter or target is not manifold.")
    return result


def _manifold_to_mesh(manifold) -> Mesh:
    """Convert a Manifold result into an IngeTrazo mesh."""
    import numpy as np

    result_mesh = manifold.to_mesh64()
    positions = np.asarray(
        result_mesh.vert_properties, dtype=np.float64)[:, :3]
    mesh = Mesh()
    for triangle in np.asarray(result_mesh.tri_verts, dtype=np.int64):
        mesh.add_face([
            QVector3D(*(float(value) for value in positions[index]))
            for index in triangle
        ])
    return mesh


def _subtract_cutters(target: Group, cutters: list[Group]) -> Group:
    """Subtract closed cutter groups and convert the manifold result to Mesh."""
    if not cutters:
        return target
    import manifold3d as m3d

    target_manifold = _mesh_to_manifold(target.mesh)
    cutter_manifolds = [_mesh_to_manifold(group.mesh) for group in cutters]
    cutter = m3d.Manifold.batch_boolean(cutter_manifolds, m3d.OpType.Add)
    result = target_manifold - cutter
    if result.status() != m3d.Error.NoError or result.is_empty():
        raise ValueError("The requested Gridfinity cut could not be generated.")
    # Weld coincident boolean output vertices, then simplify exact coplanars.
    result = _mesh_to_manifold(_manifold_to_mesh(result)).simplify(1e-5)
    mesh = _manifold_to_mesh(result)
    for edge in mesh.edges:
        if len(edge.faces) == 2:
            first, second = edge.faces
            if QVector3D.dotProduct(first.normal(), second.normal()) > 0.965:
                edge.soft = True
    return Group(mesh, name=target.name)


def _clip_scoop_to_inner_wall(
        scoop: Group, inner_width: float, inner_depth: float,
        inner_radius: float, floor_z: float,
        body_top_z: float, scoop_center_y: float) -> Group:
    """Trim a scoop to the cavity footprint so its ends follow rounded corners."""
    import manifold3d as m3d

    clipping_prism = _loft_solid([
        _rounded_rect(
            0, -scoop_center_y, inner_width, inner_depth,
            inner_radius, floor_z - 0.01),
        _rounded_rect(
            0, -scoop_center_y, inner_width, inner_depth,
            inner_radius, body_top_z + 0.01),
    ])
    result = m3d.Manifold.batch_boolean(
        [_mesh_to_manifold(scoop.mesh),
         _mesh_to_manifold(clipping_prism)],
        m3d.OpType.Intersect)
    if result.status() != m3d.Error.NoError or result.is_empty():
        raise ValueError("The finger scoop does not intersect the bin interior.")
    clipped = Group(_manifold_to_mesh(result), name=scoop.name)
    clipped.xform = scoop.xform
    clipped.component = False
    return clipped


def _bin_magnet_loop(cx_hole: float, cy_hole: float,
                     magnet_shape: str,
                     magnet_diameter_mm: float,
                     crush_ribs_count: int = _BIN_CRUSH_RIBS_DEFAULT_COUNT,
                     crush_ribs_waviness: float =
                     _BIN_CRUSH_RIBS_DEFAULT_WAVINESS) -> list[QVector3D]:
    """Build the bin-bottom magnet contour in world millimetres."""
    if magnet_shape == "round":
        return _circle(cx_hole, cy_hole, magnet_diameter_mm, 0.0)
    if magnet_shape == "crush_ribs":
        # Match the workbench's two-arc crush-rib profile with a sampled
        # radial wave. Its exact radial limits come from the arc geometry.
        alpha = pi / (2 * crush_ribs_count)
        beta = crush_ribs_waviness * pi / 2

        def midpoint_ratio(angle: float) -> float:
            if abs(angle) < 1e-12:
                return 1.0
            if abs(angle - alpha) < 1e-10:
                return cos(alpha)
            return (sin(angle) - sin(alpha)) / sin(angle - alpha)

        radius = magnet_diameter_mm / 2
        outer_arc_radius = radius / midpoint_ratio(beta)
        maximum_radius = outer_arc_radius * midpoint_ratio(-beta)
        minimum_radius = radius
        sample_count = crush_ribs_count * 8
        points = []
        for index in range(sample_count):
            angle = 2 * pi * index / sample_count
            radial_radius = (
                (minimum_radius + maximum_radius) / 2
                + (maximum_radius - minimum_radius) / 2
                * cos(crush_ribs_count * angle))
            points.append(QVector3D(
                (cx_hole + radial_radius * cos(angle)) / 1000.0,
                (cy_hole + radial_radius * sin(angle)) / 1000.0,
                0.0))
        return points
    return [
        QVector3D(
            (cx_hole + magnet_diameter_mm / 2
             * cos(2 * pi * (index + 0.5) / 6)) / 1000.0,
            (cy_hole + magnet_diameter_mm / 2
             * sin(2 * pi * (index + 0.5) / 6)) / 1000.0,
            0.0)
        for index in range(6)
    ]


def _build_bin_foot(mesh: Mesh, cx: float, cy: float, bottom: str,
                    magnet_shape: str,
                    magnet_diameter_mm: float,
                    crush_ribs_count: int,
                    crush_ribs_waviness: float) -> list[QVector3D]:
    """Add one standardized Gridfinity foot, returning its top and open holes."""
    outer_radius = 7.75
    profile_loops = []
    for profile_size, z in _PROFILE:
        size = profile_size
        if z == _BASE_HEIGHT_MM:
            # Preserve a small seam gap larger than the mesh's vertex weld
            # tolerance so adjoining foot and body surfaces stay manifold.
            size -= _FOOT_TOP_CLEARANCE_MM
        radius = outer_radius - (_MODULE_MM - size) / 2
        profile_loops.append(
            _rounded_rect(cx, cy, size, size, radius, z))

    foot_holes = []
    if bottom in {"magnet", "magnet_open", "screw_magnet"}:
        foot_holes.extend(
            _bin_magnet_loop(
                cx + dx, cy + dy, magnet_shape, magnet_diameter_mm,
                crush_ribs_count, crush_ribs_waviness)
            for dx in (-13.0, 13.0)
            for dy in (-13.0, 13.0))
    elif bottom == "screw":
        foot_holes.extend(
            _circle(cx + dx, cy + dy, _SCREW_DIAMETER_MM, 0.0)
            for dx in (-13.0, 13.0)
            for dy in (-13.0, 13.0))

    mesh.add_face(list(reversed(profile_loops[0])), foot_holes)
    for lower, upper in zip(profile_loops, profile_loops[1:]):
        _add_rounded_sides(mesh, lower, upper)
    return profile_loops[-1]


def _add_bin_bottom_pockets(
        mesh: Mesh, cx: float, cy: float, bottom: str,
        floor_z: float, magnet_shape: str,
        magnet_diameter_mm: float, magnet_depth_mm: float,
        open_magnet_floor_loops: list[list[QVector3D]],
        crush_ribs_count: int = _BIN_CRUSH_RIBS_DEFAULT_COUNT,
        crush_ribs_waviness: float =
        _BIN_CRUSH_RIBS_DEFAULT_WAVINESS) -> None:
    """Add magnet/screw recesses to one foot and collect open-floor loops."""
    for dx in (-13.0, 13.0):
        for dy in (-13.0, 13.0):
            cx_hole, cy_hole = cx + dx, cy + dy
            if bottom in {"magnet", "magnet_open", "screw_magnet"}:
                magnet_contour = _bin_magnet_loop(
                    cx_hole, cy_hole, magnet_shape, magnet_diameter_mm,
                    crush_ribs_count, crush_ribs_waviness)
                counterbore_bottom = [
                    QVector3D(point.x(), point.y(), magnet_depth_mm / 1000)
                    for point in magnet_contour
                ]
                _add_sides(
                    mesh,
                    magnet_contour,
                    counterbore_bottom,
                    reverse=True)
                if bottom == "magnet_open":
                    floor_opening = [
                        QVector3D(
                            point.x(), point.y(), floor_z / 1000)
                        for point in magnet_contour
                    ]
                    _add_sides(
                        mesh, counterbore_bottom, floor_opening, reverse=True)
                    open_magnet_floor_loops.append(
                        list(reversed(floor_opening)))
                elif bottom == "screw_magnet":
                    screw_opening = _circle(
                        cx_hole, cy_hole, _SCREW_DIAMETER_MM,
                        magnet_depth_mm,
                        segments=len(counterbore_bottom))
                    screw_exit = _circle(
                        cx_hole, cy_hole, _SCREW_DIAMETER_MM,
                        _SCREW_DEPTH_MM, segments=len(counterbore_bottom))
                    mesh.add_face(
                        counterbore_bottom, [list(reversed(screw_opening))])
                    _add_sides(
                        mesh, screw_opening, screw_exit, reverse=True)
                    mesh.add_face(screw_exit)
                else:
                    mesh.add_face(counterbore_bottom)
            elif bottom == "screw":
                screw_exit = _circle(
                    cx_hole, cy_hole, _SCREW_DIAMETER_MM, _SCREW_DEPTH_MM)
                _add_sides(
                    mesh,
                    _circle(cx_hole, cy_hole, _SCREW_DIAMETER_MM, 0.0),
                    screw_exit,
                    reverse=True)
                mesh.add_face(screw_exit)


def _add_bin_interior(mesh: Mesh, outer_top: list[QVector3D],
                      inner_floor: list[QVector3D],
                      open_magnet_floor_loops: list[list[QVector3D]],
                      inner_width: float, inner_depth: float,
                      inner_radius: float, wall_mm: float,
                      floor_z: float, body_top_z: float,
                      stackable: bool,
                      inside_fillet_mm: float = 0.0) -> None:
    """Close the bin cavity with either a documented lip or a plain rim."""
    floor_sections = [inner_floor]
    if inside_fillet_mm > 0:
        floor_sections = []
        for step in range(9):
            angle = pi / 2 * step / 8
            inset = inside_fillet_mm * (1 - cos(angle))
            floor_sections.append(_rounded_rect(
                0, 0,
                inner_width - 2 * inside_fillet_mm + 2 * inset,
                inner_depth - 2 * inside_fillet_mm + 2 * inset,
                inner_radius - inside_fillet_mm + inset,
                floor_z + inside_fillet_mm * sin(angle)))
        mesh.add_face(floor_sections[0], open_magnet_floor_loops or None)
        for lower, upper in zip(floor_sections, floor_sections[1:]):
            _add_rounded_sides(mesh, lower, upper, reverse=True)

    cavity_floor = floor_sections[-1]
    if stackable:
        lip_sections = _stacking_lip_sections(
            inner_width, inner_depth, inner_radius, wall_mm, body_top_z)
        first_above_floor = next(
            (index for index, loop in enumerate(lip_sections)
             if loop[0].z() * 1000 > floor_z + 1e-5),
            len(lip_sections))
        if first_above_floor == len(lip_sections):
            raise ValueError("The bin floor overlaps the stacking lip.")
        active_sections = [cavity_floor, *lip_sections[first_above_floor:]]
        if inside_fillet_mm == 0:
            mesh.add_face(inner_floor, open_magnet_floor_loops or None)
        for lower, upper in zip(active_sections, active_sections[1:]):
            _add_rounded_sides(mesh, lower, upper, reverse=True)
        mesh.add_face(outer_top, [list(reversed(active_sections[-1]))])
        return

    cavity_top = _rounded_rect(
        0, 0, inner_width, inner_depth, inner_radius, body_top_z)
    _add_rounded_sides(mesh, cavity_floor, cavity_top, reverse=True)
    mesh.add_face(outer_top, [list(reversed(cavity_top))])
    if inside_fillet_mm == 0:
        mesh.add_face(inner_floor, open_magnet_floor_loops or None)


def _build_bin_dividers(inner_width: float, inner_depth: float,
                        wall_mm: float, floor_z: float,
                        divider_x_height: float, divider_y_height: float,
                        divider_x: int, divider_y: int,
                        divider_thickness_mm: float) -> list[Group]:
    """Build detachable X/Y divider solids in the bin's local coordinates."""
    dividers = []
    inner_x, inner_y = inner_width / 1000, inner_depth / 1000
    wall = max(0.0006, divider_thickness_mm / 1000)
    z0 = floor_z / 1000
    x_z1 = z0 + divider_x_height / 1000
    y_z1 = z0 + divider_y_height / 1000
    for index in range(1, divider_x + 1):
        x = -inner_x / 2 + inner_x * index / (divider_x + 1)
        dividers.append(Group(
            _box_mesh(x - wall / 2, -inner_y / 2, z0,
                      x + wall / 2, inner_y / 2, x_z1),
            name=f"Divider X{index}"))
    for index in range(1, divider_y + 1):
        y = -inner_y / 2 + inner_y * index / (divider_y + 1)
        dividers.append(Group(
            _box_mesh(-inner_x / 2, y - wall / 2, z0,
                      inner_x / 2, y + wall / 2, y_z1),
            name=f"Divider Y{index}"))
    for divider in dividers:
        divider.xform = QMatrix4x4()
        divider.component = False
    return dividers


def _extruded_xz_profile(
        points: list[tuple[float, float]], length_mm: float) -> Mesh:
    """Extrude a counter-clockwise X/Z polygon along the Y axis."""
    half_length = length_mm / 2000
    front = [
        QVector3D(x / 1000, -half_length, z / 1000)
        for x, z in points
    ]
    back = [
        QVector3D(x / 1000, half_length, z / 1000)
        for x, z in points
    ]
    mesh = Mesh()
    mesh.add_face(list(reversed(front)))
    mesh.add_face(back)
    for index, point in enumerate(front):
        following = (index + 1) % len(front)
        mesh.add_face([
            point, front[following], back[following], back[index]])
    return mesh


def _build_bin_scoops(
        inner_width: float, inner_depth: float, inner_radius: float,
        floor_z: float, body_top_z: float,
        radius_mm: float, layout: list[list[bool]],
        corner_style: str = "rounded") -> list[Group]:
    """Build quarter-round finger-scoop solids along active right-hand edges."""
    ny, nx = len(layout), len(layout[0])
    effective_radius = min(
        radius_mm, inner_width / 2 - 0.1, body_top_z - floor_z)
    if effective_radius <= 0:
        raise ValueError("The selected bin dimensions leave no room for a scoop.")
    inner_edge_x = inner_width / 2
    groups = []
    row = 0
    while row < ny:
        if not layout[row][nx - 1]:
            row += 1
            continue
        start_row = row
        while row + 1 < ny and layout[row + 1][nx - 1]:
            row += 1
        end_row = row
        run_start = (start_row - ny / 2) * _PITCH_MM + 0.25
        run_end = ((end_row + 1 - ny / 2) * _PITCH_MM - 0.25)
        if corner_style == "straight":
            # Keep the legacy square-ended scoop clear of the rounded corners.
            y_limit = inner_depth / 2 - inner_radius
            run_start = max(run_start, -y_limit)
            run_end = min(run_end, y_limit)
        length = run_end - run_start
        if length <= 0:
            row += 1
            continue
        center_y = (run_start + run_end) / 2
        start = (inner_edge_x, floor_z + effective_radius)
        bottom_at_wall = (inner_edge_x, floor_z)
        floor_tangent = (inner_edge_x - effective_radius, floor_z)
        arc_middle = (
            inner_edge_x - effective_radius
            + effective_radius * sin(pi / 4),
            floor_z + effective_radius
            - effective_radius * sin(pi / 4))
        profile = [
            start,
            bottom_at_wall,
            floor_tangent,
            *_arc_points(
                floor_tangent, arc_middle, start, segments=12),
        ]
        scoop = Group(
            _extruded_xz_profile(profile, length),
            name=f"Finger Scoop Y{start_row + 1}-{end_row + 1}")
        scoop.xform = QMatrix4x4()
        scoop.component = False
        scoop.xform.translate(0, center_y / 1000, 0)
        if corner_style == "rounded":
            scoop = _clip_scoop_to_inner_wall(
                scoop, inner_width, inner_depth, inner_radius,
                floor_z, body_top_z, center_y)
        groups.append(scoop)
        row += 1
    return groups


def _build_label_shelves(
        inner_width: float, floor_z: float, body_top_z: float,
        wall_mm: float, stacking: bool, label_style: str,
        placement: str, width_mm: float, length_mm: float,
        angle_degrees: float, thickness_mm: float,
        layout: list[list[bool]]) -> list[Group]:
    """Build label ledges on contiguous active sections of the bin's right wall."""
    ny, nx = len(layout), len(layout[0])
    groups = []
    row = 0
    while row < ny:
        if not layout[row][nx - 1]:
            row += 1
            continue
        start_row = row
        while row + 1 < ny and layout[row + 1][nx - 1]:
            row += 1
        end_row = row
        run_length = (end_row - start_row + 1) * _PITCH_MM - 0.5
        shelf_length = min(length_mm, run_length)
        shelf_placement = placement
        shelf_angle = angle_degrees
        if label_style == "overhang":
            shelf_length = run_length
            shelf_placement = "full"
            shelf_angle = 0.0
        elif shelf_length >= run_length - 1e-6:
            shelf_placement = "full"

        run_start = (start_row - ny / 2) * _PITCH_MM + 0.25
        if shelf_placement == "center":
            y_center = run_start + run_length / 2
        elif shelf_placement == "right":
            y_center = run_start + run_length - shelf_length / 2
        else:
            y_center = run_start + shelf_length / 2

        edge_x = inner_width / 2 + min(0.2, wall_mm / 2)
        top_z = body_top_z - (_LIP_TOP_LEDGE_MM if stacking else 0.0)
        shelf_drop = tan(shelf_angle * pi / 180) * width_mm
        outer = (edge_x - width_mm, top_z - shelf_drop)
        profile = [
            (edge_x, top_z),
            outer,
            (outer[0], outer[1] - thickness_mm),
            (edge_x, top_z - thickness_mm),
        ]
        shelf = Group(
            _extruded_xz_profile(list(reversed(profile)), shelf_length),
            name=f"Label Shelf Y{start_row + 1}-{end_row + 1}")
        shelf.xform = QMatrix4x4()
        shelf.xform.translate(0, y_center / 1000, 0)
        shelf.component = False
        groups.append(shelf)
        row += 1
    return groups


def _build_bin(nx: int, ny: int, height_units: int,
               wall_mm: float, kind: str = "storage",
               bottom: str = "screw_magnet",
               stackable: bool = True, divider_x: int = 0,
               divider_y: int = 0, divider_height_mm: float | None = None,
               divider_x_height_mm: float | None = None,
               divider_y_height_mm: float | None = None,
               magnet_shape: str = "round",
               magnet_diameter_mm: float = _MAGNET_DIAMETER_MM,
               magnet_depth_mm: float = _MAGNET_DEPTH_MM,
               crush_ribs_count: int = _BIN_CRUSH_RIBS_DEFAULT_COUNT,
               crush_ribs_waviness: float =
               _BIN_CRUSH_RIBS_DEFAULT_WAVINESS,
               centered: bool = True,
               layout: list[list[bool]] | None = None,
               recessed_top_depth_mm: float = 0.0,
               inside_fillet_mm: float = _BIN_INSIDE_FILLET_DEFAULT_MM,
               scoop: bool = False,
               scoop_radius_mm: float = _BIN_SCOOP_RADIUS_DEFAULT_MM,
               scoop_corner_style: str = "rounded",
               label_shelf_style: str = "off",
               label_shelf_placement: str = "center",
               label_shelf_width_mm: float = _LABEL_SHELF_WIDTH_DEFAULT_MM,
               label_shelf_length_mm: float = _LABEL_SHELF_LENGTH_DEFAULT_MM,
               label_shelf_angle_degrees: float =
               _LABEL_SHELF_ANGLE_DEFAULT_DEGREES,
               label_shelf_thickness_mm: float =
               _LABEL_SHELF_THICKNESS_DEFAULT_MM,
               divider_thickness_mm: float =
               _BIN_DIVIDER_THICKNESS_DEFAULT_MM) -> Group:
    """Generate a Gridfinity bin, then attach any requested divider groups."""
    if bottom == "magnet_open" and kind == "blank":
        raise ValueError("Open magnet pockets require a bin with an interior.")
    if not (1 <= nx <= 10 and 1 <= ny <= 10
            and 1 <= height_units <= 20 and 0.6 <= wall_mm <= 3.0
            and kind in {"blank", "base", "storage", "parts", "eco"}
            and bottom in {
                "plain", "magnet", "magnet_open", "screw", "screw_magnet"
            }
            and 0 <= divider_x <= 10 and 0 <= divider_y <= 10
            and magnet_shape in {"round", "hex", "crush_ribs"}
            and _BIN_MAGNET_DIAMETER_MIN_MM <= magnet_diameter_mm
            <= _BIN_MAGNET_DIAMETER_MAX_MM
            and _BIN_MAGNET_DEPTH_MIN_MM <= magnet_depth_mm
            <= _BIN_MAGNET_DEPTH_MAX_MM
            and 4 <= crush_ribs_count <= 32
            and 0.0 <= crush_ribs_waviness <= 1.0
            and 0.0 <= recessed_top_depth_mm <= _BIN_RECESSED_TOP_MAX_MM
            and 0.0 <= inside_fillet_mm <= 4.0
            and 1.0 <= scoop_radius_mm <= 21.0
            and scoop_corner_style in {"straight", "rounded"}
            and label_shelf_style in {"off", "standard", "overhang"}
            and label_shelf_placement in {
                "center", "full", "left", "right"}
            and 2.0 <= label_shelf_width_mm <= 20.0
            and 10.0 <= label_shelf_length_mm <= 100.0
            and 0.0 <= label_shelf_angle_degrees <= 60.0
            and 0.5 <= label_shelf_thickness_mm <= 4.0
            and _BIN_DIVIDER_THICKNESS_MIN_MM <= divider_thickness_mm
            <= _BIN_DIVIDER_THICKNESS_MAX_MM):
        raise ValueError("Gridfinity dimensions are outside the supported range.")
    layout = _normalize_grid_layout(nx, ny, layout)

    mesh = Mesh()
    width = nx * _PITCH_MM - (_PITCH_MM - _BODY_MM)
    depth = ny * _PITCH_MM - (_PITCH_MM - _BODY_MM)
    body_top_z = height_units * _UNIT_HEIGHT_MM
    if kind == "base":
        body_top_z = min(body_top_z, _UNIT_HEIGHT_MM)
    top_z = body_top_z + (_STACK_LIP_MM if stackable else 0.0)
    floor_z = _BASE_HEIGHT_MM + (1.0 if kind == "eco" else 1.75)
    inner_width = width - 2 * wall_mm
    inner_depth = depth - 2 * wall_mm
    outer_radius = 7.75
    # Offset the inner arc from the same corner center. A fixed interior
    # radius made the inner and outer corner faces skew against each other.
    inner_radius = outer_radius - wall_mm
    if inner_width <= 2 * inner_radius or inner_depth <= 2 * inner_radius:
        raise ValueError("The wall thickness leaves no usable bin interior.")

    outer_bottom = _rounded_rect(0, 0, width, depth, outer_radius,
                                 _BASE_HEIGHT_MM)
    outer_top = _rounded_rect(0, 0, width, depth, outer_radius, top_z)
    inner_floor = _rounded_rect(0, 0, inner_width, inner_depth,
                                inner_radius, floor_z)

    # Each 42 mm cell has its own mating foot. Its stepped 45-degree profile
    # is the standardized interface, rather than a plain rectangular skirt.
    centers = _grid_centres(nx, ny, centered=True)
    top_foot_loops = []
    open_magnet_floor_loops = []
    compartment_count_x = divider_x if kind == "parts" else 0
    compartment_count_y = divider_y if kind == "parts" else 0
    divider_groups = []
    max_divider_height = (height_units - 1) * _UNIT_HEIGHT_MM
    divider_height = (
        divider_height_mm if divider_height_mm is not None
        else min(_UNIT_HEIGHT_MM, max_divider_height))
    divider_x_height = (
        divider_x_height_mm if divider_x_height_mm is not None
        else divider_height)
    divider_y_height = (
        divider_y_height_mm if divider_y_height_mm is not None
        else divider_height)
    for count, divider_value in (
            (compartment_count_x, divider_x_height),
            (compartment_count_y, divider_y_height)):
        if count and not 1.0 <= divider_value <= max_divider_height:
            raise ValueError(
                "Divider height must be at least 1 mm and no more than "
                "one height unit less than the bin.")

    for cx, cy in centers:
        foot_top = _build_bin_foot(
            mesh, cx, cy, bottom, magnet_shape, magnet_diameter_mm,
            crush_ribs_count, crush_ribs_waviness)
        top_foot_loops.append(foot_top)
        _add_bin_bottom_pockets(
            mesh, cx, cy, bottom, floor_z, magnet_shape,
            magnet_diameter_mm, magnet_depth_mm,
            open_magnet_floor_loops, crush_ribs_count,
            crush_ribs_waviness)

    mesh.add_face(list(reversed(outer_bottom)), top_foot_loops)
    _add_rounded_sides(mesh, outer_bottom, outer_top)

    if kind == "blank":
        cutters = _layout_cutters(
            layout, _PITCH_MM, -0.01, top_z + 0.01, centered=True)
        if recessed_top_depth_mm > 0:
            if recessed_top_depth_mm >= body_top_z - _BASE_HEIGHT_MM:
                raise ValueError(
                    "Recessed-top depth must be less than the blank-bin height.")
            top_recess = _rounded_rect(
                0, 0, width - 2 * wall_mm, depth - 2 * wall_mm,
                max(0.1, outer_radius - wall_mm), top_z)
            recess_floor = _rounded_rect(
                0, 0, width - 2 * wall_mm, depth - 2 * wall_mm,
                max(0.1, outer_radius - wall_mm),
                top_z - recessed_top_depth_mm)
            mesh.add_face(outer_top, [list(reversed(top_recess))])
            _add_rounded_sides(
                mesh, top_recess, recess_floor, reverse=True)
            mesh.add_face(recess_floor)
        else:
            mesh.add_face(outer_top)
        group = Group(mesh, name=f"Gridfinity Blank {nx}x{ny}")
        if cutters:
            group = _subtract_cutters(group, cutters)
        return _place_group(
            group,
            0.0 if centered else width / 2 / 1000,
            0.0 if centered else depth / 2 / 1000)

    _add_bin_interior(
        mesh, outer_top, inner_floor, open_magnet_floor_loops,
        inner_width, inner_depth, inner_radius, wall_mm,
        floor_z, body_top_z, stackable, inside_fillet_mm)
    label = {
        "base": "Bin Base",
        "storage": "Storage Bin",
        "parts": "Parts Bin",
        "eco": "Eco Bin",
    }[kind]
    bin_group = Group(mesh, name=f"Gridfinity {label} {nx}x{ny}x{height_units}U")
    cutters = _layout_cutters(
        layout, _PITCH_MM, -0.01, top_z + 0.01, centered=True)
    if cutters:
        bin_group = _subtract_cutters(bin_group, cutters)
    if compartment_count_x or compartment_count_y:
        bin_group.adopt(_build_bin_dividers(
            inner_width, inner_depth, wall_mm, floor_z,
            divider_x_height, divider_y_height,
            compartment_count_x, compartment_count_y,
            divider_thickness_mm))
    children = list(bin_group.children)
    if scoop:
        children.extend(_build_bin_scoops(
            inner_width, inner_depth, inner_radius, floor_z, body_top_z,
            scoop_radius_mm, layout, scoop_corner_style))
    if label_shelf_style != "off":
        children.extend(_build_label_shelves(
            inner_width, floor_z, body_top_z, wall_mm, stackable,
            label_shelf_style, label_shelf_placement,
            label_shelf_width_mm, label_shelf_length_mm,
            label_shelf_angle_degrees, label_shelf_thickness_mm, layout))
    if children:
        bin_group.adopt(children)
    return _place_group(
        bin_group,
        0.0 if centered else width / 2 / 1000,
        0.0 if centered else depth / 2 / 1000)


def _build_baseplate_shell(
        nx: int, ny: int, thickness: float, magnetized: bool,
        socket_profile: tuple[tuple[float, float, float], ...]
        ) -> tuple[Mesh, list[Group]]:
    """Build the plate body and Gridfinity socket cutters."""
    width, depth = nx * _PITCH_MM, ny * _PITCH_MM
    outer_bottom = _rounded_rect(width / 2, depth / 2, width, depth, 4.0, 0.0)
    outer_chamfer_top = _rounded_rect(
        width / 2, depth / 2, width, depth, 4.0, _BASEPLATE_CHAMFER_MM)
    outer_top = _rounded_rect(
        width / 2, depth / 2, width, depth, 4.0, thickness)
    mesh = Mesh()
    socket_cutters = []

    if magnetized:
        # Magnet variants start solid: socket and magnet cavities are boolean
        # cut so all walls meet in a single manifold shell.
        mesh.add_face(list(reversed(outer_bottom)))
        mesh.add_face(outer_top)
        for lower, upper in (
                (outer_bottom, outer_chamfer_top),
                (outer_chamfer_top, outer_top)):
            _add_rounded_sides(mesh, lower, upper)
        for x, y in _grid_centres(nx, ny, centered=False):
            sections = [
                _rounded_rect(x, y, size, size, radius, z)
                for size, z, radius in socket_profile
            ]
            socket_cutters.append(Group(
                _loft_solid(sections), name="Gridfinity socket"))
        return mesh, socket_cutters

    # Plain plates can be drawn directly with through-open bottom cells and
    # socket surfaces, avoiding a boolean for the standard open-grid design.
    grid_openings = [
        _rounded_rect(x, y, 36.3, 36.3, 1.15, 0.0)
        for x, y in _grid_centres(nx, ny, centered=False)
    ]
    socket_sections = [
        [_rounded_rect(x, y, size, size, radius, z)
         for size, z, radius in socket_profile]
        for x, y in _grid_centres(nx, ny, centered=False)
    ]
    mesh.add_face(list(reversed(outer_bottom)), grid_openings)
    for opening, sections in zip(grid_openings, socket_sections):
        for lower, upper in [(opening, sections[0]),
                             *zip(sections, sections[1:])]:
            _add_rounded_sides(mesh, lower, upper, reverse=True)
    mesh.add_face(outer_top, [
        list(reversed(sections[-1])) for sections in socket_sections])
    _add_rounded_sides(mesh, outer_bottom, outer_chamfer_top)
    _add_rounded_sides(mesh, outer_chamfer_top, outer_top)
    return mesh, socket_cutters


def _baseplate_magnet_cutters(
        nx: int, ny: int, kind: str, socket_floor_z: float,
        magnet_base_mm: float, pocket_diameter_mm: float,
        magnet_shape: str = "round",
        crush_ribs_count: int = _BIN_CRUSH_RIBS_DEFAULT_COUNT,
        crush_ribs_waviness: float =
        _BIN_CRUSH_RIBS_DEFAULT_WAVINESS,
        base_bore_diameter_mm: float = _MAGNET_BASE_BORE_DIAMETER_MM,
        chamfer_depth_mm: float =
        _BASEPLATE_MAGNET_CHAMFER_DEFAULT_MM,
        base_bore_chamfer_mm: float =
        _BASEPLATE_MAGNET_BASE_CHAMFER_DEFAULT_MM) -> list[Group]:
    """Create socket openings and two-stage magnet bores for each cell."""
    cutters = []
    if kind == "magnet_open":
        for x, y in _grid_centres(nx, ny, centered=False):
            lower = _magnet_grid_opening(
                x, y, _PITCH_MM, _PITCH_MM, pocket_diameter_mm, -0.01)
            upper = [
                QVector3D(point.x(), point.y(),
                          (socket_floor_z + 0.01) / 1000.0)
                for point in lower
            ]
            cutters.append(Group(
                _loft_solid([lower, upper]), name="Open magnet grid cell"))

    for x, y in _grid_centres(nx, ny, centered=False):
        for dx in (-13.0, 13.0):
            for dy in (-13.0, 13.0):
                cx, cy = x + dx, y + dy
                if base_bore_diameter_mm > 0:
                    if base_bore_chamfer_mm > 0:
                        wide_bore = _circle(
                            cx, cy,
                            base_bore_diameter_mm
                            + 2 * base_bore_chamfer_mm, -0.01)
                        narrow_bore = _circle(
                            cx, cy, base_bore_diameter_mm,
                            base_bore_chamfer_mm)
                        cutters.append(Group(
                            _loft_solid([wide_bore, narrow_bore]),
                            name="Magnet bottom countersink"))
                        cutters.append(Group(_cylinder_mesh(
                            (cx / 1000, cy / 1000,
                             (base_bore_chamfer_mm - 0.01) / 1000),
                            (cx / 1000, cy / 1000,
                             (magnet_base_mm + 0.01) / 1000),
                            base_bore_diameter_mm / 1000),
                            name="Magnet bottom opening"))
                    else:
                        cutters.append(Group(_cylinder_mesh(
                            (cx / 1000, cy / 1000, -0.01 / 1000),
                            (cx / 1000, cy / 1000,
                             (magnet_base_mm + 0.01) / 1000),
                            base_bore_diameter_mm / 1000),
                            name="Magnet bottom opening"))

                pocket_loop = _bin_magnet_loop(
                    cx, cy, magnet_shape, pocket_diameter_mm,
                    crush_ribs_count, crush_ribs_waviness)
                pocket_top_z = socket_floor_z + 0.01
                chamfer_start_z = pocket_top_z - chamfer_depth_mm
                sections = [
                    [
                        QVector3D(
                            point.x(), point.y(), magnet_base_mm / 1000)
                        for point in pocket_loop
                    ],
                    [
                        QVector3D(
                            point.x(), point.y(), chamfer_start_z / 1000)
                        for point in pocket_loop
                    ],
                ]
                if chamfer_depth_mm > 0:
                    expansion = (
                        pocket_diameter_mm + 2 * chamfer_depth_mm
                    ) / pocket_diameter_mm
                    sections.append([
                        QVector3D(
                            cx / 1000 + (point.x() - cx / 1000) * expansion,
                            cy / 1000 + (point.y() - cy / 1000) * expansion,
                            pocket_top_z / 1000)
                        for point in pocket_loop
                    ])
                else:
                    sections[-1] = [
                        QVector3D(point.x(), point.y(), pocket_top_z / 1000)
                        for point in pocket_loop
                    ]
                cutters.append(Group(
                    _loft_solid(sections), name="Magnet pocket"))
    return cutters


def _baseplate_screw_cutters(
        nx: int, ny: int, screw_hole_diameter_mm: float,
        bore_center_z: float) -> list[Group]:
    """Create crosswise connection bores at the outer edge of each cell."""
    width, depth = nx * _PITCH_MM, ny * _PITCH_MM
    bore_half_length = 6.4 / 2
    cutters = []
    for x, y in _grid_centres(nx, ny, centered=False):
        for edge_y, direction in ((0.0, -1), (depth, 1)):
            cutters.append(Group(_cylinder_mesh(
                (x / 1000, (edge_y - direction * bore_half_length) / 1000,
                 bore_center_z / 1000),
                (x / 1000, (edge_y + direction * bore_half_length) / 1000,
                 bore_center_z / 1000),
                screw_hole_diameter_mm / 1000), name="Connection hole"))
        for edge_x, direction in ((0.0, -1), (width, 1)):
            cutters.append(Group(_cylinder_mesh(
                ((edge_x - direction * bore_half_length) / 1000, y / 1000,
                 bore_center_z / 1000),
                ((edge_x + direction * bore_half_length) / 1000, y / 1000,
                 bore_center_z / 1000),
                screw_hole_diameter_mm / 1000), name="Connection hole"))
    return cutters


def _build_baseplate_legacy(
        nx: int, ny: int, kind: str = "plain",
        centered: bool = False,
        magnet_diameter_mm: float = _MAGNET_DIAMETER_DEFAULT_MM,
        magnet_height_mm: float = _MAGNET_HEIGHT_DEFAULT_MM,
        magnet_base_mm: float = _MAGNET_BASE_DEFAULT_MM,
        screw_together: bool = False,
        baseplate_base_mm: float = _BASEPLATE_DEFAULT_BASE_MM,
        screw_hole_diameter_mm: float = _SCREW_HOLE_DEFAULT_DIAMETER_MM,
        layout: list[list[bool]] | None = None,
        magnet_shape: str = "round",
        crush_ribs_count: int = _BIN_CRUSH_RIBS_DEFAULT_COUNT,
        crush_ribs_waviness: float =
        _BIN_CRUSH_RIBS_DEFAULT_WAVINESS,
        magnet_base_bore_diameter_mm: float =
        _MAGNET_BASE_BORE_DIAMETER_MM,
        magnet_chamfer_depth_mm: float =
        _BASEPLATE_MAGNET_CHAMFER_DEFAULT_MM,
        magnet_base_chamfer_depth_mm: float =
        _BASEPLATE_MAGNET_BASE_CHAMFER_DEFAULT_MM,
        ) -> Group:
    """Build a baseplate before the final coplanar-facet cleanup step."""
    if not (1 <= nx <= 10 and 1 <= ny <= 10
            and kind in {"plain", "magnet", "magnet_open",
                         "screw_together"}):
        raise ValueError("Gridfinity dimensions are outside the supported range.")
    layout = _normalize_grid_layout(nx, ny, layout)

    magnetized = kind in {"magnet", "magnet_open", "screw_together"}
    has_screw_holes = screw_together or kind == "screw_together"
    if magnetized and not (
            4.0 <= magnet_diameter_mm <= 10.0
            and 2.0 <= magnet_height_mm <= 5.0
            and 0.5 <= magnet_base_mm <= 10.0
            and magnet_shape in {"round", "hex", "crush_ribs"}
            and 4 <= crush_ribs_count <= 32
            and 0.0 <= crush_ribs_waviness <= 1.0
            and _BASEPLATE_MAGNET_BASE_BORE_MIN_MM
            <= magnet_base_bore_diameter_mm
            <= _BASEPLATE_MAGNET_BASE_BORE_MAX_MM
            and 0.0 <= magnet_chamfer_depth_mm
            <= magnet_height_mm + _MAGNET_HEIGHT_TOLERANCE_MM
            and 0.0 <= magnet_base_chamfer_depth_mm
            <= min(2.0, magnet_base_mm)):
        raise ValueError("Magnet dimensions are outside the supported range.")
    if kind == "plain" and not 0.5 <= baseplate_base_mm <= 10.0:
        raise ValueError("Baseplate base height must be between 0.5 and 10 mm.")
    if has_screw_holes and not 2.0 <= screw_hole_diameter_mm <= 8.0:
        raise ValueError("Screw-hole diameter must be between 2 and 8 mm.")
    base_height = magnet_base_mm if magnetized else baseplate_base_mm
    minimum_screw_base = (
        screw_hole_diameter_mm + _SCREW_HOLE_MINIMUM_BELOW_MM
        + _SCREW_HOLE_MINIMUM_ABOVE_MM)
    if has_screw_holes and base_height < minimum_screw_base:
        raise ValueError(
            "Base height must leave 1 mm below and 0.5 mm above the "
            "screw hole.")

    width, depth = nx * _PITCH_MM, ny * _PITCH_MM
    magnet_pocket_diameter = (
        magnet_diameter_mm + _MAGNET_DIAMETER_TOLERANCE_MM)
    magnet_pocket_depth = magnet_height_mm + _MAGNET_HEIGHT_TOLERANCE_MM
    socket_floor_z = magnet_base_mm + magnet_pocket_depth
    thickness = (
        socket_floor_z + _MAGNET_BASEPLATE_SOCKET_HEIGHT_MM
        if magnetized
        else baseplate_base_mm + _MAGNET_BASEPLATE_SOCKET_HEIGHT_MM)
    socket_profile = (
        tuple(
            (size, socket_floor_z + level, radius)
            for (size, _, radius), level in zip(
                _BASEPLATE_SOCKET_PROFILE, _MAGNET_BASEPLATE_SOCKET_LEVELS_MM)
        )
        if magnetized else tuple(
            (size, z + baseplate_base_mm - _BASEPLATE_DEFAULT_BASE_MM, radius)
            for size, z, radius in _BASEPLATE_SOCKET_PROFILE)
    )
    mesh, cutters = _build_baseplate_shell(
        nx, ny, thickness, magnetized, socket_profile)
    label = {
        "plain": "Baseplate",
        "magnet": "Magnet Baseplate",
        "magnet_open": "Open Magnet Baseplate",
        "screw_together": "Screw-Together Baseplate",
    }[kind]
    group = Group(mesh, name=f"Gridfinity {label} {nx}x{ny}")
    if magnetized:
        cutters.extend(_baseplate_magnet_cutters(
            nx, ny, kind, socket_floor_z, magnet_base_mm,
            magnet_pocket_diameter, magnet_shape, crush_ribs_count,
            crush_ribs_waviness, magnet_base_bore_diameter_mm,
            magnet_chamfer_depth_mm, magnet_base_chamfer_depth_mm))

    if has_screw_holes:
        bore_z = (screw_hole_diameter_mm / 2
                  + _SCREW_HOLE_MINIMUM_BELOW_MM)
        cutters.extend(_baseplate_screw_cutters(
            nx, ny, screw_hole_diameter_mm, bore_z))
    cutters.extend(_layout_cutters(
        layout, _PITCH_MM, -0.01, thickness + 0.01, centered=False))
    if cutters:
        group = _subtract_cutters(group, cutters)
        group.name = f"Gridfinity {label} {nx}x{ny}"
    return _place_group(
        group,
        -width / 2 / 1000 if centered else 0.0,
        -depth / 2 / 1000 if centered else 0.0)


def _build_baseplate(nx: int, ny: int,
                     kind: str = "plain",
                     centered: bool = False,
                     magnet_diameter_mm: float = _MAGNET_DIAMETER_DEFAULT_MM,
                     magnet_height_mm: float = _MAGNET_HEIGHT_DEFAULT_MM,
                     magnet_base_mm: float = _MAGNET_BASE_DEFAULT_MM,
                     screw_together: bool = False,
                     baseplate_base_mm: float = _BASEPLATE_DEFAULT_BASE_MM,
                     screw_hole_diameter_mm: float =
                     _SCREW_HOLE_DEFAULT_DIAMETER_MM,
                     layout: list[list[bool]] | None = None,
                     magnet_shape: str = "round",
                     crush_ribs_count: int = _BIN_CRUSH_RIBS_DEFAULT_COUNT,
                     crush_ribs_waviness: float =
                     _BIN_CRUSH_RIBS_DEFAULT_WAVINESS,
                     magnet_base_bore_diameter_mm: float =
                     _MAGNET_BASE_BORE_DIAMETER_MM,
                     magnet_chamfer_depth_mm: float =
                     _BASEPLATE_MAGNET_CHAMFER_DEFAULT_MM,
                     magnet_base_chamfer_depth_mm: float =
                     _BASEPLATE_MAGNET_BASE_CHAMFER_DEFAULT_MM) -> Group:
    """Build a baseplate and merge coplanar boolean facets on magnet variants."""
    # Retain compatibility with the former standalone variant, but make its
    # intended open center explicit in newly generated geometry.
    if kind == "screw_together":
        kind, screw_together = "magnet_open", True
    if screw_together and kind not in {"plain", "magnet_open"}:
        raise ValueError(
            "Screw-together holes require a plain or open-magnet baseplate.")
    group = _build_baseplate_legacy(
        nx, ny, kind, centered, magnet_diameter_mm, magnet_height_mm,
        magnet_base_mm, screw_together, baseplate_base_mm,
        screw_hole_diameter_mm, layout, magnet_shape, crush_ribs_count,
        crush_ribs_waviness, magnet_base_bore_diameter_mm,
        magnet_chamfer_depth_mm, magnet_base_chamfer_depth_mm)
    if kind in {"magnet", "magnet_open"} or screw_together:
        from formats.fuse import simplify_mesh

        simplify_mesh(group.mesh)
    if screw_together:
        group.name += " Screw-Together"
    return group


class GridfinityPanel(QWidget):
    """Sidebar controls for choosing, configuring, and creating Gridfinity models."""

    def __init__(self, viewport, parent=None) -> None:
        """Create the variant cards, parameter form, and model action."""
        super().__init__(parent or viewport.window())
        self._viewport = viewport
        self._kind_value = "bin"
        self._variant_value = "blank"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)

        (self._baseplate_cards, self._baseplate_buttons,
         self._baseplate_button_group) = \
            self._variant_section(
                tr("Baseplates"),
                (
                    (tr("Baseplate"), "plain"),
                    (tr("Open Magnets"), "magnet_open"),
                    (tr("With Magnets"), "magnet"),
                ),
                "baseplate",
            )
        layout.addWidget(self._baseplate_cards)
        (self._bin_cards, self._bin_buttons,
         self._bin_button_group) = self._variant_section(
            tr("Bins"),
            (
                (tr("Simple"), "storage"),
                (tr("Parts"), "parts"),
                (tr("Blank"), "blank"),
            ),
            "bin",
        )
        layout.addWidget(self._bin_cards)
        self._bin_buttons["blank"].setChecked(True)

        self._replace_selected = QCheckBox(
            tr("Replace selected model group"))
        self._replace_selected.setChecked(True)
        layout.addWidget(self._replace_selected)
        self._editing_group = None
        self._model_status = QLabel(tr("Select a generated model to edit it."))
        self._model_status.setWordWrap(True)
        layout.addWidget(self._model_status)

        form = QFormLayout()
        self._options_form = form
        layout.addLayout(form)

        self._placement = QComboBox()
        self._placement.addItem(tr("Centered"), True)
        self._placement.addItem(tr("From origin"), False)
        form.addRow(tr("Placement:"), self._placement)

        self._nx = self._grid_spin()
        self._ny = self._grid_spin()
        form.addRow(tr("Grid width (42 mm cells):"), self._nx)
        form.addRow(tr("Grid depth (42 mm cells):"), self._ny)
        self._layout = [[True, True], [True, True]]
        self._layout_button = QPushButton()
        self._layout_button.clicked.connect(self._edit_layout)
        form.addRow(tr("Custom footprint:"), self._layout_button)
        self._nx.valueChanged.connect(self._resize_layout)
        self._ny.valueChanged.connect(self._resize_layout)
        self._update_layout_button()

        self._height = QSpinBox()
        self._height.setRange(1, 20)
        self._height.setValue(3)
        self._height.setSuffix(" U")
        form.addRow(tr("Bin height:"), self._height)

        self._wall = QDoubleSpinBox()
        self._wall.setRange(0.6, 3.0)
        self._wall.setSingleStep(0.1)
        self._wall.setDecimals(1)
        self._wall.setValue(0.8)
        self._wall.setSuffix(" mm")
        form.addRow(tr("Wall thickness:"), self._wall)

        self._inside_fillet = QDoubleSpinBox()
        self._inside_fillet.setRange(0.0, 4.0)
        self._inside_fillet.setSingleStep(0.1)
        self._inside_fillet.setDecimals(2)
        self._inside_fillet.setValue(_BIN_INSIDE_FILLET_DEFAULT_MM)
        self._inside_fillet.setSuffix(" mm")
        form.addRow(tr("Inside floor fillet:"), self._inside_fillet)

        self._scoop_enabled = QCheckBox(tr("Add finger scoop"))
        form.addRow(self._scoop_enabled)
        self._scoop_radius = QDoubleSpinBox()
        self._scoop_radius.setRange(1.0, 21.0)
        self._scoop_radius.setSingleStep(0.5)
        self._scoop_radius.setDecimals(1)
        self._scoop_radius.setValue(_BIN_SCOOP_RADIUS_DEFAULT_MM)
        self._scoop_radius.setSuffix(" mm")
        form.addRow(tr("Scoop radius:"), self._scoop_radius)
        self._scoop_enabled.toggled.connect(self._update_variant_features)

        self._scoop_corner_style = QComboBox()
        self._scoop_corner_style.addItem(
            tr("Follow rounded corners"), "rounded")
        self._scoop_corner_style.addItem(
            tr("Straight ends (legacy)"), "straight")
        form.addRow(tr("Scoop corner style:"), self._scoop_corner_style)

        self._label_shelf_style = QComboBox()
        for label, value in (
                (tr("Off"), "off"),
                (tr("Standard"), "standard"),
                (tr("Overhang"), "overhang")):
            self._label_shelf_style.addItem(label, value)
        self._label_shelf_style.currentIndexChanged.connect(
            self._update_variant_features)
        form.addRow(tr("Label shelf style:"), self._label_shelf_style)

        self._label_shelf_placement = QComboBox()
        for label, value in (
                (tr("Center"), "center"),
                (tr("Full width"), "full"),
                (tr("Left"), "left"),
                (tr("Right"), "right")):
            self._label_shelf_placement.addItem(label, value)
        form.addRow(tr("Label shelf placement:"), self._label_shelf_placement)

        self._label_shelf_width = QDoubleSpinBox()
        self._label_shelf_width.setRange(2.0, 20.0)
        self._label_shelf_width.setSingleStep(0.5)
        self._label_shelf_width.setValue(_LABEL_SHELF_WIDTH_DEFAULT_MM)
        self._label_shelf_width.setSuffix(" mm")
        form.addRow(tr("Label shelf width:"), self._label_shelf_width)

        self._label_shelf_length = QDoubleSpinBox()
        self._label_shelf_length.setRange(10.0, 100.0)
        self._label_shelf_length.setSingleStep(1.0)
        self._label_shelf_length.setValue(_LABEL_SHELF_LENGTH_DEFAULT_MM)
        self._label_shelf_length.setSuffix(" mm")
        form.addRow(tr("Label shelf length:"), self._label_shelf_length)

        self._label_shelf_angle = QDoubleSpinBox()
        self._label_shelf_angle.setRange(0.0, 60.0)
        self._label_shelf_angle.setSingleStep(1.0)
        self._label_shelf_angle.setValue(
            _LABEL_SHELF_ANGLE_DEFAULT_DEGREES)
        self._label_shelf_angle.setSuffix("°")
        form.addRow(tr("Label shelf angle:"), self._label_shelf_angle)

        self._label_shelf_thickness = QDoubleSpinBox()
        self._label_shelf_thickness.setRange(0.5, 4.0)
        self._label_shelf_thickness.setSingleStep(0.1)
        self._label_shelf_thickness.setValue(
            _LABEL_SHELF_THICKNESS_DEFAULT_MM)
        self._label_shelf_thickness.setSuffix(" mm")
        form.addRow(tr("Label shelf thickness:"), self._label_shelf_thickness)

        self._recessed_top_depth = QDoubleSpinBox()
        self._recessed_top_depth.setRange(0.0, _BIN_RECESSED_TOP_MAX_MM)
        self._recessed_top_depth.setSingleStep(0.5)
        self._recessed_top_depth.setDecimals(1)
        self._recessed_top_depth.setValue(0.0)
        self._recessed_top_depth.setSuffix(" mm")
        form.addRow(tr("Blank-bin recessed top:"), self._recessed_top_depth)

        self._bottom = QComboBox()
        for label, value in (
            (tr("Plain"), "plain"),
            (tr("Magnets"), "magnet"),
            (tr("Open magnets"), "magnet_open"),
            (tr("Screws"), "screw"),
            (tr("Screws and magnets"), "screw_magnet"),
        ):
            self._bottom.addItem(label, value)
        form.addRow(tr("Bin bottom:"), self._bottom)

        self._magnet_shape = QComboBox()
        self._magnet_shape.addItem(tr("Round"), "round")
        self._magnet_shape.addItem(tr("Crush ribs"), "crush_ribs")
        self._magnet_shape.addItem(tr("Hex"), "hex")
        self._bottom.currentIndexChanged.connect(
            self._update_variant_features)
        self._magnet_shape.currentIndexChanged.connect(
            self._update_variant_features)
        form.addRow(tr("Magnet pocket shape:"), self._magnet_shape)

        self._crush_ribs_count = QSpinBox()
        self._crush_ribs_count.setRange(4, 32)
        self._crush_ribs_count.setValue(_BIN_CRUSH_RIBS_DEFAULT_COUNT)
        form.addRow(tr("Crush rib count:"), self._crush_ribs_count)

        self._crush_ribs_waviness = QDoubleSpinBox()
        self._crush_ribs_waviness.setRange(0.0, 1.0)
        self._crush_ribs_waviness.setSingleStep(0.05)
        self._crush_ribs_waviness.setDecimals(2)
        self._crush_ribs_waviness.setValue(
            _BIN_CRUSH_RIBS_DEFAULT_WAVINESS)
        form.addRow(tr("Crush rib waviness:"), self._crush_ribs_waviness)

        self._bin_magnet_diameter = QDoubleSpinBox()
        self._bin_magnet_diameter.setRange(
            _BIN_MAGNET_DIAMETER_MIN_MM, _BIN_MAGNET_DIAMETER_MAX_MM)
        self._bin_magnet_diameter.setSingleStep(0.5)
        self._bin_magnet_diameter.setDecimals(1)
        self._bin_magnet_diameter.setValue(_MAGNET_DIAMETER_MM)
        self._bin_magnet_diameter.setSuffix(" mm")
        form.addRow(tr("Bin magnet diameter:"), self._bin_magnet_diameter)

        self._bin_magnet_depth = QDoubleSpinBox()
        self._bin_magnet_depth.setRange(
            _BIN_MAGNET_DEPTH_MIN_MM, _BIN_MAGNET_DEPTH_MAX_MM)
        self._bin_magnet_depth.setSingleStep(0.2)
        self._bin_magnet_depth.setDecimals(1)
        self._bin_magnet_depth.setValue(_MAGNET_DEPTH_MM)
        self._bin_magnet_depth.setSuffix(" mm")
        form.addRow(tr("Bin magnet pocket depth:"), self._bin_magnet_depth)

        self._baseplate_magnet_diameter = QDoubleSpinBox()
        self._baseplate_magnet_diameter.setRange(4.0, 10.0)
        self._baseplate_magnet_diameter.setSingleStep(0.5)
        self._baseplate_magnet_diameter.setDecimals(1)
        self._baseplate_magnet_diameter.setValue(_MAGNET_DIAMETER_DEFAULT_MM)
        self._baseplate_magnet_diameter.setSuffix(" mm")
        self._baseplate_magnet_diameter.setToolTip(
            tr("Adds 0.5 mm clearance to the nominal magnet diameter."))
        form.addRow(tr("Baseplate magnet diameter:"),
                    self._baseplate_magnet_diameter)

        self._baseplate_magnet_shape = QComboBox()
        self._baseplate_magnet_shape.addItem(tr("Round"), "round")
        self._baseplate_magnet_shape.addItem(tr("Crush ribs"), "crush_ribs")
        self._baseplate_magnet_shape.addItem(tr("Hex"), "hex")
        self._baseplate_magnet_shape.currentIndexChanged.connect(
            self._update_variant_features)
        form.addRow(tr("Baseplate magnet-hole shape:"),
                    self._baseplate_magnet_shape)

        self._baseplate_crush_ribs_count = QSpinBox()
        self._baseplate_crush_ribs_count.setRange(4, 32)
        self._baseplate_crush_ribs_count.setValue(
            _BIN_CRUSH_RIBS_DEFAULT_COUNT)
        form.addRow(tr("Baseplate crush-rib count:"),
                    self._baseplate_crush_ribs_count)

        self._baseplate_crush_ribs_waviness = QDoubleSpinBox()
        self._baseplate_crush_ribs_waviness.setRange(0.0, 1.0)
        self._baseplate_crush_ribs_waviness.setSingleStep(0.05)
        self._baseplate_crush_ribs_waviness.setDecimals(2)
        self._baseplate_crush_ribs_waviness.setValue(
            _BIN_CRUSH_RIBS_DEFAULT_WAVINESS)
        form.addRow(tr("Baseplate crush-rib waviness:"),
                    self._baseplate_crush_ribs_waviness)

        self._baseplate_magnet_base_bore = QDoubleSpinBox()
        self._baseplate_magnet_base_bore.setRange(
            _BASEPLATE_MAGNET_BASE_BORE_MIN_MM,
            _BASEPLATE_MAGNET_BASE_BORE_MAX_MM)
        self._baseplate_magnet_base_bore.setSingleStep(0.5)
        self._baseplate_magnet_base_bore.setDecimals(1)
        self._baseplate_magnet_base_bore.setValue(
            _MAGNET_BASE_BORE_DIAMETER_MM)
        self._baseplate_magnet_base_bore.setSuffix(" mm")
        self._baseplate_magnet_base_bore.setToolTip(
            tr("Set to zero to close the underside access bore."))
        form.addRow(tr("Underside magnet access diameter:"),
                    self._baseplate_magnet_base_bore)

        self._baseplate_magnet_base_chamfer = QDoubleSpinBox()
        self._baseplate_magnet_base_chamfer.setRange(0.0, 2.0)
        self._baseplate_magnet_base_chamfer.setSingleStep(0.1)
        self._baseplate_magnet_base_chamfer.setDecimals(1)
        self._baseplate_magnet_base_chamfer.setValue(
            _BASEPLATE_MAGNET_BASE_CHAMFER_DEFAULT_MM)
        self._baseplate_magnet_base_chamfer.setSuffix(" mm")
        self._baseplate_magnet_base_chamfer.setToolTip(
            tr("Underside countersink depth; limited by material below the magnet."))
        form.addRow(tr("Underside countersink depth:"),
                    self._baseplate_magnet_base_chamfer)

        self._baseplate_magnet_chamfer = QDoubleSpinBox()
        self._baseplate_magnet_chamfer.setRange(0.0, 1.5)
        self._baseplate_magnet_chamfer.setSingleStep(0.05)
        self._baseplate_magnet_chamfer.setDecimals(2)
        self._baseplate_magnet_chamfer.setValue(
            _BASEPLATE_MAGNET_CHAMFER_DEFAULT_MM)
        self._baseplate_magnet_chamfer.setSuffix(" mm")
        self._baseplate_magnet_chamfer.setToolTip(
            tr("Depth of the chamfer at the socket-side magnet opening."))
        form.addRow(tr("Magnet pocket top chamfer:"),
                    self._baseplate_magnet_chamfer)

        self._baseplate_magnet_height = QDoubleSpinBox()
        self._baseplate_magnet_height.setRange(2.0, 5.0)
        self._baseplate_magnet_height.setSingleStep(0.5)
        self._baseplate_magnet_height.setDecimals(1)
        self._baseplate_magnet_height.setValue(_MAGNET_HEIGHT_DEFAULT_MM)
        self._baseplate_magnet_height.setSuffix(" mm")
        self._baseplate_magnet_height.setToolTip(
            tr("Adds 0.5 mm clearance to the nominal magnet height."))
        form.addRow(tr("Baseplate magnet height:"),
                    self._baseplate_magnet_height)

        self._baseplate_magnet_base = QDoubleSpinBox()
        self._baseplate_magnet_base.setRange(0.5, 10.0)
        self._baseplate_magnet_base.setSingleStep(0.5)
        self._baseplate_magnet_base.setDecimals(1)
        self._baseplate_magnet_base.setValue(_MAGNET_BASE_DEFAULT_MM)
        self._baseplate_magnet_base.setSuffix(" mm")
        self._baseplate_magnet_base.valueChanged.connect(
            self._update_variant_features)
        form.addRow(tr("Material below magnet pockets:"),
                    self._baseplate_magnet_base)

        self._baseplate_base = QDoubleSpinBox()
        self._baseplate_base.setRange(0.5, 10.0)
        self._baseplate_base.setSingleStep(0.5)
        self._baseplate_base.setDecimals(2)
        self._baseplate_base.setValue(_BASEPLATE_DEFAULT_BASE_MM)
        self._baseplate_base.setSuffix(" mm")
        self._baseplate_base.setToolTip(
            tr("Height below the Gridfinity lip."))
        form.addRow(tr("Base height (below lip):"), self._baseplate_base)

        self._screw_together = QCheckBox(tr("Add screw-together holes"))
        self._screw_together.toggled.connect(self._update_variant_features)
        form.addRow(self._screw_together)

        self._screw_hole_diameter = QDoubleSpinBox()
        self._screw_hole_diameter.setRange(2.0, 8.0)
        self._screw_hole_diameter.setSingleStep(0.2)
        self._screw_hole_diameter.setDecimals(1)
        self._screw_hole_diameter.setValue(
            _SCREW_HOLE_DEFAULT_DIAMETER_MM)
        self._screw_hole_diameter.setSuffix(" mm")
        self._screw_hole_diameter.valueChanged.connect(
            self._update_variant_features)
        form.addRow(tr("Screw-hole diameter:"),
                    self._screw_hole_diameter)

        self._stackable = QCheckBox(tr("Add stacking lip"))
        self._stackable.setChecked(True)
        form.addRow(self._stackable)

        self._divider_x = QSpinBox()
        self._divider_x.setRange(0, 8)
        self._divider_x.setValue(1)
        form.addRow(tr("Parts-bin dividers across X:"), self._divider_x)

        self._divider_y = QSpinBox()
        self._divider_y.setRange(0, 8)
        self._divider_y.setValue(1)
        form.addRow(tr("Parts-bin dividers across Y:"), self._divider_y)

        self._divider_height = QSpinBox()
        self._divider_height.setRange(1, 19)
        self._divider_height.setValue(1)
        self._divider_height.setSuffix(" U")
        divider_height_layout = QHBoxLayout()
        divider_height_layout.addWidget(self._divider_height)
        self._divider_height_mm = QLabel()
        divider_height_layout.addWidget(self._divider_height_mm)
        self._divider_height_row = QWidget()
        self._divider_height_row.setLayout(divider_height_layout)
        form.addRow(tr("Divider height:"), self._divider_height_row)
        self._divider_height.valueChanged.connect(
            self._update_divider_height_label)
        self._height.valueChanged.connect(self._update_variant_features)
        self._divider_x.valueChanged.connect(self._update_variant_features)
        self._divider_y.valueChanged.connect(self._update_variant_features)

        self._independent_divider_heights = QCheckBox(
            tr("Set X and Y divider heights separately"))
        form.addRow(self._independent_divider_heights)
        (self._divider_x_height, self._divider_x_height_row,
         self._divider_x_height_mm) = \
            self._divider_height_control()
        (self._divider_y_height, self._divider_y_height_row,
         self._divider_y_height_mm) = \
            self._divider_height_control()
        form.addRow(tr("X divider height:"), self._divider_x_height_row)
        form.addRow(tr("Y divider height:"), self._divider_y_height_row)
        self._divider_thickness = QDoubleSpinBox()
        self._divider_thickness.setRange(
            _BIN_DIVIDER_THICKNESS_MIN_MM,
            _BIN_DIVIDER_THICKNESS_MAX_MM)
        self._divider_thickness.setSingleStep(0.1)
        self._divider_thickness.setDecimals(1)
        self._divider_thickness.setValue(
            _BIN_DIVIDER_THICKNESS_DEFAULT_MM)
        self._divider_thickness.setSuffix(" mm")
        form.addRow(tr("Divider thickness:"), self._divider_thickness)

        self._create_button = QPushButton(tr("Create model"))
        self._create_button.clicked.connect(self._create)
        layout.addWidget(self._create_button)
        layout.addStretch(1)
        scroll.setWidget(content)
        self._update_variant_features()
        self._update_divider_height_label()
        self._divider_x_height.valueChanged.connect(
            self._update_axis_divider_height_labels)
        self._divider_y_height.valueChanged.connect(
            self._update_axis_divider_height_labels)
        self._independent_divider_heights.toggled.connect(
            self._update_variant_features)
        selection_signal = getattr(
            self._viewport, "sceneVersionChanged", None)
        if selection_signal is not None:
            selection_signal.connect(self._on_scene_changed)
        self._on_scene_changed()

    @staticmethod
    def _divider_height_control() -> tuple[QSpinBox, QWidget, QLabel]:
        """Create a U-based divider height field with its millimetre label."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        spin = QSpinBox()
        spin.setRange(1, 19)
        spin.setValue(1)
        spin.setSuffix(" U")
        label = QLabel("(7 mm)")
        layout.addWidget(spin)
        layout.addWidget(label)
        return spin, row, label

    def _variant_section(self, title: str,
                         variants: tuple[tuple[str, str], ...],
                         kind: str) -> tuple[
                             QGroupBox, dict[str, QToolButton],
                             QButtonGroup]:
        """Build an exclusive icon-card grid and its corresponding button map."""
        section = QGroupBox(title)
        grid = QGridLayout(section)
        grid.setContentsMargins(4, 8, 4, 4)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        buttons = {}
        group = QButtonGroup(section)
        group.setExclusive(True)
        for index, (label, variant) in enumerate(variants):
            button = QToolButton(section)
            button.setText(label)
            button.setIcon(self._variant_icon(kind, variant))
            button.setIconSize(QSize(48, 40))
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            button.setCheckable(True)
            button.setMinimumSize(94, 88)
            button.setStyleSheet(
                "QToolButton { border: 1px solid palette(mid);"
                " border-radius: 10px; padding: 5px; }"
                "QToolButton:checked { border: 2px solid palette(highlight);"
                " background: palette(alternate-base); }")
            button.clicked.connect(
                lambda _checked=False, selected_kind=kind,
                selected_variant=variant: self._select_variant(
                    selected_kind, selected_variant))
            group.addButton(button)
            buttons[variant] = button
            grid.addWidget(button, index // 3, index % 3)
        return section, buttons, group

    @staticmethod
    def _variant_icon(kind: str, variant: str) -> QIcon:
        """Draw a small placeholder icon describing a model variant."""
        pixmap = QPixmap(64, 48)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        outline = QPen(QColor(70, 88, 105), 2.2)
        painter.setPen(outline)
        painter.setBrush(QBrush(QColor(216, 229, 239)))
        if kind == "baseplate":
            painter.drawRoundedRect(9, 8, 46, 32, 5, 5)
            if variant == "magnet_open":
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.drawRoundedRect(19, 15, 26, 18, 3, 3)
                painter.setBrush(QBrush(QColor(132, 166, 190)))
                for x, y in ((15, 14), (49, 14), (15, 34), (49, 34)):
                    painter.drawEllipse(x - 2, y - 2, 5, 5)
            elif variant == "magnet":
                painter.setBrush(QBrush(QColor(132, 166, 190)))
                for x, y in ((19, 17), (45, 17), (19, 31), (45, 31)):
                    painter.drawEllipse(x - 3, y - 3, 6, 6)
            else:
                painter.drawLine(32, 9, 32, 39)
                painter.drawLine(10, 24, 54, 24)
        else:
            painter.drawRoundedRect(13, 8, 38, 32, 4, 4)
            painter.drawLine(13, 17, 51, 17)
            if variant == "parts":
                painter.drawLine(32, 18, 32, 38)
                painter.drawLine(14, 28, 50, 28)
            elif variant == "blank":
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(18, 11, 46, 11)
            elif variant == "base":
                painter.drawLine(18, 33, 46, 33)
            elif variant == "eco":
                painter.drawLine(19, 22, 45, 22)
                painter.drawLine(19, 29, 45, 29)
        painter.end()
        return QIcon(pixmap)

    def _select_variant(self, kind: str, variant: str) -> None:
        """Select exactly one card across both variant families."""
        self._kind_value = kind
        self._variant_value = variant
        self._baseplate_button_group.setExclusive(False)
        for button_variant, button in self._baseplate_buttons.items():
            button.setChecked(kind == "baseplate"
                              and button_variant == variant)
        self._baseplate_button_group.setExclusive(True)
        self._bin_button_group.setExclusive(False)
        for button_variant, button in self._bin_buttons.items():
            button.setChecked(kind == "bin" and button_variant == variant)
        self._bin_button_group.setExclusive(True)
        self._update_variant_features()

    @staticmethod
    def _grid_spin() -> QSpinBox:
        """Create a grid-count control with supported minimum and default."""
        spin = QSpinBox()
        spin.setRange(1, 10)
        spin.setValue(2)
        return spin

    def _resize_layout(self, *_args) -> None:
        """Resize the footprint mask while keeping existing cells in place."""
        width, depth = self._nx.value(), self._ny.value()
        self._layout = [
            [
                self._layout[y][x] if y < len(self._layout)
                and x < len(self._layout[y]) else True
                for x in range(width)
            ]
            for y in range(depth)
        ]
        self._update_layout_button()

    def _set_layout(self, layout: list[list[bool]]) -> None:
        """Validate and apply a new footprint mask."""
        self._layout = _normalize_grid_layout(
            self._nx.value(), self._ny.value(), layout)
        self._update_layout_button()

    def _update_layout_button(self) -> None:
        """Show the number of included grid cells in the layout action."""
        active = sum(cell for row in self._layout for cell in row)
        total = self._nx.value() * self._ny.value()
        self._layout_button.setText(
            tr("Edit footprint ({active}/{total} cells)").format(
                active=active, total=total))

    def _edit_layout(self) -> None:
        """Edit active cells in a small row-major grid dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Custom Gridfinity footprint"))
        dialog_layout = QVBoxLayout(dialog)
        tools = QHBoxLayout()
        select_all = QPushButton(tr("Select all"))
        clear_all = QPushButton(tr("Clear all"))
        tools.addWidget(select_all)
        tools.addWidget(clear_all)
        dialog_layout.addLayout(tools)
        cells = {}
        grid = QGridLayout()
        for y in range(self._ny.value()):
            for x in range(self._nx.value()):
                cell = QCheckBox()
                cell.setChecked(self._layout[y][x])
                cell.setToolTip(tr("Grid cell {x}, {y}").format(
                    x=x + 1, y=y + 1))
                cells[(x, y)] = cell
                grid.addWidget(cell, self._ny.value() - 1 - y, x)
        dialog_layout.addLayout(grid)
        select_all.clicked.connect(
            lambda: [cell.setChecked(True) for cell in cells.values()])
        clear_all.clicked.connect(
            lambda: [cell.setChecked(False) for cell in cells.values()])
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        layout = [
            [cells[(x, y)].isChecked() for x in range(self._nx.value())]
            for y in range(self._ny.value())
        ]
        try:
            self._set_layout(layout)
        except ValueError as exc:
            QMessageBox.warning(self, tr("Gridfinity Generator"), str(exc))

    def _update_variant_features(self) -> None:
        """Show only applicable controls and enforce dependent minimums."""
        is_bin = self._kind_value == "bin"
        is_parts = is_bin and self._variant_value == "parts"
        is_blank = is_bin and self._variant_value == "blank"
        self._set_option_visible(self._height, is_bin)
        self._set_option_visible(self._wall, is_bin and not is_blank)
        self._set_option_visible(self._bottom, is_bin and not is_blank)
        has_bin_magnets = is_bin and self._bottom.currentData() in {
            "magnet", "magnet_open", "screw_magnet"}
        self._set_option_visible(self._magnet_shape, has_bin_magnets)
        self._set_option_visible(self._bin_magnet_diameter, has_bin_magnets)
        self._set_option_visible(self._bin_magnet_depth, has_bin_magnets)
        has_crush_ribs = (
            has_bin_magnets
            and self._magnet_shape.currentData() == "crush_ribs")
        self._set_option_visible(self._crush_ribs_count, has_crush_ribs)
        self._set_option_visible(self._crush_ribs_waviness, has_crush_ribs)
        self._set_option_visible(self._stackable, is_bin and not is_blank)
        if (is_bin and self._variant_value == "eco"
                and self._wall.value() > 0.6):
            self._wall.setValue(0.6)
        if is_blank and self._bottom.currentData() == "magnet_open":
            self._bottom.setCurrentIndex(self._bottom.findData("magnet"))
        self._set_option_visible(self._divider_x, is_parts)
        self._set_option_visible(self._divider_y, is_parts)
        max_divider_units = self._height.value() - 1
        has_divider_space = max_divider_units >= 1
        if not has_divider_space:
            self._divider_x.setValue(0)
            self._divider_y.setValue(0)
        self._divider_height.setMaximum(max(1, max_divider_units))
        for height_spin in (
                self._divider_x_height, self._divider_y_height):
            height_spin.setMaximum(max(1, max_divider_units))
        self._set_option_visible(
            self._divider_height_row,
            is_parts and has_divider_space
            and not self._independent_divider_heights.isChecked())
        self._set_option_visible(
            self._independent_divider_heights,
            is_parts and has_divider_space)
        self._set_option_visible(
            self._divider_x_height_row,
            is_parts and has_divider_space
            and self._independent_divider_heights.isChecked()
            and self._divider_x.value() > 0)
        self._set_option_visible(
            self._divider_y_height_row,
            is_parts and has_divider_space
            and self._independent_divider_heights.isChecked()
            and self._divider_y.value() > 0)
        self._set_option_visible(self._divider_thickness, is_parts)
        self._set_option_visible(
            self._inside_fillet, is_bin and not is_blank)
        has_scoop = is_bin and not is_blank and self._scoop_enabled.isChecked()
        self._set_option_visible(self._scoop_enabled, is_bin and not is_blank)
        self._set_option_visible(self._scoop_radius, has_scoop)
        self._set_option_visible(self._scoop_corner_style, has_scoop)
        has_label_shelf = (
            is_bin and not is_blank
            and self._label_shelf_style.currentData() != "off")
        is_overhang_shelf = (
            has_label_shelf
            and self._label_shelf_style.currentData() == "overhang")
        self._set_option_visible(
            self._label_shelf_style, is_bin and not is_blank)
        self._set_option_visible(
            self._label_shelf_placement,
            has_label_shelf and not is_overhang_shelf)
        self._set_option_visible(self._label_shelf_width, has_label_shelf)
        self._set_option_visible(self._label_shelf_length, has_label_shelf)
        self._set_option_visible(
            self._label_shelf_angle,
            has_label_shelf and not is_overhang_shelf)
        self._set_option_visible(
            self._label_shelf_thickness, has_label_shelf)
        self._set_option_visible(self._recessed_top_depth, is_blank)
        magnet_baseplate = (
            not is_bin and self._variant_value in {"magnet", "magnet_open"})
        self._set_option_visible(
            self._baseplate_magnet_diameter, magnet_baseplate)
        self._set_option_visible(
            self._baseplate_magnet_shape, magnet_baseplate)
        has_baseplate_crush_ribs = (
            magnet_baseplate
            and self._baseplate_magnet_shape.currentData() == "crush_ribs")
        self._set_option_visible(
            self._baseplate_crush_ribs_count, has_baseplate_crush_ribs)
        self._set_option_visible(
            self._baseplate_crush_ribs_waviness, has_baseplate_crush_ribs)
        self._set_option_visible(
            self._baseplate_magnet_base_bore, magnet_baseplate)
        self._baseplate_magnet_base_chamfer.setMaximum(
            min(2.0, self._baseplate_magnet_base.value()))
        self._set_option_visible(
            self._baseplate_magnet_base_chamfer, magnet_baseplate)
        self._set_option_visible(
            self._baseplate_magnet_chamfer, magnet_baseplate)
        self._set_option_visible(
            self._baseplate_magnet_height, magnet_baseplate)
        self._set_option_visible(
            self._baseplate_magnet_base, magnet_baseplate)
        screw_together_supported = (
            not is_bin and self._variant_value in {"plain", "magnet_open"})
        self._set_option_visible(
            self._screw_together, screw_together_supported)
        if not screw_together_supported:
            self._screw_together.setChecked(False)
        screw_holes_visible = (
            screw_together_supported and self._screw_together.isChecked())
        self._set_option_visible(
            self._screw_hole_diameter, screw_holes_visible)
        magnet_base = (
            self._baseplate_magnet_base if magnet_baseplate else None)
        for base_spin, applicable in (
                (self._baseplate_base, not is_bin
                 and self._variant_value == "plain"),
                (magnet_base, magnet_baseplate)):
            if base_spin is None:
                continue
            minimum = (
                self._screw_hole_diameter.value()
                + _SCREW_HOLE_MINIMUM_BELOW_MM
                + _SCREW_HOLE_MINIMUM_ABOVE_MM
                if screw_holes_visible and applicable else 0.5)
            base_spin.setMinimum(minimum)
            self._set_option_visible(base_spin, applicable)

    def _update_divider_height_label(self, *_args) -> None:
        """Keep the divider's millimetre equivalent beside its U control."""
        height_mm = self._divider_height.value() * _UNIT_HEIGHT_MM
        self._divider_height_mm.setText(f"({height_mm:g} mm)")

    def _update_axis_divider_height_labels(self, *_args) -> None:
        """Update the X/Y independent height labels."""
        for spin, label in (
                (self._divider_x_height, self._divider_x_height_mm),
                (self._divider_y_height, self._divider_y_height_mm)):
            label.setText(f"({spin.value() * _UNIT_HEIGHT_MM:g} mm)")

    def _set_option_visible(self, field: QWidget, visible: bool) -> None:
        """Toggle a form control and the label owned by its form row."""
        label = self._options_form.labelForField(field)
        if label is not None:
            label.setVisible(visible)
        field.setVisible(visible)

    def _selected_top_level_groups(self) -> list[Group]:
        """Return selected scene groups eligible for whole-group replacement."""
        scene = getattr(self._viewport, "scene", None)
        if scene is None:
            return []
        return [
            entity for entity in scene.selection
            if isinstance(entity, Group) and entity in scene.groups
        ]

    def _on_scene_changed(self, *_args) -> None:
        """Load saved settings when one generated Gridfinity group is selected."""
        selected = self._selected_top_level_groups()
        if len(selected) != 1:
            self._editing_group = None
            self._model_status.setText(tr("Select a generated model to edit it."))
            self._create_button.setText(tr("Create model"))
            return

        group = selected[0]
        if group is self._editing_group:
            return
        scene = self._viewport.scene
        plugin_state = scene.plugin_data.get(
            _CreateGridfinityCommand._DATA_KEY, {})
        models = plugin_state.get("models", {}) if isinstance(
            plugin_state, dict) else {}
        parameters = models.get(group.uid) if isinstance(models, dict) else None
        if not isinstance(parameters, dict):
            self._editing_group = None
            self._model_status.setText(tr("Selected group is not a Gridfinity model."))
            self._create_button.setText(tr("Create model"))
            return

        if not self._load_parameters(parameters):
            return
        self._editing_group = group
        self._model_status.setText(tr("Editing selected Gridfinity model."))
        self._create_button.setText(tr("Update selected model"))

    def _load_parameters(self, parameters: dict) -> bool:
        """Restore saved generator settings into the sidebar controls."""
        try:
            schema_version = parameters.get("schema_version", 1)
            if schema_version not in (
                    1, 2, _CreateGridfinityCommand._PARAMETERS_SCHEMA):
                raise ValueError("Unsupported Gridfinity settings version.")
            self._select_variant(parameters["model"], parameters["kind"])
            self._nx.setValue(parameters["nx"])
            self._ny.setValue(parameters["ny"])
            layout = parameters.get(
                "layout",
                [[True] * self._nx.value()
                 for _ in range(self._ny.value())])
            self._set_layout(layout)
            self._placement.setCurrentIndex(self._placement.findData(
                parameters["centered"]))
            if parameters["model"] == "bin":
                self._height.setValue(parameters["height_units"])
                self._wall.setValue(parameters["wall_mm"])
                self._bottom.setCurrentIndex(self._bottom.findData(
                    parameters["bottom"]))
                self._magnet_shape.setCurrentIndex(
                    self._magnet_shape.findData(parameters["magnet_shape"]))
                self._bin_magnet_diameter.setValue(
                    parameters.get(
                        "bin_magnet_diameter_mm", _MAGNET_DIAMETER_MM))
                self._bin_magnet_depth.setValue(
                    parameters.get("bin_magnet_depth_mm", _MAGNET_DEPTH_MM))
                self._crush_ribs_count.setValue(parameters.get(
                    "crush_ribs_count", _BIN_CRUSH_RIBS_DEFAULT_COUNT))
                self._crush_ribs_waviness.setValue(parameters.get(
                    "crush_ribs_waviness",
                    _BIN_CRUSH_RIBS_DEFAULT_WAVINESS))
                self._inside_fillet.setValue(parameters.get(
                    "inside_fillet_mm", _BIN_INSIDE_FILLET_DEFAULT_MM))
                self._scoop_enabled.setChecked(
                    parameters.get("scoop", False))
                self._scoop_radius.setValue(parameters.get(
                    "scoop_radius_mm", _BIN_SCOOP_RADIUS_DEFAULT_MM))
                self._scoop_corner_style.setCurrentIndex(
                    self._scoop_corner_style.findData(
                        parameters.get("scoop_corner_style", "rounded")))
                self._label_shelf_style.setCurrentIndex(
                    self._label_shelf_style.findData(
                        parameters.get("label_shelf_style", "off")))
                self._label_shelf_placement.setCurrentIndex(
                    self._label_shelf_placement.findData(
                        parameters.get(
                            "label_shelf_placement", "center")))
                self._label_shelf_width.setValue(parameters.get(
                    "label_shelf_width_mm",
                    _LABEL_SHELF_WIDTH_DEFAULT_MM))
                self._label_shelf_length.setValue(parameters.get(
                    "label_shelf_length_mm",
                    _LABEL_SHELF_LENGTH_DEFAULT_MM))
                self._label_shelf_angle.setValue(parameters.get(
                    "label_shelf_angle_degrees",
                    _LABEL_SHELF_ANGLE_DEFAULT_DEGREES))
                self._label_shelf_thickness.setValue(parameters.get(
                    "label_shelf_thickness_mm",
                    _LABEL_SHELF_THICKNESS_DEFAULT_MM))
                self._recessed_top_depth.setValue(
                    parameters.get("recessed_top_depth_mm", 0.0))
                self._divider_thickness.setValue(parameters.get(
                    "divider_thickness_mm",
                    _BIN_DIVIDER_THICKNESS_DEFAULT_MM))
                self._stackable.setChecked(parameters["stackable"])
                self._divider_x.setValue(parameters["divider_x"])
                self._divider_y.setValue(parameters["divider_y"])
                self._divider_height.setValue(
                    max(1, round(parameters["divider_height_mm"]
                                 / _UNIT_HEIGHT_MM)))
                self._independent_divider_heights.setChecked(
                    parameters.get("independent_divider_heights", False))
                self._divider_x_height.setValue(max(1, round(
                    parameters.get(
                        "divider_x_height_mm",
                        parameters["divider_height_mm"])
                    / _UNIT_HEIGHT_MM)))
                self._divider_y_height.setValue(max(1, round(
                    parameters.get(
                        "divider_y_height_mm",
                        parameters["divider_height_mm"])
                    / _UNIT_HEIGHT_MM)))
            else:
                self._baseplate_magnet_diameter.setValue(
                    parameters["magnet_diameter_mm"])
                self._baseplate_magnet_shape.setCurrentIndex(
                    self._baseplate_magnet_shape.findData(
                        parameters.get("magnet_shape", "round")))
                self._baseplate_crush_ribs_count.setValue(parameters.get(
                    "crush_ribs_count", _BIN_CRUSH_RIBS_DEFAULT_COUNT))
                self._baseplate_crush_ribs_waviness.setValue(parameters.get(
                    "crush_ribs_waviness",
                    _BIN_CRUSH_RIBS_DEFAULT_WAVINESS))
                self._baseplate_magnet_base_bore.setValue(parameters.get(
                    "magnet_base_bore_diameter_mm",
                    _MAGNET_BASE_BORE_DIAMETER_MM))
                self._baseplate_magnet_base_chamfer.setValue(parameters.get(
                    "magnet_base_chamfer_depth_mm",
                    _BASEPLATE_MAGNET_BASE_CHAMFER_DEFAULT_MM))
                self._baseplate_magnet_chamfer.setValue(parameters.get(
                    "magnet_chamfer_depth_mm",
                    _BASEPLATE_MAGNET_CHAMFER_DEFAULT_MM))
                self._baseplate_magnet_height.setValue(
                    parameters["magnet_height_mm"])
                self._baseplate_magnet_base.setValue(
                    parameters["magnet_base_mm"])
                self._baseplate_base.setValue(
                    parameters["baseplate_base_mm"])
                self._screw_together.setChecked(
                    parameters["screw_together"])
                self._screw_hole_diameter.setValue(
                    parameters["screw_hole_diameter_mm"])
        except (KeyError, TypeError, ValueError):
            self._editing_group = None
            self._model_status.setText(
                tr("Saved Gridfinity settings are invalid; creating a new model."))
            self._create_button.setText(tr("Create model"))
            return False
        self._update_variant_features()
        return True

    def _current_parameters(self, nx: int, ny: int) -> dict:
        """Return JSON-safe settings matching the currently selected builder."""
        common = {
            "schema_version": _CreateGridfinityCommand._PARAMETERS_SCHEMA,
            "model": self._kind_value,
            "kind": self._variant_value,
            "nx": nx,
            "ny": ny,
            "centered": bool(self._placement.currentData()),
        }
        if self._kind_value == "bin":
            return {
                **common,
                "height_units": self._height.value(),
                "wall_mm": self._wall.value(),
                "bottom": self._bottom.currentData(),
                "stackable": self._stackable.isChecked(),
                "divider_x": self._divider_x.value(),
                "divider_y": self._divider_y.value(),
                "divider_height_mm": (
                    self._divider_height.value() * _UNIT_HEIGHT_MM),
                "divider_x_height_mm": (
                    self._divider_x_height.value() * _UNIT_HEIGHT_MM),
                "divider_y_height_mm": (
                    self._divider_y_height.value() * _UNIT_HEIGHT_MM),
                "independent_divider_heights":
                    self._independent_divider_heights.isChecked(),
                "magnet_shape": self._magnet_shape.currentData(),
                "bin_magnet_diameter_mm": self._bin_magnet_diameter.value(),
                "bin_magnet_depth_mm": self._bin_magnet_depth.value(),
                "crush_ribs_count": self._crush_ribs_count.value(),
                "crush_ribs_waviness":
                    self._crush_ribs_waviness.value(),
                "inside_fillet_mm": self._inside_fillet.value(),
                "scoop": self._scoop_enabled.isChecked(),
                "scoop_radius_mm": self._scoop_radius.value(),
                "scoop_corner_style": self._scoop_corner_style.currentData(),
                "label_shelf_style": self._label_shelf_style.currentData(),
                "label_shelf_placement":
                    self._label_shelf_placement.currentData(),
                "label_shelf_width_mm": self._label_shelf_width.value(),
                "label_shelf_length_mm": self._label_shelf_length.value(),
                "label_shelf_angle_degrees":
                    self._label_shelf_angle.value(),
                "label_shelf_thickness_mm":
                    self._label_shelf_thickness.value(),
                "recessed_top_depth_mm": self._recessed_top_depth.value(),
                "divider_thickness_mm": self._divider_thickness.value(),
                "layout": [list(row) for row in self._layout],
            }
        return {
            **common,
            "magnet_diameter_mm": self._baseplate_magnet_diameter.value(),
            "magnet_shape": self._baseplate_magnet_shape.currentData(),
            "crush_ribs_count":
                self._baseplate_crush_ribs_count.value(),
            "crush_ribs_waviness":
                self._baseplate_crush_ribs_waviness.value(),
            "magnet_base_bore_diameter_mm":
                self._baseplate_magnet_base_bore.value(),
            "magnet_base_chamfer_depth_mm":
                self._baseplate_magnet_base_chamfer.value(),
            "magnet_chamfer_depth_mm":
                self._baseplate_magnet_chamfer.value(),
            "magnet_height_mm": self._baseplate_magnet_height.value(),
            "magnet_base_mm": self._baseplate_magnet_base.value(),
            "screw_together": self._screw_together.isChecked(),
            "baseplate_base_mm": self._baseplate_base.value(),
            "screw_hole_diameter_mm": self._screw_hole_diameter.value(),
            "layout": [list(row) for row in self._layout],
        }

    def _create(self) -> None:
        """Build the selected model and execute its scene change in history."""
        nx, ny = self._nx.value(), self._ny.value()
        try:
            self._update_variant_features()
            replace_groups = self._selected_top_level_groups()
            parameters = self._current_parameters(nx, ny)
            if self._kind_value == "bin":
                group = _build_bin(nx, ny, self._height.value(),
                                   self._wall.value(),
                                   kind=self._variant_value,
                                   bottom=self._bottom.currentData(),
                                   stackable=self._stackable.isChecked(),
                                   divider_x=self._divider_x.value(),
                                   divider_y=self._divider_y.value(),
                                   divider_height_mm=(
                                       self._divider_height.value()
                                       * _UNIT_HEIGHT_MM),
                                   divider_x_height_mm=(
                                       self._divider_x_height.value()
                                       * _UNIT_HEIGHT_MM
                                       if self._independent_divider_heights
                                       .isChecked() else None),
                                   divider_y_height_mm=(
                                       self._divider_y_height.value()
                                       * _UNIT_HEIGHT_MM
                                       if self._independent_divider_heights
                                       .isChecked() else None),
                                   magnet_shape=self._magnet_shape.currentData(),
                                   magnet_diameter_mm=(
                                       self._bin_magnet_diameter.value()),
                                   magnet_depth_mm=(
                                       self._bin_magnet_depth.value()),
                                   crush_ribs_count=(
                                       self._crush_ribs_count.value()),
                                   crush_ribs_waviness=(
                                       self._crush_ribs_waviness.value()),
                                   centered=bool(self._placement.currentData()),
                                   layout=self._layout,
                                   recessed_top_depth_mm=(
                                       self._recessed_top_depth.value()),
                                   inside_fillet_mm=self._inside_fillet.value(),
                                   scoop=self._scoop_enabled.isChecked(),
                                   scoop_radius_mm=self._scoop_radius.value(),
                                   scoop_corner_style=(
                                       self._scoop_corner_style.currentData()),
                                   label_shelf_style=(
                                       self._label_shelf_style.currentData()),
                                   label_shelf_placement=(
                                       self._label_shelf_placement
                                       .currentData()),
                                   label_shelf_width_mm=(
                                       self._label_shelf_width.value()),
                                   label_shelf_length_mm=(
                                       self._label_shelf_length.value()),
                                   label_shelf_angle_degrees=(
                                       self._label_shelf_angle.value()),
                                   label_shelf_thickness_mm=(
                                       self._label_shelf_thickness.value()),
                                   divider_thickness_mm=(
                                       self._divider_thickness.value()))
            else:
                group = _build_baseplate(
                    nx, ny, kind=self._variant_value,
                    centered=bool(self._placement.currentData()),
                    magnet_diameter_mm=self._baseplate_magnet_diameter.value(),
                    magnet_height_mm=self._baseplate_magnet_height.value(),
                    magnet_base_mm=self._baseplate_magnet_base.value(),
                    screw_together=self._screw_together.isChecked(),
                    baseplate_base_mm=self._baseplate_base.value(),
                    screw_hole_diameter_mm=(
                        self._screw_hole_diameter.value()),
                    layout=self._layout,
                    magnet_shape=self._baseplate_magnet_shape.currentData(),
                    crush_ribs_count=(
                        self._baseplate_crush_ribs_count.value()),
                    crush_ribs_waviness=(
                        self._baseplate_crush_ribs_waviness.value()),
                    magnet_base_bore_diameter_mm=(
                        self._baseplate_magnet_base_bore.value()),
                    magnet_chamfer_depth_mm=(
                        self._baseplate_magnet_chamfer.value()),
                    magnet_base_chamfer_depth_mm=(
                        self._baseplate_magnet_base_chamfer.value()))
            history = self._viewport.history
            replace_group = None
            if (self._replace_selected.isChecked()
                    and len(replace_groups) == 1):
                replace_group = replace_groups[0]
            history.execute(_CreateGridfinityCommand(
                group, parameters, old_group=replace_group))
            if history.last_error:
                QMessageBox.critical(
                    self, tr("Gridfinity Generator"), history.last_error)
                return
            self._editing_group = group
            self._model_status.setText(tr("Editing selected Gridfinity model."))
            self._create_button.setText(tr("Update selected model"))
            self._viewport.notify_scene_changed()
        except (RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, tr("Gridfinity Generator"), str(exc))


def setup(app) -> None:
    """Register the Gridfinity sidebar and an Extensions-menu shortcut."""
    panel = GridfinityPanel(app.viewport)
    dock = app.add_panel(tr("Gridfinity"), panel)
    app.add_menu_action(
        tr("Gridfinity Generator"), lambda: app.show_panel(dock))
