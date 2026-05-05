from __future__ import annotations

from typing import Optional, Union

import click

from cwmscli.utils import colors, init_cwms_session


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


def _init_cwms(api_root: str, api_key: str, api_key_loc: str) -> object:
    import cwms

    init_cwms_session(cwms, api_root=api_root, api_key=api_key, api_key_loc=api_key_loc)
    return cwms


def _fetch_roles(cwms_module) -> list[str]:
    try:
        return sorted(cwms_module.get_roles(), key=str.casefold)
    except cwms_module.api.ApiError as error:
        _handle_api_error(error, cwms_module)


def _fetch_users(
    cwms_module, office=None, username_like=None, page_size: int = 5000
) -> list[dict]:
    users: list[dict] = []

    try:
        response = cwms_module.get_users(
            office_id=office, username_like=username_like, page_size=page_size
        )
    except cwms_module.api.ApiError as error:
        _handle_api_error(error, cwms_module)

    payload = getattr(response, "json", {}) or {}
    page_users = payload.get("users", [])
    users.extend(page_users)

    return users


def _fetch_user_roles(
    cwms_module, user_name: str, office: Optional[str] = None
) -> list[str]:
    roles_payload = _get_user_roles_payload(cwms_module, user_name)
    return _extract_roles_from_payload(roles_payload, office)


def _get_user_roles_payload(cwms_module, user_name: str) -> dict:
    try:
        payload = cwms_module.get_user(user_name=user_name)
        return payload.get("roles", {})
    except cwms_module.api.ApiError as error:
        _handle_api_error(error, cwms_module)


def _extract_roles_from_payload(
    roles_payload: dict, office: Optional[str] = None
) -> list[str]:
    if isinstance(roles_payload, dict):
        if office:
            office_key = office.strip().upper()
            office_roles = roles_payload.get(office_key, [])
            if office_roles is None:
                office_roles = []
            return [r.strip() for r in office_roles if r and r.strip()]
        all_roles = []
        for rlist in roles_payload.values():
            if rlist:
                all_roles.extend(rlist)
        return sorted(
            {r.strip() for r in all_roles if r and r.strip()}, key=str.casefold
        )

    if isinstance(roles_payload, list):
        return [r.strip() for r in roles_payload if r and r.strip()]

    return []


def _existing_user_name(users: list[dict], user_name: str) -> Optional[str]:

    requested = user_name.strip().casefold()
    for user in users:
        existing = str(user.get("user-name", "")).strip()
        if existing and existing.casefold() == requested:
            return existing
    return None


def _split_roles(
    raw_roles: Optional[Union[tuple[str, ...], list[str]]] = None
) -> list[str]:
    if not raw_roles:
        return []
    return [role.strip() for role in raw_roles if role and role.strip()]


def _expand_role_shortcuts(roles: list[str]) -> list[str]:
    emap = {
        "admin": ["All Users", "CWMS Users", "TS ID Creator", "CWMS User Admins"],
        "readonly": ["All Users", "CWMS Users"],
        "readwrite": ["All Users", "CWMS Users", "TS ID Creator"],
    }

    expanded_roles: list[str] = []
    for role in roles:
        key = role.strip().casefold()
        if key == "all":
            expanded_roles.append(role)  # Keep "all" as is, handled elsewhere
        elif key in emap:
            expanded_roles.extend(emap[key])
        else:
            expanded_roles.append(role)
    return expanded_roles


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

    deduped_roles = []
    seen_roles = set()
    for role in normalized_roles:
        if role not in seen_roles:
            seen_roles.add(role)
            deduped_roles.append(role)

    if not deduped_roles:
        raise click.ClickException("At least one valid role is required.")

    return existing_user, deduped_roles


def _render_roles_table(roles: list[str]) -> str:
    rows = [[colors.c(role, "green")] for role in roles]
    return _format_table(["Role"], rows)


def _render_user_roles_table(user_roles: dict[str, list[str]]) -> str:
    rows = []
    for office, roles in sorted(user_roles.items()):
        roles_str = ", ".join(sorted(roles))
        rows.append([colors.c(office, "cyan"), colors.c(roles_str, "green")])
    return _format_table(["Office", "Roles"], rows)


def _render_users_table(users: list[dict]) -> str:
    rows = [[colors.c(user.get("user-name", ""), "green")] for user in users]
    return _format_table(["User Name"], rows)


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
        "Roles (comma-separated; use names exactly as listed; or shortcuts admin/readwrite/readonly)",
        type=str,
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


