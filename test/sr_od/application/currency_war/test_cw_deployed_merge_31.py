""" 容器合并(DeployedView)落地锁面。

锁三块(design details/deployed-merge.md 验收判据):
- 快照旧档迁移等价:schema 1 紧凑行域档(front_row/back_row 两键、
  Unit dict 自带 slot 信息位)→ restore 单次转换落 deployed,槽位
  语义等价(按槽位落位,缺席/越界顺延兜底);新档两键均不现;
- 单写写序:换排/替换/空槽上场各为**单次** deployed 写(一次写 =
  一次完整语义变更,无跨字段中间态;写序经容器写口记录逐条断言);
- 槽位语义对拍:视图 ↔ 定长 10 下标工作表两桥(deployed_indexed_
  of_view / deployed_view_of_indexed)往返等价(后排容量 6 内),
  紧缩行序顺延落位(deployed_view_sequential)与旧紧凑行域
  「顺序即占位」口径对拍。
"""

from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
    report_action_sell_deployed_param,
    report_action_swap_deploy_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BENCH_CAPACITY_DEFAULT,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    deployed_indexed_of_view,
    deployed_rows_of_view,
    deployed_view_of_indexed,
    deployed_view_sequential,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
    CwActionSellDeployedParam,
    CwActionSwapDeployParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_SIG = ChannelSig(family='logic_action', actor='MandateV1Strategy',
                  mode='compute')


def _u(cid: str, star: int = 1, equips: list[str] | None = None) -> Unit:
    return Unit(char_id=cid, star=star, equips=list(equips or []))


def _gs_with(view: DeployedView, bench: list[BenchSlot] | None = None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = list(bench or []) + [BenchSlot(kind='empty')] * (
        BENCH_CAPACITY_DEFAULT - len(bench or []))
    gs.observe(gs.bench, BenchView(slots=slots,
                                   capacity=BENCH_CAPACITY_DEFAULT),
               sig=_SIG_OBS)
    gs.observe(gs.deployed, view, sig=_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    return gs


_ORIG_WRITES = (GameState.write_logic, GameState.write_logic_rand,
                GameState.observe)


class _WriteRecorder:
    """容器写口记录器(单写写序断言面:写时刻按「target 即该名当前
    Field 实例」解析字段名——Field 帧替换语义下写后实例即换,身份表
    只能在写时刻对位;logic/logic_rand/observe 三写口全记)。"""

    def __init__(self, gs: GameState) -> None:
        self.gs = gs
        self.rows: list[str] = []   # 字段名序列(写序)

    def __enter__(self) -> '_WriteRecorder':
        rec = self

        def _wrap(orig):
            def _w(s, target, value, **kw):
                name = next((n for n in dir(s)
                             if getattr(s, n, None) is target), '?')
                rec.rows.append(name)
                return orig(s, target, value, **kw)
            return _w

        GameState.write_logic = _wrap(_ORIG_WRITES[0])
        GameState.write_logic_rand = _wrap(_ORIG_WRITES[1])
        GameState.observe = _wrap(_ORIG_WRITES[2])
        return self

    def __exit__(self, *exc) -> None:
        (GameState.write_logic, GameState.write_logic_rand,
         GameState.observe) = _ORIG_WRITES

    def count(self, field_name: str) -> int:
        """指定字段的写次数。"""
        return sum(1 for n in self.rows if n == field_name)


# ============================================================ 快照旧档迁移等价


def test_restore_migrates_schema1_rows_snapshot_by_slot_bits() -> None:
    """旧档迁移主锁:schema 1 行域档 → deployed 视图按 slot 信息位
    等价落位(前排槽 4 → front_slots[3];后排槽 1 → back_slots[0]);
    行键消费后摘除,restore 幂等可重放。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        restore_state_snapshot,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    snap = {'values': {
        'front_row': [{'char_id': '丙', 'star': 2, 'equips': ['轮滑鞋'],
                       'slot': 4}],
        'back_row': [{'char_id': '丁', 'star': 1, 'equips': [],
                      'slot': 1}],
    }, 'prov': {}}

    restore_state_snapshot(gs, snap)

    view = gs.deployed.value
    assert [u.char_id if u else None for u in view.front_slots] \
        == [None, None, None, '丙'], '槽位语义等价(前排槽 4 → 下标 3)'
    assert [u.char_id if u else None for u in view.back_slots][:2] \
        == ['丁', None], '后排槽 1 → 下标 0'
    assert view.front_slots[3].equips == ['轮滑鞋'], '装备随单位重建'
    # 重放幂等(转换不破坏原 snap:values 拷贝单次转换)
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs2, snap)
    assert gs2.deployed.value == view


def test_restore_migrates_missing_slot_bits_sequential_fallback() -> None:
    """迁移兜底腿:slot 信息位缺席(0)按占用序顺延;越界(>cap)
    同兜底(旧 deployed_rows_to_indexed 兼容口径同向)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        restore_state_snapshot,
    )
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs, {'values': {
        'front_row': [{'char_id': '甲', 'star': 1, 'equips': [], 'slot': 0},
                      {'char_id': '乙', 'star': 1, 'equips': [], 'slot': 99}],
        'back_row': [],
    }, 'prov': {}})
    assert [u.char_id if u else None for u in gs.deployed.value.front_slots] \
        == ['甲', '乙', None, None], '缺席/越界顺延落位'


