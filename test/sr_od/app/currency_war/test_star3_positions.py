"""star3 全位置识别回归 + 全帧校验(3.5.3 收口,2026-08-17 M72 采集)。

两层断言:
1. 目标位断言:每张 fixture 的三月七(3星)所在槽 read_star==3。
2. **全帧真值断言(用户指示 2026-08-17)**:同一帧其余 18 槽位是同一阵容的真实星级
   (2星占位角色/1星角色/空槽=1),与 truth.json 逐一一致——19 张 × 19 槽 = 361 个
   校验点,把「其他位置识别」也纳入覆盖(read_star 对 1/2 星在 3星采集帧上的表现)。

真值表生成:.debug/temp/currency_war/cw_dev/star3_truth_gen.py(一次性,数据进
truth.json 固化;阵容会变,真值跟 fixture 走不跟时间走)。
采集教训(存档):①「停 bot 保画面」在备战不成立(倒计时自动出战推进);②事件
overlay 盖棋盘时拖拽静默失败,批次间必须验证落位;③VLM 看不清星数,定位用
read_star 全帧扫描(客观优先)。
"""
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

from one_dragon.utils import cv2_utils  # noqa: E402
from sr_od.application.currency_war.obs.cw_identity_obs import read_star  # noqa: E402
from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect  # noqa: E402
from test.conftest import SrTestContext  # noqa: E402

_SLOTS = [f'前排-{i}' for i in range(1, 5)] + [f'后排-{i}' for i in range(1, 7)] \
    + [f'备战栏-{i}' for i in range(1, 10)]
_FIX_DIR = _REPO / 'sr-od-test' / 'screens' / 'star3_slots'


def _load_truth() -> dict[str, dict[str, int]] | None:
    p = _FIX_DIR / 'truth.json'
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8'))


def test_star3_all_positions_read_3(test_context: SrTestContext) -> None:
    """层1:19 张 fixture 目标位全读 3。

    (2026-08 精简审计:改用 session 级 test_context fixture,
    避免自建 SrContext 重复 init——全量跑时 ctx 只初始化一次。)
    """
    sr_ctx = test_context
    fixes = sorted(_FIX_DIR.glob('*.webp'))
    if not fixes:
        pytest.skip('star3_slots/ fixture 缺')
    rects = {s: _area_rect(sr_ctx, s, '货币战争-备战') for s in _SLOTS}
    for fix in fixes:
        img = cv2_utils.read_image(str(fix))
        expect = fix.stem.replace('备战-', '备战栏-')
        rect = rects[expect]
        assert rect is not None, f'{expect} area 缺'
        got = read_star(img[rect.y1:rect.y2, rect.x1:rect.x2])
        assert got == 3, f'{fix.stem}: 目标位 3星应读 3,实得 {got}'


def test_star3_full_frame_truth(test_context: SrTestContext) -> None:
    """层2(全帧校验):每张 fixture 全部 19 槽位与真值表一致(361 校验点)。

    真值 = 采集时同帧其余槽位的真实星级(2星占位角色/1星/空槽 fallback=1)。
    防 read_star 在非 3 星槽上的回归(此前只测过目标位)。
    """
    sr_ctx = test_context
    truth = _load_truth()
    if truth is None:
        pytest.skip('truth.json 缺(先跑 star3_truth_gen.py)')
    fixes = sorted(_FIX_DIR.glob('*.webp'))
    assert fixes, 'star3_slots/ fixture 缺'
    rects = {s: _area_rect(sr_ctx, s, '货币战争-备战') for s in _SLOTS}
    checked = 0
    for fix in fixes:
        row = truth.get(fix.stem)
        assert row is not None, f'{fix.stem} 不在 truth.json'
        img = cv2_utils.read_image(str(fix))
        for slot, expected in row.items():
            rect = rects.get(slot)
            assert rect is not None, f'{slot} area 缺'
            got = read_star(img[rect.y1:rect.y2, rect.x1:rect.x2])
            assert got == expected, (
                f'{fix.stem}/{slot}: 真值 {expected} 实得 {got}(read_star 回归)')
            checked += 1
    assert checked >= 19 * 15, f'校验点异常少: {checked}(应≈361)'
