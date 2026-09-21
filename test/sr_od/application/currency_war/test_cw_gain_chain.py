"""获得链(gain-chain)行为锁(链式规范 + 开局种子底座通道规则)。

锁面依据(语义正本,changes/ 过程件不引):获得链正本 =
docs/develop/sr_od/application/currency_war/game_state/gain-chain.md
(§2 原语契约/§2.5 单级合成/§6 失败安全);通道规则与种子底座正本 =
同目录 fields.md §2.6(未锚定 → 随机态、锚定后按形参、失配网生效)。锁面:

- **对拍一致**(§2.1-3):单级合成 ``merge_step_once`` ×N 次终态与
  ``cw_merge_simulate.merge_simulate`` 同池同输入不动点终态一致(禁第二
  套语义的执行锁);
- **调用序**(§2.1 固定时序):落位 → 回调 → 升星 → 产物递归;回调补齐
  第三只后再合成;
- **通道收口双臂**(通道规则「未锚定 → 随机态」):直构未闩容器
  rand=False 链写被改道 write_logic_rand;置闩(测试专口直赋)后
  rand=False 恢复 write_logic;rand=True 恒 write_logic_rand;采样
  效果腿对子链的通道翻转只及子链;
- **失败安全**(§2.7):溢出落位/归位/溢出位被占留证;bench/equips
  未观察(直构域)= 拒落档零写、零缺陷发射(两未观察 kind 已随开局
  种子底座与锚定闩批退役);种子容器(缓存单例支,接管局同构)正常
  落账;置闩后失配网原样生效(确定面被观察覆盖产失配行);
- **欢愉契约条件腿 rider**(条件腿正式模型,锁面 = 银狼策划选择落地相
  上报的授予行为):通道语义(授予 rand=True 全通道 logic_rand,rand
  形参优先于锚定闩——未闩/置闩同通道)+ 覆盖校准面 = 观察覆盖落
  logic_rand_outcome 行零失配行;在册判定(active_env 归一 = 欢愉契约)、
  rng 注入确定性(同 seed 同单位,两候选均可达)、触发计数封闭清单
  (落地相 equip/upgrade/unknown 各恰一次,发射相零授予,leg_type=''
  兜底仍触发且终态兜底 reason = unrouted_leg_zero_write)、授予失败
  调用点级 best-effort(腿型分派照常 + joy_conditional_grant_failed
  留证行)、授予走链固定时序(预置两枚同候选可合成);弱化兜底档退役
  锁(分类落 unknown/打分两档制)归 test_cw_yinlang_phase32.py。
"""
from __future__ import annotations

import dataclasses
import random

import pytest

from sr_od.application.currency_war.kernel import cw_gain_chain
from sr_od.application.currency_war.kernel.cw_action_report.pick_planner import (
    report_action_pick_planner_param,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    SOURCE_STRATEGY,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    DEFECT_ADVISOR_DECL,
    DEFECT_OVERFLOW_TAKEN,
    PICK_INVEST_INVALID_PAYLOAD,
    GainOutcome,
    gain_character,
    gain_equipment,
    gain_invest_env,
    gain_invest_strategy,
    merge_step_once,
    on_strategy_gained,
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
    game_state_of,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_GIFTS,
    INVESTMENT_ENVS,
)
from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    merge_simulate,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _lsig(actor: str = 'CwGainChain') -> ChannelSig:
    return ChannelSig(family='logic_action', actor=actor, mode='compute')


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             front: list[Unit] | None = None,
             equips: list[str] | None = None,
             overflow_card: str | None = None,
             overflow_warning: bool | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供未观察边界腿)。"""
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
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
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
    对拍锁;merge_simulate 是语义权威,期望值即其输出)。"""
    bench: list[BenchSlot | None] = [
        BenchSlot(kind='unit', unit=Unit(char_id=c, star=s)) for c, s in bench_spec]
    bench += [None] * (9 - len(bench))
    dep: list[Unit | None] = [None] * 10
    if dep_idx is not None:
        dep[dep_idx] = Unit(char_id=bench_spec[0][0], star=bench_spec[0][1],
                            slot=1)
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
    """固定时序锁(§2.1):落位 → 回调 → 升星 → 产物递归;回调补齐第三只
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
    rand=True 恒 write_logic_rand;采样效果腿对子链的通道翻转只及子链。"""
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

    # 采样效果腿翻转子链(机制锁,rand 透传纪律;置闩容器上外链与子链
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
                         unit=Unit(char_id='停云', star=1, slot=1))]
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
    """ENV_GIFTS 分道(§2.3-1):advisor=True 不入席只申报;advisor=False
    入席递归(chars_immediate 1★);表外环境查无效果安静不写(裁定④)。
    session=None = 登记腿跳过、容器写照常(编排语义裁定)。"""
    # advisor:特邀专家 → 顾问入商店,不入席(置闩保持确定面通道断言;
    # 本测试焦点 = 分道)
    gs_a = _make_gs(bench=[], equips=[])
    gs_a.prep_anchored = True
    out_a = gain_invest_env(gs_a, None, '特邀专家:停云', rand=False,
                           sig=_lsig())
    assert out_a.effects == ('advisor_decl:特邀专家:停云',)
    assert gs_a.active_env.value == '特邀专家:停云'   # 容器写照常
    assert gs_a.active_env.source == 'logic'
    assert bench_units_of(gs_a) == [], '不入席(容器无商店池字段,只申报)'
    assert rows_sink.kinds() == [DEFECT_ADVISOR_DECL]
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
    assert rows_sink.kinds() == [DEFECT_ADVISOR_DECL], '表外零留证行'


