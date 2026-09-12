"""CW 装备域测试(#10):分配不变量 4 代表行 + M7 转移门(dd-027 事故家族)
+ 穿戴语义代表 + 阵营星徽(dd-015 事故代表)+ 穿着可行性三谓词(W1/W2/W3)。

收缩注记(CUT9 二次收缩:原 15 测试→8 测试;同分支变体/双保险重复砍,
git 可复活):
- 分配 4 代表行全留(CUT7 定稿参数化,覆盖 equip_allocation 全分支);
- transfer 留门① 工具-only 事故回归帧 1 代表(fail-closed 根);
  门① 正向/门② 同相位闩/C3 部署终结不烧闩/截断存活四变体砍;
- wear 留释放判据表 row5(committed/opening 不对称)1 代表;零上身
  哨兵兜底行砍(fail-closed 面由 transfer 门① 承载);
- 星徽留同阵营排除(dd-015 定谳)1 代表,异阵营正常授予变体砍;
- 真值锚留散文↔结构对拍(罚值 80%/8% 注册表真值);I5 轮转保序全序
  行砍(nocomp_empty 代表档已辖 comp=None 路径)。

覆盖面:
- 分配 4 代表行:test_allocation_invariants 参数化 4 档(CUT7 收缩定稿,
  覆盖 equip_allocation 全分支);
- transfer gate:M7 可穿存在性门①(工具-only 活锁事故回归帧);
- wear 代表:释放判据表 row5(committed 域豁免 + opening 不对称)+
  散文↔结构对拍真值锚(罚值 80%/8%);
- 星徽:同阵营排除(dd-015 复盘 g_20260902_181254 定谳);
- 穿着可行性三谓词(W1 同名∧非两基础件合成图谱对 / W2 件专属前置 /
  W3 骇客目标类 fail-closed):设计出处 =
  docs/develop/sr_od/application/currency_war/proofs/p95-allocation-feasibility-dominance.md
  §2-A/§5(必拒对分配前排除严格支配分配后重试;三谓词各一组按「删守卫
  即红/过宽即红」判别力落锁)+ 结构化载体
  data/cw_equipment_wear_rules_data(前置/可穿性建模单一源)。锁面申报
  (部分有效):W1/W2 的 worn 输入与容量扣减同源(below-avatar 画面现读),
  read_row_equipped mini icon 漏读(3 件读 1 实证)使 worn 缩水 → 漏读帧
  拦不全,识别面批收口前谓词部分有效,禁把漏读帧的漏拦读成谓词无效
  (P95 §2 附出辖声明)。

来源:本文件 = test_cw_equip_alloc_gen.py(git mv)+ test_cw_equip_transfer_gate.py
/test_cw_equip_wear_semantics.py 代表行并入(2026-09-09 套件重建批 A,#10;
CUT9 二次收缩见收缩注记)。其余历史锁已退役(git 可复活)。

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
    classify_item_hold,
    is_free_item,
    resolve_wear_release,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    RunEquip,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import BenchChar
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
    # 穿戴可行性豁免(锁语义重推记录,P95 支配命题 §2-A 分配前排除):
    # key 同名多副本是 comp 设计的合法输入形态,但第二副本对已持有同名件
    # 的 core 构成必拒对(游戏侧同名∧非两基础件合成图谱对拒收,W1 建模)
    # ——排除后副本留 pool 走兜底。故「非 core 收到 key 实例」的唯一合法
    # 形态 = 每个在场 core 对该实例均被穿戴可行性门拦;复核用生产谓词
    # 单源(_wearable_gate_ok)直调 + 分配终态 core 已穿名单,不复刻分配
    # 内部序。W3 门(hacker 类)下非 core 同样不可穿,该形态仍被本断言拦。
    if comp is not None and comp.key_equips:
        keys = list(comp.key_equips)
        core_set = set(comp.core_chars) | ({comp.plaza_carry} if comp.plaza_carry else set())
        field_core = core_set & on_field
        from sr_od.application.currency_war.kernel.cw_comps import _wearable_gate_ok
        core_worn_final: dict[str, list[str]] = {}
        for c, w in alloc:
            if c in core_set:
                core_worn_final.setdefault(c, []).append(w)
        for cname, w in alloc:
            if w in keys and field_core:
                if cname in core_set:
                    keys.remove(w)   # multiplicity 消费
                    continue
                infeasible_cores = [c for c in field_core
                                    if not _wearable_gate_ok(
                                        core_worn_final.get(c, []), c, w)]
                assert len(infeasible_cores) == len(field_core), \
                    (f'key 件 {w} 分给了非 core {cname},但存在可行 core '
                     f'{[c for c in field_core if c not in infeasible_cores]}'
                     f'(必拒对排除面失守)')
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
    from sr_od.application.currency_war.kernel.cw_game_state import (
        board_state_bridge as _bsb,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame as _F
    # state 容器必填(容器化段 2):帧轴镜像 _m7_frame 同值构造。
    st = _F(gold=0, level=3, bench=[], deployed=[], deploy_cap=4,
            node_type='战斗', round_num=3)
    out = mandate.run_mandate(_m7_frame(), _m7_session(_TOOLS), state=_bsb(st))
    assert _m7_actions(out) == []


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


# ==================== 穿着可行性三谓词(W1/W2/W3;P95 §2-A 分配前排除) ====================
# 设计出处(持久锚):docs/develop/sr_od/application/currency_war/proofs/
# p95-allocation-feasibility-dominance.md §2-A(三谓词机制事实)/§3 边界②③
# (推断级定谳前统一保守拦截 + 拦域与配对守卫例外域互斥)/§5(消费位与锁)。
# 判定单源 = kernel/cw_comps._wearable_gate_ok(分配与分配空归因镜像共用);
# 前置/可穿性建模单一源 = data/cw_equipment_wear_rules_data。
# 每组首锁 = 「删守卫即红」的守卫移除验证载体;反例面锁 = 「过宽即红」
# (防 W1 退化回裸同名形态拦掉合法穿着即合成通道)。

def test_w1_same_name_non_graph_pair_stays_owned():
    """W1 判拒面:身上已有永动机,同池再入第二件永动机 → 必拒留 owned
    (同名对 ∉ 两基础件合成图谱对;定谳前保守拦截,P95 §3 边界②)。
    删除 _wearable_gate_ok 的 W1 分支本锁即红。"""
    deploy = [_mk_dep('符玄', slot=1)]
    out = equip_allocation(None, deploy, ['永动机'], {('back', 1): ['永动机']})
    assert out == [], f'同名非图谱对应被拦(件留 owned),得 {out}'


def test_w1_same_name_basic_self_pair_allowed():
    """W1 反例面(收窄辖域回归锚):身上已有光能电池,同池再入光能电池 →
    放行(同名对 ∈ 配方图 = 合法穿着即合成通道,游戏自动合成永动机),
    交配对守卫例外①②既有辖域;W1 若退化回裸「item ∈ worn」形态本锁即红。"""
    deploy = [_mk_dep('符玄', slot=1)]
    out = equip_allocation(None, deploy, ['光能电池'], {('back', 1): ['光能电池']})
    assert out == [('符玄', '光能电池')], f'同名自配对 = 合成通道须放行,得 {out}'


def test_w1_synthesis_product_expansion():
    """W1 输入口径:现读仍见原始组件对(光能电池×2,游戏侧已合成永动机)
    → 同名第二件永动机判拒(合成产物展开 = P95 §2-A「worn = 现读 ∪ 合成
    产物展开」;展开 = cw_synthesis.expand_worn_products)。删除展开调用
    本锁即红。"""
    deploy = [_mk_dep('符玄', slot=1)]
    out = equip_allocation(None, deploy, ['永动机'],
                           {('back', 1): ['光能电池', '光能电池']})
    assert out == [], f'合成产物展开后应见永动机在身(判拒),得 {out}'


def test_w1_block_domain_disjoint_from_pairing_guard_exception_domain():
    """W1 拦域 ∩ 配对守卫例外①②辖域 = 空(P95 §3 边界③互斥对账回归锁;
    程序化口径:拦域成员 [同名对 ∉ 图谱] 全为非基础件,例外域全为基础件
    交叉配对)。注册表图谱形态漂移(某基础件失去自配配方 → 拦域混入
    基础件 = 拦合法合成通道)本锁即红。"""
    from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
    from sr_od.application.currency_war.data.cw_synthesis import (
        RESERVED_COMPONENTS,
        self_advance,
    )
    blocked = [n for n in EQUIPMENTS if self_advance(n) is None]
    assert blocked, '拦域非空前提失真(注册表形态漂移,先复核再动)'
    leaked = [n for n in blocked if n in RESERVED_COMPONENTS]
    assert not leaked, \
        f'基础件 {leaked} 无自配配方 → 混入 W1 拦域,与例外①②辖域相交(互斥被破坏)'


def test_w2_empty_slots_prereq_blocks_nonempty_wearer():
    """W2 判拒面:「需要空装备栏」族(随便骰子·特权)对身上有件的角色必拒
    留 owned(实机实证形态:希儿 2 件在身拖骰子被拒;读法定谳前保守
    「有任意件即拒」)。删除 W2 分支本锁即红。"""
    deploy = [_mk_dep('希儿', slot=1)]
    out = equip_allocation(None, deploy, ['随便骰子·特权'],
                           {('back', 1): ['折叠小刀', '轮滑鞋']})
    assert out == [], f'前置不满足(身上有件)应拒,得 {out}'


def test_w2_empty_wearer_wearable():
    """W2 合法面:空装备栏角色(occupied 空)→ 前置满足正常分配(保守缺省
    只拒「有件」帧;空栏是骰子族唯一合法穿着态,不得误伤)。W2 过宽
    (恒拒)本锁即红。"""
    deploy = [_mk_dep('希儿', slot=1)]
    out = equip_allocation(None, deploy, ['随便骰子·特权'], {('back', 1): []})
    assert out == [('希儿', '随便骰子·特权')], f'空装备栏应可穿,得 {out}'


def test_w2_structured_rule_coverage_lock():
    """W2 散文↔结构对拍锁(载体同构先例 = 软弱无力罚值对拍锁):结构条目
    谓词值与注册表 effect 措辞互为锚,漂移即红;互检零告警 = 无漏建模/
    孤儿条目/名锚错位(消费点显警的静态保证面)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
    from sr_od.application.currency_war.data.cw_equipment_wear_rules_data import (
        EQUIP_WEAR_PREREQUISITES,
        WEAR_PREREQ_EMPTY_SLOTS,
        check_equipment_wear_rule_coverage,
    )
    assert check_equipment_wear_rule_coverage() == [], '互检显警非空(漏建模/孤儿/措辞漂移)'
    assert set(EQUIP_WEAR_PREREQUISITES) == {'随便骰子', '随便骰子·特权'}, \
        '在册条目集漂移:增删条目须同步核对注册表 effect 全文(全表恰两处前置措辞)'
    for name, entry in EQUIP_WEAR_PREREQUISITES.items():
        assert entry.predicate == WEAR_PREREQ_EMPTY_SLOTS
        assert '需要空装备栏' in EQUIPMENTS[name].effect, \
            f'{name} 散文锚已漂移(effect 不再含前置措辞),对拍后更新结构载体'


