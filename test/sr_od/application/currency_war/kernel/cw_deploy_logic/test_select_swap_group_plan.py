"""转型域最小充分组贪心计划形态测试(枚举情形表/两级序/组生长/拒绝键)。

被测 = ``kernel/cw_deploy_logic.py`` ``select_swap_plan`` 转型域组计划形态
与序参数构建(design 2026-10-26-swap-channel-unified §2.2 枚举情形表/
§2.7 组配对算法/§2.3.1 双轨域照旧;判据域单元面另见同目录
test_swap_bond_gate_domain.py,mandate 发出分键见 strategies 侧
test_emit_swap_bond_gate.py):

- **枚举表全情形**(§2.2,锚数值按 §2.1 档位梯直调):
  A/A′/B/C/D/G/E/F;
- **C 情形单帧构造**(§2.7 组生长语义):两对各自不达腿、累积组过门 1④;
- **两级 victim 序 + 换入序全序**(§2.7 序参数 ports 注入,tie-break 钉死);
- **无可行组零动作稳态**(§2.7)与拒绝侧分键来源三态;
- **双轨域照旧**:pair 帧(腿②)单对形态 + arm='transition'
  (design §2.3.1 pair 路由钉死)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war.kernel.cw_deploy_logic.test_swap_bond_gate_domain import (
    _FUX,
    _GIL,
    _HUO,
    _JI,
    _QING,
    _RIN,
    _SBR,
    _TING,
    _WALT,
    _YAO,
    _gate_ctx,
)

from sr_od.application.currency_war.kernel.cw_comps import Comp, get_comp
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    swap_bond_gate_benefit,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    build_swap_group_order,
    select_deployments_reasoned,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)


def _plan(ctx, select_up=select_deployments_reasoned):
    """组计划直驱(序参数 = 生产构建器 ports 注入;design §2.7)。"""
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        select_swap_plan,
    )
    return select_swap_plan(ctx, select_up=select_up,
                            group_order=build_swap_group_order(ctx))


def _up_names(plan, ctx) -> list[str]:
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        swap_plan_up_names,
    )
    return swap_plan_up_names(plan, ctx)


# ============================================================
# 枚举情形表(design §2.2;完成判据 1)
# ============================================================

def test_case_a_anchor_saber_swaps_yao_guang() -> None:
    """A 锚帧(判据 10 锚帧复验):Saber 换爻光——一级序首 victim(贡献
    1 = 爻光 < 2 = 青雀,度量域 = all_factions 全量并集),组换后圣杯
    2→3(二阶)∧ 能量 2→3(一阶)双激活,归因 ①(② 亦中)。"""
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=[_SBR], cap=5)
    plan = _plan(ctx)
    assert plan.nonempty
    assert plan.sell_names == [_YAO], f'锚① = Saber 换爻光,实得 {plan.sell_names}'
    assert _up_names(plan, ctx) == [_SBR]
    assert plan.arm == 'bond_gate'
    assert plan.bond_gate_leg == 'tier'
    assert plan.victim_tier == '一级'


def test_case_a2_second_tier_victim_ting_yun() -> None:
    """A′ 情形:换出件为终局标签支撑件(停云,二级)——无一级 victim 在板
    时二级承接;Saber 入板圣杯 3 激活(能量持平),归因 ①。"""
    ctx = _gate_ctx(board=[_GIL, _RIN, _TING, _WALT, _FUX],
                    bench=[_SBR], cap=5)
    plan = _plan(ctx)
    assert plan.nonempty
    assert plan.sell_names == [_TING], \
        f'二级 victim 首选停云(贡献 0 < 远坂凛),实得 {plan.sell_names}'
    assert plan.arm == 'bond_gate' and plan.bond_gate_leg == 'tier'
    assert plan.victim_tier == '二级'


def test_case_b_external_bond_filler_swap_in() -> None:
    """B 情形:外部凑档件(停云,能量标签)换入组——能量 2→3 新档激活
    (帧定)、支撑数增,归因 ①(② 亦中);一级 victim 承让。"""
    ctx = _gate_ctx(board=[_GIL, _SBR, _QING, _YAO, '椒丘'],
                    bench=[_TING], cap=5)
    plan = _plan(ctx)
    assert plan.nonempty
    assert plan.sell_names == [_QING], '一级 victim 首选(贡献并列 0 → 扫描序)'
    assert _up_names(plan, ctx) == [_TING], '外部支撑件换入(up∩名单=∅ 形态)'
    assert plan.bond_gate_leg == 'tier'


def test_case_c_group_growth_two_pairs_completion() -> None:
    """C 情形单帧构造(判据 1;§2.7 组生长语义):两对各自不达任何腿、
    累积组过门 1④(单对只试不生长会使此形态不可达)。

    阵容 = 纯 required 形态(键集空 → ① 恒不中;全名单支撑 → ② 持平;
    异名 → ③ 不中):pair1 (瓦尔特→停云) 只补 1/2 必需腿,pair2
    (杰帕德→希儿) 补满 → fp ✗→✓ 归因 ④。"""
    comp = Comp(name='C组生长测', factions=[], core_chars=[
        '瓦尔特', '杰帕德', '停云', '希儿', '符玄'],
        form_tiers={}, strength='A', form_difficulty='easy',
        early_power='中', required_deployed=('瓦尔特', '杰帕德'))
    ctx = _gate_ctx(board=['停云', '希儿', '符玄'], bench=['瓦尔特', '杰帕德'],
                    cap=3, comp=comp, fp=0.5)
    plan = _plan(ctx)
    assert plan.nonempty, f'组生长须成组:reasons={plan.reasons} ' \
                          f'reject={plan.bond_gate_reject}'
    assert plan.sell_names == ['停云', '希儿'], \
        f'累积两对定稿(换入主序 × victim 辅序字典序),实得 {plan.sell_names}'
    assert _up_names(plan, ctx) == ['瓦尔特', '杰帕德']
    assert plan.arm == 'bond_gate' and plan.bond_gate_leg == 'completion', \
        '累积组过门 1④(组生长语义)'
    # 反证面:单对各自不达任何腿(若单对可行,搜索不会长成两对)
    for v, u in ((['停云'], ['瓦尔特']), (['希儿'], ['杰帕德'])):
        ok, _leg = swap_bond_gate_benefit(ctx, victims=v, ups=u,
                                          pairs=[(v[0], u[0])],
                                          up_stars={u[0]: 1})
        assert ok is False, f'单对 {v}->{u} 不得单独过门 1(组生长前提)'


def test_inner_victim_retry_gate1_fail_then_completion() -> None:
    """内层 victim 回退(design §2.7 组构造遍历序钉死面「先换 victim
    (内层耗尽)→ 再换 up」):当前 up 首个 victim 过全部前置闸但门 1
    不中时,内层按 victim 辅序继续重试(试组不并入前缀),后续 victim
    可达 ④ → 字典序第一可行组发射——「首 victim 挡道」不得遮蔽后续
    可行组。

    复现形态 = 下帧续发场景(3.2 交付报告):板上 required 件(瓦尔特)
    占 victim 首扫描位,残余 up(杰帕德)与首扫描位的横换 = required
    对调 no-op(④ 不中/② 持平),回退后 (希儿→杰帕德) ④ 成型可达。
    """
    comp = Comp(name='C组生长测', factions=[], core_chars=[
        '瓦尔特', '杰帕德', '停云', '希儿', '符玄'],
        form_tiers={}, strength='A', form_difficulty='easy',
        early_power='中', required_deployed=('瓦尔特', '杰帕德'))
    ctx = _gate_ctx(board=['瓦尔特', '希儿', '符玄'], bench=['杰帕德'],
                    cap=3, comp=comp, fp=0.5)
    plan = _plan(ctx)
    assert plan.nonempty, f'内层回退须找到可行组:reasons={plan.reasons} ' \
                          f'reject={plan.bond_gate_reject}'
    assert plan.sell_names == ['希儿'], \
        f'首 victim(瓦尔特)门 1 不中 → 内层回退至次序 victim,实得 {plan.sell_names}'
    assert _up_names(plan, ctx) == ['杰帕德']
    assert plan.bond_gate_leg == 'completion', \
        '回退组 ④ 首达(required 全在板成型)'
    assert plan.victim_tier == '名单末位'


def test_case_d_same_star_horizontal_swap_3a() -> None:
    """D 情形:板上 1★ Saber、备战席 2★ Saber——同名升星横换(③ +
    §2.2.1 让位通道 3(a));名单成员让位末位语义 = 一级 victim 被同名
    去重裁判挡下后落到名单 3(a) 对(键集/支撑全持平,归因 ③)。"""
    ctx = _gate_ctx(board=[_SBR, _GIL, _TING, _YAO, '椒丘'],
                    bench=[_SBR], cap=5, bench_stars={_SBR: 2})
    plan = _plan(ctx)
    assert plan.nonempty
    assert plan.sell_names == [_SBR] and _up_names(plan, ctx) == [_SBR], \
        '同名升星横换(1★ → 2★,该名仍在板)'
    assert plan.arm == 'bond_gate' and plan.bond_gate_leg == 'star', \
        '键集/支撑/成型全持平,唯一收益 = 星级升(③)'
    assert plan.victim_tier == '名单末位', \
        '名单成员让位通道 3(a):victim 层来源 = 名单末位'


def test_case_g_or_carry_completion_swap_in() -> None:
    """G 情形(完成判据 3):希儿量子静态套完成品换入经门 1④ 放行——
    希儿入板(required 腿 + SEELE_OR_LEGS 全承接),fp ✗→✓ 不跨档位梯
    (①不中)。"""
    comp = get_comp('希儿量子')
    ctx = _gate_ctx(board=['花火', '缇宝', '娜塔莎', '杰帕德', '佩拉'],
                    bench=['希儿'], cap=5, comp=comp)
    plan = _plan(ctx)
    assert plan.nonempty
    assert plan.sell_names == ['娜塔莎'], \
        'victim 二级(贝标签)首选(名单成员让位沉末位桶)'
    assert _up_names(plan, ctx) == ['希儿'], '完成品换入'
    assert plan.arm == 'bond_gate' and plan.bond_gate_leg == 'completion', \
        'OR 承接阵容成型归因 ④(不跨档位梯)'


def test_case_e_roster_victim_pool_reject() -> None:
    """E 情形:终局件横换终局件(瓦尔特换符玄)——拒绝层 = victim 池层
    (白名单两通道均不通:3(a) 无同名升星 / 3(b) 无分支 hold),板名
    target_keep;计划不得卖名单无通道成员。"""
    ctx = _gate_ctx(board=[_WALT, _GIL, _RIN, _TING, _QING],
                    bench=['符玄'], cap=5)
    assert _gate_ctx(board=[_WALT, _GIL, _RIN, _TING, _QING],
                     bench=['符玄'], cap=5) is not None
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        swap_sell_exclusion_reason,
    )
    assert swap_sell_exclusion_reason(_WALT, ctx) == 'target_keep', \
        'E 拒绝层 = victim 池层(名单成员让位白名单两通道均不通)'
    plan = _plan(ctx)
    assert _WALT not in plan.sell_names, '无通道名单成员不得进卖序'


def test_case_e_gate1_reject_second_tier_par_frame() -> None:
    """二级持平换人帧(design §2.2 E 行补测):开拓者·记忆(能量)换停云
    (能量)——键集计数全持平(圣杯 1 持平、能量 3 持平,能量梯 tier1
    已达成不新增)、支撑持平(同标签同数)、非同名、成型不达成——
    门 1 四腿全不中 → 零动作,拒绝侧分键 = nogain。"""
    ctx = _gate_ctx(board=[_GIL, _TING, _HUO, _WALT, _FUX],
                    bench=[_JI], cap=5)
    plan = _plan(ctx)
    assert not plan.nonempty, '二级持平帧四腿全不中 = 零动作'
    assert plan.arm == 'bond_gate'
    assert plan.bond_gate_reject == 'nogain', \
        f'拒绝侧分键 nogain(四腿全不中),实得 {plan.bond_gate_reject}'


def test_case_f_roster_tier_carrier_protected() -> None:
    """F 情形:卖终局档位承载件(开拓者·记忆)——拒绝层 = victim 池层
    (名单成员无让位通道 → target_keep);守恒拦为次层防线(经
    test_bond_gate_conservation 另测)。"""
    ctx = _gate_ctx(board=[_GIL, _JI, _HUO, _TING, _YAO],
                    bench=[_SBR], cap=5)
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        swap_sell_exclusion_reason,
    )
    assert swap_sell_exclusion_reason(_JI, ctx) == 'target_keep', \
        'F 拒绝层 = victim 池层(名单成员保护/白名单通道不通)'
    plan = _plan(ctx)
    assert _JI not in plan.sell_names


def test_conservation_reject_key_on_tier_drop() -> None:
    """守恒拦拒绝侧分键:唯一可行收益对的 victim 为终局档位承载件时,
    组级档位非降拦下 → 零动作 + conservation(design §2.3 守恒面;
    §2.3.1 拒绝侧闭集)。板:圣杯2/能量4,名单victim 停云(能量承载)
    对 瓦尔特 收益对被拦,远坂凛(圣杯承载)对 符玄 同被拦。"""
    ctx = _gate_ctx(board=[_GIL, _JI, _HUO, _TING, _RIN],
                    bench=[_WALT, _FUX], cap=5)
    plan = _plan(ctx)
    assert not plan.nonempty
    assert plan.bond_gate_reject == 'conservation', \
        f'守恒拦分键,实得 {plan.bond_gate_reject}'


def test_no_feasible_group_zero_action_steady_state() -> None:
    """无可行组 = 零动作合法稳态(§2.7):victim 池空(2★ star_guard 全拒)
    → novictim;victim 存在但无换入候选 → novictim;四腿全不中 → nogain。"""
    # victim 池空:全 2★ 板(star_guard 恒拒,演进未武装)
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=[_SBR], cap=5,
                    stars=dict.fromkeys((_GIL, _RIN, _QING, _TING, _YAO), 2))
    plan = _plan(ctx)
    assert not plan.nonempty and plan.bond_gate_reject == 'novictim'
    # victim 存在但 bench 无支撑件换入候选(青雀/爻光非支撑,不入 up 池)
    ctx2 = _gate_ctx(board=[_GIL, _TING, _WALT, _FUX, '希儿'],
                     bench=[_QING], cap=5)
    plan2 = _plan(ctx2)
    assert not plan2.nonempty and plan2.bond_gate_reject == 'novictim', \
        '无合法换入候选 = 无可行组(novictim)'


# ============================================================
# 序参数全序(design §2.7 序参数 ports 注入;完成判据 10)
# ============================================================

def test_victim_order_two_tier_full_order() -> None:
    """victim 两级全序:一级(纯过渡件,层内 = 贡献升序)→ 二级(标签
    支撑件,层内同款)→ 名单末位桶;锚帧 = [爻光(1), 青雀(2), 停云(1),
    远坂凛(2)],名单成员(吉,无通道)不入池。"""
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=[_SBR], cap=5)
    order = build_swap_group_order(ctx)
    got = sorted({n for n in (_GIL, _RIN, _QING, _TING, _YAO)
                  if swap_sellable(ctx, n)}, key=order.victim_sort_key)
    assert got == [_YAO, _QING, _TING, _RIN], \
        f'锚帧两级序(一级先于二级,层内贡献升序),实得 {got}'


def swap_sellable(ctx, name: str) -> bool:
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        swap_sell_exclusion_reason,
    )
    return swap_sell_exclusion_reason(name, ctx) == ''


def test_up_order_roster_first_and_tie_breaks() -> None:
    """换入候选序全序:名单成员桶先(层内星级降序 → 名单注册序 =
    line_members 拼接序)→ 外部支撑件(星级降序 → 标签命中数降序 →
    注册表序);非支撑件不入池。"""
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=['符玄', _WALT, _TING], cap=5)
    order = build_swap_group_order(ctx)
    # 符玄/瓦尔特 = 名单(1★):名单注册序 = core 拼接序,瓦尔特(core[2])
    # 先于 符玄(core[3])——注册表序则相反(符玄先),钉住拼接序 tie-break。
    # (up_sort_key 消费 bench 下标;bench 序 = [符玄, 瓦尔特, 停云])
    bench_names = ['符玄', _WALT, _TING]
    got = [bench_names[i] for i in sorted(range(len(bench_names)),
                                          key=order.up_sort_key)]
    assert got == [_WALT, '符玄', _TING], \
        f'名单桶先于外部桶 + 名单注册序 tie-break,实得 {got}'
    # 外部桶内:星级降序(停云 2★ 先)同星并列 = 注册表序
    ctx2 = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                     bench=['佩拉', _TING], cap=5,
                     bench_stars={_TING: 2})
    order2 = build_swap_group_order(ctx2)
    bench2 = ['佩拉', _TING]
    got2 = [bench2[i] for i in sorted(range(len(bench2)),
                                      key=order2.up_sort_key)]
    assert got2 == [_TING, '佩拉'], '外部桶星级降序'


def test_up_order_label_hits_desc_tie_break() -> None:
    """外部桶并列 tie-break = 标签命中数降序(3.5 预测表确定性要求
    全序钉死):键集 {能量, 治疗} 下藿藿双命中压过单命中停云(注册表序
    停云在前,命中数翻转)。"""
    ctx = _gate_ctx(board=[_GIL, _SBR, _YAO, '椒丘', '娜塔莎'],
                    bench=[_TING, _HUO], cap=5,
                    k_members=frozenset({_GIL, _SBR}))
    ctx.bond_gate_keys = frozenset({'能量', '治疗'})
    order = build_swap_group_order(ctx)
    bench3 = [_TING, _HUO]
    got = [bench3[i] for i in sorted(range(len(bench3)),
                                     key=order.up_sort_key)]
    assert got == [_HUO, _TING], \
        f'外部并列 = 标签命中数降序(藿藿 2 命中 > 停云 1),实得 {got}'


# ============================================================
# 双轨域照旧(design §2.3.1 pair 路由钉死;完成判据 5)
# ============================================================

def test_pair_frame_plan_stays_single_pair_transition_arm() -> None:
    """pair 双轨帧(腿②)计划形态逐位照旧:单对计划 + arm='transition'
    (转型分支机器退役后双轨域标注保留,design §2.3.1 发出闸路由申报);
    判别子排除 pair 后双轨域不进组形态。"""
    from test.sr_od.application.currency_war.kernel.test_deploy import (
        _swap_ctx,
    )
    ctx = _swap_ctx(board=['卡芙卡', '希儿', '花火', '娜塔莎'],
                    bench=['黑天鹅'], cap=4, fp=0.833, locked=True)
    plan = _plan(ctx)
    assert plan.nonempty
    assert plan.sell_names == ['花火'], '双轨域 victim 序/让位照旧(P79-4)'
    assert plan.arm == 'transition', \
        '双轨域 arm 标注照旧(转型分支退役不波及 pair 帧)'
    assert plan.bond_gate_leg == '' and plan.bond_gate_reject == '', \
        '双轨域不产 bond_gate 分键字段'


def test_swap_group_order_comp_fallback_no_comp() -> None:
    """序参数构建 fail-safe:target_comp 缺读(手装 ctx)→ 名单/键集空,
    键函数仍全序可排(消费面零炸;分组判定按 ctx 字段自治)。"""
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=[_SBR], cap=5)
    ctx.target_comp = None
    order = build_swap_group_order(ctx)
    assert order.victim_sort_key(_YAO) is not None
    assert order.up_sort_key(0) is not None
    assert predicates.line_members(None) == ()
