"""画面观察上报端口锁(kernel/cw_screen_report 包;迭代
2026-09-18-screen-op-flat-report T-1 kernel 基座)。

三面锁(同动作族 test_cw_action_report_contract 形态;零真实副作用,
纯容器直驱):

1. 完备锁:遍历包内全部 obs 类,断言「非推进型 ↔ report_screen_<snake>_obs
   在场;推进型/商店框 ↔ 不在场」+ 统一签名形态 (gs, obs, *, sig=None);
2. 逐 report 接口写入锁:obs 桩值 → 空白容器(GameState 直构,仓内
   惯例)→ 调 report → 断言容器域值与来源;门语义(空不写/恒写空表/
   简报三闸/过渡链防御)单独成测;
3. 渠道签名锁:缺省 sig 构造逐位沿用现役写点原值(family/actor/screen/
   mode)——经状态流水捕获行断言(sink/run_id 官方注入槽,monkeypatch
   测试结束自动还原)的行为锁。

纪律:串行、零识别零点击零真实 IO、不断言容器写入行为以外的东西。
"""
import importlib
import inspect
import re

import pytest

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel.cw_events import (
    EncounterOption,
    MegastarOption,
    PartnerOption,
    PlannerOption,
    SupplyOption,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    EncounterPayload,
    ExpertInvitePayload,
    GameState,
    NodeChain,
    SupplyPayload,
    TokenCell,
)

_PKG = 'sr_od.application.currency_war.kernel.cw_screen_report'

#: 包内全部画面文件(包 ``__init__`` 不暴露模块,项目惯例 → 显式点名;
#: 新增屏文件必须登记到此处,漏登记 = 完备锁红)。
_SCREENS = (
    # 含 report 的 23 屏(18 实体写点 + 5 文档化占位)
    'encounter', 'megastar', 'equip_pick', 'partner', 'planner', 'fortune',
    'bookcard', 'expert_invite', 'supply_node', 'invest_env',
    'invest_strategy', 'wish_trial', 'box_pick', 'briefing',
    'plane_transition', 'armory_box', 'boss_briefing', 'wait_one_one',
    'deploy_not_full', 'battle_wait', 'plane_intel', 'prep', 'buy_cards',
    # 推进型/商店框 12 屏(无 report)
    'next_button', 'plane_detail', 'consumable_overlay',
    'emblem_detail_popup', 'item_detail_popup', 'interrupt_dialog',
    'refresh_odds_popup', 'role_detail_overlay', 'shop_card_detail',
    'prep_locked_return', 'aha_equip_pick', 'open_shop',
)

#: 推进型/商店框(空决策形态,无 report 接口;design.md §2.2)。
#: 名单外的 obs 类默认必须带 report 函数——新增屏漏归侧即红。
#: (关店编排壳 obs 行随壳退役删除,迭代 2026-09-21-shop-refresh-terminal
#:  3.4:CloseShop 执行位收编进 CwActionCloseShopOp,孤儿 obs 文件随壳退役。)
_NO_REPORT = frozenset({
    'CwScreenNextButtonObs', 'CwScreenPlaneDetailObs',
    'CwScreenConsumableOverlayObs', 'CwScreenEmblemDetailPopupObs',
    'CwScreenItemDetailPopupObs', 'CwScreenInterruptDialogObs',
    'CwScreenRefreshOddsPopupObs', 'CwScreenRoleDetailOverlayObs',
    'CwScreenShopCardDetailPopupObs', 'CwScreenPrepLockedReturnObs',
    'CwScreenAhaEquipPickObs', 'CwOpOpenShopObs',
})

#: 文档化占位 report(现役零观察容器写点,统一形态占位)。
#: (prep 已于重型屏迁移批升级为真实写面——可选域字段在场才写,见
#:  _WRITE_CASES['prep'] 与 prep 专项锁;plane_intel 已于接管域迭代
#:  2026-09-20-takeover-intel-pipeline 升级为真实写面——采集真值写门,
#:  见 _WRITE_CASES['plane_intel'] 与写门专项锁;boss_briefing 已于
#:  2026-09-20-node-advance-action-report 切换批升级为真实写面——BOSS
#:  类型直定(目标 = 现 hist),写门/直定专项锁归 test_cw_node_chain 与
#:  test_cw_game_state_contract 节点域锁;buy_cards 保持占位:
#:  唯一候选写点 = 段头 gold 救援补写,属入口观察链内纠正补写,勘察
#:  结论申报在 kernel 屏文件模块头,不收编交后续批裁决。)
_PLACEHOLDERS = ('armory_box', 'wait_one_one',
                 'deploy_not_full', 'battle_wait', 'buy_cards')

