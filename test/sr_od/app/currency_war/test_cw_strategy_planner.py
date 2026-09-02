# -*- coding: utf-8 -*-
"""test_cw_strategy_planner 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- strategy: test_cw_strategy.py
- test_planner_strategy: test_planner_strategy.py
- strategy_chain_smoke: test_cw_strategy_chain_smoke.py
- w953_planner_strategy_wiring: test_cw_w953_planner_strategy_wiring.py
- w603_telemetry_wiring: test_cw_w603_telemetry_wiring.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== strategy ====================

import random
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.operation.application.plugin_info import PluginSource
import sr_od.application.currency_war.decision.cw_strategy as _cw_strategy_mod
from sr_od.application.currency_war.kernel.cw_events import  MegastarOption, PartnerOption
from sr_od.application.currency_war.kernel.cw_state import GameState, PickEvent
from sr_od.application.currency_war.decision.cw_strategy import  CurrencyWarMatch, CwStrategy, StrategySession
from sr_od.application.currency_war.decision.cw_strategy_manager import StrategyManager
from sr_od.application.currency_war.kernel.cw_registry import  DEFAULT_REGISTRY
from sr_od.application.currency_war.decision.decision_v2.strategy import  DecisionV2Strategy


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
    builtin = Path(_cw_strategy_mod.__file__).parents[1] / "strategies"
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
            "from sr_od.application.currency_war.decision.decision_v2.strategy "
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
                "from sr_od.application.currency_war.decision.decision_v2.strategy "
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
    from sr_od.application.currency_war.kernel.cw_performance import  RoundOutcome

    strat = DecisionV2Strategy()
    sess = strat.create_session(_cfg())
    assert sess.last_hp is None
    obs = RoundOutcome(round_num=4, plane=1, node_type='普通战斗', comp_tag='DOT队',
                       hp_after=58, hp_confidence=1.0)   # 结算屏读对(高置信)
    strat.on_round_end(GameState(), sess, _cfg(), obs)
    assert sess.last_hp == 58


def test_on_round_end_skips_low_confidence_hp() -> None:
    """D-94:低置信(hp_confidence<阈,如结算屏 OCR 失败 hp_after=0)→ 不存(防 0 污染下回合 prep)。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome

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
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    strat = DecisionV2Strategy()
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
    strat = DecisionV2Strategy()
    cfg = _cfg()
    session = strat.create_session(cfg)
    session.target_comp = _comp_by_name('反甲白厄')
    options = [MegastarOption(idx=0, char_id='星期日'), MegastarOption(idx=1, char_id='花火')]
    pick = strat.decide_megastar(options, _state_with_units(), session, cfg)
    assert pick.idx == 0
    assert pick.reason == 'select_megastar 命中 星期日'
    assert pick.enhance_char_id is None


# ==================== test_planner_strategy ====================

import sys
from pathlib import Path as _test_planner_strategy_Path

sys.path.insert(0, 'src')
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from sr_od.application.currency_war.kernel.cw_events import PlannerOption, decide_planner
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState as _test_planner_strategy_GameState

SHOT = r'.debug\sr_od_mcp\screenshot\screenshot_20260819_220156_428969.png'
# r104b fixtures(测试仓归档,与 .debug 解耦;局29 五态实拍)
FIX_DIR = _test_planner_strategy_Path(__file__).resolve().parents[4] / 'screens' / 'cw_planner'
FIX_EVENT = FIX_DIR / 'event_two_cards.webp'           # 事件态:左=破解芯片(弱化)/右=升费
FIX_EVENT_AGAIN = FIX_DIR / 'event_two_cards_again.webp'   # 二次事件态(内容同首次,未消费证)
FIX_DETAIL = FIX_DIR / 'detail_panel_open.webp'        # 详情面板态(点卡上半部触发)
FIX_SELECTED = FIX_DIR / 'card_selected_confirm_ready.webp'  # 选中态(右卡选中+确认亮)


