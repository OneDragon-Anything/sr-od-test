"""获得链(gain-chain)行为测试(链式规范 + 开局种子底座通道规则)。

测试面依据(语义正本,changes/ 过程件不引):获得链正本 =
docs/develop/sr_od/application/currency_war/game_state/gain-chain.md
(§2 原语契约/§2.5 单级合成/§6 失败安全);通道规则与种子底座正本 =
同目录 fields.md §2.6(未锚定 → 随机态、锚定后按形参、失配网生效)。测试面:

- **对拍一致**(§2.1-3):单级合成 ``merge_step_once`` ×N 次终态与
  ``cw_merge_simulate.merge_simulate`` 同池同输入不动点终态一致(禁第二
  套语义的执行测试);
- **调用序**(§2.1 固定时序):落位 → 回调 → 升星 → 产物递归;回调补齐
  第三只后再合成;
- **通道收口双臂**(通道规则「未锚定 → 随机态」):直构未闩容器
  rand=False 链写被改道 write_logic_rand;置闩(测试专口直赋)后
  rand=False 恢复 write_logic;rand=True 恒 write_logic_rand;采样
  效果分支对子链的通道翻转只及子链;
- **失败安全**(§2.7):溢出落位/归位/溢出位被占留证;bench/equips
  未观察(直构域)= 拒落档零写、零缺陷发射(两未观察 kind 已随开局
  种子底座与锚定闩批退役);种子容器(缓存单例支,接管局同构)正常
  落账;置闩后失配网原样生效(确定面被观察覆盖产失配行);
- **欢愉契约条件分支 rider**(条件分支正式模型,测试面 = 银狼策划选择落地相
  上报的授予行为):通道语义(授予 rand=True 全通道 logic_rand,rand
  形参优先于锚定闩——未闩/置闩同通道)+ 覆盖校准面 = 观察覆盖落
  logic_rand_outcome 行零失配行;在册判定(active_env 归一 = 欢愉契约)、
  rng 注入确定性(同 seed 同单位,两候选均可达)、触发计数封闭清单
  (落地相 equip/upgrade/unknown 各恰一次,发射相零授予,branch_type=''
  兜底仍触发且终态兜底 reason = unrouted_leg_zero_write)、授予失败
  调用点级 best-effort(分支类型分派照常 + joy_conditional_grant_failed
  留证行)、授予走链固定时序(预置两枚同候选可合成);弱化兜底档退役
  测试(分类落 unknown/打分两档制)归 test_planner_report.py;
- **LV.999 变换窗**(银狼费用档变换,2026-09-18 定谳〔口述·权威〕:
  费用档不同时存在,分组键 (char_id, star) 无跨档歧义):升费分支 2★→1★
  变换三态与级联合并、上阵 3★→1★ 变换窗与恒等搬运对照;
- **选卡上报落地**(投资策略屏/portal 经获得链):策略屏注册去重 +
  骇客效果分派、portal 整支走获得链、表外安静不写;
- **卖/换动作上报 v2 族契约**(sell bench/deployed + swap deploy:
  出参 applied/reason/income + 域写回 + 未辖域零写;原金样迁移史见
  git 历史,现测试 = 活上报函数直测)。
"""
from __future__ import annotations

import random
from unittest import mock

import pytest

from sr_od.application.currency_war.kernel import cw_gain_chain
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_deploy_move_param,
    report_action_pick_invest_env_param,
    report_action_pick_invest_strategy_param,
    report_action_sell_bench_param,
    report_action_sell_deployed_param,
    report_action_swap_deploy_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
    report_action_pick_planner_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    bench_char_cost,
    sell_refund,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    SOURCE_STRATEGY,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    DEFECT_OVERFLOW_TAKEN,
    ENV_REROLL_DECL,
    PICK_INVEST_INVALID_PAYLOAD,
    discharge_due_item_grants,
    gain_bench_item,
    gain_character,
    gain_equipment,
    gain_invest_env,
    gain_invest_strategy,
    merge_step_once,
    on_env_gained,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    NodeKey,
    ShopPayload,
    ShopSlot,
    Unit,
    bench_units_of,
    consume_defect_sink,
    game_state_of,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_NAMES,
    ENV_GIFTS,
    INVESTMENT_ENVS,
    STRATEGY_GRANTS,
    RandomCharSpec,
    equips_by_category,
    random_char_pool,
)
from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    merge_simulate,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    PLANE_NODE_TABLES,
)
from sr_od.application.currency_war.kernel.cw_pool import grant_char_pool
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
    CwActionPickInvestEnvParam,
    CwActionPickInvestStrategyParam,
    CwActionSellBenchParam,
    CwActionSellDeployedParam,
    CwActionSwapDeployParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _lsig(actor: str = 'CwGainChain') -> ChannelSig:
    return ChannelSig(family='logic_action', actor=actor, mode='compute')


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             front: list[Unit] | None = None,
             equips: list[str] | None = None,
             gold: int | None = None,
             overflow_card: str | None = None,
             overflow_warning: bool | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供未观察边界分支)。"""
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
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_SIG_OBS)
    if overflow_card is not None:
        gs.observe(gs.overflow_card, overflow_card, sig=_SIG_OBS)
    if overflow_warning is not None:
        gs.observe(gs.overflow_warning, overflow_warning, sig=_SIG_OBS)
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


def _idents(seq: list) -> list:
    """槽位表 → 身份签名列表(None = 空槽/占位件;对拍比较用)。"""
    out = []
    for x in seq:
        if x is None:
            out.append(None)
            continue
        u = x.unit if isinstance(x, BenchSlot) else x
        if u is None or (isinstance(x, BenchSlot) and x.kind != 'unit'):
            out.append(None)
            continue
        out.append((str(u.char_id), int(u.star), tuple(u.equips or ())))
    return out


# ============================================================ 对拍(§2.1-3)


@pytest.mark.parametrize('bench_spec,dep_idx', [
    ([('希儿', 1)] * 3, None),                      # 单级:3×1★ → 2★
    ([('希儿', 1)] * 3 + [('希儿', 2)] * 2, None),  # 级联:→ 3★
    ([('希儿', 1)] * 2, 4),                         # 场上载体:bench 2 + 场上 1
    ([('希儿', 1)] * 3 + [('银狼', 1)] * 3, None),  # 双组各自合成
    ([('希儿', 1)] * 2 + [('银狼', 1)], None),      # 无三连 → 零推进
])
def test_merge_step_once_parity_with_merge_simulate(
        bench_spec: list[tuple[str, int]], dep_idx: int | None) -> None:
    """单级×N 终态 == merge_simulate 同池同输入不动点终态(design §2.1-3
    对拍测试;merge_simulate 是语义权威,期望值即其输出)。"""
    bench: list[BenchSlot | None] = [
        BenchSlot(kind='unit', unit=Unit(char_id=c, star=s)) for c, s in bench_spec]
    bench += [None] * (9 - len(bench))
    dep: list[Unit | None] = [None] * 10
    if dep_idx is not None:
        dep[dep_idx] = Unit(char_id=bench_spec[0][0], star=bench_spec[0][1])
    ours_b, ours_d, ours_ovf = list(bench), list(dep), []
    steps = 0
    while merge_step_once(ours_b, ours_d, ours_ovf) is not None:
        steps += 1
        assert steps < 50, '单级合成应随件数收敛,防死循环护栏'
    sim = merge_simulate(list(bench), list(dep), name='希儿', star=1, k=0)
    assert _idents(ours_b) == _idents(sim.bench_after)
    assert _idents(ours_d) == _idents(sim.deployed_after)
    assert ours_ovf == []


def test_merge_step_once_equips_inheritance() -> None:
    """装备继承并入(§2.1-3 对齐 merge_simulate 规则 4):被消耗两只的
    装备全量并入载体,载体自身装备在前、素材按扫描序在后。"""
    bench: list[BenchSlot | None] = [
        BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1, equips=['e1'])),
        BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1, equips=['e2'])),
    ] + [None] * 7
    dep: list[Unit | None] = [None] * 10
    dep[4] = Unit(char_id='希儿', star=1, equips=['e3'])
    ours_b, ours_d, ours_ovf = list(bench), list(dep), []
    assert merge_step_once(ours_b, ours_d, ours_ovf) == ('希儿', 2)
    assert ours_d[4] is not None and ours_d[4].equips == ['e3', 'e1', 'e2'], \
        '场上载体优先,装备 = 载体自身 + 素材(扫描序)'
    assert ours_b[0] is None and ours_b[1] is None, '备战素材摘除腾槽'


# ============================================================ 调用序(§2.1)


def test_call_order_place_callback_merge_recurse(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """固定时序测试(§2.1):落位 → 回调 → 升星 → 产物递归;回调补齐第三只
    后再合成(用户裁定「先触发回调…回来后再触发 3 合 1 升星判断」)。"""
    gs = _make_gs(bench=[('银狼', 1), ('希儿', 1)])
    # 置闩(测试专口直赋):本测试焦点 = 调用序,置闩使 rand=False 链写
    # 走 write_logic 桩(未闩会被通道规则改道 write_logic_rand,桩不触发)。
    gs.prep_anchored = True
    events: list[str] = []
    granted = {'n': 0}

    def fake_cb(gs: GameState, name: str, star: int, *, rand: bool,
                sig: ChannelSig) -> tuple[str, ...]:
        events.append(f'cb:{name}:{star}')
        if name == '银狼' and star == 1 and granted['n'] == 0:
            granted['n'] += 1
            events.append('cb_grant:银狼')
            gain_character(gs, '银狼', 1, rand=rand, sig=sig,
                           evidence='third', producer='T')
        return ()

    monkeypatch.setattr(cw_gain_chain, 'on_character_gained', fake_cb)
    orig_write = gs.write_logic

    def rec_write(target, value, **kw) -> None:
        events.append(f'write:{kw.get("evidence")}')
        orig_write(target, value, **kw)

    monkeypatch.setattr(gs, 'write_logic', rec_write)
    out = gain_character(gs, '银狼', 1, rand=False, sig=_lsig(),
                         evidence='main', producer='T')
    assert events == [
        'write:main#place',          # 落位先于回调
        'cb:银狼:1',                 # 回调(获得角色触发)
        'cb_grant:银狼',             # 回调补齐第三只(递归子链)
        'write:third#place',         # 子链落位
        'cb:银狼:1',                 # 子链回调
        'write:third#merge1',        # 三只齐 → 合成(回调返回后)
        'cb:银狼:2',                 # 升星产物重进获得角色(回调触发)
    ], '固定时序:落位 → 回调 → 升星 → 产物递归'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('银狼', 2), ('希儿', 1)], '三只全消耗、产物 2★'
    assert out.placed is True and out.landing == 'bench'


# ============================================================ rand 纪律(§2.4)


def test_rand_passthrough_and_channel_by_anchor(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """通道收口双臂 + rand 透传(通道规则「未锚定 → 随机态」):直构
    未闩容器 rand=False 链写被改道 write_logic_rand(未验证推算,首观察
    静默覆盖);置闩(测试专口直赋)后 rand=False 恢复 write_logic;
    rand=True 恒 write_logic_rand;采样效果分支对子链的通道翻转只及子链。"""
    # 臂 1:直构未闩 + rand=False → 通道改道 logic_rand
    gs = _make_gs(bench=[])
    assert gs.prep_anchored is False
    out = gain_character(gs, '希儿', 1, rand=False, sig=_lsig(),
                         evidence='g', producer='T')
    assert out.placed is True
    assert gs.bench.source == 'logic_rand', '未锚定期确定入口被改道随机态'
    # 臂 2:置闩 + rand=False → 恢复按形参走 write_logic
    gs2 = _make_gs(bench=[])
    gs2.prep_anchored = True
    gain_character(gs2, '希儿', 1, rand=False, sig=_lsig(), evidence='g',
                   producer='T')
    assert gs2.bench.source == 'logic', '锚定后确定面通道按形参'
    # 臂 3:rand=True 恒 logic_rand(与闩无关)
    gs3 = _make_gs(bench=[])
    gs3.prep_anchored = True
    gain_character(gs3, '停云', 1, rand=True, sig=_lsig(), evidence='g',
                   producer='T')
    assert gs3.bench.source == 'logic_rand'

    # 采样效果分支翻转子链(机制测试,rand 透传纪律;置闩容器上外链与子链
    # 通道可分辨):确定入口走 write_logic,采样子链走 write_logic_rand,
    # 外链不被子链污染。
    def sampling_cb(gs: GameState, name: str, star: int, *, rand: bool,
                    sig: ChannelSig) -> tuple[str, ...]:
        gain_character(gs, '希儿', 1, rand=True, sig=sig,
                       evidence='sampled', producer='T')
        return ()

    monkeypatch.setattr(cw_gain_chain, 'on_character_gained', sampling_cb)
    gs4 = _make_gs(bench=[])
    gs4.prep_anchored = True
    orig_logic, orig_rand = gs4.write_logic, gs4.write_logic_rand
    chan: list[tuple[str, str | None]] = []

    def rec_l(target, value, **kw) -> None:
        chan.append(('logic', kw.get('evidence')))
        orig_logic(target, value, **kw)

    def rec_r(target, value, **kw) -> None:
        chan.append(('logic_rand', kw.get('evidence')))
        orig_rand(target, value, **kw)

    monkeypatch.setattr(gs4, 'write_logic', rec_l)
    monkeypatch.setattr(gs4, 'write_logic_rand', rec_r)
    gain_character(gs4, '银狼', 1, rand=False, sig=_lsig(), evidence='main',
                   producer='T')
    assert ('logic', 'main#place') in chan, '置闩确定入口落位走 write_logic'
    assert ('logic_rand', 'sampled#place') in chan, \
        '采样效果子链走 write_logic_rand(翻转只及子链)'
    assert all(c == 'logic' for c, e in chan if e and e.startswith('main')), \
        '外链(确定面)不被采样子链污染'


# ============================================================ 溢出落位/归位/被占(§2.7)


def test_overflow_landing_writes_pair_fields() -> None:
    """席满 → 溢出落位(裁定⑥配套):overflow_warning/overflow_card 两字段
    各一行落位;星级不入容器字段(字段只有身份串);bench 零写。"""
    gs = _make_gs(bench=[('希儿', 1), ('银狼', 1), ('翡翠', 1), ('砂金', 1),
                         ('符玄', 1), ('希儿', 2), ('银狼', 2), ('卡芙卡', 1),
                         ('黑天鹅', 1)])   # 9 槽满且无同名同星三连(不触发合成)
    seq_before = gs.write_seq
    out = gain_character(gs, '停云', 1, rand=False, sig=_lsig(),
                         evidence='g', producer='T')
    assert out.placed is True and out.landing == 'overflow'
    assert gs.overflow_warning.value is True
    assert gs.overflow_card.value == '停云'
    assert gs.write_seq - seq_before == 2, '恰好两行(两字段各一行)'
    assert len(bench_units_of(gs)) == 9, 'bench 零写(值不动)'


def test_overflow_unit_merges_back_and_clears() -> None:
    """溢出件进合成池 → 合成腾槽归位(§2.1-3):满栏 2×银狼1★ + 溢出的
    第 3 只合成 2★,备战素材摘除腾槽,溢出位两字段成对清写。"""
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1),
                         ('希儿', 1), ('翡翠', 1), ('砂金', 1), ('符玄', 1),
                         ('卡芙卡', 1), ('黑天鹅', 1), ('停云', 1)])   # 满栏
    out = gain_character(gs, '银狼', 1, rand=False, sig=_lsig(),
                         evidence='g', producer='T')
    assert out.landing == 'overflow' and out.merge_levels == 1
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units.count(('银狼', 2)) == 1, '合成产物(载体 = 备战最左素材位)'
    assert ('银狼', 1) not in units
    assert gs.overflow_warning.value is False and gs.overflow_card.value == ''


def test_overflow_slot_taken_zero_write(rows_sink: _RowSink) -> None:
    """溢出位已被占(第二次溢出):游戏行为未实证 → 零写 + 留证禁猜(§2.7)。"""
    gs = _make_gs(bench=[('希儿', 1)] * 9,
                  overflow_card='停云', overflow_warning=True)
    seq_before = gs.write_seq
    out = gain_character(gs, '加拉赫', 1, rand=False, sig=_lsig(),
                         evidence='g', producer='T')
    assert out.placed is False and out.landing == 'skipped'
    assert out.detail == 'overflow_slot_taken'
    assert gs.write_seq == seq_before, '零写(不腾位不卖牌,链只如实记账)'
    assert rows_sink.kinds() == [DEFECT_OVERFLOW_TAKEN]


# ============================================================ 未观察退役 + 种子容器(§2.6-2/§2.7)


def test_unobserved_direct_zero_write_no_defect(rows_sink: _RowSink) -> None:
    """bench/equips 未观察(直构容器,种子底座下生产不可达):拒落档
    零写 + detail 档保留,零缺陷行发射(两未观察 kind 已退役——退役
    断言走台账面:调链原语后台账无新增行,禁源码扫描)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seq_before = gs.write_seq
    out_c = gain_character(gs, '希儿', 1, rand=False, sig=_lsig(),
                           evidence='g', producer='T')
    assert out_c.placed is False and out_c.detail == 'bench_unobserved'
    out_e = gain_equipment(gs, '分身墨镜', rand=False, sig=_lsig(),
                           evidence='g', producer='T')
    assert out_e.placed is False and out_e.detail == 'equips_unobserved'
    assert gs.write_seq == seq_before, '拒落档零写'
    assert rows_sink.kinds() == [], '退役 kind 零发射(台账零新增行)'


