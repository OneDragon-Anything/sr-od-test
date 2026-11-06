"""CW 动作上报与记账链测试面(上报函数族 + 工具写端 + 归一 reason 序列化
+ 动作 op 发出即记账 + 合并采样步回调)。

五节归并自原五个主题文件(测试函数名全量保留,原文件已删):

1. 上报函数族命名规约完备测试(原 test_cw_action_report_contract.py):
   词表类 ``CwActionXxxParam`` 恰有同名上报函数
   ``report_action_<snake>_param``(kernel/cw_action_report 包,每动作
   一文件;工具族落 ``tool_use``,其余零写族落 ``zero_writes``;包级
   ``__getattr__`` 命名规约解析)。新增动作漏建上报函数/漏建文件 = 本测试红。
   声明面即命名规约本身,无分发表——分派只允许出现在实机 op 直调与
   sim/回放引擎入口。
2. 工具上报容器写测试(原 test_cw_tool_use_report.py):逐工具写端/冶金炉
   采样/投影仪走链/EQUIP_WRITE_SIDES 词表校验;
3. 动作行归一 reason 键序列化(原 test_cw_action_reason_serialization.py;
   提取键序单一源 = telemetry/schema.py ``ACTION_REASON_SOURCE_KEYS``,
   接入调用位 = ``serialize_action``;缺陷实证 = 2026-09-15 sim 批
   CwActionLevelUpParam 6978 行 / CwActionSellBenchParam 3729 行零 reason);
4. 动作 op「机械执行 + 发出即记账」(原 test_cw_action_emit_book.py;
   用户裁定:动作 op = 机械执行,动作层禁设一切判效与重试——落地判定归
   观察侧 reconcile 对账);
5. ``_merge_bench`` 步回调(原 test_cw_merge_step_callback.py):采样链
   逐步写的机械基础(生产消费面 = cw_action_report/collect_ore 与
   cw_effect_inventory 的 on_step 范式);合成规则本体由既有投影直测钉住,
   本节只校验回调机制。
"""
from __future__ import annotations

import random
import re
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

import sr_od.application.currency_war.operations.cw_op.cw_buy_card_action as buy_action_mod
from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENTS,
)
from sr_od.application.currency_war.data.cw_equipment_wear_rules_data import (
    ITEM_WEAR_GATES,
)
from sr_od.application.currency_war.kernel import cw_action_report as rpt
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
    ShopPayload,
    ShopSlot,
    Unit,
    consume_defect_sink,
    game_state_of,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    _merge_bench,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    CwActionBuyCardParam,
    CwActionFurnaceUseParam,
    CwActionLevelUpParam,
    CwActionLuckyTokenUseParam,
    CwActionPerfectProjectorUseParam,
    CwActionPrecisionWrenchUseParam,
    CwActionPrivilegeCardUseParam,
    CwActionSellBenchParam,
    CwActionStaffProjectorUseParam,
    CwActionWearEquipParam,
    CwActionWrenchUseParam,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op.cw_buy_card_action import (
    CwActionBuyCardOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopExecEnv,
    ShopVisitLedger,
)
from sr_od.application.currency_war.operations.cw_op.cw_wear_equip_action import (
    CwActionWearEquipOp,
)
from sr_od.application.currency_war.prep_actions import PrepExecEnv
from sr_od.application.currency_war.telemetry.schema import (
    serialize_action,
)

# ============================================================
# 1. 上报函数族命名规约完备测试
# ============================================================


def _snake(cls_name: str) -> str:
    core = cls_name[len('CwAction'):] if cls_name.startswith('CwAction') else cls_name
    if core.endswith('Param'):
        core = core[:-len('Param')]
    return re.sub(r'(?<!^)(?=[A-Z])', '_', core).lower()


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(工具七类上报升格容器写后,冒烟路径对空参/未观察
    容器会产生 tool_* 留证行;前清防他测残留、后清防本测外泄——全局缓冲
    被后续测试整池排水对账,残留行即假红)。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


