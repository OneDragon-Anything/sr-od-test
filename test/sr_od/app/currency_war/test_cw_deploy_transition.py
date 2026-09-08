# 部署面让渡(T-127 R2)单帧锁——锁线域装配级键集收窄(读法 D)/
# 转型域资格族统一(基座臂封堵)/ P79-3 执行条件发射门 / P79-4 让渡序 /
# 分键闭集扩展 / 病灶局帧复演。
# 语义出处:ADR-0590(docs/develop/currency_war/decisions/
# 0590-deploy-yield-transition.md)+ T-127 方案 v3.1 §2.3/§3.1/§3.2/§6
# (.debug/temp/currency_war/t127_deploy_trigger/方案.md)+ math_proofs
# P79(R1 已入册)。锁的存在性纪律:每条锁 docstring 引出处;守卫均为
# 「移除即红」属性。
from types import SimpleNamespace as _NS

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SwapPlanContext,
    locked_redeploy_target_keys,
    select_swap_plan,
    swap_sell_exclusion_reason,
    swap_yield_contribution,
)
from sr_od.application.currency_war.kernel.cw_launch_admission import (
    offtarget_sell_allowed,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ===== 病灶局 g_20260907_214130 r7 FORM 帧真值(档案申报值)=====
# 帧可读性申报(T-127 方案 §6.2/三轮 N3):locked+fp 仅 r7 FORM 帧
# (22:21:34-54)在档、deploy_cap=8 在 r6 帧在档(均无单一在档帧)——
# 锁构造按「r7 FORM 帧 deployed/board/bench + r6 帧 level」跨帧重建。
# 断言依据 = 本文件内联合成帧(测试输入密闭,README 纪律 #19),数值
# 锚 = 档案申报值。
_LESION_DEPLOYED = [('火花', 1), ('丹恒·饮月', 2), ('希儿', 1),
                    ('艾丝妲', 2), ('三月七', 2), ('忘归人', 1),
                    ('缇宝', 1), ('绯英', 1)]
_LESION_BOARD = {'星间旅人': 1, '战技点': 7, '欢愉': 2, '仙舟': 2,
                 '列车同行': 2, '贝洛伯格': 1, '量子同频': 2, '银河学者': 1,
                 '持续伤害': 1, '护盾': 1, '击破': 1, '昼之半神': 1,
                 '群攻': 1}
_LESION_BENCH = ['罗刹', '真理医生', '银狼LV.999', '希儿', '丹恒·饮月']
_LESION_LEVEL = 8          # r6 帧 cap 真值(lv8 → max_units 8)
_NARROWED_KEYS = frozenset({'欢愉', '星间旅人', '量子同频', '战技点'})
_MEMBERSHIP = frozenset({'绯英', '瓦尔特', '爻光', '开拓者·欢愉', '符玄',
                         '火花', '银狼LV.999', '罗刹', '真理医生', '银枝'})


def _bc(name: str, slot: int = 1, star: int = 1) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions[0] if ch.factions else '?'))


def _lesion_deployed() -> list[BenchChar]:
    return [_bc(n, i + 1, s) for i, (n, s) in enumerate(_LESION_DEPLOYED)]


def _lesion_bench() -> list[BenchChar]:
    return [_bc(n, i + 1) for i, n in enumerate(_LESION_BENCH)]


def _comp() -> _NS:
    """绯英欢愉 comp 视图(注册表/comp 库同值;all_factions = 核心∪弹性,
    ADR-0152 口径;form_tiers 单一源 = cw_comps 注册表)。"""
    return _NS(
        factions=('欢愉', '星间旅人'),
        all_factions=frozenset({'欢愉', '星间旅人', '能量', '仙舟', '治疗',
                                '量子同频', '战技点'}),
        core_chars=('绯英', '瓦尔特', '爻光', '开拓者·欢愉', '符玄'),
        form_tiers={'欢愉': 4, '星间旅人': 2},
        shared_chars=(), substitute_plan=None)


