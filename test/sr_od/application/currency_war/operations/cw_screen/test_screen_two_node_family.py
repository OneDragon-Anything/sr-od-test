"""节点循环族 8 屏两 node 形态测试()。

测试的语义(测试纪律:只校验新形态的核心约定,先例 = test_obs_arch_event_
screens.py 盛会之星段;report 函数级契约由 test_screen_report_ports 测试
承重,本文件不重复):

- **观察上报接入调用测试**(表驱动;命运卜者双域拆独立测试):观察 node 读链桩化 →
  驱动 observe →
  report 经屏文件落容器(容器终值);盛会之星接入调用由 obs_arch_event_screens
  同文件测试承重(懒读保真,不在本表);
- **入口门语义测试**(带门四屏):门 miss = round_fail 交回外循环重判,
  文案沿用现役,且不进读链(obs 不装载);
- **chosen 写时机测试**(祈愿试炼代表):确认已发 → 标识不在 = 选卡落地
  → 此刻才写 chosen_wish + success 交回;标识在 = 未落地 → 不写、重走
  (chosen_* 动作事实边界留守重入裁决点);
- **决策动作 node 测试**(银狼策划,无门单发型):决策从容器零参读
  (决策调用形态不变)→ 组装 equip(分支类型载荷 classify_planner_branch)→
  点卡链派发 → 派发即 round_success 终结(零重入裁决轮;即时上报迭代
  。原装备三选一代表测试
  随该屏误判退役删除)。

驱动方式 = 真类实例(构造走 __init__)+ 读链/门/机械点击链桩化,节点
函数直驱(run_node 外壳)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel.cw_events import PartnerOption, PlannerOption
from sr_od.application.currency_war.kernel.cw_game_state import (
    ExpertInvitePayload,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

_FRAME = object()   # 稳定帧哨兵(读链桩只验传递不断言内容)

_CW_SCREEN_PKG = 'sr_od.application.currency_war.operations.cw_screen'


class _StubOcr:
    """ocr_service 桩(get_ocr_result_map/list 程序化回值)。"""

    def __init__(self, map_result: dict | None = None,
                 list_result: list | None = None) -> None:
        self._map = map_result or {}
        self._list = list_result or []

    def get_ocr_result_map(self, image, rect=None, color_range=None,
                           crop_first=False):
        return self._map

    def get_ocr_result_list(self, image, crop_first=False):
        return self._list


def _mrl(x: float, y: float) -> SimpleNamespace:
    """OCR 结果行桩(max.center.x/y 消费面)。"""
    return SimpleNamespace(max=SimpleNamespace(center=SimpleNamespace(x=x, y=y)))


def _make_match(session: StrategySession, **strategy) -> SimpleNamespace:
    """局内 match 桩(session 挂容器;策略入口按屏注入零参决策桩)。"""
    match = SimpleNamespace(session=session, strategy=SimpleNamespace(**strategy))
    match.gs = game_state_of(session)
    return match


def _setup_bookcard(op, monkeypatch) -> None:
    """星徽秘典读链桩(全屏 OCR「X星徽」→ 阵营名 + x 中心)。"""
    monkeypatch.setattr(
        op.ctx, 'ocr_service',
        _StubOcr(list_result=[SimpleNamespace(data='列车同行星徽', x=700,
                                              y=100, w=120, h=30)]),
        raising=False)


def _setup_expert(op, monkeypatch) -> None:
    """专家邀请函读链桩(卡羁绊解析模块符号 + 羁绊面板读口 + area_center
    读桩回定值——坐标域随观察上报入 payload 后,恒稳断言不读真实建档)。"""
    from one_dragon.base.geometry.point import Point
    from sr_od.application.currency_war.kernel import cw_obs_core
    from sr_od.application.currency_war.obs import cw_observation
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_expert_invite as mod,
    )
    monkeypatch.setattr(mod, '_resolve_card_bonds',
                        lambda ctx, screen, a: '仙舟' if a == '卡-1' else None)
    monkeypatch.setattr(cw_observation, 'read_board',
                        lambda ctx, screen: {'仙舟': 3})
    _pts = {'卡-1': Point(300, 400), '卡-2': Point(700, 400),
            '卡-3': Point(1100, 400), '卡-4': Point(1500, 400),
            mod.CASH_AREA: Point(500, 900)}
    monkeypatch.setattr(cw_obs_core, 'area_center',
                        lambda ctx, name, screen: _pts.get(name))


# ==================== 观察上报接入调用测试(表驱动)====================

# 屏键 → (模块名, 类名, 装配钩子(op, monkeypatch), 期望容器字段, 期望终值)
_OBS_ROWS = {
    'partner':
        ('cw_screen_partner', 'CwScreenPartner',
         lambda op, mp: (mp.setattr(op, '_read_candidates',
                                    lambda s: [('护盾', 800, 360),
                                               ('能量', 1100, 360)]),
                         mp.setattr(op, '_identify_portraits',
                                    lambda s, c: ['charA', 'charB'])),
         'partner_opts', [PartnerOption(idx=0, char_id='charA'),
                          PartnerOption(idx=1, char_id='charB')]),
    'planner':
        ('cw_screen_yinlang', 'CwScreenYinLang',
         lambda op, mp: mp.setattr(op.ctx, 'ocr_service', _StubOcr(
             # 桩文本位置 = 建档两卡 rect 中心(观察过滤 = 中心点落入
             # area rect,坐标单一真相源回 yml;银狼升星记账批 §2.4)。
             map_result={'左卡文': _mrl(795, 317), '右卡文': _mrl(1305, 317)}),
             raising=False),
         'planner_opts', [PlannerOption(idx=0, text='左卡文'),
                          PlannerOption(idx=1, text='右卡文')]),
    'wish_trial':
        ('cw_screen_wish_trial', 'CwScreenWishTrial',
         lambda op, mp: mp.setattr(op.ctx, 'ocr_service', _StubOcr(
             list_result=[SimpleNamespace(data='objective甲', x=600, y=300,
                                          w=100, h=30)]), raising=False),
         'wish_trial_opts', ['objective甲', '', '']),
    'bookcard':
        ('cw_screen_bookcard', 'CwScreenBookcard',
         _setup_bookcard, 'star_tome_opts', ['列车同行']),
    'expert_invite':
        ('cw_screen_expert_invite', 'CwScreenExpertInvite',
         _setup_expert, 'expert_invite',
         ExpertInvitePayload(card_bonds=['仙舟', None, None, None],
                             board={'仙舟': 3},
                             card_points=[(300, 400), (700, 400),
                                          (1100, 400), (1500, 400)],
                             cash_point=(500, 900))),
}


@pytest.mark.parametrize('screen_key', [
    'partner', 'planner', 'wish_trial', 'expert_invite'])
def test_observe_reports_container_per_screen(test_context, monkeypatch,
                                              screen_key: str) -> None:
    """观察上报接入调用测试(表驱动四屏;命运卜者/星徽秘典双域测试拆独立 = 下两个测试):
    观察 node 读链桩化 → observe success → report 经屏文件落容器
    (容器终值逐位 = 现役写点转录值)+ obs 挂实例属性。红 = 接入调用断流 /
    容器终值漂移 / obs 未装载。"""
    import importlib

    mod_name, cls_name, setup, field, expected = _OBS_ROWS[screen_key]
    mod = importlib.import_module(f'{_CW_SCREEN_PKG}.{mod_name}')
    op = getattr(mod, cls_name)(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    if cls_name in ('CwScreenPartner', 'CwScreenWishTrial', 'CwScreenBookcard',
                    'CwScreenExpertInvite'):
        # 带门屏:门桩放行(门 miss 语义由下一测试承重)
        monkeypatch.setattr(op, 'round_by_find_area',
                            lambda s, sc, a, **k: _Area(True), raising=False)
    setup(op, monkeypatch)

    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        _make_match(session), raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'{screen_key}: 观察 success:{rs!r}'
    gs = game_state_of(session)
    assert getattr(gs, field).value == expected, (
        f'{screen_key}: report 落容器(容器终值):'
        f'{getattr(gs, field).value!r}')
    assert op._obs is not None, f'{screen_key}: obs 挂实例属性'


def test_fortune_observe_reports_dual_domain(test_context, monkeypatch) -> None:
    """命运卜者观察上报测试(双域,坐标随报条款):表驱动 5 元组不容双域
    拆独立测试——观察 node 读链桩化(OCR + area_center 读桩回定值,恒稳
    断言不读真实建档)→ observe success → report 双写 fortune_opts /
    fortune_opts_xy(同门同序等长)+ obs 挂实例属性。红 = 接入调用断流 /
    坐标域未随观察上报 / 双域终值漂移。"""
    from one_dragon.base.geometry.point import Point
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_fortune as mod,
    )

    op = mod.CwScreenFortune(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op.ctx, 'ocr_service', _StubOcr(
        map_result={'甲文': _mrl(510, 350), '乙文': _mrl(900, 350)}),
        raising=False)
    # area 读桩回定值(恒稳;不读真实建档,桩序 = 卡-强化1/2/3)。
    monkeypatch.setattr(
        mod, 'area_center',
        lambda ctx, name, screen_name: Point(
            {'卡-强化1': 511, '卡-强化2': 901, '卡-强化3': 1291}[name], 481))
    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        _make_match(session), raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'fortune: 观察 success:{rs!r}'
    gs = game_state_of(session)
    assert gs.fortune_opts.value == ['甲文', '乙文', ''], (
        f'fortune: report 落名字域:{gs.fortune_opts.value!r}')
    assert gs.fortune_opts_xy.value == [(511, 481), (901, 481), (1291, 481)], (
        f'fortune: report 落坐标域(同门双写):{gs.fortune_opts_xy.value!r}')
    assert op._obs is not None, 'fortune: obs 挂实例属性'


def test_wish_observe_reports_dual_domain(test_context, monkeypatch) -> None:
    """祈愿试炼观察上报测试(双域,选择坐标观察上报条款):观察 node 读链
    桩化(OCR 桩 + 门桩放行,恒稳断言不读真实建档)→ observe success →
    report 双写 wish_trial_opts / wish_trial_opts_xy(同门同序等长;坐标
    = CARD_XS 桶锚 + CARD_Y 观察期一次解出,值锚 660/340 槽常量)+
    obs 挂实例属性。红 = 接入调用断流 / 坐标域未随观察上报 / 双域终值漂移。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wish_trial as mod,
    )

    op = mod.CwScreenWishTrial(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(True), raising=False)
    monkeypatch.setattr(op.ctx, 'ocr_service', _StubOcr(
        list_result=[SimpleNamespace(data='objective甲', x=600, y=300,
                                     w=100, h=30)]), raising=False)
    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        _make_match(session), raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'wish: 观察 success:{rs!r}'
    gs = game_state_of(session)
    assert gs.wish_trial_opts.value == ['objective甲', '', ''], (
        f'wish: report 落名字域:{gs.wish_trial_opts.value!r}')
    assert gs.wish_trial_opts_xy.value == [
        (660, 340), (960, 340), (1260, 340)], (
        f'wish: report 落坐标域(同门双写):{gs.wish_trial_opts_xy.value!r}')
    assert len(gs.wish_trial_opts_xy.value) == len(gs.wish_trial_opts.value), (
        '坐标域与名字域同序等长')
    assert op._obs is not None, 'wish: obs 挂实例属性'
    assert op._obs.option_points == gs.wish_trial_opts_xy.value, (
        'obs 坐标与容器同源')


