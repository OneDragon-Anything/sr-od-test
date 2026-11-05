"""统一部署搜索(评分制)单测(镜像 src = strategies/impl/mandate_v1/
deploy_search.py;设计单一源 = changes/2026-10-30-roster-plane1-union/
details/unified-deploy-order.md §1 评分函数/§2 三段搜索——场景走查表
可纯面板构造的行 + 评分层结构锚)。

名字表达纪律:测试想要某羁绊/偏好 = 挑注册表真实角色名。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    deploy_search as ds,
)


def _u(name: str, star: int = 1, origin: str = 'bench',
       row: str = '') -> ds.SearchUnit:
    return ds.SearchUnit(key=name, char_id=name, star=star, origin=origin,
                         row=row, uid=None)


def _panel(units, *, locked=False, locked_comp=None, candidate_comps=(),
           transition_comps=(), k=10, back=6,
           current_board=None) -> ds.DeploySearchPanel:
    return ds.DeploySearchPanel(
        units=tuple(units), k_budget=k, front_capacity=4,
        back_capacity=back, locked=locked, locked_comp=locked_comp,
        candidate_comps=candidate_comps,
        transition_comps=tuple(transition_comps),
        current_board=dict(current_board or {}))


def test_p1_early_scatter_board_fills_l3() -> None:
    """P1 早期全散牌(K=4):空骨架合法 → L3 定序摆最强散件,尽量
    填满(场景走查第 1 行)。"""
    units = [_u('青雀'), _u('艾丝妲'), _u('娜塔莎'), _u('佩拉'),
             _u('彦卿')]
    out = ds.search_deploy_target(_panel(units, k=4))
    assert len(out) == 4, '散牌期尽量填满 K'


def test_p1_system_skeleton_beats_scatter() -> None:
    """未终局锁定的过渡条目骨架成型 > 全散件板:仙舟3+DOT2 条目在场,
    候选含条目骨架板(仙舟档 L1),L1 压倒 L3 散件——最优板至少 3 仙舟
    (一档成型;第 4 席留 L3 竞争,断言不写死哪件)。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        transition_entry_of,
    )
    scatter = [_u('娜塔莎'), _u('佩拉'), _u('布洛妮娅')]
    xianzhou = [_u('青雀'), _u('停云'), _u('藿藿'), _u('彦卿')]
    out_xz = ds.search_deploy_target(
        _panel([*xianzhou, *scatter], k=4,
               transition_comps=(transition_entry_of('仙舟3+DOT2'),)))
    assert len({'青雀', '停云', '藿藿', '彦卿'} & set(out_xz)) >= 3, \
        f'体系件凑档(≥3 仙舟)优先于散件,实际 {sorted(out_xz)}'
    # 对照:无体系件时散件板照常。
    out_sc = ds.search_deploy_target(_panel(scatter, k=3))
    assert len(out_sc) == 3


# (test_lock_keep_phase_transition_x4_beats_buff 已随换轴删除:终局锁定窗
#  过渡家族骨架枚举与 L3 过渡 ×4 保板相位系数均随「终局锁定即过渡层
#  退役」删除——P1 锁定窗在现行终局锁定时点下不可达,保板相位行为
#  消亡;comp-structure-unification 3.3。)


def test_lock_first_tier_flip_displaces_transition() -> None:
    """换防跳变(锁定线第一档成型 → L1 压倒 + 过渡回落 ×1,场景走查
    第 2 行后半):列车 4 人在手,锁定线一档成型压倒过渡板。"""
    comp = get_comp('列车同行·反震')
    # 列车 4 人(锁定线档 0=4)vs 过渡仙舟 3 人 + 减益件;K=4。
    units = [_u('姬子·启行'), _u('丹恒·饮月'), _u('三月七'), _u('星期日'),
             _u('青雀'), _u('停云'), _u('藿藿')]
    panel = _panel(units, locked=True, locked_comp=comp, k=4)
    out = ds.search_deploy_target(panel)
    assert {'姬子·启行', '丹恒·饮月', '三月七', '星期日'} <= set(out), \
        '锁定线一档成型(L1 ≥ 10⁷)压倒过渡加分'