def _lesion_ctx(*, bench: list[BenchChar] | None = None,
                ) -> SwapPlanContext:
    """病灶局帧手装 ctx(键集 = 收窄产物,装配级收窄另有装配面锁)。"""
    return SwapPlanContext(
        target_factions=_NARROWED_KEYS,
        target_cores=frozenset({'绯英', '瓦尔特', '爻光', '开拓者·欢愉',
                                '符玄'}),
        fw_carry=frozenset(), locked_factions=frozenset(),
        protect_names=frozenset(), membership=_MEMBERSHIP,
        fresh_buys=frozenset(), board=dict(_LESION_BOARD),
        deployed=_lesion_deployed(),
        bench=bench if bench is not None else _lesion_bench(),
        cap=_LESION_LEVEL, fp=0.5, locked=True, board_full=True)


# ============ 病灶局帧复演(方案 §6.2;victim=忘归人 / up=罗刹)============

def test_lesion_frame_replay_fires_victim_yuanguiren(monkeypatch) -> None:
    """病灶局帧复演锁(ADR-0590 决策1/2;T-127 方案 §6.1/§6.2):锁线转型
    域 + 收窄键集帧 ⇒ M1″ 发射且 victim = 忘归人(让渡序全局首件,非
    「合格集内首件」)、up = 罗刹(锁线档关键件到席即上,P79-1/2)、
    arm='transition'。红证双向:改前代码本帧 victim 全员被拒
    (4×target_keep+2×buy_membership+star_guard+engines_guard)计划空 =
    病灶本体;收窄回退则忘归人复被 target_keep 锁死 = 本锁红。
    分键闭集扩展同锁显影(buy_membership/target_keep 进入逐件拒因
    分键,T-127 方案 §2.3——旧闭集下「臂武装而计划空」不可归因)。"""
    import sr_od.application.currency_war.kernel.cw_intention as _int_mod
    import sr_od.application.currency_war.strategies.impl.mandate_v1.mandate as _mandate_mod
    from sr_od.application.currency_war.kernel.cw_state import GameState
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        MandateFrame,
        run_mandate,
    )
    monkeypatch.setattr(_mandate_mod, 'M1P_SEAM_VERIFIED', True)
    monkeypatch.setattr(_int_mod, 'committed_from',
                        lambda session, state=None: True)
    monkeypatch.setattr(_int_mod, 'locked_buy_membership',
                        lambda ist: _MEMBERSHIP)
    sess = _NS(last_owned_equips=None)
    _st = state_of(sess)
    _st.cw4_counters = {}
    _st.v3_intention = _NS(locked_comp='绯英欢愉', p1_pair=(),
                           phase='locked', transition_pair=())
    _st.target_comp = _comp()
    _st.transition_framework = ''
    dep, bench = _lesion_deployed(), _lesion_bench()
    st = GameState(gold=60, level=_LESION_LEVEL, plane=2, round_num=7,
                   board=dict(_LESION_BOARD), deployed=list(dep),
                   bench=list(bench))
    frame = MandateFrame(gold=60, level=_LESION_LEVEL, bench=list(bench),
                         deployed=list(dep), deploy_cap=_LESION_LEVEL,
                         node_type=None, stop_flag=False, k_members=(),
                         round_num=7)
    out = run_mandate(frame, sess, state=st)
    fired = [e for e in out if e.action.__class__.__name__ == 'RunDeploy'
             and e.reason == 'm1_swap_redeploy']
    assert len(fired) == 1
    c = state_of(sess).cw4_counters
    assert c.get('m1p_fired') == 1
    assert c.get('swap_arm_transition_trigger') == 1
    assert c.get('redeploy_transition_victim_忘归人') == 1   # §2.3 新分键
    # 逐件拒因闭集扩展显影(T-127 §2.3):义务集拒因与弹性保护拒因可归因
    assert c.get('buy_membership') == 1      # 火花/绯英
    assert c.get('target_keep') == 1         # 缇宝(量子同频达成留保护域)
    assert c.get('star_guard') == 1          # 艾丝妲(2★,P41② fail-closed)
    assert c.get('engines_guard') == 1       # 三月七(列车同行 2→1)
    assert state_of(sess).cw4_m1p_arm_pending == 'transition'


