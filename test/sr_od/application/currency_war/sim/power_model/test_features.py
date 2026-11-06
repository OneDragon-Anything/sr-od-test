"""power_model 特征面对齐测试(src 镜像:sim/power_model/features.py)。

锁的设计约定(design 2026-10-19-sim-power-model-v1 §2.2 + 权威版本
sim-power-model §4.2):
- 双侧同源:sim GameState 与实机 decisions 行同一板面输入 → 同一
  特征向量(对齐测试是设计验收对象,非实现细节);
- 取大定义:平局破缺 = COMP_LIBRARY 注册序首个最大;
- 难度缺失口径(None ∨ [20,300] 外)与缺失指示联动;
- 空槽过滤:char_id 为空的条目不计入任何单位计数;
- rung 分档域四档(0-3),rung≥3 并入第三位。
"""
from __future__ import annotations

from typing import Any

import pytest

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_game_state import (
    DeployedView,
    Field,
    GameState,
    NodeKey,
    Unit,
)
from sr_od.application.currency_war.sim.power_model import features as pm
from sr_od.application.currency_war.sim.power_model.features import (
    best_line,
    compute_features,
    features_from_decision_row,
    features_from_game_state,
)

#: 仙舟系三名(注册表核实 factions 含「仙舟」)——重算板面可达成
#: 仙舟3 体系(rung≥1)的最小板面。
_XIANZHOU_TRIO = ('停云', '青雀', '藿藿')


def _trio_entries() -> list[dict[str, Any]]:
    """仙舟三人 + 后排欢愉开拓者的 decisions 行条目形态(带排内槽号)。"""
    return [
        {'slot': 1, 'char_id': _XIANZHOU_TRIO[0], 'star': 2,
         'equips': [], 'position_pref': 'front', 'is_item_slot': False},
        {'slot': 2, 'char_id': _XIANZHOU_TRIO[1], 'star': 1,
         'equips': [], 'position_pref': 'front', 'is_item_slot': False},
        {'slot': 1, 'char_id': _XIANZHOU_TRIO[2], 'star': 2,
         'equips': [], 'position_pref': 'back', 'is_item_slot': False},
        {'slot': 2, 'char_id': '开拓者·欢愉', 'star': 1, 'equips': ['轮滑鞋'],
         'position_pref': 'back', 'is_item_slot': False},
    ]


def _trio_units() -> DeployedView:
    """与 _trio_entries 同一名单的状态容器 Unit 形态(sim 侧;开拓者后排
    = Unit 缺省排语义,与行侧 position_pref='back' 同值)。"""
    return DeployedView(
        front_slots=[Unit(char_id=_XIANZHOU_TRIO[0], star=2),
                     Unit(char_id=_XIANZHOU_TRIO[1], star=1), None, None],
        back_slots=[Unit(char_id=_XIANZHOU_TRIO[2], star=2),
                    Unit(char_id='开拓者·欢愉', star=1, equips=['轮滑鞋']),
                    None, None, None, None],
    )


def _row(board: dict[str, int], level: int,
         difficulty: int | None) -> dict[str, Any]:
    """实机行载体(state 旧帧形状;与现盘实机行同键面)。"""
    return {
        'run_id': 'run_x', 'plane': 1, 'round_num': 3,
        'state': {'board': board, 'deployed': _trio_entries(),
                  'level': level, 'enemy_difficulty': difficulty,
                  'node_type': 'battle', 'hp': 40},
        'target_comp': '',
    }


def _game_state(board: dict[str, int], level: int) -> GameState:
    """sim 侧状态容器(与 _row 同一名单同一板面)。"""
    gs = GameState(schema_version=1)
    gs.board = Field(value=board)
    gs.deployed = Field(value=_trio_units())
    gs.level = Field(value=level)
    gs.node = Field(value=NodeKey(plane=1, round_num=3, kind='battle'))
    return gs


