"""Tests for @param annotation feature."""

import json
import pytest

from polyscript.params import (
    parse_param_options,
    extract_params,
    ParamInfo,
    ParamSet,
    attach_param_annotations,
    _eval_default,
)
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript.executor import compile_source
from polyscript import ast_nodes as ast


# ---------------------------------------------------------------------------
# parse_param_options
# ---------------------------------------------------------------------------

class TestParseParamOptions:
    def test_empty(self):
        opts = parse_param_options("")
        assert opts == {}

    def test_range_two_part(self):
        opts = parse_param_options("1..100")
        assert opts == {"min": 1, "max": 100}

    def test_range_three_part(self):
        opts = parse_param_options("1..100..0.5")
        assert opts == {"min": 1, "max": 100, "step": 0.5}

    def test_range_negative(self):
        opts = parse_param_options("-10..10..1")
        assert opts == {"min": -10, "max": 10, "step": 1}

    def test_range_float(self):
        opts = parse_param_options("0.1..9.9..0.1")
        assert opts["min"] == pytest.approx(0.1)
        assert opts["max"] == pytest.approx(9.9)
        assert opts["step"] == pytest.approx(0.1)

    def test_key_value_pairs(self):
        opts = parse_param_options('min:1 max:100 step:0.5 desc:"Wall thickness"')
        assert opts["min"] == 1
        assert opts["max"] == 100
        assert opts["step"] == 0.5
        assert opts["desc"] == "Wall thickness"

    def test_range_with_options(self):
        opts = parse_param_options('1..100 desc:"Height" group:"Dimensions"')
        assert opts["min"] == 1
        assert opts["max"] == 100
        assert opts["desc"] == "Height"
        assert opts["group"] == "Dimensions"

    def test_choices(self):
        opts = parse_param_options('choices:["M3","M4","M5"]')
        assert opts["choices"] == ["M3", "M4", "M5"]

    def test_type_explicit(self):
        opts = parse_param_options('type:"int"')
        assert opts["type"] == "int"

    def test_hidden(self):
        opts = parse_param_options("hidden:true")
        assert opts["hidden"] is True

    def test_hidden_false(self):
        opts = parse_param_options("hidden:false")
        assert opts["hidden"] is False

    def test_group(self):
        opts = parse_param_options('group:"Advanced"')
        assert opts["group"] == "Advanced"


# ---------------------------------------------------------------------------
# AST integration: @param lines are extracted and attached
# ---------------------------------------------------------------------------

class TestParamAnnotationAST:
    def test_single_param_annotation(self):
        source = '@param min:1 max:100\n$thickness = 2.0'
        tree = parse(source)
        program = transform(tree)
        # The transform should have attached the annotation
        assignments = [s for s in program.statements if isinstance(s, ast.Assignment)]
        assert len(assignments) == 1
        assert assignments[0].name == "thickness"
        assert assignments[0].annotation is not None
        assert assignments[0].annotation.options["min"] == 1
        assert assignments[0].annotation.options["max"] == 100

    def test_multiple_param_annotations(self):
        source = (
            '@param 1..100\n'
            '$width = 10\n'
            '@param 1..50 desc:"Height"\n'
            '$height = 20\n'
        )
        tree = parse(source)
        program = transform(tree)
        assignments = [s for s in program.statements if isinstance(s, ast.Assignment)]
        assert len(assignments) == 2

        assert assignments[0].name == "width"
        assert assignments[0].annotation is not None
        assert assignments[0].annotation.options["min"] == 1
        assert assignments[0].annotation.options["max"] == 100

        assert assignments[1].name == "height"
        assert assignments[1].annotation is not None
        assert assignments[1].annotation.options["min"] == 1
        assert assignments[1].annotation.options["max"] == 50
        assert assignments[1].annotation.options["desc"] == "Height"

    def test_assignment_without_annotation(self):
        source = '$width = 10\n$height = 20'
        tree = parse(source)
        program = transform(tree)
        assignments = [s for s in program.statements if isinstance(s, ast.Assignment)]
        for a in assignments:
            assert a.annotation is None

    def test_mixed_annotated_and_plain(self):
        source = (
            '$plain = 5\n'
            '@param 1..100\n'
            '$annotated = 10\n'
            '$another_plain = 15\n'
        )
        tree = parse(source)
        program = transform(tree)
        assignments = [s for s in program.statements if isinstance(s, ast.Assignment)]
        assert len(assignments) == 3
        assert assignments[0].name == "plain"
        assert assignments[0].annotation is None
        assert assignments[1].name == "annotated"
        assert assignments[1].annotation is not None
        assert assignments[2].name == "another_plain"
        assert assignments[2].annotation is None

    def test_param_with_pipeline_after(self):
        """@param followed by assignment, then a pipeline statement."""
        source = (
            '@param 1..100\n'
            '$size = 10\n'
            'box $size $size $size\n'
        )
        tree = parse(source)
        program = transform(tree)
        assignments = [s for s in program.statements if isinstance(s, ast.Assignment)]
        assert len(assignments) == 1
        assert assignments[0].annotation is not None


