import click

from cwmscli.utils import colors, get_api_key


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def render_row(row: list[str]) -> str:
        return "  ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))

    divider = "  ".join("-" * width for width in widths)
    lines = [render_row(headers), divider]
    lines.extend(render_row(row) for row in rows)
    return "\n".join(lines)


def list_roles(office: str, api_root: str, api_key: str, api_key_loc: str) -> None:
    import cwms

    resolved_api_key = get_api_key(api_key, api_key_loc)
    cwms.init_session(api_root=api_root, api_key=resolved_api_key)
    roles = sorted(cwms.get_roles(), key=str.casefold)

    header_count = colors.c(str(len(roles)), "cyan", bright=True)
    click.echo(f"Available roles for user management: {header_count}")

    if not roles:
        click.echo(colors.warn(f"No roles were returned for office {office}."))
        return

    rows = [
        [colors.dim(str(index)), colors.c(role, "green")]
        for index, role in enumerate(roles, start=1)
    ]
    click.echo(_format_table(["#", "Role"], rows))
