"""刷新上报·策略出对条件金币效果条目测试(report_action_refresh_shop_param 镜像)。

锁面 = 「合并同类项」金币效果条目设计与实现(卡面官方原文:「刷新商店时，若刷新的
角色中出现2个相同的角色，获得1金币。获得4次免费刷新。」):随机态效果条目之后挂
策略条件金检查效果条目,``sim_backend_installed()`` 门控——sim 采样即状态副本里的值、
判定成立经观察通道发金;live 采样是猜测,金面禁猜测直写(零写)。本文件锁:

- 锁 2:sim 装配 + 本卡在场 → 出对帧 gold 恰 +1(观察笔形态断言);
- 锁 10(并入锁 2):零 rng——同 seed 双跑(登记/未登记)终态采样流
  state 逐位一致,发放不额外消耗;
- 锁 3:全异名 payload → 零金写;
- 锁 4:live 门控(核心负锁)——未装配 sim 零金写,防门控失效退化成
  猜测写金;附 level 缺读帧同判(调用点在随机态分支 level 判空块内的备案);
- 锁 9:过滤隔离——同触发异载体条目(淘金客 STATE / 采购专员·金
  BATTLEFIELD / 市场干预 ECONOMY-无字段鸭子缺省)零金写。

判读基准:判定 = payload 5 槽非空 card 按 name 计数存在任意名 ≥2、单刷至多
一笔;发金 = ``gs.observe``(sim 状态副本数值面 = 观察通道,禁 logic 写)。
"""
from __future__ import annotations

