"""test_cw_strategy 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_strategy_planner.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

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
    assert state_of(session).target_comp is None
    assert isinstance(session.rng, random.Random)
    assert session.performance is not None


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


def test_on_round_end_records_performance() -> None:
    """on_round_end → session.performance.record(obs)(观测段非空;loop 每轮胜结算调用)。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    strat = MandateV1Strategy()
    session = strat.create_session(_cfg())
    obs = RoundOutcome(round_num=1, plane=1, node_type="普通战斗", comp_tag="x", hp_after=90)
    strat.on_round_end(GameState(), session, _cfg(), obs)
    assert len(session.performance.history) == 1


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
    state_of(session).target_comp = _comp_by_name('反甲白厄')
    options = [MegastarOption(idx=0, char_id='星期日'), MegastarOption(idx=1, char_id='花火')]
    pick = strat.decide_megastar(options, _state_with_units(), session, cfg)
    assert pick.idx == 0
    assert pick.reason == 'select_megastar 命中 星期日'
    assert pick.enhance_char_id is None


# —— supply 失活治本:on_round_end node_type 空值回落(15 号稿批 C 残余件③)——
# 病灶:空 node_type 轮被 BloodAlarmTracker 战斗节点门整轮丢弃 → 掉血数据缺失、
# 生死窗判读缺页(supply 失活升级线 第6/7次复现)。修法 = 台账(局内轮行序
# 单一源,档案装配的局内对应物)按 (plane, round_num) 查同轮 node_type。

def _feed_round_end(strat, sess, *, round_num: int, node_type: str,
                    hp_after: int):
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    state_of(sess).v3_prev_hp = 85   # 上轮结算 hp(真值链口径)
    obs = RoundOutcome(round_num=round_num, plane=1, node_type=node_type,
                       comp_tag='x', hp_after=hp_after, hp_confidence=1.0)
    strat.on_round_end(GameState(), sess, _cfg(), obs)


def test_on_round_end_node_type_fallback_recovers_loss_window(monkeypatch) -> None:
    """supply 轮恢复计数锁:node_type 空值 + 台账该位次 = 'battle' →
    回落「普通战斗」喂 BloodAlarmTracker → 该轮掉血 **入窗**(recent_losses
    计数恢复,生死窗不再缺页)+ 分键留证(auto_resolved=True)。"""
    from sr_od.application.currency_war.kernel import cw_telemetry_exit as exit_mod
    from sr_od.application.currency_war.kernel.cw_state import get_node_ledger

    defects: list[dict] = []
    monkeypatch.setattr(exit_mod, '_record_defect',
                        lambda **kw: defects.append(kw))
    strat = MandateV1Strategy()
    sess = strat.create_session(_cfg())
    ledger = get_node_ledger(sess)
    ledger.seq_by_plane = {1: ['battle', 'supply', 'battle', 'reward', 'boss',
                              'encounter', 'battle', 'reward', 'boss']}
    _feed_round_end(strat, sess, round_num=3, node_type='', hp_after=70)
    tracker = state_of(sess).v3_alarm
    losses = [loss for _t, loss in tracker.recent_losses]
    assert losses == [15], f'掉血应恢复入窗,实得 {tracker.recent_losses}'
    assert tracker.consec_battle_fails == 1   # ≥10 = 结构性败局计数亦恢复
    assert len(defects) == 1
    assert defects[0]['kind'] == exit_mod.DEFECT_KIND_BLOOD_ALARM_NODE_FALLBACK
    assert defects[0]['auto_resolved'] is True
    assert '普通战斗' in defects[0]['observed']


def test_on_round_end_node_type_fallback_miss_keeps_empty(monkeypatch) -> None:
    """台账未命中(表缺)→ 照旧空串(不猜)+ 分键留证;tracker 不入窗
    (零行为变更面),判读侧按分键可见缺口。"""
    from sr_od.application.currency_war.kernel import cw_telemetry_exit as exit_mod

    defects: list[dict] = []
    monkeypatch.setattr(exit_mod, '_record_defect',
                        lambda **kw: defects.append(kw))
    strat = MandateV1Strategy()
    sess = strat.create_session(_cfg())   # 无台账
    _feed_round_end(strat, sess, round_num=3, node_type='', hp_after=70)
    assert list(state_of(sess).v3_alarm.recent_losses) == []   # 未命中=照旧不入窗
    assert len(defects) == 1
    assert defects[0]['auto_resolved'] is False
    assert '空串' in defects[0]['observed']


def test_on_round_end_supply_token_stays_non_battle(monkeypatch) -> None:
    """词汇表语义保持:台账 'supply' 位次 → 回落「补给」(生产词表),但
    BloodAlarmTracker 战斗节点门语义不变——非战斗节点不入窗不清臂。"""
    from sr_od.application.currency_war.kernel.cw_state import get_node_ledger

    strat = MandateV1Strategy()
    sess = strat.create_session(_cfg())
    ledger = get_node_ledger(sess)
    ledger.seq_by_plane = {1: ['battle', 'supply', 'battle', 'reward', 'boss',
                              'encounter', 'battle', 'reward', 'boss']}
    _feed_round_end(strat, sess, round_num=2, node_type='', hp_after=85)
    tracker = state_of(sess).v3_alarm
    assert list(tracker.recent_losses) == []   # 补给轮不入窗(语义不变)
    assert tracker.consec_battle_fails == 0


def test_new_session_resets_layout_unknown_streak(monkeypatch) -> None:
    """落地审 C4:跨局残留锁——上一局末未知 streak≥1 时,新局
    create_session 必须复位布局未知态计数(否则开局 level 未 observed/
    CV 高发不可判期会提前吃写面冻结)。"""
    import sr_od.application.currency_war.obs.cw_back_layout as cbl
    monkeypatch.setattr(cbl, '_unknown_streak', 2)
    strat = MandateV1Strategy()
    strat.create_session(_cfg())
    assert cbl._unknown_streak == 0, '新局未复位布局未知态计数'