def test_lesion_frame_plan_shape_and_yield_order_calibration() -> None:
    """计划形态 + P79-4 让渡序校准值锁(ADR-0590 决策5;T-127 方案 §3.2
    三轮 R3 重推值,注册表直调复算):victim = 忘归人(贡献 0 唯一 1★)、
    up = 罗刹;贡献校准 忘归人 0/艾丝妲 0/三月七 1/希儿 2/缇宝 2/饮月 2
    (度量 = 「target 视图 ∪ SWAP_GUARD_SYSTEMS」并集 achieved 差分,
    计数源 = deployed_bond_counts)。数值断言钉注册表口径:星间旅人
    registered = 2(火花+绯英)≠ board 面板 1(欠计,二轮 X7④/§7#12)。"""
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        deployed_bond_counts,
    )
    dep = _lesion_deployed()
    names = {d.char_id for d in dep}
    counts = deployed_bond_counts(names)
    assert counts['星间旅人'] == 2, '注册表口径(非面板 1)'
    ctx = _lesion_ctx()
    plan = select_swap_plan(ctx)
    assert plan.nonempty
    assert plan.sell_names == ['忘归人']
    assert {_lesion_bench()[i].char_id for i in plan.up_bench} == {'罗刹'}
    assert plan.arm == 'transition'
    assert plan.reasons.get('艾丝妲') == 'star_guard'
    assert plan.reasons.get('三月七') == 'engines_guard'
    for name, want in (('忘归人', 0), ('艾丝妲', 0), ('三月七', 1),
                       ('希儿', 2), ('缇宝', 2), ('丹恒·饮月', 2)):
        got = swap_yield_contribution(_NARROWED_KEYS, names, name)
        assert got == want, (name, got, want)


def test_formed_frame_released_flex_member_still_target_keep() -> None:
    """锁线成型帧收窄辖域锁(落地审 F1/F1-a 修复;ADR-0590 决策 1 修订):
    装配收窄辖域钉锁线**转型域**——锁线∧fp≥1.00∧板满帧(fenced_on=True
    成型臂帧)键集回全量,纯弹性未达成件(藿藿 2★,bonds 全落仙舟/治疗/
    能量)仍 target_keep(offtarget-② 保护,不经成型臂无守卫卖出——
    收窄外溢时 2★ 绕过 star_guard/P41② 被成型臂卖出 = F1 实证,本锁红)。
    八件全保护构造:非成员件 bonds 均 ∩ 全量键非空 ⇒ 计划空。
    G1 准入预估(all_factions 口径)与本帧计划体同键集,F1-a 分叉消解。
    转型域收窄存活性由病灶局锁(test_assembly_narrows…/病灶复演)承载。"""
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        assemble_swap_plan_inputs,
    )
    from sr_od.application.currency_war.kernel.cw_state import GameState
    comp = _comp()
    sess = _NS()
    _st = state_of(sess)
    _st.target_comp = comp
    _st.v3_intention = _NS(locked_comp='绯英欢愉')
    _st.transition_framework = ''
    dep = [_bc('藿藿', 1, star=2), _bc('绯英', 2), _bc('火花', 3),
           _bc('爻光', 4), _bc('符玄', 5), _bc('花火', 6),
           _bc('青雀', 7), _bc('停云', 8)]
    st = GameState(gold=60, level=_LESION_LEVEL, plane=2, round_num=7,
                   board={'欢愉': 4, '星间旅人': 2},   # fp = 1.00 成型帧
                   deployed=list(dep), bench=[_bc('罗刹', 1)])
    ctx = assemble_swap_plan_inputs(sess, state=st, deployed=list(dep),
                                    bench=[_bc('罗刹', 1)],
                                    cap=_LESION_LEVEL)
    assert ctx is not None
    assert ctx.locked and ctx.board_full and ctx.fenced_on   # F1 帧类确认
    assert ctx.fp == pytest.approx(1.0)
    assert ctx.target_factions == frozenset(comp.all_factions), \
        '成型帧键集必须回全量(收窄辖域 = 转型域)'
    assert swap_sell_exclusion_reason('藿藿', ctx) == 'target_keep'
    plan = select_swap_plan(ctx)
    assert not plan.nonempty, plan
    assert '藿藿' not in plan.sell_names
    assert plan.reasons.get('藿藿') == 'target_keep'


