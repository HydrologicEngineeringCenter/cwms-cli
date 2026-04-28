import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from cwmscli.usgs.rating_ini_file_import import (
    parse_ini_line,
    rating_ini_file_import,
    rating_types,
    update_rating_spec,
)


class TestParseIniLine:
    """Test the parse_ini_line function with various input formats."""

    def test_simple_space_separated_fields(self):
        """Test parsing simple space-separated fields."""
        line = "store_corr $($db_corr)"
        fields = parse_ini_line(line)
        assert fields == ["store_corr", "$($db_corr)"]

    def test_quoted_fields_with_spaces(self):
        """Test parsing fields quoted with double quotes."""
        line = 'store_corr "CEDI4.Stage;Flow.USGS-BASE.USGS-NWIS"'
        fields = parse_ini_line(line)
        assert len(fields) == 2
        assert fields[0] == "store_corr"
        assert "CEDI4.Stage;Flow.USGS-BASE.USGS-NWIS" in fields[1]

    def test_single_quoted_fields(self):
        """Test parsing fields quoted with single quotes."""
        line = "store_corr 'CEDI4.Stage;Flow.USGS-BASE.USGS-NWIS'"
        fields = parse_ini_line(line)
        assert len(fields) == 2
        assert fields[0] == "store_corr"

    def test_tab_separated_fields(self):
        """Test parsing tab-separated fields."""
        line = "store_corr\t$($db_corr)"
        fields = parse_ini_line(line)
        assert fields == ["store_corr", "$($db_corr)"]

    def test_escaped_quotes(self):
        """Test parsing with escaped quotes."""
        line = r'field1 "quoted \"value\" here"'
        fields = parse_ini_line(line)
        assert len(fields) >= 1
        assert fields[0] == "field1"

    def test_empty_line(self):
        """Test parsing empty line."""
        line = ""
        fields = parse_ini_line(line)
        assert fields == []

    def test_single_field(self):
        """Test parsing single field."""
        line = "field1"
        fields = parse_ini_line(line)
        assert fields == ["field1"]

    def test_multiple_spaces_between_fields(self):
        """Test parsing with multiple spaces between fields."""
        line = "field1    field2    field3"
        fields = parse_ini_line(line)
        assert fields == ["field1", "field2", "field3"]

    def test_quoted_field_preserves_internal_spaces(self):
        """Test that spaces inside quotes are preserved."""
        line = 'field1 "field with spaces" field3'
        fields = parse_ini_line(line)
        assert len(fields) == 3
        assert "field with spaces" in fields[1]


class TestRatingTypesConfig:
    """Test the rating_types configuration."""

    def test_rating_types_structure(self):
        """Verify rating_types has expected structure."""
        assert "store_corr" in rating_types
        assert "store_base" in rating_types
        assert "store_exsa" in rating_types

    def test_store_corr_config(self):
        """Test store_corr configuration."""
        config = rating_types["store_corr"]
        assert config["db_type"] == "db_corr"
        assert config["db_disc"] == "USGS-CORR"

    def test_store_base_config(self):
        """Test store_base configuration."""
        config = rating_types["store_base"]
        assert config["db_type"] == "db_base"
        assert config["db_disc"] == "USGS-BASE"

    def test_store_exsa_config(self):
        """Test store_exsa configuration."""
        config = rating_types["store_exsa"]
        assert config["db_type"] == "db_exsa"
        assert config["db_disc"] == "USGS-EXSA"


