"""货币战争 策略插件机制测试(D-34/§11.10)—— 纯逻辑,不依赖游戏。

验证:
- ``StrategyManager`` 发现 BUILTIN ``default`` + THIRD_PARTY 临时插件 + 去重报错 + 实例化回退。
- ``DefaultCwStrategy`` 薄委托(每个钩子→既有模块函数,行为等价)。
- ``StrategySession`` 生命周期 + ``rng`` 可种子化复现。
用 mock config(SimpleNamespace)避免 config IO;THIRD_PARTY 用 tempfile 造假插件。
"""
from __future__ import annotations

import random
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.operation.application.plugin_info import PluginSource
from sr_od.application.currency_war import cw_strategy as _cw_strategy_mod
from sr_od.application.currency_war.cw_decisions import (
    MegastarOption,
    PartnerOption,
    PickEvent,
)
from sr_od.application.currency_war.cw_state import GameState, ShopCard
from sr_od.application.currency_war.cw_strategy import (
    CurrencyWarMatch,
    CwStrategy,
    StrategySession,
)
from sr_od.application.currency_war.cw_strategy_manager import StrategyManager
from sr_od.application.currency_war.strategies.default_strategy import DefaultCwStrategy


def _cfg(**overrides) -> SimpleNamespace:
    """mock CurrencyWarConfig(纯属性,策略钩子用 getattr 读)。"""
    base = {
        "faction_priority": ["贝洛伯格", "仙舟", "巡海游侠"],
        "character_priority": ["阿格莱雅"],
        "economy_mode": "adaptive",
        "event_whitelist": {"中产阶级": 82, "定期福利": 90},
        "boss_counter": {"电视机": ["昼之半神"]},
        "dot_punish_envs": ["净化身心"],
        "character_build_around": [],
        "strategy_id": "default",
        "strategy_seed": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _builtin_dirs() -> list[tuple[Path, PluginSource]]:
    """BUILTIN 策略目录(src/.../currency_war/strategies/)。"""
    builtin = Path(_cw_strategy_mod.__file__).parent / "strategies"
    return [(builtin, PluginSource.BUILTIN)]


# —— StrategyManager 发现 / 去重 / 实例化 / 回退 ——


def test_discovers_default_builtin() -> None:
    """BUILTIN 扫描发现 ``default``(DefaultCwStrategy)。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    ids = [info.strategy_id for info in mgr.strategies]
    assert "default" in ids
    default_info = next(i for i in mgr.strategies if i.strategy_id == "default")
    assert default_info.name == "内置默认策略"
    assert default_info.source == PluginSource.BUILTIN


def test_instantiate_default() -> None:
    """instantiate('default') → DefaultCwStrategy 实例。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    strat = mgr.instantiate("default")
    assert isinstance(strat, DefaultCwStrategy)


def test_instantiate_missing_falls_back_to_default() -> None:
    """instantiate(不存在的 id)→ 回退 DefaultCwStrategy(§11.5)。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    strat = mgr.instantiate("totally_nonexistent_strategy")
    assert isinstance(strat, DefaultCwStrategy)


def test_third_party_discovery() -> None:
    """THIRD_PARTY:临时目录造假策略 → 自动发现 + 实例化(对标 app 插件)。"""
    # 第三方策略必须放子目录(不能直接放 plugins 根,§11.5)
    with tempfile.TemporaryDirectory() as tmp:
        pkg_dir = Path(tmp) / "my_test_strategy"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
        (pkg_dir / "my_strategy.py").write_text(
            "from sr_od.application.currency_war.strategies.default_strategy "
            "import DefaultCwStrategy\n"
            "class MyTestStrategy(DefaultCwStrategy):\n"
            "    STRATEGY_ID = 'my_test_strategy'\n"
            "    STRATEGY_NAME = '测试第三方策略'\n"
            "    AUTHOR = 'tester'\n",
            encoding="utf-8",
        )
        mgr = StrategyManager(ctx=None, plugin_dirs=[
            (Path(tmp), PluginSource.THIRD_PARTY),
        ])
        ids = [info.strategy_id for info in mgr.strategies]
        assert "my_test_strategy" in ids
        info = next(i for i in mgr.strategies if i.strategy_id == "my_test_strategy")
        assert info.source == PluginSource.THIRD_PARTY
        assert info.is_third_party
        strat = mgr.instantiate("my_test_strategy")
        assert strat.STRATEGY_ID == "my_test_strategy"


def test_duplicate_strategy_id_raises() -> None:
    """STRATEGY_ID 重复 → 扫描报错(对标 app 插件 APP_ID 唯一性)。"""
    with tempfile.TemporaryDirectory() as tmp:
        # 两个子目录各放一个 STRATEGY_ID='dup' 的策略 → 第二个注册时冲突
        for sub in ("a", "b"):
            pkg = Path(tmp) / sub
            pkg.mkdir()
            (pkg / "__init__.py").write_text("", encoding="utf-8")
            (pkg / f"{sub}.py").write_text(
                "from sr_od.application.currency_war.strategies.default_strategy "
                "import DefaultCwStrategy\n"
                f"class S{sub}(DefaultCwStrategy):\n"
                "    STRATEGY_ID = 'dup'\n"
                "    STRATEGY_NAME = 'dup'\n",
                encoding="utf-8",
            )
        mgr = StrategyManager(ctx=None, plugin_dirs=[
            (Path(tmp), PluginSource.THIRD_PARTY),
        ])
        mgr.discover()   # 显式扫描(触发重复检测;scan_failures 属性不 auto-discover,需先调)
        # 重复 → 第二个不注册(strategies 只剩一个 'dup')+ scan_failures 记录冲突
        dup_registered = [i for i in mgr.strategies if i.strategy_id == "dup"]
        assert len(dup_registered) == 1
        assert any("dup" in msg and "重复" in msg
                   for _f, msg in mgr.scan_failures)


# —— DefaultCwStrategy 薄委托:每个钩子→既有模块函数(行为等价于今天打法)——


def test_create_session() -> None:
    """create_session → StrategySession(rng + performance 就绪,target None)。"""
    strat = DefaultCwStrategy()
    session = strat.create_session(_cfg())
    assert isinstance(session, StrategySession)
    assert session.target_comp is None
    assert isinstance(session.rng, random.Random)
    assert session.performance is not None


def test_update_target_writes_session() -> None:
    """首轮 update_target → 写 session.target_comp(select_comp 首选)。"""
    strat = DefaultCwStrategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    state = GameState(gold=50, level=6, plane=1, round_num=3, board={"贝洛伯格": 3})
    strat.update_target(state, session, cfg)
    assert session.target_comp is not None
    # 再次调(已有 target)→ 不抛错(maybe_pivot 路径,无强信号保持)
    strat.update_target(state, session, cfg)


def test_decide_prep_returns_actions() -> None:
    """decide_prep → 委托 plan,返回 Action 列表(读 session.target_comp/rng)。"""
    strat = DefaultCwStrategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    state = GameState(gold=40, level=5, plane=1, round_num=2,
                      shop=[ShopCard(x=400, faction="贝洛伯格", name="阿格莱雅", cost=1)],
                      board={"贝洛伯格": 2})
    strat.update_target(state, session, cfg)
    actions = strat.decide_prep(state, session, cfg)
    assert isinstance(actions, list)


def test_decide_invest_delegates_decide_event() -> None:
    """decide_invest → 委托 decide_event,返回 PickEvent(白名单命中)。"""
    strat = DefaultCwStrategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    state = GameState()
    pick = strat.decide_invest("strategy", ["定期福利", "未知策略"], state, session, cfg)
    assert isinstance(pick, PickEvent)
    # 白名单「定期福利」=90 > 「未知策略」→ 选 idx=0
    assert pick.option_idx == 0


def test_decide_megastar_fallback_idx0_when_no_charid() -> None:
    """decide_megastar:候选 char_id 全空(OCR 未就绪)→ idx=0(今天盲点左候选)。"""
    strat = DefaultCwStrategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    state = GameState()
    options = [MegastarOption(idx=0), MegastarOption(idx=1), MegastarOption(idx=2)]
    pick = strat.decide_megastar(options, state, session, cfg)
    assert pick.idx == 0


def test_decide_partner_fallback_idx0_when_no_charid() -> None:
    """decide_partner:候选 char_id 全空 → idx=0(今天盲点 stage 立绘)。"""
    strat = DefaultCwStrategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    state = GameState()
    options = [PartnerOption(idx=0), PartnerOption(idx=1)]
    pick = strat.decide_partner(options, state, session, cfg)
    assert pick.idx == 0


# —— StrategySession 生命周期 + rng 种子复现(D-34/§11.4)——


def test_rng_seed_reproducible() -> None:
    """同 seed → session.rng 序列一致(公平/replay;只种子化策略内部随机)。"""
    s1 = StrategySession()
    s2 = StrategySession()
    s1.rng = random.Random(42)
    s2.rng = random.Random(42)
    assert [s1.rng.random() for _ in range(5)] == [s2.rng.random() for _ in range(5)]


def test_currency_war_match_holds_strategy_and_session() -> None:
    """CurrencyWarMatch 轻容器持有 strategy + session。"""
    strat = DefaultCwStrategy()
    session = strat.create_session(_cfg())
    match = CurrencyWarMatch(strat, session)
    assert match.strategy is strat
    assert match.session is session


def test_on_round_end_records_performance() -> None:
    """on_round_end → session.performance.record(obs)(默认实现非空;P1 无 caller 但实现就位)。"""
    from sr_od.application.currency_war.cw_performance import RoundOutcome
    strat = DefaultCwStrategy()
    session = strat.create_session(_cfg())
    obs = RoundOutcome(round_num=1, plane=1, node_type="普通战斗", comp_tag="x", hp_after=90)
    strat.on_round_end(GameState(), session, _cfg(), obs)
    assert len(session.performance.history) == 1


def test_cwstrategy_is_abstract() -> None:
    """CwStrategy ABC 不能直接实例化(全 abstract 钩子)。"""
    with pytest.raises(TypeError):
        CwStrategy()  # type: ignore[abstract]
