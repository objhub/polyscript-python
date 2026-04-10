# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PolyScript CLI (onedir mode)."""

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

block_cipher = None

# Collect OCP bindings and OCCT native libraries
ocp_datas, ocp_binaries, ocp_hiddenimports = collect_all('OCP')
_, ocp_libs_binaries, _ = collect_all('cadquery_ocp')

# OCP submodules used by polyscript (top-level + lazy imports)
ocp_modules = [
    'OCP.gp', 'OCP.BRepPrimAPI', 'OCP.BRepAlgoAPI', 'OCP.BRepFilletAPI',
    'OCP.BRepOffsetAPI', 'OCP.BRepTools', 'OCP.BRepBuilderAPI',
    'OCP.TopoDS', 'OCP.TopExp', 'OCP.TopAbs', 'OCP.TopLoc',
    'OCP.BRep', 'OCP.BRepBndLib', 'OCP.Bnd', 'OCP.BRepGProp',
    'OCP.GProp', 'OCP.GC', 'OCP.Geom', 'OCP.GeomAPI',
    'OCP.TopTools', 'OCP.TColgp', 'OCP.ShapeAnalysis',
    'OCP.BRepAdaptor', 'OCP.GeomAbs',
    # lazy imports
    'OCP.Geom2d', 'OCP.GCE2d', 'OCP.BRepLib',
    'OCP.StlAPI', 'OCP.BRepMesh',
    'OCP.STEPControl', 'OCP.Interface',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=ocp_binaries + ocp_libs_binaries,
    datas=[
        ('src/polyscript/grammar.lark', 'polyscript'),
    ] + ocp_datas,
    hiddenimports=[
        'polyscript',
        'polyscript.cli',
        'polyscript.parser',
        'polyscript.transformer',
        'polyscript.codegen',
        'polyscript.codegen_ocp',
        'polyscript.ocp_kernel',
        'polyscript.ast_nodes',
        'polyscript.errors',
        'polyscript.executor',
        'polyscript.colors',
        'polyscript.params',
        'lark',
    ] + ocp_modules + ocp_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'PIL', 'scipy', 'numpy',
        'cadquery',
        'pytest', 'coverage', 'pytest_cov',
        'vtkmodules',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='poly',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    name='poly',
)
