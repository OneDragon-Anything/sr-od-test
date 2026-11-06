"""策略卡合并升星触发发放腿测试(镜像 src = kernel/cw_gain_chain.py 的
check_strategy_merge_grants;分方法拆目录规范落位,文件镜像超限纪律 =
新函数落拆目录新文件,先例 = 同目录 test_check_strategy_star_merge_gold.py
与 kernel/cw_env_grants/test_check_env_merge_grants.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-179-shali-
taojin.md(定稿)§4 锁 1/3/4 + REVIEW-T179 §3.4(卡面官方原文:「合成
2星2费角色时，获得1张【砂金】。」)+ designs/T-409-heita-jiyuan.md §5.1
用户终裁(2026-11-06 具名判据行,卡面原文:「你获得3星【黑塔】时获得
【大黑塔】」):

- 主锁(锁 1):持卡局 gain_character 1★×3 同名 2 费 → 链内合成 2★ →
  bench 含 1 个 1★砂金,evidence 笔 = strategy_merge_grant:砂里淘金
  (链顶层发火,采集在级联);非持卡局同操作零发放(合成照常);
- 判据负例(锁 3):星级不符(直构 3★ 级 facts——物理级联下路径上的
  2★2费事件按判据会发,负例断言对象 = 3★ 级 facts 自身零发放)/
  费用不符(2★3费)→ 零效果串零写;
- 逐级触发(锁 4):一次调用链级联 1→2→3(2 费)→ facts 两级、发放恰
  一次(仅 to_star==2 级,级联终档 3★ 不发——用户裁定「每完成一级
  3 合 1 各发一次」先例的判据粒度);
- live 门控负锁:未装配 sim(纯实机态)→ 持卡 + 命中 facts 零写
  (策略卡发牌族权威版本:不建逻辑写、观察收尾,防门控失效退化成猜测写);
- 具名判据行(T-409):持黑塔纪元 + 3★黑塔 facts(星级/费用/角色名
  三匹配)→ 发 1★大黑塔;同星同费不同名(三月七 1 费 3★ facts)→
  零发放(名字维单变量负例,通配行此形会发);级联 1→2→3(黑塔)
  facts 两级发放恰一次(仅 3★ 级命中具名判据)。通配行行为回归 =
  本文件既有砂里淘金各锁(空串判据角色名,费用/星级双匹配即发)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_merge_grants,
    gain_character,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_SIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_SIG_OBS = ChannelSig(family='obs', actor='test-seed')

_EV = 'strategy_merge_grant:砂里淘金'

_EV_PLACE = _EV + '#place'  # #place 后缀 = 获得链落位写 evidence 约定

_CARD = '砂里淘金'

_EV_HT = 'strategy_merge_grant:黑塔纪元'

_EV_HT_PLACE = _EV_HT + '#place'

_CARD_HT = '黑塔纪元'

_CHAR2 = '花火'   # 2 费(cw_chars 判据费用域内素材)
_CHAR3 = '姬子'   # 3 费(费用负例素材)


class _SimPresenceStub:
    """装配占位后端(仅令 ``sim_backend_installed()`` 为真;本腿不触后端
    任何口,触即 AssertionError 响亮——被测门控只读装配槽非 None;
    test_check_strategy_star_merge_gold 同名先例)。"""

    def screen_identity(self) -> str:
        raise AssertionError('策略卡合成发放腿不触后端读口')

    def observe(self, screen_name: str) -> object:
        raise AssertionError('策略卡合成发放腿不触后端观察')

    def visible(self, screen_name: str, area_name: str) -> bool:
        raise AssertionError('策略卡合成发放腿不触后端门问询')

    def click_answer(self, op: object, screen_name: str, area_name: str,
                     until_find_all: object, until_not_find_all: object):
        raise AssertionError('策略卡合成发放腿不触后端点击')

    def advance(self, decl: object) -> None:
        raise AssertionError('策略卡合成发放腿不触后端推进')


@pytest.fixture
def sim_installed():
    """sim 形态:装配占位后端;teardown 必卸(模块槽进程全局)。"""
    cw_sim_ports.install_sim_backend(_SimPresenceStub())
    yield
    cw_sim_ports.uninstall_sim_backend()


def _gs(*, card: str | None = _CARD) -> GameState:
    """直构状态容器(card=None = 未持卡;表外卡同参;bench 种空席——直构域
    bench 未观察 = 链拒落零写,本腿落席面断言需可写席)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card', sig=_SIG)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    return gs


