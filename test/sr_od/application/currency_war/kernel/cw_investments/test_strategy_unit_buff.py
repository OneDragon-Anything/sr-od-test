"""策略源 UNIT_BUFF 族战力类零响应登记锁,逐卡(cw_investments 分目录
镜像;族模式卡 = 「全队的希望」/同目录 test_strategy_zanmei_entry.py
装备党同代形)。

星魂升华(id 253101)测试面依据 = 原稿锁面
本文件锁面申报(定稿,REVIEW 无需用户决定 5/5)§4 锁面
(卡面官方原文:「本局游戏中，我方前台角色的星魂提高1阶」):

- 条目锁(锁 1):UNIT_BUFF 零响应登记形 / id 253101 / trigger
  PLANE_START 占位形(无离散触发事件,对齐 _portal_placeholder_spec
  环境源先例)× WHILE_HELD × UnitBuffRef 且 effect_text 与卡面单一源
  对拍 / duties 三位全 False / pending False / 现金分支 fail-closed
  (估值恒 (0.0, False));
- 登记链锁 + 桥负锁(锁 2):获得链既有只登记不写状态的实现分支自动入册(register_strategy
  → by_source 含本条)、注册照常;UnitBuffRef 无任何写状态副本字段 → 全部
  桥鸭子类型读取(duck typing)缺省守卫 no-op(burst / 位面段补发 / 板面重写 / 节点边界 /
  容量直写五桥,登记期零 Field 行);on_strategy_gained 未收录安静
  返回零效果串;session=None 支登记跳过、注册照常;
- 绑定不绑锁(锁 3):泛用养成数值(前台角色星魂 +1 阶)不入显式绑定表
  (登记判据:效果引用阵容专属机制/召唤物/星徽/赠 key 角色才绑),公开
  绑定读端 fail-closed 空元组——把现状固化为设计约定,防未来误绑;
- 封闭集不扩锁(锁 4):本卡不入 PICK_INVEST_EFFECTS(入集 = 实现错误,
  既有封闭集断言在 test_gain_chain.py 原样保留即第二道防线)+ 不入商店
  停机钩子名单(卡面无采集需求,零响应 buff 非停机对象)。

幸运闪避EX(id 351701)测试面依据 = 同原稿锁面(定稿 v1.2)§4 五锁面(卡面官方原文:「我方小队获得25%幸运
一击率，受到敌人攻击时，有等同于30%幸运一击率的概率使受到的伤害变为
1。」clause 1 全队幸运一击率直增 + clause 2 受击概率伤害变换,均战斗
内游戏侧自算 bot 零响应):条目形状(锁 1)/单一源对拍(锁 2)/封闭集不扩
(锁 3)/绑定隔离(锁 4)/估值停机双隔离(锁 5)与星魂升华同形;同 payload
形的获得链登记与桥 no-op 行为面由星魂升华锁承载,不重测。

羁绊的力量(id 351801)测试面依据 = 同原稿锁面(定稿 v1.2)§4 五锁面(卡面官方原文:「每有一个已激活的非
独立羁绊，小队就会获得5%伤害增幅和3%伤害减免。」羁绊计数线性缩放 +
双轴[伤害增幅/伤害减免]独立定值并列非跨轴派生,计数判定与数值全游戏
侧自算 bot 零响应):五锁与幸运闪避EX 同形;同 payload 形的获得链登记
与桥 no-op 行为面由星魂升华锁承载,不重测。

调饮专家:加拉赫(id 360501)测试面依据 = 同原稿锁面(定稿,判定无需裁定·可实现)§4 五锁面(卡面官方原文:
「获得装备着【绝对热量】的专家顾问【加拉赫】，并使其在本局游戏中加入
商店。加拉赫行动时，为我方全体恢复3点能量并触发【绝对热量】的生命回复
效果。」顾问授予族三条效果条目分治:效果条目1 顾问授予+入商店 = GRANTS advisor=True
条目已登记零动作;效果条目2 佩戴绝对热量零建模;效果条目3 行动触发双效果 = 触发面/
效果面/联动面三盲零响应登记):payload 单一源对拍(锁 1)/条目构造七字段
(锁 2)/存量负向 GRANTS 计数与 PICK 闭集不变(锁 3,存量计数锁与键集
闭集现值基准在 test_invest_strategy.py / test_gain_chain.py 原样保留即第二
道防线)/估值零计分带 gs 实参(锁 4)/登记面现值钉死(锁 5,赠 key 专家
顾问显式绑定行已登记,与族内三卡「泛用不绑」形态相反,钉现值防漂移)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    SOURCE_STRATEGY,
    DurationKind,
    EffectKind,
    TriggerKind,
    UnitBuffRef,
    apply_board_rewrite,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    apply_effect_burst_grant,
    apply_effect_plane_refire_grant,
    grant_effect_node_refresh_balance,
    project_effect_capacity,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    _STRATEGY_BINDINGS_EXPLICIT,
    INVESTMENT_STRATEGIES,
    STRATEGY_BINDINGS,
    STRATEGY_EFFECTS,
    STRATEGY_GRANTS,
    strategy_bindings,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    strategy_economy_value,
)

_CARD = '星魂升华'
_CID = '253101'

_CARD_EX = '幸运闪避EX'
_CID_EX = '351701'

_CARD_JB = '羁绊的力量'
_CID_JB = '351801'

_CARD_TY = '调饮专家:加拉赫'
_CID_TY = '360501'

_SIG_LOGIC = ChannelSig(family='logic_action', actor='CwGainChain',
                        mode='compute')


def _make_gs() -> GameState:
    """最小观测面(bench/equips 观察容量默认 9,供容量桥负锁读数)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=ChannelSig(family='obs', actor='CwScreenPrep'))
    gs.observe(gs.equips, [],
               sig=ChannelSig(family='obs', actor='CwScreenPrep'))
    return gs


