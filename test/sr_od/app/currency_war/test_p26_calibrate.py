"""P26 标定脚本自测接入 pytest(三审修复任务书必修3)。

背景:`tools/cw/proofs/p26/p26_calibrate.py` 的 ``--selftest`` 分支
原本不进测试仓——分位 CI95 取生成序重采样值而非排序百分位的 bug
正是经该漏网面溜进「候用户裁」链的。本文件把它接进快速集:

- ``test_selftest_pass``:整体跑脚本自验(临时目录合成数据,零真实
  副作用,不写 .debug),覆盖分桶/CI/删失/质量门/join 对账/报告;
- ``test_quantile_ci95_sorted_percentile_lock``:分位 CI95 排序百分位
  锁(必修2 的独立钉死)——有序合成样本 {10,20,30,40} 四局各一值,
  期望值由排序百分位定义解析可查(列 2.5% 分位=最小可达值 10/20,
  97.5%=最大可达值 40)。守卫移除属性:恢复旧取法(生成序第
  50/1949 个重采样值)对本样本给 p50=[20,30]、p75=[40,40],即红。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[5]
_TOOL = _REPO / 'tools' / 'cw' / 'proofs' / 'p26' / 'p26_calibrate.py'


def _load_tool():
    """按文件路径加载标定脚本模块(工具不在任何包内,无包导入路径)。"""
    src = str(_REPO / 'src')
    if src not in sys.path:
        sys.path.insert(0, src)
    spec = importlib.util.spec_from_file_location('p26_calibrate', _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selftest_pass() -> None:
    """脚本整体自验直跑(合成数据,零真实副作用)。"""
    assert _load_tool()._selftest() == 0


def test_quantile_ci95_sorted_percentile_lock() -> None:
    """分位 CI95 = 逐分位列 sort 后百分位;旧取法(生成序取值)即红。"""
    mod = _load_tool()
    qc = mod.quantile_ci95({'A': [10], 'B': [20], 'C': [30], 'D': [40]})
    assert qc == {'p50': [10, 40], 'p75': [20, 40],
                  'p90': [20, 40], 'p95': [20, 40]}, qc


def test_quantile_ci95_degenerate_single_run() -> None:
    """单局一桶不估 CI(聚类重抽 <2 局无意义),诚实返回空。"""
    assert _load_tool().quantile_ci95({'only': [1.0, 2.0]}) == {}
