"""补给屏测试面(决策 / 选项归并读链 / 选卡上报 / 节点推进接线)。

判据正本(持久索引):
- 决策单帧测试 = docs/develop/sr_od/application/currency_war/strategy-docs/
  30_supply_screen.md(3.1 验收凭据①-⑨,判据语义 = §2.5);
- 选项归并读链 = T-9 过剩经费 design §2.2/§4.1/§4.2(设计正本 =
  .debug/progress/2026-09-23-invest-effects-calc/designs/
  T-9-guoshengjingfei.md);
- 选卡上报(pick_supply 通道)= supply-pick design §2.0B/§3 验收锚 1
  + T-60 批漏项补齐(零写迁移通道;按动作 key 幂等契约);
- 节点推进接线 = 补给节点**零推进**接线判据面(2026-10-29 流程模型
  对齐:补给选完关模态回备战自动弹店,推进归出战动作 supply_finish,
  旧「确认即 supply_confirm 推进」接线随「确认即推节点」废止);
  kernel 原语语义(门挡/去重/补推)由 test_node_advance
  承重,本文件只校验接线面。

测试纪律:零真实副作用;决策/归并断言钉住设计语义不断言牌面;归并读链坐标
全部为测试自造常量(按归档帧布局实证取值,不读归档帧文件、不跑 OCR)。
装备配方/价值取自注册表真实数据(火力风暴潮 = 折叠小刀+轮滑鞋,
cw_equipment_data)。
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

from sr_od.application.currency_war.kernel.cw_action_report.pick_supply import (
    report_action_pick_supply_param,
)
from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_events import (
    SupplyOption,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
    consume_defect_sink,
    game_state_of,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickSupplyParam,
    action_key,
)
from sr_od.application.currency_war.obs.cw_node_obs import (
    _group_supply_columns,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import supply
from sr_od.application.currency_war.strategies.impl.mandate_v1.supply import (
    SupplyDecision,
    SupplyRefreshSuggestion,
)

_SIG = ChannelSig(family='logic_action', actor='cw-supply-decision-test',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenSupplyNode')
_PB = 'cw-supply-decision-test'


# ==================== 决策帧构造器 ====================


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


# ==================== ③ 角色级(虚拟全局评估;3.2 形态)====================


def test_unlocked_frames_evaluate_chars_via_virtual_assessment():
    """凭据③(3.2 重写):「是否终局角色」布尔门退役(总纲 §2.6 消费点
    映射)——未锁定/降格帧角色候选同样过虚拟全局评估,幸存者(备战位
    有空位 = 无让路对象,不经淘汰判定)按第 2 级胜出;装备轴仅在角色级
    无幸存时承接。"""
    comp = _comp(['飞霄'], key=['火力风暴潮'])
    opts = [_opt(0, char='飞霄', equip='反卫星狙击枪'),
            _opt(1, equip='轮滑鞋')]
    # 未锁定帧:飞霄虚拟置入(空备战位 = 无位移)幸存 → 角色卡胜出。
    out = supply.decide(opts, _fresh_gs(), None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0
    # 降格帧:同未锁口径(布尔门已退役,降格位对角色级零作用)。
    out = supply.decide(opts, _fresh_gs(), comp, True)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0
    # 角色级无幸存(候选全被虚拟阵容淘汰,席满帧构造见凭据⑦)→ 装备轴。


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
    """凭据⑤:建议刷 = 且仅 = 三级全空(无钻 ∧ 角色级无幸存 ∧ 装备全
    tier 0)∧ 次数闸放行;left 缺(None)/尽(0)不刷且不阻塞落选卡
    (闸内嵌 decide,fail-closed)。角色级「无幸存」两形态:无角色选项/
    候选被虚拟阵容淘汰(席满帧末位 = 自己,见凭据⑦构帧)。"""
    comp = _comp(['飞霄'], key=['火力风暴潮'])
    # 三级全空形态一(无角色选项,装备全 tier 0)+ left=1 → 刷
    gs = _fresh_gs()
    _set_left(gs, 1)
    opts = [_opt(0, equip='绝对热量'),
            _opt(1, equip='生命之环')]
    assert isinstance(supply.decide(opts, gs, comp, False),
                      SupplyRefreshSuggestion)
    # 读法 A:tier 0 内高通用值件(火力风暴潮 6,无 key 参照)仍属三级全空 → 刷
    gs_hi = _fresh_gs()
    _set_left(gs_hi, 1)
    assert isinstance(supply.decide([_opt(0, equip='火力风暴潮')], gs_hi,
                                    None, False), SupplyRefreshSuggestion)
    # 角色级有幸存候选 → 不刷(空备战位帧角色卡不经淘汰)→ 落选卡
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
    # 第 1 级早退不经闸)——两钻均非幸存角色/非 key 件(装备全 tier 0)
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
    """凭据⑥(3.2 形态):席满帧选卡 = 虚拟全局评估照常判定,无溢出
    特殊分支——成员候选(档 2,键小于同费垫牌)幸存照选(记账失真申报 =
    溢入单位不入 gs,凑星漏计归观察/记账批)。"""
    comp = _comp(['花火'])
    gs = _fresh_gs()
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of,
    )
    state_of(gs).line_candidates = ('列车同行',)
    _set_bench_units(gs, [Unit(char_id=f'杂鱼{i}', star=1)
                          for i in range(9)])
    opts = [_opt(0, char='花火', equip=''), _opt(1, equip='轮滑鞋')]
    out = supply.decide(opts, gs, comp, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0


# ==================== ⑥' 席满帧虚拟淘汰(3.2 形态)====================


def test_full_bench_junk_char_eliminated_by_virtual_assessment():
    """3.2 淘汰语义:席满帧候选经虚拟置入排序定位——排序末位 = 自己
    (最易让路 = 统一序列键最大)的被虚拟阵容淘汰,角色级空转落装备轴;
    高优先级候选(成员件)同帧幸存照选。构帧纪律:垫牌互异(同名凑三
    会触发合成净释放 → 无位移 → 候选不经淘汰,淘汰分支测空)。"""
    # 构帧:候选快照 = 列车同行(持牌花火/瓦尔特 = 档 2/5 成员件)+
    # 万金油三月七(档 6);持牌垫 = 互异高费档 8 件(2-5 费,Lv3 概率
    # 0 = 难再遇 = 序列靠后);候选 = 万敌(1费,概率满 = 最易再遇 =
    # 统一序列末位)→ 虚拟排序末位 = 万敌自己 → 淘汰 → 装备轴。
    gs = _fresh_gs()
    from test.sr_od.application.currency_war._cw_helpers import (
        cw4_comp as _comp_of,
    )
    from test.sr_od.application.currency_war._cw_helpers import (
        cw4_members as _members,
    )

    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.protection import (
        CROSS_LINE_KEEP_NAMES,
    )
    state_of(gs).line_candidates = ('列车同行',)
    km = set(_members(_comp_of('列车同行')))
    # 干净名 = 非线内非万金油(身份保护规避面已随统一让位优先级迭代
    # 3.4 退役,虚拟评估的淘汰语义由档位结构承载)。
    pool = [n for n, c in CHARACTERS.items()
            if n not in km and n not in CROSS_LINE_KEEP_NAMES
            and (c.cost or 0) >= 2]
    assert len(pool) >= 6, '测试前提:互异高费干净名不足'
    _set_bench_units(gs, [Unit(char_id='花火', star=1),
                          Unit(char_id='瓦尔特', star=1),
                          Unit(char_id='三月七', star=1)]
                     + [Unit(char_id=n, star=1) for n in pool[:6]])
    opts = [_opt(0, char='万敌', equip=''), _opt(1, equip='轮滑鞋')]
    out = supply.decide(opts, gs, None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1, '席满帧最易让位候选被虚拟阵容淘汰 → 装备轴承接'
    # 同帧高优先级候选(成员花火)幸存 → 角色卡胜出。
    opts_member = [_opt(0, char='花火', equip=''), _opt(1, equip='轮滑鞋')]
    out = supply.decide(opts_member, gs, None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0, '席满帧成员候选幸存(档 2 保护)→ 角色卡胜出'


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


# ==================== flow 接线测试(3.1 改接线)====================


def test_flow_supply_wiring_wraps_actions_and_parses_locked_comp():
    """flow.decide_supply 接线测试:候选自 gs.supply payload、纯值出口包装
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

    # 解析失败帧:伪套名 → get_comp None → 按未锁口径(3.2 后角色级
    # 无终局布尔门——花火虚拟置入(空备战位 = 无位移)幸存,仍压装备轴)
    gs3 = _fresh_gs()
    gs3.write_logic(gs3.supply, SupplyPayload(options=[
        _opt(0, char='花火', equip='反卫星狙击枪'),
        _opt(1, equip='轮滑鞋')]), produced_by=_PB, sig=_SIG)
    strategy3 = _wired(gs3)
    strategy3.state.v3_intention = IntentionState(locked_comp='不存在的套名')
    out = strategy3.decide_supply()
    assert isinstance(out, CwActionPickSupplyParam)
    assert out.idx == 0


