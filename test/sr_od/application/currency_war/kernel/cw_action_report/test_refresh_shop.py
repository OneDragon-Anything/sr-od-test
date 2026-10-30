"""刷新上报·策略出对条件金腿测试(report_action_refresh_shop_param 镜像)。

锁面 = 「合并同类项」金腿设计与实现(卡面官方原文:「刷新商店时，若刷新的
角色中出现2个相同的角色，获得1金币。获得4次免费刷新。」):随机态腿之后挂
策略条件金检查腿,``sim_backend_installed()`` 门控——sim 采样即世界真值、
判定成立经观察通道发金;live 采样是猜测,金面禁猜测直写(零写)。本文件锁:

- 锁 2:sim 装配 + 本卡在场 → 出对帧 gold 恰 +1(观察笔形态断言);
- 锁 10(并入锁 2):零 rng——同 seed 双跑(登记/未登记)终态采样流
  state 逐位一致,发放不额外消耗;
- 锁 3:全异名 payload → 零金写;
- 锁 4:live 门控(核心负锁)——未装配 sim 零金写,防门控失效退化成
  猜测写金;附 level 缺读帧同判(挂点在随机态分支 level 判空块内的备案);
- 锁 9:过滤隔离——同触发异载体条目(淘金客 STATE / 采购专员·金
  BATTLEFIELD / 市场干预 ECONOMY-无字段鸭子缺省)零金写。

判读锚:判定 = payload 5 槽非空 card 按 name 计数存在任意名 ≥2、单刷至多
一笔;发金 = ``gs.observe``(sim 世界数值面 = 观察通道,禁 logic 写)。
"""
from __future__ import annotations

import random

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel import cw_shop_deal
from sr_od.application.currency_war.kernel.cw_action_report import refresh_shop
from sr_od.application.currency_war.kernel.cw_action_report.refresh_shop import (
    report_action_refresh_shop_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopPayload,
    ShopSlot,
    shop_card_to_container,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionRefreshShopParam,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_SIG = ChannelSig(family='logic_action', actor='CwActionRefreshShopParam',
                  mode='compute')


class _SimPresenceStub:
    """装配占位后端(仅令 ``sim_backend_installed()`` 为真;本腿不触后端
    任何口,触即 AssertionError 响亮——被测门控只读装配槽非 None)。"""

    def screen_identity(self) -> str:
        raise AssertionError('出对金腿不触后端读口')

    def observe(self, screen_name: str) -> object:
        raise AssertionError('出对金腿不触后端观察')

    def visible(self, screen_name: str, area_name: str) -> bool:
        raise AssertionError('出对金腿不触后端门问询')

    def click_answer(self, op: object, screen_name: str, area_name: str,
                     until_find_all: object, until_not_find_all: object):
        raise AssertionError('出对金腿不触后端点击')

    def advance(self, decl: object) -> None:
        raise AssertionError('出对金腿不触后端推进')


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
    """金位已读(30)+ 本卡入册的容器(免费帧隔离:显式 free=True 排除
    扣费腿/免费扣减腿干扰,金面只承载被测腿)。"""
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
        '发金 = 观察通道(sim 世界数值面,禁 logic 写)'
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
    level 缺读帧同判:采样腿跳写(概率表按级索引),挂点在 level 判空块内
    → 本腿同帧零发放(shop 保持离屏 + gold 零写)。"""
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
    # level 缺读帧:整段随机态分支跳写(shop 不写),金腿同帧零发放
    gs2 = cw4_gs(gold=30, level_unread=True, node_fill=False,
                 shop_screen='off')
    gs2.effects.register_strategy(STRATEGY_EFFECTS['合并同类项'], (1, 2))
    report_action_refresh_shop_param(
        gs2, CwActionRefreshShopParam(cost=2), _SIG, free=True,
        rng=random.Random('cw-pair-live'))
    assert gs2.shop.value is None, 'level 缺读 → 随机态分支跳写(离屏保持)'
    assert gs2.gold.value == 30, '同帧零发放(挂点在 level 判空块内)'


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
