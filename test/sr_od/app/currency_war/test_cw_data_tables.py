"""CW data 域·静态数据表四种合同(先删后重建轮;规范 = CW_TEST_SPEC.md §4)。

静态数据表按「文件 × 合同」配测试,禁止逐条目铺(72 角色/98 装备逐条断言 =
快照陷阱:改数据必红且无可登记语义)。四种合同:
1. 引用完整性:外键全在注册表(错位=匹配永不命中,历史病灶防复发);
2. 值域守恒:概率和/非增单调/id 唯一/值域;
3. 派生一致性:import 时派生的常量与从单一源重算对照(防派生被改手抄);
4. 登记门:覆盖完整性断言,红时知道该登记什么(README 第 7 条登记门形态)。
自 data_registry 解体收编:registry_complete/plaza_snapshot/recipe×2。
"""
import pytest
from sr_od.application.currency_war.data import cw_synthesis as synth
from sr_od.application.currency_war.data.cw_battle_tables import (
    NODE_WIN_P_BY_TYPE,
    NODE_WIN_P_LADDER,
)
from sr_od.application.currency_war.data.cw_chars import (
    CHARACTERS,
    chars_by_cost,
)
from sr_od.application.currency_war.data.cw_enemy_data import (
    BOSS_MECHANICS,
    BOSS_NICKNAMES,
)
from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENTS,
    EQUIPMENT_ROSTER,
)
from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.data.cw_invest_data import (
    PLAZA_AUGMENTS,
    PLAZA_PORTALS,
)
from sr_od.application.currency_war.data.cw_shop_odds import (
    DISTINCT_CARDS_PER_COST,
    POOL_COPIES_PER_CARD,
    REFRESH_PROB,
)


# ===== 合同一:引用完整性(外键全在注册表) =====

class TestReferenceIntegrity:
    """跨表外键:错位 = 下游匹配永不命中(enemy_data task#73 病灶防复发)。"""

    def test_char_factions_in_faction_registry(self):
        # 角色阵营标签必须都能在阵营注册表对上(form_or/board 计数按名匹配)
        bad = {c: ch.factions for c, ch in CHARACTERS.items()
               for f in ch.factions if f not in FACTIONS}
        assert bad == {}, f'阵营外键缺失: {bad}'

    def test_boss_nickname_targets_in_mechanics(self):
        # 名字空间对齐:俗称映射的目标必须是规范公司名——错位=briefing 读数
        # 清洗结果永远匹配不上 boss_fit(「剧目」vs「造梦兄弟影业」病灶,task#73)
        miss = {k: v for k, v in BOSS_NICKNAMES.items() if v not in BOSS_MECHANICS}
        assert miss == {}, f'俗称目标不在规范名注册表: {miss}'

    def test_all_recipe_names_in_roster(self):
        # 迁自 data_registry:合成结果名(交叉+自配+光能系)都在装备注册表
        names = (set(synth.CROSS_RECIPES) | set(synth.SELF_RECIPES)
                 | set(synth.GUANGNENG_CROSS_RECIPES)
                 | set(synth.GUANGNENG_SELF_RECIPES))
        miss = [n for n in names if n not in EQUIPMENT_ROSTER]
        assert miss == [], f'注册表缺: {miss}'

    def test_synthesis_bases_in_roster(self):
        assert all(b in EQUIPMENT_ROSTER for b in synth.SYNTHESIS_BASES)


# ===== 合同二:值域守恒(概率/单调/唯一) =====

class TestValueDomain:
    """数值表的内蕴约束:违反 = 识别错或数据缺口的第一道防线。"""

    def test_refresh_prob_rows_sum_to_one(self):
        # 每等级行概率和=100%(V4.4 权威表,游戏内 OCR 实机采集;D-91)
        sums = {lv: sum(row.values()) for lv, row in REFRESH_PROB.items()}
        for lv, s in sums.items():
            assert s == pytest.approx(1.0, abs=1e-9), f'Lv{lv} 概率和 {s}'

    def test_refresh_prob_keys_in_domain(self):
        # levels 1-10 全登记;行键 ⊆ 费用档 1-5 且必含 1 费(低级 1 费主导)
        assert set(REFRESH_PROB) == set(range(1, 11))
        for lv, row in REFRESH_PROB.items():
            assert set(row) <= set(range(1, 6)), f'Lv{lv} 费用档越域: {set(row)}'
            assert 1 in row, f'Lv{lv} 缺 1 费档'
            assert all(0 < v <= 1 for v in row.values()), f'Lv{lv} 概率值越域'

    def test_pool_copies_non_increasing_with_cost(self):
        # 池副本上限:费用越高副本越少(27,27,9,9,9 非增)
        caps = [POOL_COPIES_PER_CARD[c] for c in sorted(POOL_COPIES_PER_CARD)]
        assert caps == sorted(caps, reverse=True)

    def test_win_probability_in_domain(self):
        for key, p in NODE_WIN_P_LADDER.items():
            assert 0 < p <= 1, f'{key} 胜率 {p} 越域'
        for t, p in NODE_WIN_P_BY_TYPE.items():
            assert 0 < p <= 1, f'{t} 胜率 {p} 越域'

    def test_invest_registry_ids_and_names_unique(self):
        # 数字 id 为稳定主键;name 已 canon 归一(注册表键)——重复 = 采样/查表歧义
        for reg, label in ((PLAZA_AUGMENTS, 'augments'), (PLAZA_PORTALS, 'portals')):
            ids = [e.id for e in reg] if isinstance(reg, list) else list(reg)
            names = [e.name for e in reg] if isinstance(reg, list) else list(reg)
            assert len(ids) == len(set(ids)), f'{label} id 重复'
            assert len(names) == len(set(names)), f'{label} name 重复'


