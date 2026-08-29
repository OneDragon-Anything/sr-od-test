"""screen_recognizer_scan 扫描器单元测试(镜像 operation_registry 测法)。

扫描真实 import ``sr_od.operations`` + ``sr_od.application`` 承载包,验证发现 / 过滤 / 容错 / 缓存。
用 MagicMock 伪造 SrContext(扫描纯反射,ctx 仅占位)。
"""
import dataclasses
import importlib
from unittest.mock import MagicMock

import pytest

import sr_od.backend.screen_recognizer_scan as _scan
from one_dragon.base.screen.screen_recognizer import ScreenRecognizer
from sr_od.backend.screen_recognizer_scan import (
    _is_recognizer,
    get_recognizer,
    scan_recognizers,
)


@pytest.fixture
def mock_ctx() -> MagicMock:
    """mock SrContext:扫描纯反射,ctx 仅作 API 占位。"""
    return MagicMock(name='SrContext')


# ---------- _is_recognizer 过滤 ----------

def test_is_recognizer_true_for_subclass() -> None:
    """ScreenRecognizer 子类(同模块定义)→ True。"""

    class _R(ScreenRecognizer):
        screen_name: str = 'x'

        def recognize(self, ctx, image, screen_info) -> None:  # noqa: ANN001
            return None

    assert _is_recognizer(_R.__module__, _R) is True


def test_is_recognizer_false_for_base() -> None:
    """基类 ScreenRecognizer 本身 → False。"""
    assert _is_recognizer('one_dragon.base.screen.screen_recognizer', ScreenRecognizer) is False


def test_is_recognizer_false_for_base_suffix() -> None:
    """*Base 后缀 → False(抽象兜底)。"""

    class _RBase(ScreenRecognizer):
        screen_name: str = 'x'

        def recognize(self, ctx, image, screen_info) -> None:  # noqa: ANN001
            return None

    assert _is_recognizer(_RBase.__module__, _RBase) is False


def test_is_recognizer_false_for_non_recognizer() -> None:
    """非 ScreenRecognizer 类 → False。"""
    assert _is_recognizer(__name__, int) is False
    assert _is_recognizer(__name__, MagicMock) is False


def test_is_recognizer_false_for_rexport() -> None:
    """__module__ 守卫:从别处 import 进来的类(__module__ ≠ 当前模块)→ False。"""
    # ScreenRecognizer 定义在 one_dragon.base.screen.screen_recognizer,不是本测试模块
    assert _is_recognizer(__name__, ScreenRecognizer) is False


# ---------- scan_recognizers 发现 ----------

def test_scan_discovers_battle_prep_recognizer(mock_ctx: MagicMock) -> None:
    """扫描应发现货币战争备战 recognizer(screen_name='货币战争-备战')。"""
    result = scan_recognizers(mock_ctx, refresh=True)
    recognizer = result.registry.get('货币战争-备战')
    assert recognizer is not None
    assert type(recognizer).__name__ == 'BattlePrepRecognizer'


def test_scan_discovers_briefing_recognizer(mock_ctx: MagicMock) -> None:
    """扫描应发现货币战争简报 recognizer(screen_name='货币战争-简报')。"""
    result = scan_recognizers(mock_ctx, refresh=True)
    recognizer = result.registry.get('货币战争-简报')
    assert recognizer is not None
    assert type(recognizer).__name__ == 'BriefingRecognizer'


def test_scan_discovers_settlement_recognizer(mock_ctx: MagicMock) -> None:
    """扫描应发现货币战争结算 recognizer(screen_name='货币战争-结算')。"""
    result = scan_recognizers(mock_ctx, refresh=True)
    recognizer = result.registry.get('货币战争-结算')
    assert recognizer is not None
    assert type(recognizer).__name__ == 'SettlementRecognizer'


def test_scan_discovers_invest_strategy_recognizer(mock_ctx: MagicMock) -> None:
    """扫描应发现货币战争投资策略 recognizer(screen_name='货币战争-投资策略')。"""
    result = scan_recognizers(mock_ctx, refresh=True)
    recognizer = result.registry.get('货币战争-投资策略')
    assert recognizer is not None
    assert type(recognizer).__name__ == 'InvestStrategyRecognizer'


