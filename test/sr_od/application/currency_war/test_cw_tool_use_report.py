"""工具上报容器写锁(tool-gain-report 迭代;design.md §2.2/§2.5)。

设计依据 = docs/develop/sr_od/application/currency_war/changes/
2026-09-21-tool-gain-report/design.md(定稿):
- 逐工具写端锁:记账载体 = equips 合并单笔写(消耗移除与效果同笔,
  禁拆两笔);扳手两笔(equips 合并 + 行域清空);炉随机面
  write_logic_rand 采样链;
- 冶金炉采样锁:rng 注入同种子同产物(采样单一源 = 本模块;sim 私有
  动作腿随驱动反转退役,原对拍腿删除);采样命中后果表键集 → 采证行;
- 投影仪走链锁:经 ``gain_character``(回调触发 + 凑满三连合成);
  变异面(冶金炉/特权卡)不走链、不触发获得回调;
- 特权卡 char 腿 fail-closed;费用门防御;EQUIP_WRITE_SIDES 新词表
  (第五形 report:<函数名>)校验锁。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)

import random

import pytest

from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENTS,
)
from sr_od.application.currency_war.data.cw_equipment_wear_rules_data import (
    ITEM_WEAR_GATES,
)
from sr_od.application.currency_war.kernel import cw_gain_chain
from sr_od.application.currency_war.kernel.cw_action_report import tool_use
from sr_od.application.currency_war.kernel.cw_action_report.tool_use import (
    report_action_furnace_use_param,
    report_action_lucky_token_use_param,
    report_action_perfect_projector_use_param,
    report_action_precision_wrench_use_param,
    report_action_privilege_card_use_param,
    report_action_staff_projector_use_param,
    report_action_wrench_use_param,
)
from sr_od.application.currency_war.kernel.cw_affix_effects import (
    EQUIP_WRITE_SIDES,
    _validate_equip_write_sides,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionFurnaceUseParam,
    CwActionLuckyTokenUseParam,
    CwActionPerfectProjectorUseParam,
    CwActionPrecisionWrenchUseParam,
    CwActionPrivilegeCardUseParam,
    CwActionStaffProjectorUseParam,
    CwActionWrenchUseParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwToolUseReportSeed')

_COST3_CHAR = '艾丝妲'    # 注册表 1 费(费用门内;cw_chars 注册名)
_COST4_CHAR = '火花'      # 注册表 4 费(员工投影仪费用门外)


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='CwActionToolUseOp',
                      mode='compute')


def _record_char_calls(calls: list) :
    """on_character_gained 桩(记录触发;返回值契约 = 效果名元组,空集)。"""

    def _stub(gs, name, star, *, rand, sig):
        calls.append((name, star))
        return ()

    return _stub


def _record_equip_calls(calls: list):
    """on_equipment_gained 桩(记录触发;空集效果)。"""

    def _stub(gs, item, *, rand, sig):
        calls.append(item)
        return ()

    return _stub


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             front: list[Unit] | None = None,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供 bug 面零写腿)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit',
                           unit=Unit(char_id=c, star=s))
                 for i, (c, s) in enumerate(bench)]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if front is not None:
        gs.observe(gs.deployed, _dvs(list(front), []), sig=_SIG_OBS)
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


# ============================================================ 逐工具写端锁


def test_furnace_equip_merged_single_rand_write(rows_sink: _RowSink) -> None:
    """炉·拖装备:单笔 write_logic_rand 合并写——消耗移除(工具 ∧ 目标件)
    与采样替换同笔(write_seq 推进恰 1),禁拆两笔(design §2.2 表)。"""
    gs = _make_gs(equips=['冶金炉', '轮滑鞋'])
    seq0 = gs.write_seq
    pool = [n for n in EQUIPMENTS
            if EQUIPMENTS[n].category == '简易' and n != '轮滑鞋']
    out = report_action_furnace_use_param(
        gs, CwActionFurnaceUseParam(target_kind='equip',
                                    item_name='轮滑鞋'),
        _lsig(), rng=random.Random(7))
    assert out.applied is True
    assert gs.write_seq - seq0 == 1, '合并单笔(移除与替换同笔)'
    assert gs.equips.source == 'logic_rand', '随机面采样链写'
    assert gs.equips.value == [tool_use.furnace_mutate_sample(
        random.Random(7), '轮滑鞋')], '值 = 采样替换(工具与目标件已移除)'
    assert gs.equips.value[0] in pool, '替换件属同类别池(注册表现算)'


def test_furnace_char_legs_equips_rand_and_row_logic(
        rows_sink: _RowSink) -> None:
    """炉·拖角色:①equips 单笔 rand 合并写(移除工具 ∧ 移除穿戴 ∧ 追加各
    采样替换);②目标角色行域 write_logic(穿戴清空);两腿各落一行
    (design §2.2 表 rand/logic 分面)。"""
    gs = _make_gs(front=[Unit(char_id='丙', star=1,
                              equips=['轮滑鞋', '幸运星'])],
                  equips=['冶金炉', '折叠小刀'])
    seq0 = gs.write_seq
    out = report_action_furnace_use_param(
        gs, CwActionFurnaceUseParam(target_kind='char', row='front', slot=1),
        _lsig(), rng=random.Random(7))
    assert out.applied is True
    assert gs.write_seq - seq0 == 2, '两腿各一行(equips + 行域)'
    r_shoes = tool_use.furnace_mutate_sample(random.Random(7), '轮滑鞋')
    r_star = tool_use.furnace_mutate_sample(
        _rng_after(random.Random(7), '轮滑鞋'), '幸运星')
    assert gs.equips.source == 'logic_rand'
    assert gs.equips.value == ['折叠小刀', r_shoes, r_star], \
        '工具与穿戴件已移除、各采样替换追加'
    unit = gs.deployed.value.front_slots[0]
    assert unit.char_id == '丙' and unit.equips == [], '行域穿戴清空'
    assert gs.deployed.source == 'logic', '行域腿 = 确定面'


def test_furnace_char_leg_mixed_worn_keeps_out_of_scope(
        rows_sink: _RowSink) -> None:
    """炉·拖角色作用域白名单(口述·权威 2026-09-21):混合穿戴(简易 +
    非白名单)下白名单件采样替换、越白名单件保留原样 + 聚合留证行
    (kind=furnace_mutate_out_of_scope_kept);行域仍全拆清空(越白名单
    件是否随动作消失未采证,v0 保留 = 库存面)。"""
    gs = _make_gs(front=[Unit(char_id='丙', star=1,
                              equips=['轮滑鞋', '反重力皮靴·特权'])],
                  equips=['冶金炉', '折叠小刀'])
    out = report_action_furnace_use_param(
        gs, CwActionFurnaceUseParam(target_kind='char', row='front', slot=1),
        _lsig(), rng=random.Random(7))
    assert out.applied is True
    inv = gs.equips.value
    assert '反重力皮靴·特权' in inv, '越白名单穿戴件保留原样入库存'
    r_shoes = tool_use.furnace_mutate_sample(random.Random(7), '轮滑鞋')
    assert r_shoes in inv, '白名单穿戴件采样替换'
    assert '冶金炉' not in inv, '工具消耗移除'
    unit = gs.deployed.value.front_slots[0]
    assert unit.equips == [], '行域全拆清空'
    assert 'furnace_mutate_out_of_scope_kept' in rows_sink.kinds(), \
        '聚合留证行落证'


def _rng_after(rng: random.Random, item: str) -> random.Random:
    """复刻同种子流:先消耗 item 的一次采样,返回后续状态的 rng
    (等值期望从采样器单一来源现算,不手抄采样值)。"""
    tool_use.furnace_mutate_sample(rng, item)
    return rng


def test_furnace_sample_same_seed_reproducible() -> None:
    """采样锁:同种子同产物(可复现;rng 注入槽,同种子同序列)。
    样本限作用域白名单内(简易/进阶;白名单 = 口述·权威 2026-09-21)。
    原对拍腿(旧 sim 私有重掷实现)随 sim 私有动作腿退役删除,
    采样单一源 = 本模块。"""
    for item in ('轮滑鞋', '反重力皮靴'):
        pool = tool_use.furnace_mutate_pool(item)
        assert pool is not None and pool, f'{item} 池可用'
        for seed in (0, 1, 42):
            r1, r2 = random.Random(seed), random.Random(seed)
            first = [tool_use.furnace_mutate_sample(r1, item)
                     for _ in range(10)]
            second = [tool_use.furnace_mutate_sample(r2, item)
                      for _ in range(10)]
            assert first == second, f'{item} seed={seed} 同种子异序列'
    # 报告函数同种子复现:两次独立容器同 rng 种子 → 同终值。
    vals = []
    for _ in range(2):
        gs = _make_gs(equips=['冶金炉', '轮滑鞋'])
        report_action_furnace_use_param(
            gs, CwActionFurnaceUseParam(target_kind='equip',
                                        item_name='轮滑鞋'),
            _lsig(), rng=random.Random(42))
        vals.append(gs.equips.value)
    assert vals[0] == vals[1], '同种子报告结果可复现'


def test_furnace_pool_scope_whitelist() -> None:
    """作用域白名单锁(口述·权威 2026-09-21):冶金炉只作用简易/进阶——
    特殊/工具目标池 = None(不可作用);白名单池不含特殊/骇客/专属件。"""
    assert tool_use.furnace_mutate_pool('垃圾袋') is None, '特殊不可作用'
    assert tool_use.furnace_mutate_pool('冶金炉') is None, '工具不可作用'
    assert tool_use.furnace_mutate_pool('分身墨镜') is None, '专属不可作用'
    for name, e in EQUIPMENTS.items():
        if e.category not in ('简易', '进阶'):
            continue
        pool = tool_use.furnace_mutate_pool(name)
        assert pool is not None, f'{name} 白名单内池可用'
        cats = {EQUIPMENTS[n].category for n in pool}
        assert cats <= {'简易', '进阶'}, f'{name} 产物域越白名单'
        exclusives = set(ITEM_WEAR_GATES)
        assert not (set(pool) & exclusives), f'{name} 池含银狼专属件'
        from sr_od.application.currency_war.kernel.cw_effect_inventory import (
            EQUIP_ACQUIRE_CONSEQUENCES,
        )
        assert not (set(pool) & set(EQUIP_ACQUIRE_CONSEQUENCES)), \
            f'{name} 池含后果表成员(结构性不触发面)'


def test_furnace_equip_leg_target_out_of_scope_fail_closed(
        rows_sink: _RowSink) -> None:
    """炉·目标越白名单(特殊)= fail-closed 零写 + 留证(禁猜;容器含
    工具与目标件原样)。"""
    gs = _make_gs(equips=['冶金炉', '垃圾袋'])
    out = report_action_furnace_use_param(
        gs, CwActionFurnaceUseParam(target_kind='equip',
                                    item_name='垃圾袋'),
        _lsig(), rng=random.Random(7))
    assert out.applied is True
    assert gs.equips.value == ['冶金炉', '垃圾袋'], '越白名单零容器写'
    assert 'tool_bridge_zero_write' in rows_sink.kinds(), '留证行落证'


def test_privilege_equip_merged_single_logic_write(
        rows_sink: _RowSink) -> None:
    """特权卡·库存腿:单笔 write_logic 合并写 = 移除工具 ∧ 目标件名 →
    privilege_counterpart 替换同笔(design §2.2;禁拆两笔)。"""
    gs = _make_gs(equips=['特权赋予卡', '反重力皮靴', '幸运星'])
    seq0 = gs.write_seq
    out = report_action_privilege_card_use_param(
        gs, CwActionPrivilegeCardUseParam(target_kind='equip',
                                          item_name='反重力皮靴'),
        _lsig())
    assert out.applied is True
    assert gs.write_seq - seq0 == 1, '合并单笔'
    assert gs.equips.source == 'logic', '确定面'
    assert gs.equips.value == ['反重力皮靴·特权', '幸运星'], \
        '工具移除与变换同笔(映射桥 privilege_counterpart 同口径)'


def test_privilege_char_leg_fail_closed(rows_sink: _RowSink) -> None:
    """特权卡·拖角色腿 fail-closed(用户裁定 2026-09-21 按不能拖角色处理):
    零写 + 留证行(kind=tool_privilege_worn_unsupported)。"""
    gs = _make_gs(front=[Unit(char_id='丙', star=1,
                              equips=['反重力皮靴'])],
                  equips=['特权赋予卡'])
    seq0 = gs.write_seq
    out = report_action_privilege_card_use_param(
        gs, CwActionPrivilegeCardUseParam(target_kind='char',
                                          row='front', slot=1),
        _lsig())
    assert out.applied is True
    assert gs.write_seq == seq0, '零写'
    assert gs.equips.value == ['特权赋予卡'], '库存未被触碰'
    assert gs.deployed.value.front_slots[0].equips == ['反重力皮靴'], '穿戴未被触碰'
    assert rows_sink.kinds() == ['tool_privilege_worn_unsupported']


def test_wrench_returns_worn_and_consumes_tool(rows_sink: _RowSink) -> None:
    """扳手:两笔 write_logic——①equips 合并(移除工具 ∧ 追加全部穿戴件);
    ②行域穿戴清空(design §2.2 表;归属迁移非获得)。"""
    gs = _make_gs(front=[Unit(char_id='丙', star=1,
                              equips=['轮滑鞋', '幸运星'])],
                  equips=['拆装扳手'])
    seq0 = gs.write_seq
    out = report_action_wrench_use_param(
        gs, CwActionWrenchUseParam(row='front', slot=1), _lsig())
    assert out.applied is True
    assert gs.write_seq - seq0 == 2, '两笔(equips + 行域)'
    assert gs.equips.source == 'logic'
    assert sorted(gs.equips.value) == ['幸运星', '轮滑鞋'], \
        '工具已消耗、穿戴件全量回区'
    assert gs.deployed.value.front_slots[0].equips == [], '行域穿戴清空'


def test_precision_wrench_keeps_tool_in_inventory(rows_sink: _RowSink) -> None:
    """精密扳手:同扳手两笔 logic,但 equips 不移除工具(无限次不递减)。"""
    gs = _make_gs(front=[Unit(char_id='丙', star=1,
                              equips=['轮滑鞋'])],
                  equips=['精密拆装扳手'])
    out = report_action_precision_wrench_use_param(
        gs, CwActionPrecisionWrenchUseParam(row='front', slot=1), _lsig())
    assert out.applied is True
    assert gs.equips.value == ['精密拆装扳手', '轮滑鞋'], '工具不递减、回区照写'
    assert gs.deployed.value.front_slots[0].equips == []


# ============================================================ 投影仪走链锁


def test_staff_projector_walks_gain_chain_and_merges(
        monkeypatch, rows_sink: _RowSink) -> None:
    """员工投影仪走链锁:复制进席经 ``gain_character`` 统一时序——
    ``on_character_gained`` 回调触发(现役空集安静不写)+ 凑满三连合成
    (升星判断 = 1★×3 → 2★,复制触发三合一 = 口述·权威 2026-09-21);
    equips 消耗腿同落(工具 −1)。"""
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(cw_gain_chain, 'on_character_gained',
                        _record_char_calls(calls))
    gs = _make_gs(bench=[(_COST3_CHAR, 1), (_COST3_CHAR, 1)],
                  front=[Unit(char_id=_COST3_CHAR, star=1, equips=[])],
                  equips=['员工投影仪'])
    out = report_action_staff_projector_use_param(
        gs, CwActionStaffProjectorUseParam(row='front', slot=1), _lsig())
    assert out.applied is True
    assert calls == [(_COST3_CHAR, 1), (_COST3_CHAR, 2)], \
        '获得角色回调经链触发(升星产物重进也回调 = 链时序)'
    bench_units = [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
                   if s.kind == 'unit' and s.unit is not None]
    assert (_COST3_CHAR, 2) in bench_units, '凑满三连合成 2★(链升星判断)'
    assert gs.equips.value == [], '工具消耗移除(独立腿)'


def test_staff_projector_cost_gate_defense(rows_sink: _RowSink) -> None:
    """费用门防御纵深(发射位已辖,上报侧注册表现读前置查):>3 费目标 =
    零写 + 留证行(tool_bridge_zero_write),工具不移除。"""
    gs = _make_gs(front=[Unit(char_id=_COST4_CHAR, star=1, equips=[])],
                  equips=['员工投影仪'])
    seq0 = gs.write_seq
    out = report_action_staff_projector_use_param(
        gs, CwActionStaffProjectorUseParam(row='front', slot=1), _lsig())
    assert out.applied is True
    assert gs.write_seq == seq0, '超门零写'
    assert gs.equips.value == ['员工投影仪'], '工具未被消耗'
    kinds = rows_sink.kinds()
    assert kinds == ['tool_bridge_zero_write']
    assert 'cost_gate_over' in rows_sink.rows[0]['observed_evidence'], \
        'detail 区分因'


def test_perfect_projector_no_gate_walks_chain(monkeypatch,
                                               rows_sink: _RowSink) -> None:
    """完美投影仪:无费用门——>3 费目标照走获得链(复制落席)。"""
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(cw_gain_chain, 'on_character_gained',
                        _record_char_calls(calls))
    gs = _make_gs(bench=[], front=[Unit(char_id=_COST4_CHAR, star=1,
                                        equips=[])],
                  equips=['完美投影仪'])
    out = report_action_perfect_projector_use_param(
        gs, CwActionPerfectProjectorUseParam(row='front', slot=1), _lsig())
    assert out.applied is True
    assert calls == [(_COST4_CHAR, 1)], '无门走链(回调触发)'
    bench_units = [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
                   if s.kind == 'unit' and s.unit is not None]
    assert (_COST4_CHAR, 1) in bench_units, '复制入席'


# ============================================================ 令牌/目标缺失/桥零写


def test_lucky_token_zero_write_not_admitted(rows_sink: _RowSink) -> None:
    """好运令牌:零写 + 留证行(kind=tool_token_not_admitted 注记;发射位
    永不准入,写端随 R9 判据批,design §2.2)。"""
    gs = _make_gs(front=[Unit(char_id='丙', star=1, equips=[])],
                  equips=['好运令牌'])
    seq0 = gs.write_seq
    out = report_action_lucky_token_use_param(
        gs, CwActionLuckyTokenUseParam(row='front', slot=1), _lsig())
    assert out.applied is True
    assert gs.write_seq == seq0, '零写'
    assert rows_sink.kinds() == ['tool_token_not_admitted']


def test_target_unit_missing_zero_write_with_evidence(
        rows_sink: _RowSink) -> None:
    """目标单位缺失(行域未观察/漂移)= bug 面:char 模式各工具零写 +
    留证行(kind=tool_target_unit_missing,design §2.2;留证不停机)。"""
    gs = _make_gs(front=[Unit(char_id='丙', star=1, equips=[])],
                  equips=['拆装扳手'])
    seq0 = gs.write_seq
    params = [
        CwActionFurnaceUseParam(target_kind='char', row='front', slot=9),
        CwActionWrenchUseParam(row='front', slot=9),
        CwActionPrecisionWrenchUseParam(row='front', slot=9),
        CwActionStaffProjectorUseParam(row='front', slot=9),
        CwActionPerfectProjectorUseParam(row='front', slot=9),
    ]
    for p in params:
        fn = {CwActionFurnaceUseParam: report_action_furnace_use_param,
              CwActionWrenchUseParam: report_action_wrench_use_param,
              CwActionPrecisionWrenchUseParam:
                  report_action_precision_wrench_use_param,
              CwActionStaffProjectorUseParam:
                  report_action_staff_projector_use_param,
              CwActionPerfectProjectorUseParam:
                  report_action_perfect_projector_use_param}[type(p)]
        out = fn(gs, p, _lsig())   # type: ignore[arg-type]
        assert out.applied is True
    assert gs.write_seq == seq0, '全部零写(禁猜禁写)'
    assert rows_sink.kinds() == ['tool_target_unit_missing'] * len(params)


def test_bridge_zero_write_branches_evidenced(rows_sink: _RowSink) -> None:
    """桥零写分支透传(库存未观察/无此件):统一落证行
    (kind=tool_bridge_zero_write,detail 区分因,design §2.2)。"""
    gs_unobserved = _make_gs()   # equips 未观察
    out = report_action_privilege_card_use_param(
        gs_unobserved, CwActionPrivilegeCardUseParam(
            target_kind='equip', item_name='反重力皮靴'), _lsig())
    assert out.applied is True
    gs_missing = _make_gs(equips=['幸运星'])
    out2 = report_action_privilege_card_use_param(
        gs_missing, CwActionPrivilegeCardUseParam(
            target_kind='equip', item_name='反重力皮靴'), _lsig())
    assert out2.applied is True
    out3 = report_action_furnace_use_param(
        _make_gs(equips=['幸运星']),
        CwActionFurnaceUseParam(target_kind='equip', item_name='反重力皮靴'),
        _lsig(), rng=random.Random(1))
    assert out3.applied is True
    kinds = rows_sink.kinds()
    assert kinds == ['tool_bridge_zero_write'] * 3
    assert 'equips_unobserved' in rows_sink.rows[0]['observed_evidence']
    assert 'target_item_missing' in rows_sink.rows[1]['observed_evidence']
    assert 'target_item_missing' in rows_sink.rows[2]['observed_evidence']


def test_mutate_faces_do_not_fire_gain_callbacks(monkeypatch,
                                                 rows_sink: _RowSink) -> None:
    """变异面不走链锁(design §2.0):冶金炉/特权卡 = 原地替换数量不变,
    不触发获得回调(on_character_gained/on_equipment_gained 零调用);
    容器写照常发生(非零写)。"""
    char_calls: list = []
    equip_calls: list = []
    monkeypatch.setattr(cw_gain_chain, 'on_character_gained',
                        _record_char_calls(char_calls))
    monkeypatch.setattr(cw_gain_chain, 'on_equipment_gained',
                        _record_equip_calls(equip_calls))
    gs_furnace = _make_gs(equips=['冶金炉', '轮滑鞋'])
    report_action_furnace_use_param(
        gs_furnace, CwActionFurnaceUseParam(target_kind='equip',
                                            item_name='轮滑鞋'),
        _lsig(), rng=random.Random(3))
    gs_priv = _make_gs(equips=['特权赋予卡', '反重力皮靴'])
    report_action_privilege_card_use_param(
        gs_priv, CwActionPrivilegeCardUseParam(target_kind='equip',
                                               item_name='反重力皮靴'),
        _lsig())
    assert gs_furnace.equips.source == 'logic_rand', '炉容器写照常(rand 面)'
    assert gs_priv.equips.value == ['反重力皮靴·特权'], '特权卡容器写照常'
    assert char_calls == [] and equip_calls == [], '变异面零获得回调'


# ============================================================ 词表校验锁


def test_equip_write_sides_report_form_final_values() -> None:
    """EQUIP_WRITE_SIDES 新词表校验锁:工具七行逐行终值(design §2.3 表)
    + 校验器通过(report: 第五形目标须在 tool_use 在册,import 即炸面
    的直调复验)。"""
    assert EQUIP_WRITE_SIDES['冶金炉'] == \
        'report:report_action_furnace_use_param'
    assert EQUIP_WRITE_SIDES['员工投影仪'] == \
        'report:report_action_staff_projector_use_param'
    assert EQUIP_WRITE_SIDES['完美投影仪'] == \
        'report:report_action_perfect_projector_use_param'
    assert EQUIP_WRITE_SIDES['特权赋予卡'] == \
        'bridge:transform_equip_to_privilege', '库存腿桥继续消费'
    assert EQUIP_WRITE_SIDES['拆装扳手'] == \
        'report:report_action_wrench_use_param'
    assert EQUIP_WRITE_SIDES['精密拆装扳手'] == \
        'contribution:equip_wrench_duplicate_gold', '金面不变'
    assert EQUIP_WRITE_SIDES['好运令牌'] == 'bridge:grant_equip_item', \
        '维持 R9 挂账(不虚报已接线)'
    _validate_equip_write_sides()   # 词表封闭 + 落码目标在册


def test_equip_write_sides_report_form_rejects_unknown_target(
        monkeypatch) -> None:
    """report: 第五形校验封闭性:目标函数不在 tool_use 在册 = 构建校验炸
    (改名/删除即暴露,禁静默失联)。"""
    monkeypatch.setitem(EQUIP_WRITE_SIDES, '冶金炉',
                        'report:report_action_not_in_tool_use')
    with pytest.raises(ValueError, match='tool_use 不在册'):
        _validate_equip_write_sides()
