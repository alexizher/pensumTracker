import json
from collections.abc import Iterable, Iterator

from app.core.errors import PortalFormatChanged, PortalUnavailable
from app.core.stream import Event, StreamContext, ndjson, run_stages
from app.portal.session import PortalSession


class EtapaFalsa:
    def __init__(
        self,
        name: str,
        eventos: Iterable[Event] = (),
        error: Exception | None = None,
        optional: bool = False,
    ) -> None:
        self.name = name
        self.optional = optional
        self._eventos = list(eventos)
        self._error = error
        self.corrio = False

    def run(self, ctx: StreamContext) -> Iterator[Event]:
        self.corrio = True
        yield from self._eventos
        if self._error is not None:
            raise self._error


def _ctx() -> StreamContext:
    return StreamContext(session=PortalSession(), requested_version=0)


def _lineas(etapas: list[EtapaFalsa], on_finish=lambda: None) -> list[dict[str, object]]:
    return [json.loads(linea) for linea in run_stages(etapas, _ctx(), on_finish)]


def test_etapas_en_orden():
    etapas = [
        EtapaFalsa("a", [{"stage": "a", "data": 1}]),
        EtapaFalsa("b", [{"stage": "b", "data": 2}]),
    ]
    assert _lineas(etapas) == [{"stage": "a", "data": 1}, {"stage": "b", "data": 2}]


def test_obligatoria_que_falla_corta():
    segunda = EtapaFalsa("b", [{"stage": "b", "data": 2}])
    etapas = [EtapaFalsa("a", error=PortalFormatChanged()), segunda]
    assert _lineas(etapas) == [
        {
            "stage": "error",
            "status": 502,
            "detail": "El portal de la UdeA no devolvió una respuesta válida",
        }
    ]
    assert not segunda.corrio


def test_excepcion_cualquiera_da_500():
    etapas = [EtapaFalsa("a", error=KeyError("x"))]
    assert _lineas(etapas) == [
        {"stage": "error", "status": 500, "detail": "Error inesperado al obtener el pensum"}
    ]


def test_opcional_que_falla_emite_warning_y_sigue():
    etapas = [
        EtapaFalsa("record", [{"stage": "record", "data": 1}]),
        EtapaFalsa("grades", error=PortalUnavailable(), optional=True),
        EtapaFalsa("tercera", [{"stage": "tercera", "data": 3}]),
    ]
    assert _lineas(etapas) == [
        {"stage": "record", "data": 1},
        {
            "stage": "warning",
            "source": "grades",
            "detail": "Error inesperado al obtener el pensum",
        },
        {"stage": "tercera", "data": 3},
    ]


def test_on_finish_corre_al_terminar():
    llamadas = []
    _lineas([EtapaFalsa("a", [{"stage": "a", "data": 1}])], lambda: llamadas.append(1))
    assert len(llamadas) == 1


def test_on_finish_corre_si_falla():
    llamadas = []
    _lineas([EtapaFalsa("a", error=KeyError("x"))], lambda: llamadas.append(1))
    assert len(llamadas) == 1


def test_on_finish_corre_al_cerrar_a_medias():
    llamadas = []
    etapas = [EtapaFalsa("a", [{"stage": "a", "data": 1}, {"stage": "a", "data": 2}])]
    flujo = run_stages(etapas, _ctx(), lambda: llamadas.append(1))
    next(flujo)
    flujo.close()
    assert len(llamadas) == 1


def test_ndjson_conserva_tildes():
    assert "Cálculo" in ndjson({"stage": "x", "data": "Cálculo"})
