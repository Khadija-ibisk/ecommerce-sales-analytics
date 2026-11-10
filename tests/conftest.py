import pytest

from sales import config, data_generation, etl


@pytest.fixture(scope="session")
def raw():
    return data_generation.generate_all(seed=1)


@pytest.fixture(scope="session")
def star(raw):
    return etl.build_star_schema(raw)


@pytest.fixture(scope="session")
def warehouse(star, tmp_path_factory):
    db = tmp_path_factory.mktemp("dw") / "warehouse.db"
    etl.load_warehouse(star, db)
    return db


@pytest.fixture
def tmp_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(config, "FIGURES_DIR", tmp_path / "figures")
    (tmp_path / "figures").mkdir()
    return tmp_path