# ==================== 选项归并读链(纯函数)====================
# ===== 自造坐标常量(依据 = 归档帧布局实证的设计记录,非运行时真值)=====

_COL_XS: tuple[int, ...] = (256, 608, 960, 1312, 1664)   # 5 列锚 x,列距 352
_CHAR_Y: int = 565            # 单排角色名 y(双排 ≈513,纯函数不消费 char y)
_EQUIP_Y: int = 700           # 单排装备名 y
_EQUIP_Y_A: int = 648         # 双排第一行 y
_EQUIP_Y_B: int = 748         # 双排第二行 y
_CLICK_Y = 550                # 卡身点击 y(常量语义断言用,纯函数不输出 y)


def _chars(names: tuple[str, ...],
           xs: tuple[int, ...] = _COL_XS) -> list[tuple[int, str]]:
    """列锚造料:第 i 列角色名文本中心 x = 列锚 x(截断 = 前列锚复用,
    失读降级造料靠少传名字;可传 xs 局部覆盖)。"""
    return list(zip(xs, names, strict=False))


def _single_row(names: tuple[str, ...],
                drift: tuple[int, ...] = (0, 0, 0, 0, 0),
                xs: tuple[int, ...] = _COL_XS) -> list[tuple[int, int, str]]:
    """单排装备造料:每列一件,装备文本中心 x = 列锚 x + 名长漂移量
    (截断语义同 _chars)。"""
    return [(x + d, _EQUIP_Y, n)
            for x, d, n in zip(xs, drift, names, strict=False)]