def _ocr_cards(path: str) -> tuple[list[str], list[str]]:
    """离线复刻 handler 的 OCR 卡文字提取(左/右)——框架 OnnxOcrMatcher(模型路径自动解析)。

    实测(局29 存档画面):左=「使后续节点【弱化】，降低敌人属性。/破解芯片」、
    右=「提升费用至4费，变为1星银」——y 300-420 过滤带 + x<960 分流正确。
    """
    import cv2
    import numpy as np
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        m = OnnxOcrMatcher()
    except Exception:
        return [], []
    img = cv2.imdecode(np.fromfile(path, dtype='uint8'), cv2.IMREAD_COLOR)
    res = m.run_ocr(img)
    left, right = [], []
    LO, HI = 300, 420
    for t, mr in (res or {}).items():
        if mr.max is None:
            continue
        cy = mr.max.center.y
        cx = mr.max.center.x
        if LO <= cy <= HI and cx < 1750:   # 右侧详情面板数值列(1413+)不进卡文字
            (left if cx < 960 else right).append(t)
    return left, right


def test_planner_strategy_upgrade_wolf_line():
    """银狼线:升费 100+30=130 > 弱化 55 → 选升费。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '狼尊欢愉')
    st = _test_planner_strategy_GameState(hp=80)
    st.bench = [BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2, position_pref='front')]
    opts = [PlannerOption(idx=0, text='提升费用至4费,变为1星银狼'),
            PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')]
    pick = decide_planner(opts, st, tgt)
    assert pick.idx == 0 and '升费' in pick.reason


def test_planner_strategy_weaken_low_hp():
    """非银狼线+银狼不在场+低血:升费 100-60=40 < 弱化 55+20=75 → 弱化。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '反甲白厄')
    st = _test_planner_strategy_GameState(hp=30)
    st.bench = [BenchChar(slot=1, char_id='白厄', faction='?', star=1, position_pref='front')]
    opts = [PlannerOption(idx=0, text='提升费用至4费,变为1星银狼'),
            PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')]
    pick = decide_planner(opts, st, tgt)
    assert pick.idx == 1, f'低血非银狼线应选弱化,实得 {pick.reason}'


def test_planner_strategy_both_equipment():
    """5费升2星:两卡全装备 → 装备分值定(非升费字样)。"""
    st = _test_planner_strategy_GameState(hp=60)
    opts = [PlannerOption(idx=0, text='火力风暴潮 进阶装备'),
            PlannerOption(idx=1, text='轮滑鞋 简易装备')]
    pick = decide_planner(opts, st, None)
    assert pick.reason.startswith('装备'), f'装备局 reason 应为装备,实得 {pick.reason}'


def test_planner_ocr_on_archive_shot():
    """存档画面(局29)选项识别:左右卡文字提取 + 策略结论=升费。
    OCR 模型不可用时 skip(环境限制)。"""
    left, right = _ocr_cards(SHOT)
    if not left and not right:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    ltxt, rtxt = ' '.join(left), ' '.join(right)
    # 局29 实测:升费在右卡
    assert '提升费用' in rtxt or '提升费用' in ltxt, f'升费卡应被识别: L={ltxt!r} R={rtxt!r}'
    assert '弱化' in (rtxt + ltxt), '弱化卡应被识别'
    opts = [PlannerOption(idx=0, text=ltxt), PlannerOption(idx=1, text=rtxt)]
    pick = decide_planner(opts, _test_planner_strategy_GameState(hp=80), None)
    assert '升费' in pick.reason
    assert pick.idx == (1 if '提升费用' in rtxt else 0), '选升费卡那侧'


def test_planner_fixtures_event_two_cards():
    """fixture:事件二卡态——左右卡文字识别正确(升费右/弱化左)+策略选右。"""
    if not FIX_EVENT.exists():
        import pytest
        pytest.skip('fixture 缺失')
    left, right = _ocr_cards(str(FIX_EVENT))
    if not left and not right:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    ltxt, rtxt = ' '.join(left), ' '.join(right)
    assert '提升费用' in rtxt, f'升费卡应在右: R={rtxt!r}'
    assert '弱化' in ltxt, f'弱化卡应在左: L={ltxt!r}'


def test_planner_fixtures_event_again_same_content():
    """fixture:二次事件态(23:27)——内容与首次一致(事件未消费的证据画面),
    识别结论应相同:识别链对该态稳定。"""
    if not FIX_EVENT_AGAIN.exists():
        import pytest
        pytest.skip('fixture 缺失')
    left, right = _ocr_cards(str(FIX_EVENT_AGAIN))
    if not left and not right:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    assert '提升费用' in ' '.join(right), '二次态升费卡仍识别'


def test_planner_fixtures_detail_panel_detectable():
    """fixture:详情面板态——handler 的 3b 分支依据「属性详情」OCR 检测;
    该态下卡文字应不可读(被面板盖)或面板标题可读,二者至少其一。"""
    if not FIX_DETAIL.exists():
        import pytest
        pytest.skip('fixture 缺失')
    import cv2
    import numpy as np
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        m = OnnxOcrMatcher()
    except Exception:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    img = cv2.imdecode(np.fromfile(str(FIX_DETAIL), np.uint8), cv2.IMREAD_COLOR)
    res = m.run_ocr(img)
    texts = ' '.join((res or {}).keys())
    assert '属性详情' in texts, '详情面板态应能检出「属性详情」(handler 3b 分支依据)'


def test_planner_fixtures_selected_confirm_ready():
    """fixture:选中态——右卡选中后「确认选择」按钮显影(x≈1440-1542,y≈584-615);
    佐证 CONFIRM 坐标(交互实锤):OCR 能在该区域读到「确认选择」。"""
    if not FIX_SELECTED.exists():
        import pytest
        pytest.skip('fixture 缺失')
    import cv2
    import numpy as np
    try:
        from one_dragon.base.matcher.ocr.onnx_ocr_matcher import OnnxOcrMatcher
        m = OnnxOcrMatcher()
    except Exception:
        import pytest
        pytest.skip('离线 OCR 模型不可用')
    img = cv2.imdecode(np.fromfile(str(FIX_SELECTED), np.uint8), cv2.IMREAD_COLOR)
    res = m.run_ocr(img)
    hit = None
    for t, mr in (res or {}).items():
        if '确认选择' in t and mr.max is not None:
            hit = (t, mr.max.center.x, mr.max.center.y)
            break
    assert hit is not None, '选中态应有「确认选择」按钮可读'
    _t, cx, cy = hit
    assert 1400 <= cx <= 1580 and 570 <= cy <= 630, \
        f'确认按钮应在右侧偏下(实测 ({cx},{cy});handler CONFIRM=(1491,600))'


# ==================== strategy_chain_smoke ====================

from sr_od.application.currency_war.kernel import cw_comps, cw_economy, cw_plane_table
from sr_od.application.currency_war.telemetry import state, recorder as recorder
from sr_od.application.currency_war.kernel.cw_state import GameState as _strategy_chain_smoke_GameState
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from sr_od.application.currency_war.decision.decision_v2.strategy import  DecisionV2Strategy as _strategy_chain_smoke_DecisionV2Strategy


def test_strategy_chain_importable():
    """策略链入口模块全部可导入(import 错路径在此爆,不等实跑)。"""
    for m in (cw_comps, cw_economy, cw_plane_table, state, recorder,
              _strategy_chain_smoke_DecisionV2Strategy):
        assert m is not None


def test_decide_prep_smoke():
    """decide_prep 全链真调用(四层:候选生成/硬过滤/板面评分/预算仲裁;无游戏依赖)。"""
    strat = _strategy_chain_smoke_DecisionV2Strategy()

    class _Cfg:
        faction_priority: list[str] = ['仙舟', '列车同行', '持续伤害']
    sess = strat.create_session(_Cfg())
    from sr_od.application.currency_war.kernel.cw_state import ShopCard
    st = _strategy_chain_smoke_GameState(gold=30, hp=80, level=5, round_num=3, plane=1,
                   board={"仙舟": 2, "持续伤害": 1},
                   shop=[ShopCard(x=400, faction="仙舟", name="爻光", cost=1)])
    actions = strat.decide_prep(st, sess, _Cfg())
    assert isinstance(actions, list)


def test_decide_prep_action_smoke():
    """步级决策环入口真调用(腾席链/主流程平移自持钩子;M-6 门/空板守卫全链)。"""
    from types import SimpleNamespace
    strat = _strategy_chain_smoke_DecisionV2Strategy()
    sess = strat.create_session(SimpleNamespace())
    obs = SimpleNamespace(box_overlay_open=False, tomes=[], boxes=[], spheres=[],
                          free_bench_slots=9, shop_open=False, bench_chars=[],
                          deployed_chars=[], front_occupied=set(), back_occupied=set(),
                          front_size=4, back_size=6, state=None,
                          state_gold_trusted=False)
    act = strat.decide_prep_action(obs, sess, SimpleNamespace(
        faction_priority=[], character_priority=[]))
    # W970 批 C 改型(dd-017):主流程买牌段 RunBuyPhase → OpenShop(等价改名)
    assert type(act).__name__ == 'OpenShop' and not act.read_only





# ==================== w953_planner_strategy_wiring ====================

import inspect
import sys as _w953_planner_strategy_wiring_sys

_w953_planner_strategy_wiring_sys.path.insert(0, 'src')
_w953_planner_strategy_wiring_sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from types import SimpleNamespace as _w953_planner_strategy_wiring_SimpleNamespace

from sr_od.application.currency_war.decision.decision_v2.strategy import  DecisionV2Strategy as _w953_planner_strategy_wiring_DecisionV2Strategy
from sr_od.application.currency_war.kernel.cw_events import  PlannerOption as _w953_planner_strategy_wiring_PlannerOption, decide_planner as _w953_planner_strategy_wiring_decide_planner
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w953_planner_strategy_wiring_BenchChar, GameState as _w953_planner_strategy_wiring_GameState
from sr_od.application.currency_war.operations.handlers.handle_planner_event import  HandlePlannerEvent

_UPGRADE = _w953_planner_strategy_wiring_PlannerOption(idx=0, text='提升费用至4费,变为1星银狼')
_WEAKEN = _w953_planner_strategy_wiring_PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')


def _session(target_comp) -> _w953_planner_strategy_wiring_SimpleNamespace:
    """最小 session stub:decide_planner 只读 target_comp。"""
    return _w953_planner_strategy_wiring_SimpleNamespace(target_comp=target_comp)


def test_planner_handler_routes_through_strategy_layer() -> None:
    """接线锁:策略层路径被走;kernel 直调仅在无 match 防御分支。

    锁的是「调用路径」不是分布数值;改接线形态时先重推语义再改锁
    (锁的存在性纪律)。"""
    src = inspect.getsource(HandlePlannerEvent.handle)
    # ① 唯一入口 = 策略对象(DESIGN §3.4 规约1)
    assert '_match.strategy.decide_planner(' in src, \
        'handle 必须经 match.strategy.decide_planner(策略层唯一入口)'
    # ② kernel 纯函数直调只允许在 else(无 match 防御)分支:直调行位于
    #    else 块内(其前最近的控制行是 else:)。W953 批1 治的就是
    #    「有 match 也直调 kernel」→ 策略对象被绕过。
    lines = src.splitlines()
    direct = [i for i, ln in enumerate(lines)
              if 'decide_planner(options' in ln and 'strategy' not in ln]
    assert len(direct) == 1, f'kernel 直调应恰一处(防御分支),实得 {len(direct)}'
    _head = [ln for ln in lines[:direct[0]] if ln.strip() == 'else:']
    assert _head, 'kernel 直调必须位于无 match 防御(else)分支内'


def test_planner_strategy_delegates_kernel_bitwise() -> None:
    """零行为锁:策略对象实现与 kernel 纯函数同输入逐位一致(委托不变形)。"""
    st = _w953_planner_strategy_wiring_GameState(hp=80)
    st.bench = [_w953_planner_strategy_wiring_BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2,
                          position_pref='front')]
    opts = [_UPGRADE, _WEAKEN]
    strat = _w953_planner_strategy_wiring_DecisionV2Strategy()
    via_strategy = strat.decide_planner(opts, st, _session(None), _w953_planner_strategy_wiring_SimpleNamespace())
    via_kernel = _w953_planner_strategy_wiring_decide_planner(opts, st, None)
    assert (via_strategy.idx, via_strategy.reason) == (via_kernel.idx, via_kernel.reason)


