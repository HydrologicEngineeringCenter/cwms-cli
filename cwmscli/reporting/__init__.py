import json
import os
from pathlib import Path

import click

from cwmscli.utils import api_key_option, api_root_option, get_api_key, office_option
from cwmscli.utils.deps import requires


# ---- Group ----
@click.group("reporting", help="Create CWMS reports (Jinja, Repgen5, iText).")
@office_option
@api_root_option
@api_key_option
def reporting(office, api_root, api_key):
    """
    Shared options for all reporting commands. Stores values in ctx.obj.
    """
    print("Report!")


# ---- reporting scaffold ----
@reporting.command(
    "scaffold", help="Create a starter Jinja + Requests report in a folder."
)
@click.option(
    "-d",
    "--dir",
    "out_dir",
    default=".",
    show_default=True,
    help="Directory to create starter files.",
)
@requires(
    {
        "module": "jinja2",
        "package": "Jinja2",
        "version": "3.1.0",
        "desc": "Templating engine",
        "link": "https://palletsprojects.com/p/jinja/",
    },
    {
        "module": "requests",
        "version": "2.31.0",
        "desc": "HTTP client",
        "link": "https://requests.readthedocs.io/",
    },
)
def scaffold(**kwargs):
    from jinja2 import Template  # lazy import so CLI stays snappy

    print(kwargs)
    base = Path(kwargs.get("out_dir"))
    base.mkdir(parents=True, exist_ok=True)

    # Minimal starter template (HTML) using variables and a small loop.
    template = """<!doctype html>
<html>
  <head><meta charset="utf-8"/><title>{{ title }}</title></head>
  <body>
    <h1>{{ title }}</h1>
    <p>Office: {{ office }}</p>
    <p>Generated at: {{ generated_at }}</p>

    <h2>Latest values</h2>
    <ul>
    {% for item in series %}
      <li><strong>{{ item.name }}</strong>: {{ item.value }} {{ item.unit }} at {{ item.time }}</li>
    {% endfor %}
    </ul>
  </body>
</html>
"""
    (base / "report.html.j2").write_text(template, encoding="utf-8")

    # Starter config: which time series to fetch and how to label the report.
    config = {
        "title": "Sample CWMS Report",
        "series": [
            {
                "name": "KEYS.Elev.Inst.1Hour.0.Ccp-Rev",
                "alias": "Keystone Elevation",
            }
        ],
        # Optional begin/end ISO strings; if omitted, the renderer can choose defaults
        "begin": None,
        "end": None,
        "unit_system": "EN",
    }
    (base / "report.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    # Tiny README
    (base / "README.md").write_text(
        """# Reporting Starter

Files:
- `report.html.j2` — Jinja2 template
- `report.json` — configuration (title, series list, optional begin/end)
- Use: `cwms-cli reporting render -d reporting_starter -o out.html`

""",
        encoding="utf-8",
    )

    click.echo(f"Scaffold created in: {base.resolve()}")


# ---- reporting render ----
@reporting.command("render", help="Render a Jinja template using CWMS Data API.")
@click.option(
    "-d",
    "--dir",
    "in_dir",
    default=".",
    show_default=True,
    help="Directory with report.html.j2 and report.json.",
)
@click.option(
    "-t",
    "--template",
    default="report.html.j2",
    show_default=True,
    help="Template filename inside the directory.",
)
@click.option(
    "-c",
    "--config",
    default="report.json",
    show_default=True,
    help="Config JSON filename inside the directory.",
)
@click.option(
    "--output",
    "out_file",
    default="report.html",
    show_default=True,
    help="Output file.",
)
@click.option("--begin", help="Override begin ISO8601 (optional).")
@click.option("--end", help="Override end ISO8601 (optional).")
@office_option
@api_root_option
@requires(
    {
        "module": "jinja2",
        "package": "Jinja2",
        "version": "3.1.0",
        "desc": "Templating engine",
    },
    {
        "module": "requests",
        "version": "2.31.0",
        "desc": "HTTP client",
    },
)
def render_report(**kwargs):
    """
    Loads config, calls CWMS Data API for each series, renders template.
    """
    from datetime import datetime, timezone

    import requests
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    office = kwargs.get("office")
    api_root = kwargs.get("api_root").rstrip("/")
    api_key = kwargs.get("api_key")

    base = Path(kwargs.get("in_dir"))
    cfg = json.loads((base / kwargs.get("config")).read_text(encoding="utf-8"))

    # Allow CLI begin/end overrides
    if kwargs.get("begin"):
        cfg["begin"] = kwargs.get("begin")
    if kwargs.get("end"):
        cfg["end"] = kwargs.get("end")

    headers = {}
    # if api_key:
    #    headers["Authorization"] = f"Bearer {api_key}"

    # Minimal fetcher: latest value or bounded time-window (kept simple here)
    def fetch_latest(name: str):
        # If you want last value, ask for a tiny window ending "now"
        # You can refine with timeseries/values GET params as needed
        params = {
            "name": name,
            "office": office,
        }
        if cfg.get("begin"):
            params["begin"] = kwargs.get("begin")
        if cfg.get("end"):
            params["end"] = kwargs.get("end")
        if cfg.get("unit_system"):
            params["unit-system"] = cfg.get("unit_system")

        url = f"{api_root}/timeseries"
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()

        # Normalize a simple return shape (you’ll adapt to your exact API)
        # Expecting something like: { "values": [ [epoch_ms, value, qual], ... ], "units": "ft", ... }
        values = data.get("values") or data.get("value-pairs") or []
        unit = data.get("units") or data.get("unit") or ""
        if values:
            # Try to handle both [epoch,value,...] or object shapes
            last = values[-1]
            if isinstance(last, (list, tuple)) and len(last) >= 2:
                epoch_ms, val = last[0], last[1]
                t = datetime.fromtimestamp(
                    epoch_ms / 1000.0, tz=timezone.utc
                ).isoformat()
                return val, t, unit
            elif isinstance(last, dict):
                val = last.get("value")
                t = last.get("time") or last.get("date-time") or ""
                return val, t, unit
        return None, None, unit

    series_results = []
    for s in cfg.get("series", []):
        val, t, unit = fetch_latest(s["name"])
        series_results.append(
            {
                "name": s.get("alias") or s["name"],
                "value": val,
                "time": t,
                "unit": unit,
            }
        )

    env = Environment(
        loader=FileSystemLoader(str(base)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tmpl = env.get_template(kwargs.get("template"))

    html = tmpl.render(
        title=cfg.get("title", "CWMS Report"),
        office=office,
        generated_at=datetime.utcnow().isoformat() + "Z",
        series=series_results,
        cfg=cfg,
    )
    Path(kwargs.get("out_file")).write_text(html, encoding="utf-8")
    click.echo(f"Wrote {Path(kwargs.get('out_file')).resolve()}")


# ---- reporting repgen ----
@reporting.command("repgen", help="Create a report using Repgen5 (stub).")
@requires(
    {
        "module": "jinja2",
        "package": "Jinja2",
        "version": "3.1.0",
        "desc": "Templating for pre/post-processing",
    },
    # Add your repgen5 dependency discovery here when ready (e.g., Java/JAR presence)
)
@click.option("--template", help="Repgen template/file to execute (future).")
def generate_repgen(template):
    click.echo("Repgen5 integration coming soon.")


# ---- reporting itext ----
@reporting.command("itext", help="Create a report using iText (stub).")
@requires(
    # Example: you might end up calling into Java; jpype could be one approach
    {
        "module": "jpype",
        "version": "1.5.0",
        "desc": "Bridge to call Java iText from Python (optional approach).",
        "link": "https://jpype.readthedocs.io/",
    },
)
@click.option("--template", help="iText template/file to execute (future).")
def generate_itext(template):
    click.echo("iText integration coming soon.")
