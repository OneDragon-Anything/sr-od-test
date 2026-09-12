"""T-162 投资刷新能力恢复 · 预注册单帧锁(kernel 锁 1-8 + handler 锁 9-14)。

锁面出处 = ADR-0600(docs/develop/sr_od/application/currency_war/decisions/
0600-t162-invest-refresh-criterion.md,§3 判据与执行链 + §5 验证;推导权威 =
ADR-0600 §3.2 + math_proofs P81;方案过程档案 = .debug/temp/currency_war/
attacks/t162_invest_refresh/设计方案.md R4,四轮对抗 14→11→8→0)——预注册
合同,锁语义不锁卡名,docstring 引 ADR 章节。判据本体 = 零阈值结构存在性
(ADR-0600 §3.2 逐槽弱占优论证):帧级触发(候选恰 3 ∧ 全精确分类 ∧ 非 env
帧 ∧ 无 S1/S2 ∧ max_N≠1)+ 槽级动作集(非顶级 ∧ 逐卡计数闸 ∧ 唯一 L1 守卫)。
环境帧轴 = invest-env 迭代 design.md §2.8 判据(3.5 接线,取代 ADR-0600
「env 帧恒不刷」F9;R1-R5/R7 kernel 锁同文件落此,锁 5 已随翻转改形;
R6 = 环境屏 handler 执行链端到端锁,3.8 接线,镜像策略侧锁 9-14 桩形,
env 形差异 = 整组重掷单钮单计数 + 验效双通道按 design §2.8 保留)。

fixture 卡取自注册表实卡(分类谓词直调核验,模块导入即验,漂移即全文件先红):
- 全普通 S4:赌神·银/恢复生机/气氛组(无引擎无对齐无血);
- S2 引擎:免费午餐;S1 定义型:黑塔纪元;血:奋斗协议/不等价交换;
- 希儿量子锁线(comp factions=[量子同频,贝洛伯格],core 含希儿/花火/符玄/缇宝/
  刻律德菈)下 N≥2 对齐卡:贝洛伯格星徽(贝洛伯格+希儿)/钢铁美学/贝洛伯格星徽套组;
- 绯英欢愉锁线下 N=1 对齐卡:阿哈大悦(仅欢愉阵营命中);
- handler 端到端用真 MandateV1Strategy(flow.decide_invest 入口,G1)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_comps import (
    AUGMENT_COMP_AFFINITY,
    candidate_faction_universe,
)
from sr_od.application.currency_war.kernel.cw_env_economy import (
    ENV_ECONOMY_ESTIMATES,
    EconomyEstimate,
)
from sr_od.application.currency_war.kernel.cw_events import decide_event
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    EconomyEffect,
    InvestmentStrategy,
    get_strategy,
    is_blood_economy,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame, PickEvent
from sr_od.application.currency_war.obs.cw_node_obs import (
    pair_refresh_counts_to_slots,
    read_invest_refresh_counts,
)
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_invest_env as env_mod,
)
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_invest_strategy as strat_mod,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_env import (
    CwScreenInvestEnv,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_strategy import (
    CwScreenInvestStrategy,
)

# fixture 前提直调核验(锁语义依赖的分类事实;漂移 = 注册表/谓词变更,先红于此)
assert AUGMENT_COMP_AFFINITY.get('黑塔纪元'), 'S1 fixture 须为定义型卡'
assert is_blood_economy(get_strategy('奋斗协议').economy), '血 fixture 直调'
assert is_blood_economy(get_strategy('不等价交换').economy), '血 fixture 直调'


def _cfg(**overrides) -> SimpleNamespace:
    base: dict = {'strategy_priority': [], 'strategy_forbid': []}
    base.update(overrides)
    return SimpleNamespace(**base)


_STATE = CwWorkFrame(board={}, hp=100, hp_readable=True)


def _pick(options: list[str], cfg=None, **kw) -> PickEvent:
    # W6 波3:decide_event 切容器签名,旧帧经过渡桥装箱。
    return decide_event(options, cfg if cfg is not None else _cfg(),
                        board_state_bridge(_STATE), **kw)


# ===== kernel 锁 1:全顶级集 → refresh_slots=∅(S1 一案 + S2 一案)=====


def test_lock1_all_top_tier_sets_no_refresh() -> None:
    """锁 1(ADR-0600 §5 预注册清单):帧内任一非被禁卡达 S1(定义型)或 S2(经济引擎档)
    → 整帧阻断(fail-closed,顶级卡不可刷)。"""
    p1 = _pick(['黑塔纪元', '气氛组', '恢复生机'])
    assert p1.refresh_slots == () and p1.refresh is False, 'S1 定义型在场须阻断'
    p2 = _pick(['免费午餐', '黄金垃圾', '恢复生机'])
    assert p2.refresh_slots == () and p2.refresh is False, 'S2 引擎在场须阻断'


# ===== kernel 锁 2:S3 保护判别式(按 max_N 分档,不锁全称结论)=====


def test_lock2_max_n_equals_one_frame_blocked() -> None:
    """锁 2a:帧内最高对齐档 = 1(N=1 可被 S4 顶部逾越,ADR-0600 §3.2)→ 整帧不刷。
    fixture:阿哈大悦(绑定=欢愉阵营)× 绯英欢愉锁线 = 仅阵营命中 N=1。"""
    p = _pick(['阿哈大悦', '气氛组', '恢复生机'], locked_comp='绯英欢愉')
    assert p.refresh_slots == () and p.refresh is False, 'max_N=1 帧整帧阻断'


def test_lock2_mixed_tiers_n1_slot_refreshable() -> None:
    """锁 2b(混合档帧,G3 钉死):N≥2 载体与 N=1 槽并存 → 可触发,动作集 =
    全部槽 − N≥2 对齐槽(N=1 槽可刷——其跌档风险被 110 载体兜底,ADR-0600 §3.2)。
    fixture:贝洛伯格星徽 N=2(阵营+角色双命中)/ 盛会之星星徽 N=1(仅花火)/
    气氛组 N=0 × 希儿量子锁线。"""
    p = _pick(['贝洛伯格星徽', '盛会之星星徽', '气氛组'], locked_comp='希儿量子')
    assert p.refresh is True and p.refresh_slots == (1, 2), (
        f'混合档帧动作集应只保护 N≥2 槽,实得 {p.refresh_slots}')


def test_lock2_all_aligned_slots_no_refresh() -> None:
    """锁 2c:三槽全部 N≥2 对齐(非血)→ 全保护 → 动作集空 → 不建议刷新。"""
    p = _pick(['贝洛伯格星徽', '钢铁美学', '贝洛伯格星徽套组'],
              locked_comp='希儿量子')
    assert p.refresh_slots == () and p.refresh is False, '全对齐帧无槽可刷'


def test_lock2_aligned_plus_plain_mixed_only_plain_refreshable() -> None:
    """锁 2d:N≥2 对齐 + 非对齐混合 → 动作集仅含非对齐槽(对齐槽保护不刷)。"""
    p = _pick(['贝洛伯格星徽', '钢铁美学', '气氛组'], locked_comp='希儿量子')
    assert p.refresh is True and p.refresh_slots == (2,), (
        f'仅非对齐槽可刷,实得 {p.refresh_slots}')


# ===== kernel 锁 3:fail-closed(分类不可靠/候选数≠3 → 阻断)=====


def test_lock3_fail_closed_classification() -> None:
    """锁 3(LCS 形变/未注册/精确误中环境名,轴钉死 G7):任一候选不可精确
    分类 → 整帧阻断。策略∩环境注册表双 ∅(ADR-0600 §3.1 直调),环境名在策略轴
    恒 miss → 阻断(fail-closed:评分错只排错序、刷新错会弃掉真顶级卡,
    不对称风险取严)。"""
    p1 = _pick(['赌神·银', '恢复生机', '奋斗协讉'])   # LCS 形变名(可解析但非精确)
    assert p1.refresh_slots == (), 'LCS 形变名不入刷新分类 → 阻断'
    p2 = _pick(['赌神·银', '恢复生机', '完全未知卡'])   # 未注册名
    assert p2.refresh_slots == (), '未注册名 → 阻断'
    p3 = _pick(['赌神·银', '恢复生机', '彩虹时代'])   # 精确命中环境注册表(G7 轴)
    assert p3.refresh_slots == (), '环境名在策略轴不可分类 → 阻断'


def test_lock3_candidate_count_not_three_blocked() -> None:
    """锁 3(J3 门槛):候选数 ≠ 3(9 字卡名超读带/读缺/同名碰撞收敛)→ 整帧
    阻断——「恰三槽」的 x 就近配对假设由结构保证,非 OCR 碰运气。"""
    p2 = _pick(['赌神·银', '恢复生机'])
    assert p2.refresh_slots == (), '2-可见帧 → 阻断'
    p4 = _pick(['赌神·银', '恢复生机', '气氛组', '着眼当下'])
    assert p4.refresh_slots == (), '4 候选帧 → 阻断'


# ===== kernel 锁 4:血本位槽可刷 + 唯一 L1 守卫(kernel 静态)+ L2/L3 帧形态 =====


def test_lock4_blood_slot_in_action_set() -> None:
    """锁 4a(P4 行为面):血本位槽非顶级 → 在动作集内(刷掉血卡 = P4 回避
    的改进支,ADR-0600 §3.2 四支④)。"""
    p = _pick(['奋斗协议', '气氛组', '恢复生机'])
    assert p.refresh is True and 0 in p.refresh_slots, '血槽应在动作集内'


def test_lock4_unique_l1_slot_protected() -> None:
    """锁 4b(F2 唯一 L1 守卫,kernel 静态口径):L1={X} 帧 → X 不入动作集
    (刷掉唯一非血非禁卡且新卡为血/禁 → 三态序强制血选,确定损失分支)。
    序贯形态条款归 handler 锁 14(kernel 单次调用不可表达,J5)。"""
    p = _pick(['奋斗协议', '不等价交换', '恢复生机'])
    assert p.refresh is True and p.refresh_slots == (0, 1), (
        f'唯一 L1 槽(2)应被保护,实得 {p.refresh_slots}')


def test_lock4_all_blood_frame_all_slots_actionable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 4c(L2 全血非禁帧,G4 补):L1=∅ → 唯一 L1 守卫空转(welfare 延拓)
    → 动作集 = 全部可分类槽。注册表现存仅两血卡,第三张测试注入(先例:
    test_decide_event_unevaluated_blood_candidate_level,teardown 自动恢复)。"""
    monkeypatch.setitem(
        INVESTMENT_STRATEGIES, '血契协议',
        InvestmentStrategy(name='血契协议', rarity='棱彩',
                           effect='测试注入:血本位第三卡',
                           economy=EconomyEffect(xp_buy_hp_cost=6)))
    assert is_blood_economy(get_strategy('血契协议').economy)
    p = _pick(['奋斗协议', '不等价交换', '血契协议'])
    assert p.refresh is True and p.refresh_slots == (0, 1, 2), (
        f'全血帧守卫空转、全部槽可刷,实得 {p.refresh_slots}')


