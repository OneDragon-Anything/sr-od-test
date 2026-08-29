"""W50 口径统一批锁测(ADR-0312;W49 裁决三项 + W47 条2)。

锁四件事:
1. **羁绊口径单一源** ``cw_bond_equips.unit_bond_tags``:L1 全集
   (factions+flows+independent,开拓者按排归一)+ L2 星徽装备羁绊贡献
   (星徽「加入【X】」/欢愉卡带「已是成员计数+1」净效果=无条件 +1/
   星核猎手卡带「计数+1」);
2. **三侧同函数**:board_from_tracked(实机)/_recount_board(= sim
   _board_counts_of,状态派生)/_board_agg_of_deployed_row(checks 镜像)
   全部经 unit_bond_tags——构造同一 deployed,三处结果逐键相等;
3. **Δ池桶键**:_deployable_depth = Σboard(全集口径,与池语料同口径;
   v11/ADR-0407 后辖 reward/supply——boss 桶键已改净星深
   deployed_star_depth(W240/ADR-0404),encounter 桶键已改 rung
   _settle_rung,见 test_cw_w238_boss_hp_projection);
4. **W47 条2**:W16_MAJORITY_LINES 补全 + CROSS_LINE_SKELETON 派生 ==
   原 10 名快照(不等 = 数据错)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_bond_equips import (
    equip_bond_grants,
    unit_bond_tags,
)
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_intention import CROSS_LINE_SKELETON
from sr_od.application.currency_war.cw_observation import board_from_tracked
from sr_od.application.currency_war.cw_plugins import (
    PLUGIN_LIBRARY,
    W16_MAJORITY_LINES,
    cross_line_skeleton,
)
from sr_od.application.currency_war.cw_sim import _deployable_depth
from sr_od.application.currency_war.cw_state import BenchChar, GameState, _recount_board


def _char(name: str, slot: int = 0, row: str = 'back',
          equips: list[str] | None = None) -> BenchChar:
    c = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row, equips=list(equips or []))


# ---------- 1. 装备羁绊贡献解析 ----------

def test_equip_bond_grants_registry_derived() -> None:
    """星徽/卡带贡献从注册表 effect 派生;普通装备零贡献。"""
    assert equip_bond_grants('列车同行星徽') == ('列车同行',)
    assert equip_bond_grants('仙舟星徽') == ('仙舟',)
    assert equip_bond_grants('欢愉星徽') == ('欢愉',)
    # 卡带系(骇客):欢愉卡带加入+成员计数+1;星核猎手卡带纯计数+1
    assert equip_bond_grants('欢愉卡带') == ('欢愉',)
    assert equip_bond_grants('欢愉卡带Max') == ('欢愉',)
    assert equip_bond_grants('星核猎手卡带') == ('星核猎手',)
    assert equip_bond_grants('星核猎手卡带Max') == ('星核猎手',)
    # 非羁绊装备
    assert equip_bond_grants('轮滑鞋') == ()
    assert equip_bond_grants('火力风暴潮') == ()
    assert equip_bond_grants('不存在装备') == ()


def test_equip_bond_grants_cover_all_badges() -> None:
    """22 张星徽全解析成功(注册表 category='星徽' 逐张非空)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
    badges = [e for e in EQUIPMENTS.values() if e.category == '星徽']
    assert len(badges) == 22
    for e in badges:
        assert equip_bond_grants(e.name), f'星徽 {e.name} 未解析出羁绊贡献'


# ---------- 2. unit_bond_tags(L1 全集 + L2 星徽)----------

def test_unit_bond_tags_fullset() -> None:
    """L1 全集:factions+flows+independent 都进标签(多羁绊每系都计)。"""
    # 布洛妮娅:factions 空 + flows 燃血 + independent 大守护者
    assert unit_bond_tags(_char('布洛妮娅')) == ('燃血', '大守护者')
    # 白厄:仅独立羁绊救世主(复制效果不计人数,官方 trait 3005)
    assert unit_bond_tags(_char('白厄')) == ('救世主',)
    # 银狼LV.999:阵营+流派+独立三层
    assert unit_bond_tags(_char('银狼LV.999')) == ('星核猎手', '欢愉', '头号玩家')


def test_unit_bond_tags_unknown_and_trailblazer() -> None:
    """身份未知 → 空元组;开拓者按排归一(前排=记忆/后排=欢愉)。"""
    assert unit_bond_tags(BenchChar(slot=1, char_id='')) == ()
    assert unit_bond_tags(BenchChar(slot=1, char_id='?')) == ()
    assert unit_bond_tags(BenchChar(slot=1, char_id='不存在角色')) == ()
    assert unit_bond_tags(BenchChar(slot=1, char_id='', faction='量子同频')) == ()
    tb_names = [n for n in CHARACTERS
                if n.startswith('开拓者') and n != '开拓者·欢愉']
    assert tb_names   # 注册表有开拓者形态
    # 形态归一按 position_pref(欢愉形态 flows 欢愉;记忆形态另计)
    back = unit_bond_tags(_char('开拓者·欢愉', row='back'))
    front = unit_bond_tags(_char('开拓者·欢愉', row='front'))
    assert back and front and back != front


