"""PolyScript CLI - the `poly` command."""

import argparse
import json
import sys
from pathlib import Path

from .executor import compile_source, execute, export
from .errors import PolyScriptError


def _parse_cli_value(s: str):
    """Infer a typed value from a CLI string.

    Order: bool > int > float > str.
    """
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _build_overrides(defines: list[str], params_file: Path | None) -> dict[str, object]:
    """Combine --params-file and -D defines into a single overrides dict.

    CLI -D flags take precedence over the JSON file.
    """
    overrides: dict[str, object] = {}

    if params_file is not None:
        if not params_file.exists():
            print(f"Error: params file not found: {params_file}", file=sys.stderr)
            sys.exit(2)
        try:
            data = json.loads(params_file.read_text())
        except json.JSONDecodeError as e:
            print(f"Error: failed to parse {params_file}: {e}", file=sys.stderr)
            sys.exit(2)
        if not isinstance(data, dict):
            print(f"Error: {params_file} must contain a JSON object", file=sys.stderr)
            sys.exit(2)
        overrides.update(data)

    for define in defines:
        if "=" not in define:
            print(
                f"Error: -D expects NAME=VALUE (got: {define!r})",
                file=sys.stderr,
            )
            sys.exit(2)
        name, _, raw_value = define.partition("=")
        name = name.strip()
        if not name:
            print(f"Error: -D expects NAME=VALUE (got: {define!r})", file=sys.stderr)
            sys.exit(2)
        overrides[name] = _parse_cli_value(raw_value)

    return overrides


def _warn_unknown_params(source: str, overrides: dict[str, object]) -> None:
    """Emit a stderr warning for override keys not assigned in the source."""
    if not overrides:
        return
    # Lightweight scan: look for top-level `name =` patterns. This is a
    # conservative best-effort — false positives (e.g. assignments inside
    # `def` bodies) are OK, we just want to catch obvious typos.
    import re

    assigned = set(re.findall(r"^\s*(\$?[A-Za-z_][A-Za-z_0-9]*)\s*=", source, re.M))
    # Strip leading $ for comparison so both `x = 1` and `$x = 1` match.
    assigned_plain = {n.lstrip("$") for n in assigned}
    for name in overrides:
        if name.lstrip("$") not in assigned_plain:
            print(
                f"Warning: -D {name}: no top-level assignment found in input",
                file=sys.stderr,
            )


def main():
    parser = argparse.ArgumentParser(
        prog="poly",
        description="PolyScript - Parametric CAD DSL compiler",
    )
    parser.add_argument("input", help="Input .poly file")
    parser.add_argument(
        "-o", "--output",
        help="Output file (.stl, .step, or .py). Default: ./<input>.stl",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print B-Rep info (bbox, volume, topology)",
    )
    parser.add_argument(
        "-D", "--define",
        action="append", dest="defines", default=[],
        metavar="NAME=VALUE",
        help="Override parameter (repeatable: -D width=100 -D height=50)",
    )
    parser.add_argument(
        "--params-file", type=Path,
        help="JSON file with parameter overrides (merged with -D; -D takes precedence)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    source = input_path.read_text()
    overrides = _build_overrides(args.defines, args.params_file)
    _warn_unknown_params(source, overrides)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(input_path.stem + ".stl")

    try:
        source_dir = input_path.parent

        if output_path.suffix == ".py":
            code = compile_source(source, source_dir=source_dir, overrides=overrides)
            output_path.write_text(code)
            print(f"Generated: {output_path}")
        else:
            result = execute(source, source_dir=source_dir, overrides=overrides)
            if result is None:
                print("No geometry to export (library-only file)")
            else:
                if args.verbose:
                    from .ocp_kernel import shape_info
                    info = shape_info(result._shape)
                    bbox = info["bbox"]
                    topo = info["topology"]
                    print(f"bbox: {bbox['min']} - {bbox['max']}")
                    print(f"volume: {info['volume']:.2f}")
                    print(f"topology: {topo['faces']} faces, {topo['edges']} edges, {topo['vertices']} vertices")
                export(result, str(output_path))
                print(f"Exported: {output_path}")

    except PolyScriptError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Internal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