def test_scan_excludes_base_class(mock_ctx: MagicMock) -> None:
    """基类 ScreenRecognizer 不进注册表。"""
    result = scan_recognizers(mock_ctx, refresh=True)
    # 没有哪个注册项的实例类型是基类本身
    for name in result.registry.screen_names():
        assert type(result.registry.get(name)) is not ScreenRecognizer


def test_scan_import_failure_tolerant(mock_ctx: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """单模块 import 失败不中断扫描,记入 failures,已知 recognizer 仍出现。"""
    real_import = importlib.import_module

    def flaky_import(name: str):  # noqa: ANN202
        # currency_war/battle_prep_recognizer 不直接是顶层包名;挑一个真实存在的子模块制造失败
        if name == 'sr_od.application.currency_war.data.cw_synthesis':
            raise RuntimeError('模拟 import 失败')
        return real_import(name)

    monkeypatch.setattr(_scan.importlib, 'import_module', flaky_import)
    result = scan_recognizers(mock_ctx, refresh=True)
    assert any('cw_synthesis' in f for f in result.failures)
    # 扫描未中断,备战 recognizer 仍出现
    assert result.registry.get('货币战争-备战') is not None


def test_scan_caches_and_refresh(mock_ctx: MagicMock) -> None:
    """无 refresh 复用缓存(同一对象);refresh=True 重扫(对象可不同、内容一致)。"""
    r1 = scan_recognizers(mock_ctx, refresh=True)
    r2 = scan_recognizers(mock_ctx)              # 命中缓存
    assert r1 is r2
    r3 = scan_recognizers(mock_ctx, refresh=True)   # 强制重扫
    assert r1 is not r3
    # 内容一致(screen_name 集合相同)
    assert r1.registry.screen_names() == r3.registry.screen_names()


# ---------- get_recognizer ----------

def test_get_recognizer_hit_and_miss(mock_ctx: MagicMock) -> None:
    """get_recognizer 命中已注册画面;未注册返 None。"""
    scan_recognizers(mock_ctx, refresh=True)     # 填缓存
    assert get_recognizer(mock_ctx, '货币战争-备战') is not None
    assert get_recognizer(mock_ctx, '不存在的画面') is None


# ---------- extras_doc 字段说明(随 analyze 响应平级返回) ----------

def test_all_recognizers_declare_extras_doc(mock_ctx: MagicMock) -> None:
    """所有注册的 recognizer 都声明了非空 extras_doc(缺了调用方拿到 extras 只能猜)。"""
    result = scan_recognizers(mock_ctx, refresh=True)
    for name in result.registry.screen_names():
        recognizer = result.registry.get(name)
        assert getattr(recognizer, 'extras_doc', None), f'{name} 未声明 extras_doc'


@pytest.mark.parametrize(('recognizer_mod', 'state_cls'), [
    ('sr_od.application.currency_war.obs.recognizers.battle_prep_recognizer', '_BattlePrepState'),
    ('sr_od.application.currency_war.obs.recognizers.briefing_recognizer', '_BriefingState'),
    ('sr_od.application.currency_war.obs.recognizers.settlement_recognizer', '_SettlementState'),
    ('sr_od.application.currency_war.obs.recognizers.invest_strategy_recognizer', '_InvestStrategyState'),
])
def test_extras_doc_keys_match_state_fields(recognizer_mod: str, state_cls: str) -> None:
    """extras_doc 键集与领域模型字段一致(加 / 改字段时防漂移)。"""
    mod = importlib.import_module(recognizer_mod)
    state = getattr(mod, state_cls)
    recognizer = next(
        cls for _n, cls in vars(mod).items()
        if _is_recognizer(recognizer_mod, cls)
    )
    expected = {f.name for f in dataclasses.fields(state)}
    assert set(recognizer.extras_doc) == expected
