"""Tests for @profile annotation feature."""

from __future__ import annotations

import json
import warnings

import pytest

from polyscript.profile import (
    Profile,
    ProfileEntry,
    ProfileError,
    extract_profile,
    parse_profile_block,
)
from polyscript.params import extract_params


# ---------------------------------------------------------------------------
# parse_profile_block: basic cases
# ---------------------------------------------------------------------------


class TestParseProfileBasic:
    """Basic parsing of @profile body text."""

    def test_multiple_variables(self):
        """S/M/L with width, height, depth."""
        text = """{
          "S": { width: 10, height: 10, depth: 10 },
          "M": { width: 20, height: 20, depth: 20 },
          "L": { width: 30, height: 30, depth: 30 }
        }"""
        profile = parse_profile_block(text)
        assert len(profile.entries) == 3
        assert profile.entries[0].name == "S"
        assert profile.entries[0].values == {"width": 10, "height": 10, "depth": 10}
        assert profile.entries[1].name == "M"
        assert profile.entries[1].values == {"width": 20, "height": 20, "depth": 20}
        assert profile.entries[2].name == "L"
        assert profile.entries[2].values == {"width": 30, "height": 30, "depth": 30}

    def test_simple_single_variable(self):
        """1 variable only (size)."""
        text = """{
          "S": { size: 10 },
          "M": { size: 20 },
          "L": { size: 30 }
        }"""
        profile = parse_profile_block(text)
        assert len(profile.entries) == 3
        assert profile.entries[0].values == {"size": 10}
        assert profile.entries[1].values == {"size": 20}
        assert profile.entries[2].values == {"size": 30}


class TestParseProfileEmptyEntry:
    """Empty entry (e.g. "Default": {}) is allowed."""

    def test_empty_entry_allowed(self):
        text = """{
          "Default": {},
          "Small":   { width: 30, height: 20 },
          "Large":   { width: 150, height: 80 }
        }"""
        profile = parse_profile_block(text)
        assert len(profile.entries) == 3
        assert profile.entries[0].name == "Default"
        assert profile.entries[0].values == {}
        assert profile.entries[1].name == "Small"
        assert profile.entries[1].values == {"width": 30, "height": 20}


class TestParseProfileValueTypes:
    """Mixed value types: numbers, strings, booleans."""

    def test_mixed_types(self):
        text = """{
          "Config1": { count: 5, label: "hello", enabled: true },
          "Config2": { count: 10, label: "world", enabled: false }
        }"""
        profile = parse_profile_block(text)
        e0 = profile.entries[0]
        assert e0.values["count"] == 5
        assert e0.values["label"] == "hello"
        assert e0.values["enabled"] is True
        e1 = profile.entries[1]
        assert e1.values["count"] == 10
        assert e1.values["label"] == "world"
        assert e1.values["enabled"] is False

    def test_float_values(self):
        text = '{ "A": { radius: 3.14, height: 2.0 } }'
        profile = parse_profile_block(text)
        assert profile.entries[0].values["radius"] == pytest.approx(3.14)
        assert profile.entries[0].values["height"] == pytest.approx(2.0)

    def test_negative_number(self):
        text = '{ "A": { offset: -5 } }'
        profile = parse_profile_block(text)
        assert profile.entries[0].values["offset"] == -5


class TestParseProfileSourceOrder:
    """Entries preserve source order."""

    def test_source_order_preserved(self):
        text = """{
          "First": { a: 1 },
          "Second": { a: 2 },
          "Third": { a: 3 },
          "Fourth": { a: 4 }
        }"""
        profile = parse_profile_block(text)
        names = [e.name for e in profile.entries]
        assert names == ["First", "Second", "Third", "Fourth"]


# ---------------------------------------------------------------------------
# parse_profile_block: error cases
# ---------------------------------------------------------------------------


class TestParseProfileErrors:
    """Error conditions that must raise ProfileError."""

    def test_empty_body(self):
        """@profile {} (zero entries) is an error."""
        with pytest.raises(ProfileError, match="[Ee]mpty"):
            parse_profile_block("{}")

    def test_duplicate_preset_name(self):
        text = """{
          "S": { width: 10 },
          "S": { width: 20 }
        }"""
        with pytest.raises(ProfileError, match="[Dd]uplicate"):
            parse_profile_block(text)

    def test_syntax_error_missing_closing_brace(self):
        text = '{ "S": { width: 10 }'
        with pytest.raises(ProfileError):
            parse_profile_block(text)

    def test_syntax_error_missing_colon(self):
        text = '{ "S" { width: 10 } }'
        with pytest.raises(ProfileError):
            parse_profile_block(text)

    def test_null_value_rejected(self):
        text = '{ "S": { width: null } }'
        with pytest.raises(ProfileError, match="null"):
            parse_profile_block(text)

    def test_null_as_identifier_rejected(self):
        text = '{ "S": { null: 10 } }'
        with pytest.raises(ProfileError, match="null"):
            parse_profile_block(text)


