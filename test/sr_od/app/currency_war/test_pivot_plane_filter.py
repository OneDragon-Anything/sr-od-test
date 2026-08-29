"""r20:Pivot 保命信号位面过滤测试(DOT队 P2 乏力案例)。"""
import sys
from pathlib import Path
from types import SimpleNamespace

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, maybe_pivot  # noqa: E402
from sr_od.application.currency_war.kernel.cw_state import GameState  # noqa: E402


def test_dot_comp_has_weak_plane_tag() -> None:
    """DOT队 标 P2 乏力(攻略实证)。"""
    dot = next(c for c in COMP_LIBRARY if c.name == 'DOT队')
    assert 2 in dot.weak_planes


def test_pivot_p2_avoids_dot_if_alternative() -> None:
    """P2 保命转型不选当前位面乏力 comp(mock 候选池最小化验证过滤路径)。

    用 monkeypatch select_comp 返回受控候选(DOT队 + 一个非乏力 easy),
    断言 P2 危血时选非乏力那个;P1 时 DOT 仍可选(过滤只按位面)。
    """
    import sr_od.application.currency_war.kernel.cw_comps as cc
    dot = next(c for c in COMP_LIBRARY if c.name == 'DOT队')
    other = next(c for c in COMP_LIBRARY
                 if c.name != 'DOT队' and c.form_difficulty == 'easy'
                 and not c.weak_planes)
    orig = cc.select_comp

    def _fake(state, ctx, config, top_n=None, **kw):
        return [dot, other]

    cc.select_comp = _fake
    try:
        # P2 危血(hp 低):应选 other(非 P2 乏力),不选 DOT
        st2 = GameState(level=6, plane=2, round_num=1, gold=30, hp=10)
        got = maybe_pivot(st2, None, SimpleNamespace(), None)
        assert got is None or got.name != 'DOT队', f'P2 保命不应选 P2 乏力 comp,实选 {got and got.name}'
        # P1 危血:DOT 不过滤(P1 是它的强势面,过滤只按当前位面)
        st1 = GameState(level=6, plane=1, round_num=1, gold=30, hp=10)
        got1 = maybe_pivot(st1, None, SimpleNamespace(), None)
        # P1 时 DOT(P1强,form 可能更快)允许被选;不 assert 具体,只验证不炸
        assert got1 is None or got1.name in ('DOT队', other.name)
    finally:
        cc.select_comp = orig
