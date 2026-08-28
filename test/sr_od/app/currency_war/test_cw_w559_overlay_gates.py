# -*- coding: utf-8 -*-
"""备战 overlay 三形态帧态门回归锁(角色详情档拆分 + UPPER_SCREENS 扩容)。

背景(离线复跑实证):「货币战争-备战-角色详情」画面唯一 id_mark 锚(按钮-装备推荐)
只属角色详情大面板形态;装备详情浮窗(点右侧装备弹,可合成列表)与 角色信息提示
(悬停角色 tooltip,携带装备)两形态帧在锚 rect 处无该按钮 → 判不出角色详情 →
两段式门(is_prep_like_frame,ADR-0269)回落备战判定,而备战 id_mark(购买经验等)
在浮窗帧全可见 → 放行为备战帧(与 ADR-0269 记录的局72 伙伴误拖同型门漏)。

修复:按真值帧形态拆档 —— 新画面 货币战争-备战-装备详情浮窗(锚 标识-可合成列表,
真值帧 equip_detail_roller/synth_target)与 货币战争-备战-角色信息提示(锚 标识-携带装备,
真值帧 char_detail),同步进 cw_obs_core.UPPER_SCREENS。本文件锁死:
① 新锚在各自真值帧上命中;② 三张 overlay 帧 is_prep_like_frame=False;
③ 备战正样本与大面板帧不被新锚误命中(prep 正样本仍 True)。
fixture 位置:equip_detail_roller/synth_target → screens/货币战争-备战-装备详情浮窗/,
char_detail → screens/货币战争-备战-角色信息提示/(原错档在 货币战争-备战/ 目录,已迁移)。
"""
from __future__ import annotations

import pytest

_FLOAT_SCREEN = '货币战争-备战-装备详情浮窗'
_TIP_SCREEN = '货币战争-备战-角色信息提示'


def _load(ctx, screen: str, state: str):
    if not ctx.has_screen(screen, state):
        pytest.skip(f'fixture 缺:screens/{screen}/{state}.webp')
    return ctx.load_screen(screen, state)


@pytest.mark.parametrize('state', ['equip_detail_roller', 'equip_detail_synth_target'])
def test_float_anchor_hits_fixtures(test_context, state: str) -> None:
    """浮窗锚「可合成列表」在两张真值帧上命中(排除门成立的根)。"""
    from one_dragon.base.screen import screen_utils
    frame = _load(test_context, _FLOAT_SCREEN, state)
    assert screen_utils.get_match_screen_name(
        ctx=test_context, screen=frame,
        screen_name_list=[_FLOAT_SCREEN], crop_first=False) == _FLOAT_SCREEN, (
        f'浮窗锚在 {state} 上失配——两段式将放行该帧(overlay 门漏复发)')


@pytest.mark.parametrize('state', ['equip_detail_roller', 'equip_detail_synth_target'])
def test_prep_like_frame_rejects_equip_float(test_context, state: str) -> None:
    """浮窗帧 is_prep_like_frame 必 False(备战 readers/钩子不得在其上跑)。"""
    from sr_od.application.currency_war.cw_obs_core import is_prep_like_frame
    frame = _load(test_context, _FLOAT_SCREEN, state)
    assert is_prep_like_frame(test_context, frame) is False, (
        f'装备详情浮窗帧 {state} 被判 prep-like(锚失配门漏回归)')


def test_char_tooltip_anchor_hits_fixture(test_context) -> None:
    """提示锚「携带装备」在真值帧上命中。"""
    from one_dragon.base.screen import screen_utils
    frame = _load(test_context, _TIP_SCREEN, 'char_detail')
    assert screen_utils.get_match_screen_name(
        ctx=test_context, screen=frame,
        screen_name_list=[_TIP_SCREEN], crop_first=False) == _TIP_SCREEN, (
        '提示锚在 char_detail 上失配——两段式将放行该帧(overlay 门漏复发)')


def test_prep_like_frame_rejects_char_tooltip(test_context) -> None:
    """tooltip 帧 is_prep_like_frame 必 False。"""
    from sr_od.application.currency_war.cw_obs_core import is_prep_like_frame
    frame = _load(test_context, _TIP_SCREEN, 'char_detail')
    assert is_prep_like_frame(test_context, frame) is False, (
        '角色信息提示帧被判 prep-like(锚失配门漏回归)')


def test_big_panel_frame_still_rejected(test_context) -> None:
    """大面板形态(信息tab,原 档锚覆盖)仍被排除——拆分不削原有覆盖。"""
    from sr_od.application.currency_war.cw_obs_core import is_prep_like_frame
    frame = _load(test_context, '货币战争-备战-角色详情', '信息tab')
    assert is_prep_like_frame(test_context, frame) is False, (
        '角色详情大面板帧不再被排除(拆分削了原有覆盖)')


def test_new_anchors_not_hit_clean_prep(test_context) -> None:
    """防过度排除:新锚不得命中干净备战帧(否则备战帧被误判上层屏)。"""
    from one_dragon.base.screen import screen_utils
    frame = _load(test_context, '货币战争-备战', 'r1_idle_stop')
    for screen in (_FLOAT_SCREEN, _TIP_SCREEN):
        assert screen_utils.get_match_screen_name(
            ctx=test_context, screen=frame,
            screen_name_list=[screen], crop_first=False) is None, (
            f'{screen} 锚误命中干净备战帧 → 备战帧被误排除(过度排除)')


def test_prep_positive_sample_not_rejected(test_context) -> None:
    """备战正样本帧仍 True(门语义改动防反向回归)。"""
    from sr_od.application.currency_war.cw_obs_core import is_prep_like_frame
    frame = _load(test_context, '货币战争-备战', 'r1_idle_stop')
    assert is_prep_like_frame(test_context, frame) is True, (
        '备战正样本帧被判非 prep-like(过度排除)')
