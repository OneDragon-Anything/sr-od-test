"""分发身份语料回归测试(两阶段身份分发的语料纪律可执行锁)。

纪律单一源 = skill 反馈「分发用画面身份必须过语料验证」+ flow/outer_loop.md §2.2:
每画面身份须两向验证——本画面全部已存档实机帧 True + 堆叠底图/兄弟画面帧 False。
本测试锁两向:
- True 向:阶段一身份清单语料帧上,get_match_screen_name 必须返回本画面屏名;
- 默认向:备战语料帧上,阶段一必须 miss(备战不在清单,身份组合语料误杀
  dc435da4d)且阶段二双锚(购买经验∧出战)必须命中(备战默认分支的入场判据)。
新增分发画面 = 补语料帧 + 在 CASES 加一行。

慢速集:全图 OCR × N 帧,单条 >2s(slow_marks 登记)。
"""
from pathlib import Path

import pytest
from test.conftest import SrTestContext

from one_dragon.base.screen.screen_utils import (
    FindAreaResultEnum,
    find_area_in_screen,
    get_match_screen_name,
)

_SCREENS_DIR = Path(__file__).parents[4] / 'screens'

#: 阶段一身份清单语料(True 向):帧 → 期望屏名
IDENTITY_CASES: list[tuple[str, str]] = [
    ('货币战争-备战-遭遇锁定/锁定态.webp', '货币战争-备战-遭遇锁定'),
    ('货币战争-列车同行/伙伴遮罩-备战透出.webp', '货币战争-列车同行'),
    ('货币战争-列车同行/伙伴遮罩-未选中.webp', '货币战争-列车同行'),
    ('货币战争-备战-开商店/shop_open.webp', '货币战争-备战-开商店'),
    ('货币战争-备战-角色详情/char_detail_equipped.webp', '货币战争-备战-角色详情'),
    ('货币战争-备战-专家邀请函/弹窗.webp', '货币战争-备战-专家邀请函'),
    ('货币战争-备战-武装箱选择/box_open.webp', '货币战争-备战-武装箱选择'),
]

#: 阶段二默认分支语料:阶段一必须 miss(返回 None)+ 双锚必须命中
PREP_DEFAULT_CASES: list[str] = [
    '货币战争-备战/shop_closed.webp',
    '货币战争-备战/shop_closed_a8_start.webp',
    '货币战争-备战/后排8槽-P3局.webp',
]


def test_dispatch_corpus_identity_true_direction(test_context: SrTestContext) -> None:
    """阶段一:身份清单语料帧必须判定为本画面屏名。"""
    from sr_od.application.currency_war.operations.cw_loop import CwLoop

    for rel, expected in IDENTITY_CASES:
        path = _SCREENS_DIR / rel
        if not path.exists():
            pytest.skip(f'语料帧缺失: {rel}')
        screen = _read(path)
        name = get_match_screen_name(
            test_context, screen, screen_name_list=list(CwLoop.CW_DISPATCH_SCREENS))
        assert name == expected, f'语料帧 {rel} 分发判定 {name!r} ≠ {expected!r}'


def test_dispatch_corpus_prep_default_direction(test_context: SrTestContext) -> None:
    """阶段二:备战语料帧上阶段一必须 miss,且双锚默认分支判据必须命中。"""
    for rel in PREP_DEFAULT_CASES:
        path = _SCREENS_DIR / rel
        if not path.exists():
            pytest.skip(f'语料帧缺失: {rel}')
        screen = _read(path)
        name = get_match_screen_name(
            test_context, screen,
            screen_name_list=_prep_excluded_dispatch_names(test_context))
        assert name is None, \
            f'语料帧 {rel} 阶段一误命中 {name!r}(备战不在清单,应为 miss)'
        for _area in ('备战标识-购买经验', '按钮-出战'):
            area = test_context.screen_loader.get_area('货币战争-备战', _area)
            r = find_area_in_screen(test_context, screen, area, crop_first=False)
            assert r == FindAreaResultEnum.TRUE, \
                f'语料帧 {rel} 备战双锚 {_area} 未命中({r})'


def _read(path: Path):
    from one_dragon.utils import cv2_utils
    screen = cv2_utils.read_image(str(path))
    assert screen is not None, f'语料帧读取失败: {path}'
    return screen


def _prep_excluded_dispatch_names(test_context: SrTestContext) -> list[str]:
    from sr_od.application.currency_war.operations.cw_loop import CwLoop
    return list(CwLoop.CW_DISPATCH_SCREENS)