def test_every_action_type_has_report_function():
    """每个词表动作类恰有一个 ``report_action_<snake>_param`` 可调用。"""
    missing = []
    for t in CW_ACTION_TYPES:
        fn = f'report_action_{_snake(t.__name__)}_param'
        if not callable(getattr(rpt, fn, None)):
            missing.append(f'{t.__name__} -> {fn}')
    assert not missing, f'漏建上报函数: {missing}'


@pytest.mark.parametrize('t', CW_ACTION_TYPES, ids=lambda t: t.__name__)
def test_report_function_accepts_param_and_sig(t, _isolate_defect_buffer):
    """逐类冒烟:上报函数以零写/拒绝路径可调用(不要求容器效果,
    只断言「函数在场且签名可走」——语义正确性归各域直测)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        GameState,
    )

    gs = GameState(schema_version=1)
    sig = ChannelSig(family='logic_action', actor='cw-report-lock',
                     mode='compute')
    fn = getattr(rpt, f'report_action_{_snake(t.__name__)}_param')
    # 构造最小 param:必填字段给哑值(仅为了走函数入口;写路径按域测试覆盖)
    import dataclasses

    from sr_od.application.currency_war.kernel.cw_vocab import ShopCard

    kwargs = {}
    for f in dataclasses.fields(t):
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            kwargs[f.name] = ShopCard(x=0) if f.name == 'card' else (
                0 if f.type == 'int' else '')
    param = t(**kwargs)
    if t.__name__ == 'CwActionPickInvestEnvParam':
        # 按 idx 取名契约(op-layer.md §1.1 观察标准化门):env 上报从容器
        # invest_env_opts 取标准名直传链,容器缺读 = 响亮失败——冒烟播种
        # 容器承载该路径(裸容器直调会被正当拒绝)。播种名 = 环境注册表
        # 真名(含半角冒号,兼覆盖链内归一幂等路径;ENV_GIFTS 仅条件分支,
        # 效果面安静零写)。
        gs.write_logic(gs.invest_env_opts, ['特邀专家:银狼'],
                       produced_by='test', sig=sig)
    outcome = fn(gs, param, sig)
    assert outcome is not None
    assert isinstance(outcome.applied, bool)


def test_report_pick_invest_env_container_miss_loud_failure():
    """env 上报「按 idx 取名」契约拒绝分支(op-layer.md §1.1;即时上报契约:
    选卡链发生时观察必然已完成,容器缺读/idx 越界 = 代码 bug = 响亮失败,
    异常上抛禁吞)。红 = 静默零写 noop 回潮 / 非法索引穿透。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        ChannelSig,
        GameState,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestEnvParam,
    )

    sig = ChannelSig(family='logic_action', actor='cw-report-lock',
                     mode='compute')
    fn = rpt.report_action_pick_invest_env_param
    # ① 容器缺读(None)
    with pytest.raises(ValueError):
        fn(GameState(schema_version=1), CwActionPickInvestEnvParam(idx=0), sig)
    # ② 容器空(读得空 = 同判缺读)
    gs_empty = GameState(schema_version=1)
    gs_empty.write_logic(gs_empty.invest_env_opts, [],
                         produced_by='test', sig=sig)
    with pytest.raises(ValueError):
        fn(gs_empty, CwActionPickInvestEnvParam(idx=0), sig)
    # ③ idx 越界(容器非空但 idx 出界)
    gs_seeded = GameState(schema_version=1)
    gs_seeded.write_logic(gs_seeded.invest_env_opts, ['特邀专家:银狼'],
                          produced_by='test', sig=sig)
    with pytest.raises(ValueError):
        fn(gs_seeded, CwActionPickInvestEnvParam(idx=3), sig)


# ============================================================
# 2. 工具上报容器写测试(逐工具写端 / 冶金炉采样 / 投影仪走链)
# ============================================================

_SIG_OBS = ChannelSig(family='obs', actor='CwToolUseReportSeed')

