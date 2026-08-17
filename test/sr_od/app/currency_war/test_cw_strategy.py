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
from sr_od.application.currency_war.cw_events import (
    MegastarOption,
    PartnerOption,
)
from sr_od.application.currency_war.cw_state import GameState, PickEvent, ShopCard
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


def test_update_target_drought_bail_after_5_dry_rounds(monkeypatch) -> None:
    """D-92 + T#97:target 连续 5 轮 shop 无其阵营卡(shop_supply<1.0)→ 弃 target 重选(防 commit 锁死不可达)。

    live round4-6 target=DOT队 但 shop/board 始终无 持续伤害/减益 → comp 建不成 → HP4 死。
    修(D-92):update_target 追踪 target_drought;≥DROUGHT_BAIL → 弃 target(=None)→ select_comp 重选。
    T#97:DROUGHT_BAIL 3→5(3 太激进 —— shop 随机 3 轮无阵营卡是正常波动不该弃;5 容忍随机,稳 commit)。
    隔离:monkeypatch select_comp 恒返 [dot](挡住 maybe_pivot 的 pivot 噪声,专验 drought 机制)。
    """
    from sr_od.application.currency_war import cw_comps as _cw_comps
    from sr_od.application.currency_war.cw_comps import Comp
    from sr_od.application.currency_war.cw_state import GameState, ShopCard

    strat = DefaultCwStrategy()
    sess = strat.create_session(_cfg())
    dot = Comp(name="DOT队", factions=["持续伤害", "减益"], core_chars=["卡芙卡"],
               form_tiers={"持续伤害": 4, "减益": 4}, strength="B", form_difficulty="easy")
    monkeypatch.setattr(_cw_comps, "select_comp", lambda *a, **k: [dot])

    # shop 全 off-faction(无 持续伤害/减益)→ shop_supply(dot)=0.3(board-back)<1.0 → drought 累积。
    # board={持续伤害:2} 提供 emergent 信号(D-122:阵营 count≥2 才选 target),否则 target 恒 None。
    state = GameState(gold=10, hp=60, level=5, round_num=5, plane=1,
                      board={"持续伤害": 2},
                      shop=[ShopCard(x=1, faction="群攻", name="", cost=1)])

    strat.update_target(state, sess, _cfg())      # 首轮 target None → select → dot;drought 不检(=0)
    assert sess.target_comp is not None
    assert sess.target_drought == 0
    strat.update_target(state, sess, _cfg())      # target=dot,dry → drought 1
    assert sess.target_drought == 1
    strat.update_target(state, sess, _cfg())      # drought 2
    assert sess.target_drought == 2
    strat.update_target(state, sess, _cfg())      # drought 3(T#97:3→5,未达 bail)
    assert sess.target_drought == 3
    strat.update_target(state, sess, _cfg())      # drought 4
    assert sess.target_drought == 4
    strat.update_target(state, sess, _cfg())      # drought 5 → bail → 弃 target 重选 → drought 0
    assert sess.target_drought == 0, "连续 5 轮 dry 应 bail 重选,drought 归 0"
    assert sess.target_comp is not None


def test_update_target_drought_resets_when_shop_supplies(monkeypatch) -> None:
    """D-92:shop 重新出现 target 阵营卡(shop_supply=1.0)→ drought 归 0(正常 shop 波动不累积成 bail)。"""
    from sr_od.application.currency_war import cw_comps as _cw_comps
    from sr_od.application.currency_war.cw_comps import Comp
    from sr_od.application.currency_war.cw_state import GameState, ShopCard

    strat = DefaultCwStrategy()
    sess = strat.create_session(_cfg())
    dot = Comp(name="DOT队", factions=["持续伤害", "减益"], core_chars=["卡芙卡"],
               form_tiers={"持续伤害": 4, "减益": 4}, strength="B", form_difficulty="easy")
    monkeypatch.setattr(_cw_comps, "select_comp", lambda *a, **k: [dot])
    dry = GameState(gold=10, hp=60, level=5, round_num=5, plane=1,
                    board={"持续伤害": 2},   # D-122 emergent 信号(否则 target 恒 None)
                    shop=[ShopCard(x=1, faction="群攻", name="", cost=1)])
    wet = GameState(gold=10, hp=60, level=5, round_num=5, plane=1,
                    board={"持续伤害": 2},
                    shop=[ShopCard(x=1, faction="持续伤害", name="", cost=1)])  # 有 target 阵营卡

    strat.update_target(dry, sess, _cfg())   # select → dot
    strat.update_target(dry, sess, _cfg())   # drought 1
    assert sess.target_drought == 1
    strat.update_target(wet, sess, _cfg())   # shop 供上 → drought 归 0(不累积)
    assert sess.target_drought == 0


def test_update_target_emergent_no_signal_then_signal() -> None:
    """D-146:早选 target(EMERGENT_SIGNAL_COUNT 2→1)—— 阵营 count≥1(starter 任一在场,r1 即触发)。

    D-122 count≥2 太慢(spread starter 难达 r6-7,HP 在 comp 成型前崩)。改 count1:r1 starter 在场即
    选 comp + 早聚焦买(D-138)+ D-145 deploy 全板 → 快集中。无信号 = 空板(count0,无任何阵营)。
    """
    from sr_od.application.currency_war.cw_state import GameState

    strat = DefaultCwStrategy()
    sess = strat.create_session(_cfg())
    # 无信号:board 空(count0,无任何阵营)→ target 保持 None
    no_sig = GameState(gold=10, hp=60, level=4, round_num=1, plane=1, board={})
    strat.update_target(no_sig, sess, _cfg())
    assert sess.target_comp is None, "空板(无阵营 count≥1)→ target 保持 None"
    # 有信号:board 阵营 count≥1(starter 在场,r1 即触发)→ select_comp 早选 comp(D-146)
    sig = GameState(gold=10, hp=60, level=4, round_num=1, plane=1, board={"仙舟": 1})
    strat.update_target(sig, sess, _cfg())
    assert sess.target_comp is not None, "阵营 count≥1 → target 早选(D-146,select_comp 选 board-leader comp)"



def test_on_round_end_stores_last_hp_when_confident() -> None:
    """D-94:on_round_end 达阈置信度的结算 hp_after → 存 session.last_hp(给下回合 prep state.hp)。"""
    from sr_od.application.currency_war.cw_performance import (
        RoundOutcome,
    )

    strat = DefaultCwStrategy()
    sess = strat.create_session(_cfg())
    assert sess.last_hp is None
    obs = RoundOutcome(round_num=4, plane=1, node_type='普通战斗', comp_tag='DOT队',
                       hp_after=58, hp_confidence=1.0)   # 结算屏读对(高置信)
    strat.on_round_end(GameState(), sess, _cfg(), obs)
    assert sess.last_hp == 58


def test_on_round_end_skips_low_confidence_hp() -> None:
    """D-94:低置信(hp_confidence<阈,如结算屏 OCR 失败 hp_after=0)→ 不存(防 0 污染下回合 prep)。"""
    from sr_od.application.currency_war.cw_performance import RoundOutcome

    strat = DefaultCwStrategy()
    sess = strat.create_session(_cfg())
    sess.last_hp = 70   # 上轮已存的可靠值
    obs = RoundOutcome(round_num=5, plane=1, node_type='普通战斗', comp_tag='DOT队',
                       hp_after=0, hp_confidence=0.0)   # OCR 失败(conf 0)
    strat.on_round_end(GameState(), sess, _cfg(), obs)
    assert sess.last_hp == 70, "低置信结算不应覆盖已存的可靠 HP"



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
