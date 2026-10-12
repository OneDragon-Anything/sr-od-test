"""T-8 人身意外险(id 107)节点序列环境修饰 · 锁面(设计 §4 锁 1-11)。

设计正本 = .debug/progress/2026-09-23-invest-effects-calc/designs/
T-8-renshenyiwai-xian.md(裁决点 1-7 已裁;本文件锁的是设计约定,不锁
实现细节)。锁面地图:

- 锁 1 修饰规则纯函数(:func:`resolve_plane_node_seqs` 白名单/默认表不可变);
- 锁 2 正反解互逆(修饰制全域对拍 + 域外 P3UnobservedError + None 回退与
  固定 9 制逐值等价);
- 锁 3 场字段生命周期(写点唯一/字段恒全量/None 回退/快照恢复携带);
- 锁 4 next_screen 推导(修饰制声明补给/boss 档/位面过渡/超 18 局终);
- 锁 5 sim 世界真值(修饰局全链:插入补给屏 M18 + 收入 supply 分支 +
  局终 eff=19 + 零 DECL_SCREEN_DRIFT);
- 锁 6 观察读链两位数(read 顶栏/识别器工具态/recorder 接线);
- 锁 7 白名单归属校验(import 期孤儿键炸);
- 锁 8 默认局回归(env 无修饰全链局终轮次与现役基线同);
- 锁 9 坐标消费面修饰局(商店查链反解/镜像序/直定倒退免疫/两锚定写端);
- 锁 10 acquired_t 同坐标系(登记当拍不递减);
- 锁 11 结算读数与单调门(两位数/粘连噪声/元组比较三态/HP 推断路径消亡)。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel import cw_node_schedule as ns
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    _portal_acquired_t,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    _obs_node_ordinal,
    _shop_panel_type_target,
    _write_derived_node_type,
    game_state_of,
    node_ordinal_of,
    observe_node_anchor,
    report_node_advance,
    restore_state_snapshot,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    P1_NODE_SEQUENCE,
    P2_NODE_SEQUENCE,
    PLANE_NODE_TABLES,
    P3UnobservedError,
    node_pos_of,
    node_round_cap,
    node_sequence_of,
    resolve_plane_node_seqs,
)
from sr_od.application.currency_war.obs.cw_observation import (
    parse_phase_round_text,
    phase_round_in_range,
)
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    parse_settlement_round,
)

_SIG_OBS = ChannelSig(family='obs', actor='TestSeqEnv', mode='read')


def _logic_sig(actor: str = 'TestSeqEnv') -> ChannelSig:
    return ChannelSig(family='logic_action', actor=actor, mode='compute')


def _modified() -> dict[int, tuple[str, ...]]:
    return resolve_plane_node_seqs('人身意外险')


def _gs_with_field(
        value: dict[int, tuple[str, ...]] | None) -> GameState:
    """带场字段的裸容器(写通道 = 生产写口 write_logic;None = 未注册态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if value is not None:
        gs.write_logic(gs.node_seq_by_plane, value,
                       produced_by='TestSeqEnv', evidence='node_seq:env',
                       sig=_logic_sig())
    return gs


# ============================================================ 锁 1 修饰规则

def test_lock1_resolve_default_env_returns_default_tables() -> None:
    """白名单外环境(含空名)原样返回默认表;默认表元组对象不被复制也不
    被原地改(对象同一性)。"""
    for name in ('头彩', '火药味', '过剩经费', ''):
        out = resolve_plane_node_seqs(name)
        assert out == {1: P1_NODE_SEQUENCE, 2: P2_NODE_SEQUENCE}
        assert out[1] is P1_NODE_SEQUENCE and out[2] is P2_NODE_SEQUENCE
    assert PLANE_NODE_TABLES == {1: P1_NODE_SEQUENCE, 2: P2_NODE_SEQUENCE}


def test_lock1_resolve_modified_inserts_supply_before_each_boss() -> None:
    """人身意外险:P1 r9 supply + r10 boss、P2 r7 supply + r8 boss(每个
    boss 位前各一);P3 不产出键(不运行现状)。"""
    mod = _modified()
    assert set(mod) == {1, 2}
    assert mod[1][-2:] == ('supply', 'boss')
    assert mod[1][:-2] == P1_NODE_SEQUENCE[:-1]
    assert len(mod[1]) == 10
    assert mod[2][-2:] == ('supply', 'boss')
    assert mod[2][:-2] == P2_NODE_SEQUENCE[:-1]
    assert len(mod[2]) == 8
    with pytest.raises(P3UnobservedError):
        node_sequence_of(3, mod)


# ============================================================ 锁 2 正反解互逆

def test_lock2_forward_inverse_modified_domain_exhaustive() -> None:
    """修饰制 (plane, round) ↔ ordinal 全域对拍(P1×10 + P2×8 穷举);
    域外点 (3,1) 两函数同抛 P3UnobservedError。"""
    mod = _modified()
    for plane in (1, 2):
        for r in range(1, len(mod[plane]) + 1):
            o = node_ordinal_of(plane, r, mod)
            assert node_pos_of(o, mod) == (plane, r)
    assert node_ordinal_of(2, 1, mod) == 11
    assert node_ordinal_of(1, 10, mod) == 10, '修饰制 (1,10)/(2,1) 不塌缩'
    with pytest.raises(P3UnobservedError):
        node_ordinal_of(3, 1, mod)
    with pytest.raises(P3UnobservedError):
        node_pos_of(19, mod)


def test_lock2_none_fallback_equals_legacy_formula() -> None:
    """seqs=None 与固定 9 制公式在有效域内逐值等价(现役行为回归)。"""
    for plane in (1, 2):
        for r in range(1, 10):
            assert node_ordinal_of(plane, r) == (plane - 1) * 9 + r
    assert node_pos_of(10) == (2, 1)
    assert node_pos_of(9) == (1, 9)


# ============================================================ 锁 3 场字段生命周期

def test_lock3_write_leg_whitelist_full_modified_table() -> None:
    """环境注册(白名单内)→ 字段落修饰表,evidence='node_seq:env',
    通道 = logic(确定性可计算);字段恒全量无半态。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        gain_invest_env,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gain_invest_env(gs, None, '人身意外险', rand=False, sig=_logic_sig())
    assert gs.node_seq_by_plane.value == _modified()
    assert gs.node_seq_by_plane.source == 'logic'
    assert gs.node_seq_by_plane.evidence == 'node_seq:env'


def test_lock3_write_leg_non_whitelist_full_default_table() -> None:
    """环境注册(白名单外)→ 字段落默认表(注册后恒全量);OCR 形变名
    经归一后命中。"""
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        gain_invest_env,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gain_invest_env(gs, None, '火药味', rand=False, sig=_logic_sig())
    assert gs.node_seq_by_plane.value == dict(PLANE_NODE_TABLES)


def test_lock3_none_field_consumers_fall_back_to_default() -> None:
    """字段 None(未注册)→ 消费方回退默认表;裸容器字段缺省 None。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert gs.node_seq_by_plane.value is None
    assert node_sequence_of(1, gs.node_seq_by_plane.value) \
        == P1_NODE_SEQUENCE
    assert node_round_cap(2, gs.node_seq_by_plane.value) == 7


def test_lock3_snapshot_restore_carries_field() -> None:
    """快照恢复随容器现值携带(键 int 化 + 值 tuple 化重建)。"""
    gs = _gs_with_field(_modified())
    snap = gs.full_state_snapshot()
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs2, snap)
    assert gs2.node_seq_by_plane.value == _modified()
    assert all(isinstance(k, int) for k in gs2.node_seq_by_plane.value)
    assert all(isinstance(v, tuple) for v in gs2.node_seq_by_plane.value.values())


