import pytest
from simple_function import human_volume, another_human_volume

def test_human_volume_defaults():
    """Проверяем выброс ошибки при отсутствии параметров (согласно коду)."""
    with pytest.raises(ValueError):
        human_volume()

def test_human_volume_args():
    """Проверяем точный расчет объема."""
    assert pytest.approx(human_volume(weight=70, height=1.75), rel=1e-5) == 0.000375156

def test_another_human_volume_args():
    """Проверяем вторую функцию объема."""
    assert pytest.approx(another_human_volume(70, 1.63), rel=1e-5) == 0.000303152

def test_another_human_volume_defaults():
    """Проверяем стандартную ошибку типов Python для позиционных аргументов."""
    with pytest.raises(TypeError):
        another_human_volume()
