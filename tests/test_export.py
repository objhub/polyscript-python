"""Tests for OFF, glTF and GLB export (O10)."""

import json
import os
import tempfile

import pytest

from polyscript.ocp_kernel import Workplane, exporters


class TestOFFExport:
    """OFF (Object File Format) export tests."""

    def test_off_basic(self, tmp_path):
        """A simple box exports to a valid OFF file."""
        wp = Workplane("XY").box(10, 20, 30)
        out = str(tmp_path / "box.off")
        exporters.export(wp, out)

        assert os.path.exists(out)
        lines = open(out).readlines()
        assert lines[0].strip() == "OFF"
        # Second line: num_vertices num_faces 0
        parts = lines[1].strip().split()
        nv, nf = int(parts[0]), int(parts[1])
        assert nv > 0
        assert nf > 0
        # Verify vertex lines
        for i in range(2, 2 + nv):
            coords = lines[i].strip().split()
            assert len(coords) == 3
            for c in coords:
                float(c)  # must be valid floats
        # Verify face lines
        for i in range(2 + nv, 2 + nv + nf):
            parts = lines[i].strip().split()
            assert int(parts[0]) == 3  # triangular faces
            for idx_str in parts[1:4]:
                idx = int(idx_str)
                assert 0 <= idx < nv

    def test_off_file_size(self, tmp_path):
        """OFF output for a sphere has reasonable size."""
        wp = Workplane("XY").sphere(5)
        out = str(tmp_path / "sphere.off")
        exporters.export(wp, out)
        size = os.path.getsize(out)
        assert size > 100  # non-trivial content

    def test_coff_with_color(self, tmp_path):
        """When the shape has color metadata, export uses COFF header."""
        wp = Workplane("XY").box(10, 10, 10).setColor(1.0, 0.0, 0.0)
        out = str(tmp_path / "red_box.off")
        exporters.export(wp, out)

        lines = open(out).readlines()
        assert lines[0].strip() == "COFF"
        # Parse header
        parts = lines[1].strip().split()
        nv, nf = int(parts[0]), int(parts[1])
        # Face lines should have RGBA appended
        face_line = lines[2 + nv].strip().split()
        # "3 i0 i1 i2 R G B A" => 8 tokens
        assert len(face_line) == 8
        r, g, b, a = int(face_line[4]), int(face_line[5]), int(face_line[6]), int(face_line[7])
        assert r == 255
        assert g == 0
        assert b == 0
        assert a == 255

    def test_off_no_color(self, tmp_path):
        """Without color metadata, header is plain OFF."""
        wp = Workplane("XY").box(5, 5, 5)
        out = str(tmp_path / "box_noclr.off")
        exporters.export(wp, out)
        lines = open(out).readlines()
        assert lines[0].strip() == "OFF"

    def test_off_reparse(self, tmp_path):
        """Basic structural re-parse of exported OFF file."""
        wp = Workplane("XY").cylinder(5, 10)
        out = str(tmp_path / "cyl.off")
        exporters.export(wp, out)

        with open(out) as f:
            header = f.readline().strip()
            assert header in ("OFF", "COFF")
            nv, nf, _ = f.readline().strip().split()
            nv, nf = int(nv), int(nf)
            verts = []
            for _ in range(nv):
                xyz = f.readline().strip().split()
                verts.append(tuple(float(c) for c in xyz[:3]))
            faces = []
            for _ in range(nf):
                parts = f.readline().strip().split()
                n = int(parts[0])
                indices = [int(x) for x in parts[1:1 + n]]
                faces.append(indices)

        assert len(verts) == nv
        assert len(faces) == nf
        # All indices should reference valid vertices
        for face in faces:
            for idx in face:
                assert 0 <= idx < nv


class TestGLTFExport:
    """glTF / GLB export tests."""

    def test_glb_basic(self, tmp_path):
        """A box exports to a non-empty GLB file."""
        wp = Workplane("XY").box(10, 20, 30)
        out = str(tmp_path / "box.glb")
        exporters.export(wp, out)

        assert os.path.exists(out)
        size = os.path.getsize(out)
        assert size > 100  # must contain mesh data

        # GLB magic bytes: 0x46546C67 ("glTF")
        with open(out, "rb") as f:
            magic = f.read(4)
        assert magic == b"glTF"

    def test_gltf_basic(self, tmp_path):
        """A box exports to a valid JSON glTF file."""
        wp = Workplane("XY").box(10, 20, 30)
        out = str(tmp_path / "box.gltf")
        exporters.export(wp, out)

        assert os.path.exists(out)
        with open(out) as f:
            data = json.load(f)
        assert "asset" in data
        assert "meshes" in data
        assert len(data["meshes"]) > 0

    def test_gltf_with_color(self, tmp_path):
        """Color metadata appears as a glTF material."""
        wp = Workplane("XY").box(10, 10, 10).setColor(0.0, 1.0, 0.0)
        out = str(tmp_path / "green_box.gltf")
        exporters.export(wp, out)

        with open(out) as f:
            data = json.load(f)
        assert "materials" in data
        mat = data["materials"][0]
        pbr = mat.get("pbrMetallicRoughness", {})
        color = pbr.get("baseColorFactor", [])
        # Green channel should be 1.0
        assert len(color) == 4
        assert color[1] == pytest.approx(1.0, abs=0.01)

    def test_glb_sphere(self, tmp_path):
        """Sphere exports to a reasonably-sized GLB."""
        wp = Workplane("XY").sphere(5)
        out = str(tmp_path / "sphere.glb")
        exporters.export(wp, out)
        size = os.path.getsize(out)
        assert size > 500  # sphere has many triangles

    def test_gltf_format_detection(self, tmp_path):
        """Format is auto-detected from file extension."""
        wp = Workplane("XY").box(5, 5, 5)
        for ext in (".gltf", ".glb", ".off"):
            out = str(tmp_path / f"test{ext}")
            exporters.export(wp, out)
            assert os.path.exists(out)
            assert os.path.getsize(out) > 0


class TestExportUnsupported:
    """Edge cases for export."""

    def test_unsupported_format(self, tmp_path):
        wp = Workplane("XY").box(5, 5, 5)
        with pytest.raises(ValueError, match="Unsupported"):
            exporters.export(wp, str(tmp_path / "box.xyz"))