# ============================================================ 装备获得(§2.1/§2.3-3)


def test_gain_equipment_consequence_and_quiet() -> None:
    """gain_equipment:入栏 + EQUIP_ACQUIRE_CONSEQUENCES 命中送单位递归
    (2×银狼在手 → 分身墨镜第 3 只合成 2★);表外件查无效果安静不写。"""
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=[])
    out = gain_equipment(gs, '分身墨镜', rand=False, sig=_lsig(),
                         evidence='g', producer='T')
    assert out.placed is True and out.effects == ('equip_consequence:银狼',)
    assert gs.equips.value == ['分身墨镜']
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units.count(('银狼', 2)) == 1, '送出单位经链入席并可触发合成'
    gs2 = _make_gs(bench=[], equips=[])
    out2 = gain_equipment(gs2, '轮滑鞋', rand=False, sig=_lsig(),
                          evidence='g', producer='T')
    assert out2.effects == () and gs2.equips.value == ['轮滑鞋']
    assert bench_units_of(gs2) == [], '表外件无后果声明,零单位写'


def test_gain_outcome_shape_on_skip() -> None:
    """GainOutcome 为 frozen 留证载体(§2.1;沿 BenchGrantResult 先例,
    零决策消费)——拒落路径的形状锁(detail 键词表)。"""
    o = GainOutcome(placed=False, landing='skipped', merge_levels=0,
                    effects=(), detail='bench_unobserved')
    with pytest.raises(dataclasses.FrozenInstanceError):
        o.placed = True   # type: ignore[misc]  # frozen 载体禁就地改


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
    写入语义)→ 登记腿(session=None 跳过)→ on_strategy_gained 分派
    骇客效果(狼腿经 gain_character 链入席 + 合成;改件经 gain_equipment
    rand=True 入栏,后果表件经 on_equipment_gained 回调送单位;标记域 =
    前后值快照比对,gold 永不翻)。"""
    monkeypatch.setattr(random.Random, 'choice',
                        lambda self, seq: '破解芯片')   # 表外件(无后果腿)
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=[])
    # 置闩(测试专口直赋):注册腿确定面通道断言(source == 'logic')以
    # 通道规则前置;采样腿 rand=True 恒 logic_rand 不受影响。
    gs.prep_anchored = True
    seq_before = gs.write_seq
    gain_invest_strategy(gs, None, '骇客专家:银狼', rand=False,
                         sig=_lsig())
    assert gs.active_strategies.value == ['骇客专家:银狼'], '注册入表'
    assert gs.active_strategies.source == 'logic', '确定面 write_logic'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [('银狼', 2)], '狼腿经链:送出 1★ 与既有合成 → 2★'
    assert gs.equips.value == ['破解芯片'], '改件入栏(采样值)'
    assert gs.equips.source == 'logic_rand', '采样腿 logic_rand'
    assert gs.write_seq > seq_before, '多步各占写序'
    assert 'pick_invest_shop_pool_decl' in rows_sink.kinds(), '商店池申报行'
    # 去重:同卡再入 → 持卡面跳写不重复;效果腿照常(裁定⑩语义 = 仅持卡
    # 列表去重,效果分派零闸)
    seq2 = gs.write_seq
    gain_invest_strategy(gs, None, '骇客专家:银狼', rand=False,
                         sig=_lsig())
    assert gs.active_strategies.value == ['骇客专家:银狼'], '持卡面单份'
    assert gs.write_seq > seq2, '效果腿照走(零幂等闸)'


def test_gain_invest_strategy_session_ledger_leg() -> None:
    """登记腿(design §2.4-2):session 在场 + STRATEGY_EFFECTS 命中 →
    register_strategy 入册 + burst 桥累加免费刷新余额;session=None =
    登记腿跳过、注册照常;未收录卡登记腿零动作。(选卡 = 固定理财:
    STRATEGY_EFFECTS 在册条目且 payload.free_refresh_burst=2,桥 docstring
    背书;市场干预仅在经济聚合表 STRATEGY_ECONOMY,不入本表。)"""
    gs = _make_gs(bench=[], equips=[])
    gain_invest_strategy(gs, object(), '固定理财', rand=False, sig=_lsig())
    assert gs.active_strategies.value == ['固定理财']
    assert [e.spec.name for e in gs.effects.by_source(SOURCE_STRATEGY)] \
        == ['固定理财'], 'register_strategy 入册'
    assert gs.effects.free_refresh_balance == 2, 'burst 桥(free_refresh_burst)'
    gs2 = _make_gs(bench=[], equips=[])
    gain_invest_strategy(gs2, None, '固定理财', rand=False, sig=_lsig())
    assert gs2.active_strategies.value == ['固定理财'], '注册照常'
    assert gs2.effects.by_source(SOURCE_STRATEGY) == [], 'session=None 跳过'
    assert gs2.effects.free_refresh_balance == 0, 'burst 零累加'


def test_on_strategy_gained_unregistered_quiet() -> None:
    """未收录卡:查无效果安静不写(gain-chain §3 裁定④);效果表键集
    现役单行(迁移零变化)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert set(PICK_INVEST_EFFECTS) == {'骇客专家:银狼'}
    gs = _make_gs(bench=[('希儿', 1)], equips=[])
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '随便一张未收录卡', rand=False,
                                 sig=_lsig())
    assert effects == ()
    assert gs.write_seq == seq_before, '零写'


