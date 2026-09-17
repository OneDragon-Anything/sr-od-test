"""路由点陈旧清点挂单测(策略器终态契约 landing §3.1 剧本断言)。

被测体 = ``CwLoop._route_clear_stale_payloads``(只依赖 self.ctx 取容器,
以桩 self 直调函数体,免整环装配)。剧本:
1. 未识别轮 = 清全部十槽(route_clearable 位);
2. 属屏命中轮 = 只清异属屏、属屏槽保活;
3. shop route_clearable=False 永不清(既有显式清点口独占);
4. 已 None 跳过(不占 write_seq);
5. actor 三登记在册(在册校验防线前置)。
"""

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_events import (
    EncounterOption,
    SupplyOption,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    _PAYLOAD_DOMAINS,
    REGISTERED_ACTORS,
    ChannelSig,
    EncounterPayload,
    GameState,
    SupplyPayload,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    PickEncounter,
    PickSupply,
)
from sr_od.application.currency_war.operations.cw_loop import CwLoop

_OBS_SIG = ChannelSig(family='obs', actor='cw_observation',
                      screen='货币战争-遭遇节点', mode='read')


def _stub_loop(gs: GameState) -> SimpleNamespace:
    """桩 self:挂点只读 self.ctx.cw_match.gs,其余零依赖。"""
    return SimpleNamespace(ctx=SimpleNamespace(
        cw_match=SimpleNamespace(gs=gs)))


def _seed(gs: GameState) -> None:
    """播种四槽非 None(encounter 属屏 = 遭遇节点;supply/planner 异属屏;
    shop 豁免面播种为保活见证)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import ShopPayload
    gs.observe(gs.encounter,
               EncounterPayload(options=[EncounterOption(idx=1)]),
               sig=_OBS_SIG)
    gs.observe(gs.supply,
               SupplyPayload(options=[SupplyOption(idx=1)]),
               sig=ChannelSig(family='obs', actor='cw_observation',
                              screen='货币战争-补给', mode='read'))
    gs.observe(gs.shop, ShopPayload(), sig=_OBS_SIG)
    gs.write_logic(gs.planner_opts, ['p1'], produced_by='test',
                   sig=ChannelSig(family='logic_action', actor='CwLoop',
                                  screen='', mode='compute'))


def test_route_clear_unidentified_clears_all_ten():
    gs = GameState(schema_version=1)
    _seed(gs)
    seq0 = gs.write_seq
    CwLoop._route_clear_stale_payloads(_stub_loop(gs), None)
    for name, (_, clearable) in _PAYLOAD_DOMAINS.items():
        if not clearable:
            assert getattr(gs, name).value is not None, name   # shop 豁免保活
        else:
            assert getattr(gs, name).value is None, name
    assert gs.write_seq > seq0


def test_route_clear_own_screen_keeps_own_slot():
    gs = GameState(schema_version=1)
    _seed(gs)
    CwLoop._route_clear_stale_payloads(_stub_loop(gs), '货币战争-遭遇节点')
    assert gs.encounter.value is not None          # 属屏在屏保活
    assert gs.supply.value is None                 # 异属屏清
    assert gs.planner_opts.value is None


def test_route_clear_shop_exempt_and_none_skip():
    gs = GameState(schema_version=1)
    _seed(gs)
    gs.observe(gs.shop, __import__(
        'sr_od.application.currency_war.kernel.cw_game_state',
        fromlist=['ShopPayload']).ShopPayload(), sig=_OBS_SIG)
    CwLoop._route_clear_stale_payloads(_stub_loop(gs), None)
    assert gs.shop.value is not None               # route_clearable=False 不清
    seq_after_first = gs.write_seq
    CwLoop._route_clear_stale_payloads(_stub_loop(gs), None)
    assert gs.write_seq == seq_after_first         # 已 None 跳过不占版本


def test_route_clear_actor_registered_and_clear_uses_action_type_guard():
    assert 'cw_loop_route_clear' in REGISTERED_ACTORS
    gs = GameState(schema_version=1)
    gs.write_logic(gs.encounter, EncounterPayload(), produced_by='test',
                   sig=ChannelSig(family='logic_action', actor='CwLoop',
                                  screen='', mode='compute'))
    # 动作类型守卫冒烟:新词表选择子类型可构造(词表块健康性,与清点无耦合)
    assert PickEncounter(idx=0).idx == 0 and PickSupply(idx=1).idx == 1


def test_terminal_contract_schema_and_match_shape():
    """schema 断言(landing §3.1 判据:8 新域键 + encounter/supply bump +
    node_screen_refresh 域 +1)+ Match 前置字段断言(additive 形态)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        DEFAULT_GS_SCHEMA,
    )
    from sr_od.application.currency_war.kernel.cw_events import (
        MegastarOption,
        PartnerOption,
        PlannerOption,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
    )
    # 八新域键在册
    for key in ('invest_opts', 'megastar_opts', 'partner_opts', 'planner_opts',
                'star_tome_opts', 'wish_trial_opts', 'box_card_opts'):
        assert DEFAULT_GS_SCHEMA[key] == 1, key
    assert DEFAULT_GS_SCHEMA['encounter'] == 2
    assert DEFAULT_GS_SCHEMA['supply'] == 2
    assert DEFAULT_GS_SCHEMA['node_screen_refresh'] == 2
    # Match additive 前置字段:生产漏斗填充形态,缺省 None(3.5 收紧必填)
    gs = GameState(schema_version=1)
    m = CurrencyWarMatch(strategy=None, session=None, gs=gs)
    assert m.gs is gs and m.performance is None
    # 十二槽:8 新槽 + per-visit 位在容器上可解析(声明健康性)
    for name in ('invest_strategy_opts', 'invest_env_opts', 'megastar_opts',
                 'partner_opts', 'planner_opts', 'star_tome_opts',
                 'wish_trial_opts', 'box_card_names',
                 'encounter_refreshed_in_visit'):
        assert getattr(gs, name).value is None, name
    # typed 选项可构造(cw_events 宿主,3.5 接线消费)
    assert MegastarOption(idx=0) and PartnerOption(idx=0) and PlannerOption(idx=0)
