"""test_cw_strategy 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_strategy_planner.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations

import random
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.strategies.impl.cw_strategy as _cw_strategy_mod
from one_dragon.base.operation.application.plugin_info import PluginSource
from sr_od.application.currency_war.kernel.cw_events import (
    MegastarOption,
    PartnerOption,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import GameState, PickEvent
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
    CwStrategy,
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy_manager import (
    StrategyManager,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)


def _cfg(**overrides) -> SimpleNamespace:
    """mock CurrencyWarConfig(纯属性,策略钩子用 getattr 读)。"""
    base = {
        "faction_priority": ["贝洛伯格", "仙舟", "巡海游侠"],
        "character_priority": ["阿格莱雅"],
        "character_build_around": [],
        "strategy_id": "mandate_v1",
        "strategy_seed": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _builtin_dirs() -> list[tuple[Path, PluginSource]]:
    """BUILTIN 策略目录(src/.../currency_war/strategies/)。

    锚 = 接口模块(cw_strategy)上一层,即注册面目录本身(统一迁移批
    二勘误落位:接口基类与 cw_strategy_manager 同层,均在
    strategies/impl/;注册壳在 strategies/ 顶层)。"""
    builtin = Path(_cw_strategy_mod.__file__).parents[1]
    return [(builtin, PluginSource.BUILTIN)]


# —— StrategyManager 发现 / 去重 / 实例化 / 值域 ——


def test_builtin_registry_is_mandate_v1_only() -> None:
    """BUILTIN 注册集 = mandate_v1(统一迁移批 ②:decision_v2 注册壳删除;
    原锁钉「default 栈退役后无第二内置策略」,换核批4 扩 mandate_v1,
    ② 收敛为唯一活策略核——锁改钉注册面封闭集,新增策略须显式入此清单;
    未知 id 不再回退——manager.instantiate 显式报错)。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    ids = sorted(i.strategy_id for i in mgr.strategies)
    assert ids == ["mandate_v1"]
    info = mgr.strategies[0]
    assert info.source == PluginSource.BUILTIN


def test_instantiate_mandate_v1_bridges_to_real_strategy() -> None:
    """instantiate('mandate_v1') → MandateV1Strategy 实例(锁「桥到真身」——防壳与实现脱钩)。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    strat = mgr.instantiate("mandate_v1")
    assert isinstance(strat, MandateV1Strategy)


def test_instantiate_unknown_id_raises() -> None:
    """instantiate(不存在的 id)→ 显式 ValueError(旧「回退 default」分支已随
    default 本体退役删除——静默换栈比运行报错更危险)。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    with pytest.raises(ValueError, match="mandate_v1"):
        mgr.instantiate("totally_nonexistent_strategy")


def test_instantiate_mandate_v1_default_registry() -> None:
    """mandate_v1 实例缺省持有 DEFAULT_REGISTRY(锁 registry 注入链完好,A/B 通道前提)。

    本断言为单一源:test_cw_adr0293_calibration.py 的同款注入锁已并入此处
    (重复构成并/删理由,README 纪律 8);标定值本身由该文件的字段面锁辖。"""
    mgr = StrategyManager(ctx=None, plugin_dirs=_builtin_dirs())
    strat = mgr.instantiate("mandate_v1")
    assert strat.registry is DEFAULT_REGISTRY


