"""W299 summon 兜底 × 首领简报画面负样本回放锁。

背景(2026-08-27,W295 抽样判读):summon_unknown 兜底批 133 张中 21 张是
「货币战争-简报」画面帧(2026-08-18 23:13 采集,火线动力机甲/绘师家族产业/
本场对局首领 UI)——采集时 r330 帧态门(08-21)与 ADR-0269 两段式(08-23)
尚不存在,兜底在非备战画面跑了 bench 槽判定并停机。现行为:两段式第一段
``UPPER_SCREENS`` 已含「货币战争-简报」,简报帧应被 ``is_prep_like_frame``
判 False → summon/bookcard 钩子跳过。

本文件用 6 张归档简报帧(screens/货币战争-简报/boss_briefing_w299_*.webp,
取自 shots_archive_20260827/summon_unknown_w295/ 21 张 B 族)离线回放锁死:
① 简 id_mark 在帧上真命中(负样本成立的根);② is_prep_like_frame=False
(钩子必跳过);③ 备战正样本帧仍 True(不误伤)。
以后改 UPPER_SCREENS / 简报建档 / 两段式语义,跑这里即知简报排除是否还成立。
"""
from __future__ import annotations

import pytest

_W299_FIXTURES: list[str] = [
    'boss_briefing_w299_04cfb3c4',
    'boss_briefing_w299_2ae9afde',
    'boss_briefing_w299_3ccb9018',
    'boss_briefing_w299_7085c41e',
    'boss_briefing_w299_93550a0d',
    'boss_briefing_w299_c4ab224f',
]

_BRIEFING_SCREEN: str = '货币战争-简报'


def _load(ctx, state: str):
    if not ctx.has_screen(_BRIEFING_SCREEN, state):
        pytest.skip(f'fixture 缺:screens/{_BRIEFING_SCREEN}/{state}.webp')
    return ctx.load_screen(_BRIEFING_SCREEN, state)


@pytest.mark.parametrize('state', _W299_FIXTURES)
def test_briefing_id_mark_hits_fixture(test_context, state: str) -> None:
    """负样本成立之根:简报 id_mark「本场对局首领」在归档帧上真命中。

    若此处失配(OCR 形变/坐标漂移),两段式第一段就看不见简报 →
    summon 兜底会重新在简报帧上跑 bench 判定(= W295 病灶复发)。
    """
    from one_dragon.base.screen import screen_utils
    frame = _load(test_context, state)
    assert screen_utils.get_match_screen_name(
        ctx=test_context, screen=frame,
        screen_name_list=[_BRIEFING_SCREEN],
        crop_first=False) == _BRIEFING_SCREEN, (
        f'简报 id_mark 在 {state} 上失配——两段式将放行该帧,简报排除失效')


@pytest.mark.parametrize('state', _W299_FIXTURES)
def test_prep_like_frame_rejects_briefing(test_context, state: str) -> None:
    """W299 主锁:简报帧 is_prep_like_frame 必 False(21 张 B 族的代表 6 张)。"""
    from sr_od.application.currency_war.cw_obs_core import is_prep_like_frame
    frame = _load(test_context, state)
    assert is_prep_like_frame(test_context, frame) is False, (
        f'简报帧 {state} 被判 prep-like → summon 兜底会在其上跑 bench 判定'
        '(W295 21 张 B 族病灶回归)')


def test_prep_positive_sample_not_rejected(test_context) -> None:
    """正样本不误伤:备战帧仍 True(gate 语义改动防反向回归)。"""
    from sr_od.application.currency_war.cw_obs_core import is_prep_like_frame
    if not test_context.has_screen('货币战争-备战', 'r1_idle_stop'):
        pytest.skip('fixture 缺:screens/货币战争-备战/r1_idle_stop.webp')
    frame = test_context.load_screen('货币战争-备战', 'r1_idle_stop')
    assert is_prep_like_frame(test_context, frame) is True, (
        '备战正样本帧被判非 prep-like → 兜底停机全废(过度排除)')
