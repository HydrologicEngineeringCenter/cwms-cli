from __future__ import annotations

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


def _cmd(text: str) -> str:
    return colors.c(text, "blue", bright=True)


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


def _handle_api_error(error: Exception, cwms_module) -> None:
    raise click.ClickException(_format_api_error(error, cwms_module)) from None


def _init_cwms(api_root: str, api_key: str, api_key_loc: str):
    import cwms

    resolved_api_key = get_api_key(api_key, api_key_loc)
    cwms.init_session(api_root=api_root, api_key=resolved_api_key)
    return cwms


def _fetch_roles(cwms_module) -> list[str]:
    try:
        return sorted(cwms_module.get_roles(), key=str.casefold)
    except cwms_module.api.ApiError as error:
        _handle_api_error(error, cwms_module)


def _fetch_users(cwms_module, page_size: int = 500) -> list[dict]:
    users: list[dict] = []
    page = None

    while True:
        try:
            response = cwms_module.get_users(page=page, page_size=page_size)
        except cwms_module.api.ApiError as error:
            _handle_api_error(error, cwms_module)

        payload = getattr(response, "json", {}) or {}
        page_users = payload.get("users", [])
        if isinstance(page_users, list):
            users.extend(user for user in page_users if isinstance(user, dict))

        page = payload.get("next-page")
        if not page:
            break

    return users


def _existing_user_name(users: list[dict], user_name: str) -> str | None:
    requested = user_name.strip().casefold()
    for user in users:
        existing = str(user.get("user-name", "")).strip()
        if existing and existing.casefold() == requested:
            return existing
    return None


def _split_roles(raw_roles: tuple[str, ...] | list[str] | None) -> list[str]:
    if not raw_roles:
        return []
    return [role.strip() for role in raw_roles if role and role.strip()]


def _validate_role_inputs(
    users: list[dict], available_roles: list[str], user_name: str, roles: list[str]
) -> tuple[str, list[str]]:
    existing_user = _existing_user_name(users, user_name)
    if not existing_user:
        raise click.ClickException(f"User '{user_name}' was not found in CDA /users.")

    roles_lookup = {role.casefold(): role for role in available_roles}
    normalized_roles: list[str] = []
    invalid_roles: list[str] = []

    for role in roles:
        normalized = roles_lookup.get(role.casefold())
        if normalized:
            normalized_roles.append(normalized)
        else:
            invalid_roles.append(role)

    if invalid_roles:
        invalid = ", ".join(colors.err(role) for role in invalid_roles)
        raise click.ClickException(
            f"Unknown role value(s): {invalid}. Run {_cmd('cwms-cli users roles')} to see the valid role catalog."
        )

    deduped_roles = sorted(set(normalized_roles), key=str.casefold)
    if not deduped_roles:
        raise click.ClickException("At least one valid role is required.")

    return existing_user, deduped_roles


def _render_roles_table(roles: list[str]) -> str:
    rows = [[colors.c(role, "green")] for role in roles]
    return _format_table(["Role"], rows)


def _prompt_for_role_inputs(
    action: str, available_roles: list[str]
) -> tuple[str, list[str]]:
    click.echo(f"Enter the target user and one or more roles to {action}.")
    click.echo("")
    user_name = click.prompt("User name", type=str).strip()
    click.echo("")
    click.echo("Available roles:")
    click.echo(_render_roles_table(available_roles))
    click.echo("")
    roles_raw = click.prompt(
        "Roles (comma-separated; use names exactly as listed)", type=str
    ).strip()
    roles = [role.strip() for role in roles_raw.split(",") if role.strip()]
    return user_name, roles


def _prompt_for_office(office: str) -> str:
    colored_office = colors.c(office, "cyan", bright=True)
    change_office = click.confirm(
        f"You have office set to {colored_office}, would you like to change this?",
        default=False,
    )
    if not change_office:
        return office

    return (
        click.prompt("Office", type=str, default=office, show_default=True)
        .strip()
        .upper()
    )


def list_roles(office: str, api_root: str, api_key: str, api_key_loc: str) -> None:
    cwms = _init_cwms(api_root, api_key, api_key_loc)
    roles = _fetch_roles(cwms)

    header_count = colors.c(str(len(roles)), "cyan", bright=True)
    click.echo(f"Available roles for user management: {header_count}")

    if not roles:
        click.echo(colors.warn(f"No roles were returned for office {office}."))
        return

    click.echo(_render_roles_table(roles))


def add_roles(
    office: str,
    api_root: str,
    api_key: str,
    api_key_loc: str,
    user_name: str | None,
    roles: tuple[str, ...] | list[str] | None,
) -> None:
    provided_user_name = (user_name or "").strip()
    provided_roles = _split_roles(roles)

    if bool(provided_user_name) ^ bool(provided_roles):
        raise click.ClickException(
            "Either specify all add arguments (--user-name and --roles) or run "
            f"{_cmd('cwms-cli users roles add')} interactively with no add-specific args."
        )

    cwms = _init_cwms(api_root, api_key, api_key_loc)
    users = _fetch_users(cwms)
    available_roles = _fetch_roles(cwms)

    if not provided_user_name and not provided_roles:
        office = _prompt_for_office(office)
        provided_user_name, provided_roles = _prompt_for_role_inputs(
            "add", available_roles
        )

    existing_user, validated_roles = _validate_role_inputs(
        users, available_roles, provided_user_name, provided_roles
    )

    try:
        cwms.store_user(
            user_name=existing_user, office_id=office, roles=validated_roles
        )
    except cwms.api.ApiError as error:
        _handle_api_error(error, cwms)

    click.echo(
        f"Added {len(validated_roles)} role(s) to user "
        f"{colors.c(existing_user, 'cyan', bright=True)} for office "
        f"{colors.c(office, 'cyan', bright=True)}."
    )
    click.echo(_render_roles_table(validated_roles))


def delete_roles(
    office: str,
    api_root: str,
    api_key: str,
    api_key_loc: str,
    user_name: str | None,
    roles: tuple[str, ...] | list[str] | None,
) -> None:
    provided_user_name = (user_name or "").strip()
    provided_roles = _split_roles(roles)

    if bool(provided_user_name) ^ bool(provided_roles):
        raise click.ClickException(
            "Either specify all delete arguments (--user-name and --roles) or run "
            f"{_cmd('cwms-cli users roles delete')} interactively with no delete-specific args."
        )

    cwms = _init_cwms(api_root, api_key, api_key_loc)
    users = _fetch_users(cwms)
    available_roles = _fetch_roles(cwms)

    if not provided_user_name and not provided_roles:
        office = _prompt_for_office(office)
        provided_user_name, provided_roles = _prompt_for_role_inputs(
            "delete", available_roles
        )

    existing_user, validated_roles = _validate_role_inputs(
        users, available_roles, provided_user_name, provided_roles
    )

    try:
        cwms.delete_user_roles(
            user_name=existing_user, office_id=office, roles=validated_roles
        )
    except cwms.api.ApiError as error:
        _handle_api_error(error, cwms)

    click.echo(
        f"Deleted {len(validated_roles)} role(s) from user "
        f"{colors.c(existing_user, 'cyan', bright=True)} for office "
        f"{colors.c(office, 'cyan', bright=True)}."
    )
    click.echo(_render_roles_table(validated_roles))