# ---------------------------------------------------------------------------
# extract_params API
# ---------------------------------------------------------------------------

class TestExtractParams:
    def test_basic_extraction(self):
        source = '@param min:1 max:100 step:0.5 desc:"Wall thickness"\n$thickness = 2.5'
        result = extract_params(source)
        assert len(result.params) == 1
        p = result.params[0]
        assert p.name == "thickness"
        assert p.default == 2.5
        assert p.min == 1
        assert p.max == 100
        assert p.step == 0.5
        assert p.desc == "Wall thickness"
        assert p.type == "float"
        assert p.group == "General"
        assert p.hidden is False

    def test_int_default_type_inference(self):
        source = '@param 1..100\n$count = 5'
        result = extract_params(source)
        assert result.params[0].type == "int"
        assert result.params[0].default == 5

    def test_string_default(self):
        source = '@param choices:["M3","M4"]\n$screw = "M3"'
        result = extract_params(source)
        p = result.params[0]
        assert p.type == "string"
        assert p.default == "M3"
        assert p.choices == ["M3", "M4"]

    def test_bool_default(self):
        source = '@param type:"bool"\n$enabled = true'
        result = extract_params(source)
        p = result.params[0]
        assert p.type == "bool"
        assert p.default is True

    def test_negative_default(self):
        source = '@param -100..100\n$ofs = -5'
        result = extract_params(source)
        p = result.params[0]
        assert p.default == -5

    def test_expression_default(self):
        source = '@param 0..100\n$val = 2 + 3'
        result = extract_params(source)
        assert result.params[0].default == 5

    def test_multiple_params(self):
        source = (
            '@param 1..200 desc:"Width"\n'
            '$w = 80\n'
            '@param 1..200 desc:"Height"\n'
            '$h = 60\n'
            '@param 1..50\n'
            '$d = 10\n'
        )
        result = extract_params(source)
        assert len(result.params) == 3
        assert result.params[0].name == "w"
        assert result.params[1].name == "h"
        assert result.params[2].name == "d"

    def test_no_params(self):
        source = '$w = 80\nbox $w 60 10'
        result = extract_params(source)
        assert len(result.params) == 0

    def test_range_shorthand_with_desc(self):
        source = '@param 1..100..0.5 desc:"Height" group:"Dimensions"\n$height = 50'
        result = extract_params(source)
        p = result.params[0]
        assert p.min == 1
        assert p.max == 100
        assert p.step == 0.5
        assert p.desc == "Height"
        assert p.group == "Dimensions"

    def test_explicit_type_override(self):
        source = '@param type:"float"\n$val = 5'
        result = extract_params(source)
        assert result.params[0].type == "float"  # explicit override, not "int"


# ---------------------------------------------------------------------------
# JSON merge
# ---------------------------------------------------------------------------

class TestJSONMerge:
    def test_json_overrides_metadata(self):
        source = '@param min:1 max:100\n$thickness = 2.0'
        json_data = json.dumps({
            "params": {
                "thickness": {
                    "min": 0.5,
                    "max": 200,
                    "desc": "From JSON",
                }
            }
        })
        result = extract_params(source, json_str=json_data)
        p = result.params[0]
        assert p.min == 0.5  # JSON overrides source
        assert p.max == 200
        assert p.desc == "From JSON"

    def test_json_default_override(self):
        source = '@param 1..100\n$val = 10'
        json_data = json.dumps({
            "params": {"val": {"default": 42}}
        })
        result = extract_params(source, json_str=json_data)
        assert result.params[0].default == 42

    def test_json_ignores_unknown_params(self):
        source = '@param 1..100\n$val = 10'
        json_data = json.dumps({
            "params": {"nonexistent": {"min": 0, "max": 999}}
        })
        result = extract_params(source, json_str=json_data)
        assert len(result.params) == 1
        assert result.params[0].name == "val"

    def test_json_parameter_sets(self):
        source = '@param 1..100\n$val = 10'
        json_data = json.dumps({
            "parameterSets": {
                "small": {"val": 5},
                "large": {"val": 95},
            }
        })
        result = extract_params(source, json_str=json_data)
        assert "small" in result.parameter_sets
        assert result.parameter_sets["small"]["val"] == 5
        assert result.parameter_sets["large"]["val"] == 95

    def test_json_params_as_list(self):
        source = '@param 1..100\n$val = 10'
        json_data = json.dumps({
            "params": [
                {"name": "val", "desc": "From list format"}
            ]
        })
        result = extract_params(source, json_str=json_data)
        assert result.params[0].desc == "From list format"


# ---------------------------------------------------------------------------
# Overrides in compile_source
# ---------------------------------------------------------------------------

