"""W948 转型臂(停滞评估臂)单帧锁。

命题出处 = 设计件 .debug/temp/currency_war/w948_transform_design/DESIGN.md
§2.1-§2.5(机制/防振荡/验证划分)+ ADR-0509(决策 why)。病灶 = 锁定态
form_ok 恒 False 板混填充多轮无下车(复盘 g_20260831_053546:锁 DOT 队后
form 锁死 7 轮零重估)——锁语义缺「当前最优假设可改判」半边,本机制在
锁定态补进度侧停滞评估:窗级采购集缺口无收敛 + hp 净降 + form 恒未成型
→ 降级 weak(完全复用撤销出口①字段契约,证据 kind='stagnate')。

锁契约(每条 = 一个确定输入下的确定行为;不锁分布数值):
- ① 停滞判据与触发时机:on 臂下连续 N 个评估窗(W 轮/窗)停滞恰好于
  第 W×N 轮触发降级;任一判据破缺(缺口收敛 / hp 不降 / form 任一帧
  成型)即窗计数归零不触发——判据是窗级过程量,gap = 锁线 hoard 角色
  目标件未到手数,**不升格 form_score**(ADR-0353 纯遥测口径不动);
- ② 触发链复用:降级形态与撤销出口①同字段契约(weak_comp=原线 /
  prev_lock_layer 暂存 / revoke_evidence.kind='stagnate'),下游新信号
  经既有 C4 门落新线、证据消费清空;
- ③ 防振荡:单向降级(无信号不自动回锁)+ 冷却驻留(同线同位面至多
  一次改判——回锁后再停滞不重触发);位面切换清冷却与计数;
- ④ salvage 出口分支:stagnate-weak 持续超窗仍无新线 → hoard 转向
  mode='salvage'(跨线骨架,停线内投入);**非 absorbing**——新信号
  照常落线救回;P3 demoted_endgame absorbing 语义零改动(本批不触);
- ⑤ P2 入口弱占位(乙):无信号空位帧派生资产最厚占位方向,hoard
  优先于⑤绯英兜底;有信号即退场;
- ⑥ 关臂零漂移锚(显式注入 off):同场景序列行为与缺省栈逐位一致,
  ist 停滞状态族保持缺省值;
- ⑦ registry 字段面:双开关默认 False(开关生命周期第 1 态落码,
  开臂判据挂账 = registry 注释 + ADR-0509)。

守卫移除红检(验证纪律):⑥的 off 锚由守卫分支承载——把
cw_intention._stagnation_tick / 占位写入段的开关守卫移除(或
update_intention 入口清零段去门)后,⑥必须转红;实施批已按此口径
人工变异复验(REPORT 记录),禁只信绿。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_intention import (
    CROSS_LINE_SKELETON,
    FALLBACK_COMP_NAME,
    IntentionState,
    _line_hoard,
    get_comp,
    hoard_target_set,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.data.cw_chars import CHARACTERS

_LINE = '列车同行'          # 锁定线(v2 家族;plaza_carry 姬子·启行 全库唯一)
_CORE = '姬子·启行'
_ALT_LINE = '命运圣杯红A'    # 异线(v2 家族;plaza_carry Archer 全库唯一)
_ALT_CORE = 'Archer'

_REG_ON = dataclasses.replace(DEFAULT_REGISTRY,
                              intention_stagnation_arm_enabled=True)
_REG_B_ON = dataclasses.replace(DEFAULT_REGISTRY,
                                p2_entry_weak_target_enabled=True)


def _state(round_num: int, *, hp: int = 10, level: int = 5,
           shop: list[str] | None = None,
           bench: list[str] | None = None) -> GameState:
    """P2 备战帧基准构造(空板空店 = 无信号、缺口恒定、战力零)。"""
    shop = shop or []
    bench = bench or []
    return GameState(
        plane=2, round_num=round_num, gold=30, level=level, hp=hp,
        shop_refresh_cost=2,
        shop=[_shop_card(n, i) for i, n in enumerate(shop)],
        deployed=[],
        bench=[BenchChar(slot=i, char_id=n, faction='?', star=1)
               for i, n in enumerate(bench)] + [None] * (BENCH_CAPACITY - len(bench)),
        node_type='prep')


def _shop_card(name: str, i: int):
    """商店卡构造(费用按注册表;可见面读 card.name,构造直接给规范名)。"""
    ch = CHARACTERS.get(name)
    from sr_od.application.currency_war.kernel.cw_state import ShopCard
    return ShopCard(x=100 + i * 150, name=name,
                    cost=ch.cost if ch is not None else 1)


def _locked_ist() -> IntentionState:
    """P2 锁定帧(③层锁线形;prev_lock_layer 待降级时暂存验证)。"""
    return IntentionState(phase='locked', locked_comp=_LINE,
                          lock_layer=3, lock_plane=2, lock_round=1)


def _drive_stagnate(state: GameState, ist: IntentionState,
                    sess: StrategySession, reg, round_num: int,
                    hp: int) -> None:
    """推进一轮停滞驱动(hp 递减、form 恒未成型、无信号)。"""
    state.round_num = round_num
    state.hp = hp
    sess.v3_form_ok = False
    update_intention(state, ist, sess, registry=reg)


def _run_stagnation(reg, rounds: int, *, sess_form_ok: bool = True):
    """跑 rounds 轮 hp 线性递减的停滞序列,返回 (state, ist, session)。"""
    st = _state(1, hp=20)
    ist = _locked_ist()
    sess = StrategySession()
    for r in range(2, rounds + 1):
        _drive_stagnate(st, ist, sess, reg, r, hp=20 - r)
        if not sess_form_ok:
            sess.v3_form_ok = True
    return st, ist, sess


# --- ① 停滞判据与触发时机 ------------------------------------------------------


def test_stagnate_triggers_at_exactly_windows_x_rounds() -> None:
    """on:W=2×N=2 → 恰在第 4 个停滞驱动轮(轮 5)触发降级;证据字段契齐。"""
    st, ist, _ = _run_stagnation(_REG_ON, rounds=4)
    assert ist.phase == 'locked'   # 首窗已停滞(1/2),窗数未满不触发
    assert ist.stagnate_windows_hit == 1
    st, ist, _ = _run_stagnation(_REG_ON, rounds=5)
    assert ist.phase == 'weak'
    assert ist.weak_comp == _LINE
    assert ist.locked_comp == ''
    assert ist.prev_lock_layer == 3   # 出口①同款暂存契约
    ev = ist.revoke_evidence
    assert ev.get('kind') == 'stagnate'
    assert ev.get('windows') == 2
    assert ev.get('gap_from') == ev.get('gap_to')   # 缺口恒定=无收敛
    assert ev.get('hp_to', 0) < ev.get('hp_from', 0)   # 净降
    assert ist.stagnate_cool == {_LINE: 2}
    assert ist.last_event.startswith('revoke:stagnate:')


def test_stagnate_gap_convergence_blocks_trigger() -> None:
    """on:窗内缺口下降(收敛)→ 该窗不计停滞,连停计数归零,不触发。"""
    st, ist, sess = _run_stagnation(_REG_ON, rounds=3)
    assert ist.stagnate_windows_hit == 1   # 窗 1 停滞(对照基准)
    # 窗 2 首轮后补进一枚锁线 hoard 成员 → 窗末 gap < 窗首 gap
    st.bench[0] = BenchChar(slot=0, char_id='三月七', faction='?', star=1)
    _drive_stagnate(st, ist, sess, _REG_ON, 4, hp=16)
    _drive_stagnate(st, ist, sess, _REG_ON, 6, hp=14)
    assert ist.phase == 'locked'
    assert ist.stagnate_windows_hit == 0


def test_stagnate_hp_flat_blocks_trigger() -> None:
    """on:hp 不降(缺战力侧确证)→ 不触发。"""
    st = _state(1, hp=20)
    ist = _locked_ist()
    sess = StrategySession()
    for r in range(2, 7):
        _drive_stagnate(st, ist, sess, _REG_ON, r, hp=20)   # hp 恒定
    assert ist.phase == 'locked'


def test_stagnate_form_genuine_green_frame_blocks_trigger() -> None:
    """on:评估窗内任一帧 form 真成型(核心 2★ 当量在手)→ 丧失停滞资格。"""
    st = _state(1, hp=20)
    st.bench[0] = BenchChar(slot=0, char_id=_CORE, faction='?', star=2)
    ist = _locked_ist()
    sess = StrategySession()
    for r in range(2, 5):
        _drive_stagnate(st, ist, sess, _REG_ON, r, hp=20 - r)
    st.round_num = 5
    st.hp = 15
    sess.v3_form_ok = True   # 窗 2 末帧真成型(核心 2★ 在手)→ 丧失停滞资格
    update_intention(st, ist, sess, registry=_REG_ON)
    assert ist.phase == 'locked'
    assert ist.stagnate_windows_hit == 0


def test_stagnate_form_fake_green_still_triggers() -> None:
    """on:form 假绿形态(sim 支B:form_ok 恒 true 而核心零副本未兑现)→
    假绿计入未成型,停滞照常触发——判据 P2 修正的靶形。"""
    st = _state(1, hp=20)
    ist = _locked_ist()
    sess = StrategySession()
    for r in range(2, 6):
        st.round_num = r
        st.hp = 20 - r
        sess.v3_form_ok = True   # 假绿:form 恒绿(空板核心 0 副本)
        update_intention(st, ist, sess, registry=_REG_ON)
    assert ist.phase == 'weak'
    assert ist.revoke_evidence.get('kind') == 'stagnate'


# --- ② 触发链复用(下游零新增)--------------------------------------------------


def test_stagnate_downstream_new_line_lock_consumes_evidence() -> None:
    """on:停滞降级后异线核心在店(③信号)→ 经既有通道落新线,证据消费。"""
    st, ist, sess = _run_stagnation(_REG_ON, rounds=5)
    assert ist.phase == 'weak'
    st.shop = [_shop_card(_ALT_CORE, 0)]
    st.round_num = 6
    update_intention(st, ist, sess, registry=_REG_ON)
    assert ist.phase == 'locked'
    assert ist.locked_comp == _ALT_LINE
    assert ist.revoke_evidence == {}   # _lock=证据消费完毕(字段契约)


def test_stagnate_downgrade_hoard_detaches_from_line_immediately() -> None:
    """on:降级当帧起买侧囤货依据即脱离原线采购集(hoard mode='weak' 跨线
    骨架)——本臂对「分配器/演进执行线 vs 锁线脱节」病灶(复盘存档
    match g_20260831_082322 候选#2 实证)辖域内的半边:方向层只保证
    hoard 单一消费面即时切换;执行侧 alloc/evolve 是否跟随 hoard 属
    分配器域断言,不归本锁(对账结论见 w954 REPORT §5)。"""
    st, ist, sess = _run_stagnation(_REG_ON, rounds=5)
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'weak'
    assert ht.char_targets == frozenset(CROSS_LINE_SKELETON)
    line_comp = get_comp(_LINE)
    assert line_comp is not None
    chars, _eq = _line_hoard(line_comp)
    assert not (frozenset(chars) - frozenset(CROSS_LINE_SKELETON)) \
        & ht.char_targets   # 原线独有目标件零残留(囤货依据已换面)


# --- ③ 防振荡(单向降级 + 冷却驻留)----------------------------------------------


def test_stagnate_no_auto_relock_without_signal() -> None:
    """on:降级后无信号 → 停留 weak(单向降级,无反向自动升级)。"""
    st, ist, sess = _run_stagnation(_REG_ON, rounds=5)
    _drive_stagnate(st, ist, sess, _REG_ON, 6, hp=14)
    assert ist.phase == 'weak'


def test_stagnate_cooldown_blocks_second_trigger_same_plane() -> None:
    """on:冷却驻留——停滞降级后经同线豁免回锁原线,再停滞不重触发。"""
    st, ist, sess = _run_stagnation(_REG_ON, rounds=5)
    assert ist.stagnate_cool == {_LINE: 2}
    # 原线核心在店 → ③信号,同线豁免门回锁(既有 weak 下游语义)
    st.shop = [_shop_card(_CORE, 0)]
    st.round_num = 6
    update_intention(st, ist, sess, registry=_REG_ON)
    assert ist.locked_comp == _LINE   # 回锁原线
    # 再停滞 W×N 轮(hp 递减、form 恒 False、核心离场):冷却必须拦住
    st.shop = []
    for r in range(7, 11):
        _drive_stagnate(st, ist, sess, _REG_ON, r, hp=10 - (r - 6))
    assert ist.phase == 'locked'   # 未再降级(同线同位面只改判一次)
    assert ist.last_event.startswith('lock:')


def test_stagnate_state_cleared_on_plane_switch() -> None:
    """on:位面切换清窗级计数与冷却驻留(陈旧进度证据不跨位面)。"""
    st, ist, sess = _run_stagnation(_REG_ON, rounds=5)
    assert ist.stagnate_cool
    st.plane = 3
    st.round_num = 1
    update_intention(st, ist, sess, registry=_REG_ON)
    assert ist.stagnate_cool == {}
    assert ist.stagnate_rounds_in_window == 0
    assert ist.stagnate_windows_hit == 0
    assert ist.stagnate_gap_ref is None
    assert ist.stagnate_hp_ref is None


# --- ④ salvage 出口分支(weak 子模式,非 absorbing)------------------------------


def test_salvage_mode_after_weak_window_expiry() -> None:
    """on:stagnate-weak 持续超 salvage_window_rounds → hoard 转向 salvage
    (跨线骨架;停原线终局件投入)。"""
    st, ist, sess = _run_stagnation(_REG_ON, rounds=5)
    for r in range(6, 10):   # weak 计数 1..4 > 阈值 3
        _drive_stagnate(st, ist, sess, _REG_ON, r, hp=14)
    assert ist.stagnate_salvage is True
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'salvage'
    assert ht.char_targets == frozenset(CROSS_LINE_SKELETON)


def test_salvage_not_absorbing_new_signal_rescues() -> None:
    """on:salvage 在效时新信号照常落新线(salvage 非 absorbing)。"""
    st, ist, sess = _run_stagnation(_REG_ON, rounds=5)
    for r in range(6, 10):
        _drive_stagnate(st, ist, sess, _REG_ON, r, hp=14)
    assert ist.stagnate_salvage is True
    st.shop = [_shop_card(_ALT_CORE, 0)]
    st.round_num = 10
    update_intention(st, ist, sess, registry=_REG_ON)
    assert ist.phase == 'locked'
    assert ist.locked_comp == _ALT_LINE
    assert ist.stagnate_salvage is False   # 离开 stagnate-weak 即退场


def test_weak_without_stagnate_keeps_plain_weak_mode() -> None:
    """on:出口①降级的 weak(证据 kind='miss')不走 salvage——
    salvage 辖域仅 stagnate 证据,不动既有撤销下游语义。"""
    ist = IntentionState(phase='weak', weak_comp=_LINE,
                         revoke_evidence={'kind': 'miss'})
    ist.stagnate_salvage = False
    st = _state(6, hp=3)
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'weak'


# --- ⑤ P2 入口弱占位(乙)--------------------------------------------------------


def test_p2_entry_placeholder_takes_hoard_priority() -> None:
    """乙 on:P2 unlocked 无信号帧派生占位方向,hoard 优先于绯英兜底。"""
    st = _state(1)
    ist = IntentionState(phase='unlocked')
    sess = StrategySession()
    update_intention(st, ist, sess, registry=_REG_B_ON)
    assert ist.weak_placeholder != ''
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'p2_weak_target'
    pc = get_comp(ist.weak_placeholder)
    assert pc is not None
    chars, equips = _line_hoard(pc)
    assert ht.char_targets == frozenset(chars)
    assert ht.equip_targets == frozenset(equips)


def test_p2_entry_placeholder_off_falls_back() -> None:
    """乙 off(缺省):同帧 hoard 仍落⑤绯英兜底(零漂移)。"""
    st = _state(1)
    ist = IntentionState(phase='unlocked')
    sess = StrategySession()
    update_intention(st, ist, sess, registry=DEFAULT_REGISTRY)
    assert ist.weak_placeholder == ''
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'fallback'
    assert FALLBACK_COMP_NAME == '绯英欢愉'   # 兜底单一源 sanity


def test_p2_entry_placeholder_exits_on_signal() -> None:
    """乙:信号帧占位退场(可被任何信号推翻的初始假设)——核心在店即落锁。"""
    st = _state(1)
    ist = IntentionState(phase='unlocked')
    sess = StrategySession()
    update_intention(st, ist, sess, registry=_REG_B_ON)
    assert ist.weak_placeholder != ''
    st.shop = [_shop_card(_CORE, 0)]
    st.round_num = 2
    update_intention(st, ist, sess, registry=_REG_B_ON)
    assert ist.phase == 'locked'
    assert ist.weak_placeholder == ''
    assert hoard_target_set(st, ist).mode == 'locked'


# --- ⑥⑦ 关臂零漂移锚 + registry 字段面 ------------------------------------------


def test_off_arm_zero_drift() -> None:
    """off(显式注入缺省表):同停滞场景 8 轮零转移、停滞状态族保持缺省。"""
    st, ist, sess = _run_stagnation(DEFAULT_REGISTRY, rounds=8)
    assert ist.phase == 'locked'
    assert ist.last_event == ''
    assert ist.stagnate_cool == {}
    assert ist.stagnate_plane == 0
    assert ist.stagnate_windows_hit == 0
    assert ist.stagnate_gap_ref is None
    assert ist.stagnate_salvage is False
    assert ist.weak_placeholder == ''
    assert hoard_target_set(st, ist).mode == 'locked'


def test_registry_defaults_off() -> None:
    """registry 字段面:双开关默认关(第 1 态落码;开臂=翻默认+改写本锁)。"""
    assert DEFAULT_REGISTRY.intention_stagnation_arm_enabled is False
    assert DEFAULT_REGISTRY.p2_entry_weak_target_enabled is False
