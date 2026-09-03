"""ScreenRecognizer / ScreenRecognizerRegistry / RecognizerScanResult 单元测试(纯逻辑,无游戏依赖)。"""
from unittest.mock import MagicMock

from one_dragon.base.screen.screen_recognizer import (
    RecognizerScanResult,
    ScreenRecognizer,
    ScreenRecognizerRegistry,
)


class _DummyRecognizer(ScreenRecognizer):
    """测试用具体 recognizer。"""

    screen_name: str = '测试画面'

    def recognize(self, ctx, image, screen_info) -> dict | None:  # noqa: ANN001
        return {'ok': True}


class _OtherRecognizer(ScreenRecognizer):
    """另一个画面。"""

    screen_name: str = '另一画面'

    def recognize(self, ctx, image, screen_info) -> dict | None:  # noqa: ANN001
        return None


class _EmptyNameRecognizer(ScreenRecognizer):
    """screen_name 为空(违例)。"""

    screen_name: str = ''

    def recognize(self, ctx, image, screen_info) -> dict | None:  # noqa: ANN001
        return None


# ---------- ScreenRecognizerRegistry ----------

def test_register_and_get() -> None:
    """register 成功 → get 能取到;未注册画面 → None。"""
    reg = ScreenRecognizerRegistry()
    assert reg.get('测试画面') is None
    assert reg.register(_DummyRecognizer()) is None          # 成功返 None
    assert isinstance(reg.get('测试画面'), _DummyRecognizer)
    assert reg.get('不存在') is None


def test_register_rejects_empty_screen_name() -> None:
    """screen_name 为空 → 返错误描述(不抛),不入表。"""
    reg = ScreenRecognizerRegistry()
    err = reg.register(_EmptyNameRecognizer())
    assert err is not None
    assert '为空' in err
    assert reg.get('') is None


def test_register_rejects_duplicate_screen_name_first_wins() -> None:
    """重复 screen_name → 返错误描述(含两个类名),先注册者胜。"""

    class _DupA(ScreenRecognizer):
        screen_name: str = '重复画面'

        def recognize(self, ctx, image, screen_info) -> None:  # noqa: ANN001
            return None

    class _DupB(ScreenRecognizer):
        screen_name: str = '重复画面'

        def recognize(self, ctx, image, screen_info) -> None:  # noqa: ANN001
            return None

    reg = ScreenRecognizerRegistry()
    assert reg.register(_DupA()) is None
    err = reg.register(_DupB())
    assert err is not None
    assert '重复' in err
    assert '_DupA' in err and '_DupB' in err
    # 先注册者(_DupA)胜
    assert isinstance(reg.get('重复画面'), _DupA)


def test_screen_names_sorted() -> None:
    """screen_names 返回已注册画面名(排序)。"""
    reg = ScreenRecognizerRegistry()
    reg.register(_OtherRecognizer())
    reg.register(_DummyRecognizer())
    assert reg.screen_names() == ['另一画面', '测试画面']


# ---------- RecognizerScanResult ----------

def test_scan_result_defaults() -> None:
    """RecognizerScanResult 默认空 registry + 空 failures。"""
    result = RecognizerScanResult()
    assert result.failures == []
    assert result.registry.screen_names() == []


# (2026-09-03 攻击性排查:原 test_scan_result_carries_failures 删除——
#  字段赋值透传断言(dataclass 行为,纪律 18)。)


# ---------- ScreenRecognizer 基类 ----------

def test_base_recognize_not_implemented() -> None:
    """基类 recognize 默认抛 NotImplementedError(子类必须实现)。"""
    base = ScreenRecognizer()
    base.screen_name = 'x'   # type: ignore[method-assign]
    try:
        base.recognize(MagicMock(), MagicMock(), MagicMock())
    except NotImplementedError:
        return
    raise AssertionError('基类 recognize 应抛 NotImplementedError')
