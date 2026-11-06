"""降本增效注册面测试(cw_investments 分目录镜像;卖全场族/板面重写族
出售支 + 免费购买族,先例 = 同目录 test_strategy_dacaiyuan_registry.py;
宿主 test_cw_investments.py 超行数线,登记面新锁落本镜像目录)。

测试面依据 = 迭代设计 designs/T-188-jiangben-zengxiao.md §2.1/§4(锁 1)
+ 八裁决点默认案(经族级授权收口,逐点亮判见 designs/REVIEW-T188.md)。
卡面官方原文(cw_invest_data.py:136 逐字):「出售场上和备战席的所有角色，
获得双倍价格的金币。你接下来6次购买角色是免费的。」

- EffectSpec 条目锁(锁 1):id/trigger/duration/category 五元组 +
  素出售载体(board_rewrite=SELL_ALL)+ 免费购买腿 uses 种子
  (duration_uses=6,免战牌机制复用)+ duties predict+track 双置
  (predict=买牌对账须预知免费价;track=次数余量剩余期量);
- 注册值锁:STRATEGY_ECONOMY sell_price_mult == 2.0(官方卡文「双倍
  价格」,建模早于本条目在册,零漂移订正面);
- 交付通道锁:两条效果条目全在获得链只登记不写状态的实现分支,③段效果体表零新增(键集断言
  零联动);
- 发牌判据细分确认锁(义务 6):素出售卡不入 sim 发牌判据集(sim 局
  零假发牌;词表 _DEAL 双值细分在码,本卡注册自动不入集);
- 待建模登记锁(裁决点 7):卡级 PENDING 行存续 + 描述非空 + 现金分
  fail-closed(免费购买腿估值未入现金通道,×2 修饰施径缺口待实采,
  估值塌 0 = 治理账零行为)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    BOARD_REWRITE_SELL_ALL,
    BOARD_REWRITE_SELL_ALL_DEAL,
    DurationKind,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.sim import cw_sim_backend
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    STRATEGY_ECONOMY_PENDING_MODELING,
    strategy_economy_value,
)

_CARD = '降本增效'


def test_jiangben_zengxiao_effect_spec_entry() -> None:
    """锁 1(条目锁):五元组 + 素出售载体 + uses 种子 + duties 双置;
    构建校验复跑不炸(孤儿键/id 双匹配漂移哨在役)。"""
    cw_investments._validate_strategy_effects()
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '202301'
    assert spec.trigger is TriggerKind.INSTANT
    assert spec.duration is DurationKind.ONCE, \
        'ONCE 注记辖出售腿一次性语义(uses 维度独立播种,免战牌机制)'
    assert spec.category is EffectKind.BATTLEFIELD
    assert spec.payload.board_rewrite == BOARD_REWRITE_SELL_ALL, \
        '素出售语义(卡文无发牌句,不入 sim 发牌集)'
    assert spec.duration_uses == 6, '官方卡文「你接下来6次购买角色是免费的」'
    assert spec.duties.predict is True, \
        'predict=买牌对账须预知免费价(同人力重组/大裁员家族)'
    assert spec.duties.track is True, \
        'track=次数余量剩余期量(免战牌 track=True 同形)'
    assert spec.pending is False


def test_jiangben_zengxiao_registry_sell_price_mult() -> None:
    """注册值锁:注册行 sell_price_mult == 2.0(官方卡文「获得双倍价格的
    金币」;注册行 = ×2 修饰估值面对账源,单一条目不可变)。"""
    assert STRATEGY_ECONOMY[_CARD].sell_price_mult == 2.0, \
        '×2 卖价修饰在册(官方卡文 2 倍,无漂移订正面)'


def test_jiangben_zengxiao_delivery_channel_registration_leg() -> None:
    """交付通道锁:两条效果条目全在获得链只登记不写状态的实现分支(STRATEGY_EFFECTS 条目),③段
    效果体表零新增(键集闭集断言零联动)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD in STRATEGY_EFFECTS
    assert _CARD not in PICK_INVEST_EFFECTS, '登记腿交付,③段零新增'


def test_jiangben_zengxiao_not_in_sim_deal_criterion() -> None:
    """发牌判据细分确认锁(义务 6):本卡 ∉ sim 发牌判据集(素出售语义
    值,判据集 = 具发牌腿 _DEAL 值派生)→ sim 局选本卡零假发牌;撤销
    细分(判据回退素出售值过滤)则本卡自动入集、sim 局误发 5 只 2★。"""
    assert _CARD not in cw_sim_backend.SELL_ALL_REWRITE_STRATEGIES, \
        '素出售卡不入发牌判据集(语义值细分)'
    assert BOARD_REWRITE_SELL_ALL_DEAL != BOARD_REWRITE_SELL_ALL


def test_jiangben_zengxiao_pending_modeling_and_cash_failclosed() -> None:
    """待建模登记锁(裁决点 7 默认案):卡级 PENDING 行存续 + 描述非空
    (治理账可见性,零运行时闸);现金分 fail-closed——免费购买腿估值
    未入现金通道,×2 修饰(sell_price_mult)归待建模分类塌 0。"""
    assert _CARD in STRATEGY_ECONOMY_PENDING_MODELING, '卡级 PENDING 行在册'
    assert STRATEGY_ECONOMY_PENDING_MODELING[_CARD], '描述非空'
    gs = game_state_of(SimpleNamespace())
    assert strategy_economy_value(_CARD, gs) == (0.0, False), \
        '现金分 fail-closed(sell_price_mult 待建模塌 0,免费腿无现金通道)'
