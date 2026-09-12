"""RunNode 历史抽象退役批:行为等价锁(用户裁决:按新架构统一)。

RunSupplyNode → CwScreenSupplyNode(cw_screen/cw_screen_supply_node.py)、
RunMegastarNode → CwScreenMegastar 内联(委托壳废止)。本文件锁迁移前后的
**行为断言一致**:①验证完成才 success(离开节点画面)(原 ADR-0264 关态
基线预置断言随 gate 模块退役删除,见 test_supply_leaves_node_success 注);
②仍在节点内 = 做动作 + round_retry(计 node_max_retry_times=8 预算,
超限框架转 FAIL 交回——预算语义不变);③源码零残留(基类/包路径)。
"""
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fixtures.masked_scan import (
    MaskedSource,
    build_masked_sources,
    find_violations,
    scan_code_violations,
)


def _make_op(cls, *, in_node: bool, do_action_calls: list):
    """构画面 op 桩(bypass __init__):round_by_find_area 程序化回 in_node。"""

    class _FakeArea:
        def __init__(self, ok: bool): self.is_success = ok

    class _Op(cls):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self.last_screenshot = object()
            self.op_name = cls.__name__
            self.ctx = SimpleNamespace(cw_match=None)

        def round_by_find_area(self, scr, screen, area, **k):
            return _FakeArea(in_node)

        def _do_action(self, screen):
            do_action_calls.append(1)

        def round_success(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait, success=True)

        def round_retry(self, status='', wait: float = 0):
            return SimpleNamespace(status=status, wait=wait, success=None,
                                   _retry=True)

        def round_fail(self, status=''):
            return SimpleNamespace(status=status, success=False)

        def save_screenshot(self, prefix=None):
            return ''

    return _Op()

# ==================== 补给节点流转(行为等价①②) ====================

def test_supply_leaves_node_success() -> None:
    """验证完成才 success:离开补给屏(锚 miss)→ success(节点完成)。
    (gate 清尾批:原「+关态稳定基线预置」断言随 gate 模块退役删除。)"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    actions: list = []
    op = _make_op(CwScreenSupplyNode, in_node=False, do_action_calls=actions)
    res = op.handle()
    assert res.success is True
    assert '节点完成' in res.status
    assert actions == []                       # 离开节点 = 不再发动作


def test_supply_in_node_act_then_retry() -> None:
    """仍在补给屏 → 做一个动作 + round_retry(计节点预算;不 success)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    actions: list = []
    op = _make_op(CwScreenSupplyNode, in_node=True, do_action_calls=actions)
    res = op.handle()
    assert actions == [1]                      # 每轮恰好一个动作
    assert getattr(res, '_retry', False) is True


def test_supply_budget_semantics_unchanged() -> None:
    """预算语义不变:node_max_retry_times=8(原 RunNode 子类口径,
    超限框架转 FAIL bail 交回)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )
    node = CwScreenSupplyNode.handle.operation_node_annotation
    assert node.node_max_retry_times == 8


# ==================== 巨星流转(行为等价①②) ====================

def test_megastar_leaves_node_success_with_settle() -> None:
    """巨星:overlay 消失 → success(完成承诺 = 固定 1.0s,原委托壳语义)
    (选中标记复位副作用随迁)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_flow_const import (
        CW_OVERLAY_SETTLE_S,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    actions: list = []
    op = _make_op(CwScreenMegastar, in_node=False, do_action_calls=actions)
    res = op.handle()
    assert res.success is True
    assert res.wait == CW_OVERLAY_SETTLE_S
    assert actions == []


def test_megastar_in_node_act_then_retry() -> None:
    """巨星:仍在 overlay → 一个动作 + round_retry。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    actions: list = []
    op = _make_op(CwScreenMegastar, in_node=True, do_action_calls=actions)
    res = op.handle()
    assert actions == [1]
    assert getattr(res, '_retry', False) is True


def test_megastar_budget_semantics_unchanged() -> None:
    """预算语义不变:node_max_retry_times=8(原 RunNode 子类口径)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_megastar import (
        CwScreenMegastar,
    )
    node = CwScreenMegastar.handle.operation_node_annotation
    assert node.node_max_retry_times == 8


# ==================== 零残留 ====================

# 掩蔽式扫描器(T-103 迁移;T-107 起改引公共单一源 fixtures/masked_scan.py,
# 手法定型版 = 测试仓 commit 149f86b,三处内联已收敛):注释/docstring 在源
# 文本上按字符等长置空后对代码文本跑正则。「RunNode 已退役」类负向声明是
# 退役背书而非活引用,置空后不误红;代码域引用(标识符/字符串字面量)仍在
# 域内,防复活。tokenize/ast 失败回退原文全判(宁误红)。变异自检直扫共享
# 实现。


#: 生产树扫描根(绝对化,不随 cwd 漂移)。
_CW_SRC_ROOT: Path = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
                      / 'application' / 'currency_war')