_TEST_SIG = ChannelSig(family='logic_action', actor='TestSigWriter',
                       mode='compute')


def _blank_gs() -> GameState:
    """空白容器(仓内 cw kernel 测试惯例构造)。"""
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def _screen_module(screen: str):
    return importlib.import_module(f'{_PKG}.{screen}')


def _obs_class(mod) -> type:
    """每文件恰一个 obs 类(本模块内定义且 ``Obs`` 后缀)。"""
    found = [obj for _, obj in inspect.getmembers(mod, inspect.isclass)
             if obj.__module__ == mod.__name__ and obj.__name__.endswith('Obs')]
    assert len(found) == 1, f'{mod.__name__} 应恰含一个 obs 类,实得 {found}'
    return found[0]


def _report_fn_name(cls_name: str) -> str:
    """命名规约:obs 类去 ``CwScreen``/``CwOp`` 前缀去 ``Obs`` 后缀转 snake。"""
    core = cls_name
    if core.startswith('CwScreen'):
        core = core[len('CwScreen'):]
    elif core.startswith('CwOp'):
        core = core[len('CwOp'):]
    if core.endswith('Obs'):
        core = core[:-len('Obs')]
    return f'report_screen_{re.sub(r"(?<!^)(?=[A-Z])", "_", core).lower()}_obs'


# ============================================================ 1. 完备锁


def test_completeness_report_presence_matches_screen_form():
    """完备锁:非推进型 ↔ report 函数在场;推进型/商店框 ↔ 不在场。"""
    names = set()
    for screen in _SCREENS:
        mod = _screen_module(screen)
        cls = _obs_class(mod)
        names.add(cls.__name__)
        fn = getattr(mod, _report_fn_name(cls.__name__), None)
        if cls.__name__ in _NO_REPORT:
            assert fn is None, \
                f'{cls.__name__} 为推进型/商店框,禁设 report 函数'
        else:
            assert callable(fn), \
                f'{cls.__name__} 漏建 {_report_fn_name(cls.__name__)}'
    assert len(names) == len(_SCREENS), '跨文件重名 obs 类'
    assert names.issuperset(_NO_REPORT), '无 report 名单与包内实际类漂移'


def test_report_signature_unified_shape():
    """统一形态 (gs, obs, *, sig=None)——与动作族「一个上报概念一个形状」
    同约定,禁额外位置参/聚合入参。"""
    for screen in _SCREENS:
        mod = _screen_module(screen)
        cls = _obs_class(mod)
        if cls.__name__ in _NO_REPORT:
            continue
        fn = getattr(mod, _report_fn_name(cls.__name__))
        params = list(inspect.signature(fn).parameters.values())
        assert len(params) == 3, f'{fn.__name__} 形参面偏离统一形态'
        assert [p.name for p in params[:2]] == ['gs', 'obs']
        assert all(p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
                   for p in params[:2])
        assert params[2].name == 'sig'
        assert params[2].kind is inspect.Parameter.KEYWORD_ONLY
        assert params[2].default is None


# ============================================================ 2. 逐接口写入锁


def _case_encounter(m):
    opts = [EncounterOption(idx=0, difficulty=2),
            EncounterOption(idx=1, difficulty=3)]
    return (m.CwScreenEncounterObs(options=opts, refresh_left=2),
            {'encounter': (EncounterPayload(options=opts), 'logic'),
             'encounter_refresh_left': (2, 'logic')})


def _case_megastar(m):
    opts = [MegastarOption(idx=0, char_id='三月七')]
    return (m.CwScreenMegastarObs(in_node=True, options=opts),
            {'megastar_opts': (opts, 'logic')})


