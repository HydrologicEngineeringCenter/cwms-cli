import json
import ssl
import urllib.error
import urllib.request


class HttpClient:
    """HTTP client to send POST and GET requests using urllib"""

    def __init__(
        self,
        base_url: str,
        dry_run: bool = False,
        version=None,
        ignore_ssl_errors=False,
    ):
        """Initialize the HTTP client

        Args:
            base_url (str): The base URL to send requests to
            dry_run (bool, optional): If True, the request will not be sent. Defaults to False.
            version (str, optional): The API version to include in the headers. Defaults to None.

        Example usage:
        ```python
        from scada_ts.httpclient import HttpClient

        client = HttpClient(
            base_url="https://api.example.com"
        )

        response_code, response_body = client.post("path/to/endpoint", data={"key": "value"},
          headers
            {
                "Content-Type": "application/json",
                "Accept": "application/json;version=1.0"
            })
        ```
        """
        self.ssl_context = ssl.create_default_context()
        if ignore_ssl_errors:
            self.ssl_context = ssl._create_unverified_context()
        self.dry_run = dry_run
        # Remove trailing slash from base URL
        self.base_url = base_url.rstrip("/")

    def post(self, path: str, data: dict, headers: dict) -> tuple[int, str]:
        """Send a POST request to the specified path with the provided data

        Args:
            path (str): The path to send the POST request to
            data (dict): The data to send in the request
            headers (dict, optional): Headers to include in the request. Defaults to None.

        Returns:
            tuple[int, str]: The HTTP status code and the response body
        """
        # Remove leading slash from path
        url = f"{self.base_url}/{path.lstrip('/')}"
        _data = json.dumps(data).encode("utf-8")
        request = urllib.request.Request(
            url, data=_data, headers=headers, method="POST"
        )
        if self.dry_run:
            return 200, {"url": url, "data": data, "headers": headers}
        try:
            with urllib.request.urlopen(request, context=self.ssl_context) as response:
                response_body = response.read().decode("utf-8")
                return response.getcode(), {
                    "body": response_body,
                    "url": url,
                    "response": {
                        "headers": response.getheaders(),
                        "status_code": response.getcode(),
                    },
                }
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")
        except urllib.error.URLError as e:
            return -1, str(e.reason)

    def get(self, path: str) -> tuple[int, str]:
        """Send a GET request to the specified path

        Args:
            path (str): The path to send the GET request to

        Returns:
            tuple[int, str]: The HTTP status code and the response body
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        request = urllib.request.Request(url, headers=self.headers, method="GET")
        if self.dry_run:
            return 200, {"url": url, "headers": self.headers}
        try:
            with urllib.request.urlopen(request) as response:
                response_body = response.read().decode("utf-8")
                return response.getcode(), response_body
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")
        except urllib.error.URLError as e:
            return -1, str(e.reason)
