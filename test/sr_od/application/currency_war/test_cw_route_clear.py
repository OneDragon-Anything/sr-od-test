"""路由点陈旧清点挂单测(策略器终态契约 landing §3.1 剧本断言)。

被测体 = ``CwLoop._route_clear_stale_payloads``(只依赖 self.ctx 取容器,
以桩 self 直调函数体,免整环装配)。剧本:
1. 未识别轮 = 清全部十槽(route_clearable 位);
2. 属屏命中轮 = 只清异属屏、属屏槽保活;
3. shop route_clearable=False 永不清(既有显式清点口独占);
4. 已 None 跳过(不占 write_seq)。
"""

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_events import (
    EncounterOption,
    SupplyOption,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    _PAYLOAD_DOMAINS,
    ChannelSig,
    EncounterPayload,
    GameState,
    SupplyPayload,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickEncounterParam,
    CwActionPickSupplyParam,
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


def test_route_clear_uses_action_type_guard():
    gs = GameState(schema_version=1)
    gs.write_logic(gs.encounter, EncounterPayload(), produced_by='test',
                   sig=ChannelSig(family='logic_action', actor='CwLoop',
                                  screen='', mode='compute'))
    # 动作类型守卫冒烟:新词表选择子类型可构造(词表块健康性,与清点无耦合)
    assert CwActionPickEncounterParam(idx=0).idx == 0 and CwActionPickSupplyParam(idx=1).idx == 1


def test_terminal_contract_schema_and_match_shape(monkeypatch):
    """schema 断言(七新域键在册——终态契约八新槽,invest_opts 辖两
    字段;+ encounter/supply bump + node_screen_refresh 域 +1)+ Match
    前置字段断言(additive 形态)。"""
    from sr_od.application.currency_war.kernel import cw_strategy_session
    # 本测试零策略语义:中性化状态附着(全量下他测注册的工厂会摸 None.session)
    monkeypatch.setattr(cw_strategy_session, 'ensure_strategy_state_attached',
                        lambda session: None)
    from sr_od.application.currency_war.kernel.cw_events import (
        MegastarOption,
        PartnerOption,
        PlannerOption,
    )
    from sr_od.application.currency_war.kernel.cw_game_state import (
        DEFAULT_GS_SCHEMA,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
    )
    # 七新域键在册(终态契约八新槽,invest_opts 辖两字段;
    # megastar_opts 随选择坐标观察上报收敛批扩 MegastarOption.xy,
    # 按 game_state/fields.md §3.4.5a「B 类 typed 扩 xy = 域版本自现值
    # bump 一档」bump 至 2;同款先例 = expert_invite payload 扩坐标字段)
    for key in ('invest_opts', 'partner_opts', 'planner_opts',
                'star_tome_opts', 'wish_trial_opts', 'box_card_names'):
        assert DEFAULT_GS_SCHEMA[key] == 1, key
    assert DEFAULT_GS_SCHEMA['megastar_opts'] == 2
    assert DEFAULT_GS_SCHEMA['encounter'] == 2
    assert DEFAULT_GS_SCHEMA['supply'] == 2
    assert DEFAULT_GS_SCHEMA['node_screen_refresh'] == 4
    # Match additive 前置字段:生产漏斗填充形态,缺省 None(3.5 收紧必填)
    gs = GameState(schema_version=1)
    m = CurrencyWarMatch(strategy=None, session=None, gs=gs)
    assert m.gs is gs and m.performance is None
    # 十二槽:8 新槽经 getattr 同名域字段在容器上可解析(声明健康性);
    # box_card_names 的 schema 键与字段同名,invest 两槽属合并域
    # 'invest_opts' 显式例外
    for name in ('invest_strategy_opts', 'invest_env_opts', 'megastar_opts',
                 'partner_opts', 'planner_opts', 'star_tome_opts',
                 'wish_trial_opts', 'box_card_names'):
        assert getattr(gs, name).value is None, name
    # typed 选项可构造(cw_events 宿主,3.5 接线消费)
    assert MegastarOption(idx=0) and PartnerOption(idx=0) and PlannerOption(idx=0)


def test_single_field_slot_schema_keys_align_with_field_names():
    """schema 域键 ↔ 槽字段名同名对齐(登记漂移防线)。正向辖域 =
    九个在册单字段槽域键(非 ``_opts`` 后缀成员 = box_card_names/
    box_card_names_xy/expert_invite)双向同名断言(域键在册 ∧ 字段在册);
    反向辖域 = ``_opts`` 型域键(除 invest_opts 合并标签)必须为字段名。
    组域语义域名键(node/units/economy 等)无 ``_opts`` 后缀天然不入;
    invest_opts 为唯一显式豁免。新增槽域须同步扩正向清单。"""
    from dataclasses import fields

    from sr_od.application.currency_war.kernel.cw_game_state import (
        DEFAULT_GS_SCHEMA,
        GameState,
    )
    single_field_slots = (
        'megastar_opts', 'partner_opts', 'planner_opts',
        'star_tome_opts', 'wish_trial_opts', 'box_card_names',
        'box_card_names_xy', 'fortune_opts', 'expert_invite',
    )
    field_names = {f.name for f in fields(GameState)}
    for name in single_field_slots:
        assert name in DEFAULT_GS_SCHEMA, name
        assert name in field_names, name
    for key in DEFAULT_GS_SCHEMA:
        if key.endswith('_opts') and key != 'invest_opts':
            assert key in field_names, key


def test_hp_direct_read_after_anchor_retirement():
    """hp 直读对照(landing §3.2 判据:门简化为 gs.hp 直读,结算覆盖写端
    在场场景)。终态契约 §A:锚退役后 decision_hp = gs.hp 直读——
    ①结算覆盖写端写入 → 读口立即反映(「结算即写」时序保持);
    ②锚字段不再影响读口(旧锚在场与否零差异 = 单一源成立);
    ③可信位语义不变(observation/carried 可信,prior/logic fail-closed)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import GameState
    from sr_od.application.currency_war.kernel.cw_hp_policy import (
        decision_hp,
        hp_decision_trusted_of,
    )
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )

    sess = StrategySession()
    sess.last_hp = 77          # 旧锚残留(已无写端,模拟迁移期残值)
    sess.last_hp_t = 9
    gs = GameState(schema_version=1)
    _sig = ChannelSig(family='obs', actor='cw_observation',
                      screen='货币战争-结算', mode='read')
    # 结算覆盖写端(§3.5.1 语义:观察直写)→ 读口反映现值,旧锚零影响
    gs.observe(gs.hp, 80, sig=_sig)
    assert decision_hp(gs, sess) == 80
    assert hp_decision_trusted_of(gs) is True
    # carried 语义(失读沿用)= 可信位 True,读口同值
    gs.carry(gs.hp, frame=1, sig=ChannelSig(family='obs', actor='cw_observation',
                                            screen='货币战争-备战', mode='carried'))
    assert decision_hp(gs, sess) == 80
    assert hp_decision_trusted_of(gs) is True
    # 锚字段在场不产生任何覆盖(旧门行为已退役:锚不再回写读口)
    assert decision_hp(gs, sess) == 80