def test_planner_strategy_uses_session_target_comp() -> None:
    """零行为锁:策略对象把 session.target_comp 喂给 kernel 判定(银狼线加成),
    与旧 handler 直传 target_comp 的行为一致(接线不丢参)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '狼尊欢愉')
    st = _w953_planner_strategy_wiring_GameState(hp=80)
    st.bench = [_w953_planner_strategy_wiring_BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2,
                          position_pref='front')]
    opts = [_UPGRADE, _WEAKEN]
    strat = _w953_planner_strategy_wiring_DecisionV2Strategy()
    via_strategy = strat.decide_planner(opts, st, _session(tgt), _w953_planner_strategy_wiring_SimpleNamespace())
    via_kernel = _w953_planner_strategy_wiring_decide_planner(opts, st, tgt)
    assert via_strategy.idx == 0 and '升费' in via_strategy.reason
    assert (via_strategy.idx, via_strategy.reason) == (via_kernel.idx, via_kernel.reason)


# ==================== w603_telemetry_wiring ====================

import json
from pathlib import Path as _w603_telemetry_wiring_Path
from types import SimpleNamespace as _w603_telemetry_wiring_SimpleNamespace

from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w603_telemetry_wiring_StrategySession
from sr_od.application.currency_war.kernel import cw_observe
from sr_od.application.currency_war.kernel.cw_state import GameState as _w603_telemetry_wiring_GameState
# 分包期 6:恢复兜底族(DESIGN §4.4 hooks 行)归 sim/ledger_hooks,
# _w603_telemetry_wiring_state.start_run 经该模块属性查找调用 → 桩点随生产引用址重钉
from sr_od.application.currency_war.sim import ledger_hooks
from sr_od.application.currency_war.telemetry import query, recorder as _w603_telemetry_wiring_recorder, state as _w603_telemetry_wiring_state
from sr_od.application.currency_war.telemetry import state as _w603_telemetry_wiring_cw_telemetry


def _setup_recorder(monkeypatch, tmp_path: _w603_telemetry_wiring_Path, run_id: str = 'w603t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律:不写真实 .debug/)。"""
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_RECORDER',
                        _w603_telemetry_wiring_recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_CURRENT_RUN_ID', run_id)
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_CURRENT_DIFFICULTY', 'A8')
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_RUN_CLOSED', False)
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_PENDING_BRIEFING_ROWS', [])
    # 缺陷台账复现计数/L0 副作用链隔离(W505 同款)
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_defect_seen_run', '')
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_L0_ANDON_HANDLER', lambda payload: True)
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_L0_ANDON_FIRED_RUNS', set())
    # 分包期 4:obs_conflict 的 run_id 归属键读 kernel.cw_telemetry_exit 钩子位,
    # provider 钉回本模块 current_run_id(随 _CURRENT_RUN_ID 桩值走)
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider',
                        _w603_telemetry_wiring_state.current_run_id)


