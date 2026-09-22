"""RunNode 历史抽象退役批:行为等价锁(用户裁决:按新架构统一)。

RunSupplyNode → CwScreenSupplyNode(cw_screen/cw_screen_supply_node.py)、
RunMegastarNode → CwScreenMegastar 内联(委托壳废止)。本文件锁迁移前后的
**行为断言一致**:①验证完成才 success(离开节点画面)(原 ADR-0264 关态
基线预置断言随 gate 模块退役删除,见 test_supply_leaves_node_success 注);
②仍在节点内 = 做一个动作 + 循环推进轮次(两屏均两 node 形态,迭代
2026-09-18-screen-op-flat-report:决策动作 node round_wait 推进,不计节点
重试预算,无防御上限)。

恢复分诊:原文件第③腿「源码零残留掩蔽扫描」(fixtures.masked_scan
+ test_runnode_zero_residue_in_src / test_runnode_scan_mutation_selfcheck)
不恢复——源码扫描形态(AGENTS §10.4.4 退役符号墓碑禁令),且其公共单一源
fixtures/masked_scan.py 已随 09-13 清理(1cc1958b)删除;退役防复活跃责归
review 与代码规范,行为腿 6 锁照常守护流转语义。
"""
from types import SimpleNamespace


def _make_op(cls, *, in_node: bool, do_action_calls: list):
    """构画面 op 桩(bypass __init__):round_by_find_area 程序化回 in_node。

    ``_do_action`` 形参收窄为可选(补给现役体传 screen / 盛会之星两 node
    形态动作体零参——桩只记调用,不绑签名)。"""

    class _FakeArea:
        def __init__(self, ok: bool): self.is_success = ok

    class _Op(cls):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self.last_screenshot = object()
            self.op_name = cls.__name__
            self.ctx = SimpleNamespace(cw_match=None)

        def round_by_find_area(self, scr, screen, area, **k):
            return _FakeArea(in_node)

        def _do_action(self, screen=None):
            do_action_calls.append(1)

        def round_success(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait, success=True)

        def round_retry(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait, success=None,
                                   _retry=True)

        def round_wait(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait, success=None,
                                   _wait=True)

        def round_fail(self, status=''):
            return SimpleNamespace(status=status, success=False)

        def save_screenshot(self, prefix=None):
            return ''

    return _Op()

# ==================== 补给节点流转(行为等价①②) ====================

def test_supply_node_flow_act_wait_then_success() -> None:
    """补给流转两段(行为等价①②,两 node 形态):仍在补给屏 → 决策动作
    node 恰一个动作 + round_wait(不计节点重试预算,无防御上限);锚 miss
    (离开节点画面)→ success(验证完成才 success,不再发动作)。
    (gate 清尾批:原「+关态稳定基线预置」断言随 gate 模块退役删除。)"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    actions: list = []
    op = _make_op(CwScreenSupplyNode, in_node=True, do_action_calls=actions)
    res = op.act()
    assert actions == [1]                      # 每轮恰好一个动作
    assert getattr(res, '_wait', False) is True   # 循环推进 = round_wait
    actions2: list = []
    op2 = _make_op(CwScreenSupplyNode, in_node=False,
                   do_action_calls=actions2)
    res2 = op2.act()
    assert res2.success is True
    assert '节点完成' in res2.status
    assert actions2 == []                       # 离开节点 = 不再发动作


# ==================== 巨星流转(行为等价①②) ====================

def test_megastar_node_flow_act_wait_then_success() -> None:
    """巨星流转两段(两 node 形态,迭代 2026-09-18-screen-op-flat-report):
    仍在 overlay → 决策动作 node 恰一个动作 + round_wait(不计节点重试
    预算;无防御上限);overlay 消失 → success(完成承诺 = 固定 settle
    时长;选中标记复位副作用随 ``_in_node`` 复检迁)。夹具 = 对局内
    (match 带 gs):局外 = 零决策零点击 round_success 交回(正本
    op-layer.md §1.1「画面 op 不支持局外单独调用」),其语义归
    test_cw_obs_arch_event_screens 巨星局外交回锁;本锁只辖流转形态。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_flow_const import (
        CW_OVERLAY_SETTLE_S,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    actions: list = []
    op = _make_op(CwScreenMegastar, in_node=True, do_action_calls=actions)
    op.ctx = SimpleNamespace(cw_match=SimpleNamespace(gs=object()))
    res = op.act()
    assert actions == [1]                      # 每轮恰好一个动作
    assert getattr(res, '_wait', False) is True   # 循环推进 = round_wait
    actions2: list = []
    op2 = _make_op(CwScreenMegastar, in_node=False,
                   do_action_calls=actions2)
    res2 = op2.act()
    assert res2.success is True
    assert res2.wait == CW_OVERLAY_SETTLE_S
    assert actions2 == []                       # 离开节点 = 不再发动作
