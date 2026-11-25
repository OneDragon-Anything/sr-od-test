"""银轨商店入口识别（``find_rail_shop_train`` 带内模板匹配 + ``parse_rail_shop_banner``
横幅解析 + 可买解析）fixture 回归。

锁的设计约定（标定依据见 src battle_prep_recognizer.py rail_shop 常量块注释）：
- 在场判定：横幅左段**列车图案**带内 TM 命中（开拓银轨商店开张的备战态帧），
  命中中心落建档带内且跨帧稳定（同布局存档帧中心恒 (416,297)——位置稳定性回归）；
  商店未开张（开拓银轨<2）帧带内不命中（实测最高分 0.167 << 阈值 0.7）；
- 开拓商店面板开启态帧**不命中**：面板盖住横幅、仅左缘窄条露出——锁这个物理事实
  防模板误配（该画面不产 extras，识别面无消费；收店走徽记锚，见 cw_toggle_shop_panel）；
- 横幅解析：锚「打开商店」文本条目 → (余额, 开店点击点)；单行 / 两行渲染均可达；
  锚缺失 → 三元组全 None；锚在场数字缺失 → 余额 None 但点击点独立产出；
- 胶囊在场性解析：「有商品可购买」锚命中 → True；未读到 → None
  （False 不产出；⚠️ 游戏语义未收敛,见 src ``_parse_rail_shop_buyable`` docstring ——
  测试只锁识别行为,不锁游戏触发语义）。

带内 OCR 拼装端到端依赖 ctx,单测覆盖不到 ——
由实机 / 离线 analyze 验证兜底（src ``_read_rail_shop`` docstring 申报）。

fixture：rail_badge_prep_r4、rail_badge_consumed_r4、rail_badge_absent_r2 在
货币战争-备战/；rail_badge_shop_open_r4 实属开拓商店面板开启态画面
（建档「货币战争-备战-开拓商店」id_mark 双锚实测 is_precise），归档在
货币战争-备战-开拓商店/（test_id_mark 真阳性口径的画面身份归档）。
缺帧/缺模板 → skip。
"""
from __future__ import annotations

from functools import cache
from pathlib import Path

import cv2
import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from sr_od.application.currency_war.obs.recognizers.battle_prep_recognizer import (
    _RAIL_CAPSULE_RECT,
    _parse_rail_shop_buyable,
    find_rail_shop_train,
    parse_rail_shop_banner,
)

#: 列车图案搜索带 = 画面档「标识-银轨商店列车图案」pc_rect（建档单一源；晶矿回归同款硬编码先例）
_RAIL_TRAIN_RECT = Rect(325, 250, 500, 480)


def _screens_dir() -> Path:
    """向上定位中央归档库 ``screens/``（同 test_identity_obs 手法）。"""
    p = Path(__file__)
    while p != p.parent:
        cand = p / 'screens'
        if cand.is_dir() and (any(cand.glob('*/*.webp')) or any(cand.glob('*/*.png'))):
            return cand
        p = p.parent
    raise RuntimeError('未找到 screens/ 归档库')


#: 帧查找目录序：备战本体 + 开拓商店面板态（帧按画面身份归档,本测试按名字跨目录取）
_FRAME_DIRS: tuple[str, ...] = ('货币战争-备战', '货币战争-备战-开拓商店')


@cache
def _load_frame(name: str) -> np.ndarray | None:
    """读 fixture 帧（RGB 口径，框架截图同口径）；缺失 → None。"""
    d = _screens_dir()
    for dir_name in _FRAME_DIRS:
        for suffix in ('.webp', '.png'):
            f = d / dir_name / f'{name}{suffix}'
            if f.is_file():
                img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
                return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return None


def _require_frame(name: str) -> np.ndarray:
    img = _load_frame(name)
    if img is None:
        pytest.skip(f'存档截图缺失：screens/货币战争-备战[|开拓商店]/{name}.webp|png')
    return img


