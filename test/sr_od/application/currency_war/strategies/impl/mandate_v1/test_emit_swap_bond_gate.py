"""mandate 发出闸 bond_gate 分键写入断言(arm 分键新键族/拒绝侧闭集/
双轨域 arm='transition' 照旧)。

被测 = ``strategies/impl/mandate_v1/mandate.py`` ``emit_swap_redeploy``
分键写点与 :1495 发出闸路由(design 2026-10-26-swap-channel-unified
§2.3.1 arm 分键归宿;判据层计划形态另见 kernel 侧
test_select_swap_group_plan.py):

- **accept 侧新键族**:bond_gate_{branch}(branch ∈ tier/support/star/
  completion,首达分支)+ bond_gate_victim_tier_{tier}(值域 =
  一级/二级/名单末位);``cw4_m1p_arm_pending`` 载体保留;
- **拒绝侧分键闭集**:bond_gate_reject_nogain / conservation / novictim
  (3.5 预测表依赖闭集);
- **:1495 路由**:双轨域 arm='transition' 过 P79-3 放行门照旧(分键
  swap_arm_transition_trigger),转型域 bond_gate 臂不经 P79-3;
- **载荷迁移**:cw4_m1p_plan_pending 域事实键 = 'arm'(旧
  'trans_domain' 随域谓词退役);
- **3.2 阶段(同帧逐对原子序 + 复算统一门,design §2.5/§2.7)**:
  bond_gate 臂发射面逐对原子序(首对发射/中途失败停发/下帧续发/
  竞速占位重评)+ 发射帧复算统一门(门 1 现读通过即放行,分叉撤计划)
  + seam 门生产面写点(entry.emit prologue)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
    cw4_session,
)
from test.sr_od.application.currency_war.kernel.cw_deploy_logic.test_swap_bond_gate_domain import (
    _gate_ctx,
)

from sr_od.application.currency_war.kernel.cw_comps import Comp, get_comp
from sr_od.application.currency_war.kernel.cw_deploy_logic import SwapPlan
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    Unit,
    bench_entries_of,
    deployed_rows_of,
    max_units_of,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
    CwActionSellBenchParam,
    CwActionSellDeployedParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_GIL = '吉尔伽美什'
_RIN = '远坂凛'
_QING = '青雀'
_TING = '停云'
_YAO = '爻光'
_SBR = 'Saber'
_WALT = '瓦尔特'
_FUX = '符玄'
_HUO = '藿藿'
_JI = '开拓者·记忆'


def _locked_session(comp_name: str) -> tuple:
    """终局锁定 session 桩(target_comp 直种 + ist 分支① + seam 开闸 +
    计数器清零;装配源 = cw4_session/cw4_gs 容器域)。"""
    session = cw4_session(get_comp(comp_name))
    st = state_of(session)
    st.v3_intention = IntentionState(locked_comp=comp_name)
    st.cw4_m1p_seam_verified = True
    st.cw4_counters = {}
    return session, st


def _pair_session() -> tuple:
    """配方对锁 session 桩(p1_pair 分支② + pair 伪阵容;双轨域)。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        pair_target_comp,
    )
    session = cw4_session(pair_target_comp(('持续伤害', '希儿系')))
    st = state_of(session)
    st.v3_intention = IntentionState(p1_pair=('持续伤害', '希儿系'))
    st.cw4_m1p_seam_verified = True
    st.cw4_counters = {}
    return session, st


def _emit(session, st, *, bench: list[str], front: list[str],
          back: list[str], deploy_cap: int = 5, level: int = 5):
    """emit 直驱(A 锚帧形态;deployed = front+back 行域,bench = 占席;
    level 与 deploy_cap 联动定 max_units——板满分支按容器派生链现算)。"""
    gs = cw4_gs(session, deploy_cap=deploy_cap, level=level,
                bench=[cw4_bc(n) for n in bench],
                front_row=[Unit(char_id=n, star=1) for n in front],
                back_row=[Unit(char_id=n, star=1) for n in back])
    frame = mandate.MandateFrame(
        gold=30, level=5,
        bench=[cw4_bc(n) for n in bench],
        deployed=[Unit(char_id=n, star=1) for n in (*front, *back)],
        deploy_cap=deploy_cap, node_type=None, stop_flag=False,
        k_members=(), round_num=2)
    out = mandate.emit_swap_redeploy(frame, session, gs)
    return out, st.cw4_counters