def _rows(tmp_path: _w603_telemetry_wiring_Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① 披露键进 decisions 遥测行 =====

def _fake_match(counters: tuple[int, int] = (2, 1),
                ledger: object | None = None):
    """fake ctx.cw_match 容器(session 带披露键;record_outcome 板深快照同款槽)。"""
    sess = _w603_telemetry_wiring_StrategySession()
    sess.v3_blood_budget_rejects = counters[0]
    sess.v3_blood_budget_refresh_rejects = counters[1]
    sess.xp_expect_ledger = ledger
    return _w603_telemetry_wiring_SimpleNamespace(session=sess)


def test_decision_row_carries_disclosure_keys(tmp_path: _w603_telemetry_wiring_Path, monkeypatch) -> None:
    """锁①a:record_decision 落盘行带血预算计数/降格触发面/经验账本字段。

    降格触发面现算:P1 ∧ r>=6 ∧ hp<60 → True(W576 组1.6 判读锚:
    「末窗降格触发出现」从此有遥测门,不再依赖 session 披露键落盘)。
    """
    _setup_recorder(monkeypatch, tmp_path)

    from sr_od.application.currency_war.kernel.cw_prep_expect import XpLedger
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_CTX_MATCH_REF',
                        [_fake_match((2, 1), XpLedger(level=3, xp_cur=4,
                                                      xp_next=8, anchored=True))])
    st = _w603_telemetry_wiring_GameState(gold=30, hp=50, round_num=6, plane=1)
    _w603_telemetry_wiring_state.get_recorder().record_decision('w603a', 'A8', st, '', {}, {}, [])
    rows = _rows(tmp_path, 'decisions.jsonl')
    assert len(rows) == 1
    r = rows[0]
    assert r['sess_blood_budget_rejects'] == 2
    assert r['sess_blood_budget_refresh_rejects'] == 1
    assert r['p1_downgrade_active'] is True
    led = r['xp_expect_ledger']
    assert isinstance(led, dict) and led['level'] == 3 and led['anchored'] is True