def list_roles(api_root: str, api_key: str, api_key_loc: str) -> None:
    cwms = _init_cwms(api_root, api_key, api_key_loc)
    roles = _fetch_roles(cwms)
    header_count = colors.c(str(len(roles)), "cyan", bright=True)
    click.echo(f"Available roles for user management: {header_count}")
    if not roles:
        click.echo(colors.warn("No roles were returned."))
        return
    click.echo(_render_roles_table(roles))


def list_user_roles(
    user_name: str, office: Optional[str], api_root: str, api_key: str, api_key_loc: str
) -> None:
    cwms = _init_cwms(api_root, api_key, api_key_loc)
    roles_payload = _get_user_roles_payload(cwms, user_name)
    if isinstance(roles_payload, dict):
        if office:
            office_key = office.strip().upper()
            office_roles = roles_payload.get(office_key, [])
            if office_roles is None:
                office_roles = []
            user_roles = [r.strip() for r in office_roles if r and r.strip()]
            header = (
                f"Roles for user '{user_name}' in office '{office}': {len(user_roles)}"
            )
            click.echo(colors.c(header, "cyan", bright=True))
            if not user_roles:
                click.echo(colors.warn("No roles found."))
                return
            click.echo(_render_roles_table(user_roles))
        else:
            # List roles for each office
            header = f"Roles for user '{user_name}' across all offices:"
            click.echo(colors.c(header, "cyan", bright=True))
            for off, roles in roles_payload.items():
                if roles:
                    cleaned_roles = [r.strip() for r in roles if r and r.strip()]
                    if cleaned_roles:
                        click.echo(
                            colors.c(
                                f"Office '{off}': {len(cleaned_roles)} roles", "yellow"
                            )
                        )
                        click.echo(_render_roles_table(cleaned_roles))
                        click.echo("")
                else:
                    click.echo(colors.c(f"Office '{off}': No roles", "yellow"))
                    click.echo("")
    else:
        click.echo(colors.warn("Unexpected roles format."))


def list_user_ids(
    office: str,
    api_root: str,
    api_key: str,
    api_key_loc: str,
    username_like: Optional[str] = None,
) -> None:
    # This command is wired from user roles group default action. Users can
    # pass an optional name filter but for now roles view is what should be shown.
    cwms = _init_cwms(api_root, api_key, api_key_loc)
    users = _fetch_users(cwms, office, username_like=username_like)
    click.echo(_render_users_table(users))


def add_roles(
    office: str,
    api_root: str,
    api_key: str,
    api_key_loc: str,
    user_name: Optional[str],
    roles: Optional[Union[tuple[str, ...], list[str]]],
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

    provided_roles = _expand_role_shortcuts(provided_roles)
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
    user_name: Optional[str],
    roles: Optional[Union[tuple[str, ...], list[str]]],
) -> None:
    provided_user_name = (user_name or "").strip()
    provided_roles = _split_roles(roles)
    provided_roles = _expand_role_shortcuts(provided_roles)

    if bool(provided_user_name) ^ bool(provided_roles):
        raise click.ClickException(
            "Either specify all delete arguments (--user-name and --roles) or run "
            f"{_cmd('cwms-cli users roles delete')} interactively with no delete-specific args."
        )

    cwms = _init_cwms(api_root, api_key, api_key_loc)
    users = _fetch_users(cwms, office)
    available_roles = _fetch_roles(cwms)

    if not provided_user_name and not provided_roles:
        office = _prompt_for_office(office)
        provided_user_name, provided_roles = _prompt_for_role_inputs(
            "delete", available_roles
        )
        provided_roles = _expand_role_shortcuts(provided_roles)

    if provided_roles and any(r.strip().casefold() == "all" for r in provided_roles):
        if len(provided_roles) > 1:
            raise click.ClickException("'all' cannot be specified with other roles.")
        existing_user = _existing_user_name(users, provided_user_name)
        if not existing_user:
            raise click.ClickException(f"User '{provided_user_name}' not found.")
        fetched_roles = _fetch_user_roles(cwms, existing_user, office)
        provided_roles = fetched_roles

    existing_user, validated_roles = _validate_role_inputs(
        users, available_roles, provided_user_name, provided_roles
    )
    if "All Users" in validated_roles:
        validated_roles.remove("All Users")
        click.echo(
            colors.warn(
                "Warning: 'All Users' role cannot be deleted directly and will remain assigned. "
                "Any other specified roles will be deleted as requested."
            )
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