# ============================================================ 锁 4 next_screen 推导

def test_lock4_next_screen_modified_regime() -> None:
    """修饰制推进声明:P1 r8→r9 = 补给、r9→r10 = boss 简报、跨位面 =
    位面过渡、P2 r7→r8 = boss 简报、超 18(eff=19)= 局终空档。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SCREEN_BOSS_BRIEFING,
    )
    gs = _gs_with_field(_modified())
    anchor = '货币战争-备战'
    observe_node_anchor(gs, 8, trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and out.world_decl.next_screen == '货币战争-补给'
    observe_node_anchor(gs, 9, trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and out.world_decl.next_screen == SCREEN_BOSS_BRIEFING
    observe_node_anchor(gs, 10, trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied \
        and out.world_decl.next_screen == '货币战争-位面过渡'
    observe_node_anchor(gs, 17, trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and out.world_decl.next_screen == SCREEN_BOSS_BRIEFING
    observe_node_anchor(gs, 18, trigger_screen=anchor, actor='TestSeqEnv')
    out = report_node_advance(gs, trigger='settle_confirm')
    assert out.applied and out.world_decl.next_screen == '', \
        'eff=19 超修饰表总长 → 局终声明'


# ============================================================ 锁 6 观察读链

def test_lock6_parse_and_cap_two_digit_round() -> None:
    """「1-10」形:修饰局(round_caps=修饰表)整读 (1,10);默认局
    (caps=None/默认表)P1 仍拒(cap 9,现役口径回归)。「A8」类错源仍拒;
    位面化上限外仍拒;(Lv.12-3)旧误读窗被两位数正则顺带拒掉。"""
    assert parse_phase_round_text('备战阶段 1-10') == (1, 10)
    assert phase_round_in_range((1, 10), _modified()) is True
    assert phase_round_in_range((1, 10), dict(PLANE_NODE_TABLES)) is False
    assert phase_round_in_range((1, 10), None) is False
    assert parse_phase_round_text('A8') is None
    assert parse_phase_round_text('A8', digit_fallback=True) == (8, 8)
    assert phase_round_in_range((8, 8), _modified()) is False
    assert phase_round_in_range((1, 11), _modified()) is False, 'cap 10'
    assert phase_round_in_range((2, 9), _modified()) is False, 'cap 8'
    assert phase_round_in_range((1, 13), _modified()) is False
    assert parse_phase_round_text('Lv.12-3') == (12, 3)
    assert phase_round_in_range((12, 3), None) is False
    assert parse_phase_round_text('备战阶段 1-3') == (1, 3)
    assert phase_round_in_range((1, 3), None) is True
    # read_phase_round 主链不带数字回退(w891 停用裁定共享实现关该支)
    assert parse_phase_round_text('Lv.3') is None
    assert parse_phase_round_text('Lv.3', digit_fallback=True) == (3, 3)


def test_lock6_p3_cap_margin_twelve_both_states() -> None:
    """P3 无观测表:seqs 给定缺该位面与 seqs=None 两态均落 12 余量
    (数值单一源 = node_round_cap)。"""
    assert node_round_cap(3, _modified()) == 12
    assert node_round_cap(3, None) == 12


def test_lock6_recognizer_tool_state_shares_parsing(
        test_context, monkeypatch) -> None:
    """battle_prep_recognizer 与正解共享解析(同正则同值域);工具态
    round_caps 恒 None → cap 回退默认长度 P1=9:「1-10」不作放行要求
    (工具面显示 r9 口径,修饰局真值由场字段/台账承载)。"""
    from sr_od.application.currency_war.obs.recognizers import (
        battle_prep_recognizer as rec,
    )

    def _fake_ocr(ctx, screen, rect):
        return [SimpleNamespace(data=_blob['text'])]

    _blob = {'text': '备战阶段 1-3'}
    monkeypatch.setattr(rec, '_ocr', _fake_ocr)
    assert rec._read_phase_round_pure(test_context, object()) == (1, 3)
    _blob['text'] = '备战阶段 1-10'
    assert rec._read_phase_round_pure(test_context, object()) is None, \
        '工具态 cap 回退默认 9,r10 拒(披露:1-10 断言对 recognizer 不作要求)'
    _blob['text'] = '第2位面'
    assert rec._read_phase_round_pure(test_context, object()) == (2, 2)


def test_lock6_recorder_and_funnel_wiring_passes_caps(
        monkeypatch) -> None:
    """cw_match_recorder 语料采集与 read_game_state 漏斗随批接线:
    round_caps 透传场字段现值(实时态);局外无容器 = None 回退。"""
    from sr_od.application.currency_war.telemetry import cw_match_recorder

    captured: dict = {}

    def _fake_read(ctx, img, round_caps=None):
        captured['caps'] = round_caps
        return 1, 10

    monkeypatch.setattr(cw_match_recorder, 'read_phase_round', _fake_read)
    # 实时态:session 旁表单例(game_state_from_ctx 取口 = cw_match.session)
    session = cw4_session()
    gs = game_state_of(session)
    gs.write_logic(gs.node_seq_by_plane, _modified(),
                   produced_by='TestSeqEnv', evidence='node_seq:env',
                   sig=_logic_sig())
    ctx = SimpleNamespace(cw_match=SimpleNamespace(session=session))
    cw_match_recorder.extract_frame(ctx, object(), object())
    assert captured['caps'] == _modified()
    # 局外:无 match → caps None(回退默认口径,披露 10②)
    cw_match_recorder.extract_frame(SimpleNamespace(), object(), object())
    assert captured['caps'] is None


# ============================================================ 锁 7 归属校验

def test_lock7_registry_ownership_orphan_key_raises(monkeypatch) -> None:
    """白名单键改名漂移(注册表无此环境)→ 校验炸(键 ⊆ INVESTMENT_ENVS,
    防版本改名静默失联);现役键校验通过。"""
    cw_investments._validate_env_node_seq()   # 现役键通过
    monkeypatch.setattr(ns, 'ENV_NODE_SUPPLY_BEFORE_BOSS',
                        frozenset({'不存在的环境'}))
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_env_node_seq()


# ============================================================ 锁 9 坐标消费面

def _shop_gs_with_target(mod_target_ord: int,
                         mirror: NodeKey | None) -> GameState:
    """修饰局商店帧容器:生效序 = 修饰制目标序(hist/ord 同值),镜像按参。"""
    gs = _gs_with_field(_modified())
    observe_node_anchor(gs, mod_target_ord, trigger_screen='货币战争-备战',
                        actor='TestSeqEnv')
    if mirror is not None:
        gs.observe(gs.node, mirror, evidence='t', sig=_SIG_OBS)
    return gs


def test_lock9_shop_chain_query_key_modified_not_9shift(monkeypatch) -> None:
    """①商店查链:修饰局 P2 r2(修饰制 ord 12)店开帧 → 链查询键 =
    (2,2),非 9 制解码的 (2,3)(漏改则恒查后一节点,类型查链静默失效);
    直定反解同源落 (2,2) 键。"""
    gs = _shop_gs_with_target(12, NodeKey(plane=2, round_num=2, kind=''))
    queried: list[tuple[int, int]] = []

    def _fake_chain(g, plane, round_num):
        queried.append((plane, round_num))
        from sr_od.application.currency_war.kernel.cw_game_state import (
            ChainQuery,
        )
        return ChainQuery(token=None)   # 链缺 = 零写,只锁查询键

    monkeypatch.setattr(gs_mod, 'chain_node_type', _fake_chain)
    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG_OBS)
    assert queried == [(2, 2)]
    assert _node_key_for_ord_modified(12) == (2, 2), '直定反解 = 修饰制 (2,2)'


def _node_key_for_ord_modified(ordinal: int) -> tuple[int, int]:
    from sr_od.application.currency_war.kernel.cw_game_state import (
        _node_key_for_ord,
    )
    key = _node_key_for_ord(ordinal, 'boss', seqs=_modified())
    return key.plane, key.round_num


def test_lock9_mirror_sequence_reads_field(monkeypatch) -> None:
    """③镜像序:镜像 (2,3)/生效序 12(修饰制 (2,2))的修饰局 →
    `_shop_panel_type_target` 取 max = 修饰制 (2,3) 序 13(镜像领先保护
    维持);场字段缺位反差镜 = 9 制 12(漏传即回归本锁红的病理形态)。"""
    gs = _shop_gs_with_target(12, NodeKey(plane=2, round_num=3, kind='battle'))
    assert _obs_node_ordinal(gs) == 13
    assert _shop_panel_type_target(gs) == 13
    # 反差镜:同镜像按 9 制解码 = 12(漏读场字段的退化值,非现役行为)
    gs9 = _shop_gs_with_target(12, NodeKey(plane=2, round_num=3,
                                           kind='battle'))
    gs9.write_logic(gs9.node_seq_by_plane, None, produced_by='TestSeqEnv',
                    evidence='t:none', sig=_logic_sig())
    assert _obs_node_ordinal(gs9) == 12


def test_lock9_direct_write_regression_immunity_uses_field() -> None:
    """②直定倒退免疫:镜像 (2,3) 领先、直定目标 (2,2)(修饰制 ord 12)
    → 修饰制镜像序 13 > 12 丢弃留证不回写;直定 (2,3)(ord 13)照常落
    (2,3) 键。漏读场字段则 12>12 判假、类型串写——本锁必红。"""
    gs = _shop_gs_with_target(12, NodeKey(plane=2, round_num=3,
                                          kind='battle'))
    seq = gs.write_seq
    _write_derived_node_type(gs, 'boss', target_ord=12, actor='TestSeqEnv',
                             trigger_screen='货币战争-备战-开商店',
                             seq=seq + 1)
    assert gs.node.value.round_num == 3, '倒退丢弃:镜像节点不被回写'
    # 同帧不落直定(node 镜像未被改写;丢弃走 obs_event 留证)
    _write_derived_node_type(gs, 'boss', target_ord=13, actor='TestSeqEnv',
                             trigger_screen='货币战争-备战-开商店',
                             seq=seq + 2)
    assert (gs.node.value.plane, gs.node.value.round_num, gs.node.value.kind) \
        == (2, 3, 'boss'), '目标序 = 修饰制 (2,3),直定落同键'


def test_lock9_prep_anchor_write_end_passes_field(
        test_context, monkeypatch) -> None:
    """④live 锚定写端 1(CwScreenPrep 备战帧,P2 战斗节点唯一 node_ord
    观察写端):修饰局 (2,1) 回执 → 锚定 ordinal = 11(场字段派生);
    漏传 = 9 制 10 → 恒滞后一节影子轨道,本锁红。"""
    from test.sr_od.application.currency_war._cw_helpers import (
        run_node,
    )

    from sr_od.application.currency_war.obs import cw_observe_full as ofm
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_prep as pp,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )

    session = cw4_session()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    gs = game_state_of(session)
    gs.write_logic(gs.node_seq_by_plane, _modified(),
                   produced_by='TestSeqEnv', evidence='node_seq:env',
                   sig=_logic_sig())
    _receipt: dict = {}

    def _fake_observe_full(ctx, screen, **kw):
        _r = _receipt.get('r')
        return {
            'bench_view': None, 'deployed_rows': None,
            'read_receipt': (SimpleNamespace(plane=_r[0], round_num=_r[1],
                                             level=None)
                             if _r is not None else None),
            'node_slots': None, 'owned_equips': None,
            'occupied_equips': None, 'substate': None,
        }

    monkeypatch.setattr(ofm, 'observe_full', _fake_observe_full)
    op = CwScreenPrep(test_context)
    monkeypatch.setattr(op, 'park_cursor', lambda **k: None)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(op, '_reconcile_tracking',
                        lambda bv, dr, screen: (None, None, None))
    monkeypatch.setattr(pp, 'row_area_centers', lambda ctx, name: [])
    monkeypatch.setattr(pp, 'read_ore_sights', lambda ctx, screen: [])
    monkeypatch.setattr(pp, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(pp, 'read_deployed_count', lambda ctx, screen: None)

    _receipt['r'] = (2, 1)
    run_node(test_context, op, lambda: op._observe(True, screen=object()))
    assert gs.node_ord.value == 11, \
        '修饰局 (2,1) 锚定 = 修饰制序 11(9 制 10 = 影子轨道回归)'
    assert gs.node_ord.source == 'observation'


def test_lock9_supply_bar_write_end_passes_field(test_context) -> None:
    """④live 锚定写端 2(CwScreenSupplyNode 节点条):修饰局「2-7」读数
    → ordinal 17(场字段派生,消第二份内联公式);「2-8」随 cap 8 放行 =
    18;场字段缺位反差镜 = 9 制 16 / 「2-8」拒(漏传回归形态)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
        CwScreenSupplyNode,
    )

    def _make(ctx_gs, text: str):
        def _map(**kw):
            return {text: SimpleNamespace(
                max=SimpleNamespace(center=SimpleNamespace(x=1, y=1)))}
        ctx = SimpleNamespace(
            screen_loader=SimpleNamespace(get_area=lambda s, a: SimpleNamespace(
                pc_rect=SimpleNamespace(x1=10, y1=10, x2=200, y2=40))),
            ocr_service=SimpleNamespace(get_ocr_result_map=_map),
            cw_match=SimpleNamespace(gs=ctx_gs),
        )
        op = CwScreenSupplyNode.__new__(CwScreenSupplyNode)
        op.ctx = ctx
        return op

    mod = _modified()
    op = _make(_gs_with_field(mod), '备战阶段 2-7')
    assert op._read_node_bar(object()) == 17, '修饰制 (2,7) = 17'
    op = _make(_gs_with_field(mod), '备战阶段 2-8')
    assert op._read_node_bar(object()) == 18, 'cap 随场字段放宽到 8'

    # 反差镜:场字段缺位(未注册)→ cap 7:「2-7」= 9 制 16、「2-8」拒
    op9 = _make(_gs_with_field(None), '备战阶段 2-7')
    assert op9._read_node_bar(object()) == 16
    op9 = _make(_gs_with_field(None), '备战阶段 2-8')
    assert op9._read_node_bar(object()) is None


