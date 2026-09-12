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

辖域 = 三挂点接线烟雾(容忍档唯一一条,提交面读法)+ 选卡登记挂点
「现役零装备写端条目」依赖方向守卫 + full_state_snapshot equip_progress
捕获行为锁 + 工具回执分派手臂行为锁(特权赋予卡库存腿直写/冶金炉零写
留证/异常不冒泡)。
"""
from __future__ import annotations

import inspect
from pathlib import Path

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    GameState,
    ChannelSig,
    register_sig_actors,
)

register_sig_actors('TestSigWriter')


def _sig() -> ChannelSig:
    """渠道①签名(obs 族;观察构造 GameState 前置态)。"""
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _char_by_cost(cost: int) -> str:
    """从角色注册表按费用取一个稳定代表名(数据在仓,断言可复现)。"""
    names = sorted(n for n, c in CHARACTERS.items() if c.cost == cost)
    assert names, f'注册表缺 cost={cost} 角色(数据面漂移,换锚并同步本注释)'
    return names[0]


# ==================== 1. 挂点接线烟雾(纪律 8 容忍档唯一一条;提交面读法) ====================

def _head_text(rel: str) -> str:
    """主仓 HEAD 提交面文件文本(锚锁辖已提交树形状,工作树在飞批改动
    不进视线——消并行窗口咬红;接线批改挂点随批同笔提交)。"""
    import subprocess

    root = Path(__file__).parents[5]
    return subprocess.run(
        ['git', '-C', str(root), 'show', f'HEAD:{rel}'],
        capture_output=True, check=True).stdout.decode('utf-8')


def _head_method(rel: str, name: str) -> str:
    """HEAD 文本中指定方法的源码切片(到下一个同级 def 为止)。"""
    src = _head_text(rel)
    start = src.index(f'def {name}(')
    end = src.find('\n    def ', start + 1)
    return src[start:end if end != -1 else len(src)]


def test_equipment_wiring_hooks_present() -> None:
    """三挂点接线存在性烟雾(纪律 8 容忍档:本文件唯一一条;四测试收敛
    为此一条——表达式级字面 'diamond_gold=0'/'killed is True' 与聚合链
    在场断言退役,见 docstring 末段承重映射)。提交面读法(git show HEAD)。
    失守事故语义:挂点静默脱落 = 效果账本三载体断供(节点边界金/拷贝仪
    参与/工具效果全零写入),红指向重接线:
    - 节点边界金结算住 cw_loop 备战分支(底稿 = effect-domain.md §7.3,
      指派批报告 reports/T-63-r1.md §⑤.6 为暂记出处,回填义务在案);
    - 拷贝仪参与结算与 on_battle_end 同方法同段(cw_screen_battle_wait
      ._record_round_outcome,同分支同时序契约);
    - 工具执行写端分派住 cw_op_tools 消费回执点。
    参数级契约承重映射:diamond_gold 透传/streak 语义由载体参数锁
    (test_cw_effect_write_carriers 节点边界金族)分侧承重;倍率/息修饰
    聚合链由 test_cw_economy/test_cw_cap_override_link 承重;败局保守闸
    (killed 门)为 cw_loop 调用点参数——调用点住主循环体无廉价驱动面,
    调用侧参数传递行为锁挂账,候 cw_loop 主循环 harness 落位后升级。"""
    loop_src = _head_text(
        'src/sr_od/application/currency_war/operations/cw_loop.py')
    assert 'settle_node_boundary_gold' in loop_src, '节点边界金结算接线脱落'
    rec_src = _head_method(
        'src/sr_od/application/currency_war/operations/cw_screen/'
        'cw_screen_battle_wait.py', '_record_round_outcome')
    assert 'on_battle_end' in rec_src, '既有效果账本结算挂点在位'
    assert 'settle_copy_machine_participation' in rec_src, \
        '拷贝仪参与结算接线被移除或落在结算带之外(同分支同时序契约)'
    tools_src = _head_text(
        'src/sr_od/application/currency_war/operations/cw_op/cw_op_tools.py')
    assert 'apply_tool_execution_write' in tools_src, '工具效果写端分派脱落'


def test_strategy_card_hook_has_zero_equip_write_entries() -> None:
    """选卡登记挂点「现役零装备写端条目」依赖方向守卫(纪律 8 合法源码
    扫描②):装备写端三载体的生命周期映射事件 = 节点推进/工具拖拽回执/
    战斗结算,与选卡落地(INSTANT 登记 + burst/板面重写两桥)零交集——
    三载体符号均不得落选卡登记面。原「既有登记三件在位」正向断言退役:
    register_strategy/burst 与 test_cw_game_state
    .test_effect_hooks_wired_at_production_sites 同事实(纪律 7 择一),
    apply_board_rewrite 由 test_cw_affix_runtime_wiring
    .test_append_confirmed_strategy_applies_board_rewrite 行为锁承重。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_invest_strategy,
    )
    src = inspect.getsource(cw_screen_invest_strategy)
    for marker in ('settle_node_boundary_gold',
                   'apply_tool_execution_write',
                   'settle_copy_machine_participation'):
        assert marker not in src, \
            f'{marker} 不应落在选卡登记挂点(生命周期映射无交集)'


# ==================== 2. 快照捕获行为锁(equip_progress 侧栏) ====================


def test_full_state_snapshot_captures_equip_progress_sidebar() -> None:
    """装备进度侧栏快照捕获(T-63 §⑤.4 缺口一行收口):bump 后快照
    equip_progress 以「装备名|装备者」键形携带计数(元组键 JSON 不安全,
    序列化为竖线串);空侧栏 = 空 dict(行形状稳定);既有 effects 整窗
    键不受影响。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    wearer = _char_by_cost(1)
    bs.effects.bump_equip_progress('数据拷贝仪', wearer)
    snap = bs.full_state_snapshot()
    assert snap['equip_progress'] == {f'数据拷贝仪|{wearer}': 1}
    assert 'effects' in snap, '既有 effects 整窗键不受本批影响'
    # 空侧栏 = 空 dict(行形状稳定,遥测面无键缺位歧义)
    empty = GameState(schema_version=BS_SCHEMA_VERSION).full_state_snapshot()
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
    from sr_od.application.currency_war.kernel.cw_game_state import (
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