def test_seeded_container_chain_lands_and_takeover_isomorphic(
        rows_sink: _RowSink) -> None:
    """种子容器(经 game_state_of 缓存单例支,新局/接管局同构)链原语
    正常落账:bench 空底座(种子)落位、equips 空栏追加入栏——未观察
    拒落档生产死化。"""
    gs = game_state_of(StrategySession())
    assert gs.bench.source == 'logic_rand' \
        and gs.bench.evidence == 'seed:opening', '缓存单例支冷建含种子'
    out_c = gain_character(gs, '希儿', 1, rand=False, sig=_lsig(),
                           evidence='g', producer='T')
    assert out_c.placed is True and out_c.landing == 'bench'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [('希儿', 1)]
    out_e = gain_equipment(gs, '分身墨镜', rand=False, sig=_lsig(),
                           evidence='g', producer='T')
    assert out_e.placed is True
    assert gs.equips.value == ['分身墨镜'], '种子空栏追加入栏'
    assert rows_sink.kinds() == [], '种子底座上链落账零缺陷行'


def test_anchor_gates_mismatch_net() -> None:
    """锚定闩辖失配网(通道规则的验证信号面):置闩后链写(确定面)被
    观察以不同值覆盖 → 产 observe_vs_logic_mismatch 失配行(网未盲);
    未锚定期链写(随机态)被观察覆盖 → 仅 logic_rand_outcome 台账行、
    零失配行(首观察静默覆盖)。"""
    sig_obs = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')
    other_view = BenchView(
        slots=[BenchSlot(kind='unit',
                         unit=Unit(char_id='停云', star=1))]
        + [BenchSlot(kind='empty')] * 8, capacity=9)
    # 未闩臂:随机态链写 → 观察覆盖静默(差异落 logic_rand_outcome)
    gs = _make_gs(bench=[])
    consume_defect_sink()
    gain_character(gs, '希儿', 1, rand=False, sig=_lsig(), evidence='g',
                   producer='T')
    gs.observe(gs.bench, other_view, sig=sig_obs)
    kinds = [r['kind'] for r in consume_defect_sink()]
    assert 'observe_vs_logic_mismatch' not in kinds, '未锚定期首观察零失配行'
    assert 'logic_rand_outcome' in kinds, '随机态差异落 logic_rand_outcome'
    # 闩臂:确定面链写 → 观察覆盖产真失配行(失配网未盲)
    gs2 = _make_gs(bench=[])
    gs2.prep_anchored = True
    consume_defect_sink()
    gain_character(gs2, '希儿', 1, rand=False, sig=_lsig(), evidence='g',
                   producer='T')
    gs2.observe(gs2.bench, other_view, sig=sig_obs)
    kinds2 = [r['kind'] for r in consume_defect_sink()]
    assert 'observe_vs_logic_mismatch' in kinds2, '锚定后失配网原样生效'


# ============================================================ ENV_GIFTS 分道(§2.3)


def test_env_gift_advisor_split_and_quiet(rows_sink: _RowSink) -> None:
    """ENV_GIFTS 分道(§2.3-1):advisor=True 不入席,写解锁状态
    (gs.unlocked_experts,权威容器字段——专家顾问初始不参与普通商店
    招募,解锁后入池可刷,economy.md §1;原「只申报一行」随权威写道
    退役);advisor=False 入席递归(chars_immediate 1★);表外环境查无
    效果安静不写(裁定④)。session=None = 登记分支跳过、容器写照常
    (编排语义裁定)。"""
    # advisor:特邀专家 → 解锁入池(置闩保持确定面通道断言;本测试焦点
    # = 分道)
    gs_a = _make_gs(bench=[], equips=[])
    gs_a.prep_anchored = True
    out_a = gain_invest_env(gs_a, None, '特邀专家:停云', rand=False,
                           sig=_lsig())
    assert out_a.effects == ('advisor_unlock:特邀专家:停云:停云',)
    assert gs_a.unlocked_experts.value == ('停云',), '解锁状态写入'
    assert gs_a.active_env.value == '特邀专家:停云'   # 容器写照常
    assert gs_a.active_env.source == 'logic'
    assert bench_units_of(gs_a) == [], '不入席(顾问入商店非送单位)'
    assert rows_sink.kinds() == [], '权威写道零台账申报行'
    # 契约:直接送卡 → 入席递归
    gs_c = _make_gs(bench=[], equips=[])
    gs_c.prep_anchored = True
    out_c = gain_invest_env(gs_c, None, '公司契约', rand=False, sig=_lsig())
    assert out_c.effects == ('env_gift:翡翠', 'env_gift:砂金')
    units = [(u.char_id, u.star) for u in bench_units_of(gs_c)]
    assert units == [('翡翠', 1), ('砂金', 1)], 'chars_immediate 逐个 1★ 入席'
    # 表外环境:查无效果安静不写
    quiet = next(n for n in INVESTMENT_ENVS if n not in ENV_GIFTS)
    gs_q = _make_gs(bench=[], equips=[])
    gs_q.prep_anchored = True
    out_q = gain_invest_env(gs_q, None, quiet, rand=False, sig=_lsig())
    assert out_q.effects == () and out_q.placed is True
    assert bench_units_of(gs_q) == []
    assert rows_sink.kinds() == [], '表外零留证行'


def test_env_gift_summon_unit_sanxing_peipei(rows_sink: _RowSink) -> None:
    """ENV_GIFTS 召唤单位支首例(三星佩佩,T-16):chars_immediate 具名支
    与契约族同链——佩佩落席,效果串 ``env_gift:佩佩``,正常路径零申报行;
    星级 1 = 链必填占位(用户裁定佩佩无星级,非先验);星徽佩戴分支零建模
    (用户裁定:星徽佩戴在佩佩身上非入栏)→ equips 零写(防未来误把穿戴
    塞进道具/装备通道)。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_env(gs, None, '三星佩佩', rand=False, sig=_lsig())
    assert out.effects == ('env_gift:佩佩',), '召唤单位支效果串'
    assert gs.active_env.value == '三星佩佩', '容器写照常'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [('佩佩', 1)], \
        '佩佩落席(星级 1 = 占位值非先验)'
    assert gs.equips.value == [], '佩戴星徽分支零建模,equips 零写'
    assert rows_sink.kinds() == [], '非 advisor 非道具,零申报行'


def test_env_gift_summon_unit_cuxing_peipei(rows_sink: _RowSink) -> None:
    """ENV_GIFTS 召唤单位支姊妹卡(粗星佩佩,T-17):与三星佩佩同链——
    佩佩落席,效果串 ``env_gift:佩佩``,正常路径零申报行;星级 1 = 链必填
    占位(用户裁定佩佩无星级,非先验);双零分支零建模(佩戴 = 穿戴非入栏;
    掉落 = 概率/时点/件数/池四维全无载)→ equips 与 pending_item_grants
    零写(防未来误把星徽分支塞进道具/装备/定时通道)。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_env(gs, None, '粗星佩佩', rand=False, sig=_lsig())
    assert out.effects == ('env_gift:佩佩',), '召唤单位支效果串'
    assert gs.active_env.value == '粗星佩佩', '容器写照常'
    assert [(u.char_id, u.star) for u in bench_units_of(gs)] == [('佩佩', 1)], \
        '佩佩落席(星级 1 = 占位值非先验)'
    assert gs.equips.value == [], '双零分支零建模,equips 零写'
    assert not gs.pending_item_grants.value, '掉落分支不经定时队列,零入队'
    assert rows_sink.kinds() == [], '非 advisor 非道具,零申报行'


def test_env_gift_item_channel(rows_sink: _RowSink) -> None:
    """ENV_GIFTS 道具通道(§2.3):items_immediate 命中 → 效果串
    ``item_gift:<名>``(数量 = 元素重复次数)+ 落席写入(送卡落席同构,
    备战空槽 ``kind='supply_box'``;双端同一获得链,sim 世界写入即容器写);
    正常路径零申报行。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_env(gs, None, '火药味', rand=False, sig=_lsig())
    assert out.effects == ('item_gift:简易武装箱', 'item_gift:简易武装箱'), \
        '道具通道效果串:数量 = 元素重复次数'
    assert gs.active_env.value == '火药味'   # 容器写照常
    slots = gs.bench.value.slots
    assert sum(1 for s in slots if s.kind == 'supply_box') == 2, \
        '两箱落备战席空槽(supply_box 槽件)'
    assert bench_units_of(gs) == [], '道具非角色,单位域不变'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_env_gift_item_channel_bench_full(rows_sink: _RowSink) -> None:
    """ENV_GIFTS 道具通道席满(实机真值:道具与角色同款溢出语义):
    第一箱溢出落位(两字段直写,身份 = 道具名),第二箱撞被占溢出位 →
    零写一留证;效果串恒登记(发放事实与落位成败解耦)。"""
    gs = _make_gs(bench=[('希儿', 1)] * 9, equips=[])
    gs.prep_anchored = True
    out = gain_invest_env(gs, None, '火药味', rand=False, sig=_lsig())
    assert out.effects == ('item_gift:简易武装箱', 'item_gift:简易武装箱'), \
        '发放事实恒登记'
    assert sum(1 for s in gs.bench.value.slots
               if s.kind == 'supply_box') == 0, '席满不入备战槽'
    assert gs.overflow_warning.value is True, '第一箱溢出落位(告警在场)'
    assert gs.overflow_card.value == '简易武装箱', '溢出位身份 = 道具名'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('希儿', 1)] * 9, '席原样'
    assert rows_sink.kinds() == [DEFECT_OVERFLOW_TAKEN], \
        '第二箱撞被占溢出位,零写一留证'


def test_overflow_item_merges_back_as_box_and_clears() -> None:
    """溢出道具进合成池 = 惰性槽件(BENCH_ITEM_NAMES 判 kind,禁成假角色
    素材)→ 合成腾槽后归位为 supply_box(§4 身份两分);溢出位两字段成对
    清写。"""
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1),
                         ('希儿', 1), ('翡翠', 1), ('砂金', 1), ('符玄', 1),
                         ('卡芙卡', 1), ('黑天鹅', 1)])   # 8/9,无三连
    gs.observe(gs.overflow_card, '简易武装箱', sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    gain_character(gs, '银狼', 1, rand=False, sig=_lsig(),
                   evidence='g', producer='T')
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units.count(('银狼', 2)) == 1, '合成产物落位'
    assert all(c != '简易武装箱' for c, _ in units), '道具禁入角色域'
    slots = gs.bench.value.slots
    assert sum(1 for s in slots if s.kind == 'supply_box') == 1, \
        '合成腾槽 → 溢出道具归位备战槽(supply_box 槽件)'
    assert gs.overflow_warning.value is False and gs.overflow_card.value == '', \
        '溢出位腾空,两字段成对清写'


def test_env_reroll_declaration_row_member_only(rows_sink: _RowSink) -> None:
    """追加随机环境申报行(§3,名单成员-only;首例 = 蓝海 id113):名单内
    环境 = 金收入分支照常 + 申报行恰一行(kind = ENV_REROLL_DECL,语义申报非
    缺陷告警;live 不自掷 fail-closed,active_env 写值 = 选择事实,容器
    写通道与普通环境一致);名单外环境(增发货币,经济表成员)零申报行
    ——申报只随 ENV_REROLL_NAMES 名单,不随经济表成员身份。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_env(gs, None, '蓝海', rand=False, sig=_lsig())
    assert gs.active_env.value == '蓝海', '选择事实写值'
    assert gs.active_env.source == 'logic', '容器写通道与普通环境一致'
    assert gs.gold.value == 6, '金收入分支照常(+6,ENV_ECONOMY 唯一 gold_instant)'
    assert out.effects == (), '追加获得非本链职责(世界掷骰归 sim 后端)'
    assert rows_sink.kinds() == [ENV_REROLL_DECL], '申报行恰一行'
    # 名单外对照:增发货币零新增申报行
    gs2 = _make_gs(bench=[], equips=[])
    gs2.prep_anchored = True
    gain_invest_env(gs2, None, '增发货币', rand=False, sig=_lsig())
    assert gs2.active_env.value == '增发货币'
    assert rows_sink.kinds() == [ENV_REROLL_DECL], '名单外零新增申报行'


# ============================================================ 随机角色通道
# (环境随机发放:chars_random_immediate 规格池掷骰;迭代
# 2026-09-23-invest-effects-calc T-10 人才引进)