class TestBothSideAlignment:
    """双侧同源:同一板面输入 → 两侧同一特征向量(设计验收对象)。"""

    def test_same_board_same_vector(self) -> None:
        board = {'仙舟': 4, '欢愉': 2, '追击': 1}
        v_sim = features_from_game_state(
            _game_state(board, 7), node_type='battle', enemy_difficulty=108)
        v_row = features_from_decision_row(
            _row(board, 7, 108), node_type='battle')
        assert v_sim == v_row
        assert v_sim.to_list() == v_row.to_list()

    def test_row_rung_from_recounted_board(self) -> None:
        """rung 从上阵行重算(单一源 _settle_rung;行侧不读 state.board)。

        仙舟三人 → 仙舟3 体系达成 → rung≥1 → rung_1 置位;observed
        board 与重算无关(两侧同源函数内自算)。"""
        v = features_from_decision_row(_row({'仙舟': 3}, 7, 108),
                                       node_type='battle')
        assert v.rung_1 == 1.0
        assert v.rung_2 == 0.0 and v.rung_3 == 0.0

    def test_difficulty_missing_semantics(self) -> None:
        """缺失口径 = None ∨ [20,300] 外;缺失 → 指示位 1、数值按 0。"""
        for raw, miss, val in ((None, 1.0, 0.0), (19, 1.0, 0.0),
                               (301, 1.0, 0.0), (108, 0.0, 108.0)):
            base = _row({'仙舟': 3}, 7, 108)
            row = {**base, 'state': {**base['state'],
                                     'enemy_difficulty': raw}}
            v = features_from_decision_row(row, node_type='battle')
            assert v.enemy_difficulty_missing == miss, f'raw={raw}'
            assert v.enemy_difficulty == val, f'raw={raw}'


class TestFeatureDefinitions:
    """单特征定义位(design §2.2 表逐位的最小锁)。"""

    def test_empty_slots_counted_nowhere(self) -> None:
        """char_id 为空的条目不计入任何单位计数(上场数/rung/星深)。

        空条目带 faction 字段(生产行实测形态)也不触发 faction 兜底
        (行侧适配不携带 faction——两侧结构同形)。"""
        entries = _trio_entries()
        entries.append({'slot': 3, 'char_id': '', 'star': 1, 'equips': [],
                        'position_pref': 'back', 'faction': '群攻',
                        'is_item_slot': False})
        v_clean = features_from_decision_row(
            _row({'仙舟': 3}, 7, 108), node_type='battle')
        row_dirty = _row({'仙舟': 3}, 7, 108)
        row_dirty['state']['deployed'] = entries
        v_dirty = features_from_decision_row(row_dirty, node_type='battle')
        assert v_dirty.deployed_minus_level == v_clean.deployed_minus_level
        assert (v_dirty.rung_1, v_dirty.rung_2, v_dirty.rung_3) \
            == (v_clean.rung_1, v_clean.rung_2, v_clean.rung_3)
        assert v_dirty.total_star_depth == v_clean.total_star_depth

    def test_context_bits(self) -> None:
        """位面二值/node one-hot/round 序位的直接映射。"""
        board = {'仙舟': 3}
        v = compute_features(board, _trio_units(), 7, plane=2, round_num=4,
                             node_type='encounter', enemy_difficulty=108)
        assert v.plane_not_first == 1.0
        assert v.node_encounter == 1.0 and v.node_boss == 0.0
        assert v.round_num == 4.0
        v2 = compute_features(board, _trio_units(), 7, plane=1, round_num=1,
                              node_type='boss', enemy_difficulty=None)
        assert v2.plane_not_first == 0.0
        assert v2.node_boss == 1.0 and v2.node_encounter == 0.0

    def test_rung_clamped_to_four_levels(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """rung≥3 并入第三位(分档域四档 0-3;rung4 输入 = 防御路径)。"""
        monkeypatch.setattr(pm, '_settle_rung', lambda gs: 4)
        v = compute_features({}, _trio_units(), 7, plane=1, round_num=1,
                             node_type='battle', enemy_difficulty=None)
        assert (v.rung_1, v.rung_2, v.rung_3) == (0.0, 0.0, 1.0)

    def test_best_line_tie_break_registration_order(self) -> None:
        """平局破缺 = 注册序首个最大(空板全零 → 首套胜出)。"""
        comp, fp = best_line({}, None)
        assert comp is COMP_LIBRARY[0]
        assert fp == 0.0

    def test_core_star_depth_uses_best_line_cores(self) -> None:
        """核心星深只计取大线 core_chars 名单内单位。"""
        board = {'仙舟': 3}
        units = [u for u in (*_trio_units().front_slots,
                             *_trio_units().back_slots) if u is not None]
        comp, _fp = best_line(board, _trio_units())
        v = compute_features(board, _trio_units(), 7, plane=1, round_num=1,
                             node_type='battle', enemy_difficulty=None)
        expected = sum(u.star - 1 for u in units
                       if u.char_id in set(comp.core_chars))
        assert v.core_star_depth == float(expected)