def test_or_group_takes_best_branch() -> None:
    """OR 承接组取最优支(or_reqs = 量子 2 ∨ 贝 2):贝洛伯格支先达
    (2 人)时按最优支计完成度,量子支半程不稀释。载体 = 手构 Comp
    (旧过渡条目「希儿引擎」已随 or-reqs-retirement 3.2 组合制退役,
    OR 折法语义仍在库外独立成立,机器删除归 3.3)。"""
    from sr_od.application.currency_war.kernel.cw_comps import Comp
    comp = Comp(
        name='手构OR条目',
        core_chars=['希儿'],
        faction_reqs={0: {'量子同频': 2, '贝洛伯格': 2}},
        or_reqs=[('量子同频', 2), ('贝洛伯格', 2)],
        need_star={'希儿': 3},
    )
    units = [_u('希儿'), _u('佩拉'), _u('杰帕德'),   # 贝 2 人支
             _u('青雀'), _u('停云')]                 # 无关件
    panel = _panel(units, locked=True, locked_comp=comp, k=4)
    out = ds.search_deploy_target(panel)
    assert {'希儿', '佩拉', '杰帕德'} <= set(out), 'OR 组最优支(贝 2)入选'


def test_dp_fill_captures_multi_group_tier_mix() -> None:
    """段 2 分组背包 DP 的跨组增益捕获(unified-deploy-order §2 段 2
    设计基线;贪心近似的覆盖缺口反例):锁定命运圣杯线(线内件不在手 →
    空骨架),K=4,手牌 = 持续伤害 2(卡芙卡/黑天鹅,首标签持续伤害,
    档 1 需 2 人)+ 列车同行 2(三月七/姬子·启行,首标签列车同行,
    档 1 需 2 人)+ 零值扰动件(停云,首标签仙舟,档 1 需 3 人独件
    不可达;名字序最早)。

    贪心全局序按名字取前 4(三月七/停云/卡芙卡/姬子)→ 挤掉黑天鹅 →
    持续伤害组不成档(L3 = 1 档);单组变体只保一组(各 1 档)。DP
    联合分配取「持续伤害 2 + 列车 2」→ 双组成档(L3 = 2 档)——
    段 3 全量终评按实测 L3 选 DP 板(锁定窗保板相位两组同为过渡
    系 ×4,同 L1=0 同 L2 无 sub,跨组增量即决胜差)。"""
    comp = get_comp('命运圣杯红A')
    units = [_u('卡芙卡'), _u('黑天鹅'),      # 持续伤害组(档 1 = 2 人)
             _u('三月七'), _u('姬子·启行'),  # 列车同行组(档 1 = 2 人)
             _u('停云')]                     # 仙舟组独件(零值扰动)
    panel = _panel(units, locked=True, locked_comp=comp, k=4)
    out = ds.search_deploy_target(panel)
    assert set(out) == {'卡芙卡', '黑天鹅', '三月七', '姬子·启行'}, \
        f'DP 联合分配捕获双组凑档(扰动件出局),实际 {sorted(out)}'


def test_required_deployed_missing_zeroes_l1() -> None:
    """required 逐名折条(希儿不在场 → 希儿量子线 L1 = 0):无希儿的
    量子板不成型,过渡/散件板竞争胜出。"""
    comp = get_comp('希儿量子')
    with_seele = [_u('希儿'), _u('花火'), _u('符玄'), _u('缇宝')]
    out_with = ds.selection_score(
        _panel(with_seele, locked=True, locked_comp=comp),
        with_seele, comp, ('量子同频', '贝洛伯格'))
    # required 折条:3 量子成员在场但无希儿 → L1 = 0。
    l1_none = ds.selection_score(
        _panel([_u('花火'), _u('符玄'), _u('缇宝')], locked=True,
               locked_comp=comp),
        [_u('花火'), _u('符玄'), _u('缇宝')], comp,
        ('量子同频', '贝洛伯格'))[0]
    assert l1_none == 0.0, '希儿不在场 → 该线 L1 = 0'
    assert out_with[0] > 0.0


def test_seele_binary_needs_two_amplifiers() -> None:
    """希儿系二元计分(对齐现役 seele_system_formed:希儿在场 ∧ 面板
    放大器阵营计数 ≥2——希儿本人亦量子/贝成员计入面板口径):计数
    不足不成型,补齐第二件成型。"""
    one_amp = [_u('希儿'), _u('青雀'), _u('彦卿')]    # 量子 1 / 贝 1(均希儿)
    two_amp = [_u('希儿'), _u('花火'), _u('青雀')]    # 量子 2(希儿+花火)
    panel = _panel([])
    s1 = ds.selection_score(panel, one_amp, None, ('希儿系',))
    s2 = ds.selection_score(panel, two_amp, None, ('希儿系',))
    assert s1[0] == 0.0, '面板放大器计数 1:未成型'
    assert s2[0] > 0.0, '面板放大器计数 2:成型'


def test_same_name_highest_star_wins() -> None:
    """同键多副本取最高星(唯一性键不变量;枚举选定的最高星副本
    进 target,§2 段 0)。"""
    units = [_u('青雀', star=1, origin='board', row='front'),
             _u('青雀', star=2, origin='bench'),
             _u('停云'), _u('藿藿')]
    out = ds.search_deploy_target(_panel(units, k=4))
    assert out.get('青雀') == ('front', 2, None), '最高星副本承载目标'


