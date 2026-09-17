"""board 派生视图 + 行槽位纯重排吸收 锁面(观察对账族架构收口,20260918-
reconcile 第 5 例收口批)。

出处 = ``.debug/temp/incidents/20260918-reconcile/report.md`` 第 5 例
(run_20260918_045918 p1-r2 停局:board 减益1 vs 实读 减益2 + back_row
同单位集 [佩佩,黑塔,万敌] 纯槽位排列不同)+ 迭代目录 projection-audit.md
(字段完备性审计)。

锁面(全部运行时行为锁,零真实 IO):
- board 派生一致性:front_row/back_row 任何逻辑写端(含历史上忘记写
  board 的写端)后 board 自动按单位集合增量重算单一源
  (``GameState._resync_board_delta``);纯重排写 = 零差零写;
- 观察基座贡献保留:增量口径(非全量重算)不抹掉面板真值中容器行未
  建模的装备羁绊贡献(实机 5 例形态:环境卡星徽穿戴只在面板);
- 纯重排吸收:同单位多重集排列差异 → ``deploy_slot_reorder`` 台账行
  采新(安灯面→纠漂面),缺员/多员/星级差/装备差照真失配停;
- 字段审计完备性:GameState 全部容器字段已在 ``PROJECTION_AUDIT``
  登记且无缺口态(「无写端无规则」恒空)。

单帧锁自足:动作语义复用既有 golden 面(test_cw_transfer_golden),
本文件不重锁动作域写回,只锁 board 派生与重排吸收两块新契约。
"""

from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war.kernel import cw_projection_audit as pa
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    Unit,
    apply_prep_action_logic,
    consume_defect_sink,
    game_state_of,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_mismatch_policy import (
    fire_reconcile_andon,
    set_reconcile_andon_hook,
)
from sr_od.application.currency_war.kernel.cw_vocab import SellDeployed

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


# 注册表真值(data/cw_chars.py):乱破=[巡海游侠,击破],佩佩=零标签。
def _unit(char_id: str, slot: int, *, star: int = 1,
          equips: list[str] | None = None) -> Unit:
    return Unit(char_id=char_id, star=star, equips=list(equips or []),
                slot=slot)


def _pepe(slot: int) -> Unit:
    return _unit('佩佩', slot)


def _luanpo(slot: int) -> Unit:
    return _unit('乱破', slot)


def _heita(slot: int) -> Unit:
    return _unit('黑塔', slot)


def _wandi(slot: int) -> Unit:
    return _unit('万敌', slot)


class _AndonRecorder:
    """安灯钩子记录器(注入槽模式;缺省关,测试显式接通)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def __call__(self, row: dict) -> None:
        self.rows.append(dict(row))


@pytest.fixture()
def andon(monkeypatch: pytest.MonkeyPatch) -> _AndonRecorder:
    """接通安灯钩子并在用例结束复位(跨用例零残留,conftest 防污染纪律)。"""
    rec = _AndonRecorder()
    set_reconcile_andon_hook(rec)
    yield rec
    set_reconcile_andon_hook(None)


# ============================================================ board 派生视图


def test_row_write_resyncs_board_and_preserves_observed_base() -> None:
    """board 派生一致性主锁(5 例回归形态):观察基座 {减益:1}(环境卡
    星徽贡献,容器行未建模)保持不变,行写端新增乱破 → 其注册表标签
    (巡海游侠/击破)自动入 board——历史上忘记写 board 的写端(直接
    write_logic 行域)不再产生「加了单位 board 没跟上」。"""
    gs = game_state_of(None)
    gs.observe(gs.back_row, [_pepe(1)], sig=_SIG_OBS)
    gs.observe(gs.board, {'减益': 1}, sig=_SIG_OBS)
    gs.write_logic(gs.back_row, [_pepe(1), _luanpo(2)],
                   produced_by='T', sig=_SIG)
    assert gs.board.value == {'减益': 1, '巡海游侠': 1, '击破': 1}, \
        '基座贡献保留 + 新增单位标签联动(board 派生单一源)'


def test_row_clear_resyncs_board_to_dropped_tags() -> None:
    """清排写端补锁(EffectLedgerBridge 全场出售清 rows 形态):行写端
    清空后 board 对应标签摘除(减至 0 摘键),不残留幽灵计数。"""
    gs = game_state_of(None)
    gs.observe(gs.front_row, [_luanpo(1)], sig=_SIG_OBS)
    gs.observe(gs.board, {'巡海游侠': 1, '击破': 1}, sig=_SIG_OBS)
    gs.write_logic(gs.front_row, [], produced_by='EffectLedgerBridge',
                   sig=ChannelSig(family='logic_hook',
                                  actor='EffectLedgerBridge'))
    assert gs.board.value == {}, '行清空 → board 标签摘除(派生联动)'


def test_resync_writes_board_with_derived_evidence() -> None:
    """board 派生写端证据:resync 写 source=logic + evidence=
    proj_board_resync(journal 排障入口;独立手写 board 的旧证据名
    proj_board_recount/proj_deploy_board_incr 已随单一源退役)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_row, [_heita(1)], sig=_SIG_OBS)
    gs.observe(gs.board, {'银河学者': 1, '群攻': 1}, sig=_SIG_OBS)
    gs.write_logic(gs.back_row, [_heita(1), _wandi(2)],
                   produced_by='T', sig=_SIG)
    assert gs.board.source == 'logic'
    assert gs.board.evidence == 'proj_board_resync'