def _case_equip_pick(m):
    opts = ['装备甲', '装备乙', '装备丙']
    return (m.CwScreenEquipPickObs(on_screen=True, options=opts),
            {'equip_pick_opts': (opts, 'logic')})


def _case_partner(m):
    opts = [PartnerOption(idx=0, char_id='丹恒')]
    return (m.CwScreenPartnerObs(on_screen=True, options=opts),
            {'partner_opts': (opts, 'logic')})


def _case_planner(m):
    opts = [PlannerOption(idx=0, text='甲卡'), PlannerOption(idx=1, text='乙卡')]
    return (m.CwScreenPlannerObs(on_screen=True, options=opts),
            {'planner_opts': (opts, 'logic')})


def _case_fortune(m):
    opts = ['强化甲', '强化乙', '强化丙']
    return (m.CwScreenFortuneObs(on_screen=True, options=opts),
            {'fortune_opts': (opts, 'logic')})


def _case_bookcard(m):
    opts = ['巡猎', '丰饶']
    return (m.CwScreenBookcardObs(on_screen=True, options=opts),
            {'star_tome_opts': (opts, 'logic')})


def _case_expert_invite(m):
    bonds = ['巡猎', None, '丰饶', None]
    board = {'巡猎': 2}
    return (m.CwScreenExpertInviteObs(on_screen=True, card_bonds=bonds,
                                      board=board),
            {'expert_invite': (ExpertInvitePayload(card_bonds=bonds,
                                                   board=board), 'logic')})


def _case_supply_node(m):
    opts = [SupplyOption(idx=0, char='三月七', equip='记忆镜',
                         has_diamond=True)]
    return (m.CwScreenSupplyNodeObs(in_node=True, options=opts,
                                    refresh_left=2),
            {'supply': (SupplyPayload(options=opts), 'logic'),
             'supply_refresh_left': (2, 'logic')})


def _case_invest_env(m):
    return (m.CwScreenInvestEnvObs(hit=True, options=[('轮岗', 400)]),
            {'invest_env_opts': (['轮岗'], 'logic')})


def _case_invest_strategy(m):
    return (m.CwScreenInvestStrategyObs(entry_ok=True,
                                        options=[('抢先体验', 300, 500)]),
            {'invest_strategy_opts': (['抢先体验'], 'logic')})


def _case_wish_trial(m):
    return (m.CwScreenWishTrialObs(on_screen=True, options=['objective甲']),
            {'wish_trial_opts': (['objective甲'], 'logic')})


def _case_box_pick(m):
    return (m.CwScreenBoxPickObs(on_screen=True,
                                 card_names=['铁驭头盔', '开拓脊角']),
            {'box_card_names': (['铁驭头盔', '开拓脊角'], 'logic')})


def _case_briefing(m):
    return (m.CwScreenBriefingObs(on_screen=True, enemy_affixes=['词缀甲'],
                                  plane_bosses=['幻胧'], enemy_difficulty=3),
            {'enemy_affixes': (['词缀甲'], 'logic'),
             'plane_bosses': (['幻胧'], 'logic'),
             'enemy_difficulty': (3, 'logic')})


def _case_plane_transition(m):
    chain = NodeChain(plane=1, seq=[TokenCell('battle', 'hu', 0.1)])
    return (m.CwScreenPlaneTransitionObs(on_screen=True, chain=chain),
            {'node_path': (chain, 'observation'),
             'node_path_baseline': (chain, 'observation')})


def _case_prep(m):
    chain = NodeChain(plane=1, seq=[TokenCell('battle', 'hu', 0.1)])
    return (m.CwScreenPrepObs(node_path_chain=chain),
            {'node_path': (chain, 'observation'),
             'node_path_baseline': (chain, 'observation')})


def _case_plane_intel(m):
    return (m.CwScreenPlaneIntelObs(on_screen=True,
                                    plane_bosses=['幻胧', '巨鹿生物制药',
                                                  '镜泊影卫'],
                                    enemy_affixes=['灼热轰炸']),
            {'plane_bosses': (['幻胧', '巨鹿生物制药', '镜泊影卫'], 'logic'),
             'enemy_affixes': (['灼热轰炸'], 'logic')})