def test_env_gift_random_leg_seeded_roll(rows_sink: _RowSink) -> None:
    """随机支发放分支(on_env_gained 直构,T-10 设计 §4 测试 3):固定种子
    rng → bench 追加 1 张 1★ 且名 ∈ 4 费规格池;效果串
    ``env_gift_random:<名>@1star`` 前缀 + 后缀同断言(采样发放的审计
    对账键);星级 = spec.star(人才引进 = 1 先验)。期望名从同 seed
    现算(单一来源,不手抄)。"""
    gs = _make_gs(bench=[], equips=[])
    pool = grant_char_pool(gs, RandomCharSpec(cost=4, star=1))
    expected = random.Random(20261014).choice(pool)
    out = on_env_gained(gs, None, '人才引进', rand=False, sig=_lsig(),
                        rng=random.Random(20261014))
    assert out == (f'env_gift_random:{expected}@1star',)
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [(expected, 1)], '落席 1 张,星级 = 先验 1'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_env_gift_random_branch_typed_pool_star2_seeded(
        rows_sink: _RowSink) -> None:
    """类型过滤随机支发放分支(on_env_gained 直构,T-36 设计 §4 锁 3/9):
    固定种子 rng → bench 追加 1 张 2★(spec.star 直传,类型过滤池 =
    1 费「输出」件)且名 ∈ 规格池;效果串 'env_gift_random:<名>@2star'
    (星级后缀随 spec,卡面明写非先验);获得链写序 = 仅 bench 一笔写——
    属性加成分支不建模的零写端钉死(锁 9 收窄形:节点推进无本卡挂点,
    差分重放不稳定不设)。期望名从同 seed 现算(单一来源,不手抄)。"""
    gs = _make_gs(bench=[], equips=[])
    seq_before = gs.write_seq
    pool = grant_char_pool(gs, RandomCharSpec(cost=1, star=2, type_tag='输出'))
    expected = random.Random(20261021).choice(pool)
    out = on_env_gained(gs, None, '战力提升', rand=False, sig=_lsig(),
                        rng=random.Random(20261021))
    assert out == (f'env_gift_random:{expected}@2star',)
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [(expected, 2)], '落席 1 张,星级 = spec.star 2'
    assert gs.write_seq - seq_before == 1, \
        '获得链仅 bench 一笔写(零计数器/持久域追加)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_env_gift_random_leg_star2_merge_boundary(
        rows_sink: _RowSink) -> None:
    """2★ 赠卡合成边界(T-36 设计 §4 锁 5):预置两枚同名 2★ → 赠 2★
    同星 3 合 1 升 3★((char_id, star) 二元组识别,星级感知);预置两枚
    同名 1★ → 赠 2★ 星级不同不合并。期望名从同 seed 现算。"""
    pool = grant_char_pool(_make_gs(bench=[], equips=[]),
                           RandomCharSpec(cost=1, star=2, type_tag='输出'))
    name = random.Random(20261021).choice(pool)
    gs = _make_gs(bench=[(name, 2), (name, 2)], equips=[])
    on_env_gained(gs, None, '战力提升', rand=False, sig=_lsig(),
                  rng=random.Random(20261021))
    merged = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert merged == [(name, 3)], '两枚 2★ + 赠 2★ → 3★(同星 3 合 1)'
    gs1 = _make_gs(bench=[(name, 1), (name, 1)], equips=[])
    on_env_gained(gs1, None, '战力提升', rand=False, sig=_lsig(),
                  rng=random.Random(20261021))
    no_merge = sorted((u.char_id, u.star) for u in bench_units_of(gs1))
    assert no_merge == [(name, 1), (name, 1), (name, 2)], \
        '1★×2 与赠 2★ 星级不同,不合并'


def test_env_gift_random_leg_cost2_star2_seeded(rows_sink: _RowSink) -> None:
    """战力飙升(2 费无类型词)发放分支(on_env_gained 直构,T-37 设计 §4
    锁 3/9):固定种子 rng → bench 追加 1 张 2★(名 ∈ 2 费全档池);
    效果串 'env_gift_random:<名>@2star';获得链写序 = 仅 bench 一笔写——
    属性加成分支不建模的零写端钉死。期望名从同 seed 现算(单一来源,不手抄)。"""
    gs = _make_gs(bench=[], equips=[])
    seq_before = gs.write_seq
    pool = grant_char_pool(gs, RandomCharSpec(cost=2, star=2))
    expected = random.Random(20261022).choice(pool)
    out = on_env_gained(gs, None, '战力飙升', rand=False, sig=_lsig(),
                        rng=random.Random(20261022))
    assert out == (f'env_gift_random:{expected}@2star',)
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [(expected, 2)], '落席 1 张,星级 = spec.star 2'
    assert gs.write_seq - seq_before == 1, \
        '获得链仅 bench 一笔写(零计数器/持久域追加)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_env_gift_random_leg_star2_merge_cost2_boundary(
        rows_sink: _RowSink) -> None:
    """战力飙升 2★ 赠卡合成边界(T-37 设计 §4 锁 5,开局形状 (1,1,2,2)
    同名态为本卡天然边界):预置两枚同名 1★ 2 费件 → 赠 2★ 星级失配
    不合并(席面三件并存,(char_id, star) 二元组识别);预置两枚同名 2★
    → 同星 3 合 1 升 3★。期望名从同 seed 现算。"""
    pool = grant_char_pool(_make_gs(bench=[], equips=[]),
                           RandomCharSpec(cost=2, star=2))
    name = random.Random(20261022).choice(pool)
    gs1 = _make_gs(bench=[(name, 1), (name, 1)], equips=[])
    on_env_gained(gs1, None, '战力飙升', rand=False, sig=_lsig(),
                  rng=random.Random(20261022))
    no_merge = sorted((u.char_id, u.star) for u in bench_units_of(gs1))
    assert no_merge == [(name, 1), (name, 1), (name, 2)], \
        '1★×2 与赠 2★ 星级不同,不合并(开局同名边界)'
    gs = _make_gs(bench=[(name, 2), (name, 2)], equips=[])
    on_env_gained(gs, None, '战力飙升', rand=False, sig=_lsig(),
                  rng=random.Random(20261022))
    merged = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert merged == [(name, 3)], '两枚 2★ + 赠 2★ → 3★(同星 3 合 1)'