_COST3_CHAR = '艾丝妲'    # 注册表 1 费(费用门内;cw_chars 注册名)
_COST4_CHAR = '火花'      # 注册表 4 费(员工投影仪费用门外)


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='CwActionToolUseOp',
                      mode='compute')


def _record_char_calls(calls: list):
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
    """观测面按参组装(None = 保持未观察,供 bug 面零写分支)。"""
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


def test_furnace_char_branchs_equips_rand_and_row_logic(
        rows_sink: _RowSink) -> None:
    """炉·拖角色:①equips 单笔 rand 合并写(移除工具 ∧ 移除穿戴 ∧ 追加各
    采样替换);②目标角色行域 write_logic(穿戴清空);两条分支各落一行
    (design §2.2 表 rand/logic 分面)。"""
    gs = _make_gs(front=[Unit(char_id='丙', star=1,
                              equips=['轮滑鞋', '幸运星'])],
                  equips=['冶金炉', '折叠小刀'])
    seq0 = gs.write_seq
    out = report_action_furnace_use_param(
        gs, CwActionFurnaceUseParam(target_kind='char', row='front', slot=1),
        _lsig(), rng=random.Random(7))
    assert out.applied is True
    assert gs.write_seq - seq0 == 2, '两条分支各一行(equips + 行域)'
    r_shoes = tool_use.furnace_mutate_sample(random.Random(7), '轮滑鞋')
    r_star = tool_use.furnace_mutate_sample(
        _rng_after(random.Random(7), '轮滑鞋'), '幸运星')
    assert gs.equips.source == 'logic_rand'
    assert gs.equips.value == ['折叠小刀', r_shoes, r_star], \
        '工具与穿戴件已移除、各采样替换追加'
    unit = gs.deployed.value.front_slots[0]
    assert unit.char_id == '丙' and unit.equips == [], '行域穿戴清空'
    assert gs.deployed.source == 'logic', '行域分支 = 确定面'


