import logging as lg

# create logging for logging
logging = lg.getLogger()
if logging.hasHandlers():
    logging.handlers.clear()
handler = lg.StreamHandler()
formatter = lg.Formatter("%(asctime)s;%(levelname)s;%(message)s", "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logging.addHandler(handler)
logging.setLevel(lg.INFO)
logging.propagate = False
