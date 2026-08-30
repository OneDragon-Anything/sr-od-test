"""通道边际排序(overlay A 契约锁组;W645 提案 A-v2 + W720 修订)。

设计出处=ADR-0476(提案面原文见 .debug/temp/currency_war/
w645_proposal_v2/SPECS.md 提案 A-v2 节;落码判定=同目录 w720_overlay_reeval/
REPORT.md「提案 A:修订后实施」,三条修订要点:①辖域谓词按 ADR-0445 现
flip 语义重述=纯溢余判定,复合条件=flip_hit ∧ posture.level_up ∧ cap 满员
(第三路径不先截);②刷新边际与 cw_shop_odds.expected_refreshes_for_card
单一址互指、与分配器 Π_refresh 估计器同源、禁第二概率口径;③off 臂基线=
当前 HEAD 冻结 worktree)。另并入 ADR-0475 挂账的定向刷新车道塌缩判据
arbiter 接线(判据单一址=kernel.cw_economy._omega_collapse_zeroed)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 排序契约:升级边际(省刷金 saving / 升级费 fee,两量均既有单一址
  函数输出)≥ 1 → 'upgrade_first'(现行固定序,零漂移);< 1(峰值级
  saving=0 即病灶帧)→ 'refresh_first';
- ② flip 谓词辖域(ADR-0445 现语义):排序辖域 = release flip 义务帧
  ∧ 包装后 posture.level_up ∧ cap 满员(第三路径辖区 deployed<cap 不辖,
  人口解锁边际=0 由第三路径自辖);third_path/非 flip/未包装帧不辖;
- ③ 单一址互指:排序两腿只消费 ev.levelup_refresh_saving 与
  kernel.upgrade_plan_fee(前者内部调 expected_refreshes_for_card);
  monkeypatch cw_shop_odds 概率符号 → 排序随之翻(自建概率表即翻红);
- ④ arbiter 消费点(排序接线):刷新先帧的升级候选在授权臂 dp/static_ev
  下降级拒(升级授权重估留待下帧);upgrade_first 帧/非辖域帧/pop_slot
  人口位臂([33] 当轮兑现,排序不覆写)零漂移;
- ⑤ 定向刷新车道塌缩判据接线(ADR-0475 挂账补线):塌缩带归零帧 M-A
  定向车道同判据停付(预算零消耗);非塌缩帧 M-A 授权零漂移。
"""
from __future__ import annotations

import logging

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    ReleaseDirective,
    channel_rank_scope,
    rank_refresh_vs_upgrade,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    LevelUp,
    RefreshShop,
)


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)


_REG = DEFAULT_REGISTRY


def _state(*, gold: int = 80, hp: int = 80, level: int = 6,
           deployed_n: int = 6, bench_n: int = 1,
           plane: int = 1, r: int = 5) -> GameState:
    """cap 满员(deployed_n=6)溢余帧工厂;deployed_n=5 造第三路径辖区。"""
    return GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                            star=1) for i in range(deployed_n)],
        bench=[BenchChar(slot=i, char_id=f'席{i}', faction='公司', star=1)
               for i in range(bench_n)]
        + [None] * (BENCH_CAPACITY - bench_n),
        shop=[], node_type='battle', board={})


def _sess_of(state: GameState) -> StrategySession:
    """裸 session(release_directive/flip_hit 的 registry 均显式传参)。"""
    return StrategySession()


def _flip_session(state: GameState, *, third_path: bool = False,
                  level_up: bool = True) -> StrategySession:
    """flip 义务帧 session(v3_release=flip 指令 + 包装后 level_up 姿态,
    与生产链 evaluate_release 写入形态同构)。"""
    s = StrategySession()
    s.v3_release = ReleaseDirective(budget_gold=20, rolls=10,
                                    third_path=third_path, reason='flip')
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=False, level_up=level_up, refresh_budget=6,
                tag='release'))
    return s


# --- ① 排序契约 ---------------------------------------------------------------


def test_rank_upgrade_first_when_saving_covers_fee(monkeypatch) -> None:
    """升级边际覆盖费率锁:省刷金 ≥ 升级费 → 'upgrade_first'(现行固定序
    零漂移;边际口径=省刷金/升级费,单一址两函数输出之比)。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    st = _state()
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 100.0)
    monkeypatch.setattr(cw_economy, 'upgrade_plan_fee',
                        lambda *a, **k: 10)
    assert rank_refresh_vs_upgrade(st, _flip_session(st), _REG) \
        == 'upgrade_first'


def test_rank_refresh_first_when_saving_below_fee(monkeypatch) -> None:
    """反方向错序修正锁(SPECS A-v2 §3 病灶 1):省刷金 < 升级费 →
    'refresh_first'(刷新先吃溢余残差;峰值级 saving=0 帧即此形态)。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    st = _state()
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 0.0)   # 峰值级 ΔE≤0 → saving=0
    assert rank_refresh_vs_upgrade(st, _flip_session(st), _REG) \
        == 'refresh_first'