def test_bookcard_observe_reports_dual_domain(test_context, monkeypatch) -> None:
    """星徽秘典观察上报测试(双域,选择坐标观察上报条款):观察 node 读链
    桩化(OCR 桩 + 门桩放行 + area_center 读桩回定值,恒稳断言不读真实
    建档)→ 标准化门(「列车同行星徽」→ FACTIONS 精确命中)→ observe
    success → report 双写 star_tome_opts / star_tome_opts_xy(同门同序
    等长;坐标 = OCR x 中心 + x 近邻「星徽卡-N」建档中心 y,观察期一次
    解出)+ obs 挂实例属性。红 = 接入调用断流 / 坐标域未随观察上报 / 双域
    终值漂移 / 标准化门失守(裸 OCR 名直写容器)。"""
    from one_dragon.base.geometry.point import Point
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_bookcard as mod,
    )

    op = mod.CwScreenBookcard(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(True), raising=False)
    monkeypatch.setattr(op.ctx, 'ocr_service', _StubOcr(
        list_result=[SimpleNamespace(data='列车同行星徽', x=700, y=100,
                                     w=120, h=30)]), raising=False)
    # area 读桩回定值(恒稳;不读真实建档,桩序 = 星徽卡-1..4)。
    monkeypatch.setattr(
        mod, 'area_center',
        lambda ctx, name, screen_name: Point(
            {'星徽卡-1': 260, '星徽卡-2': 700, '星徽卡-3': 1140,
             '星徽卡-4': 1580}[name], 500))
    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        _make_match(session), raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'bookcard: 观察 success:{rs!r}'
    gs = game_state_of(session)
    assert gs.star_tome_opts.value == ['列车同行'], (
        f'bookcard: report 落名字域(标准化注册名):'
        f'{gs.star_tome_opts.value!r}')
    assert gs.star_tome_opts_xy.value == [(760, 500)], (
        f'bookcard: report 落坐标域(同门双写):'
        f'{gs.star_tome_opts_xy.value!r}')
    assert len(gs.star_tome_opts_xy.value) == len(gs.star_tome_opts.value), (
        '坐标域与名字域同序等长')
    assert op._obs is not None, 'bookcard: obs 挂实例属性'
    assert op._obs.option_points == gs.star_tome_opts_xy.value, (
        'obs 坐标与容器同源')


