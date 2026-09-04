"""货币战争包布局守卫(分包重构 DESIGN §3.2/§2;期5 补遗 T3)。

三件守卫,锁「结构」不锁「形状」(行数/行段不入断言):
1. 桶依赖矩阵:包内全部 import 边(含根包属性式按符号解析)必须落在 §3.2 矩阵
   合法向内(唯一历史豁免边 decision→strategy_v1 已随买层接管批消亡,ADR-0477)。
2. 桶成员完备:包内每个 .py 模块必须解析到已声明桶,不允许 '?' 盲区(scan_v2
   教训:盲区 = 守卫不可见,新文件落错位置时矩阵锁会假绿)。
3. 包根顶层布局:包根只允许已声明的桶子目录 + app/tools 壳文件(结构契约;
   新增顶层文件 = 改本守卫的清单并说明归属,防根包再堆积)。

桶清单 = DESIGN §2 归类表(单一源);改动归类须同改本文件三张表。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

_PKG_DIR = _REPO / 'src' / 'sr_od' / 'application' / 'currency_war'
_PKG = 'sr_od.application.currency_war'

# ---- 桶结构表(路径前缀 → 桶;与 DESIGN §2 一致)----
BUCKET_DIRS: dict[str, str] = {
    'data': 'data',
    'kernel': 'kernel',
    'obs': 'obs',
    'sim': 'sim',
    'telemetry': 'telemetry',
    'operations': 'app',
    'strategies': 'strategies',   # 策略注册壳+impl 实现本体(策略统一迁移批;顶层壳可注册,impl 子包 manager 扫描忽略)
    'tools': 'tools',
    'knowledge': 'knowledge',   # 处死计划批 0 知识层符号包(redesign/03 批 0)
}

# 包根散置文件 → 桶(app/tools 壳;新增须入册)
ROOT_FILES: dict[str, str] = {
    'currency_war_app': 'app',
    'currency_war_app_factory': 'app',
    'currency_war_config': 'app',
    'currency_war_const': 'app',
    'currency_war_run_record': 'app',
    'decision_assembly': 'app',
    'prep_actions': 'app',
    'cw_screen_prep': 'app',
    'run_state': 'app',
    # 轻量画面状态判定(模块 docstring:仿 sim_uni_screen_state;只依赖
    # one_dragon 框架原语,供上层兜底 op 复用对局中判定单一源)——归属 app 桶
    # (与 run_state 同类:运行态/判定辅助,非 data/kernel 纯层)。
    'cw_screen_state': 'app',
}

# DESIGN §3.2 目标依赖矩阵(期6 §4.4 ledger_hooks 归属)
LEGAL_EDGES: dict[str, set[str]] = {
    'data': set(),
    'kernel': {'data', 'knowledge'},   # knowledge = 批 0 迁出符号的权威副本(数据半部)
    # strategies = 策略注册壳(顶层)+ impl 实现本体(纯逻辑:接口基类/
    # 主流程驱动核/mandate_v1 机器)。impl 只依 data/kernel;顶层壳依 app
    # 桶 decision_assembly(装配缝 obs→Snapshot,adapter 分拆先例)。
    'strategies': {'data', 'kernel', 'app'},   # decision 注册壳已随 v2 退役批物理删除,死许可同步清(2026-09-03)
    'obs': {'data', 'kernel'},
    'sim': {'data', 'kernel', 'telemetry', 'strategies'},
    'telemetry': {'data', 'kernel', 'obs', 'sim', 'knowledge'},
    'app': {'data', 'kernel', 'obs', 'sim', 'telemetry', 'tools',
            'strategies'},
    'tools': {'data', 'kernel', 'obs', 'sim', 'telemetry', 'app'},
    # knowledge(批 0 符号包)= 数据/纯函数叶子包:自身只读 data/kernel 注册表;
    # kernel/telemetry 保留层消费其迁出符号(消费边按批 0 实际接线登记)。
    'knowledge': {'data', 'kernel'},
}


def _module_name(path: Path) -> tuple[str, str]:
    """(包内相对模块名, 所属桶); '__init__' 归父目录名。"""
    rel = path.relative_to(_PKG_DIR).with_suffix('')
    parts = rel.parts
    mod = '.'.join(parts) if parts[-1] != '__init__' else '.'.join(parts[:-1])
    if parts[0] in BUCKET_DIRS:
        return mod, BUCKET_DIRS[parts[0]]
    return mod, ROOT_FILES.get(mod, '??')


def _scan_edges() -> dict[tuple[str, str], list[str]]:
    """桶级 import 边 → 边来源明细(语义同 scan_v3:含函数级 import 与
    根包属性式按被导入符号逐个解析,不留盲区)。"""
    edges: dict[tuple[str, str], list[str]] = {}
    for f in sorted(_PKG_DIR.rglob('*.py')):
        me, src_b = _module_name(f)
        if me == '':
            continue   # 包根 __init__
        text = f.read_text(encoding='utf-8')
        for m in re.finditer(r'^\s*(?:from|import)\s+(.+)', text, re.M):
            stmt = m.group(1).strip()
            mm = re.match(r'([\w.]+)\s*(?:import\s+(.+))?$', stmt)
            if not mm:
                continue
            target, names = mm.group(1), mm.group(2)
            if not (target == _PKG or target.startswith(_PKG + '.')):
                continue
            mod = target[len(_PKG) + 1:] if target != _PKG else ''
            ln = text[:m.start()].count('\n') + 1
            where = f'{me}:{ln}'
            if mod == '':
                if not names:
                    continue
                for nm in names.split(','):
                    nm = nm.strip().split(' as ')[0].strip()
                    if not nm:
                        continue
                    dst_b = ROOT_FILES.get(nm, BUCKET_DIRS.get(nm, '??'))
                    if dst_b != src_b:
                        edges.setdefault((src_b, dst_b), []).append(
                            f'{where} root-attr {nm}')
            else:
                head = mod.split('.')[0]
                dst_b = (BUCKET_DIRS.get(head)
                         or ROOT_FILES.get(head) or ROOT_FILES.get(mod) or '??')
                if dst_b != src_b:
                    edges.setdefault((src_b, dst_b), []).append(f'{where} {mod}')
    return edges


def test_bucket_dependency_matrix() -> None:
    """守卫 1:全部桶级 import 边落在 §3.2 矩阵(无豁免边)。"""
    bad = []
    for (a, b), detail in _scan_edges().items():
        if a == b or a == '??' or b == '??':
            continue   # 盲区由守卫 2 单独起诉
        if b in LEGAL_EDGES.get(a, set()):
            continue
        bad.append(f'{a}->{b}: ' + '; '.join(detail[:5]))
    assert not bad, '违规桶依赖边(合法矩阵见 LEGAL_EDGES):\n' + '\n'.join(bad)


def test_bucket_membership_complete() -> None:
    """守卫 2:包内每个 .py 模块都解析到已声明桶(禁 '?' 盲区)。"""
    unknown = [str(f.relative_to(_PKG_DIR))
               for f in sorted(_PKG_DIR.rglob('*.py'))
               if _module_name(f)[1] == '??' and f.name != '__init__.py']
    assert not unknown, '未归桶模块(落错位置或桶表缺册):\n' + '\n'.join(unknown)


def test_package_root_layout() -> None:
    """守卫 3:包根顶层 = 声明的桶子目录 + app/tools 壳文件(结构契约)。"""
    actual = sorted(f.stem for f in _PKG_DIR.iterdir() if f.suffix == '.py'
                    and f.name != '__init__.py')
    extra = [n for n in actual if n not in ROOT_FILES]
    missing_dirs = [d for d in BUCKET_DIRS if not (_PKG_DIR / d).is_dir()]
    assert not extra, f'包根出现未入册顶层文件(改 ROOT_FILES 并声明归属):{extra}'
    assert not missing_dirs, f'声明的桶子目录缺失:{missing_dirs}'
    # 根包 __init__ 保持空壳(不暴露模块;项目硬约束)
    init = (_PKG_DIR / '__init__.py').read_text(encoding='utf-8').strip()
    assert init == '', '包根 __init__ 应为空壳,不得承载导入面'
