"""回收计划(id 230701)随机腿×延时入队腿组合展开锁(镜像 src =
kernel/cw_gain_effects.py 的 ``PICK_INVEST_EFFECTS['回收计划']`` 组合
登记行;按被测方法拆目录规范落位——test_gain_chain.py 超线冻结禁追加,
新增测试落新镜像,先例 = 同目录姊妹组合卡镜像文件
test_strategy_compose_grant_maicai_plus.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-237-huishou-jihua.md(定稿,落地形态按 REVIEW-T237 §2.5 撞键缺陷
修正)§4 锁 1 + 七裁决点默认案:
- 组合登记 = ``PICK_INVEST_EFFECTS['回收计划'] = _compose_grant_legs(
  _make_random_equip_effect('进阶', 1), _make_delayed_only_grant_effect(
  '回收计划'))``(腿序 = 卡文语序即时随机腿先/延时入队腿后;随机腿
  参数登记行单次出现,单一源;不入随机装备泛化表——同名键 dict 顺序
  覆盖静默丢即时腿,负断言锁死回退双面撞键形态);
- 固定 rng 注入链发放真值:rng 消费序 = 仅第 1 抽装备(进阶池,入队腿
  零采样面)——腿序改排/入队腿预掷 = 采样漂移,被同序对拍捕获;效果串
  恰 2 条且两腿形态字面分明(腿1 ``strategy_random_equip:<名>`` 无
  placed 后缀 / 腿2 ``strategy_grant_scheduled:随机简易(类别池)@5``
  池标记形,跨家族前缀分域可独立过滤);
- 前提守卫:「效果串恒 2 条」前提 = 进阶池 ∩ ``EQUIP_ACQUIRE_
  CONSEQUENCES`` = ∅(设计 §1.3 级联普查,装备注册表扩员时守卫先红,
  勿盲改主锁断言数);
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
    _STRATEGY_RANDOM_EQUIP_GRANTS,
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

_CARD = '回收计划'

#: 固定种子(单抽形态无互异约束,任意种子;失配 = 换种子)。
_HUISHOU_SEED = 20261102


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


def test_huishou_compose_legs_chain_in_order(rows_sink: _RowSink) -> None:
    """组合腿锁(设计 §4 锁 1):gain_invest_strategy 确定入口(rand=
    False)+ 固定 rng 注入 → equips 恰 +1(腿1 名 = 采样值 ∈ 进阶池
    派生集禁手抄清单)、效果串恰 2 条且顺序 = 卡文语序(随机腿串在前/
    入队腿池标记形在后)、入队腿零采样(同序预采样对拍)、正常路径零
    申报行;泛化表零键负断言(撞键缺陷防线:组合卡误入泛化表 = 同名键
    dict 顺序覆盖丢即时腿);表外卡零写(未收录卡安静不写,本卡注册不
    扰动分派面)。"""
    # 前提守卫(设计 §4 前提注记):破前提时任一腿获得后果链追加串,
    # 「效果串恒 2 条」失效——守卫先红,勿盲改断言数。
    assert set(equips_by_category('进阶')) & \
        set(EQUIP_ACQUIRE_CONSEQUENCES) == set(), \
        '进阶池 ∩ 后果表须为空(腿1 效果串恒 1 条前提)'
    # 预采样(独立 rng 实例按消费序恰 1 抽):与实际注入的 rng 同种子
    # 同序——入队腿若预掷(消费第 2 抽)不影响首抽名,故另以效果串腿序
    # 与队列值共同钉死「入队腿零采样」(scheduled 串只含节拍不含采样值,
    # 预掷与否在串面不可见,由 discharge 侧零预掷锁兜底)。
    equip_pick = roll_random_equip(random.Random(_HUISHOU_SEED), '进阶')
    assert equip_pick in equips_by_category('进阶'), '预验证:采样 ∈ 进阶池'

    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG,
                               rng=random.Random(_HUISHOU_SEED))
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    # 腿1 = 随机进阶(名 = 采样值)、腿2 = 延时入队(池标记形,登记值
    # @5 源自 STRATEGY_DELAYED_GRANTS 行)。
    assert gs.equips.value == [equip_pick], \
        'equips 恰 +1(即时随机腿)'
    assert out.effects == (
        f'strategy_random_equip:{equip_pick}',
        'strategy_grant_scheduled:随机简易(类别池)@5',
    ), '效果串恰 2 条且两腿形态字面分明'
    assert gs.pending_strategy_grants.value == ((_CARD, 5),), \
        f'队列值: {gs.pending_strategy_grants.value}'
    assert rows_sink.kinds() == [], '正常路径零申报行'
    # 撞键缺陷防线(设计稿 §2.3 形态修正的负向锁):泛化表零本卡键——
    # 误入表 = 泛化表 spread(字面量前段)被组合行覆盖丢即时腿,或表行
    # 单腿体覆盖组合体,两形皆静默丢腿。
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '组合卡误入随机装备泛化表(同名键覆盖丢腿形态回退)'

    # 表外卡零写:未收录卡查无效果安静不写(gain-chain §3 裁定④)。
    seq_before = gs.write_seq
    offtable = on_strategy_gained(gs, '随便一张未收录卡', rand=False,
                                  sig=_LSIG)
    assert offtable == (), '表外卡零效果'
    assert gs.write_seq == seq_before, '表外卡零写'