def test_rank_margins_hand_recalc_from_single_addresses() -> None:
    """手算对拍锁:真实查表帧上排序结果 == (saving ≥ fee) 不等式——
    两腿对拍侧与实现侧同源(ev.levelup_refresh_saving 内部消费
    cw_shop_odds.expected_refreshes_for_card;升级费=kernel.upgrade_plan_fee),
    锁钉「比较形状」不锁数值巧合(帧取锁定核 1★ 副本未齐的常态溢余帧)。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.decision.decision_v2.ev import (
        levelup_refresh_saving,
    )
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_economy import (
        upgrade_plan_fee,
    )
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
        intention_core,
    )
    # 锁定核 comp:bench 放 1★ 核心 1 张(saving 的 owned 输入非退化)
    comp = next(c for c in COMP_LIBRARY
                if CHARACTERS.get(intention_core(c)) is not None
                and (CHARACTERS[intention_core(c)].cost or 0) > 0)
    core = intention_core(comp)
    st = _state(gold=90, bench_n=1)
    st.bench[0] = BenchChar(slot=0, char_id=core,
                            faction=(CHARACTERS[core].factions
                                     or ('?',))[0], star=1)
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp=comp.name)
    saving = levelup_refresh_saving(st, s, _REG)
    fee = upgrade_plan_fee(st)
    expect = 'upgrade_first' if saving >= fee else 'refresh_first'
    assert rank_refresh_vs_upgrade(st, s, _REG) == expect


# --- ② flip 谓词辖域(ADR-0445 现语义,W720 修订要点①)--------------------------


def test_scope_requires_flip_release_frame() -> None:
    """辖域=flip 义务帧单一址(session.v3_release.reason=='flip'):
    非 flip 帧无指令不辖(只排其一不辖,行为零漂移);reserve_admission
    指令帧不辖。"""
    st = _state()
    assert not channel_rank_scope(st, StrategySession())
    s2 = StrategySession()
    s2.v3_release = ReleaseDirective(budget_gold=0, rolls=0,
                                     reason='reserve_admission')
    assert not channel_rank_scope(st, s2)


def test_scope_excludes_third_path_and_free_slot() -> None:
    """第三路径辖区(deployed<cap,slot 守卫已压 level_up)不辖——人口
    解锁边际本窗=0 由第三路径自辖,排序不得覆写(W720 修订要点①:
    cap 满员使第三路径不先截);third_path 指令帧同不辖。"""
    st_free = _state(deployed_n=5)   # deployed<cap:第三路径辖区
    assert not channel_rank_scope(st_free, _flip_session(st_free))
    st_full = _state()
    assert channel_rank_scope(st_full, _flip_session(st_full))
    s_tp = _flip_session(st_full, third_path=True)
    assert not channel_rank_scope(st_full, s_tp)


def test_scope_requires_wrapped_level_up() -> None:
    """包装后 posture.level_up=False 帧(DP 未说升/第三路径压掉)不辖:
    只辖「升级 ∧ 刷新并存」帧(SPECS A-v2 §1 复合谓词第二枝)。"""
    st = _state()
    assert not channel_rank_scope(st, _flip_session(st, level_up=False))


def test_scope_predicate_uses_adr0445_flip_semantics() -> None:
    """flip 谓词语义对照锁(ADR-0445 纯溢余判定):辖域继承 flip_hit 的
    现语义——经生产链 release_directive 取指令:应急带帧(hp≤25)flip
    让位(指令非 flip,不辖)、息线以内(g≤R*)无 flip 指令不辖;溢余段
    flip 帧辖,且 hp 高低/可信位无关(旧血量复合谓词不得回归)。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        release_directive,
    )
    st_low = _state(gold=80, hp=25)   # 应急辖区,flip 让位
    d = release_directive(st_low, _sess_of(st_low), _REG, 'FORM',
                          Posture(save=False, level_up=True,
                                  refresh_budget=6))
    assert d is None or d.reason != 'flip'
    st_hp39 = _state(gold=80, hp=39)
    st_hp100 = _state(gold=80, hp=100)
    st_hp100.hp_readable = False
    st_hp100.hp_trusted = False      # 100 兜底假帧也辖(血量维度退场)
    for st in (st_hp39, st_hp100):
        d = release_directive(st, _sess_of(st), _REG, 'FORM',
                              Posture(save=False, level_up=True,
                                      refresh_budget=6))
        assert d is not None and d.reason == 'flip'
        assert channel_rank_scope(st, _flip_session(st))
    st_narrow = _state(gold=48)      # 息线以内:溢余判定不 fire
    d = release_directive(st_narrow, _sess_of(st_narrow), _REG, 'FORM',
                          Posture(save=False, level_up=True,
                                  refresh_budget=6))
    assert d is None or d.reason != 'flip'


