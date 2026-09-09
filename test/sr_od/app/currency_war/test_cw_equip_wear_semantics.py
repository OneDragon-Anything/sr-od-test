"""18 号稿「装备穿戴策略语义」落码锁面(ADR-0526)。

五组锁:
1. 释放判据表五行 + 多行合并规则(扣留任一命中、豁免取并集;row5 只辖
   committed 域不辖 opening,§2.1 不对称);
2. 零上身哨兵 stop_reason 辖域二分(策略 by-design / 策略缺口 / 执行链
   + 枚举外兜底行,§1.2);
3. 词缀条件优先层求序(限输出侧罚则族;comp=None 强制零重排,§3.2/§3.3);
4. equip_allocation priority_order 签名扩展(缺省零漂移 / 重排不改件数
   / fill-only 不取下已穿件,§3.3 + §1.2-3);
5. 结构化载体对拍锁(散文↔结构值逐条对拍 + 互检检测面零显警,§3.1)。
"""
from sr_od.application.currency_war.data.affix_effects_data import AFFIX_EFFECTS
from sr_od.application.currency_war.data.affix_wear_semantics_data import (
    WEAR_AFFIX_SEMANTICS,
    check_wear_semantics_coverage,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    EQUIP_CAPACITY,
    Comp,
    equip_allocation,
)
from sr_od.application.currency_war.kernel.cw_equip_env import (
    ZERO_WEAR_EXECUTION,
    ZERO_WEAR_EXECUTION_PENDING,
    ZERO_WEAR_STRATEGY_BY_DESIGN,
    ZERO_WEAR_STRATEGY_GAP,
    classify_item_hold,
    classify_zero_wear_stop_reason,
    is_free_item,
    resolve_affix_priority_order,
    resolve_wear_release,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar

_BATTLE = frozenset({'战斗', 'boss', '遭遇', '精英'})


def _mk_comp(cores, keys=None, carry=None):
    c = Comp(name='测试线', factions=['贝洛伯格'], core_chars=list(cores),
             form_tiers={}, strength=5.0, form_difficulty='hard')
    c.key_equips = list(keys or [])
    if carry:
        c.plaza_carry = carry
    return c


def _mk_dep(char_id, row='back', slot=1):
    return BenchChar(slot=slot, char_id=char_id, faction='', star=1,
                     position_pref=row)


def _prio_comp():
    """词缀优先层/分配重排两组锁共用的定型线载体(carry + 双 core)。"""
    return _mk_comp(['卡芙卡', '三月七'], carry='卡芙卡')


def _prio_dep():
    """三人在场帧:卡芙卡(back-1)/三月七(back-2)/砂金(back-3,非 core)。"""
    return [_mk_dep('卡芙卡'), _mk_dep('三月七'), _mk_dep('砂金', slot=3)]


# ===== 1. 释放判据表(§2.1)=====

class TestWearReleaseTable:
    def test_row4_rust_releases_all_hold(self):
        """生锈豁免辖「一切扣留」:opening 与 committed 都解。"""
        d = resolve_wear_release(1, '奖励', True, _BATTLE, 'c', 0.2, True,
                                 ['库藏生锈'], True)
        assert d.opening_hold and d.committed_hold and d.rust_release
        assert d.hold is False

    def test_row5_releases_committed_only(self):
        """输出侧词缀豁免只辖 committed 扣留域,不辖 opening hold
        (不对称 = 罚则结算时点,§2.1)。"""
        # r>2:无 opening,仅 committed hold 活跃 → row5 解除
        d = resolve_wear_release(5, '投资', True, _BATTLE, 'c', 0.2, True,
                                 ['软弱无力'], True)
        assert d.output_penalty_release is True
        assert d.committed_hold is True
        assert d.hold is False
        d2 = resolve_wear_release(5, '投资', True, _BATTLE, 'c', 0.2, True,
                                  ['软弱无力', '库藏生锈'], True)
        assert d2.hold is False           # 豁免取并集,行为一致
        # opening 活跃时 row5 不解 opening 域(21 号稿 ADR-0531 收窄后帧级
        # hold 只辖 row2 域;旧断言「opening 帧 hold=True」随帧级布尔降格
        # 改写,锁存在性纪律)——hold 属性若回退旧公式(opening 参与),
        # d3.hold 翻 True 即红
        d3 = resolve_wear_release(2, '奖励', True, _BATTLE, None, 0.0, False,
                                  ['软弱无力'], True)
        assert d3.opening_hold is True
        assert d3.output_penalty_release is True
        assert d3.hold is False
        # row5 豁免辖域 = row2:opening 帧内 committed 活跃时非 key 件仍扣。
        # 样本须为真自由件(非 key/非保留域/非唯一/非工具,前提自证防样本
        # 失真后静默落「枚举外恒扣」门);free_slot=False 让 O2 不中,判别
        # 路径 = row1 帧保留域①——若 row5 豁免误辖 opening 域,本断言翻红
        sample = '反重力皮靴'
        assert is_free_item(sample, _mk_comp(['a'])) is True, '锁样本须为真自由件'
        d4 = resolve_wear_release(2, '奖励', True, _BATTLE, 'c', 0.2, True,
                                  ['软弱无力'], True)
        assert classify_item_hold(d4, sample, _mk_comp(['a']), False) is True

    def test_row5_needs_structured_output_entry(self):
        """在册词缀集判定:承伤侧(额外打击)与无结构条目的散文词缀都不触发。"""
        for affixes in (['额外打击'], ['挫其锋芒'], ['形单影只'], ['未知词缀']):
            d = resolve_wear_release(5, '投资', True, _BATTLE, 'c', 0.2, True,
                                     affixes, True)
            assert d.output_penalty_release is False, affixes


# ===== 2. 哨兵辖域二分(§1.2)=====

class TestZeroWearClassification:
    def test_strategy_domains(self):
        assert classify_zero_wear_stop_reason(
            '过渡期hold:无 key_equips 命中(全攒着)') \
            == ZERO_WEAR_STRATEGY_BY_DESIGN
        assert classify_zero_wear_stop_reason(
            '分配方案空:pairing_guard') == ZERO_WEAR_STRATEGY_GAP

    def test_execution_domains(self):
        for r in ('drag 落空(失败继续,dd-015)',
                  'pool_empty(无穿戴候选)',
                  '分配对全部拉黑(drag 连败,dd-015)',
                  '画面非干净备战',
                  '白厄 槽位坐标缺失'):
            assert classify_zero_wear_stop_reason(r) == ZERO_WEAR_EXECUTION, r

    def test_fallback_pending(self):
        """兜底行:枚举外一切(含空串 stall)暂归执行链待分诊。"""
        for r in ('', '神秘新原因', '循环自然结束(stall)'):
            assert classify_zero_wear_stop_reason(r) \
                == ZERO_WEAR_EXECUTION_PENDING, r


# ===== 3. 词缀条件优先层求序(§3.2)=====

class TestAffixPriorityOrder:
    def test_unsatisfied_predicate_reorders(self):
        """谓词未满足:未满足者按 [9] 基序置前,core 恒在列(凑满契约)。"""
        order = resolve_affix_priority_order(
            _prio_comp(), _prio_dep(), ['软弱无力'],
            {('back', 1): ['光能电池']})   # 卡芙卡 1 件 < 3
        assert order[0] == '卡芙卡'
        assert '三月七' in order           # core 恒在列(fill-to-full)
        assert '砂金' in order             # 砂金 0 件也未满足(罚则按角色个体,
        #                                      在场角色全集都入凑满面,§3.2-1)
        # 非 core 已满足谓词者不占凑满位
        order2 = resolve_affix_priority_order(
            _prio_comp(), _prio_dep(), ['软弱无力'],
            {('back', 1): ['光能电池'],
             ('back', 3): ['x', 'y', 'z']})   # 砂金(back-3)已满 3 件
        assert '砂金' not in order2

    def test_satisfied_returns_none(self):
        """谓词满足 → 回落基分配序(零重排)。"""
        occ = {('back', 1): ['a', 'b', 'c'], ('back', 2): ['d', 'e', 'f'],
                ('back', 3): ['g', 'h', 'i']}
        assert resolve_affix_priority_order(
            _prio_comp(), _prio_dep(), ['软弱无力'], occ) is None

    def test_comp_none_forced_none(self):
        """§3.3:comp=None(未定型帧)强制零重排。"""
        assert resolve_affix_priority_order(
            None, _prio_dep(), ['软弱无力'], None) is None

    def test_no_output_side_affix_none(self):
        """承伤侧族与无词缀帧不启用优先层(§3.2 分叉声明)。"""
        for affixes in (None, [], ['额外打击']):
            assert resolve_affix_priority_order(
                _prio_comp(), _prio_dep(), affixes, None) is None

    def test_no_deployed_none(self):
        assert resolve_affix_priority_order(
            _prio_comp(), [], ['软弱无力'], None) is None


# ===== 4. equip_allocation priority_order(§3.3 + fill-only)=====

class TestEquipAllocationPriorityOrder:
    def test_default_zero_drift(self):
        """缺省 None = 现行内部派生序,输出逐位一致(零漂移锁)。"""
        dep, owned = _prio_dep(), ['a', 'b', 'c', 'd', 'e']
        assert equip_allocation(_prio_comp(), dep, owned) == \
            equip_allocation(_prio_comp(), dep, owned, priority_order=None)

    def test_reorder_changes_landing_not_count(self):
        """重排改「落在谁身上」,不改可穿件总数(§3.3 语义保持声明)。"""
        dep = _prio_dep()
        owned = ['a', 'b', 'c', 'd', 'e']
        base = equip_allocation(_prio_comp(), dep, owned)
        prio = equip_allocation(_prio_comp(), dep, owned,
                                priority_order=['砂金', '卡芙卡', '三月七'])
        assert len(base) == len(prio)
        # 砂金(非 core)入凑满序后吃满容量,先于 core 拿件
        assert sum(1 for c, _ in prio if c == '砂金') == EQUIP_CAPACITY

    def test_fill_only_never_removes_worn(self):
        """脱落预防(§1.2-3):occupied 仅容量扣减;已穿 3 件的角色零新分配,
        任何重排都不产出「取下/迁移」语义(输出只有 (角色, 新件) 对)。"""
        occ = {('back', 1): ['a', 'b', 'c']}   # 卡芙卡已穿满
        dep = _prio_dep()
        for prio in (None, ['卡芙卡', '砂金', '三月七']):
            alloc = equip_allocation(_prio_comp(), dep, ['x', 'y'], occ,
                                     priority_order=prio)
            assert all(c != '卡芙卡' for c, _ in alloc), (prio, alloc)

    def test_key_binding_not_redirect_by_priority(self):
        """key 件绑定裁决(§3.2 落码批回记):谓词层只重排候选序不改 key 件
        绑定——非 core 置前也不得先拿 key 件(key 接收者限于 carry∪core)。"""
        comp = _mk_comp(['卡芙卡', '三月七'],
                        keys=['火力风暴潮'], carry='卡芙卡')
        dep = _prio_dep()
        alloc = equip_allocation(comp, dep, ['火力风暴潮', 'x'],
                                 priority_order=['砂金', '卡芙卡', '三月七'])
        key_owner = next(c for c, w in alloc if w == '火力风暴潮')
        assert key_owner in ('卡芙卡', '三月七'), alloc
        assert key_owner == '卡芙卡', 'carry 仍最先拿 key 件([9] 基序不变)'

    def test_comp_none_ignores_priority_order(self):
        """comp=None 强制 priority_order=None(§3.3),与缺省输出一致。"""
        dep = _prio_dep()
        assert equip_allocation(None, dep, ['a', 'b', 'c']) == \
            equip_allocation(None, dep, ['a', 'b', 'c'],
                             priority_order=['砂金', '卡芙卡'])


# ===== 5. 结构化载体对拍锁 + 检测面(§3.1)=====

class TestWearSemanticsCarrier:
    def test_prose_ref_anchor_exists(self):
        """prose_ref 词缀名锚:每个结构条目在散文注册表有同名行(孤儿缓存警)。"""
        for name, e in WEAR_AFFIX_SEMANTICS.items():
            assert e.prose_ref == name
            assert name in AFFIX_EFFECTS, name

    def test_prose_value_pairing_lock(self):
        """首次消费对拍锁:结构值与散文原文逐条对拍(18 号稿 §3.1)。
        游戏改罚值 → 散文更新 → 本锁红 = 派生缓存 divergent,禁静默沿用。"""
        e = WEAR_AFFIX_SEMANTICS['软弱无力']
        prose = AFFIX_EFFECTS['软弱无力']
        assert e.wear_predicate == ('min_worn_per_char', 3)
        assert e.penalty_side == 'output'
        assert '3件装备' in prose, '散文 N=3 已漂移,对拍后更新结构缓存'
        assert '80%' in prose, '散文罚值 80% 已漂移,对拍后更新 penalty_value'
        assert e.penalty_value == 0.8
        e2 = WEAR_AFFIX_SEMANTICS['额外打击']
        prose2 = AFFIX_EFFECTS['额外打击']
        assert e2.wear_predicate is None and e2.penalty_side == 'damage_taken'
        assert '空缺装备栏' in prose2
        assert '8%' in prose2, '散文罚值 8% 已漂移,对拍后更新 penalty_value'
        assert e2.penalty_value == 0.08

    def test_coverage_no_warnings_now(self):
        """互检显警检测面(§3.1):当前在册集零显警;新词缀漏建模会在
        消费点 log.warning 并可在此加断言。"""
        assert check_wear_semantics_coverage() == []
