"""件3(ADR-0275)成本模型统一 flat-4 锁:cw_economy._want_level_up 简算走 xp_click_cost。

旧 `4+state.level` 简算(lv7 门槛 4+7+10=21)与生产 flat-4 兜底互相矛盾;裁决证据
(VLM 三帧 lv4/lv7 均 4 金/击 + lv5 既有实测锚)→ 统一 flat-4(lv7 门槛 4+10=14)。
锁边界:lv7 金 13 拦 / 金 14 过(旧模型两者全拦)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_economy import _want_level_up, xp_click_cost
from sr_od.application.currency_war.cw_state import GameState


def _st(level: int, gold: int) -> GameState:
    """P1 lv≥5 追级抑制门作用域的构造态(非 boss/hp≥30/gold<50)。"""
    return GameState(level=level, gold=gold, plane=1, round_num=3,
                     node_type='普通战斗', hp=100)


def test_flat4_click_cost_constant() -> None:
    """OCR 通道死(stylized 不可检,ADR-0275)→ xp_click_cost 恒 flat-4 兜底。"""
    assert xp_click_cost(_st(7, 50)) == 4
    assert xp_click_cost(_st(5, 50)) == 4


def test_flat4_gate_boundary_lv7() -> None:
    """lv7 边界:金 13 拦 / 金 14 过(旧 4+level 模型两值全拦,门槛 21)。"""
    assert _want_level_up(_st(7, 13), None) is False, '金 13 < 4+10 → 追级抑制照拦'
    assert _want_level_up(_st(7, 14), None) is True, \
        '金 14 ≥ flat-4 单击+保命地板 → 放行(旧 4+level 模型误拦)'


def test_flat4_gate_boundary_lv5() -> None:
    """lv5 同边界(M31 语义:拦攒金追级,不拦金够的有效点击)。"""
    assert _want_level_up(_st(5, 13), None) is False
    assert _want_level_up(_st(5, 14), None) is True