class TestUpdateRatingSpec:
    """Test the update_rating_spec function."""

    @patch("cwmscli.usgs.rating_ini_file_import.cwms")
    def test_update_rating_spec_basic(self, mock_cwms):
        """Test basic rating spec update."""
        mock_df = pd.DataFrame(
            {
                "active": [False],
                "auto-update": [False],
                "auto-activate": [False],
                "source-agency": ["OTHER"],
                "description": ["Old description"],
                "effective-dates": ["2020-01-01"],
            }
        )
        mock_rating_spec = MagicMock()
        mock_rating_spec.df = mock_df.copy()

        mock_cwms.get_rating_spec.return_value = mock_rating_spec
        mock_cwms.rating_spec_df_to_xml.return_value = "<xml></xml>"

        update_rating_spec("CEDI4.Stage;Flow", "MVP", "USGS-CORR")

        mock_cwms.get_rating_spec.assert_called_once_with(
            rating_id="CEDI4.Stage;Flow", office_id="MVP"
        )
        mock_cwms.store_rating_spec.assert_called_once()

    @patch("cwmscli.usgs.rating_ini_file_import.cwms")
    def test_update_rating_spec_sets_flags(self, mock_cwms):
        """Test that update_rating_spec sets all required flags."""
        mock_df = pd.DataFrame(
            {
                "active": [False],
                "auto-update": [False],
                "auto-activate": [False],
                "source-agency": ["OTHER"],
                "description": ["Old"],
                "effective-dates": ["2020-01-01"],
            }
        )
        mock_rating_spec = MagicMock()
        mock_rating_spec.df = mock_df.copy()

        mock_cwms.get_rating_spec.return_value = mock_rating_spec
        mock_cwms.rating_spec_df_to_xml.return_value = "<xml></xml>"

        update_rating_spec("TEST_ID", "MVP", "USGS-CORR")

        # Get the dataframe that was modified (called with positional arg)
        modified_df = mock_cwms.rating_spec_df_to_xml.call_args[0][0]
        assert modified_df["active"].iloc[0]
        assert modified_df["auto-update"].iloc[0]
        assert modified_df["auto-activate"].iloc[0]
        assert modified_df["source-agency"].iloc[0] == "USGS"

    @patch("cwmscli.usgs.rating_ini_file_import.cwms")
    def test_update_rating_spec_adds_description(self, mock_cwms):
        """Test that update_rating_spec adds discriminator to description."""
        mock_df = pd.DataFrame(
            {
                "active": [False],
                "auto-update": [False],
                "auto-activate": [False],
                "source-agency": ["OTHER"],
                "description": ["Existing"],
                "effective-dates": ["2020-01-01"],
            }
        )
        mock_rating_spec = MagicMock()
        mock_rating_spec.df = mock_df.copy()

        mock_cwms.get_rating_spec.return_value = mock_rating_spec
        mock_cwms.rating_spec_df_to_xml.return_value = "<xml></xml>"

        update_rating_spec("TEST_ID", "MVP", "USGS-CORR")

        modified_df = mock_cwms.rating_spec_df_to_xml.call_args[0][0]
        assert "USGS-CORR" in modified_df["description"].iloc[0]

    @patch("cwmscli.usgs.rating_ini_file_import.cwms")
    def test_update_rating_spec_with_missing_description(self, mock_cwms):
        """Test update_rating_spec when description column doesn't exist."""
        mock_df = pd.DataFrame(
            {
                "active": [False],
                "auto-update": [False],
                "auto-activate": [False],
                "source-agency": ["OTHER"],
                "effective-dates": ["2020-01-01"],
            }
        )
        mock_rating_spec = MagicMock()
        mock_rating_spec.df = mock_df.copy()

        mock_cwms.get_rating_spec.return_value = mock_rating_spec
        mock_cwms.rating_spec_df_to_xml.return_value = "<xml></xml>"

        update_rating_spec("TEST_ID", "MVP", "USGS-CORR")

        modified_df = mock_cwms.rating_spec_df_to_xml.call_args[0][0]
        assert "description" in modified_df.columns
        assert modified_df["description"].iloc[0] == "USGS-CORR"

    @patch("cwmscli.usgs.rating_ini_file_import.cwms")
    def test_update_rating_spec_dry_run_doesnt_store(self, mock_cwms):
        """Test that update_rating_spec with dry_run=True doesn't call store_rating_spec."""
        mock_df = pd.DataFrame(
            {
                "active": [False],
                "auto-update": [False],
                "auto-activate": [False],
                "source-agency": ["OTHER"],
                "description": ["Old"],
                "effective-dates": ["2020-01-01"],
            }
        )
        mock_rating_spec = MagicMock()
        mock_rating_spec.df = mock_df.copy()

        mock_cwms.get_rating_spec.return_value = mock_rating_spec
        mock_cwms.rating_spec_df_to_xml.return_value = "<xml></xml>"

        update_rating_spec("TEST_ID", "MVP", "USGS-CORR", dry_run=True)

        # rating_spec_df_to_xml should still be called
        mock_cwms.rating_spec_df_to_xml.assert_called_once()
        # But store_rating_spec should NOT be called
        mock_cwms.store_rating_spec.assert_not_called()