def _bench_units(gs) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_gain_chain_three_one_star_merge_grants_sha_jin(
        sim_installed) -> None:
    """获得链集成主锁(锁 1):持卡局 gain_character 1★×3 同名 2 费 →
    链内合成 2★ → bench 含 1 个 1★砂金,evidence 笔 = 本腿写点
    (链顶层发火,发放 1★ 先验 rand=False 确定写)。"""
    gs = cw4_gs(node_fill=False, shop_screen='off',
                bench=[_bc(_CHAR2, 1), _bc(_CHAR2, 1)])
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)
    out = gain_character(gs, _CHAR2, 1, rand=False, sig=_SIG,
                         evidence='t:chain', producer='TestChain')
    assert out.merge_levels == 1, f'链内合成 1 级(1★×3 → 2★): {out}'
    units = _bench_units(gs)
    assert ('花火', 2) in units, f'合成产物 2★ 在席(链主分支照常): {units}'
    assert units.count(('砂金', 1)) == 1, \
        f'发放恰 1 个 1★砂金(1★ 先验): {units}'
    assert gs.bench.evidence == _EV_PLACE, \
        f'bench 尾笔 evidence = 发放写点(链 #place 后缀): {gs.bench.evidence!r}'


def test_gain_chain_no_card_zero_grant(sim_installed) -> None:
    """非持卡局零发放(锁 1 负面):同操作合成照常发生,本腿零动作——
    表外卡同路(白名单表外禁自动猜装)。"""
    for card in (None, '躺平'):
        gs = cw4_gs(node_fill=False, shop_screen='off',
                    bench=[_bc(_CHAR2, 1), _bc(_CHAR2, 1)])
        if card is not None:
            gs.write_logic(gs.active_strategies, [card],
                           produced_by='test-seed', evidence='t:card',
                           sig=_SIG)
        out = gain_character(gs, _CHAR2, 1, rand=False, sig=_SIG,
                             evidence='t:chain', producer='TestChain')
        assert out.merge_levels == 1, f'{card}: 合成照常发生: {out}'
        assert ('砂金', 1) not in _bench_units(gs), \
            f'{card}: 零发放(合成产物落席不受影响)'


def test_star_mismatch_zero_grant(sim_installed) -> None:
    """判据星级负例(锁 3):直构 3★ 级 facts(费用匹配)→ 零效果串
    零写——判据 = 产物星级双匹配,3★ 级(级联终档)不触发;断言对象 =
    3★ 级 facts 自身零发放(R2-O1:物理级联下路径上的 2★2费事件按判据
    会发,勿把负例扩成整局零发放)。"""
    gs = _gs()
    effects = check_strategy_merge_grants(gs, ((_CHAR2, 3),), sig=_SIG)
    assert effects == (), f'3★ 级 facts 零发放: {effects}'


def test_cost_mismatch_zero_grant(sim_installed) -> None:
    """判据费用负例(锁 3):2★3费 facts → 零效果串零写(费用双匹配
    判据;注册表外名 None 判空跳过同路零发)。"""
    gs = _gs()
    effects = check_strategy_merge_grants(gs, ((_CHAR3, 2),), sig=_SIG)
    assert effects == (), f'2★3费零发放: {effects}'
    unknown = check_strategy_merge_grants(gs, (('注册表外名', 2),), sig=_SIG)
    assert unknown == (), f'注册表外名判空跳过零发放: {unknown}'


def test_live_form_zero_write() -> None:
    """live 门控负锁(锁 1):未装配 sim(纯实机态)→ 持卡 + 命中 facts
    零效果串——防门控失效退化成猜测写(策略卡发牌族权威版本:不建逻辑写、
    观察收尾)。"""
    cw_sim_ports.uninstall_sim_backend()
    gs = _gs()
    effects = check_strategy_merge_grants(gs, ((_CHAR2, 2),), sig=_SIG)
    assert effects == (), f'live 门控零发放: {effects}'


def test_direct_hit_pinned_evidence_and_star(sim_installed) -> None:
    """函数直构主锁:持卡 + 单条 2★2费 facts → 恰一条效果串(卡名
    证据串),bench 落 1 个 1★砂金;同窗两条命中逐条发(逐级触发先例)。"""
    gs = _gs()
    effects = check_strategy_merge_grants(gs, ((_CHAR2, 2),), sig=_SIG)
    assert effects == (_EV,), f'效果串钉死: {effects}'
    assert _bench_units(gs).count(('砂金', 1)) == 1, '落 1 个 1★砂金'

    gs2 = _gs()
    effects2 = check_strategy_merge_grants(gs2, ((_CHAR2, 2), (_CHAR2, 2)),
                                           sig=_SIG)
    assert effects2 == (_EV, _EV), \
        f'同窗两条命中逐条发: {effects2}'
    assert _bench_units(gs2).count(('砂金', 1)) == 2, '两次发放各落 1★'