def test_assembly_narrows_keys_and_fp_panel_basis(monkeypatch) -> None:
    """装配级键集收窄单一源锁(ADR-0590 决策1;读法 D):生产装配函数对
    病灶局帧产出收窄键集(核心 {欢愉,星间旅人} ∪ 已达成档承载弹性
    {量子同频,战技点};剔除未达成 flex 仙舟/治疗/能量——仙舟 2<3 计数
    源 = deployed_bond_counts 注册表口径)+ fp = 0.5(面板口径与档案
    精确互证,读法 b);未锁帧同输入键集逐位同旧(all_factions 全量,
    零行为差)。锁定线布尔 = ist.locked_comp 非空(17 号稿 B-1 单源)。"""
    from sr_od.application.currency_war.kernel.cw_comps import form_progress
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        assemble_swap_plan_inputs,
    )
    from sr_od.application.currency_war.kernel.cw_state import GameState
    comp = _comp()
    sess = _NS()
    _st = state_of(sess)
    _st.target_comp = comp
    _st.v3_intention = _NS(locked_comp='绯英欢愉')
    _st.transition_framework = ''
    st = GameState(gold=60, level=_LESION_LEVEL, plane=2, round_num=7,
                   board=dict(_LESION_BOARD), deployed=_lesion_deployed(),
                   bench=_lesion_bench())
    assert abs(form_progress(comp, st) - 0.5) < 1e-9   # 面板口径互证
    ctx = assemble_swap_plan_inputs(sess, state=st,
                                    deployed=_lesion_deployed(),
                                    bench=_lesion_bench(),
                                    cap=_LESION_LEVEL)
    assert ctx is not None and ctx.locked and ctx.board_full
    assert ctx.target_factions == _NARROWED_KEYS, ctx.target_factions
    assert ctx.fp == pytest.approx(0.5)
    # 装配产物与收窄函数直调同值(装配层单一源,禁第二份收窄)
    names = {d.char_id for d in _lesion_deployed()}
    assert locked_redeploy_target_keys(
        frozenset(comp.all_factions), frozenset(comp.factions),
        names) == _NARROWED_KEYS
    # 未锁域零差:同帧 locked=False → 键集全量
    sess_u = _NS()
    _stu = state_of(sess_u)
    _stu.target_comp = comp
    _stu.v3_intention = _NS(locked_comp='')
    _stu.transition_framework = ''
    ctx_u = assemble_swap_plan_inputs(sess_u, state=st,
                                      deployed=_lesion_deployed(),
                                      bench=_lesion_bench(),
                                      cap=_LESION_LEVEL)
    assert ctx_u is not None and not ctx_u.locked
    assert ctx_u.target_factions == frozenset(comp.all_factions)


# ============ 五消费位单一源(方案 §7 #9 blast radius 行为锁)============

def test_five_consumption_sites_share_narrowed_keys() -> None:
    """五消费位单一源锁(ADR-0590 决策1;T-127 方案 §3.1 行 #4 规格):
    收窄键集装配一次,五个消费位同吃同值——①offtarget-② target 早拒:
    忘归人(唯一键 = 未达成仙舟)释放进资格族(全量键下为 target_keep);
    ②:895 宽口径归因:饮月(战技点达成留保护域)拒因 target_keep;
    ③上行 is_tgt + _bench_is_target + post_sell_offline 底线:bench 仅
    藿藿(仙舟件,收窄下非 target 视图)⇒ 卖忘归人后上序无 target 视图
    ⇒ post_sell_offline 计划空(全量键下藿藿为 target 视图会误发射);
    ④保护面基准:希儿/缇宝(量子同频达成)仍 target_keep。任一消费位
    内联第二份收窄/回退全量键,本锁对应断言红。"""
    ctx = _lesion_ctx()
    # ①+②:逐件判定(键面注:板/备同名 post_sell_held 覆写为既知键面
    # 限制,本锁用判定函数直读规避覆盖)
    assert swap_sell_exclusion_reason('忘归人', ctx) == ''
    assert swap_sell_exclusion_reason('丹恒·饮月', ctx) == 'target_keep'
    assert swap_sell_exclusion_reason('希儿', ctx) == 'target_keep'
    assert swap_sell_exclusion_reason('缇宝', ctx) == 'target_keep'
    # 义务/保护拒因锁线域不松绑(方案 §6.1):fresh_buy 与 protect_names
    # 在资格族之前照旧排除(成员类轴/收窄不豁免义务集与保护域)
    import dataclasses
    ctx_fresh = dataclasses.replace(ctx, fresh_buys=frozenset({'忘归人'}))
    assert swap_sell_exclusion_reason('忘归人', ctx_fresh) == 'fresh_buy'
    ctx_prot = dataclasses.replace(ctx, protect_names=frozenset({'忘归人'}))
    assert swap_sell_exclusion_reason('忘归人', ctx_prot) == 'target_keep'
    assert swap_sell_exclusion_reason('火花', ctx) == 'buy_membership'
    # ③:上行视图面 —— is_tgt/_bench_is_target/post_sell_offline 同键集
    plan = select_swap_plan(_lesion_ctx(bench=[_bc('藿藿', 1)]))
    assert not plan.nonempty
    assert plan.reasons.get('忘归人') == 'post_sell_offline', plan.reasons