def test_xinghun_entry_registered() -> None:
    """条目锁(锁 1):UNIT_BUFF 零响应登记形;五元组逐位 + id 对拍;
    duties 三位全 False;pending False(数值/位置/对象全卡面明文,无
    二义冻结面);构建校验(孤儿键/id 双匹配)import 期已过。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == _CID, 'id 对拍'
    assert spec.name == _CARD
    assert spec.trigger is TriggerKind.PLANE_START, '占位形(无离散触发)'
    assert spec.duration is DurationKind.WHILE_HELD, '持有期绑定'
    assert spec.category is EffectKind.UNIT_BUFF, 'category = UNIT_BUFF'
    assert isinstance(spec.payload, UnitBuffRef), '载荷 = UnitBuffRef'
    assert spec.duration_nodes == 0 and spec.duration_uses == 0, \
        'WHILE_HELD 无余期计数器(余期播种双 None)'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_xinghun_effect_text_single_source() -> None:
    """锁 1 续:effect_text 与卡面单一源对拍(经 PLAZA_AUGMENTS 数据面
    表达式,版本更新改文自动跟随;id 漂移 = StopIteration import 即炸,
    本条目存活即证)。"""
    assert STRATEGY_EFFECTS[_CARD].payload.effect_text \
        == INVESTMENT_STRATEGIES[_CARD].effect, \
        'effect_text 单一源对拍(= base 注册表 .effect)'


def test_xinghun_cash_fail_closed() -> None:
    """现金分支锁(锁 1 尾):无 STRATEGY_ECONOMY 条目 → 估值 fail-closed
    (0.0, False)(战力类不进经济模型,防未来误加 STRATEGY_ECONOMY 条目
    或通道误开)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert strategy_economy_value(_CARD, gs) == (0.0, False)