def test_emit_bond_gate_accept_key_family() -> None:
    """accept 侧新键族写入断言(锚帧 A):组计划发射 → bond_gate_tier
    (首达分支)+ bond_gate_victim_tier_一级 + m1p_fired;arm 载体 =
    'bond_gate';不经 P79-3(redeploy_cost_gate_defer 零显影);载荷
    域事实键 = arm(旧 trans_domain 退役)。"""
    session, st = _locked_session('双王圣杯')
    out, counters = _emit(session, st, bench=[_SBR],
                          front=[_GIL, _RIN, _QING, _TING], back=[_YAO])
    assert counters.get('m1p_fired') == 1, '组计划发射'
    assert counters.get('bond_gate_tier') == 1, \
        f"accept 分键 bond_gate_tier(首达分支),实得 {counters}"
    assert counters.get('bond_gate_victim_tier_一级') == 1, \
        'victim 层来源分键(值域一级)'
    assert counters.get('redeploy_cost_gate_defer') is None, \
        'bond_gate 臂不经 P79-3(转型域废弃面,3.2 接线复算)'
    assert st.cw4_m1p_arm_pending == 'bond_gate', 'arm 载体保留'
    assert st.cw4_m1p_plan_pending.get('arm') == 'bond_gate', \
        '载荷域事实键 = arm'
    assert 'trans_domain' not in st.cw4_m1p_plan_pending, \
        '旧 trans_domain 键随域谓词退役'
    sells = [e.action for e in out]
    assert len(sells) == 1, '锚帧 = 单对组(1 换 1)'
    assert getattr(sells[0], 'deployed_idx', None) == 4, \
        'victim 容器下标对位(后排首槽 = 4 + 0)'


def test_emit_bond_gate_reject_key_closed_set() -> None:
    """拒绝侧分键闭集写入断言:二级持平帧四条分支全不中 → bond_gate_reject_
    nogain(+ m1p_plan_empty 照旧);arm 载体复位 None。"""
    session, st = _locked_session('双王圣杯')
    _out, counters = _emit(session, st, bench=[_JI],
                           front=[_GIL, _TING, _HUO, _WALT], back=[_FUX])
    assert counters.get('m1p_plan_empty') == 1, '计划空照旧计数'
    assert counters.get('bond_gate_reject_nogain') == 1, \
        f'拒绝侧闭集 nogain(四条分支全不中),实得 {counters}'
    assert st.cw4_m1p_arm_pending is None, '无发出帧 arm 载体复位'


def test_emit_pair_frame_transition_gate_unchanged() -> None:
    """:1495 路由双轨域照旧:pair 帧(分支②)完成品计划 arm='transition'
    照旧**经 P79-3 放行门**(现行三轴在容器 bench 形状下的现行为 =
    帧级 defer,与改前逐帧等价——本函数零触碰;P79-3 废弃/复算接线 =
    后续阶段,届时本断言随废弃面改写);bond_gate 键族零显影(域切分,
    design §2.3.1 发出闸路由申报)。"""
    session, st = _pair_session()
    _out, counters = _emit(session, st, bench=['黑天鹅'],
                           front=['卡芙卡', '希儿', '花火', '娜塔莎'],
                           back=[], deploy_cap=4, level=4)
    assert counters.get('redeploy_cost_gate_defer') == 1, \
        '双轨域 arm=transition 过 P79-3 门(现行三轴 verdict 照旧)'
    assert counters.get('m1p_fired') is None, 'defer 帧不发射(现行)'
    assert counters.get('bond_gate_tier') is None \
        and counters.get('bond_gate_victim_tier_一级') is None, \
        '双轨域不产 bond_gate 新键族(域切分)'
    assert st.cw4_m1p_arm_pending is None, 'defer 帧 arm 载体复位(现行)'


