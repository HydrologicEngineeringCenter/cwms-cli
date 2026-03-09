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


def _format_api_error(error: Exception, cwms_module) -> str:
    message = str(error)
    if isinstance(error, cwms_module.api.PermissionError):
        status_text = "CDA responded with 403 Forbidden."
        if status_text in message:
            message = message.replace(status_text, colors.err(status_text))
        message = (
            f"{message} Use an admin API key or sign in as a user with user-management "
            "admin roles. I.e. 'CWMS User Admins'"
        )
    return message


def list_roles(office: str, api_root: str, api_key: str, api_key_loc: str) -> None:
    import cwms

    resolved_api_key = get_api_key(api_key, api_key_loc)
    cwms.init_session(api_root=api_root, api_key=resolved_api_key)
    try:
        roles = sorted(cwms.get_roles(), key=str.casefold)
    except cwms.api.ApiError as error:
        raise click.ClickException(_format_api_error(error, cwms)) from None

    header_count = colors.c(str(len(roles)), "cyan", bright=True)
    click.echo(f"Available roles for user management: {header_count}")

    if not roles:
        click.echo(colors.warn(f"No roles were returned for office {office}."))
        return

    rows = [[colors.c(role, "green")] for role in roles]
    click.echo(_format_table(["Role"], rows))
