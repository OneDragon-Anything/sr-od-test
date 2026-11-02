"""公司军火更新·金(id 230601)随机简易装备发放锁(镜像 src = kernel/
cw_gain_effects.py 的泛化随机装备表 ``_STRATEGY_RANDOM_EQUIP_GRANTS``
'公司军火更新·金' 行('简易', 2)+ 工厂 ``_make_random_equip_effect('简易', 2)``
经 ``PICK_INVEST_EFFECTS`` 生成式注册;按被测方法拆目录规范落位——
test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_random_equip_grant_gongsi_junhuo_yin.py 银卡(count=1))。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-236 对应稿
§4(REVIEW-T236 免裁 9/9;卡面官方原文:「获得2件随机简易装备」;count=2
放回抽 = T-167 判例直引——同 rng 两次采样可重复同名;变异腿不属本文件
辖域,登记形态 = 同目录 test_gain_invest_strategy_equips_reroll.py):

- 固定 rng 注入链发放真值(行身份锁):equips 恰 +2、两件同名 = 采样值
  (放回抽语义)、效果串恰 2 条 ``strategy_random_equip:<名>``;
- equips 未观察拒落跳写形态:效果串恒登记 2 条 skipped 形态。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
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

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '公司军火更新·金'

#: 固定种子(采样名失配 = 换种子,禁手抄池清单)。
_SIMPLE_SEED = 20261203


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
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
    """缺陷台账行收集(镜像银卡锁同名,装配 + 必达收尾)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


def test_gold_two_equip_leg_chain_places_two() -> None:
    """链发放真值(行身份锁):确定入口+固定 rng → equips 恰 +2、两件
    同名 = 采样值(放回抽 T-167 判例:同 rng 两次采样可重复同名)、
    效果串恰 2 条、active_strategies 入表;正常路径零申报行。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    rng0 = random.Random(_SIMPLE_SEED)
    pick = roll_random_equip(rng0, '简易')
    pick2 = roll_random_equip(rng0, '简易')
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=random.Random(_SIMPLE_SEED))
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert gs.equips.value == [pick, pick2], \
        f'equips 恰 +2 = 两采样值(放回抽序): {gs.equips.value}'
    assert out.effects == (f'strategy_random_equip:{pick}',
                           f'strategy_random_equip:{pick2}'), \
        f'效果串恰 2 条: {out.effects}'
    assert len(out.effects) == 2, 'count=2 逐件一条'


def test_gold_two_equip_leg_unobserved_skip_two() -> None:
    """equips 未观察形态锁:拒落跳写、效果串恒登记 2 条 skipped 形态
    (发放事实与落位成败解耦,银卡同构)。"""
    gs = _make_gs(bench=[])   # equips 不种 = 域未观察
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=random.Random(_SIMPLE_SEED))
    assert out.placed
    assert gs.equips.value is None, '未观察域零写'
    assert len(out.effects) == 2, f'效果串恒登记 2 条: {out.effects}'
    assert all(e.endswith('(skipped)') and
               e.startswith('strategy_random_equip:') for e in out.effects), \
        f'skipped 形态: {out.effects}'
