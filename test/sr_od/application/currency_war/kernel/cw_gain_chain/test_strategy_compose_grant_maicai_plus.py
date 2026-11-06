"""买彩票+(id 110102)两条效果条目组合展开锁(镜像 src = kernel/cw_gain_effects.py
的 ``PICK_INVEST_EFFECTS['买彩票+']`` 组合登记行;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新增测试落新镜像,先例 = 同目录
姊妹组合卡镜像文件 test_strategy_compose_grant(_plus).py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-137-maicai-piao-plus.md(定稿)§4 锁 2 + REVIEW-T137 七裁决点默认案:
- 组合登记 = ``PICK_INVEST_EFFECTS['买彩票+'] = _compose_grant_legs(
  _make_random_equip_effect('星徽', 1), _make_named_equip_grant_effect(
  '冶金炉', 1))``(条目序 = 卡文语序随机效果条目先/具名效果条目后;效果条目参数登记行单次
  出现,单一源;不入随机装备泛化表——同名键 dict 顺序覆盖丢效果条目);
- 固定 rng 注入链发放真值:rng 消费序 = 仅第 1 抽装备(星徽池,效果条目2 具名
  确定发放零采样面)——条目序改排即采样名漂移,被顺序断言捕获;效果串恰
  2 条且两条效果条目形态字面分明(效果条目1 ``strategy_random_equip:<名>`` 无 placed
  后缀 / 效果条目2 ``named_equip_grant:<名>(placed=<bool>)`` 带 placed 形态,
  跨家族前缀分域可独立过滤);
- 前提守卫:「效果串恒 2 条」前提 = 星徽池 ∩ ``EQUIP_ACQUIRE_
  CONSEQUENCES`` = ∅ 且冶金炉 ∉ 后果表(设计 §1.2d/§4 锁 5 前提注记)
  ——装备注册表扩员(新件带获得后果)时守卫先红,提示语义变化,勿盲改
  主锁断言数;
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
_MAICAI_PLUS_SEED = 20261102

#: 效果条目2 发放物 = 具名确定(卡文【冶金炉】直读,效果串字面断言基准)。
_NAMED_LEG_ITEM = '冶金炉'


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


def test_maicai_plus_compose_legs_chain_in_order(rows_sink: _RowSink) -> None:
    """组合效果条目锁(设计 §4 锁 2):gain_invest_strategy 确定入口(rand=False)
    + 固定 rng 注入 → equips 恰 +2 且两条效果条目各就各位(效果条目1 名 = 采样值 ∈ 星徽池
    派生集禁手抄清单、效果条目2 == 冶金炉精确名)、效果串恰 2 条且顺序 = 卡文语序
    (随机效果条目串在前)两条效果条目形态字面分明、正常路径零申报行;表外卡零写(未收录
    卡安静不写,本卡注册不扰动分派面)。rng 恰 1 次语义由预采样同序对拍锁
    首——「恰 1 次」= 正常径契约,池空漂移态 rng 行为归 T-136 载体锁辖域
    (设计 §4 锁 2 边界注记)。"""
    # 预采样(独立 rng 实例按消费序 1 抽):与实际注入的 rng 同种子同序,
    # 条目序改排(具名效果条目先) = 采样名漂移,顺序断言必红(改序 = 掷序漂移)。
    rng = random.Random(_MAICAI_PLUS_SEED)
    equip_pick = roll_random_equip(rng, '星徽')
    # 前提守卫(设计 §4 锁 5 前提注记):破前提时任一效果条目获得后果链追加串,
    # 「效果串恒 2 条」失效——守卫先红,勿盲改断言数。
    assert set(equips_by_category('星徽')) & \
        set(EQUIP_ACQUIRE_CONSEQUENCES) == set(), \
        '星徽池 ∩ 后果表须为空(效果条目1 效果串恒 1 条前提)'
    assert _NAMED_LEG_ITEM not in EQUIP_ACQUIRE_CONSEQUENCES, \
        '冶金炉 ∉ 后果表(效果条目2 效果串恒 1 条前提)'
    assert equip_pick in equips_by_category('星徽'), '预验证:装备采样 ∈ 星徽池'

    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, '买彩票+', rand=False, sig=_LSIG,
                               rng=random.Random(_MAICAI_PLUS_SEED))
    assert out.placed
    assert gs.active_strategies.value == ['买彩票+'], '注册入表'
    # 两条效果条目各就各位:效果条目1 = 随机星徽(名 = 采样值,追加序 = 卡文语序)、
    # 效果条目2 = 冶金炉精确名(具名件名面防护:误名在此暴露,非静默)。
    assert gs.equips.value == [equip_pick, _NAMED_LEG_ITEM], \
        'equips 恰 +2 且条目序 = 卡文语序(随机效果条目先/具名效果条目后)'
    # 效果串两态分形:恰 2 条,两条效果条目各持本族字面形态(效果条目1 无 placed 后缀 /
    # 效果条目2 带 placed=<bool>),跨家族前缀分域可独立过滤,禁并单串。
    assert out.effects == (
        f'strategy_random_equip:{equip_pick}',
        f'named_equip_grant:{_NAMED_LEG_ITEM}(placed=True)',
    ), '效果串恰 2 条且两条效果条目形态字面分明'
    assert rows_sink.kinds() == [], '正常路径零申报行'

    # 表外卡零写:未收录卡查无效果安静不写(gain-chain §3 裁定④),
    # 本卡 +1 注册不改变分派面未收录分支语义。
    seq_before = gs.write_seq
    offtable = on_strategy_gained(gs, '随便一张未收录卡', rand=False,
                                  sig=_LSIG)
    assert offtable == (), '表外卡零效果'
    assert gs.write_seq == seq_before, '表外卡零写'