def test_bookcard_observe_gate_failures_zero_write(test_context,
                                                   monkeypatch) -> None:
    """星徽秘典观察失败三态测试(观察标准化门 + 解点失败归宿;名字与坐标
    同进退双域零写零上报):①任一候选转换失败(可转换+乱名混读,两段
    皆不中)/②多候选命中同一注册名(选项互斥屏同判)/③「星徽卡-N」
    建档缺失(area_center 返 None)→ 均 observe round_fail 早退、
    star_tome_opts / star_tome_opts_xy 双域零写、obs 不装载。红 = 带病
    上报 / 裸 OCR 名直写 / 半截状态(名字域写、坐标域不写)。"""
    from one_dragon.base.geometry.point import Point
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_bookcard as mod,
    )

    def _row(text: str, x: int) -> SimpleNamespace:
        return SimpleNamespace(data=text, x=x, y=100, w=120, h=30)

    def _run(ocr_rows: list) -> tuple:
        op = mod.CwScreenBookcard(test_context)
        monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
        monkeypatch.setattr(op, 'round_by_find_area',
                            lambda s, sc, a, **k: _Area(True), raising=False)
        monkeypatch.setattr(op.ctx, 'ocr_service', _StubOcr(
            list_result=ocr_rows), raising=False)
        monkeypatch.setattr(
            mod, 'area_center',
            lambda ctx, name, screen_name: Point(700, 500))
        session = StrategySession()
        monkeypatch.setattr(test_context, 'cw_match',
                            _make_match(session), raising=False)
        rs = _run_node(test_context, op, op.observe)
        gs = game_state_of(session)
        assert gs.star_tome_opts.value is None, '观察失败名字域零写'
        assert gs.star_tome_opts_xy.value is None, '观察失败坐标域零写(同进退)'
        assert op._obs is None, '观察失败不装载 obs'
        return rs

    # ① 任一候选转换失败 = 观察失败(仙舟可转换;乱名带「星徽」后缀过
    # 读链过滤、去后缀后两段皆不中)。
    rs = _run([_row('仙舟星徽', 700), _row('乱码七八星徽', 1500)])
    assert not rs.is_success and '标准化失败' in (rs.status or ''), (
        f'转换失败 = 观察失败 round_fail:{rs!r}')
    # ② 多候选命中同一注册名(选项互斥屏)= 同判转换失败。
    rs = _run([_row('仙舟星徽', 700), _row('仙舟星徽', 1500)])
    assert not rs.is_success and '标准化失败' in (rs.status or ''), (
        f'多候选同名同判转换失败:{rs!r}')
    # ③ 「星徽卡-N」建档缺失(解点返 None)= 观察失败。
    op = mod.CwScreenBookcard(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(True), raising=False)
    monkeypatch.setattr(op.ctx, 'ocr_service', _StubOcr(
        list_result=[_row('仙舟星徽', 700)]), raising=False)
    monkeypatch.setattr(mod, 'area_center',
                        lambda ctx, name, screen_name: None)
    session = StrategySession()
    monkeypatch.setattr(test_context, 'cw_match',
                        _make_match(session), raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and '建档' in (rs.status or ''), (
        f'建档缺失 = 观察失败 round_fail:{rs!r}')
    gs = game_state_of(session)
    assert gs.star_tome_opts.value is None, '建档缺失名字域零写'
    assert gs.star_tome_opts_xy.value is None, '建档缺失坐标域零写(同进退)'
    assert op._obs is None, '建档缺失不装载 obs'


def test_bookcard_lcs_ambiguity_rejection_and_unique_pass(test_context,
                                                          monkeypatch) -> None:
    """星徽秘典观察标准化门·次高分差拒判测试(op-layer.md §1.1;用户裁定
    2026-09-22 全族统一):LCS 阶段最高分未明显高于次高分 = 歧义 =
    转换失败,禁直接取最高分——「宙之半神」对昼之/夜之半神同分 3/4 =
    0.75,旧形态取注册表序首个 = 一半概率错配(点卡即选不可逆),现判
    round_fail 零写零上报;明确唯一(「昼之半祌」对昼之半神 3/4 = 0.75、
    对夜之半神 2/4 = 0.5,差 0.25)照常命中 = 拒判不过严回归锚。红 =
    歧义静默取最高分回潮 / 拒判误杀唯一命中。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_bookcard as mod,
    )

    def _row(text: str, x: int) -> SimpleNamespace:
        return SimpleNamespace(data=text, x=x, y=100, w=120, h=30)

    def _run(ocr_rows: list) -> tuple:
        op = mod.CwScreenBookcard(test_context)
        monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
        monkeypatch.setattr(op, 'round_by_find_area',
                            lambda s, sc, a, **k: _Area(True), raising=False)
        monkeypatch.setattr(op.ctx, 'ocr_service', _StubOcr(
            list_result=ocr_rows), raising=False)
        # 解点读桩(area_center 回定值;唯一命中分支要过解点才落容器)。
        monkeypatch.setattr(
            mod, 'area_center',
            lambda ctx, name, screen_name: Point(700, 500))
        session = StrategySession()
        monkeypatch.setattr(test_context, 'cw_match',
                            _make_match(session), raising=False)
        rs = _run_node(test_context, op, op.observe)
        return rs, session, op

    # ① 歧义对(同分)→ round_fail,双域零写、obs 不装载。
    from one_dragon.base.geometry.point import Point
    rs, session, op = _run([_row('宙之半神星徽', 700)])
    assert not rs.is_success and '标准化失败' in (rs.status or ''), (
        f'近分歧义 = 转换失败 round_fail:{rs!r}')
    gs = game_state_of(session)
    assert gs.star_tome_opts.value is None, '歧义名字域零写'
    assert gs.star_tome_opts_xy.value is None, '歧义坐标域零写(同进退)'
    assert op._obs is None, '歧义不装载 obs'
    # ② 明确唯一(分差足额)→ 通过,容器落标准注册名 + 坐标同门双写。
    rs2, session2, op2 = _run([_row('昼之半祌星徽', 700)])
    assert rs2.is_success, f'唯一命中放行(拒判不过严):{rs2!r}'
    gs2 = game_state_of(session2)
    assert gs2.star_tome_opts.value == ['昼之半神'], (
        f'唯一命中落标准注册名:{gs2.star_tome_opts.value!r}')
    assert gs2.star_tome_opts_xy.value == [(760, 500)], (
        f'坐标同门双写:{gs2.star_tome_opts_xy.value!r}')


# ==================== 入口门语义测试(带门四屏)====================

_GATE_ROWS = [
    # (屏键, 门 miss 现役文案)
    ('partner', '非选择伙伴屏'),
    ('wish_trial', '非祈愿试炼屏'),
    ('bookcard', '非星徽秘典画面'),
    ('expert_invite', '选卡入口:邀请函弹窗未现'),
]


@pytest.mark.parametrize('screen_key, expect_status', _GATE_ROWS)
def test_entry_gate_miss_fails_round(test_context, monkeypatch, screen_key,
                                     expect_status: str) -> None:
    """入口门语义测试:门 miss = round_fail 早退(文案沿用现役,交回外循环
    重判),且不进读链(obs 不装载)。红 = 门失效 / 文案漂移 / miss 后
    仍读屏装 obs。"""
    import importlib

    mod_name, cls_name = _OBS_ROWS[screen_key][0], _OBS_ROWS[screen_key][1]
    mod = importlib.import_module(f'{_CW_SCREEN_PKG}.{mod_name}')
    op = getattr(mod, cls_name)(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(False), raising=False)
    _read_calls: list[int] = []
    if screen_key == 'partner':
        monkeypatch.setattr(op, '_read_candidates',
                            lambda s: _read_calls.append(1) or [])
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    rs = _run_node(test_context, op, op.observe)
    assert not rs.is_success and expect_status in (rs.status or ''), (
        f'{screen_key}: 门 miss 文案沿用现役:{rs!r}')
    assert op._obs is None, f'{screen_key}: 门早退不装载 obs'
    if screen_key == 'partner':
        assert _read_calls == [], '门早退不进读链'


# ==================== chosen 写时机测试(祈愿试炼代表)====================

def test_wish_chosen_written_at_reentry_adjudication_only(
        test_context, monkeypatch) -> None:
    """chosen 写时机测试(动作事实边界:chosen_* 值在「确认已落地」重入
    观察后才可信,写端留守重入裁决点):
    - 确认已发 + 标识仍在(= 未落地)→ 不写,清标志重走(决策 + 点卡 +
      确认机械交回);
    - 确认已发 + 标识不在(= 选卡落地)→ 此刻才写 chosen_wish + success
      交回。
    红 = 落地前写(幻影 chosen)/ 落地后断流 / 未落地分支丢失。"""
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    from sr_od.application.currency_war.kernel.cw_screen_report.wish_trial import (
        CwScreenWishTrialObs,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickWishTrialParam,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wish_trial as mod,
    )

    session = StrategySession()
    pick_stub = CwActionPickWishTrialParam(idx=0, reason='stub')
    monkeypatch.setattr(
        test_context, 'cw_match',
        _make_match(session, decide_wish_trial=lambda: pick_stub),
        raising=False)
    op = mod.CwScreenWishTrial(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    op._obs = CwScreenWishTrialObs(on_screen=True,
                                   options=['累计刷新10次', ''],
                                   screen=_FRAME)   # obs 注入(观察 node 产物形态)
    # pick-op-unify:选卡+确认机械链迁入 CwActionPickWishTrialOp;本测试桩
    # 派发捕获(param/env)断言决策半产物,机械链行为测试 =
    # test_overlay_ops 祈愿 pick op 测试。
    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(act, env))
    # ① 未落地:标识仍在 → 不写 chosen,重走(决策 + 派发选卡确认链)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(True), raising=False)
    op._confirm_pending = (['累计刷新10次', ''], 0)
    rs = _run_node(test_context, op, op.act)
    assert game_state_of(session).chosen_wish.value is None, (
        '标识仍在(未落地)→ chosen 不写')
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'未落地重走:round_wait 机械交回:{rs!r}')
    assert len(dispatches) == 1, f'未落地重走:选卡确认链恰一次派发:{dispatches!r}'
    assert dispatches[0].param.idx == 0, '零参决策 idx=0'
    assert dispatches[0].param is pick_stub, (
        '派发 param = 策略产实例(直发零重建,reason 归因不丢)')
    assert (dispatches[0].env.target is None
            and dispatches[0].env.idx is None), (
        'env 仅携 op(定位点 = 观察上报坐标,动作 op 自容器 '
        'wish_trial_opts_xy 取,零 env 坐标喂)')
    assert op._confirm_pending == (['累计刷新10次', ''], 0), (
        '重走后待裁决快照重置(本轮选择)')
    # ② 落地:标识不在 → 此刻才写 chosen + success 交回
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(False), raising=False)
    rs2 = _run_node(test_context, op, op.act)
    assert rs2.is_success and '祈愿试炼选卡已确认' in (rs2.status or ''), (
        f'落地 → success 交回:{rs2!r}')
    assert game_state_of(session).chosen_wish.value == '累计刷新10次', (
        'chosen_wish = 重入裁决点留守写端(落地后值才可信)')


# ==================== 祈愿试炼决策出口测试(守卫①②③ + 直发)====================

def _setup_wish_act(test_context, monkeypatch, session, decide):
    """wish act 测试公共装配(fortune 测试同构):match 桩挂零参决策桩
    (decide=None = cw_match None 局外态)+ obs 注入 + 注册表派发捕获。"""
    from sr_od.application.currency_war.kernel.cw_screen_report.wish_trial import (
        CwScreenWishTrialObs,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_wish_trial as mod,
    )

    monkeypatch.setattr(
        test_context, 'cw_match',
        None if decide is None else _make_match(session, decide_wish_trial=decide),
        raising=False)
    op = mod.CwScreenWishTrial(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    op._obs = CwScreenWishTrialObs(on_screen=True,
                                   options=['甲objective', '乙objective', ''],
                                   option_points=[(660, 340), (960, 340),
                                                  (1260, 340)],
                                   screen=_FRAME)   # obs 注入(观察 node 产物形态)
    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(act, env))
    return op, dispatches


def test_wish_act_no_match_fails_via_normal_chain(test_context, monkeypatch):
    """守卫①(局外无早退支,用户裁决 2026-09-22 全族删门,op-layer.md
    §1.1):cw_match=None → act 不设局外早退门,沿正常链路因缺上下文自然
    失败(AttributeError)、零派发零点击、_confirm_pending 保持未置位。
    红 = 局外 round_success 早退门回潮 / 局外兜底决策路径回潮(盲发首卡)。"""
    session = StrategySession()
    op, dispatches = _setup_wish_act(test_context, monkeypatch, session, None)
    with pytest.raises(AttributeError, match='strategy'):
        _run_node(test_context, op, op.act)   # 无 match 正常链路失败
    assert dispatches == [], '守卫①:零派发'
    assert op._confirm_pending is None, '守卫①:确认未置位(零点击)'


def test_wish_act_guard_invalid_decision_fails_without_dispatch(
        test_context, monkeypatch):
    """守卫②(返回契约):decide_wish_trial 返 None/词表外(SimpleNamespace)
    两子态合一测试 → act 具名 round_fail(消息含「决策无有效输出」,留证
    原值)、零派发零点击、_confirm_pending 保持未置位。红 = 守卫缺失盲发
    / 钳位回潮 / 策略异常被吞。"""
    for stub in (None, SimpleNamespace(idx=0, reason='stub')):
        session = StrategySession()
        op, dispatches = _setup_wish_act(
            test_context, monkeypatch, session, lambda s=stub: s)
        rs = _run_node(test_context, op, op.act)
        assert not rs.is_success and '决策无有效输出' in (rs.status or ''), (
            f'守卫②({stub!r}):具名 round_fail 零盲发:{rs!r}')
        assert dispatches == [], f'守卫②({stub!r}):零派发'
        assert op._confirm_pending is None, (
            f'守卫②({stub!r}):确认未置位(零点击)')


def test_wish_act_guard_idx_out_of_range_asserts(
        test_context, monkeypatch):
    """守卫③(值域):真词表类 idx=3(槽常量现值 3,越界)→
    AssertionError 传播(守卫断言响亮暴露,禁钳位)、零派发零点击。
    红 = 钳位回潮。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickWishTrialParam,
    )

    session = StrategySession()
    op, dispatches = _setup_wish_act(
        test_context, monkeypatch, session,
        lambda: CwActionPickWishTrialParam(idx=3))
    with pytest.raises(AssertionError, match='越界'):
        _run_node(test_context, op, op.act)
    assert dispatches == [], '守卫③:零派发'
    assert op._confirm_pending is None, '守卫③:确认未置位(零点击)'