def test_unlocked_frame_all_gates_bitwise_unchanged() -> None:
    """未锁域零外溢锁(ADR-0590 决策2;T-127 方案 §6.1):同板面
    locked=False ⇒ 键集全量、W209 熔断全域保持(fenced victim 全拒
    fenced_arm_closed)、非 fenced off-target 件走基座臂旧语义——
    封堵与收窄不外溢未锁帧(ADR-0530/0534 语义照旧)。"""
    ctx = SwapPlanContext(
        target_factions=frozenset({'欢愉', '星间旅人', '能量', '仙舟',
                                   '治疗', '量子同频', '战技点'}),
        target_cores=frozenset({'绯英', '瓦尔特', '爻光', '开拓者·欢愉',
                                '符玄'}),
        fw_carry=frozenset(), locked_factions=frozenset(),
        protect_names=frozenset(), membership=_MEMBERSHIP,
        fresh_buys=frozenset(), board=dict(_LESION_BOARD),
        deployed=_lesion_deployed(), bench=_lesion_bench(),
        cap=_LESION_LEVEL, fp=0.5, locked=False, board_full=True)
    # 全量键下忘归人 = target_keep(方案 §0.3 逐件表旧拒因,零漂移证明)
    assert swap_sell_exclusion_reason('忘归人', ctx) == 'target_keep'
    assert swap_sell_exclusion_reason('希儿', ctx) == 'target_keep'
    plan = select_swap_plan(ctx)
    assert not plan.nonempty
    assert plan.reasons.get('艾丝妲') == 'fenced_arm_closed'
    assert plan.reasons.get('三月七') == 'fenced_arm_closed'


# ============ 希儿形态红对(四条件;方案 §6.1 三轮 R2 重钉)============

def _seele_leak_ctx(*, deployed: list[BenchChar],
                    bench: list[BenchChar]) -> SwapPlanContext:
    """希儿泄漏帧 ctx(键集剔量子同频 = 条件①;板满/转型域同病灶帧)。"""
    return SwapPlanContext(
        target_factions=frozenset({'欢愉', '星间旅人', '战技点'}),
        target_cores=frozenset({'绯英', '瓦尔特', '爻光', '开拓者·欢愉',
                                '符玄'}),
        fw_carry=frozenset(), locked_factions=frozenset(),
        protect_names=frozenset(), membership=_MEMBERSHIP,
        fresh_buys=frozenset(), board={}, deployed=deployed, bench=bench,
        cap=6, fp=0.5, locked=True, board_full=True)


