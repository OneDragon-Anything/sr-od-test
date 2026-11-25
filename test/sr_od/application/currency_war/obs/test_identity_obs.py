"""晶矿识别(``find_ore_sights`` 多尺度模板匹配管线)fixture 回归。

锁的设计约定(标定依据见 src cw_identity_obs.py 晶矿常量块注释):
- 真球检出:金/蓝/灰三色全档位命中(fixture reward_spheres_8 = 1 金 + 5 蓝 + 2 灰);
- 高命中零误报:存证帧 15 球 ground truth 上 ≥14 命中(已知结构性盲区:被两大球
  夹死的重度遮挡小球,可见球面占比小 → 分数掉阈值下,设计披露宁漏勿误)且输出
  无一落 GT 之外(零假阳性);
- 幻检免疫:礼盒幻检帧(历史停机事故帧)与空面板 0 检出;
- 遮挡态不输出:邀请函 overlay 覆盖奖励面板时 0 检出(旧形状检测管线在此帧
  幻检 2 圆,点击零消失 = 死循环风险——本回归锁修复不回退)。

fixture(货币战争-备战/):reward_spheres_{8,15}、reward_giftbox_phantom、
reward_panel_empty、reward_panel_invite_overlay。缺帧/缺模板 → skip。

**身份识别回归段**(开拓者个性化卡「Momojie」入席读数,文件镜像
src cw_identity_obs.resolve_char_name):fixture 在 货币战争-备战-开拓商店/
(bench6_momojie_r13 / bench6_empty_r13,入席帧与购买前对照帧),
bench-6 裁片走生产同款 SIFT+resolve 链。
"""
from __future__ import annotations

from functools import cache
from pathlib import Path

import cv2
import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.obs.cw_identity_obs import find_ore_sights

_ORE_PANEL_RECT = Rect(1257, 140, 1662, 492)


def _screens_dir() -> Path:
    """向上定位中央归档库 ``screens/``(同 test_get_match_screen_name 手法)。"""
    p = Path(__file__)
    while p != p.parent:
        cand = p / 'screens'
        if cand.is_dir() and (any(cand.glob('*/*.webp')) or any(cand.glob('*/*.png'))):
            return cand
        p = p.parent
    raise RuntimeError('未找到 screens/ 归档库')


@cache
def _load_frame(name: str) -> np.ndarray | None:
    """读 fixture 帧(RGB 口径,框架截图同口径);缺失 → None。"""
    d = _screens_dir()
    for suffix in ('.webp', '.png'):
        f = d / '货币战争-备战' / f'{name}{suffix}'
        if f.is_file():
            img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
            return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return None


def _require_frame(name: str) -> np.ndarray:
    img = _load_frame(name)
    if img is None:
        pytest.skip(f'存档截图缺失:screens/货币战争-备战/{name}.webp|png')
    return img


def _run_find(name: str) -> list[tuple[str, object, int]]:
    """单帧只跑一次识别(慢计算 ~220ms),结果供该帧全部断言共用。"""
    return find_ore_sights(_require_frame(name), _ORE_PANEL_RECT)


def _ore_tpl_missing() -> bool:
    from one_dragon.utils.file_utils import get_project_root
    base = get_project_root() / 'assets' / 'template' / 'cw_reward_ore'
    return not base.is_dir() or not any(base.glob('*.webp'))


#: 晶矿模板缺席 skip(测试级装饰:身份回归段不依赖晶矿模板,不用模块级 pytestmark)
_ore_tpl_skip = pytest.mark.skipif(_ore_tpl_missing(), reason='晶矿模板未归档')


@_ore_tpl_skip
def test_gold_blue_gray_all_detected() -> None:
    """三色全档位检出:spheres_8 = 1 金 + 5 蓝 + 2 灰(金球是高价值优先级依据)。"""
    out = _run_find('reward_spheres_8')
    by_color = {'gold': 0, 'blue': 0, 'gray': 0}
    for color, _pt, _r in out:
        by_color[color] += 1
    assert by_color == {'gold': 1, 'blue': 5, 'gray': 2}


