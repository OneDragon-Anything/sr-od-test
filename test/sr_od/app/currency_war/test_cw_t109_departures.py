"""T-109① 锁:离场事件派生列 departures(v10,ADR-0605)——执行期 deploy
换血卖出的逐件落账缺口(复盘 g_20260907_075840 p1r1 Saber 实锤:场上件无
卖出动作而消失,逐件身份只在 log 行与匿名计数键 sell_offtarget_*)。

素材 = 075840 帧形态(多重集差 + 通道分键 + 段界隔离 + 不可知帧跳过);
决策时点卖出(SellBench/SellDeployed)本就逐件在案,不在本列重复的语义
由 sell_recorded 通道用例钉住。
"""
from __future__ import annotations

import json
from pathlib import Path as _P

from sr_od.application.currency_war.telemetry import match_archive as arch

# ===== 源流构造(手法沿用 test_cw_t100_v9_assembly 既有先例) =====


def _write_jsonl(d: _P, name: str, rows: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    with (d / name).open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _dep(char_id: str, star: int, pref: str, slot: int) -> dict:
    """deployed 条目(键面 = 075840 decisions 切片实读形态)。"""
    return {'slot': slot, 'char_id': char_id, 'faction': '', 'star': star,
            'position_pref': pref, 'equips': [], 'is_item_slot': False}


def _dec(run_id, plane, rnd, ts, deployed, actions=None):
    return {'run_id': run_id, 'plane': plane, 'round_num': rnd, 'ts': ts,
            'gold': 10, 'gold_readable': True, 'hp': 100,
            'hp_readable': False, 'actions': actions or [],
            'state': {'deployed': deployed}}


def _seg_files(rd: _P, rid: str, dec_rows: list[dict]) -> None:
    """单段最小流(runs result=win,零结算行——departures 不依赖 outcomes)。"""
    _write_jsonl(rd, 'outcomes.jsonl', [])
    _write_jsonl(rd, 'decisions.jsonl', dec_rows)
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': rid, 'ts': '2026-09-07T08:42:10', 'result': 'win',
         'final_hp': 50}])
    _write_jsonl(rd, 'exogenous.jsonl', [])
    _write_jsonl(rd, 'shop_snapshots.jsonl', [])
    _write_jsonl(rd, 'invest_cards.jsonl', [])
    _write_jsonl(rd, 'spend_ledger.jsonl', [])


def _build(rd: _P) -> dict:
    return arch.build_archive(rd, arch.assign_games(rd)[0])


# ===== ① 主实锤形态:075840 p1r1 Saber 换血卖出(unexplained) =====

def test_swap_sell_departure_unexplained_075840_saber(tmp_path: _P):
    """075840 素材帧锁:08:00:18 [椒丘,藿藿,Saber] --RunDeploy--> 08:00:42
    [椒丘,艾丝妲,藿藿]。Saber 无 SellDeployed/SellBench 动作而离场 =
    执行期换血卖出信号通道(unexplained);同窗到场 1:1(艾丝妲)入行
    same_window_arrivals 供归因并读;离场行锚前一帧的 plane/round/ts。"""
    rd = tmp_path / 'replay'
    rid = 'run_20260907_075840'
    dep_a = [_dep('椒丘', 1, 'front', 1), _dep('藿藿', 1, 'back', 1),
             _dep('Saber', 1, 'back', 2)]
    dep_b = [_dep('椒丘', 1, 'front', 1), _dep('艾丝妲', 1, 'front', 2),
             _dep('藿藿', 1, 'back', 1)]
    _seg_files(rd, rid, [
        _dec(rid, 1, 1, '2026-09-07T08:00:18', dep_a,
             actions=[{'__type__': 'RunDeploy'}]),
        _dec(rid, 1, 1, '2026-09-07T08:00:42', dep_b,
             actions=[{'__type__': 'StartBattle'}])])
    a = _build(rd)
    assert a['schema_version'] == 10
    assert a['departures'] == [{
        'run_id': rid, 'plane': 1, 'round': 1,
        'ts': '2026-09-07T08:00:18',
        'char': 'Saber', 'star': 1, 'count': 1,
        'channel': 'unexplained',
        'same_window_arrivals': ['艾丝妲']}]


# ===== ② 通道分键:sell_recorded(SellDeployed 槽位解析命中) =====