def test_seele_leak_red_pair_conservation_gate_blocks() -> None:
    """希儿形态红对·贝洛伯格成形变体(ADR-0590 决策2;T-127 方案 §6.1
    四条件:①量子同频未达成→剔出收窄键集 ②贝洛伯格 ≥2 使希儿系仍成形
    ④无更低贡献竞争件——竞争件全为义务集成员或 2★ star_guard 持有):
    泄漏向断言 = 基座臂放行谓词对希儿为真(键集剔量子同频后希儿非
    fenced 非 target,读法 D 释放面);封堵向断言 = 单一判定函数拒因
    engines_guard(希儿系 achieved 1→0,守恒门资格保护)且计划不选中
    希儿(计划空 = 一换止血形态)。封堵移除(行 #5 回退)⇒ 希儿经
    基座臂可卖且 arm='base' 只查 up2 ⇒ 本锁红。"""
    deployed = [_bc('希儿', 1), _bc('杰帕德', 2), _bc('绯英', 3),
                _bc('火花', 4), _bc('艾丝妲', 5, star=2),
                _bc('三月七', 6, star=2)]
    bench = [_bc('罗刹', 1), _bc('希儿', 2)]
    ctx = _seele_leak_ctx(deployed=deployed, bench=bench)
    # 泄漏向:收窄后基座臂谓词放行(条件①成立 = 收窄真实剔除保护键)
    assert offtarget_sell_allowed(
        '希儿', {'贝洛伯格', '量子同频'}, set(ctx.target_factions),
        set(ctx.target_cores), fenced_offline_sellable=False,
        protect_names=frozenset()) is True
    # 封堵向:希儿系成形(希儿+贝洛伯格 2)⇒ 守恒门拒,arm 恒 transition
    assert swap_sell_exclusion_reason('希儿', ctx) == 'engines_guard'
    plan = select_swap_plan(ctx)
    assert '希儿' not in plan.sell_names
    assert not plan.nonempty   # 竞争件全被义务集/星级/守恒门持有
    assert plan.reasons.get('杰帕德') == 'engines_guard'


def test_seele_leak_red_pair_merge_material_variant() -> None:
    """希儿形态红对·素材对变体(条件③同名同星素材对在场;ADR-0534 §2
    合成素材守卫经资格族适用于非 fenced 释放件 = 行 #5 统一资格族):
    希儿系不成形(量子同频 1/贝洛伯格 1,守恒门 Δ0)⇒ 守恒门不拦,
    merge_material_guard 拒(含自身全场域同名同星计数 = 2 未完态)——
    「排序靠后不选中」与「资格被拦不选中」两因由经拒因键分异,禁混同。"""
    deployed = [_bc('希儿', 1), _bc('爻光', 2), _bc('绯英', 3),
                _bc('火花', 4), _bc('艾丝妲', 5, star=2),
                _bc('三月七', 6, star=2)]
    bench = [_bc('罗刹', 1), _bc('希儿', 2)]
    ctx = _seele_leak_ctx(deployed=deployed, bench=bench)
    assert swap_sell_exclusion_reason('希儿', ctx) == 'merge_material_guard'
    plan = select_swap_plan(ctx)
    assert '希儿' not in plan.sell_names


# 「资格门不被 f≥2 收益侧豁免」(方案 §2.3 辖域)事实由病灶复演锁与计划
# 形态锁自持:前者经 run_mandate 计数器分键(star_guard/engines_guard),
# 后者经 plan.reasons 逐件断言同两件同两拒因——独立锁省去,防双点维护。


# ============ P79-3 执行条件发射门(ADR-0590 决策4/6)============

_GATE_COMP = _NS(
    factions=('欢愉',),
    all_factions=frozenset({'欢愉', '星间旅人'}),
    core_chars=('绯英',), form_tiers={'欢愉': 4, '星间旅人': 2},
    shared_chars=(), substitute_plan=None)


def _gate_deployed() -> list[BenchChar]:
    """门测试板面六件(注册表直核,收窄键 = {欢愉}:弹性星间旅人板面
    计数 0 未达成剔除;victim 候选 = 4 张 1★ 零贡献释放件(仙舟计 2,
    离场 2→1 未达 tier1,守恒门 Δ0),2★ 两张被 star_guard 持有——
    资格门轴与成员类轴分离,帧内不混因)。"""
    return [_bc('忘归人', 1), _bc('青雀', 2), _bc('艾丝妲', 3, star=2),
            _bc('三月七', 4, star=2), _bc('黑塔', 5), _bc('娜塔莎', 6)]


