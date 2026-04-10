"""PolyScript CLI - the `poly` command."""

import argparse
import sys
from pathlib import Path

from .executor import compile_source, execute, export
from .errors import PolyScriptError


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
        "--dump-code",
        action="store_true",
        help="Print generated code to stdout",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    source = input_path.read_text()

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(input_path.stem + ".stl")

    try:
        source_dir = input_path.parent

        if args.dump_code:
            code = compile_source(source, source_dir=source_dir)
            print(code)
            return

        if output_path.suffix == ".py":
            code = compile_source(source, source_dir=source_dir)
            output_path.write_text(code)
            print(f"Generated: {output_path}")
        else:
            result = execute(source, source_dir=source_dir)
            if result is None:
                print(f"No geometry to export (library-only file)")
            else:
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