def test_w3_hacker_item_blocked_for_non_whitelist():
    """W3 判拒面:骇客改件对白名单外角色必拒留 owned(fail-closed;实机
    实证形态:欢愉卡带Max 对异阵营普通角色 4/4 拖拽全败)。删除 W3 分支
    本锁即红。本锁兼作 cw_bond_equips 对账锚:卡带「非成员 +1」半边所依赖
    的分配通道由本谓词在分配面关闭(bot 自派不再放电该形态)。"""
    deploy = [_mk_dep('三月七', slot=1), _mk_dep('姬子·启行', slot=2)]
    out = equip_allocation(None, deploy, ['欢愉卡带Max'])
    assert out == [], f'骇客件对白名单外角色应全拦(件留 owned),得 {out}'


def test_w3_hacker_gate_whitelist_form():
    """W3 白名单形态锁(登记门语义):fail-closed 门在册值 = 仅银狼LV.999
    (假说级,真值未定谳,禁当已证);银狼LV.999 在场时正常分配。白名单
    静默放宽/收窄本锁即红——扩大或收窄须随实测定谳批(骇客件合法装备者
    单点拖拽观测)同步改写本锁并更新载体注释。"""
    from sr_od.application.currency_war.data.cw_equipment_wear_rules_data import (
        CATEGORY_WEAR_GATES,
    )
    assert CATEGORY_WEAR_GATES.get('骇客') == frozenset({'银狼LV.999'}), \
        '骇客门白名单形态漂移:改值须随定谳批同步(载体注释 + 本锁)'
    deploy = [_mk_dep('银狼LV.999', slot=1)]
    out = equip_allocation(None, deploy, ['欢愉卡带Max'])
    assert out == [('银狼LV.999', '欢愉卡带Max')], f'白名单角色应可穿,得 {out}'