import random

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import REFRESH_PROB
from sr_od.application.currency_war.kernel import cw_shop_deal
from sr_od.application.currency_war.kernel.cw_action_report import (
    refresh_shop,
    report_action_buy_card_param,
    report_action_close_shop_param,
    report_action_level_up_param,
    report_action_sell_bench_param,
)
from sr_od.application.currency_war.kernel.cw_action_report.refresh_shop import (
    report_action_refresh_shop_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    ShopPayload,
    ShopSlot,
    consume_defect_sink,
    set_defect_sink,
    shop_card_to_container,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionLevelUpParam,
    CwActionRefreshShopParam,
    CwActionSellBenchParam,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_SIG = ChannelSig(family='logic_action', actor='CwActionRefreshShopParam',
                  mode='compute')


class _SimPresenceStub:
    """装配占位后端(仅令 ``sim_backend_installed()`` 为真;本效果条目不触后端
    任何口,触即 AssertionError 响亮——被测门控只读装配槽非 None)。"""

    def screen_identity(self) -> str:
        raise AssertionError('出对金币效果条目不触后端读口')

    def observe(self, screen_name: str) -> object:
        raise AssertionError('出对金币效果条目不触后端观察')

    def visible(self, screen_name: str, area_name: str) -> bool:
        raise AssertionError('出对金币效果条目不触后端门问询')

    def click_answer(self, op: object, screen_name: str, area_name: str,
                     until_find_all: object, until_not_find_all: object):
        raise AssertionError('出对金币效果条目不触后端点击')

    def advance(self, decl: object) -> None:
        raise AssertionError('出对金币效果条目不触后端推进')


@pytest.fixture
def sim_installed():
    """sim 形态:装配占位后端;teardown 必卸(模块槽进程全局)。"""
    cw_sim_ports.install_sim_backend(_SimPresenceStub())
    yield
    cw_sim_ports.uninstall_sim_backend()


def _payload_of(entries: list[tuple[str, int] | None]) -> ShopPayload:
    """定长 5 槽 payload 直构((name, star) 或 None = 空槽;不足补空)。"""
    cards: list[ShopSlot] = []
    for i, entry in enumerate(entries):
        if entry is None:
            cards.append(ShopSlot(kind='empty'))
        else:
            name, star = entry
            cards.append(ShopSlot(
                kind='content',
                card=shop_card_to_container(_card(name, cost=3, star=star,
                                                  x=i))))
    while len(cards) < 5:
        cards.append(ShopSlot(kind='empty'))
    return ShopPayload(cards=cards, refresh_probs={})


def _seed_gs_with_card() -> object:
    """金位已读(30)+ 本卡入册的状态容器(免费帧隔离:显式 free=True 排除
    扣费效果条目/免费扣减效果条目干扰,金面只承载被测效果条目)。"""
    gs = cw4_gs(gold=30, node_fill=False, shop_screen='off')
    gs.effects.register_strategy(STRATEGY_EFFECTS['合并同类项'], (1, 2))
    return gs


def test_sim_pair_refresh_grants_one_gold_and_zero_extra_rng(
        monkeypatch: pytest.MonkeyPatch, sim_installed) -> None:
    """锁 2 + 锁 10:出对帧 gold 恰 +1 观察笔;零 rng = 同 seed 双跑
    (登记/未登记)终态采样流 state 逐位一致。采样面走真采样器
    (drawable_names 钉单名 → 逐槽必同名,出对由采样器原生允许的重复同名
    语义保证);免费帧隔离(显式 free=True)。"""
    monkeypatch.setattr(cw_shop_deal, 'drawable_names',
                        lambda gs, cost: ['希儿'])

    def _run(register: bool) -> tuple[object, random.Random]:
        gs = cw4_gs(gold=30, node_fill=False, shop_screen='off')
        if register:
            gs.effects.register_strategy(STRATEGY_EFFECTS['合并同类项'],
                                         (1, 2))
        rng = random.Random('cw-pair-gold-lock')
        report_action_refresh_shop_param(
            gs, CwActionRefreshShopParam(cost=2), _SIG, free=True, rng=rng)
        return gs, rng

    gs, rng = _run(register=True)
    assert gs.shop.source == 'logic_rand', '随机态分支照常写(前置面)'
    assert gs.gold.value == 31, '出对帧 +1 金(免费帧零扣费干扰)'
    assert gs.gold.source == 'observation', \
        '发金 = 观察通道(sim 状态副本数值面,禁 logic 写)'
    assert gs.gold.evidence == 'strategy_refresh_pair_gold@refresh', \
        '观察笔证据串(判读可辨,带动作帧)'
    _, rng_ctrl = _run(register=False)
    assert rng.getstate() == rng_ctrl.getstate(), \
        '零 rng:发放不消耗采样流(登记/未登记同 seed 终态逐位一致)'


def test_sim_no_pair_no_gold_write(monkeypatch: pytest.MonkeyPatch,
                                   sim_installed) -> None:
    """锁 3:全异名 payload → 零金写(gold 值/来源/证据三面均保持种子态,
    零观察行)。判定输入 = 采样 payload,直构全异名固定 payload 经采样桩
    注入(名称相等性判定与注册表无关,合成名即可)。"""
    payload = _payload_of([('甲', 1), ('乙', 1), ('丙', 1), ('丁', 1),
                           ('戊', 1)])
    monkeypatch.setattr(refresh_shop, 'sample_shop_deal',
                        lambda gs, rng, *, level, probs: payload)
    gs = _seed_gs_with_card()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _SIG, free=True,
        rng=random.Random('cw-pair-neg'))
    assert gs.shop.source == 'logic_rand', '随机态分支照常写(前置面)'
    assert gs.gold.value == 30 and gs.gold.source == 'observation', \
        '无对 → 零金写(值与来源保持种子态)'