def test_decision_row_downgrade_inactive_and_no_match(tmp_path: _w603_telemetry_wiring_Path, monkeypatch) -> None:
    """锁①b:带外帧(hp>=60)降格触发面 False;无 match 注册 → 键恒 None
    (离线/测试缺省,旧 schema 不破坏)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_CTX_MATCH_REF',
                        [_fake_match((0, 0), None)])
    st = _w603_telemetry_wiring_GameState(gold=30, hp=90, round_num=2, plane=1)
    _w603_telemetry_wiring_state.get_recorder().record_decision('w603b', 'A8', st, '', {}, {}, [])
    r = _rows(tmp_path, 'decisions.jsonl')[0]
    assert r['p1_downgrade_active'] is False
    assert r['sess_blood_budget_rejects'] == 0
    assert r['xp_expect_ledger'] is None

    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_CTX_MATCH_REF', [None])
    _w603_telemetry_wiring_state.get_recorder().record_decision(
        'w603b2', 'A8', _w603_telemetry_wiring_GameState(gold=30, hp=50, round_num=6, plane=1),
        '', {}, {}, [])
    r2 = _rows(tmp_path, 'decisions.jsonl')[1]
    assert r2['sess_blood_budget_rejects'] is None
    assert r2['xp_expect_ledger'] is None


def test_session_field_xp_expect_ledger_declared() -> None:
    """锁①c:xp_expect_ledger 为 StrategySession 正式字段(动态属性升声明,
    pending_buy_expect 同判例;prep_director _xp_ledger 的 getattr 读写不变)。"""
    import dataclasses
    names = {f.name for f in dataclasses.fields(_w603_telemetry_wiring_StrategySession)}
    assert 'xp_expect_ledger' in names
    sess = _w603_telemetry_wiring_StrategySession()
    assert sess.xp_expect_ledger is None   # 新建 session 缺省未锚定


# ===== ② obs_conflicts 补 run_id =====

def test_obs_conflict_row_carries_run_id(tmp_path: _w603_telemetry_wiring_Path, monkeypatch) -> None:
    """锁②a:汇点写入行带 run_id(取 current_run_id;调用方零改动)。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='run_w603x')
    monkeypatch.setattr(cw_observe, '_CONFLICT_JOURNAL',
                        tmp_path / 'obs_conflicts.jsonl')
    cw_observe.obs_conflict('gold_delta', 45, 20, None,
                            verdict='测试', source='w603')
    r = _rows(tmp_path, 'obs_conflicts.jsonl')[0]
    assert r['run_id'] == 'run_w603x'
    assert r['field'] == 'gold_delta'


