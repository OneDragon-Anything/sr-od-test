"""HP 档案装配与血购写点主题文件(ADR-0577 两道独立的门,禁合断言)。

收缩注记(CUT9 二次收缩:原 22 测试→10 测试;同分支变体/双实证重复案砍,
git 可复活):
- 装配核留:事件步进链主锚(含 hp_pay_defects 对账出行)/ 段界重锚 B 件
  主用例 / 单段局 v8 逐字节退化 / 合成行守卫(025608 案,兼锚终局腿
  endgame_final 产出)/ 缺 ts 行 fail-closed;
- 写端 conf 诚实性留陈旧降权 1 代表(新鲜/无结算/不可读三变体砍);
- 写点留两通道各 1(店通道一击一行 + prep 通道 4 击 4 行 F2 粒度),
  非血本位零行变体砍;
- 隔离门 + grep 守卫门(两道独立的门,midsize3 驳回在案)全留;
- 砍:对账吻合零 defect(无事件域由 v8 退化行承载)/ 重锚 no-op 与
  不可读不锚 / 182456 第二实证 / T2 纯补给轮 / 同秒 tiebreak / 终局腿
  独立行与 win/stopped 零腿。

合并出处(2026-09-09 CUT2 合并批③,自 test_cw_hp_pay 整体并入;断言面
原样迁入,装配门与写点/隔离/grep 守卫门保持语义分节——写点隔离测与
grep 守卫是两道独立的门,midsize3 驳回在案,合并不改变门的独立性):

- 装配门(⑧ 节前,T-100 批2):v9 装配统一件——hp 变化事件步进链 +
  段界重锚 + 合成行一律退出步进链 + 终局腿 + ts 三边界 + 真值对账 +
  写端 conf 诚实性。验收单甲(025608 旧档 v9 重装配诚实预期)与
  182456 对照的机制等价形态在各用例 docstring 标注;双档案实装读数见
  ADR-0577 §验证。
- 写点门(⑧ 节,T-100 批1):hp_pay 血购执行回执写点——写点 =
  prep_actions.record_hp_pay_event(两通道共用唯一实现):店通道
  LevelUpOp.execute(单击=一行)与 prep 通道 _level_up(连点循环内
  每击一行),粒度 = 击数(F2 裁决,判读口径:行数=击数,总量=
  Σhp_delta);mode 与判定同源注册表派生(F8):active_strategies 中
  xp_buy_hp_cost>0 的卡;非 active(金本位升级)→ 零行。
- 隔离门(⑨ 节,F6-2/§1.3):hp_pay 行纯观测追加写,禁入决策输入
  ——写点零状态突变锁。
- grep 守卫门(⑩ 节,F7):键在 strategies/impl 决策面零命中,手法 =
  ADR-0571 test_disclosure_fields_not_consumed_by_decision_modules。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_state import GameState, LevelUp
from sr_od.application.currency_war.prep_actions import (
    PrepActionExecutor,
    record_hp_pay_event,
)
from sr_od.application.currency_war.telemetry import match_archive as arch
from sr_od.application.currency_war.telemetry import recorder as cw_recorder

# ===== 源流构造(手法沿用 test_cw_telemetry_archive 既有先例) =====

def _write_jsonl(d: Path, name: str, rows: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    with (d / name).open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _dec(run_id, plane, rnd, ts, **kw):
    base = {'run_id': run_id, 'plane': plane, 'round_num': rnd, 'ts': ts,
            'gold': 10, 'gold_readable': True, 'hp': 100,
            'hp_readable': False, 'actions': [], 'state': {}}
    base.update(kw)
    return base


def _out(run_id, plane, rnd, ts, hp_after, conf=1.0,
         node_type='普通战斗', source=''):
    return {'run_id': run_id, 'plane': plane, 'round_num': rnd, 'ts': ts,
            'node_type': node_type, 'hp_after': hp_after,
            'hp_confidence': conf, 'killed': False, 'source': source}


def _ev(run_id, plane, rnd, ts, hp_delta=-6, mode='奋斗协议', **kw):
    """hp_pay 事件行(写点契约:plane/round 显式入 choice)。"""
    base = {'run_id': run_id, 'kind': 'hp_pay', 'ts': ts,
            'round_num': rnd,
            'choice': {'plane': plane, 'round_num': rnd, 'currency': 'hp',
                       'hp_delta': hp_delta, 'mode': mode, 'clicks': 1,
                       'basis': 'modeled'}}
    base.update(kw)
    return base


def _build(rd: Path) -> dict:
    return arch.build_archive(rd, arch.assign_games(rd)[0])


def _ln_at(a: dict, plane: int, rnd: int) -> list[dict]:
    return [n for n in a['loss_nodes']
            if n['plane'] == plane and n['round'] == rnd]


# ===== ① 事件步进链(单乙同构:66 →事件−24→ 42 →结算 44) =====

def test_events_advance_cursor_no_phantom_entry(tmp_path: Path):
    """单乙形态锁(§1.4 测试2/测试5):66 → hp_pay×4(−24)→ 结算 44
    → 幻影败场条目消失(游标 42,结算腿 +2 无条目);hp_events 显影 4 行;
    真值对账:modeled 期望 42 vs 结算 44 偏差 +2 → hp_pay_defects 落一行
    (modeled 错账当场显影,游标照取结算值自愈)。"""
    rd = tmp_path / 'replay'
    rid = 'run_20260908_100000'
    _write_jsonl(rd, 'outcomes.jsonl', [
        _out(rid, 1, 1, '2026-09-08T10:01:00', 66),
        _out(rid, 1, 2, '2026-09-08T10:05:00', 44)])
    _write_jsonl(rd, 'decisions.jsonl', [])
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': rid, 'ts': '2026-09-08T10:10:00', 'result': 'win',
         'final_hp': 44}])
    _write_jsonl(rd, 'exogenous.jsonl', [
        _ev(rid, 1, 2, f'2026-09-08T10:0{i}:00') for i in (2, 3, 4, 5)])
    _write_jsonl(rd, 'shop_snapshots.jsonl', [])
    _write_jsonl(rd, 'invest_cards.jsonl', [])
    a = _build(rd)
    # 幻影消失:修前(v8)结算腿 = 44−66 = −22 出条目;v9 事件步吸收血购
    assert a['loss_nodes'] == []
    # hp_events 加法列:4 行逐击显影(行数=击数,总量=Σhp_delta=−24)
    assert len(a['hp_events']) == 4
    assert all(e['hp_delta'] == -6 and e['mode'] == '奋斗协议'
               and e['basis'] == 'modeled' and e['plane'] == 1
               for e in a['hp_events'])
    # 真值对账:期望 66−24=42,实际 44,gap=+2(建模 −24 与真值差的显影)
    assert a['hp_pay_defects'] == [
        {'plane': 1, 'round': 2, 'expected_hp': 42, 'actual_hp': 44,
         'gap': 2, 'modeled_paid': -24, 'ts': '2026-09-08T10:05:00'}]
    # rounds 槽不受事件影响(事件不进轮槽聚合)
    by_key = {(r['plane'], r['round']): r for r in a['rounds']}
    assert by_key[(1, 2)]['hp'] == 44


# ===== ② 段界重锚(025608 形态①:游标 61 → 重锚 37 → 战斗腿 −19) =====

def test_segment_boundary_reanchor_minus19(tmp_path: Path):
    """B 件主用例(§2.4 测试1):段1 尾无事件 hp 61、段2 恢复帧 37 + 结算
    18 → 修前(v8)跨段膨胀 −43;v9 重锚 → 战斗腿 −19 + 边界差 −24 显影
    (unexplained_delta/consumed_by_chain 进 resume_reconciliation,不进
    loss_nodes);rounds 续段首槽 hp_delta 从跨段净额变段内变化(−19)。"""
    rd = tmp_path / 'replay'
    r1, r2 = 'run_20260907_030000', 'run_20260907_050000'
    _write_jsonl(rd, 'outcomes.jsonl', [
        _out(r1, 1, 9, '2026-09-07T03:17:42', 61),
        _out(r2, 2, 1, '2026-09-07T05:59:32', 18)])
    _write_jsonl(rd, 'decisions.jsonl', [
        _dec(r2, 2, 1, '2026-09-07T05:58:00', hp=37, hp_readable=True)])
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': r1, 'ts': '2026-09-07T03:20:00', 'result': 'stopped',
         'final_hp': 61},
        {'run_id': r2, 'ts': '2026-09-07T06:10:00', 'result': 'stopped',
         'final_hp': 18}])
    _write_jsonl(rd, 'exogenous.jsonl', [])
    _write_jsonl(rd, 'shop_snapshots.jsonl', [])
    _write_jsonl(rd, 'invest_cards.jsonl', [])
    a = _build(rd)
    assert _ln_at(a, 2, 1) == [{
        'plane': 2, 'round': 1, 'node_type': '普通战斗', 'hp': 18,
        'delta': -19, 'hp_source': 'settlement', 'outcome_source': '',
        'ts': '2026-09-07T05:59:32'}]
    rec = a['resume_reconciliation']
    assert len(rec) == 1
    assert rec[0]['unexplained_delta'] == -24       # 37 − 61
    assert rec[0]['consumed_by_chain'] is True
    by_key = {(r['plane'], r['round']): r for r in a['rounds']}
    assert by_key[(2, 1)]['hp_delta'] == -19        # 段内化(读端口径变化)


# ===== ③ 单段局逐字节退化(§2.4 测试2) =====

def test_single_segment_degradation_v8_parity(tmp_path: Path):
    """单段局(无事件/无合成行/无重锚形态/win 局)与 v8 输出逐字节一致:
    loss_nodes 条目集与序、rounds、resume_reconciliation 空表;加法列空、
    无终局腿。结算腿序 = key 序(ts 同序),帧回落轮条目形状同 v8 契约
    (outcome_source/ts 为 None)。"""
    rd = tmp_path / 'replay'
    rid = 'run_20260908_120000'
    _write_jsonl(rd, 'outcomes.jsonl', [
        _out(rid, 1, 1, '2026-09-08T12:01:00', 60),
        _out(rid, 1, 2, '2026-09-08T12:03:00', 52)])
    _write_jsonl(rd, 'decisions.jsonl', [
        _dec(rid, 1, 3, '2026-09-08T12:04:00', hp=48, hp_readable=True)])
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': rid, 'ts': '2026-09-08T12:10:00', 'result': 'win',
         'final_hp': 48}])
    _write_jsonl(rd, 'exogenous.jsonl', [])
    _write_jsonl(rd, 'shop_snapshots.jsonl', [])
    _write_jsonl(rd, 'invest_cards.jsonl', [])
    a = _build(rd)
    assert a['loss_nodes'] == [
        {'plane': 1, 'round': 2, 'node_type': '普通战斗', 'hp': 52,
         'delta': -8, 'hp_source': 'settlement', 'outcome_source': '',
         'ts': '2026-09-08T12:03:00'},
        {'plane': 1, 'round': 3, 'node_type': None, 'hp': 48,
         'delta': -4, 'hp_source': 'frame', 'outcome_source': None,
         'ts': None}]
    assert a['resume_reconciliation'] == []
    assert a['hp_events'] == [] and a['hp_pay_defects'] == []
    assert all(n['hp_source'] != 'endgame_final' for n in a['loss_nodes'])


# ===== ④ 合成行一律退出步进链(§3.4 测试4,双实证案各一锁) =====

def test_synthetic_conf1_stale_row_excluded_025608_case(tmp_path: Path):
    """025608 p2r4 案(§3.4 测试1 合并;C1 回落守卫落地后重推):陈旧合成行
    18@conf=1.0 不入链,同轮 ts 末行 loss_page 0@conf=0.0 作回落源行同守卫
    (conf 门)→ 该轮零回落条目,游标保真 1;死亡由 runs.final_hp=0 结构
    真值出终局腿(delta=−1,osrc=runs.final_hp,ts=None)——死亡不被吞,
    来源从不可信回落值换结构保证。rounds 槽显示行为不变(槽 hp 仍取 ts
    末结算行 0,降权只及链)。"""
    rd = tmp_path / 'replay'
    rid = 'run_20260907_025608'
    _write_jsonl(rd, 'outcomes.jsonl', [
        _out(rid, 2, 2, '2026-09-07T06:03:38', 1),
        _out(rid, 2, 4, '2026-09-07T06:04:12', 18,
             node_type='补给', source='synthetic_supply'),
        _out(rid, 2, 4, '2026-09-07T06:09:19', 0, conf=0.0,
             node_type='遭遇', source='loss_page')])
    _write_jsonl(rd, 'decisions.jsonl', [])
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': rid, 'ts': '2026-09-07T06:10:00', 'result': 'loss',
         'final_hp': 0}])
    _write_jsonl(rd, 'exogenous.jsonl', [])
    _write_jsonl(rd, 'shop_snapshots.jsonl', [])
    _write_jsonl(rd, 'invest_cards.jsonl', [])
    a = _build(rd)
    ln4 = _ln_at(a, 2, 4)
    assert len(ln4) == 1                    # 恰终局腿一条(回落被守卫挡下)
    assert ln4[0] == {
        'plane': 2, 'round': 4, 'node_type': '遭遇', 'hp': 0, 'delta': -1,
        'hp_source': 'endgame_final', 'outcome_source': 'runs.final_hp',
        'ts': None}
    by_key = {(r['plane'], r['round']): r for r in a['rounds']}
    assert by_key[(2, 4)]['hp'] == 0        # rounds 槽显示行为不变


# ===== ⑤ ts 三边界(F5) =====

def test_missing_ts_rows_excluded_from_chain(tmp_path: Path):
    """F5② 缺 ts 行守卫:缺 ts 结算行/事件行不进步进链(空串排序键会错位
    到全局最前);缺 ts 结算行的步进资格让位回落(条目仍按轮槽语义产出,
    ts=None 同 v8 契约);缺 ts 事件不推进游标(结算腿证明:−10 而非 −4)。"""
    rd = tmp_path / 'replay'
    rid = 'run_20260908_140000'
    _write_jsonl(rd, 'outcomes.jsonl', [
        _out(rid, 1, 1, '2026-09-08T14:01:00', 60),
        _out(rid, 1, 2, '', 10),                 # 缺 ts 结算行
        _out(rid, 1, 3, '2026-09-08T14:05:00', 50)])
    _write_jsonl(rd, 'decisions.jsonl', [])
    _write_jsonl(rd, 'runs.jsonl', [
        {'run_id': rid, 'ts': '2026-09-08T14:10:00', 'result': 'win',
         'final_hp': 50}])
    _write_jsonl(rd, 'exogenous.jsonl', [
        _ev(rid, 1, 3, '', hp_delta=-6)])        # 缺 ts 事件
    _write_jsonl(rd, 'shop_snapshots.jsonl', [])
    _write_jsonl(rd, 'invest_cards.jsonl', [])
    a = _build(rd)
    # 缺 ts 回落源行同守卫不进链 → (1,2) 零条目(游标跨轮携带 60)
    assert _ln_at(a, 1, 2) == []
    # 缺 ts 事件未推进游标:结算腿 = 50−60 = −10(若被推进则为 −4)
    assert _ln_at(a, 1, 3)[0]['delta'] == -10


# ===== ⑦ 写端 conf 诚实性(§3.4 测试6,cw_loop 合成行) =====

class TestSupplyConfHonesty:
    """快照新鲜性降权(锚 last_hp_t 比较,ADR-0577 禁 readable 位作新鲜
    证据):快照 hp 观察节点(last_hp_real_node)≤ 最后可信结算节点
    (last_hp_t)⇒ conf=0.0;任一锚 None(无结算/无真读)⇒ conf 维持。"""

    def _run(self, monkeypatch, last_state, **sess_kw) -> list[dict]:
        from sr_od.application.currency_war.operations import cw_loop as bl
        from sr_od.application.currency_war.telemetry import state as tel_state
        captured: list[dict] = []

        def _fake(outcome, source='', supply_pick=None):
            captured.append({'outcome': outcome, 'source': source})

        monkeypatch.setattr(cw_recorder, 'record_outcome', _fake)
        monkeypatch.setattr(tel_state, 'consume_last_supply_pick',
                            lambda: None)
        monkeypatch.setattr(bl, 'read_phase_round', lambda ctx, s: (2, 4))
        sess = SimpleNamespace(last_state=last_state, **sess_kw)
        op = object.__new__(bl.CwLoop)
        op.ctx = SimpleNamespace(cw_match=SimpleNamespace(session=sess))
        op._record_supply_outcome(screen=None)
        return captured

    def test_stale_snapshot_conf_zero(self, monkeypatch):
        """结算后快照(观察节点 11 ≤ 结算节点 12)→ conf=0.0,不冒真值。"""
        cap = self._run(monkeypatch, GameState(hp=18, hp_readable=True),
                        last_hp_real_node=11, last_hp_t=12)
        assert cap[0]['outcome'].hp_confidence == 0.0
        assert cap[0]['source'] == 'synthetic_supply'


# ===== ⑧ 血购写点回执(合并批③自 test_cw_hp_pay 迁入;F2 粒度/F8 mode
# ===== 注册表派生;两通道共用唯一写点实现)=====

def _hp_session(active: list[str] | None = None) -> SimpleNamespace:
    """血购回执写点依赖面桩:active_strategies + last_state(其余无关)。"""
    return SimpleNamespace(
        active_strategies=list(active or []),
        last_state=GameState(plane=2, round_num=1, hp=61, gold=70),
    )


@pytest.fixture()
def captured_exo(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """捕获 record_exogenous 调用(写点经模块属性消费,patch 即全捕)。"""
    rows: list[dict] = []

    def _cap(round_num, kind, detail='', state=None, choice=None):
        rows.append({'round_num': round_num, 'kind': kind,
                     'detail': detail, 'choice': choice})

    monkeypatch.setattr(cw_recorder, 'record_exogenous', _cap)
    return rows


# ===== 单元:店通道(prep_actions LevelUpOp 走 cw_shop_action_ops) =====

def _shop_env(session, ledger=None):
    """ShopExecEnv 依赖面桩(LevelUpOp.execute 只触 op/ledger/match/state)。"""

    from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
        LevelUpOp,
        ShopExecEnv,
        ShopVisitLedger,
    )

    op = SimpleNamespace(ctx=SimpleNamespace(
        controller=SimpleNamespace(click=lambda p: None)))
    env = ShopExecEnv(
        op=op, match=SimpleNamespace(session=session), config=None,
        click_pts=[], level_btn=Point(1, 2), refresh_btn=Point(3, 4),
        ledger=ledger or ShopVisitLedger(), state=GameState())
    return LevelUpOp(LevelUp(cost=4)), env


def test_shop_channel_receipt_per_click(captured_exo, monkeypatch):
    """店通道协议 active → execute 一击一行,字段全锁(F8 mode=注册表派生
    卡名;plane/round 显式入 choice,currency/hp_delta/clicks/basis 定值)。"""
    import sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops as so
    monkeypatch.setattr(so.time, 'sleep', lambda s: None)   # 动画等待桩
    op, env = _shop_env(_hp_session(['奋斗协议']))
    assert op.execute(env) is True
    rows = [r for r in captured_exo if r['kind'] == 'hp_pay']
    assert len(rows) == 1                    # 单动作形态 = 恰一击一行
    assert rows[0]['choice'] == {
        'plane': 2, 'round_num': 1, 'currency': 'hp', 'hp_delta': -6,
        'mode': '奋斗协议', 'clicks': 1, 'basis': 'modeled'}
    assert rows[0]['round_num'] == 1         # 顶层 round 同步携带(读端兼容)


def test_prep_channel_four_clicks_four_rows(captured_exo, monkeypatch):
    """F2 粒度锁:prep 通道连点 4 击 → 4 行(每击已实际扣血,机械发射序
    逐击落行);同批 level_up 事件行不混入 hp_pay 计数。批3a(A4 判效
    拆除):点击按授权击数机械执行(血本位 = 入口整级授权击数
    blood_xp_full_clicks),原逐击 OCR 验级判效半删除——击数由授权口径
    承载,不再由验证停点决定。"""
    import sr_od.application.currency_war.prep_actions as pa
    ex = object.__new__(PrepActionExecutor)
    sess = _hp_session(['奋斗协议'])
    sess.effect_inventory = SimpleNamespace(on_level_up=lambda: None)
    sess.last_level_obs = None
    ex._ctx = SimpleNamespace(
        cw_match=SimpleNamespace(session=sess),
        controller=SimpleNamespace(mouse_move=lambda p: None,
                                   click=lambda p: None))
    ex._op = SimpleNamespace(screenshot=lambda: None,
                             park_cursor=lambda **kw: None)
    # 基线读一次(血闸/击数推导输入,执行前观察);判效读已拆(A4)
    reads = iter([5])
    monkeypatch.setattr(pa, '_read_level_raw',
                        lambda ctx, screen: next(reads))
    monkeypatch.setattr(pa, 'read_gold', lambda ctx, screen: 100)
    monkeypatch.setattr(pa, 'area_center', lambda ctx, name: None)
    _detail, emitted = ex._level_up()
    assert emitted is True
    # before=5 → 下一级需 XP 20 → 全量击数 ⌈20/4⌉ = 5 击(机械授权击数)
    rows = [r for r in captured_exo if r['kind'] == 'hp_pay']
    assert len(rows) == 5, \
        f'授权击数 5 = 5 行(粒度=击数,机械执行),实得 {len(rows)}'
    assert all(r['choice']['hp_delta'] == -6 and r['choice']['clicks'] == 1
               for r in rows)


# ===== ⑨ 隔离门(§1.4 测试3):写点零决策状态突变 =====

def test_receipt_write_isolation_no_state_mutation(captured_exo):
    """hp_pay 回执写入前后:state 序列化逐字节不变 + session 无新增属性
    ——写入路径与决策路径无共享可变状态(ADR-0577 隔离申报的可执行面)。"""
    from sr_od.application.currency_war.telemetry.schema import serialize_state
    sess = _hp_session(['奋斗协议'])
    before = json.dumps(serialize_state(sess.last_state), sort_keys=True)
    attrs_before = set(vars(sess).keys())
    record_hp_pay_event(sess, 2, 1)
    assert json.dumps(serialize_state(sess.last_state),
                      sort_keys=True) == before
    assert set(vars(sess).keys()) == attrs_before
    assert len(captured_exo) == 1            # 行照常落(隔离≠不写)


# ===== ⑩ grep 守卫门(F7,ADR-0571 同款手法):hp_pay 遥测键禁入决策面 =====

#: 守卫键集:kind 名 / 结构化载荷键。'basis' 用词边界匹配——决策面在册键
#: auth_basis(授权依据记录字段,LevelUp/发射分键)是不同语义的合法存在,
#: 子串判据会误伤(\\b 在 auth_basis 的下划线处不成立,天然排除)。
_HP_PAY_SUBSTR_KEYS: tuple[str, ...] = ('hp_pay', 'hp_delta')
_HP_PAY_WORD_KEYS: tuple[str, ...] = ('basis',)


def _guard_key_hits(text: str) -> list[str]:
    """守卫判据单一实现(主扫描与变异自检共用,防自检复刻判据)。"""
    hits = [name for name in _HP_PAY_SUBSTR_KEYS if name in text]
    hits += [name for name in _HP_PAY_WORD_KEYS
             if re.search(rf'\b{name}\b', text)]
    return hits


def test_hp_pay_keys_not_consumed_by_decision_modules():
    """hp_pay 遥测键禁现于决策面(strategies/impl 全子树扫描,零白名单
    ——决策判据消费 hp_pay = 把「建模期望账」当支付真值读,违反遥测禁入
    决策输入禁令(ADR-0577 §隔离申报);写点/装配消费面分别在
    prep_actions 与 telemetry,均不在扫描根)。盲区自检:扫描根失准 =
    假绿,先证根在且非空;变异自检:判据函数对合成坏形必须可检出,
    auth_basis 合法在册键必须不误伤。"""
    root = (Path(__file__).resolve().parents[5] / 'src' / 'sr_od'
            / 'application' / 'currency_war' / 'strategies' / 'impl')
    sentinel = root / 'mandate_v1' / 'mandate.py'
    assert sentinel.is_file(), f'扫描根解析失准:{root}'
    scanned = list(root.rglob('*.py'))
    assert len(scanned) >= 20, f'扫描文件数异常({len(scanned)}),根可能错位'
    # 变异自检:正例两键可检出;auth_basis 在册键不误伤(word 边界在
    # 下划线处不成立,天然排除)。
    assert _guard_key_hits("x('hp_pay') r['hp_delta']") == \
        ['hp_pay', 'hp_delta'], '变异自检未命中'
    assert _guard_key_hits('self.auth_basis = "record"') == [], \
        '变异自检:auth_basis 被误伤'
    offenders: dict[str, str] = {}
    for path in scanned:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8')
        for name in _guard_key_hits(text):
            offenders[f'{rel}:{name}'] = name
    assert not offenders, (
        'hp_pay 遥测键被决策面引用(禁令 = ADR-0577:血购回执纯观测,'
        f'禁回写 state.hp/session.last_hp_real/预算门):{offenders}')
