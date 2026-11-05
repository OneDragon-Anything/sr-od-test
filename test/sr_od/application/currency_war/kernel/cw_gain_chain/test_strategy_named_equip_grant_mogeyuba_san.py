"""摸个鱼吧III(id 360101)具名装备授予腿锁(镜像 src = kernel/cw_gain_effects.py
的 ``PICK_INVEST_EFFECTS`` 直书登记行「摸个鱼吧III」;摸个鱼吧族收官卡双腿
分治:送卡腿「获得18个【青雀】」登记面镜像 = cw_investments.STRATEGY_GRANTS
同卡行(已在册,数量「18个」失真族判例单元素申报,估值档机器只读 chars
集合零影响,非 advisor 零运行时消费道),令牌腿「2个【好运令牌】」= 本
文件锁面;族模式卡 = 全员晋升——工厂语义锁住同目录姊妹镜像
test_strategy_named_equip_grant.py,count=2 同物形先例 = 小复制
test_strategy_named_equip_grant_xiaofuzhi.py,按被测方法拆目录规范落位)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-413-mogeyuba-san.md
(定稿)§4 锁 1/锁 2/锁 3:
- 腿2 = 登记行直书 ``_make_named_equip_grant_effect('好运令牌', 2)``,具名
  确定发放 ``gain_equipment(rand=False)`` 循环 2 次逐件一条入栏,效果串恰
  两条各含 placed(evidence 断言用前缀匹配——原语内追加 ``#equip`` 后缀,
  精确匹配假红,同族口径);
- 物名断言防卡名当物名笔误:发放名 == '好运令牌' 精确串(卡名「摸个鱼吧III」
  与物名「好运令牌」异名对,工厂参数漂移或卡名误引在此红);
- 精密金面前置按物判(判据映射只挂拆装扳手):好运令牌 gate 恒 None,
  精密拆装扳手在场照常发放零申报行(卡级前置分支零遗传机械回归);
- rng 零消费 = 确定发放(卡文无随机词;效果体直接调用前后随机源状态不变,
  种子无关可复现);
- 送卡腿零运行时消费:非 advisor 登记 → unlocked_experts 零解锁写(承姊妹
  卡摸个鱼吧II 同构断言面);
- 本卡无金句零金腿(gold 域零写断言覆盖);装备非占席不入 bench,板面域
  (bench/deployed)零写。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
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

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '摸个鱼吧III'
_ITEM = '好运令牌'


def _make_gs(*, equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供拒落分支;本卡锁面只涉 equips
    域,bench 恒空场 + gold 未读 = 金腿域零干扰对照)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1)),
             BenchSlot(kind='empty')]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


class _RowSink:
    """缺陷台账行收集(镜像姊妹文件同名 fixture,装配 + 必达收尾)。"""

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


def test_mogeyuba_san_grant_leg_places_two_tokens(rows_sink: _RowSink) -> None:
    """登记面 + 腿行为主锁(锁 2):gain_invest_strategy 全链(rand=False)
    → 注册入表 + equips 恰 +2 好运令牌(发放名精确串,防卡名当物名笔误)、
    写数恰 3(注册 1 + 腿 2;②段账本登记 session=None 跳过)、来源 = 确定
    面 logic;gold 未读零金写(本卡无金句);板面域(bench/deployed)零写;
    非 advisor 零解锁写(送卡腿不解锁专家);正常路径零申报行。"""
    assert _CARD in PICK_INVEST_EFFECTS, '登记面在册'
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert gs.equips.value == [_ITEM, _ITEM], \
        '逐件入栏恰 2 件,物名精确 = 好运令牌(防卡名当物名笔误)'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence.startswith('pick_invest_named_equip'), \
        '腿写端 evidence 前缀(原语内追加 #equip 后缀,前缀匹配防假红)'
    assert gs.write_seq - seq_before == 3, \
        '写数恰 3 = 注册 1 + 装备腿 2(②段账本登记 session=None 跳过)'
    assert gs.gold.value is None, '本卡无金句零金写'
    assert len(bench_units_of(gs)) == 1, 'bench 零变化(送卡腿零运行时消费)'
    assert gs.deployed.value is None, 'deployed 未观察保持未写(板面零建模)'
    assert gs.unlocked_experts.value in (None, ()), \
        '非 advisor 零解锁写(送卡腿不解锁专家)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_mogeyuba_san_effect_steps_exactly_two(rows_sink: _RowSink) -> None:
    """效果串形态锁(锁 1 条数断言):on_strategy_gained 效果串恰 2 条
    ``named_equip_grant:好运令牌(placed=True)``——count=2 循环逐件一条
    携带 placed(前缀 named_equip_grant 分域可审计)。"""
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (
        f'named_equip_grant:{_ITEM}(placed=True)',
        f'named_equip_grant:{_ITEM}(placed=True)',
    ), '效果串恰 2 条逐件一条各含 placed'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_mogeyuba_san_rng_zero_consumption(rows_sink: _RowSink) -> None:
    """rng 零消费锁(锁 2 确定发放面):效果体直接调用前后随机源状态不变
    ——具名发放 rand=False 零采样面(卡文无随机词),种子无关可复现。"""
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng = random.Random(2026)
    state_before = rng.getstate()
    effects = PICK_INVEST_EFFECTS[_CARD](gs, sig=_LSIG, rng=rng)
    assert rng.getstate() == state_before, 'rng 零消费(确定发放零采样面)'
    assert effects == [
        f'named_equip_grant:{_ITEM}(placed=True)',
        f'named_equip_grant:{_ITEM}(placed=True)',
    ], '直呼效果体仍恰 2 条'
    assert gs.equips.value == [_ITEM, _ITEM], '直呼效果体照常入栏 2 件'
    assert gs.write_seq - seq_before == 2, '直呼效果体写数恰 2(腿 2 无注册)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_mogeyuba_san_precise_gate_not_hit(rows_sink: _RowSink) -> None:
    """精密前置机械回归锁(锁 3):预置精密拆装扳手 1 件 → 拿本卡 → 腿
    照常发放 2 令牌零申报行——精密金面判据按物判(判据映射只挂拆装扳手),
    好运令牌 gate 恒 None,卡级前置分支零遗传(后继卡直呼工厂不受污染)。"""
    gs = _make_gs(equips=['精密拆装扳手'])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (
        f'named_equip_grant:{_ITEM}(placed=True)',
        f'named_equip_grant:{_ITEM}(placed=True)',
    ), '精密在场腿照常发放,placed=True ×2'
    assert gs.equips.value == ['精密拆装扳手', _ITEM, _ITEM], \
        '库尾追加 2 件,精密原值不动'
    assert gs.write_seq - seq_before == 2, \
        '写数恰 2 = 腿 2(on_strategy_gained 无注册写,注册归 gain_invest_\
strategy ①段)'
    assert rows_sink.kinds() == [], '精密判据对本卡不命中,零申报行'


def test_mogeyuba_san_unobserved_reject_auditable(rows_sink: _RowSink) -> None:
    """拒落负支:equips 未观察(None)直构 → 原语拒落零写 + 效果串仍逐件
    登记(placed=False ×2,拒落可审计)+ 零申报行(拒落档 = 原语既有语义
    静默档,与精密 fail-closed 申报档区分)。"""
    gs = _make_gs()
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (
        f'named_equip_grant:{_ITEM}(placed=False)',
        f'named_equip_grant:{_ITEM}(placed=False)',
    ), '效果串恒 2 条逐件一条,placed=False 拒落可审计'
    assert gs.write_seq == seq_before, '拒落零写'
    assert rows_sink.kinds() == [], '拒落档零申报行(非 fail-closed 档)'
