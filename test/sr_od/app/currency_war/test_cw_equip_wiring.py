"""装备写端生产接线批主题锁(T-70:生产挂点一行调用+进度侧栏快照捕获)。

设计出处(持久索引):
- 底稿 = .debug/progress/2026-09-11-cw-clear-run/reports/T-63-r1.md §⑤.6
  (三挂点指派:节点边界金结算→备战分支 advance_node 点/工具分派→工具
  拖拽回执点/拷贝仪参与结算→战斗结算覆盖带 on_battle_end 同分支同时序)
  与 §⑤.4(equip_progress 侧栏快照捕获缺口一行,归接线批);
- 生命周期映射与登记挂点纪律正本 =
  docs/develop/sr_od/application/currency_war/game_state/effect-domain.md §7.3(best-effort
  失败不阻塞主链;新增效果 = 新增规格声明,挂点代码零改动);
- 载体实现单一源 = kernel/cw_effect_inventory.py / cw_affix_effects.py
  (T-51/T-63 交付;载体本体行为锁在 test_cw_effect_write_carriers.py,
  本文件不重复,只锁「生产面调用了它们」的接线形状与快照捕获行)。

辖域 = 三挂点在场锁(cw_loop 备战 tick/cw_screen_battle_wait 结算覆盖带/
cw_op_tools 消费回执)+ 选卡登记挂点「现役零装备写端条目」声明与实物一致
锁 + full_state_snapshot equip_progress 捕获行为锁 + 工具回执分派手臂
行为锁(特权赋予卡库存腿直写/冶金炉零写留证/异常不冒泡)。
"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_board_state import (
    BS_SCHEMA_VERSION,
    BoardState,
    ChannelSig,
    register_sig_actors,
)

register_sig_actors('TestSigWriter')


def _sig() -> ChannelSig:
    """渠道①签名(obs 族;观察构造 BoardState 前置态)。"""
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _char_by_cost(cost: int) -> str:
    """从角色注册表按费用取一个稳定代表名(数据在仓,断言可复现)。"""
    names = sorted(n for n, c in CHARACTERS.items() if c.cost == cost)
    assert names, f'注册表缺 cost={cost} 角色(数据面漂移,换锚并同步本注释)'
    return names[0]


# ==================== 1. 挂点在场锁(接线形状) ====================


def test_node_boundary_settlement_wired_at_prep_tick() -> None:
    """节点边界金结算接线在场:cw_loop 备战分支 tick 块内调用
    settle_node_boundary_gold(T-63 §⑤.6 指定挂点 = 备战分支 advance_node
    点);倍率/息修饰经 aggregate_economy 聚合链(载体 docstring 指派归
    接线批的调用方契约);宝钻透传 0(T-51 逐件进度载体缺位申报维持);
    保守闸(最近结算败局跳过,败补口径 ADR-0623 决策3 待定谳)在场。"""
    from sr_od.application.currency_war.operations import cw_loop
    src = inspect.getsource(cw_loop)
    assert 'settle_node_boundary_gold' in src, '节点边界金结算接线被移除'
    assert 'aggregate_economy' in src, \
        '倍率/息修饰聚合链缺失(调用方契约 = aggregate_economy)'
    assert 'diamond_gold=0' in src, \
        '宝钻逐件进度载体缺位透传 0(申报面)缺失'
    assert 'killed is True' in src, \
        '败局保守闸缺失(败补口径待定谳,该窗须维持观察覆盖兜底)'


def test_copy_machine_settlement_wired_at_battle_settlement_band() -> None:
    """拷贝仪参与计数接线在场:cw_screen_battle_wait 结算覆盖带调用
    settle_copy_machine_participation,与 on_battle_end 挂点同分支同时序
    (同一 _record_round_outcome 非 telemetry_only 段;独立 best-effort)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait,
    )
    rec_src = inspect.getsource(
        cw_screen_battle_wait.CwScreenBattleWait._record_round_outcome)
    assert 'on_battle_end' in rec_src, '既有效果账本结算挂点在位'
    assert 'settle_copy_machine_participation' in rec_src, \
        '拷贝仪参与结算接线被移除或落在结算带之外(同分支同时序契约)'


def test_tool_execution_write_wired_at_drag_receipt() -> None:
    """工具执行写端分派接线在场:cw_op_tools 消费确认(consumed)回执点
    调用 apply_tool_execution_write(T-63 §⑤.6 指定挂点 = 工具拖拽回执
    点);手臂方法在 CwOpTools 上,回执闭包内发起。"""
    from sr_od.application.currency_war.operations.cw_op import cw_op_tools
    mod_src = inspect.getsource(cw_op_tools)
    assert 'apply_tool_execution_write' in mod_src, '工具效果写端分派被移除'
    consume_src = inspect.getsource(cw_op_tools.CwOpTools.tools_consume)
    assert '_apply_tool_effect_write' in consume_src, \
        '回执点未发起分派(挂点须在 consumed 确认闭包内)'


