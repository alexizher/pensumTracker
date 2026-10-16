import ssl
from typing import Any
from urllib.parse import urlsplit

from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context


class LegacyTLSAdapter(HTTPAdapter):
    """Adaptador para los servidores de la UdeA, que aún negocian TLS antiguo."""

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        ctx.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)


def is_udea_host(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "udea.edu.co" or host.endswith(".udea.edu.co")
