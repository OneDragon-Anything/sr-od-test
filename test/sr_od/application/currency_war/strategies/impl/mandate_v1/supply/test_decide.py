"""补给选卡决策单帧测试(补给统一优先级后的角色级判据面)。

判据正本(持久索引):
- 统一装配与候选不进档 1 = docs/develop/sr_od/application/currency_war/
  strategy-docs/30_supply_screen.md §2.1(裁定五 2026-11-01:补给沿用
  统一优先级;候选 = 假设性入场者按卡面八档定序,凑星价值经档 2 承载);
- 统一装配入口 = priority.assemble_candidate_eval(与商店获取让位
  [11_shop_decisions.md §4.0 步 4] 同一实现,域差异仅候选牌三件套);
- 行为申报两口(非成员凑星无承载 / 席满同名并列攒素材翻转)= 30 号篇
  §2.1 行为申报段。

构帧纪律:补齐件互异(同名凑三触发合成净释放会改走直幸存路径);
「干净名」= 非万金油(CROSS_LINE_KEEP_NAMES)/ 非档 7 羁绊
(TIER7_BOND_NAMES 求交空)的注册表名,注册表现查防漂移。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_events import (
    SupplyOption,
)
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    supply,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.priority import (
    TIER7_BOND_NAMES,
    ShopUnit,
    assemble_candidate_eval,
    sell_order_with_keys,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.protection import (
    CROSS_LINE_KEEP_NAMES,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.supply import (
    SupplyDecision,
)


def _opt(idx: int, char: str = '', equip: str = '') -> SupplyOption:
    return SupplyOption(idx=idx, char=char, equip=equip)


def _clean_cost_fillers(count: int, cost: int, exclude: set[str]) -> list[str]:
    """互异同费干净名(注册表现查):费用恰 = cost、非万金油、非档 7
    羁绊——Lv1-3 帧 2 费+件概率 0 且 -cost < 0(候选零成本),档 8 内
    键小于候选 = 池件更保,候选末位形态的可控构帧件。"""
    out: list[str] = []
    for n, c in CHARACTERS.items():
        if len(out) >= count:
            break
        if n in exclude or (c.cost or 0) != cost:
            continue
        if n in CROSS_LINE_KEEP_NAMES:
            continue
        ch = CHARACTERS[n]
        if (set(ch.factions) | set(ch.flows)) & TIER7_BOND_NAMES:
            continue
        out.append(n)
    assert len(out) >= count, f'测试前提:同费干净名不足({len(out)})'
    return out


def _make_gs(*, bench: list[tuple[str, int]], front: tuple[str, ...],
             level: int, locked: str | None = None,
             candidates: tuple[str, ...] = ()):
    """补给评估帧(容器 + 双宿主状态同源接线;补给域 session = gs
    同一对象,与生产 supply.decide 调用形态一致)。"""
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.kernel.cw_intention import (
        IntentionState,
    )
    sess = StrategySession()
    st = state_of(sess)
    st.cw4_counters = {}
    st.v3_intention = (IntentionState(locked_comp=locked)
                       if locked else IntentionState())
    if locked:
        st.target_comp = get_comp(locked)
    st.line_candidates = tuple(candidates)
    gs = cw4_gs(sess, plane=1, round_num=3, node='battle',
                gold=30, level=level, hp=80, deploy_cap=level,
                bench=[cw4_bc(n, star=s) for n, s in bench],
                front_row=[Unit(char_id=n, star=1) for n in front])
    gs.strategy_state = st
    return gs


def _virtual_target(gs, name: str):
    """直调部署接口复算评估链步 3(纯读零污染,与生产同参):返回
    (frame, sim, target)——帧前提断言的复算载体。"""
    frame = mandate.snapshot_frame(gs)
    sim = mandate.simulate_acquired_units(frame.bench, frame.deployed,
                                          name, 1)
    prep = mandate.assemble_prep_context(gs, gs, frame)
    target = mandate.select_deployment(
        frame, prep,
        virtual_bench=[bs for _i, bs in sim.bench], virtual_field=sim.field)
    return frame, sim, target


def test_same_name_candidate_ranks_by_card_face_not_tier1():
    """同名候选不再因部署同名命中档 1(裁定五特例退役;30 号篇 §2.1
    统一装配):分跨备战席/上阵行域的同名 3 张凑星帧(1 bench + 1 front
    + 候选 → 升星连锁合成 2★),候选按卡面档定序——飞霄(非成员/非
    万金油/非羁绊)落档 8,被希儿(量子同频羁绊,档 7)压过;胜出键首档
    = 7 直断「档 1 按名命中已不保护候选」(旧特例形态下飞霄键首档
    = 1 必胜出)。旧「同名凑星候选优先」语义的现行承载 = 档 2,见
    test_tier2_carries_merge_star_value_for_member。"""
    gs = _make_gs(bench=[('飞霄', 1)], front=('飞霄',), level=3)
    opts = [_opt(0, char='飞霄', equip=''),
            _opt(1, char='希儿', equip='火力风暴潮')]
    out = supply.decide(opts, gs, None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1, '同名候选按卡面档定序:希儿(档 7)压飞霄(档 8)'
    assert '键首档=7' in out.reason, \
        f'胜出键首档应 = 7(羁绊档):{out.reason!r}'


def test_tier2_carries_merge_star_value_for_member():
    """凑星价值经档 2 承载(30 号篇 §2.1:成员星目标推进件的候选按
    卡面落档 2,档内 -total_star 聚合含置入候选):列车同行线内,候选
    花火(在场 1 张,置入后聚合 2)先于候选姬子·启行(未持有,置入后
    聚合 1)——聚合大者键小排先,凑星候选天然排高。在手件放上阵行
    域:聚合读源 = 备战位 ∪ 前后排全量,实现漏计上阵域(二元组直传
    被静默跳过)时花火聚合缺 1、与本断言冲突。"""
    gs = _make_gs(bench=[], front=('花火',), level=3,
                  candidates=('列车同行',))
    opts = [_opt(0, char='姬子·启行', equip=''),
            _opt(1, char='花火', equip='')]
    out = supply.decide(opts, gs, None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1, '档 2 聚合承载:在场 1 张的花火候选排先'
    assert '键首档=2' in out.reason, \
        f'成员星目标推进件应落档 2:{out.reason!r}'


def test_candidate_absorbed_into_virtual_target_still_eliminated():
    """候选进虚拟定型仍判末位 = 候选反例(商店 X 反例的补给镜像;
    30 号篇 §2.1 候选不进档 1):杂件候选(娜塔莎,与 bench 佩拉共享
    贝洛伯格标签)被虚拟定型收编进 target,装配减名后仍按卡面档 8
    参与末位判定——Lv3 帧池内 2 费件(概率 0 同档、-cost < 0 的候选
    零成本分量)全子键更小 → 末位 = 候选 → 被虚拟阵容淘汰,角色级
    空转落装备轴。若档 1 按名命中覆盖候选(旧特例),候选键首档 = 1
    恒幸存——本帧即红。帧前提断言候选 ∈ 虚拟定型名集(收编形态在
    场;定型漂移使候选出 target 时本帧退化为平凡末位帧,前置断言
    让退化响亮暴露)。"""
    fillers = _clean_cost_fillers(8, 2, {'娜塔莎', '佩拉'})
    bench = [('佩拉', 1)] + [(n, 1) for n in fillers]
    # 未锁定帧 + 前排留空位:DP 枚举贝洛伯格对(佩拉 + 娜塔莎)凑档
    # 上场 → 候选被收编。
    gs = _make_gs(bench=bench, front=('吉尔伽美什',), level=3)
    _frame, _sim, target = _virtual_target(gs, '娜塔莎')
    assert '娜塔莎' in target, \
        f'帧前提失守:候选未被虚拟定型收编: {sorted(target)}'
    opts = [_opt(0, char='娜塔莎', equip=''),
            _opt(1, equip='轮滑鞋')]
    out = supply.decide(opts, gs, None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 1, \
        '收编形态下末位 = 候选 → 被虚拟阵容淘汰,角色级空转落装备轴'


def test_field_redeployed_out_units_enter_elimination_pool():
    """部署外全集比较域(30 号篇 §2.1 统一装配:让位池 = 虚拟备战位
    ∪ 虚拟场上部署外件——field 撤下件入池,与商店同款):换阵帧
    (锁定双王圣杯,bench Saber 3★ 触发虚拟定型换人 → 前排 3 费杂件
    被撤下为部署外),撤下件(Lv5 概率 0.2 > 0)键大于零成本候选
    (概率恒 0)→ 撤下件垫末位、候选幸存照选。旧「只扫 bench」分叉
    形态下池 = bench 5 费件(概率 0 同档、-cost < 0)全小于候选 →
    候选末位被淘汰——本帧断言幸存即钉住 field 件入池。"""
    fillers5 = _clean_cost_fillers(7, 5, {'娜塔莎'})
    bench = [('Saber', 3)] + [(n, 1) for n in fillers5]
    front = ('吉尔伽美什', '刻律德菈', '镜流', '姬子·启行')
    gs = _make_gs(bench=bench, front=front, level=5, locked='双王圣杯')
    # 帧前提:前排存在被虚拟定型撤下的件(部署外形态在场)。
    _frame, _sim, target = _virtual_target(gs, '娜塔莎')
    assert any(n not in target for n in front), \
        f'帧前提失守:前排无撤下件(部署外形态缺席): {sorted(target)}'
    opts = [_opt(0, char='娜塔莎', equip=''),
            _opt(1, equip='轮滑鞋')]
    out = supply.decide(opts, gs, None, False)
    assert isinstance(out, SupplyDecision)
    assert out.idx == 0, '撤下件垫末位 → 候选幸存照选(field 件入池)'
    assert '键首档=8' in out.reason, \
        f'杂件候选按卡面落档 8:{out.reason!r}'


def test_supply_and_shop_paths_agree_on_same_virtual_board():
    """两域同一排序序(30 号篇 §2.1 统一装配的行为断言):同一虚拟
    局面 + 同一候选牌三件套下,补给路径(supply._rank_char_candidates
    全链)产出的候选排序键与商店消费形态(assemble_candidate_eval +
    sell_order_with_keys)产出的键逐分量一致(去随机尾键——尾键每次
    现抽,非行为语义)。补给侧若绕开统一装配另写第二份(如池只扫
    bench / 不减候选名),同帧两键分叉 → 红。"""
    fillers5 = _clean_cost_fillers(7, 5, {'娜塔莎'})
    bench = [('Saber', 3)] + [(n, 1) for n in fillers5]
    gs = _make_gs(bench=bench,
                  front=('吉尔伽美什', '刻律德菈', '镜流', '姬子·启行'),
                  level=5, locked='双王圣杯')
    opts = [_opt(0, char='娜塔莎', equip='')]
    ranked = supply._rank_char_candidates(opts, gs)
    assert ranked, '帧前提失守:候选被淘汰,无键可比(换幸存帧)'
    sup_key = ranked[0][1][:-1]
    frame, sim, target = _virtual_target(gs, '娜塔莎')
    ctx, units = assemble_candidate_eval(
        gs, gs, sim=sim, base_bench_len=len(frame.bench), target=target,
        name='娜塔莎', star=1, cost=0)
    keyed = sell_order_with_keys(units, ctx)
    shop_key = next(k[:-1] for u, k in keyed if isinstance(u, ShopUnit))
    assert sup_key == shop_key, \
        f'两域键分叉:supply={sup_key} shop={shop_key}'