def test_single_row_five_columns_matches_legacy_per_equip_reading() -> None:
    """单排 5 列回归锚:角色锚点定列与旧「每装备名 = 1 选项」读链逐值
    一致(idx/char/equip 序、点击点 = 装备文本中心 x + 卡身 y)——
    默认布局零行为漂移(design §3 零改动声明)。"""
    chars = _chars(('镜流', '希儿', '花火', '停云', '杰帕德'))
    equips = _single_row(('折叠小刀', '量产型装甲', '光能电池',
                          '垃圾袋', '生命之花'),
                         drift=(12, 40, 0, 25, 8))
    out = _group_supply_columns(chars, equips)
    assert len(out) == 5
    for i, ((opt, click_x), (ex, _ey, name)) in enumerate(zip(out, equips, strict=True)):
        assert opt.idx == i
        assert opt.char == chars[i][1], f'第 {i} 列角色配对'
        assert opt.equip == name
        assert opt.extra_equips == (), '单排每列恰一件'
        assert opt.has_diamond is False
        assert click_x == ex, '点击点 x = 装备文本中心 x(现役语义零漂移)'


def test_double_row_five_columns_groups_by_column() -> None:
    """双排 5 列 10 件(归档帧布局造料:跨列重复实证 = 光能电池第 3/5 列、
    折叠小刀第 1/5 列)→ 5 选项;每列 equip = y 序首件、extra_equips =
    其余;char 配对正确;点击点 = 簇首件(y 序)x。"""
    chars = _chars(('镜流', '希儿', '花火', '停云', '杰帕德'))
    equips: list[tuple[int, int, str]] = []
    # 逐列两件:(首件 y=648, 次件 y=748);x = 列锚 + 名长漂移(≤60)
    per_col = (
        ('折叠小刀', '垃圾袋'),
        ('量产型装甲', '生命之花'),
        ('光能电池', '折叠小刀'),
        ('生命之花', '光能电池'),
        ('光能电池', '折叠小刀'),
    )
    drifts = ((0, 18), (44, 6), (0, 30), (22, 50), (8, 0))
    for cx, (n1, n2), (d1, d2) in zip(_COL_XS, per_col, drifts,
                                    strict=True):
        equips.append((cx + d1, _EQUIP_Y_A, n1))
        equips.append((cx + d2, _EQUIP_Y_B, n2))
    out = _group_supply_columns(chars, equips)
    assert len(out) == 5, '双排 10 件归并为 5 列(非 10 幻影选项)'
    for i, ((opt, click_x), (n1, n2), (d1, _d2)) in enumerate(
            zip(out, per_col, drifts, strict=True)):
        assert opt.idx == i
        assert opt.char == chars[i][1]
        assert opt.equip == n1, 'equip = 列内 y 序首件'
        assert opt.extra_equips == (n2,), 'extra_equips = 其余件(y 序)'
        assert click_x == _COL_XS[i] + d1, '点击点 = 簇首件 x'


