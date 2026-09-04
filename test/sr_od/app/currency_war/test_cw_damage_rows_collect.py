# -*- coding: utf-8 -*-
"""ΔV_2★ 结算屏逐角色伤害行采集(parse_settlement_damage_rows)回归锁。

设计出处 = ``.debug/temp/currency_war/delta_v2star_active/DESIGN.md``
§2(schema 口径)/§3(fail-closed 与删留条件)/§6(验收线)。

锁面(本文件):
- 同帧互为对拍:Σ(damage_rows.damage) == damage_dealt(既有求和生产观测
  不动,逐行是平行新纯函数,DESIGN §6 ①);
- None 删失语义:面板不可见 → 全链路 None(纯函数/read_round_outcome/
  telemetry 透传),无 0 冒认(DESIGN §6 ②);
- 「试用」徽标位锁(is_trial 只认同行 ≤25px 的徽标 token);
- roster 匹配不上留 name_raw + name=None(DESIGN §5 风险表口径)。

fixture 复用既有结算屏帧 win.webp / ended.webp 的全屏 OCR 实测 token
(与 test_cw_round_flow 的 WIN_FRAME/ENDED_DAMAGE 同源,坐标逐字一致);
「试用」同行/roster 匹配两锁在实帧 token 上做**合成增广**(真实面板行 =
「角色名 + 试用徽标 + 伤害值」同行,实帧 OCR 常漏读名与徽标——立绘渲染,
2026-09 离线抽检多帧仅伤害值可读——增广 token 按 win.webp 行位摆放在
_STAT_COL_RECT 内,y 中心与伤害 token 差 ≤5px)。临时采集钩子的删留条件
见 DESIGN §3:届时本测试文件整份随实现一并删除。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTER_ROSTER
from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    parse_settlement_damage,
    parse_settlement_damage_rows,
    read_round_outcome,
)
from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder
from sr_od.application.currency_war.telemetry.cw_replay_reader import load_outcomes


class _Item(SimpleNamespace):
    """OCR 结果桩(data/x/y/width/height;坐标取自 fixture 实测 OCR)。"""


def _items(spec: list[tuple[str, int, int, int, int]]) -> list[_Item]:
    return [_Item(data=t, x=x, y=y, width=w, height=h)
            for t, x, y, w, h in spec]


# sr-od-test/screens/货币战争-结算/win.webp 全屏 OCR 实测(同 test_cw_round_flow)
WIN_FRAME = _items([
    ('挑战成功', 831, 192, 256, 73), ('1-8', 887, 270, 44, 28),
    ('奖励', 981, 269, 55, 30), ('Lv.5', 1110, 367, 85, 66),
    ('4/20', 1127, 427, 55, 25), ('小队命值20i', 646, 479, 226, 43),
    ('获得金币总览', 530, 553, 146, 28), ('10', 1042, 555, 31, 26),
    ('数据统计', 1120, 554, 98, 29), ('基础奖励', 530, 604, 98, 28),
    ('5', 1051, 605, 22, 25), ('试用', 1144, 601, 47, 25),
    ('396.3万', 1198, 635, 81, 25), ('利息', 527, 653, 56, 31),
    ('4', 1057, 660, 13, 17), ('试用', 1144, 678, 48, 26),
    ('连胜×0', 528, 702, 113, 35), ('6.4万', 1196, 712, 58, 26),
    ('掉落晶矿', 528, 771, 100, 32), ('5', 1058, 780, 8, 14),
    ('继续挑战', 910, 878, 100, 31),
])

# ended.webp(挑战结束态)同布局;伤害列 137.0万 + 1.1万
ENDED_DAMAGE = _items([
    ('挑战结束', 831, 191, 257, 73), ('数据统计', 1120, 554, 98, 29),
    ('试用', 1144, 601, 48, 25), ('137.0万', 1198, 635, 80, 25),
    ('试用', 1144, 678, 48, 26), ('1.1万', 1196, 712, 56, 26),
])

# win.webp 行位合成增广:角色名 + 同行试用徽标(实帧 OCR 漏读位补真布局;
# y 中心与 396.3万 token 差 5px ≤25px,落 _STAT_COL_RECT 内)
WIN_AUGMENTED = _items([
    ('挑战成功', 831, 192, 256, 73), ('数据统计', 1120, 554, 98, 29),
    ('希儿·实测名', 1132, 636, 60, 24), ('试用', 1144, 635, 48, 25),
    ('396.3万', 1198, 635, 81, 25), ('6.4万', 1196, 712, 58, 26),
])


def _ctx_with_items(items: list) -> SimpleNamespace:
    return SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=lambda image, rect=None, crop_first=False: items))


# ===== ① 同帧求和与逐行和恒等(fixture 实测) =====

def test_win_fixture_rows_sum_equals_damage_dealt() -> None:
    """win.webp:两行 damage 和 == parse_settlement_damage 同帧求和(对拍恒等)。"""
    rows = parse_settlement_damage_rows(WIN_FRAME)
    assert rows is not None and len(rows) == 2
    assert [r['damage'] for r in rows] == [3_963_000, 64_000]   # 行 y 自上而下
    assert sum(r['damage'] for r in rows) == parse_settlement_damage(WIN_FRAME) == 4_027_000


def test_ended_fixture_rows_sum_equals_damage_dealt() -> None:
    """ended.webp(挑战结束态):逐行和 == 求和 == 1381000。"""
    rows = parse_settlement_damage_rows(ENDED_DAMAGE)
    assert rows is not None and len(rows) == 2
    assert sum(r['damage'] for r in rows) == parse_settlement_damage(ENDED_DAMAGE) == 1_381_000


def test_read_round_outcome_same_frame_identity() -> None:
    """read_round_outcome 同帧:Σ(damage_rows) == damage_dealt(同帧互为对拍锁)。"""
    obs = read_round_outcome(_ctx_with_items(WIN_FRAME), None,
                             plane=1, round_num=8, comp_tag='c')
    assert obs.damage_dealt == 4_027_000
    assert obs.damage_rows is not None
    assert sum(r['damage'] for r in obs.damage_rows) == obs.damage_dealt


# ===== ② None 删失语义(全链路,无 0 冒认) =====

def test_no_panel_returns_none_and_zero_never_fabricated() -> None:
    """面板不可见(无万形 token)→ 纯函数 None;绝不产 damage=0 的行。"""
    items = _items([('挑战成功', 831, 192, 256, 73), ('10', 1042, 555, 31, 26)])
    rows = parse_settlement_damage_rows(items)
    assert rows is None
    assert not any(isinstance(r, dict) and r.get('damage') == 0
                   for r in (rows or []))


def test_no_panel_full_chain_none() -> None:
    """读不到帧全链路 None:纯函数 → RoundOutcome.damage_rows → 透传行。"""
    items = _items([('挑战成功', 831, 192, 256, 73),
                    ('小队生命值86i', 646, 479, 226, 43)])
    obs = read_round_outcome(_ctx_with_items(items), None,
                             plane=1, round_num=3, comp_tag='c')
    assert obs.damage_rows is None
    assert obs.damage_dealt is None   # 既有求和同款删失语义,零波及


def test_out_of_column_token_returns_none() -> None:
    """万形 token 落左列(位置守卫)→ 不产行,整体 None。"""
    items = _items([('6.5万', 600, 650, 50, 25), ('基础奖励', 530, 604, 98, 28)])
    assert parse_settlement_damage_rows(items) is None


def test_telemetry_none_roundtrip() -> None:
    """删失语义透传:默认行 damage_rows=None 落盘仍 None;无 0 冒认。"""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        rec = TelemetryRecorder(replay_dir=td, enabled=True)
        rec.record_outcome('r1', RoundOutcome(
            round_num=8, plane=1, node_type='战斗', comp_tag='c', hp_after=20))
        lines = _read_outcome_lines(td)
        assert len(lines) == 1
        assert lines[0]['damage_rows'] is None


def _read_outcome_lines(replay_dir: str) -> list[dict]:
    import json
    from pathlib import Path
    p = Path(replay_dir) / 'outcomes.jsonl'
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


# ===== 「试用」徽标位锁 =====

def test_trial_badge_same_row_only() -> None:
    """is_trial 只认同行(y 中心差 ≤25px)的「试用」token。

    - 增广帧第 1 行(试用与伤害同行)→ True;
    - 第 2 行无同行试用 → False;
    - win 原帧试用 token 与伤害行差 34px(异行/漏锚)→ False(诚实删失,
      不跨行冒认徽标)。
    """
    rows = parse_settlement_damage_rows(WIN_AUGMENTED)
    assert rows is not None
    assert rows[0]['is_trial'] is True
    assert rows[1]['is_trial'] is False
    base = parse_settlement_damage_rows(WIN_FRAME)
    assert base is not None
    assert all(r['is_trial'] is False for r in base), (
        'win 原帧试用 token 中心距伤害行 34px >25px,按行对齐口径不认作同行')


# ===== roster 匹配锁 =====

def test_name_match_and_miss_lock() -> None:
    """name=roster 相似匹配:命中归一;匹配不上留 name_raw + name=None。"""
    roster_name = sorted(CHARACTER_ROSTER)[0]
    items = _items([
        ('挑战成功', 831, 192, 256, 73), ('数据统计', 1120, 554, 98, 29),
        (roster_name, 1132, 636, 60, 24), ('396.3万', 1198, 635, 81, 25),
        ('甲乙丙丁测', 1132, 712, 80, 25), ('6.4万', 1196, 712, 58, 26),
    ])
    assert '甲乙丙丁测' not in CHARACTER_ROSTER   # 桩自检:确在 roster 外
    rows = parse_settlement_damage_rows(items)
    assert rows is not None and len(rows) == 2
    assert rows[0]['name'] == roster_name
    assert rows[0]['name_raw'] == roster_name
    assert rows[1]['name_raw'] == '甲乙丙丁测'   # 原文保留(离线端可二次匹配)
    assert rows[1]['name'] is None


def test_fixture_rows_name_censored_honestly() -> None:
    """实帧(win.webp)OCR 漏读角色名 → name_raw='' name=None(诚实删失,禁造名)。"""
    rows = parse_settlement_damage_rows(WIN_FRAME)
    assert rows is not None
    assert all(r['name_raw'] == '' and r['name'] is None for r in rows)


# ===== telemetry 透传(roundtrip + 旧记录读端容忍) =====

def test_damage_rows_roundtrip_and_old_record_tolerance() -> None:
    """带行的 outcome 落盘往返含逐行字段;旧记录(缺键)读端容忍不炸。"""
    import json
    import tempfile
    from pathlib import Path

    rows = [{'name_raw': '希儿', 'name': '希儿', 'is_trial': False,
             'damage': 3_963_000}]
    with tempfile.TemporaryDirectory() as td:
        rec = TelemetryRecorder(replay_dir=td, enabled=True)
        rec.record_outcome('r1', RoundOutcome(
            round_num=8, plane=1, node_type='战斗', comp_tag='c', hp_after=20,
            damage_dealt=3_963_000, damage_rows=rows))
        rec.record_outcome('r1', RoundOutcome(
            round_num=9, plane=1, node_type='boss', comp_tag='c', hp_after=1))
        lines = [json.loads(l) for l
                 in (Path(td) / 'outcomes.jsonl').read_text(encoding='utf-8').splitlines()
                 if l.strip()]
        assert lines[0]['damage_rows'] == rows
        assert lines[1]['damage_rows'] is None
        # 旧记录容忍:抹掉 damage_rows 键后规范读端(from_dict)照常构造
        (Path(td) / 'outcomes.jsonl').write_text(
            '\n'.join(json.dumps({k: v for k, v in l.items() if k != 'damage_rows'})
                      for l in lines) + '\n', encoding='utf-8')
        loaded = load_outcomes(Path(td) / 'outcomes.jsonl')
        assert len(loaded) == 2
        assert loaded[0].damage_rows is None
        assert loaded[1].damage_rows is None