class TestRatingIniFileImport:
    """Test the main rating_ini_file_import function."""

    @patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session")
    @patch("cwmscli.usgs.rating_ini_file_import.update_rating_spec")
    def test_import_with_real_file(self, mock_update, mock_init_cwms):
        """Test import with the actual mvp_ratings_ini.ini file."""
        desktop_file = Path.home() / "Desktop" / "mvp_ratings_ini.ini"

        if desktop_file.exists():
            # Run the import
            rating_ini_file_import(
                "http://localhost:8080", "test_key", str(desktop_file)
            )

            # Verify init_cwms_session was called
            mock_init_cwms.assert_called_once()
            # Verify update_rating_spec was called for each non-commented store_* line
            assert mock_update.call_count > 0

    def test_import_with_simple_ini_file(self):
        """Test import with a simple temporary INI file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                """
# Test config
cwms_office=MVP
db_corr=$localid.Stage;Flow.USGS-CORR.USGS-NWIS
localid=TESTLOC
store_corr $($db_corr)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file
                    )

                    mock_update.assert_called_once()
        finally:
            os.unlink(temp_file)

    def test_import_parameter_parsing(self):
        """Test that import correctly parses configuration parameters."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                r"""
cwms_office=MVP
db_base=BASE_\$localid.SPEC
db_exsa=EXSA_\$localid.SPEC
db_corr=CORR_\$localid.SPEC
localid=TESTLOC
store_corr $($db_corr)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file
                    )

                    # Verify that update_rating_spec was called with correct parameters
                    mock_update.assert_called_once()
                    args = mock_update.call_args[0]
                    # The rating_spec should be the db_corr value with localid substituted
                    assert "TESTLOC" in args[0]
                    assert args[1] == "MVP"  # office_id
        finally:
            os.unlink(temp_file)

    def test_import_skips_comments(self):
        """Test that import correctly skips commented lines."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                """
cwms_office=MVP
db_corr=$localid.Stage;Flow.USGS-CORR.USGS-NWIS
db_exsa=$localid.Stage;Flow.USGS-EXSA.USGS-NWIS
localid=LOC1
#store_corr $($db_corr)
store_exsa $($db_exsa)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file
                    )
                    # Should only call for store_exsa, not commented store_corr
                    mock_update.assert_called_once()
        finally:
            os.unlink(temp_file)

    def test_import_handles_inline_comments(self):
        """Test that import correctly handles inline comments."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                """
cwms_office=MVP  # This is the office
db_corr=$localid.Stage;Flow.USGS-CORR.USGS-NWIS
localid=TESTLOC # Location identifier
store_corr $($db_corr)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file
                    )
                    # Verify office_id is correctly set (without comment)
                    mock_update.assert_called_once()
                    assert mock_update.call_args[0][1] == "MVP"
        finally:
            os.unlink(temp_file)

    def test_import_office_id_uppercase(self):
        """Test that office_id is converted to uppercase."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                """
cwms_office=mvp
db_corr=$localid.Stage;Flow.USGS-CORR.USGS-NWIS
localid=TESTLOC
store_corr $($db_corr)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file
                    )
                    # Verify office_id is uppercase
                    mock_update.assert_called_once()
                    assert mock_update.call_args[0][1] == "MVP"
        finally:
            os.unlink(temp_file)

    def test_import_handles_multiple_locations(self):
        """Test that import correctly processes multiple location blocks."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                """
cwms_office=MVP
db_corr=$localid.Stage;Flow.USGS-CORR.USGS-NWIS
localid=LOC1
store_corr $($db_corr)
localid=LOC2
store_corr $($db_corr)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file
                    )
                    # Should be called twice, once for each location
                    assert mock_update.call_count == 2
        finally:
            os.unlink(temp_file)

    def test_import_localid_substitution(self):
        """Test that $localid is correctly substituted in specifications."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                r"""