def test_env_gift_random_leg_anchored_rand_channel(
        rows_sink: _RowSink) -> None:
    """随机支通道语义(T-10 设计 §4 测试 4):锚定容器 + 采样子链
    rand=True → 写值照常生效且不进失配网(随机态语义,gain-chain.md
    §5:采样写走 write_logic_rand,首观察静默覆盖不响安灯);未锚定
    写生效已由 seeded_roll 测试校验(直构缺省未锚定)。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = on_env_gained(gs, None, '人才引进', rand=False, sig=_lsig(),
                        rng=random.Random(7))
    assert len(out) == 1 and out[0].startswith('env_gift_random:')
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert len(units) == 1 and units[0][1] == 1, '锚定后采样写照常落席'
    assert rows_sink.kinds() == [], '随机态写不进失配网,零缺陷行'


# ============================================================ 开局替换清席支
# (replaces_opening_supply;迭代 2026-09-23-invest-effects-calc T-43 人才储备)


class _FixedSeqRng:
    """固定抽序桩 rng(choice 按序弹出自备序列):合成边界锁锁「抽形」
    (三同名 / 两同一异)而非具体名——注册表漂移不改抽形,比寻实种子稳。"""

    def __init__(self, names: list[str]) -> None:
        self._names = list(names)

    def choice(self, seq: list) -> str:
        return self._names.pop(0)


def test_opening_replace_leg_clear_and_grant(rows_sink: _RowSink) -> None:
    """清+发直构核心锁(T-43 设计 §4 锁 2/7):预置 4 只任意 1★ + 固定
    种子 rng → on_env_gained 后 bench 恰 3 只,每只 1★ 且名 ∈ 3 费规格池
    (= chars_by_cost(3) 全档,type_tag 空);效果串 = env_opening_replace:4
    + env_gift_random:<名>@1star ×3;获得链全部写面 = 清席 1 + 落席 3
    恰 4 笔(分支 2 不建模的零写端钉死:升星/节点/战斗无本卡挂点,零顺手
    计数器);容量随原观察保持。期望名从同 seed 现算(单一来源,不手抄)。"""
    gs = _make_gs(bench=[('希儿', 1)] * 4, equips=[])
    seq_before = gs.write_seq
    pool = grant_char_pool(gs, RandomCharSpec(cost=3, star=1))
    r = random.Random(20261025)
    expected = [r.choice(pool) for _ in range(3)]
    assert len(set(expected)) > 1, '种子抽形两同一异(非全同名,预登记)'
    out = on_env_gained(gs, None, '人才储备', rand=False, sig=_lsig(),
                        rng=random.Random(20261025))
    assert out == ('env_opening_replace:4',
                   *(f'env_gift_random:{n}@1star' for n in expected))
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert sorted(units) == sorted((n, 1) for n in expected), \
        '恰 3 只 1★(4 张开局被替换,非叠加 7 只)'
    assert gs.write_seq - seq_before == 4, \
        '写面 = 清席 1 + 落席 3(零计数器/持久域追加)'
    assert gs.bench.value.capacity == 9, '容量随原观察保持'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_opening_replace_leg_zero_unit_zero_write(rows_sink: _RowSink) -> None:
    """零 unit 零写(T-43 设计 §4 锁 3):空 bench 直构(live 空底座形态)
    → 清席分支零写,只留效果串 env_opening_replace:0 申报替换事实;写面 =
    落席 3 笔(赠卡照常落,替换语义对 live = 无开局可清,发放不受影响)。"""
    gs = _make_gs(bench=[], equips=[])
    seq_before = gs.write_seq
    pool = grant_char_pool(gs, RandomCharSpec(cost=3, star=1))
    r = random.Random(20261025)
    expected = [r.choice(pool) for _ in range(3)]
    out = on_env_gained(gs, None, '人才储备', rand=False, sig=_lsig(),
                        rng=random.Random(20261025))
    assert out == ('env_opening_replace:0',
                   *(f'env_gift_random:{n}@1star' for n in expected))
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert sorted(units) == sorted((n, 1) for n in expected)
    assert gs.write_seq - seq_before == 3, '清席分支零写,写面 = 落席 3 笔'


def test_opening_replace_leg_three_same_merge_to_2star() -> None:
    """三同名合成边界(T-43 设计 §4 锁 4a,裁决点 3 可重口径):桩 rng
    三抽同名 → 3 合 1 升 2★(获得链自然结果,零新逻辑);效果串星级后缀
    = spec.star 1(采样发放星级,非合成产物星级)。"""
    pool = random_char_pool(RandomCharSpec(cost=3, star=1))
    name = pool[0]
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '人才储备', rand=False, sig=_lsig(),
                        rng=_FixedSeqRng([name, name, name]))
    assert out == ('env_opening_replace:0',
                   *(f'env_gift_random:{name}@1star',) * 3)
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [(name, 2)], '三同名 1★ 链内合成一只 2★'


def test_opening_replace_leg_two_same_one_diff_no_merge() -> None:
    """两同一异不合并(T-43 设计 §4 锁 4b):桩 rng [X, X, Y] → 3 只 1★
    并存(同星 3 合 1 需三只,两只不触发)。"""
    pool = random_char_pool(RandomCharSpec(cost=3, star=1))
    x, y = pool[0], pool[1]
    gs = _make_gs(bench=[], equips=[])
    on_env_gained(gs, None, '人才储备', rand=False, sig=_lsig(),
                  rng=_FixedSeqRng([x, x, y]))
    units = sorted((u.char_id, u.star) for u in bench_units_of(gs))
    assert units == sorted([(x, 1), (x, 1), (y, 1)]), '两同一异 3 只并存'


def test_env_gift_conditional_only_quiet_after_random_branch(
        rows_sink: _RowSink) -> None:
    """具名支回归(T-10 设计 §4 测试 6):仅条件分支条目(量子同频契约)
    在随机支落地后行为逐位不变——零即时发放、零效果串、零容器写
    (随机支为追加分支,前置分支零触碰)。"""
    gs = _make_gs(bench=[], equips=[])
    seq_before = gs.write_seq
    out = on_env_gained(gs, None, '量子同频契约', rand=False, sig=_lsig())
    assert out == (), '条件分支不即时发放'
    assert bench_units_of(gs) == []
    assert gs.write_seq == seq_before, '安静不写,零容器写'


# ============================================================ 随机装备通道
# (环境随机装备发放:equips_random_immediate 类别池掷骰 + 绑定分支;首例
# 劳务派遣合同分支1,设计 = 该迭代 designs/T-19-laowu-paiqian-hetong.md
# §2.4)


def test_env_star_grant_seeded_roll_and_binding(rows_sink: _RowSink) -> None:
    """随机装备支发放分支(on_env_gained 直构,T-19 设计 §4.2):固定种子
    rng → equips 尾追 1 件 category='星徽' 装备且名 ∈ 类别池;done 追加
    ``('劳务派遣合同', 'star_grant#<名>')`` 绑定键;效果串
    ``env_star_grant:<名>``。期望名同 seed 现算(单一来源,不手抄)。"""
    gs = _make_gs(bench=[], equips=[])
    pool = equips_by_category('星徽')
    expected = random.Random(20261015).choice(pool)
    out = on_env_gained(gs, None, '劳务派遣合同', rand=False, sig=_lsig(),
                        rng=random.Random(20261015))
    assert out == (f'env_star_grant:{expected}',), '效果串前缀 env_star_grant:'
    assert gs.equips.value == [expected], '库存尾追 1 件星徽'
    assert gs.env_grants_done.value == (('劳务派遣合同',
                                         f'star_grant#{expected}'),), \
        '绑定分支:发放名落 done(分支2 触发依赖)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_env_star_grant_equips_unobserved_zero_write(
        rows_sink: _RowSink) -> None:
    """equips 未观察 → 装备与绑定同零写(T-19 设计 §4.2 placed 守卫锁):
    禁「绑定在而装备未发」残缺态(与分支2 bench None 缓发口径对称);
    效果串恒登记(与落位成败解耦,items 通道现役惯例)。"""
    gs = _make_gs(bench=[])   # equips 未写 = None
    pool = equips_by_category('星徽')
    expected = random.Random(9).choice(pool)
    out = on_env_gained(gs, None, '劳务派遣合同', rand=False, sig=_lsig(),
                        rng=random.Random(9))
    assert out == (f'env_star_grant:{expected}',), '效果串恒登记'
    assert gs.equips.value is None, '零写:装备未入栏'
    assert gs.env_grants_done.value is None, '绑定不落(placed 守卫)'


def test_env_star_grant_empty_pool_skip(rows_sink: _RowSink) -> None:
    """运行期空池防御(T-19 设计 §2.4 log+跳过):注册表漂移态(类别池
    派生空)→ 零写不炸链(与 chars_random 支空池防御及分支2 池空防御
    对称);无效果串。"""
    gs = _make_gs(bench=[], equips=[])
    seq_before = gs.write_seq
    with mock.patch.object(cw_gain_chain, 'equips_by_category',
                           lambda cat: ()):
        out = on_env_gained(gs, None, '劳务派遣合同', rand=False,
                            sig=_lsig(), rng=random.Random(3))
    assert out == (), '空池跳过,无效果串'
    assert gs.equips.value == [], '零写'
    assert gs.env_grants_done.value is None, '绑定不落'
    assert gs.write_seq == seq_before, '零容器写'
    assert rows_sink.kinds() == [], '防御分支非缺陷(留 log 不留证)'


# ============================================================ 定时道具通道
# (环境定时发放:items_scheduled 登记入队 + discharge_due_item_grants 到点发放)


def test_env_gift_scheduled_channel_enqueues(rows_sink: _RowSink) -> None:
    """定时通道登记(gain_invest_env):items_scheduled 逐项入容器队列
    pending_item_grants(一次 write 回写整表;entry 形 =
    {env, plane, round_num, item}),效果串 ``item_scheduled:<名>@<节点键>``;
    登记不落席(零 supply_box 落位),active_env 容器写照常。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_env(gs, None, '特权阶级', rand=False, sig=_lsig())
    assert out.effects == ('item_scheduled:特权武装箱@2-1',), \
        '定时通道效果串:发放事实登记,数量 = 元素重复次数'
    assert gs.active_env.value == '特权阶级'
    assert gs.active_env.source == 'logic', '容器写照常(确定面)'
    assert gs.pending_item_grants.value == [
        {'env': '特权阶级', 'plane': 2, 'round_num': 1, 'item': '特权武装箱'}], \
        '入队 = 解析好的目标节点 + 来源环境'
    assert gs.pending_item_grants.source == 'logic', '登记期确定面写'
    slots = gs.bench.value.slots
    assert sum(1 for s in slots if s.kind == 'supply_box') == 0, '登记不落席'
    assert bench_units_of(gs) == [], '道具非角色,单位域不变'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_discharge_due_item_grants_place_and_drain(rows_sink: _RowSink) -> None:
    """到点发放(原语主径):命中 (plane, round_num) 项逐个落位(备战空槽
    supply_box)+ 效果串 ``item_gift:<名>`` + 队列回写保留集;非到点节点
    零写零效果、队列原样。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    gain_invest_env(gs, None, '特权阶级', rand=False, sig=_lsig())
    effects = discharge_due_item_grants(gs, plane=2, round_num=1,
                                        rand=False, sig=_lsig())
    assert effects == ('item_gift:特权武装箱',)
    slots = gs.bench.value.slots
    assert sum(1 for s in slots if s.kind == 'supply_box') == 1, '到点落位'
    assert gs.pending_item_grants.value == [], '命中清空,队列回写保留集'
    assert rows_sink.kinds() == [], '正常路径零申报行'
    # 非到点:零写零效果、队列原样
    gs2 = _make_gs(bench=[], equips=[])
    gs2.prep_anchored = True
    gain_invest_env(gs2, None, '特权阶级', rand=False, sig=_lsig())
    seq_before = gs2.write_seq
    effects2 = discharge_due_item_grants(gs2, plane=1, round_num=1,
                                         rand=False, sig=_lsig())
    assert effects2 == () and gs2.write_seq == seq_before, '非到点零写'
    assert gs2.pending_item_grants.value == [
        {'env': '特权阶级', 'plane': 2, 'round_num': 1, 'item': '特权武装箱'}], \
        '队列原样'


def test_discharge_overflow_semantics_reused(rows_sink: _RowSink) -> None:
    """落位语义复用(design §2.3 ②):席满 → 溢出落位两字段(身份 = 道具名,
    角色入账分支同款);溢出位再被占 → 该项零写留证(DEFECT_OVERFLOW_TAKEN);
    队列回写只看命中非空,与落位成败解耦。"""
    gs = _make_gs(bench=[('希儿', 1)] * 9, equips=[])
    gs.prep_anchored = True
    gain_invest_env(gs, None, '特权阶级', rand=False, sig=_lsig())
    effects = discharge_due_item_grants(gs, plane=2, round_num=1,
                                        rand=False, sig=_lsig())
    assert effects == ('item_gift:特权武装箱',), '发放事实恒登记'
    assert gs.overflow_warning.value is True, '席满溢出落位(告警在场)'
    assert gs.overflow_card.value == '特权武装箱', '溢出位身份 = 道具名'
    assert gs.pending_item_grants.value == []
    assert rows_sink.kinds() == [], '席满溢出落位是既定语义,零留证'
    gs2 = _make_gs(bench=[('希儿', 1)] * 9, equips=[],
                   overflow_card='简易武装箱', overflow_warning=True)
    gs2.prep_anchored = True
    gain_invest_env(gs2, None, '特权阶级', rand=False, sig=_lsig())
    effects2 = discharge_due_item_grants(gs2, plane=2, round_num=1,
                                         rand=False, sig=_lsig())
    assert effects2 == ('item_gift:特权武装箱',)
    assert gs2.overflow_card.value == '简易武装箱', '溢出位被占:零写'
    assert rows_sink.kinds() == [DEFECT_OVERFLOW_TAKEN], '零写一留证'
    assert gs2.pending_item_grants.value == [], '队列回写与落位成败解耦'


def test_bench_item_names_cover_scheduled_channel() -> None:
    """占席道具词表派生面:BENCH_ITEM_NAMES 并入 items_scheduled 道具名
    (定时道具同为占席道具,溢出位身份 kind 判定同面——缺派生会把箱当
    角色,假身份进合成素材组);策略箱分支登记同样自动派生覆盖(design
    §2.1 断言:登记即入词表,进阶武装箱首例)。"""
    assert '特权武装箱' in BENCH_ITEM_NAMES, 'scheduled 派生覆盖'
    assert '简易武装箱' in BENCH_ITEM_NAMES, 'immediate 派生保持'
    assert '进阶武装箱' in BENCH_ITEM_NAMES, '策略箱分支登记即派生覆盖'


def test_pending_item_grants_audit_row_declared() -> None:
    """对账申报(容器字段完备性纪律):新容器字段必须在 PROJECTION_AUDIT
    登记行,行状态 = process_only(队列 = 卡文推算知识,无观察读端)。"""
    from sr_od.application.currency_war.kernel.cw_projection_audit import (
        AUDIT_PROCESS_ONLY,
        PROJECTION_AUDIT,
    )
    row = PROJECTION_AUDIT.get('pending_item_grants')
    assert row is not None, '登记行在册'
    assert row.status == AUDIT_PROCESS_ONLY, '无观察读端 → process_only'


def test_gain_invest_env_invalid_payload_zero_write(rows_sink: _RowSink) -> None:
    """无效载荷拒绝(env 支步 0,与策略支同形测试同构,gain-chain.md §2.1
    步 0):归一后空/'?' = 零写 + 缺陷留证(active_env 值不变;无效输入
    拒绝,非防重复保护)。"""
    gs = _make_gs(bench=[], equips=[])
    seq_before = gs.write_seq
    for bad in ('', '?'):
        out = gain_invest_env(gs, None, bad, rand=False, sig=_lsig())
        assert out.placed is False and out.detail == 'invalid_payload'
    assert gs.active_env.value in (None, ''), '零写:active_env 值不变'
    assert gs.write_seq == seq_before, '零写'
    assert rows_sink.kinds() == [PICK_INVEST_INVALID_PAYLOAD,
                                 PICK_INVEST_INVALID_PAYLOAD]


# ============================================================ 装备获得(§2.1/§2.3-3)


def test_gain_equipment_consequence_and_quiet() -> None:
    """gain_equipment:入栏 + EQUIP_ACQUIRE_CONSEQUENCES 命中送单位递归
    (2×银狼在手 → 分身墨镜第 3 只合成 2★);分身墨镜卡文「解锁并获得」
    = 解锁专家入池 + 送单位两条分支(官方机制:专家顾问初始不在商店池,
    economy.md §1);表外件查无效果安静不写。"""
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=[])
    out = gain_equipment(gs, '分身墨镜', rand=False, sig=_lsig(),
                         evidence='g', producer='T')
    assert out.placed is True
    assert out.effects == ('equip_expert_unlock:银狼',
                           'equip_consequence:银狼'), '解锁 + 送单位两条分支'
    assert gs.unlocked_experts.value == ('银狼',), '解锁状态写入'
    assert gs.equips.value == ['分身墨镜']
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units.count(('银狼', 2)) == 1, '送出单位经链入席并可触发合成'
    gs2 = _make_gs(bench=[], equips=[])
    out2 = gain_equipment(gs2, '轮滑鞋', rand=False, sig=_lsig(),
                          evidence='g', producer='T')
    assert out2.effects == () and gs2.equips.value == ['轮滑鞋']
    assert bench_units_of(gs2) == [], '表外件无后果声明,零单位写'
    assert gs2.unlocked_experts.value in (None, ()), '表外件零解锁写'


# (GainOutcome frozen 形状构造断言已删:dataclass 冻结属性为语言级保证,
#  无可判别的运行故障形态——留证载体行为由各拒落路径测试实际校验。)


# ============================================================ 获得投资策略(策略屏迁移批 3.1)


def test_gain_invest_strategy_invalid_payload_zero_write(
        rows_sink: _RowSink) -> None:
    """无效载荷拒绝(归一后空/'?' = 零写 + 缺陷留证;无效输入拒绝非防
    重复保护,design §2.4-0)。"""
    gs = _make_gs(bench=[], equips=[])
    seq_before = gs.write_seq
    for bad in ('', '?'):
        out = gain_invest_strategy(gs, None, bad, rand=False, sig=_lsig())
        assert out.placed is False and out.detail == 'invalid_payload'
    assert gs.active_strategies.value in (None, [])
    assert gs.write_seq == seq_before, '零写'
    assert rows_sink.kinds() == [PICK_INVEST_INVALID_PAYLOAD,
                                 PICK_INVEST_INVALID_PAYLOAD]


def test_gain_invest_strategy_register_dedup_and_hacker_chain(
        monkeypatch: pytest.MonkeyPatch, rows_sink: _RowSink) -> None:
    """三段式主链(design §2.4):注册按名字去重追加(裁定⑩持卡列表
    写入语义)→ 登记分支(session=None 跳过)→ on_strategy_gained 分派
    advisor 解锁分支(银狼入池,官方卡文 = 加入商店非送单位,原入席分支
    随权威解锁写道退役)+ 骇客效果体(改件经 gain_equipment rand=True
    入栏,后果表件经 on_equipment_gained 回调送单位;标记域 = 前后值
    快照比对,gold 永不翻)。"""
    monkeypatch.setattr(random.Random, 'choice',
                        lambda self, seq: '破解芯片')   # 表外件(无后果分支)
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=[])
    # 置闩(测试专口直赋):注册分支确定面通道断言(source == 'logic')以
    # 通道规则前置;采样分支 rand=True 恒 logic_rand 不受影响。
    gs.prep_anchored = True
    seq_before = gs.write_seq
    gain_invest_strategy(gs, None, '骇客专家:银狼', rand=False,
                         sig=_lsig())
    assert gs.active_strategies.value == ['骇客专家:银狼'], '注册入表'
    assert gs.active_strategies.source == 'logic', '确定面 write_logic'
    assert gs.unlocked_experts.value == ('银狼',), 'advisor 解锁分支写入'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('银狼', 1), ('银狼', 1)], \
        '顾问入商店非送单位,预置单位保持 1★'
    assert gs.equips.value == ['破解芯片'], '改件入栏(采样值)'
    assert gs.equips.source == 'logic_rand', '采样分支 logic_rand'
    assert gs.write_seq > seq_before, '多步各占写序'
    assert rows_sink.kinds() == [], '解锁权威写,零台账申报行'
    # 去重:同卡再入 → 持卡面跳写不重复;效果分支照常(裁定⑩语义 = 仅持卡
    # 列表去重,效果分派零闸;解锁只增去重幂等)
    seq2 = gs.write_seq
    gain_invest_strategy(gs, None, '骇客专家:银狼', rand=False,
                         sig=_lsig())
    assert gs.active_strategies.value == ['骇客专家:银狼'], '持卡面单份'
    assert gs.unlocked_experts.value == ('银狼',), '解锁幂等(不重复追加)'
    assert gs.write_seq > seq2, '效果分支照走(零幂等闸)'


def test_gain_invest_strategy_session_ledger_branch() -> None:
    """登记分支(design §2.4-2):session 在场 + STRATEGY_EFFECTS 命中 →
    register_strategy 入册 + burst 桥累加免费刷新余额;session=None =
    登记分支跳过、注册照常;未收录卡登记分支零动作。(选卡 = 固定理财:
    STRATEGY_EFFECTS 在册条目且 payload.free_refresh_burst=2,桥 docstring
    背书;市场干预仅在经济聚合表 STRATEGY_ECONOMY,不入本表。)"""
    gs = _make_gs(bench=[], equips=[])
    gain_invest_strategy(gs, object(), '固定理财', rand=False, sig=_lsig())
    assert gs.active_strategies.value == ['固定理财']
    assert [e.spec.name for e in gs.effects.by_source(SOURCE_STRATEGY)] \
        == ['固定理财'], 'register_strategy 入册'
    assert gs.free_refresh_left.value == 2, 'burst 桥(free_refresh_burst)'
    gs2 = _make_gs(bench=[], equips=[])
    gain_invest_strategy(gs2, None, '固定理财', rand=False, sig=_lsig())
    assert gs2.active_strategies.value == ['固定理财'], '注册照常'
    assert gs2.effects.by_source(SOURCE_STRATEGY) == [], 'session=None 跳过'
    assert gs2.free_refresh_left.value is None, 'burst 零累加(零 Field 行)'


def test_on_strategy_gained_advisor_unlock() -> None:
    """advisor 解锁分支(on_strategy_gained):STRATEGY_GRANTS advisor=True
    卡(停云顾问)→ 解锁状态写入 + 效果串,不入席;非 advisor 卡不触发
    解锁;未收录卡零写(test_on_strategy_gained_unregistered_quiet 已锁)。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, '停云顾问', rand=False, sig=_lsig())
    assert effects == ('advisor_unlock:停云顾问:停云',)
    assert gs.unlocked_experts.value == ('停云',)
    assert bench_units_of(gs) == [], '顾问入商店非送单位'
    # 非 advisor 登记卡(摸个鱼吧II 直接给单位族,现役零效果体)不触发解锁
    gs2 = _make_gs(bench=[], equips=[])
    effects2 = on_strategy_gained(gs2, '摸个鱼吧II', rand=False, sig=_lsig())
    assert effects2 == ()
    assert gs2.unlocked_experts.value in (None, ()), '非 advisor 零解锁写'


