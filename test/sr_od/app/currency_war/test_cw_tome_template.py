"""货币战争 备战栏可开启物品(典籍/书册卡)模板回归锁。

背景:秘密典籍旧模板为 113x134 整槽尺寸且渲染不同源(蓝底书册 vs 实机金票券卡),
在小于模板的槽裁片(最小 111x131)上被 shape 守卫静默跳过——真值帧
shop_closed_lowhp.webp 的 slot7 金卡因此被箱模板低分接走,互斥判箱,策略走 OpenBox
绕开了星徽四选一接管路径。修复 = 典籍/书册卡模板自真值渲染内窗重裁(≤97x118,
小于全部槽裁片)。本文件锁四件事:
① slot1/slot7 金卡 → find_tomes 命中(真值帧回归);
② 银箱槽不回退(箱命中,互斥拒典籍;备战满帧箱判定不变);
③ 模板尺寸收进槽内(shape 容差)+ 守卫跳过可见(记数递增,不再静默);
④ 策略层 tomes 非空优先 OpenTome(金卡走对路径的行为面锁)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from one_dragon.base.geometry.rectangle import Rect  # noqa: E402
from one_dragon.utils.cv2_utils import read_image  # noqa: E402
from sr_od.application.currency_war.obs import cw_identity_obs as cio

# 备战栏-1..9 pc_rect(assets/game_data/screen_info/currency_war_battle_prep.yml;
# 与 cw_identity_obs._ctx_slots 同一坐标系的离线硬编码,同 find_supply_boxes 分层约定)
SLOTS = [
    Rect(382, 845, 495, 979), Rect(507, 844, 620, 978), Rect(632, 844, 743, 978),
    Rect(757, 845, 869, 979), Rect(882, 846, 995, 980), Rect(1004, 847, 1118, 978),
    Rect(1132, 846, 1244, 977), Rect(1256, 845, 1368, 979), Rect(1379, 844, 1493, 980),
]
_IDX = list(enumerate(SLOTS, 1))

_SCREEN_DIR = _REPO / 'sr-od-test' / 'screens' / '货币战争-备战'
_FRAME_GOLD = _SCREEN_DIR / 'shop_closed_lowhp.webp'      # slot1/7 金卡典籍 + slot4/9 银箱
_FRAME_FULL = _SCREEN_DIR / 'reward_spheres_5.webp'        # slot1 银箱,备战 9/9 满


def _slots(screen: np.ndarray) -> list[tuple[int, Rect]]:
    """1080p 整帧校验 + 带槽号 rect 对(防 fixture 尺寸漂移静默错位)。"""
    assert screen.shape[:2] == (1080, 1920), f'真值帧应为 1080p,实得 {screen.shape}'
    return _IDX


@pytest.fixture(scope='module')
def gold_frame() -> np.ndarray:
    img = read_image(str(_FRAME_GOLD))
    assert img is not None, f'真值帧缺失:{_FRAME_GOLD}'
    return img


@pytest.fixture(scope='module')
def full_frame() -> np.ndarray:
    img = read_image(str(_FRAME_FULL))
    assert img is not None, f'真值帧缺失:{_FRAME_FULL}'
    return img


def test_gold_card_slots_hit_tomes(gold_frame) -> None:
    """slot1/slot7 金票券卡必须被 find_tomes 命中(旧模板在 slot7 被 shape 守卫
    判盲 → 箱模板低分接走 → 误判为箱)。"""
    tomes = cio.find_tomes(gold_frame, _slots(gold_frame))
    tome_slots = {idx for idx, _ in tomes}
    assert {1, 7} <= tome_slots, f'金卡典籍槽应命中,实得 {sorted(tome_slots)}'


def test_silver_box_slots_not_tomes(gold_frame) -> None:
    """银箱槽(slot4/9)互斥判定必须走箱:箱命中且不被认成典籍。"""
    boxes = cio.find_supply_boxes(gold_frame, _slots(gold_frame))
    tomes = cio.find_tomes(gold_frame, _slots(gold_frame))
    box_slots = {idx for idx, _ in boxes}
    tome_slots = {idx for idx, _ in tomes}
    assert {4, 9} <= box_slots, f'银箱槽应报箱,实得 {sorted(box_slots)}'
    assert not ({4, 9} & tome_slots), f'银箱槽不得判典籍,实得 {sorted(tome_slots)}'


def test_full_bench_box_frame_unregressed(full_frame) -> None:
    """备战满帧(9/9)的箱格判定不得回归:slot1 银箱仍报箱、不判典籍。"""
    boxes = cio.find_supply_boxes(full_frame, _slots(full_frame))
    tomes = cio.find_tomes(full_frame, _slots(full_frame))
    assert 1 in {idx for idx, _ in boxes}, '满帧 slot1 银箱应报箱'
    assert 1 not in {idx for idx, _ in tomes}, '满帧 slot1 银箱不得判典籍'


def test_templates_fit_smallest_slot_crop() -> None:
    """shape 容差锁:supply 目录全部模板必须不大于最小槽裁片(宽 111 x 高 131),
    否则该槽被 shape 守卫跳过 = 对此物品判盲(典籍旧模板 113x134 的病根)。"""
    tpl_dir = _REPO / 'assets' / 'template' / 'currency_war' / 'supply'
    for p in tpl_dir.glob('*.png'):
        img = read_image(str(p))
        assert img is not None, f'模板读取失败:{p.name}'
        h, w = img.shape[:2]
        assert w <= 111 and h <= 131, \
            f'{p.name} 尺寸 {w}x{h} 超过最小槽裁片 111x131,shape 守卫会判盲部分槽'


def test_shape_guard_skip_is_visible(monkeypatch) -> None:
    """守卫观测锁:裁片小于模板时跳过,但记数必须递增(不再静默)。"""
    monkeypatch.setattr(cio, '_tome_gray', None)
    monkeypatch.setattr(cio, '_tome_loaded', False)
    before = cio._shape_guard_skip_count
    # 槽 rect 5x5 < 任何 supply 模板 → 全部走守卫跳过
    out = cio.find_tomes(np.full((20, 20, 3), 200, dtype=np.uint8),
                         [(1, Rect(0, 0, 5, 5))])
    assert out == []
    assert cio._shape_guard_skip_count > before, '守卫跳过必须记数可见'


def test_strategy_prefers_opentome_when_gold_card_in_tomes() -> None:
    """行为面锁:tomes 非空时策略优先 OpenTome(即使 boxes 也非空)——
    金卡典籍走 OpenBox 会绕开星徽四选一接管路径,即本批修复的行为目标。"""
    from types import SimpleNamespace
    from sr_od.application.currency_war.decision.decision_v2.strategy import DecisionV2Strategy
    strat = DecisionV2Strategy()
    obs = SimpleNamespace(box_overlay_open=False, tomes=[(7, None)],
                          boxes=[(4, None)], spheres=[], free_bench_slots=3,
                          shop_open=False, bench_chars=[], deployed_chars=[],
                          front_occupied=set(), back_occupied=set(),
                          front_size=4, back_size=6, state=None,
                          state_gold_trusted=False)
    sess = SimpleNamespace(defer_count=0, memory={}, target_comp=None,
                           tracked_bench_chars=[], pending_deploys=[], prep_phase=0,
                           tracked_deployed=[], bail_reason_counts={})
    act = strat.decide_prep_action(obs, sess, SimpleNamespace())
    assert type(act).__name__ == 'OpenTome', \
        f'tomes 非空应优先 OpenTome,实得 {type(act).__name__}'