def test_lock4_all_forbidden_frame_all_slots_actionable() -> None:
    """锁 4d(L3 全禁帧,G4 补):被禁不计达档/不计 max_N(P5①/J6)→ 触发
    继续;被禁槽恒入可刷集(P5②)→ 动作集 = 全部槽。"""
    cfg = _cfg(strategy_forbid=['赌神·银', '恢复生机', '气氛组'])
    p = _pick(['赌神·银', '恢复生机', '气氛组'], cfg)
    assert p.refresh is True and p.refresh_slots == (0, 1, 2), (
        f'全禁帧全部槽可刷,实得 {p.refresh_slots}')


# ===== kernel 锁 5:env 帧全部受保护槽形 → 刷新集空(F9 语义已被 §2.8 取代)=====


def test_lock5_env_frame_all_protected_no_refresh() -> None:
    """锁 5(原 F9「env 帧恒不刷」帧;行为翻转在册申报 = invest-env 迭代
    design.md §2.8:ADR-0600 §2/§4 恒不刷规则由环境帧刷新判据取代,启用
    前置「环境侧顶级类建模」由经济域带/送卡档接线满足)。本帧三槽全为
    全集内/受保护形({追击概念股, 彩虹时代, 头彩}:无全集外零价值槽、
    无被禁)→ 环境判据动作集空 → 不刷——与零价值槽可刷新语义(R 组)互补,
    帧 fixture 保持原值作行为连续性对照。"""
    p = _pick(['追击概念股', '彩虹时代', '头彩'])
    assert p.refresh_slots == () and p.refresh is False, '全保护 env 帧不刷'


# ===== kernel 锁 6:判据零次数输入(签名结构锁)=====


def test_lock6_no_count_input_in_signature() -> None:
    """锁 6(ADR-0600 §3.4):触发与槽选择只消费分类结果,计数只在执行层作画面
    现读闸——kernel 签名不含任何计数/次数参数(结构锁,防次数口径混入判据)。"""
    params = inspect.signature(decide_event).parameters
    assert not any('count' in name or 'refresh' in name or 'times' in name
                   for name in params), f'签名出现次数面参数:{list(params)}'


# ===== kernel 锁 7:被禁卡统一规则(P5/J6)=====


def test_lock7_forbidden_engine_does_not_block() -> None:
    """锁 7a(P5①):被禁引擎卡不参加达档判定 → 不阻断触发(被禁卡永不被选,
    无保护对象);被禁槽恒入可刷集(P5②)。"""
    cfg = _cfg(strategy_forbid=['免费午餐'])
    p = _pick(['免费午餐', '气氛组', '恢复生机'], cfg)
    assert p.refresh is True and p.refresh_slots == (0, 1, 2), (
        f'被禁引擎不阻断、被禁槽恒入,实得 {p.refresh_slots}')


def test_lock7_forbidden_aligned_slot_still_actionable() -> None:
    """锁 7b(P5②,含被禁∧N≥2 对齐槽):被禁对齐槽失去保护(永不被选,保护
    无对象)→ 入动作集。对照非被禁帧(保护生效)作判别。"""
    base = _pick(['贝洛伯格星徽', '气氛组', '恢复生机'], locked_comp='希儿量子')
    assert base.refresh_slots == (1, 2), '前提:非被禁对齐槽受保护'
    cfg = _cfg(strategy_forbid=['贝洛伯格星徽'])
    p = _pick(['贝洛伯格星徽', '气氛组', '恢复生机'], cfg, locked_comp='希儿量子')
    assert p.refresh is True and p.refresh_slots == (0, 1, 2), (
        f'被禁对齐槽应转为可刷,实得 {p.refresh_slots}')