#: 逐实体 report 接口的 obs 桩与期望容器终值(字段 → (期望值, 期望来源);
#: 门语义不在此表,见空桩/分屏闸专项)。
_WRITE_CASES = {
    'encounter': _case_encounter,
    'megastar': _case_megastar,
    'equip_pick': _case_equip_pick,
    'partner': _case_partner,
    'planner': _case_planner,
    'fortune': _case_fortune,
    'bookcard': _case_bookcard,
    'expert_invite': _case_expert_invite,
    'supply_node': _case_supply_node,
    'invest_env': _case_invest_env,
    'invest_strategy': _case_invest_strategy,
    'wish_trial': _case_wish_trial,
    'box_pick': _case_box_pick,
    'briefing': _case_briefing,
    'plane_transition': _case_plane_transition,
    'prep': _case_prep,
    'plane_intel': _case_plane_intel,
}


@pytest.mark.parametrize('screen', sorted(_WRITE_CASES))
def test_report_writes_stub_obs_into_container(screen):
    """逐 report 接口:obs 桩值 → 空白容器 → 断言容器域值与来源。"""
    mod = _screen_module(screen)
    obs, expected = _WRITE_CASES[screen](mod)
    gs = _blank_gs()
    fn = getattr(mod, _report_fn_name(_obs_class(mod).__name__))
    fn(gs, obs)
    for field_name, (want_value, want_source) in expected.items():
        fld = getattr(gs, field_name)
        assert fld.value == want_value, f'{screen}.{field_name} 容器域值不符'
        assert fld.source == want_source, \
            f'{screen}.{field_name} 来源渠道不符'


#: 空桩门语义:候选空 = 原「读得才写」早退闸不写(None);原写点无空门
#: 的屏空表照写([])——防线逐位平移,不加强不减弱。
_EMPTY_OBS_CASES = {
    # 摄入序锁(迭代 2026-09-21-event-refresh-unify-supply-pick 3.3):
    # options 空 = 整函数早退不写含 left——left 读得(3)也不入容器。
    'encounter': (lambda m: m.CwScreenEncounterObs(refresh_left=3),
                  {'encounter': None, 'encounter_refresh_left': None}),
    'megastar': (lambda m: m.CwScreenMegastarObs(), {'megastar_opts': None}),
    'partner': (lambda m: m.CwScreenPartnerObs(), {'partner_opts': None}),
    'bookcard': (lambda m: m.CwScreenBookcardObs(), {'star_tome_opts': None}),
    'supply_node': (lambda m: m.CwScreenSupplyNodeObs(), {'supply': None}),
    'invest_env': (lambda m: m.CwScreenInvestEnvObs(),
                   {'invest_env_opts': None}),
    'invest_strategy': (lambda m: m.CwScreenInvestStrategyObs(),
                        {'invest_strategy_opts': None}),
    'equip_pick': (lambda m: m.CwScreenEquipPickObs(),
                   {'equip_pick_opts': []}),
    'planner': (lambda m: m.CwScreenPlannerObs(), {'planner_opts': []}),
    'fortune': (lambda m: m.CwScreenFortuneObs(), {'fortune_opts': []}),
    'wish_trial': (lambda m: m.CwScreenWishTrialObs(),
                   {'wish_trial_opts': []}),
    'box_pick': (lambda m: m.CwScreenBoxPickObs(), {'box_card_names': []}),
}


@pytest.mark.parametrize('screen', sorted(_EMPTY_OBS_CASES))
def test_empty_stub_gate_semantics(screen):
    """空桩门语义:候选空时的容器终态逐屏对照原写点闸。"""
    make_obs, expected = _EMPTY_OBS_CASES[screen]
    mod = _screen_module(screen)
    gs = _blank_gs()
    fn = getattr(mod, _report_fn_name(_obs_class(mod).__name__))
    fn(gs, make_obs(mod))
    for field_name, want in expected.items():
        assert getattr(gs, field_name).value == want, \
            f'{screen}.{field_name} 空桩门语义不符'


