"""W414 行为锁:结算屏金币明细采集钩子(败轮收入残差成分钉死的数据源)。

采集目标:结算屏「获得金币总览」明细行(基础奖励/连胜/利息三分量)同帧解析 +
旁路 jsonl(``replay/gold_detail.jsonl``)+ 整屏 ``cw_shot_unique('cw_settle')`` 兜底。
评估依据 = .debug/temp/currency_war/w409_streak_calib_eval/REPORT.md §4。

单帧锁用 sr-od-test win.webp 实测帧坐标(test_cw_w40_settlement_damage.WIN_FRAME 同源);
落盘契约测试全部指向 tmp_path(不写真实 .debug),cw_shot_unique monkeypatch no-op。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war import cw_settlement_obs
from sr_od.application.currency_war.cw_settlement_obs import (
    collect_gold_detail_hook,
    parse_settlement_gold_detail,
    read_round_outcome,
)


class _Item(SimpleNamespace):
    """OCR 结果桩(data/x/y/width/height;坐标取自 win.webp 实测帧)。"""


def _items(spec: list[tuple[str, int, int, int, int]]) -> list[_Item]:
    return [_Item(data=t, x=x, y=y, width=w, height=h)
            for t, x, y, w, h in spec]


# win.webp 全屏 OCR 实测(与 test_cw_w40_settlement_damage.WIN_FRAME 同源;金币明细区:
# 基础奖励(530,604)→5(1051,605);利息(527,653)→4(1057,660);连胜×0(528,702))
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


# ===== 纯函数:parse_settlement_gold_detail =====

def test_win_fixture_three_components() -> None:
    """实锤帧:基础奖励=5 / 利息=4 / 连胜=0(总分 10 = 5+4+0 交叉自洽)。"""
    assert parse_settlement_gold_detail(WIN_FRAME) == {
        'base': 5, 'streak': 0, 'interest': 4}


def test_attached_token_forms() -> None:
    """同 token 粘连形态(OCR 把标签与值读进一块):'基础奖励5' / '连胜x3'。"""
    items = _items([
        ('获得金币总览', 530, 553, 146, 28), ('基础奖励5', 530, 604, 120, 28),
        ('连胜x3', 528, 702, 113, 35), ('利息', 527, 653, 56, 31),
    ])
    assert parse_settlement_gold_detail(items) == {
        'base': 5, 'streak': 3, 'interest': None}


def test_header_streak_affix_not_detail_row() -> None:
    """头部「火热连胜×1」词缀不是明细行(锚点下方守卫)→ 连胜只取明细行值。"""
    items = _items([
        ('火热连胜×1', 700, 300, 150, 30),
        ('获得金币总览', 530, 553, 146, 28),
        ('连胜×2', 528, 702, 113, 35),
    ])
    assert parse_settlement_gold_detail(items)['streak'] == 2


def test_no_anchor_returns_all_none() -> None:
    """无「总览」标题(非结算屏/OCR 全漏)→ 三分量全 None,不抛。"""
    items = _items([('挑战成功', 831, 192, 256, 73)])
    assert parse_settlement_gold_detail(items) == {
        'base': None, 'streak': None, 'interest': None}


def test_missing_value_component_is_none() -> None:
    """某分量标签在、同行数值缺(OCR 漏)→ 该分量 None,其余照读。"""
    items = _items([
        ('获得金币总览', 530, 553, 146, 28), ('基础奖励', 530, 604, 98, 28),
        ('利息', 527, 653, 56, 31), ('4', 1057, 660, 13, 17),
    ])
    assert parse_settlement_gold_detail(items) == {
        'base': None, 'streak': None, 'interest': 4}


def test_value_out_of_range_guard() -> None:
    """三位数/越界值不是明细分量(格式先验 0-99)→ 拒,置 None。"""
    items = _items([
        ('获得金币总览', 530, 553, 146, 28), ('基础奖励', 530, 604, 98, 28),
        ('120', 1051, 605, 40, 25),
    ])
    assert parse_settlement_gold_detail(items)['base'] is None


# ===== 采集钩子契约(jsonl 落盘 / 去重 / 容错;全走 tmp_path) =====

@pytest.fixture()
def _hook_env(tmp_path, monkeypatch):
    """钩子落盘指向 tmp_path + 截图/运行号外部依赖 no-op(测试不触真实 .debug)。"""
    monkeypatch.setattr(cw_settlement_obs, '_GOLD_DETAIL_JOURNAL',
                        tmp_path / 'gold_detail.jsonl')
    monkeypatch.setattr(cw_settlement_obs, '_gold_last_row_key', None)
    import sr_od.application.currency_war.kernel.cw_observe as obs_mod
    monkeypatch.setattr(obs_mod, 'cw_shot_unique',
                        lambda image, label: f'{label}__dead.png')
    import sr_od.application.currency_war.cw_telemetry as tel
    monkeypatch.setattr(tel, 'current_run_id', lambda: 'run_x')
    return tmp_path


def test_hook_appends_jsonl_row(_hook_env) -> None:
    texts = [it.data for it in WIN_FRAME]
    collect_gold_detail_hook(object(), texts, WIN_FRAME, plane=1, round_num=8,
                             node_type='奖励', streak_after=0)
    rows = [json.loads(l) for l in
            (_hook_env / 'gold_detail.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 1
    r = rows[0]
    assert (r['run_id'], r['plane'], r['round_num'], r['node_type']) == \
        ('run_x', 1, 8, '奖励')
    assert (r['base'], r['streak'], r['interest']) == (5, 0, 4)
    assert r['shot'] == 'cw_settle__dead.png'


def test_hook_dedup_same_frame(_hook_env) -> None:
    """结算停留期同帧重复读(同 plane/round/文本)只落一行。"""
    texts = [it.data for it in WIN_FRAME]
    for _ in range(3):
        collect_gold_detail_hook(None, texts, WIN_FRAME, plane=1, round_num=8,
                                 node_type='奖励', streak_after=0)
    lines = (_hook_env / 'gold_detail.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1


def test_hook_tolerates_run_id_failure(_hook_env, monkeypatch) -> None:
    """run id 源抛异常 → 行照落,run_id='-'(采集零行为影响,不炸主流程)。"""
    import sr_od.application.currency_war.cw_telemetry as tel
    def _boom():
        raise RuntimeError('no session')
    monkeypatch.setattr(tel, 'current_run_id', _boom)
    texts = [it.data for it in WIN_FRAME]
    collect_gold_detail_hook(None, texts, WIN_FRAME, plane=2, round_num=1,
                             node_type='普通战斗', streak_after=-1)
    r = json.loads((_hook_env / 'gold_detail.jsonl')
                   .read_text(encoding='utf-8').splitlines()[0])
    assert r['run_id'] == '-'


def test_hook_swallows_journal_failure(_hook_env, monkeypatch) -> None:
    """落盘路径不可用(父级是普通文件,mkdir 必败)→ 吞异常不抛(钩子 best-effort 纪律)。"""
    blocker = _hook_env / 'blocker.txt'
    blocker.write_text('x', encoding='utf-8')
    monkeypatch.setattr(cw_settlement_obs, '_GOLD_DETAIL_JOURNAL',
                        blocker / 'sub' / 'gold_detail.jsonl')
    texts = [it.data for it in WIN_FRAME]
    collect_gold_detail_hook(None, texts, WIN_FRAME, plane=1, round_num=8,
                             node_type='奖励', streak_after=0)   # 不抛即过


# ===== read_round_outcome 接线(同帧产明细 → jsonl) =====

def _ctx_with_items(items: list[_Item]) -> SimpleNamespace:
    return SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=lambda image, rect=None, crop_first=False: items))


def test_read_round_outcome_triggers_hook(_hook_env) -> None:
    """结算帧 → RoundOutcome 照旧 + 旁路 jsonl 落一行明细(零额外 OCR 调用)。"""
    obs = read_round_outcome(_ctx_with_items(WIN_FRAME), None,
                             plane=1, round_num=8, comp_tag='c')
    assert obs.hp_after == 20
    lines = (_hook_env / 'gold_detail.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])['base'] == 5


def test_read_round_outcome_no_detail_frame_still_row(_hook_env) -> None:
    """无明细区帧(面板被遮形态)→ 明细 None 照落行(缺行会伪装「没轮」,假 0 不许)。"""
    items = _items([('挑战成功', 831, 192, 256, 73),
                    ('小队生命值86i', 646, 479, 226, 43)])
    read_round_outcome(_ctx_with_items(items), None,
                       plane=1, round_num=3, comp_tag='c')
    r = json.loads((_hook_env / 'gold_detail.jsonl')
                   .read_text(encoding='utf-8').splitlines()[0])
    assert (r['base'], r['streak'], r['interest']) == (None, None, None)
