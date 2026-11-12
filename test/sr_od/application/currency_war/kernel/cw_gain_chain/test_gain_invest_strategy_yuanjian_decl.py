"""gain_invest_strategy 随机策略发放申报行测试(镜像 src =
kernel/cw_gain_chain.py 的 gain_invest_strategy 名单分支 + STRATEGY_
GRANT_DECL 常量;按被测方法拆目录规范落位,先例 = 同目录
test_gain_invest_strategy_pick_grant.py)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 3 + §2.2(kernel
申报行,裁决点 4 默认案 = 内联名单分支):
- 名单卡两形各一行:rand=False/True 写通道两形同产申报行(申报与写通道
  无关——申报对象是「获得机制本身」的随机掷骰留证,非写通道语义);
- 非名单卡闭集零行:注册表派生对照(代表卡跨三品质 + 效果条目② granted 金名
  场景)零申报行——名单单一源 = STRATEGY_RANDOM_GRANTS,表外卡获得
  零掷骰语义,行为 fail-closed 同构(ENV_REROLL_DECL 实机(live)和模拟器(sim)两边分道先例)。
构造沿现役获得链测试先例:GameState 直构(取安静未收录卡/注册表已登记
卡,席位/道具/效果域零触碰)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    STRATEGY_GRANT_DECL,
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_RANDOM_GRANTS,
)

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(前清防他测残留、后清防本测外泄;形态 =
    sim/test_sim_backend._isolate_defect_buffer 同款,kernel 侧自带
    同形——该 fixture 住各自文件本地不可跨文件复用)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


@pytest.mark.parametrize('rand', [False, True])
def test_yuanjian_grant_decl_one_row(rand: bool,
                                     _isolate_defect_buffer) -> None:
    """名单卡申报行(rand 两形参数化):远见获得 → STRATEGY_GRANT_DECL
    恰一行(选择时点真值不可观察,申报留证);状态容器注册照常(行为
    fail-closed——申报行外零字段写操作差异)。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    out = gain_invest_strategy(gs, None, '远见', rand=rand, sig=_LSIG)
    assert out.placed, '状态容器注册照常(fail-closed 形态)'
    assert '远见' in (gs.active_strategies.value or []), '注册入列'
    kinds = [r['kind'] for r in rows]
    assert kinds.count(STRATEGY_GRANT_DECL) == 1, \
        f'申报行恰一行(rand={rand}): {kinds}'
    row = next(r for r in rows if r['kind'] == STRATEGY_GRANT_DECL)
    assert '远见' in str(row.get('actual', '')), \
        f'申报行携带获得事实: {row!r}'


def test_non_member_zero_rows(_isolate_defect_buffer) -> None:
    """非名单卡闭集零行:注册表派生对照(跨三品质代表卡 + 效果条目② granted
    金名获得场景)零 STRATEGY_GRANT_DECL 行——名单单一源 =
    STRATEGY_RANDOM_GRANTS,表外卡获得零掷骰语义。"""
    rows: list[dict] = []
    set_defect_sink(rows.append)
    representatives = [
        '随便一张未收录卡',                      # 安静未收录卡(先例构造)
        '躺平',                                  # 现役已登记卡(银)
        '免费午餐',                              # 金池 ∩ STRATEGY_EFFECTS
        '这么大的钻石',                          # 棱彩(宝钻联动卡)
    ]
    granted_like = [n for n, s in INVESTMENT_STRATEGIES.items()
                    if s.rarity == STRATEGY_RANDOM_GRANTS['远见']][0]
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    for name in [*representatives, granted_like]:
        gain_invest_strategy(gs, None, name, rand=False, sig=_LSIG)
    kinds = [r['kind'] for r in rows]
    assert kinds.count(STRATEGY_GRANT_DECL) == 0, \
        f'非名单卡闭集零申报行(含 granted 名获得): {kinds}'
    assert granted_like in (gs.active_strategies.value or []), \
        'granted 名注册照常(申报行缺位非状态容器缺位)'