def test_strategy_card_hook_has_zero_equip_write_entries() -> None:
    """选卡登记挂点「现役零装备写端条目」声明与实物一致:装备写端三载体
    的生命周期映射事件 = 节点推进/工具拖拽回执/战斗结算,与选卡落地
    (INSTANT 登记 + burst/板面重写两桥)零交集——三载体符号均不得落
    选卡登记面;既有登记三件不因本批扰动。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy,
    )
    src = inspect.getsource(cw_screen_invest_strategy)
    for marker in ('settle_node_boundary_gold',
                   'apply_tool_execution_write',
                   'settle_copy_machine_participation'):
        assert marker not in src, \
            f'{marker} 不应落在选卡登记挂点(生命周期映射无交集)'
    for marker in ('register_strategy', 'apply_effect_burst_grant',
                   'apply_board_rewrite'):
        assert marker in src, f'既有选卡登记挂点件 {marker} 被误删'


# ==================== 2. 快照捕获行为锁(equip_progress 侧栏) ====================


def test_full_state_snapshot_captures_equip_progress_sidebar() -> None:
    """装备进度侧栏快照捕获(T-63 §⑤.4 缺口一行收口):bump 后快照
    equip_progress 以「装备名|装备者」键形携带计数(元组键 JSON 不安全,
    序列化为竖线串);空侧栏 = 空 dict(行形状稳定);既有 effects 整窗
    键不受影响。"""
    bs = BoardState(schema_version=BS_SCHEMA_VERSION)
    wearer = _char_by_cost(1)
    bs.effects.bump_equip_progress('数据拷贝仪', wearer)
    snap = bs.full_state_snapshot()
    assert snap['equip_progress'] == {f'数据拷贝仪|{wearer}': 1}
    assert 'effects' in snap, '既有 effects 整窗键不受本批影响'
    # 空侧栏 = 空 dict(行形状稳定,遥测面无键缺位歧义)
    empty = BoardState(schema_version=BS_SCHEMA_VERSION).full_state_snapshot()
    assert empty['equip_progress'] == {}


# ==================== 3. 工具回执分派手臂行为锁 ====================


class _StubSession:
    """裸桩 session(board_state_of 惰性挂对象属性,生命周期随对象)。"""


def _plan(tool: str, target: str) -> object:
    from sr_od.application.currency_war.operations.cw_op.cw_op_tools import (
        ToolDragPlan,
    )
    return ToolDragPlan(action='any', tool=tool, target=target,
                        tool_pos=(1, 1), target_pos=(2, 2))


def test_tool_receipt_dispatch_privilege_inventory_leg() -> None:
    """特权赋予卡 consumed 回执 → 分派库存腿:bs.equips 中目标进阶件
    原位变换为·特权(logic 写);冶金炉回执 = 负写端观察收口零写留证
    (write_seq 不动);session None 防御零动作;分派炸错被吞不冒泡
    (best-effort,失败不阻塞执行主链)。"""
    from sr_od.application.currency_war.kernel.cw_board_state import (
        board_state_of,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_op_tools import (
        CwOpTools,
    )
    op = CwOpTools.__new__(CwOpTools)   # 跳过 __init__(本臂不依赖 ctx)

    sess = _StubSession()
    bs = board_state_of(sess)
    bs.observe(bs.equips, ['生命之环', '特权赋予卡'], sig=_sig())
    op._apply_tool_effect_write(sess, _plan('特权赋予卡', '生命之环'))
    assert bs.equips.value == ['生命之环·特权', '特权赋予卡']
    assert bs.equips.source == 'logic'

    sess_furn = _StubSession()
    bs_furn = board_state_of(sess_furn)
    bs_furn.observe(bs_furn.equips, ['生命之环'], sig=_sig())
    seq0 = bs_furn.write_seq
    op._apply_tool_effect_write(sess_furn, _plan('冶金炉', '生命之环'))
    assert bs_furn.write_seq == seq0, '冶金炉 = 负写端,零逻辑写留证'

    op._apply_tool_effect_write(None, _plan('特权赋予卡', '生命之环'))  # 防御
    op._apply_tool_effect_write(sess, _plan('非在册工具名', '生命之环'))  # 吞炸
