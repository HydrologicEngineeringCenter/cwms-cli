import logging

import cwms

from cwmscli.utils import init_cwms_session

rating_types = {
    "store_corr": {"db_type": "db_corr", "db_disc": "USGS-CORR"},
    "store_base": {"db_type": "db_base", "db_disc": "USGS-BASE"},
    "store_exsa": {"db_type": "db_exsa", "db_disc": "USGS-EXSA"},
}


def rating_ini_file_import(api_root, api_key, ini_filename, dry_run=False):
    if dry_run:
        logging.info("DRY RUN MODE - no changes will be made")
        init_cwms_session(cwms, api_root=api_root)
    else:
        init_cwms_session(cwms, api_root=api_root, api_key="apikey " + api_key)

    logging.info(f"CDA connection: {api_root}")
    logging.info(f"Opening ini file: {ini_filename}")
    ini_file = open(ini_filename, "r")
    lines = ini_file.readlines()
    ini_file.close()

    params = {}
    rating_errors = []
    for i in range(len(lines)):
        line = lines[i][:-1].strip()
        try:
            line = line[: line.index("#")].strip()  # strip comments
        except:
            pass
        if not line:
            continue
        if "=" in line:
            fields = line.split("=")
            key = fields[0].strip().lower()
            value = fields[1].strip()
            if key == "cwms_office":
                value = value.upper()
            params[key] = value
        else:
            fields = parse_ini_line(line)
            if fields[0] in rating_types.keys():
                # Find the database reference in the fields (e.g., $($db_tail), $($db_exsa), etc.)
                db_key = None
                for field in fields[1:]:
                    if field.startswith("$(") and field.endswith(")"):
                        # Extract the key name from $(...), e.g., "db_exsa" from "$($db_exsa)"
                        potential_key = field[2:-1].lstrip("$")
                        if potential_key in params:
                            db_key = potential_key
                            break

                if db_key:
                    rating_spec = params[db_key]
                    # Substitute any custom parameters found in rating_spec
                    for param_key, param_value in params.items():
                        placeholder = f"\\${param_key}"
                        if placeholder in rating_spec:
                            rating_spec = rating_spec.replace(placeholder, param_value)
                    logging.info(f"Updating rating specification: {rating_spec}")
                    try:
                        update_rating_spec(
                            rating_spec,
                            params.get("cwms_office"),
                            rating_types[fields[0]]["db_disc"],
                            dry_run=dry_run,
                        )
                        if not dry_run:
                            logging.info("SUCCESS: rating specification changes stored")
                    except:
                        logging.error(
                            "ERROR: rating specificataion could not be update"
                        )
                        rating_errors.append(
                            [rating_spec, rating_types[fields[0]]["db_disc"]]
                        )
    logging.info(
        f"ERRORS: The following rating specifications could not be updated {rating_errors}"
    )


def parse_ini_line(line):
    """
    Parses a line in the ini_file into fields
    """
    if line.find("'") > 0 or line.find('"') > 0:
        # ---------------------------#
        # fields with spaces quoted #
        # ---------------------------#
        c1 = [c for c in line]
        escape = False
        quote = None
        c2 = []
        for c in c1:
            if c == "\\":
                escape = not escape
                if not escape:
                    c2.append(c)
                continue
            if c in ('"', "'"):
                if not quote:
                    quote = c
                    continue
                if c == quote:
                    quote = None
                    continue
            if c.isspace() and quote:
                c = chr(0)
            c2.append(c)
        fields = "".join(c2).split()
        for i in range(len(fields)):
            fields[i] = fields[i].replace(chr(0), " ")
    elif line.find("\t") > 0:
        # ------------------------------------------------------------#
        # all fields without spaces separated by tabs (version < 5.0 #
        # ------------------------------------------------------------#
        fields = line.split("\t")
    else:
        # -----------------------#
        # no fields with spaces #
        # -----------------------#
        fields = line.split()
    return fields


def update_rating_spec(rating_id, office_id, db_disc, dry_run=False):
    rating_spec = cwms.get_rating_spec(rating_id=rating_id, office_id=office_id)
    data = rating_spec.df
    data = data.drop("effective-dates", axis=1)
    logging.info(f"Setting source-agency to USGS")
    data["source-agency"] = "USGS"
    logging.info(f"Setting Active, Auto-update, Auto-Activate to True")
    data["active"] = True
    data["auto-update"] = True
    data["auto-activate"] = True
    if "description" in data.columns:
        if db_disc not in data.loc[0, "description"]:
            data["description"] = data["description"] + " " + db_disc
    else:
        data["description"] = db_disc
    disc = data.loc[0, "description"]
    logging.info(f"Saving specification discription as: {disc}")
    data_xml = cwms.rating_spec_df_to_xml(data)
    if dry_run:
        logging.info("DRY RUN: Would store rating specification with XML:")
        logging.info(data_xml)
    else:
        cwms.store_rating_spec(data=data_xml, fail_if_exists=False)
