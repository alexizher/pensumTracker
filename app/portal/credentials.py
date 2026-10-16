from dataclasses import dataclass
from typing import Protocol

from pydantic import SecretStr

from app.core.errors import InvalidCredentials
from app.portal import auth
from app.portal.session import PortalSession


@dataclass(frozen=True)
class PortalCredentials:
    username: str
    password: SecretStr


class SessionProvider(Protocol):
    def open(self, credentials: PortalCredentials) -> PortalSession: ...


class LoginPerRequest:
    """Abre una sesión nueva por petición y no guarda nada fuera de ella."""

    def open(self, credentials: PortalCredentials) -> PortalSession:
        session = PortalSession()
        try:
            ok = auth.login(session, credentials)
        except BaseException:
            session.close()
            raise
        if not ok:
            session.close()
            raise InvalidCredentials()
        session.credentials = credentials
        return session


def get_session_provider() -> SessionProvider:
    return LoginPerRequest()
