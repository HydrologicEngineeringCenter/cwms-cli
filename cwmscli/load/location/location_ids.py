from typing import Iterable, Optional
import click
import cwms


def load_locations(
    source_cda: str,
    source_office: str,
    target_cda: str,
    target_api_key: Optional[str],
    verbose: int,
    dry_run: bool,
    like: Optional[str],
    location_kind_like: Optional[Iterable[str]] = 'ALL'
):

    if verbose:
        click.echo(
            f"[load locations] source={source_cda} ({source_office}) -> target={target_cda}"
        )
        click.echo(
            f"  like={like or '-'}  kinds={list(location_kind_like) or '-'}  dry_run={dry_run}"
        )

    cwms.init_session(api_root=source_cda, api_key=None)

    cat_kwargs = {"office_id": source_office}
    if like:
        cat_kwargs["like"] = like
    kinds = list(location_kind_like) if location_kind_like else [None]

    locations = []

    if 'ALL' in kinds:
        locations = cwms.get_locations(
            office_id=source_office).json
    else:
        locations = []
        for kind in kinds:
            cat_kwargs_k = dict(cat_kwargs)
            if kind != 'ALL':
                cat_kwargs_k["location_kind_like"] = kind

            if verbose >= 2:
                click.echo(f"  > catalog query: {cat_kwargs_k}")

            resp = cwms.get_locations_catalog(**cat_kwargs_k)
            if resp.df.empty:
                continue

            loc_ids = resp.df["name"].tolist()
            locations_resp = cwms.get_locations(
                office_id=source_office, location_ids=loc_ids
            )
            locations.extend(locations_resp.json or [])

    if verbose:
        click.echo(f"Fetched {len(locations)} locations from source")

    if dry_run:
        for loc in locations:
            click.echo(
                f"[dry-run] would store Location(name={loc['name']}) to {target_cda} ({source_office})"
            )
        return

    # init target once
    cwms.init_session(api_root=target_cda, api_key=target_api_key)

    errors = 0
    for loc in locations:
        try:
            if loc['active'] is True:
                result = cwms.store_location(data=loc, fail_if_exists=False)
                if verbose:
                    click.echo(result)
        except Exception as e:
            errors += 1
            click.echo(f"Error storing location {loc}: \n\t{e}", err=True)

    if errors:
        raise click.ClickException(f"Completed with {errors} error(s).")
    if verbose:
        click.echo("Done.")