def test_wish_act_dispatches_strategy_param_env_op_only(
        test_context, monkeypatch):
    """正路形态:真词表类 idx=1 → 恰一次派发且派发 param 即策略产实例
    (直发零重建,reason 归因不丢)、env 仅携 op(零 target 零 idx——
    坐标随报条款,点击坐标 = 动作 op 自容器 wish_trial_opts_xy 读)、
    rs = round_wait、_confirm_pending 置位快照 = 本轮选择。红 = 派发
    实例重建 / env 坐标喂回潮。"""
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickWishTrialParam,
    )

    session = StrategySession()
    pick = CwActionPickWishTrialParam(idx=1, reason='stub')
    op, dispatches = _setup_wish_act(
        test_context, monkeypatch, session, lambda: pick)
    rs = _run_node(test_context, op, op.act)
    assert len(dispatches) == 1, f'恰一次派发:{dispatches!r}'
    assert dispatches[0].param is pick, '派发 param = 策略产实例(直发零重建)'
    assert dispatches[0].env.target is None and dispatches[0].env.idx is None, (
        'env 仅携 op(零 target 零 idx,停喂)')
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'round_wait 推进循环(确认未落地轮重走):{rs!r}')
    assert op._confirm_pending == (['甲objective', '乙objective', ''], 1), (
        '确认已发待重入裁决置位(快照 = 本轮选择)')


