"""operation_flow 静态提取与渲染的单元测试。

锁的设计约定(镜像 ``Operation._analyse_node_annotations`` /
``_init_network`` / ``_get_next_node`` 的运行时语义):
- ``ignore_status`` 静态归一:status 边不被标兜底(裸赋值归一在
  ``OperationEdge.__init__``);
- 断名边(from 悬空)不计入度 / 不参与 BFS / 不进 ``←入:`` 计数,
  ``edges[]`` 垫底、挂 to 节点侧 ``←✗`` 呈现;
- 兜底边生效是双模语义:无 status 返回时首条生效、带 status 返回且无
  匹配时末条生效(``_get_next_node`` 的 break 与 final 覆盖两分支);
- 同名双显式起点归 ``duplicate_node_name`` 不报 ``multiple_start``
  (运行时判定条件 ``start_node.cn != node.cn`` 放过同名)。

fake op 类全部定义在本文件内(真装饰器),零实例化、零副作用。
"""
import sys
import types

import pytest

from one_dragon.base.operation.application_base import Application
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_edge import node_from
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from sr_od.backend import operation_registry
from sr_od.backend.operation_flow import (
    describe_operation_flow,
    extract_operation_flow,
)
from sr_od.backend.operation_registry import scan_operations
from sr_od.backend.schemas import OperationInfo, OperationListResult


class _FakeNormalFlow(Operation):
    """正常提取样本:多分支 / status 边 / 兜底边 / 汇聚点 / 环。

    方法名字母序(battle < choose_team < choose_times < settle < transport)
    即注解扫描序,边构建序 = 方法字母序 × 方法内装饰器自下而上。
    """

    @node_from(from_name='选择配队', success=False)
    @node_from(from_name='选择配队')
    @operation_node(name='战斗', node_max_retry_times=2)
    def battle(self) -> OperationRoundResult:
        return None

    @node_from(from_name='传送', status='跳过传送')
    @node_from(from_name='选择次数')
    @operation_node(name='选择配队')
    def choose_team(self) -> OperationRoundResult:
        return None

    @node_from(from_name='传送')
    @operation_node(name='选择次数', timeout_seconds=30.0)
    def choose_times(self) -> OperationRoundResult:
        return None

    @node_from(from_name='战斗')
    @operation_node(name='结算')
    def settle(self) -> OperationRoundResult:
        return None

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        return None


class _FakeDanglingEdges(Operation):
    """断名边样本:from 悬空挂 to 侧,不计入度 / 不进 ``←入:`` 计数 / 垫底。"""

    @node_from(from_name='幽灵来源', status='坏状态')
    @node_from(from_name='传送')
    @operation_node(name='选择配队')
    def choose_team(self) -> OperationRoundResult:
        return None

    @node_from(from_name='幽灵来源2')
    @node_from(from_name='传送', status='直达')
    @operation_node(name='结束')
    def finish(self) -> OperationRoundResult:
        return None

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        return None


class _FakeDanglingAutoStart(Operation):
    """断名边不计入度:唯一节点仍自动判定为起点,不误报 no_start。"""

    @node_from(from_name='幽灵')
    @operation_node(name='唯一')
    def only(self) -> OperationRoundResult:
        return None


class _FakeDuplicateName(Operation):
    """重复节点名 + 同名双显式起点:归 duplicate_node_name,不报 multiple_start。"""

    @operation_node(name='处理', is_start_node=True)
    def handle_a(self) -> OperationRoundResult:
        return None

    @node_from(from_name='处理')
    @operation_node(name='处理', is_start_node=True)
    def handle_b(self) -> OperationRoundResult:
        return None


class _FakeMultipleStart(Operation):
    """不同名显式双起点。"""

    @operation_node(name='甲', is_start_node=True)
    def a(self) -> OperationRoundResult:
        return None

    @operation_node(name='乙', is_start_node=True)
    def b(self) -> OperationRoundResult:
        return None


class _FakeNoStart(Operation):
    """环图零起点:报 no_start 且不逐节点报 unreachable。"""

    @node_from(from_name='乙')
    @operation_node(name='甲')
    def a(self) -> OperationRoundResult:
        return None

    @node_from(from_name='甲')
    @operation_node(name='乙')
    def b(self) -> OperationRoundResult:
        return None