# --- ③ 单一址互指(W720 修订要点②)---------------------------------------------


def test_rank_single_address_probability_source(monkeypatch) -> None:
    """概率单一址行为锁:排序两腿只消费既有概率符号——monkeypatch
    cw_shop_odds.expected_refreshes_for_card(级联进 saving)使 saving
    归零 → 排序翻到 refresh_first;实现若自建概率表,本锁翻红(W720
    互指条款:与分配器 Π_refresh 估计器同源,禁第二概率口径)。"""
    import sr_od.application.currency_war.data.cw_shop_odds as odds
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
        intention_core,
    )
    comp = next(c for c in COMP_LIBRARY
                if CHARACTERS.get(intention_core(c)) is not None
                and (CHARACTERS[intention_core(c)].cost or 0) > 0)
    core = intention_core(comp)
    st = _state(gold=90, bench_n=1)
    st.bench[0] = BenchChar(slot=0, char_id=core,
                            faction=(CHARACTERS[core].factions
                                     or ('?',))[0], star=1)
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp=comp.name)
    orig = odds.expected_refreshes_for_card
    odds.expected_refreshes_for_card = (
        lambda level, cost, target_star, owned=0, non_target_taken=0: 0.0)
    try:
        # E(L)=E(L+1)=0 → saving=0 < fee → refresh_first(概率源被换即翻;
        # 实现若自建概率表,排序不随本符号变,本锁翻红)
        assert rank_refresh_vs_upgrade(st, s, _REG) == 'refresh_first'
    finally:
        odds.expected_refreshes_for_card = orig


def test_rank_no_second_margin_address_structure() -> None:
    """结构互指锁:排序函数源码只引用 ev.levelup_refresh_saving 与
    kernel.upgrade_plan_fee 两个既有单一址符号,不出现任何本地概率/
    费用查表(W720 修订要点②:刷新边际单一址,禁第二账)。"""
    import inspect

    from sr_od.application.currency_war.decision.decision_v2 import (
        posture_release,
    )
    src = inspect.getsource(posture_release.rank_refresh_vs_upgrade)
    assert 'levelup_refresh_saving' in src
    assert 'upgrade_plan_fee' in src
    for banned in ('refresh_prob(', 'SHOP_ODDS', 'PROB_TABLE'):
        assert banned not in src, banned


# --- ④ arbiter 消费点(排序接线)------------------------------------------------


def _lvl_cand(cost: int = 10) -> Candidate:
    return Candidate(action=LevelUp(cost=cost), tag='levelup', source='ui')


def _arbitrate_levelup(st: GameState, s: StrategySession,
                       val: float = 1.0):
    return arbitrate([(_lvl_cand(), val, {'int_emb': 0.0})], st, s, _REG)


def test_arbiter_defers_levelup_on_refresh_first_frame(monkeypatch) -> None:
    """消费点锁(提案 A 消费点=arbiter 升级门):排序辖域帧(rank=
    refresh_first)升级候选降级拒,拒因含通道边际排序标注——隐式固定序
    (买/升级恒先于刷新)自此收回显式单一址。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    st = _state(gold=80)
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)     # ② DP 授权臂开
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 0.0)      # refresh_first
    res = _arbitrate_levelup(st, _flip_session(st))
    row = res.log[-1]
    assert row['accepted'] is False, f'refresh_first 帧升级应降级(log={row})'
    assert '通道边际排序' in (row.get('reject') or '')


def test_arbiter_upgrade_first_frame_zero_drift(monkeypatch) -> None:
    """零漂移臂:同帧 rank='upgrade_first'(saving 覆盖费率)→ 升级
    照现行固定序放行(排序不改写 upgrade_first 行为)。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    st = _state(gold=80)
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 999.0)
    res = _arbitrate_levelup(st, _flip_session(st))
    assert res.log[-1]['accepted'] is True, res.log[-1]


