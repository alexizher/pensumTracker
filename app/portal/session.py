from typing import TYPE_CHECKING, Any

import requests
from requests.adapters import BaseAdapter

from app.core.config import get_settings
from app.core.errors import PortalUnavailable
from app.portal.tls import LegacyTLSAdapter, is_udea_host

if TYPE_CHECKING:
    from app.portal.credentials import PortalCredentials

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_COOKIE_DOMAIN = ".udea.edu.co"


class PortalSession(requests.Session):
    def __init__(self, timeout: tuple[float, float] | None = None) -> None:
        super().__init__()
        if timeout is None:
            settings = get_settings()
            timeout = (settings.portal_connect_timeout, settings.portal_read_timeout)
        self._timeout = timeout
        self._legacy_adapter = LegacyTLSAdapter()
        self.headers.update({"User-Agent": _USER_AGENT})
        self.udeasecure: str = ""
        self.credentials: PortalCredentials | None = None
        self.closed: bool = False

    def get_adapter(self, url: str) -> BaseAdapter:
        if is_udea_host(url):
            return self._legacy_adapter
        return super().get_adapter(url)

    # Firma genérica a propósito: solo se añaden el timeout por defecto y la traducción de errores.
    def request(self, *args: Any, **kwargs: Any) -> requests.Response:  # type: ignore[override]
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self._timeout
        try:
            return super().request(*args, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise PortalUnavailable() from exc

    def _write_udeasecure(self) -> None:
        self.cookies.set("udeasecure", self.udeasecure, domain=_COOKIE_DOMAIN, path="/")

    def set_udeasecure(self, value: str) -> None:
        self.udeasecure = value
        self._write_udeasecure()

    def tsone_get(self, url: str) -> requests.Response:
        if self.udeasecure:
            self._write_udeasecure()
        return self.get(url, allow_redirects=True)

    def tsone_post(self, url: str, data: dict[str, str]) -> requests.Response:
        if self.udeasecure:
            self._write_udeasecure()
        return self.post(url, data=data, allow_redirects=True)

    def close(self) -> None:
        super().close()
        self._legacy_adapter.close()
        self.credentials = None
        self.udeasecure = ""
        self.cookies.clear()
        self.closed = True

    @classmethod
    def from_cookies(cls, cookies: dict[str, str]) -> "PortalSession":
        session = cls()
        for name, value in cookies.items():
            if name in ("user_name", "udeasecure"):
                session.cookies.set(name, value, domain=_COOKIE_DOMAIN, path="/")
            elif name == "phpsessid_ayudame2":
                session.cookies.set("PHPSESSID", value, domain="ayudame2.udea.edu.co", path="/")
        session.udeasecure = cookies.get("udeasecure", "")
        return session
