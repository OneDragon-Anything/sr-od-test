"""货币战争 视觉身份观测测试(cw_identity_obs)。

- 纯单元:``resolve_char_name``(avatar_id → 规范名)。
- 集成:``identify_slots`` / ``read_deployed_chars`` 对实机 fixture(``deployed_p1r9.webp``)
  → 前排 4 角色身份。证明 ``character_avatar`` 脸近景库对备战半身立绘可匹配(D-75)。
"""
from __future__ import annotations

import inspect

import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import file_utils
from sr_od.application.currency_war.currency_war_char_id import load_avatar_templates
from sr_od.application.currency_war.cw_identity_obs import (
    identify_slots,
    read_deployed_chars,
    read_star,
    resolve_char_name,
)
from sr_od.context.sr_context import SrContext
from test.conftest import SrTestContext

# character_avatar 脸库在主仓 assets/(sr_od 所在 repo 根;同 conftest.application_plugin_dirs 定位法)
_REPO_ROOT = file_utils.find_src_dir(inspect.getfile(SrContext)).parent
_AVATAR_DIR = _REPO_ROOT / 'assets' / 'template' / 'character_avatar'


def test_resolve_char_name_basic() -> None:
    """avatar_id(主游英文 id)→ 货币战争规范名(直接命中 roster)。"""
    assert resolve_char_name('pela') == '佩拉'
    assert resolve_char_name('herta') == '黑塔'
    assert resolve_char_name('saber') == 'Saber'
    assert resolve_char_name('huohuo') == '藿藿'


def test_resolve_char_name_unknown() -> None:
    """avatar_id 不在主游角色表 → None。"""
    assert resolve_char_name('nonexistent_xyz') is None


@pytest.fixture(scope='module')
def avatar_templates():
    """加载 character_avatar 脸库(预计算 SIFT 关键点/描述子);模块内复用。"""
    return load_avatar_templates(_AVATAR_DIR)


def test_identify_deployed_front_row(test_context: SrTestContext, avatar_templates) -> None:
    """identify_slots:实机 fixture(deployed_p1r9)前排 4 槽 → [佩拉,黑塔,Saber,藿藿]。

    硬编码 yml rect(ground truth);D-75 证脸库可匹配备战半身立绘(4/4 强命中)。后排空(VLM 计数
    幻觉,实际无后排部署)→ 不在该断言内。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        pytest.skip('fixture deployed_p1r9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    front = [(i, Rect(*r)) for i, r in enumerate([
        [677, 329, 810, 467], [823, 329, 951, 467],
        [969, 329, 1097, 467], [1109, 329, 1241, 467]], start=1)]
    chars = identify_slots(screen, avatar_templates, front, 'front')
    assert [c.char_id for c in chars] == ['佩拉', '黑塔', 'Saber', '藿藿']
    assert all(c.position_pref == 'front' for c in chars)


def test_read_deployed_chars_via_ctx(test_context: SrTestContext, avatar_templates) -> None:
    """read_deployed_chars:经 ctx.screen_info 取槽位 rect → 前排 4 角色身份(集成,验 screen_info 接线)。

    与 ``test_identify_deployed_front_row`` 互补:前者硬编码 rect 测纯 CV 核心,本测经 ctx screen_loader
    取 rect(= ``_ctx_slots``),验 screen_info area 名(前排-1..4 / 后排-1..6)接线正确。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        pytest.skip('fixture deployed_p1r9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    chars = read_deployed_chars(test_context, screen, avatar_templates)
    front = [c.char_id for c in chars if c.position_pref == 'front']
    assert front == ['佩拉', '黑塔', 'Saber', '藿藿']
    # 后排空(fixture 该态无后排部署;VLM 曾幻觉"1 个后排",实为空)
    assert [c for c in chars if c.position_pref == 'back'] == []


def test_read_star_front_row_1star(test_context: SrTestContext) -> None:
    """read_star:deployed_p1r9 前排 4 槽(佩拉/黑塔/Saber/藿藿,早期 round → 1 星)→ read_star 都=1。

    金星计数(立绘底部金色五角星)。⚠️ 仅 1 星样本验过(2/3 星缺 live 样本);逻辑同(数金星个数),
    2/3 星待后期回合采到样本再补断言。
    """
    if not test_context.has_screen('货币战争-备战', 'deployed_p1r9'):
        pytest.skip('fixture deployed_p1r9.webp 未采')
    screen = test_context.load_screen('货币战争-备战', 'deployed_p1r9')
    # 前排-1..4 rect(同 test_identify_deployed_front_row ground truth)= 采 star_front_1..4 的槽位
    front_rects = [Rect(*r) for r in [
        [677, 329, 810, 467], [823, 329, 951, 467],
        [969, 329, 1097, 467], [1109, 329, 1241, 467]]]
    for r in front_rects:
        assert read_star(screen[r.y1:r.y2, r.x1:r.x2]) == 1, f'前排槽 {r} 应为 1 星(1 个金星)'
