"""Portal UdeA falso para pruebas: registra en un RequestsMock todas las URLs que
PortalScraper pide durante el login y el stream, con páginas inventadas.

Toda URL va con coincidencia exacta de query string. Lo que el scraper pida y no
esté registrado falla con ConnectionError de responses.
"""

from pathlib import Path
from urllib.parse import urlsplit

import responses
from responses import matchers

TSONE = "https://tsone.udea.edu.co"
AYUDAME2 = "https://ayudame2.udea.edu.co"
CURSUM = "https://wsingenieria.udea.edu.co:8094/cursum/ingenieria"
SSO = f"{AYUDAME2}/php_mua_externos/"

HISTORIA = f"{TSONE}/php_historia_estudiante/"
CONSTANCIA = f"{TSONE}/php_constancia_estudiante/"
PENSUM = f"{AYUDAME2}/php_pensum_estudiante/"
SELECTOR = (
    f"{TSONE}/php_programas_estudiante/"
    "?app=listar"
    "&tipos=MAESTRIA,PREGRADO,DOCTORAD,ESPECIAL,PREPARAT,E-FLEXIB,SIGUEME,EXTENSIO"
    "&estados=ACTIVO,DESERTOR,CANCELO%20SEM,ADMITIDO,GRADUADO,TERMINOMATERIAS"
    "&canal=post&retorno=historia"
)

HOSTS = ("tsone.udea.edu.co", "ayudame2.udea.edu.co")
SEMESTRES = ("20241", "20242")
PENSUM_VERSIONES = (3, 5)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "portal"
HTML = "text/html; charset=utf-8"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _matcher_for(url: str) -> list:
    """Query string exacto: el de la URL, o ninguno si la URL no lleva."""
    query = urlsplit(url).query
    if not query:
        return [matchers.query_param_matcher({})]
    return [matchers.query_string_matcher(query)]


def _key(method: str, url: str) -> tuple[str, str]:
    return method.upper(), url


class FakePortal:
    def __init__(
        self,
        rsps: responses.RequestsMock,
        *,
        multi_program: bool = False,
        validar_ok: bool = True,
    ) -> None:
        self.rsps = rsps
        self.multi_program = multi_program
        self.validar_ok = validar_ok
        self._registered: dict[tuple[str, str], responses.BaseResponse] = {}
        self._register_all()

    def _add(self, method: str, url: str, **kwargs) -> None:
        key = _key(method, url)
        old = self._registered.pop(key, None)
        if old is not None:
            self.rsps.remove(old)
        base = url.split("?", 1)[0]
        response = responses.Response(
            method=method.upper(),
            url=base,
            match=_matcher_for(url),
            **kwargs,
        )
        self.rsps.add(response)
        self._registered[key] = response

    def _html(self, method: str, url: str, name: str, **kwargs) -> None:
        self._add(method, url, body=fixture(name), content_type=HTML, **kwargs)

    def _register_all(self) -> None:
        self._add("POST", SSO, body="<html><body>ok</body></html>", content_type=HTML)

        historia = f"{HISTORIA}?app=consultar"
        if self.multi_program:
            self._add("GET", historia, status=302, headers={"Location": SELECTOR})
            self._html("GET", SELECTOR, "selector_programas.html")
        else:
            self._html("GET", historia, "historia.html")
        self._html("POST", historia, "historia.html")

        for host in HOSTS:
            relogin = f"https://{host}/php_relogin/"
            self._add("POST", f"{relogin}?app=ingreso", body="", content_type=HTML)
            if self.validar_ok:
                self._add("POST", f"{relogin}?app=validar", json={"hash": f"hash-{host}"})
            else:
                self._add("POST", f"{relogin}?app=validar", json={"error": "clave"})
            end = f"https://{host}/php_libs/reauthenticate_end.php?hash=hash-{host}"
            self._add(
                "GET",
                end,
                body=fixture("reauth_end.html").replace("__HOST__", host),
                content_type=HTML,
            )
            self._add("POST", f"https://{host}/php_libs/fin.php", body="", content_type=HTML)

        self._html("GET", f"{CONSTANCIA}?app=consultar", "constancia.html")
        for sem in SEMESTRES:
            self._html("GET", f"{HISTORIA}?app=ver_semestre&semestre={sem}", f"semestre_{sem}.html")
        self._html("GET", f"{PENSUM}?app=consultar", "pensum_oficial.html")

        self._add(
            "GET",
            f"{CURSUM}/programas",
            body=fixture("cursum_programas.json"),
            content_type="application/json",
        )
        for version in PENSUM_VERSIONES:
            self._add(
                "GET",
                f"{CURSUM}/pensum/506/{version}",
                body=fixture("cursum_pensum_506.json"),
                content_type="application/json",
            )

    def override(
        self,
        method: str,
        url: str,
        *,
        body: str | bytes | Exception | None = None,
        json: object | None = None,
        status: int = 200,
    ) -> None:
        """Reemplaza la respuesta registrada para method+url (o la agrega si no existía).

        body puede ser una excepción: responses la lanza al recibir la petición.
        """
        kwargs: dict = {"status": status}
        if json is not None:
            kwargs["json"] = json
        else:
            kwargs["body"] = "" if body is None else body
            if isinstance(body, str):
                kwargs["content_type"] = HTML
        self._add(method, url, **kwargs)
