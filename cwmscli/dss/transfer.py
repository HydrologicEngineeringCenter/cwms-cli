from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Optional, Protocol

from cwmscli.dss.naming import ExportRule, ImportRule

logger = logging.getLogger(__name__)


class TimeSeriesSource(Protocol):
    def catalog(self) -> Iterable[str]: ...

    def retrieve(self, identifier: str): ...


class TimeSeriesSink(Protocol):
    def store(self, timeseries) -> None: ...


class NullSink:
    def store(self, timeseries) -> None:
        pass


@dataclass
class TransferSummary:
    discovered: int = 0
    transferred: int = 0
    skipped: int = 0
    failed: int = 0


def transfer_all(
    *,
    source: TimeSeriesSource,
    sink: TimeSeriesSink,
    resolve: Callable[[str], object],
    transform: Callable[[object, object], object],
    dry_run: bool,
    identifiers: Optional[Iterable[str]] = None,
) -> TransferSummary:
    summary = TransferSummary()
    catalog = source.catalog() if identifiers is None else identifiers
    for identifier in sorted(catalog, key=str.lower):
        summary.discovered += 1
        try:
            rule = resolve(identifier)
            if rule is None:
                summary.skipped += 1
                logger.debug("Skipped unmapped time series %s", identifier)
                continue
            timeseries = source.retrieve(identifier)
            timeseries = transform(timeseries, rule)
            if dry_run:
                logger.info("Would transfer %s -> %s", identifier, timeseries.name)
            else:
                sink.store(timeseries)
                logger.info("Transferred %s -> %s", identifier, timeseries.name)
            summary.transferred += 1
        except Exception:
            summary.failed += 1
            logger.exception("Failed to transfer %s", identifier)
    return summary


def transform_import(timeseries, rule: ImportRule):
    source_unit = timeseries.unit
    if timeseries.time_zone is None:
        timeseries.ilabel_as_time_zone("UTC")
    if rule.factor != 1.0:
        timeseries.data.loc[:, "value"] *= rule.factor
    timeseries.name = rule.tsid
    timeseries.iset_unit(rule.cwms_unit or source_unit)
    return timeseries


def transform_export(timeseries, rule: ExportRule, dss_time_zone: str):
    parameter_type = timeseries.name.split(".")[2]
    if rule.cwms_unit:
        timeseries.ito(rule.cwms_unit)
    if timeseries.time_zone:
        timeseries.iconvert_to_time_zone(dss_time_zone)
    else:
        timeseries.ilabel_as_time_zone(dss_time_zone)
    if rule.factor != 1.0:
        timeseries.data.loc[:, "value"] *= rule.factor
    source_unit = timeseries.unit
    timeseries.name = rule.pathname
    timeseries.iset_parameter_type(parameter_type)
    timeseries.iset_unit(rule.dss_unit or source_unit)
    return timeseries


class DssSource:
    def __init__(self, filename: str, start: datetime, end: datetime):
        from hec import DssDataStore

        self._start = start.astimezone(timezone.utc)
        self._end = end.astimezone(timezone.utc)
        # The native hecdss date converter requires naive bounds, which it
        # interprets in each record's local clock. Read a safe envelope and
        # apply the exact aware window after timezone metadata is restored.
        dss_start = (self._start - timedelta(days=1)).replace(tzinfo=None)
        dss_end = (self._end + timedelta(days=1)).replace(tzinfo=None)
        self._store = DssDataStore.open(
            filename, read_only=True, start_time=dss_start, end_time=dss_end
        )

    def catalog(self):
        return self._store.catalog("timeseries", condensed=True)

    def retrieve(self, identifier: str):
        timeseries = self._store.retrieve(identifier)
        data = timeseries.data
        outside_window = (data.index < self._start) | (data.index > self._end)
        data.drop(index=data.index[outside_window], inplace=True)
        return timeseries

    def close(self):
        self._store.close()


class DssSink:
    def __init__(self, filename: str):
        from hec import DssDataStore

        self._store = DssDataStore.open(
            filename, read_only=False, store_rule="REPLACE_ALL"
        )

    def store(self, timeseries):
        self._store.store(timeseries)

    def close(self):
        self._store.close()


class CwmsSource:
    def __init__(
        self,
        api_root: str,
        office: str,
        start: datetime,
        end: datetime,
        api_key: Optional[str],
        token: Optional[str],
    ):
        from hec import CwmsDataStore

        kwargs = dict(
            office=office,
            read_only=True,
            start_time=start,
            end_time=end,
            time_zone="UTC",
        )
        self._store = CwmsDataStore.open(api_root, **kwargs)
        _apply_credentials(api_root, api_key, token)

    def catalog(self):
        return self._store.catalog("timeseries")

    def retrieve(self, identifier: str):
        return self._store.retrieve(identifier)

    def close(self):
        self._store.close()


class CwmsSink:
    def __init__(
        self,
        api_root: str,
        office: str,
        api_key: Optional[str],
        token: Optional[str],
    ):
        from hec import CwmsDataStore

        kwargs = dict(office=office, read_only=False, time_zone="UTC")
        self._store = CwmsDataStore.open(api_root, **kwargs)
        _apply_credentials(api_root, api_key, token)

    def store(self, timeseries):
        self._store.store(timeseries)

    def close(self):
        self._store.close()


def _apply_credentials(
    api_root: str, api_key: Optional[str], token: Optional[str]
) -> None:
    import cwms

    # CwmsDataStore reads CDA_API_KEY during construction and currently turns
    # it into an Authorization header. Reinitialize unconditionally so an
    # unrelated environment key is never leaked to a different CDA instance.
    session = cwms.init_session(api_root=api_root, token=token)
    session.headers.pop("x-api-key", None)
    session.headers.pop("Authorization", None)
    if token:
        token_value = token.strip()
        if token_value.lower().startswith("bearer "):
            token_value = token_value.split(maxsplit=1)[1]
        session.headers["Authorization"] = f"Bearer {token_value}"
        return
    if api_key:
        session.headers["Authorization"] = f"apikey {api_key}"
