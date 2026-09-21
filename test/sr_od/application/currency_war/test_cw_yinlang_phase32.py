"""银狼闭环 3.2 落码批锁(R1 双腿 + 上阵变换窗 + 获得后果 + pick_invest 迁移)。

设计正本 = changes/2026-09-18-yinlang-exclusive-loop/design.md §2.0-§2.4/§2.1A
+ landing.md §3.2 完成判据。锁面:

- **腿型判定单源**(design §2.1①):装备域优先——破解芯片卡文含「弱化」
  仍判 equip(碰撞治理);longest-match(分身墨镜Max 不被短名截胡);相似
  归一唯一命中;多命中 = equip 且件名未解析(禁猜);关键词降级/unknown;
- **R1 升费变换窗三态**(design §2.1③):恰一枚 2★银狼LV.999 → 变换
  (write_logic);多枚 → 值不变翻来源 + 留证(planner_upgrade_ambiguous);
  零枚/未观察 → 不写 + 留证(planner_upgrade_source_missing);
- **装备腿**(design §2.1②):归一命中 → 入栏 + 获得后果链;未解析 →
  值不变翻来源 + 留证(planner_equip_name_unresolved);
- **幂等证据闩**(design §2.1①/对抗审③⑦):发射相仅意图遥测零容器写
  (重派发不重写);效果腿只在落地相应用一次;
- **上阵变换窗**(design §2.1A):3★银狼LV.999 落场写下一费用档 1★;
  其余单位恒等搬运零行为差;级联全员正常推演(费用档不同时存在,
  2026-09-18 定谳[口述·权威],分组键 (char_id, star) 无跨档歧义);
- **获得后果**(design §2.2):分身墨镜系送出银狼族进备战席 + 合成级联;
- **pick_invest 迁移**(design §2.3;gain-chain 3.2):分步上报——策略屏
  确认落地入 active_strategies + 效果分派(骇客专家:银狼 = bench 腿 +
  商店池申报行 + 随机改件采样链,翻来源域集不含 gold);portal 确认整支
  走获得链 gain_invest_env(active_env 写 + ENV_GIFTS 全量接入 + 欢愉
  契约 provisional 闩随 on_env_gained 迁 kernel),禁污染持卡面;表外
  环境效果面安静不写;
- **采样链 v0 池**(design §2.4):硬编码名单(4 费排除 Max 件口径的
  显式第二真相源)无 Max 件,种子可复现。

观察收口(等值静默/差异 logic_rand_outcome)= 基座锁
test_cw_game_state.py::test_write_logic_rand_and_observe_random_outcome,
不重复。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    deploy_move as deploy_move_mod,
)
from sr_od.application.currency_war.kernel.cw_action_report import (
    pick_invest as pick_invest_mod,
)
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.pick_invest import (
    EVIDENCE_OVERLAY_CLOSED,
    HACKER_MOD_POOL_V0,
    PICK_INVEST_EFFECTS,
    PICK_INVEST_SOURCE_PORTAL,
    PICK_INVEST_SOURCE_STRATEGY,
    roll_hacker_mod,
)
from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
    report_action_pick_planner_param,
)
from sr_od.application.currency_war.kernel.cw_events import (
    classify_planner_leg,
    normalize_equip_name,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
    CwActionPickInvestParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _lsig(actor: str = 'CwScreenYinLang') -> ChannelSig:
    return ChannelSig(family='logic_action', actor=actor, mode='compute')


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             front: list[Unit] | None = None,
             gold: int | None = 30,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供 None 边界腿)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit',
                           unit=Unit(char_id=c, star=s, slot=i + 1))
                 for i, (c, s) in enumerate(bench)]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if front is not None:
        gs.observe(gs.front_row, list(front), sig=_SIG_OBS)
        gs.observe(gs.back_row, [], sig=_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


# ============================================================ 腿型判定单源


def test_leg_classifier_equip_domain_first_and_longest_match() -> None:
    """腿型分类锁(design §2.1①):装备域优先——破解芯片卡文含「弱化」
    仍判 equip(决策关键词碰撞治理);longest-match;相似归一;多命中
    = equip+未解析;关键词降级;unknown。"""
    # 破解芯片 = 名字 + 含「弱化」效果文 → 装备域锚先行,不落 weaken。
    assert classify_planner_leg(
        '破解芯片 前台强度 30% 首次穿戴该装备时，会使多个节点变为弱化状'
        '态：敌人的生命上限降低10%，伤害降低 20%') == ('equip', '破解芯片')
    # longest-match:分身墨镜Max 不被短名「分身墨镜」截胡。
    assert classify_planner_leg(
        '分身墨镜Max 获得时解锁并获得2星专家【银狼】') == ('equip', '分身墨镜Max')
    assert classify_planner_leg(
        '分身墨镜 获得时解锁并获得1星专家【银狼】') == ('equip', '分身墨镜')
    # 相似归一:OCR 形变(基础名破坏)唯一命中。
    assert normalize_equip_name('破解 芯片!') == '破解芯片'
    assert classify_planner_leg('破解 芯片!') == ('equip', '破解芯片')
    # 多命中(锚未中,注册表多件同时高相似)= 装备信号成立、件名未解析
    # (禁猜——繁体形变使「数据拷贝仪」基础名锚不中,Max 与基础名同时高相似)。
    assert normalize_equip_name('数據拷贝仪Max') == ''
    assert classify_planner_leg('数據拷贝仪Max') == ('equip', '')
    # 关键词降级(锚/相似均未中才轮到)。
    assert classify_planner_leg(
        '提升费用至4费,变为1星银狼LV.999') == ('upgrade', '')
    assert classify_planner_leg('使后续节点【弱化】') == ('weaken', '')
    assert classify_planner_leg('随便什么不认识的卡') == ('unknown', '')
    assert classify_planner_leg('') == ('unknown', '')


# ============================================================ R1 升费变换窗三态


def test_upgrade_transform_exactly_one(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """恰一枚 2★银狼LV.999 → 工作副本变换(2★→1★,身份保持),write_logic。"""
    gs = _make_gs(bench=[('希儿', 1), ('银狼LV.999', 2)], equips=[])
    out = report_action_pick_planner_param(gs, None, leg_type='upgrade', norm_item='',
                                     sig=_lsig(), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert ('银狼LV.999', 1) in units, '变换为 1★(下一费用档,身份保持)'
    assert ('银狼LV.999', 2) not in units, '2★ 源已消费'
    assert ('希儿', 1) in units, '无关单位零差'
    assert gs.bench.source == 'logic', '确定面 write_logic'
    assert rows_sink.kinds() == [], '正常变换零留证行'


def test_upgrade_transform_multiple_flips_source(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """多枚(二次升费现实可发)→ 禁猜:值不变翻来源 + 留证自愈。"""
    gs = _make_gs(bench=[('银狼LV.999', 2), ('银狼LV.999', 2)], equips=[])
    seq_before = gs.write_seq
    out = report_action_pick_planner_param(gs, None, leg_type='upgrade', norm_item='',
                                     sig=_lsig(), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True
    stars = sorted(u.star for u in bench_units_of(gs)
                   if u.char_id == '银狼LV.999')
    assert stars == [2, 2], '值不变(触发单位不可辨,不写变换)'
    assert gs.bench.source == 'logic_rand', '受影响域值不变翻来源'
    assert gs.write_seq > seq_before, '翻来源占写序(遥测行)'
    assert rows_sink.kinds() == ['planner_upgrade_ambiguous'], '留证行 kind'


def test_upgrade_transform_zero_or_unobserved(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """零枚/未观察 → 不写 + 留证(真异常,照真失配响停,fail-closed 禁猜)。"""
    # 零枚(已观察但无 2★ 源)。
    gs = _make_gs(bench=[('银狼LV.999', 1)], equips=[])
    seq_before = gs.write_seq
    out = report_action_pick_planner_param(gs, None, leg_type='upgrade', norm_item='',
                                     sig=_lsig(), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is False and out.reason == 'upgrade_source_missing'
    assert gs.write_seq == seq_before, '零枚不写'
    assert rows_sink.kinds() == ['planner_upgrade_source_missing']
    # 未观察(三容器全 None)同态。
    gs2 = _make_gs()
    out2 = report_action_pick_planner_param(gs2, None, leg_type='upgrade', norm_item='',
                                      sig=_lsig(), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out2.applied is False and out2.reason == 'upgrade_source_unobserved'
    assert rows_sink.kinds() == ['planner_upgrade_source_missing',
                                 'planner_upgrade_source_missing']


def test_upgrade_cascade_lv999_normal_merge(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """涉 LV.999 级联合并正常推演锁(费用档不同时存在,2026-09-18 定谳
    [口述·权威]——分组键 (char_id, star) 无跨档歧义):变换出的 1★ 凑满
    同星组 → 与普通单位同语义升星(write_logic 逐级落行,零留证行)。"""
    gs = _make_gs(bench=[('银狼LV.999', 2), ('银狼LV.999', 1),
                         ('银狼LV.999', 1)], equips=[])
    out = report_action_pick_planner_param(gs, None, leg_type='upgrade', norm_item='',
                                     sig=_lsig(), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('银狼LV.999', 2)], '正常推演:3×1★ 合成 → 2★(普通单位同语义)'
    assert gs.bench.source == 'logic', '级联确定面 write_logic'
    assert rows_sink.kinds() == [], '正常推演零留证行'


# ============================================================ 装备腿与获得后果


def test_equip_leg_gain_with_consequence_chain(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """装备腿(design §2.1②/§2.2):入栏 + 获得后果链(分身墨镜送 1★银狼
    进备战席,与 2× 既有 1★ 银狼合成升星——效果同商店购买)。"""
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=['幸运星'])
    out = report_action_pick_planner_param(gs, None, leg_type='equip', norm_item='分身墨镜',
                                     sig=_lsig(), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True
    assert gs.equips.value == ['幸运星', '分身墨镜'], '装备入栏'
    assert gs.equips.source == 'logic'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('银狼', 2)], '送出 1★银狼与既有两枚合成 → 2★(购买同语义)'
    assert gs.bench.source == 'logic', '后果链确定面同源 write_logic'
    assert rows_sink.kinds() == [], '表内件零留证行'


def test_equip_leg_unresolved_flips_source(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """未解析(norm_item='')→ 禁猜名:equips 值不变翻来源 + 留证行。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['幸运星'])
    out = report_action_pick_planner_param(gs, None, leg_type='equip', norm_item='',
                                     sig=_lsig(), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True
    assert gs.equips.value == ['幸运星'], '值不变'
    assert gs.equips.source == 'logic_rand', '翻来源(观察差异收口自愈)'
    assert rows_sink.kinds() == ['planner_equip_name_unresolved']
    assert gs.bench.source == 'observation', '无后果链(不猜件名)'


def test_unknown_leg_evidenced_weaken_zero(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """unknown = 零记账 + 留证证未识别事实;weaken = 纯零记账。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=[])
    seq_before = gs.write_seq
    out = report_action_pick_planner_param(gs, None, leg_type='unknown', norm_item='',
                                     sig=_lsig(), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True and gs.write_seq == seq_before, '零容器写'
    assert rows_sink.kinds() == ['planner_leg_unknown']
    out2 = report_action_pick_planner_param(gs, None, leg_type='weaken', norm_item='',
                                      sig=_lsig(), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out2.applied is True and gs.write_seq == seq_before
    assert rows_sink.kinds() == ['planner_leg_unknown'], 'weaken 零留证'


# ============================================================ 幂等证据闩


def test_emission_phase_is_intent_only(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """证据闩锁(design §2.1①/对抗审③⑦):发射相(动作 op 自上报)仅登记
    意图遥测——容器零写;重派发重复发射仍零写(实例闩不设防面由证据
    绑定兜住),效果腿只在落地相应用一次。"""
    gs = _make_gs(bench=[('银狼LV.999', 2)], equips=['幸运星'])
    seq_before = gs.write_seq
    param = CwActionPickInvestParam(idx=1, source=PICK_INVEST_SOURCE_STRATEGY,
                                    norm_name='骇客专家:银狼')
    out1 = report_action_pick_planner_param(gs, param, _lsig('CwActionPickPlannerOp'),
                                            leg_type='upgrade')
    out2 = report_action_pick_planner_param(gs, param, _lsig('CwActionPickPlannerOp'),
                                            leg_type='upgrade')
    assert out1.applied and out2.applied, '受理(意图遥测)'
    assert gs.write_seq == seq_before, '发射相零容器写(重派发不重写)'
    assert gs.bench.value.slots[0].unit.star == 2, '2★ 源未被发射相触碰'
    out_inv = pick_invest_mod.report_action_pick_invest_param(gs, param, _lsig())
    out_inv2 = pick_invest_mod.report_action_pick_invest_param(gs, param, _lsig())
    assert out_inv.reason == 'intent_only' and out_inv2.reason == 'intent_only'
    assert gs.write_seq == seq_before, '投资发射相同锁'
    assert gs.active_strategies.value in (None, []), '持卡面未被发射相触碰'
    # 落地相才应用(对照)。
    out_land = pick_invest_mod.report_action_pick_invest_param(
        gs, param, _lsig('CwScreenInvestStrategy'),
        evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out_land.applied is True
    assert gs.active_strategies.value == ['骇客专家:银狼'], '落地相才入表'


# ============================================================ 上阵变换窗


def test_deploy_transform_window_3star_lv999(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """上阵变换窗(design §2.1A):3★银狼LV.999 拖上场 → 落场写下一费用档
    1★(非 3★ 原样)+ bench 摘除源;级联无组可合 → 零额外行。"""
    gs = _make_gs(bench=[('银狼LV.999', 3), ('希儿', 1)],
                  front=[Unit(char_id='黑塔', star=1, slot=1)], equips=[])
    out = report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=2,
                                    faction=''),
        _lsig('CwActionDeployMoveOp'))
    assert out.applied is True
    assert gs.front_row.value[1].char_id == '银狼LV.999', '落场'
    assert gs.front_row.value[1].star == 1, '变换窗:落场写 1★(下一费用档)'
    assert gs.front_row.source == 'logic'
    assert gs.lv999_cost_tier.value == 4, '上阵变费档行(3费档 3★ 上场 → 4)'
    bench_units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert ('希儿', 1) in bench_units and \
        ('银狼LV.999', 3) not in bench_units, 'bench 源已摘除'
    assert rows_sink.kinds() == [], '无组可合零留证'


def test_deploy_non_target_identity(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """非 (银狼LV.999,3★) 单位 = 恒等搬运零行为差(2★ LV.999 与 3★ 普通件)。"""
    for bench_units, idx in (
            ([('银狼LV.999', 2), ('希儿', 3)], 1),   # 3★ 非目标角色
            ([('银狼LV.999', 3), ('银狼LV.999', 2)], 1)):  # 2★ 目标名
        gs = _make_gs(bench=bench_units, front=[], equips=[])
        out = report_action_deploy_move_param(
            gs, CwActionDeployMoveParam(bench_idx=idx, to_row='back',
                                        to_slot=1, faction=''),
            _lsig('CwActionDeployMoveOp'))
        assert out.applied is True
        moved = gs.back_row.value[0]
        assert moved.star == bench_units[idx][1], \
            f'恒等搬运保持 {bench_units[idx]} 星级'
        assert gs.lv999_cost_tier.value is None, '非目标恒等搬运零档写'
        assert rows_sink.kinds() == []


def test_deploy_cascade_lv999_normal_merge(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """上阵级联正常推演锁(同 2026-09-18 定谳,普通单位同语义):变换出的
    1★ 落场与备战 2× 1★ 凑满全场同星组 → 合成载体 = 场上那张(场上优先,
    _merge_bench 语义),备战素材被消费腾槽,write_logic 逐级落行。"""
    gs = _make_gs(bench=[('银狼LV.999', 3), ('银狼LV.999', 1),
                         ('银狼LV.999', 1)], front=[], equips=[])
    out = report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=1,
                                    faction=''),
        _lsig('CwActionDeployMoveOp'))
    assert out.applied is True
    assert gs.front_row.value[0].star == 2, '级联正常推演:场上载体 1★→2★'
    assert gs.lv999_cost_tier.value == 4, '上阵变费档行(级联同批落)'
    bench_units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert bench_units == [], '备战素材被合成消费腾槽'
    assert gs.bench.source == 'logic' \
        and gs.front_row.source == 'logic', '受影响域逐级落行(write_logic)'
    assert rows_sink.kinds() == [], '正常推演零留证行'


# ============================================================ pick_invest 迁移


def test_invest_strategy_landing_hacker_wolf(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """策略屏确认落地(design §2.3 分步):①入 active_strategies(判重)
    + 遥测一行;②骇客专家:银狼效果链 = bench 银狼(merge 级联)+ 商店池
    遥测申报行(零容器写)+ 随机改件采样链(equips + 命中后果表三件则链内
    后果);翻来源域集不含 gold(对抗审⑪)。"""
    # 场景一:改件采样 = 破解芯片(表外件,链内无后果腿)。
    monkeypatch.setattr(random.Random, 'choice',
                        lambda self, seq: '破解芯片')
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=[])
    seq_before = gs.write_seq
    param = CwActionPickInvestParam(idx=0, source=PICK_INVEST_SOURCE_STRATEGY,
                                    norm_name='骇客专家:银狼')
    out = pick_invest_mod.report_action_pick_invest_param(
        gs, param, _lsig('CwScreenInvestStrategy'),
        evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True
    assert gs.write_seq > seq_before, '分步更新各占写序(多遥测行 = 预期)'
    assert gs.active_strategies.value == ['骇客专家:银狼'], '第一步入持卡面'
    assert gs.active_strategies.source == 'logic'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('银狼', 2)], 'bench 腿:送出 1★银狼与既有合成 → 2★'
    assert gs.equips.value == ['破解芯片'], '随机改件入栏(采样值)'
    assert gs.equips.source == 'logic_rand', '随机腿 logic_rand'
    assert gs.gold.source == 'observation' and gs.gold.value == 30, \
        'gold 不翻来源(改件链域集裁剪,无噪声行)'
    assert 'pick_invest_shop_pool_decl' in rows_sink.kinds(), '商店池腿遥测申报行'
    # 判重:同卡二次落地不重复入表(效果腿由证据闩保证一次;表面去重兜底)。
    out2 = pick_invest_mod.report_action_pick_invest_param(
        gs, param, _lsig('CwScreenInvestStrategy'),
        evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out2.applied is True
    assert gs.active_strategies.value == ['骇客专家:银狼'], '判重不重复入列'
    # 场景二:改件采样命中后果表三件(Max 件张力形状)→ 链内后果腿
    #(design §2.4 链序:装备入栏 → 送角色腿 → 级联)。
    monkeypatch.setattr(random.Random, 'choice',
                        lambda self, seq: '数据拷贝仪Max')
    gs3 = _make_gs(bench=[('希儿', 1)], equips=[])
    out3 = pick_invest_mod.report_action_pick_invest_param(
        gs3, param, _lsig('CwScreenInvestStrategy'),
        evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out3.applied is True
    assert gs3.equips.value == ['数据拷贝仪Max'], '改件入栏'
    units3 = [(u.char_id, u.star) for u in bench_units_of(gs3)]
    assert ('银狼LV.999', 1) in units3, '链内后果:改件送出 1★ 银狼LV.999'


def test_invest_portal_landing_no_card_pollution(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """portal 确认(欢愉契约)整支走获得链(gain-chain design §2.5):
    active_env 写(选择事实落地经 gain_invest_env)+ 银狼LV.999 1★ 入席
    递归(on_env_gained chars_immediate)+ 条件腿临时翻来源闩随枚举迁
    kernel(bench/equips 翻来源 + joy_contract_provisional 留证,kind
    不变);禁入 active_strategies(防 portal 卡污染持卡面)。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['幸运星'], gold=30)
    param = CwActionPickInvestParam(idx=1, source=PICK_INVEST_SOURCE_PORTAL,
                                    norm_name='欢愉契约')
    out = pick_invest_mod.report_action_pick_invest_param(
        gs, param, _lsig('CwScreenInvestEnv'),
        evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True and out.reason == 'gain_chain_applied'
    assert gs.active_strategies.value in (None, []), '双屏分流防污染锁'
    assert gs.active_env.value == '欢愉契约', '选择事实落地经获得链写'
    assert gs.active_env.source == 'logic', '确定性入口 write_logic'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert ('银狼LV.999', 1) in units, 'immediate 腿(chars_immediate 实证)'
    assert gs.bench.source == 'logic_rand', '条件腿临时闩翻来源(bench)'
    assert gs.equips.source == 'logic_rand' \
        and gs.equips.value == ['幸运星'], '条件腿临时闩翻来源(equips 值不变)'
    assert 'joy_contract_provisional' in rows_sink.kinds(), '披露键留证行'


def test_invest_portal_env_gifts_full_access(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """ENV_GIFTS 全量即时发放经落地相可用(gain-chain design §2.6-②:
    此前仅欢愉契约有容器写腿,现契约类 chars_immediate 全部经链生效;
    表外环境安静不写)。公司契约 = 翡翠/砂金 逐个 1★ 入席递归。"""
    gs = _make_gs(bench=[], equips=[])
    out = pick_invest_mod.report_action_pick_invest_param(
        gs, CwActionPickInvestParam(idx=0, source=PICK_INVEST_SOURCE_PORTAL,
                                    norm_name='公司契约'),
        _lsig('CwScreenInvestEnv'), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True and out.reason == 'gain_chain_applied'
    assert gs.active_env.value == '公司契约'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('翡翠', 1), ('砂金', 1)], 'chars_immediate 逐个入席'
    assert gs.bench.source == 'logic', '确定发放 write_logic'
    assert rows_sink.kinds() == [], '非欢愉契约零留证行'


def test_invest_unregistered_card_unchanged(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """未收录卡行为回归锁(3.2 后口径):策略屏未收录卡只走第一步(入表
    零效果);portal 表外环境 = active_env 选择事实写(经获得链,§2.6-①
    写时点迁移)+ 效果面安静不写(表外环境零入席,裁定④)。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['幸运星'])
    seq_before = gs.write_seq
    out = pick_invest_mod.report_action_pick_invest_param(
        gs, CwActionPickInvestParam(idx=0, source=PICK_INVEST_SOURCE_STRATEGY,
                                    norm_name='随便一张未收录卡'),
        _lsig('CwScreenInvestStrategy'), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out.applied is True
    assert gs.active_strategies.value == ['随便一张未收录卡'], \
        '未收录策略只走第一步'
    assert gs.write_seq == seq_before + 1, '恰一行遥测(持卡面),零效果腿'
    # portal 表外环境 = 选择事实写 + 零效果。
    gs2 = _make_gs(bench=[('希儿', 1)], equips=['幸运星'])
    seq2_before = gs2.write_seq
    out2 = pick_invest_mod.report_action_pick_invest_param(
        gs2, CwActionPickInvestParam(idx=0, source=PICK_INVEST_SOURCE_PORTAL,
                                     norm_name='随便一个未收录环境'),
        _lsig('CwScreenInvestEnv'), evidence=EVIDENCE_OVERLAY_CLOSED)
    assert out2.applied is True
    assert gs2.active_env.value == '随便一个未收录环境', \
        '选择事实落地写(表外环境同样经链注册)'
    assert gs2.write_seq == seq2_before + 1, '恰 active_env 一行,零效果腿'
    assert bench_units_of(gs2) and \
        [(u.char_id, u.star) for u in bench_units_of(gs2)] == [('希儿', 1)], \
        '表外环境零入席(安静不写)'
    assert gs2.active_strategies.value in (None, [])
    # 效果注册表收窄为单行(欢愉契约随 portal 支迁获得链;行 = 策略屏
    # 专用死键已删,gain-chain design §2.5)。
    assert set(PICK_INVEST_EFFECTS) == {'骇客专家:银狼'}


def test_hacker_mod_pool_v0_no_max() -> None:
    """采样链 v0 池形状锁(design §2.4):硬编码名单 = 4 费装备排除 Max 件
    的显式第二真相源——成员恒 5(专属 10 件的非 Max 件),零 Max 件,种子
    可复现(同种子同序列)。"""
    from sr_od.application.currency_war.data.cw_equipment_wear_rules_data import (
        ITEM_WEAR_GATES,
    )
    assert len(HACKER_MOD_POOL_V0) == 5
    assert all(not n.endswith('Max') for n in HACKER_MOD_POOL_V0), \
        '排除 Max 件(用户拍定临时口径)'
    assert all(n in ITEM_WEAR_GATES for n in HACKER_MOD_POOL_V0), \
        '成员 ⊆ 银狼专属 10 件名单'
    a = [roll_hacker_mod(random.Random(7)) for _ in range(20)]
    b = [roll_hacker_mod(random.Random(7)) for _ in range(20)]
    assert a == b and set(a) <= set(HACKER_MOD_POOL_V0), '种子可复现'


def test_grant_channel_consequence_anchor(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """好运令牌 grant_equip_item 渠道同纳后果链锚(design §2.2 全渠道):
    后果函数对表外件零写零行为(令牌推荐四件域恒表外 = 渠道零差);
    表内件直锁后果应用(送出 1★ 银狼LV.999 进备战席)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        apply_equip_acquire_consequence,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.equips, ['轮滑鞋'], sig=_SIG_OBS)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    seq_before = gs.write_seq
    r = apply_equip_acquire_consequence(gs, '轮滑鞋', frame='token')
    assert r.performed is False and r.detail == 'no_consequence_declared', \
        '表外件零写零行为(令牌渠道零差)'
    assert gs.write_seq == seq_before
    r2 = apply_equip_acquire_consequence(gs, '数据拷贝仪Max', frame='token')
    assert r2.performed is True and r2.granted == '银狼LV.999' \
        and r2.star == 1, '表内件后果应用(送出 1★ 银狼LV.999)'
    assert any(u.char_id == '银狼LV.999' and u.star == 1
               for u in bench_units_of(gs))


def test_deploy_move_module_uses_shared_cascade() -> None:
    """变换窗级联走共享级联体(单源消费;禁消费方手搓级联)。"""
    assert deploy_move_mod.merge_cascade_write.__module__ == \
        'sr_od.application.currency_war.kernel.cw_effect_inventory'
