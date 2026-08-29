"""r91 pivot 冷却不变量测试:任意两次 pivot 之间至少间隔冷却轮,无例外。

不变量单一入口 = maybe_pivot 函数顶(所有信号路径必经)。锁两个历史漏洞形态:
①r87 H2:信号3保命 with_progress 路径翻转后,同轮再调应被拦;
②r90c:危机豁免绕过调用侧冷却门(or 短路)→ 同轮两翻(第12局 p2r7 实证)。
"""
from pathlib import Path

from sr_od.application.currency_war.kernel import cw_comps
from sr_od.application.currency_war.kernel.cw_comps import maybe_pivot
from sr_od.application.currency_war.kernel.cw_state import GameState

_ROOT = Path(__file__).resolve().parents[4]


class _Sess:
    """假 session:只带 pivot_cooldown_until(守卫读取的唯一字段)。"""

    def __init__(self, cd_until: int = 0):
        self.pivot_cooldown_until = cd_until


class _Ctx:
    def __init__(self, sess):
        self.session = sess


def _state(**kw) -> GameState:
    base = dict(plane=2, round_num=7, hp=20, level=8, gold=30, hp_readable=True)
    base.update(kw)
    return GameState(**base)


def test_cooldown_blocks_crisis_pivot_same_round(monkeypatch):
    """危机信号(信号3)+ 冷却中(同轮已 pivot)→ 必须 None(不变量无例外)。"""
    st = _state(hp=20)   # hp20 < 0.75×阈值 → 危机
    monkeypatch.setattr(cw_comps, 'select_comp', lambda *a, **k: list(cw_comps.COMP_LIBRARY))
    for cd_until in (7, 8, 9):   # 同轮(7)/跨 1-2 轮内:全拦
        ctx = _Ctx(_Sess(cd_until=cd_until))
        assert maybe_pivot(st, ctx, None, None) is None, f'冷却至 r{cd_until} 仍翻转'


def test_cooldown_release_allows_pivot(monkeypatch):
    """冷却过期 → 危机 pivot 放行(守卫不误杀保命通道)。"""
    st = _state(hp=20)
    monkeypatch.setattr(cw_comps, 'select_comp', lambda *a, **k: list(cw_comps.COMP_LIBRARY))
    ctx = _Ctx(_Sess(cd_until=6))   # r7 > 6:冷却过
    piv = maybe_pivot(st, ctx, None, None)
    # 放行(返回某 easy comp)——具体哪个由保命逻辑定,关键是非 None 或有明确保持理由
    # (target=None + 危机 → 应给出落点)
    assert piv is not None


def test_invariant_single_guard_location():
    """守卫单一入口:maybe_pivot 内不再有第二份冷却检查(源码级锁,防再分散)。"""
    import inspect
    src = inspect.getsource(maybe_pivot)
    assert src.count('pivot_cooldown_until') == 1, (
        '冷却守卫必须只在函数顶出现一次(不变量单一入口);'
        '再出现 = 分散检查回归(r87/r90c 病根)')