def test_new_schema_snapshot_round_trip_no_legacy_keys() -> None:
    """新档往返:schema 2 快照只现 deployed 键(front_row/back_row
    均不现),往返视图逐位等价(含空槽显式 None)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        restore_state_snapshot,
    )
    gs = _gs_with(DeployedView(
        front_slots=[_u('甲'), None, _u('乙'), None],
        back_slots=[None, _u('丙'), None, None, None, None]))
    snap = gs.full_state_snapshot()
    assert 'deployed' in snap['values']
    assert 'front_row' not in snap['values'] \
        and 'back_row' not in snap['values'], '新档行键不现'

    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    restore_state_snapshot(gs2, snap)
    assert gs2.deployed.value == gs.deployed.value, '往返逐位等价'


# ============================================================ 单写写序(一次写 = 一次完整语义变更)


def test_deploy_move_writes_deployed_exactly_once() -> None:
    """空槽上场 = 单次 deployed 写(合卷契约):写序只含
    bench 摘槽写 + deployed 单写,无姊妹行域中间态。"""
    gs = _gs_with(
        DeployedView(front_slots=[None] * 4, back_slots=[None] * 6),
        bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    with _WriteRecorder(gs) as rec:
        report_action_deploy_move_param(
            gs, CwActionDeployMoveParam(bench_idx=0, to_row='back',
                                        to_slot=3, faction=''),
            _SIG)
    assert rec.count('deployed') == 1, '空槽上场恰一次 deployed 写'
    assert gs.deployed.value.back_slots[2].char_id == '甲'


def test_deploy_move_swap_occupied_target_single_write() -> None:
    """替换(目标槽有人 = 交换)= 仍单次 deployed 写:整视图整值替换,
    被占位者回源 bench 槽(bench 写独立,deployed 无第二写)。"""
    gs = _gs_with(
        DeployedView(front_slots=[_u('乙'), None, None, None],
                     back_slots=[None] * 6),
        bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    with _WriteRecorder(gs) as rec:
        report_action_deploy_move_param(
            gs, CwActionDeployMoveParam(bench_idx=0, to_row='front',
                                        to_slot=1, faction=''),
            _SIG)
    assert rec.count('deployed') == 1
    assert gs.deployed.value.front_slots[0].char_id == '甲'
    assert gs.bench.value.slots[0].unit.char_id == '乙', '被占位者回源'


def test_sell_and_swap_deployed_single_write() -> None:
    """卖场上/换位 = 各恰一次 deployed 写(合卷契约族全查)。"""
    gs = _gs_with(
        DeployedView(front_slots=[_u('乙'), None, None, None],
                     back_slots=[_u('丙'), None, None, None, None, None]),
        bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    with _WriteRecorder(gs) as rec:
        report_action_sell_deployed_param(
            gs, CwActionSellDeployedParam(deployed_idx=0), _SIG)
    assert rec.count('deployed') == 1
    assert gs.deployed.value.front_slots[0] is None

    with _WriteRecorder(gs) as rec2:
        report_action_swap_deploy_param(
            gs, CwActionSwapDeployParam(deployed_idx=4, bench_idx=0), _SIG)
    assert rec2.count('deployed') == 1
    assert gs.deployed.value.back_slots[0].char_id == '甲', '上场者落槽'


def test_row_reposition_observed_write_is_single() -> None:
    """换排/重排观察写 = 单次 deployed 写(director 观察合一写;同子表
    纯重排吸收不产生额外 deployed 写)。"""
    gs = _gs_with(DeployedView(
        front_slots=[_u('佩佩'), _u('黑塔'), _u('万敌'), None],
        back_slots=[None] * 6))
    # 换排:佩佩 前→后
    with _WriteRecorder(gs) as rec:
        gs.observe(gs.deployed, DeployedView(
            front_slots=[None, _u('黑塔'), _u('万敌'), None],
            back_slots=[_u('佩佩'), None, None, None, None, None]),
            sig=_SIG_OBS)
    assert rec.count('deployed') == 1
    # 同子表纯重排:观察 = 采新覆盖(observe 源不走 logic 吸收路径,
    # 纯重排台账行为由 test_cw_board_derived_and_reorder 行域族锁定),
    # 仍单写。
    with _WriteRecorder(gs) as rec2:
        gs.observe(gs.deployed, DeployedView(
            front_slots=[_u('万敌'), _u('黑塔'), None, None],
            back_slots=[_u('佩佩'), None, None, None, None, None]),
            sig=_SIG_OBS)
    assert rec2.count('deployed') == 1


# ============================================================ 槽位语义对拍(视图 ↔ 工作表桥)


def test_indexed_bridge_round_trip_within_back_capacity() -> None:
    """两桥往返等价:视图 → 定长 10 表 → 视图(后排容量 6 内逐位
    等价;7-9 扩展格截断 = 旧 tracked 表硬上限语义,3.2 续辖)。"""
    view = DeployedView(
        front_slots=[_u('甲'), None, _u('乙'), None],
        back_slots=[None, _u('丙'), None, None, _u('丁'), None,
                    _u('越界七格')])   # 后排第 7 格(超出 6)
    dep = deployed_indexed_of_view(view)
    assert len(dep) == 10, '定长 10 工作表'
    assert dep[0].char_id == '甲' and dep[2].char_id == '乙'
    assert dep[5].char_id == '丙' and dep[8].char_id == '丁'
    assert dep[9] is None
    back2 = deployed_view_of_indexed(dep, view)
    assert back2.front_slots == view.front_slots
    assert back2.back_slots[:6] == view.back_slots[:6]
    assert back2.back_slots[6:] == [_u('越界七格')], \
        '7-9 扩展格继承原视图(容量改写不丢扩展格)'


def test_sequential_placement_matches_compact_row_semantics() -> None:
    """紧缩行序顺延落位 = 旧紧凑行域「顺序即占位」口径:第 k 个单位
    落槽 k;紧缩行读回(deployed_rows_of_view)保序往返。"""
    view = deployed_view_sequential(
        [_u('甲'), _u('乙')], [_u('丙'), _u('丁')], back_capacity=6)
    assert [u.char_id if u else None for u in view.front_slots] \
        == ['甲', '乙', None, None]
    assert [u.char_id if u else None for u in view.back_slots] \
        == ['丙', '丁', None, None, None, None]
    front, back = deployed_rows_of_view(view)
    assert [u.char_id for u in front] == ['甲', '乙']
    assert [u.char_id for u in back] == ['丙', '丁'], '紧缩行保序'


def test_deployed_field_replacement_inherits_capacity() -> None:
    """容量变化 = 整视图结构性写:seed 底座后排容量 6;7-9 扩展格由
    语义写端显式扩容(工作副本桥 orig 参继承),禁静默截断。"""
    view = deployed_view_sequential([], [_u('甲')] * 7, back_capacity=7)
    assert len(view.back_slots) == 7, '7 格局显式扩容'
    dep = deployed_indexed_of_view(view)
    assert [d.char_id for d in dep[4:10]] == ['甲'] * 6, \
        '动作坐标系 10 槽内:后排 1-6 格'
    rebuilt = deployed_view_of_indexed(dep, view)
    assert rebuilt.back_slots == view.back_slots, \
        '桥继承 orig 容量(7 格不截断回 6)'


def test_unit_has_no_slot_information_bit() -> None:
    """信息位退役直锁:Unit 数据类无 slot 字段(位置 = 载体下标纯派生;
    快照序列化同样不出现该键)。"""
    assert not any(f.name == 'slot' for f in dataclasses.fields(Unit))
    gs = _gs_with(DeployedView(front_slots=[_u('甲'), None, None, None],
                               back_slots=[None] * 6))
    snap = gs.full_state_snapshot()
    front_raw = snap['values']['deployed']['front_slots']
    assert front_raw[0] == {'char_id': '甲', 'star': 1, 'equips': []}, \
        '序列化键集 = 身份/星级/装备(槽位不入 Unit)'


# ============================================================ 评审修复批(需修-1 / 建议-4 / 建议-5)


def test_board_rewrite_clear_then_front_deploy_no_crash() -> None:
    """清盘 → 再买 → 前排部署不崩(需修-1 交互锁):EffectLedgerBridge
    全场出售清空后视图 = 规范形空视图(front_slots 定长 4),后续
    deploy_move 前排直址落位不 IndexError;清盘写本身保持单写。

    测试卫生:未锚定清盘走 write_logic_rand,下方 bench 再观察覆盖
    异值 → 一行 logic_rand_outcome 入进程级缺陷缓冲(预期内,非安灯)
    ——用例末尾 consume_defect_sink 排水,防跨用例顺序依赖红。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        apply_board_rewrite,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_EFFECTS,
    )
    gs = _gs_with(
        DeployedView(front_slots=[_u('银枝'), None, None, None],
                     back_slots=[_u('刃'), None, None, None, None, None]),
        bench=[BenchSlot(kind='unit', unit=_u('停云'))])

    report = apply_board_rewrite(gs, STRATEGY_EFFECTS['人力重组'])
    assert report is not None and 'deployed' in report.cleared_fields

    view = gs.deployed.value
    assert len(view.front_slots) == 4, '清盘后 front_slots 恒定长 4(规范形不变量)'
    assert all(u is None for u in view.front_slots)
    assert all(u is None for u in view.back_slots), '两排全空(语义清盘)'

    # 清盘 → 再买(落席)→ 前排部署:不崩 + 落位正确。
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='unit', unit=_u('甲'))]
        + [BenchSlot(kind='empty')] * 8,
        capacity=BENCH_CAPACITY_DEFAULT), sig=_SIG_OBS)
    report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front',
                                    to_slot=4, faction=''),
        _SIG)
    assert gs.deployed.value.front_slots[3].char_id == '甲', \
        '前排 4 号直址落位(清盘后规范形视图上不崩)'
    consume_defect_sink()   # 排水:logic_rand_outcome 行不跨用例泄漏