def test_missing_char_anchor_degrades_to_orphan_column() -> None:
    """锚点失读降级:某列角色名缺席 → 该列装备簇自成孤儿列(char='',
    不并入邻列);列序按 x 保持,其余列配对不受扰。"""
    # 第 3 列(花火,x=960)失读:其余四列锚显式传 xs
    chars = _chars(('镜流', '希儿', '停云', '杰帕德'),
                   xs=(_COL_XS[0], _COL_XS[1], _COL_XS[3], _COL_XS[4]))
    equips = _single_row(('折叠小刀', '量产型装甲', '光能电池',
                          '垃圾袋', '生命之花'))
    out = _group_supply_columns(chars, equips)
    assert len(out) == 5, '孤儿簇不并邻列,5 列仍在'
    assert [opt.char for opt, _ in out] == \
        ['镜流', '希儿', '', '停云', '杰帕德'], '第 3 列孤儿列 char=空'
    assert out[2][0].equip == '光能电池'
    assert [opt.idx for opt, _ in out] == [0, 1, 2, 3, 4], '列序 = 画面列序'


def test_char_only_column_first_class_option() -> None:
    """char-only 列(锚点在、装备簇缺)→ equip=''、extra_equips=() 的
    一等选项成立(人才储备类变体天然承接);点击点 = 角色锚 x。"""
    chars = _chars(('镜流', '希儿', '花火'))
    equips = [(x, _EQUIP_Y, n) for x, n in
              zip(_COL_XS[1:3], ('折叠小刀', '量产型装甲'),
                                strict=True)]   # 第 1 列无装备
    out = _group_supply_columns(chars, equips)
    assert len(out) == 3
    first = out[0][0]
    assert (first.char, first.equip, first.extra_equips) == ('镜流', '', ())
    assert out[0][1] == _COL_XS[0], 'char-only 列点击点 = 锚 x'
    assert out[1][0].equip == '折叠小刀' and out[2][0].equip == '量产型装甲'


def test_zero_anchor_fallback_cluster_skeleton() -> None:
    """零锚点兜底(角色名极端全失读)→ 装备 x 簇作骨架,各簇自成
    char='' 列,列序 = 簇 x 序。"""
    equips = _single_row(('折叠小刀', '量产型装甲', '光能电池'))
    out = _group_supply_columns([], equips)
    assert len(out) == 3
    assert all(opt.char == '' for opt, _ in out), '簇骨架列 char=空'
    assert [opt.equip for opt, _ in out] == ['折叠小刀', '量产型装甲',
                                             '光能电池']


def test_column_gap_keeps_clusters_split_and_name_drift_does_not() -> None:
    """聚簇双向余量:同列双件名长漂移(x 互距 ≤60)不裂簇;相邻列距
    352 > 阈值 200 不并簇(左列最右件与右列最左件间距仍 >> 阈值)。"""
    chars = _chars(('镜流', '希儿'))
    equips = [
        (_COL_XS[0], _EQUIP_Y_A, '折叠小刀'),
        (_COL_XS[0] + 60, _EQUIP_Y_B, '垃圾袋'),     # 同列漂移 60 ≤ 200
        (_COL_XS[1] - 60, _EQUIP_Y_A, '量产型装甲'),  # 距左列次件 352-120=232
        (_COL_XS[1], _EQUIP_Y_B, '生命之花'),
    ]
    out = _group_supply_columns(chars, equips)
    assert len(out) == 2, '两列四件,裂簇/并簇均不发生'
    assert out[0][0].equip == '折叠小刀'
    assert out[0][0].extra_equips == ('垃圾袋',)
    assert out[1][0].equip == '量产型装甲'
    assert out[1][0].extra_equips == ('生命之花',)