def test_cascade_two_levels_fires_once_on_star2(sim_installed) -> None:
    """逐级触发锁(锁 4):一次 gain_character 调用链级联 1→2→3(2 费,
    素材 1★×4 + 2★×2)→ facts 两级、发放恰一次(仅 to_star==2 级;
    级联终档 3★ 不发)。"""
    gs = cw4_gs(node_fill=False, shop_screen='off',
                bench=[_bc(_CHAR2, 1), _bc(_CHAR2, 1),
                       _bc(_CHAR2, 2), _bc(_CHAR2, 2)])
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)
    out = gain_character(gs, _CHAR2, 1, rand=False, sig=_SIG,
                         evidence='t:casc', producer='TestChain')
    assert out.merge_levels == 2, f'级联两级(1→2→3): {out}'
    units = _bench_units(gs)
    assert ('花火', 3) in units, f'级联产物 3★ 在席: {units}'
    assert units.count(('砂金', 1)) == 1, \
        f'发放恰 1 个(仅 to_star==2 级,终档 3★ 零发放): {units}'
    assert gs.bench.evidence == _EV_PLACE, \
        f'bench 尾笔 evidence = 发放写点: {gs.bench.evidence!r}'


def test_empty_facts_zero_grant(sim_installed) -> None:
    """facts 空(链零升星形态)→ 零动作(持卡不变零写)。"""
    gs = _gs()
    assert check_strategy_merge_grants(gs, (), sig=_SIG) == ()


def test_named_row_direct_hit_grants_daheita(sim_installed) -> None:
    """具名行行为锁(T-409 终裁 A 案):持黑塔纪元 + 单条 3★黑塔 facts
    (星级 3 + 费用 1 + 具名黑塔三匹配)→ 恰一条效果串,bench 落 1 个
    1★大黑塔(发放 1★ 先验 rand=False 确定写)。"""
    gs = _gs(card=_CARD_HT)
    effects = check_strategy_merge_grants(gs, (('黑塔', 3),), sig=_SIG)
    assert effects == (_EV_HT,), f'具名行效果串钉死: {effects}'
    assert _bench_units(gs).count(('大黑塔', 1)) == 1, '落 1 个 1★大黑塔'


def test_named_row_role_mismatch_zero_grant(sim_installed) -> None:
    """具名判据角色名负例(名字维单变量):同星同费不同名(三月七 1 费
    3★ facts)→ 零效果串零写——事件角色名 ≠ 判据角色名黑塔;同形 facts
    在通配行(砂里淘金族费用域内)会发,具名行拦住 = 名字维判定生效。"""
    gs = _gs(card=_CARD_HT)
    effects = check_strategy_merge_grants(gs, (('三月七', 3),), sig=_SIG)
    assert effects == (), f'具名判据角色名不匹配零发放: {effects}'
    assert not _bench_units(gs), '零写'


def test_named_row_gain_chain_cascade_grants_once(sim_installed) -> None:
    """获得链集成(具名行,逐级判据粒度):持黑塔纪元,席面 2★×2 +
    1★×3 → gain 1 只 1★ → 链内级联 1→2→3 → facts 两级、发放恰一次
    (仅 3★ 级命中具名判据;2★ 级星级不符黑塔纪元、费用不符砂里淘金
    〔未持〕)。"""
    gs = cw4_gs(node_fill=False, shop_screen='off',
                bench=[_bc('黑塔', 2), _bc('黑塔', 2),
                       _bc('黑塔', 1), _bc('黑塔', 1), _bc('黑塔', 1)])
    gs.write_logic(gs.active_strategies, [_CARD_HT],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)
    out = gain_character(gs, '黑塔', 1, rand=False, sig=_SIG,
                         evidence='t:chain', producer='TestChain')
    assert out.merge_levels == 2, \
        f'链内级联两级(3×1★→2★,再 3×2★→3★): {out}'
    units = _bench_units(gs)
    assert ('黑塔', 3) in units, f'级联产物 3★黑塔 在席: {units}'
    assert units.count(('大黑塔', 1)) == 1, \
        f'具名行发放恰 1 个 1★大黑塔(仅 3★ 级命中): {units}'
    assert gs.bench.evidence == _EV_HT_PLACE, \
        f'bench 尾笔 evidence = 发放写点: {gs.bench.evidence!r}'