def test_xinghun_gain_chain_register_and_bridges_noop() -> None:
    """登记链锁 + 桥负锁(锁 2):session 在场选卡 → 注册入表 + 账本
    登记(register_strategy,by_source 含本条);UnitBuffRef 无写状态副本
    字段 → 五桥鸭子类型读取缺省守卫 no-op,登记期零 Field 行;on_strategy_
    gained 未收录安静返回零效果串;session=None 支登记跳过、注册照常。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), _CARD, rand=False, sig=_SIG_LOGIC)
    assert gs.active_strategies.value == [_CARD], '注册入表'
    entries = gs.effects.by_source(SOURCE_STRATEGY)
    assert [e.spec.name for e in entries] == [_CARD], \
        'register_strategy 入册(获得链只登记不写状态的实现分支既有链,零新代码)'
    assert entries[0].spec.id == _CID
    assert gs.free_refresh_left.value is None, \
        'burst/位面段补发桥 no-op(零 Field 行)'
    seq_after_gain = gs.write_seq   # 入册本身占账本写;五桥零写以此为基
    spec = entries[0].spec
    apply_effect_burst_grant(gs, spec)
    apply_effect_plane_refire_grant(gs, spec)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, 'burst/位面段补发桥显式调用零写'
    assert apply_board_rewrite(gs, spec) is None, '板面重写桥 no-op'
    assert gs.write_seq == seq_after_gain
    grant_effect_node_refresh_balance(gs)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, '节点边界桥 no-op'
    project_effect_capacity(gs)
    assert gs.write_seq == seq_after_gain, '容量直写桥 no-op'
    assert gs.bench.value.capacity == 9, '容量默认值未被改写'
    assert on_strategy_gained(gs, _CARD, rand=False, sig=_SIG_LOGIC) == (), \
        '未收录 PICK 安静零效果串'
    # session=None 支:登记跳过、注册照常(登记分支同型断言)
    gs2 = _make_gs()
    gain_invest_strategy(gs2, None, _CARD, rand=False, sig=_SIG_LOGIC)
    assert gs2.active_strategies.value == [_CARD], '注册照常'
    assert gs2.effects.by_source(SOURCE_STRATEGY) == [], 'session=None 跳过'


def test_xinghun_no_faction_binding() -> None:
    """绑定不绑锁(锁 3):泛用养成数值不入显式绑定表(登记判据直辖,
    同形泛用卡全队的希望/独狼/团队力量·金同不在表);公开绑定读端对
    表外卡返回默认空元组(fail-closed,方向分 0)。"""
    assert _CARD not in _STRATEGY_BINDINGS_EXPLICIT, '显式绑定表零触碰'
    assert _CARD not in STRATEGY_BINDINGS, '派生绑定表零触碰'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_xinghun_not_in_pick_and_watch_names() -> None:
    """封闭集不扩 + 停机钩子零成员(锁 4):零响应登记非效果体卡,不入
    PICK(入集 = 实现错误;既有封闭集断言 test_gain_chain.py 原样保留
    即第二道防线);卡面无采集需求,不入商店停机钩子名单(名单访问形 =
    类限定 ClassVar)。"""
    assert _CARD not in set(PICK_INVEST_EFFECTS), '本卡禁入 PICK 封闭集'
    assert _CARD not in CwScreenPrep._SPEC_INVEST_WATCH_NAMES, \
        '本卡不入停机钩子名单'


def test_xingyun_shanbi_entry_registered() -> None:
    """幸运闪避EX 条目锁(锁 1):UNIT_BUFF 零响应登记形;五元组逐位 +
    id 对拍;duties 三位全 False;pending False(概率读法/受击粒度/变换
    边界判读申报制不冻结,零响应下两读法 bot 行为恒同);构建校验
    import 期已过(表长按开工基线 +1 语义,无绝对数断言)。"""
    spec = STRATEGY_EFFECTS[_CARD_EX]
    assert spec.id == _CID_EX, 'id 对拍'
    assert spec.name == _CARD_EX
    assert spec.trigger is TriggerKind.PLANE_START, '占位形(无离散触发)'
    assert spec.duration is DurationKind.WHILE_HELD, '持有期绑定'
    assert spec.category is EffectKind.UNIT_BUFF, 'category = UNIT_BUFF'
    assert isinstance(spec.payload, UnitBuffRef), '载荷 = UnitBuffRef'
    assert spec.duration_nodes == 0 and spec.duration_uses == 0, \
        'WHILE_HELD 无余期计数器'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_xingyun_shanbi_effect_text_single_source() -> None:
    """幸运闪避EX 单一源对拍锁(锁 2):effect_text 与 base 注册表卡面
    原文对拍(payload 表达式经 PLAZA_AUGMENTS id 键取数,禁字面量第二
    源;版本更新改文自动跟随,id 漂移 = StopIteration import 即炸)。"""
    assert STRATEGY_EFFECTS[_CARD_EX].payload.effect_text \
        == INVESTMENT_STRATEGIES[_CARD_EX].effect, \
        'effect_text 单一源对拍(= base 注册表 .effect)'


def test_xingyun_shanbi_cash_fail_closed() -> None:
    """幸运闪避EX 现金分支锁(锁 5 前半):无 STRATEGY_ECONOMY 条目 →
    估值 fail-closed (0.0, False)(战力类不进经济模型,防未来误加
    STRATEGY_ECONOMY 条目或通道误开)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert strategy_economy_value(_CARD_EX, gs) == (0.0, False)