def test_departure_sell_recorded_channel(tmp_path: _P):
    """决策时点 SellDeployed(row=front, slot=1)卖掉椒丘 → 离场行通道
    = sell_recorded(该件本就在 actions 逐件在案,通道分键防双计混淆);
    同帧同名不同星不受更高星误判(合并通道只在无卖出背书时参与)。"""
    rd = tmp_path / 'replay'
    rid = 'run_20260908_120000'
    dep_a = [_dep('椒丘', 1, 'front', 1), _dep('藿藿', 1, 'back', 1)]
    dep_b = [_dep('藿藿', 1, 'back', 1)]
    _seg_files(rd, rid, [
        _dec(rid, 1, 3, '2026-09-08T12:00:00', dep_a,
             actions=[{'__type__': 'SellDeployed', 'row': 'front', 'slot': 1}]),
        _dec(rid, 1, 3, '2026-09-08T12:00:20', dep_b,
             actions=[{'__type__': 'StartBattle'}])])
    a = _build(rd)
    assert [(d['char'], d['channel']) for d in a['departures']] == \
        [('椒丘', 'sell_recorded')]


# ===== ③ 通道分键:merge_promoted(同名更高星在场) =====

def test_departure_merge_promoted_channel(tmp_path: _P):
    """买牌 3 合 1:1★×3 → 2★×1 = 同名更高星在场,三张 1★ 副本离场
    合并为单行 count=3、通道 merge_promoted(合成链已有 merge_chain
    期望态登记,本列只做差分显影不重复细节)。"""
    rd = tmp_path / 'replay'
    rid = 'run_20260908_130000'
    dep_a = [_dep('椒丘', 1, 'front', 1), _dep('椒丘', 1, 'front', 2),
             _dep('椒丘', 1, 'front', 3)]
    dep_b = [_dep('椒丘', 2, 'front', 1)]
    _seg_files(rd, rid, [
        _dec(rid, 1, 4, '2026-09-08T13:00:00', dep_a),
        _dec(rid, 1, 4, '2026-09-08T13:00:20', dep_b,
             actions=[{'__type__': 'StartBattle'}])])
    a = _build(rd)
    assert a['departures'] == [{
        'run_id': rid, 'plane': 1, 'round': 4,
        'ts': '2026-09-08T13:00:00',
        'char': '椒丘', 'star': 1, 'count': 3,
        'channel': 'merge_promoted',
        'same_window_arrivals': ['椒丘']}]


# ===== ④ 边界:身份不可知帧对跳过 / 零变化空列 / 段界隔离 =====

def test_departure_skips_unknown_frames(tmp_path: _P):
    """deployed 缺/非列表 = 身份不可知(旧数据形态)→ 该帧对不产行,
    宁缺勿造(与 hp 链「不可信不入链」同纪律)。"""
    rd = tmp_path / 'replay'
    rid = 'run_20260908_140000'
    _seg_files(rd, rid, [
        _dec(rid, 1, 1, '2026-09-08T14:00:00', []),
        # state 无 deployed 键 → 不可知
        {'run_id': rid, 'plane': 1, 'round_num': 1,
         'ts': '2026-09-08T14:00:20', 'actions': [], 'state': {}},
        _dec(rid, 1, 2, '2026-09-08T14:01:00',
             [_dep('椒丘', 1, 'front', 1)])])
    a = _build(rd)
    assert a['departures'] == []


def test_departure_empty_when_board_stable(tmp_path: _P):
    """板面恒定(帧间多重集相等)→ departures 恒空列表(键在,零行)。"""
    rd = tmp_path / 'replay'
    rid = 'run_20260908_150000'
    dep = [_dep('椒丘', 1, 'front', 1), _dep('藿藿', 2, 'back', 1)]
    _seg_files(rd, rid, [
        _dec(rid, 1, 1, '2026-09-08T15:00:00', dep),
        _dec(rid, 1, 2, '2026-09-08T15:01:00', dep)])
    assert _build(rd)['departures'] == []


def test_departure_isolated_per_segment(tmp_path: _P):
    """段界隔离:段间(停机/续段)场上 legitimately 重建,跨段帧对不入差分
    ——段1 末帧与段2 首帧的身份差不出行(跨段变化归 resume 对账语义)。"""
    rd = tmp_path / 'replay'
    r1, r2 = 'run_20260908_160000', 'run_20260908_170000'
    _write_jsonl(rd, 'outcomes.jsonl', [])
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': r1, 'ts': '2026-09-08T16:10:00', 'result': 'loss',
         'final_hp': 1},
        {'run_id': r2, 'ts': '2026-09-08T17:10:00', 'result': 'win',
         'final_hp': 99}])
    _write_jsonl(rd, 'decisions.jsonl', [
        _dec(r1, 1, 1, '2026-09-08T16:00:00', [_dep('椒丘', 1, 'front', 1)]),
        _dec(r2, 2, 1, '2026-09-08T17:00:00', [])])
    for name in ('exogenous.jsonl', 'shop_snapshots.jsonl',
                 'invest_cards.jsonl', 'spend_ledger.jsonl'):
        _write_jsonl(rd, name, [])
    a = _build(rd)
    assert a['departures'] == []
