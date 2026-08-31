"""PrepAction 白名单完备性回归(r15 review P0-① 的测试防线)。

策略层可发出的全部 PrepAction 子类 ⊆ PREP_ACTION_TYPES——防「新动作漏登记」
(OpenTome 曾漏,fc888bc1 加类漏白名单 → 从未真正执行,M55 414 次全 validate 拒绝)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

import sr_od.application.currency_war.kernel.cw_prep_actions as pa_mod  # noqa: E402
from sr_od.application.currency_war.kernel.cw_prep_actions import (  # noqa: E402
    PREP_ACTION_TYPES,
    PrepAction,
)


def _all_prep_subclasses() -> set[type]:
    """prep_actions 模块内定义的全部 PrepAction 具体子类。"""
    return {obj for _, obj in vars(pa_mod).items()
            if isinstance(obj, type)
            and issubclass(obj, PrepAction)
            and obj is not PrepAction
            and obj.__module__ == pa_mod.__name__}


def test_whitelist_covers_all_prep_subclasses() -> None:
    """模块内全部 PrepAction 子类都在白名单(新动作漏登记 = 此测试红)。"""
    subs = _all_prep_subclasses()
    assert subs, ' PrepAction 子类发现失败(模块扫描空)'
    missing = subs - set(PREP_ACTION_TYPES)
    assert not missing, (
        f'动作漏登记白名单(将 never-execute): {sorted(m.__name__ for m in missing)}')


def test_opentome_registered() -> None:
    """OpenTome 回归锚(P0-① 直接用例)。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import OpenTome
    assert OpenTome in PREP_ACTION_TYPES