def test_arbiter_non_scope_frame_zero_drift(monkeypatch) -> None:
    """零漂移臂(非 flip 帧):无 release 指令的同帧升级照放行——排序
    只辖 flip ∧ level_up ∧ cap 满员帧(SPECS A-v2 §1:非辖帧行为零漂移)。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    st = _state(gold=80)
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 0.0)
    res = _arbitrate_levelup(st, StrategySession())
    assert res.log[-1]['accepted'] is True, res.log[-1]


def test_arbiter_pop_slot_arm_not_overwritten(monkeypatch) -> None:
    """人口位臂不覆写锁(SPECS A-v2 §1:[33] 当轮兑现,排序不辖①臂)——
    cap 满 ∧ bench 有目标件(pop_slot)帧,即便 rank='refresh_first'
    升级照放行。"""
    from sr_od.application.currency_war.decision.decision_v2 import ev as _ev
    from sr_od.application.currency_war.kernel import cw_economy
    from sr_od.application.currency_war.kernel.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    carry = '姬子·启行'
    st = _state(gold=80)
    st.bench = [BenchChar(slot=0, char_id=carry, faction='贝洛伯格', star=1)] \
        + [None] * (BENCH_CAPACITY - 1)
    s = _flip_session(st)
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({carry, '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {carry}
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda *a, **k: True)
    monkeypatch.setattr(_ev, 'levelup_refresh_saving',
                        lambda *a, **k: 0.0)      # refresh_first
    res = _arbitrate_levelup(st, s)
    assert res.log[-1]['accepted'] is True, res.log[-1]
    assert getattr(res.actions[0], 'auth_basis', '') == 'pop_slot'


# --- ⑤ 定向刷新车道塌缩判据接线(ADR-0475 挂账补线,W721 并入)--------------------


def _ma_frame(level: int = 5):
    """M-A 授权帧底座(承 test_cw_w252 形态):P1 末窗 gap>0 ∧ 追名
    peak≥2 ∧ hp 带外(非血预算停付);锁定核=4 费「波提欧」(巡海击破),
    level 参数控塌缩带判定面(lv5 时 refresh_prob(5,4)/refresh_prob(7,4)
    ≈0.05 < ω=0.1,塌缩带;W721 帧族同款)。"""
    from types import SimpleNamespace
    carry = '波提欧'
    st = GameState(
        plane=1, round_num=8, gold=55, level=level, hp=70,
        board={'击破': 2, '贝洛伯格': 1},
        deployed=[SimpleNamespace(char_id=carry, faction='击破',
                                  star=1, position_pref='back', equips=(),
                                  slot=0),
                  SimpleNamespace(char_id='娜塔莎', faction='贝洛伯格',
                                  star=1, position_pref='back', equips=(),
                                  slot=1)],
        bench=[BenchChar(slot=0, char_id=carry, faction='击破', star=1)],
        shop=[], node_type='battle')
    from sr_od.application.currency_war.kernel.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '巡海击破'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({carry}), frozenset(), 'locked')
    s.v3_core_names = {carry}
    s.target_comp = SimpleNamespace(factions=('击破',),
                                    core_chars=(carry,))
    return st, s


def test_ma_lane_stops_on_collapse_frame() -> None:
    """塌缩停付锁(ADR-0475 定向车道同判据辖):塌缩带归零帧
    (锁定核 4 费 @lv5,refresh_prob 比值<ω)M-A 定向车道停付——
    非正分刷新拒,预算零消耗(轮/局计数不动)。"""
    st, s = _ma_frame(level=5)
    from sr_od.application.currency_war.kernel.cw_economy import (
        _omega_collapse_zeroed,
        _target_core_cost,
    )
    _, tc = _target_core_cost(s)
    assert _omega_collapse_zeroed(st, s, _REG, tc), '前置:帧须在塌缩带'
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], st, s, _REG)
    assert res.log[-1]['accepted'] is False, res.log[-1]
    assert not any(isinstance(a, RefreshShop) for a in res.actions)
    assert getattr(s, 'v3_dir_refresh_used', 0) == 0
    assert getattr(s, 'v3_dir_refresh_round', 0) == 0


def test_ma_lane_zero_drift_outside_collapse_band() -> None:
    """零漂移臂:非塌缩带同级帧(M-A 授权窗开)定向刷新照常有界放行
    (ADR-0475 接线只辖塌缩带,不缩窗内正常搜索量)。"""
    st, s = _ma_frame(level=8)
    from sr_od.application.currency_war.kernel.cw_economy import (
        _omega_collapse_zeroed,
        _target_core_cost,
    )
    _, tc = _target_core_cost(s)
    assert not _omega_collapse_zeroed(st, s, _REG, tc), '前置:帧须在带外'
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], st, s, _REG)
    assert res.log[-1]['accepted'] is True, res.log[-1]
    assert any(isinstance(a, RefreshShop) for a in res.actions)
    assert getattr(s, 'v3_dir_refresh_used', 0) == 1


def test_ma_collapse_single_address_no_reimplementation() -> None:
    """判据单一址结构锁:arbiter 的塌缩停付只引用 kernel.cw_economy
    ._omega_collapse_zeroed(ADR-0475 挂账原文指定单一址),不出现
    第二概率口径(refresh_prob 直调/本地比值)。"""
    import inspect

    from sr_od.application.currency_war.decision.decision_v2 import arbiter
    src = inspect.getsource(arbiter)
    assert '_omega_collapse_zeroed' in src
    # 判据不在 arbiter 本地重算:禁直调概率符号/读判据阈值字段
    assert 'refresh_prob' not in src
    assert 'registry.omega_collapse_ratio' not in src