class TestOverrides:
    def test_override_numeric(self):
        source = '@param 1..100\n$w = 80\nbox $w 60 10'
        code = compile_source(source, overrides={"w": 42})
        assert "w = 42" in code

    def test_override_float(self):
        source = '@param 0.1..10.0\n$r = 5.0\nsphere $r'
        code = compile_source(source, overrides={"r": 3.14})
        assert "r = 3.14" in code

    def test_override_string(self):
        source = '@param choices:["M3","M4"]\n$screw = "M3"'
        code = compile_source(source, overrides={"screw": "M4"})
        assert "screw = 'M4'" in code or 'screw = "M4"' in code

    def test_override_negative(self):
        source = '@param -100..100\n$ofs = 0'
        code = compile_source(source, overrides={"ofs": -10})
        assert "ofs = -(10)" in code or "ofs = -10" in code or "ofs = (-10)" in code

    def test_override_preserves_other_vars(self):
        source = '$a = 1\n$b = 2\nbox $a $b 10'
        code = compile_source(source, overrides={"a": 99})
        assert "a = 99" in code
        assert "b = 2" in code

    def test_override_nonexistent_is_ignored(self):
        source = '$w = 80\nbox $w 60 10'
        code = compile_source(source, overrides={"nonexistent": 999})
        assert "w = 80" in code
        # No crash, nonexistent is just ignored

    def test_override_bool(self):
        source = '@param type:"bool"\n$enabled = true'
        code = compile_source(source, overrides={"enabled": False})
        assert "enabled = False" in code

    def test_no_overrides(self):
        source = '$w = 80\nbox $w 60 10'
        code = compile_source(source)
        assert "w = 80" in code


# ---------------------------------------------------------------------------
# Evaluator ignores annotations
# ---------------------------------------------------------------------------

class TestEvaluatorIgnoresAnnotation:
    """Verify that @param annotations don't affect code generation."""

    def test_codegen_unaffected(self):
        source_plain = '$thickness = 2.0\nbox $thickness 60 10'
        source_annotated = '@param min:1 max:100\n$thickness = 2.0\nbox $thickness 60 10'
        code_plain = compile_source(source_plain)
        code_annotated = compile_source(source_annotated)
        assert code_plain == code_annotated


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_param_before_non_assignment_is_skipped(self):
        """@param before a non-assignment (e.g., pipeline) should not crash."""
        source = '@param 1..100\nbox 10 10 10'
        # Should not crash, annotation is just orphaned
        tree = parse(source)
        program = transform(tree)
        # No assignments, so annotation is not attached
        assignments = [s for s in program.statements if isinstance(s, ast.Assignment)]
        assert len(assignments) == 0

    def test_param_with_comment_after(self):
        source = '@param 1..100  # this is a range\n$val = 50'
        # The comment should be handled by the Lark COMMENT token
        # but @param is extracted before Lark, so the comment is part of the raw text.
        # We need to handle this.
        result = extract_params(source)
        assert len(result.params) == 1
        assert result.params[0].min == 1
        assert result.params[0].max == 100

    def test_param_annotation_without_dollar(self):
        """@param should match variable without $ prefix."""
        source = '@param 1..100\nwidth = 80'
        tree = parse(source)
        program = transform(tree)
        assignments = [s for s in program.statements if isinstance(s, ast.Assignment)]
        assert len(assignments) == 1
        assert assignments[0].name == "width"
        assert assignments[0].annotation is not None
        assert assignments[0].annotation.options["min"] == 1
        assert assignments[0].annotation.options["max"] == 100

    def test_extract_params_without_dollar(self):
        """extract_params should work with variables without $ prefix."""
        source = '@param 1..200 desc:"Width"\nwidth = 80'
        result = extract_params(source)
        assert len(result.params) == 1
        assert result.params[0].name == "width"
        assert result.params[0].default == 80
        assert result.params[0].desc == "Width"

    def test_mixed_dollar_and_no_dollar_params(self):
        """@param should work with a mix of $ and non-$ variables."""
        source = (
            '@param 1..200\n'
            '$w = 80\n'
            '@param 1..100\n'
            'h = 60\n'
        )
        result = extract_params(source)
        assert len(result.params) == 2
        assert result.params[0].name == "w"
        assert result.params[1].name == "h"

    def test_multiple_params_complex(self):
        source = (
            '@param 1..200 desc:"Width" group:"Size"\n'
            '$w = 80\n'
            '@param 1..200 desc:"Height" group:"Size"\n'
            '$h = 60\n'
            '@param 1..50 desc:"Depth" group:"Size"\n'
            '$d = 10\n'
            '@param 0..5 step:0.1 desc:"Fillet radius"\n'
            '$r = 2\n'
            'box $w $h $d | fillet $r\n'
        )
        result = extract_params(source)
        assert len(result.params) == 4
        names = [p.name for p in result.params]
        assert names == ["w", "h", "d", "r"]
        assert result.params[0].group == "Size"
        assert result.params[3].step == 0.1
