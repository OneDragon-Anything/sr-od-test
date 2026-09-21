"""获得链(gain-chain)3.1 落地锁。

设计 = docs/develop/sr_od/application/currency_war/changes/2026-09-21-gain-chain/
design.md §2.1-2.4/§2.7 + landing.md 3.1 完成判据。锁面:

- **对拍一致**(§2.1-3):单级合成 ``merge_step_once`` ×N 次终态与
  ``cw_merge_simulate.merge_simulate`` 同池同输入不动点终态一致(禁第二
  套语义的执行锁);
- **调用序**(§2.1 固定时序):落位 → 回调 → 升星 → 产物递归;回调补齐
  第三只后再合成;
- **rand 透传**(§2.4):确定入口走 write_logic、rand=True 透传走
  write_logic_rand、采样效果腿可翻转子链通道;
- **失败安全**(§2.7):溢出落位/归位/溢出位被占留证;bench/equips
  未观察 = 零写 + 留证不停机;
- **ENV_GIFTS 分道**(§2.3):advisor=True 不入席只申报、advisor=False
  入席递归;查无效果安静不写(裁定④)。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war.kernel import cw_gain_chain
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    DEFECT_ADVISOR_DECL,
    DEFECT_BENCH_UNOBSERVED,
    DEFECT_EQUIPS_UNOBSERVED,
    DEFECT_OVERFLOW_TAKEN,
    GainOutcome,
    gain_character,
    gain_equipment,
    gain_invest_env,
    merge_step_once,
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
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_GIFTS,
    INVESTMENT_ENVS,
)
from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    merge_simulate,
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


def test_rand_passthrough_and_flip(monkeypatch: pytest.MonkeyPatch) -> None:
    """rand 透传与翻转(§2.4):确定入口 rand=False 走 write_logic;
    rand=True 透传走 write_logic_rand;采样效果腿对子链传 rand=True 只
    翻转自己的子链(现役枚举无采样腿,以桩模拟采样效果验证机制)。"""
    gs = _make_gs(bench=[], equips=[])
    orig_logic, orig_rand = gs.write_logic, gs.write_logic_rand
    chan: list[tuple[str, str | None]] = []

    def rec_l(target, value, **kw) -> None:
        chan.append(('logic', kw.get('evidence')))
        orig_logic(target, value, **kw)

    def rec_r(target, value, **kw) -> None:
        chan.append(('logic_rand', kw.get('evidence')))
        orig_rand(target, value, **kw)

    monkeypatch.setattr(gs, 'write_logic', rec_l)
    monkeypatch.setattr(gs, 'write_logic_rand', rec_r)

    def sampling_cb(gs: GameState, name: str, star: int, *, rand: bool,
                    sig: ChannelSig) -> tuple[str, ...]:
        gain_character(gs, '希儿', 1, rand=True, sig=sig,
                       evidence='sampled', producer='T')
        return ()

    monkeypatch.setattr(cw_gain_chain, 'on_character_gained', sampling_cb)
    gain_character(gs, '银狼', 1, rand=False, sig=_lsig(), evidence='main',
                   producer='T')
    assert ('logic', 'main#place') in chan, '确定入口落位走 write_logic'
    assert ('logic_rand', 'sampled#place') in chan, \
        '采样效果子链走 write_logic_rand(翻转只及子链)'
    assert all(c == 'logic' for c, e in chan if e and e.startswith('main')), \
        '外链(确定面)不被采样子链污染'
    # 透传态:rand=True 入口全链走随机通道
    gs2 = _make_gs(bench=[])
    gain_character(gs2, '停云', 1, rand=True, sig=_lsig(), evidence='main',
                   producer='T')
    assert gs2.bench.source == 'logic_rand'


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


# ============================================================ 未观察留证(§2.7 裁定⑤)


def test_unobserved_zero_write_with_defect(rows_sink: _RowSink) -> None:
    """bench/equips 未观察 = bug 面:零写 + 留证不停机(裁定⑤)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seq_before = gs.write_seq
    out_c = gain_character(gs, '希儿', 1, rand=False, sig=_lsig(),
                           evidence='g', producer='T')
    assert out_c.placed is False and out_c.detail == 'bench_unobserved'
    out_e = gain_equipment(gs, '分身墨镜', rand=False, sig=_lsig(),
                           evidence='g', producer='T')
    assert out_e.placed is False and out_e.detail == 'equips_unobserved'
    assert gs.write_seq == seq_before
    assert rows_sink.kinds() == [DEFECT_BENCH_UNOBSERVED,
                                 DEFECT_EQUIPS_UNOBSERVED]


# ============================================================ ENV_GIFTS 分道(§2.3)


def test_env_gift_advisor_split_and_quiet(rows_sink: _RowSink) -> None:
    """ENV_GIFTS 分道(§2.3-1):advisor=True 不入席只申报;advisor=False
    入席递归(chars_immediate 1★);表外环境查无效果安静不写(裁定④)。
    session=None = 登记腿跳过、容器写照常(编排语义裁定)。"""
    # advisor:特邀专家 → 顾问入商店,不入席
    gs_a = _make_gs(bench=[], equips=[])
    out_a = gain_invest_env(gs_a, None, '特邀专家:停云', rand=False,
                           sig=_lsig())
    assert out_a.effects == ('advisor_decl:特邀专家:停云',)
    assert gs_a.active_env.value == '特邀专家:停云'   # 容器写照常
    assert gs_a.active_env.source == 'logic'
    assert bench_units_of(gs_a) == [], '不入席(容器无商店池字段,只申报)'
    assert rows_sink.kinds() == [DEFECT_ADVISOR_DECL]
    # 契约:直接送卡 → 入席递归
    gs_c = _make_gs(bench=[], equips=[])
    out_c = gain_invest_env(gs_c, None, '公司契约', rand=False, sig=_lsig())
    assert out_c.effects == ('env_gift:翡翠', 'env_gift:砂金')
    units = [(u.char_id, u.star) for u in bench_units_of(gs_c)]
    assert units == [('翡翠', 1), ('砂金', 1)], 'chars_immediate 逐个 1★ 入席'
    # 表外环境:查无效果安静不写
    quiet = next(n for n in INVESTMENT_ENVS if n not in ENV_GIFTS)
    gs_q = _make_gs(bench=[], equips=[])
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