def test_emit_bond_gate_no_victim_reject_key() -> None:
    """拒绝侧闭集 novictim:全 2★ 板(victim 池空)且 bench 无义务成员
    (evolution 不武装 → star_guard 恒拒 2★ 生效)→ bond_gate_reject_
    novictim(无可行组零动作)。"""
    session2, st2 = _locked_session('双王圣杯')
    gs = cw4_gs(session2, deploy_cap=5, level=5,
                bench=[cw4_bc('椒丘')],
                front_row=[Unit(char_id=n, star=2)
                           for n in (_GIL, _RIN, _QING, _TING)],
                back_row=[Unit(char_id=_YAO, star=2)])
    frame = mandate.MandateFrame(
        gold=30, level=5, bench=[cw4_bc('椒丘')],
        deployed=[Unit(char_id=n, star=2)
                  for n in (_GIL, _RIN, _QING, _TING, _YAO)],
        deploy_cap=5, node_type=None, stop_flag=False,
        k_members=(), round_num=2)
    mandate.emit_swap_redeploy(frame, session2, gs)
    counters2 = st2.cw4_counters
    assert counters2.get('bond_gate_reject_novictim') == 1, \
        f'拒绝侧闭集 novictim(victim 池空),实得 {counters2}'
    assert counters2.get('m1p_plan_empty') == 1, '计划空照旧计数'


# ============================================================
# 3.2 同帧逐对原子序 + 复算统一门(design §2.5/§2.7)
# ============================================================

_C_COMP = Comp(name='C组生长测', factions=[], core_chars=[
    '瓦尔特', '杰帕德', '停云', '希儿', '符玄'],
    form_tiers={}, strength='A', form_difficulty='easy',
    early_power='中', required_deployed=('瓦尔特', '杰帕德'))

_ACT_SIG = ChannelSig(family='logic_action', actor='test_emit_swap',
                      mode='compute')


def _locked_c_session() -> tuple:
    """C 形态组生长 session 桩(自定义 Comp 直种 + ist 分支① + seam 开闸)。"""
    session = cw4_session(_C_COMP)
    st = state_of(session)
    st.v3_intention = IntentionState(locked_comp=_C_COMP.name)
    st.cw4_m1p_seam_verified = True
    st.cw4_counters = {}
    return session, st


def _seed_c_board(session, *, bench: tuple[str, ...] = ('瓦尔特', '杰帕德'),
                  board: tuple[str, ...] = ('停云', '希儿', '符玄'),
                  gold: int = 30):
    """C 形态板满帧容器种子(cap=3 板满;两对组 = C 形态基准面)。"""
    return cw4_gs(session, deploy_cap=3, level=3, gold=gold,
                  bench=[cw4_bc(n) for n in bench],
                  front_row=[Unit(char_id=n, star=1) for n in board])


def _frame_of(gs):
    """容器现读重建 MandateFrame(entry.emit 同款装配;决策帧 = 全量现读,
    零跨帧快照——组计划重算幂等的输入面)。"""
    front, back = deployed_rows_of(gs)
    return mandate.MandateFrame(
        gold=0, level=3,
        bench=bench_entries_of(gs),
        deployed=[d for d in (*front, *back) if d is not None],
        deploy_cap=max_units_of(gs), node_type=None, stop_flag=False,
        k_members=(), round_num=2)


def _drive_step5(session, gs) -> list:
    """生产部署面单决策调用(entry._step5_deploy;M5/M1/M1″ 同序,
    vacancy>0 时 M1 残余补部署先于 M1″ 换人分支)。"""
    return entry._step5_deploy(session, gs, _frame_of(gs),
                               levelup_actions=[])


def _apply(gs, act) -> None:
    """单动作逻辑态直写(动作上报函数族 = 生产单动作执行后的容器写口;
    决策环逻辑态续算的测试承载)。"""
    from sr_od.application.currency_war.kernel.cw_action_report.deploy_move import (
        report_action_deploy_move_param,
    )
    from sr_od.application.currency_war.kernel.cw_action_report.sell_deployed import (
        report_action_sell_deployed_param,
    )
    if isinstance(act, CwActionSellDeployedParam):
        out = report_action_sell_deployed_param(gs, act, _ACT_SIG)
    elif isinstance(act, CwActionDeployMoveParam):
        out = report_action_deploy_move_param(gs, act, _ACT_SIG)
    else:
        raise AssertionError(f'未支持的测试动作类型: {type(act).__name__}')
    assert out.applied, f'逻辑态直写被拒(陈旧提案?): {out.reason}'


def _board_names(gs) -> set[str]:
    front, back = deployed_rows_of(gs)
    return {d.char_id for d in (*front, *back)
            if d is not None and d.char_id}


