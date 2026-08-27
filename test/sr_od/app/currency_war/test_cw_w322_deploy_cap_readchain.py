# -*- coding: utf-8 -*-
"""W322 行为锁:deploy_cap 拒信族根因 = 等级/XP 小字 OCR 双失读 → 启发式等级虚高。

判读实证(2026-08-27 run48 前后窗口,obs_conflicts.jsonl deploy_cap_domain 30 条):
冲突帧画面自洽(paddle「3/3」+Lv.3、「3/4」+Lv.4),虚高全在 state.level 侧 ——
「文本-等级」与「文本-升级所需经验」两个小字区原生分辨率 det 漏检 → 双失读 →
``_expected_level`` 启发式兜底(P1 早期假设已买经验,系统性偏高 +2:1-2→5、1-4→6)
→ cap(3)<level(5) 域守卫拒信 deploy_cap=None、prep_director 留证 deploy_cap_vs_level。

修法(识别语义零改动,ADR-0420 域外双帧采信语义保持):
- 小字区裁剪 + 3x 放大 OCR(``_ocr_upscaled``,read_gold 同款手法);
- XP 解析两级:斜杠 normalize(D-53)+ 斜杠被识成数字 '1' 时按等级表分母先验插入
  ("2/4"→"214"、"4/6"→"416" 冲突帧实测形态);
- 读链单一源 ``read_level_raw_opt``(决策/三源解析/完成验证共用)。

fixture = 今日冲突帧实拍(cw_conflict_lv3_xp24_prep_frame.png / cw_conflict_lv4_xp26_prep_frame.png),
真实 OCR 锁「修复后这些帧可读」;mock 锁解析行为不回归。
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.cw_observation import (
    _level_from_xp,
    _parse_xp_pair,
    read_level_raw_opt,
    read_xp_progress,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

_DIR = Path(__file__).parent
_FIX_LV3 = _DIR / 'cw_conflict_lv3_xp24_prep_frame.png'   # 备战 1-2:Lv.3、XP 2/4、paddle 3/3
_FIX_LV4 = _DIR / 'cw_conflict_lv4_xp26_prep_frame.png'   # 备战 1-4:Lv.4、XP 2/6、paddle 3/4


def _load_fixture_rgb(path: Path) -> np.ndarray:
    img_bgr = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {path}'
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB


# ===== 锁①:_parse_xp_pair 两级解析(今日冲突帧 OCR 形态回归) =====

def test_parse_xp_pair_normal_slash() -> None:
    """斜杠正常可读:直读 X/Y(既有契约形态)。"""
    assert _parse_xp_pair('2/6') == (2, 6)
    assert _parse_xp_pair('4/20') == (4, 20)
    assert _parse_xp_pair('0/4') == (0, 4)


def test_parse_xp_pair_slash_read_as_one() -> None:
    """斜杠被识成数字 '1'(W322 冲突帧实测 "214"/"416"):按等级表分母先验插 '/'。"""
    assert _parse_xp_pair('214') == (2, 4)      # 23dee97a 帧 "2/4" 实读形态
    assert _parse_xp_pair('416') == (4, 6)      # 77a0e871 帧 "4/6" 实读形态
    assert _parse_xp_pair('2140') == (2, 40)    # 6 级门槛 40 同族
    # 非法拆分不采:任何 '1' 位拆出的分母都不在等级表 → None(先验守卫,防普通数字串误拆)
    assert _parse_xp_pair('919') is None       # 9/9:9 非合法分母
    assert _parse_xp_pair('515') is None       # 5/5 同理
    assert _parse_xp_pair('购买经验') is None


def test_parse_xp_pair_slash_noise_normalized() -> None:
    """数字间非数字单字符 → '/' normalize(D-53 同款,先行级)。"""
    assert _parse_xp_pair('2l6') == (2, 6)
    assert _parse_xp_pair('2/6/') == (2, 6)     # 尾部残留不干扰首个 X/Y


# ===== 锁②:read_level_raw_opt 无兜底契约 + 放大读不破坏 mock 注入 =====

def test_read_level_raw_opt_contract(test_context: SrTestContext, monkeypatch) -> None:
    """直读无兜底:读到返回值,失读/越界返 None(完成验证依赖此契约)。"""
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': 'Lv.3'})()])
    assert read_level_raw_opt(test_context, None) == 3
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': 'Lv.'})()])
    assert read_level_raw_opt(test_context, None) is None
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': '14'})()])
    assert read_level_raw_opt(test_context, None) is None   # LEVEL_MAX=10 域外按失读


def test_read_xp_progress_keeps_domain_guard(test_context: SrTestContext, monkeypatch) -> None:
    """read_xp_progress sanity 不放松:cur>next / 无 X/Y 仍 None(既有契约,修法不放宽)。"""
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': '20/4'})()])
    assert read_xp_progress(test_context, None) is None
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list',
                        lambda **kw: [type('R', (), {'data': '购买经验'})()])
    assert read_xp_progress(test_context, None) is None


# ===== 锁③:今日冲突帧真实 OCR 回归(修复前 lv_raw/xp 双 None;修复后全可读) =====

def test_conflict_frame_lv3_xp24_readable(test_context: SrTestContext) -> None:
    """23dee97a 帧:修复前「文本-等级」与 XP 双失读(→启发式虚高 5);修复后 lv=3、xp=(2,4)。"""
    from sr_od.application.currency_war.cw_obs_core import _area_rect
    if _area_rect(test_context, '文本-等级') is None:
        test_context.screen_loader.reload(from_separated_files=True)
    screen = _load_fixture_rgb(_FIX_LV3)
    assert read_level_raw_opt(test_context, screen) == 3
    assert read_xp_progress(test_context, screen) == (2, 4)
    assert _level_from_xp((2, 4)) == 3


def test_conflict_frame_lv4_xp26_readable(test_context: SrTestContext) -> None:
    """6f41536e 帧:修复前 XP 失读(lv OCR 偶读 4,XP 兜底缺位);修复后 xp=(2,6)。"""
    from sr_od.application.currency_war.cw_obs_core import _area_rect
    if _area_rect(test_context, '文本-等级') is None:
        test_context.screen_loader.reload(from_separated_files=True)
    screen = _load_fixture_rgb(_FIX_LV4)
    assert read_level_raw_opt(test_context, screen) == 4
    assert read_xp_progress(test_context, screen) == (2, 6)
    assert _level_from_xp((2, 6)) == 4


def test_conflict_frame_level_resolves_in_domain(test_context: SrTestContext) -> None:
    """端到端:冲突帧三源解析后 level 与 paddle cap 自洽入域(cap≥level),域守卫不再拒信。"""
    from sr_od.application.currency_war.cw_obs_core import _area_rect
    from sr_od.application.currency_war.cw_observation import (
        _expected_level,
        _resolve_level,
        read_deploy_cap_debounced,
    )
    if _area_rect(test_context, '文本-等级') is None:
        test_context.screen_loader.reload(from_separated_files=True)
    for path, truth_lv, truth_cap in ((_FIX_LV3, 3, 3), (_FIX_LV4, 4, 4)):
        screen = _load_fixture_rgb(path)
        lv_raw = read_level_raw_opt(test_context, screen)
        xp_lv = _level_from_xp(read_xp_progress(test_context, screen))
        # plane/round 传帧内真值(该帧备战阶段;phase_round 非本批修复对象)
        level, _ev, _auth = _resolve_level(lv_raw, _expected_level(1, truth_lv), xp_lv, 0)
        assert level == truth_lv, f'{path.name}: level={level} 应为 {truth_lv}'
        cap = read_deploy_cap_debounced(test_context, screen, level)
        assert cap == truth_cap, f'{path.name}: cap={cap} 应为 {truth_cap}(拒信=None 即回归)'


def test_prep_actions_level_raw_uses_shared_reader() -> None:
    """完成验证直读与决策读链单一源(prep_actions._read_level_raw 委托 read_level_raw_opt)。"""
    import inspect

    from sr_od.application.currency_war import prep_actions
    src = inspect.getsource(prep_actions._read_level_raw)
    assert 'read_level_raw_opt' in src, '完成验证直读应委托单一源(重复裁剪 OCR 实现已删)'