def test_obs_conflict_no_run_id_outside_run(tmp_path: _w603_telemetry_wiring_Path, monkeypatch) -> None:
    """锁②b:局外冲突(进程首局前,run_id 空)不写假键(历史行同形)。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='')
    monkeypatch.setattr(cw_observe, '_CONFLICT_JOURNAL',
                        tmp_path / 'obs_conflicts.jsonl')
    cw_observe.obs_conflict('level', 4, 5, None, verdict='测试')
    r = _rows(tmp_path, 'obs_conflicts.jsonl')[0]
    assert 'run_id' not in r


def test_query_obs_conflicts_filters_by_run_id(tmp_path: _w603_telemetry_wiring_Path) -> None:
    """锁②c:读端 --run 过滤「有键且相等」;历史行(无键)只在全量视图出现。"""
    p = tmp_path / 'obs_conflicts.jsonl'
    p.write_text(
        json.dumps({'ts': '2026-08-30T01:00:00', 'field': 'gold',
                    'run_id': 'run_a'}) + '\n'
        + json.dumps({'ts': '2026-08-30T02:00:00', 'field': 'hp'}) + '\n',
        encoding='utf-8')
    filtered = query.query_obs_conflicts(tmp_path, 'run_a')
    assert any('[gold]' in ln for ln in filtered)
    assert not any('[hp]' in ln for ln in filtered)   # 历史行(无键)被过滤
    assert query.query_obs_conflicts(tmp_path, 'run_b') == ['  (无记录)']
    # 全量(空 run_id)= 历史行 + 新行都在
    full = query.query_obs_conflicts(tmp_path, '')
    assert any('[hp]' in ln for ln in full) and any('[gold]' in ln for ln in full)


# ===== ③ 简报行 run_id 归属(局间缓冲)=====

def test_briefing_before_first_run_lands_in_next_run(tmp_path: _w603_telemetry_wiring_Path,
                                                     monkeypatch) -> None:
    """锁③a:进程首局(无 live run)简报行不再被丢 → start_run 后以新 id 补写,
    ts 保留采集时点(归属滞后/丢失双修)。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='')
    _w603_telemetry_wiring_recorder.record_exogenous(0, 'briefing', detail='affixes=[甲] bosses=[乙]')
    # 局前:不落盘,只缓冲
    assert _rows(tmp_path, 'exogenous.jsonl') == []
    assert len(_w603_telemetry_wiring_state._PENDING_BRIEFING_ROWS) == 1
    buffered_ts = _w603_telemetry_wiring_state._PENDING_BRIEFING_ROWS[0]['ts']
    # 新局开局:缓冲以新 run_id 补写
    # 分包期 6:恢复兜底族归 sim/ledger_hooks(DESIGN §4.4 hooks 行),
    # _w603_telemetry_wiring_state.start_run 经 _lh. 属性查找调用 → 桩点随生产引用址重钉
    monkeypatch.setattr(ledger_hooks, 'recover_dangling_run_summaries',
                        lambda: None)
    new_rid = _w603_telemetry_wiring_state.start_run('A8')
    assert new_rid.startswith('run_')
    rows = _rows(tmp_path, 'exogenous.jsonl')
    assert len(rows) == 1
    assert rows[0]['run_id'] == new_rid
    assert rows[0]['kind'] == 'briefing'
    assert rows[0]['ts'] == buffered_ts   # ts=采集时点,非补写时点
    assert _w603_telemetry_wiring_state._PENDING_BRIEFING_ROWS == []


