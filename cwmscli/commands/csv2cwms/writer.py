import traceback

import cwms


def write_timeseries(
    file_name, ts_data, config_item, office, dry_run, config_path, logger
):
    if dry_run:
        logger.info("DRY RUN enabled. No data will be posted")

    for ts_object in ts_data:
        try:
            ts_object.update({"office-id": office})
            logger.info(
                "Store Rule: " + config_item.get("store_rule", "")
                if config_item.get("store_rule", "")
                else f"No Store Rule specified, will default to REPLACE_ALL in {config_path}."
            )
            if dry_run:
                logger.info(f"DRY RUN: {ts_object}")
            else:
                cwms.store_timeseries(
                    data=ts_object,
                    store_rule=config_item.get("store_rule", "REPLACE_ALL"),
                )
                logger.info(f"Stored {ts_object['name']} values")
        except Exception as e:
            logger.error(
                f"Error posting data for {file_name}: {e}\n{traceback.format_exc()}"
            )
