"""装备获得转换·装备目标分支锁(镜像 src = kernel/cw_gain_chain.py 的
gain_equipment 顶段装备目标分支 + _equip_gain_conversion_hit 判定件 +
equip_gain_conversion_target 公开预测面;按被测方法拆目录规范落位——
test_gain_chain.py 已登记超限冻结禁追加,新锁落新镜像;bench 分支先例 =
同目录 test_gain_equipment_conversion.py 模式卡自由市场)。

测试面依据 = 迭代设计 designs/T-248-haoyunlai.md §4 锁 1/2/3/5 +
REVIEW-T248 §4③ 裁决点默认案(转换载体 A = 专表 + 装备目标分支解锁):
- 锁 1 转换主锁:持卡 + gain_equipment(进阶件, rand=False)→ 进阶件
  不入栏、转换产物 '好运令牌' 入栏(名字替换落原插入路径)、detail 含
  converted 标记;on_equipment_gained 以令牌分派零后果(令牌 ∉
  EQUIP_ACQUIRE_CONSEQUENCES,effects 空)——任一经原语的进阶获得通道
  同判定(如回收计划双卡随机进阶组合腿),拦截单咽喉自动覆盖;
- 锁 2 类别边界:简易〔以太钻头点名:注册表归'简易'作基础件,防图鉴
  口径误引〕/工具/星徽/特殊类别获得不转换照常入栏(转换谓词按注册
  类别判,进阶谓词仅辖源类别);
- 锁 3 不持卡零转换(守卫零副作用,同族他卡持卡也不触发);
- 锁 5 双域对号:双持自由市场 + 好运来,简易获得 → 武装箱(其辖)、
  进阶获得 → 令牌(本卡辖),互不串扰,单事件至多一卡命中(源类别
  互斥的构造性保证);
- 预测面锁:equip_gain_conversion_target 公开只读(穿着即合成产物预测
  的判定单源,wear_equip 注入消费),零写零 rng。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    equip_gain_conversion_target,
    gain_equipment,
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
    equips_by_category,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwGainChainTest')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '好运来'

_TARGET = '好运令牌'


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None,
             cards: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;镜像同目录
    test_gain_equipment_conversion._make_gs,持卡面多一支 cards 直置)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
                 for c, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    if cards:
        gs.write_logic(gs.active_strategies, cards, produced_by='test-seed',
                       evidence='t:card', sig=_LSIG)
    return gs


def _hold_card(gs: GameState, cards: list[str]) -> None:
    """持卡直置(注册容器直写;同族多卡持卡态由 cards 列表承载)。"""
    gs.write_logic(gs.active_strategies, cards, produced_by='test-seed',
                   evidence='t:card', sig=_LSIG)


def _box_slots(gs: GameState) -> list:
    return [s for s in gs.bench.value.slots
            if s is not None and s.kind == 'supply_box']


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


def test_conversion_intercept_places_token_not_equip(
        rows_sink: _RowSink) -> None:
    """转换主锁(设计 §4 锁 1):持卡 + gain_equipment(进阶件, rand=False)
    → 出参 placed=True/detail=f'converted:{卡}'/landing='skipped';
    进阶件不入栏 + 令牌入栏恰 +1(名字替换落原插入路径);on_equipment_
    gained 以令牌分派零后果(effects 空,令牌 ∉ 后果表);正常路径零申报
    行。任一经原语的进阶获得通道同判定(随机进阶组合腿等),单咽喉自动
    覆盖,零特判。"""
    item = sorted(equips_by_category('进阶'))[0]
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, [_CARD])
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed, '转换产物入栏 = 转换发生(placed=True)'
    assert out.detail == f'converted:{_CARD}', 'detail 含 converted 标记'
    assert out.landing == 'skipped' and out.merge_levels == 0, \
        '出参形状 = 转换 GainOutcome(装备原语语义档)'
    assert gs.equips.value == [_TARGET], \
        f'进阶件被替换,令牌入栏恰 +1: {gs.equips.value!r}'
    assert item not in gs.equips.value, '被转换进阶件不入栏'
    assert out.effects == (), '令牌获得零后果(后果表零涉)'
    assert _box_slots(gs) == [], '零箱(非 bench 分支)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_conversion_equips_unobserved_zero_write() -> None:
    """栏未观察形态:守卫在栏未观察早退之前,直构域持卡也转换——装备
    分支落原插入路径遇 equips 未观察拒落 → placed=False、detail=
    'equips_unobserved'(与原插入路径同语义档,拒绝因 = 落位域非转换
    面),零写零申报。"""
    item = sorted(equips_by_category('进阶'))[0]
    gs = _make_gs(bench=[])   # equips 不种 = 域未观察
    _hold_card(gs, [_CARD])
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed is False and out.detail == 'equips_unobserved', \
        '栏未观察拒落零写(转换语义档)'
    assert gs.equips.value is None, '未观察域零写'


@pytest.mark.parametrize('cat', ['简易', '工具', '星徽', '特殊'])
def test_non_advanced_categories_pass_through(cat: str,
                                              rows_sink: _RowSink) -> None:
    """类别边界(设计 §4 锁 2):非进阶类别获得不转换照常入栏(转换谓词
    按注册类别判)。简易含以太钻头点名——注册表归'简易'作基础件的类别
    怪癖,图鉴口径视为可合成材料不入本卡进阶谓词(防按图鉴误判转换);
    取样排除后果表成员,隔离 on_equipment_gained 追加入席干扰;工具池
    含转换产物好运令牌自身,获得令牌(如他卡发放)不转换 = 不重入的
    行为级佐证。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        EQUIP_ACQUIRE_CONSEQUENCES,
    )
    pool = [n for n in sorted(equips_by_category(cat))
            if n not in EQUIP_ACQUIRE_CONSEQUENCES]
    assert pool, f'{cat} 池全被后果表占用?取样前提失配,须随批改'
    item = pool[0]
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, [_CARD])
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed and out.detail == '', '照常入栏(零转换标记)'
    assert gs.equips.value == [item], '入栏恰 +1'
    assert _box_slots(gs) == [], '零箱(不转换)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_yitai_drillhead_named_not_converted(rows_sink: _RowSink) -> None:
    """以太钻头点名锁(设计 §4 锁 2 防误引支):注册表类别 '简易' 的
    合成基础件,持卡局获得照常入栏——进阶谓词按注册类别判,不按图鉴
    「可合成进阶材料」口径(设计 §1.5 类别怪癖辨析回归)。"""
    eq = equips_by_category('简易')
    assert '以太钻头' in eq, '前提:以太钻头注册类别 ∈ 简易池(漂移须随批改)'
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, [_CARD])
    out = gain_equipment(gs, '以太钻头', rand=False, sig=_LSIG,
                         evidence='t', producer='Test')
    assert out.placed and out.detail == '', '照常入栏(零转换标记)'
    assert gs.equips.value == ['以太钻头'], '钻头入栏恰 +1'


