"""调用点 kwarg 名 ↔ 被调签名 静态对拍锁(kwarg 错传病族回归资产,W63)。

背景(2026-08-25 实锤):``@operation_node(node_name='处理策划事件')`` 用了不存在的
keyword,而框架签名是 ``name=`` —— TypeError 在 import 期爆,但该 handler 是惰性
import,常规测试不触发,存活 6 天才被 MCP ``list_operations`` 暴露。病根 = 调用点
参数名无静态校验(Python 语言特性);修根 = 静态锁进测试网:每次跑测试即对拍全仓
调用点 keyword 名与被调签名形参集,防同型地雷再次存活。

- 扫描器本体:``sr-od-test/kwarg_audit/scanner.py``(测试仓,可 commit;仓库根
  ``.debug/temp/currency_war/cw_dev/kwarg_audit.py`` 重跑脚本引用它,单一源);
- 断言:全仓违规数 == 0(白名单过滤后);白名单只承载「人工确认的合法转发」或
  「已裁决暂缓的已知遗留项」,每条必须带豁免原因;
- 白名单自维护:条目若已不再对应真实违规(被修掉了)→ 本测试红,提示删条目;
- 性能:全仓 AST 扫描 < 30s(实测 ~1s,纯 AST 零 import 副作用为主路径)。
"""
from __future__ import annotations

from pathlib import Path

from kwarg_audit.scanner import run_audit

#: 仓库根 = sr-od-test/test/ 上溯 2 级(sr-od-test 是独立测试仓,位于仓库根下)
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / 'src'

#: 白名单 { (相对仓库根 posix 路径, 行号, kwarg 名): 豁免原因 }
#: 只两类可入:
#:   ① 扫描器静态不可见但运行时**合法**的转发(如 singledispatchmethod 重载 /
#:      TypedDict 等——这些已由扫描器处理,此表只作兜底);
#:   ② 已裁决**暂缓**的已知遗留违规(非合法转发!)——必须写明裁决归属与处置
#:      路径;白名单不是洗白,裁决前违规同步在 W63 报告与进度树追踪。
#: (首条 convert_screen_info 死代码已于 e17574b5 删除,条目随之清空。)
WHITELIST: dict[tuple[str, int, str], str] = {}

#: 全仓扫描耗时上限(秒)。纯 AST 主路径 ~1s,给足余量。
SCAN_TIME_LIMIT_S = 30.0


def test_kwarg_call_sites_match_signatures() -> None:
    """全仓调用点 keyword 名必须 ∈ 被调签名形参集(白名单过滤后 == 0)。"""
    result = run_audit(SRC_ROOT, whitelist=set(WHITELIST))
    assert result.elapsed_seconds < SCAN_TIME_LIMIT_S, (
        f'全仓 AST 扫描超时: {result.elapsed_seconds:.1f}s '
        f'(上限 {SCAN_TIME_LIMIT_S}s)'
    )
    assert result.violation_count == 0, (
        f'调用点 kwarg 名与签名不符 {result.violation_count} 处'
        f'(完整报告: uv run python .debug/temp/currency_war/cw_dev/kwarg_audit.py)\n'
        + '\n'.join(
            f'  {v.file}:{v.line}:{v.col}  {v.callee}  kwarg={v.kwargs}  | {v.snippet}'
            for v in result.violations[:20]
        )
    )


def test_whitelist_entries_still_apply() -> None:
    """白名单自维护:每条豁免必须仍对应一个真实违规(修掉后应删条目,不是留着)。

    先做无白名单的原始扫描,再逐条核对:白名单条目 (file, line, kwarg) 必须出现在
    原始违规里;且被豁免的 kwarg 数量不得超过原始违规数(防条目漂移)。
    """
    result = run_audit(SRC_ROOT)  # 不带白名单
    raw = {(v.file, v.line, kw) for v in result.violations for kw in v.kwargs}
    stale = [key for key in WHITELIST if key not in raw]
    assert not stale, (
        '白名单条目已过期(对应违规已被修复)——请删除以下条目,而不是留着:\n'
        + '\n'.join(f'  {key}: {WHITELIST[key]}' for key in stale)
    )


def test_audit_stats_sanity() -> None:
    """扫描覆盖面快照(量级护栏,防扫描器退化漏扫)。"""
    result = run_audit(SRC_ROOT)
    assert result.files_scanned > 800, f'扫描文件数异常少: {result.files_scanned}'
    assert result.kw_call_nodes > 5000, (
        f'含 keyword 调用点异常少: {result.kw_call_nodes}'
    )
    assert result.resolved_ok > 3000, f'解析成功数异常少: {result.resolved_ok}'
