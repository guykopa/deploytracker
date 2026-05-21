from sqlalchemy.orm import Session

from deploytracker.domain.models import Service
from deploytracker.infrastructure.db.orm_models import ServiceORM


def _orm_to_domain(orm: ServiceORM) -> Service:
    return Service(
        name=orm.name,
        team=orm.team,
        created_at=orm.created_at,
    )


class SqlAlchemyServiceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, service: Service) -> Service:
        orm = ServiceORM(name=service.name, team=service.team, created_at=service.created_at)
        self._session.add(orm)
        self._session.flush()
        return _orm_to_domain(orm)

    def get(self, name: str) -> Service | None:
        orm = self._session.get(ServiceORM, name)
        if orm is None:
            return None
        return _orm_to_domain(orm)

    def list_all(self) -> list[Service]:
        rows = self._session.query(ServiceORM).order_by(ServiceORM.name).all()
        return [_orm_to_domain(r) for r in rows]