def test_no_card_zero_interception(rows_sink: _RowSink) -> None:
    """不持卡零转换(设计 §4 锁 3):同调用无卡时进阶件照常入栏(守卫
    零副作用;同族他卡持卡也不触发——持卡判定 ∩ 转换登记表,表外卡零
    涉)。"""
    item = sorted(equips_by_category('进阶'))[0]
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, ['规模效应'])
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed and out.detail == '', '照常入栏'
    assert gs.equips.value == [item], '入栏恰 +1'
    assert _box_slots(gs) == [], '零箱'


def test_dual_card_domains_disjoint(rows_sink: _RowSink) -> None:
    """双域对号(设计 §4 锁 5):双持自由市场 + 好运来——简易获得 →
    简易武装箱(其辖 bench 分支)、进阶获得 → 令牌(本卡辖装备分支),
    互不串扰;单事件至多一卡命中(源类别简易/进阶互斥的构造性保证,
    共用同一拦截点逐卡判定)。"""
    simple = [n for n in sorted(equips_by_category('简易'))
              if n != '以太钻头'][0]
    advanced = sorted(equips_by_category('进阶'))[0]
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs, ['自由市场', _CARD])
    out_adv = gain_equipment(gs, advanced, rand=False, sig=_LSIG,
                             evidence='t', producer='Test')
    assert out_adv.detail == f'converted:{_CARD}', '进阶事件本卡辖'
    assert gs.equips.value == [_TARGET], '进阶被替换为令牌(零箱面)'
    assert _box_slots(gs) == [], '进阶事件零箱(不串扰其辖)'
    out_simple = gain_equipment(gs, simple, rand=False, sig=_LSIG,
                                evidence='t', producer='Test')
    assert out_simple.detail == 'converted:自由市场', '简易事件其辖'
    assert gs.equips.value == [_TARGET], '简易被替换,不入栏(零串扰)'
    boxes = _box_slots(gs)
    assert len(boxes) == 1 and boxes[0].item == '简易武装箱', \
        '简易事件净得 1 箱(bench 分支)'
    assert bench_units_of(gs) == [], '两事件零单位域写'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_prediction_surface_readonly(rows_sink: _RowSink) -> None:
    """预测面只读锁:equip_gain_conversion_target 持卡进阶 → 令牌名、
    非源类别 → None、不持卡 → None;零写零申报(公开预测面 = 穿着即
    合成产物预测的判定单源,wear_equip 注入消费,禁第二份判定)。"""
    advanced = sorted(equips_by_category('进阶'))[0]
    gs = _make_gs(bench=[], equips=[])
    assert equip_gain_conversion_target(gs, advanced) is None, '不持卡 None'
    _hold_card(gs, [_CARD])
    seq0 = gs.write_seq
    assert equip_gain_conversion_target(gs, advanced) == _TARGET, \
        '持卡进阶 → 转换目标名'
    assert equip_gain_conversion_target(gs, '好运令牌') is None, \
        '工具类 None(不属源类别,误重入零再转换)'
    assert equip_gain_conversion_target(gs, '不存在物') is None, \
        '未知名 None(保持原语盲追加行为边)'
    assert gs.write_seq == seq0, '预测面零写'
    assert rows_sink.kinds() == [], '预测面零申报行'