# ============================================================ 锁 10 acquired_t

def test_lock10_acquired_t_same_coordinate_system() -> None:
    """登记时点快照与推进入账同坐标系:修饰局 (2,2) 登记「接下来 N 节点」
    → 快照 = 12(修饰制;9 制 11 = 回归形态);登记节点当拍不递减,推进
    至 (2,3)(13)起递减。"""
    session = cw4_session()
    gs = game_state_of(session)
    gs.write_logic(gs.node_seq_by_plane, _modified(),
                   produced_by='TestSeqEnv', evidence='node_seq:env',
                   sig=_logic_sig())
    gs.observe(gs.node, NodeKey(plane=2, round_num=2, kind='battle'),
               evidence='t', sig=_SIG_OBS)
    acquired = _portal_acquired_t(gs, session)
    assert acquired == 12, '登记快照 = 修饰制 (2,2) 序(9 制 11 = 漏改)'
    gs.effects.register_strategy(STRATEGY_EFFECTS['躺平'], acquired)
    advanced, expired = gs.effects.advance_node(12)
    assert advanced and not expired
    entry = next(e for e in gs.effects.entries if e.spec.name == '躺平')
    assert entry.remaining_nodes == 3, '登记节点当拍不递减'
    advanced, expired = gs.effects.advance_node(13)
    assert advanced and not expired
    assert entry.remaining_nodes == 2, '推进至 (2,3) 起递减'