# ============================================================ 欢愉契约条件腿
# ============================================================ rider(银狼策划落地相正式模型)


def _joy_candidates() -> list[str]:
    """条件腿候选名集单一源(结构化在册数据,禁测试内第二抄本)。"""
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
        gs, None, _lsig('CwScreenYinLang'), leg_type='unknown',
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
        gs2, None, _lsig('CwScreenYinLang'), leg_type='unknown',
        rng=random.Random(seed))
    assert gs2.bench.source == 'logic_rand', '锚定后授予仍 logic_rand(采样面)'


def test_joy_rider_registry_gate(rows_sink: _RowSink) -> None:
    """在册判定:active_env 空(种子初值)/其他环境 → 零授予零写;欢愉
    契约在册 → 恰一次授予(正常授予零留证行,unknown 腿载荷各留一行)。"""
    cands = _joy_candidates()
    seed = _joy_seed_for(cands[0])
    gs = _joy_seeded_gs('')          # 空 = 种子初值
    seq = gs.write_seq
    report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), leg_type='unknown',
        rng=random.Random(seed))
    assert [u for u in bench_units_of(gs) if u.char_id in cands] == [], \
        '空环境零授予'
    assert gs.write_seq == seq, '空环境零容器写'
    gs.observe(gs.active_env, '公司契约', sig=_SIG_OBS)
    seq2 = gs.write_seq
    report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), leg_type='unknown',
        rng=random.Random(seed))
    assert [u for u in bench_units_of(gs) if u.char_id in cands] == [], \
        '其他环境零授予'
    assert gs.write_seq == seq2, '其他环境零容器写'
    gs.observe(gs.active_env, '欢愉契约', sig=_SIG_OBS)
    report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), leg_type='unknown',
        rng=random.Random(seed))
    granted = [u.char_id for u in bench_units_of(gs) if u.char_id in cands]
    assert granted == [cands[0]], '欢愉契约在册恰一次授予'
    kinds = rows_sink.kinds()
    # 台账除三腿载荷行外,仅「观察覆盖种子('' → 公司契约)」的 outcome
    # 行(随机态覆盖预期内,与授予无关);授予自身零留证。
    assert kinds.count('planner_leg_unknown') == 3, 'unknown 腿载荷恰各一行'
    assert 'joy_conditional_grant_failed' not in kinds, '正常授予零授予失败留证'