def test_on_strategy_gained_unregistered_quiet() -> None:
    """未收录卡:查无效果安静不写(gain-chain §3 裁定④);效果表键集 =
    骇客单行 + 三箱分支卡(开箱分支由工厂自 _STRATEGY_BOX_GRANTS 生成,
    )。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert set(PICK_INVEST_EFFECTS) == {
        '骇客专家:银狼', '战术义眼++', '保守派', '快请专家·彩'}
    gs = _make_gs(bench=[('希儿', 1)], equips=[])
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '随便一张未收录卡', rand=False,
                                 sig=_lsig())
    assert effects == ()
    assert gs.write_seq == seq_before, '零写'


# ============================================================ 策略箱分支效果
# (策略卡获得时点占席道具发放,进阶武装箱首例;迭代
#  design §2.3)


@pytest.mark.parametrize('card', ['战术义眼++', '保守派', '快请专家·彩'])
def test_strategy_box_leg_effect_places_box(
        card: str, rows_sink: _RowSink) -> None:
    """三箱分支卡效果体(on_strategy_gained 分派):备战空槽 supply_box×1 +
    步串 ``box_grant:进阶武装箱(placed=True)``(沿骇客卡 steps 形态);
    确定发放(rand=False 走确定面,rng 不消费);道具非角色,单位域不变;
    正常路径零留证。"""
    gs = _make_gs(bench=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, card, rand=False, sig=_lsig(),
                                 rng=random.Random(0))
    assert effects == ('box_grant:进阶武装箱(placed=True)',), '单箱步串'
    slots = gs.bench.value.slots
    assert sum(1 for s in slots if s.kind == 'supply_box') == 1, '落备战空槽'
    assert bench_units_of(gs) == [], '道具非角色,单位域不变'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_strategy_box_leg_bench_full_overflow_name(
        rows_sink: _RowSink) -> None:
    """席满行为测试(名字经溢出落位真值暴露——BenchSlot kind 与道具名解耦,
    备战断言发现不了名字漂移):bench 满 9 → pick 开箱分支卡 → 溢出落位,
    overflow_card == '进阶武装箱'(BENCH_ITEM_NAMES 判 kind → 身份两分
    正确)。"""
    gs = _make_gs(bench=[('希儿', 1)] * 9)
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, '保守派', rand=False, sig=_lsig(),
                                 rng=random.Random(0))
    assert effects == ('box_grant:进阶武装箱(placed=True)',)
    assert gs.overflow_warning.value is True, '席满溢出落位(告警在场)'
    assert gs.overflow_card.value == '进阶武装箱', '溢出位身份 = 道具名'
    assert rows_sink.kinds() == [], '席满溢出落位是既定语义,零留证'


def test_strategy_box_grants_consistency_lock() -> None:
    """发放名单单一源一致性测试(阻断修订):效果体工厂表
    _STRATEGY_BOX_GRANTS 与登记表 STRATEGY_GRANTS 三卡 items_immediate
    逐对相等(表集同校验,防工厂表扩员而登记面漏登——两处独立字面量的
    名字漂移在备战断言不可见,唯此测试 + 席满溢出真值可暴露)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_BOX_GRANTS,
    )
    assert set(_STRATEGY_BOX_GRANTS) == {
        '战术义眼++', '保守派', '快请专家·彩'}
    for name, item in _STRATEGY_BOX_GRANTS.items():
        assert STRATEGY_GRANTS[name].items_immediate == (item,), \
            f'{name} 效果体发放名与登记表 items_immediate 漂移'


def test_gain_bench_item_three_landings(
        monkeypatch: pytest.MonkeyPatch, rows_sink: _RowSink) -> None:
    """公开原语落位三态 + 署名透传(design §2.2:与 on_env_gained 既有
    道具通道语义逐项一致——备战空槽 → 席满溢出落位 → 溢出位被占零写
    留证;producer 形参自定义署名透传写端,环境通道现役调用点不传即
    链缺省署名,行为不变形)。"""
    # 态 1:备战空槽 → True + supply_box 落位;自定义 producer 透传写端
    gs = _make_gs(bench=[])
    gs.prep_anchored = True
    captured: list[str | None] = []
    orig_write = gs.write_logic

    def rec_write(target, value, **kw) -> None:
        captured.append(kw.get('produced_by'))
        orig_write(target, value, **kw)

    monkeypatch.setattr(gs, 'write_logic', rec_write)
    assert gain_bench_item(gs, '进阶武装箱', rand=False, sig=_lsig(),
                           evidence='t', producer='CustomProducer') is True
    assert sum(1 for s in gs.bench.value.slots
               if s.kind == 'supply_box') == 1, '落备战空槽'
    assert captured == ['CustomProducer'], '自定义写端署名透传'
    # 态 2:席满 → True + 溢出落位两字段(身份 = 道具名)
    gs2 = _make_gs(bench=[('希儿', 1)] * 9)
    gs2.prep_anchored = True
    assert gain_bench_item(gs2, '进阶武装箱', rand=False, sig=_lsig(),
                           evidence='t') is True
    assert gs2.overflow_card.value == '进阶武装箱', '溢出位身份 = 道具名'
    assert gs2.overflow_warning.value is True
    # 态 3:溢出位被占 → False + 零写 + 留证(角色入账分支同款)
    gs3 = _make_gs(bench=[('希儿', 1)] * 9,
                   overflow_card='简易武装箱', overflow_warning=True)
    gs3.prep_anchored = True
    seq3 = gs3.write_seq
    assert gain_bench_item(gs3, '进阶武装箱', rand=False, sig=_lsig(),
                           evidence='t') is False
    assert gs3.write_seq == seq3, '零写'
    assert rows_sink.kinds() == [DEFECT_OVERFLOW_TAKEN], '零写一留证'


# ============================================================ 欢愉契约条件分支
# ============================================================ rider(银狼策划落地相正式模型)


def _joy_candidates() -> list[str]:
    """条件分支候选名集单一源(结构化在册数据,禁测试内第二抄本)。"""
    return [name for name, _text in ENV_GIFTS['欢愉契约'].chars_conditional]


def _joy_seed_for(candidate: str) -> int:
    """使 ``random.Random(seed).choice`` 选中指定候选的最小非负种子
    (采样面探针;rider 的采样注入语义与之同一)。"""
    cands = _joy_candidates()
    return next(s for s in range(200)
                if random.Random(s).choice(cands) == candidate)


def _joy_seeded_gs(env_name: str = '欢愉契约') -> GameState:
    """种子容器(缓存单例支冷建即含开局种子底座)+ 在册环境直写
    (观察链同写入口;'' = 保持种子初值空环境)。"""
    gs = game_state_of(StrategySession())
    if env_name:
        gs.observe(gs.active_env, env_name, sig=_SIG_OBS)
    return gs


def test_joy_rider_grant_channel_rand_anchor_and_coverage(
        rows_sink: _RowSink) -> None:
    """通道语义(授予体含采样 → rand=True 全通道 logic_rand,rand 形参
    优先于锚定闩):种子容器未闩臂授予落 bench source=logic_rand;置闩
    (测试专口直赋)后同路径 source 仍 = logic_rand;未闩臂观察覆盖落
    logic_rand_outcome 行、零 observe_vs_logic_mismatch(无失配网辖 =
    采样面本义,校准面 = outcome 行)。"""
    cands = _joy_candidates()
    seed = _joy_seed_for(cands[0])
    # 臂 1:未闩(种子底座窗)。
    gs = _joy_seeded_gs()
    out = report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), branch_type='unknown',
        rng=random.Random(seed))
    assert out.applied is True
    granted = [u.char_id for u in bench_units_of(gs) if u.char_id in cands]
    assert granted == [cands[0]], '恰一次授予,选中单位 = 注入 rng 采样值'
    assert gs.bench.source == 'logic_rand', '未闩授予落随机态'
    # 观察覆盖:差异落 logic_rand_outcome、零失配行(首观察静默覆盖)。
    sig_obs = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')
    other = BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9)
    consume_defect_sink()
    gs.observe(gs.bench, other, sig=sig_obs)
    kinds = [r['kind'] for r in consume_defect_sink()]
    assert 'observe_vs_logic_mismatch' not in kinds, '随机态覆盖零失配行'
    assert 'logic_rand_outcome' in kinds, '校准面 = outcome 行'
    # 臂 2:置闩后同路径 —— source 仍 = logic_rand(rand 优先于闩)。
    gs2 = _joy_seeded_gs()
    gs2.prep_anchored = True
    report_action_pick_planner_param(
        gs2, None, _lsig('CwScreenYinLang'), branch_type='unknown',
        rng=random.Random(seed))
    assert gs2.bench.source == 'logic_rand', '锚定后授予仍 logic_rand(采样面)'


def test_joy_rider_registry_gate(rows_sink: _RowSink) -> None:
    """在册判定:active_env 空(种子初值)/其他环境 → 零授予零写;欢愉
    契约在册 → 恰一次授予(正常授予零留证行,unknown 分支载荷各留一行)。"""
    cands = _joy_candidates()
    seed = _joy_seed_for(cands[0])
    gs = _joy_seeded_gs('')          # 空 = 种子初值
    seq = gs.write_seq
    report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), branch_type='unknown',
        rng=random.Random(seed))
    assert [u for u in bench_units_of(gs) if u.char_id in cands] == [], \
        '空环境零授予'
    assert gs.write_seq == seq, '空环境零容器写'
    gs.observe(gs.active_env, '公司契约', sig=_SIG_OBS)
    seq2 = gs.write_seq
    report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), branch_type='unknown',
        rng=random.Random(seed))
    assert [u for u in bench_units_of(gs) if u.char_id in cands] == [], \
        '其他环境零授予'
    assert gs.write_seq == seq2, '其他环境零容器写'
    gs.observe(gs.active_env, '欢愉契约', sig=_SIG_OBS)
    report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), branch_type='unknown',
        rng=random.Random(seed))
    granted = [u.char_id for u in bench_units_of(gs) if u.char_id in cands]
    assert granted == [cands[0]], '欢愉契约在册恰一次授予'
    kinds = rows_sink.kinds()
    # 台账除三条分支载荷行外,仅「观察覆盖种子('' → 公司契约)」的 outcome
    # 行(随机态覆盖预期内,与授予无关);授予自身零留证。
    assert kinds.count('planner_leg_unknown') == 3, 'unknown 分支载荷恰各一行'
    assert 'joy_conditional_grant_failed' not in kinds, '正常授予零授予失败留证'


def test_joy_rider_rng_injection_deterministic_and_reaches_both(
        rows_sink: _RowSink) -> None:
    """rng 注入(缺省 None = 实机未播种猜测语义,不在此测试面;注入面 =
    sim 消费契约):同 seed 同单位;两候选均可达(各候选都有使其经完整
    上报路径落位的种子)。"""
    cands = _joy_candidates()
    for c in cands:
        seed = _joy_seed_for(c)
        units_by_container = []
        for _ in range(2):
            gs = _joy_seeded_gs()
            report_action_pick_planner_param(
                gs, None, _lsig('CwScreenYinLang'), branch_type='unknown',
                rng=random.Random(seed))
            units_by_container += [u.char_id for u in bench_units_of(gs)
                                   if u.char_id in cands]
        assert units_by_container == [c, c], \
            f'seed={seed} 同 seed 同单位且恒选 {c}'


def test_joy_rider_fires_once_per_report_call(
        rows_sink: _RowSink) -> None:
    """触发计数封闭清单(单相即时上报,
    equip-immediate-report):一次上报 equip/upgrade/unknown 三条分支各恰一次
    授予(rider 在分支类型分派前,与分支类型无关);branch_type='' 直调 rider 仍触发
    (兜底形态)且走终态兜底零写(reason = unrouted_leg_zero_write)。"""
    cands = _joy_candidates()
    seed = _joy_seed_for(cands[0])
    expect = [random.Random(seed).choice(cands)]
    for branch, kw in (('equip', {'norm_item': '破解芯片'}),
                    ('upgrade', {}), ('unknown', {})):
        gs = _joy_seeded_gs()
        if branch == 'upgrade':
            # 升费分支前置:恰一枚 2★银狼LV.999(rider 候选与其无身份交叠)。
            slots = [BenchSlot(kind='unit',
                               unit=Unit(char_id='银狼LV.999', star=2))]
            slots += [BenchSlot(kind='empty')] * 8
            gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                       sig=_SIG_OBS)
        out = report_action_pick_planner_param(
            gs, None, _lsig('CwScreenYinLang'), branch_type=branch,
            rng=random.Random(seed), **kw)
        assert out.applied is True
        granted = [u.char_id for u in bench_units_of(gs)
                   if u.char_id in cands]
        assert granted == expect, f'{branch} 分支 rider 恰一次'
    # branch_type='' 直调落地相(兜底形态):rider 仍触发 + 终态兜底零写。
    gs4 = _joy_seeded_gs()
    out4 = report_action_pick_planner_param(
        gs4, None, _lsig('CwScreenYinLang'),
        rng=random.Random(seed))
    assert out4.applied is True
    assert out4.reason == 'unrouted_leg_zero_write', '终态兜底 reason'
    granted4 = [u.char_id for u in bench_units_of(gs4)
                if u.char_id in cands]
    assert granted4 == expect, '兜底形态 rider 仍触发恰一次'


def test_joy_rider_failure_best_effort(
        monkeypatch: pytest.MonkeyPatch, rows_sink: _RowSink) -> None:
    """授予失败语义(调用点级 best-effort,链零吞错纪律的显式例外):
    gain_character 注入异常 → 恰一行 joy_conditional_grant_failed 留证
    (expected/actual/evidence 对齐),分支类型分派照常执行(升费变换仍应用)
    ——授予与选项应用两条独立因果,授予失败不拖垮选项应用。"""
    import sr_od.application.currency_war.kernel.cw_action_report.\
        pick_planner as pp_mod
    gs = _make_gs(bench=[('银狼LV.999', 2)], equips=[])
    gs.observe(gs.active_env, '欢愉契约', sig=_SIG_OBS)

    def _boom(gs: GameState, name: str, star: int, **kw: object) -> object:
        raise RuntimeError('授予通道注入异常')

    monkeypatch.setattr(pp_mod, 'gain_character', _boom)
    out = report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), branch_type='upgrade',
        rng=random.Random(0))
    assert out.applied is True
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert ('银狼LV.999', 1) in units and ('银狼LV.999', 2) not in units, \
        '分支类型分派照常执行(升费变换仍应用)'
    fails = [r for r in rows_sink.rows
             if r['kind'] == 'joy_conditional_grant_failed']
    assert len(fails) == 1, '恰一行授予失败留证'
    row = fails[0]
    assert row['expected'] == '条件分支授予成功'
    assert '授予通道注入异常' in str(row['actual']), 'actual = 异常摘要'
    assert str(row['observed_evidence']).startswith('joy_conditional:')