@cache
def _run_find(name: str) -> tuple[float, int, int] | None:
    """单帧只跑一次识别，结果供该帧全部断言共用。"""
    return find_rail_shop_train(_require_frame(name), _RAIL_TRAIN_RECT)


def _rail_tpl_missing() -> bool:
    from one_dragon.utils.file_utils import get_project_root
    p = (get_project_root() / 'assets' / 'template'
         / 'cw_rail_shop_train' / 'cw_rail_shop_train' / 'raw.webp')
    return not p.is_file()


pytestmark = pytest.mark.skipif(_rail_tpl_missing(), reason='银轨商店列车图案模板未归档')


@pytest.mark.parametrize('frame', [
    'rail_badge_prep_r4',        # 备战态：横幅在场
    'rail_badge_consumed_r4',    # 消费后回备战：横幅在场
    'rail_badge_capsule_prep_r4',  # 备战态（胶囊在场局）：横幅在场
])
def test_train_present_in_prep_states(frame: str) -> None:
    """备战态帧列车图案带内命中：score ≥ 阈值、中心恒 (416,297) 且落建档带内。

    中心等值锁 = 同布局存档帧的位置稳定性回归（识别锚漂移即红）。"""
    out = _run_find(frame)
    assert out is not None, f'{frame} 列车图案应命中（备战态横幅在场）'
    score, cx, cy = out
    assert score >= 0.7
    assert (cx, cy) == (416, 297), f'中心漂移: ({cx},{cy}) != (416,297)'
    assert 325 <= cx <= 500, f'cx={cx} 超出建档带 x [325,500]'
    assert 250 <= cy <= 480, f'cy={cy} 超出建档带 y [250,480]'


def test_train_miss_when_shop_closed() -> None:
    """商店未开张（开拓银轨<2）帧带内不命中（实测缺席帧带内最高分 0.167 << 阈值 0.7）。"""
    assert _run_find('rail_badge_absent_r2') is None


def test_train_miss_on_pioneer_panel_open() -> None:
    """开拓商店面板开启态帧不命中：面板盖住横幅、仅左缘窄条露出（实测最高分
    0.518 < 0.7）——锁「开启态横幅被盖」的物理事实防模板误配;该画面不产 extras,
    收店点击走徽记锚（cw_toggle_shop_panel）,本 miss 无生产消费面。"""
    assert _run_find('rail_badge_shop_open_r4') is None


def _ocr_item(x: int, y: int, w: int, h: int, data: str) -> OcrMatchResult:
    """构造带绝对坐标与文本的 OCR 结果（框架 OcrMatchResult 同构）。"""
    return OcrMatchResult(c=0.9, x=x, y=y, w=w, h=h, data=data)


def test_banner_parse_single_line_anchor() -> None:
    """单行渲染「打开商店 ×N」：锚条目自带数字直接取,点击点 = 锚 bbox 中心。"""
    balance, cx, cy = parse_rail_shop_banner(
        [_ocr_item(505, 274, 90, 21, '打开商店 ×330')])
    assert balance == 330
    assert (cx, cy) == (550, 284)


def test_banner_parse_two_line_anchor() -> None:
    """两行渲染（「打开商店」/「×N」分行）：余额取锚后第一条数字,点击点 = 锚中心。"""
    balance, cx, cy = parse_rail_shop_banner([
        _ocr_item(505, 274, 90, 21, '打开商店'),
        _ocr_item(560, 300, 33, 20, '×330'),
    ])
    assert balance == 330
    assert (cx, cy) == (550, 284)


def test_banner_parse_anchor_without_number_keeps_click_point() -> None:
    """锚在场但无数字（OCR 丢数字行）：余额 None 不伪造,开店点击点独立产出。"""
    balance, cx, cy = parse_rail_shop_banner(
        [_ocr_item(505, 274, 90, 21, '打开商店')])
    assert balance is None
    assert (cx, cy) == (550, 284)


