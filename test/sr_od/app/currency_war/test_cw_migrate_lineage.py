"""迁移合并协议·内容锚血缘判定表驱动锁(tools/cw/migrate_telemetry_tree.py)。

被测实现 = 主仓 ``tools/cw/migrate_telemetry_tree.py`` 的
``_lineage_anchor`` + ``_move_or_merge``(纯路径参数 + 注入台账 dict,
零 src 深依赖),经 importlib 按路径装载(先例:test_cw_replay_to_md.py
装载 replay_to_md.py)。

协议语义与三边界修订叙述 = ADR-0586「合并协议内容锚修订」节;同域
姊妹锁 = test_cw_infra_locks(布局单一源守卫 + 旧根墓碑扫描)。本锁
11 case 升格自主仓一份易失验证脚本(随 .debug/temp 批产物生存)——
批报告类出处按 sr-od-test README 纪律 7 须回填仓内永久锁,脚本灭失后
该协议仍有守卫,本文件即回填后的永久载体。

锁面 = 每个合成场景断言终态四元组(动作标记 / dst 字节 / src 存在性 /
台账推进)。case 表三列:场景(三边界 / 防线 / 回归)/ 输入构造(dst
现有字节 + 台账 offset + src 字节,全部 tmp_path 合成,零真实 .debug
写——工具只操作入参路径,不触模块级 _MANIFEST 常量)/ 期望处置。整体
毫秒级,不入慢桶。

已知覆盖边界(登记,不属本锁职责):防线③在 'new' 路径的重叠拒并、
'same' 锚且 size<offset 的越界拒并两分支未单列——均为拒并(fail-safe
方向),与升格源的覆盖面一致。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, NamedTuple

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_TOOL_PATH = _REPO_ROOT / 'tools' / 'cw' / 'migrate_telemetry_tree.py'
_MODULE_NAME = 'cw_migrate_telemetry_tree_tool'


def _load_tool() -> Any:
    """按路径装载被测工具(sys.modules 缓存,跨用例只 exec 一次)。"""
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _TOOL_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


def _lines(*items: bytes) -> bytes:
    """行语料拼接(每行以换行字节收尾;jsonl 追加流的行语义同型)。"""
    return b''.join(ln + b'\n' for ln in items)


# ---- 合成语料常量:case 的输入与期望终态全部由此现推导,禁手抄散值 ----
_OLD3 = _lines(b'old0', b'old1', b'old2')    # 12B 已消费旧化身(台账 offset 同值)
_NEW2 = _lines(b'n0', b'n1')                 # 6B 比记账短的新化身(边界 a)
_NEW3 = _lines(b'x0', b'x1', b'x2')          # 12B 与记账恰等长的新化身(边界 c)
_NEW6 = _lines(b'q0', b'q1', b'q2', b'q3', b'q4', b'q5')  # 24B 长过记账(边界 b)
_GROWN = _OLD3 + _lines(b'old3', b'old4')    # 20B 同源化身接尾增长(回归)
_BLOB_OLD = bytes(range(256)) * 4            # 1024B 二进制(购买留证 webp 同型)
_BLOB_NEW = bytes(reversed(_BLOB_OLD))       # 同尺寸异内容二进制新文件


class MergeCase(NamedTuple):
    """case 表一行 = 场景 / 输入构造 / 期望处置。

    字段语义:offset = 台账记的已消费字节数(None = 台账无 entry,
    走防线①);expect_src_gone = merge 后 src 是否应被 unlink;
    expect_manifest = 台账 entry 终值(None = entry 应不存在——防线①
    拒并从无记账;拒并场景则保持原值不动)。
    """

    scenario: str
    dst_bytes: bytes
    offset: int | None
    src_bytes: bytes
    expect_action: str
    expect_src_gone: bool
    expect_manifest: int | None
    expect_dst: bytes


#: case 表:场景命名保留三边界编号(a=短于记账 / b=长过记账 / c=恰等长),
#: 与 ADR-0586「合并协议内容锚修订」节处置表逐行对照。三种恰巧尺寸的
#: 真新化身(旧化身被搬走后被旧代码进程重建的文件)的处置 = 内容锚
#: 修订的验收面;其余 case 钉防线①②、锚窗不足拒并与二进制/空消费回归。
_MERGE_CASES: tuple[MergeCase, ...] = (
    MergeCase(
        scenario='a1 size<offset 真新化身→整份并入',
        dst_bytes=_OLD3, offset=len(_OLD3), src_bytes=_NEW2,
        expect_action='appended', expect_src_gone=True,
        expect_manifest=len(_NEW2), expect_dst=_OLD3 + _NEW2,
    ),
    MergeCase(
        scenario='c2 size==offset 同源残躯→清理',
        dst_bytes=_OLD3, offset=len(_OLD3), src_bytes=_OLD3,
        expect_action='clean', expect_src_gone=True,
        expect_manifest=len(_OLD3), expect_dst=_OLD3,
    ),
    MergeCase(
        scenario='c3 size==offset 真新化身→整份并入',
        dst_bytes=_OLD3, offset=len(_OLD3), src_bytes=_NEW3,
        expect_action='appended', expect_src_gone=True,
        expect_manifest=len(_NEW3), expect_dst=_OLD3 + _NEW3,
    ),
    MergeCase(
        scenario='b4 size>offset 真新化身→整份并入',
        dst_bytes=_OLD3, offset=len(_OLD3), src_bytes=_NEW6,
        expect_action='appended', expect_src_gone=True,
        expect_manifest=len(_NEW6), expect_dst=_OLD3 + _NEW6,
    ),
    MergeCase(
        scenario='同源接尾回归',
        dst_bytes=_OLD3, offset=len(_OLD3), src_bytes=_GROWN,
        expect_action='appended', expect_src_gone=True,
        expect_manifest=len(_GROWN), expect_dst=_GROWN,
    ),
    MergeCase(
        scenario='防线①台账无记账拒并',
        dst_bytes=_OLD3, offset=None, src_bytes=_NEW3,
        expect_action='refused', expect_src_gone=False,
        expect_manifest=None, expect_dst=_OLD3,
    ),
    MergeCase(
        scenario='防线②撕裂接尾拒并',
        dst_bytes=b'alpha\nbe', offset=8, src_bytes=b'alpha\nbeta\ngamma\n',
        expect_action='refused', expect_src_gone=False,
        expect_manifest=8, expect_dst=b'alpha\nbe',
    ),
    MergeCase(
        scenario='锚窗不足拒并(dst 被外部截短)',
        dst_bytes=b'tiny', offset=100, src_bytes=b'z' * 200,
        expect_action='refused', expect_src_gone=False,
        expect_manifest=100, expect_dst=b'tiny',
    ),
    MergeCase(
        scenario='二进制同源残躯清理',
        dst_bytes=_BLOB_OLD, offset=len(_BLOB_OLD), src_bytes=_BLOB_OLD,
        expect_action='clean', expect_src_gone=True,
        expect_manifest=len(_BLOB_OLD), expect_dst=_BLOB_OLD,
    ),
    MergeCase(
        scenario='二进制同尺寸异内容新件→整份并入',
        dst_bytes=_BLOB_OLD, offset=len(_BLOB_OLD), src_bytes=_BLOB_NEW,
        expect_action='appended', expect_src_gone=True,
        expect_manifest=len(_BLOB_NEW), expect_dst=_BLOB_OLD + _BLOB_NEW,
    ),
    MergeCase(
        scenario='offset=0 空消费后首并→整份并入',
        dst_bytes=b'', offset=0, src_bytes=_NEW3,
        expect_action='appended', expect_src_gone=True,
        expect_manifest=len(_NEW3), expect_dst=_NEW3,
    ),
)


@pytest.mark.parametrize(
    'case', _MERGE_CASES, ids=[c.scenario for c in _MERGE_CASES],
)
def test_merge_lineage_disposition(case: MergeCase, tmp_path: Path) -> None:
    """每场景独立 tmp 沙盘:搭 old/new 双目录跑一次 _move_or_merge,断言
    终态四元组。期望值全部来自 case 表合成输入的推导(台账 offset 用
    len() 现算),无手抄常数;工具不写任何真实 .debug 路径。"""
    mt = _load_tool()
    src = tmp_path / 'old' / 'decisions.jsonl'
    dst = tmp_path / 'new' / 'decisions.jsonl'
    src.parent.mkdir()
    dst.parent.mkdir()
    dst.write_bytes(case.dst_bytes)
    src.write_bytes(case.src_bytes)
    manifest: dict[str, int] = (
        {} if case.offset is None else {'k': case.offset})
    report: list[str] = []
    action = mt._move_or_merge(src, dst, manifest, 'k', report)
    assert action == case.expect_action, f'report={report}'
    assert dst.read_bytes() == case.expect_dst, f'scenario={case.scenario}'
    assert src.exists() is not case.expect_src_gone
    assert manifest.get('k') == case.expect_manifest
