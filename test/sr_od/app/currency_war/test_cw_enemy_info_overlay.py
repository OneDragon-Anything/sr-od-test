"""「货币战争-敌人信息浮层」id_mark 测试锁。

档案 ``currency_war_enemy_info.yml``(11 area,含 id_mark「标识-敌方信息」)的
真阳性锁:fixture 帧(screens/货币战争-位面详情/敌人信息浮层.png,1920×1080
佩佩局实拍,建档 commit e42bbdfe)上 id_mark 全命中 = is_precise 精准匹配。
坐标漂移 / OCR 形变 / 建档误改任一发生,本锁即红——浮层入口判定(备战点
难度框进入)失效的前置信号。

fixture 目录归属说明:帧现挂 ``screens/货币战争-位面详情/`` 下,与建档 doc
(``docs/game/screens/货币战争-敌人信息浮层.md``)的 source_image 指针一致;
按屏找帧易漏的问题以本测试文件为登记点,挪目录需同步改 doc(共享文档,
另行确认),故暂留原位。

背景对账报告:``.debug/temp/currency_war/redesign/ENEMY_OVERLAY_RECON.md``。

需完整 SR 数据栈(screen_info + 模板 + OCR),CI clean checkout 无 → 本地跑。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    bool(os.environ.get('CI')),
    reason='需完整 SR 数据栈(screen_info / 模板 / OCR),CI clean checkout 无;本地有数据则跑',
)

_SCREEN: str = '货币战争-敌人信息浮层'

# 档案 11 area 的 1080p 坐标锁(单一源 = currency_war_enemy_info.yml;
# 改坐标属建档变更,先 MCP upsert_screen_area 改档案,再同步本表并重验 fixture)。
_EXPECTED_AREAS: dict[str, list[int]] = {
    '标识-敌方信息': [90, 40, 215, 90],      # id_mark,text=敌方信息
    '区域-敌方波次列表': [25, 120, 1030, 700],
    '区域-敌人详情卡': [1230, 150, 1870, 560],
    '文本-敌人名': [1300, 235, 1580, 290],
    '区域-词缀横条': [40, 965, 1430, 1015],
    '文本-敌人难度值': [75, 965, 340, 1015],
    '页签-遭遇其一': [583, 100, 960, 145],
    '页签-遭遇其二': [965, 100, 1330, 145],
    '页签-技能': [1650, 165, 1790, 200],
    '按钮-关闭': [1825, 35, 1900, 95],
    '文本-词缀读数带': [340, 965, 1045, 1015],
}


def _fixture_path() -> Path:
    """fixture 帧路径(png,挂在位面详情目录——见模块 docstring 归属说明)。"""
    return (Path(__file__).parents[4] / 'screens' / '货币战争-位面详情'
            / '敌人信息浮层.png')


def _load_fixture(test_context):
    """读 fixture 为 RGB(生产语义),缺文件时 skip 而非 error。"""
    import cv2
    import numpy as np

    p = _fixture_path()
    if not p.exists():
        pytest.skip(f'fixture 缺失: {p}')
    img_bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 读取失败: {p}'
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def _get_screen_info(test_context):
    """取画面档案;未建档时 skip(与通用 id_mark 测试同口径)。"""
    try:
        info = test_context.screen_loader.get_screen(_SCREEN)
    except Exception:
        pytest.skip(f'无 screen_info:{_SCREEN}')
    if info is None:
        pytest.skip(f'无 screen_info:{_SCREEN}')
    return info


def test_enemy_overlay_id_mark_precise(test_context) -> None:
    """真阳性:fixture 上 id_mark 全命中 → is_precise 精准匹配。"""
    from one_dragon.base.screen import screen_utils

    info = _get_screen_info(test_context)
    assert any(a.id_mark for a in info.area_list), (
        f'{_SCREEN} 档案丢失 id_mark(id_mark 是本屏精准匹配唯一依据)')
    frame = _load_fixture(test_context)
    assert screen_utils.is_target_screen(test_context, frame, screen_info=info), (
        f'{_SCREEN} id_mark 未在 fixture 全命中(坐标漂移 / OCR 形变 / 建档误改),'
        '浮层入口判定失效前置信号')


def test_enemy_overlay_area_rects_locked(test_context) -> None:
    """档案一致性:11 area 名称与 pc_rect 与本文件坐标锁一致。"""
    info = _get_screen_info(test_context)
    actual = {
        a.area_name: [a.pc_rect.x1, a.pc_rect.y1, a.pc_rect.x2, a.pc_rect.y2]
        for a in info.area_list
    }
    assert actual == _EXPECTED_AREAS, (
        f'{_SCREEN} 档案 area 与坐标锁不一致(建档被改而测试未同步,或反向)。\n'
        f'档案: {actual}\n锁: {_EXPECTED_AREAS}')
    assert actual['标识-敌方信息'] == _EXPECTED_AREAS['标识-敌方信息']