def test_xingyun_shanbi_no_faction_binding() -> None:
    """幸运闪避EX 绑定不绑锁(锁 4):全队泛用数值直增不入显式绑定表
    (登记判据:效果引用阵容专属机制/召唤物/星徽/赠 key 角色才绑);公开
    绑定读端 fail-closed 空元组。"""
    assert _CARD_EX not in _STRATEGY_BINDINGS_EXPLICIT, '显式绑定表零触碰'
    assert _CARD_EX not in STRATEGY_BINDINGS, '派生绑定表零触碰'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD_EX]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_xingyun_shanbi_not_in_pick_and_watch_names() -> None:
    """幸运闪避EX 封闭集不扩 + 停机钩子零成员(锁 3 + 锁 5 后半):零响应
    登记非效果体卡不入 PICK(入集 = 实现错误);卡面无采集需求,不入商店
    停机钩子名单(名单访问形 = 类限定 ClassVar)。"""
    assert _CARD_EX not in set(PICK_INVEST_EFFECTS), '本卡禁入 PICK 封闭集'
    assert _CARD_EX not in CwScreenPrep._SPEC_INVEST_WATCH_NAMES, \
        '本卡不入停机钩子名单'


def test_jiban_entry_registered() -> None:
    """羁绊的力量 条目锁(锁 1):UNIT_BUFF 零响应登记形;五元组逐位 +
    id 对拍;duties 三位全 False;pending False(计数基础/作用对象/双轴
    数值全卡面明文,「已激活」口径游戏侧定义零响应消费端不构成登记二义);
    构建校验 import 期已过(表长按开工基线 +1 语义,无绝对数断言)。"""
    spec = STRATEGY_EFFECTS[_CARD_JB]
    assert spec.id == _CID_JB, 'id 对拍'
    assert spec.name == _CARD_JB
    assert spec.trigger is TriggerKind.PLANE_START, '占位形(无离散触发)'
    assert spec.duration is DurationKind.WHILE_HELD, '持有期绑定'
    assert spec.category is EffectKind.UNIT_BUFF, 'category = UNIT_BUFF'
    assert isinstance(spec.payload, UnitBuffRef), '载荷 = UnitBuffRef'
    assert spec.duration_nodes == 0 and spec.duration_uses == 0, \
        'WHILE_HELD 无余期计数器'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_jiban_effect_text_single_source() -> None:
    """羁绊的力量 单一源对拍锁(锁 2):effect_text 与 base 注册表卡面
    原文对拍(payload 表达式经 PLAZA_AUGMENTS id 键取数[在码族内多数形],
    禁字面量第二源;版本更新改文自动跟随,id 漂移 = StopIteration import
    即炸)。"""
    assert STRATEGY_EFFECTS[_CARD_JB].payload.effect_text \
        == INVESTMENT_STRATEGIES[_CARD_JB].effect, \
        'effect_text 单一源对拍(= base 注册表 .effect)'