cwms_office=MVP
db_corr=\$localid.Stage;Flow.USGS-CORR.USGS-NWIS
localid=MYLOC
store_corr $($db_corr)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file
                    )

                    mock_update.assert_called_once()
                    # First argument should have MYLOC substituted for \$localid
                    rating_spec_arg = mock_update.call_args[0][0]
                    assert "MYLOC" in rating_spec_arg
        finally:
            os.unlink(temp_file)

    def test_import_cwmsid_substitution_with_nae_format(self):
        """Test NAE format with cwmsid and flexible db references (db_tail, db_river)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                r"""
CWMS_OFFICE=NAE
CWMS_DATABASE=local
db_tail=\$cwmsid.Stage-TAILWATER;Flow.USGS-EXSA.USGS-NWIS
db_river=\$cwmsid.Stage;Flow.USGS-EXSA.USGS-NWIS

cwmsid=BMD
usgsid=01155500
replace_exsa $(textfile)
store_exsa   $($db_tail)

cwmsid=NHD
usgsid=01151500
replace_exsa $(textfile)
store_exsa   $($db_river)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file
                    )

                    # Should be called twice (once for each cwmsid, replace_exsa is skipped)
                    assert mock_update.call_count == 2

                    # First call should use db_tail with BMD substituted
                    call1_args = mock_update.call_args_list[0][0]
                    assert "BMD" in call1_args[0]
                    assert "TAILWATER" in call1_args[0]
                    assert call1_args[1] == "NAE"

                    # Second call should use db_river with NHD substituted
                    call2_args = mock_update.call_args_list[1][0]
                    assert "NHD" in call2_args[0]
                    assert "TAILWATER" not in call2_args[0]
                    assert call2_args[1] == "NAE"
        finally:
            os.unlink(temp_file)

    def test_dry_run_mode_calls_update_with_flag(self):
        """Test that dry_run mode calls update_rating_spec with dry_run=True."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                r"""
cwms_office=MVP
db_corr=\$localid.Stage;Flow.USGS-CORR.USGS-NWIS
localid=TESTLOC
store_corr $($db_corr)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    # Run with dry_run=True
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file, dry_run=True
                    )

                    # update_rating_spec should be called WITH dry_run=True
                    mock_update.assert_called_once()
                    assert mock_update.call_args[1]["dry_run"] is True
        finally:
            os.unlink(temp_file)

    def test_dry_run_mode_with_multiple_entries(self):
        """Test that dry_run processes all entries with dry_run flag."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                r"""
CWMS_OFFICE=NAE
CWMS_DATABASE=local
db_tail=\$cwmsid.Stage-TAILWATER;Flow.USGS-EXSA.USGS-NWIS
db_river=\$cwmsid.Stage;Flow.USGS-EXSA.USGS-NWIS

cwmsid=BMD
usgsid=01155500
store_exsa   $($db_tail)

cwmsid=NHD
usgsid=01151500
store_exsa   $($db_river)

cwmsid=NSD
usgsid=01153000
store_exsa   $($db_tail)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    # Run with dry_run=True
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file, dry_run=True
                    )

                    # update_rating_spec should be called 3 times with dry_run=True
                    assert mock_update.call_count == 3
                    for call in mock_update.call_args_list:
                        assert call[1]["dry_run"] is True
        finally:
            os.unlink(temp_file)

    def test_normal_mode_calls_updates(self):
        """Test that normal mode (not dry_run) calls update_rating_spec with dry_run=False."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                r"""
cwms_office=MVP
db_corr=\$localid.Stage;Flow.USGS-CORR.USGS-NWIS
localid=TESTLOC
store_corr $($db_corr)
"""
            )
            temp_file = f.name

        try:
            with patch("cwmscli.usgs.rating_ini_file_import.init_cwms_session"):
                with patch(
                    "cwmscli.usgs.rating_ini_file_import.update_rating_spec"
                ) as mock_update:
                    # Run with dry_run=False (default)
                    rating_ini_file_import(
                        "http://localhost:8080", "test_key", temp_file, dry_run=False
                    )

                    # update_rating_spec SHOULD be called with dry_run=False
                    mock_update.assert_called_once()
                    assert mock_update.call_args[1]["dry_run"] is False
        finally:
            os.unlink(temp_file)
