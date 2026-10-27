"""转型域双门核判据测试(判别子三合取/fenced 域腿/门 1 四腿/守恒/
资格面收窄/narrow_frame 迁移/完成品域参数化)。

被测 = ``kernel/cw_deploy_logic.py`` 转型域判据族(design 2026-10-26-
swap-channel-unified §2.0/§2.1/§2.2/§2.2.1/§2.3/§2.3.1;组贪心计划形态
另见同目录 test_select_swap_group_plan.py,mandate 发出分键见
strategies 侧 test_emit_swap_bond_gate.py):

- **判别子三合取**(§2.0):腿①终局阵容锁定(显式排除 p1_pair 腿②)
  ∧ fp<1.00 ∧ 板满;三腿全继承现行语义;
- **narrow_frame 谓词源迁移**(§2.3.1):``swap_transition_narrow_frame``
  改挂新判别子全合取,终局锁定域语义逐帧对照现行(回滚常量腿缺省开,
  等价 = 去腿),pair 帧不倒转进域;
- **fenced 关门分支域腿钉死**(§2.3.1):混轨 locked(腿①∨腿②)∧
  fp<1.00 ∧ 板满,无回滚常量腿,四行真值表逐帧;
- **门 1 四腿 + 守恒**(§2.2/§2.3):成品腿/tier/support/star;守恒 =
  终局档位非降(与门 1① 同一计数函数);
- **target_keep 口径收窄 + 让位白名单 + 义务集豁免**(§2.2/§2.2.1);
- **完成品分支域参数化**(§2.3):双轨域 fp✗→✓ 照旧,转型域门 1④
  同源折法(同一 ``_completion_swap_ins`` 单点门);
- **evolution 触发谓词域腿不迁移**(§2.3.1 钉死,零行为差);
- **k_members 装配单一源对账**:core∪shared 与
  ``predicates.line_members`` 全注册表等价(装配注释声明的等价性测试)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_session,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_front_window_predicates import (
    _d_frame_st,
)

from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    Comp,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SwapPlanContext,
    _bond_gate_same_star_up_available,
    _completion_swap_ins,
    bond_gate_tier_profile,
    evolution_swap_arm_trigger,
    fenced_swap_gate_open,
    required_swap_arm_pending,
    swap_bond_gate_benefit,
    swap_bond_gate_conservation,
    swap_bond_gate_domain,
    swap_bond_gate_domain_of,
    swap_sell_exclusion_reason,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_launch_admission import (
    protect_names_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)

# 双王圣杯锚帧注册表真值(cw_chars):吉/Saber = 命运圣杯+能量;
# 远坂凛 = 命运圣杯+战技点;停云 = 仙舟+能量;青雀 = 仙舟+战技点;
# 爻光 = 仙舟+欢愉(终局键集零命中,纯过渡件);爻光非圣杯非能量
# (design §2.1 标签实测)。键集 = 双王圣杯 form_tiers = {命运圣杯, 能量}。
_SBR = 'Saber'
_GIL = '吉尔伽美什'
_RIN = '远坂凛'
_QING = '青雀'
_TING = '停云'
_YAO = '爻光'
_WALT = '瓦尔特'
_FUX = '符玄'
_HUO = '藿藿'
_JI = '开拓者·记忆'

_COMP_NAME = '双王圣杯'


def _gate_ctx(*, board: list[str], bench: list[str], cap: int,
              comp: Comp | str = _COMP_NAME, fp: float = 0.5,
              locked: bool = True, stars: dict[str, int] | None = None,
              bench_stars: dict[str, int] | None = None,
              membership: frozenset[str] = frozenset(),
              fresh_buys: frozenset[str] = frozenset(),
              required: frozenset[str] | None = None,
              k_members: frozenset[str] | None = None,
              protect_names: frozenset[str] | None = None,
              ) -> SwapPlanContext:
    """转型域 ctx 直构(1★ 单元格缺省;locked = 混轨方向锁,
    locked_core 随同 = 腿①在效;pair 帧(腿②)构造见
    ``locked=False`` + 外部覆写或 test_deploy._swap_ctx)。"""
    comp_obj = get_comp(comp) if isinstance(comp, str) else comp
    stars = stars or {}
    bench_stars = bench_stars or stars
    return SwapPlanContext(
        target_factions=frozenset(comp_obj.all_factions),
        target_cores=frozenset(comp_obj.core_chars),
        fw_carry=frozenset(),
        locked_factions=frozenset(),
        protect_names=frozenset(protect_names)
        if protect_names is not None else protect_names_of(comp_obj),
        membership=frozenset(membership),
        fresh_buys=frozenset(fresh_buys),
        board={},
        deployed=[Unit(char_id=n, star=stars.get(n, 1)) for n in board],
        bench=[BenchSlot(kind='unit',
                         unit=Unit(char_id=n, star=bench_stars.get(n, 1)))
               for n in bench],
        cap=cap,
        front_slots=4,
        back_slots=6,
        fenced_on=False,
        fp=fp,
        locked=locked,
        locked_core=locked,
        bond_gate_keys=frozenset(comp_obj.form_tiers),
        k_members=frozenset(dict.fromkeys(
            [*comp_obj.core_chars, *comp_obj.shared_chars]))
        if k_members is None else frozenset(k_members),
        board_full=len(board) >= cap,
        recipe_floor_lock_exempt=False,
        target_comp=comp_obj,
        evolution_swap_armed=False,
        required_names=frozenset(required)
        if required is not None else frozenset(
            getattr(comp_obj, 'required_deployed', ()) or ()),
    )


# ============================================================
# 判别子三合取(design §2.0;完成判据 7)
# ============================================================

def test_bond_gate_domain_discriminator_truth_table() -> None:
    """转型域判别子三合取逐帧:腿① ∧ fp<1.00 ∧ 板满,三腿全继承现行语义;
    pair 腿②(locked_core=False)帧不进本域;fp 缺读 = 域外(fail-closed)。"""
    assert swap_bond_gate_domain_of(True, 0.5, True) is True
    assert swap_bond_gate_domain_of(False, 0.5, True) is False, '腿①缺 = 域外'
    assert swap_bond_gate_domain_of(True, 1.0, True) is False, '成型帧不进域'
    assert swap_bond_gate_domain_of(True, None, True) is False, 'fp 缺读 fail-closed'
    assert swap_bond_gate_domain_of(True, 0.5, False) is False, '板不满不进域'

    # ctx 形态:腿①在效帧进域;pair 帧(腿②混轨 locked=True 而
    # locked_core=False)不进本域(design §2.0 显式排除)。
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=[_SBR], cap=5)
    assert swap_bond_gate_domain(ctx) is True
    pair_ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                         bench=[_SBR], cap=5)
    pair_ctx.locked_core = False   # 配方对锁帧:混轨 locked 在而腿①不在
    assert swap_bond_gate_domain(pair_ctx) is False, \
        'pair 腿②帧不进转型域(判别子显式排除,design §2.0)'
    assert swap_bond_gate_domain(None) is False


def test_k_members_assembly_matches_line_members() -> None:
    """k_members 装配(kernel core∪shared 去重拼接)与策略层
    ``predicates.line_members`` 全注册表等价——装配函数注释声明的
    「同构同值」单一源对账,禁两源漂移(design §2.1 k_members 单一源)。"""
    for comp in COMP_LIBRARY:
        assembled = frozenset(dict.fromkeys([
            *comp.core_chars, *comp.shared_chars]))
        assert assembled == set(predicates.line_members(comp)), comp.name


# ============================================================
# narrow_frame 谓词源迁移(design §2.3.1;完成判据 11)
# ============================================================

def test_narrow_frame_predicate_source_truth_table_equivalence() -> None:
    """narrow_frame 迁移真值表等价:新判别子(去回滚常量腿)与现行语义
    (常量恒 True ⇒ 腿① ∧ fp<1.00 ∧ 板满)逐帧等价——终局锁定域语义
    逐帧对照,禁静默分叉(design §2.3.1 谓词源迁移钉死)。"""
    for locked in (False, True):
        for fp in (None, 0.5, 1.0):
            for full in (False, True):
                new = swap_bond_gate_domain_of(locked, fp, full)
                legacy = locked and fp is not None and fp < 1.00 and full
                assert new == legacy, (locked, fp, full)


def test_narrow_frame_pair_domain_not_inverted() -> None:
    """narrow_frame(P88 买侧收窄)端到端:终局锁定帧 True 与 kernel
    判别子同值;配方对锁帧(p1_pair 在、locked_comp 空)恒 False——
    pair 域不倒转进收窄域,消费位保留(design §2.3.1)。"""
    # 终局锁定 D 帧(front-window 测试的板满锁线构造,n_km=0 纯垫件):
    from test.sr_od.application.currency_war._cw_helpers import cw4_gs
    from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_leak_ladder import (
        _session_stub as _lad_session,
    )
    st = _d_frame_st(60, [])
    sess = _lad_session(locked=True)
    gs = cw4_gs(sess, **st)
    assert mandate.swap_transition_narrow_frame(gs, sess) is True, \
        '终局锁定 D 帧收窄旗 = 判别子同值(腿① ∧ fp<1.00 ∧ 板满)'
    # 配方对锁帧:locked_comp 空 = 腿①不在,恒 False(不收窄 = 保守侧)
    comp = get_comp('列车同行')
    pair_sess = cw4_session(comp)
    state_of(pair_sess).v3_intention = IntentionState(p1_pair=('仙舟', '持续伤害'))
    from test.sr_od.application.currency_war._cw_helpers import cw4_gs as _gs
    pair_gs = _gs(pair_sess, deploy_cap=3, level=3,
                  front_row=[Unit(char_id='丹恒·饮月', star=1),
                             Unit(char_id='卡芙卡', star=1),
                             Unit(char_id='杰帕德', star=1)])
    assert mandate.swap_transition_narrow_frame(pair_gs, pair_sess) is False, \
        '配方对锁帧不进 P88 收窄域(登记域不倒转,design §2.3.1)'


# ============================================================
# fenced 关门分支域腿(design §2.3.1 四行真值表)
# ============================================================

def test_fenced_gate_open_truth_table() -> None:
    """fenced 关门分支域腿四行真值表(混轨,无回滚常量腿):
    未锁关门 / 锁定 pre-form 开门 / 成型帧关门 / fp 缺读关门(fail-closed)。"""
    assert fenced_swap_gate_open(False, 0.5, True) is False   # 未锁关门
    assert fenced_swap_gate_open(True, 0.5, True) is True     # 锁定 pre-form 开门
    assert fenced_swap_gate_open(True, 1.0, True) is False    # 成型帧关门
    assert fenced_swap_gate_open(True, None, True) is False   # fp 缺读关门
    assert fenced_swap_gate_open(True, 0.5, False) is False   # 板不满关门


def test_fenced_piece_per_frame_reject_keys() -> None:
    """fenced 件逐帧拒因(域外现行机器逐位照旧;pair 双轨帧经 p1_pair
    腿②构造 = 混轨 locked):开门帧落资格族放行 / 成型帧与未锁帧
    fenced_arm_closed / fp 缺读 fp_unreadable——`fenced_arm_closed` 拒因键
    保留(design §2.3.1)。"""
    board = ['卡芙卡', _XIER_G, '花火', _SANYUE]
    # pair 帧(腿②):locked=True/locked_core=False,pair 真值键面
    from test.sr_od.application.currency_war.kernel.test_deploy import (
        _swap_ctx,
    )
    open_ctx = _swap_ctx(board=board, bench=['黑天鹅'], cap=4,
                         fp=0.833, locked=True)
    assert swap_sell_exclusion_reason(_SANYUE, open_ctx) == '', \
        'pair 双轨帧 fenced 开门:落资格族放行(守恒/星级/素材全过)'
    closed_ctx = _swap_ctx(board=board, bench=['黑天鹅'], cap=4,
                           fp=1.0, locked=True)
    assert swap_sell_exclusion_reason(_SANYUE, closed_ctx) \
        == 'fenced_arm_closed', '成型帧关门(现行)'
    unlocked_ctx = _swap_ctx(board=board, bench=['黑天鹅'], cap=4,
                             fp=0.833, locked=False)
    assert swap_sell_exclusion_reason(_SANYUE, unlocked_ctx) \
        == 'fenced_arm_closed', '未锁帧关门(fenced 件受保护)'
    unread_ctx = _swap_ctx(board=board, bench=['黑天鹅'], cap=4,
                           fp=None, locked=True)
    assert swap_sell_exclusion_reason(_SANYUE, unread_ctx) == 'fp_unreadable', \
        '锁定帧 fp 缺读两分支同弃权(fail-closed 同向)'


_XIER_G = '希儿'
_SANYUE = '三月七'


# ============================================================
# 门 1 四腿 + 守恒(design §2.2/§2.3)
# ============================================================

def test_bond_gate_leg_completion_and_tier_and_support() -> None:
    """门 1 首达腿检查序 ④→①→②(design §2.2 枚举表 C/G 行归因 ④;
    A 行 ①② 同中归因 ①):成品腿(④,同源折法 form_progress)优先于
    tier;tier 优先于 support。"""
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=[_SBR], cap=5)
    # A 帧:Saber 换爻光 → 圣杯 2→3(二阶)∧ 能量 2→3(一阶)双激活
    ok, leg = swap_bond_gate_benefit(ctx, victims=[_YAO], ups=[_SBR],
                                     pairs=[(_YAO, _SBR)],
                                     up_stars={_SBR: 1})
    assert ok is True and leg == 'tier', f'A 帧归因 ①,实得 {leg}'
    # ④ 优先帧:组换后成型(Saber+停云组 → 圣杯 3 ∧ 能量 4 仍 ✗;
    # 用 required 阵容构造纯 ④ 形态见 test_completion_branch_domain_
    # parameterized 的希儿量子帧)。此处钉 ①>②:支撑数增但档位持平帧
    # 归因 ②(键集外 victim 换入)。
    ctx_b = _gate_ctx(board=[_GIL, _SBR, _QING, _YAO, '椒丘'],
                      bench=[_TING], cap=5)
    ok_b, leg_b = swap_bond_gate_benefit(ctx_b, victims=['椒丘'],
                                         ups=[_TING],
                                         pairs=[('椒丘', _TING)],
                                         up_stars={_TING: 1})
    assert ok_b is True and leg_b == 'tier', \
        'B 帧:外部凑档件使能量 2→3 新档,归因 ①(tier 优先于 support)'


def test_bond_gate_leg_star_requires_same_name() -> None:
    """门 1③ 谓词钉死(完成判据 2 前半):同名必要——异名星级升换不构成
    ③(键集/支撑全持平帧 (False, ''));同名升星换对 ③ 成立。"""
    # 同名:Saber 2★ 换板上 Saber 1★(键集计数同名相抵、支撑同名相抵)
    ctx = _gate_ctx(board=[_SBR, _GIL, _TING, _YAO, '椒丘'],
                    bench=[f'{_SBR}2'], cap=5, k_members=frozenset({_SBR}))
    # (bench 名用占位防同名去重干扰单测判定;pairs/星级直接喂参数)
    ok, leg = swap_bond_gate_benefit(
        ctx, victims=[_SBR], ups=[_SBR], pairs=[(_SBR, _SBR)],
        up_stars={_SBR: 2})
    assert ok is True and leg == 'star', f'同名升星换归因 ③,实得 {leg}'
    # 异名:星级升但不同名 → ③ 不成立(两件都计入名单 → 支撑持平;
    # 键集零命中 → 档位持平;target_comp 成型不达成态)
    ok2, leg2 = swap_bond_gate_benefit(
        ctx, victims=[_YAO], ups=[_TING], pairs=[(_YAO, _TING)],
        up_stars={_TING: 2})
    assert (ok2, leg2) == (False, '') or leg2 != 'star', \
        f'异名星级升换不得归因 ③,实得 {leg2!r}'


def test_bond_gate_conservation_tier_non_decreasing() -> None:
    """守恒 = 终局档位非降(组换后板态口径;design §2.3)与门 1① 同一
    计数函数(bond_gate_tier_profile):掉档拦 / 持档放;档位梯逐档计数
    直调(cw_factions tiers 单源,design §21 档位语义源切分)。"""
    keys = frozenset(get_comp(_COMP_NAME).form_tiers)
    # 圣杯档位梯 (2,3,4,5):2 人 = 1 档、3 人 = 2 档(逐档计数直调)
    assert bond_gate_tier_profile(keys, {_GIL, _RIN}) \
        == {'命运圣杯': 1, '能量': 0}
    assert bond_gate_tier_profile(keys, {_GIL, _SBR, _TING}) \
        == {'命运圣杯': 1, '能量': 1}, '圣杯 2 人一阶 ∧ 能量 3 人一阶(梯 3/5/7/10)'
    # 掉档拦:能量 3 档承载组(吉+Saber+停云)卖停云不补能 → 档位降
    ctx = _gate_ctx(board=[_GIL, _SBR, _TING, _YAO, '椒丘'],
                    bench=['佩拉'], cap=5)
    assert swap_bond_gate_conservation(ctx, victims=[_TING],
                                       ups=['佩拉']) is False, \
        '卖能量承载件不补能 = 终局档位降,守恒拦'
    assert swap_bond_gate_conservation(ctx, victims=[_TING],
                                       ups=[_HUO]) is True, \
        '换入件(藿藿,能量)补回能量档 = 档位非降,守恒放'


# ============================================================
# target_keep 口径收窄 + 让位白名单 + 义务集豁免
# (design §2.2/§2.2.1;完成判据 8)
# ============================================================

def test_target_keep_narrowed_whitelist_channels() -> None:
    """转型域 victim 白名单:纯过渡件(一级)/终局标签支撑件(二级)入池;
    名单成员无 3(a)/3(b) 通道 → target_keep;替班契约件/fw_carry 恒拒;
    fresh_buy 排除照旧。"""
    ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                    bench=[_SBR], cap=5)
    assert swap_sell_exclusion_reason(_YAO, ctx) == '', \
        '纯过渡件(爻光,键集零命中)= 通道 1 入池(C1 解锁点)'
    assert swap_sell_exclusion_reason(_QING, ctx) == '', \
        '青雀(仙舟+战技点,键集零命中)= 通道 1 入池'
    assert swap_sell_exclusion_reason(_TING, ctx) == '', \
        '终局标签支撑件(停云,能量命中)= 通道 2 入池(阵营视图恒拒退役)'
    assert swap_sell_exclusion_reason(_RIN, ctx) == '', \
        '远坂凛(圣杯命中,非名单)= 通道 2 入池'
    assert swap_sell_exclusion_reason(_GIL, ctx) == 'target_keep', \
        '名单成员无 3(a)(bench 无同名升星)/3(b)(无 required/完成件)→ 拒'
    sub_ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                        bench=[_SBR], cap=5,
                        protect_names=frozenset({_TING, _RIN, _QING,
                                                 _GIL, _YAO, '椒丘'}),
                        k_members=frozenset({_GIL, _SBR}))
    assert swap_sell_exclusion_reason('椒丘', sub_ctx) == 'target_keep', \
        '替班契约件(protect_names − 名单,椒丘替班位)恒拒:不因白名单沦为 victim'
    fresh_ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                          bench=[_SBR], cap=5, fresh_buys=frozenset({_YAO}))
    assert swap_sell_exclusion_reason(_YAO, fresh_ctx) == 'fresh_buy', \
        '轮内新鲜度排除照旧(域切分不豁免)'


def test_membership_waived_in_bond_gate_only() -> None:
    """义务集面域切分(design §2.2):``locked_buy_membership`` 拒卖腿在
    转型域换人让位路径整体豁免(白名单三通道全免);域外(pair 帧)照旧
    buy_membership 拒。membership 缺读(None)弃权两侧保留在前。"""
    hoard = frozenset({_YAO, _QING, _TING, _RIN, _GIL})
    gate_ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                         bench=[_SBR], cap=5, membership=hoard)
    assert swap_sell_exclusion_reason(_YAO, gate_ctx) == '', \
        '转型域:义务集成员经让位白名单豁免拒卖腿(路径域豁免)'
    # 域外 pair 帧(腿②):义务集拒照旧
    from test.sr_od.application.currency_war.kernel.test_deploy import (
        _swap_ctx,
    )
    pair_ctx = _swap_ctx(board=['卡芙卡', _XIER_G, '花火', _SANYUE],
                         bench=['黑天鹅'], cap=4, fp=0.833, locked=True)
    pair_ctx.membership = frozenset({_SANYUE})
    assert swap_sell_exclusion_reason(_SANYUE, pair_ctx) == 'buy_membership', \
        'pair 双轨帧义务集拒照旧(豁免仅转型域换人路径)'
    unread_ctx = _gate_ctx(board=[_GIL, _RIN, _QING, _TING, _YAO],
                           bench=[_SBR], cap=5)
    unread_ctx.membership = None
    assert swap_sell_exclusion_reason(_YAO, unread_ctx) \
        == 'membership_unreadable', '缺读弃权两侧保留在前(fail-closed)'


def test_roster_channel_3a_and_3b_availability() -> None:
    """名单成员两让位通道可用性(完成判据 4):3(a) = bench 同名星级严格升
    (同名必要);3(b) = 分支 hold 让位(required pending ∧ 判据保持检验,
    含量席让位现行语义)。"""
    # 3(a):bench Saber 2★ > 板上 Saber 1★
    ctx_3a = _gate_ctx(board=[_SBR, _GIL, _TING, _YAO, '椒丘'],
                       bench=[_SBR], cap=5, bench_stars={_SBR: 2})
    assert _bond_gate_same_star_up_available(ctx_3a, _SBR) is True
    assert swap_sell_exclusion_reason(_SBR, ctx_3a) == '', \
        '名单成员经 3(a) 同名升星横换让位放行(D 情形通道)'
    # 同星同名(bench Saber 1★)不构成 3(a)——星级严格升才可
    ctx_same = _gate_ctx(board=[_SBR, _GIL, _TING, _YAO, '椒丘'],
                         bench=[_SBR], cap=5)
    assert _bond_gate_same_star_up_available(ctx_same, _SBR) is False
    # 3(b):required pending 帧(希儿量子:required 希儿缺 + bench 有)
    # ——名单成员(花火)经分支 hold 让位放行(量席让位现行语义保留)。
    comp = get_comp('希儿量子')
    ctx_3b = _gate_ctx(board=['花火', '缇宝', '娜塔莎', '杰帕德', '佩拉'],
                       bench=['希儿'], cap=5, comp=comp)
    assert required_swap_arm_pending(ctx_3b), '必需件滞留:分支武装'
    assert swap_sell_exclusion_reason('花火', ctx_3b) == '', \
        '名单成员经 3(b) 分支 hold 让位放行(量席让位现行语义保留)'


# ============================================================
# 完成品分支域参数化(design §2.3 收窄点钉死;完成判据 6)
# ============================================================

def test_completion_branch_dual_domain_same_source() -> None:
    """完成品分支判据域参数化:双轨域(pair 帧)fp✗→✓ 照旧 + 转型域
    (腿①)门 1④ 同源折法——同一 ``_completion_swap_ins`` 单点门两域
    各自适用范围,禁复制第二实现(候选集同吃,三消费位零签名)。"""
    # 双轨域:pair 对锁帧完成件(现行 test_deploy 完成通道帧面)
    from test.sr_od.application.currency_war.kernel.test_deploy import (
        _swap_ctx,
    )
    pair_ctx = _swap_ctx(board=['卡芙卡', _XIER_G, '花火', '娜塔莎'],
                         bench=['黑天鹅'], cap=4, fp=0.833, locked=True)
    assert _completion_swap_ins(pair_ctx) == {'黑天鹅'}, \
        '双轨域:配方完成件候选照旧(fp✗→✓ 同一单点门)'
    # 转型域:希儿量子静态套(OR 承接)完成件 = 希儿入板即成型
    comp = get_comp('希儿量子')
    gate_ctx = _gate_ctx(board=['花火', '缇宝', '娜塔莎', '杰帕德', '佩拉'],
                         bench=['希儿'], cap=5, comp=comp)
    assert _completion_swap_ins(gate_ctx) == {'希儿'}, \
        '转型域:完成品候选同吃单点门(门 1④ 同源折法)'
    ok, leg = swap_bond_gate_benefit(gate_ctx, victims=['娜塔莎'],
                                     ups=['希儿'], pairs=[('娜塔莎', '希儿')],
                                     up_stars={'希儿': 1})
    assert ok is True and leg == 'completion', \
        '转型域完成品换入经门 1④ 放行(G 情形;不跨档位梯)'


def test_evolution_arm_trigger_domain_legs_unchanged() -> None:
    """evolution_swap_arm_trigger 域腿对账(design §2.3.1 钉死):维持
    现行混轨语义不迁移——准入三元含 pair 帧,与 fenced 关门分支域腿同形
    并存,零行为差(禁静默分叉)。"""
    bench_member = [cw4_bc('希儿')]
    hoard = frozenset({'希儿'})
    assert evolution_swap_arm_trigger(
        hoard, bench_member, locked=True, fp=0.5, board_full=True) is True, \
        '混轨 locked(pair 腿②帧同值)准入照旧'
    assert evolution_swap_arm_trigger(
        hoard, bench_member, locked=False, fp=0.5, board_full=True) is False
    assert evolution_swap_arm_trigger(
        hoard, bench_member, locked=True, fp=1.0, board_full=True) is False, \
        '成型帧分支关(现行)'
    assert evolution_swap_arm_trigger(
        hoard, bench_member, locked=True, fp=None, board_full=True) is False, \
        'fp 缺读分支关(fail-closed,现行)'
    assert evolution_swap_arm_trigger(
        frozenset(), bench_member, locked=True, fp=0.5,
        board_full=True) is False, 'membership 缺省空 = 分支关(现行)'