# ==================== 决策动作 node 测试(银狼策划代表)====================

def test_planner_act_decides_leg_and_dispatch_terminal(
        test_context, monkeypatch) -> None:
    """决策动作 node 测试(银狼策划,即时上报
    equip-immediate-report design §2.1):零参决策 → 分支类型判定单源
    ``classify_planner_branch`` → env 携分支类型载荷 → 选卡确认链派发即
    ``round_success`` 终结(零重入裁决轮、零证据一次性标志位存证——效果分支在动作 op
    确认点击后即时上报)。
    红 = 分支类型载荷断流 / 派发后回退 wait(重入裁决回潮)/ 存证一次性标志位回潮。"""
    from sr_od.application.currency_war.kernel.cw_screen_report.planner import (
        CwScreenPlannerObs,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_yinlang as ymod,
    )

    session = StrategySession()
    _decide_calls: list[int] = []
    match = _make_match(
        session,
        decide_planner=lambda: (_decide_calls.append(1)
                                or SimpleNamespace(idx=1, reason='stub')))
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = ymod.CwScreenYinLang(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    # 决策半分支类型判定输入 = 选中的右卡卡文(破解芯片 = 装备域锚命中)。
    op._obs = CwScreenPlannerObs(
        on_screen=True,
        options=[PlannerOption(idx=0, text='随便什么左卡'),
                 PlannerOption(idx=1, text='破解芯片 前台强度 30%')],
        screen=_FRAME)
    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(act, env))
    rs = _run_node(test_context, op, op.act)
    assert _decide_calls == [1], f'零参决策恰一次:{_decide_calls!r}'
    assert len(dispatches) == 1 and dispatches[0].param.idx == 1, (
        f'选卡确认链恰一次派发,param 携真实 idx:{dispatches!r}')
    assert dispatches[0].env.branch_type == 'equip', (
        'env 携分支类型载荷(classify_planner_branch 单源)')
    assert dispatches[0].env.norm_item == '破解芯片', '归一件名随 env 透传'
    assert dispatches[0].env.target is not None, '点卡定位点经 env 传入'
    assert rs.is_success, f'派发即 round_success 终结(零重入裁决轮):{rs!r}'