# ============================================================ 锁 11 结算读数与单调门

def test_lock11_parse_settlement_round_two_digit_and_noise() -> None:
    """结算屏读数:「1-10」→ (1,10)(修饰局 caps);caps=None 回退默认
    长度拒;「11-6」粘连噪声仍拒(lookaround 保留);值域外 (1,13) 拒。"""
    mod = _modified()
    assert parse_settlement_round(['挑战结束', '1-10', '战斗'], mod) == (1, 10)
    assert parse_settlement_round(['挑战结束', '1-10', '战斗'], None) is None
    assert parse_settlement_round(['挑战结束', '1-6', '战斗'], None) == (1, 6)
    assert parse_settlement_round(['挑战结束', '11-6', '战斗'], mod) is None
    assert parse_settlement_round(['挑战结束', '1-13', '战斗'], mod) is None
    assert parse_settlement_round(['挑战结束', '13-2', '战斗'], mod) is None


def _battle_wait_op(test_context, monkeypatch, last_known: tuple[int, int],
                    screen_round: tuple[int, int] | None,
                    captured: dict, outcome=None):
    """battle_wait 裸实例 + 全桩面(先例 = test_cw_env_grants_live):
    last_known = read_phase_round 桩值;screen_round = parse_settlement_round
    桩值;captured 收集 read_round_outcome/apply_settlement_cover 入参。"""
    from sr_od.application.currency_war.kernel.cw_performance import (
        RoundOutcome,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bw,
    )
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
        CwScreenBattleWait,
        SettlementState,
    )

    session = cw4_session()
    st = SettlementState(battle_ts=1234.0, run_start_ts=time.monotonic(),
                         is_new_match=False)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    monkeypatch.setattr(test_context, 'ocr_service',
                        SimpleNamespace(get_ocr_result_list=lambda **k: []),
                        raising=False)
    op = CwScreenBattleWait.__new__(CwScreenBattleWait)
    op.ctx = test_context
    op._st = st
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(bw, 'read_phase_round',
                        lambda ctx, scr, round_caps=None: last_known)
    monkeypatch.setattr(bw, 'parse_settlement_round',
                        lambda texts, round_caps=None: screen_round)
    if outcome is None:
        outcome = RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                               comp_tag='c', hp_after=3, hp_confidence=1.0,
                               killed=False)

    def _fake_outcome(ctx, scr, **k):
        captured['outcome_plane'] = k.get('plane')
        captured['outcome_round'] = k.get('round_num')
        captured['outcome_killed'] = getattr(
            queue[0], 'killed', None) if queue else None
        return queue.pop(0)

    queue = [outcome]
    monkeypatch.setattr(bw, 'read_round_outcome', _fake_outcome)

    real_cover = gs_mod.apply_settlement_cover

    def _fake_cover(gs, **k):
        captured['cover_killed'] = k.get('killed')
        return real_cover(gs, **k)

    monkeypatch.setattr(gs_mod, 'apply_settlement_cover', _fake_cover)
    return op


