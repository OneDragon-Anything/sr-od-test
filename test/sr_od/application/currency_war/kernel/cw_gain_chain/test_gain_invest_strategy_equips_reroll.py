"""公司军火更新·银(id 130101)登记形态锁(镜像 src = kernel/cw_investments.py
STRATEGY_EFFECTS 银条目 + kernel/cw_effect_inventory.py BattlefieldEffect.
equips_reroll 字段与 EQUIPS_REROLL_SAME_QUALITY 词表;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,登记区新锁落本拆目录,先例 =
同目录 test_gain_invest_strategy_* 镜像文件;锁形承同族先例公司人才流动
102101 登记形态两锁)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-138-gongsi-junhuo-gengxin-yin.md(定稿)§4 锁 2/锁 3:
- 变异腿登记形态(session 选入 → 账本条目四元组 + payload 词表值 +
  duties.track 置位;锁登记形态与词表值,防裸串漂移与载体误配);
- 三桥 no-op 负断言哨(限定当前 spec 形态 = NODE_ENTER / WHILE_HELD /
  BATTLEFIELD + equips_reroll-only payload;桥 no-op 本质 = 桥 docstring
  契约——payload 无对应字段或缺省零;族扩展批若合法给 equips_reroll 接
  执行桥,须随批改哨)。

双腿并存结构由本文件(STRATEGY_EFFECTS 在账)+ 发放腿链锁合取承载;
发放腿(「获得1件随机简易装备」)链面 = 同目录
test_strategy_random_equip_grant_gongsi_junhuo_yin.py(两注册面分域,
不经组合子)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EQUIPS_REROLL_SAME_QUALITY,
    DurationKind,
    EffectKind,
    TriggerKind,
    apply_board_rewrite,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    apply_effect_burst_grant,
    grant_effect_node_refresh_balance,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


def _make_gs() -> GameState:
    """观测面空装配(bench/equips 两域观察为空集;镜像 test_gain_chain.
    _make_gs 同名形态,本卡登记面只涉账本与注册两域)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    return gs


def test_gain_invest_strategy_equips_reroll_register_shape() -> None:
    """公司军火更新·银 登记形态锁:session 选入 → 账本条目形态 =
    NODE_ENTER / WHILE_HELD / BATTLEFIELD + payload.equips_reroll 词表值
    (防裸串漂移与载体误配)+ duties.track 置位(账本可见性,无
    predict/respond 消费面)。发放腿(选卡落地简易装备入栏)不属本锁
    辖域,由发放腿链锁承载。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), '公司军火更新·银', rand=False,
                         sig=_LSIG)
    assert gs.active_strategies.value == ['公司军火更新·银'], '注册入表'
    entry = gs.effects.first('130101')
    assert entry is not None, '账本登记非空'
    spec = entry.spec
    assert spec.trigger == TriggerKind.NODE_ENTER, '触发 = 节点进入'
    assert spec.duration == DurationKind.WHILE_HELD, '持续期 = 持有绑定'
    assert spec.category == EffectKind.BATTLEFIELD, '类别 = 战场改变'
    assert spec.payload.equips_reroll == EQUIPS_REROLL_SAME_QUALITY, \
        '词表值单一源(禁裸串漂移)'
    assert spec.duties.track, 'duties.track 置位'
    assert not spec.duties.predict and not spec.duties.respond, \
        'predict/respond 不设(现役读链无预知/姿态消费面)'


def test_gain_invest_strategy_equips_reroll_bridges_noop() -> None:
    """公司军火更新·银 变异面零执行端负断言哨(限定当前 spec 形态 =
    NODE_ENTER / WHILE_HELD / BATTLEFIELD + equips_reroll-only payload):
    三桥逐一调全 no-op——burst 桥零 Field 行 / 板面重写桥返回 None /
    节点边界桥免费余额零增。桥 no-op 本质 = 桥 docstring 契约(payload
    无对应字段或缺省零),本锁增量 = 本条目形态哨;变异面零逻辑写端
    (游戏侧每节点自行变异,bot 备战帧 equips 整表观察收真值),
    族扩展批若合法接执行桥须随批改本锁。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), '公司军火更新·银', rand=False,
                         sig=_LSIG)
    spec = gs.effects.first('130101').spec
    seq_after_gain = gs.write_seq
    apply_effect_burst_grant(gs, spec)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, 'burst 桥 no-op(零 Field 行)'
    assert apply_board_rewrite(gs, spec) is None, '板面重写桥 no-op'
    assert gs.write_seq == seq_after_gain, '板面重写桥零写'
    grant_effect_node_refresh_balance(gs)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, '节点边界桥零授予(免费余额零增)'
