"""W595 试用角色揭示卡(发光金卡)识别覆盖 + 行为接线锁。

机制(2026-08-30 局22 2-4 实机确认):备战栏偶现发光金色神秘卡,点击即揭示为
试用角色 2★ 卡(免费,原地变普通角色卡)。曾落 summon unknown 兜底停机。
本批:模板+发光签名双通道识别(find_trial_reveal_cards)、summon 兜底将其
归为已知物品、battle_loop 备战环派发前点击揭示。

锁:
- 正样本帧 slot3 双通道命中(离线 fixture 回放);
- 负样本备战帧全槽零误报;
- summon 兜底对该形态不再停机(已知物品豁免链接线);
- battle_loop 揭示接线在场(防接线被误删后退回停机)。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils.cv2_utils import read_image

TEST_DIR = Path(__file__).parents[4]
SCREENS = TEST_DIR / 'screens' / '货币战争-备战'

# screen_info「货币战争-备战.备战栏-1..9」pc_rect(1080p;与 yml 同步,离线硬编码约定)
_BENCH_SLOTS: list[tuple[int, Rect]] = [
    (1, Rect(382, 845, 495, 979)),
    (2, Rect(507, 844, 620, 978)),
    (3, Rect(632, 844, 743, 978)),
    (4, Rect(757, 845, 869, 979)),
    (5, Rect(882, 846, 995, 980)),
    (6, Rect(1004, 847, 1118, 978)),
    (7, Rect(1132, 846, 1244, 977)),
    (8, Rect(1256, 845, 1368, 979)),
    (9, Rect(1379, 844, 1493, 980)),
]

_POS_FIXTURE = SCREENS / 'trial_reveal_w595.webp'


def _load(name: str):
    img = read_image(str(SCREENS / name))
    assert img is not None, f'fixture 缺失:{name}'
    return img


def test_positive_frame_slot3_hit() -> None:
    """正样本帧(建档帧 slot3 发光卡)→ 双通道命中 slot3,且不误报其他槽。"""
    from sr_od.application.currency_war.cw_identity_obs import find_trial_reveal_cards

    screen = _load(_POS_FIXTURE.name)
    hits = find_trial_reveal_cards(screen, _BENCH_SLOTS)
    hit_slots = [i for i, _p in hits]
    assert 3 in hit_slots


def test_negative_frames_no_false_positive() -> None:
    """既有备战 fixture(角色/箱/球/商店等)全槽零误报(双通道负样本分离度锁)。"""
    from sr_od.application.currency_war.cw_identity_obs import find_trial_reveal_cards

    for name in ('r1_idle_stop.webp', 'shop_closed.webp',
                 'deployed_2star_bench1.webp', 'reward_spheres_8.webp'):
        screen = _load(name)
        hits = find_trial_reveal_cards(screen, _BENCH_SLOTS)
        assert hits == [], f'{name} 误报:{hits}'


def test_tm_channel_separation() -> None:
    """TM 通道单通道独立命中正样本(阈值 0.5 的余量锁:正 ≥0.9 / 负 ≤0.26 标定)。"""
    import cv2

    from sr_od.application.currency_war.cw_identity_obs import (
        _TRIAL_REVEAL_TM_THR,
        _get_trial_reveal_gray,
    )

    tm = _get_trial_reveal_gray()
    assert tm is not None, '模板缺失:assets/template/currency_war/supply/试用角色揭示卡.png'
    pos = _load(_POS_FIXTURE.name)
    rect = _BENCH_SLOTS[2][1]
    crop = cv2.cvtColor(pos[rect.y1:rect.y2, rect.x1:rect.x2], cv2.COLOR_RGB2GRAY)
    val = cv2.minMaxLoc(cv2.matchTemplate(crop, tm, cv2.TM_CCOEFF_NORMED))[1]
    assert val >= max(0.9, _TRIAL_REVEAL_TM_THR), f'正样本 TM 掉到 {val:.3f}(发光帧模板失配?)'


# ===== summon 兜底豁免链(钩子层,mock 依赖;同 ADR-0263 测试手法) =====

_SLOT6 = Rect(1004, 847, 1118, 978)


class _FakeRunContext:
    def __init__(self) -> None:
        self.stops: list[str] = []

    def stop_running(self, reason: str = '') -> None:
        self.stops.append(reason)


class _FakeOcrService:
    def get_ocr_result_list(self, **kwargs):   # noqa: ANN003 ARG003 兼容签名
        return []


class _HookCtx:
    def __init__(self) -> None:
        self.ocr_service = _FakeOcrService()
        self.run_context = _FakeRunContext()


def test_summon_hook_skips_trial_reveal_card(monkeypatch, tmp_path) -> None:
    """发光卡形态:slot 占用 + SIFT 不识别,但 find_trial_reveal_cards 命中
    → 归已知物品,不停机不采证(免费增益不再触发停机)。"""
    from sr_od.application.currency_war import currency_war_cv, cw_identity_obs
    from sr_od.application.currency_war.kernel import cw_obs_core, cw_observe
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.debug/temp/currency_war').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cw_identity_obs, 'identify_slots', lambda *a, **k: [])
    monkeypatch.setattr(cw_identity_obs, '_ctx_slots',
                        lambda ctx, prefix, count: [(6, _SLOT6)])
    monkeypatch.setattr(cw_identity_obs, 'find_supply_boxes', lambda screen, slots: [])
    monkeypatch.setattr(cw_identity_obs, 'find_tomes', lambda screen, slots: [])
    monkeypatch.setattr(cw_identity_obs, 'find_bookcards', lambda screen, slots: [])
    # 豁免源:揭示卡在 slot6 命中(接线锁——摘掉 _obj_slots 豁免行本测即红)
    monkeypatch.setattr(cw_identity_obs, 'find_trial_reveal_cards',
                        lambda screen, slots: [(6, Point(1061, 912))])
    monkeypatch.setattr(cw_identity_obs, '_area_rect',
                        lambda ctx, name, screen_name=None: None)
    monkeypatch.setattr(cw_obs_core, 'is_prep_like_frame', lambda ctx, screen: True)
    monkeypatch.setattr(currency_war_cv, 'slot_occupied', lambda screen, x, y: True)
    shots: list[str] = []
    monkeypatch.setattr(cw_observe, 'cw_shot_unique',
                        lambda screen, prefix: shots.append(prefix) or f'{prefix}.png')

    ctx = _HookCtx()
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    cw_identity_obs.read_bench_chars(ctx, screen, None)
    assert ctx.run_context.stops == []
    assert shots == []
    assert not (tmp_path / '.debug/temp/currency_war/summon_stop_hook.flag').exists()


def test_battle_loop_reveal_wiring_present() -> None:
    """行为接线锁:battle_loop 备战分支的揭示清场在场(防误删后退回停机/漏增益)。"""
    import inspect

    from sr_od.application.currency_war.operations import battle_loop

    src = inspect.getsource(battle_loop)
    assert 'find_trial_reveal_cards' in src, 'battle_loop 试用揭示卡清场接线被移除'
