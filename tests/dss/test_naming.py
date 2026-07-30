from pathlib import Path

import pytest

from cwmscli.dss.naming import (
    ExportResolver,
    ImportResolver,
    MappingError,
    default_pathname,
    default_tsid,
    read_export_rules,
    read_filters,
    read_import_rules,
)


@pytest.mark.parametrize(
    "tsid",
    [
        "Test.Flow.Inst.1Hour.0.Raw",
        "Test.Precip.Total.15Minutes.15Minutes.Raw",
        "Test.Stage.Inst.0.0.Raw",
        "Test.Flow.Ave.~1Day.1Day.Rev-CWMS",
    ],
)
def test_legacy_default_name_round_trip(tsid):
    assert default_tsid(default_pathname(tsid)) == tsid


def test_import_mapping_and_location_substitution(tmp_path: Path):
    mapping = tmp_path / "import.csv"
    mapping.write_text(
        "/A/$LOC/FLOW--INST--0//1HOUR/RAW/,$LOC.Flow.Inst.1Hour.0.Raw,cfs,2\n",
        encoding="utf-8",
    )
    resolver = ImportResolver(read_import_rules(mapping), ())

    rule = resolver.resolve("/A/TULSA/FLOW--INST--0/01JAN2026/1HOUR/RAW/")

    assert rule is not None
    assert rule.tsid == "TULSA.Flow.Inst.1Hour.0.Raw"
    assert rule.factor == 2


def test_export_mapping_and_location_substitution(tmp_path: Path):
    mapping = tmp_path / "export.csv"
    mapping.write_text(
        "$LOC.Flow.Inst.1Hour.0.Raw,/A/$LOC/FLOW//1HOUR/RAW/,cfs,1,CFS\n",
        encoding="utf-8",
    )
    resolver = ExportResolver(read_export_rules(mapping), ())

    rule = resolver.resolve("Tulsa.Flow.Inst.1Hour.0.Raw")

    assert rule is not None
    assert rule.pathname == "/A/Tulsa/FLOW//1HOUR/RAW/"
    assert resolver.catalog_identifiers() is None


def test_exact_mappings_can_bypass_full_catalog(tmp_path: Path):
    mapping = tmp_path / "export.csv"
    mapping.write_text(
        "Tulsa.Flow.Inst.1Hour.0.Raw,/A/Tulsa/FLOW//1HOUR/RAW/,cfs,1,CFS\n",
        encoding="utf-8",
    )

    resolver = ExportResolver(read_export_rules(mapping), ())

    assert resolver.catalog_identifiers() == ("Tulsa.Flow.Inst.1Hour.0.Raw",)


def test_filters_are_case_insensitive(tmp_path: Path):
    filters = tmp_path / "filter.txt"
    filters.write_text("# comment\n*.FLOW.*.RAW\n", encoding="utf-8")
    resolver = ExportResolver((), read_filters(filters))

    assert resolver.resolve("Tulsa.Flow.Inst.1Hour.0.Raw") is not None
    assert resolver.resolve("Tulsa.Stage.Inst.1Hour.0.Raw") is None


def test_bad_mapping_is_not_silently_ignored(tmp_path: Path):
    mapping = tmp_path / "bad.csv"
    mapping.write_text("not,enough,columns\n", encoding="utf-8")

    with pytest.raises(MappingError, match="expected"):
        read_import_rules(mapping)