@pytest.fixture(scope='module')
def _masked_sources() -> tuple[MaskedSource, ...]:
    """零残留锁共享掩蔽语料(module 级)。

    跨文件共享机制(进程内缓存,与 old_stream/infra_locks 扫描锁共用
    currency_war 根同一份构建)= fixtures.masked_scan.build_masked_sources。
    """
    return build_masked_sources(_CW_SRC_ROOT)


#: 零残留扫描正则(基类名/包路径;字面子串,无正则元字符)。
_RUNNODE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r'RunNode'), re.compile(r'run_nodes'))
_RUNNODE_LABELS: tuple[str, ...] = ('RunNode', 'run_nodes')


def test_runnode_zero_residue_in_src(
        _masked_sources: tuple[MaskedSource, ...]) -> None:
    """grep 零残留:currency_war src 下无 RunNode 基类/run_nodes 包路径的
    活引用(sim/telemetry 注释中的旧类名 RunSupplyNode 不含 RunNode 子串,
    且按纪律不动)。

    判定域 = 掩蔽代码域(T-103 迁移,机制见 fixtures.masked_scan):
    「RunNode 已退役」类负向声明(注释/docstring)不判红——退役背书而非
    活引用;代码域标识符/字符串字面量引用仍判红,防复活。"""
    assert not (_CW_SRC_ROOT / 'operations' / 'run_nodes').exists(), \
        'run_nodes/ 包应已删除'
    violations: list[str] = []
    for src in _masked_sources:
        for lineno, snippet, pi in find_violations(
                src.masked, *_RUNNODE_PATTERNS):
            violations.append(
                f'{src.path}:{lineno} 残留 {_RUNNODE_LABELS[pi]}: {snippet}')
    assert not violations, 'RunNode 活引用残留(防复活):\n' + '\n'.join(violations)


def test_runnode_scan_mutation_selfcheck() -> None:
    """掩蔽式扫描变异自检(双向):负向声明不判红,代码域引用仍判红。

    防两种回归:①豁免写宽(注释/docstring 未置空即跳过整行)→ 真实引用
    漏判;②豁免失效(回退逐行原文)→「RunNode 已退役」负向声明误红复发。
    合成语料直扫 scan_code_violations,不落生产树。"""
    # 豁免腿:注释/docstring 中的负向声明与历史提及不得判红
    assert scan_code_violations(
        '# RunNode 基类已退役(按新架构统一,禁复活)', *_RUNNODE_PATTERNS) == []
    assert scan_code_violations(
        '"""RunNode 历史抽象退役批:run_nodes 包路径已删除。"""',
        *_RUNNODE_PATTERNS) == []
    # 检出腿:代码域标识符/字符串字面量必须判红(防复活)
    hits = scan_code_violations('class RunNode(SrOperation):',
                                 *_RUNNODE_PATTERNS)
    assert len(hits) == 1 and hits[0][2] == 0, f'类定义复活形须红,实得 {hits}'
    hits = scan_code_violations("pkg = 'operations.run_nodes'",
                                 *_RUNNODE_PATTERNS)
    assert len(hits) == 1 and hits[0][2] == 1, f'包路径字面量复活形须红,实得 {hits}'
    # 混合腿:行尾注释不吞同行代码引用(豁免按 token 置空,不按行)
    hits = scan_code_violations(
        '_legacy = RunNode  # RunNode 已退役(负向声明)', *_RUNNODE_PATTERNS)
    assert len(hits) == 1, f'行尾注释不豁免同行代码,实得 {hits}'
    # 跨 token 复合形:引用与注释隔行相邻,掩蔽只吞注释行不吞引用行
    hits = scan_code_violations(
        'from x import RunNode\n# RunNode 已退役\ny = 1', *_RUNNODE_PATTERNS)
    assert len(hits) == 1 and hits[0][0] == 1, \
        f'隔行注释掩蔽不吞引用行,实得 {hits}'