def test_third_party_discovery() -> None:
    """THIRD_PARTY:临时目录造假策略 → 自动发现 + 实例化(对标 app 插件)。"""
    # 第三方策略必须放子目录(不能直接放 plugins 根,§11.5)
    with tempfile.TemporaryDirectory() as tmp:
        pkg_dir = Path(tmp) / "my_test_strategy"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
        (pkg_dir / "my_strategy.py").write_text(
            "from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge "
            "import MandateV1Strategy\n"
            "class MyTestStrategy(MandateV1Strategy):\n"
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
                "from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge "
                "import MandateV1Strategy\n"
                f"class S{sub}(MandateV1Strategy):\n"
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
    strat = MandateV1Strategy()
    session = strat.create_session(_cfg())
    assert isinstance(session, StrategySession)
    assert session.target_comp is None
    assert isinstance(session.rng, random.Random)
    assert session.performance is not None


def test_session_node_type_current_contract() -> None:
    """StrategySession.node_type_current 消费契约(r265 并入)。

    写端 = prep 环写当前槽节点类型,读端 = 战斗环消费;
    默认 None(未读到)→ 消费方兜底「普通战斗」,不得误判特殊节点。"""
    s = StrategySession()
    assert s.node_type_current is None            # 默认未读到
    s.node_type_current = '遭遇'                  # 写端可写
    assert s.node_type_current == '遭遇'
    s2 = StrategySession()
    assert (s2.node_type_current or '普通战斗') == '普通战斗'   # None 兜底语义


def test_on_round_end_stores_last_hp_when_confident() -> None:
    """D-94:on_round_end 达阈置信度的结算 hp_after → 存 session.last_hp(给下回合 prep state.hp)。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome

    strat = MandateV1Strategy()
    sess = strat.create_session(_cfg())
    assert sess.last_hp is None
    obs = RoundOutcome(round_num=4, plane=1, node_type='普通战斗', comp_tag='DOT队',
                       hp_after=58, hp_confidence=1.0)   # 结算屏读对(高置信)
    strat.on_round_end(GameState(), sess, _cfg(), obs)
    assert sess.last_hp == 58


def test_on_round_end_skips_low_confidence_hp() -> None:
    """D-94:低置信(hp_confidence<阈,如结算屏 OCR 失败 hp_after=0)→ 不存(防 0 污染下回合 prep)。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome

    strat = MandateV1Strategy()
    sess = strat.create_session(_cfg())
    sess.last_hp = 70   # 上轮已存的可靠值
    obs = RoundOutcome(round_num=5, plane=1, node_type='普通战斗', comp_tag='DOT队',
                       hp_after=0, hp_confidence=0.0)   # OCR 失败(conf 0)
    strat.on_round_end(GameState(), sess, _cfg(), obs)
    assert sess.last_hp == 70, "低置信结算不应覆盖已存的可靠 HP"


def test_decide_invest_delegates_decide_event() -> None:
    """decide_invest → 委托 decide_event,返回 PickEvent(白名单命中)。"""
    strat = MandateV1Strategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    state = GameState()
    pick = strat.decide_invest("strategy", ["定期福利", "未知策略"], state, session, cfg)
    assert isinstance(pick, PickEvent)
    # 白名单「定期福利」=90 > 「未知策略」→ 选 idx=0
    assert pick.option_idx == 0


def test_decide_megastar_fallback_idx0_when_no_charid() -> None:
    """decide_megastar:候选 char_id 全空(OCR 未就绪)→ idx=0(今天盲点左候选)。"""
    strat = MandateV1Strategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    state = GameState()
    options = [MegastarOption(idx=0), MegastarOption(idx=1), MegastarOption(idx=2)]
    pick = strat.decide_megastar(options, state, session, cfg)
    assert pick.idx == 0


def test_decide_partner_fallback_idx0_when_no_charid() -> None:
    """decide_partner:候选 char_id 全空 → idx=0(今天盲点 stage 立绘)。"""
    strat = MandateV1Strategy()
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
    strat = MandateV1Strategy()
    session = strat.create_session(_cfg())
    match = CurrencyWarMatch(strat, session)
    assert match.strategy is strat
    assert match.session is session


def test_on_round_end_records_performance() -> None:
    """on_round_end → session.performance.record(obs)(观测段非空;loop 每轮胜结算调用)。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    strat = MandateV1Strategy()
    session = strat.create_session(_cfg())
    obs = RoundOutcome(round_num=1, plane=1, node_type="普通战斗", comp_tag="x", hp_after=90)
    strat.on_round_end(GameState(), session, _cfg(), obs)
    assert len(session.performance.history) == 1


def test_cwstrategy_is_abstract() -> None:
    """CwStrategy ABC 不能直接实例化(全 abstract 钩子)。"""
    with pytest.raises(TypeError):
        CwStrategy()  # type: ignore[abstract]


# —— 巨星强化角色维度已随 megastar_enhance_enabled 开关族删除——旧方案
# —— 清退批,清查报告 OLD_MIX_AUDIT §1.3;保留一条恒 None 行为锁 ——


def _comp_by_name(name: str):
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    return next(c for c in COMP_LIBRARY if c.name == name)


def _state_with_units() -> GameState:
    """前排 carry=白厄 + 后台 core=知更鸟。"""
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    s = GameState()
    s.deployed = [BenchChar(slot=1, char_id='白厄')]
    s.bench = [BenchChar(slot=1, char_id='知更鸟')]
    return s


def test_decide_megastar_enhance_intent_deleted() -> None:
    """行为锁:强化角色意向维度删除后 decide_megastar 输出恒无强化意向
    (enhance_char_id=None、reason 无后缀;候选 idx 选择不受影响)。"""
    strat = MandateV1Strategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    session.target_comp = _comp_by_name('反甲白厄')
    options = [MegastarOption(idx=0, char_id='星期日'), MegastarOption(idx=1, char_id='花火')]
    pick = strat.decide_megastar(options, _state_with_units(), session, cfg)
    assert pick.idx == 0
    assert pick.reason == 'select_megastar 命中 星期日'
    assert pick.enhance_char_id is None