def test_joy_rider_grant_chain_timing_merge(rows_sink: _RowSink) -> None:
    """时序测试:授予走获得链固定时序(落位 → 回调 → 单级合成)——bench
    预置两枚同候选单位,rider 授予第三枚 → 3 合 1 合成 2★(4 费单位正常
    参与合成,非旁路直写)。"""
    cands = _joy_candidates()
    seed = _joy_seed_for(cands[0])
    gs = _make_gs(bench=[(cands[0], 1), (cands[0], 1)], equips=[])
    gs.observe(gs.active_env, '欢愉契约', sig=_SIG_OBS)
    report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), branch_type='equip',
        norm_item='破解芯片',   # 表外件(无后果分支)→ 台账零留证行,焦点留给授予时序
        rng=random.Random(seed))
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [(cands[0], 2)], '三枚合成 2★(链固定时序,非旁路直写)'
    assert rows_sink.kinds() == [], '正常授予合成零留证行'


# ============================================================ LV.999 变换窗
# (银狼费用档变换;升费分支经 pick_planner 上报、上阵分支经 deploy_move 上报,
#  2026-09-18 定谳〔口述·权威〕:费用档不同时存在,分组键 (char_id, star)
#  无跨档歧义)


def test_upgrade_transform_exactly_one(rows_sink: _RowSink) -> None:
    """恰一枚 2★银狼LV.999 → 工作副本变换(2★→1★,身份保持),write_logic。"""
    gs = _make_gs(bench=[('希儿', 1), ('银狼LV.999', 2)], equips=[])
    out = report_action_pick_planner_param(gs, None, branch_type='upgrade',
                                           norm_item='',
                                           sig=_lsig('CwScreenYinLang'))
    assert out.applied is True
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert ('银狼LV.999', 1) in units, '变换为 1★(下一费用档,身份保持)'
    assert ('银狼LV.999', 2) not in units, '2★ 源已消费'
    assert ('希儿', 1) in units, '无关单位零差'
    assert gs.bench.source == 'logic', '确定面 write_logic'
    assert rows_sink.kinds() == [], '正常变换零留证行'


def test_upgrade_transform_multiple_flips_source(rows_sink: _RowSink) -> None:
    """多枚(二次升费现实可发)→ 禁猜:值不变翻来源 + 留证自愈。"""
    gs = _make_gs(bench=[('银狼LV.999', 2), ('银狼LV.999', 2)], equips=[])
    seq_before = gs.write_seq
    out = report_action_pick_planner_param(gs, None, branch_type='upgrade',
                                           norm_item='',
                                           sig=_lsig('CwScreenYinLang'))
    assert out.applied is True
    stars = sorted(u.star for u in bench_units_of(gs)
                   if u.char_id == '银狼LV.999')
    assert stars == [2, 2], '值不变(触发单位不可辨,不写变换)'
    assert gs.bench.source == 'logic_rand', '受影响域值不变翻来源'
    assert gs.write_seq > seq_before, '翻来源占写序(遥测行)'
    assert rows_sink.kinds() == ['planner_upgrade_ambiguous'], '留证行 kind'


def test_upgrade_transform_zero_or_unobserved(rows_sink: _RowSink) -> None:
    """零枚/未观察 → 不写 + 留证(真异常,照真失配响停,fail-closed 禁猜)。"""
    # 零枚(已观察但无 2★ 源)。
    gs = _make_gs(bench=[('银狼LV.999', 1)], equips=[])
    seq_before = gs.write_seq
    out = report_action_pick_planner_param(gs, None, branch_type='upgrade',
                                           norm_item='',
                                           sig=_lsig('CwScreenYinLang'))
    assert out.applied is False and out.reason == 'upgrade_source_missing'
    assert gs.write_seq == seq_before, '零枚不写'
    assert rows_sink.kinds() == ['planner_upgrade_source_missing']
    # 未观察(三容器全 None)同态。
    gs2 = _make_gs()
    out2 = report_action_pick_planner_param(gs2, None, branch_type='upgrade',
                                            norm_item='',
                                            sig=_lsig('CwScreenYinLang'))
    assert out2.applied is False and out2.reason == 'upgrade_source_unobserved'
    assert rows_sink.kinds() == ['planner_upgrade_source_missing',
                                 'planner_upgrade_source_missing']


def test_upgrade_cascade_lv999_normal_merge(rows_sink: _RowSink) -> None:
    """涉 LV.999 级联合并正常推演测试(费用档不同时存在——分组键
    (char_id, star) 无跨档歧义):变换出的 1★ 凑满同星组 → 与普通单位
    同语义升星(write_logic 逐级落行,零留证行)。"""
    gs = _make_gs(bench=[('银狼LV.999', 2), ('银狼LV.999', 1),
                         ('银狼LV.999', 1)], equips=[])
    out = report_action_pick_planner_param(gs, None, branch_type='upgrade',
                                           norm_item='',
                                           sig=_lsig('CwScreenYinLang'))
    assert out.applied is True
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('银狼LV.999', 2)], '正常推演:3×1★ 合成 → 2★(普通单位同语义)'
    assert gs.bench.source == 'logic', '级联确定面 write_logic'
    assert rows_sink.kinds() == [], '正常推演零留证行'


def test_deploy_transform_window_3star_lv999(rows_sink: _RowSink) -> None:
    """上阵变换窗:3★银狼LV.999 拖上场 → 落场写下一费用档 1★(非 3★
    原样)+ bench 摘除源;级联无组可合 → 零额外行。"""
    gs = _make_gs(bench=[('银狼LV.999', 3), ('希儿', 1)],
                  front=[Unit(char_id='黑塔', star=1)], equips=[])
    out = report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=2,
                                    faction=''),
        _lsig('CwActionDeployMoveOp'))
    assert out.applied is True
    assert gs.deployed.value.front_slots[1].char_id == '银狼LV.999', '落场'
    assert gs.deployed.value.front_slots[1].star == 1, '变换窗:落场写 1★(下一费用档)'
    assert gs.deployed.source == 'logic'
    assert gs.lv999_cost_tier.value == 4, '上阵变费档行(3费档 3★ 上场 → 4)'
    bench_units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert ('希儿', 1) in bench_units and \
        ('银狼LV.999', 3) not in bench_units, 'bench 源已摘除'
    assert rows_sink.kinds() == [], '无组可合零留证'


def test_deploy_non_target_identity(rows_sink: _RowSink) -> None:
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
        moved = gs.deployed.value.back_slots[0]
        assert moved.star == bench_units[idx][1], \
            f'恒等搬运保持 {bench_units[idx]} 星级'
        assert gs.lv999_cost_tier.value is None, '非目标恒等搬运零档写'
        assert rows_sink.kinds() == []


def test_deploy_cascade_lv999_normal_merge(rows_sink: _RowSink) -> None:
    """上阵级联正常推演测试(同 2026-09-18 定谳,普通单位同语义):变换出的
    1★ 落场与备战 2× 1★ 凑满全场同星组 → 合成载体 = 场上那张(场上优先,
    _merge_bench 语义),备战素材被消费腾槽,write_logic 逐级落行。"""
    gs = _make_gs(bench=[('银狼LV.999', 3), ('银狼LV.999', 1),
                         ('银狼LV.999', 1)], front=[], equips=[])
    out = report_action_deploy_move_param(
        gs, CwActionDeployMoveParam(bench_idx=0, to_row='front', to_slot=1,
                                    faction=''),
        _lsig('CwActionDeployMoveOp'))
    assert out.applied is True
    assert gs.deployed.value.front_slots[0].star == 2, '级联正常推演:场上载体 1★→2★'
    assert gs.lv999_cost_tier.value == 4, '上阵变费档行(级联同批落)'
    bench_units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert bench_units == [], '备战素材被合成消费腾槽'
    assert gs.bench.source == 'logic' \
        and gs.deployed.source == 'logic', '受影响域逐级落行(write_logic)'
    assert rows_sink.kinds() == [], '正常推演零留证行'


# ============================================================ 选卡上报落地
# (投资策略屏/portal 经获得链落账;按 idx 取名契约 = op-layer.md §1.1
#  观察标准化门)


def test_invest_strategy_landing_hacker_wolf(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """策略屏选择即时上报:点完即写入 = 注册按名字去重追加
    (active_strategies)+ 登记分支(session=None 跳过)+ 效果分派
    骇客专家:银狼(advisor 解锁分支:银狼入池权威写,官方卡文 = 加入
    商店非送单位,原入席分支退役 + 改件 gain_equipment 采样入栏,后果表件
    经 on_equipment_gained 回调送单位);翻来源域集不含 gold(对抗审⑪)。"""
    # 场景一:改件采样 = 破解芯片(表外件,链内无后果分支)。
    monkeypatch.setattr(random.Random, 'choice',
                        lambda self, seq: '破解芯片')
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=[], gold=30)
    seq_before = gs.write_seq
    param = CwActionPickInvestStrategyParam(idx=0, norm_name='骇客专家:银狼')
    out = report_action_pick_invest_strategy_param(
        gs, param, _lsig('CwActionPickInvestOp'))
    assert out.applied is True and out.reason == 'gain_chain_applied'
    assert gs.write_seq > seq_before, '分步更新各占写序(多遥测行 = 预期)'
    assert gs.active_strategies.value == ['骇客专家:银狼'], '注册入持卡面'
    # 投资策略屏在生产链序(简报→投资环境→投资策略→备战)位于锚定(备战
    # heavy)之前,通道规则「未锚定 → 随机态」使确定入口链写改道
    # logic_rand(开局种子底座与锚定闩批行为申报,首观察静默覆盖)。
    assert gs.active_strategies.source == 'logic_rand'
    assert gs.unlocked_experts.value == ('银狼',), 'advisor 解锁分支写入'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('银狼', 1), ('银狼', 1)], \
        '顾问入商店非送单位,预置单位保持 1★'
    assert gs.equips.value == ['破解芯片'], '随机改件入栏(采样值)'
    assert gs.equips.source == 'logic_rand', '随机分支 logic_rand'
    assert gs.gold.source == 'observation' and gs.gold.value == 30, \
        'gold 不翻来源(改件链域集裁剪,无噪声行)'
    assert rows_sink.kinds() == [], '解锁权威写,零台账申报行'
    # 去重:同卡二次上报 → 持卡面跳写不重复;效果分支零闸照走(裁定⑩)。
    seq2 = gs.write_seq
    report_action_pick_invest_strategy_param(
        gs, param, _lsig('CwActionPickInvestOp'))
    assert gs.active_strategies.value == ['骇客专家:银狼'], '持卡面单份(去重)'
    assert gs.unlocked_experts.value == ('银狼',), '解锁幂等(不重复追加)'
    assert gs.write_seq > seq2, '效果分支照走(零幂等闸)'
    # 场景二:改件采样命中后果表三件(Max 件张力形状)→ 回调后果分支
    #(gain_equipment → on_equipment_gained 回调 → gain_character 送单位;
    # 银狼LV.999 非专家顾问,解锁面零写)。
    monkeypatch.setattr(random.Random, 'choice',
                        lambda self, seq: '数据拷贝仪Max')
    gs3 = _make_gs(bench=[('希儿', 1)], equips=[])
    out3 = report_action_pick_invest_strategy_param(
        gs3, param, _lsig('CwActionPickInvestOp'))
    assert out3.applied is True
    assert gs3.equips.value == ['数据拷贝仪Max'], '改件入栏'
    units3 = [(u.char_id, u.star) for u in bench_units_of(gs3)]
    assert ('银狼LV.999', 1) in units3, '回调后果:改件送出 1★ 银狼LV.999'
    assert '银狼LV.999' not in (gs3.unlocked_experts.value or ()), \
        '非专家送出单位不触发解锁'


def test_invest_strategy_landing_invalid_payload(
        rows_sink: _RowSink) -> None:
    """无效载荷拒绝(即时上报契约配套):归一后空/'?' = 零写 + 缺陷留证,
    持卡面不收无效名。"""
    for bad in ('', '?'):
        gs = _make_gs(bench=[('希儿', 1)], equips=['幸运星'])
        seq_before = gs.write_seq
        out = report_action_pick_invest_strategy_param(
            gs, CwActionPickInvestStrategyParam(idx=0, norm_name=bad),
            _lsig('CwActionPickInvestOp'))
        assert out.applied is True
        assert gs.active_strategies.value in (None, []), '零写'
        assert gs.write_seq == seq_before
    assert rows_sink.kinds() == ['pick_invest_invalid_payload',
                                 'pick_invest_invalid_payload']


