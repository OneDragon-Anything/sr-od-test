"""精密拆装·银(id 130801)两条效果条目组合展开锁(镜像 src = kernel/cw_gain_effects.py
的 ``PICK_INVEST_EFFECTS['精密拆装·银']`` 组合登记行;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新增测试落新镜像,先例 = 同目录
姊妹组合卡镜像文件 test_strategy_compose_grant_maicai_plus.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-145-jingmi-caizhuang-yin.md(定稿)§4 锁 2 + REVIEW-T145 六裁决点默认案:
- 组合登记 = ``PICK_INVEST_EFFECTS['精密拆装·银'] = _compose_grant_legs(
  _make_named_equip_grant_effect('精密拆装扳手', 1), _make_random_equip_effect(
  '简易', 1))``(腿序 = 卡文语序具名腿先/随机腿后;腿参数登记行单次出现,
  单一源;不入随机装备泛化表——同名键 dict 顺序覆盖丢腿);
- 固定 rng 注入链发放真值:rng 消费序 = 仅第 2 抽装备(简易池,效果条目1 具名
  确定发放零采样面)——腿序改排(随机腿先)= 效果串序与 equips 追加序
  漂移,被顺序断言捕获;效果串恰 2 条且两条效果条目形态字面分明(效果条目1
  ``named_equip_grant:<名>(placed=<bool>)`` 带 placed 形态 / 效果条目2
  ``strategy_random_equip:<名>`` 无 placed 后缀,跨家族前缀分域可独立
  过滤);
- 前提守卫:「效果串恒 2 条」前提 = 简易池 ∩ ``EQUIP_ACQUIRE_
  CONSEQUENCES`` = ∅ 且精密拆装扳手 ∉ 后果表(设计 §1.3/§1.5 双零交集)
  ——装备注册表扩员(新件带获得后果)时守卫先红,提示语义变化,勿盲改
  主锁断言数;
- 精密门表轻断言(设计 §4 锁 6 降级形态,沿赌神·银镜像先例):本卡效果条目1
  发放物 = 精密拆装扳手自身,∉ ``_NAMED_EQUIP_PRECISE_GATES``(门表只挂
  拆装扳手——金面规则只辖「再获得拆装扳手」)gate 恒 None = 零自我拦截,
  二次持有照常入栏;本镜像主锁空场路径覆盖首次获得,预置精密二次持有
  行为锁不在本批交付面(金面接入调用批回改前置分支时为其耐用回归点);
- 转换拦截边界(设计 §4 锁 5 边界注记,自由市场批已写进代码、现值生效):持自由
  市场局的随机简易获得将被获得原语顶段改道发简易武装箱——本锁不激活
  自由市场(active_strategies 仅本卡),仅辖不持自由市场场景;
- 表外卡零写(设计 §1.2f 联动面):未收录卡安静不写语义随本镜像回归,
  键集闭集断言仍在 test_gain_chain.py 原区(本镜像不重复立集断言)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EQUIP_ACQUIRE_CONSEQUENCES,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _NAMED_EQUIP_PRECISE_GATES,
    roll_random_equip,
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
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

#: 固定种子(单抽形态无互异约束,任意种子;失配 = 换种子)。
_JINGMI_YIN_SEED = 20261103

#: 效果条目1 发放物 = 具名确定(卡文【精密拆装扳手】直读,效果串字面断言基准)。
_NAMED_LEG_ITEM = '精密拆装扳手'


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;镜像 test_gain_chain._make_gs
    的 bench/equips 两支,本卡只涉这两域)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
                 for c, s in bench]
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


def test_jingmi_yin_compose_legs_chain_in_order(rows_sink: _RowSink) -> None:
    """组合腿锁(设计 §4 锁 2):gain_invest_strategy 确定入口(rand=False)
    + 固定 rng 注入 → equips 恰 +2 且两条效果条目各就各位(效果条目1 == 精密拆装扳手精确名、
    效果条目2 名 = 采样值 ∈ 简易池派生集禁手抄清单)、效果串恰 2 条且顺序 = 卡文
    语序(具名腿串在前)两条效果条目形态字面分明、正常路径零申报行;表外卡零写
    (未收录卡安静不写,本卡注册不扰动分派面)。rng 恰 1 次语义由预采样
    同序对拍锁首。"""
    # 预采样(独立 rng 实例按消费序 1 抽):与实际注入的 rng 同种子同序。
    rng = random.Random(_JINGMI_YIN_SEED)
    equip_pick = roll_random_equip(rng, '简易')
    # 前提守卫(设计 §4 锁 5 前提注记):破前提时任一腿获得后果链追加串,
    # 「效果串恒 2 条」失效——守卫先红,勿盲改断言数。
    assert set(equips_by_category('简易')) & \
        set(EQUIP_ACQUIRE_CONSEQUENCES) == set(), \
        '简易池 ∩ 后果表须为空(效果条目2 效果串恒 1 条前提)'
    assert _NAMED_LEG_ITEM not in EQUIP_ACQUIRE_CONSEQUENCES, \
        '精密拆装扳手 ∉ 后果表(效果条目1 效果串恒 1 条前提)'
    # 精密门表轻断言(锁 6 降级形态):发放精密自身不在判据映射内,
    # gate 恒 None 走纯发放循环 = 零自我拦截的注册面结构前提。
    assert _NAMED_LEG_ITEM not in _NAMED_EQUIP_PRECISE_GATES, \
        '精密门表外(发放精密自身 gate 恒 None,零自我拦截)'
    assert equip_pick in equips_by_category('简易'), '预验证:装备采样 ∈ 简易池'

    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, '精密拆装·银', rand=False, sig=_LSIG,
                               rng=random.Random(_JINGMI_YIN_SEED))
    assert out.placed
    assert gs.active_strategies.value == ['精密拆装·银'], '注册入表'
    # 两条效果条目各就各位:效果条目1 = 精密拆装扳手精确名(具名件名面防护:误名在此
    # 暴露,非静默)、效果条目2 = 随机简易(名 = 采样值,追加序 = 卡文语序)。
    assert gs.equips.value == [_NAMED_LEG_ITEM, equip_pick], \
        'equips 恰 +2 且腿序 = 卡文语序(具名腿先/随机腿后)'
    # 效果串两态分形:恰 2 条,两条效果条目各持本族字面形态(效果条目1 带 placed=<bool> /
    # 效果条目2 无 placed 后缀),跨家族前缀分域可独立过滤,禁并单串。
    assert out.effects == (
        f'named_equip_grant:{_NAMED_LEG_ITEM}(placed=True)',
        f'strategy_random_equip:{equip_pick}',
    ), '效果串恰 2 条且两条效果条目形态字面分明'
    assert rows_sink.kinds() == [], '正常路径零申报行'

    # 表外卡零写:未收录卡查无效果安静不写(gain-chain §3 裁定④),
    # 本卡 +1 注册不改变分派面未收录分支语义。
    seq_before = gs.write_seq
    offtable = on_strategy_gained(gs, '随便一张未收录卡', rand=False,
                                  sig=_LSIG)
    assert offtable == (), '表外卡零效果'
    assert gs.write_seq == seq_before, '表外卡零写'