def test_lock7_forbidden_n1_sole_carrier_still_triggers() -> None:
    """锁 7c(J6 钉死):被禁 N=1 唯一对齐帧 → 被禁不计入 max_N → max_N=0 ≠ 1
    → 触发继续,动作集按槽级规则(被禁槽恒入)。"""
    cfg = _cfg(strategy_forbid=['阿哈大悦'])
    p = _pick(['阿哈大悦', '气氛组', '恢复生机'], cfg, locked_comp='绯英欢愉')
    assert p.refresh is True and p.refresh_slots == (0, 1, 2), (
        f'被禁 N=1 载体不阻断触发,实得 {p.refresh_slots}')


# ===== kernel 锁 8:N≥2 fallback 恒等性质(strict > 取槽序首,G11;J1 申报)=====


def test_lock8_any_slot_refresh_still_picks_aligned() -> None:
    """锁 8(ADR-0600 §3.2 fallback 恒等):帧含非血 N≥2 对齐卡时,动作集任一槽
    刷新后(新卡为非顶级)重决策的 option_idx 仍 = 某 N≥2 对齐卡槽——
    双对齐卡帧取 strict > 首序(槽 0),与主循环同语义(G11 歧义消)。
    新卡取 S4 顶部 鲜血阶梯(75,非血非顶级):110 > 75,对齐卡恒胜。"""
    frame = ['贝洛伯格星徽', '钢铁美学', '气氛组']
    p = _pick(frame, locked_comp='希儿量子')
    assert p.refresh_slots == (2,), '前提:动作集 = 非对齐槽'
    for j in p.refresh_slots:
        after = list(frame)
        after[j] = '鲜血阶梯'
        repick = _pick(after, locked_comp='希儿量子')
        assert repick.option_idx == 0, (
            f'槽{j}刷新(新卡 S4 75)后 option_idx 应仍=对齐卡槽 0,实得 {repick}')


def test_lock8_steering_priority_keeps_aligned_pick() -> None:
    """锁 8 例外分支(J1 steering 面申报锁,禁实现批二选一):对齐卡命中
    user priority(110+30=140)、新顶级卡不命中(120)→ option_idx 仍 =
    对齐卡槽——刷新白耗一次计数、无损失,弱占优结论不变。"""
    cfg = _cfg(strategy_priority=['贝洛伯格星徽'])
    frame = ['贝洛伯格星徽', '气氛组', '恢复生机']
    p = _pick(frame, cfg, locked_comp='希儿量子')
    assert p.refresh_slots == (1, 2), '前提:对齐槽保护,priority 不改变保护面'
    after = list(frame)
    after[1] = '黑塔纪元'   # S1 定义型 120,不命中 priority
    repick = _pick(after, cfg, locked_comp='希儿量子')
    assert repick.option_idx == 0, (
        f'对齐卡+priority(140)应压过新 S1(120),实得 {repick}')


# ===== 3.5 环境帧刷新判据 R 组(invest-env 迭代 design.md §2.8;kernel 侧)=====
# 判据 = 零自由参数结构分类:零价值(全集门失格 ∧ 未被 user-priority 命中)
# 恒可刷(逐槽弱占优:当前价值 0,替换样本任一 ≥ 0 且 P(>0) 显著,免费刷新
# 用失即废)/ 被禁恒可刷(P5② 同构:被禁者永不被选,保护无对象)/ 顶级
# (经济域带 resolved ∨ 阵营 floor 命中)与其余集内裸分槽(含送卡档、
# unresolved 经济槽——基数化挂账 §2.8)保护不刷。帧级门 = 恰 3 ∧ 全部精确
# 命中环境注册表(未知名 fail-closed 不刷,G7 轴同款)。
# R 帧前提直调核验(漂移先红,重核 R 组咬合面):
_R_OFF_UNIVERSE = ('狼狩概念股', '狼狩邀请', '盛会之星邀请')
_UNIV0 = candidate_faction_universe()
for _n in _R_OFF_UNIVERSE:
    _e = INVESTMENT_ENVS[_n]
    assert _e.faction and _e.faction not in _UNIV0, (
        f'{_n} 应在全集外(R 组零价值槽前提)')
assert INVESTMENT_ENVS['增发货币'].economy is not None, (
    'R3/R7 顶级槽前提:增发货币应带经济通道')
for _n in ('战力提升', '成功经验', '彩虹时代', '头彩', '火药味'):
    assert INVESTMENT_ENVS[_n].faction == '', (
        f'{_n} 应为 faction 空候选(集内槽前提)')
assert INVESTMENT_ENVS['仙舟概念股'].faction in _UNIV0, (
    'R6e 前提:仙舟概念股应在全集内(锁线 floor 保护形,R6e 判别载体)')


def _inject_arrival_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """R3/R7 到达参数注入(design R3 行「到达参数注入 resolved」;不依赖
    注册表现值,全达帧 6+8+12=26 → 域带 116,方向确定)。"""
    for _k in ('plane_arrival_p2', 'plane_arrival_p3'):
        monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, _k, EconomyEstimate(
            value=1.0, ci=(0.9, 1.0), source='test-inject', cutoff='1970-01-01'))


def test_r1_zero_value_slot_refreshable() -> None:
    """R1(design §2.8 R1 行):{狼狩概念股, 战力提升, 成功经验} → 动作集 =
    {0}——全集外零价值槽恒可刷,集内槽(裸分/经济顶级)不刷。"""
    p = _pick(['狼狩概念股', '战力提升', '成功经验'])
    assert p.refresh is True and p.refresh_slots == (0,), (
        f'零价值槽可刷、集内槽不刷,实得 {p.refresh_slots} ({p.reason})')


def test_r2_all_off_universe_all_slots() -> None:
    """R2(design §2.8 R2 行):三全集外实卡(狼狩概念股/狼狩邀请/盛会之星
    邀请)→ 全槽可刷。"""
    p = _pick(list(_R_OFF_UNIVERSE))
    assert p.refresh is True and p.refresh_slots == (0, 1, 2), (
        f'三零价值槽全可刷,实得 {p.refresh_slots}')


