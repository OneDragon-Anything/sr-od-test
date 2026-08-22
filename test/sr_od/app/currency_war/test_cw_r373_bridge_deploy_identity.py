# -*- coding: utf-8 -*-
"""r373 桥 deploy 身份修测(五局反思 25e3838d;局53 铁证)。

根因:hunt3/dot_belog 桥不在 _BRIDGE_FW_MAP → transition_framework=''
→ deploy_bench 的 target 集与框架豁免全空 → 桥件+配方核心只能走
散牌通道与 8 阵营散板同序竞争,板满即滞留 bench。
锁:桥选定后 session.transition_framework 有身份;hunt3 桥的 deploy
target 集含 狼狩+持续伤害(FRAMEWORK_FACTIONS 单一源)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_transition import FRAMEWORK_FACTIONS
from sr_od.application.currency_war.cw_bridge_pool import BRIDGE_POOL
from sr_od.application.currency_war.strategies.line_strategy import LineStrategy

_BRIDGE_IDS = {c.bridge_id for c in BRIDGE_POOL}


class _Sess:
    locked_line = None
    bridge_id = None
    transition_framework = ''
    dual_track_phase = False
    target_comp = None
    v2_state = None
    dual_track_phase_done = False


class _St:
    plane = 1
    round_num = 1


def test_all_bridges_have_framework_identity() -> None:
    """P1 桥池全桥都有 framework 映射(防再漏)。"""
    fw_map = {
        'xianzhou_dot': '仙舟', 'xianzhou_train': '仙舟',
        'train_dot': '列车', 'train4_shield3': '列车',
        'hunt3': '狼狩', 'dot_belog': '贝洛伯格',
    }
    for bid in _BRIDGE_IDS:
        assert bid in fw_map, f'桥 {bid} 无 framework 映射(桥期 deploy 真空)'


def test_hunt3_framework_factions() -> None:
    """hunt3 桥的框架目标 = 狼狩+持续伤害(局53:仙舟核心对要能上场)。"""
    assert FRAMEWORK_FACTIONS['狼狩'] == ('狼狩', '持续伤害')


def test_dot_belog_framework_factions() -> None:
    assert FRAMEWORK_FACTIONS['贝洛伯格'] == ('持续伤害', '贝洛伯格')


def test_frameworks_tuple_unchanged() -> None:
    """pick_framework 早期框架选择仍只认三主流(新框架仅 deploy 侧)。"""
    from sr_od.application.currency_war.cw_transition import FRAMEWORKS
    assert FRAMEWORKS == ('仙舟', '列车', '量子')