class _FakeUnreachable(Operation):
    """孤岛节点:显式起点存在时不进自动起点判定,报 unreachable。"""

    @operation_node(name='孤岛')
    def island(self) -> OperationRoundResult:
        return None

    @node_from(from_name='起点')
    @operation_node(name='中转')
    def mid(self) -> OperationRoundResult:
        return None

    @operation_node(name='起点', is_start_node=True)
    def start(self) -> OperationRoundResult:
        return None


class _FakeDupFallbackMixed(Operation):
    """同方向多条兜底边(末条异目标):双模生效 message 按构建序指认首末。"""

    @node_from(from_name='传送')
    @node_from(from_name='传送')
    @operation_node(name='甲')
    def go_a(self) -> OperationRoundResult:
        return None

    @node_from(from_name='传送')
    @operation_node(name='乙')
    def go_b(self) -> OperationRoundResult:
        return None

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        return None


class _FakeDupFallbackSameTarget(Operation):
    """同方向同目标冗余兜底边:目标相同无路径丢失。"""

    @node_from(from_name='传送')
    @node_from(from_name='传送')
    @operation_node(name='甲')
    def go_a(self) -> OperationRoundResult:
        return None

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        return None


class _FakeFallbackByDirection(Operation):
    """成功/失败各一条兜底边:按方向分组不冲突,零诊断。"""

    @node_from(from_name='传送', success=False)
    @node_from(from_name='传送')
    @operation_node(name='甲')
    def go_a(self) -> OperationRoundResult:
        return None

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        return None


class _FakeEdgeOnNonNode(Operation):
    """边挂在未装饰方法上:边被丢弃(镜像运行时 continue 分支)+ warn。"""

    @node_from(from_name='传送')
    def not_a_node(self) -> OperationRoundResult:
        return None

    @node_from(from_name='传送')
    @operation_node(name='下一步')
    def next_step(self) -> OperationRoundResult:
        return None

    @operation_node(name='传送', is_start_node=True)
    def transport(self) -> OperationRoundResult:
        return None


class _FakeQuoteEscape(Operation):
    """mermaid 转义样本:label / 边标注内的英文双引号替换全角。"""

    @node_from(from_name='幽灵"源"', status='带"引号"状态')
    @operation_node(name='落点"引号"')
    def target(self) -> OperationRoundResult:
        return None


class _FakeAppFlow(Application):
    """Application 子类样本:类级提取对 app 同样成立(app 是编排重灾区)。"""

    @node_from(from_name='准备')
    @operation_node(name='收尾')
    def finish(self) -> OperationRoundResult:
        return None

    @operation_node(name='准备', is_start_node=True)
    def prepare(self) -> OperationRoundResult:
        return None


def _codes(result: dict) -> list[str]:
    return [d['code'] for d in result['diagnostics']]


# ===== 正常图提取(结构 / 文本图 / mermaid)=====

def test_extract_normal_flow_structure() -> None:
    """BFS 执行序、字段透传、ignore_status 归一(status 边不误标兜底)。"""
    flow = extract_operation_flow(_FakeNormalFlow)
    assert flow['start_node'] == '传送'
    assert flow['node_count'] == 5
    assert flow['edge_count'] == 6
    assert flow['mermaid'] is None
    # BFS 序:从起点按出边构建序首次发现,不按字母序
    assert [(n['cn'], n['method']) for n in flow['nodes']] == [
        ('传送', 'transport'), ('选择配队', 'choose_team'),
        ('选择次数', 'choose_times'), ('战斗', 'battle'), ('结算', 'settle')]
    assert all(n['reachable'] for n in flow['nodes'])
    assert flow['nodes'][0]['is_start_node'] is True
    assert flow['nodes'][3]['node_max_retry_times'] == 2
    assert flow['nodes'][2]['timeout_seconds'] == 30.0
    # edges 序:from 节点 BFS 序 × 组内构建序
    assert [(e['from'], e['to']) for e in flow['edges']] == [
        ('传送', '选择配队'), ('传送', '选择次数'),
        ('选择配队', '战斗'), ('选择配队', '战斗'),
        ('选择次数', '选择配队'), ('战斗', '结算')]
    status_edge = flow['edges'][0]
    assert status_edge['status'] == '跳过传送'
    # 归一锚点:desc.ignore_status 裸值 True,归一后 status 边必为 False
    assert status_edge['ignore_status'] is False
    assert all(e['ignore_status'] is True for e in flow['edges'][1:])
    assert flow['diagnostics'] == []