def test_w3_gate_covers_key_equips_channel():
    """W3 全通道辖域:key_equips 通道同受穿戴可行性门辖(P95 命题主语 =
    (件,角色) 对,必拒对全分配通道排除;与 _emblem_ok/_pairing_ok 同构
    ——后两者本就辖 key 环)。key 环摘钩本锁即红。"""
    comp = _mk_comp(['三月七'], ['欢愉卡带'], carry='三月七')
    deploy = [_mk_dep('三月七', slot=1)]
    out = equip_allocation(comp, deploy, ['欢愉卡带'])
    assert out == [], f'key 通道亦须过穿戴可行性门,得 {out}'


def test_alloc_empty_reason_wearable_gate():
    """分配空归因镜像:全池被穿戴可行性门拦下 → 'wearable_gate'(诊断与
    分配语义单源镜像;镜像缺失会把全拦帧误归 'unknown' 漂移信号)。
    stop_reason 同走「分配方案空:」前缀 → 哨兵归域 strategy_gap,与
    pairing_guard 同域,归域枚举零改动。"""
    from sr_od.application.currency_war.kernel.cw_comps import (
        equip_alloc_empty_reason,
    )
    deploy = [_mk_dep('三月七', slot=1)]
    reason = equip_alloc_empty_reason(None, deploy, ['欢愉卡带Max'],
                                      {('back', 1): []})
    assert reason == 'wearable_gate', f'得 {reason}'
    reason2 = equip_alloc_empty_reason(None, [_mk_dep('符玄', slot=1)], ['轮滑鞋'],
                                       {('back', 1): ['光能电池']})
    assert reason2 == 'pairing_guard', f'配对守卫归因被穿戴门遮蔽,得 {reason2}'