def test_invest_portal_landing_no_card_pollution(
        rows_sink: _RowSink) -> None:
    """portal 确认(欢愉契约)整支走获得链:active_env 写(选择事实落地
    经 gain_invest_env)+ 银狼LV.999 1★ 入席递归(on_env_gained
    chars_immediate 唯一分支——条件分支临时翻来源闩已撤:零翻面、零
    provisional 标记行,正式模型 = 银狼策划上报条件分支 rider,测试面 =
    本文件 rider 组);禁入 active_strategies(防 portal 卡污染持卡面)。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['幸运星'], gold=30)
    # 按 idx 取名契约(op-layer.md §1.1 观察标准化门):env 上报自容器
    # invest_env_opts 取标准名——播种容器承载(名字 = 原 norm_name 语义)。
    gs.write_logic(gs.invest_env_opts, ['彩虹时代', '欢愉契约'],
                   produced_by='test', sig=_lsig('CwScreenYinLang'))
    param = CwActionPickInvestEnvParam(idx=1, norm_name='欢愉契约')
    out = report_action_pick_invest_env_param(
        gs, param, _lsig('CwActionPickInvestOp'))
    assert out.applied is True and out.reason == 'gain_chain_applied'
    assert gs.active_strategies.value in (None, []), '双屏分流防污染测试'
    assert gs.active_env.value == '欢愉契约', '选择事实落地经获得链写'
    # 投资环境屏同在锚定前(未锚定期):链写改道 logic_rand(通道规则)。
    assert gs.active_env.source == 'logic_rand'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('希儿', 1), ('银狼LV.999', 1)], \
        'immediate 分支唯一(撤闩后 on_env_gained 仅 chars_immediate)'
    assert gs.bench.source == 'logic_rand', '送卡链写未锚定期改道随机态'
    assert gs.equips.source == 'observation' \
        and gs.equips.value == ['幸运星'], '零翻面(equips 值与来源均不动)'
    assert rows_sink.kinds() == [], 'provisional 标记行零发射(撤闩后台账零新增)'


def test_invest_portal_env_gifts_full_access(
        rows_sink: _RowSink) -> None:
    """ENV_GIFTS 全量即时发放经落地相可用(此前仅欢愉契约有容器写分支,
    现契约类 chars_immediate 全部经链生效;表外环境安静不写)。
    公司契约 = 翡翠/砂金 逐个 1★ 入席递归。"""
    gs = _make_gs(bench=[], equips=[])
    # 按 idx 取名契约(op-layer.md §1.1):上报自容器取标准名,播种承载。
    gs.write_logic(gs.invest_env_opts, ['公司契约'],
                   produced_by='test', sig=_lsig('CwScreenYinLang'))
    out = report_action_pick_invest_env_param(
        gs, CwActionPickInvestEnvParam(idx=0, norm_name='公司契约'),
        _lsig('CwActionPickInvestOp'))
    assert out.applied is True and out.reason == 'gain_chain_applied'
    assert gs.active_env.value == '公司契约'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('翡翠', 1), ('砂金', 1)], 'chars_immediate 逐个入席'
    # 未锚定期(投资环境屏)送卡链写被通道规则改道 logic_rand。
    assert gs.bench.source == 'logic_rand'
    assert rows_sink.kinds() == [], '非欢愉契约零留证行'


def test_invest_portal_env_gifts_summon_unit(rows_sink: _RowSink) -> None:
    """召唤单位环境(三星佩佩)经落地相可用:portal 确认整支走获得链,
    佩佩入席(公司契约全量接入测试同构;T-16 §4 锁 3)。"""
    gs = _make_gs(bench=[], equips=[])
    # 按 idx 取名契约(op-layer.md §1.1):上报自容器取标准名,播种承载。
    gs.write_logic(gs.invest_env_opts, ['三星佩佩'],
                   produced_by='test', sig=_lsig('CwScreenYinLang'))
    out = report_action_pick_invest_env_param(
        gs, CwActionPickInvestEnvParam(idx=0, norm_name='三星佩佩'),
        _lsig('CwActionPickInvestOp'))
    assert out.applied is True and out.reason == 'gain_chain_applied'
    assert gs.active_env.value == '三星佩佩'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('佩佩', 1)], '召唤单位经链入席'
    # 未锚定期(投资环境屏)送卡链写被通道规则改道 logic_rand。
    assert gs.bench.source == 'logic_rand'
    assert rows_sink.kinds() == [], '零留证行'


def test_invest_portal_env_gifts_summon_unit_cuxing(
        rows_sink: _RowSink) -> None:
    """召唤单位环境(粗星佩佩)经落地相可用:portal 确认整支走获得链,
    佩佩入席(姊妹卡三星佩佩测试同构;T-17 §4 锁 3)。"""
    gs = _make_gs(bench=[], equips=[])
    # 按 idx 取名契约(op-layer.md §1.1):上报自容器取标准名,播种承载。
    gs.write_logic(gs.invest_env_opts, ['粗星佩佩'],
                   produced_by='test', sig=_lsig('CwScreenYinLang'))
    out = report_action_pick_invest_env_param(
        gs, CwActionPickInvestEnvParam(idx=0, norm_name='粗星佩佩'),
        _lsig('CwActionPickInvestOp'))
    assert out.applied is True and out.reason == 'gain_chain_applied'
    assert gs.active_env.value == '粗星佩佩'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('佩佩', 1)], '召唤单位经链入席'
    # 未锚定期(投资环境屏)送卡链写被通道规则改道 logic_rand。
    assert gs.bench.source == 'logic_rand'
    assert rows_sink.kinds() == [], '零留证行'


def test_invest_unregistered_card_unchanged(
        rows_sink: _RowSink) -> None:
    """未收录卡行为回归测试:策略屏未收录卡只走第一步(入表零效果);portal
    表外环境 = active_env 选择事实写(经获得链,写时点随选卡上报迁移)+
    效果面安静不写(表外环境零入席)。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['幸运星'])
    seq_before = gs.write_seq
    out = report_action_pick_invest_strategy_param(
        gs, CwActionPickInvestStrategyParam(idx=0, norm_name='随便一张未收录卡'),
        _lsig('CwActionPickInvestOp'))
    assert out.applied is True
    assert gs.active_strategies.value == ['随便一张未收录卡'], \
        '未收录策略只走第一步'
    assert gs.write_seq == seq_before + 1, '恰一行遥测(持卡面),零效果分支'
    # portal 表外环境 = 选择事实写 + 零效果。
    gs2 = _make_gs(bench=[('希儿', 1)], equips=['幸运星'])
    # 按 idx 取名契约(op-layer.md §1.1):上报自容器取标准名,播种承载。
    gs2.write_logic(gs2.invest_env_opts, ['随便一个未收录环境'],
                    produced_by='test', sig=_lsig('CwScreenYinLang'))
    seq2_before = gs2.write_seq
    out2 = report_action_pick_invest_env_param(
        gs2, CwActionPickInvestEnvParam(idx=0, norm_name='随便一个未收录环境'),
        _lsig('CwActionPickInvestOp'))
    assert out2.applied is True
    assert gs2.active_env.value == '随便一个未收录环境', \
        '选择事实落地写(表外环境同样经链注册)'
    # 注册尾段恒两行:active_env 选择事实 + node_seq_by_plane 场字段
    #(表外环境落默认表,字段恒全量无半态;写点唯一 = 获得链尾段)。
    assert gs2.write_seq == seq2_before + 2, \
        '恰 active_env + node_seq_by_plane 两行(零其他效果分支)'
    assert gs2.node_seq_by_plane.value == dict(PLANE_NODE_TABLES), \
        '表外环境场字段落默认表'
    assert bench_units_of(gs2) and \
        [(u.char_id, u.star) for u in bench_units_of(gs2)] == [('希儿', 1)], \
        '表外环境零入席(安静不写)'
    assert gs2.active_strategies.value in (None, [])


def test_grant_channel_consequence_anchor(
        monkeypatch: pytest.MonkeyPatch,
        rows_sink: _RowSink) -> None:
    """好运令牌 grant_equip_item 渠道同纳后果链锚(§2.2 全渠道):后果
    函数对表外件零写零行为(令牌推荐四件域恒表外 = 渠道零差);表内件
    直测后果应用(送出 1★ 银狼LV.999 进备战席)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_session

    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        apply_equip_acquire_consequence,
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


# ============================================================ 卖/换动作上报
# (v2 族契约直测:出参 applied/reason/income + gold/bench/front_row/
#  back_row/board/equips 域写回 + 未辖域零写;历史金样对照已按到期兑现
#  改活等价测试,初态本地构造经观察写入口。)

_TR_SIG_OBS = ChannelSig(family='obs', actor='cw_observation', mode='read')
_TR_SIG_LOGIC = ChannelSig(family='logic_action', actor='MandateV1Strategy',
                           mode='compute')

#: 初态共用底稿(原金样捕获帧 p1-r3 battle / lv5 / xp(4,20) / hp80 /
#: 金 10);退款真值从注册表现算(1★ 银枝 cost 2),不手抄常数。
_TR_REFUND = sell_refund(1, bench_char_cost(Unit(char_id='银枝', star=1)))

_TR_EMPTY_SHOP = ShopPayload(cards=[ShopSlot(kind='empty')] * 5,
                             refresh_probs={})


def _tr_unit(char_id: str, slot: int, *,
             equips: list[str] | None = None) -> Unit:
    return Unit(char_id=char_id, star=1, equips=list(equips or []))


def _tr_gs_with(*, bench: list[Unit], front: list[Unit], gold: int = 10,
                equips: list[str] | None = None,
                board: dict[str, int] | None = None) -> GameState:
    """初态本地构造(共用底稿 + 案给定域,全部经观察写入口,生产同路)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='battle'),
               sig=_TR_SIG_OBS)
    slots = [BenchSlot(kind='empty')] * 9
    for i, u in enumerate(bench):
        if u is not None:
            slots[i] = BenchSlot(kind='unit', unit=u)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_TR_SIG_OBS)
    gs.observe(gs.deployed, _dvs(list(front), []), sig=_TR_SIG_OBS)
    if board is not None:
        gs.observe(gs.board, dict(board), sig=_TR_SIG_OBS)
    gs.observe(gs.back_layout, 6, sig=_TR_SIG_OBS)
    gs.observe(gs.gold, gold, sig=_TR_SIG_OBS)
    gs.observe(gs.level, 5, sig=_TR_SIG_OBS)
    gs.observe(gs.xp, (4, 20), sig=_TR_SIG_OBS)
    gs.observe(gs.hp, 80, sig=_TR_SIG_OBS)
    gs.observe(gs.shop, ShopPayload(cards=[ShopSlot(kind='empty')] * 5,
                                     refresh_probs={}), sig=_TR_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_TR_SIG_OBS)
    return gs


def _tr_bench_units(gs: GameState) -> list[tuple[int, str]]:
    """bench 视图 → (槽下标, char_id) 紧缩断言面。"""
    view = gs.bench.value
    assert view is not None
    return [(i, s.unit.char_id) for i, s in enumerate(view.slots)
            if s.kind == 'unit' and s.unit is not None]


def _tr_row_pairs(gs) -> list[tuple[str, int]]:
    """前排视图 → (char_id, 物理槽号) 断言面(位置 = 子表下标 + 1 派生)。"""
    view = gs.deployed.value
    return [(u.char_id, i + 1) for i, u in enumerate(
        getattr(view, 'front_slots', None) or []) if u is not None]


# 案表:(案名, 动作构造, 初态构造参数, applied, reason(None=不辖),
# income(None=不辖 | 数值=现算退款断言), 期望金, 期望 bench 紧缩,
# 期望 front 行(char_id, slot) | None=断言不变, 期望 board | None=未观察
# 不写, 期望 equips | None=未观察不写)。
_TR_CASES = [
    pytest.param(
        'sellbench_apply_equips',
        lambda: CwActionSellBenchParam(bench_idx=0, expect='银枝', reason='test'),
        {'bench': [_tr_unit('银枝', 1, equips=['以太钻头']),
                   _tr_unit('爻光', 2)],
         'front': [], 'equips': ['光速螺旋桨·特权']},
        True, None, _TR_REFUND, 10 + _TR_REFUND,
        [(1, '爻光')], None, None, ['光速螺旋桨·特权', '以太钻头'],
        id='sellbench-apply-equips'),
    pytest.param(
        'sellbench_stale_reject',
        lambda: CwActionSellBenchParam(bench_idx=0, expect='刃', reason='test'),
        {'bench': [_tr_unit('银枝', 1), _tr_unit('爻光', 2)], 'front': []},
        False, 'stale_proposal:刃!=银枝', None, 10,
        [(0, '银枝'), (1, '爻光')], None, None, None,
        id='sellbench-stale-reject'),
    pytest.param(
        'selldeployed_apply',
        lambda: CwActionSellDeployedParam(deployed_idx=0, expect='银枝', reason='test'),
        {'bench': [], 'front': [_tr_unit('银枝', 1, equips=['以太钻头'])],
         'board': {'星间旅人': 1, '群攻': 1}},
        True, 'test', _TR_REFUND, 10 + _TR_REFUND,
        [], [], {}, ['以太钻头'],
        id='selldeployed-apply'),
    pytest.param(
        'selldeployed_stale_reject',
        lambda: CwActionSellDeployedParam(deployed_idx=0, expect='刃', reason='test'),
        {'bench': [], 'front': [_tr_unit('银枝', 1)],
         'board': {'星间旅人': 1, '群攻': 1}},
        False, 'stale_proposal:刃!=银枝', None, 10,
        [], [('银枝', 1)], {'星间旅人': 1, '群攻': 1}, None,
        id='selldeployed-stale-reject'),
    pytest.param(
        'swapdeploy_apply',
        lambda: CwActionSwapDeployParam(deployed_idx=0, bench_idx=0, reason='test'),
        {'bench': [_tr_unit('爻光', 1), _tr_unit('停云', 2)],
         'front': [_tr_unit('银枝', 1)],
         'board': {'星间旅人': 1, '群攻': 1}},
        True, 'test', None, 10,
        [(0, '银枝'), (1, '停云')], [('爻光', 1)],
        {'仙舟': 1, '欢愉': 1}, None,
        id='swapdeploy-apply'),
    pytest.param(
        'swapdeploy_idx_reject',
        lambda: CwActionSwapDeployParam(deployed_idx=5, bench_idx=0, reason='test'),
        {'bench': [_tr_unit('爻光', 1)], 'front': [_tr_unit('银枝', 1)],
         'board': {'星间旅人': 1, '群攻': 1}},
        False, 'idx_out_of_range:d5/b0', None, 10,
        [(0, '爻光')], [('银枝', 1)], {'星间旅人': 1, '群攻': 1}, None,
        id='swapdeploy-idx-reject'),
]


def _tr_report(gs: GameState, action) -> object:
    """按动作类型直调对应上报函数(每动作一函数,零聚合分派)。"""
    if isinstance(action, CwActionSellBenchParam):
        return report_action_sell_bench_param(gs, action, sig=_TR_SIG_LOGIC)
    if isinstance(action, CwActionSellDeployedParam):
        return report_action_sell_deployed_param(gs, action, sig=_TR_SIG_LOGIC)
    if isinstance(action, CwActionSwapDeployParam):
        return report_action_swap_deploy_param(gs, action, sig=_TR_SIG_LOGIC)
    raise AssertionError(f'未覆盖的动作类型:{type(action).__name__}')


@pytest.mark.parametrize(
    'case_name,make_action,init_kw,applied,reason,income,gold,'
    'bench_expect,front_expect,board_expect,equips_expect',
    _TR_CASES)
def test_sell_swap_transfer_v2_contract(
        case_name: str, make_action, init_kw: dict,
        applied: bool, reason: str | None,
        income: int | None, gold: int,
        bench_expect: list[tuple[int, str]],
        front_expect: list[tuple[str, int]] | None,
        board_expect: dict[str, int] | None,
        equips_expect: list[str] | None) -> None:
    """v2 族直测(案表驱动;断言域 = 平移契约申报表全集):出参契约
    (applied/reason/income)+ gold/bench/rows/board/equips 域写回 +
    未辖域(hp/level/xp/shop/back_layout)零写。"""
    gs = _tr_gs_with(**init_kw)
    out = _tr_report(gs, make_action())
    # —— 出参契约(LogicOutcome;拒绝 = applied=False + reason 零写)——
    assert out.applied is applied, f'{case_name}: applied'
    if reason is not None:
        assert out.reason == reason, f'{case_name}: reason'
    if income is not None:
        assert out.income == income, f'{case_name}: income(注册表现算)'
    # —— 域写回 ——
    assert gs.gold.value == gold, f'{case_name}: gold'
    assert _tr_bench_units(gs) == bench_expect, f'{case_name}: bench'
    if front_expect is not None:
        assert _tr_row_pairs(gs) == front_expect, \
            f'{case_name}: front_row'
    if board_expect is not None:
        assert gs.board.value == board_expect, f'{case_name}: board'
    if equips_expect is not None:
        assert gs.equips.value == equips_expect, \
            f'{case_name}: equips(回收进 owned 池尾)'
    # —— 未辖域零写(域封闭分支;初态常量即期望)——
    assert gs.hp.value == 80 and gs.level.value == 5 \
        and gs.xp.value == (4, 20), f'{case_name}: hp/level/xp 零写'
    assert gs.back_layout.value == 6, f'{case_name}: back_layout 零写'
    assert gs.shop.value == _TR_EMPTY_SHOP, f'{case_name}: shop 零写'


