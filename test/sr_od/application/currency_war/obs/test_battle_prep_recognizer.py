"""银轨商店入口识别（``find_rail_shop_badge`` 带内模板匹配 + 余额/可买解析）fixture 回归。

锁的设计约定（标定依据见 src battle_prep_recognizer.py rail_shop 常量块注释）：
- 在场判定：开拓银轨商店开张三态（备战 / 商店面板开启 / 消费回备战）徽记带内命中
  且坐标落建档带内；商店未开张（开拓银轨<2）帧带内不命中
  （实测分数带：在场 1.0 / 缺席 0.241，阈值 0.7 居中分离）；
- 余额解析：横幅「打开商店 ×N」锚正则提取（单行 / 两行渲染均可达）；锚缺失 → None；
- 可买提示解析：「有商品可购买」锚命中 → True；未读到 → None
  （False 不产出，口径见 src ``_parse_rail_shop_buyable`` docstring）。

OCR 端到端（余额/可买的带内 OCR 拼装）依赖 ctx,单测覆盖不到 ——
由实机 / 离线 analyze 验证兜底（src ``_read_rail_shop`` docstring 申报）。

fixture（货币战争-备战/）：rail_badge_prep_r4、rail_badge_shop_open_r4、
rail_badge_consumed_r4、rail_badge_absent_r2。缺帧/缺模板 → skip。
"""
from __future__ import annotations

from functools import cache
from pathlib import Path

import cv2
import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.obs.recognizers.battle_prep_recognizer import (
    find_rail_shop_badge,
    _parse_rail_shop_balance,
    _parse_rail_shop_buyable,
)

#: 徽记搜索带 = 画面档「标识-银轨商店徽记」pc_rect（建档单一源；晶矿回归同款硬编码先例）
_RAIL_BADGE_RECT = Rect(230, 220, 310, 580)


def _screens_dir() -> Path:
    """向上定位中央归档库 ``screens/``（同 test_identity_obs 手法）。"""
    p = Path(__file__)
    while p != p.parent:
        cand = p / 'screens'
        if cand.is_dir() and (any(cand.glob('*/*.webp')) or any(cand.glob('*/*.png'))):
            return cand
        p = p.parent
    raise RuntimeError('未找到 screens/ 归档库')


@cache
def _load_frame(name: str) -> np.ndarray | None:
    """读 fixture 帧（RGB 口径，框架截图同口径）；缺失 → None。"""
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
        pytest.skip(f'存档截图缺失：screens/货币战争-备战/{name}.webp|png')
    return img


@cache
def _run_find(name: str) -> tuple[float, int, int] | None:
    """单帧只跑一次识别，结果供该帧全部断言共用。"""
    return find_rail_shop_badge(_require_frame(name), _RAIL_BADGE_RECT)


def _rail_badge_tpl_missing() -> bool:
    from one_dragon.utils.file_utils import get_project_root
    p = (get_project_root() / 'assets' / 'template' / 'currency_war'
         / 'cw_rail_shop_badge' / 'raw.webp')
    return not p.is_file()


pytestmark = pytest.mark.skipif(_rail_badge_tpl_missing(), reason='银轨商店徽记模板未归档')


@pytest.mark.parametrize('frame', [
    'rail_badge_prep_r4',        # 备战态：徽记在场
    'rail_badge_shop_open_r4',   # 商店面板开启态：徽记仍在场
    'rail_badge_consumed_r4',    # 消费后回备战：徽记仍在
])
def test_badge_present_in_shop_open_states(frame: str) -> None:
    """商店开张三态徽记带内命中：score ≥ 阈值且中心落建档带内（点它打开商店）。"""
    out = _run_find(frame)
    assert out is not None, f'{frame} 徽记应命中（商店开张三态都在场）'
    score, cx, cy = out
    assert score >= 0.7
    assert 230 <= cx <= 310, f'cx={cx} 超出建档带 x [230,310]'
    assert 220 <= cy <= 580, f'cy={cy} 超出建档带 y [220,580]'


def test_badge_absent_when_shop_closed() -> None:
    """商店未开张（开拓银轨<2）帧带内不命中（实测缺席帧带内最高分 0.241 << 阈值 0.7）。"""
    assert _run_find('rail_badge_absent_r2') is None


def test_balance_parse_single_line_anchor() -> None:
    """单行渲染「打开商店 ×N」：锚条目自带数字直接取。"""
    assert _parse_rail_shop_balance(['打开商店 ×330']) == 330


def test_balance_parse_two_line_anchor() -> None:
    """两行渲染（「打开商店」/「×N」分行）：取锚后第一条数字。"""
    assert _parse_rail_shop_balance(['打开商店', '×330']) == 330


@pytest.mark.parametrize('texts', [
    ['打开商店'],            # 锚在场但无数字（OCR 丢数字行）→ None 不伪造
    ['羁绊面板行'],           # 无锚（带外面板文本）→ None
    [],                      # 空读 → None
])
def test_balance_no_anchor_or_number_returns_none(texts: list[str]) -> None:
    """锚缺失 / 数字缺失 → None（正确降级，不伪造余额）。"""
    assert _parse_rail_shop_balance(texts) is None


def test_buyable_present_and_absent() -> None:
    """可买提示：读到锚 → True；未读到 → None（False 不产出，见 src 口径裁定）。"""
    assert _parse_rail_shop_buyable(['有商品可购买']) is True
    assert _parse_rail_shop_buyable(['打开商店', '×330']) is None
    assert _parse_rail_shop_buyable([]) is None