def test_worst_case_geometry_pairs_to_own_anchor() -> None:
    """最差几何造料(5 字件名 × 2 字角色名,簇心-自身锚点 ~112)不破
    配对:归入自身锚点(112 ≤ 容差 150),距邻锚 240 > 150 不误归。"""
    chars = [(_COL_XS[0], '镜流'), (_COL_XS[1], '希儿')]
    # 量产型装甲(5 字名)文本中心右移:距自身锚 112(单排帧实测最差列)
    equips = [(_COL_XS[0] + 112, _EQUIP_Y, '量产型装甲'),
              (_COL_XS[1] + 30, _EQUIP_Y, '折叠小刀')]
    out = _group_supply_columns(chars, equips)
    assert len(out) == 2
    assert out[0][0].char == '镜流' and out[0][0].equip == '量产型装甲', \
        '最差几何仍配对自身锚点'
    assert out[1][0].char == '希儿'


def test_diamond_text_fallback_scans_all_column_names() -> None:
    """带钻文本兜底遍历全列件名(design §2.2.8 迁移):extra_equips 命中
    三钻词表 → 该列 has_diamond=True;「虫洞掘进钻头」类带钻字非钻名
    不误判(精确匹配非子串)。"""
    chars = _chars(('镜流', '希儿', '花火'))
    equips = [
        (_COL_XS[0], _EQUIP_Y_A, '折叠小刀'),
        (_COL_XS[0], _EQUIP_Y_B, '财富宝钻'),        # 附加件带钻 → 兜底命中
        (_COL_XS[1], _EQUIP_Y, '虫洞掘进钻头'),       # 带钻字非钻名
        (_COL_XS[2], _EQUIP_Y, '量产型装甲'),
    ]
    out = _group_supply_columns(chars, equips)
    assert out[0][0].has_diamond is True, '附加件名命中钻词表 → 列带钻'
    assert out[1][0].has_diamond is False, '带钻字非钻名不误判'
    assert out[2][0].has_diamond is False


def test_sift_hit_assigns_to_nearest_cluster() -> None:
    """SIFT 主通道:命中点归最近簇心(≤ 容差)→ 该列 has_diamond=True;
    文本名不含钻词表也成立(视觉通道独立于文本兜底)。"""
    chars = _chars(('镜流', '希儿', '花火'))
    equips = _single_row(('折叠小刀', '量产型装甲', '光能电池'))
    out = _group_supply_columns(chars, equips,
                                sift_hits=[(_COL_XS[1] + 10, 716)])
    assert [opt.has_diamond for opt, _ in out] == [False, True, False], \
        'SIFT 命中点归第 2 列簇'


# ==================== pick_supply 通道上报 ====================


def _lsig(actor: str) -> ChannelSig:
    return ChannelSig(family='logic_action', actor=actor, mode='compute')


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
    """上报帧观测面按参组装(None = 保持未观察,供 None 边界分支)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit',
                           unit=Unit(char_id=c, star=s))
                 for i, (c, s) in enumerate(bench)]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def _units(gs: GameState) -> list[tuple[str, int]]:
    return [(u.char_id, u.star) for u in bench_units_of(gs)]


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


def test_pick_supply_immediate_char_and_consequence(
        rows_sink: _RowSink) -> None:
    """补给确认即时单相上报测试(supply-pick design §2.0B):一口写 owned
    规范名 + 单位入账分支(char 入席 1★ + 合成级联)+ 装备后果分支(命中表 →
    送角色入账分支)——无发射/落地两相,无证据参数。"""
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=[])
    out = report_action_pick_supply_param(
        gs, CwActionPickSupplyParam(idx=0, char_name='银狼',
                                    norm_item='分身墨镜'),
        _lsig('CwActionPickSupplyOp'))
    assert out.applied is True
    units = _units(gs)
    assert ('银狼', 2) in units and ('银狼', 1) in units, \
        '单位入账分支 1★入席合成 2★ + 后果分支送出 1★(购买同语义)'
    assert gs.bench.source == 'logic', '两条分支同源 write_logic'
    assert gs.equips.value == ['分身墨镜'], 'owned += 规范名(即时入栏)'
    assert gs.equips.source == 'logic', '入栏 write_logic(单相一口写)'


def test_pick_channels_payload_fields_excluded_from_action_key() -> None:
    """载荷扩展不换键(照 PickInvest 先例):归一件名/角色载荷字段
    action_key_exclude,幂等键与纯 idx 形态恒等。"""
    assert action_key(CwActionPickSupplyParam(idx=2, char_name='银狼',
                                              norm_item='分身墨镜Max')) \
        == action_key(CwActionPickSupplyParam(idx=2)), 'supply 载荷不入键'


def test_pick_supply_equip_unresolved_flips_source(
        rows_sink: _RowSink) -> None:
    """补给装备名未解析(逐件 fail-closed,T-9 列表式装备入账分支):未解析件
    禁猜——equips 值不变翻来源 + 留证行;已解析件照常入账(不整批弃)。
    形态 = 装备入账分支集合内含 '' 件(norm_item=''+附加件非空,或附加件
    归一未解析);``char≠'' ∧ 全部分支空`` 已改走零装备名分支(见
    test_pick_supply_char_only_zero_equip_column,旧「主件空 = 未解析」
    归因随 T-9 退役)。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['折叠小刀'])
    out = report_action_pick_supply_param(
        gs, CwActionPickSupplyParam(idx=0, char_name='希儿',
                                    norm_item='量产型装甲',
                                    extra_norm_items=('',)),
        _lsig('CwScreenSupplyNode'))
    assert out.applied is True
    assert ('希儿', 1) in _units(gs), '单位入账分支不受装备名未解析影响'
    assert gs.equips.value == ['折叠小刀', '量产型装甲'], \
        '已解析件照常入账(fail-closed 不整批弃)'
    assert gs.equips.source == 'logic_rand', '未解析件值不变翻来源'
    assert rows_sink.kinds() == ['pick_supply_name_unresolved'], '留证行 kind'


