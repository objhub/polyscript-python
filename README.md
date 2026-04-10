# PolyScript

A pipe-based parametric CAD language built on OpenCascade that exports STL/STEP files.

```
box 80 60 10
 | fillet 2
 | diff cylinder 10 10
 | faces top | offset -5 | verts | hole 2
```

## Features

- **Pipe syntax** -- chain operations with `|` for readable modeling workflows
- **OCP backend** -- OpenCascade kernel via OCP
- **Functions** -- define reusable parametric shapes with `def`
- **Import** -- split libraries into separate `.poly` files
- **Expressions** -- arithmetic, comparisons, `if/then/else`, list comprehensions
- **Export** -- STL, STEP, or Python code

## Download

https://github.com/objhub/polyscript-python/releases


## Quick Start

Create `hello.poly`:

```
box 30 20 10 | fillet 2
```

Build:

```bash
poly hello.poly                     # → hello.stl (default)
poly hello.poly -o hello.step       # export STEP
poly hello.poly -o hello.py         # export Python code
```

## Examples

### Parametric function

```
def standoff(r, h, hole_r) = cylinder h r | diff cylinder h hole_r

box 80 60 3
 | fillet 1
 | union standoff 4 10 1.5 at:[(10, 10), (70, 10), (10, 50), (70, 50)]
```

### Hex nut (list comprehension + math)

```
r = 10
polygon [(r * cos(rad(60 * i)), r * sin(rad(60 * i)))
         for i in range(6)]
 | extrude 8
 | diff cylinder 10 4
 | faces ">Z" | chamfer 1
 | faces "<Z" | chamfer 1
```

### Spur gear (import library)

```
import "gear"

spur_gear 12 2
 | extrude 8
 | diff cylinder 8 3
 | faces ">Z" | chamfer 0.5
```

### Threaded bolt

```
pitch = 1.5
depth = 0.6134 * pitch
r = 4
h = 25

path = helix pitch h r
groove = polygon [(0, -pitch/3), (-depth*1.5, 0), (0, pitch/3)]
shaft = cylinder h r | diff (groove | sweep path)

hr = 8
head = polygon [(hr * cos(rad(60 * i)), hr * sin(rad(60 * i)))
                for i in range(6)]
 | extrude 6
 | faces ">Z" | chamfer 2

[head, shaft]
```

### Flanged pipe with bolt holes

```
cylinder 5 25
 | faces ">Z" | workplane
 | circle 15 | extrude 30
 | diff cylinder 40 12
 | faces "<Z" | workplane
 | points (polar 6 20)
 | hole 5 depth:5
```

## Documentation

- [PolyScript User Document](https://polyscript.objhub.org)

## CLI

```
poly <input.poly> [-o <output>]
```

| Flag | Description |
|------|-------------|
| `-o file.stl` | Export as STL |
| `-o file.step` | Export as STEP |
| `-o file.py` | Export as Python code |

Default output is `<input>.stl`.

## License

MIT