# ===== 合同三:派生一致性(派生常量 vs 单一源重算) =====

class TestDerivationConsistency:
    """import 时派生的常量与从单一源重算对照——防派生表达式被改手抄。"""

    def test_synthesis_derived_from_equipments(self):
        # cw_synthesis 全部配方常量声明派生自 EQUIPMENTS[].recipes(compose_list);
        # 从单一源现算对照组,防派生链被改成手抄表
        recalc_advance = {n: e.recipes for n, e in EQUIPMENTS.items()
                          if e.category == '进阶' and e.recipes}
        assert synth._ADVANCE_RECIPES == recalc_advance
        recalc_bases = frozenset(
            c for recipes in recalc_advance.values() for r in recipes for c in r)
        assert synth.SYNTHESIS_BASES == recalc_bases - {'光能电池'}

    def test_distinct_cards_matches_chars(self):
        # shop_odds 的每档卡种数 = chars 注册表现算(派生;两表各自登记时此锁防漂移)
        assert DISTINCT_CARDS_PER_COST == {
            cost: len(chars_by_cost(cost)) for cost in range(1, 6)}

    def test_plaza_snapshot_guard(self):
        # 迁自 data_registry:8 条 plaza 冻结条目(与生成器同源 config API V4.4)
        # 断言 cost/position/traits 与 CHARACTERS 一致;全量对拍跑 gen_plaza_chars.py
        pool = (
            ('1001', '三月七', 1, 'Back', ('列车同行', '护盾')),
            ('1014', 'Saber', 3, 'Common', ('命运圣杯', '能量')),
            ('1202', '停云', 1, 'Back', ('仙舟', '能量')),
            ('1304', '砂金', 2, 'Front', ('公司', '追击', '护盾')),
            ('1408', '白厄', 3, 'Front', ('救世主',)),
            ('1501', '火花', 4, 'Front', ('星间旅人', '战技点', '欢愉')),
            ('15061', '银狼LV.999', 3, 'Front', ('星核猎手', '欢愉', '头号玩家')),
            ('8009', '开拓者·欢愉', 4, 'Back', ('列车同行', '能量', '欢愉')),
        )
        position_map = {'Front': 'front', 'Back': 'back', 'Common': 'flex'}
        for pid, name, cost, pos, traits in pool:
            ch = CHARACTERS[name]
            assert ch.cost == cost, f'{pid} {name}: cost {ch.cost} != plaza {cost}'
            assert ch.position == position_map[pos], f'{pid} {name}: position'
            reg_traits = (set(ch.factions) | set(ch.flows)
                          | ({ch.independent} if ch.independent else set()))
            assert reg_traits == set(traits), f'{pid} {name}: traits'


# ===== 合同四:登记门(覆盖完整性,红时知道该登记什么) =====

class TestRegistrationGates:
    """覆盖门:高频被动更新合法(红=提醒登记新语义,非快照陷阱)。"""

    def test_registry_covers_all_costs(self):
        # 迁自 data_registry:注册表覆盖全费用 1-5 且每档非空;总数合理(V4.4 ~70+)
        for cost in range(1, 6):
            assert len(chars_by_cost(cost)) > 0, f'{cost} 费应有角色'
        assert len(CHARACTERS) > 60

    def test_all_advanced_have_recipe(self):
        # 迁自 data_registry(K8 闭合):进阶全量有配方;36 件数变化=登记新进阶
        adv = [n for n, e in EQUIPMENTS.items() if e.category == '进阶']
        assert len(adv) == 36
        missing = [n for n in adv
                   if not (synth.cross_components(n) or synth.self_base(n))]
        assert missing == [], f'进阶无配方: {missing}'