def test_bond_gate_recalc_allowed_truth_values() -> None:
    """复算统一门判据本体真值(design §2.5;kernel ``swap_bond_gate_
    benefit`` 同一函数消费):锚组(爻光→Saber,圣杯 2→3 tier 激活)现读
    通过 → True;无收益组(键集/支撑/成型全持平形态)→ False;组形状
    破坏(up 下标越界 → 1:1 骨架失守)→ False(fail-closed)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        _bond_gate_recalc_allowed,
    )
    # 通过面:锚组(A 情形,tier 首达)
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=[_SBR], cap=5)
    assert _bond_gate_recalc_allowed(
        ctx, SwapPlan(sell_names=[_YAO], up_bench=[0], arm='bond_gate'))
    # 不通过面:键集/支撑/成型全持平横换(椒丘零标签,爻光零标签,
    # 支撑持平、非同名)——门 1 四条分支全不中
    ctx2 = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                     bench=['椒丘'], cap=5)
    assert not _bond_gate_recalc_allowed(
        ctx2, SwapPlan(sell_names=[_YAO], up_bench=[0], arm='bond_gate'))
    # 形状破坏面:sell/up 数不齐(2 卖 1 上 = 1:1 配对骨架失守)
    assert not _bond_gate_recalc_allowed(
        ctx, SwapPlan(sell_names=[_YAO, _TING], up_bench=[0], arm='bond_gate'))


def test_emit_bond_gate_recalc_withdraw_on_divergence(monkeypatch) -> None:
    """分叉撤计划面(design §2.5 语义钉死):计划快照与现读板态分叉
    (计划声称的收益组在现读板面上四条分支全不中)→ 复算门拦下,发射面
    计划撤(bond_gate_recalc_withdraw 分键 + 零动作 + pending 复位)。
    计划注入 = monkeypatch kernel 计划谓词返回陈旧提案(同帧架构下
    计划⇔发射同 ctx,分叉面只可经桩构造——本测试锁发射面的撤计划契约)。"""
    import sr_od.application.currency_war.kernel.cw_deploy_logic as cdl

    session, st = _locked_session('双王圣杯')
    stale = SwapPlan(sell_names=['椒丘'], up_bench=[0], arm='bond_gate',
                     bond_gate_branch='tier', victim_tier='一级')
    monkeypatch.setattr(cdl, 'select_swap_plan',
                        lambda *a, **k: stale, raising=True)
    out, counters = _emit(session, st, bench=['椒丘'],
                          front=[_GIL, _RIN, _QING, _TING], back=[_YAO])
    assert not any(isinstance(e.action, CwActionSellDeployedParam)
                   for e in out), '分叉撤计划 = 零动作(§2.5)'
    assert counters.get('bond_gate_recalc_withdraw') == 1, \
        f'撤计划分键,实得 {counters}'
    assert counters.get('m1p_fired') is None, '撤计划帧不计发射'
    assert st.cw4_m1p_plan_pending is None and \
        st.cw4_m1p_arm_pending is None, '撤计划帧 pending 复位'


def test_emit_bond_gate_head_pair_per_call() -> None:
    """同帧逐对原子序·发射面(design §2.7 执行形态):两对组计划帧的
    动作发出面只产**首对** SellDeployed(单动作循环 = bridge 取首项,
    发出面不得预发全组 sell 序 = 申报废止的「先卖后续帧续发」形态);
    载体载荷保留全组(sell/up 名单);复算统一门通过帧 withdraw 键零
    显影(§2.5 通过面)。"""
    session, st = _locked_c_session()
    gs = _seed_c_board(session)
    out = mandate.emit_swap_redeploy(_frame_of(gs), session, gs)
    sells = [e.action for e in out
             if isinstance(e.action, CwActionSellDeployedParam)]
    assert len(sells) == 1, \
        f'发射面只发首对 sell(逐对原子序),实得 {len(sells)} 件'
    front, _back = deployed_rows_of(gs)
    assert front[sells[0].deployed_idx] is not None and \
        front[sells[0].deployed_idx].char_id == '停云', \
        '首对 victim = 组贪心字典序首(victim 序一级停云)'
    payload = st.cw4_m1p_plan_pending
    assert payload['sell'] == ['停云', '希儿'], '载荷保留全组 sell 名单'
    assert payload['up'] == ['瓦尔特', '杰帕德'], '载荷保留全组 up 名单'
    assert payload['arm'] == 'bond_gate'
    counters = st.cw4_counters
    assert counters.get('bond_gate_completion') == 1, \
        'C 形态首达分支 = ④(累积组成型)'
    assert counters.get('bond_gate_recalc_withdraw') is None, \
        '复算门通过帧零撤计划(§2.5 通过面)'


def test_emit_bond_gate_pair_stall_on_unresolvable(monkeypatch) -> None:
    """中途失败语义·发射面(design §2.7「帧内停发后续对」):bond_gate
    臂首对 sell 解析失败(计划名与黑板失配)→ 帧内停发,零发射 +
    bond_gate_pair_stall 分键 + pending 复位;下帧重算续发由计划无跨帧
    状态承载。计划注入 = monkeypatch 陈旧提案(同帧架构下生产不可达,
    本测试锁 fail-closed 契约面)。"""
    import sr_od.application.currency_war.kernel.cw_deploy_logic as cdl

    session, st = _locked_c_session()
    gs = _seed_c_board(session)
    stale = SwapPlan(sell_names=['注册表外幻影件'], up_bench=[0],
                     arm='bond_gate', bond_gate_branch='support',
                     victim_tier='一级')
    monkeypatch.setattr(cdl, 'select_swap_plan',
                        lambda *a, **k: stale, raising=True)
    out = mandate.emit_swap_redeploy(_frame_of(gs), session, gs)
    assert not any(isinstance(e.action, CwActionSellDeployedParam)
                   for e in out), '首对失败 = 帧内停发(零发射)'
    assert st.cw4_counters.get('bond_gate_pair_stall') == 1, \
        f'中途失败分键,实得 {st.cw4_counters}'
    assert st.cw4_m1p_plan_pending is None, '停发帧 pending 复位'


def test_step5_pair_atomic_order_and_fresh_rederive() -> None:
    """同帧逐对原子序·生产部署面全序(决策环逻辑态续算形态,design §2.7
    执行形态):两对组经连续决策调用展开为 sell(停云) → deploy(瓦尔特)
    → sell(希儿) → deploy(杰帕德)——sell 仅在板满帧发射、空槽由 M1
    残余补部署先行落位换入,对间原子序结构性成立;下帧对**换后现读板面**
    重新现算(计划无跨帧状态),剩余对经内层 victim 回退可达(组贪心
    遍历序补钉,design §2.7「先换 victim(内层耗尽)」);终板 = 成型
    (required 全在板)——design §2.7「部分完成态…由下帧续发闭合」的全序。"""
    session, st = _locked_c_session()
    gs = _seed_c_board(session)
    fired: list[str] = []
    for _ in range(8):   # 防御上界(决策环不收敛 = 实现缺陷,不得静默)
        out = _drive_step5(session, gs)
        if not out:
            break
        act = out[0].action
        if isinstance(act, CwActionSellDeployedParam):
            front, _back = deployed_rows_of(gs)
            fired.append(f"sell:{front[act.deployed_idx].char_id}")
        elif isinstance(act, CwActionDeployMoveParam):
            from sr_od.application.currency_war.kernel.cw_exec_state import (
                bench_slot_unit,
            )
            from sr_od.application.currency_war.kernel.cw_game_state import (
                bench_view_slots_of,
            )
            _u = bench_slot_unit(bench_view_slots_of(gs)[act.bench_idx])
            fired.append(f"deploy:{getattr(_u, 'char_id', '')}")
        else:
            fired.append(f'其他动作 {type(act).__name__}(部署面被截断)')
            break
        _apply(gs, act)
    assert fired == ['sell:停云', 'deploy:瓦尔特',
                     'sell:希儿', 'deploy:杰帕德'], \
        f'逐对原子序全序(sell→deploy→sell→deploy),实得 {fired}'
    assert _board_names(gs) == {'瓦尔特', '杰帕德', '符玄'}, \
        '终板 = 全组落位(required 全在板成型)'
    counters = st.cw4_counters
    assert counters.get('m1p_fired') == 2, '两对各自计发射(帧级)'
    assert counters.get('bond_gate_completion') == 2, \
        '两对均 ④ 首达(第二对在 pair1 落位后按现读板态重评仍成型达标)'


def test_step5_race_occupied_board_rejudged() -> None:
    """竞速占位重评 + 下帧续发(design §2.7「下帧竞速申报」):换出空槽
    被同帧残余补部署先行占位(合成竞速结果 = 非名单件椒丘占位——M1
    裁判视野含域外件,竞速落点不保证组内)→ 下一决策调用按**占位后
    板面**重评:重算计划 = (椒丘→瓦尔特)② 支撑增,发射续发——发射对
    ≠ 陈旧计划的剩余对(希儿→杰帕德),组按现读重评,无强推陈旧对;
    其后逐对原子序续发至终局收益分支兑现(「部分完成态…由下帧续发闭合」)。"""
    session, st = _locked_c_session()
    gs = _seed_c_board(session, bench=("瓦尔特", "杰帕德", "椒丘"))
    out1 = _drive_step5(session, gs)
    act1 = out1[0].action
    assert isinstance(act1, CwActionSellDeployedParam)
    front, _back = deployed_rows_of(gs)
    assert front[act1.deployed_idx].char_id == '停云', '首对 victim(组序)'
    assert st.cw4_m1p_plan_pending['up'] == ['瓦尔特', '杰帕德'], \
        '原计划全组载荷'
    _apply(gs, act1)   # sell:停云 → vacancy=1
    # 竞速:残余补部署落椒丘(bench 槽表下标 2;非组内换入件)
    _apply(gs, CwActionDeployMoveParam(bench_idx=2, to_row='front',
                                       to_slot=1, faction=''))
    out2 = _drive_step5(session, gs)
    act2 = out2[0].action
    assert isinstance(act2, CwActionSellDeployedParam), \
        f'占位后板满帧重评仍成组(续发非停摆),实得 {out2}'
    front, _back = deployed_rows_of(gs)
    assert front[act2.deployed_idx].char_id == '椒丘', \
        '重评 victim = 占位件(现读板面一级序首)'
    assert st.cw4_m1p_plan_pending['up'] == ['瓦尔特'], \
        '重评换入 = 占位后板面裁判胜出者(非陈旧计划的杰帕德)'
    assert st.cw4_counters.get('bond_gate_support') == 1, \
        '重评组 ② 首达(支撑数严格增)'
    _apply(gs, act2)   # sell:椒丘 → vacancy=1,组剩余续发
    # 占位件椒丘入板后即成重评组的一级 victim:先被换出(② 支撑增),
    # 原剩余对(希儿→杰帕德)按换后板面重评仍 ④ 达成 → 逐对原子序续发
    # 至组闭合(design §2.7「部分完成态…由下帧续发闭合」全序)。
    fired: list[str] = ['sell:停云', 'sell:椒丘']
    for _ in range(6):   # 防御上界(决策环不收敛 = 实现缺陷,不得静默)
        out = _drive_step5(session, gs)
        if not out:
            break
        act = out[0].action
        if isinstance(act, CwActionSellDeployedParam):
            front, _back = deployed_rows_of(gs)
            fired.append(f"sell:{front[act.deployed_idx].char_id}")
        elif isinstance(act, CwActionDeployMoveParam):
            from sr_od.application.currency_war.kernel.cw_exec_state import (
                bench_slot_unit,
            )
            from sr_od.application.currency_war.kernel.cw_game_state import (
                bench_view_slots_of,
            )
            _u = bench_slot_unit(bench_view_slots_of(gs)[act.bench_idx])
            fired.append(f"deploy:{getattr(_u, 'char_id', '')}")
        else:
            fired.append(f'其他动作 {type(act).__name__}(部署面被截断)')
            break
        _apply(gs, act)
    assert fired == ['sell:停云', 'sell:椒丘', 'deploy:瓦尔特',
                     'sell:希儿', 'deploy:杰帕德'], \
        f'占位重评后续发至组闭合,实得 {fired}'
    assert _board_names(gs) == {'瓦尔特', '杰帕德', '符玄'}, \
        '终板 = 全组落位(required 全在板成型)'


def test_emit_bond_gate_bench_exhausted_novictim_no_forcing() -> None:
    """组剩余不可行即自然停(design §2.7「无强推」):换入候选耗尽
    (bench 空,组内 up 已被竞速占位消耗)→ 重算零动作
    (bond_gate_reject_novictim),板面剩余 victim 不被强推卖出。"""
    session, st = _locked_c_session()
    # 竞速占位后的板面:杰帕德已入板,bench 耗尽,希儿/符玄留在板
    gs = _seed_c_board(session, bench=(),
                       board=('杰帕德', '希儿', '符玄'))
    out = mandate.emit_swap_redeploy(_frame_of(gs), session, gs)
    assert not any(isinstance(e.action, CwActionSellDeployedParam)
                   for e in out), '无可行组 = 零动作(无强推)'
    assert st.cw4_counters.get('bond_gate_reject_novictim') == 1, \
        f'拒绝侧闭集 novictim(换入候选耗尽),实得 {st.cw4_counters}'


def test_emit_bond_gate_label_victim_pair_form_p60_observer() -> None:
    """义务集豁免×P60 换手病理交互观测锚(design 2026-10-26-swap-channel-
    unified §2.8):二级标签件(停云,能量标签,非名单)换血发射形态 =
    **换血伴随同帧换入**——发射面只产对内首对 SellDeployed、零
    SellBenchParam(无单独卖出标签件的发射形态;bench 侧标签件换金面
    已由装配 A 身份段封死,来金侧单帧锚见 test_sell_candidates 六通道
    逐一点名),载荷保留对骨架(sell=[停云] ↔ up=[Saber] 1:1);观测键
    = bond_gate_tier(accept 首达分支)+ bond_gate_victim_tier_二级
    (换人对计数,3.5 预测表逐帧对照可检出异常换手频次);组级支撑数
    净非降由配对骨架承保(§2.8 段一)。"""
    session, st = _locked_session('双王圣杯')
    bench = [_SBR]
    front = [_GIL, _RIN, _HUO]
    back = [_FUX, _TING]
    gs = cw4_gs(session, deploy_cap=5, level=5,
                bench=[cw4_bc(n) for n in bench],
                front_row=[Unit(char_id=n, star=1) for n in front],
                back_row=[Unit(char_id=n, star=1) for n in back])
    frame = mandate.MandateFrame(
        gold=30, level=5, bench=[cw4_bc(n) for n in bench],
        deployed=[Unit(char_id=n, star=1) for n in (*front, *back)],
        deploy_cap=5, node_type=None, stop_flag=False,
        k_members=(), round_num=2)
    out = mandate.emit_swap_redeploy(frame, session, gs)
    sells = [e.action for e in out
             if isinstance(e.action, CwActionSellDeployedParam)]
    assert len(sells) == 1 and not any(
        isinstance(e.action, CwActionSellBenchParam) for e in out), \
        '发射形态 = 仅对内首对换人卖出,零 bench 卖出' \
        '(标签件无单独卖出形态,P60 换手面无金损耗循环入口)'
    payload = st.cw4_m1p_plan_pending
    assert payload['sell'] == [_TING] and payload['up'] == [_SBR], \
        f'对骨架载荷(sell↔up 1:1,换血伴随换入;victim = 二级标签件),实得 {payload}'
    counters = st.cw4_counters
    assert counters.get('bond_gate_tier') == 1, \
        f'accept 首达分支分键(圣杯 2→3 二阶激活),实得 {counters}'
    assert counters.get('bond_gate_victim_tier_二级') == 1, \
        'victim 层来源分键(换人对计数观测面)'


def test_entry_emit_writes_seam_flag() -> None:
    """seam 门生产面写点(entry.emit prologue;3.2 补接线):fresh state
    经生产决策入口一帧后 cw4_m1p_seam_verified = True(值源 =
    M1P_SEAM_VERIFIED 常量,两面同值同源;回滚 = 常量写 False 两面同关)。
    此前写点残留测试面 prologue,生产 entry 面恒缺省 False → 非空换人
    计划恒被 m1p_input_seam_pending 拦(C1 局 g_20261026_203023 遥测
    实锤 m1p_input_seam_pending=1 ∧ m1p_fired=0)。"""
    session = cw4_session()
    gs = cw4_gs(session, deploy_cap=3, level=3, gold=30,
                bench=[cw4_bc('椒丘')],
                front_row=[Unit(char_id=n, star=1)
                           for n in ('停云', '希儿', '符玄')])
    gs.observe(gs.overflow_warning, True, evidence='sim:synthesized',
               sig=ChannelSig(family='obs', actor='cw4_seed',
                              mode='synthesized'))
    st = state_of(session)
    assert st.cw4_m1p_seam_verified is False, 'fresh state 缺省关(fail-closed)'
    entry.emit(session, None)
    assert st.cw4_m1p_seam_verified is True, \
        '生产面 prologue 写点(seam 开闸在生产面生效)'
