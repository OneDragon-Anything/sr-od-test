"""CW 装备域测试(#10):分配不变量 4 代表行 + M7 转移门(dd-027 事故家族)
+ 穿戴语义代表 + 阵营星徽(dd-015 事故代表)。

覆盖面:
- 分配 4 代表行:test_allocation_invariants 参数化 4 档(CUT7 收缩定稿,
  覆盖 equip_allocation 全分支)+ I5 轮转保序全序锚;
- transfer gate:M7 可穿存在性门①(工具-only 活锁事故回归帧)+ 门② 执行位闩
  (同相位只消费一次)+ 发射序回排截断存活 + C3「发射不烧闩」残留锁;
- wear 代表:释放判据表 row5(committed 域豁免 + opening 不对称)+
  零上身哨兵枚举外兜底 fail-closed + 散文↔结构对拍真值锚(罚值 80%/8%);
- 星徽:同阵营排除(dd-015 复盘 g_20260902_181254 定谳)+ 异阵营正常授予。

来源:本文件 = test_cw_equip_alloc_gen.py(git mv)+ test_cw_equip_transfer_gate.py
/test_cw_equip_wear_semantics.py 代表行并入(2026-09-09 套件重建批 A,#10)。
其余历史锁已退役(git 可复活)。

--- 原 r135 装备分配场景生成器说明(用户提议:装备做成模拟数据 test) ---
与 r134 手写 4 条互补:组合枚举 × 不变量。枚举面 = 真实分配维度:
- comp 态(None/有 core/key_equips 有无)
- deployed 构成(core 数 × 非 core 数 × 前后排)
- owned 构成(key 命中数 × 通用件数 × 件数 < / = / > 总容量)

不变量(分配纪律的数学性质,比断言具体分配更强):
I1 容量守恒:任何角色分得数 ≤ EQUIP_CAPACITY × 该角色槽位数
I2 key 优先:key_equips 全部分给 core(carry 先于其它 core)
I3 core 优先:comp 在场时,通用件先填满 core 才轮非 core
   (r134 具名样本背书——用户质询「为什么给砂金」:反甲白厄线 3 件通用
   应由 core 白厄吃满容量 3,非 core 砂金/赛飞儿 0 件,核心换血摩擦最小)
I4 不超发:输出总条数 ≤ owned 总数(每件至多一次)
I5 无 comp 轮转保序:comp=None 按 deployed 原序轮转(r232 改轮转,
   前排先入序;全序断言判别「deployed 原序」与「按行排序」两种实现)
"""
import pytest

