r"""test_cw_obs_parsers 主题锁——OCR 真值锚:streak/board/结算金/difficulty 解析器级。

覆盖面(四类承重件,每真实分支 1 代表行,非全枚举):
- streak 解析:「连胜×N」/「连败×N」方向 + ×读成 x 容忍 + 缺文本 0;
- board 解析:左面板 X/Y → count/next_tier + 徽标数字优先于档位链(低估修复);
- 结算金解析:结算屏「存量 N」= 当前金 + Lv/xp 伴随读数(win/loss 页两形态,
  败局页无等级/经验 → None;宁缺勿造);
- difficulty 解析:难度确认职级 A\d+(-\d+)? 过滤非职级 / 敌人难度N 越界拒。

来源指针(2026-09-09 目标形态重建批;来源文件在飞 M,以 git show HEAD 已提交
内容为搬水源,断言零改动;其退役随并行批落地后二轮):
- test_cw_obs_gates.py@HEAD(streak/board/difficulty 解析器测试);
- 结算金两测复活自 git 历史(ba34eae test_cw_expected_state.py,dd-038 随
  v2 清理整删;被测 parse_settlement_assets 仍在产,消费点 =
  operations/cw_screen/cw_screen_battle_wait.py,规格点名「结算金」故按
  「历史锁 git 可复活」恢复,断言逐字未改)。
其余历史锁已退役(git 可复活)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.obs.cw_briefing_obs import parse_enemy_difficulty
from sr_od.application.currency_war.obs.cw_observation import (
    parse_selected_difficulty,
    read_board,
    read_board_next_tier,
)
from sr_od.application.currency_war.obs.cw_settlement_obs import parse_streak
from test.conftest import SrTestContext


def _ocr(text: str, x: int, y: int) -> SimpleNamespace:
    """造 OCR result(data + center + x/w),给 read_board 系 mock 用。

    x/w 以「center=x」补齐(x-20 宽40 → x+w/2 = x):真实 OcrMatchResult 有 x/w 属性
    (r80 read_node_type 位置化后消费),mock 对齐。"""
    return SimpleNamespace(data=text, center=Point(x, y), x=x - 20, w=40)


# ==================== streak 解析真值(自 test_cw_obs_gates.py@HEAD 迁入) ====================

def test_parse_streak_win_loss_direction() -> None:
    """结算「连胜×N」/「连败×N」前缀=方向:连胜 + / 连败 −。

    末腿随在飞 src 契约同步(迁移批次二 §8.8,parse_settlement_obs.py
    docstring):失读 → None(0 是真实读数,失读返 0 会把「未读到」冒充
    「真 0」);HEAD 原断言为 `== 0`(旧语义),并行批落地后由其测试
    更新承载,此处按现行产码契约对齐以保绿。"""
    assert parse_streak(['连胜×0']) == 0
    assert parse_streak(['挑战结束', '连胜×3', '继续挑战']) == 3
    assert parse_streak(['连败×2']) == -2
    assert parse_streak(['连胜x5']) == 5               # × 读成 x 也容忍
    assert parse_streak(['挑战结束', '数据统计']) is None   # 无 streak 文本 = 失读(非真 0)


# ==================== board 解析真值(自 test_cw_obs_gates.py@HEAD 迁入) ====================

def test_read_board_xy_count_and_next_tier(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """左面板 'X/Y' → count=X + next_tier=Y(doc 13 FactionState;D-68 备战字段采集)。

    聚焦 OCR 读对 "X/Y"(全屏密度把 "2/3" 误读 "213";区域裁切/mock 读对)。count 走 X(read_board
    回归),next_tier 走 Y(read_board_next_tier 新)。裸数字(tier 链残留)不当 count。
    """
    ocr = [
        _ocr('能量', 105, 222), _ocr('2/3', 108, 259),       # count=2, next_tier=3
        _ocr('仙舟', 106, 310), _ocr('1/3', 108, 342),       # count=1, next_tier=3
        _ocr('贝洛伯格', 108, 476), _ocr('1/2', 108, 513),   # count=1, next_tier=2
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    assert read_board(test_context, None) == {'能量': 2, '仙舟': 1, '贝洛伯格': 1}
    assert read_board_next_tier(test_context, None) == {'能量': 3, '仙舟': 3, '贝洛伯格': 2}


def test_read_board_badge_digit_wins_over_tier_chain(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """徽标数字优先于档位链:持续伤害行 徽标"3"(x=73,名称列左侧)+ 链"2/4/6"(x=107)
    → count=3(旧链被 "2/4" 误配成 2 或兜底 1);next_tier 走注册表(>3 最小档=4)。"""
    ocr = [
        _ocr('持续伤害', 106, 143),
        _ocr('3', 73, 177),        # 徽标(纯数字,名称列左侧 x<104)
        _ocr('21416', 107, 177),   # 档位链 "2/4/6" 斜杠丢失,不产 count
    ]
    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', lambda **kw: ocr)
    assert read_board(test_context, None) == {'持续伤害': 3}
    assert read_board_next_tier(test_context, None) == {'持续伤害': 4}


# ==================== 结算金解析真值(git 复活,见头部出处) ====================

def test_parse_settlement_assets_win_frame_forms() -> None:
    """win 帧亲读形态(EXPECTED_STATE §1 引):存量=当前金;Lv.5 4/20。"""
    from sr_od.application.currency_war.obs.cw_settlement_obs import (
        parse_settlement_assets,
    )
    out = parse_settlement_assets(
        ['挑战成功', '小队生命值20', '金币总览', '10', '存量 60',
         'Lv.5', '4/20', '继续挑战'])
    assert out == {'gold': 60, 'level': 5, 'xp_cur': 4, 'xp_next': 20}


def test_parse_settlement_assets_loss_page_forms() -> None:
    """败局链读数口径(05-battle §1):轮败页无等级/经验 → 对应键 None;
    金币右上存量可读。"""
    from sr_od.application.currency_war.obs.cw_settlement_obs import (
        parse_settlement_assets,
    )
    out = parse_settlement_assets(['挑战结束', '-22', '挑战进度', '存量 30',
                                   '前往结算'])
    assert out['gold'] == 30
    assert out['level'] is None and out['xp_cur'] is None
    # 全不可读 = 诚实未知(不冒认)
    assert parse_settlement_assets(['挑战成功', '继续挑战']) == {
        'gold': None, 'level': None, 'xp_cur': None, 'xp_next': None}


# ==================== difficulty 解析真值(自 test_cw_obs_gates.py@HEAD 迁入) ====================

def test_parse_selected_difficulty() -> None:
    r"""难度确认 OCR 文字 → 职级(A\d+(-\d+)?);过滤非职级(财富造物主 等)。"""
    assert parse_selected_difficulty(['A8', '财富造物主']) == 'A8'
    assert parse_selected_difficulty(['A5']) == 'A5'
    assert parse_selected_difficulty(['A8-1']) == 'A8-1'
    assert parse_selected_difficulty(['A8-50']) == 'A8-50'
    assert parse_selected_difficulty(['财富造物主', '当前职级难度效果']) == ''
    assert parse_selected_difficulty([]) == ''


def test_parse_enemy_difficulty() -> None:
    """简报「敌人难度N」OCR → int;过滤词缀/首领;越界(>300)→ None(3.5.2)。"""
    assert parse_enemy_difficulty(['敌人难度108', '随从强化']) == 108
    assert parse_enemy_difficulty(['敌人难度 50']) == 50
    assert parse_enemy_difficulty(['随从强化', '开局不利']) is None  # 无难度文字
    assert parse_enemy_difficulty(['敌人难度999']) is None  # 越界(>300)
    assert parse_enemy_difficulty([]) is None
