"""货币战争 策略插件机制测试(D-34/§11.10)—— 纯逻辑,不依赖游戏。

验证:
- ``StrategyManager`` 发现 BUILTIN ``decision_v2`` + THIRD_PARTY 临时插件 + 去重报错 + 未知 id 显式报错。
- ``DecisionV2Strategy`` 平移自持钩子(生命周期/事件/prep 步级,default 栈本体退役批平移)。
- ``StrategySession`` 生命周期 + ``rng`` 可种子化复现。
用 mock config(SimpleNamespace)避免 config IO;THIRD_PARTY 用 tempfile 造假插件。

(default 栈 ``DefaultCwStrategy`` 已退役删除:其 v1 专属行为锁(update_target
drought bail/emergent 选线、薄委托 plan 链)随本体退役——语义由 cw_intention
/decision_v2 四层的对应测试接管;本文件只留仍存活的插件机制与平移钩子锁。)
"""
from __future__ import annotations

import random
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.operation.application.plugin_info import PluginSource
from sr_od.application.currency_war import cw_strategy as _cw_strategy_mod
from sr_od.application.currency_war.cw_events import (
    MegastarOption,
    PartnerOption,
)
from sr_od.application.currency_war.cw_state import GameState, PickEvent
from sr_od.application.currency_war.cw_strategy import (
    CurrencyWarMatch,
    CwStrategy,
    StrategySession,
)
from sr_od.application.currency_war.cw_strategy_manager import StrategyManager
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)


