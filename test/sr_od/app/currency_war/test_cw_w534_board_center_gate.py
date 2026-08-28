"""W534 板面 SIFT 位置感知裁决回归锁(ADR-0452)。

三例病灶的生产语义锁(``identify_slots`` min15 + live_only + center_gate =
read_deployed_chars 同参),素材 = sr-od-test/screens 实机帧:

1. 邻卡渗漏异名混淆:角色卡宽(~170)> 槽窗宽(~142),后排6槽-P2开局局
   (按 7 槽窗裁)
   后排-2 裁片左缘渗入邻卡(花火)残条,花火 18 内点中 12 落渗漏带压过真身
   大丽花(11)。中心归属门下花火假设投影中心在邻槽核,几何出局,大丽花以
   扩展窗核内内点转正。
2. 变体模板 UI 铬互撞致歧义假拒:变体曾无掩码入库(``mask.png`` 形状只配
   主档),艾丝妲 board 变体的卡框/角标内点(13,全在铬上)把那刻夏真命中
   (19)抬成歧义。逐文件掩码后铬特征不进库。
3. live_only 强主档例外:开拓者·欢愉 plaza 主档 73 内点(跨域弱命中带实测
   上限 29)被「有变体即拒」误杀;≥ ``_LIVE_ONLY_PLAZA_STRONG`` 收。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[5]          # 仓库根(StarRailOneDragon)
_TEST_ROOT = Path(__file__).resolve().parents[4]    # 测试仓根(sr-od-test)
sys.path.insert(0, str(_ROOT / 'src'))

from one_dragon.base.geometry.rectangle import Rect  # noqa: E402
from one_dragon.utils import cv2_utils  # noqa: E402
from sr_od.application.currency_war.currency_war_char_id import (  # noqa: E402
    load_avatar_templates,
)
from sr_od.application.currency_war.cw_identity_obs import (  # noqa: E402
    identify_slots,
)

FIXTURES = _TEST_ROOT / 'screens' / '货币战争-备战'
TPL_DIR = _ROOT / 'assets/template/currency_war/portrait_plaza'

# 生产参数(read_deployed_chars 同参)
_PROD = {'min_inliers': 15, 'live_only': True, 'center_gate': True}

# 槽位 rect(1080p,与 screen_info 后排布局档一致;同基准 run_sift 表)
BACK_7 = [(463, 600, 605, 739), (605, 600, 747, 739), (747, 600, 889, 739),
          (889, 600, 1031, 739), (1031, 600, 1173, 739), (1173, 600, 1315, 739),
          (1315, 600, 1457, 739)]
BACK_8 = [(393, 600, 535, 739), (535, 600, 677, 739), (677, 600, 819, 739),
          (818, 600, 960, 739), (960, 600, 1102, 739), (1103, 600, 1245, 739),
          (1245, 600, 1387, 739), (1387, 600, 1529, 739)]
FRONT = [(677, 329, 810, 467), (823, 329, 951, 467),
         (969, 329, 1097, 467), (1109, 329, 1241, 467)]


def _slots(rects):
    return [(i, Rect(*r)) for i, r in enumerate(rects, 1)]


@pytest.fixture(scope='module')
def templates():
    return load_avatar_templates(TPL_DIR)


def _read(name: str):
    for ext in ('.webp', '.png'):
        img = cv2_utils.read_image(str(FIXTURES / f'{name}{ext}'))
        if img is not None:
            return img
    raise FileNotFoundError(f'{name}(.webp/.png 均不可读)')


def test_leak_ghost_resolved_by_center_gate(templates):
    """病灶1 锁:渗漏邻卡(花火)按中心归属出局,真身大丽花转正。"""
    frame = _read('后排6槽-P2开局局')
    got = {c.slot: c.char_id for c in identify_slots(
        frame, templates, _slots(BACK_7), 'back', **_PROD)}
    assert got.get(1) == '花火' and got.get(2) == '大丽花', got
    assert all(v not in ('花火',) or k == 1 for k, v in got.items()), got


def test_variant_chrome_mask_stops_false_ambiguity(templates):
    """病灶2 锁:那刻夏真命中不再被无掩码变体的卡框内点抬成歧义。"""
    frame = _read('equipped_front1_feixiao_2')
    got = {c.slot: c.char_id for c in identify_slots(
        frame, templates, _slots(FRONT), 'front', **_PROD)}
    assert got == {1: '飞霄', 2: '赛飞儿', 3: '那刻夏', 4: '黄泉'}, got


def test_live_only_strong_plaza_main_accepted(templates):
    """病灶3 锁:开拓者·欢愉 plaza 主档强命中(73 内点)过 live_only 门。"""
    frame = _read('后排8槽-全位验证')
    got = {c.slot: c.char_id for c in identify_slots(
        frame, templates, _slots(BACK_8), 'back', **_PROD)}
    assert got == {1: '藿藿', 2: '爻光', 6: '开拓者·欢愉',
                   7: '狸小虎', 8: '狸小龙'}, got


def test_pepe_frame_empty_slots_stay_empty(templates):
    """退化 homography 守卫锁:佩佩局(拖测前)空槽 2/4/6 零误检
    (忘归人 21 内点伪假设:19 内点塌缩到单场景点,投影中心蹭进核)。"""
    frame = _read('后排7槽-佩佩局')
    got = {c.slot: c.char_id for c in identify_slots(
        frame, templates, _slots(BACK_7), 'back', **_PROD)}
    assert got.get(2) is None and got.get(4) is None and got.get(6) is None, got
    assert got.get(1) == '卡芙卡' and got.get(3) == '万敌' \
        and got.get(5) == '爻光' and got.get(7) == '佩佩', got


def test_variant_mask_file_loaded_per_stem(tmp_path: Path) -> None:
    """变体逐文件掩码加载锁:``raw_board.png`` 读 ``mask_board.png``,
    主档 mask 形状失配不影响变体拿到自己的掩码;变体缺专属掩码退 mask.png
    (形状仍须匹配,失配 = 无掩码,同旧语义)。"""
    import cv2

    d = tmp_path / '角色X'
    d.mkdir()
    rng = np.random.default_rng(7)
    raw = (rng.random((100, 100, 3)) * 255).astype('uint8')
    cv2.imencode('.png', raw)[1].tofile(str(d / 'raw.png'))
    cv2.imencode('.png', (rng.random((60, 60)) * 255).astype('uint8'))[1] \
        .tofile(str(d / 'mask.png'))                    # 形状失配 → 主档无掩码
    board = (rng.random((40, 40, 3)) * 255).astype('uint8')
    cv2.imencode('.png', board)[1].tofile(str(d / 'raw_board.png'))
    cv2.imencode('.png', np.zeros((40, 40), np.uint8))[1] \
        .tofile(str(d / 'mask_board.png'))              # 全零掩码 → 变体零关键点

    t = load_avatar_templates(tmp_path)
    assert set(t) == {'角色X', '角色X#1'}
    assert len(t['角色X'][1]) > 0, '主档掩码形状失配应按无掩码(全图提特征)'
    assert len(t['角色X#1'][1]) == 0, '变体应读到 mask_board.png(全零 → 零关键点)'