def test_furnace_char_branch_mixed_worn_keeps_out_of_scope(
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
    """采样测试:同种子同产物(可复现;rng 注入槽,同种子同序列)。
    样本限作用域白名单内(简易/进阶;白名单 = 口述·权威 2026-09-21)。
    原对拍分支(旧 sim 私有重掷实现)随 sim 私有动作分支退役删除,
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
    """作用域白名单测试(口述·权威 2026-09-21):冶金炉只作用简易/进阶——
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


def test_furnace_equip_branch_target_out_of_scope_fail_closed(
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
    """特权卡·库存分支:单笔 write_logic 合并写 = 移除工具 ∧ 目标件名 →
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
    """特权卡·拖角色入账分支 fail-closed(用户裁定 2026-09-21 按不能拖角色处理):
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


def test_staff_projector_walks_gain_chain_and_merges(
        monkeypatch, rows_sink: _RowSink) -> None:
    """员工投影仪走链测试:复制进席经 ``gain_character`` 统一时序——
    ``on_character_gained`` 回调触发(现役空集安静不写)+ 凑满三连合成
    (升星判断 = 1★×3 → 2★,复制触发三合一 = 口述·权威 2026-09-21);
    equips 消耗分支同落(工具 −1)。"""
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
    assert gs.equips.value == [], '工具消耗移除(独立分支)'


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
    """变异面不走链测试(design §2.0):冶金炉/特权卡 = 原地替换数量不变,
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


def test_equip_write_sides_report_form_final_values() -> None:
    """EQUIP_WRITE_SIDES 新词表校验测试:工具七行逐行终值(design §2.3 表)
    + 校验器通过(report: 第五形目标须在 tool_use 已登记,import 即炸面
    的直调复验)。"""
    assert EQUIP_WRITE_SIDES['冶金炉'] == \
        'report:report_action_furnace_use_param'
    assert EQUIP_WRITE_SIDES['员工投影仪'] == \
        'report:report_action_staff_projector_use_param'
    assert EQUIP_WRITE_SIDES['完美投影仪'] == \
        'report:report_action_perfect_projector_use_param'
    assert EQUIP_WRITE_SIDES['特权赋予卡'] == \
        'bridge:transform_equip_to_privilege', '库存分支桥继续消费'
    assert EQUIP_WRITE_SIDES['拆装扳手'] == \
        'report:report_action_wrench_use_param'
    assert EQUIP_WRITE_SIDES['精密拆装扳手'] == \
        'contribution:equip_wrench_duplicate_gold', '金面不变'
    assert EQUIP_WRITE_SIDES['好运令牌'] == 'bridge:grant_equip_item', \
        '维持 R9 待办(不虚报已接通)'
    _validate_equip_write_sides()   # 词表封闭 + 已写进代码的目标已登记


def test_equip_write_sides_report_form_rejects_unknown_target(
        monkeypatch) -> None:
    """report: 第五形校验封闭性:目标函数不在 tool_use 已登记 = 构建校验炸
    (改名/删除即暴露,禁静默失联)。"""
    monkeypatch.setitem(EQUIP_WRITE_SIDES, '冶金炉',
                        'report:report_action_not_in_tool_use')
    with pytest.raises(ValueError, match='tool_use 未登记'):
        _validate_equip_write_sides()


# ============================================================
# 3. 动作行归一 reason 键序列化
# ============================================================


def test_serialize_action_attaches_normalized_reason():
    """归一 reason 键矩阵(键序 = ACTION_REASON_SOURCE_KEYS 单一源)。"""
    # CwActionLevelUpParam:route_tag 载体显形(桥伴透传 m3_levelup_batch:<tag>)
    lv = CwActionLevelUpParam(cost=4, auth_basis='arm1',
                 route_tag='m3_levelup_batch:arm1')
    d = serialize_action(lv)
    assert d['reason'] == 'm3_levelup_batch:arm1'
    # CwActionSellBenchParam:自带 reason 字段(登记门键)优先
    sb = CwActionSellBenchParam(bench_idx=2, reason='funding_support')
    d2 = serialize_action(sb)
    assert d2['reason'] == 'funding_support'
    # auth_basis 兜底(键序次位;route_tag/reason 皆空时)
    lv2 = CwActionLevelUpParam(cost=4, auth_basis='must_spend')
    d3 = serialize_action(lv2)
    assert d3['reason'] == 'must_spend'
    # 全空 = 诚实缺省 ''
    d4 = serialize_action(CwActionLevelUpParam(cost=4))
    assert d4['reason'] == ''


# ============================================================
# 4. 动作 op「机械执行 + 发出即记账」
# ============================================================

_SIG = ChannelSig(family='logic_action', actor='CwScreenShop')


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    """测试卫生(3.2):主域种子经 observe 覆盖开局种子(logic_rand 通道)
    会产预期内 logic_rand_outcome 行入进程级缓冲——前后双清,防跨用例
    顺序依赖红(同 merge_31 批次事故教训)。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


def _buy_op_env(monkeypatch: pytest.MonkeyPatch,
                click_pts: list[Point] | None = None):
    """BuyCardOp 离线执行环境(零真实副作用,零读屏替身):容器在屏
    payload 槽1 = 花火;click_pts 可参(缺省槽1命中)。返回 (op, env,
    ledger, gs, clicks)。"""
    session = StrategySession()
    gs = game_state_of(session)
    card = ShopCard(x=50, slot=1, name='花火', faction='?', cost=3, star=1)
    gs.write_logic(
        gs.shop,
        ShopPayload(cards=[ShopSlot(kind='content', card=card)]
                    + [ShopSlot(kind='empty') for _ in range(4)],
                    refresh_probs={}),
        produced_by='test', sig=_SIG)
    ledger = ShopVisitLedger()
    clicks: list = []

    class _Ctrl:
        def click(self, pt) -> None:
            clicks.append(pt)

    class _Op:
        ctx = SimpleNamespace(controller=_Ctrl(),
                              cw_match=SimpleNamespace(session=session))

    env = ShopExecEnv(
        op=_Op(), match=SimpleNamespace(session=session), config=None,
        click_pts=click_pts if click_pts is not None else [Point(50, 50)],
        level_btn=None, refresh_btn=None,
        ledger=ledger, state=gs)
    monkeypatch.setattr(buy_action_mod.time, 'sleep', lambda s: None)
    return CwActionBuyCardOp(env.op.ctx, CwActionBuyCardParam(card=card), env=env), env, ledger, gs, clicks


def test_buy_card_emits_and_books_unconditionally(monkeypatch):
    """机械执行主测试:恒返回 True + 照常落账(账本/主域 bench 全落)——
    零判效的直接证据;落地真值归下一入口观察对账(静默不生效 →
    shop+gold 失配安灯停,按真 bug 修)。"""
    op, env, ledger, gs, clicks = _buy_op_env(monkeypatch)

    ok = op.run()

    assert ok.is_success, '发出即记账(round 成功态,零判效)'
    assert clicks, '机械点击已发出'
    assert ledger.total_buy == 1 and ledger.spend_executed == 3
    assert ledger.bought_names == ['花火']
    assert len(ledger.buy_purchases) == 1
    _view = gs.bench.value
    assert [(s.unit.char_id, s.unit.star)
            for s in (_view.slots if _view is not None else [])
            if s.kind == 'unit' and s.unit is not None] == [('花火', 1)]


def test_buy_card_missing_slot_point_fails_loudly(monkeypatch):
    """兜底坐标清除测试:槽号越界(点位缺失同出口)→ op 内守卫断言
    AssertionError(消息带 area 名),零点击零记账——禁兜底坐标静默点击
    (坐标单一真相源;terminal-fail-status 用户裁定:参数违法由 op 自判,
    action_ops.md §1 决策侧参数现算契约)。"""
    op, _env, ledger, _gs, clicks = _buy_op_env(monkeypatch, click_pts=[])

    with pytest.raises(AssertionError) as ei:
        op.run()

    assert '商店牌-' in str(ei.value), '错误信息带 area 名'
    assert clicks == [], '零点击(禁兜底坐标)'
    assert ledger.total_buy == 0, '零记账(动作未发出)'


def _buy_op_env_ex(monkeypatch: pytest.MonkeyPatch, *, slots: list,
                   action_card: ShopCard, click_pts: list[Point]):
    """B 层失败形态宿主:payload 槽阵列/动作牌/点表全可参,其余与
    _buy_op_env 同式(零真实副作用,零读屏)。返回 (op, ledger, clicks)。"""
    session = StrategySession()
    gs = game_state_of(session)
    gs.write_logic(
        gs.shop,
        ShopPayload(cards=list(slots), refresh_probs={}),
        produced_by='test', sig=_SIG)
    ledger = ShopVisitLedger()
    clicks: list = []

    class _Ctrl:
        def click(self, pt) -> None:
            clicks.append(pt)

    class _Op:
        ctx = SimpleNamespace(controller=_Ctrl())

    env = ShopExecEnv(
        op=_Op(), match=SimpleNamespace(session=session), config=None,
        click_pts=click_pts, level_btn=None, refresh_btn=None,
        ledger=ledger, state=gs)
    monkeypatch.setattr(buy_action_mod.time, 'sleep', lambda s: None)
    return (CwActionBuyCardOp(env.op.ctx, CwActionBuyCardParam(card=action_card),
                              env=env), ledger, clicks)


def test_buy_card_unknown_proposal_fails_without_slot_fallback(monkeypatch):
    """B 层·槽解析失败:payload 无此牌(身份同一性 ∧ (name,star) 双未
    命中)→ op 内守卫断言 AssertionError,信息含 slot_no=None 与双未命中
    形态——card.slot 旧档兜底已删,提案数据 bug 响亮暴露(静默错槽
    掩盖 bug 禁);零点击零记账。"""
    in_shop = ShopCard(x=60, slot=2, name='景元', faction='?', cost=4, star=2)
    ghost = ShopCard(x=50, slot=0, name='花火', faction='?', cost=3, star=1)
    op, ledger, clicks = _buy_op_env_ex(
        monkeypatch,
        slots=[ShopSlot(kind='content', card=in_shop)]
        + [ShopSlot(kind='empty') for _ in range(4)],
        action_card=ghost, click_pts=[Point(50, 50)] * 5)

    with pytest.raises(AssertionError) as ei:
        op.run()

    status = str(ei.value)
    assert 'slot_no=None' in status, '信息含 slot_no=None 形态'
    assert '身份未命中' in status, '信息含双未命中形态'
    assert clicks == [] and ledger.total_buy == 0, '零点击零记账(未发出事实)'
    assert ledger.spend_executed == 0 and ledger.bought_names == [], \
        '记账面零增量'


def test_buy_card_slot_out_of_range_fails(monkeypatch):
    """B 层·槽号越界:payload 槽号 7 对 5 点表 → op 内守卫断言
    AssertionError(信息含 slot 与点表长,槽号-点表不一致 = 建档/数据
    漂移上游暴露);零点击零记账。"""
    deep = ShopCard(x=70, slot=7, name='停云', faction='?', cost=2, star=1)
    op, ledger, clicks = _buy_op_env_ex(
        monkeypatch,
        slots=[ShopSlot(kind='empty') for _ in range(6)]
        + [ShopSlot(kind='content', card=deep)],
        action_card=deep, click_pts=[Point(50, 50)] * 5)

    with pytest.raises(AssertionError) as ei:
        op.run()

    status = str(ei.value)
    assert 'slot=7' in status and 'click_pts=5' in status, \
        '信息含槽号与点表长(槽号-点表不一致形态)'
    assert '槽号-点表不一致' in status
    assert clicks == [] and ledger.total_buy == 0, '零点击零记账(未发出事实)'


def _wear_env(monkeypatch: pytest.MonkeyPatch) -> tuple:
    """WearEquipOp 离线执行环境(零真实副作用):坐标注入绕 screen_info
    (拖点/源件格心固定),screens = 截图调用计数;返回 (op, env,
    拖拽记录, 截图计数列表)。"""
    drags: list = []
    screens: list[int] = []
    controller = type('_Ctl', (), {
        'mouse_move': lambda self, p: None,
        'drag_to': lambda self, **kw: drags.append(kw),
    })()
    sl = type('_SL', (), {'get_screen': lambda self, n: None})()
    op = type('_Op', (), {
        'screenshot': lambda self: (screens.append(1)
                                    or np.zeros((4, 4), dtype='uint8')),
        'park_cursor': lambda self, **kw: None,
        'ctx': type('_Ctx', (), {
            'controller': controller,
            'cw_match': None,
            'run_context': None,
            'screen_loader': sl,
        })(),
    })()
    ctx = op.ctx
    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor(op, ctx)
    ex._bench_pts = [Point(300, 800)] * 9
    ex._front_pts = [Point(300 + i * 140, 400) for i in range(4)]
    ex._back_pts = [Point(300 + i * 140, 620) for i in range(6)]
    # 坐标边注入(替身函数接缝 = 执行器实例方法;等价于 screen_info 命中形态)。
    ex._equip_slot_drag_point = lambda row, slot: Point(420, 421)
    ex._owned_grid_locate = lambda name: Point(1768, 247)
    env = PrepExecEnv(op=op, match=ctx.cw_match, executor=ex)
    monkeypatch.setattr('time.sleep', lambda _s: None)
    return CwActionWearEquipOp(ctx, CwActionWearEquipParam(item_name='轮滑鞋', char_name='刃',
                                        row='front', slot=1), env=env), env, drags, screens


def test_wear_equip_single_mechanical_drag_emits(monkeypatch):
    """发出即记账主测试:单次机械拖拽(无补救链重试)+ emitted=True +
    拖后零读屏(零落地判定);定位落空 = 未发出通道(emitted=False,
    非判效语义保留)。"""
    op, env, drags, screens = _wear_env(monkeypatch)

    ok = op.run()

    assert ok.is_success
    assert len(drags) == 1, '单次机械拖拽(无重试链)'
    assert ok.is_success, '发出即记账(round 成功态)'
    assert '已发' in (ok.status or '')
    assert screens == [], '拖后零读屏(落地判定归观察侧对账)'

    # 定位落空 = 未发出通道(计划失效,下帧重派重算;非 miss 判效)
    op2, env2, drags2, _screens = _wear_env(monkeypatch)
    env2.executor._owned_grid_locate = lambda name: None
    _r2 = op2.run()
    assert _r2.is_success is False and drags2 == []


def test_wear_locate_slot_anchor_over_name_match():
    """穿戴目标定位测试:计划步恒戳的物理槽位锚优先于名匹配——同名角色
    跨域在场(deployed 空装 + bench 副本穿满)时,旧 bench 先序名匹配
    会把穿戴记到席上副本 → 超限拒单零写 → 决策环同输入重派无限自旋
    (sim 冒烟 seed 20261014 实证);机械拖拽的真实落点 = 槽位 avatar,
    账随拖点走。槽位在位者与 char_name 不符 = 陈旧提案,如实拒(禁
    静默按名改目标)。"""
    from sr_od.application.currency_war.kernel.cw_action_report.wear_equip import (
        report_action_wear_equip_param,
    )
    sig_obs = ChannelSig(family='obs', actor='lock', mode='synthesized')
    sig = ChannelSig(family='logic_action', actor='lock', mode='compute')
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [None] * 9
    slots[0] = BenchSlot(kind='unit', unit=Unit(
        char_id='椒丘', star=2, equips=['追逐星辰', '动能激发剑', '生命之花']))
    gs.observe(gs.bench,
               BenchView(slots=[s if s is not None else BenchSlot(kind='empty')
                                for s in slots], capacity=9), sig=sig_obs)
    gs.observe(gs.deployed,
               _dvs([Unit(char_id='三月七', star=1),
                     Unit(char_id='椒丘', star=1)], [], back_capacity=6),
               sig=sig_obs)
    gs.observe(gs.equips, ['幸运星'], sig=sig_obs)
    # 槽位锚:front:2 = deployed 椒丘(空装)→ 穿上;bench 同名副本不动。
    out = report_action_wear_equip_param(
        gs, CwActionWearEquipParam(item_name='幸运星', char_name='椒丘',
                                   row='front', slot=2), sig)
    assert out.applied, f'槽位锚应命中 deployed 椒丘,实得 {out.reason!r}'
    dep = gs.deployed.value
    assert dep is not None and dep.front_slots[1] is not None \
        and dep.front_slots[1].char_id == '椒丘' \
        and list(dep.front_slots[1].equips) == ['幸运星'], \
        '账随拖点走:穿戴落在槽位锚指名的 deployed 单位'
    bench_unit = gs.bench.value.slots[0].unit
    assert bench_unit is not None and len(bench_unit.equips) == 3, \
        'bench 同名副本不动(名匹配不再先序)'
    # 陈旧提案:槽位在位者与 char_name 不符 → 拒(禁静默按名改目标)。
    gs.observe(gs.equips, ['和平手枪'], sig=sig_obs)
    out_stale = report_action_wear_equip_param(
        gs, CwActionWearEquipParam(item_name='和平手枪', char_name='椒丘',
                                   row='front', slot=1), sig)
    assert not out_stale.applied \
        and out_stale.reason == 'wear_target_unit_missing', \
        '槽位身份不符 = 陈旧提案如实拒'


def _deploy_env(session: object | None):
    """DeployMoveOp 离线执行环境(坐标注入;截图序列 scripted)。"""
    from sr_od.application.currency_war import prep_actions as pa
    controller = type('_Ctl', (), {
        'mouse_move': lambda self, p: None,
        'drag_to': lambda self, **kw: None,
    })()
    sl = type('_SL', (), {'get_screen': lambda self, n: None})()
    op = type('_Op', (), {
        'screenshot': staticmethod(lambda: None),
        'park_cursor': staticmethod(lambda **kw: None),
        'ctx': type('_Ctx', (), {
            'controller': controller,
            'cw_match': (None if session is None
                         else type('_M', (), {'session': session})()),
            'run_context': None,
            'screen_loader': sl,
        })(),
    })()
    ctx = op.ctx
    ex = pa.PrepActionExecutor(op, ctx)
    ex._bench_pts = [Point(300, 800)] * 9
    ex._front_pts = [Point(300 + i * 140, 400) for i in range(4)]
    ex._back_pts = [Point(300 + i * 140, 620) for i in range(6)]
    env = PrepExecEnv(op=op, match=ctx.cw_match, executor=ex)
    return env


# (test_deploy_move_tracks_immediately_on_emit 已随 CwActionDeployMoveOp 戊批并入后删除:
#  发出即记账语义 = move_unit 统一拖动上报,镜像测试见 cw_action_report/
#  test_move_unit.py。)


# ============================================================
# 5. _merge_bench 步回调(采样链逐步写的机械基础)
# ============================================================


def _char(slot: int, star: int, char_id: str = '阿格莱雅') -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=star))