def test_lock11_monotonic_gate_tuple_compare(
        test_context, monkeypatch) -> None:
    """结算单调门元组比较:(1,10) 后遇 (2,1) 结算屏被采(前进,塌缩
    消除);(2,1) 后遇陈旧 (1,10) 被拒(防修饰局重放残留);同轮重录
    (2,1)==(2,1) 照常接受。"""
    # 采:last-known (1,10) + 结算屏 (2,1) → 行落 (2,1)
    captured: dict = {}
    op = _battle_wait_op(test_context, monkeypatch, (1, 10), (2, 1), captured)
    op._record_round_outcome(object())
    assert (captured['outcome_plane'], captured['outcome_round']) == (2, 1)

    # 拒:last-known (2,1) + 陈旧 (1,10) → 保 last-known
    captured = {}
    op = _battle_wait_op(test_context, monkeypatch, (2, 1), (1, 10), captured)
    op._record_round_outcome(object())
    assert (captured['outcome_plane'], captured['outcome_round']) == (2, 1), \
        '陈旧 (1,10) < (2,1) 字典序拒(9 制下同为 10 会被平局放行)'

    # 同轮重录:(2,1) == (2,1) → 接受
    captured = {}
    op = _battle_wait_op(test_context, monkeypatch, (2, 1), (2, 1), captured)
    op._record_round_outcome(object())
    assert (captured['outcome_plane'], captured['outcome_round']) == (2, 1)