@_ore_tpl_skip
def test_high_hit_zero_false_positive_on_15_spheres() -> None:
    """存证帧 15 球 GT:≥14 命中(盲区披露 1 颗)且零假阳性(输出全部落 GT 容差内)。"""
    gt = [
        ('blue', 1346, 351, 30), ('blue', 1359, 259, 31), ('blue', 1400, 301, 31),
        ('blue', 1402, 407, 34), ('blue', 1418, 374, 19), ('blue', 1431, 257, 32),
        ('blue', 1466, 396, 34), ('blue', 1496, 308, 18), ('blue', 1509, 252, 28),
        ('blue', 1513, 343, 34), ('blue', 1572, 403, 34), ('blue', 1578, 312, 34),
        ('gray', 1293, 265, 18), ('gray', 1317, 295, 19), ('gray', 1438, 341, 17),
    ]
    out = _run_find('reward_spheres_15')
    tol = 4
    hits = 0
    for _color, pt, _r in out:
        near = [g for g in gt
                if abs(pt.x - g[1]) <= g[3] // 2 + tol
                and abs(pt.y - g[2]) <= g[3] // 2 + tol]
        assert near, f'假阳性:输出 ({pt.x},{pt.y}) 不落任何 GT 球容差内'
        hits += 1
    assert hits >= 14, f'命中不足(已知盲区球 1 颗之外不得再漏): {hits}/15'


@_ore_tpl_skip
@pytest.mark.parametrize('frame', [
    'reward_giftbox_phantom',   # 礼盒幻检历史事故帧(旧管线 Hough 检出 2 圆)
    'reward_panel_empty',       # 空面板(点阵/按钮背景)
])
def test_no_phantom_on_non_ore_frames(frame: str) -> None:
    """非晶矿实体零检出:模板分数带(真球 ≥0.741 / 非球响应 ≤0.652)天然分离。"""
    assert _run_find(frame) == []


@_ore_tpl_skip
def test_invite_overlay_zero_detection() -> None:
    """奖励面板被邀请函 overlay 覆盖 → 0 检出(遮挡态不输出读数)。"""
    assert _run_find('reward_panel_invite_overlay') == []


# ===== 身份识别回归(开拓者个性化卡「Momojie」入席读数;文件镜像
# src cw_identity_obs.resolve_char_name) =====

#: 画面档「备战栏-6」pc_rect(建档单一源;晶矿回归同款硬编码先例)
_BENCH_SLOT6_RECT = Rect(1004, 847, 1118, 978)


def _char_tpl_missing() -> bool:
    from one_dragon.utils.file_utils import get_project_root
    base = get_project_root() / 'assets' / 'template' / 'cw_character_avatar'
    return not base.is_dir() or not any(base.glob('*/raw.png'))


_char_tpl_skip = pytest.mark.skipif(_char_tpl_missing(), reason='角色立绘模板库未归档')


@cache
def _char_templates() -> dict:
    """全库 SIFT 模板(慢计算 ~2s,进程级只算一次,供身份段全部断言共用)。"""
    from one_dragon.utils.file_utils import get_project_root
    from sr_od.application.currency_war.obs.currency_war_char_id import (
        load_avatar_templates,
    )
    base = get_project_root() / 'assets' / 'template' / 'cw_character_avatar'
    return load_avatar_templates(base)


@cache
def _load_shop_panel_frame(name: str) -> np.ndarray | None:
    """读开拓商店面板态 fixture 帧(RGB 口径);缺失 → None。"""
    f = _screens_dir() / '货币战争-备战-开拓商店' / f'{name}.webp'
    if not f.is_file():
        return None
    img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
    return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _bench_slot6_identity(name: str) -> str | None:
    """bench-6 裁片走生产同款识别链(SIFT → resolve),单帧只算一次。"""
    frame = _load_shop_panel_frame(name)
    if frame is None:
        pytest.skip(f'存档截图缺失:screens/货币战争-备战-开拓商店/{name}.webp')
    from sr_od.application.currency_war.obs.currency_war_char_id import (
        identify_character,
    )
    from sr_od.application.currency_war.obs.cw_identity_obs import resolve_char_name
    crop = frame[_BENCH_SLOT6_RECT.y1:_BENCH_SLOT6_RECT.y2,
                 _BENCH_SLOT6_RECT.x1:_BENCH_SLOT6_RECT.x2]
    avatar_id, _inliers = identify_character(crop, _char_templates())
    return resolve_char_name(avatar_id) if avatar_id else None


def test_trailblazer_form_names_normalize() -> None:
    """换季改名归一(锁 resolve 层修复,纯函数零 fixture):旧季开拓者命途
    形态模板名 → 现役规范名 开拓者;在册名与系统单位名不受影响。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import resolve_char_name
    assert resolve_char_name('开拓者·欢愉') == '开拓者'
    assert resolve_char_name('开拓者·记忆') == '开拓者'
    assert resolve_char_name('开拓者') == '开拓者'
    assert resolve_char_name('佩佩') == '佩佩'
    assert resolve_char_name('杨叔') == '杨叔'


@_char_tpl_skip
def test_momojie_bench_slot_resolves_to_trailblazer() -> None:
    """个性化开拓者卡(卡面显示玩家昵称,立绘=开拓者命途形态 art)购入入席
    备战栏-6 → 身份读 开拓者(修复前:resolve None → 槽位静默丢弃读 empty)。"""
    assert _bench_slot6_identity('bench6_momojie_r13') == '开拓者'


@_char_tpl_skip
def test_bench_slot6_empty_before_purchase() -> None:
    """购买前对照帧同槽零命中(真空槽不因归一产生假阳)。"""
    assert _bench_slot6_identity('bench6_empty_r13') is None


# ===== 后排部署排身份回归(三件批:奇遇伙伴杨叔模板补齐 + 银狼LV.999 /
# 姬子·启行 plaza 主档部署排读数;链 = identify_slots 部署排语义) =====

#: screen_info 后排7槽档 rect(居中重排族,布局单一源;与本批两帧实拍布局同档)
_BACK7_SLOTS = [(i, Rect(463 + 142 * (i - 1), 600, 605 + 142 * (i - 1), 739))
                for i in range(1, 8)]
#: screen_info 后排基线档 2 号格 rect(deployed_p1r9 为 6 格基线布局)
_BACK_BASE_SLOT2_RECT = Rect(679, 600, 814, 739)


def _back_row_hits(name: str, slots: list, screen: str = '货币战争-备战') -> dict[int, str]:
    """部署排生产链识别(live_only + center_gate,同 read_deployed_rows 语义)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import identify_slots
    frame = _require_screen_frame(screen, name)
    hits = identify_slots(frame, _char_templates(), slots, 'back',
                          min_inliers=15, live_only=True, center_gate=True)
    return {s: u.char_id for s, u in hits}


@cache
def _load_screen_frame(screen: str, name: str) -> np.ndarray | None:
    """读指定画面目录下的 fixture 帧(RGB 口径);缺失 → None。"""
    f = _screens_dir() / screen / f'{name}.webp'
    if not f.is_file():
        return None
    img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
    return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _require_screen_frame(screen: str, name: str) -> np.ndarray:
    img = _load_screen_frame(screen, name)
    if img is None:
        pytest.skip(f'存档截图缺失:screens/{screen}/{name}.webp')
    return img


@_char_tpl_skip
def test_yangshu_partner_back_slot6_reads() -> None:
    """奇遇伙伴杨叔(7槽-6)部署排读出(补模板前该槽零假设失读,身份靠人工);
    同帧三月七照常命中,其余扩展档空槽零假阳。"""
    by_slot = _back_row_hits('后排7槽-奇遇伙伴杨叔局', _BACK7_SLOTS)
    assert by_slot.get(6) == '杨叔'
    assert by_slot.get(1) == '三月七'
    assert set(by_slot) == {1, 6}


@_char_tpl_skip
def test_yinlang_bench_and_overlay_board_reads() -> None:
    """银狼LV.999 双域:杨叔局帧 bench-7 读出(备战语义);骇入选择帧
    7槽-2 部署排读出(浮层压暗真板面,模板缺口误判的原始帧,锁不回退;
    帧归 货币战争-银狼升星 档——浮层即该画面档,同 fixture 骇入二选一)。"""
    from sr_od.application.currency_war.obs.cw_identity_obs import identify_slots
    frame = _require_frame('后排7槽-奇遇伙伴杨叔局')
    bench7 = Rect(1132, 846, 1244, 977)
    hits = identify_slots(frame, _char_templates(), [(7, bench7)], '',
                          min_inliers=10)
    assert [u.char_id for _s, u in hits] == ['银狼LV.999']
    by_slot = _back_row_hits('骇入二选一-r24', _BACK7_SLOTS, screen='货币战争-银狼升星')
    assert by_slot.get(2) == '银狼LV.999'


@_char_tpl_skip
def test_jizi_board_read_on_p1r9_fixture() -> None:
    """姬子·启行 部署排读出(既有 fixture deployed_p1r9,后排基线 2 号格;
    shop/bench 域另有带名裁片与 g25 帧实证,本条锁部署排链不回退)。"""
    by_slot = _back_row_hits('deployed_p1r9', [(2, _BACK_BASE_SLOT2_RECT)])
    assert by_slot.get(2) == '姬子·启行'
