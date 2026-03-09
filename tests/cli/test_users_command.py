from click.testing import CliRunner

from cwmscli.__main__ import cli


def test_users_roles_lists_available_roles(monkeypatch):
    monkeypatch.setattr(
        "cwmscli.commands.users.get_api_key", lambda api_key, api_key_loc: "test-key"
    )

    captured = {}

    class _FakeCwms:
        @staticmethod
        def init_session(api_root, api_key):
            captured["api_root"] = api_root
            captured["api_key"] = api_key

        @staticmethod
        def get_roles():
            return ["Viewer", "CWMS User Admins", "Analyst"]

    monkeypatch.setattr(
        "cwmscli.commands.users.click.echo",
        lambda msg: captured.setdefault("output", []).append(msg),
    )
    monkeypatch.setitem(__import__("sys").modules, "cwms", _FakeCwms)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "users",
            "roles",
            "--office",
            "SPK",
            "--api-root",
            "https://example.test/cda/",
            "--api-key",
            "ignored",
        ],
    )

    assert result.exit_code == 0
    assert captured["api_root"] == "https://example.test/cda/"
    assert captured["api_key"] == "test-key"
    output = "\n".join(captured["output"])
    assert "Available roles for user management: 3" in output
    assert "CWMS User Admins" in output
    assert "Analyst" in output
    assert "Viewer" in output