def test_banner_parse_no_anchor_returns_all_none() -> None:
    """无锚（横幅不在场/被面板盖住）→ (None, None, None) 正确降级。"""
    assert parse_rail_shop_banner([]) == (None, None, None)
    assert parse_rail_shop_banner(
        [_ocr_item(109, 437, 180, 27, '羁绊面板行')]) == (None, None, None)


def test_banner_parse_noise_before_anchor() -> None:
    """锚前有带内噪声条目不干扰:仍锚「打开商店」条目取值。"""
    balance, cx, cy = parse_rail_shop_banner([
        _ocr_item(109, 437, 180, 27, '2/4/6/8/10'),
        _ocr_item(505, 274, 90, 21, '打开商店'),
        _ocr_item(560, 300, 33, 20, '×20'),
    ])
    assert balance == 20
    assert (cx, cy) == (550, 284)


def test_buyable_present_and_absent() -> None:
    """胶囊在场性：读到锚 → True；未读到 → None（False 不产出，见 src 口径裁定）。"""
    assert _parse_rail_shop_buyable(['有商品可购买']) is True
    assert _parse_rail_shop_buyable(['打开商店', '×330']) is None
    assert _parse_rail_shop_buyable([]) is None


def test_capsule_rect_covers_observed_y_band() -> None:
    """胶囊搜索带覆盖两局实测 y 域（一局 y≈345-375 / 另一局 y≈445-470）——
    胶囊 y 随局浮动,带收窄到任一实测域之外即漏检回归（旧带 438 起漏检
    345-375 局的教训,标定与扩带论证见 src ``_RAIL_CAPSULE_RECT`` 注释）。"""
    assert _RAIL_CAPSULE_RECT[1] <= 345, '胶囊带 y 下界须覆盖上布局实测 345'
    assert _RAIL_CAPSULE_RECT[3] >= 470, '胶囊带 y 上界须覆盖下布局实测 470'


# ===== 阶段读数(工具面):与流程侧同口径,不做数字回退 =====

def _phase_env(monkeypatch: pytest.MonkeyPatch, tokens: list[tuple[str, int, int]]) -> None:
    """``_read_phase_round_pure`` 桩环境:识别器模块内的 ``_ocr`` / ``_area_rect`` 打桩,
    不跑识别。"""
    import types

    import sr_od.application.currency_war.obs.recognizers.battle_prep_recognizer as bpr
    monkeypatch.setattr(bpr, '_ocr', lambda *_a, **_k: [
        types.SimpleNamespace(data=d, w=w, h=h) for d, w, h in tokens])
    monkeypatch.setattr(bpr, '_area_rect', lambda *_a, **_k: None)


@pytest.mark.parametrize(('tokens', 'expected'), [
    # 开商店态入场首帧:短横线漏检,两个数字记号——修前数字回退产出值域内假值 (2,2)
    ([('备战阶段', 81, 25), ('2', 17, 22), ('6', 17, 21)], None),
    ([('备战阶段', 81, 25), ('2-6', 53, 34)], (2, 6)),
    ([('备战阶段', 81, 25), ('1-3', 56, 34), ('0', 9, 6)], (1, 3)),
])
def test_read_phase_round_pure(monkeypatch: pytest.MonkeyPatch, tokens, expected) -> None:
    """``_read_phase_round_pure``:读数只认完整「X-Y」,杂散小记号不进拼接,读不到返 None
    (契约 = 该函数 docstring)。"""
    from sr_od.application.currency_war.obs.recognizers import battle_prep_recognizer as bpr
    _phase_env(monkeypatch, tokens)
    assert bpr._read_phase_round_pure(object(), None) == expected