def test_briefing_write_semantics():
    """简报写语义(统一读写口径):三字段读到非空恒覆写(重读自愈
    首次误读)/ 读空跳过写(读缺=跳过写,瞬时 OCR 失手不擦同局已读
    真值;跨局残留由每局容器冷建/丢弃挡死)。"""
    mod = _screen_module('briefing')
    gs = _blank_gs()
    gs.write_logic(gs.enemy_affixes, ['已有词缀'],
                   produced_by='TestSigWriter', sig=_TEST_SIG)
    gs.write_logic(gs.plane_bosses, ['旧boss', None, None],
                   produced_by='TestSigWriter', sig=_TEST_SIG)
    gs.write_logic(gs.enemy_difficulty, 2,
                   produced_by='TestSigWriter', sig=_TEST_SIG)
    # 读到非空 → 恒覆写
    obs = mod.CwScreenBriefingObs(on_screen=True, enemy_affixes=['新词缀'],
                                  plane_bosses=['新boss', None, None],
                                  enemy_difficulty=9)
    mod.report_screen_briefing_obs(gs, obs)
    assert gs.enemy_affixes.value == ['新词缀'], '词缀读到必写(恒覆写)'
    assert gs.plane_bosses.value == ['新boss', None, None], \
        'boss 读到必写(恒覆写,None 槽保位)'
    assert gs.enemy_difficulty.value == 9, '难度读到必写(恒覆写)'
    # 读空 → 跳过写(不擦已读真值)
    obs_empty = mod.CwScreenBriefingObs(on_screen=True, enemy_affixes=[],
                                        plane_bosses=None, enemy_difficulty=None)
    mod.report_screen_briefing_obs(gs, obs_empty)
    assert gs.enemy_affixes.value == ['新词缀'], '词缀读空跳过写'
    assert gs.plane_bosses.value == ['新boss', None, None], 'boss 读空跳过写'
    assert gs.enemy_difficulty.value == 9, '难度读空跳过写'


def test_plane_intel_write_gates():
    """位面情报写门两件(接管域迭代 design §2.3):boss 已有真值不覆写
    (简报源先落 = 真值已在,实采不冲真值)/ 词缀幂等门(仅容器空时写;
    空读数 = 无词缀不落写,空表覆写会把真值抹成「无数据」)。"""
    mod = _screen_module('plane_intel')
    # boss 已有真值(简报源,含 None 槽)→ 跳写;词缀空读数 → 不写
    gs = _blank_gs()
    gs.write_logic(gs.plane_bosses, ['简报boss', None, None],
                   produced_by='TestSigWriter', sig=_TEST_SIG)
    mod.report_screen_plane_intel_obs(gs, mod.CwScreenPlaneIntelObs(
        on_screen=True, plane_bosses=['实采甲', '实采乙', '实采丙'],
        enemy_affixes=[]))
    assert gs.plane_bosses.value == ['简报boss', None, None], \
        'boss 已有真值不覆写'
    assert gs.enemy_affixes.value is None, '词缀空读数不落写'
    # 词缀已有 → 幂等门不重写;boss 无真值 → 全量写
    gs2 = _blank_gs()
    gs2.write_logic(gs2.enemy_affixes, ['已有词缀'],
                    produced_by='TestSigWriter', sig=_TEST_SIG)
    mod.report_screen_plane_intel_obs(gs2, mod.CwScreenPlaneIntelObs(
        on_screen=True, plane_bosses=['实采甲', '实采乙', '实采丙'],
        enemy_affixes=['新词缀']))
    assert gs2.enemy_affixes.value == ['已有词缀'], '词缀幂等门:已有不重写'
    assert gs2.plane_bosses.value == ['实采甲', '实采乙', '实采丙'], \
        'boss 无真值 = 3 槽保位全量写'
    assert gs2.plane_bosses.source == 'logic', '写门 = logic 直写'