def test_deploy_move_back_slot8_with_nine_layout_applies_and_extends() -> None:
    """偏差③直锁:back_layout=9 局 to_slot=8 applied + 视图扩容到 8——
    动态容量布局真值辖载荷校验(旧定长表结构性拒绝的表示缺陷消失);
    同载荷在默认 6 档仍拒绝(布局真值辖域互不越界)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_deploy_move_param as _dep,
    )
    # 9 格局:to_slot=8 落位 + 视图随落位扩容
    gs = _gs_with(DeployedView(front_slots=[None] * 4,
                               back_slots=[None] * 6),
                  bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    gs.observe(gs.back_layout, 9, sig=_SIG_OBS)
    out = _dep(gs, CwActionDeployMoveParam(bench_idx=0, to_row='back',
                                           to_slot=8, faction=''),
               _SIG)
    assert out.applied, '9 格局 to_slot=8 在容量内(旧定长表拒绝 = 表示缺陷)'
    assert len(gs.deployed.value.back_slots) == 8, '视图随落位扩容'
    assert gs.deployed.value.back_slots[7].char_id == '甲'
    # 对照:默认 6 档同载荷拒绝(未观察 back_layout = 6 基线)
    gs6 = _gs_with(DeployedView(front_slots=[None] * 4,
                                back_slots=[None] * 6),
                   bench=[BenchSlot(kind='unit', unit=_u('甲'))])
    out6 = _dep(gs6, CwActionDeployMoveParam(bench_idx=0, to_row='back',
                                             to_slot=8, faction=''),
                _SIG)
    assert not out6.applied, '6 档 to_slot=8 越容量 = 陈旧载荷零写'


def test_deployed_view_of_hits_back_bounds_and_extension() -> None:
    """观察命中构造的越界边界(建议-5):后排命中越提示容量但在布局
    值域 {6..9} 内 → 扩容落位;超上界 9 或 <1 → 丢弃留证不崩。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        deployed_view_of_hits,
    )
    view = deployed_view_of_hits(
        [], [(8, _u('甲')), (3, _u('乙'))], back_capacity=6)
    assert len(view.back_slots) == 8, '合法命中(≤9)越提示 6 → 扩容'
    assert view.back_slots[7].char_id == '甲'
    assert view.back_slots[2].char_id == '乙'

    view2 = deployed_view_of_hits(
        [], [(10, _u('越界')), (0, _u('零位'))], back_capacity=9)
    assert all(u is None for u in view2.back_slots), \
        '>布局上界 9 / <1 → 丢弃(读链漂移留证,不扩容不落位)'
    assert len(view2.back_slots) == 9, '容量不被漂移命中撑大'
