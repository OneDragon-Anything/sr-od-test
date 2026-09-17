"""deploy 判据必需件语义锁(T-17 修复批;行为出处 = 判据必要条件支配论证)。

被锁行为(语义出处,非实现巧合):
- **必需件首桶序**(``select_deployments`` ``required_names``):目标
  comp 的 ``required_deployed`` 成员(现役唯一实例 = 希儿系 pair 的
  ``pair_target_comp`` required=(希儿,);判据合取支 = 希儿在板)在 cap
  竞争(空位 < 候选数)时先于其他 target 成员上板——缺它该体系永远无法
  成型,普通成员可替换而必需件不可,[31]②「目标件最高优先」的必需件
  特化。实证 = sim n1000 s91700 基线 s91746/s92124 双失败局(希儿全程
  bench,席位被普通成员按旧序占走)。
- **板满换入臂**(``required_swap_arm_pending`` ×
  ``swap_sell_exclusion_reason`` × select_swap_plan 卖后上序):
  板满 ∧ 必需件滞留 bench 时,离场不破判据(AND 腿全保持 ∧ OR 腿
  至少一条保持)的 target 板件让位可卖,换入必需件;破腿件照旧
  target_keep;必需件已在板 = 臂关。证据 = 20260915 sim 找问题报告
  问题 2(s77408 dep 9/9 bench 8/8 含希儿,整轮无 swap-in)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SwapPlanContext,
    required_swap_arm_pending,
    select_deployments,
    select_swap_plan,
    swap_sell_exclusion_reason,
)
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_intention import (
    pair_target_comp,
)

# 真实注册表角色(锁语义不锁巧合;registry 真值):
# 桑博 = 贝+持续伤害 / 娜塔莎 = 贝 / 花火 = 量子 / 卡芙卡 = 持续伤害 /
# 希儿 = 贝+量(required carry)。
_SANGBO = '桑博'
_NATASHA = '娜塔莎'
_HUAHUO = '花火'
_KAFKA = '卡芙卡'
_XIER = '希儿'


def _bc(name: str, idx: int) -> BenchChar:
    """bench 件(slot = 1 基物理槽;idx 供唯一 slot)。"""
    return BenchChar(slot=idx, char_id=name, star=1)


# 持续伤害+希儿系 pair 的判据腿(真实 pair 键;fallback 分支产物 =
# form_tiers {持续伤害:2} + or_legs 量2∨贝2 + required 希儿;单一源 =
# pair_target_comp)。
_PAIR = ('持续伤害', '希儿系')


def _pair_comp():
    return pair_target_comp(_PAIR)


# ============================================================ V1 首桶序

def test_required_carry_seats_first_under_cap_competition() -> None:
    """cap 竞争(空位 1,候选 2)下必需件先于普通 target 成员上板。

    反证面:required_names 缺省空集 = 逐位旧序(bench 序先者上),锁
    「默认路径零漂移」与「新参翻转竞争结果」一对事实。
    """
    bench = [_bc(_SANGBO, 1), _bc(_XIER, 2)]   # 桑博 bench 序在前
    up, _held = select_deployments(
        bench, deployed_cids=set(), deployed_fac={}, board={},
        cap=1, target_factions={'贝洛伯格', '持续伤害'},
        target_cores={_SANGBO, _XIER}, required_names={_XIER})
    assert [bench[i].char_id for i in up] == [_XIER]

    up_old, _held = select_deployments(
        bench, deployed_cids=set(), deployed_fac={}, board={},
        cap=1, target_factions={'贝洛伯格', '持续伤害'},
        target_cores={_SANGBO, _XIER})
    assert [bench[i].char_id for i in up_old] == [_SANGBO]


# ============================================================ V2 换入臂

def _ctx(*, board: list[str], bench: list[str], cap: int) -> SwapPlanContext:
    """直构 SwapPlanContext(1★ 单元格;target 键 = pair 真值)。"""
    return SwapPlanContext(
        target_factions=frozenset({'持续伤害', '量子同频', '贝洛伯格'}),
        target_cores=frozenset({c for c in (*board, *bench)}),
        fw_carry=frozenset(),
        locked_factions=frozenset(),
        protect_names=frozenset(),
        membership=frozenset(),
        fresh_buys=frozenset(),
        board={},
        deployed=[BenchChar(slot=i + 1, char_id=n, star=1,
                            position_pref='back')
                  for i, n in enumerate(board)],
        bench=[_bc(n, i + 1) for i, n in enumerate(bench)],
        cap=cap,
        front_slots=4,
        back_slots=6,
        fenced_on=False,
        fp=0.0,
        locked=False,
        board_full=len(board) >= cap,
        recipe_floor_lock_exempt=False,
        target_comp=_pair_comp(),
        evolution_swap_armed=False,
        transition_domain=False,
        required_names=frozenset({_XIER})
        if _XIER in bench and _XIER not in board else frozenset(),
    )


def test_swap_arm_sellable_only_when_completion_holds() -> None:
    """换入臂资格分野:离场保判据的可卖;破腿的照旧 target_keep。

    板 = 桑博(贝+DOT)+卡芙卡(DOT)+娜塔莎(贝)+花火(量),pair
    判据 = DOT2 ∧ (量2∨贝2) ∧ 希儿在板:花火离场 → DOT2 ✓∧贝2 ✓ =
    判据保持 → 让位可卖(1★ 单元格资格族余守卫全过);桑博离场 →
    DOT1 = AND 破;娜塔莎离场 → 贝1∧量1 = OR 全破——均 target_keep。
    """
    ctx = _ctx(board=[_SANGBO, _KAFKA, _NATASHA, _HUAHUO],
               bench=[_XIER], cap=4)
    assert required_swap_arm_pending(ctx)
    assert swap_sell_exclusion_reason(_HUAHUO, ctx) == ''
    assert swap_sell_exclusion_reason(_SANGBO, ctx) == 'target_keep'
    assert swap_sell_exclusion_reason(_NATASHA, ctx) == 'target_keep'


def test_swap_arm_closed_when_carry_already_on_board() -> None:
    """必需件在板 = 臂关(无换入需求),target 保护原样。"""
    ctx = _ctx(board=[_SANGBO, _KAFKA, _NATASHA, _HUAHUO, _XIER],
               bench=[_HUAHUO], cap=5)
    assert not required_swap_arm_pending(ctx)


def test_swap_plan_seats_required_carry_after_sell() -> None:
    """卖后上序正形:卖冗余件后空位落必需件(计划 = sell 花火,up 希儿)。

    席位竞争面:bench 序普通 target 成员在前时,必需件仍须先落
    (V1 首桶序 × V2 卖后上序的组合语义;旧序会把席位给普通成员 =
    白卖形态)。
    """
    ctx = _ctx(board=[_SANGBO, _KAFKA, _NATASHA, _HUAHUO],
               bench=[_NATASHA, _XIER], cap=4)
    plan = select_swap_plan(ctx)
    assert plan.nonempty
    assert plan.sell_names == [_HUAHUO]
    up_names = {ctx.bench[i].char_id for i in plan.up_bench}
    assert up_names == {_XIER}