def test_joy_rider_rng_injection_deterministic_and_reaches_both(
        rows_sink: _RowSink) -> None:
    """rng 注入(缺省 None = 实机未播种猜测语义,不在此锁面;注入面 =
    sim 消费契约):同 seed 同单位;两候选均可达(各候选都有使其经完整
    上报路径落位的种子)。"""
    cands = _joy_candidates()
    for c in cands:
        seed = _joy_seed_for(c)
        units_by_container = []
        for _ in range(2):
            gs = _joy_seeded_gs()
            report_action_pick_planner_param(
                gs, None, _lsig('CwScreenYinLang'), leg_type='unknown',
                rng=random.Random(seed))
            units_by_container += [u.char_id for u in bench_units_of(gs)
                                   if u.char_id in cands]
        assert units_by_container == [c, c], \
            f'seed={seed} 同 seed 同单位且恒选 {c}'


def test_joy_rider_fires_once_per_report_call(
        rows_sink: _RowSink) -> None:
    """触发计数封闭清单(单相即时上报,迭代 2026-09-21-pick-planner-
    equip-immediate-report):一次上报 equip/upgrade/unknown 三腿各恰一次
    授予(rider 在腿型分派前,与腿型无关);leg_type='' 直调 rider 仍触发
    (兜底形态)且走终态兜底零写(reason = unrouted_leg_zero_write)。"""
    cands = _joy_candidates()
    seed = _joy_seed_for(cands[0])
    expect = [random.Random(seed).choice(cands)]
    for leg, kw in (('equip', {'norm_item': '破解芯片'}),
                    ('upgrade', {}), ('unknown', {})):
        gs = _joy_seeded_gs()
        if leg == 'upgrade':
            # 升费腿前置:恰一枚 2★银狼LV.999(rider 候选与其无身份交叠)。
            slots = [BenchSlot(kind='unit',
                               unit=Unit(char_id='银狼LV.999', star=2,
                                         slot=1))]
            slots += [BenchSlot(kind='empty')] * 8
            gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                       sig=_SIG_OBS)
        out = report_action_pick_planner_param(
            gs, None, _lsig('CwScreenYinLang'), leg_type=leg,
            rng=random.Random(seed), **kw)
        assert out.applied is True
        granted = [u.char_id for u in bench_units_of(gs)
                   if u.char_id in cands]
        assert granted == expect, f'{leg} 腿 rider 恰一次'
    # leg_type='' 直调落地相(兜底形态):rider 仍触发 + 终态兜底零写。
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
    (expected/actual/evidence 对齐),腿型分派照常执行(升费变换仍应用)
    ——授予与选项应用两条独立因果,授予失败不拖垮选项应用。"""
    import sr_od.application.currency_war.kernel.cw_action_report.\
        pick_planner as pp_mod
    gs = _make_gs(bench=[('银狼LV.999', 2)], equips=[])
    gs.observe(gs.active_env, '欢愉契约', sig=_SIG_OBS)

    def _boom(gs: GameState, name: str, star: int, **kw: object) -> object:
        raise RuntimeError('授予通道注入异常')

    monkeypatch.setattr(pp_mod, 'gain_character', _boom)
    out = report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), leg_type='upgrade',
        rng=random.Random(0))
    assert out.applied is True
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert ('银狼LV.999', 1) in units and ('银狼LV.999', 2) not in units, \
        '腿型分派照常执行(升费变换仍应用)'
    fails = [r for r in rows_sink.rows
             if r['kind'] == 'joy_conditional_grant_failed']
    assert len(fails) == 1, '恰一行授予失败留证'
    row = fails[0]
    assert row['expected'] == '条件腿授予成功'
    assert '授予通道注入异常' in str(row['actual']), 'actual = 异常摘要'
    assert str(row['observed_evidence']).startswith('joy_conditional:')


def test_joy_rider_grant_chain_timing_merge(rows_sink: _RowSink) -> None:
    """时序锁:授予走获得链固定时序(落位 → 回调 → 单级合成)——bench
    预置两枚同候选单位,rider 授予第三枚 → 3 合 1 合成 2★(4 费单位正常
    参与合成,非旁路直写)。"""
    cands = _joy_candidates()
    seed = _joy_seed_for(cands[0])
    gs = _make_gs(bench=[(cands[0], 1), (cands[0], 1)], equips=[])
    gs.observe(gs.active_env, '欢愉契约', sig=_SIG_OBS)
    report_action_pick_planner_param(
        gs, None, _lsig('CwScreenYinLang'), leg_type='equip',
        norm_item='破解芯片',   # 表外件(无后果腿)→ 台账零留证行,焦点留给授予时序
        rng=random.Random(seed))
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [(cands[0], 2)], '三枚合成 2★(链固定时序,非旁路直写)'
    assert rows_sink.kinds() == [], '正常授予合成零留证行'