def test_pure_reorder_logic_write_yields_zero_board_delta() -> None:
    """纯重排零差零写:同单位多重集的行内排列写(键含槽位号前已滤)
    不产生 board 写(羁绊计数与顺序无关),board 帧保持原引用语义
    (evidence 不变 = 未发生 board 写)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_row, [_pepe(1), _heita(2), _wandi(3)], sig=_SIG_OBS)
    gs.observe(gs.board, {'银河学者': 1, '群攻': 1}, sig=_SIG_OBS)
    board_before = gs.board
    gs.write_logic(gs.back_row, [_heita(1), _wandi(2), _pepe(3)],
                   produced_by='T', sig=_SIG)
    assert gs.board.value == {'银河学者': 1, '群攻': 1}
    assert gs.board is board_before, '零差 → 零 board 写(原帧未换)'


def test_selldeployed_updates_board_via_derived_resync() -> None:
    """投影写端走同一派生口:SellDeployed 容器腿(旧 board 全量重算写端
    已退役)卖出场上单位后 board 经 resync 摘除其标签。"""
    gs = game_state_of(None)
    gs.observe(gs.front_row, [_luanpo(1)], sig=_SIG_OBS)
    gs.observe(gs.board, {'巡海游侠': 1, '击破': 1}, sig=_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    apply_prep_action_logic(gs, SellDeployed(deployed_idx=0),
                            produced_by='T', sig=_SIG)
    assert gs.board.value == {}, '卖出 → 标签摘除(派生口单一)'
    assert gs.board.evidence == 'proj_board_resync'


def test_resync_skips_when_board_never_observed() -> None:
    """板未读(None)= 无派生基座,行写端跳过重算等观察首读(禁造空板
    假值;与「观察基座 + 增量」语义一致)。"""
    gs = game_state_of(None)
    gs.observe(gs.back_row, [_luanpo(1)], sig=_SIG_OBS)
    gs.write_logic(gs.back_row, [_luanpo(1), _wandi(2)],
                   produced_by='T', sig=_SIG)
    assert gs.board.value is None, '板未读 → 跳过派生(不造假值)'


# ============================================================ 行纯重排吸收


def _seed_row_logic(gs: GameState) -> None:
    """5 例事故行态:逻辑 back_row = [佩佩@1, 黑塔@2, 万敌@3](放置序)。"""
    gs.write_logic(gs.back_row, [_pepe(1), _heita(2), _wandi(3)],
                   produced_by='T', sig=_SIG)


def test_pure_slot_reorder_observed_absorbed_with_ledger_row(andon) -> None:
    """纯重排吸收主锁(5 例 back_row 形态):同单位多重集、仅槽位排列
    不同 → deploy_slot_reorder 台账行(无告警无停机)+ 采新覆盖,安灯
    不触发(「纯重排」从安灯面移入纠漂面)。"""
    gs = game_state_of(None)
    _seed_row_logic(gs)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        # 游戏侧排序(实读):黑塔@1, 万敌@2, 佩佩@3
        gs.observe(gs.back_row, [_heita(1), _wandi(2), _pepe(3)],
                   sig=_SIG_OBS)
    finally:
        set_defect_sink(None)
        drained = consume_defect_sink()
    assert gs.back_row.source == 'observation', '采新(游戏排序为画面事实)'
    assert [u.char_id for u in gs.back_row.value] == ['黑塔', '万敌', '佩佩']
    assert len(rows) == 1 and rows[0]['kind'] == 'deploy_slot_reorder', \
        '台账行落证(无告警无停机族)'
    assert rows[0]['field'] == 'back_row'
    assert andon.rows == [], '纯重排不触发安灯'
    assert drained == rows


def test_row_missing_member_is_real_mismatch(andon) -> None:
    """缺员照停锁:重排形状不成立(实读少一人)→ 真失配缺陷行 + 安灯,
    真 bug 不被吸收面吞。"""
    gs = game_state_of(None)
    _seed_row_logic(gs)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.back_row, [_heita(1), _wandi(2)], sig=_SIG_OBS)
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert rows and rows[-1]['kind'] == 'observe_vs_logic_mismatch'
    assert len(andon.rows) == 1, '缺员 = 真失配照停'


def test_row_star_diff_is_real_mismatch(andon) -> None:
    """星级差照停锁:同身份不同星级 = 非纯重排(合成/漏读等真差异),
    照真失配停。"""
    gs = game_state_of(None)
    _seed_row_logic(gs)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.back_row, [
            Unit(char_id='佩佩', star=2, equips=[], slot=1),
            _heita(2), _wandi(3)], sig=_SIG_OBS)
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert rows and rows[-1]['kind'] == 'observe_vs_logic_mismatch'
    assert len(andon.rows) == 1


def test_row_equip_diff_is_real_mismatch(andon) -> None:
    """装备差照停锁:键含装备集——穿戴变化(星徽贡献面)不算纯重排,
    照真失配停(吸收面不吞穿戴族 bug)。"""
    gs = game_state_of(None)
    _seed_row_logic(gs)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.back_row, [
            Unit(char_id='佩佩', star=1, equips=['减益星徽'], slot=1),
            _heita(2), _wandi(3)], sig=_SIG_OBS)
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert rows and rows[-1]['kind'] == 'observe_vs_logic_mismatch'
    assert len(andon.rows) == 1


def test_andon_hook_absent_reorder_still_adopts_silently() -> None:
    """缺省安灯(测试/sim 形态)= 吸收面只留证不炸;fire 路径与钩子
    解耦(cw_mismatch_policy 注入槽契约回归)。"""
    gs = game_state_of(None)
    _seed_row_logic(gs)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.back_row, [_wandi(1), _pepe(2), _heita(3)],
                   sig=_SIG_OBS)
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert gs.back_row.source == 'observation'
    assert rows[0]['kind'] == 'deploy_slot_reorder'
    fire_reconcile_andon({'probe': True})   # 钩子缺席 = best-effort 静默


# ============================================================ 字段审计完备性


def _gs_field_names() -> list[str]:
    """GameState 全部容器(Field 域)字段名(与 cw_game_state 域声明
    同源;非 Field 簿记宿主不在审计域)。"""
    out: list[str] = []
    for f in dataclasses.fields(GameState):
        t = f.type if isinstance(f.type, str) else str(f.type)
        if t.split('[')[0].strip().endswith('Field'):
            out.append(f.name)
    return out


def test_projection_audit_table_complete_and_gap_free() -> None:
    """字段审计完备性抽检锁:①GameState 全部容器字段已登记(防新字段
    静默逃过审计);②表无退役残留键;③状态全在枚举内(「无写端无规则」
    缺口态 = 表内不可表达,可失配面必须落在写端/吸收两态);④已知停局
    家族(20260918 五连停局各域)的收口机制关键词仍在位(防重构悄悄
    拔掉吸收/派生面)。"""
    names = _gs_field_names()
    assert pa.audit_missing_fields(names) == [], '字段漏登记'
    assert pa.audit_stale_keys(names) == [], '表残留退役键'
    assert pa.audit_bad_status_keys() == [], '状态越枚举'
    assert pa.audit_family_mechanism_missing() == [], \
        '停局家族收口机制失位'
