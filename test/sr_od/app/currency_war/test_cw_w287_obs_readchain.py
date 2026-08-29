# -*- coding: utf-8 -*-
"""观测读链修复批锁(ADR-0417):商店行/羁绊计数不再当部署数 + board 裁决翻转。

背景(分层抽样实证,`.debug/temp/currency_war/w285_obs_conflict_sampling.md`):
- deployed_align 3/6 误判:旧对齐目标 ``min(sum(board), level)`` 把羁绊计数(多阵营
  角色重复计)当部署数,补齐/截断幻影;
- tracking 空板帧幻影 2 张:底部商店行/备战栏被读链误当部署;
- board 3/6 采 computed 错:左栏徽标(OCR)才是画面事实,旧裁决采身份 computed。

fixture = 判读过的实机帧(自 shots 目录拷入本目录,框架 ``cv2_utils.read_image``
RGB 口径直读)。三条帧锁 + 源码锁,纯离线。
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from one_dragon.utils import cv2_utils
import sr_od.application.currency_war.cw_observation as obs_mod
from sr_od.application.currency_war.cw_observation import (
    _board_pairs,
    read_deployed_count,
)
from sr_od.application.currency_war.kernel.cw_state import rebuild_deployed_from_board

_IMG_DIR = Path(__file__).parent


def _load(name: str):
    p = _IMG_DIR / name
    if not p.exists():
        pytest.skip(f'fixture 缺失:{name}')
    return cv2_utils.read_image(str(p))


def test_paddle_excludes_bench_row_on_empty_board(test_context) -> None:
    """空板帧(1-1,0/3,底部备战栏 4 卡)→ paddle X=0。

    tracking 幻影帧(6796888e)锁:部署数目标取舞台指示,几何上不含底部
    商店行/备战栏 —— 空板不再幻影出部署角色。旧链 board 徽标/计数源无此保证。
    """
    screen = _load('w287_tracking_empty_6796888e.png')
    n = read_deployed_count(test_context, screen)
    assert n == 0, f'空板帧部署数应为 0(底部 4 卡是备战栏,不计部署),实得 {n}'


def test_paddle_obscured_board_sum_is_not_deploy_count(test_context) -> None:
    """实部署 4 帧(前台2+后台2,角色详情 overlay 遮 paddle)→ 对齐基准行为锁。

    deployed_align 误判帧(37e6d7fd)双断言:
    - paddle 被 overlay 遮挡 → read_deployed_count=None → read_game_state 跳过
      对齐(tracked 4 保真,宁缺勿造);
    - 同帧左栏徽标羁绊和 = 8 ≠ 4 —— 实证 board 羁绊和当部署数必错
      (多阵营角色重复计),旧 ``min(sum(board), level)`` 目标即病根。
    """
    screen = _load('w287_deployed_align_37e6d7fd.png')
    n = read_deployed_count(test_context, screen)
    assert n is None, f'paddle 被 overlay 遮挡应读不到(None → 跳过对齐),实得 {n}'
    pairs, _honest = _board_pairs(test_context, screen)
    bond_sum = sum(c for c, _nt in pairs.values())
    assert bond_sum >= 7, f'该帧徽标羁绊和应≥7(≠实部署4,多阵营重复计),实得 {bond_sum}'


def test_board_pairs_reads_badge_truth(test_context) -> None:
    """左栏徽标「盛会之星=2」帧 → _board_pairs 读 2(徽标=画面事实)。

    board 误裁帧(b6fc9934)锁:OCR 徽标行真值可读;旧裁决在该帧采
    computed=1(错)。裁决翻转后此读数即采信源。
    """
    screen = _load('w287_board_b6fc9934.png')
    pairs, honest = _board_pairs(test_context, screen)
    assert honest, '徽标帧应有至少一行 X/Y 真解析(honest)'
    assert pairs.get('盛会之星', (None,))[0] == 2, \
        f'徽标「盛会之星」应读 2(画面事实),实得 {pairs.get("盛会之星")}'


def test_rebuild_cap_zero_blocks_phantom() -> None:
    """重建上限 0(paddle 空板)→ 0 幻影部署;上限 2 → 截到 2。

    锁 ``rebuild_deployed_from_board`` 的 max_count 语义 = read_game_state 重建
    分支 ``min(level, paddle X)`` 的依赖:board 徽标误读(如 6)不再幻影出
    超额部署角色(空板帧 同根)。注意返回是**槽位表**(定长含 None,
    ADR-0392),计数走占用数。
    """
    board = {'盛会之星': 6}
    _occ = lambda lst: sum(1 for x in lst if x is not None)
    assert _occ(rebuild_deployed_from_board(board, max_count=0)) == 0
    assert _occ(rebuild_deployed_from_board(board, max_count=2)) == 2


def test_source_deployed_align_uses_paddle_not_board_sum() -> None:
    """源码锁:read_game_state 部署对齐不再用羁绊和,改用 paddle X。

    防 修复回退(旧 ``min(sum(state.board.values), level)`` 是
    deployed_align 误判族根因)。
    """
    src = inspect.getsource(obs_mod.read_game_state)
    assert '_board_n' not in src, \
        'read_game_state 不得再保留 board 羁绊和对齐目标 _board_n(ADR-0417)'
    # ADR-0462 阶段化后:全量路径仍直读 deployed_count;阶段 gate 路径合并单读
    # (resolve_paddle_pair 产出同一 paddle X)。锁语义=对齐基准是 paddle X 非
    # board 羁绊和,两形态任一在源即守住了语义。
    assert ('_paddle_n = read_deployed_count(ctx, screen)' in src
            or '_paddle_n = _paddle_x if _spec is not None '
               'else read_deployed_count(ctx, screen)' in src), \
        'read_game_state 部署对齐/重建应以 paddle X 为基准(ADR-0417)'
    assert 'resolve_paddle_pair' in src, \
        '阶段 gate 路径应使用 paddle 合并单读(ADR-0462)'
    assert 'tracked_vs_paddle' in src, '对齐留证 source 应指向 paddle 基准'


def test_source_board_arbitration_prefers_badge_with_overlay_guard() -> None:
    """源码锁:board 裁决翻转(备战帧徽标覆入)+ overlay 双不可信守卫。

    board 3/6 采 computed 错 → 备战帧裁决翻转为采徽标;overlay 干扰
    2/6(徽标与 computed 各错一次)→ 非备战帧(is_prep_like_frame=False)不裁
    不覆,保 computed 底座防新错。
    """
    src = inspect.getsource(obs_mod.read_game_state)
    assert '采新-badge' in src, '备战帧裁决应采徽标(画面事实优先,ADR-0417)'
    assert '留证-双不可信' in src, 'overlay/动画帧应留证不裁(双不可信防新错)'
    assert 'is_prep_like_frame(ctx, screen)' in src, \
        '裁决前应过备战帧态判定(overlay 守卫)'
    # 守卫语义:帧态判定仅在真有分歧时做(常态一致零开销),且非备战帧不覆写
    assert '_merged[_f] = _ocr_c' in src, '覆写只应发生在备战帧徽标分支'