def test_plane_intel_channel_sig_fixed_shape(monkeypatch):
    """位面情报写门渠道签名 = 定死形状(logic_action/CwScreenPlaneIntel/
    screen=货币战争-位面详情/compute;evidence = plane_intel_row /
    plane_intel_affixes),经状态流水捕获行断言;screens 行签名逐位对照。"""
    rows: list[dict] = []
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: 'test-run')
    mod = _screen_module('plane_intel')
    gs = _blank_gs()
    mod.report_screen_plane_intel_obs(gs, mod.CwScreenPlaneIntelObs(
        on_screen=True, plane_bosses=['甲', '乙', '丙'],
        enemy_affixes=['词缀']))
    got = {(r['field'],
            r['sig']['family'], r['sig']['actor'],
            r['sig']['screen'], r['sig']['mode'])
           for r in rows if r['row'] == 'write'}
    assert got == {
        ('plane_bosses', 'logic_action', 'CwScreenPlaneIntel',
         '货币战争-位面详情', 'compute'),
        ('enemy_affixes', 'logic_action', 'CwScreenPlaneIntel',
         '货币战争-位面详情', 'compute'),
    }, f'写门渠道签名偏离定死形状: {got}'
    assert gs.plane_bosses.evidence == 'plane_intel_row', \
        'boss 行 evidence = 实采语义段'
    assert gs.enemy_affixes.evidence == 'plane_intel_affixes', \
        '词缀行 evidence = 实采语义段'


def test_plane_transition_chain_defenses():
    """过渡链防御逐位平移:非开局且节点镜像缺禁猜跳写 / chain 缺诚实缺位 /
    基线幂等门(基线已有不覆写)。"""
    mod = _screen_module('plane_transition')
    chain = NodeChain(plane=1, seq=[TokenCell('battle', 'hu', 0.1)])

    # 非开局且镜像缺:行归属位面不可知 → 全跳
    gs = _blank_gs()
    gs.node_hist_ord = 5
    mod.report_screen_plane_transition_obs(
        gs, mod.CwScreenPlaneTransitionObs(on_screen=True, chain=chain))
    assert gs.node_path.value is None
    assert gs.node_path_baseline.value is None

    # chain 缺(行空/读缺):诚实缺位 → 全跳
    gs2 = _blank_gs()
    mod.report_screen_plane_transition_obs(
        gs2, mod.CwScreenPlaneTransitionObs(on_screen=True, chain=None))
    assert gs2.node_path.value is None

    # 开局但基线已有:现行链写、基线幂等门不覆写
    gs3 = _blank_gs()
    existing = NodeChain(plane=1, seq=[TokenCell(None, 'none')])
    gs3.observe(gs3.node_path_baseline, existing,
                sig=ChannelSig(family='obs', actor='TestSigWriter',
                               mode='read'))
    mod.report_screen_plane_transition_obs(
        gs3, mod.CwScreenPlaneTransitionObs(on_screen=True, chain=chain))
    assert gs3.node_path.value == chain
    assert gs3.node_path_baseline.value == existing


def test_prep_optional_domains_field_presence_after_takeover_retirement():
    """备战可选域字段在场才写(接管域退役批后契约:链域 = 唯一可选写域):
    - 全 None obs(仅 prep 整包缺省)→ 零写(占位语义存续面);
    - 接管域四字段(takeover_tries/takeover_collect_done/plane_bosses/
      enemy_affixes)已随编排单一源退役出 obs 类(零残留断言)。"""
    import dataclasses

    mod = _screen_module('prep')
    field_names = {f.name for f in dataclasses.fields(mod.CwScreenPrepObs)}
    assert 'node_path_chain' in field_names, '链域可选写域存续'
    for retired in ('takeover_tries', 'takeover_collect_done',
                    'plane_bosses', 'enemy_affixes'):
        assert retired not in field_names, f'接管域字段应已退役:{retired}'
    # 全 None → 零写
    gs = _blank_gs()
    mod.report_screen_prep_obs(gs, mod.CwScreenPrepObs())
    assert gs.write_seq == 0, '全 None 可选域 = 本轮无此面,零写'


def test_prep_chain_baseline_idempotent_gate():
    """备战链域基线幂等门(与位面过渡链同款防线):现行链照写、基线已有
    不覆写;sig 形参透传(原写点观察渠道链,actor 不受限缺省)。"""
    mod = _screen_module('prep')
    chain = NodeChain(plane=1, seq=[TokenCell('battle', 'hu', 0.1)])
    existing = NodeChain(plane=2, seq=[TokenCell(None, 'none')])
    gs = _blank_gs()
    gs.observe(gs.node_path_baseline, existing,
               sig=ChannelSig(family='obs', actor='TestChainSigWriter',
                              mode='read'))
    mod.report_screen_prep_obs(
        gs, mod.CwScreenPrepObs(node_path_chain=chain),
        sig=ChannelSig(family='obs', actor='TestChainSigWriter',
                       mode='read'))
    assert gs.node_path.value == chain, '现行链照写'
    assert gs.node_path_baseline.value == existing, '基线幂等门不覆写'