# ============================================================ 即时装备通道
# (环境确定性具名装备发放:equips_immediate 装备入账分支 + items_immediate
# 开箱分支;迭代 2026-09-23-invest-effects-calc T-31 红钻贵族)


def test_env_gift_equip_leg_card_text_order(rows_sink: _RowSink) -> None:
    """发放分支(T-31 设计 §4 锁 2,on_env_gained 直构 + 种子底座):equips
    尾追 '红钻'、bench 落 1 个 supply_box 槽件;效果串两行按卡文序
    (``equip_gift:红钻`` 先、``item_gift:简易武装箱`` 后——装备支位于
    道具支之前,遥测序与卡文对齐)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '红钻贵族', rand=False, sig=_lsig())
    assert out == ('equip_gift:红钻', 'item_gift:简易武装箱'), \
        '效果串序 = 卡文序(钻先箱后)'
    assert list(gs.equips.value) == ['红钻'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert len(boxes) == 1, '箱落 1 个 supply_box 槽件'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_env_gift_equip_leg_callback_zero_effect(
        rows_sink: _RowSink) -> None:
    """回调零效果(T-31 设计 §4 锁 4):红钻 ∈ EQUIP_ACQUIRE_CONSEQUENCES
    表外 → 获得链零子链;红钻非财富宝钻 → 宝钻数值回调族
    (diamond_count/deploy_cap/back_layout)零变化(on_diamond_acquired
    非财富宝钻早退在册,且唯一调用点 = sim 深井发放路径,本链不经)。"""
    gs = _make_gs(bench=[], equips=[])
    diamond0 = gs.diamond_count.value
    cap0 = gs.deploy_cap.value
    back0 = gs.back_layout.value
    on_env_gained(gs, None, '红钻贵族', rand=False, sig=_lsig())
    assert gs.diamond_count.value == diamond0, '宝钻计数零写'
    assert gs.deploy_cap.value == cap0, '上阵上限零写'
    assert gs.back_layout.value == back0, '后排格数零写'
    assert list(gs.equips.value) == ['红钻'], '装备照常入栏(主分支生效)'


def test_env_gift_box_leg_overflow_equips_unaffected() -> None:
    """席满溢出(T-31 设计 §4 锁 7):bench 9 席全占时箱走溢出落位两字段
    (现役 _place_bench_item 语义);装备入账分支不受席影响(equips 无席概念,
    照常入栏)。"""
    gs = _make_gs(bench=[], equips=[],
                  overflow_card='', overflow_warning=False)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='supply_box')] * 9,
                         capacity=9),
               sig=_SIG_OBS)
    out = on_env_gained(gs, None, '红钻贵族', rand=False, sig=_lsig())
    assert out == ('equip_gift:红钻', 'item_gift:简易武装箱'), \
        '效果串恒登记(与落位成败解耦)'
    assert list(gs.equips.value) == ['红钻'], '装备入账分支不受席影响'
    assert gs.overflow_warning.value is True, '席满溢出告警置位'
    assert gs.overflow_card.value == '简易武装箱', '溢出位身份 = 箱名'


def test_env_gift_channel_selection_both_states(rows_sink: _RowSink) -> None:
    """写通道择道(T-31 设计 §4 锁 8):装备入账分支 rand=True 硬编码 → 未锚定
    与锚定两态均走 write_logic_rand(equips.source 恒 'logic_rand',
    猜测语义不进失配网);开箱分支 rand=False 透传 → 未锚定 'logic_rand'、
    锚定 'logic' 确定面(对照分支;T-2 实机定谳纪律)。"""
    gs = _make_gs(bench=[], equips=[])
    on_env_gained(gs, None, '红钻贵族', rand=False, sig=_lsig())
    assert gs.equips.source == 'logic_rand', '装备入账分支未锚定随机态'
    assert gs.bench.source == 'logic_rand', '开箱分支未锚定随机态'
    gs2 = _make_gs(bench=[], equips=[])
    gs2.prep_anchored = True
    on_env_gained(gs2, None, '红钻贵族', rand=False, sig=_lsig())
    assert gs2.equips.source == 'logic_rand', \
        '装备入账分支锚定仍随机态(rand=True 硬编码,裁定语义)'
    assert gs2.bench.source == 'logic', '开箱分支锚定确定面(rand=False 透传)'
    assert rows_sink.kinds() == [], '两态零申报行(不进失配网)'


# —— 蓝钻贵族姊妹行(2026-09-23-invest-effects-calc T-32;机制件零改动,
# 消费锁与 T-31 同构,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_blue_diamond(rows_sink: _RowSink) -> None:
    """发放分支(T-32 设计 §4 锁 2,on_env_gained 直构;容器前置同 T-31
    判例 = 观察/逻辑写组装,equips/bench 非 None 才落):equips 尾追
    '蓝钻'、bench 落 1 个 supply_box 槽件;效果串两行按卡文序
    (``equip_gift:蓝钻`` 先、``item_gift:简易武装箱`` 后)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '蓝钻贵族', rand=False, sig=_lsig())
    assert out == ('equip_gift:蓝钻', 'item_gift:简易武装箱'), \
        '效果串序 = 卡文序(钻先箱后)'
    assert list(gs.equips.value) == ['蓝钻'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert len(boxes) == 1, '箱落 1 个 supply_box 槽件'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_env_gift_blue_callback_zero_effect(rows_sink: _RowSink) -> None:
    """回调零效果(T-32 设计 §4 锁 3):蓝钻 ∈ EQUIP_ACQUIRE_CONSEQUENCES
    表外 → 获得链零子链;蓝钻非财富宝钻 → 宝钻数值回调族
    (diamond_count/deploy_cap/back_layout)零变化(on_diamond_acquired
    非财富宝钻早退在册,红钻贵族同判)。"""
    gs = _make_gs(bench=[], equips=[])
    diamond0 = gs.diamond_count.value
    cap0 = gs.deploy_cap.value
    back0 = gs.back_layout.value
    on_env_gained(gs, None, '蓝钻贵族', rand=False, sig=_lsig())
    assert gs.diamond_count.value == diamond0, '宝钻计数零写'
    assert gs.deploy_cap.value == cap0, '上阵上限零写'
    assert gs.back_layout.value == back0, '后排格数零写'
    assert list(gs.equips.value) == ['蓝钻'], '装备照常入栏(主分支生效)'


def test_env_gift_dual_diamond_no_cross_name(rows_sink: _RowSink) -> None:
    """双钻并存(T-32 设计 §4 锁 7):红钻贵族/蓝钻贵族两姊妹条目各自
    发放各自具名件互不串名——登记形状互斥(装备入账分支各含自家钻)+ 行为面
    两条链各自产出单件自家装备、效果串互不含对方名(环境单值一局一个,
    并存 = 登记面两行齐备、形状与产出双向不串)。"""
    assert ENV_GIFTS['红钻贵族'].equips_immediate == ('红钻',)
    assert ENV_GIFTS['蓝钻贵族'].equips_immediate == ('蓝钻',)
    gs_r = _make_gs(bench=[], equips=[])
    out_r = on_env_gained(gs_r, None, '红钻贵族', rand=False, sig=_lsig())
    gs_b = _make_gs(bench=[], equips=[])
    out_b = on_env_gained(gs_b, None, '蓝钻贵族', rand=False, sig=_lsig())
    assert out_r == ('equip_gift:红钻', 'item_gift:简易武装箱'), \
        '红钻链效果串零串名'
    assert out_b == ('equip_gift:蓝钻', 'item_gift:简易武装箱'), \
        '蓝钻链效果串零串名'
    assert list(gs_r.equips.value) == ['红钻'], '红钻链入栏零串名'
    assert list(gs_b.equips.value) == ['蓝钻'], '蓝钻链入栏零串名'
    assert rows_sink.kinds() == [], '双链零申报行'


def test_env_gift_blue_channel_selection_both_states(
        rows_sink: _RowSink) -> None:
    """写通道择道(T-32 设计 §4 锁 8,蓝钻行骑 T-31 同一代码路径):
    装备入账分支 rand=True 硬编码 → 未锚定与锚定两态均 write_logic_rand
    (equips.source 恒 'logic_rand',随机态语义不进失配网);开箱分支
    rand=False 透传 → 未锚定 'logic_rand'、锚定 'logic' 确定面(对照分支)。"""
    gs = _make_gs(bench=[], equips=[])
    on_env_gained(gs, None, '蓝钻贵族', rand=False, sig=_lsig())
    assert gs.equips.source == 'logic_rand', '装备入账分支未锚定随机态'
    assert gs.bench.source == 'logic_rand', '开箱分支未锚定随机态'
    gs2 = _make_gs(bench=[], equips=[])
    gs2.prep_anchored = True
    on_env_gained(gs2, None, '蓝钻贵族', rand=False, sig=_lsig())
    assert gs2.equips.source == 'logic_rand', \
        '装备入账分支锚定仍随机态(rand=True 硬编码,裁定语义)'
    assert gs2.bench.source == 'logic', '开箱分支锚定确定面(rand=False 透传)'
    assert rows_sink.kinds() == [], '两态零申报行(不进失配网)'


# —— 列车同行邀请(2026-09-23-invest-effects-calc T-63;邀请族首例模式卡,
# 机制件零新增,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_lieche_invite(rows_sink: _RowSink) -> None:
    """发放分支(T-63 设计 §4 锁 3,on_env_gained 直构):选列车同行邀请 →
    equips 尾追 '列车同行星徽'、bench 零落位(装备 only,无开箱腿);
    效果串单行 ``equip_gift:列车同行星徽``。星徽 ∈ EQUIP_ACQUIRE_
    CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '列车同行邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:列车同行星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['列车同行星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 银河学者邀请(2026-09-23-invest-effects-calc T-64;邀请族展开首卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_yinhe_invite(rows_sink: _RowSink) -> None:
    """发放分支(T-64 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    银河学者邀请 → equips 尾追 '银河学者星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:银河学者星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '银河学者邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:银河学者星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['银河学者星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 贝洛伯格邀请(2026-09-23-invest-effects-calc T-65;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_beluoboge_invite(rows_sink: _RowSink) -> None:
    """发放分支(T-65 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    贝洛伯格邀请 → equips 尾追 '贝洛伯格星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:贝洛伯格星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '贝洛伯格邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:贝洛伯格星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['贝洛伯格星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 星间旅人邀请(2026-09-23-invest-effects-calc T-66;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_xingjian_lvren_invite(rows_sink: _RowSink) -> None:
    """发放分支(T-66 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    星间旅人邀请 → equips 尾追 '星间旅人星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:星间旅人星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '星间旅人邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:星间旅人星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['星间旅人星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 仙舟邀请(2026-09-23-invest-effects-calc T-67;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_xianzhou_invite(rows_sink: _RowSink) -> None:
    """发放分支(T-67 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    仙舟邀请 → equips 尾追 '仙舟星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:仙舟星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '仙舟邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:仙舟星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['仙舟星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 狼狩邀请(2026-09-23-invest-effects-calc T-68;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_langshou_invite(rows_sink: _RowSink) -> None:
    """发放分支(T-68 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    狼狩邀请 → equips 尾追 '狼狩星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:狼狩星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '狼狩邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:狼狩星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['狼狩星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 盛会之星邀请(2026-09-23-invest-effects-calc T-69;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_shenghui_zhixing_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-69 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    盛会之星邀请 → equips 尾追 '盛会之星星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:盛会之星星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '盛会之星邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:盛会之星星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['盛会之星星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 昼之半神邀请(2026-09-23-invest-effects-calc T-70;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_zhouzhi_banshen_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-70 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    昼之半神邀请 → equips 尾追 '昼之半神星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:昼之半神星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '昼之半神邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:昼之半神星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['昼之半神星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 夜之半神邀请(2026-09-23-invest-effects-calc T-71;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_yezhi_banshen_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-71 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    夜之半神邀请 → equips 尾追 '夜之半神星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:夜之半神星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '夜之半神邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:夜之半神星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['夜之半神星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 追击邀请(2026-09-23-invest-effects-calc T-72;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_zhuiji_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-72 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    追击邀请 → equips 尾追 '追击星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:追击星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '追击邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:追击星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['追击星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 击破邀请(2026-09-23-invest-effects-calc T-73;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_jipo_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-73 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    击破邀请 → equips 尾追 '击破星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:击破星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '击破邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:击破星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['击破星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 群攻邀请(2026-09-23-invest-effects-calc T-74;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_qungong_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-74 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    群攻邀请 → equips 尾追 '群攻星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:群攻星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '群攻邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:群攻星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['群攻星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 能量邀请(2026-09-23-invest-effects-calc T-75;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_nengliang_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-75 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    能量邀请 → equips 尾追 '能量星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:能量星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '能量邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:能量星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['能量星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 燃血邀请(2026-09-23-invest-effects-calc T-76;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_ranxue_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-76 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    燃血邀请 → equips 尾追 '燃血星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:燃血星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '燃血邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:燃血星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['燃血星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 减益邀请(2026-09-23-invest-effects-calc T-77;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_jianyi_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-77 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    减益邀请 → equips 尾追 '减益星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:减益星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '减益邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:减益星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['减益星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 持续伤害邀请(2026-09-23-invest-effects-calc T-78;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_chixu_shanghai_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-78 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    持续伤害邀请 → equips 尾追 '持续伤害星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:持续伤害星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '持续伤害邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:持续伤害星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['持续伤害星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 量子同频邀请(2026-09-23-invest-effects-calc T-79;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_liangzi_tongpin_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-79 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    量子同频邀请 → equips 尾追 '量子同频星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:量子同频星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '量子同频邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:量子同频星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['量子同频星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 战技点邀请(2026-09-23-invest-effects-calc T-80;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_zhanjidian_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-80 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    战技点邀请 → equips 尾追 '战技点星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:战技点星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '战技点邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:战技点星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['战技点星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'


# —— 欢愉邀请(2026-09-23-invest-effects-calc T-81;邀请族展开卡,
# 纯数据行,骑同一 on_env_gained 即时装备支)——


def test_env_gift_equip_leg_huanyu_invite(
        rows_sink: _RowSink) -> None:
    """发放分支(T-81 设计 §4 锁 3,治理后形态,on_env_gained 直构):选
    欢愉邀请 → equips 尾追 '欢愉星徽'、bench 零落位(装备 only,
    无开箱腿);效果串单行 ``equip_gift:欢愉星徽``。星徽 ∈ EQUIP_
    ACQUIRE_CONSEQUENCES 表外 → 零子链(申报行空为证)。"""
    gs = _make_gs(bench=[], equips=[])
    out = on_env_gained(gs, None, '欢愉邀请', rand=False, sig=_lsig())
    assert out == ('equip_gift:欢愉星徽',), '效果串 = 具名装备单行'
    assert list(gs.equips.value) == ['欢愉星徽'], '装备入栏(尾追)'
    boxes = [s for s in gs.bench.value.slots
             if s is not None and s.kind == 'supply_box']
    assert boxes == [], '零道具落位(装备 only)'
    assert rows_sink.kinds() == [], '正常路径零申报行(零子链)'