def test_r3_top_tier_protected_with_zero_slot(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """R3(design §2.8 R3 行):{增发货币, 狼狩概念股, 战力提升} + 到达参数
    注入 resolved → 顶级保护(增发货币域带)与零槽可刷(狼狩概念股)并存,
    集内裸分槽(战力提升)不刷 → (1,)。"""
    _inject_arrival_params(monkeypatch)
    p = _pick(['增发货币', '狼狩概念股', '战力提升'])
    assert p.refresh is True and p.refresh_slots == (1,), (
        f'仅零价值槽可刷,顶级与集内槽保护,实得 {p.refresh_slots}')


def test_r4_priority_hit_off_universe_slot_kept() -> None:
    """R4(design §2.8 R4 行):priority 命中全集外槽 → 该槽不入动作集
    (用户点名保选,user-priority 最高语义与全集门 U5 同构);对照槽(狼狩
    邀请,未命中 priority)零价值恒可刷 → (1,)。"""
    p = _pick(['狼狩概念股', '狼狩邀请', '火药味'],
              _cfg(env_priority=['狼狩概念股']))
    assert p.refresh is True and p.refresh_slots == (1,), (
        f'priority 命中集外槽不入动作集,实得 {p.refresh_slots}')


def test_r5_unknown_name_fail_closed() -> None:
    """R5(design §2.8 R5 行):含未注册名 → 帧级门(全部精确命中环境注册表)
    不触发 → refresh_slots=∅(fail-closed:评分错只排错序、刷新错会弃掉真
    顶级卡,不对称风险取严)。"""
    p = _pick(['狼狩概念股', '战力提升', '完全未知卡'])
    assert p.refresh_slots == () and p.refresh is False, '未知名 fail-closed 不刷'


def test_r7_forbidden_slot_always_actionable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """R7(design §2.8 R7 行):集内被禁槽(env_forbid 命中 彩虹时代)与顶级
    (增发货币,注入 resolved)/集外零价值槽(狼狩概念股)并存 → 被禁槽恒入
    动作集(顶级保护不辖被禁,P5② 同构:被禁者永不被选)→ (0, 2)。"""
    _inject_arrival_params(monkeypatch)
    p = _pick(['彩虹时代', '增发货币', '狼狩概念股'],
              _cfg(env_forbid=['彩虹时代']))
    assert p.refresh is True and p.refresh_slots == (0, 2), (
        f'被禁槽恒可刷(顶级保护不辖),实得 {p.refresh_slots}')


# ===== handler 锁 9-14(执行链;桩化 OCR/读数/点击,零真实副作用)=====

# 计数文本 x(归档帧实测 ≈{477,975,1474},y≈855)与钮偏移 -88 → 钮心 ≈{389,887,1386};
# 卡名行 x(配对锚)≈{460,960,1460}、y=screen_info「区域-卡名行」center=480;
# 确认 = 「按钮-确认」center=(978,983)。全部与 screen_info/归档帧同源。
_CNT_XS = (477, 975, 1474)
_CNT_Y = 855
_OPT_XS = (460, 960, 1460)
_SELECT_Y = 480
_CONFIRM = Point(978, 983)
_DX = CwScreenInvestStrategy._REFRESH_BTN_DX


class _StubStrategy:
    """decide_invest 记录桩:按序弹出预置 PickEvent,记录每次调用的名集。"""

    def __init__(self, picks: list[PickEvent]) -> None:
        self.picks = list(picks)
        self.calls: list[list[str]] = []

    def decide_invest(self, kind, options, state, session, config) -> PickEvent:
        assert kind == 'strategy'
        self.calls.append(list(options))
        return self.picks.pop(0) if self.picks else PickEvent(
            option_idx=0, reason='stub-exhausted')


class _FrameBook:
    """帧登记簿:op.screenshot 逐次弹帧(末帧复用);读数桩按帧对象分发。"""

    def __init__(self, frames: list[object]) -> None:
        self.frames = frames
        self.options: dict[int, list[tuple[str, int, int]]] = {}
        self.counts: dict[int, list[tuple[int, int, int]]] = {}
        self.read_calls: list[str] = []
        self.i = 0

    def next_frame(self) -> object:
        f = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return f


def _counts_of(values: list[int]) -> list[tuple[int, int, int]]:
    return [(v, _CNT_XS[i], _CNT_Y) for i, v in enumerate(values)]


def _opts_of(names: list[str]) -> list[tuple[str, int, int]]:
    return [(n, _OPT_XS[i], 490) for i, n in enumerate(names)]


def _pts(clicks: list[Point]) -> list[tuple[int, int]]:
    """Point → 坐标元组(Point 无 __eq__,断言按 x/y 比)。"""
    return [(p.x, p.y) for p in clicks]


def _make_op(test_context, monkeypatch: pytest.MonkeyPatch,
             book: _FrameBook) -> tuple[CwScreenInvestStrategy, list[Point]]:
    """构造被测 op:入口锚恒过、截图走帧簿、计数读/点击/确认全桩化(零真实 IO;
    safe_click/confirm 走 handler 模块命名空间桩,选卡 y 用真 screen_info area)。"""
    op = CwScreenInvestStrategy(test_context)
    monkeypatch.setattr(op, '_ensure_entry_screen', lambda: True)
    # 验证废除批(pending 重入裁决)联动桩:入口锚单帧判定恒命中 = 重入时
    # 「确认未落地」车道(清 pending 重走),禁走真 OCR(last_screenshot 为
    # object 哨兵帧,digest 即炸)。
    monkeypatch.setattr(op, '_entry_anchor_hit', lambda screen: True)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: book.next_frame())
    monkeypatch.setattr(op, '_read_options',
                        lambda screen: book.options.get(id(screen), []))
    monkeypatch.setattr(op, '_interruptible_sleep', lambda s: None)
    monkeypatch.setattr(strat_mod.time, 'sleep', lambda s: None)

    def _fake_counts(ctx, screen, kind):
        book.read_calls.append(kind)
        return book.counts.get(id(screen), [])

    monkeypatch.setattr(strat_mod, 'read_invest_refresh_counts', _fake_counts)
    monkeypatch.setattr(strat_mod, 'emit_overlay_confirm',
                        lambda op, confirm_point, entry_keyword, tag:
                        (clicks.append(confirm_point),
                         SimpleNamespace(is_success=True))[1])
    clicks: list[Point] = []
    monkeypatch.setattr(strat_mod, 'safe_click',
                        lambda op, point, *, tag: clicks.append(point))
    return op, clicks


def _wire(test_context, monkeypatch: pytest.MonkeyPatch,
          strategy: object) -> object:
    sess = SimpleNamespace(active_strategies=[], last_state=None)
    match = SimpleNamespace(strategy=strategy, session=sess)
    monkeypatch.setattr(test_context, 'cw_match', match)
    return sess