def test_placeholder_report_is_documented_noop():
    """轻屏/重型屏占位:接口在场、零容器写(摄入面出现时落此处;
    占位不构造不校验 sig——无写即无渠道面)。"""
    for screen in _PLACEHOLDERS:
        mod = _screen_module(screen)
        cls = _obs_class(mod)
        fn = getattr(mod, _report_fn_name(cls.__name__))
        gs = _blank_gs()
        fn(gs, cls())
        assert gs.write_seq == 0, f'{screen} 占位 report 不得写容器'


# ============================================================ 3. 渠道签名锁


#: 缺省 sig 原值表(逐位沿用各画面现役写点):
#: screen → (family, actor, screen, mode)。
_DEFAULT_SIGS = {
    'encounter': ('logic_action', 'CwScreenEncounter', None, 'compute'),
    'megastar': ('logic_action', 'CwScreenMegastar', None, 'compute'),
    'equip_pick': ('logic_action', 'CwScreenEquipPick', None, 'compute'),
    'partner': ('logic_action', 'CwScreenPartner', None, 'compute'),
    'planner': ('logic_action', 'CwScreenYinLang', None, 'compute'),
    'fortune': ('logic_action', 'CwScreenFortune', None, 'compute'),
    'bookcard': ('logic_action', 'CwScreenBookcard', None, 'compute'),
    'expert_invite': ('logic_action', 'CwScreenExpertInvite', None, 'compute'),
    'supply_node': ('logic_action', 'CwScreenSupplyNode', None, 'compute'),
    'invest_env': ('logic_action', 'CwScreenInvestEnv', None, 'compute'),
    'invest_strategy': ('logic_action', 'CwScreenInvestStrategy', None,
                        'compute'),
    'wish_trial': ('logic_action', 'CwScreenWishTrial', None, 'compute'),
    'box_pick': ('logic_action', 'CwScreenBoxPick', None, 'compute'),
    'briefing': ('logic_action', 'CwScreenBriefing', '', 'compute'),
    'plane_transition': ('obs', 'CwScreenPlaneTransition',
                         '货币战争-位面过渡', 'read'),
    'prep': ('obs', 'CwScreenPrep', '货币战争-备战', 'read'),
}


@pytest.mark.parametrize('screen', sorted(_DEFAULT_SIGS))
def test_default_sig_matches_live_write_point(monkeypatch, screen):
    """缺省 sig 构造 = 现役写点原值;经状态流水捕获行断言(sink/run_id
    官方注入槽,monkeypatch 测试结束自动还原)。"""
    rows: list[dict] = []
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: 'test-run')
    mod = _screen_module(screen)
    obs = _WRITE_CASES[screen](mod)[0]
    gs = _blank_gs()
    fn = getattr(mod, _report_fn_name(_obs_class(mod).__name__))
    fn(gs, obs)
    want = _DEFAULT_SIGS[screen]
    got = {(r['sig']['family'], r['sig']['actor'], r['sig']['screen'],
            r['sig']['mode'])
           for r in rows if r['row'] == 'write'}
    assert got, f'{screen} 缺省调用未产生状态流水写入行'
    assert got == {want}, f'{screen} 缺省 sig 偏离原写点原值: {got}'


def test_report_sig_family_mismatch_rejected():
    """显式 sig 渠道族校验在场(与动作族 buy_card 同构;越族渠道禁收)。"""
    mod = _screen_module('encounter')
    gs = _blank_gs()
    bad = ChannelSig(family='obs', actor='CwScreenEncounter', mode='read')
    with pytest.raises(ValueError):
        mod.report_screen_encounter_obs(
            gs, mod.CwScreenEncounterObs(
                options=[EncounterOption(idx=0, difficulty=1)]), sig=bad)
