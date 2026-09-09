"""test_cw_deploy_core 主题锁——部署/换血/伪槽/围栏单一源核代表行。

覆盖面(四类承重件):
- 决策真值代表锚:W209 换阵卖出义务臂喂入语义(板满=真部署数,禁羁绊计数
  总和——P1 阻断判别)/ 成型臂 victim 让渡序(1★ 优先旧序,贡献重排不外溢);
- fail-closed 代表:伪槽(kernel 防线)is_item_slot=True 恒 held,即使 target
  件 ∧ 板有空位仍拒——先于一切围栏/cap 判定;
- schema/注册表级守卫:DEPLOY_FENCE 围栏集单一源(kernel 两侧派生绑定必须
  同等于 cw_line_defs 桥派生集,字面量分叉即红)。

来源指针(2026-09-09 目标形态重建批,断言零改动迁移):
- test_cw_deploy_ops.py(W209 喂入语义;事故 = 线成型板满换阵死锁,
  20260905_noprogress_stop_diag「第三次停机」);
- test_cw_deploy_transition.py(成型臂 victim 序,ADR-0590 决策5);
- test_cw_deploy_pseudo_slot.py(伪槽 kernel 防线);
- test_cw_deploy_single_source.py(N2 围栏单一源,r357 收口口径)。
其余历史锁已退役(git 可复活)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    DEPLOY_FENCE,
    SwapPlanContext,
    select_deployments_reasoned,
    select_swap_plan,
)
from sr_od.application.currency_war.kernel.cw_launch_admission import (
    DEPLOY_FENCE as _LAUNCH_FENCE,
)
from sr_od.application.currency_war.kernel.cw_line_defs import (
    ENGINE_FACTIONS,
    RECIPE_FACTIONS,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
    fenced_swap_arm_of,
    swap_arm_deployed_count,
)


def _bc(name: str, slot: int = 1, star: int = 1) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions[0] if ch.factions else '?'))


# ==================== W209 换阵卖出义务臂喂入语义(自 test_cw_deploy_ops.py 迁入) ====================
# 事故形态(线成型后板满换阵死锁:备战环守卫三环 RunDeploy 单签名停机,
# 详见诊断档案 20260905_noprogress_stop_diag「第三次停机」节):修复后
# 「板满」喂入 = 真部署数(swap_arm_deployed_count),禁羁绊计数总和。

def test_w209_swap_arm_feed_is_deployed_count_not_bond_sum() -> None:
    """live 喂入语义锁(P1 阻断判别):「板满」喂入 = 真部署数
    (deployed_occupied 槽位表计数),禁羁绊计数总和——board 语义 =
    阵营→在场人数,一人多阵营(4 人可 11 阵营次):旧形态喂 sum(board
    .values())=11 ≥ 7 槽 ⇒ 板未满即开臂、不可逆卖出逐环发生;修复后
    喂 4 < 7 ⇒ 不开臂。"""
    board = {'仙舟': 3, '治疗': 2, '列车同行': 3, '战技点': 2, '护盾': 1}
    assert sum(board.values()) == 11, '锁前提:4 人多阵营贡献 11 阵营次'
    tracked = [BenchChar(slot=i + 1, char_id=n, star=1)
               for i, n in enumerate(('丹恒·饮月', '停云', '藿藿', '艾丝妲'))]
    assert swap_arm_deployed_count(board, tracked) == 4
    # 建模对象判别:同一形态下,喂部署数不开臂;喂羁绊总和必开臂(旧病)
    assert fenced_swap_arm_of(1.0, swap_arm_deployed_count(board, tracked),
                              7) is False
    assert fenced_swap_arm_of(1.0, sum(board.values()), 7) is True
    # 边界:tracked 缺失/空 ⇒ 0(缺输入保守侧,不开臂)
    assert swap_arm_deployed_count(board, []) == 0
    assert swap_arm_deployed_count(None, None) == 0
    assert fenced_swap_arm_of(1.0, swap_arm_deployed_count(board, []),
                              7) is False


# ==================== 成型臂 victim 让渡序域外照旧(自 test_cw_deploy_transition.py 迁入) ====================

def test_formed_frame_victim_order_star_key_unchanged() -> None:
    """成型臂域外序照旧锁(ADR-0590 决策5:P79-4 让渡序辖域 = 锁线转型
    域;fp≥1.00 成型臂 victim 序 = 旧 1★ 优先,ADR-0530/0534 语义不动):
    成型帧(fenced_on)双 victim——三月七 1★ 与忘归人 2★(仙舟)——
    若贡献首键误外溢到成型臂域,2★ 会顶掉 1★;锁定旧星级序胜出
    (三月七)。差分构造:两档星级交叉,序判据可区分两种语义。
    夹具升级(T-167 F1/F-2 用例预期更新):bench 换丹恒·饮月(仙舟
    目标视图件)∧ target={'仙舟'}——原希儿(非目标视图件)夹具自 F1
    三合取谓词起落 no_bench_target 弃权(执行面本就跳过该形态,旧计划
    非空 = 幻影),序判据改在可兑现形态上锁;原形态新预期由原文件
    对照臂锁承载(已退役,git 可复活)。"""
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


# ==================== 伪槽 kernel 防线(自 test_cw_deploy_pseudo_slot.py 迁入) ====================

def test_item_slot_held_even_as_target_with_vacancy() -> None:
    """防线强度:is_item_slot=True 即使是 target 件且板面有大量空位,
    仍恒 held(先于一切围栏/cap 判定被拒)。"""
    name = next(n for n, ch in CHARACTERS.items() if ch.factions)
    item = BenchChar(slot=2, char_id=name,
                     faction=CHARACTERS[name].factions[0], is_item_slot=True)
    up, held, reasons = select_deployments_reasoned(
        [item], deployed_cids=set(), deployed_fac={}, board={}, cap=9,
        target_factions=frozenset(CHARACTERS[name].factions))
    assert up == [] and held == [0] and reasons.get(0) == 'item_slot'


# ==================== 围栏集单一源守卫(自 test_cw_deploy_single_source.py 迁入) ====================

def test_fence_set_single_derived_source():
    """围栏集单一源守卫:kernel 存在两个 DEPLOY_FENCE 派生绑定
    (cw_deploy_logic / cw_launch_admission,注释均自称同源)——两者
    必须都等于 cw_line_defs 桥派生集(r357 收口口径)。任一侧被改
    字面量即围栏语义在 kernel 内部分叉(发射准入集 ≠ 执行侧 held
    集),本锁红。"""
    assert frozenset(RECIPE_FACTIONS | ENGINE_FACTIONS) == DEPLOY_FENCE
    assert _LAUNCH_FENCE == DEPLOY_FENCE