# ==================== 命运卜者决策出口测试(守卫⓪①② + 直发)====================

def _setup_fortune_act(test_context, monkeypatch, session, decide):
    """fortune act 测试公共装配(祈愿测试先例同构):match 桩挂零参决策桩
    (decide=None = cw_match None 局外态)+ obs 注入 + 注册表派发捕获。"""
    from sr_od.application.currency_war.kernel.cw_screen_report.fortune import (
        CwScreenFortuneObs,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_fortune as mod,
    )

    monkeypatch.setattr(
        test_context, 'cw_match',
        None if decide is None else _make_match(session, decide_fortune=decide),
        raising=False)
    op = mod.CwScreenFortune(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    op._obs = CwScreenFortuneObs(on_screen=True,
                                 options=['甲文', '乙文', '丙文'],
                                 option_points=[(511, 481), (901, 481),
                                                (1291, 481)],
                                 screen=_FRAME)   # obs 注入(观察 node 产物形态)
    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(act, env))
    return op, dispatches


def test_fortune_act_guard_invalid_decision_fails_without_dispatch(
        test_context, monkeypatch) -> None:
    """补充测试①(返回契约):decide_fortune 返 None/词表外(SimpleNamespace)
    两子态合一测试 → act 具名 round_fail(消息含「决策无有效输出」,留证
    原值)、零派发零点击、_confirm_pending 保持未置位。红 = 守卫缺失盲发
    / 钳位回潮 / 策略异常被吞。"""
    for stub in (None, SimpleNamespace(idx=0, reason='stub')):
        session = StrategySession()
        op, dispatches = _setup_fortune_act(
            test_context, monkeypatch, session, lambda s=stub: s)
        rs = _run_node(test_context, op, op.act)
        assert not rs.is_success and '决策无有效输出' in (rs.status or ''), (
            f'守卫①({stub!r}):具名 round_fail 零盲发:{rs!r}')
        assert dispatches == [], f'守卫①({stub!r}):零派发'
        assert op._confirm_pending is False, (
            f'守卫①({stub!r}):确认未置位(零点击)')