def test_live_without_sim_backend_never_writes_pair_gold(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 4(live 门控负锁,核心):未装配 sim(纯实机态)→ 出对帧零金写
    ——防门控失效退化成猜测写金(live 采样是猜测,金面禁猜测直写)。附
    level 缺读帧同判:采样写分支跳写(概率表按级索引),调用点在 level 判空块内
    → 本效果条目同帧零发放(shop 保持离屏 + gold 零写)。"""
    payload = _payload_of([('甲', 1), ('甲', 1), ('乙', 1), None, None])
    monkeypatch.setattr(refresh_shop, 'sample_shop_deal',
                        lambda gs, rng, *, level, probs: payload)
    # 纯实机态(装配槽空;防御性复位,幂等公开口)
    cw_sim_ports.uninstall_sim_backend()
    gs = _seed_gs_with_card()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _SIG, free=True,
        rng=random.Random('cw-pair-live'))
    assert gs.shop.source == 'logic_rand', '随机态分支照常写(采样桩面)'
    assert gs.gold.value == 30 and gs.gold.source == 'observation', \
        'live 门控:出对帧零金写(真值 = 下一入口观察覆盖)'
    # level 缺读帧:整段随机态分支跳写(shop 不写),金币效果条目同帧零发放
    gs2 = cw4_gs(gold=30, level_unread=True, node_fill=False,
                 shop_screen='off')
    gs2.effects.register_strategy(STRATEGY_EFFECTS['合并同类项'], (1, 2))
    report_action_refresh_shop_param(
        gs2, CwActionRefreshShopParam(cost=2), _SIG, free=True,
        rng=random.Random('cw-pair-live'))
    assert gs2.shop.value is None, 'level 缺读 → 随机态分支跳写(离屏保持)'
    assert gs2.gold.value == 30, '同帧零发放(调用点在 level 判空块内)'


@pytest.mark.parametrize('spec_name', ['淘金客', '采购专员·金', '市场干预'])
def test_non_matching_entries_isolated_from_pair_grant(
        monkeypatch: pytest.MonkeyPatch, sim_installed,
        spec_name: str) -> None:
    """锁 9:过滤隔离——仅持同触发异载体条目时出对帧零金写。三形态:
    淘金客(STATE:trigger 命中 category 不中)/ 采购专员·金(BATTLEFIELD:
    两不中)/ 市场干预(ECONOMY 命中但 payload 无 gold_per_refresh_pair 字段
    → 鸭子缺省 0 零授予)。"""
    payload = _payload_of([('甲', 1), ('甲', 1), ('乙', 1), None, None])
    monkeypatch.setattr(refresh_shop, 'sample_shop_deal',
                        lambda gs, rng, *, level, probs: payload)
    gs = cw4_gs(gold=30, node_fill=False, shop_screen='off')
    gs.effects.register_strategy(STRATEGY_EFFECTS[spec_name], (1, 2))
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _SIG, free=True,
        rng=random.Random('cw-pair-isolation'))
    assert gs.gold.value == 30 and gs.gold.source == 'observation', \
        f'{spec_name}:过滤隔离零金写(trigger∧category 双过滤/鸭子缺省 0)'


# ============================================================ M1 投影直测(《商店黑板容器化方案》§4-M1;同 src 按被测方法归并)

# 改写依据(分诊):写入者登记面随「商店单动作循环纳入统一管理」演进——
# 生产写点 actor 现役 = CwScreenShop(cw_screen_shop,登记面已登记),
# 旧名 CwOpBuyCards 已退役;测试模拟生产写入随登记面改名。
_PROJ_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                       mode='compute', group_id='act:CwScreenShop@1')


def _gs_of(**axes):
    """M1 场景种子(原裸帧合成配方承接:节点整域不写、空店离屏;
    域覆盖集与原合成口逐域一致)。"""
    return cw4_gs(node_fill=False, shop_screen='off', **axes)


def _content_of(gs):
    """shop payload content 槽紧缩视图,槽序 (idx, name, star, cost);
    离屏(None)归一空表 = 旧紧缩列表等价读法(三态定长五槽模型,
    用户三态裁定 2026-09-13)。"""
    payload = gs.shop.value
    if payload is None:
        return []
    return [(i, s.card.name, s.card.star or 1, s.card.cost or 0)
            for i, s in enumerate(payload.cards)
            if s.kind == 'content' and s.card is not None]


def _bench_slots(gs):
    """bench 槽位占用签名,槽序 (idx, char_id, star);空槽跳过。"""
    view = gs.bench.value
    if view is None:
        return []
    return [(i, s.unit.char_id, s.unit.star)
            for i, s in enumerate(view.slots)
            if s.kind != 'empty' and s.unit is not None]


def _report_action(gs, action, executed=None):
    """商店域动作单次上报(生产同形):买牌快照三件组与升星分支内聚
    report 函数内,一动作恰一次调用;合计结果的逐域期望态由各案直测
    断言(设计件 §4-M1)。executed 仅对带回执参数的函数透传。"""
    if isinstance(action, CwActionBuyCardParam):
        return report_action_buy_card_param(gs, action, _PROJ_SIG,
                                            executed=executed)
    if isinstance(action, CwActionLevelUpParam):
        return report_action_level_up_param(gs, action, _PROJ_SIG,
                                            executed=executed)
    if isinstance(action, CwActionRefreshShopParam):
        return report_action_refresh_shop_param(gs, action, _PROJ_SIG,
                                                executed=executed)
    if isinstance(action, CwActionSellBenchParam):
        return report_action_sell_bench_param(gs, action, _PROJ_SIG)
    if isinstance(action, CwActionCloseShopParam):
        return report_action_close_shop_param(gs, action, _PROJ_SIG)
    raise AssertionError(f'未覆盖的商店动作类型:{type(action).__name__}')


def test_refresh_paid_deducts_gold_and_samples_rand_payload():
    """付费刷新:gold −状态容器刷价(费用单一源 = ``gs.shop_refresh_cost``
    状态容器直读,2026-10-16 用户裁决,付费计数语义不变);payload = 随机
    态采样(2026-09-21 Field 化 supersession:2026-09-18「终结跳写
    payload 不写」的 payload 半边收窄为 write_logic_rand 随机态——观察
    覆盖差异预期内,采样即猜测)。"""
    gs = _gs_of(gold=30, shop=[_card('希儿')])
    gs.observe(gs.shop_refresh_cost, 2,
               sig=ChannelSig(family='obs', actor='cw_observation'))
    _report_action(gs, CwActionRefreshShopParam(cost=2))
    assert gs.gold.value == 28, 'gold: 期望 30 −状态容器刷价 2'
    assert gs.shop.source == 'logic_rand', \
        'shop payload: 随机态分支采样写(write_logic_rand 专用通道)'
    assert gs.shop.evidence == 'refresh_random_sample', '随机态写端注记'
    assert len(gs.shop.value.cards) == 5, '采样 payload = 定长 5 槽'
    assert _bench_slots(gs) == [], 'bench: 刷新分支零写(保持全空)'
    assert gs.xp.value is None, \
        'xp: 刷新分支零写(未读域保持种子初值 None)'


def test_refresh_free_gold_unwritten():
    """免费帧:金账扣 0(gold 不写——费用清零集中在上报函数免费分支
    同一 free 判定,2026-10-16 用户裁决;free 显式喂 True = sim 形态)。
    Field 扣减语义测试 = 本文件刷新 Field 段
    (test_report_free_leg_deducts_field)。"""
    gs = _gs_of(gold=30, shop=[_card('希儿')])
    gs.write_logic(gs.free_refresh_left, 2, produced_by='test-bridge',
                   sig=ChannelSig(family='logic_hook', actor='cw4_seed'))
    report_action_refresh_shop_param(gs, CwActionRefreshShopParam(cost=2),
                                     _PROJ_SIG, free=True)
    assert gs.gold.value == 30
    assert gs.effects.refresh_paid == 0, '免费帧禁进付费计数'


# ============================================================ 刷新 Field 段(免费刷新次数容器化)

_LSIG = ChannelSig(family='logic_action', actor='CwShopRefreshFieldTest',
                   mode='compute')
_HSIG = ChannelSig(family='logic_hook', actor='CwShopRefreshFieldTest',
                   mode='compute')
_OSIG = ChannelSig(family='obs', actor='CwShopRefreshFieldTest', mode='read')


def _fresh_gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def _spy_write_logic(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """GameState.write_logic 调用面捕获(produced_by 不落 Field,写端
    produced_by/evidence 断言 = 调用面测试):收 (field, value, produced_by,
    evidence) 四元组,调用照常透传。"""
    captured: list[tuple] = []
    real = GameState.write_logic

    def _spy(self: GameState, target, value, **kw):
        captured.append((self._field_name(target), value,
                         kw.get('produced_by'), kw.get('evidence')))
        return real(self, target, value, **kw)

    monkeypatch.setattr(GameState, 'write_logic', _spy)
    return captured


# ---- 动作上报扣减(逻辑态)----


def test_report_free_leg_deducts_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """免费分支扣减:Field 值 > 0 → 免费帧——Field write_logic 扣减(下限 0)
    + 付费计数不动 + 写端 produced_by/evidence 断言。"""
    captured = _spy_write_logic(monkeypatch)
    gs = _fresh_gs()
    gs.observe(gs.level, 3, sig=_OSIG)
    gs.write_logic(gs.free_refresh_left, 2, produced_by='EffectLedgerBridge',
                   evidence='effect_burst@p1-r2', sig=_HSIG)
    captured.clear()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-field-test'))
    assert gs.free_refresh_left.value == 1, '免费帧 Field 扣减 2→1'
    assert gs.free_refresh_left.source == 'logic'
    assert captured == [('free_refresh_left', 1, 'CwActionRefreshShopParam',
                         'proj_refresh_free_left')], '写端调用面元数据'
    assert gs.effects.refresh_paid == 0, '免费帧禁进付费计数'
    assert gs.effects.refresh_total == 1, '全量计数含免费'


def test_market_intervention_burst_then_free_leg_consumes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """市场干预免费帧消费闭环(T-113 设计 §4 锁 4,轻集成):burst 形态
    写端先置免费余额(常量源 = STRATEGY_ECONOMY['市场干预'].
    free_refresh_burst 直读禁写死)→ 刷新上报一次 → Field 扣减
    burst→burst-1 + 免费帧断言(免费判定走 Field;消费链现役零新消费
    端——先例 = test_report_free_leg_deducts_field 同窗形)。"""
    captured = _spy_write_logic(monkeypatch)
    gs = _fresh_gs()
    gs.observe(gs.level, 3, sig=_OSIG)
    burst = STRATEGY_ECONOMY['市场干预'].free_refresh_burst
    gs.write_logic(gs.free_refresh_left, burst,
                   produced_by='EffectLedgerBridge:市场干预',
                   evidence='effect_burst@p1-r2', sig=_HSIG)
    captured.clear()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-field-test'))
    assert gs.free_refresh_left.value == burst - 1, \
        f'免费帧 Field 扣减 {burst}->{burst - 1}'
    assert gs.free_refresh_left.source == 'logic'
    assert captured == [('free_refresh_left', burst - 1,
                         'CwActionRefreshShopParam',
                         'proj_refresh_free_left')], '写端调用面元数据'
    assert gs.effects.refresh_paid == 0, '免费帧禁进付费计数'
    assert gs.effects.refresh_total == 1, '全量计数含免费'


def test_report_unobserved_field_conservative_paid() -> None:
    """未观察(None)→ 保守按付费:计数进 paid,零 Field 扣减行(次数是
    记账面非决策闸);level 同帧缺读 → 随机态分支跳写(概率表按级索引)。
    唯一容器写 = 金币花费置位(T-92:非免费帧与账本 refresh_paid +1 同
    条件置位——「未观察保守按付费」的保守性一并继承到花费口径)。"""
    gs = _fresh_gs()
    seq0 = gs.write_seq
    report_action_refresh_shop_param(gs, CwActionRefreshShopParam(cost=2),
                                     _LSIG)
    assert gs.free_refresh_left.value is None, '未观察 = 不扣减(零 Field 行)'
    assert gs.effects.refresh_paid == 1, '保守按付费计数'
    assert gs.effects.refresh_total == 1
    assert gs.prev_node_spent.value is True, \
        '非免费帧置位(保守按付费一并计花费,T-92)'
    assert gs.write_seq == seq0 + 1, \
        '唯一容器写 = 花费置位行(扣减/随机态两分支跳写不变)'


# ---- 两桥发放(写端元数据)----


def test_grant_bridges_field_write_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """两桥发放写端元数据(值语义测试 = test_game_state 桥面):burst 桥
    produced_by 带效果名 + evidence effect_burst@frame;节点桥
    produced_by 带在场条目名 + evidence effect_node@frame;None 基 = 0
    起算(开局无免费次数 = 机制真值,发放即首次落值)。"""
    captured = _spy_write_logic(monkeypatch)
    gs = _fresh_gs()
    from sr_od.application.currency_war.kernel.cw_game_state import (
        apply_effect_burst_grant,
        grant_effect_node_refresh_balance,
    )
    apply_effect_burst_grant(gs, STRATEGY_EFFECTS['固定理财'], frame='p1-r2')
    assert gs.free_refresh_left.value == 2, 'None 基 = 0 起算'
    assert captured[-1] == ('free_refresh_left', 2,
                            'EffectLedgerBridge:固定理财',
                            'effect_burst@p1-r2'), 'burst 桥写端元数据'
    gs2 = _fresh_gs()
    gs2.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                  acquired_key=(1, 5))
    gs2.effects.advance_node((1, 6))
    grant_effect_node_refresh_balance(gs2, frame='p1-r6')
    assert gs2.free_refresh_left.value == 2, 'None 基 = 0 起算'
    assert captured[-1] == ('free_refresh_left', 2,
                            'EffectLedgerBridge:双手狸开键盘！',
                            'effect_node@p1-r6'), '节点桥写端元数据'


# ---- 刷新随机态分支(kernel 采样器)----


def _seed_for_random_branch() -> GameState:
    """随机态分支场景种子:等级可读(概率表索引)+ 在屏空店(覆盖面已登记)。"""
    gs = _fresh_gs()
    gs.observe(gs.level, 1, sig=_OSIG)
    gs.observe(gs.shop, ShopPayload(cards=[ShopSlot(kind='empty')
                                            for _ in range(5)],
                                    refresh_probs={}), sig=_OSIG)
    return gs


def _slot_signature(payload: ShopPayload) -> list:
    return [(s.kind,
             (s.card.name, s.card.cost, s.card.slot, s.card.star)
             if s.card is not None else None)
            for s in payload.cards]


def test_report_random_leg_deterministic() -> None:
    """随机态分支 = kernel 采样器(sample_shop_deal,与 sim deal_shop 同源):
    固定种子两次独立状态容器采样逐槽一致(确定性);payload 形态 = 定长 5 槽
    content/1★/注册表名 + 基线概率条;写通道 = write_logic_rand 专用通道
    (source=logic_rand + evidence 注记)。"""
    signatures = []
    for _ in range(2):
        gs = _seed_for_random_branch()
        report_action_refresh_shop_param(
            gs, CwActionRefreshShopParam(cost=2), _LSIG,
            rng=random.Random('cw-shop-deal-fixed-seed'))
        payload = gs.shop.value
        assert payload is not None and len(payload.cards) == 5
        assert payload.refresh_probs == {int(k): float(v)
                                         for k, v in REFRESH_PROB[1].items()
                                         if v > 0}, '基线概率条随载荷'
        for slot in payload.cards:
            if slot.card is not None:
                assert slot.card.name in CHARACTERS
                assert slot.card.star == 1, '表外直出恒 1★(U12 + 注册表分支不触发)'
        assert gs.shop.source == 'logic_rand', '随机态专用通道'
        assert gs.shop.evidence == 'refresh_random_sample'
        signatures.append(_slot_signature(payload))
    assert signatures[0] == signatures[1], '固定种子 → 采样确定性'


def test_report_random_leg_rand_outcome_not_andon(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """write_logic_rand 通道语义:随机态采样被下一入口观察覆盖,差异 =
    预期内——只落 logic_rand_outcome 台账行,不进失配安灯三分流(无
    observe_vs_logic_mismatch 行、安灯钩子不触发、无 [cw!] 告警面)。"""
    from sr_od.application.currency_war.kernel import cw_game_state as _gs_mod
    from sr_od.application.currency_war.kernel import (
        cw_mismatch_policy as _policy,
    )

    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    warns: list[tuple] = []
    monkeypatch.setattr(_gs_mod.log, 'warning',
                        lambda *a, **k: warns.append(a))

    gs = _seed_for_random_branch()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-deal-fixed-seed'))
    assert gs.shop.source == 'logic_rand'
    # 下一入口观察覆盖(换一张不同的真值牌面)
    truth = ShopPayload(
        cards=[ShopSlot(kind='content'), ShopSlot(kind='empty'),
               ShopSlot(kind='empty'), ShopSlot(kind='empty'),
               ShopSlot(kind='empty')], refresh_probs={})
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.shop, truth, sig=_OSIG)
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    kinds = [r['kind'] for r in rows]
    assert 'logic_rand_outcome' in kinds, '差异落随机结果台账'
    assert 'observe_vs_logic_mismatch' not in kinds, '不进失配三分流'
    assert fired == [], '安灯不触发(随机落地非 bug)'
    assert not any('观察覆盖 logic 失配' in str(w) for w in warns), \
        '无 [cw!] 告警面'
    assert gs.shop.source == 'observation', '观察赢覆盖照常'


# ---- 观察锚定失配安灯(免费次数 Field 机制白送)----


def test_anchor_covers_logic_mismatch_fires_andon(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """失配对账 = Field 机制白送:动作扣减/发放登记的 logic 值被下一入口
    观察覆盖,失配走既有 observe_vs_logic_mismatch 安灯(缺陷行 + 钩子),
    零手写台账。"""
    from sr_od.application.currency_war.kernel import (
        cw_mismatch_policy as _policy,
    )

    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    gs = _fresh_gs()
    gs.write_logic(gs.free_refresh_left, 1,
                   produced_by='CwActionRefreshShopParam',
                   evidence='proj_refresh_free_left', sig=_LSIG)
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.free_refresh_left, 2, sig=_OSIG)   # 入口实读 2 次 ≠ 账面 1
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert len(rows) == 1 and rows[0]['kind'] == 'observe_vs_logic_mismatch'
    assert fired and fired[0] == rows[0], '既有安灯被调(行同构)'
    assert gs.free_refresh_left.source == 'observation', '观察赢覆盖照常'


# ---- 付费刷新 XP 分支(T-311 淘金客:刷新上报写端付费帧把结果写进
# 状态副本,写分支 = 把结果写进状态副本的实现分支)----


def _seed_xp_leg_gs(*, level: int | None = 3,
                    xp: tuple[int, int] | None = (1, 4),
                    hold_taojinke: bool = True) -> GameState:
    """XP 分支场景种子:level/xp 按参观察(传 None = 未观察形态,None 门
    锁用)+ 在屏空店(随机态分支采样面)+ 持淘金客 = 账本登记(与生产
    选卡入账同一入口;驱动源 = 鸭子类型读取(duck typing) payload.xp_per_refresh)。"""
    gs = _fresh_gs()
    if level is not None:
        gs.observe(gs.level, level, sig=_OSIG)
    if xp is not None:
        gs.observe(gs.xp, xp, sig=_OSIG)
    gs.observe(gs.shop, ShopPayload(cards=[ShopSlot(kind='empty')
                                            for _ in range(5)],
                                    refresh_probs={}), sig=_OSIG)
    if hold_taojinke:
        gs.effects.register_strategy(STRATEGY_EFFECTS['淘金客'],
                                     acquired_key=(1, 5))
    return gs


def test_refresh_paid_xp_leg_world_write(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 1 付费帧把结果写进状态副本(非跨级帧):持卡 + level/xp 在场 →
    付费帧上报 → xp 推进对 +2,写端元数据 evidence='effect_refresh_xp' +
    produced_by='EffectLedgerBridge:淘金客'(署名 = 在场条目名拼接,驱动源 =
    鸭子类型读取 payload.xp_per_refresh 聚合);不持卡零基线对照臂 =
    test_refresh_paid_deducts_gold_and_samples_rand_payload(零 XP 写行,
    xp 保持 None,禁误改)。"""
    captured = _spy_write_logic(monkeypatch)
    gs = _seed_xp_leg_gs(level=3, xp=(1, 4))
    captured.clear()
    out = report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-xp-leg'))
    assert out.applied, 'applied 恒 True(计数职责不受 XP 分支影响)'
    assert gs.level.value == 3, '非跨级帧 level 不写'
    assert gs.xp.value == (3, 4), 'xp: 期望 1+2=3 < lv3 门槛 4 推进不跨级'
    assert [row for row in captured if row[0] == 'xp'] == [
        ('xp', (3, 4), 'EffectLedgerBridge:淘金客', 'effect_refresh_xp'),
    ], 'XP 分支写端元数据(署名 = 在场条目名拼接,evidence 常量词面)'
    assert gs.effects.refresh_paid == 1 and gs.effects.refresh_total == 1, \
        '付费帧计数分支照常'


def test_refresh_paid_xp_leg_cross_level_and_same_frame_deal() -> None:
    """锁 1 跨级结转 + 同帧发牌 level 断言:跨级帧本帧 shop 采样用升级后
    level(XP 分支插入位置 = 随机态分支前,时序假设被结构固定)——采样
    概率条 = 升级后等级的概率表(载荷 refresh_probs 承载,结构断言零
    mock)。"""
    gs = _seed_xp_leg_gs(level=7, xp=(51, 52))
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-xp-leg-cross'))
    assert gs.level.value == 8, '跨级直写 7→8(51+2=53 ≥ lv7 门槛 52)'
    assert gs.xp.value == (1, 72), 'xp: 溢出结转 (1, lv8 门槛 72)'
    payload = gs.shop.value
    assert payload is not None and gs.shop.source == 'logic_rand', \
        '本帧发牌照常(随机态通道)'
    assert payload.refresh_probs == {c: p for c, p in REFRESH_PROB[8].items()
                                     if p > 0}, \
        '同帧发牌用升级后 level(采样概率条 = lv8 表非 lv7 表——插入位置' \
        '在随机态分支前的结构证据)'


def test_refresh_free_xp_leg_zero_write(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 2 免费帧零 XP(Field 免费帧与显式 free=True 两支):XP 分支零
    写行(「消耗金币」排免费刷),计数分支照常(refresh_total+1/refresh_paid
    +0)。"""
    captured = _spy_write_logic(monkeypatch)
    # 支 1:Field 免费帧(登记置剩余次数,免费判定走 Field 值)
    gs = _seed_xp_leg_gs(level=3, xp=(1, 4))
    gs.write_logic(gs.free_refresh_left, 2, produced_by='EffectLedgerBridge',
                   evidence='effect_burst', sig=_HSIG)
    captured.clear()
    report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-xp-leg-free'))
    assert not [row for row in captured if row[0] in ('xp', 'level')], \
        '免费帧零 XP 写行'
    assert gs.xp.value == (1, 4) and gs.xp.source == 'observation', \
        'xp 保持观察值不翻 logic'
    assert gs.effects.refresh_total == 1 and gs.effects.refresh_paid == 0, \
        '计数分支照常(免费帧不进 paid)'
    # 支 2:显式 free=True 帧(sim 形态注入,Field 同置值)
    gs2 = _seed_xp_leg_gs(level=3, xp=(1, 4))
    gs2.write_logic(gs2.free_refresh_left, 1, produced_by='EffectLedgerBridge',
                    evidence='effect_burst', sig=_HSIG)
    captured.clear()
    report_action_refresh_shop_param(
        gs2, CwActionRefreshShopParam(cost=2), _LSIG, free=True,
        rng=random.Random('cw-shop-xp-leg-free'))
    assert not [row for row in captured if row[0] in ('xp', 'level')], \
        '显式免费帧零 XP 写行'
    assert gs2.effects.refresh_total == 1 and gs2.effects.refresh_paid == 0


def test_refresh_xp_leg_none_gate() -> None:
    """锁 3 None 门(grant_xp 原语单一源):level 或 xp 任一未观察 → 零 XP
    写行(无基座不虚构推进对,未读域保持种子原值),applied 恒 True
    (计数职责不受门影响)。"""
    for why, axes in (('level 未观察', {'level': None}),
                      ('xp 未观察', {'xp': None})):
        gs = _seed_xp_leg_gs(**axes)
        out = report_action_refresh_shop_param(
            gs, CwActionRefreshShopParam(cost=2), _LSIG,
            rng=random.Random('cw-shop-xp-leg-none'))
        assert out.applied, f'{why}: applied 恒 True'
        if 'level' in axes:
            assert gs.level.value is None and gs.xp.value == (1, 4), \
                f'{why}: 双域零动作(xp 值/来源不变)'
            assert gs.xp.source == 'observation', f'{why}: xp 不翻 logic'
        else:
            assert gs.xp.value is None and gs.level.value == 3, \
                f'{why}: 双域零动作'
        assert gs.effects.refresh_paid == 1 and gs.effects.refresh_total == 1, \
            f'{why}: 计数分支照常'


def test_refresh_xp_leg_level_cap_skip(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 4 满级封顶(grant_xp 算子零变化跳写单一源):满级局付费帧 → 零
    XP/level 写行(level/xp 值不变),计数分支照常。"""
    captured = _spy_write_logic(monkeypatch)
    gs = _seed_xp_leg_gs(level=10, xp=(0, 4))
    captured.clear()
    out = report_action_refresh_shop_param(
        gs, CwActionRefreshShopParam(cost=2), _LSIG,
        rng=random.Random('cw-shop-xp-leg-cap'))
    assert out.applied
    assert not [row for row in captured if row[0] in ('xp', 'level')], \
        '满级零推进零写行(算子零变化跳写)'
    assert gs.xp.value == (0, 4) and gs.level.value == 10
    assert gs.effects.refresh_paid == 1 and gs.effects.refresh_total == 1, \
        '计数分支照常'