def test_pick_supply_char_only_zero_equip_column_no_defect(
        rows_sink: _RowSink) -> None:
    """char-only 选定测试(T-9 对抗 r1 A1):char 非空 ∧ 装备入账分支全空 →
    装备域零写(无预测无期望,零翻来源)+ reason 留证、**零缺陷行**
    ——合法无装备读数列(人才储备类 char-only 列/件名全失读列)禁发
    「装备名未解析」伪缺陷。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['折叠小刀'])
    before = (gs.equips.value, gs.equips.source)
    out = report_action_pick_supply_param(
        gs, CwActionPickSupplyParam(idx=0, char_name='希儿', norm_item=''),
        _lsig('CwScreenSupplyNode'))
    assert out.applied is True and out.reason == 'no_equip_column', \
        '零装备名分支留证载体 = reason'
    assert (gs.equips.value, gs.equips.source) == before, '装备域零写'
    assert rows_sink.kinds() == [], '零缺陷行(伪缺陷治理)'


def test_pick_supply_extra_norm_items_land_all_legs(
        rows_sink: _RowSink) -> None:
    """附加装备入账分支测试(T-9):extra_norm_items 两件 → owned 尾追两件
    (主件 → 附加件画面 y 序)+ 获得后果链逐件(主件分身墨镜送银狼 1★
    合成 2★、附加件分身墨镜Max 送银狼 2★)——世界写入 = 角色 + 随选
    装备组全列。"""
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=[])
    out = report_action_pick_supply_param(
        gs, CwActionPickSupplyParam(idx=0, char_name='银狼',
                                    norm_item='分身墨镜',
                                    extra_norm_items=('分身墨镜Max',)),
        _lsig('CwActionPickSupplyOp'))
    assert out.applied is True
    assert gs.equips.value == ['分身墨镜', '分身墨镜Max'], \
        '装备入账分支 0..n 件按画面 y 序全列入栏'
    units = _units(gs)
    assert units.count(('银狼', 2)) == 2, \
        '后果链逐件:主件合成 2★ + 附加件 Max 直送 2★'
    assert rows_sink.kinds() == [], '全解析零缺陷'


def test_pick_supply_content_unknown_flips_domains(
        rows_sink: _RowSink) -> None:
    """补给内容全未知(兜底点卡路径,载荷空):禁猜——bench/equips 值
    不变翻来源 + 留证行(观察覆盖差异收口自愈)。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['折叠小刀'])
    out = report_action_pick_supply_param(
        gs, CwActionPickSupplyParam(idx=0),
        _lsig('CwScreenSupplyNode'))
    assert out.applied is True and out.reason == 'content_unresolved'
    assert _units(gs) == [('希儿', 1)] and gs.bench.source == 'logic_rand', \
        'bench 值不变翻来源'
    assert gs.equips.value == ['折叠小刀'] and gs.equips.source == 'logic_rand', \
        'equips 值不变翻来源'
    assert rows_sink.kinds() == ['pick_supply_content_unresolved'], '留证行 kind'