def test_fortune_act_guard_idx_out_of_range_asserts(
        test_context, monkeypatch) -> None:
    """补充测试②(值域):真词表类 idx=3(槽数 = 3 越界)→ AssertionError
    传播(守卫断言响亮暴露,禁钳位)、零派发零点击。红 = 钳位回潮。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickFortuneParam,
    )

    session = StrategySession()
    op, dispatches = _setup_fortune_act(
        test_context, monkeypatch, session,
        lambda: CwActionPickFortuneParam(idx=3))
    with pytest.raises(AssertionError, match='越界'):
        _run_node(test_context, op, op.act)
    assert dispatches == [], '守卫②:零派发'
    assert op._confirm_pending is False, '守卫②:确认未置位(零点击)'


def test_fortune_act_dispatches_strategy_param_env_op_only(
        test_context, monkeypatch) -> None:
    """补充测试③(正路形态):真词表类 idx=1 → 恰一次派发且派发 param 即
    策略产实例(直发零重建,reason 归因不丢)、env 仅携 op(零 target
    零 idx——坐标随报条款,点击坐标 = 动作 op 自容器读)、rs = round_wait、
    _confirm_pending 置位。红 = 派发实例重建 / env 坐标喂回潮。"""
    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickFortuneParam,
    )

    session = StrategySession()
    pick = CwActionPickFortuneParam(idx=1, reason='stub')
    op, dispatches = _setup_fortune_act(
        test_context, monkeypatch, session, lambda: pick)
    rs = _run_node(test_context, op, op.act)
    assert len(dispatches) == 1, f'恰一次派发:{dispatches!r}'
    assert dispatches[0].param is pick, '派发 param = 策略产实例(直发零重建)'
    assert dispatches[0].env.target is None and dispatches[0].env.idx is None, (
        'env 仅携 op(零 target 零 idx,停喂)')
    assert rs.result == OperationRoundResultEnum.WAIT, (
        f'round_wait 推进循环(确认未落地轮重走):{rs!r}')
    assert op._confirm_pending is True, '确认已发待重入裁决置位'


def test_fortune_act_no_match_fails_via_normal_chain(
        test_context, monkeypatch) -> None:
    """补充测试④(局外无早退支,用户裁决 2026-09-22 全族删门,op-layer.md
    §1.1):cw_match=None → act 不设局外早退门,沿正常链路因缺上下文自然
    失败(AttributeError)、零派发零点击、_confirm_pending 保持未置位。
    红 = 局外 round_success 早退门回潮 / 局外兜底决策路径回潮。"""
    session = StrategySession()
    op, dispatches = _setup_fortune_act(test_context, monkeypatch, session,
                                        None)
    with pytest.raises(AttributeError, match='strategy'):
        _run_node(test_context, op, op.act)   # 无 match 正常链路失败
    assert dispatches == [], '守卫⓪:零派发'
    assert op._confirm_pending is False, '守卫⓪:确认未置位(零点击)'


# ==================== 星徽秘典决策出口测试(守卫①a/①b/②③ + 直发)====================

def _setup_bookcard_act(test_context, monkeypatch, session, decide):
    """bookcard act 测试公共装配(fortune 测试同构):match 桩挂零参决策桩
    (decide=None = cw_match None 局外态)+ 观察产物注入 + 注册表派发
    捕获。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_bookcard as mod,
    )

    monkeypatch.setattr(
        test_context, 'cw_match',
        None if decide is None else _make_match(session, decide_star_tome=decide),
        raising=False)
    op = mod.CwScreenBookcard(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    # 观察产物注入(标准化注册名 + x 中心;act 消费面 = self._cards)。
    op._cards = [('列车同行', 700), ('仙舟', 1100)]
    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(act, env))
    return op, dispatches


def test_bookcard_act_no_match_fails_via_normal_chain(
        test_context, monkeypatch) -> None:
    """守卫①a(局外无早退支,用户裁决 2026-09-22 全族删门,op-layer.md
    §1.1):cw_match=None → act 不设局外早退门,沿正常链路因缺上下文自然
    失败(AttributeError)、零派发零点击、_pick_pending 保持未置位。
    红 = 局外 round_success 早退门回潮 / 局外兜底决策路径回潮(盲发首卡)。"""
    session = StrategySession()
    op, dispatches = _setup_bookcard_act(test_context, monkeypatch, session,
                                         None)
    with pytest.raises(AttributeError, match='strategy'):
        _run_node(test_context, op, op.act)   # 无 match 正常链路失败
    assert dispatches == [], '守卫①a:零派发'
    assert op._pick_pending is None, '守卫①a:pending 未置位(零点击)'


def test_bookcard_act_empty_candidates_fails_without_dispatch(
        test_context, monkeypatch) -> None:
    """守卫①b(候选空臂,op-layer.md §1.1 出口③):match 在场、观察产物
    候选空(OCR 失读形态)→ act 具名 round_fail(消息含候选数)、零派发
    零点击、_pick_pending 保持未置位。红 = 空候选盲发 idx0 回潮。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickStarTomeParam,
    )

    session = StrategySession()
    op, dispatches = _setup_bookcard_act(
        test_context, monkeypatch, session,
        lambda: CwActionPickStarTomeParam(idx=0))
    op._cards = []
    rs = _run_node(test_context, op, op.act)
    assert not rs.is_success and '决策无有效输出零盲发' in (rs.status or ''), (
        f'守卫①b:候选空具名 fail 零盲发:{rs!r}')
    assert dispatches == [], '守卫①b:零派发'
    assert op._pick_pending is None, '守卫①b:pending 未置位(零点击)'


def test_bookcard_act_guard_invalid_decision_fails_without_dispatch(
        test_context, monkeypatch) -> None:
    """守卫②(返回契约):decide_star_tome 返 None/词表外(SimpleNamespace)
    两子态合一测试 → act 具名 round_fail(消息含「决策无有效输出」,留证
    原值)、零派发零点击、_pick_pending 保持未置位。红 = 守卫缺失盲发 /
    钳位回潮 / 策略异常被吞。"""
    for stub in (None, SimpleNamespace(idx=0, reason='stub')):
        session = StrategySession()
        op, dispatches = _setup_bookcard_act(
            test_context, monkeypatch, session, lambda s=stub: s)
        rs = _run_node(test_context, op, op.act)
        assert not rs.is_success and '决策无有效输出' in (rs.status or ''), (
            f'守卫②({stub!r}):具名 round_fail 零盲发:{rs!r}')
        assert dispatches == [], f'守卫②({stub!r}):零派发'
        assert op._pick_pending is None, (
            f'守卫②({stub!r}):pending 未置位(零点击)')


def test_bookcard_act_guard_idx_out_of_range_asserts(
        test_context, monkeypatch) -> None:
    """守卫③(值域):真词表类 idx=5(候选 2 元越界)→ AssertionError
    传播(守卫断言响亮暴露,禁钳位)、零派发零点击。红 = 钳位回潮。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickStarTomeParam,
    )

    session = StrategySession()
    op, dispatches = _setup_bookcard_act(
        test_context, monkeypatch, session,
        lambda: CwActionPickStarTomeParam(idx=5))
    with pytest.raises(AssertionError, match='越界'):
        _run_node(test_context, op, op.act)
    assert dispatches == [], '守卫③:零派发'
    assert op._pick_pending is None, '守卫③:pending 未置位(零点击)'