def _snapshot(bench: list[BenchSlot | None]) -> list[tuple[str, int] | None]:
    """列表值快照(防别名:回调后列表继续被改,快照才留得住每级终态)。"""
    return [None if b is None else (b.unit.char_id, b.unit.star)
            for b in bench]


def test_on_step_fires_once_per_merge_level() -> None:
    """连锁两级(3×1★→2★,再 2★×3→3★)= on_step 恰 2 次。"""
    bench = [_char(1, 1), _char(2, 1), _char(3, 1),
             _char(4, 2), _char(5, 2)]
    steps: list[list[tuple[str, int] | None]] = []
    _merge_bench(bench, None, on_step=lambda: steps.append(_snapshot(bench)))
    assert len(steps) == 2, f'连锁两级 = 回调 2 次,实得 {len(steps)}'
    assert bench and bench[0] is not None and bench[0].unit.star == 3, \
        '终态 = 3★ 载体'


def test_on_step_sees_post_step_state() -> None:
    """回调时列表已落定该级终态:第一级后 3×1★ 已消费(置 None)、
    载体升 2★——调用侧此刻落容器即该级完成后的状态副本。"""
    bench = [_char(1, 1), _char(2, 1), _char(3, 1)]
    steps: list[list[tuple[str, int] | None]] = []
    _merge_bench(bench, None, on_step=lambda: steps.append(_snapshot(bench)))
    assert len(steps) == 1
    seen = steps[0]
    upgraded = [s for s in seen if s is not None]
    assert upgraded == [('阿格莱雅', 2)], \
        f'回调所见 = 该级终态(载体 2★,素材已置 None),实得 {seen}'


def test_on_step_dual_domain_level_fires_once() -> None:
    """载体在场上的一级合并(bench 素材 + deployed 载体同级变更):
    on_step 恰 1 次,两域列表在回调时均已落定——调用侧按受影响域
    各落一行(design §2.2 #1 写入契约)。"""
    bench = [_char(1, 1)]
    deployed = [Unit(char_id='阿格莱雅', star=1),
                Unit(char_id='阿格莱雅', star=1)]
    calls: list[tuple[list, list]] = []
    _merge_bench(bench, deployed,
                 on_step=lambda: calls.append((deepcopy(bench),
                                               deepcopy(deployed))))
    assert len(calls) == 1, '一级合并 = 回调 1 次'
    b_snap, d_snap = calls[0]
    assert b_snap[0] is None, 'bench 侧素材已置 None'
    upgraded = [d for d in d_snap if d is not None and d.star == 2]
    assert len(upgraded) == 1, 'deployed 侧载体已升 2★'

