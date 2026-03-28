DOCS_BASE_URL = "https://cwms-cli.readthedocs.io/en/latest/cli"
COMPLETE_CONFIG_DOC_URL = f"{DOCS_BASE_URL}/csv2cwms_complete_config.html"
SETUP_DOC_URL = f"{DOCS_BASE_URL}/setup.html"
API_ARGUMENTS_DOC_URL = f"{DOCS_BASE_URL}/api_arguments.html"
INTERVALS_DOC_URL = f"{DOCS_BASE_URL}/csv2cwms_intervals.html"
COMMAND_DOC_URL = f"{DOCS_BASE_URL}/csv2cwms.html"


def with_doc_links(message, *urls):
    unique_urls = []
    for url in urls:
        if url and url not in unique_urls:
            unique_urls.append(url)
    if not unique_urls:
        return message
    return f"{message}\nSee documentation: {', '.join(unique_urls)}"