# ==================== 选择伙伴决策出口测试(守卫①两臂 + ②③)====================

def _setup_partner_act(test_context, monkeypatch, session, decide,
                       cands: list | None = None):
    """partner act 测试公共装配(fortune/bookcard 测试同构):match 桩挂零参
    决策桩(decide=None = cw_match None 局外态)+ 读链桩两元/门桩放行
    (装配同 ``_OBS_ROWS['partner']``,观察 node 先行产出 obs/cands)+
    注册表派发捕获;``cands=[]`` = 候选空臂(读链桩改返空)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_partner as mod,
    )

    monkeypatch.setattr(
        test_context, 'cw_match',
        None if decide is None else _make_match(session, decide_partner=decide),
        raising=False)
    op = mod.CwScreenPartner(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    # 门桩放行(入口门/未选中提示两读全部命中;门 miss 语义由既有测试承重)。
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda s, sc, a, **k: _Area(True), raising=False)
    monkeypatch.setattr(
        op, '_read_candidates',
        lambda s: [('护盾', 800, 360), ('能量', 1100, 360)]
        if cands is None else cands, raising=False)
    monkeypatch.setattr(op, '_identify_portraits',
                        lambda s, c: ['charA', 'charB'], raising=False)
    dispatches: list = []

    class _StubPickOp:
        def __init__(self, param, env) -> None:
            self.param = param
            self.env = env

        def execute(self) -> bool:
            dispatches.append(self)
            return True

    import sr_od.application.currency_war.operations.cw_op.cw_action_registry as _reg
    monkeypatch.setattr(_reg, 'action_op_for',
                        lambda act, ctx, env: _StubPickOp(act, env))
    rs = _run_node(test_context, op, op.observe)
    assert rs.is_success, f'partner: 观察 success(测试前置):{rs!r}'
    return op, dispatches


def test_partner_act_empty_candidates_fails_without_dispatch(
        test_context, monkeypatch) -> None:
    """守卫①候选空臂(op-layer.md §1.1 出口③,两臂分开断言):match 在场、
    读链桩改返空(options 空 ⇔ cands 空)→ act 具名 round_fail(「伙伴屏
    无候选」已登记文案)、零派发零点击、_confirm_pending 保持未置位。
    红 = 空候选盲发回潮 / 已登记文案漂移。"""
    session = StrategySession()
    op, dispatches = _setup_partner_act(
        test_context, monkeypatch, session,
        lambda: SimpleNamespace(idx=0, reason='stub'), cands=[])
    rs = _run_node(test_context, op, op.act)
    assert not rs.is_success and '伙伴屏无候选' in (rs.status or ''), (
        f'守卫①候选空臂:具名 round_fail 零盲发:{rs!r}')
    assert dispatches == [], '守卫①候选空臂:零派发'
    assert op._confirm_pending is False, '守卫①候选空臂:确认未置位(零点击)'


def test_partner_act_no_match_fails_via_normal_chain(test_context,
                                                     monkeypatch):
    """守卫①match 缺席臂(局外无早退支,用户裁决 2026-09-22 全族删门,
    op-layer.md §1.1,两臂分开断言):cw_match=None + 读链桩两元(候选
    在场)→ act 不设局外早退门,沿正常链路因缺上下文自然失败
    (AttributeError)、零派发零点击、_confirm_pending 保持未置位。
    红 = 局外 round_success 早退门回潮 / 局外兜底决策路径回潮(盲发首卡)。"""
    session = StrategySession()
    op, dispatches = _setup_partner_act(test_context, monkeypatch, session,
                                        None)
    with pytest.raises(AttributeError, match='strategy'):
        _run_node(test_context, op, op.act)   # 无 match 正常链路失败
    assert dispatches == [], '守卫①match 缺席臂:零派发'
    assert op._confirm_pending is False, (
        '守卫①match 缺席臂:确认未置位(零点击)')


def test_partner_act_guard_invalid_decision_fails_without_dispatch(
        test_context, monkeypatch) -> None:
    """守卫②(返回契约):decide_partner 返 None/词表外(SimpleNamespace)
    两子态合一测试 → act 具名 round_fail(消息含「词表外」,留证原值)、
    零派发零点击、_confirm_pending 保持未置位。红 = 守卫缺失盲发 /
    策略异常被吞。"""
    for stub in (None, SimpleNamespace(idx=0, reason='stub')):
        session = StrategySession()
        op, dispatches = _setup_partner_act(
            test_context, monkeypatch, session, lambda s=stub: s)
        rs = _run_node(test_context, op, op.act)
        assert not rs.is_success and '词表外' in (rs.status or ''), (
            f'守卫②({stub!r}):具名 round_fail 零盲发:{rs!r}')
        assert dispatches == [], f'守卫②({stub!r}):零派发'
        assert op._confirm_pending is False, (
            f'守卫②({stub!r}):确认未置位(零点击)')


def test_partner_act_guard_idx_out_of_range_asserts(
        test_context, monkeypatch) -> None:
    """守卫③(值域):真词表类 idx=5(候选 2 元越界)→ AssertionError
    传播(守卫断言响亮暴露,禁钳位)、零派发零点击。红 = 钳位回潮。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickPartnerParam,
    )

    session = StrategySession()
    op, dispatches = _setup_partner_act(
        test_context, monkeypatch, session,
        lambda: CwActionPickPartnerParam(idx=5, reason='stub'))
    with pytest.raises(AssertionError, match='越界'):
        _run_node(test_context, op, op.act)
    assert dispatches == [], '守卫③:零派发'
    assert op._confirm_pending is False, '守卫③:确认未置位(零点击)'