# ==================== 画面 op 即时上报与节点推进接线 ====================


def _seeded_gs():
    """剧本容器:bench 两枚 1★银狼 + equips 空读(后果分支合成级联素材)。"""
    session = StrategySession()
    gs = game_state_of(session)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='银狼', star=1))
             for i in range(2)]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    return session, gs


def _make_match(test_context, monkeypatch, session):
    match = SimpleNamespace(session=session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    return match


def test_pick_confirm_reports_full_result_immediately(
        test_context, monkeypatch) -> None:
    """pick 即时上报测试:确认点击后(机械半全桩,零落地相)容器即持
    owned 规范名 + 单位入账分支(1★入席合成级联)+ 装备后果分支(分身墨镜
    → 送 1★银狼)——一口写,无发射/落地两相。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_pick_supply_action as pa,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_env import (
        OverlayPickExecEnv,
    )

    session, gs = _seeded_gs()
    _make_match(test_context, monkeypatch, session)
    host = SimpleNamespace(
        ctx=SimpleNamespace(controller=SimpleNamespace(
            mouse_move=lambda p: None, click=lambda p, **k: None)),
        screenshot=lambda: object(),
        round_by_find_and_click_area=lambda *a, **k: _Area(True),
    )
    env = OverlayPickExecEnv(op=host, match=None, idx=0,
                                target=SimpleNamespace(x=900, y=550),
                                picked=None)
    op = pa.CwActionPickSupplyOp(
        test_context,
        CwActionPickSupplyParam(idx=0, char_name='银狼', norm_item='分身墨镜'),
        env)
    result = _run_node(test_context, op, op.run)
    assert result.is_success
    assert gs.equips.value == ['分身墨镜'], 'owned 即时持规范名(不等下一帧)'
    assert gs.equips.source == 'logic', '入栏 write_logic'
    units = _units(gs)
    assert ('银狼', 2) in units and ('银狼', 1) in units, \
        '单位入账分支 1★入席合成 2★ + 后果分支送出 1★'


def test_chosen_supply_written_before_dispatch_and_no_landing_phase(
        test_context, monkeypatch) -> None:
    """画面 op 侧测试:chosen_supply 2 元组(角色, 装备名列表;T-9 裁定 2)
    在动作派发前已写(写点 = 选择点,``op-layer.md`` §2.2);选卡派发即终结
    (动作体自产 round_success 终结交回,决策链接线迭代起 ``_do_action``
    返回轮次结果);节点完成门 miss(act 分发身份安全网)后零容器写
    (无落地相补写面)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_action_registry,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    session, gs = _seeded_gs()
    match = SimpleNamespace(
        session=session,
        strategy=SimpleNamespace(
            decide_supply=lambda: CwActionPickSupplyParam(idx=0, reason='test')))
    match.gs = gs
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    opt = SimpleNamespace(char='希儿', equip='星币收集器', has_diamond=True,
                          extra_equips=('垃圾袋',))
    monkeypatch.setattr(sn, 'read_supply_options',
                        lambda ctx, screen: [(opt, SimpleNamespace(x=900, y=550))])
    monkeypatch.setattr(op, '_read_node_bar', lambda screen: None)
    monkeypatch.setattr(op, '_read_refresh_anchor', lambda screen: None)

    chosen_at_dispatch: list = []

    class _ProbeStubOp:
        def execute(self) -> bool:
            chosen_at_dispatch.append(gs.chosen_supply.value)
            return True

    monkeypatch.setattr(cw_action_registry, 'action_op_for',
                        lambda act, ctx, env: _ProbeStubOp())
    _run_node(test_context, op, op.observe)   # 观察 node 装载 obs(report 落容器)
    rs = op._do_action()
    assert rs.is_success and '终结交回' in (rs.status or ''), \
        f'选卡派发即终结(终结交回):{rs!r}'
    assert chosen_at_dispatch == [('希儿', ('星币收集器', '垃圾袋'))], \
        'chosen_supply 2 元组在派发前已写(写点 = 选择点,携全列装备)'
    write_seq_after_dispatch = gs.write_seq
    # 节点完成门 miss(overlay 已关)= 分发身份安全网 success 交回,
    # 零落地相补写面(证据闩已随即时上报批退役)。
    monkeypatch.setattr(op, '_in_node', lambda screen: False)
    result = _run_node(test_context, op, op.act)
    assert result.is_success, '门 miss = 节点完成 success 交回'
    assert gs.write_seq == write_seq_after_dispatch, \
        '门 miss 后零容器写(无落地相补写面)'


# --- 节点推进接线(补给侧)---

#: 剧本读数:节点条「备战阶段 1-5」→ 序位键 (1, 5)(补给节点 = 位面1 第5轮)。
_POS_1_5: tuple[int, int] = (1, 5)


def _make_match_with_gs(test_context, monkeypatch):
    """局容器装配:session + gs 挂 cw_match(game_state_from_ctx 供给口)。"""
    session = StrategySession()
    match = SimpleNamespace(session=session)
    match.gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    return match


def _run_pick_supply(test_context, monkeypatch, match):
    """跑 CwActionPickSupplyOp 确认链:宿主机械半全桩(点选/确认点击),
    只留记录面(意图遥测 + 推进上报)真跑。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_pick_supply_action as pa,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_env import (
        OverlayPickExecEnv,
    )

    host = SimpleNamespace(
        ctx=SimpleNamespace(controller=SimpleNamespace(
            mouse_move=lambda p: None, click=lambda p, **k: None)),
        screenshot=lambda: object(),
        round_by_find_and_click_area=lambda *a, **k: _Area(True),
    )
    env = OverlayPickExecEnv(op=host, match=None, idx=0,
                                target=SimpleNamespace(x=900, y=550),
                                picked=None)
    op = pa.CwActionPickSupplyOp(
        test_context, CwActionPickSupplyParam(idx=0), env)
    _run_node(test_context, op, op.run)


def _run_supply_observe(test_context, monkeypatch,
                        pos: tuple[int, int] | None):
    """跑 CwScreenSupplyNode 观察 node:门内 + 选项读/节点条读桩化
    (节点条返回剧本读数;None = 读不得跳过测试的对照位)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    op = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    monkeypatch.setattr(sn, 'read_supply_options', lambda ctx, screen: [])
    monkeypatch.setattr(op, '_read_node_bar', lambda screen: pos)
    monkeypatch.setattr(op, '_read_refresh_anchor', lambda screen: None)
    _run_node(test_context, op, op.observe)


def test_auto_popup_supply_pick_does_not_advance(
        test_context, monkeypatch) -> None:
    """自动弹形态剧本:结算确认直接弹补给屏(无备战帧锚定,容器 v=None)
    → 补给屏观察 node 节点条读数首锚定(1-5 → 5)→ 选补给确认点击
    **零节点推进**(2026-10-29 流程模型对齐:选完关模态回备战自动弹店,
    节点推进归出战动作 supply_finish;旧「确认即 supply_confirm 推进恰
    一次」随「确认即推节点」废止)。"""
    match = _make_match_with_gs(test_context, monkeypatch)
    gs = match.gs
    _run_supply_observe(test_context, monkeypatch, _POS_1_5)
    assert gs.node_pos.value == _POS_1_5, \
        '自动弹形态:补给屏观察 node 完成首锚定(v=None 行)'
    assert gs.node_pos.source == 'observation'
    _run_pick_supply(test_context, monkeypatch, match)
    assert gs.node_pos.value == _POS_1_5 \
        and gs.node_pos.source == 'observation', \
        '补给确认零节点推进(选完回备战弹店,推进归出战 supply_finish)'


def test_divert_form_supply_pick_does_not_advance(
        test_context, monkeypatch) -> None:
    """divert 形态剧本:备战帧已锚(CwScreenPrep 写端形态,此处直接锚)
    → 补给屏(备战的 divert 分支)观察 node 等值 reanchor → 确认点击
    **零节点推进**(2026-10-29 流程模型对齐,同自动弹形态)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        observe_node_anchor,
    )
    match = _make_match_with_gs(test_context, monkeypatch)
    gs = match.gs
    observe_node_anchor(gs, _POS_1_5, trigger_screen='货币战争-备战',
                        actor='CwScreenPrep')
    # 备战→补给 divert:补给屏等值读数 reanchor(仍 observation 态)
    _run_supply_observe(test_context, monkeypatch, _POS_1_5)
    assert gs.node_pos.source == 'observation', 'divert 形态:等值 reanchor'
    _run_pick_supply(test_context, monkeypatch, match)
    assert gs.node_pos.value == _POS_1_5 \
        and gs.node_pos.source == 'observation', \
        'divert 形态:补给确认零节点推进(推进归出战 supply_finish)'