def test_lock11_killed_hp_fallback_path_gone(
        test_context, monkeypatch) -> None:
    """killed-hp 兜底门删除:两主路径(progress 符号/killed 文本)同失
    (killed=None ∧ progress=None)→ killed 保持 None 观察收口,无 HP
    推断路径(旧门会按 hp 对比产出 killed)。"""
    from sr_od.application.currency_war.kernel.cw_performance import (
        RoundOutcome,
    )
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.hp, 50, evidence='t', sig=_SIG_OBS)   # 旧门的前置真值源
    captured: dict = {}
    outcome = RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                           comp_tag='c', hp_after=60, hp_confidence=1.0,
                           killed=None, progress_delta=None)
    op = _battle_wait_op(test_context, monkeypatch, (1, 1), None, captured,
                         outcome=outcome)
    op._record_round_outcome(object())
    assert captured.get('cover_killed') is None, \
        'HP 推断路径消亡:killed 诚实缺位(旧门会产出 True/False)'


# ============================================================ 锁 5 / 锁 8 sim 世界真值

_DEF_STEPS = 160


def _start_game(env_present: bool, seed: int = 7):
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SimBackend,
        install_backend,
    )
    from sr_od.application.currency_war.sim.cw_sim_run_config import (
        RunConfig,
    )
    cfg = RunConfig(selected_difficulty='A8', enemy_difficulty=108,
                    env_present=env_present)
    b = SimBackend(seed=seed, cfg=cfg)
    install_backend(b)
    return b