def test_silverwolf_lands_as_1star() -> None:
    """银狼落场后形态(§1 D-6):3★ 上场即变下档 1★——枚举单位的
    target 星 = 落场后形态(评分板面 ≡ 执行后板面,场景走查「银狼
    3★ 上场」行)。"""
    # build_deploy_panel 的落场后形态折算;纯面板验证 = 同名取最高星
    # 的落场后语义由装配侧承载,此处锁 selection 层星维透传。
    units = [_u('青雀'), _u('停云'), _u('藿藿', star=2)]
    out = ds.search_deploy_target(_panel(units, k=4))
    assert out.get('藿藿', ('', 0))[1] == 2, '选定星维透传(落场后形态)'


def test_l2_bonus_keys_only() -> None:
    """L2 键集 = 仅加分层(bonus_faction_reqs,D3-1):锁定线列车同行·反震
    档 1 = 护盾(批 3 拆分各归其一,A=护盾2),加分层件凑档的 L2(10⁶)随凑档
    上升;flex_factions 不进 L2(注册表「板面不罚但完成度不数」)。"""
    comp = get_comp('列车同行·反震')
    sub_on = [_u('姬子·启行'), _u('三月七'), _u('杰帕德')]   # 护盾 2 人(三月七+杰帕德,flows=护盾)
    sub_off = [_u('姬子·启行'), _u('青雀'), _u('停云')]
    panel = _panel([], locked=True, locked_comp=comp)
    l2_on = ds.selection_score(panel, sub_on, comp, ('列车同行·反震',))[1]
    l2_off = ds.selection_score(panel, sub_off, comp, ('列车同行·反震',))[1]
    assert l2_on > 0.0 > l2_off or l2_on > l2_off, \
        f'加分层凑档 L2({l2_on}) > 无加分层件({l2_off})'


def test_empty_bond_line_core_shared_denominator() -> None:
    """空羁绊线(反甲白厄档 0 空 ∧ factions=[]):L1 由角色
    完成度单独承载,分母 = core∪shared 总数(D2-3)。"""
    comp = get_comp('反甲白厄')
    members = set(comp.core_chars) | set(comp.shared_chars or ())
    two = [_u(n) for n in list(members)[:2]]
    panel = _panel([], locked=True, locked_comp=comp)
    l1 = ds.selection_score(panel, two, comp, ())[0]
    expect = (2 / len(members)) * ds._L1_SCALE
    assert abs(l1 - expect) < 1.0, f'{l1} ≈ {expect}(core∪shared 口径)'


def test_rng_situation_seed_same_input_same_target() -> None:
    """rng 局面哈希播种(§1 D3-7):同一容器状态 → 同一 target(跨帧
    稳定,防并列板帧间翻转)。"""
    units = [_u('青雀'), _u('停云'), _u('藿藿'), _u('艾丝妲')]
    panel = _panel(units, k=3)
    assert ds.search_deploy_target(panel) == ds.search_deploy_target(panel)


def test_front_capacity_and_row_assign() -> None:
    """排分配:前排保证(出战硬要求前排有角色)与排容量约束。"""
    units = [_u('青雀'), _u('停云'), _u('藿藿'), _u('符玄'),
             _u('彦卿'), _u('忘归人')]
    out = ds.search_deploy_target(_panel(units, k=6))
    rows = [r for _n, (r, _s, _slot) in out.items()]
    assert 'front' in rows, '前排保证:至少一名前排'


def test_stable_key_prefers_current_board() -> None:
    """稳定键 = 与现板面一致数(结构化滞回,§1:站位分之后的同分
    偏好;星维不进)。直接锚 _position_score 的计数语义 + 站位分
    同分时现板一致数参与定序。"""
    units = [_u('青雀'), _u('停云'), _u('藿藿'), _u('彦卿')]
    board = {'青雀': 'front', '停云': 'front', '藿藿': 'back'}
    pos, stable = ds._position_score(
        units, {'青雀': 'front', '停云': 'front', '藿藿': 'back',
                '彦卿': 'back'}, None, board)
    assert stable == 3, '现板一致数(名+排粒度)'
    pos2, stable2 = ds._position_score(
        units, {'青雀': 'back', '停云': 'back', '藿藿': 'front',
                '彦卿': 'front'}, None, board)
    assert stable2 == 0, '不一致板 = 0'