def _run_gate_frame(monkeypatch, *, joy_panel: int, enabled: bool):
    """执行条件门帧驱动:locked 转型帧 + 压席成员银狼LV.999(欢愉
    bond = target 视图 up 候选),面板欢愉档 = joy_panel 控制成员类轴
    (部署银狼后 欢愉 joy_panel→joy_panel+1:panel=4 已达 form_tiers
    下限 ⇒ 非档关键件;panel=3 ⇒ 越档 = 档关键件)。membership 桩 =
    {'银狼LV.999'}(仅发射门压席面消费;deployed 无成员,victim 资格
    面不受影响)。返回 (发射列表, counters, session)。"""
    import sr_od.application.currency_war.kernel.cw_intention as _int_mod
    import sr_od.application.currency_war.strategies.impl.mandate_v1.mandate as _mandate_mod
    from sr_od.application.currency_war.kernel.cw_state import GameState
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        MandateFrame,
        run_mandate,
    )
    monkeypatch.setattr(_mandate_mod, 'M1P_SEAM_VERIFIED', True)
    monkeypatch.setattr(_mandate_mod, 'REDEPLOY_TRANSITION_ENABLED', enabled)
    monkeypatch.setattr(_int_mod, 'committed_from',
                        lambda session, state=None: True)
    monkeypatch.setattr(_int_mod, 'locked_buy_membership',
                        lambda ist: frozenset({'银狼LV.999'}))
    sess = _NS(last_owned_equips=None)
    _st = state_of(sess)
    _st.cw4_counters = {}
    _st.v3_intention = _NS(locked_comp='绯英欢愉', p1_pair=(),
                           phase='locked', transition_pair=())
    _st.target_comp = _GATE_COMP
    _st.transition_framework = ''
    dep, bench = _gate_deployed(), [_bc('银狼LV.999', 1, star=2)]
    board = {'欢愉': joy_panel, '星间旅人': 1}
    st = GameState(gold=0, level=6, plane=1, round_num=2, board=dict(board),
                   deployed=list(dep), bench=list(bench))
    frame = MandateFrame(gold=0, level=6, bench=list(bench),
                         deployed=list(dep), deploy_cap=6, node_type=None,
                         stop_flag=False, k_members=(), round_num=2)
    out = run_mandate(frame, sess, state=st)
    return out, state_of(sess).cw4_counters, sess


def test_emission_gate_defers_noncritical_member(monkeypatch) -> None:
    """执行条件门 defer 锁(ADR-0590 决策4;P79-3 落码 = 发射门非排序
    理由):保守形态(缺省)下压席成员非档关键件(面板 欢愉 4 已达
    form_tiers 下限,部署银狼不推 form_progress)⇒ 计划非空但帧级
    defer,分键 redeploy_cost_gate_defer 显影、不发射、pending 恒
    None——「该不该这帧换」与逐件资格拒因分列禁混桶,defer 不冒名
    m1p_plan_empty。"""
    out, c, sess = _run_gate_frame(monkeypatch, joy_panel=4, enabled=False)
    assert c.get('redeploy_cost_gate_defer') == 1
    assert 'm1p_fired' not in c
    assert 'm1p_plan_empty' not in c
    assert state_of(sess).cw4_m1p_arm_pending is None
    assert not [e for e in out
                if e.action.__class__.__name__ == 'RunDeploy']


def test_emission_gate_full_form_opens_and_victim_keyed(
        monkeypatch) -> None:
    """全量形态对照锁(ADR-0590 决策6;候裁行 = 进度账本 T-127):开关
    翻 True(全量形态)同帧发射——成员类轴放开,victim 逐件归因分键
    redeploy_transition_victim_<名> 随发射显影(§2.3/§6.3)。只翻常量
    不改结构 = 候裁落地形态预演;翻回 False 即回滚。"""
    out, c, sess = _run_gate_frame(monkeypatch, joy_panel=4, enabled=True)
    fired = [e for e in out if e.action.__class__.__name__ == 'RunDeploy'
             and e.reason == 'm1_swap_redeploy']
    assert len(fired) == 1
    assert c.get('m1p_fired') == 1
    assert c.get('swap_arm_transition_trigger') == 1
    assert c.get('redeploy_transition_victim_忘归人') == 1
    assert 'redeploy_cost_gate_defer' not in c
    assert state_of(sess).cw4_m1p_arm_pending == 'transition'