def test_unit_bond_tags_equip_grants() -> None:
    """L2 装备贡献:**星徽=额外增加一个羁绊(add-if-absent,成员穿不重复)**;
    卡带=计数+1(可双计)。用户口述 2026-08-28 分流语义。"""
    # 姬子·启行(列车+领航员)+ 列车同行星徽 → 列车计数 1(已是成员,星徽不重复)
    tags = unit_bond_tags(_char('姬子·启行', equips=['列车同行星徽']))
    assert tags.count('列车同行') == 1
    assert tags.count('领航员') == 1
    # 非成员 + 星徽 → 变成员(+1)
    tags_nonmember = unit_bond_tags(_char('佩拉', equips=['列车同行星徽']))
    assert tags_nonmember.count('列车同行') == 1
    # 银狼LV.999(欢愉 flow 成员)+ 欢愉卡带 → 欢愉 2(卡带可双计)
    tags2 = unit_bond_tags(_char('银狼LV.999', equips=['欢愉卡带']))
    assert tags2.count('欢愉') == 2
    # 非成员佩戴欢愉卡带:加入即 +1(欢愉 1)
    tags3 = unit_bond_tags(_char('符玄', equips=['欢愉卡带']))
    assert tags3.count('欢愉') == 1
    # 组合「卡带X+星徽X」(非成员):卡带授 X 后即「已有」,星徽 X 不再重复 → 仍 1
    tags_combo = unit_bond_tags(_char('符玄', equips=['欢愉卡带', '欢愉星徽']))
    assert tags_combo.count('欢愉') == 1
    # 反序(星徽在前)同判:计数与穿戴顺序无关(P19 幂等性)
    tags_combo_rev = unit_bond_tags(_char('符玄', equips=['欢愉星徽', '欢愉卡带']))
    assert tags_combo_rev.count('欢愉') == 1
    # 卡带自身可双计不受影响:成员两件欢愉系卡带 → 欢愉 3(自报 1 + 卡带 2)
    tags_tape2 = unit_bond_tags(_char('银狼LV.999', equips=['欢愉卡带', '欢愉卡带Max']))
    assert tags_tape2.count('欢愉') == 3
    # 符玄(仙舟自报)+ 仙舟星徽:成员穿同羁绊星徽不重复(仍 1);不影响自报标签
    tags4 = unit_bond_tags(_char('符玄', equips=['仙舟星徽']))
    assert tags4.count('仙舟') == 1
    # 星核猎手卡带:无条件 +1
    assert unit_bond_tags(
        _char('姬子·启行', equips=['星核猎手卡带'])).count('星核猎手') == 1


# ---------- 3. 三侧同函数(实机/派生/检查)----------

def _three_sides_agree(dep: list[BenchChar]) -> None:
    from sr_od.application.currency_war.cw_sim_checks import (
        _board_agg_of_deployed_row,
    )
    row = {'state': {'deployed': [
        {'char_id': d.char_id, 'faction': d.faction, 'slot': d.slot,
         'position_pref': d.position_pref, 'equips': list(d.equips)}
        for d in dep]}}
    assert _recount_board(dep) == board_from_tracked(dep) \
        == _board_agg_of_deployed_row(row)


def test_three_sides_same_function_fullset_with_equips() -> None:
    """实机 board_from_tracked / _recount_board / checks 镜像三处一致
    (同一 deployed——含星徽/卡带/独立羁绊/flows 构造)。"""
    dep = [
        _char('银狼LV.999', slot=1, equips=['欢愉卡带']),
        _char('姬子·启行', slot=2, equips=['列车同行星徽']),
        _char('布洛妮娅', slot=3),
        _char('白厄', slot=4),
        _char('符玄', slot=5, equips=['仙舟星徽']),
    ]
    _three_sides_agree(dep)
    b = _recount_board(dep)
    assert b['欢愉'] == 2          # 银狼999 flow 1 + 卡带 1(卡带可双计)
    assert b['列车同行'] == 1      # 姬子启行自报 1;成员穿星徽不重复
    assert b['仙舟'] == 1          # 符玄自报 1;成员穿星徽不重复
    assert b['救世主'] == 1        # 白厄独立羁绊
    assert b['燃血'] == 1 and b['大守护者'] == 1