def test_jiban_cash_fail_closed() -> None:
    """羁绊的力量 现金分支锁(锁 5 前半):无 STRATEGY_ECONOMY 条目 →
    估值 fail-closed (0.0, False)(战力类不进经济模型,防未来误加
    STRATEGY_ECONOMY 条目或通道误开)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert strategy_economy_value(_CARD_JB, gs) == (0.0, False)


def test_jiban_no_faction_binding() -> None:
    """羁绊的力量 绑定不绑锁(锁 4):泛用计数 buff(全队增幅/减免,无
    任何阵营/召唤物/星徽/具名角色点名)不入显式绑定表(登记判据直辖);
    公开绑定读端 fail-closed 空元组(方向分 0)。"""
    assert _CARD_JB not in _STRATEGY_BINDINGS_EXPLICIT, '显式绑定表零触碰'
    assert _CARD_JB not in STRATEGY_BINDINGS, '派生绑定表零触碰'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD_JB]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_jiban_not_in_pick_and_watch_names() -> None:
    """羁绊的力量 封闭集不扩 + 停机钩子零成员(锁 3 + 锁 5 后半):零响应
    登记非效果体卡不入 PICK(入集 = 实现错误);卡面无采集需求,不入商店
    停机钩子名单(名单访问形 = 类限定 ClassVar)。"""
    assert _CARD_JB not in set(PICK_INVEST_EFFECTS), '本卡禁入 PICK 封闭集'
    assert _CARD_JB not in CwScreenPrep._SPEC_INVEST_WATCH_NAMES, \
        '本卡不入停机钩子名单'


def test_tiaoyin_entry_registered() -> None:
    """调饮专家:加拉赫 条目构造锁(锁 2):UNIT_BUFF 零响应登记形;七字段
    逐位(id/name/trigger=PLANE_START 占位形/duration=WHILE_HELD/category=
    UNIT_BUFF/duties 全空/pending=False);构建校验(孤儿键/id 双匹配)
    import 期已过。"""
    spec = STRATEGY_EFFECTS[_CARD_TY]
    assert spec.id == _CID_TY, 'id 对拍'
    assert spec.name == _CARD_TY
    assert spec.trigger is TriggerKind.PLANE_START, '占位形(无离散触发)'
    assert spec.duration is DurationKind.WHILE_HELD, '持有期绑定'
    assert spec.category is EffectKind.UNIT_BUFF, 'category = UNIT_BUFF'
    assert isinstance(spec.payload, UnitBuffRef), '载荷 = UnitBuffRef'
    assert spec.duration_nodes == 0 and spec.duration_uses == 0, \
        'WHILE_HELD 无余期计数器'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_tiaoyin_effect_text_single_source() -> None:
    """调饮专家:加拉赫 payload 单一源锁(锁 1):effect_text 与 base 注册表
    卡面原文对拍(payload 表达式经 PLAZA_AUGMENTS id 键取数,禁字面量第二
    源;版本更新改文自动跟随,id 漂移 = StopIteration import 即炸)。"""
    assert STRATEGY_EFFECTS[_CARD_TY].payload.effect_text \
        == INVESTMENT_STRATEGIES[_CARD_TY].effect, \
        'effect_text 单一源对拍(= base 注册表 .effect)'


def test_tiaoyin_cash_fail_closed() -> None:
    """调饮专家:加拉赫 估值零计分锁(锁 4):无 STRATEGY_ECONOMY 条目 →
    strategy_economy_value 带 gs 实参返回 (0.0, False)(战力类不进经济
    模型,防未来误加 STRATEGY_ECONOMY 条目或通道误开;签名 (name, gs),
    缺 gs 实参非合法调用形)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert strategy_economy_value(_CARD_TY, gs) == (0.0, False)


def test_tiaoyin_registry_pins() -> None:
    """调饮专家:加拉赫 登记面现值钉死锁(锁 5 + 效果条目1 前提):赠 key 专家
    顾问(加拉赫)显式绑定行已登记,公开绑定读端现值 = (frozenset(),
    frozenset({'加拉赫'}))(零新增,只锁不动——与族内三卡「泛用不绑」
    形态相反,本卡绑定系顾问授予结构化面既有登记);效果条目1 零动作前提 =
    GRANTS advisor=True 条目已登记(获得链 advisor 道解锁入商店的登记面
    基础),逐字段钉现值防漂移。"""
    assert _CARD_TY in _STRATEGY_BINDINGS_EXPLICIT, '显式绑定行已登记(零新增)'
    assert STRATEGY_BINDINGS[_CARD_TY] == (frozenset(), frozenset({'加拉赫'})), \
        '绑定现值不动'
    grant = STRATEGY_GRANTS[_CARD_TY]
    assert grant.advisor is True, '效果条目1 前提:advisor 型授予(解锁入商店链)'
    assert grant.chars_immediate == ('加拉赫',), '授予对象 = 加拉赫'


def test_tiaoyin_not_in_pick_and_watch_names() -> None:
    """调饮专家:加拉赫 存量负向锁(锁 3 卡级面):零响应登记非效果体卡不入
    PICK(入集 = 实现错误;顾问授予计数锁与 PICK 键集闭集存量断言在
    test_invest_strategy.py / test_gain_chain.py 原样保留即第二道防线,本卡
    对两表零触碰);卡面无采集需求,不入商店停机钩子名单(名单访问形 =
    类限定 ClassVar)。"""
    assert _CARD_TY not in set(PICK_INVEST_EFFECTS), '本卡禁入 PICK 封闭集'
    assert _CARD_TY not in CwScreenPrep._SPEC_INVEST_WATCH_NAMES, \
        '本卡不入停机钩子名单'