def test_extract_normal_flow_text() -> None:
    """flow 文本图:头部摘要 + 图例、边标注记号、←入: 仅入边>=2 标注。"""
    flow = extract_operation_flow(_FakeNormalFlow)
    lines = flow['flow'].splitlines()
    assert '_FakeNormalFlow' in lines[0]
    assert '5节点 6边 · 起点=传送' in lines[0]
    assert lines[1].startswith('# 图例:')
    assert '[起点] 传送 (method=transport)' in lines
    assert '  ├─(成功·status=跳过传送)→ 选择配队' in lines
    assert '  └─(兜底·成功)→ 选择次数' in lines
    assert '  └─(兜底·失败)→ 战斗' in lines
    # 汇聚点列来源(按来源节点 BFS 序);单入边节点不标
    assert '选择配队 (method=choose_team) ←入: 传送, 选择次数' in lines
    assert '选择次数 (method=choose_times)' in lines
    # 入边 >=2 触发标注(两条入边同来源也计),来源去重
    assert '战斗 (method=battle) ←入: 选择配队' in lines
    assert '结算 (method=settle) [终点]' in lines


def test_extract_normal_flow_mermaid() -> None:
    """mermaid 渲染:引号 label / 引号边标注 / classDef / BFS 序编号。"""
    flow = extract_operation_flow(_FakeNormalFlow, mermaid=True)
    lines = flow['mermaid'].splitlines()
    assert lines[0] == 'flowchart TD'
    assert '  n1["传送"]:::start' in lines
    assert '  n1 -->|"成功·status=跳过传送"| n2' in lines
    assert '  n1 -->|"兜底·成功"| n3' in lines
    assert '  classDef start fill:#c8e6c9' in lines
    assert '  classDef unreachable stroke:#e53935,stroke-dasharray:5 5' in lines
    assert '  classDef missing fill:#ffcdd2' in lines


# ===== 诊断各 code =====

def test_diag_missing_node() -> None:
    """missing_node:error 级,message 带悬空来源名与指向节点。"""
    result = extract_operation_flow(_FakeDanglingEdges)
    assert _codes(result) == ['missing_node', 'missing_node']
    first = result['diagnostics'][0]
    assert first['level'] == 'error'
    assert '幽灵来源' in first['message']
    assert '选择配队' in first['message']


def test_diag_duplicate_node_name_absorbs_same_name_starts() -> None:
    """同名双显式起点归 duplicate_node_name,不报 multiple_start。"""
    result = extract_operation_flow(_FakeDuplicateName)
    assert _codes(result) == ['duplicate_node_name']
    message = result['diagnostics'][0]['message']
    assert '处理' in message and 'handle_a' in message and 'handle_b' in message
    # 起点仍可判定(同名覆盖语义),nodes 靠 method 区分全保留
    assert result['start_node'] == '处理'
    assert [n['method'] for n in result['nodes']] == ['handle_a', 'handle_b']


def test_diag_multiple_start() -> None:
    """不同名显式多起点:multiple_start 且 start_node=None。"""
    result = extract_operation_flow(_FakeMultipleStart)
    assert _codes(result) == ['multiple_start']
    message = result['diagnostics'][0]['message']
    assert '甲' in message and '乙' in message
    assert result['start_node'] is None


def test_diag_no_start_without_unreachable_spam() -> None:
    """环图零起点:no_start 时不逐节点报 unreachable,由 reachable 表达。"""
    result = extract_operation_flow(_FakeNoStart)
    assert _codes(result) == ['no_start']
    assert result['start_node'] is None
    assert all(n['reachable'] is False for n in result['nodes'])
    # 起点缺失退化为 cn 字母序全列(乙 < 甲)
    assert [n['cn'] for n in result['nodes']] == ['乙', '甲']
    assert '起点=无' in result['flow'].splitlines()[0]


def test_diag_unreachable_node() -> None:
    """孤岛节点:不可达 warn;显式起点存在时不进自动起点判定。"""
    result = extract_operation_flow(_FakeUnreachable)
    assert _codes(result) == ['unreachable_node']
    assert result['diagnostics'][0]['level'] == 'warn'
    assert '孤岛' in result['diagnostics'][0]['message']
    assert result['start_node'] == '起点'
    # 不可达垫底
    assert result['nodes'][-1]['cn'] == '孤岛'
    assert result['nodes'][-1]['reachable'] is False
    assert '[不可达]' in result['flow']