def test_emission_gate_critical_member_fires_conservative(
        monkeypatch) -> None:
    """保守形态放行腿锁(ADR-0590 决策4;病灶机理 = 罗刹型):压席成员
    部署推进 form 缺口(面板 欢愉 3→4 越 form_tiers 下限)⇒ 缺省形态
    即发射——「档关键件 1★ 立即上」(P79-2【注】档贡献按在场人头)是
    保守形态的准许面;面板欠计传导(§7 #12 观测项)随数据源批对账,
    本锁钉当前面板口径行为。"""
    out, c, sess = _run_gate_frame(monkeypatch, joy_panel=3, enabled=False)
    fired = [e for e in out if e.action.__class__.__name__ == 'RunDeploy'
             and e.reason == 'm1_swap_redeploy']
    assert len(fired) == 1
    assert c.get('m1p_fired') == 1
    assert 'redeploy_cost_gate_defer' not in c


# ============ 让渡序域外照旧(ADR-0590 决策5 辖域)============

def test_formed_frame_victim_order_star_key_unchanged() -> None:
    """成型臂域外序照旧锁(ADR-0590 决策5:P79-4 让渡序辖域 = 锁线转型
    域;fp≥1.00 成型臂 victim 序 = 旧 1★ 优先,ADR-0530/0534 语义不动):
    成型帧(fenced_on)双 victim——三月七 1★ 与忘归人 2★(仙舟)——
    若贡献首键误外溢到成型臂域,2★ 会顶掉 1★;锁定旧星级序胜出
    (三月七)。差分构造:两档星级交叉,序判据可区分两种语义。
    夹具升级(T-167 F1/F-2 用例预期更新):bench 换丹恒·饮月(仙舟
    目标视图件)∧ target={'仙舟'}——原希儿(非目标视图件)夹具自 F1
    三合取谓词起落 no_bench_target 弃权(执行面本就跳过该形态,旧计划
    非空 = 幻影),序判据改在可兑现形态上锁;原形态新预期由本文件
    下方对照臂锁承载。"""
    deployed = [_bc('三月七', 1), _bc('忘归人', 2)]
    bench = [_bc('丹恒·饮月', 1)]
    ctx = SwapPlanContext(
        target_factions=frozenset({'仙舟'}),
        target_cores=frozenset(), fw_carry=frozenset(),
        locked_factions=frozenset(), protect_names=frozenset(),
        membership=frozenset(), fresh_buys=frozenset(), board={},
        deployed=deployed, bench=bench, cap=2, fenced_on=True, fp=1.0,
        locked=True, board_full=True)
    plan = select_swap_plan(ctx)
    assert plan.nonempty
    assert plan.sell_names == ['三月七']   # 1★ 优先(旧序),非贡献重排
    assert plan.arm == 'formed'


def test_formed_frame_bench_no_target_piece_abstains() -> None:
    """F1 合取②新语义对照臂锁(T-167;ADR-0534 修订节用例预期更新):
    成型帧 ∧ bench 无目标视图件(希儿)→ 弃权 no_bench_target——旧
    形态「计划非空(卖 1★ 腾位上非目标件)→ 执行面 _bench_tgt_n=0 跳过
    卖出 → no-op」正是 T-167 幻影部署族;修后发射⇔执行同谓词,该形态
    出口 = 空批出战(F2 收益耗尽臂兜底推进)。"""
    deployed = [_bc('三月七', 1), _bc('忘归人', 2)]
    bench = [_bc('希儿', 1)]   # 希儿系 ∈ DEPLOY_FENCE,∉ 欢愉视图
    ctx = SwapPlanContext(
        target_factions=frozenset({'欢愉'}),
        target_cores=frozenset(), fw_carry=frozenset(),
        locked_factions=frozenset(), protect_names=frozenset(),
        membership=frozenset(), fresh_buys=frozenset(), board={},
        deployed=deployed, bench=bench, cap=2, fenced_on=True, fp=1.0,
        locked=True, board_full=True)
    plan = select_swap_plan(ctx)
    assert not plan.nonempty
    assert plan.abstain == 'no_bench_target'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