def _drive_step(b, rng_seed: int) -> None:
    """单步驱动(backend 直驱,先例 = test_cw_sim_backend._drive_step;
    按呈现屏分派到对应真实写端,18 动作全量单轨)。"""

    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_megastar_param,
        report_action_pick_planner_param,
        report_action_pick_supply_param,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        report_node_advance,
    )
    from sr_od.application.currency_war.sim import cw_sim_ports
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SCREEN_ENCOUNTER,
        SCREEN_INVEST_STRATEGY,
        SCREEN_PREP,
        SCREEN_SETTLE,
        SCREEN_SUPPLY,
        stream_rng,
    )

    screen = b.screen_identity()
    gs = b.gs
    if screen == SCREEN_SUPPLY:
        opts = gs.supply.value.options
        gs.write_logic(gs.chosen_supply,
                       ('', opts[0].equip, opts[0].has_diamond),
                       produced_by='Test', evidence='t:chosen',
                       sig=_logic_sig('Test'))
        out = report_action_pick_supply_param(
            gs, SimpleNamespace(idx=0, char_name='', norm_item=opts[0].equip),
            _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
        out2 = report_node_advance(gs, trigger='supply_confirm')
        assert out2.applied
        cw_sim_ports.declare_world(out2.world_decl)
    elif screen == SCREEN_INVEST_STRATEGY:
        opts = gs.invest_strategy_opts.value
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_pick_invest_strategy_param,
        )
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=opts[0]), _logic_sig('Test'),
            rng=stream_rng(rng_seed, 'M11/pick/part'),
            session=SimpleNamespace())
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_SETTLE:
        out = report_node_advance(gs, trigger='settle_confirm')
        assert out.applied, out.reason
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-位面过渡':
        b._handle_click_source('货币战争-位面过渡', '区域-空白点击')
    elif screen == '货币战争-BOSS简报':
        b._handle_click_source('货币战争-BOSS简报', '区域-空白点击')
    elif screen == SCREEN_ENCOUNTER:
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_pick_encounter_param,
        )
        out = report_action_pick_encounter_param(
            gs, SimpleNamespace(idx=0), _logic_sig('Test'))
        assert out.applied
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-盛会之星':
        out = report_action_pick_megastar_param(gs, SimpleNamespace(),
                                                _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == '货币战争-银狼升星':
        out = report_action_pick_planner_param(gs, SimpleNamespace(),
                                               _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
    elif screen == SCREEN_PREP:
        from sr_od.application.currency_war.kernel.cw_action_report import (
            report_action_start_battle_param,
        )
        out = report_action_start_battle_param(gs, SimpleNamespace(),
                                               _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
    else:
        raise AssertionError(f'未知呈现屏 {screen}')


def test_lock5_sim_modified_game_full_chain(monkeypatch) -> None:
    """修饰局 sim 全链:选人身意外险 → 场字段落修饰表;P1 r9 呈现补给屏
    (M18 选项)+ 收入 supply 分支(连胜不动);r10 boss;P2 r7/r8 同构;
    局终 = 推进超 18(eff=19)成立;全程零 DECL_SCREEN_DRIFT。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_invest_env_param,
    )
    from sr_od.application.currency_war.sim import cw_sim_ports
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        DECL_SCREEN_DRIFT,
        DISCLOSURE_P3_UNOBSERVED,
        SCREEN_BOSS_BRIEFING,
        SCREEN_BRIEFING,
        SCREEN_INVEST_ENV,
        SCREEN_SUPPLY,
        uninstall_backend,
    )

    b = _start_game(env_present=True, seed=61)
    try:
        assert b.screen_identity() == SCREEN_BRIEFING
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        assert b.screen_identity() == SCREEN_INVEST_ENV
        # 定向候选(测试种子,同写入口):idx=1 = 人身意外险
        b.gs.observe(b.gs.invest_env_opts,
                     ('头彩', '人身意外险', '轮岗'),
                     evidence='sim:synthesized', sig=_SIG_OBS)
        out = report_action_pick_invest_env_param(
            b.gs, SimpleNamespace(idx=1), _logic_sig('Test'))
        assert out.applied
        assert (b.gs.active_env.value or '') == '人身意外险'
        assert b.gs.node_seq_by_plane.value == _modified(), \
            '环境注册即落修饰表(获得链写腿,sim 与 live 同链)'
        cw_sim_ports.declare_world(out.world_decl)
        b._maybe_finish_wait()

        seen_supply_r9 = False
        seen_boss_r10 = False
        seen_supply_p2r7 = False
        for _ in range(_DEF_STEPS):
            if b.done:
                break
            screen = b.screen_identity()
            node = b.gs.node.value
            if screen == SCREEN_SUPPLY and node is not None:
                if (node.plane, node.round_num) == (1, 9):
                    seen_supply_r9 = True
                    assert len(b.gs.supply.value.options) == 3, \
                        'M18 三选一(插入补给走现役通道)'
                if (node.plane, node.round_num) == (2, 7):
                    seen_supply_p2r7 = True
            if screen == SCREEN_BOSS_BRIEFING and node is not None \
                    and (node.plane, node.round_num) == (1, 10):
                seen_boss_r10 = True
            _drive_step(b, 61)
        assert seen_supply_r9, 'P1 r9 = 插入补给屏'
        assert seen_boss_r10, 'P1 r10 = boss 简报'
        assert seen_supply_p2r7, 'P2 r7 = 插入补给屏'
        assert b.done, '局终(推进超 18)'
        assert DISCLOSURE_P3_UNOBSERVED in b.disclosures
        assert DECL_SCREEN_DRIFT not in b.disclosures, \
            b.disclosures.get(DECL_SCREEN_DRIFT)
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (2, 8), \
            '修饰局真实末节点 = P2 r8(18 节点)'
    finally:
        uninstall_backend()


def test_lock5_sim_modified_supply_income_keeps_streak() -> None:
    """插入补给轮首收入走 supply 分支:连胜不动(连胜转移在战斗结算后,
    补给轮无结算)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_invest_env_param,
    )
    from sr_od.application.currency_war.sim import cw_sim_ports
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SCREEN_BRIEFING,
        SCREEN_SUPPLY,
        uninstall_backend,
    )

    b = _start_game(env_present=True, seed=61)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b.gs.observe(b.gs.invest_env_opts,
                     ('头彩', '人身意外险', '轮岗'),
                     evidence='sim:synthesized', sig=_SIG_OBS)
        out = report_action_pick_invest_env_param(
            b.gs, SimpleNamespace(idx=1), _logic_sig('Test'))
        cw_sim_ports.declare_world(out.world_decl)
        b._maybe_finish_wait()
        # 快进到 P1 r8 reward 节点窗(先行 battle r3/r4 已建连胜);
        # r8 奖励轮出战结算后推进进 r9 插入补给窗。
        for _ in range(_DEF_STEPS):
            node = b.gs.node.value
            if b.done or (node is not None
                          and (node.plane, node.round_num) == (1, 8)):
                break
            _drive_step(b, 61)
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (1, 8)
        _drive_step(b, 61)   # 奖励轮出战 → 结算页(连胜不动,奖励轮非战斗类)
        _drive_step(b, 61)   # settle_confirm → 推进进 r9 插入补给窗
        assert b.screen_identity() == SCREEN_SUPPLY
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (1, 9)
        streak_at_supply = int(b.gs.streak.value or 0)
        assert streak_at_supply >= 1, '前置非零连胜已建立(r3/r4 战斗轮)'
        _drive_step(b, 61)   # 补给选卡 + supply_confirm → r10
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (1, 10)
        assert int(b.gs.streak.value or 0) == streak_at_supply, \
            '补给轮连胜不动(收入 supply 分支/连胜转移战斗结算后)'
    finally:
        uninstall_backend()


def test_lock8_sim_default_game_regression() -> None:
    """默认局回归:无环境局全链一次,局终轮次 = 现役基线(P2 r7,16 节点,
    eff=17 局终),零 DECL_SCREEN_DRIFT(默认环境零修饰行为不变)。"""
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        DECL_SCREEN_DRIFT,
        DISCLOSURE_P3_UNOBSERVED,
        SCREEN_BRIEFING,
        uninstall_backend,
    )

    b = _start_game(env_present=False, seed=61)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        assert b.gs.node_seq_by_plane.value is None
        for _ in range(_DEF_STEPS):
            if b.done:
                break
            _drive_step(b, 61)
        assert b.done
        assert DISCLOSURE_P3_UNOBSERVED in b.disclosures, 'P2 末局终(p3_unobserved)'
        assert DECL_SCREEN_DRIFT not in b.disclosures
        assert (b.gs.node.value.plane, b.gs.node.value.round_num) == (2, 7), \
            '默认局末节点 = P2 r7(现役基线轮次)'
    finally:
        uninstall_backend()