def test_diag_duplicate_fallback_edge_dual_mode() -> None:
    """兜底边冗余:双模 message(首条/末条按构建序),同目标注明无路径丢失。"""
    mixed = extract_operation_flow(_FakeDupFallbackMixed)
    messages = [d['message'] for d in mixed['diagnostics']
                if d['code'] == 'duplicate_fallback_edge']
    assert len(messages) == 1
    assert '3 条兜底边' in messages[0]
    assert '第 1 条生效（→甲）' in messages[0]
    assert '最后 1 条生效（→乙）' in messages[0]
    assert '目标相同无路径丢失' not in messages[0]

    same = extract_operation_flow(_FakeDupFallbackSameTarget)
    messages = [d['message'] for d in same['diagnostics']
                if d['code'] == 'duplicate_fallback_edge']
    assert len(messages) == 1
    assert '目标相同无路径丢失' in messages[0]

    # 不同方向的兜底边运行时先被 success 过滤,不构成冲突
    assert 'duplicate_fallback_edge' not in _codes(
        extract_operation_flow(_FakeFallbackByDirection))


def test_diag_edge_on_non_node() -> None:
    """边挂非节点方法:warn 且边不进图(镜像运行时静默丢弃)。"""
    result = extract_operation_flow(_FakeEdgeOnNonNode)
    assert _codes(result) == ['edge_on_non_node']
    assert 'not_a_node' in result['diagnostics'][0]['message']
    assert len(result['edges']) == 1


# ===== 断名边图论口径 =====

def test_dangling_edge_graph_semantics() -> None:
    """断名边:不计入度 / 不进 ←入: 计数 / edges[] 垫底 / 挂 to 侧呈现。"""
    result = extract_operation_flow(_FakeDanglingEdges, mermaid=True)
    # 断名边不进 ←入: 计数(选择配队业务入边 1 条 + 断名 1 条,仍不标注)
    assert '选择配队 (method=choose_team) [终点] ←✗不存在的来源「幽灵来源」(成功·status=坏状态)' \
        in result['flow'].splitlines()
    assert '←入:' not in result['flow']
    # edges[] 断名垫底且 from=None
    assert [e['from'] for e in result['edges']] == ['传送', '传送', None, None]
    # mermaid 幽灵来源虚拟节点标红,断名边垫底输出
    m_lines = result['mermaid'].splitlines()
    assert '  n4["✗「幽灵来源」"]:::missing' in m_lines
    assert '  n5["✗「幽灵来源2」"]:::missing' in m_lines
    assert '  n4 -->|"成功·status=坏状态"| n2' in m_lines


def test_dangling_edge_not_counted_for_start() -> None:
    """断名边不计入度:唯一节点不被断名入边指成非起点,no_start 零误报。"""
    result = extract_operation_flow(_FakeDanglingAutoStart)
    assert result['start_node'] == '唯一'
    assert 'no_start' not in _codes(result)


def test_mermaid_quote_escape() -> None:
    """mermaid 转义:label / 幽灵名 / 边标注内英文双引号替换全角;flow 不转义。"""
    result = extract_operation_flow(_FakeQuoteEscape, mermaid=True)
    m_lines = result['mermaid'].splitlines()
    assert '  n1["落点＂引号＂"]:::start' in m_lines
    assert '  n2["✗「幽灵＂源＂」"]:::missing' in m_lines
    assert '  n2 -->|"成功·status=带＂引号＂状态"| n1' in m_lines
    assert '←✗不存在的来源「幽灵"源"」(成功·status=带"引号"状态)' in result['flow']


def test_empty_base_class_no_diagnostics() -> None:
    """零节点基类:不做起点判定,零诊断(节点由子类提供,从不单独运行)。"""

    class _EmptyBase(Operation):
        def handle(self) -> OperationRoundResult:
            return None

    result = extract_operation_flow(_EmptyBase)
    assert result['diagnostics'] == []
    assert result['start_node'] is None
    assert result['nodes'] == []


# ===== 解析层(完整 op_id / 短名 / ambiguous)=====