def test_briefing_after_run_closed_lands_in_next_run(tmp_path: _w603_telemetry_wiring_Path,
                                                     monkeypatch) -> None:
    """锁③b:局终 summary 后(run 关闭位)简报行不再挂旧 run_id(W576 组5.1
    归属滞后的根因面)→ 缓冲到下一局。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='run_old')
    _w603_telemetry_wiring_state.record_run_summary('loss', 2, 8, 3)
    assert _w603_telemetry_wiring_state._RUN_CLOSED is True
    _w603_telemetry_wiring_recorder.record_exogenous(0, 'briefing', detail='d1')
    # 旧 run_id 不再直接吃行
    assert _rows(tmp_path, 'exogenous.jsonl') == []
    monkeypatch.setattr(ledger_hooks, 'recover_dangling_run_summaries',
                        lambda: None)
    new_rid = _w603_telemetry_wiring_state.start_run('A8')
    rows = _rows(tmp_path, 'exogenous.jsonl')
    assert len(rows) == 1 and rows[0]['run_id'] == new_rid
    # 开局复位关闭位:局中简报(battle_loop 位面分支)照常直写
    assert _w603_telemetry_wiring_state._RUN_CLOSED is False


def test_briefing_mid_run_writes_directly_other_kinds_noop(tmp_path: _w603_telemetry_wiring_Path,
                                                           monkeypatch) -> None:
    """锁③c:live run 内 briefing 直写不变;其余 kind 维持原 no-op 门
    (局外事件族不归属下一局,行为面不外溢)。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='run_live')
    _w603_telemetry_wiring_recorder.record_exogenous(3, 'briefing', detail='plane2')
    rows = _rows(tmp_path, 'exogenous.jsonl')
    assert len(rows) == 1
    assert rows[0]['run_id'] == 'run_live' and rows[0]['kind'] == 'briefing'
    assert _w603_telemetry_wiring_state._PENDING_BRIEFING_ROWS == []
    # 其余 kind 维持原 no-op 门(仅局外/无 live run 时丢,不入缓冲)
    monkeypatch.setattr(_w603_telemetry_wiring_cw_telemetry, '_CURRENT_RUN_ID', '')
    _w603_telemetry_wiring_recorder.record_exogenous(0, 'node_enter', detail='局外弹窗')
    assert len(_rows(tmp_path, 'exogenous.jsonl')) == 1
    assert _w603_telemetry_wiring_state._PENDING_BRIEFING_ROWS == []


from sr_od.application.currency_war.telemetry import state as _w603_telemetry_wiring_state
