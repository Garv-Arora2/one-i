from argparse import Namespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.cli import cmd_copy_db
from app.db.base import Base
from app.seed.loader import load_demo_data


def _counts(engine):
    with engine.connect() as connection:
        return {
            table.name: connection.execute(select(func.count()).select_from(table)).scalar()
            for table in Base.metadata.sorted_tables
        }


def test_copy_db_moves_every_row_and_refuses_a_non_empty_target(tmp_path):
    source_url = f"sqlite+pysqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite+pysqlite:///{tmp_path / 'target.db'}"
    source, target = create_engine(source_url), create_engine(target_url)
    Base.metadata.create_all(source)
    Base.metadata.create_all(target)
    with sessionmaker(bind=source, future=True)() as session:
        load_demo_data(session)
        session.commit()

    args = Namespace(source=source_url, target=target_url)
    assert cmd_copy_db(args) == 0
    copied = _counts(target)
    assert copied == _counts(source)
    assert copied["articles"] > 0 and copied["events"] > 0

    assert cmd_copy_db(args) == 1
    assert _counts(target) == copied