@pytest.mark.parametrize(('screen', 'state', 'expected'), [
    ('货币战争-备战', '阶段杂散小记号-1-1', (1, 1)),          # 修前读成 1-10 → 值域外 → None
    ('货币战争-备战-开商店', '2-6入场首帧', None),            # 修前数字回退 → 假值 (2, 2)
])
def test_phase_sample_frames(test_context: SrTestContext, screen: str, state: str,
                             expected) -> None:
    """两张阶段样本帧整帧读数(契约 = ``_read_phase_round_pure`` docstring)。缺帧 skip。"""
    from sr_od.application.currency_war.obs.recognizers import battle_prep_recognizer as bpr
    if not test_context.has_screen(screen, state):
        pytest.skip(f'存档截图缺失:screens/{screen}/{state}.webp')
    assert bpr._read_phase_round_pure(test_context, test_context.load_screen(screen, state)) \
        == expected


# ===== ``read_prep_extras`` 的按键口径(识别链全打桩,只锁接线) =====

def _skeleton_env(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """``read_prep_extras`` 骨架环境:识别链上的读数全部打桩成「读不到」,
    只留 ``read_equips`` 为计数桩;返回它的调用记录(每次调用追加 1)。

    模板库桩成**已加载**(``ensure_equip_sift_templates`` 返回非 None),否则
    ``full_read=True`` 时也走不到 ``read_equips``,「商店收起时照读」那半边测不到。
    """
    import sr_od.application.currency_war.obs.cw_back_layout as back_layout
    import sr_od.application.currency_war.obs.recognizers.battle_prep_recognizer as bpr

    read_equips_calls: list[int] = []
    stubs: dict[str, object] = {
        '_ocr': lambda *_a, **_k: [],
        '_area_rect': lambda *_a, **_k: None,
        '_read_phase_round_pure': lambda *_a, **_k: None,
        'read_level': lambda *_a, **_k: 1,
        'read_gold': lambda *_a, **_k: 0,
        'read_board': lambda *_a, **_k: {},
        'read_streak': lambda *_a, **_k: None,
        'read_level_up_cost': lambda *_a, **_k: None,
        'read_hp_opt': lambda *_a, **_k: None,
        'read_deployed_count': lambda *_a, **_k: None,
        'read_deploy_cap': lambda *_a, **_k: None,
        'read_armory_boxes': lambda *_a, **_k: [],
        'read_front_aura_slot': lambda *_a, **_k: None,
        'read_ore_sights': lambda *_a, **_k: [],
        'read_bench_view': lambda *_a, **_k: None,
        'read_deployed_rows': lambda *_a, **_k: ([], []),
        'read_row_equipped': lambda *_a, **_k: {},
        '_read_rail_shop': lambda *_a, **_k: None,
        'ensure_portrait_templates': lambda *_a, **_k: {},
        'ensure_equip_tm_templates': lambda *_a, **_k: {},
        'ensure_equip_sift_templates': lambda *_a, **_k: {},
        'read_equips': lambda *_a, **_k: read_equips_calls.append(1) or [],
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(bpr, name, stub)
    monkeypatch.setattr(back_layout, 'select_back_layout', lambda *_a, **_k: (None, ''))
    return read_equips_calls


def test_shop_open_skips_reading_owned_equips(monkeypatch: pytest.MonkeyPatch) -> None:
    """商店开着时不读右侧装备栏(用户裁定:商店开的画面不识别右侧装备)。

    同一张帧调两次 ``read_prep_extras``:``full_read=False``(开商店识别器传入)时
    ``read_equips`` 未被调用、返回里没有 ``owned_equips`` 键;``full_read=True`` 时
    被调用、键在——后一半防止跳过的范围扩大到商店收起的时候。
    """
    import sr_od.application.currency_war.obs.recognizers.battle_prep_recognizer as bpr

    calls = _skeleton_env(monkeypatch)
    frame = np.zeros((1080, 1920, 3), np.uint8)

    shop_open = bpr.read_prep_extras(object(), frame, full_read=False)
    assert calls == [] and 'owned_equips' not in shop_open

    shop_closed = bpr.read_prep_extras(object(), frame, full_read=True)
    assert calls == [1] and 'owned_equips' in shop_closed