def _cfg(**overrides) -> SimpleNamespace:
    """mock CurrencyWarConfig(纯属性,策略钩子用 getattr 读)。"""
    base = {
        "faction_priority": ["贝洛伯格", "仙舟", "巡海游侠"],
        "character_priority": ["阿格莱雅"],
        "character_build_around": [],
        "strategy_id": "decision_v2",
        "strategy_seed": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _builtin_dirs() -> list[tuple[Path, PluginSource]]:
    """BUILTIN 策略目录(src/.../currency_war/strategies/)。"""
    builtin = Path(_cw_strategy_mod.__file__).parent / "strategies"
    return [(builtin, PluginSource.BUILTIN)]


# —— StrategyManager 发现 / 去重 / 实例化 / 值域 ——


def test_builtin_registry_is_decision_v2_only() -> None:
    """BUILTIN 注册集唯一 = decision_v2(default 栈退役后无第二内置策略;
    未知 id 不再回退——manager.instantiate 显式报错)。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    ids = sorted(i.strategy_id for i in mgr.strategies)
    assert ids == ["decision_v2"]
    info = mgr.strategies[0]
    assert info.source == PluginSource.BUILTIN


def test_instantiate_decision_v2_bridges_to_real_strategy() -> None:
    """instantiate('decision_v2') → DecisionV2Strategy 实例(锁「桥到真身」——防壳与实现脱钩)。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    strat = mgr.instantiate("decision_v2")
    assert isinstance(strat, DecisionV2Strategy)


def test_instantiate_unknown_id_raises() -> None:
    """instantiate(不存在的 id)→ 显式 ValueError(旧「回退 default」分支已随
    default 本体退役删除——静默换栈比运行报错更危险)。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    with pytest.raises(ValueError, match="decision_v2"):
        mgr.instantiate("totally_nonexistent_strategy")


def test_instantiate_decision_v2_default_registry() -> None:
    """decision_v2 实例缺省持有 DEFAULT_REGISTRY(锁 registry 注入链完好,A/B 通道前提)。

    本断言为单一源:test_cw_adr0293_calibration.py 的同款注入锁已并入此处
    (重复构成并/删理由,README 纪律 8);标定值本身由该文件的字段面锁辖。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    strat = mgr.instantiate("decision_v2")
    assert strat.registry is DEFAULT_REGISTRY


def test_third_party_discovery() -> None:
    """THIRD_PARTY:临时目录造假策略 → 自动发现 + 实例化(对标 app 插件)。"""
    # 第三方策略必须放子目录(不能直接放 plugins 根,§11.5)
    with tempfile.TemporaryDirectory() as tmp:
        pkg_dir = Path(tmp) / "my_test_strategy"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
        (pkg_dir / "my_strategy.py").write_text(
            "from sr_od.application.currency_war.decision_v2.strategy "
            "import DecisionV2Strategy\n"
            "class MyTestStrategy(DecisionV2Strategy):\n"
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
                "from sr_od.application.currency_war.decision_v2.strategy "
                "import DecisionV2Strategy\n"
                f"class S{sub}(DecisionV2Strategy):\n"
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


# —— 平移自持钩子:生命周期 / 事件 / prep 步级(default 本体退役批平移进 dv)——


def test_create_session() -> None:
    """create_session → StrategySession(rng + performance 就绪,target None)。"""
    strat = DecisionV2Strategy()
    session = strat.create_session(_cfg())
    assert isinstance(session, StrategySession)
    assert session.target_comp is None
    assert isinstance(session.rng, random.Random)
    assert session.performance is not None


def test_on_round_end_stores_last_hp_when_confident() -> None:
    """D-94:on_round_end 达阈置信度的结算 hp_after → 存 session.last_hp(给下回合 prep state.hp)。"""
    from sr_od.application.currency_war.cw_performance import (
        RoundOutcome,
    )

    strat = DecisionV2Strategy()
    sess = strat.create_session(_cfg())
    assert sess.last_hp is None
    obs = RoundOutcome(round_num=4, plane=1, node_type='普通战斗', comp_tag='DOT队',
                       hp_after=58, hp_confidence=1.0)   # 结算屏读对(高置信)
    strat.on_round_end(GameState(), sess, _cfg(), obs)
    assert sess.last_hp == 58


def test_on_round_end_skips_low_confidence_hp() -> None:
    """D-94:低置信(hp_confidence<阈,如结算屏 OCR 失败 hp_after=0)→ 不存(防 0 污染下回合 prep)。"""
    from sr_od.application.currency_war.cw_performance import RoundOutcome

    strat = DecisionV2Strategy()
    sess = strat.create_session(_cfg())
    sess.last_hp = 70   # 上轮已存的可靠值
    obs = RoundOutcome(round_num=5, plane=1, node_type='普通战斗', comp_tag='DOT队',
                       hp_after=0, hp_confidence=0.0)   # OCR 失败(conf 0)
    strat.on_round_end(GameState(), sess, _cfg(), obs)
    assert sess.last_hp == 70, "低置信结算不应覆盖已存的可靠 HP"


def test_decide_invest_delegates_decide_event() -> None:
    """decide_invest → 委托 decide_event,返回 PickEvent(白名单命中)。"""
    strat = DecisionV2Strategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    state = GameState()
    pick = strat.decide_invest("strategy", ["定期福利", "未知策略"], state, session, cfg)
    assert isinstance(pick, PickEvent)
    # 白名单「定期福利」=90 > 「未知策略」→ 选 idx=0
    assert pick.option_idx == 0


def test_decide_megastar_fallback_idx0_when_no_charid() -> None:
    """decide_megastar:候选 char_id 全空(OCR 未就绪)→ idx=0(今天盲点左候选)。"""
    strat = DecisionV2Strategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    state = GameState()
    options = [MegastarOption(idx=0), MegastarOption(idx=1), MegastarOption(idx=2)]
    pick = strat.decide_megastar(options, state, session, cfg)
    assert pick.idx == 0


def test_decide_partner_fallback_idx0_when_no_charid() -> None:
    """decide_partner:候选 char_id 全空 → idx=0(今天盲点 stage 立绘)。"""
    strat = DecisionV2Strategy()
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
    strat = DecisionV2Strategy()
    session = strat.create_session(_cfg())
    match = CurrencyWarMatch(strat, session)
    assert match.strategy is strat
    assert match.session is session


def test_on_round_end_records_performance() -> None:
    """on_round_end → session.performance.record(obs)(观测段非空;loop 每轮胜结算调用)。"""
    from sr_od.application.currency_war.cw_performance import RoundOutcome
    strat = DecisionV2Strategy()
    session = strat.create_session(_cfg())
    obs = RoundOutcome(round_num=1, plane=1, node_type="普通战斗", comp_tag="x", hp_after=90)
    strat.on_round_end(GameState(), session, _cfg(), obs)
    assert len(session.performance.history) == 1


def test_cwstrategy_is_abstract() -> None:
    """CwStrategy ABC 不能直接实例化(全 abstract 钩子)。"""
    with pytest.raises(TypeError):
        CwStrategy()  # type: ignore[abstract]
