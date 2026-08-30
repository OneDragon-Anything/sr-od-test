"""W783 · 位面 2 支出授权单帧锁组 v3.3(十六锁全量;ADR-0480/0481/0483)。

设计出处:.debug/temp/currency_war/w757_p2_spend_auth/REPORT.md v3.3 §五
「单帧锁清单」十六条 + 预算带对齐声明 + 双通道合并语义 + 窗级水位目标 +
保留金公式化 + XP sink 授权化;W762/W772 归因、W779 审计与 W758-v3
攻击复核语境。

锁语义不锁牌面:全部断言策略决策行为(授权/拒绝/预算带/方向辖域),
不锁具体商店牌序。方向源梯级以 monkeypatch 注入(投影谓词本体在
cw_intention/桥池另有锁组),接管谓词以 monkeypatch 驱动(同 W760 锁⑨
先例,谓词本体锁组在 test_cw_w715)。

开关 p2_spend_auth_enabled 默认关=零漂移锚(每锁带 off 臂对照或
frame-None 等价断言)。

锁语义演进声明(重推依据=设计附录 B/C/D/E):
- v3.1(相对 W760 v2 锁组):锁① 贴线带占位保守不买子句随「预算带
  对齐」废除(G1-A 破息反降的收门面)——常授权层与既有息账门同判;
  锁② 濒死 hp≤10 帧从「授权整体不触发」改写为「授权可触发但升级恒
  禁」;锁⑦ 「末窗整体不辖」改写为「豁免归 v6 接管帧谓词,非接管末
  窗帧通道 B 可达」。
- v3.2(W772 分支 2 出手面修正):加急预算带的界从常数 20 改为公式
  化下限 5×min(剩余备战轮数,3)(「放宽有界」语义不变,界随公式——
  「预算带」测试断言同步重推);新增锁⑭(净支出闸)与锁⑮(高价值
  优先/兜底层条件),空店帧旧行为=L3 兜底路径,①-⑬ 锁断言在空店帧
  下语义不变。
- v3.3(W779 净支出可行性审计:sink 供给+判据口径双修):**锁⑭ 改写**
  ——v3.2 单帧净支出闸废除(单帧净>0 在 P2 中后段结构性难达 rn5-7
  ≈0-2%,W779 审计①),锁语义改「窗级水位不升出手计划」的行为可用
  性钉:店内 L1 目标即使 Σ支出≤预期收入(旧闸必拒域)也授权放行;
  无 L1/XP/合法 sink 帧零动作;窗级水位计入遥测披露键。锁⑮ 随闸废除
  重述(条件从「过净支出闸」改「店内 L1 目标在场」,行为断言不变)。
  **新增锁⑯**(XP sink 门边界:hp>停升级线 ∧ 非 P21 濒死带 ∧ 概率窗
  未达,血预算门 AND 不动;ev.levelup_ev_basis 臂④ 'p2_auth_xp')。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2 import p2_spend_auth
from sr_od.application.currency_war.decision.decision_v2.p2_spend_auth import (
    p2_spend_auth_core_must_buy,
    p2_spend_auth_frame,
    p2_spend_auth_intercept,
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
    SellBench,
    ShopCard,
)

_CORE = '姬子·启行'          # 列车同行核心名(v3_core_names 注入)
_COMP = '列车同行'
_DIR_PIECE = '方向件甲'       # 通道 B 方向梯级注入名(锁语义不锁牌面)

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
    """授权辖域基帧:plane2 中段/战斗节点/通道 A 常授权(g=53,无连败,
    hp 60 以上)。"""
    base = {'plane': 2, 'round_num': 2, 'node_type': '战斗', 'gold': 53,
            'hp': 80, 'hp_readable': True, 'level': 6, 'streak': None,
            'board': {}, 'bench': [], 'shop': [], 'deployed': []}
    base.update(kw)
    return GameState(**base)


def _buy(name: str, gold_cost: int = 3, score: float = 0.0,
         tag: str = 'line_carry') -> tuple[Candidate, float, dict]:
    cand = Candidate(action=BuyCard(ShopCard(x=0, name=name,
                                             cost=gold_cost)),
                     tag=tag, source='test')
    return cand, score, {}


def _core_buy(gold_cost: int = 3, score: float = 0.0,
              tag: str = 'line_carry') -> tuple[Candidate, float, dict]:
    return _buy(_CORE, gold_cost, score, tag)


# ===== 锁④ 守息不破 + 零漂移锚 =====

def test_lock4_below_floor_frame_is_none_and_zero_drift() -> None:
    """锁④([17]/P13):g<50 帧授权不触发;开关关逐位同(零漂移锚)。"""
    st = _st(gold=49)
    assert p2_spend_auth_frame(st, _sess(), _REG_ON) is None
    assert p2_spend_auth_intercept(st, _sess(), _REG_ON) == 't4_gold'
    # off 臂:授权帧恒 None 且枚举无语义(HEAD 行为)
    assert p2_spend_auth_frame(_st(), _sess(), _REG_OFF) is None
    assert p2_spend_auth_intercept(_st(), _sess(), _REG_OFF) == ''
    # 决策面零漂移:g=53 负分核心买,off 臂拒(非正分门,HEAD 行为)
    res_off = arbitrate([_core_buy(score=0.0)], _st(), _sess(), _REG_OFF)
    assert res_off.actions == []


# ===== 锁① 核心卡必买(全息带 / g=50 加急)+ 贴线带对齐 =====

def test_lock1_core_card_must_buy_spill_band() -> None:
    """锁①([31]②+P25 位):线锁定∧g≥53∧形态缺口∧核心卡在店→负分
    候选也越过非正分门进买序列(g=53 全息带,花完仍≥息线)。"""
    sess = _sess()
    res = arbitrate([_core_buy(gold_cost=3, score=0.0)], _st(gold=53),
                    sess, _REG_ON)
    buys = [a for a in res.actions if isinstance(a, BuyCard)]
    assert len(buys) == 1 and buys[0].card.name == _CORE, res.log


def test_lock1_boundary_g50_urgent_buys_and_line_band_aligned() -> None:
    """锁① g=50 边界 + 预算带对齐(v3「只开门不收门」;W758 攻击 A
    反例钉死):g=50 加急帧核心买入放行(通道 B 止血与通道 A 加急共
    档,保留金带内);g=50 常授权帧核心买 = 与既有息账门同判(花完
    47 跨档 → interest_rule EV 裁决,与 off 臂结论一致——v2 的「贴线
    带占位保守不买」收门子句已废除,G1-A 破息反降回归钉)。"""
    sess = _sess()
    # 加急:g=50(连败 T3)核心 3 费 → 保留金带(47≥20)→ 买
    st_u = _st(gold=50, streak=-2)
    assert p2_spend_auth_frame(st_u, sess, _REG_ON) is not None
    res_u = arbitrate([_core_buy(gold_cost=3, score=0.0)], st_u, sess,
                      _REG_ON)
    assert [a for a in res_u.actions if isinstance(a, BuyCard)], res_u.log
    # 常授权:g=50 核心买 → 与既有门同判(不买;off 臂同结论)
    res_on = arbitrate([_core_buy(gold_cost=3, score=0.0)], _st(gold=50),
                       sess, _REG_ON)
    res_off = arbitrate([_core_buy(gold_cost=3, score=0.0)], _st(gold=50),
                        sess, _REG_OFF)
    assert not [a for a in res_on.actions if isinstance(a, BuyCard)]
    assert (not [a for a in res_off.actions if isinstance(a, BuyCard)])


# ===== 锁②/⑧ 升级恒禁(濒死带 P21 + 停升级线 AND,授权不豁免)=====

def test_lock2_8_authorization_never_emits_or_relaxes_levelup() -> None:
    """锁②/⑧(P21/ADR-0448;v3.1 改写):授权通道对 LevelUp 恒不辖
    ——升级不因授权放宽;濒死 hp≤10 帧授权可触发(通道 B 止血恰以血
    线恶化为触发维度),但升级由血预算停手门(discipline 层,不受姿态
    让位影响)独立拒——授权帧动作序列不含 LevelUp。"""
    # 授权通道谓词对升级候选恒 False(加急/常授权两态同)
    for urgent_kw in ({}, {'streak': -2}, {'hp': 10}):
        st = _st(**urgent_kw)
        assert p2_spend_auth_spend_authorized(
            Candidate(action=LevelUp(cost=4), tag='levelup',
                      source='test'),
            st, st, _sess(), _REG_ON) is False
    # 濒死帧:授权触发(通道 B),但仲裁输出不含 LevelUp
    sess = _sess()
    st = _st(hp=10, streak=-2)
    auth = p2_spend_auth_frame(st, sess, _REG_ON)
    assert auth is not None and auth.channel_b
    res = arbitrate([(Candidate(action=LevelUp(cost=4), tag='levelup',
                                source='test'), 5.0, {})], st, sess,
                    _REG_ON)
    assert not any(isinstance(a, LevelUp) for a in res.actions), res.log


# ===== 锁③ j=0 负例保持(授权≠D 无条件开)=====

def test_lock3_negative_score_refresh_still_rejected_in_auth_frame() -> None:
    """锁③(P12 检验点2):授权帧(含加急)内负分刷新仍拒——授权只
    放宽预算上界,不动评分(V_D 批账 j=0 负例由既有 P12 锁组守);
    通道 B 的 D 消费 [31]②「保血急救」合法用途,凑数羁绊 D 禁令原文
    不变(评分不动即其机械化)。"""
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


# ===== 锁⑥ 锁定前提(通道 A 专属;通道 B 与锁定位解耦)=====

def test_lock6_lock_position_gates_channel_a_only() -> None:
    """锁⑥(v3.1 改写;§1.3 切分+P16):未锁定帧通道 A 不触发;通道
    B 照常判定(T3∧T4 即触发,锁不锁定次要)——消费位=滞回后 locked
    位(测试直设终态等价,生产位即 v3 状态机输出)。"""
    sess = _sess(locked=False)
    # 未锁定 ∧ 无血线恶化 → 无通道可授权(通道 A 被锁定位拦)
    assert p2_spend_auth_frame(_st(), sess, _REG_ON) is None
    assert p2_spend_auth_intercept(_st(), sess, _REG_ON) == 't1_locked'
    res = arbitrate([_core_buy(score=0.0)], _st(), sess, _REG_ON)
    assert res.actions == []
    # 未锁定 ∧ 血线恶化 → 通道 B 照常授权(解耦的行为钉)
    auth = p2_spend_auth_frame(_st(streak=-2), sess, _REG_ON)
    assert auth is not None and auth.channel_b and not auth.channel_a


# ===== 锁⑦ 末窗豁免收窄(v3:归 v6 接管帧谓词)=====

def test_lock7_endwindow_narrowed_to_v6_predicate(monkeypatch) -> None:
    """锁⑦(v3.1 改写;§3.3):r7 整体豁免废除——非接管末窗帧
    (boss 节点 r7)血线恶化∧g≥50 → 通道 B 授权可达(W762:死亡多
    发生在末窗附近);豁免统一归接管帧谓词,v6 active 末窗帧仍禁
    (与锁⑨合取闭合)。"""
    sess = _sess()
    st = _st(round_num=7, node_type='boss', streak=-2, gold=53)
    auth = p2_spend_auth_frame(st, sess, _REG_ON)
    assert auth is not None and auth.channel_b, auth
    from sr_od.application.currency_war.decision.decision_v2 import allocator
    from sr_od.application.currency_war.decision.decision_v2.allocator import (
        AllocDomain,
    )
    monkeypatch.setattr(allocator, 'alloc_domain',
                        lambda s, se, r: AllocDomain.STOP_WINDOW)
    assert p2_spend_auth_frame(st, sess, _REG_ON) is None
    assert p2_spend_auth_intercept(st, sess, _REG_ON) == 'v6_active'


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
    # 接管帧内加急预算谓词同样不放行(双保险,与门臂同源)
    st_u = _st(gold=53, streak=-2)
    monkeypatch.setattr(allocator, 'alloc_domain',
                        lambda s, se, r: AllocDomain.STOP_WINDOW)
    cand, _, _ = _core_buy(gold_cost=3, score=5.0)
    assert not p2_spend_auth_core_must_buy(cand, st_u, st_u, sess, _REG_ON)


# ===== 锁⑩ 止血通道可达性(v3;W762 死亡窗覆盖修复的行为钉)=====

def test_lock10_channel_b_reachable_decoupled_from_lock_and_form(
        monkeypatch) -> None:
    """锁⑩(§3.1 通道 B+W762 归因):未锁定∧形态已达标∧血线恶化∧
    g≥50 的非接管帧 → 授权判定触发且加急预算放宽生效(与锁定/形态
    无关);方向梯级注入名集内授权目标破息买入放行(on),off 臂同帧
    被既有息账门拒(开门的净效应可观测)。"""
    from sr_od.application.currency_war.decision.decision_v2 import phase
    sess = _sess(locked=False)
    monkeypatch.setattr(p2_spend_auth, '_hoard_projection',
                        lambda s, se: (frozenset({_DIR_PIECE}), True))
    monkeypatch.setattr(phase, 'form_ok',
                        lambda s, se, r: True)   # 形态已达标(T2 不成立)
    st = _st(gold=51, streak=-2)   # 破息刻度:51-4=47,既有门 EV 域
    auth = p2_spend_auth_frame(st, sess, _REG_ON)
    assert auth is not None and auth.channel_b \
        and not auth.channel_a and not auth.notes['t1_locked']
    assert p2_spend_auth_intercept(st, sess, _REG_ON) == 'authorized'
    cand, _, _ = _buy(_DIR_PIECE, gold_cost=4, score=0.5,
                      tag='off_target')
    # on:加急带(47≥保留金 20)放行;off:既有息账门拒(EV≤0 域)
    assert p2_spend_auth_spend_authorized(cand, st, st, sess, _REG_ON)
    res_on = arbitrate([(cand, 0.5, {})], st, sess, _REG_ON)
    res_off = arbitrate([(cand, 0.5, {})], st, sess, _REG_OFF)
    assert [a for a in res_on.actions if isinstance(a, BuyCard)], res_on.log
    assert not [a for a in res_off.actions if isinstance(a, BuyCard)]


# ===== 锁⑪ 只开门不收门(v3 预算带对齐;G1-A 反降回归钉)=====

def test_lock11_open_only_never_closes_existing_gates() -> None:
    """锁⑪(§3.1 预算带对齐):授权帧内**常授权层**(非加急)的每笔
    结论与既有息账门逐位一致——既有门放行的笔(同息档 [11])授权帧
    内照常放行,既有门拒绝的笔(跨档 EV≤0 域)授权不改判;授权臂只
    做额外放行从不拒绝。"""
    sess = _sess()
    # 同息档 1 费买(g=53,花完 52,零息损):on/off 同放行
    c1, s1, b1 = _buy('插件件一', gold_cost=1, score=5.0, tag='plugin')
    on1 = arbitrate([(c1, s1, b1)], _st(gold=53), sess, _REG_ON)
    off1 = arbitrate([(c1, s1, b1)], _st(gold=53), sess, _REG_OFF)
    assert bool([a for a in on1.actions if isinstance(a, BuyCard)])
    assert bool([a for a in off1.actions if isinstance(a, BuyCard)])
    # 跨档买(g=51 花 4 → 花完 47):常授权层不改判,on/off 同拒
    c2, s2, b2 = _buy('插件件二', gold_cost=4, score=5.0, tag='plugin')
    on2 = arbitrate([(c2, s2, b2)], _st(gold=51), sess, _REG_ON)
    off2 = arbitrate([(c2, s2, b2)], _st(gold=51), sess, _REG_OFF)
    assert (bool([a for a in on2.actions if isinstance(a, BuyCard)])
            == bool([a for a in off2.actions if isinstance(a, BuyCard)]))


# ===== 锁⑫ bench 保留槽(v3.1;[22]② 机械化)=====

def _full_bench(cap: int, free: int = 0) -> list:
    return [BenchChar(slot=i + 1, char_id=f'垫层{i}')
            for i in range(cap - free)]


def test_lock12_channel_b_bench_reserve_slot(monkeypatch) -> None:
    """锁⑫(§3.1 通道 B+[22]②):通道 B 授权买入后备战席须保留 ≥1
    空槽——买入后零空槽的笔授权不放行(降额,回落既有裁决);有余槽
    帧放行。防「连续止血买入填满 bench → 线锁定后核心卡无槽可进」的
    挤出回声。"""
    sess = _sess(locked=False)
    monkeypatch.setattr(p2_spend_auth, '_hoard_projection',
                        lambda s, se: (frozenset({_DIR_PIECE}), True))
    st = _st(gold=51, streak=-2)
    cand, _, _ = _buy(_DIR_PIECE, gold_cost=4, score=5.0)
    cap = DEFAULT_REGISTRY.bench_capacity
    # 满席 → 授权不放行(腾不出降额;仲裁面 bench_capacity 亦拒)
    st_full = _st(gold=51, streak=-2,
                  bench=_full_bench(cap, free=0))
    assert not p2_spend_auth_spend_authorized(cand, st_full, st_full,
                                              sess, _REG_ON)
    res = arbitrate([(cand, 5.0, {})], st_full, sess, _REG_ON)
    assert not [a for a in res.actions if isinstance(a, BuyCard)], res.log
    # 恰剩 1 空槽 → 买入后零空槽,授权不放行(保留槽条款本体)
    st_one = _st(gold=51, streak=-2, bench=_full_bench(cap, free=1))
    assert not p2_spend_auth_spend_authorized(cand, st_one, st_one,
                                              sess, _REG_ON)
    # 余槽 ≥2 → 买入后仍 ≥1 空槽,授权放行
    st_two = _st(gold=51, streak=-2, bench=_full_bench(cap, free=2))
    assert p2_spend_auth_spend_authorized(cand, st_two, st_two,
                                          sess, _REG_ON)


# ===== 锁⑬ hoard 投影失败禁整库保守域(v3.1 方向梯级)=====

def test_lock13_projection_failure_never_uses_conservative_domain(
        monkeypatch) -> None:
    """锁⑬(§3.1 通道 B 梯级+W758-v3 面①攻击 C):hoard 投影失败帧
    跳过 hoard 级直落桥池/[31]①,整库保守域不作方向源——纯散件
    (无过渡体系键、不在方向名集)恒不授权;桥池方向件照常授权;
    拦断面枚举记 hoard_invalid。"""
    from sr_od.application.currency_war.kernel import cw_bridge_pool
    sess = _sess(locked=False)
    # 投影失败注入(D1 同口径:失败帧 (空集, False))
    monkeypatch.setattr(p2_spend_auth, '_hoard_projection',
                        lambda s, se: (frozenset(), False))
    st = _st(gold=53, streak=-2)
    auth = p2_spend_auth_frame(st, sess, _REG_ON)
    assert auth is not None and auth.channel_b
    assert p2_spend_auth_intercept(st, sess, _REG_ON) == 'hoard_invalid'
    # 桥池级:BRIDGE_POOL_P2 方向件授权可达(P2 桥 fixed∪core∪flex;
    # 取 core[0] 避开测试核心名集与通道 A 标签集,确保走方向名集辖域)
    bridge_name = cw_bridge_pool.BRIDGE_POOL_P2[0].core[0]
    cand_bridge, _, _ = _buy(bridge_name, gold_cost=3, score=5.0,
                             tag='off_target')
    assert p2_spend_auth_spend_authorized(cand_bridge, st, st, sess,
                                          _REG_ON)
    # 桥池空(注入)→ [31]① 级:过渡体系键非空可授权(希儿系哨兵键),
    # 纯散件(无键)恒不授权——整库保守域被结构性排除
    monkeypatch.setattr(cw_bridge_pool, 'BRIDGE_POOL_P2', [])
    cand_scatter, _, _ = _buy('无注册散件', gold_cost=3, score=5.0,
                              tag='off_target')
    assert not p2_spend_auth_spend_authorized(cand_scatter, st, st, sess,
                                              _REG_ON)
    cand_fill, _, _ = _buy('希儿', gold_cost=3, score=5.0,
                           tag='off_target')
    assert p2_spend_auth_spend_authorized(cand_fill, st, st, sess,
                                          _REG_ON)


# ===== 锁⑭/⑮ 窗级水位目标(⑭ v3.3 改写:净支出闸废除)+ 高价值优先 =====

def _core_shop() -> list:
    """三张 5 费核心卡店态(注入核心名集内;锁语义不锁牌面,取测试
    核心名集任意三个)。"""
    return [ShopCard(x=0, name=nm, cost=5)
            for nm in ('花火', '瓦尔特', '三月七')]


def test_lock15_high_value_targets_gate_fallback(monkeypatch) -> None:
    """锁⑮(§3.1 梯级+[22]③;v3.3 重述):店内存在 L1 目标时,L3 低价
    兜底件不获授权放行;兜底层仅在店内无 L1 目标时出现——空店帧(L1
    无供给)L3 兜底照旧(①-⑬ 锁的既有断言域)。v3.3:条件从 v3.2 的
    「过净支出闸」改为「店内 L1 目标在场」(闸已废除,行为断言不变)。"""
    sess = _sess(locked=False)   # 通道 B 帧
    monkeypatch.setattr(p2_spend_auth, '_hoard_projection',
                        lambda s, se: (frozenset({_DIR_PIECE}), True))
    # L1 在场帧(Σ支出 15 ≤ 收入 11+——旧净支出闸按支出降序累计会给出
    # 非空选中集;v3.3 无论收支比,L1 在场即辖域)
    st = _st(gold=53, streak=-2, shop=_core_shop())
    cand_h, _, _ = _buy('花火', gold_cost=5, score=5.0)
    cand_l3, _, _ = _buy(_DIR_PIECE, gold_cost=1, score=5.0,
                         tag='off_target')
    assert p2_spend_auth_spend_authorized(cand_h, st, st, sess, _REG_ON)
    assert not p2_spend_auth_spend_authorized(cand_l3, st, st, sess,
                                              _REG_ON)
    # 兜底条件帧:空店(店内无 L1 目标)→ L3 兜底照旧放行
    st_empty = _st(gold=53, streak=-2)
    assert p2_spend_auth_spend_authorized(cand_l3, st_empty, st_empty,
                                          sess, _REG_ON)


def test_lock14_window_water_target_no_income_gate(monkeypatch) -> None:
    """锁⑭(v3.3 改写;§3.1 窗级水位目标+W779 审计①):v3.2 单帧净
    支出闸废除——店内 L1 目标即使 Σ支出 ≤ 本轮预期收入(旧闸「累计
    支出>收入前缀才放行」的必拒域,即 W779 观测的零净出手 88.5% 帧)
    也授权放行(出手计划目标=窗级水位不升,判据在协议 V4 不在帧闸);
    店内无 L1/XP/合法 sink 的帧零动作回落既有裁决(不强求出手);
    窗级水位计入遥测披露键(sess_p2_auth_water,M0b 判读数据源)。"""
    from sr_od.application.currency_war.decision.decision_v2.\
        p2_spend_auth import _expected_round_income
    sess = _sess(locked=False)
    monkeypatch.setattr(p2_spend_auth, '_hoard_projection',
                        lambda s, se: (frozenset({_DIR_PIECE}), True))
    # 旧闸必拒域钉:单张 1 费 L1 名件?不——取「三张 5 费核心 Σ=15>11」
    # 的反例:单张 3 费核心(3 ≤ 收入 11,旧闸选中集空=落 L3 不放行,
    # v3.2 下 spend_authorized 对该名返回 False)→ v3.3 放行
    st = _st(gold=53, streak=-2,
             shop=[ShopCard(x=0, name='三月七', cost=3)])
    income = _expected_round_income(st)
    assert 3 <= income   # 旧闸必拒域成立(Σ支出 ≤ 收入)
    cand, _, _ = _buy('三月七', gold_cost=3, score=5.0)
    assert p2_spend_auth_spend_authorized(cand, st, st, sess, _REG_ON)
    # L3 兜底件仍不获救:负分候选零动作(既有非正分门拒,授权不放行)
    cand_l3, _, _ = _buy(_DIR_PIECE, gold_cost=1, score=-2.0,
                         tag='off_target')
    res_l3 = arbitrate([(cand_l3, -2.0, {})], st, sess, _REG_ON)
    assert res_l3.actions == [], res_l3.log
    # 水位观测入披露键:三帧滚动窗(窗起点金/窗终金/窗内收支)
    from sr_od.application.currency_war.telemetry.schema import DecisionTrace
    assert DecisionTrace().sess_p2_auth_water is None
    p2_spend_auth.p2_spend_auth_water_note(
        _st(gold=53, streak=-2), sess, _REG_ON)
    p2_spend_auth.p2_spend_auth_water_note(
        _st(gold=60, streak=-2, round_num=3), sess, _REG_ON)
    w = p2_spend_auth.p2_spend_auth_water_note(
        _st(gold=58, streak=-2, round_num=4), sess, _REG_ON)
    assert w['window_start_gold'] == 53 and w['window_end_gold'] == 58
    assert w['window_income'] == 22 and w['window_spend'] == 17, w
    assert w['rounds'] == [2, 3, 4]
    # 同轮 re-decide 去重(刷后段链不重复记账)
    w2 = p2_spend_auth.p2_spend_auth_water_note(
        _st(gold=58, streak=-2, round_num=4), sess, _REG_ON)
    assert w2 == w


# ===== 锁⑯ XP sink 门边界(v3.3 新增;P21/ADR-0448 门 AND 不动)=====

def test_lock16_xp_sink_gate_boundaries(monkeypatch) -> None:
    """锁⑯(§3.1 XP sink+P21/ADR-0448):授权帧内买经验仅当 hp>停升级
    线(ADR-0448)∧ 非 P21 濒死带(hp>10)∧ 概率窗未达(carry 费档查
    表,[3] 提概率路径);两门帧/窗内帧 XP 授权为空。升级授权裁决落
    ev.levelup_ev_basis 臂④ 'p2_auth_xp'——授权帧 arbiter 输出含
    LevelUp(auth_basis 记臂名),门边界帧不含;off 臂谓词恒 False
    (零漂移)。spend_authorized 对 LevelUp 恒 False(买/升通道分离)。"""
    from sr_od.application.currency_war.kernel import cw_economy
    from sr_od.application.currency_war.decision.decision_v2.ev import (
        levelup_ev_basis,
    )
    sess = _sess(locked=False)
    monkeypatch.setattr(cw_economy, '_target_core_cost',
                        lambda s: ('某核心', 4))   # 概率窗目标级 L10
    lu = Candidate(action=LevelUp(cost=4), tag='levelup', source='xp')
    # 门内帧(hp 80>停升级线 21>10;level 6<10;T3∧T4):授权成立
    st_ok = _st(gold=53, streak=-2, hp=80, level=6)
    assert p2_spend_auth.p2_spend_auth_xp_authorized(st_ok, sess, _REG_ON)
    assert levelup_ev_basis(st_ok, sess, _REG_ON, 53, 4,
                            set(), val=5.0) == 'p2_auth_xp'
    # P21 濒死带(hp=10)与停升级线内(hp=21≤线):授权为空且仲裁无 LevelUp
    for hp in (10, 21):
        st_b = _st(gold=53, streak=-2, hp=hp, level=6)
        assert not p2_spend_auth.p2_spend_auth_xp_authorized(
            st_b, sess, _REG_ON)
    st_b = _st(gold=53, streak=-2, hp=10, level=6)
    res = arbitrate([(lu, 5.0, {})], st_b, sess, _REG_ON)
    assert not any(isinstance(a, LevelUp) for a in res.actions), res.log
    # 血线门内帧仲裁兜底(blood_budget_stop 独立 AND,不依赖授权谓词)
    st_line = _st(gold=53, streak=-2, hp=21, level=6)
    res_line = arbitrate([(lu, 5.0, {})], st_line, sess, _REG_ON)
    assert not any(isinstance(a, LevelUp) for a in res_line.actions), \
        res_line.log
    # hp 不可信帧 fail-closed 不授权(ADR-0448 血线谓词同口径)
    st_u = _st(gold=53, streak=-2, hp=80, level=6, hp_readable=False,
               hp_trusted=False)
    assert not p2_spend_auth.p2_spend_auth_xp_authorized(st_u, sess,
                                                         _REG_ON)
    # 已在概率窗内(level≥L10)→ 升级不再提概率,授权消失
    st_w = _st(gold=53, streak=-2, hp=80, level=10)
    assert not p2_spend_auth.p2_spend_auth_xp_authorized(st_w, sess,
                                                         _REG_ON)
    # 非加急帧(常授权层)与开关关:恒 False(零漂移)
    assert not p2_spend_auth.p2_spend_auth_xp_authorized(
        _st(hp=80, level=6), sess, _REG_ON)
    assert not p2_spend_auth.p2_spend_auth_xp_authorized(st_ok, sess,
                                                         _REG_OFF)
    # 买/升通道分离:spend_authorized 对 LevelUp 恒 False(授权帧内)
    assert not p2_spend_auth_spend_authorized(lu, st_ok, st_ok, sess,
                                              _REG_ON)
    # 门内帧仲裁端到端:LevelUp 放行且 auth_basis 记臂名
    res_ok = arbitrate([(lu, 5.0, {})], st_ok, sess, _REG_ON)
    lus = [a for a in res_ok.actions if isinstance(a, LevelUp)]
    assert len(lus) == 1 and lus[0].auth_basis == 'p2_auth_xp', res_ok.log


# ===== W766 附带发现核查:授权与成交之间的补偿分数门(W768 顺手修)=====

def _sellable_fillers(n: int) -> list:
    """可弃垫层件(真实注册名,排除引擎件保护集;board 空=无边际羁绊
    贡献守卫不挡)——S6 卖序的真实供给形态。"""
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        engine_char_names,
    )
    engines = engine_char_names()
    names = [nm for nm, ch in CHARACTERS.items()
             if nm not in engines and ch.cost]
    return [BenchChar(slot=i + 1, char_id=nm, faction='仙舟')
            for i, nm in enumerate(names[:n])]


def test_w766_authorized_core_buy_survives_bench_full_via_remediation() -> None:
    """W766 附带发现(成交率 50-70% 的买执行层否决点之一,本批顺手修;
    ADR-0481):授权帧核心必买候选(负分=评分零维伪影)在满栏帧被
    bench_capacity 拒后,补偿趟 S6 的 ``remedy_min_score`` 分数门不再
    拒绝腾位——先卖可弃垫层件、重试买成交(设计 v3.1 保留槽条款
    「先卖可弃垫层件腾槽再买」的机械化);off 臂同帧零动作(分数门
    恢复 + 非正分门拒,零漂移)。"""
    sess = _sess(locked=False)   # 通道 B 帧(锁定位解耦);核心名集注入
    filler_bench = _sellable_fillers(DEFAULT_REGISTRY.bench_capacity)
    st = _st(gold=53, streak=-2, bench=filler_bench)
    cand, _, _ = _core_buy(gold_cost=3, score=-2.0)   # 负分核心卡
    res = arbitrate([(cand, -2.0, {})], st, sess, _REG_ON)
    buys = [a for a in res.actions if isinstance(a, BuyCard)]
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert any(a.card.name == _CORE for a in buys), res.log
    assert sells, '腾位卖缺失(保留槽条款的先卖腿)' and res.log
    # off 臂:同帧同候选 → 非正分门拒(授权豁免关),零动作
    res_off = arbitrate([(cand, -2.0, {})], st, sess, _REG_OFF)
    assert res_off.actions == []




# ===== 拦断面普查枚举(设计 §3.5;协议 M0 分层消费)=====

def test_intercept_enum_full_coverage(monkeypatch) -> None:
    """拦断面普查(W757 v3 §3.5):金堆积候选帧逐帧拦截原因枚举全值
    覆盖——t4_gold/v6_active/authorized/hoard_invalid/t1_locked/
    t2_form/off 臂 ''。no_t3 分支在两通道取或结构下不可达(通道 A
    不需要 T3),保留枚举兼容协议词汇表(纯防御分支,声明于报告)。"""
    sess = _sess()
    # t4_gold / authorized
    assert p2_spend_auth_intercept(_st(gold=49), sess, _REG_ON) == 't4_gold'
    assert p2_spend_auth_intercept(_st(), sess, _REG_ON) == 'authorized'
    # v6_active(接管帧)
    from sr_od.application.currency_war.decision.decision_v2 import (
        allocator,
        phase,
    )
    from sr_od.application.currency_war.decision.decision_v2.allocator import (
        AllocDomain,
    )
    monkeypatch.setattr(allocator, 'alloc_domain',
                        lambda s, se, r: AllocDomain.DEATH)
    assert p2_spend_auth_intercept(_st(), sess, _REG_ON) == 'v6_active'
    monkeypatch.undo()
    # t1_locked(未锁定,通道 A 被拦)
    assert p2_spend_auth_intercept(_st(), _sess(locked=False),
                                   _REG_ON) == 't1_locked'
    # t2_form(锁定 ∧ 形态已达标 ∧ 无血线恶化 → 通道 A 因形态不触发)
    monkeypatch.setattr(phase, 'form_ok', lambda s, se, r: True)
    assert p2_spend_auth_intercept(_st(), sess, _REG_ON) == 't2_form'
    monkeypatch.undo()
    # off 臂:枚举恒 ''(无授权语义,零漂移)
    assert p2_spend_auth_intercept(_st(), sess, _REG_OFF) == ''


# ===== 加急预算带(通道 A 加急 / 通道 B 共档;合并语义载体)=====

def test_two_layer_budget_bands() -> None:
    """层强度:加急层(T3)破息至保留金下限([18] 止损机械化),通道 A
    加急与通道 B 同档(合并语义「预算同值交集」);常授权层无独立地板
    (既有门全权裁决,加急谓词恒 False)。v3.2:下限=公式化
    5×min(剩余备战轮数,3)——测试基帧 r2/日程先验 9 → 8 轮 → 下限 15
    (「放宽有界」语义不变,界随公式重推,常数 20 降为异常地板)。"""
    sess = _sess()
    # 常授权帧:加急谓词恒 False(预算带对齐——与既有门同判)
    assert not p2_spend_auth_spend_authorized(
        Candidate(action=RefreshShop(cost=2), tag='refresh',
                  source='test'),
        GameState(plane=2, gold=30, hp=80), _st(gold=53), sess, _REG_ON)
    # 加急帧:破息刻度花完 28 ≥ 公式下限 15 → 放行
    assert p2_spend_auth_spend_authorized(
        Candidate(action=RefreshShop(cost=2), tag='refresh',
                  source='test'),
        GameState(plane=2, gold=30, hp=80), _st(gold=53, streak=-2),
        sess, _REG_ON)
    # 通道 B 未锁定帧同档放行(合并语义:两通道同一放宽档)
    assert p2_spend_auth_spend_authorized(
        Candidate(action=RefreshShop(cost=2), tag='refresh',
                  source='test'),
        GameState(plane=2, gold=30, hp=80), _st(gold=53, streak=-2),
        _sess(locked=False), _REG_ON)
    # 公式下限之下不放行(花完 <15 的笔仍拒——放宽有界;常数 20 时代
    # 的 21 金断言随公式化重推:19 ≥ 15 现为放行域)
    assert not p2_spend_auth_spend_authorized(
        Candidate(action=RefreshShop(cost=2), tag='refresh',
                  source='test'),
        GameState(plane=2, gold=16, hp=80), _st(gold=53, streak=-2),
        sess, _REG_ON)


def test_t3_blood_worsening_two_clauses() -> None:
    """T3 血线恶化两子句(W757 §3.1;占位值注记):连败 ≥N_fail(占位
    2)或 hp≤警戒带(占位=P1 出口血目标线 60,hp 可信位守卫)。"""
    # 连败子句:streak=-2 命中,-1 不命中
    assert p2_spend_auth_frame(_st(streak=-2), _sess(), _REG_ON).urgent
    assert not p2_spend_auth_frame(_st(streak=-1), _sess(),
                                   _REG_ON).urgent
    # hp 子句:hp≤警戒带(=p1_exit_blood_target 60)命中;不可信 hp
    # (沿用/兜底帧)不作报警依据(ADR-0282 口径)
    assert p2_spend_auth_frame(_st(hp=60), _sess(), _REG_ON).urgent
    assert not p2_spend_auth_frame(_st(hp=61), _sess(),
                                   _REG_ON).urgent
    assert not p2_spend_auth_frame(_st(hp=61, hp_readable=False,
                                       hp_trusted=False), _sess(),
                                   _REG_ON).urgent