def test_bronya_side_pick_single_edge() -> None:
    """选边双羁绊(布洛妮娅)计数单边化:peers 对象上下文经
    unit_bond_tags 统一消费(单一源),板上标签不双边重复。"""
    units = [_u('布洛妮娅'), _u('佩拉'), _u('杰帕德'), _u('桑博')]
    counts = ds._tag_counts(units)
    # 布洛妮娅选边(贝 3 基数 > 燃血 0 → 贝)后只出单侧标签。
    assert counts.get('贝洛伯格', 0) == 4 and counts.get('燃血', 0) == 0, \
        f'选边后单边(贝 4 / 燃血 0),实际 {counts}'


# ==================== 次名分量收集出参(pick-margin-telemetry
# ====================  design §2.1/§2.2-3;纯观测,搜索行为零变)====================

def test_margin_out_layered_form_and_no_challenger() -> None:
    """段 3 收集分层记法(design §2.2-3):键形 = {runner_up(挑战者
    板签名 = 排序名列表), first_diff_layer(首异层 1-3), layer_gap};
    胜者 = 锁定线一档成型板(既有场景),挑战者(成员集与胜者不同的
    最高板)首异层 = 1(L1 层隔离的结构性质,gap > 0 不锁具体值);
    dedup 后仅一可行板 → 三键 null(与尾键决胜 0/0 区分)。"""
    comp = get_comp('列车同行·反震')
    units = [_u('姬子·启行'), _u('丹恒·饮月'), _u('三月七'), _u('星期日'),
             _u('青雀'), _u('停云'), _u('藿藿')]
    margin: dict = {}
    out = ds.search_deploy_target(
        _panel(units, locked=True, locked_comp=comp, k=4),
        margin_out=margin)
    assert out, '前置:搜索成功定型'
    assert set(margin) == {'runner_up', 'first_diff_layer', 'layer_gap'}
    assert margin['runner_up'] == sorted(margin['runner_up']), \
        '板签名 = 排序名列表'
    assert margin['runner_up'] != sorted(out), \
        '挑战者成员集与胜者不同'
    assert margin['first_diff_layer'] == 1, \
        f'锁定线一档成型 vs 替补板首异层 = L1,实际 {margin}'
    assert margin['layer_gap'] > 0
    # 无挑战者:单单位面板(dedup 后仅一可行板)→ 三键 null 形态。
    m_single: dict = {}
    ds.search_deploy_target(_panel([_u('青雀')], k=4), margin_out=m_single)
    assert m_single == {'runner_up': None, 'first_diff_layer': None,
                        'layer_gap': None}


def test_margin_out_all_layers_tie_decided_by_tail_key() -> None:
    """三层全同尾键决胜形态(design §2.2-3 边界值表):K=1 两张互无
    羁绊的散件,两板 L1/L2/L3 全同 → first_diff_layer = 0, layer_gap
    = 0(pos/stable/rng 尾键决胜,与无挑战者 null 形态区分)。"""
    margin: dict = {}
    out = ds.search_deploy_target(_panel([_u('佩拉'), _u('娜塔莎')], k=1),
                                  margin_out=margin)
    assert len(out) == 1, '前置:K=1 单件定型'
    assert margin == {'runner_up': ['佩拉'], 'first_diff_layer': 0,
                      'layer_gap': 0}, \
        f'三层全同 → 首异层 0/层差 0,实际 {margin}'


def test_margin_out_not_written_when_search_returns_empty() -> None:
    """搜索返 {}(候选全不可排防御路径,§2 接口契约)→ 不落键:
    margin_out 保持空(零容量面板 = 结构不可达形态)。"""
    panel = ds.DeploySearchPanel(
        units=(_u('青雀'), _u('艾丝妲')), k_budget=4, front_capacity=0,
        back_capacity=0, locked=False, locked_comp=None,
        candidate_comps=(), transition_comps=(), current_board={})
    margin: dict = {}
    out = ds.search_deploy_target(panel, margin_out=margin)
    assert out == {}, '前置:容量矛盾 → 搜索返空 dict'
    assert margin == {}, '搜索返 {} 不落键(design §2.2-3 边界值表)'


def test_margin_out_default_none_no_collect_same_target() -> None:
    """缺省不收集(虚拟定型调用点形态,design §2.1):不传 margin_out
    照常返回、与传入收集时同 target(收集面零行为变化;虚拟 4 调用
    点不传即零写入由缺省 None 的结构性质承载)。"""
    units = [_u('青雀'), _u('停云'), _u('藿藿'), _u('彦卿'), _u('艾丝妲')]
    panel = _panel(units, k=4)
    plain = ds.search_deploy_target(panel)
    with_margin: dict = {}
    collected = ds.search_deploy_target(panel, margin_out=with_margin)
    assert plain == collected, '收集开关不改定型结果(纯观测)'
    assert with_margin, '前置:该板面应有挑战者分量'