def test_lock9_empty_slots_zero_drift(test_context,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 9:refresh_slots=∅ → 现状路径逐位不变——零计数读、零刷新点击,
    调用序 = 选卡 + 确认(坐标与既有路径一致),恰一次决策。"""
    book = _FrameBook([object()])
    book.options[id(book.frames[0])] = _opts_of(['赌神·银', '恢复生机', '气氛组'])
    strategy = _StubStrategy([PickEvent(option_idx=1, reason='eval')])
    _wire(test_context, monkeypatch, strategy)
    op, clicks = _make_op(test_context, monkeypatch, book)

    result = op.handle()

    assert result.is_success
    assert strategy.calls == [['赌神·银', '恢复生机', '气氛组']], '恰一次决策'
    assert book.read_calls == [], '不读计数(refresh_slots 空直落现状路径)'
    assert len(clicks) == 2, f'现状路径恰两击(选卡+确认),实得 {clicks}'
    assert _pts(clicks) == [(960, _SELECT_Y), (_CONFIRM.x, _CONFIRM.y)], (
        '选卡 = 卡名行中心(决策 idx1)+ 确认按钮中心')


def test_lock10_zero_or_missing_count_skips_slot(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 10:计数 0 / 读缺 → 跳过该槽(不点击、不置位);计数 >0 的槽照常刷
    (权威闸 = 画面现读)。读缺形态 = 中槽计数文本漏读,配对容差(半槽距)
    拒绝邻槽文本误配 → None(ADR-0600 §3.4 x 就近配对 + fail-closed)。"""
    book = _FrameBook([object(), object()])
    book.options[id(book.frames[0])] = _opts_of(['赌神·银', '恢复生机', '气氛组'])
    book.options[id(book.frames[1])] = _opts_of(['赌神·银', '鲜血阶梯', '气氛组'])
    book.counts[id(book.frames[0])] = [_counts_of([0, 0, 1])[0],
                                       _counts_of([0, 0, 1])[2]]   # 中槽读缺
    book.counts[id(book.frames[1])] = _counts_of([0, 0, 0])
    strategy = _StubStrategy([
        PickEvent(option_idx=0, refresh=True, refresh_slots=(0, 1, 2),
                  reason='eval+refresh-suggest'),
        PickEvent(option_idx=1, reason='eval'),
    ])
    _wire(test_context, monkeypatch, strategy)
    op, clicks = _make_op(test_context, monkeypatch, book)

    result = op.handle()

    assert result.is_success
    # 刷新点击恰一次:槽 2(计数 1);槽 0 计数 0、槽 1 读缺均跳过
    refresh_clicks = [c for c in clicks if c.y == _CNT_Y]
    assert _pts(refresh_clicks) == [(_CNT_XS[2] + _DX, _CNT_Y)], (
        f'仅槽 2 点刷新钮(0 与读缺跳过),实得 {refresh_clicks}')
    assert _pts(clicks[-2:]) == [(960, _SELECT_Y), (_CONFIRM.x, _CONFIRM.y)], (
        '刷后按最终决策选卡+确认')
    assert strategy.calls[1] == ['赌神·银', '鲜血阶梯', '气氛组'], (
        '重决策用最终名集(槽 1 已换卡)')


def test_lock11_reread_redecide_natural_chain_after_emit(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 11(语义翻转改写;原「验效双输失败安全」锁):验效双通道拆除
    (用户裁定 2026-09-10 动作 op 只管机械执行禁止验效,出处 = 清查报告
    .debug/temp/currency_war/验证违规清查-报告.md H2)后,本锁改锁机械执行
    +观察驱动新形态:点刷新+固定等待→无条件重读→重决策(名集未变 = 新观察
    与旧同名,重决策结果天然等价,不要求与原 pick 等价);链继续条件只由
    新观察承载——名集未变不拦链,后续槽闸(计数现读/防重入/L1 逐步守卫)
    过即照刷;防重入(发射即记)保每槽恰一次点击。"""
    book = _FrameBook([object(), object()])
    book.options[id(book.frames[0])] = _opts_of(['赌神·银', '恢复生机', '气氛组'])
    book.options[id(book.frames[1])] = _opts_of(['赌神·银', '恢复生机', '气氛组'])
    book.counts[id(book.frames[0])] = _counts_of([1, 1, 1])
    book.counts[id(book.frames[1])] = _counts_of([1, 1, 1])   # 重读帧计数不扣(原「双输」形态)
    strategy = _StubStrategy([
        PickEvent(option_idx=0, refresh=True, refresh_slots=(0, 1),
                  reason='eval+refresh-suggest'),
        PickEvent(option_idx=0, reason='re-decide'),
    ])
    _wire(test_context, monkeypatch, strategy)
    op, clicks = _make_op(test_context, monkeypatch, book)

    result = op.handle()

    assert result.is_success
    refresh_clicks = [c for c in clicks if c.y == _CNT_Y]
    assert _pts(refresh_clicks) == [(_CNT_XS[0] + _DX, _CNT_Y),
                                    (_CNT_XS[1] + _DX, _CNT_Y)], (
        f'名集未变不拦链:两槽各点一次(防重入保恰一次),实得 {refresh_clicks}')
    assert len(strategy.calls) == 2, '恰两次决策(初始 + 刷后重决策)'
    assert strategy.calls[1] == ['赌神·银', '恢复生机', '气氛组'], (
        '重决策用重读名集(未变 = 天然等价)')
    assert _pts(clicks[-2:]) == [(460, _SELECT_Y), (_CONFIRM.x, _CONFIRM.y)], (
        '按重决策选卡(idx0)+ 确认')


def test_lock12_reset_semantics_three_lanes(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 12(G6 复位语义三车道):①同 visit 重入(同实例二次 handle)不清
    → 防重入保留(已发射槽不二次点击);②跨 visit(新实例同 session)必清
    → 陈旧集不泄入(计数仍在时该槽可重试,J8 申报);③载体 = exec_state_of
    (session) 局容器级。"""
    book = _FrameBook([object(), object()])
    book.options[id(book.frames[0])] = _opts_of(['赌神·银', '恢复生机', '气氛组'])
    book.options[id(book.frames[1])] = _opts_of(['赌神·银', '鲜血阶梯', '气氛组'])
    book.counts[id(book.frames[0])] = _counts_of([1, 1, 1])
    book.counts[id(book.frames[1])] = _counts_of([0, 0, 0])
    strategy = _StubStrategy([
        PickEvent(option_idx=0, refresh=True, refresh_slots=(0,),
                  reason='eval+refresh-suggest'),
        PickEvent(option_idx=0, reason='eval'),
    ])
    sess = _wire(test_context, monkeypatch, strategy)
    exec_state_of(sess)._invest_refresh_used_slots.add(9)   # 预置陈旧位(对照清空语义)
    op, clicks = _make_op(test_context, monkeypatch, book)

    op.handle()   # visit 1:首帧复位(清空,预置 9 一并清)+ 槽 0 发射
    assert exec_state_of(sess)._invest_refresh_used_slots == {0}, '发射即记'
    assert _pts([c for c in clicks if c.y == _CNT_Y]) == [
        (_CNT_XS[0] + _DX, _CNT_Y)], 'visit1 槽 0 点刷一次'

    op.handle()   # 车道①:同实例重入 → 不清 → 已发射槽 0 跳过(无新刷新击)
    assert _pts([c for c in clicks if c.y == _CNT_Y]) == [
        (_CNT_XS[0] + _DX, _CNT_Y)], '同 visit 重入不清,防重入保留'
    assert exec_state_of(sess)._invest_refresh_used_slots == {0}

    # 车道②:新实例(新 visit,同 session)→ 必清 → 槽 0 可重试。
    # 计数给 1(若未清,防重入闸先拦 → 无点击即红;清了才可能再点)。
    book2 = _FrameBook([object(), object()])
    book2.options[id(book2.frames[0])] = _opts_of(
        ['赌神·银', '恢复生机', '气氛组'])
    book2.options[id(book2.frames[1])] = _opts_of(
        ['赌神·银', '鲜血阶梯', '气氛组'])
    book2.counts[id(book2.frames[0])] = _counts_of([1, 1, 1])
    book2.counts[id(book2.frames[1])] = _counts_of([0, 0, 0])
    strategy.picks.append(PickEvent(option_idx=0, refresh=True,
                                    refresh_slots=(0,),
                                    reason='eval+refresh-suggest'))
    strategy.picks.append(PickEvent(option_idx=0, reason='eval'))
    op2, clicks2 = _make_op(test_context, monkeypatch, book2)
    op2.handle()
    assert _pts([c for c in clicks2 if c.y == _CNT_Y]) == [
        (_CNT_XS[0] + _DX, _CNT_Y)], '跨 visit 新实例必清,陈旧集不泄入'


def test_lock13_d_star_passes_through_redecide(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 13(G1 D*① 传递):锁线帧刷新后重决策**经 decide_invest**(真
    MandateV1Strategy,D*① 三参只在此解析)→ option_idx 仍 = 某 N≥2 对齐卡槽。
    判别:若 handler 直调 kernel 判据(丢 locked_comp → D*=∅),对齐分消失,
    S4 顶部 鲜血阶梯(75)将压过 贝洛伯格星徽(pv 28)→ 本锁红。"""
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of,
    )
    from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
        MandateV1Strategy,
    )

    strat = MandateV1Strategy()
    cfg = _cfg()
    sess = strat.create_session(cfg)
    sess.prep_frame_class = 'none'   # 丢黑板帧:方向重估不跑,锁线以注入为准
    state_of(sess).v3_intention = IntentionState(locked_comp='希儿量子')
    match = SimpleNamespace(strategy=strat, session=sess)
    monkeypatch.setattr(test_context, 'cw_match', match)

    book = _FrameBook([object(), object()])
    book.options[id(book.frames[0])] = _opts_of(
        ['贝洛伯格星徽', '气氛组', '恢复生机'])
    book.options[id(book.frames[1])] = _opts_of(
        ['贝洛伯格星徽', '鲜血阶梯', '鲜血阶梯'])
    book.counts[id(book.frames[0])] = _counts_of([1, 1, 1])
    book.counts[id(book.frames[1])] = _counts_of([0, 0, 0])
    op, clicks = _make_op(test_context, monkeypatch, book)

    result = op.handle()

    assert result.is_success
    refresh_clicks = [c for c in clicks if c.y == _CNT_Y]
    assert [c.x for c in refresh_clicks] == [_CNT_XS[1] + _DX, _CNT_XS[2] + _DX], (
        '对齐槽 0 保护不刷,槽 1/2 照刷')
    assert _pts(clicks[-2:]) == [(460, _SELECT_Y), (_CONFIRM.x, _CONFIRM.y)], (
        '重决策 option_idx 应 = 对齐卡槽 0(D*① 经 decide_invest 传递;'
        '直调 kernel 丢参时对齐分消失,本断言红)')


def test_lock14_sequential_l1_guard_skips_slot(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 14(J5 自 kernel 锁 4 移入,承载位 = handler 槽序循环):L1={A,B} 帧
    刷 A(新卡为血)后 L1 收缩为 {B} → 循环到 B 跳过不点钮(逐步重估,静态
    kernel 单次调用不可表达)。fixture:槽 0 恢复生机/槽 1 气氛组 = L1 成员、
    槽 2 奋斗协议(血)= 帧级动作集含全部三槽(L1=2 无静态保护);槽 0 刷新
    新卡 = 不等价交换(血)→ L1 收缩 {1} → 槽 1 跳过、槽 2 照刷。"""
    book = _FrameBook([object(), object(), object()])
    book.options[id(book.frames[0])] = _opts_of(
        ['恢复生机', '气氛组', '奋斗协议'])
    book.options[id(book.frames[1])] = _opts_of(
        ['不等价交换', '气氛组', '奋斗协议'])
    book.options[id(book.frames[2])] = _opts_of(
        ['不等价交换', '气氛组', '鲜血阶梯'])
    book.counts[id(book.frames[0])] = _counts_of([1, 1, 1])
    book.counts[id(book.frames[1])] = _counts_of([0, 1, 1])
    book.counts[id(book.frames[2])] = _counts_of([0, 1, 0])
    strategy = _StubStrategy([
        PickEvent(option_idx=0, refresh=True, refresh_slots=(0, 1, 2),
                  reason='eval+refresh-suggest'),
        PickEvent(option_idx=2, reason='eval'),
    ])
    sess = _wire(test_context, monkeypatch, strategy)
    op, clicks = _make_op(test_context, monkeypatch, book)

    result = op.handle()

    assert result.is_success
    refresh_clicks = [c for c in clicks if c.y == _CNT_Y]
    assert _pts(refresh_clicks) == [(_CNT_XS[0] + _DX, _CNT_Y),
                                    (_CNT_XS[2] + _DX, _CNT_Y)], (
        f'槽 0 刷后 L1 收缩 → 槽 1 跳过不点钮,槽 2 照刷,实得 {refresh_clicks}')
    assert exec_state_of(sess)._invest_refresh_used_slots == {0, 2}
    assert strategy.calls[1] == ['不等价交换', '气氛组', '鲜血阶梯'], (
        '重决策用最终名集')


# ===== 观察通道 reader(cw_node_obs;纯函数,喂 fixture OCR list)=====
# reader 走 get_ocr_result_list(list 按检测逐条保留位置):策略屏三卡计数常态
# 同文(「刷新次数1」×3),map 按文本为键会收敛丢位——本组 fixture 同文多条
# 正是防回退到 map 形态的回归面。


def _ocr_list(items: list[tuple[str, int, int]]) -> list:
    """构造 mock ocr result list:每条 {data, center}(同文多条不收敛)。"""
    return [SimpleNamespace(data=t, center=SimpleNamespace(x=cx, y=cy))
            for t, cx, cy in items]


class _FakeCtx:
    def __init__(self, items: list[tuple[str, int, int]]) -> None:
        self.ocr_service = SimpleNamespace(
            get_ocr_result_list=lambda **kw: _ocr_list(items),
        )


def test_reader_strategy_counts_baseline_and_gray_zero() -> None:
    """reader:策略屏三组「刷新次数N」(同文 ×2 不收敛)→ 按 x 升序
    (count, cx, cy);灰置 0 可读(归档帧 card3_refreshed 实证形态);无冒号
    形态(在册 OCR 证据);他行(确认)不误判。"""
    ctx = _FakeCtx([
        ('刷新次数1', 477, 855), ('刷新次数1', 975, 855), ('刷新次数0', 1474, 855),
        ('确认', 978, 983),
    ])
    out = read_invest_refresh_counts(ctx, None, 'strategy')
    assert out == [(1, 477, 855), (1, 975, 855), (0, 1474, 855)], (
        '三卡计数按 x 升序,0 如实返回,确认不误判')


def test_reader_env_remain_counts_full_and_half_colon() -> None:
    """reader:env 屏单条「剩余次数:N」;全角/半角冒号都认(OCR 渲染不一)。"""
    ctx1 = _FakeCtx([('剩余次数：1', 772, 983), ('确认', 1082, 982)])
    assert read_invest_refresh_counts(ctx1, None, 'env') == [(1, 772, 983)]
    ctx2 = _FakeCtx([('剩余次数:2', 772, 983)])
    assert read_invest_refresh_counts(ctx2, None, 'env') == [(2, 772, 983)]


def test_reader_missing_returns_empty() -> None:
    """reader:读不到(无授予/非目标屏/OCR 漏)→ [](判定归调用方,失败安全);
    正则族分屏:策略文本不进 env 支。"""
    assert read_invest_refresh_counts(_FakeCtx([]), None, 'strategy') == []
    assert read_invest_refresh_counts(_FakeCtx([]), None, 'env') == []
    assert read_invest_refresh_counts(
        _FakeCtx([('刷新次数1', 477, 855)]), None, 'env') == []


def test_pair_counts_nearest_x_one_text_one_slot() -> None:
    """配对:x 就近、一条文本只配一槽;读缺(条数不足/距离超半槽距)落 None
    (调用方按无授予处理,fail-closed——防邻槽文本误配颠覆计数闸)。"""
    counts = [(1, 477, 855), (0, 1474, 855)]   # 中槽文本漏读形态
    out = pair_refresh_counts_to_slots(counts, list(_OPT_XS))
    assert out == [(1, 477, 855), None, (0, 1474, 855)], '就近 + 超容差 None'
    assert pair_refresh_counts_to_slots([], list(_OPT_XS)) == [None, None, None]


# ===== R6 环境屏 handler 执行链锁(invest-env 迭代 3.8;design §2.8 R6 行,
# 镜像策略侧 handler 锁 9-14 桩形。env 形差异 = 整组重掷单钮单计数(cw_node_obs
# 归档帧实证,与策略屏逐卡刷新不同构)+ 验效双通道按 design §2.8 定稿保留
# ——策略侧验效已拆(2026-09-10 裁定)不构成同构镜像面,链语义见
# cw_screen_invest_env._decide_and_act 链头注)=====
# 「剩余次数」文本中心(归档帧实测,与 reader 同源)→ 钮心 = x + _REFRESH_BTN_DX;
# 选卡 y = screen_info「区域-卡牌描述行」center.y=450;确认 = 「按钮-确认」
# center=(1082,982)(与 strategy 段同款真 screen_info area)。
_ENV_CNT_X, _ENV_CNT_Y = 772, 983
_EDX = CwScreenInvestEnv._REFRESH_BTN_DX
_ESELECT_Y = 450
_ECONFIRM = (1082, 982)


def _env_opts_of(names: list[str]) -> list[tuple[str, int]]:
    """env 屏候选桩:(名字, center-x) 左→右(与 _read_options 输出同形)。"""
    return [(n, _OPT_XS[i]) for i, n in enumerate(names)]


def _wire_env(test_context, monkeypatch: pytest.MonkeyPatch,
              strategy: object) -> SimpleNamespace:
    """接线 env 局容器(桩 session 即可,board_state_of 对裸对象惰性建)。"""
    sess = SimpleNamespace()
    match = SimpleNamespace(strategy=strategy, session=sess)
    monkeypatch.setattr(test_context, 'cw_match', match)
    return sess


def _make_env_op(test_context, monkeypatch: pytest.MonkeyPatch,
                 book: _FrameBook) -> tuple[CwScreenInvestEnv, list[Point]]:
    """构造被测 env op:观察帧/截图走帧簿,计数读/点击/确认/台账全桩化
    (零真实 IO;safe_click/confirm 走 env 模块命名空间桩,选卡 y 用真
    screen_info area——与既有 env op 测试 E5/obs-arch 同款桩面)。"""
    op = CwScreenInvestEnv(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: book.next_frame())
    # 旧路径观察桩:入口门恒过 + 稳定帧 = 帧 0(经帧簿消费,与生产帧序同构:
    # 观察帧 → 链内每次刷后重读各弹一帧)。
    monkeypatch.setattr(
        op, '_observe_frame',
        lambda: (True, list(book.options.get(id(book.frames[0]), [])),
                 book.next_frame()))
    monkeypatch.setattr(op, '_read_options',
                        lambda screen: book.options.get(id(screen), []))
    monkeypatch.setattr(op, '_refresh_node_ledger', lambda: None)
    monkeypatch.setattr(env_mod.time, 'sleep', lambda s: None)

    def _fake_counts(ctx, screen, kind):
        book.read_calls.append(kind)
        return book.counts.get(id(screen), [])

    monkeypatch.setattr(env_mod, 'read_invest_refresh_counts', _fake_counts)
    monkeypatch.setattr(env_mod, 'emit_overlay_confirm',
                        lambda op, confirm_point, entry_keyword, tag:
                        (clicks.append(confirm_point),
                         SimpleNamespace(is_success=True))[1])
    clicks: list[Point] = []
    monkeypatch.setattr(env_mod, 'safe_click',
                        lambda op, point, *, tag: clicks.append(point))
    return op, clicks


class _EnvStubStrategy:
    """decide_invest 记录桩(kind='env' 断言;按序弹出预置 PickEvent)。"""

    def __init__(self, picks: list[PickEvent]) -> None:
        self.picks = list(picks)
        self.calls: list[list[str]] = []

    def decide_invest(self, kind, options, state, session, config) -> PickEvent:
        assert kind == 'env'
        self.calls.append(list(options))
        return self.picks.pop(0) if self.picks else PickEvent(
            option_idx=0, reason='stub-exhausted')


def test_r6a_count_gate_blocks_refresh(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """R6·计数现读闸:计数 0 / 读缺 → 零刷新点击、零决策重放(闸 = 画面
    现读,观察通道转正为执行闸的唯一授权源;读缺按无授予处理,失败安全),
    refresh_slots 非空也不掷,链直落现状选卡路径。"""
    names = ['狼狩概念股', '战力提升', '成功经验']
    pick = PickEvent(option_idx=0, refresh=True, refresh_slots=(0,),
                     reason='env-eval+refresh-suggest')
    for counts in ([(0, _ENV_CNT_X, _ENV_CNT_Y)], []):   # 计数 0 / 读缺
        book = _FrameBook([object()])
        book.options[id(book.frames[0])] = _env_opts_of(names)
        book.counts[id(book.frames[0])] = counts
        strategy = _EnvStubStrategy([pick])
        _wire_env(test_context, monkeypatch, strategy)
        op, clicks = _make_env_op(test_context, monkeypatch, book)

        result = op.handle()

        assert result.is_success
        assert strategy.calls == [names], '恰一次决策'
        assert _pts(clicks) == [(_OPT_XS[0], _ESELECT_Y), _ECONFIRM], (
            f'counts={counts}:零刷新击,直落选卡+确认,实得 {clicks}')


def test_r6b_dual_channel_fail_stops(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """R6·验效双输停:点击后计数未扣减 ∧ 名集未变 → 双输即停不重试
    (恰一次刷新击),名集未变不重决策(canary 支不消费),按原决策选卡。"""
    names = ['狼狩概念股', '战力提升', '成功经验']
    book = _FrameBook([object(), object()])
    book.options[id(book.frames[0])] = _env_opts_of(names)
    book.options[id(book.frames[1])] = _env_opts_of(names)   # 刷后名集未变
    book.counts[id(book.frames[0])] = [(1, _ENV_CNT_X, _ENV_CNT_Y)]
    book.counts[id(book.frames[1])] = [(1, _ENV_CNT_X, _ENV_CNT_Y)]   # 计数未扣
    strategy = _EnvStubStrategy([
        PickEvent(option_idx=1, refresh=True, refresh_slots=(0,),
                  reason='env-eval+refresh-suggest'),
        PickEvent(option_idx=2, reason='canary'),   # 误重决策即消费 → 断言红
    ])
    _wire_env(test_context, monkeypatch, strategy)
    op, clicks = _make_env_op(test_context, monkeypatch, book)

    result = op.handle()

    assert result.is_success
    refresh_clicks = [c for c in clicks if c.y == _ENV_CNT_Y]
    assert _pts(refresh_clicks) == [(_ENV_CNT_X + _EDX, _ENV_CNT_Y)], (
        f'双输即停恰一次刷新击(不重试),实得 {refresh_clicks}')
    assert len(strategy.calls) == 1, '名集未变不重决策(canary 不消费)'
    assert _pts(clicks[-2:]) == [(_OPT_XS[1], _ESELECT_Y), _ECONFIRM], (
        '按原决策选卡+确认')


def test_r6c_chain_redecide_final_names(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """R6·端到端主链:计数授权 → 文本锚定点击 → 验效(计数扣减权威)→
    重分类(重决策用最终名集)→ 新动作集空(无零价值槽)停链 → 按重决策
    选卡+确认。计数通道 = 'env'(同源 reader,不串策略轴)。"""
    book = _FrameBook([object(), object()])
    book.options[id(book.frames[0])] = _env_opts_of(
        ['狼狩概念股', '战力提升', '成功经验'])
    book.options[id(book.frames[1])] = _env_opts_of(
        ['彩虹时代', '战力提升', '成功经验'])
    book.counts[id(book.frames[0])] = [(1, _ENV_CNT_X, _ENV_CNT_Y)]
    book.counts[id(book.frames[1])] = [(0, _ENV_CNT_X, _ENV_CNT_Y)]
    strategy = _EnvStubStrategy([
        PickEvent(option_idx=0, refresh=True, refresh_slots=(0,),
                  reason='env-eval+refresh-suggest'),
        PickEvent(option_idx=1, reason='env-eval'),
    ])
    _wire_env(test_context, monkeypatch, strategy)
    op, clicks = _make_env_op(test_context, monkeypatch, book)

    result = op.handle()

    assert result.is_success
    refresh_clicks = [c for c in clicks if c.y == _ENV_CNT_Y]
    assert _pts(refresh_clicks) == [(_ENV_CNT_X + _EDX, _ENV_CNT_Y)], (
        f'文本锚定刷新击一次,实得 {refresh_clicks}')
    assert set(book.read_calls) == {'env'}, '计数读走 env 通道(不串策略轴)'
    assert strategy.calls == [['狼狩概念股', '战力提升', '成功经验'],
                              ['彩虹时代', '战力提升', '成功经验']], (
        '重决策用最终名集(掷后重分类)')
    assert _pts(clicks[-2:]) == [(_OPT_XS[1], _ESELECT_Y), _ECONFIRM], (
        '按重决策选卡(idx1 彩虹时代)+确认')


def test_r6d_name_change_fallback_rescues_chain(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """R6·验效兜底通道:刷后计数读缺但卡名已变 → 名集变化兜底验效成立,
    重分类照走;下一轮闸因计数读缺关闭(无授权不续掷)→ 恰一次刷新击。"""
    book = _FrameBook([object(), object()])
    book.options[id(book.frames[0])] = _env_opts_of(
        ['狼狩概念股', '战力提升', '成功经验'])
    book.options[id(book.frames[1])] = _env_opts_of(
        ['彩虹时代', '战力提升', '成功经验'])
    book.counts[id(book.frames[0])] = [(1, _ENV_CNT_X, _ENV_CNT_Y)]
    book.counts[id(book.frames[1])] = []   # 刷后计数读缺
    strategy = _EnvStubStrategy([
        PickEvent(option_idx=0, refresh=True, refresh_slots=(0,),
                  reason='env-eval+refresh-suggest'),
        PickEvent(option_idx=0, refresh=True, refresh_slots=(0,),
                  reason='canary'),   # 若误续掷会消费此支再点 → 断言红
        PickEvent(option_idx=1, reason='eval'),
    ])
    _wire_env(test_context, monkeypatch, strategy)
    op, clicks = _make_env_op(test_context, monkeypatch, book)

    result = op.handle()

    assert result.is_success
    refresh_clicks = [c for c in clicks if c.y == _ENV_CNT_Y]
    assert _pts(refresh_clicks) == [(_ENV_CNT_X + _EDX, _ENV_CNT_Y)], (
        f'计数读缺关闸,恰一次刷新击,实得 {refresh_clicks}')
    assert len(strategy.calls) == 2, '名集变化兜底验效成立,重分类照走'
    assert _pts(clicks[-2:]) == [(_OPT_XS[0], _ESELECT_Y), _ECONFIRM], (
        '按重分类决策(idx0)+确认')


def test_r6e_redecide_via_flow_entry_g1(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """R6·最终重决策入口 = G1(镜像策略侧锁 13 判别形态):掷后重决策经
    flow.decide_invest(D*① 三参只在此解析)。锁线帧(D*① = 景元仙舟)刷
    零价值槽(狼狩概念股)后,新卡 彩虹时代(裸 72):handler 若直调 kernel
    判据(丢 locked_comp → D*=∅)则彩虹时代压过仙舟概念股(裸 48)→ 选卡
    落槽 1,本锁红;经 flow 入口 D* floor 78 胜出 → 选卡落槽 0。"""
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of,
    )
    from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
        MandateV1Strategy,
    )

    strat = MandateV1Strategy()
    sess = strat.create_session(_cfg())
    sess.prep_frame_class = 'none'   # 丢黑板帧:方向重估不跑,锁线以注入为准
    state_of(sess).v3_intention = IntentionState(locked_comp='景元仙舟')

    calls: list[tuple[str, list[str]]] = []

    class _CountingProxy:
        """decide_invest 透传记录壳(kind/名集记账,行为零改)。"""

        def __init__(self, inner: MandateV1Strategy) -> None:
            self._inner = inner

        def decide_invest(self, kind, options, bs, session, config):
            calls.append((kind, list(options)))
            return self._inner.decide_invest(kind, options, bs, session, config)

    match = SimpleNamespace(strategy=_CountingProxy(strat), session=sess)
    monkeypatch.setattr(test_context, 'cw_match', match)

    book = _FrameBook([object(), object()])
    book.options[id(book.frames[0])] = _env_opts_of(
        ['仙舟概念股', '狼狩概念股', '战力提升'])
    book.options[id(book.frames[1])] = _env_opts_of(
        ['仙舟概念股', '彩虹时代', '战力提升'])
    book.counts[id(book.frames[0])] = [(1, _ENV_CNT_X, _ENV_CNT_Y)]
    book.counts[id(book.frames[1])] = [(0, _ENV_CNT_X, _ENV_CNT_Y)]
    op, clicks = _make_env_op(test_context, monkeypatch, book)

    result = op.handle()

    assert result.is_success
    refresh_clicks = [c for c in clicks if c.y == _ENV_CNT_Y]
    assert _pts(refresh_clicks) == [(_ENV_CNT_X + _EDX, _ENV_CNT_Y)], (
        f'仅零价值槽(狼狩概念股)掷一次,实得 {refresh_clicks}')
    assert [k for k, _n in calls] == ['env', 'env'], (
        f'恰两次决策且均经 decide_invest(env) 入口,实得 {calls}')
    assert calls[1][1] == ['仙舟概念股', '彩虹时代', '战力提升'], (
        '重决策用最终名集')
    assert _pts(clicks[-2:]) == [(_OPT_XS[0], _ESELECT_Y), _ECONFIRM], (
        '重决策 option_idx 应 = 仙舟概念股槽 0(D* floor 78 压过彩虹时代 72;'
        '直调 kernel 丢 locked_comp 时彩虹时代胜出落槽 1,本断言红)')
