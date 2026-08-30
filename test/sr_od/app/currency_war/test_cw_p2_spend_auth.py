"""W760 · 位面 2 支出授权单帧锁组(W757 v2 设计 §五判据预写落码;ADR-0480)。

设计出处:.debug/temp/currency_war/w757_p2_spend_auth/REPORT.md v2 §五
「单帧锁清单(事前写死)」九条 + 贴线带占位锁;W758 攻击报告 9 条修正
语境(g≥50 边界/接管帧禁出手/P16 滞回后锁定位)。

锁语义不锁牌面:全部断言策略决策行为(授权/拒绝/预算带),不锁具体
商店牌序。开关 p2_spend_auth_enabled 默认关=零漂移锚(每锁带 off 臂
对照或 frame-None 等价断言)。

占位期声明:P25 待证(贴线带逐点/核心卡必买 EV)——贴线带子句按设计
占位保守=不买,贴线带占位锁断言「行为与占位判据一致」,P25 证成后随
开臂批重推锁语义(策略开关生命周期第 3 态义务)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.p2_spend_auth import (
    p2_spend_auth_core_must_buy,
    p2_spend_auth_frame,
    p2_spend_auth_spend_authorized,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    ShopCard,
)

_CORE = '姬子·启行'          # 列车同行核心名(v3_core_names 注入)
_COMP = '列车同行'

_REG_ON = dataclasses.replace(DEFAULT_REGISTRY,
                              p2_spend_auth_enabled=True)
_REG_OFF = DEFAULT_REGISTRY   # 零漂移锚臂(HEAD 行为)


def _sess(locked: bool = True, core: bool = True) -> StrategySession:
    s = StrategySession()
    ist = IntentionState()
    if locked:
        ist.phase = 'locked'
        ist.locked_comp = _COMP   # P16 滞回后 v3 状态机位(测试直设终态)
    s.v3_intention = ist
    if core:
        s.v3_core_names = {_CORE, '三月七', '花火', '瓦尔特'}
    return s


def _st(**kw) -> GameState:
    """授权辖域基帧:plane2 中段/战斗节点/常授权(g=53,无连败,hp 60)。"""
    base = {'plane': 2, 'round_num': 2, 'node_type': '战斗', 'gold': 53,
            'hp': 80, 'hp_readable': True, 'level': 6, 'streak': None,
            'board': {}, 'bench': [], 'shop': [], 'deployed': []}
    base.update(kw)
    return GameState(**base)


def _core_buy(gold_cost: int = 3, score: float = 0.0,
              tag: str = 'line_carry') -> tuple[Candidate, float, dict]:
    cand = Candidate(action=BuyCard(ShopCard(x=0, name=_CORE,
                                             cost=gold_cost)),
                     tag=tag, source='test')
    return cand, score, {}


# ===== 锁④ 守息不破 + 零漂移锚 =====

def test_lock4_below_floor_frame_is_none_and_zero_drift() -> None:
    """锁④([17]/P13):g<50 帧授权不触发;开关关逐位同(零漂移锚)。"""
    st = _st(gold=49)
    assert p2_spend_auth_frame(st, _sess(), _REG_ON) is None
    # off 臂:授权帧恒 None(HEAD 行为)
    assert p2_spend_auth_frame(_st(), _sess(), _REG_OFF) is None
    # 决策面零漂移:g=53 负分核心买,off 臂拒(非正分门,HEAD 行为)
    res_off = arbitrate([_core_buy(score=0.0)], _st(), _sess(), _REG_OFF)
    assert res_off.actions == []


# ===== 锁① 核心卡必买(g≥50 全息带)+ 贴线带占位锁 =====

def test_lock1_core_card_must_buy_spill_band() -> None:
    """锁①([31]②+P25 位):线锁定∧g≥53∧形态缺口∧核心卡在店→负分
    候选也越过非正分门进买序列;g=53 全息带(花完仍≥50)。"""
    sess = _sess()
    st = _st(gold=53)
    res = arbitrate([_core_buy(gold_cost=3, score=0.0)], st, sess, _REG_ON)
    buys = [a for a in res.actions if isinstance(a, BuyCard)]
    assert len(buys) == 1 and buys[0].card.name == _CORE, res.log


def test_lock1_line_band_placeholder_conservative_no_buy() -> None:
    """贴线带占位锁(W757 v2 §五附;P25 待证):g=50 核心买入落 [45,50)
    →占位期保守=不买(off 臂同拒,行为一致)。P25 证成后本锁随开臂批
    按「买/不买与凑息账结论一致」重推(不锁方向)。"""
    sess = _sess()
    st = _st(gold=50)
    res = arbitrate([_core_buy(gold_cost=3, score=0.0)], st, sess, _REG_ON)
    assert not [a for a in res.actions if isinstance(a, BuyCard)]


# ===== 锁②/⑧ 升级恒禁(濒死带 P21 + 停升级线 AND,授权不豁免)=====

def test_lock2_8_authorization_never_emits_or_relaxes_levelup() -> None:
    """锁②/⑧(P21/ADR-0448):授权通道对 LevelUp 恒不辖——升级不因
    授权放宽;濒死 hp≤10 帧授权整体不触发(覆盖纪律态归既有族,升级
    由血预算停手门独立拒)。"""
    # 授权通道谓词对升级候选恒 False(两层同)
    for urgent_kw in ({}, {'streak': -2}):
        st = _st(**urgent_kw)
        assert p2_spend_auth_spend_authorized(
            Candidate(action=LevelUp(cost=4), tag='levelup',
                      source='test'),
            st, st, _sess(), _REG_ON) is False
    # 濒死带帧:授权不触发(授权帧内零 LevelUp 的结构性保证)
    assert p2_spend_auth_frame(_st(hp=10), _sess(), _REG_ON) is None


# ===== 锁③ j=0 负例保持(授权≠D 无条件开)=====

def test_lock3_negative_score_refresh_still_rejected_in_auth_frame() -> None:
    """锁③(P12 检验点2):授权帧(含加急)内负分刷新仍拒——授权只
    放宽预算上界,不动评分(V_D 批账 j=0 负例由既有 P12 锁组守)。"""
    sess = _sess()
    st = _st(gold=53, streak=-2)          # 加急帧
    rc = Candidate(action=RefreshShop(cost=2), tag='refresh',
                   source='test')
    res = arbitrate([(rc, -2.0, {})], st, sess, _REG_ON)
    assert not any(isinstance(a, RefreshShop) for a in res.actions), res.log


# ===== 锁⑤ 部署零支出(P24 免费域照常)=====

def test_lock5_deploy_passes_with_unchanged_gold() -> None:
    """锁⑤(P24 锁组沿用):授权帧内补部署照常采纳且金账不变。"""
    sess = _sess()
    bench_char = BenchChar(slot=1, char_id='停云', faction='仙舟')
    st = _st(gold=53, bench=[bench_char], deployed=[],
             level=6, deploy_cap=6)
    dc = Candidate(action=DeployMove(bench_idx=0, to_row='back',
                                     faction='仙舟'),
                   tag='deploy', source='test',
                   breakdown_hint={'name': '停云'})
    res = arbitrate([(dc, 5.0, {})], st, sess, _REG_ON)
    assert any(isinstance(a, DeployMove) for a in res.actions), res.log
    assert res.actions and st.gold == 53   # 金账不变(免费域)


# ===== 锁⑥ 锁定前提(P16 滞回后位;摇摆域切分)=====

def test_lock6_unlocked_frame_never_authorizes() -> None:
    """锁⑥(§1.3 切分+P16):未锁定帧授权不触发;消费位=滞回后
    locked 位(测试直设终态等价——生产位即 v3 状态机输出)。"""
    sess = _sess(locked=False)
    assert p2_spend_auth_frame(_st(), sess, _REG_ON) is None
    res = arbitrate([_core_buy(score=0.0)], _st(), sess, _REG_ON)
    assert res.actions == []


# ===== 锁⑦ 末窗不辖(boss 窗归既有族)=====

def test_lock7_boss_window_frame_not_authorized() -> None:
    """锁⑦(§3.3):P2 末窗(boss 节点)帧授权不触发(归 ALL IN/
    降格既有族)。"""
    assert p2_spend_auth_frame(_st(node_type='boss'), _sess(),
                               _REG_ON) is None


# ===== 锁⑨ 接管帧禁出手(分配器 v6 active 帧归属二选一)=====

def test_lock9_allocator_takeover_frame_blocks_authorization(
        monkeypatch) -> None:
    """锁⑨(§3.3+P23/ADR-0474):分配器接管帧(v6 active)内授权通道
    禁出手(帧归属二选一,双花结构性不可能);同帧非接管→授权照常。
    生产接管谓词单一源=allocator.alloc_domain(现值直用);测试以
    monkeypatch 驱动该谓词构造接管帧(谓词本身另有锁组)。"""
    from sr_od.application.currency_war.decision.decision_v2 import allocator
    from sr_od.application.currency_war.decision.decision_v2.allocator import (
        AllocDomain,
    )
    sess = _sess()
    st = _st(gold=53)
    # 非接管帧(现值:plane2 缺口帧分配器不辖)→ 授权照常
    auth = p2_spend_auth_frame(st, sess, _REG_ON)
    assert auth is not None
    # 接管帧 → 授权禁出手(frame None)
    monkeypatch.setattr(allocator, 'alloc_domain',
                        lambda s, se, r: AllocDomain.STOP_WINDOW)
    assert p2_spend_auth_frame(st, sess, _REG_ON) is None
    monkeypatch.undo()
    # 接管帧内预算带谓词同样不放行(双保险,与门臂同源)
    monkeypatch.setattr(allocator, 'alloc_domain',
                        lambda s, se, r: AllocDomain.STOP_WINDOW)
    cand, _, _ = _core_buy(gold_cost=3, score=5.0)
    assert not p2_spend_auth_core_must_buy(cand, st, st, sess, _REG_ON)


# ===== 两层强度:常授权层预算地板 / 加急层破息下限 =====

def test_two_layer_budget_bands() -> None:
    """层强度(W757 v2 §3.1):常授权层地板=花完仍≥息线(P5 推广);
    加急层(T3 命中)允许破息至保留金占位下限([18] 止损机械化);
    贴线带常授权保守不买、加急放行。"""
    sess = _sess()
    # 常授权:g=53 买 3费 → 花完 50 ≥息线 → 预算带过
    auth = p2_spend_auth_frame(_st(gold=53), sess, _REG_ON)
    assert auth is not None and not auth.urgent
    cand, _, _ = _core_buy(gold_cost=3)
    assert p2_spend_auth_core_must_buy(cand, _st(gold=53), _st(gold=53),
                                       sess, _REG_ON)
    # 贴线带:g=51 买 3费 → 花完 48 ∈[45,50) → 常授权保守不买/加急放行
    assert p2_spend_auth_frame(_st(gold=51), sess, _REG_ON).urgent is False
    assert not p2_spend_auth_core_must_buy(cand, _st(gold=51),
                                           _st(gold=51), sess, _REG_ON)
    st_u = _st(gold=51, streak=-2)
    auth_u = p2_spend_auth_frame(st_u, sess, _REG_ON)
    assert auth_u is not None and auth_u.urgent
    assert p2_spend_auth_core_must_buy(cand, st_u, st_u, sess, _REG_ON)
    # 破息带:花完 <45 常授权不进,加急过保留金下限(20)
    st_u2 = _st(gold=53, streak=-2)
    assert p2_spend_auth_frame(st_u2, sess, _REG_ON) is not None
    r_cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                       source='test')
    # 加急 D 预算带:working 金 30、刷 2 → 花完 28 ≥保留金下限 20 → 带
    # 内(frame 用带内刻度构造:hp 80/连败 2/frame 刻度独立于 working 金,
    # working=执行域前序花费后的金,如授权帧内已买一笔后的余金)
    st_frame_u = _st(gold=53, streak=-2)
    assert p2_spend_auth_spend_authorized(
        r_cand, GameState(plane=2, gold=30, hp=80), st_frame_u, sess,
        _REG_ON)
    # 常授权帧同刻度:花完 28 < 息线 → 预算带拒(破息带只走加急层)
    assert not p2_spend_auth_spend_authorized(
        r_cand, GameState(plane=2, gold=30, hp=80), _st(gold=53), sess,
        _REG_ON)


def test_t3_blood_worsening_two_clauses() -> None:
    """T3 报警面两子句(W757 v2 §3.1;占位值注记):连败 ≥N_fail(占位
    2)或 hp≤警戒带(占位=P1 出口血目标线 60,hp 可信位守卫)。"""
    # 连败子句:streak=-2 命中,-1 不命中
    assert p2_spend_auth_frame(_st(streak=-2), _sess(), _REG_ON).urgent
    assert not p2_spend_auth_frame(_st(streak=-1), _sess(),
                                   _REG_ON).urgent
    # hp 子句:hp≤警戒带(=p1_exit_blood_target 60)命中;不可信 hp
    # (沿用/兜底帧)不作报警依据(ADR-0282 口径)
    assert p2_spend_auth_frame(_st(hp=60), _sess(), _REG_ON).urgent
    assert not p2_spend_auth_frame(_st(hp=61), _sess(), _REG_ON).urgent
    assert not p2_spend_auth_frame(_st(hp=61, hp_readable=False,
                                       hp_trusted=False), _sess(),
                                   _REG_ON).urgent