from sr_od.application.currency_war.data.affix_effects_data import AFFIX_EFFECTS
from sr_od.application.currency_war.data.affix_wear_semantics_data import (
    WEAR_AFFIX_SEMANTICS,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    EQUIP_CAPACITY,
    Comp,
    equip_allocation,
)
from sr_od.application.currency_war.kernel.cw_equip_env import (
    ZERO_WEAR_EXECUTION_PENDING,
    classify_item_hold,
    classify_zero_wear_stop_reason,
    is_free_item,
    resolve_wear_release,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    OpenShop,
    RunDeploy,
    RunEquip,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import mandate
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


def _mk_comp(cores, keys=None, carry=None):
    c = Comp(name='测试线', factions=['贝洛伯格'], core_chars=list(cores),
             form_tiers={}, strength=5.0, form_difficulty='hard')
    c.key_equips = list(keys or [])
    if carry:
        c.plaza_carry = carry
    return c


# 枚举面(压缩到代表性档)
COMPS = [None,
         _mk_comp(['白厄']),                        # 单 core 无 key
         _mk_comp(['白厄', '三月七']),              # 双 core
         _mk_comp(['白厄', '三月七'], ['以牙还牙甲', '以牙还牙甲', '高周波电锯'], carry='白厄')]
DEPLOYED_SETS = [
    [BenchChar(slot=1, char_id='砂金', faction='公司', star=1, position_pref='front')],
    [BenchChar(slot=1, char_id='砂金', faction='公司', star=1, position_pref='front'),
     BenchChar(slot=2, char_id='白厄', faction='贝洛伯格', star=1, position_pref='front')],
    [BenchChar(slot=1, char_id='砂金', faction='公司', star=1, position_pref='front'),
     BenchChar(slot=1, char_id='白厄', faction='贝洛伯格', star=1, position_pref='back'),
     BenchChar(slot=2, char_id='三月七', faction='列车同行', star=1, position_pref='back'),
     BenchChar(slot=2, char_id='翡翠', faction='公司', star=1, position_pref='front')],
]
OWNED_SETS = [
    [],
    ['以牙还牙甲'],
    ['狙击枪', '生命之花', '物质分解液'],
    ['以牙还牙甲', '以牙还牙甲', '高周波电锯', '狙击枪', '生命之花'],
]

# 枚举面(CUT7 收缩:48 组合积 → 4 代表行,覆盖分配器全分支;2026-09-09)
# 收缩自 4×3×4=48 行 → 4 行,代表行选择依据 = equip_allocation 分支覆盖:
# - (0,2,0):comp=None 无-comp 轮转路径 + 空 owned(I4 平凡支);
# - (1,0,1):core 不在场(di=0 仅砂金)→ key/通用兜底给场上人支,I3 field_cores 空;
# - (3,1,3):key×3+carry 且 core 在场(di=1)→ I2 key 优先 + I3 容量被 key 占满
#   的非 core 豁免面(3 key 占满白厄容量 → 通用件流 non-core 合法);
# - (2,2,2):双 core + 4 人前后排交错(di=2)→ I3 多 core 容量分配。
# 被删 44 行均为同一纯函数下的数据变体:不变量 I1-I4 对任意输入成立,
# 同分支变体行错一版必被代表行与其余用例(equipment 主题文件)共同暴露。
REPRESENTATIVE_COMBOS = [(0, 2, 0), (1, 0, 1), (3, 1, 3), (2, 2, 2)]


@pytest.mark.parametrize('ci,di,oi', REPRESENTATIVE_COMBOS,
                         ids=['nocomp_empty', 'core_absent_fallback',
                              'key_priority_full', 'dual_core_multirow'])
def test_allocation_invariants(ci, di, oi):
    comp, dep, owned = COMPS[ci], DEPLOYED_SETS[di], OWNED_SETS[oi]
    alloc = equip_allocation(comp, dep, owned)
    # I4 不超发
    assert len(alloc) <= len(owned)
    # I1 容量守恒
    per_char: dict[str, int] = {}
    for cname, _w in alloc:
        per_char[cname] = per_char.get(cname, 0) + 1
    on_field = {d.char_id for d in dep if d.char_id}
    for cname, n in per_char.items():
        assert cname in on_field, f'{cname} 不在场上却分得装备'
        assert n <= EQUIP_CAPACITY, f'{cname} 超 EQUIP_CAPACITY'
    # I2 key 优先:key_equips 只给 core(carry 含);**core 在场前提**——
    # core 未上场时 key 件经兜底穿给场上人是合理行为(保战力)。core 上场后
    # 的转移不由分配器/本 op 直拖完成(装备不能角色间直拖;转移=卖角色或
    # 扳手拆,归决策器,见 equipment_mechanics「装备转移机制」节)。
    if comp is not None and comp.key_equips:
        keys = list(comp.key_equips)
        core_set = set(comp.core_chars) | ({comp.plaza_carry} if comp.plaza_carry else set())
        field_core = core_set & on_field
        for cname, w in alloc:
            if w in keys and field_core:
                assert cname in core_set, f'key 件 {w} 分给了非 core {cname}(core 在场)'
                keys.remove(w)   # multiplicity 消费
    # I3 core 优先(comp 在场):通用件填满 core 剩余容量前非 core 不拿
    # (core 容量可能已被 key 件占满——白厄 key×3 后通用容量 0,非 core 拿合法)。
    # 死库存豁免(ADR-0391,全 plane 生效——ADR-0265 增补后 P1 亦然):
    # 回收合格基础件先于 core 兜底抽取、改道非 core 工具人是有意的收益
    # 路由,不计入 I3 的「非 core 抢通用」违规面。本不变量原在 P1 保留
    # 过滤下写成(基础件永不入池,豁免面不可达),随过滤删除补豁免。
    if comp is not None:
        core_set = set(comp.core_chars)
        field_cores = [c for c in comp.core_chars if c in on_field]
        from sr_od.application.currency_war.data.cw_synthesis import (
            recycle_qualified,
        )
        dead = set(recycle_qualified(list(comp.key_equips or [])))
        key_used_by_core = sum(1 for c, w in alloc
                               if c in core_set and comp.key_equips and w in comp.key_equips)
        core_generic_cap = max(0, sum(EQUIP_CAPACITY for _ in field_cores) - key_used_by_core)
        generic_n = sum(1 for w in owned
                        if (not comp.key_equips or w not in comp.key_equips)
                        and w not in dead)
        core_got_generic = sum(1 for c, w in alloc if c in core_set
                               and (not comp.key_equips or w not in comp.key_equips)
                               and w not in dead)
        non_core_got = sum(1 for c, w in alloc if c not in core_set
                           and (not comp.key_equips or w not in comp.key_equips)
                           and w not in dead)
        if core_got_generic < min(generic_n, core_generic_cap) and non_core_got > 0:
            pytest.fail(f'core 通用容量未满({core_got_generic}<{min(generic_n, core_generic_cap)})'
                        f'但非 core 拿了 {non_core_got} 件')


def test_no_comp_rotation_keeps_deployed_order():
    """I5:comp=None 轮转按 deployed 原序(前排先入序;r232 轮转不改序)。

    4 人 front/back 交错帧:deployed 原序 ≠ 前排排序(翡翠 front 但序 4)
    ——只断首元素的旧形态对「按行排序」实现不红,全序断言才有判别力。
    2 人轮转 + 容量扣减面由 test_cw_target_matching
    ::test_equip_allocation_capacity_and_fallback 承载,两帧互补。"""
    dep = DEPLOYED_SETS[2]
    alloc = equip_allocation(None, dep, ['a', 'b', 'c', 'd'])
    assert alloc == [(d.char_id, e) for d, e in zip(dep, 'abcd')], alloc


# ----- dd-015 后补:阵营星徽排除同阵营角色(复盘 g_20260902_181254 定谳) -----

def _mk_dep(char_id, row='back', slot=1):
    return BenchChar(slot=slot, char_id=char_id, faction='', star=1, position_pref=row)


def test_emblem_not_allocated_to_same_faction():
    """列车同行星徽不发同阵营三月七(复盘 g_20260902_181254 定谳)。

    core 艾丝妲 occupied 穿满 3 件容量归零,星徽落到非 core 兜底位——
    无守卫时三月七(注册表自报列车同行)必得件,守卫在位则星徽无人可穿
    留 owned(原帧 core 容量未满、星徽必被非同阵营 core 先拿,守卫删除
    后该断言仍绿 = 零判别力,故改穿满帧)。"""
    deploy = [_mk_dep('艾丝妲', slot=1), _mk_dep('三月七', slot=2)]
    out = equip_allocation(
        _mk_comp(['艾丝妲']), deploy, ['列车同行星徽'],
        {('back', 1): ['x', 'y', 'z'], ('back', 2): []})
    assert all(not (c == '三月七' and e == '列车同行星徽') for c, e in out), out
    assert all(e != '列车同行星徽' for _, e in out), '守卫在位:同阵营无人可穿,星徽留 owned'


def test_emblem_allowed_to_other_faction():
    """非同阵营角色正常获得星徽(add-if-absent 授予新羁绊=星徽用途)。"""
    deploy = [_mk_dep('艾丝妲', slot=1), _mk_dep('三月七', slot=2)]
    out = equip_allocation(
        _mk_comp(['艾丝妲']), deploy, ['列车同行星徽'],
        {('back', 1): [], ('back', 2): []})
    assert any(e == '列车同行星徽' for _, e in out), out


# ==================== M7 装备转移发射门(自 test_cw_equip_transfer_gate.py 并入代表行) ====================
# 事故链(dd-027):mandate 旧发射谓词「last_owned_equips 非空即发 RunEquip」,
# 而 owned 快照按 ADR-0387 全量含工具件(不可穿)——工具-only 库存谓词永真 ⇒
# 每帧重发 RunEquip 且执行侧 0 穿 ⇒ 空批出口(StartBattle)永不可达,备战环
# 活锁(实机 1-6 卡死)。修法 = 门① 可穿存在性 + 门② 备战期闩(置位在执行位)。
# dd-027 修订(g_20260904_010335 漏发):RunEquip 落 OpenShop 截断点后被截断器
# 静默丢弃 ⇒ 发射序回排;TestM7EmissionOrder 锁 truncate 端到端存活。

# 工具件/穿戴件取注册表真实规范名(锁语义不锁牌面;名字变动时改此处,
# 谓词走 EQUIPMENTS 注册表现查,不依赖测试桩)
_TOOLS = ['拆装扳手', '冶金炉']          # 注册表 category='工具'
_WEARABLE = ['和平手枪', '轮滑鞋']       # 注册表非工具类(历史 fixture 常用件)


def _m7_frame(round_num: int = 3, stop: bool = True) -> mandate.MandateFrame:
    """最小备战帧:stop=True 压掉 M2/dominance/M6 的开店发射面,本批只看 M7。"""
    return mandate.MandateFrame(
        gold=0, level=3, bench=[], deployed=[], deploy_cap=4,
        node_type='战斗', stop_flag=stop, k_members=(),
        round_num=round_num)


def _m7_session(owned: list[str]) -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    s.last_owned_equips = list(owned)
    return s


def _m7_actions(out: list) -> list:
    return [e for e in out if isinstance(e.action, RunEquip)]


def test_m7_tools_only_owned_never_fires():
    """门① 事故回归帧:owned 全工具件 → 不发 RunEquip(旧码永真重发=活锁根)。"""
    out = mandate.run_mandate(_m7_frame(), _m7_session(_TOOLS))
    assert _m7_actions(out) == []


def test_m7_wearable_owned_fires():
    """门① 正向控制:owned 有穿戴类件 → 正常发射(门不误杀常态转移)。"""
    out = mandate.run_mandate(_m7_frame(), _m7_session(_WEARABLE))
    assert len(_m7_actions(out)) == 1


def test_m7_same_phase_fires_once():
    """门②:执行成功置闩后,同 (plane, round) 后续帧不再发,计数
    equip_latch_skip_m7=1;闩未置时同帧重跑照常重发(发射不烧闩)。
    (闩置位从发射位移到 RunEquip 执行位——发射位只读不写,2026-09-05
    C3 同型残留修复;详见 test_m7_deploy_termination_does_not_burn_latch。)"""
    s = _m7_session(_WEARABLE)
    st = GameState(round_num=3)
    assert len(_m7_actions(mandate.run_mandate(_m7_frame(), s, state=st))) == 1
    # 闩未置(发射≠执行):重跑照常发射
    assert len(_m7_actions(mandate.run_mandate(_m7_frame(), s, state=st))) == 1
    # 穿戴 pass 执行成功(执行位置位)→ 同期后续帧不再发
    mandate.mark_equip_pass_executed(s, st)
    out3 = mandate.run_mandate(_m7_frame(), s, state=st)
    assert _m7_actions(out3) == []
    assert state_of(s).cw4_counters['equip_latch_skip_m7'] == 1


def test_m7_deploy_termination_does_not_burn_latch():
    """C3 同型残留回归锁(2026-09-05 双修对抗审计):同帧 [RunDeploy,
    RunEquip] 发射,环被 RunDeploy 先终结(RunEquip 未执行)——下一环
    mandate 重跑 RunEquip 重新发射(闩未烧)。

    事故形态:部署空位 ∧ 可穿件同时成立(如补给发装备 + 场上有空位)时,
    单动作备战环第 1 环执行 RunDeploy 即「投影未建模,访问终结交回外循环
    重观察」;旧实现发射即置闩 ⇒ 第 2 环 equip_latch_skip ⇒ 空批
    StartBattle,装备整个备战期滞留。修法 = 置位时机移执行位。"""
    frame = mandate.MandateFrame(
        gold=0, level=3,
        bench=[BenchChar(slot=1, char_id='彦卿', star=1)],
        deployed=[], deploy_cap=4,
        node_type='战斗', stop_flag=True, k_members=(),
        round_num=3)
    s = _m7_session(_WEARABLE)
    out1 = mandate.run_mandate(frame, s)
    kinds = [type(e.action) for e in out1]
    assert kinds == [RunDeploy, RunEquip]       # 可续双动作,无截断点
    assert getattr(s, 'cw4_m7_equipped_phase', None) is None  # 发射不置闩
    out2 = mandate.run_mandate(frame, s)
    assert len(_m7_actions(out2)) == 1          # 闩未烧,重发
    assert state_of(s).cw4_counters.get('equip_latch_skip_m7', 0) == 0


def test_m7_truncation_keeps_both_actions():
    """dd-027 修订端到端(事故 g_20260904_010335 1-6/1-7 漏发):真实发射
    列表经 truncate_frame_stable 后 [RunEquip, OpenShop] 两动作均存活
    (事故里 M7 末位的 RunEquip 落截断点后被静默丢弃,闩已消耗 ⇒ 整个
    备战期装备滞留;发射序回排后本锁守存活面)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.entry import (
        truncate_frame_stable,
    )
    # 可穿件在场 + M2 买面意图(线成员缺,bench 空,金足)→ 同帧双意图
    frame = mandate.MandateFrame(
        gold=10, level=3, bench=[], deployed=[], deploy_cap=4,
        node_type='战斗', stop_flag=False, k_members=('希儿',),
        round_num=3)
    s = _m7_session(_WEARABLE)
    actions = [e.action for e in mandate.run_mandate(frame, s)]
    kept = truncate_frame_stable(actions, s)
    assert [type(a) for a in kept] == [RunEquip, OpenShop]


# ==================== 穿戴语义代表行(自 test_cw_equip_wear_semantics.py 并入) ====================

_BATTLE = frozenset({'战斗', 'boss', '遭遇', '精英'})


def test_wear_row5_releases_committed_only():
    """释放判据表 row5:输出侧词缀豁免只辖 committed 扣留域,不辖 opening hold
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


def test_zero_wear_unknown_reason_falls_back_pending():
    """零上身哨兵兜底行:枚举外一切(含空串 stall)暂归执行链待分诊(fail-closed)。"""
    for r in ('', '神秘新原因', '循环自然结束(stall)'):
        assert classify_zero_wear_stop_reason(r) \
            == ZERO_WEAR_EXECUTION_PENDING, r


def test_wear_prose_value_pairing_lock():
    """散文↔结构对拍真值锚(18 号稿 §3.1):游戏改罚值 → 散文更新 → 本锁红
    = 派生缓存 divergent,禁静默沿用。"""
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