_REAL_FULL = 'sr_od.operations.move.get_rid_of_stuck.GetRidOfStuck'
_REAL_SHORT = 'GetRidOfStuck'
# 同名假类的两个承载模块(动态注册进 sys.modules,收尾必须移除——进程级全局)
_FAKE_MODS = ('test_flow_fake_pkg.a', 'test_flow_fake_pkg.b')
_AMBIGUOUS_NAME = 'FakeAmbiguousFlowOp'


def _install_ambiguous_scan(monkeypatch) -> list[str]:
    """注册同名假类到两个假模块并 patch 扫描结果,返回两个假 op_id。"""
    operations = []
    for mod_name in _FAKE_MODS:
        mod = types.ModuleType(mod_name)
        cls = type(_AMBIGUOUS_NAME, (Operation,), {'__module__': mod_name})
        setattr(mod, _AMBIGUOUS_NAME, cls)
        sys.modules[mod_name] = mod
        operations.append(OperationInfo(
            op_id=f'{mod_name}.{_AMBIGUOUS_NAME}',
            class_name=_AMBIGUOUS_NAME,
            module=mod_name,
        ))
    fake = OperationListResult(operations=operations, failures=[])
    monkeypatch.setattr(
        operation_registry, 'scan_operations',
        lambda _ctx, refresh=False: fake)
    return [o.op_id for o in operations]


def test_resolve_full_op_id_real_class() -> None:
    """完整 op_id 解析真实类:只断结构键齐(不锁真实节点/边内容)。"""
    flow = describe_operation_flow(_REAL_FULL)
    for key in ('op_id', 'class_name', 'module', 'start_node', 'node_count',
                'edge_count', 'flow', 'mermaid', 'nodes', 'edges',
                'diagnostics', 'notes'):
        assert key in flow
    assert flow['op_id'] == _REAL_FULL
    assert flow['mermaid'] is None
    assert isinstance(flow['flow'], str)


def test_resolve_invalid_op_id_raises() -> None:
    """非法 op_id:核心层 raise(ValueError),MCP/HTTP 适配层再转 {error}。"""
    with pytest.raises(ValueError):
        describe_operation_flow('no.such.module.NoSuchOp')


def test_resolve_short_name_unique() -> None:
    """短名唯一命中:op_id 回填完整形态。"""
    flow = describe_operation_flow(_REAL_SHORT)
    assert flow['op_id'] == _REAL_FULL


def test_resolve_ambiguous_returns_candidates(monkeypatch) -> None:
    """短名多命中:轻量 ambiguous 形态(只列候选 op_id,不带参数 schema)。"""
    fake_ids = _install_ambiguous_scan(monkeypatch)
    try:
        result = describe_operation_flow(_AMBIGUOUS_NAME)
    finally:
        for mod_name in _FAKE_MODS:
            sys.modules.pop(mod_name, None)
    assert result['ambiguous'] is True
    assert result['count'] == 2
    assert sorted(result['candidates']) == sorted(fake_ids)
    assert 'matches' not in result


# ===== 全量回归(scan_operations 全部 op 零 error 诊断)=====

@pytest.fixture(scope='module')
def _full_scan_op_ids() -> list[str]:
    """扫描一次全量 op(慢计算只算一次,本模块全部断言共享)。"""
    return [o.op_id for o in scan_operations(None).operations]


def test_full_regression_zero_error(_full_scan_op_ids: list[str]) -> None:
    """全量回归:全部可运行 op 静态提取零 error 级诊断。

    编排错误(断名边/重复名/多起点/零起点)从「运行期才炸」变成
    「改完跑测试即炸」——error 级与运行时 raise 一一对应;warn 级
    (不可达/兜底冗余)存量允许,不在断言内。
    """
    offenders: list[str] = []
    for op_id in _full_scan_op_ids:
        result = describe_operation_flow(op_id)
        errors = [d['code'] for d in result['diagnostics']
                  if d['level'] == 'error']
        if errors:
            offenders.append(f'{op_id}: {", ".join(errors)}')
    assert not offenders, '存在编排错误(运行时必炸):\n' + '\n'.join(offenders)


# ===== Application 子类可达(类直入,不走解析层)=====

def test_application_class_extractable() -> None:
    """Application 子类经类直入提取:与裸 op 同结构(app 是编排重灾区)。"""
    result = extract_operation_flow(_FakeAppFlow)
    assert result['start_node'] == '准备'
    assert result['node_count'] == 2
    assert result['edge_count'] == 1
    assert result['diagnostics'] == []
