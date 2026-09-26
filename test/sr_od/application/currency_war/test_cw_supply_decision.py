"""补给选卡决策单帧锁(三级字典序 + 闸内嵌刷新;判据 = 迭代
changes/2026-09-24-supply-screen-strategy-migration landing.md §3.1
验收凭据①-⑨,判据语义 = 同目录 design.md §2.2-§2.5;3.3 起判据正本
= strategy-docs/30_supply_screen.md)。

锁语义不锁牌面:断言的是「这段判据应该怎么表现」(三级序、需求计数、
凑星布尔 tiebreak、闸 fail-closed);reason 仅断言 design 明文指定的
字面(⑨ no-options),其余不断言。判据映射:
- ① 带钻必选(单钻直选;多钻按角色/装备细分);
- ② 锁线帧终局成员卡压高价值装备卡;
- ③ 未锁线/降格帧/get_comp 解析失败帧角色级空转、装备级无 key 参照
  (解析失败帧 = flow 层 None 传入,行为锁见 flow 接线锁);
- ④ 已持够数成品不再高分、组件/近兑现升档(两账口径:备用账与上阵/
  备战席穿戴账两半边各有帧);
- ⑤ 三级全空才刷 + left 缺/尽不刷不阻塞落选卡(闸内嵌 fail-closed)
  + 带钻帧永不建议刷(「无带钻」合取支);
- ⑥ 席满无特殊分支(溢出席语义 = 正常选卡);
- ⑦ 凑星 tiebreak:同名 1★ 恰 2 张先于不凑星终局成员,含 2 张分跨
  备战席/上阵行域的构造(钉死 deployed 展平,防只数备战席漏域);
- ⑧ P1 配方锁帧(locked_comp 恒 None):无钻帧建议刷 + left 尽按
  通用值定序落选卡;
- ⑨ 空候选帧返 idx=0 no-options。

测试纪律:零真实副作用(纯函数 + 自造输入 + 提交进仓的注册表数据);
装备配方/价值取自注册表真实数据(火力风暴潮 = 折叠小刀+轮滑鞋,
cw_equipment_data)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_events import SupplyOption
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import supply
from sr_od.application.currency_war.strategies.impl.mandate_v1.supply import (
    SupplyDecision,
    SupplyRefreshSuggestion,
)

_SIG = ChannelSig(family='logic_action', actor='cw-supply-decision-test',
                  mode='compute')
_PB = 'cw-supply-decision-test'


# ==================== 构造器 ====================

def _fresh_gs() -> GameState:
    """独立容器(桩 session 宿主;弱引用表按宿主隔离,零跨测残留)。"""
    return game_state_of(SimpleNamespace())


def _opt(idx: int, char: str = '', equip: str = '',
         has_diamond: bool = False) -> SupplyOption:
    return SupplyOption(idx=idx, char=char, equip=equip,
                        has_diamond=has_diamond)


def _comp(core: list[str], key: list[str] | None = None) -> Comp:
    """测试 comp(仅决策消费的字段有意;其余注册表字段与本判据无关)。"""
    return Comp(name='测试套', factions=['追击'], core_chars=core,
                form_tiers={'追击': 3}, strength='S', form_difficulty='easy',
                key_equips=key or [])


def _set_left(gs: GameState, left: int) -> None:
    """写刷新剩余次数(容器观察真值形态;None = 不写保持未观察)。"""
    gs.write_logic(gs.supply_refresh_left, left, produced_by=_PB, sig=_SIG)


def _set_equips(gs: GameState, equips: list[str]) -> None:
    gs.write_logic(gs.equips, equips, produced_by=_PB, sig=_SIG)


def _set_rows(gs: GameState, front: list[Unit], back: list[Unit]) -> None:
    """行域合一写(front/back 两参描述游戏排,
    落容器 = 单字段 DeployedView 一次写)。"""
    gs.write_logic(gs.deployed, _dvs(front, back), produced_by=_PB, sig=_SIG)


def _set_bench_units(gs: GameState, units: list[Unit]) -> None:
    """备战席写为单位槽序(凑星判据数据源 = bench_units_of 槽序)。"""
    slots = [BenchSlot(kind='unit', unit=u) for u in units]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by=_PB, sig=_SIG)


# ==================== ① 钻级 ====================

def test_diamond_dominates_and_multi_diamond_tiebreak():
    """凭据①:单钻直选(第 1 级支配,压过终局成员与 key 直击);多钻
    按角色/装备细分(钻内终局成员先;无角色细分 → 装备定序)。"""
    comp = _comp(['飞霄'], key=['火力风暴潮'])
    # 单钻直选:带钻空装备卡 > 终局成员卡 > key 直击卡
    opts = [_opt(0, equip='', has_diamond=True), _opt(1, char='飞霄'),
            _opt(2, equip='火力风暴潮')]
    out = supply.decide(opts, _fresh_gs(), comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0

    # 多钻 + 角色细分:两张带钻,其一为终局成员 → 成员钻胜出
    gs = _fresh_gs()
    opts = [_opt(0, equip='红钻', has_diamond=True),
            _opt(1, char='飞霄', equip='蓝钻', has_diamond=True)]
    out = supply.decide(opts, gs, comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1

    # 多钻无角色细分 → 钻内装备定序:轮滑鞋(通用值 4)> 反卫星狙击枪(2)
    opts = [_opt(0, equip='反卫星狙击枪', has_diamond=True),
            _opt(1, equip='轮滑鞋', has_diamond=True)]
    out = supply.decide(opts, _fresh_gs(), comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1


# ==================== ② 角色级 ====================

def test_endgame_char_card_beats_high_value_equip():
    """凭据②:锁线帧终局成员卡压高价值装备卡(轴间不可补偿,字典序)。"""
    comp = _comp(['飞霄'], key=['火力风暴潮'])
    opts = [_opt(0, char='飞霄', equip='反卫星狙击枪'),   # 通用值 2,tier 0
            _opt(1, equip='火力风暴潮')]                  # key 直击 tier 3 + 通用值 6
    out = supply.decide(opts, _fresh_gs(), comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0


# ==================== ③ 角色级空转帧 ====================

def test_unlocked_and_demoted_frames_fall_to_equip_axis():
    """凭据③:未锁线/降格帧角色级空转 + 装备级无 key 参照(空转帧装备
    轴退化为通用值定序;get_comp 解析失败帧 = flow 传 None,见 flow
    接线锁)。锁线帧作对照,证明断言可判别。"""
    comp = _comp(['飞霄'], key=['火力风暴潮'])
    opts = [_opt(0, char='飞霄', equip='反卫星狙击枪'),
            _opt(1, equip='轮滑鞋')]
    # 未锁线:角色级空转 → 轮滑鞋(4)> 反卫星狙击枪(2)
    out = supply.decide(opts, _fresh_gs(), None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1
    # 降格帧:锁线在但 demoted_endgame=True → 同未锁口径(防御位)
    out = supply.decide(opts, _fresh_gs(), comp, True)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1
    # 对照:锁线激活帧角色级生效 → 成员卡胜出
    out = supply.decide(opts, _fresh_gs(), comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0


# ==================== ④ 需求计数与两账口径 ====================

def test_demand_counting_and_component_upgrades_two_accounts():
    """凭据④:已持够数成品不再高分(需求按计数,修旧 +10 隶属误加分)、
    组件/近兑现升档;持有账按两账口径构造(备用 gs.equips)。"""
    # 已持够数:需求 [火力风暴潮, 反重力皮靴]、备用持 1×火力风暴潮 →
    # 火力风暴潮 tier 0(已满足),反重力皮靴 tier 3(未满足直击)胜出
    #(旧 +10 形态下火力风暴潮必胜)。
    comp = _comp(['飞霄'], key=['火力风暴潮', '反重力皮靴'])
    gs = _fresh_gs()
    _set_equips(gs, ['火力风暴潮'])
    opts = [_opt(0, equip='火力风暴潮'), _opt(1, equip='反重力皮靴')]
    out = supply.decide(opts, gs, comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1

    # 组件/近兑现:key=[火力风暴潮](配方 = 折叠小刀+轮滑鞋)、备用持
    # 1×折叠小刀 → 轮滑鞋近兑现 tier 2 胜出,折叠小刀 key 材料 tier 1 次之
    comp2 = _comp(['飞霄'], key=['火力风暴潮'])
    gs2 = _fresh_gs()
    _set_equips(gs2, ['折叠小刀'])
    opts2 = [_opt(0, equip='折叠小刀'), _opt(1, equip='轮滑鞋'),
             _opt(2, equip='绝对热量')]
    out = supply.decide(opts2, gs2, comp2, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1

    # 穿戴账半边(两账口径的另一支):备用账空 + 上阵单位穿戴有目标装备
    # → 需求按总账判定(火力风暴潮 tier 0 已满足,反重力皮靴 tier 3 胜出)。
    # 备用与穿戴互补的帧面:备用账独扛时 owned_total 回落 owned_spare
    # 与正确实现同值,只有本构造能测出穿戴账透传缺口
    comp3 = _comp(['飞霄'], key=['火力风暴潮', '反重力皮靴'])
    gs3 = _fresh_gs()
    _set_equips(gs3, [])
    _set_rows(gs3, [Unit(char_id='飞霄', star=1, equips=['火力风暴潮'])], [])
    opts3 = [_opt(0, equip='火力风暴潮'), _opt(1, equip='反重力皮靴')]
    out = supply.decide(opts3, gs3, comp3, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1, '上阵穿戴计入总账:火力风暴潮需求已满足,反重力皮靴直击胜出'


# ==================== ⑤ 刷新判据(三级全空才刷)====================

def test_refresh_gate_all_three_empty_and_fail_closed():
    """凭据⑤:建议刷 = 且仅 = 三级全空 ∧ 次数闸放行;left 缺(None)/
    尽(0)不刷且不阻塞落选卡(闸内嵌 decide,fail-closed)。"""
    comp = _comp(['飞霄'], key=['火力风暴潮'])
    # 三级全空(非终局成员 char 不算角色候选;装备全 tier 0)+ left=1 → 刷
    gs = _fresh_gs()
    _set_left(gs, 1)
    opts = [_opt(0, char='三月七', equip='绝对热量'),
            _opt(1, equip='生命之环')]
    assert isinstance(supply.decide(opts, gs, comp, False),
                      SupplyRefreshSuggestion)
    # 读法 A:tier 0 内高通用值件(火力风暴潮 6,无 key 参照)仍属三级全空 → 刷
    gs_hi = _fresh_gs()
    _set_left(gs_hi, 1)
    assert isinstance(supply.decide([_opt(0, equip='火力风暴潮')], gs_hi,
                                    None, False), SupplyRefreshSuggestion)
    # 角色级有候选 → 不刷(锁线帧终局成员在)→ 落选卡
    gs_char = _fresh_gs()
    _set_left(gs_char, 1)
    out = supply.decide([_opt(0, char='飞霄', equip='绝对热量')], gs_char,
                        comp, False)
    assert isinstance(out, SupplyDecision) and out.idx == 0
    # 装备级有 tier>0(key 直击)→ 不刷 → 落选卡
    out = supply.decide([_opt(0, equip='火力风暴潮')], _fresh_gs(), comp,
                        False)
    assert isinstance(out, SupplyDecision) and out.idx == 0
    # 带钻帧永不建议刷(「无带钻」合取支):多钻帧才到达闸面(单钻经
    # 第 1 级早退不经闸)——两钻均非终局成员/非 key 件(装备全 tier 0)
    # + left=1,现实现钻内细分落选卡;凭据①的多钻帧未构造次数闸读数,
    # 测不出该支
    gs_dia = _fresh_gs()
    _set_left(gs_dia, 1)
    out = supply.decide([_opt(0, char='三月七', equip='红钻', has_diamond=True),
                         _opt(1, equip='蓝钻', has_diamond=True)],
                        gs_dia, comp, False)
    assert isinstance(out, SupplyDecision) and out.idx == 0, \
        '带钻帧永不建议刷:钻内细分落选卡(红钻/蓝钻同值取输入序先)'
    # left 缺(None 未观察)/尽(0):fail-closed 不刷,直接落第 3 级选卡
    gs_dry = _fresh_gs()
    _set_left(gs_dry, 0)
    for gs_case in (_fresh_gs(), gs_dry):
        out = supply.decide([_opt(0, equip='绝对热量'),
                             _opt(1, equip='轮滑鞋')], gs_case, None, False)
        assert isinstance(out, SupplyDecision)
        assert out.idx == 1, '闸拒绝帧落选卡:通用值定序轮滑鞋(4)'


# ==================== ⑥ 席满无特殊分支 ====================

def test_full_bench_still_normal_pick():
    """凭据⑥:席满帧选角色卡照常胜出(溢出席语义 = 正常选卡,无特殊
    分支;记账失真申报 = 溢入单位不入 gs,凑星漏计归观察/记账批)。"""
    comp = _comp(['飞霄'])
    gs = _fresh_gs()
    _set_bench_units(gs, [Unit(char_id=f'杂鱼{i}', star=1)
                          for i in range(9)])
    opts = [_opt(0, char='飞霄', equip=''), _opt(1, equip='轮滑鞋')]
    out = supply.decide(opts, gs, comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0


# ==================== ⑦ 凑星 tiebreak ====================

def test_merge_star_tiebreak_spans_bench_and_rows():
    """凭据⑦:同名 1★ 恰 2 张的终局成员候选先于不凑星终局成员;2 张分跨
    备战席/上阵行域(1 bench + 1 front_row)——钉死 deployed 展平,实现
    漏计上阵域(如二元组直传被身份协议静默跳过)时该帧必红。"""
    comp = _comp(['飞霄', '希儿'], key=[])
    # 分跨域凑星:1×飞霄 备战席 + 1×飞霄 前排 → 凑星,压过不凑星的高装备候选
    gs = _fresh_gs()
    _set_rows(gs, [Unit(char_id='飞霄', star=1)], [])
    _set_bench_units(gs, [Unit(char_id='飞霄', star=1)])
    opts = [_opt(0, char='飞霄', equip=''),              # 凑星,装备 0 值
            _opt(1, char='希儿', equip='火力风暴潮')]    # 不凑星,通用值 6
    out = supply.decide(opts, gs, comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0, '凑星成员先于不凑星终局成员(装备值更高也不让位)'
    # 阴性对照:同名仅 1 张(count 1 ≠ 2)→ 不凑星 → 装备比 → 希儿胜
    gs_single = _fresh_gs()
    _set_bench_units(gs_single, [Unit(char_id='飞霄', star=1)])
    out = supply.decide(opts, gs_single, comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1


# ==================== ⑧ P1 配方锁帧 ====================

def test_p1_recipe_lock_frame_refresh_then_generic_pick():
    """凭据⑧:P1 配方锁帧(locked_comp 恒 None)——无钻三级全空恒真 →
    有次数建议刷;刷尽后按通用值定序落选卡(design §2.6 申报⑤)。"""
    # left=1:无钻帧三级全空恒真 → 建议刷
    gs = _fresh_gs()
    _set_left(gs, 1)
    out = supply.decide([_opt(0, equip='绝对热量')], gs, None, False)
    assert isinstance(out, SupplyRefreshSuggestion)
    # left 尽:直接按「通用值定序」落选卡(轮滑鞋 4 > 绝对热量 2)
    gs_dry = _fresh_gs()
    _set_left(gs_dry, 0)
    out = supply.decide([_opt(0, equip='绝对热量'),
                         _opt(1, equip='轮滑鞋')], gs_dry, None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1


# ==================== ⑨ 空候选帧 ====================

def test_empty_options_frame_returns_no_options():
    """凭据⑨:空候选帧 idx=0 no-options(与旧码同形;现役守卫下不应
    到达,纯函数定义须完备)。"""
    out = supply.decide([], _fresh_gs(), None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0
    assert out.reason == 'no-options'


# ==================== flow 接线锁(3.1 改接线)====================

def test_flow_supply_wiring_wraps_actions_and_parses_locked_comp():
    """flow.decide_supply 接线锁:候选自 gs.supply payload、纯值出口包装
    动作词表(Pick/Refresh 互斥)、locked_comp 套名经 get_comp 解析三态
    ——锁线 comp 生效 / 伪套名解析失败按未锁口径(凭据③的解析失败帧)/
    刷新建议经 flow 闸内嵌语义直发。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        SupplyPayload,
    )
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickSupplyParam,
        CwActionRefreshSupplyParam,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        bridge,
    )

    def _wired(gs: GameState):
        return bridge.MandateV1Strategy(gs,
                                        SimpleNamespace(strategy_seed=None))

    # 锁线帧:终局成员卡(花火 ∈ 列车同行 core)压 key 直击卡(火力风暴潮
    # ∈ 列车同行 key_equips)→ Pick 包装
    gs = _fresh_gs()
    gs.write_logic(gs.supply, SupplyPayload(options=[
        _opt(0, char='花火', equip='反卫星狙击枪'),
        _opt(1, equip='火力风暴潮')]), produced_by=_PB, sig=_SIG)
    strategy = _wired(gs)
    strategy.state.v3_intention = IntentionState(locked_comp='列车同行')
    out = strategy.decide_supply()
    assert isinstance(out, CwActionPickSupplyParam)
    assert out.idx == 0

    # 刷新帧:三级全空 + left=1 → Refresh 包装(闸内嵌 decide 经 flow 生效)
    gs2 = _fresh_gs()
    gs2.write_logic(gs2.supply, SupplyPayload(options=[
        _opt(0, equip='绝对热量')]), produced_by=_PB, sig=_SIG)
    _set_left(gs2, 1)
    out = _wired(gs2).decide_supply()
    assert isinstance(out, CwActionRefreshSupplyParam)

    # 解析失败帧:伪套名 → get_comp None → 未锁口径(char 卡不提权,
    # 装备定序轮滑鞋胜出)
    gs3 = _fresh_gs()
    gs3.write_logic(gs3.supply, SupplyPayload(options=[
        _opt(0, char='花火', equip='反卫星狙击枪'),
        _opt(1, equip='轮滑鞋')]), produced_by=_PB, sig=_SIG)
    strategy3 = _wired(gs3)
    strategy3.state.v3_intention = IntentionState(locked_comp='不存在的套名')
    out = strategy3.decide_supply()
    assert isinstance(out, CwActionPickSupplyParam)
    assert out.idx == 1