def test_recount_unknown_fallback_and_deploymove_recount() -> None:
    """未识别身份回退 faction 单标签(空/'?' 不计);DeployMove 后
    board 走 _recount_board(不再 faction+=1 单标签)。"""
    dep = [_char('希儿', slot=1), BenchChar(slot=2, char_id='', faction='量子同频'),
           BenchChar(slot=3, char_id='', faction='?')]
    b = _recount_board(dep)
    assert b['量子同频'] >= 2      # 希儿全集 + 未识别兜底;? 不计
    from sr_od.application.currency_war.cw_state import (
        DeployMove,
        simulate,
    )
    st = GameState()
    st.bench = [_char('布洛妮娅')]
    st.deployed = []
    out = simulate(st, DeployMove(bench_idx=0, to_row='front', faction='燃血'))
    assert out.deployed[0].char_id == '布洛妮娅'
    assert out.board == {'燃血': 1, '大守护者': 1}   # 全集,非 {'燃血': 1}


def test_board_counts_of_is_recount_single_source() -> None:
    """cw_sim._board_counts_of = _recount_board(全集单一源,alias 语义)。"""
    from sr_od.application.currency_war.cw_sim import _board_counts_of
    dep = [_char('银狼LV.999', equips=['欢愉卡带'])]
    assert _board_counts_of(dep) == _recount_board(dep)


# ---------- 4. Δ池桶键:Σboard 全集口径 ----------

def test_deployable_depth_is_sum_board() -> None:
    """_deployable_depth = Σboard(池语料同口径;双标签角色贡献 ≥2)。"""
    st = GameState()
    st.level = 4
    st.deployed = [_char('银狼LV.999', slot=1), _char('符玄', slot=2)]
    st.board = _recount_board(st.deployed)
    assert _deployable_depth(st) == sum(st.board.values())
    assert _deployable_depth(st) >= len(st.deployed)   # 双标签放大
    st2 = GameState()
    st2.board = {}
    assert _deployable_depth(st2) == 0


# ---------- 5. W47 条2:W16 过半统计 + CROSS_LINE_SKELETON 派生 ----------

def test_w16_majority_lines_values() -> None:
    """W16 统计表值锁(数据搬运自 W16 报告 A2;家族键 ⊆ V2_FAMILIES)。"""
    from sr_od.application.currency_war.cw_comps import V2_FAMILIES
    for name, fams in W16_MAJORITY_LINES.items():
        assert fams and fams <= set(V2_FAMILIES), f'{name} 域外家族'
    assert W16_MAJORITY_LINES['瓦尔特'] == frozenset(
        {'姬子列车', '黄泉减益', 'DOT卡芙卡', '欢愉族', '希儿量子', '圣杯双C'})
    assert W16_MAJORITY_LINES['千冶·刃'] == frozenset(
        {'万敌燃血', '黄泉减益', 'DOT卡芙卡', '白厄反甲', '希儿量子',
         '姬子列车', '欢愉族', '圣杯双C'})
    assert W16_MAJORITY_LINES['缇宝'] == frozenset(
        {'大黑塔群攻', '万敌燃血', '希儿量子', '黄泉减益'})


def test_cross_line_skeleton_derived_matches_original_10() -> None:
    """派生名单 == 原 10 名快照(手写名单废弃;不等 = W16 数据错)。"""
    original = {
        '瓦尔特', '千冶·刃', '符玄', '星期日', '开拓者·记忆',
        '花火', '缇宝', '刻律德菈', '三月七', '藿藿',
    }
    assert set(cross_line_skeleton()) == original
    assert set(CROSS_LINE_SKELETON) == original
    # 排除项:姬子·启行(2 家族但= 姬子线 carry)、开拓者·欢愉(两线同族 1 键)
    assert '姬子·启行' not in CROSS_LINE_SKELETON
    assert '开拓者·欢愉' not in CROSS_LINE_SKELETON


def test_plugin_majority_lines_synced_with_w16() -> None:
    """插件库单卡条目 majority_lines 与 W16 表程序同步(单一写入口)。"""
    for name, fams in W16_MAJORITY_LINES.items():
        entry = PLUGIN_LIBRARY.get(name)
        if entry is not None:   # 千冶·刃/开拓者·记忆等骨架件不在插件池
            assert entry.majority_lines == fams, name
    # 原部分标注(瓦尔特只 {姬子列车})已被 W16 全集覆盖
    assert PLUGIN_LIBRARY['瓦尔特'].majority_lines == \
        W16_MAJORITY_LINES['瓦尔特']
    # 小羁绊条目不受同步(三C 手注口径)
    from sr_od.application.currency_war.cw_plugins import (
        PLUGIN_DISABLE_MATRIX,
    )
    assert ('护盾2', '万敌燃血') in PLUGIN_DISABLE_MATRIX