# ---------------------------------------------------------------------------
# extract_profile: source-level extraction
# ---------------------------------------------------------------------------


class TestExtractProfile:
    """Test extract_profile from full PolyScript source."""

    def test_no_profile_returns_none(self):
        source = "width = 10\nbox width 20 30"
        assert extract_profile(source) is None

    def test_multiple_profiles_error(self):
        source = """\
@profile {
  "S": { size: 10 }
}

@profile {
  "M": { size: 20 }
}
"""
        with pytest.raises(ProfileError, match="[Mm]ultiple"):
            extract_profile(source)

    def test_spec_example_basic(self):
        """SPEC.md code example: multiple variables (S/M/L with width/height/depth)."""
        source = """\
@profile {
  "S": { width: 10, height: 10, depth: 10 },
  "M": { width: 20, height: 20, depth: 20 },
  "L": { width: 30, height: 30, depth: 30 }
}

width  = 10
height = 10
depth  = 10

box width height depth
"""
        profile = extract_profile(source)
        assert profile is not None
        assert len(profile.entries) == 3
        assert profile.entries[0].name == "S"
        assert profile.entries[0].values["width"] == 10
        assert profile.entries[2].name == "L"
        assert profile.entries[2].values["depth"] == 30

    def test_spec_example_simple(self):
        """SPEC.md code example: simple case (1 variable)."""
        source = """\
@profile {
  "S": { size: 10 },
  "M": { size: 20 },
  "L": { size: 30 }
}

size = 20

sphere size
"""
        profile = extract_profile(source)
        assert profile is not None
        assert len(profile.entries) == 3
        assert profile.entries[1].name == "M"
        assert profile.entries[1].values["size"] == 20

    def test_spec_example_with_param(self):
        """SPEC.md code example: @param and @profile coexistence."""
        source = """\
@profile {
  "S": { width: 30, height: 20, depth: 15 },
  "M": { width: 60, height: 40, depth: 30 },
  "L": { width: 120, height: 80, depth: 60 }
}

@param 10..200 step:5 desc:"Box width" group:"Dimensions"
width = 60

@param 10..150 desc:"Box height" group:"Dimensions"
height = 40

@param 10..100 desc:"Box depth" group:"Dimensions"
depth = 30

@param choices:["PLA", "ABS", "PETG"] desc:"Material"
material = "PLA"

box width height depth
"""
        profile = extract_profile(source)
        assert profile is not None
        assert len(profile.entries) == 3
        assert profile.entries[0].name == "S"
        assert profile.entries[0].values == {
            "width": 30, "height": 20, "depth": 15,
        }
        assert profile.entries[2].name == "L"
        assert profile.entries[2].values == {
            "width": 120, "height": 80, "depth": 60,
        }


# ---------------------------------------------------------------------------
# extract_params integration
# ---------------------------------------------------------------------------


class TestExtractParamsProfile:
    """Test that extract_params populates ParamSet.profile."""

    def test_profile_set_on_paramset(self):
        source = """\
@profile {
  "S": { width: 10, height: 10 },
  "M": { width: 20, height: 20 }
}

@param 1..100
width = 10

@param 1..100
height = 10
"""
        result = extract_params(source)
        assert result.profile is not None
        assert len(result.profile.entries) == 2
        assert result.profile.entries[0].name == "S"
        # Also verify @param is still working
        assert len(result.params) == 2
        assert result.params[0].name == "width"

    def test_no_profile_is_none(self):
        source = "@param 1..100\nwidth = 10"
        result = extract_params(source)
        assert result.profile is None

    def test_json_parameter_sets_deprecation_warning(self):
        source = "@param 1..100\nval = 10"
        json_data = json.dumps({
            "parameterSets": {
                "small": {"val": 5},
                "large": {"val": 95},
            }
        })
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = extract_params(source, json_str=json_data)
            # Check that a DeprecationWarning was raised
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) == 1
            assert "parameterSets" in str(dep_warnings[0].message)
            assert "deprecated" in str(dep_warnings[0].message)
        # parameter_sets should still be populated (backward compat)
        assert "small" in result.parameter_sets

    def test_json_empty_parameter_sets_no_warning(self):
        """Empty parameterSets should not trigger warning."""
        source = "@param 1..100\nval = 10"
        json_data = json.dumps({
            "parameterSets": {}
        })
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            extract_params(source, json_str=json_data)
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) == 0


class TestTrailingComma:
    """Trailing commas should be tolerated (common in hand-written configs)."""

    def test_trailing_comma_outer(self):
        text = """{
          "S": { width: 10 },
          "M": { width: 20 },
        }"""
        profile = parse_profile_block(text)
        assert len(profile.entries) == 2

    def test_trailing_comma_inner(self):
        text = '{ "S": { width: 10, height: 20, } }'
        profile = parse_profile_block(text)
        assert profile.entries[0].values == {"width": 10, "height": 20}
