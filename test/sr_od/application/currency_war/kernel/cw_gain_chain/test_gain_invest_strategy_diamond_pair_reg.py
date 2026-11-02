"""这么大的钻石(id 231101)佩佩×宝钻双腿组合登记腿锁(镜像 src =
kernel/cw_gain_effects.py 的 PICK_INVEST_EFFECTS 组合直书登记行 + 登记面
cw_investments.STRATEGY_GRANTS 非直读人工转正行;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新增测试落新镜像,先例 = 同目录
姊妹镜像文件)。

测试面依据 = 迭代设计 designs/T-243-zheme-da-de-zuanshi.md §4 锁 2/4/5①
+ 用户裁定 2026-11-02 读法 B(佩佩真实入后台,裁定册
PENDING-DECISIONS.md):
- 组合腿主链(锁 2):直构 on_strategy_gained(rand=False)→ 腿序 =
  卡文语序佩佩腿先/宝钻腿后,效果串
  ``char_grant:佩佩(placed=True,merge=0)``,
  ``named_equip_grant:财富宝钻(placed=True)`` 各一条;备战恰 +1 只
  1★ 佩佩(星级占位非先验)、equips 恰 +1 件财富宝钻;正常路径零
  申报行;
- 判读前提漂移哨(锁 5①):卡面 effect 无「获得」子串程序化断言——
  本卡转正行正因该缺席而人工登记,词表改版若引入「获得」反扫即命中,
  本哨先红触发重申报;同锁钉转正行登记形态(发放对象 = 佩佩);
- 拒落形态(发放落地门下游):equips 未观察 → 宝钻腿拒落零写
  (placed=False 串留证)、佩佩腿不涉装备域照常落席;
- live 零回调锁(锁 4):kernel 形态拿卡(无 sim)→ 宝钻世界三域
  diamond_count/deploy_cap/back_layout 零写——回调只活在 sim 拿卡腿
  (sim/cw_sim_backend),三域 live 归观察识别器,逻辑侧禁写契约,
  与 sim 全链锁(sim/cw_sim_backend/test_strategy_pick_diamond_grant_
  sim_chain.py)成对锁死 sim-only 分岔。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    STRATEGY_GRANTS,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
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
    INVESTMENT_STRATEGIES,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '这么大的钻石'
_EQUIP = '财富宝钻'


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供拒落边界分支)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=s))
                 for n, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


class _RowSink:
    """缺陷台账行收集(镜像 test_gain_chain 同名 fixture,装配 + 必达收尾)。"""

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


def test_pair_legs_grant_peipei_then_diamond(rows_sink: _RowSink) -> None:
    """组合腿主链(锁 2):腿序 = 卡文语序(佩佩腿先/宝钻腿后),两腿各
    产一条效果串;备战恰 +1 只 1★ 佩佩、equips 恰 +1 件财富宝钻;
    确定发放零采样面;正常路径零申报行。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    units_before = len(bench_units_of(gs))
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:佩佩(placed=True,merge=0)',
                       f'named_equip_grant:{_EQUIP}(placed=True)'), \
        f'双腿步串漂移: {effects!r}'
    units = bench_units_of(gs)
    assert len(units) == units_before + 1, '备战恰 +1 单位'
    assert (units[-1].char_id, units[-1].star) == ('佩佩', 1), \
        '佩佩 1★ 入席(星级 1 = 占位非先验)'
    assert gs.equips.value == [_EQUIP], f'宝钻恰一件: {gs.equips.value!r}'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_effect_text_has_no_gain_verb_and_grant_registered() -> None:
    """判读前提漂移哨(锁 5①)+ 转正行形态:卡面 effect 无「获得」子串
    (本卡人工转正行的立据——词表改版引入「获得」动词时反扫即命中,
    本哨先红触发判读重申报);转正行在册且发放对象 = 佩佩;组合登记行
    在册(世界腿单一源)。"""
    assert '获得' not in INVESTMENT_STRATEGIES[_CARD].effect, \
        '卡文出现「获得」:反扫判读前提漂移,转正依据重申报'
    grant = STRATEGY_GRANTS.get(_CARD)
    assert grant is not None and grant.chars_immediate == ('佩佩',), \
        '非直读人工转正行缺位或发放对象漂移'
    assert grant.advisor is False, '转正卡非顾问型'
    assert _CARD in PICK_INVEST_EFFECTS, '组合登记行缺位'


def test_equips_unobserved_diamond_leg_rejected() -> None:
    """拒落形态(发放落地门下游):equips 未观察 → 宝钻腿拒落零写
    (效果串 placed=False 留证,容器维持 None),佩佩腿不涉装备域照常
    落席——两腿独立,装备域缺失不拖累单位入队。"""
    gs = _make_gs(bench=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects == ('char_grant:佩佩(placed=True,merge=0)',
                       f'named_equip_grant:{_EQUIP}(placed=False)'), \
        f'拒落形态步串漂移: {effects!r}'
    assert gs.equips.value is None, '拒落档零写'
    assert (bench_units_of(gs)[-1].char_id) == '佩佩', '佩佩腿不受扰'


def test_kernel_pick_zero_world_coupling_writes() -> None:
    """live 零回调锁(锁 4):kernel 形态拿卡(效果体双腿正常入栏)→
    宝钻世界三域零写(值维持 None)——on_diamond_acquired 调用只活在
    sim 拿卡腿,live 三域归观察识别器(逻辑侧禁写,投影审计契约)。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(0))
    assert effects[1] == f'named_equip_grant:{_EQUIP}(placed=True)', \
        '前置:宝钻应已入栏(联动缺席非拒落缺席)'
    assert gs.diamond_count.value is None, 'diamond_count 误写'
    assert gs.deploy_cap.value is None, 'deploy_cap 误写'
    assert gs.back_layout.value is None, 'back_layout 误写'
