import pytest

from qrpersonafy.registry import FakeRegistry
from qrpersonafy.settings import Context
from qrpersonafy.system import FakeSystem


@pytest.fixture
def make_ctx(tmp_path):
    counter = iter(range(100))

    def make() -> Context:
        return Context(FakeRegistry(), FakeSystem(tmp_path / f"pc{next(counter)}"))

    return make
