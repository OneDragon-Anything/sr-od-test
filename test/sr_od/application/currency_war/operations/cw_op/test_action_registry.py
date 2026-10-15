"""CW 动作词表与分派注册表测试面。

单一源:备战词表与坐标系裁定 = kernel/cw_vocab.py 模块头(现役声明与
全类居所);动作 → op 分派 = operations/cw_op/cw_action_registry.py
(单一表一键一行;域依赖经 env 结构化传入,op-layer.md §1.2)。

测试面四组(全部运行时行为测试,源码扫描测试禁止,AGENTS.md §10.4):
1. **键粒度**(幂等键消费 = cw_screen_prep 重派/对账去重):行为参数
   入键(变化 → 键变 = 幂等键分裂);发射臂路由标签不入键;容器下标
   字段构成键面;
2. **执行器 F3 白名单行为**:词表外类型拒(参数非法路径,Director
   交回外循环留证),在册动作合法域放行;
3. **终结集 ⟺ 注册表 terminal 属性逐一等价**:备战环终结集四类
   terminal=True、备战机械动作全部非终结、terminal_wait 同源比对
   (禁消费点私表);开店注册行 = terminal 承载行,执行抛 AssertionError
   (防静默复活,流程编排归画面 op 流程层);
4. **注册完备**:统一词表逐类断言注册表类级解析可命中(豁免成员反向
   断言确无注册行,防误挂 op = 确认链字段错位暗雷);pick 行类级/
   实例级解析一致;is-a 兜底语义与实例查询一致;词表外响亮暴露。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    CwActionCollectOreParam,
    CwActionDeployMoveParam,
    CwActionFurnaceUseParam,
    CwActionLevelUpParam,
    CwActionLevelUpShopParam,
    CwActionLuckyTokenUseParam,
    CwActionObsParam,
    CwActionOpenBookcardParam,
    CwActionOpenBoxParam,
    CwActionOpenShopParam,
    CwActionOpenTomeParam,
    CwActionPickBoxCardParam,
    CwActionPickEncounterParam,
    CwActionPickExpertInviteParam,
    CwActionPickFortuneParam,
    CwActionPickInvestEnvParam,
    CwActionPickInvestStrategyParam,
    CwActionPickMegastarParam,
    CwActionPickPartnerParam,
    CwActionPickPlannerParam,
    CwActionPickStarTomeParam,
    CwActionPickSupplyParam,
    CwActionPickWishTrialParam,
    CwActionRefreshInvestCardsParam,
    CwActionRefreshNodeOptionsParam,
    CwActionRefreshSupplyParam,
    CwActionSellBenchParam,
    CwActionSellDeployedParam,
    CwActionStartBattleParam,
    CwActionWearEquipParam,
    CwActionWrenchUseParam,
    action_key,
)
from sr_od.application.currency_war.operations.cw_op.cw_action_registry import (
    action_op_class_for,
    action_op_class_for_type,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_bookcard_action import (
    CwActionOpenBookcardOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_box_action import (
    CwActionOpenBoxOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_shop_action import (
    CwActionOpenShopOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_box_card_action import (
    CwActionPickBoxCardOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_encounter_action import (
    CwActionPickEncounterOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_expert_invite_action import (
    CwActionPickExpertInviteOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_fortune_action import (
    CwActionPickFortuneOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_invest_action import (
    CwActionPickInvestOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_megastar_action import (
    CwActionPickMegastarOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_partner_action import (
    CwActionPickPartnerOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_planner_action import (
    CwActionPickPlannerOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_star_tome_action import (
    CwActionPickStarTomeOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_supply_action import (
    CwActionPickSupplyOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_wish_trial_action import (
    CwActionPickWishTrialOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_prep_level_up_action import (
    CwActionLevelUpOp,
)
from sr_od.application.currency_war.prep_actions import (
    _OVERLAY_ANIM_WAIT_S,
)
from sr_od.operations.sr_operation import SrOperation

# 终态契约动作类型的注册豁免集(终态契约 landing 测试规格:白名单成员
# 要么有注册行、要么在豁免集——无 op 行例外申报):三刷新动作
# (handler 自管点击链;attack4 M6 裁定 (a):同型豁免)。
# (HoldFrame 曾在豁免集,随 2026-09-20 用户裁定收编进
#  CwActionObsParam(scope='outer_loop') 删除;7 pick 类已随
#  pick-op-unify 批收编入表——豁免集现形 = 三刷新动作。)
_TERMINAL_CONTRACT_REGISTRY_EXEMPT = (
    CwActionRefreshNodeOptionsParam,
    CwActionRefreshSupplyParam,
    CwActionRefreshInvestCardsParam,
)


# ============================================================ 1. 键粒度

def test_action_key_faces_pinned_per_class():
    """逐类键粒度钉死(词表归一硬判据「改名与字段合并不得漂移键粒度」,
    持久索引见模块头;幂等键消费 = cw_screen_prep 重派/对账去重):
    - 行为参数入键(变化 → 键变 = 幂等键分裂);
    - 发射臂路由标签不入键(同槽不同 tag = 同一动作实例);
    - 容器下标字段(bench_idx/deployed_idx)构成键面(替换物理槽位字段)。
    (原「键串 = 归一前族A 形态逐字」腿降规格:逐字 repr 校验的是 Python
    repr 格式,过度规格,消费面只需键稳定性与粒度。)"""
    # CwActionSellBenchParam:行为参数分裂幂等键;route_tag(发射臂路由标签)不入键
    assert action_key(CwActionSellBenchParam(bench_idx=3)) != \
        action_key(CwActionSellBenchParam(bench_idx=0))
    assert action_key(CwActionSellBenchParam(bench_idx=0, route_tag='m4_fuel_sell')) == \
        action_key(CwActionSellBenchParam(bench_idx=0))
    assert 'bench_idx' in action_key(CwActionSellBenchParam(bench_idx=0))
    # CwActionLevelUpParam:cost 与 auth_basis 入键(键粒度零漂移锚,禁静默改 metadata)
    assert action_key(CwActionLevelUpParam(cost=4)) != action_key(CwActionLevelUpParam(cost=5))
    assert action_key(CwActionLevelUpParam(cost=4, auth_basis='arm1')) != \
        action_key(CwActionLevelUpParam(cost=4))
    assert 'cost' in action_key(CwActionLevelUpParam(cost=4))
    # CwActionDeployMoveParam/CwActionSellDeployedParam:容器下标字段替换物理槽位字段,键形态同构
    assert 'bench_idx' in action_key(CwActionDeployMoveParam(bench_idx=1, to_row='front',
                                                to_slot=1, faction=''))
    assert 'deployed_idx' in action_key(CwActionSellDeployedParam(deployed_idx=0))


# ============================================================ 2. F3 白名单行为

def test_prep_f3_rejects_unknown_and_admits_registered():
    """执行器 F3 白名单 = 统一词表元组的行为半:词表外类型拒(参数非法
    路径,Director 交回外循环留证),在册动作合法域放行。"""
    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._bench_pts = [Point(i * 10, i * 10) for i in range(9)]
    ex._front_pts = [Point(i * 10, i * 10) for i in range(4)]
    ex._back_pts = [Point(i * 10, i * 10) for i in range(6)]
    assert ex.validate(SimpleNamespace()) is not None   # 词表外 → 拒
    assert ex.validate(CwActionSellBenchParam(bench_idx=0)) is None   # 在册 → 合法


def test_open_bookcard_registered_and_validated():
    """CwActionOpenBookcardParam 在统一词表白名单 + F3 静态参数域
    (漏登记先例 CwActionOpenTomeParam:漏登记时执行面 validate 拒
    「未知动作类型」,动作从未真正执行);参数域与
    CwActionOpenBoxParam/CwActionOpenTomeParam 同形(slot=None 或
    1..备战栏槽位)。"""
    assert CwActionOpenBookcardParam in CW_ACTION_TYPES
    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor.__new__(pa.PrepActionExecutor)
    ex._bench_pts = [Point(i * 10, i * 10) for i in range(9)]
    assert ex.validate(CwActionOpenBookcardParam()) is None
    assert ex.validate(CwActionOpenBookcardParam(slot=9)) is None
    err = ex.validate(CwActionOpenBookcardParam(slot=10))
    assert err is not None and '越界' in err


# ============================================================ 3. 终结集 ⟺ 注册表

def _op_cls(action):
    return action_op_class_for(action)


def test_prep_terminal_set_matches_registry_terminal_attrs():
    """备战环终结集 = {CwActionStartBattleParam, CwActionOpenShopParam,
    CwActionOpenBoxParam, CwActionOpenBookcardParam}(R7 并入
    CwActionOpenBoxParam;2026-09-19 用户裁定开卡时机归策略器,
    OpenBookcard 终结化——弹专家邀请函 = 新事实,交回外循环重观察)
    ⟺ 注册表 op 类 terminal=True,逐一等价;备战机械动作全部非终结。
    terminal_wait 同源比对:OpenBoxOp/OpenBookcardOp =
    ``_OVERLAY_ANIM_WAIT_S``(落地交回等待常量对象,漂移即红,禁消费点
    私表);StartBattleOp 交回节奏见其类注(现状等价测试 = 本终结集测试)。"""
    terminal_cases = [
        CwActionStartBattleParam(),
        CwActionOpenShopParam(),
        CwActionOpenBoxParam(),
        CwActionOpenBookcardParam(),
    ]
    for a in terminal_cases:
        assert _op_cls(a).terminal is True, type(a).__name__
    assert CwActionOpenBoxOp.terminal_wait == _OVERLAY_ANIM_WAIT_S
    assert CwActionOpenBookcardOp.terminal_wait == _OVERLAY_ANIM_WAIT_S
    mechanical_cases = [
        CwActionSellBenchParam(bench_idx=0),
        CwActionSellDeployedParam(deployed_idx=0),
        CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=1,
                                faction=''),
        CwActionWearEquipParam(item_name='轮滑鞋', char_name='刃', row='front', slot=1),
        CwActionCollectOreParam(points=((1, 2),)),
        CwActionOpenTomeParam(),
        CwActionLevelUpParam(cost=4),
        CwActionLevelUpShopParam(cost=4),
        CwActionFurnaceUseParam(target_kind='char', row='front', slot=1),
        CwActionWrenchUseParam(row='front', slot=1),
        CwActionLuckyTokenUseParam(row='front', slot=1),
        CwActionObsParam(),   # 环内重观察:非终结(执行后决策环原地续跑)
    ]
    for a in mechanical_cases:
        assert _op_cls(a).terminal is False, type(a).__name__


def test_open_shop_row_is_terminal_carrier_and_execute_loud_fails():
    """CwActionOpenShopOp = terminal 承载行:注册表解析可命中;执行抛
    AssertionError(防静默复活)——CwActionOpenShopParam 流程编排归画面
    op 流程层(cw_screen_prep._act_execute_default → _open_shop_phase),
    注册行在正常路径不可达,可达即分派漏斗被绕过。"""
    op = CwActionOpenShopOp(SimpleNamespace(), CwActionOpenShopParam(),
                            env=SimpleNamespace())
    with pytest.raises(AssertionError):
        op.run()


# ============================================================ 4. 注册完备

def test_registry_covers_unified_vocab_and_pick_types():
    """注册完备测试(主判据;终态契约 §2.2 收敛单表):统一词表
    CW_ACTION_TYPES 单表逐类断言注册表**类级**解析可命中(不构造业务
    动作实例,不读源码)——未注册 = 测试红;退役 = 删类,元组中不存在即
    天然不可复活(R1)。kernel EVENT_PICK_TYPES = 纯函数返回载体,策略
    产出词表化后不再进注册表面(§2.2)。

    终态契约扩展(landing):白名单新成员要么有注册行、要么在豁免集;
    豁免成员反向断言确无注册行(防误注册,误挂 op = 确认链字段错位
    暗雷)。"""
    for cls in CW_ACTION_TYPES:
        if cls in _TERMINAL_CONTRACT_REGISTRY_EXEMPT:
            with pytest.raises(AssertionError):
                action_op_class_for_type(cls)
            continue
        op_cls = action_op_class_for_type(cls)
        assert isinstance(op_cls, type) and issubclass(op_cls, SrOperation), \
            f'{cls.__name__} 解析产物非 SrOperation 子类: {op_cls}'
    for cls in _TERMINAL_CONTRACT_REGISTRY_EXEMPT:
        assert cls in CW_ACTION_TYPES, cls.__name__


def test_pick_rows_resolve_class_and_instance_consistently():
    """pick 行收编面(终态契约 §2.2 换键名:策略器产出 = 词表子类型;
    pick-op-unify 批起分批扩至全 12 类):类级解析与实例级工厂解析同
    op 类(行序 is-a 语义一致;实例级仅本测试构造,注册完备测试本体不
    构造)。"""
    rows = [
        (CwActionPickEncounterParam, CwActionPickEncounterOp),
        (CwActionPickSupplyParam, CwActionPickSupplyOp),
        (CwActionPickMegastarParam, CwActionPickMegastarOp),
        (CwActionPickPartnerParam, CwActionPickPartnerOp),
        (CwActionPickPlannerParam, CwActionPickPlannerOp),
        (CwActionPickInvestEnvParam, CwActionPickInvestOp),   # 投资两屏拆类:两行同指一 op
        (CwActionPickInvestStrategyParam, CwActionPickInvestOp),
        (CwActionPickFortuneParam, CwActionPickFortuneOp),
        (CwActionPickWishTrialParam, CwActionPickWishTrialOp),
        (CwActionPickStarTomeParam, CwActionPickStarTomeOp),
        (CwActionPickBoxCardParam, CwActionPickBoxCardOp),
        (CwActionPickExpertInviteParam, CwActionPickExpertInviteOp),
    ]
    for cls, expected in rows:
        assert action_op_class_for_type(cls) is expected, cls.__name__


def test_class_level_isa_fallback_matches_instance_query():
    """is-a 兜底语义同注册表:CwActionLevelUpShopParam is-a
    CwActionLevelUpParam,类级首中 CwActionLevelUpParam 行 →
    PrepLevelUpOp,与实例级查询一致。"""
    assert action_op_class_for_type(CwActionLevelUpShopParam) is CwActionLevelUpOp
    assert action_op_class_for_type(CwActionLevelUpParam) is CwActionLevelUpOp


def test_unknown_type_loud_at_class_level():
    """词表外类型 = 类级解析 AssertionError 响亮暴露(ADR-0517 决策 9
    语义,禁静默跳过)。"""

    class _NotVocab:
        pass

    with pytest.raises(AssertionError):
        action_op_class_for_type(_NotVocab)
