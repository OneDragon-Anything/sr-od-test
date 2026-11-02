"""策略延时发放入队原语与登记腿测试(镜像 src = kernel/cw_gain_chain.py
的 queue_delayed_strategy_grant + kernel/cw_gain_effects.py 的
_make_delayed_grant_effect 派生条目)。

测试面依据 = 迭代设计 designs/T-106-rencai-jili.md §4 锁 2(登记腿
2+2 条)+ 锁 5(live 链登记;发放原语无 live 调用点由模块边界承担——
kernel 不 import sim,不设静态扫描锁)+ T-107 展开卡批(designs/
T-107-rencai-jili-plus.md §4 锁 2:人才激励+ 登记腿 @3 直断,原
monkeypatch 形态测随真注册转直测):
- 拿卡人才激励 → equips 尾部 +1 员工投影仪 ∧ 队列 (('人才激励', 4),)
  ∧ 双效果串(equip_grant:strategy_grant_scheduled);人才激励+ 同构
  @3(姊妹双卡逐名独立构造);
- 许诺特权 = 延时-only 单腿登记腿(卡文纯延时单句):效果串单枚
  strategy_grant_scheduled,零即时腿(反向锁错发形态);
- 先亏后盈 = count 循环入队(数量 2 首例):队列双条目 + 效果串两枚
  + kernel 侧零 hp 写(T-144 批扩面);
- 好运令牌·银 = 延时-only 单腿展开卡(发放物与卡名异名首例):队列
  恰 (('好运令牌·银', 3),) ∧ 效果串单枚 strategy_grant_scheduled:
  好运令牌@3(物名载体直断)∧ 零即时腿;equips 未观察域效果串仍单枚
  (两腿工厂同域会多枚 equip_grant placed=False 串,反证载体分流)+
  两腿成员集负成员断言(T-146 批扩面);
- 是钻石总会发光 = 延时-only 单腿展开卡 + 族内首个随机发放行(designs/
  T-148-shizuanshi-zonghui-faguang.md §4 锁 2):队列恰 (('是钻石总会
  发光', 2),) ∧ 效果串单枚 choice-set 形 strategy_grant_scheduled:
  红钻|蓝钻@2(封闭集竖线连接直断)∧ 零即时腿 ∧ 登记 rng 零消耗
  (拿卡前后 rng 状态逐位相等,预掷被否的行为证据)∧ equips 未观察域
  载体分流直断 + 两腿成员集负成员(T-148 批扩面);
- equips 未观察 → 即时腿拒落零写 placed=False、入队腿照写;
- 未登记策略卡(表外名 + 在册无腿卡)零写;
- 回收计划 = 组合登记行入队腿(designs/T-237-huishou-jihua.md §4 锁 6:
  随机腿×延时入队腿,类别池效果串池标记形直断 + rng 恰 1 次同序对拍);
- live 落地形态(gain_invest_strategy 同函数,session=None 直构)队列
  照写,零世界发放动作。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='CwGainChain',
                      mode='compute')


def _gs(equips: list[str] | None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if equips is not None:
        gs.write_logic(gs.equips, list(equips), produced_by='test-seed',
                       evidence='t:equips', sig=_lsig())
    gs.prep_anchored = True   # 置闩:登记 = 确定事件,锁确定面写通道
    return gs


def test_pick_rencai_jili_instant_equip_and_queue() -> None:
    """登记腿主条(handler 分派形态):拿卡人才激励 → equips 尾部 +1
    员工投影仪(write_logic 确定面,rand=False 具名发放)+ 队列恰
    (('人才激励', 4),)(元素 = (触发卡规范名, 登记节拍))+ 双效果串
    equip_grant(placed=True)/ strategy_grant_scheduled:员工投影仪@4。"""
    gs = _gs(equips=[])
    effects = on_strategy_gained(gs, '人才激励', rand=False, sig=_lsig(),
                                 rng=random.Random(0))
    assert effects == ('equip_grant:员工投影仪(placed=True)',
                       'strategy_grant_scheduled:员工投影仪@4'), \
        f'效果串: {effects}'
    assert gs.equips.value == ['员工投影仪'], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('人才激励', 4),), \
        f'队列值: {gs.pending_strategy_grants.value}'
    assert gs.equips.source == 'logic' \
        and gs.pending_strategy_grants.source == 'logic', '两腿走确定面'


def test_equips_unobserved_instant_rejected_queue_still_written() -> None:
    """equips 未观察(直构域):即时腿拒落零写(placed=False,入栏跳写
    gain_equipment 既有语义)、入队腿照写(登记 = 队列通道非装备通道,
    两腿互不拖)。"""
    gs = _gs(equips=None)
    effects = on_strategy_gained(gs, '人才激励', rand=False, sig=_lsig(),
                                 rng=random.Random(0))
    assert effects == ('equip_grant:员工投影仪(placed=False)',
                       'strategy_grant_scheduled:员工投影仪@4'), \
        f'效果串: {effects}'
    assert gs.equips.value is None, '拒落域出现写'
    assert gs.pending_strategy_grants.value == (('人才激励', 4),), \
        f'入队腿未写: {gs.pending_strategy_grants.value}'


def test_unregistered_cards_zero_write() -> None:
    """未登记卡零写(两形):表外名(查无效果安静不写)与在册无腿卡
    (躺平,注册表有卡但无登记行)均 → 零效果串 + 队列零写。"""
    for name in ('随便一张未收录卡', '躺平'):
        gs = _gs(equips=[])
        seq_before = gs.write_seq
        effects = on_strategy_gained(gs, name, rand=False, sig=_lsig(),
                                     rng=random.Random(0))
        assert effects == ()
        assert gs.pending_strategy_grants.value in (None, ()), \
            f'{name} 队列被写'
        assert gs.write_seq == seq_before, f'{name} 出现额外写行'


def test_live_gain_chain_queues_grant_zero_world_grant_action() -> None:
    """live 链登记(不对称申报的行为半边,锁 5):live 落地形态同函数
    (gain_invest_strategy,session=None 直构)→ 注册去重 + 即时装备腿
    与入队腿照写;kernel 零到点发放动作(发放腿仅存在于 sim 模块,模块
    边界承担,无静态扫描锁——AGENTS.md 测试规范源码扫描禁令)。"""
    gs = _gs(equips=[])
    outcome = gain_invest_strategy(gs, None, '人才激励', rand=False,
                                   sig=_lsig(), rng=random.Random(0),
                                   producer='CwActionReport')
    assert outcome.placed is True
    assert '人才激励' in (gs.active_strategies.value or []), '持卡注册'
    assert outcome.effects == ('equip_grant:员工投影仪(placed=True)',
                               'strategy_grant_scheduled:员工投影仪@4')
    assert gs.pending_strategy_grants.value == (('人才激励', 4),), \
        f'live 链队列: {gs.pending_strategy_grants.value}'
    assert gs.equips.value == ['员工投影仪'], '即时腿 live 照写'


def test_pick_rencai_jili_plus_direct_registry_chain() -> None:
    """人才激励+ 登记腿直断(原「注册表临时行 + 效果表同步派生」
    monkeypatch 形态测,随该卡真注册落地转直测——handler 按注册表
    驱动,零新增机制件):拿卡人才激励+ → equips 尾部 +1 员工投影仪
    ∧ 队列恰 (('人才激励+', 3),) ∧ 双效果串 equip_grant(placed=
    True)/ strategy_grant_scheduled:员工投影仪@3。@3 字面直断防姊妹
    卡键序错位(两卡唯一可见差异);逐名独立构造,姊妹卡登记腿主条
    (test_pick_rencai_jili_instant_equip_and_queue)不受影响。"""
    gs = _gs(equips=[])
    effects = on_strategy_gained(gs, '人才激励+', rand=False,
                                 sig=_lsig(), rng=random.Random(0))
    assert effects == ('equip_grant:员工投影仪(placed=True)',
                       'strategy_grant_scheduled:员工投影仪@3'), \
        f'效果串: {effects}'
    assert gs.equips.value == ['员工投影仪'], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('人才激励+', 3),), \
        f'队列值: {gs.pending_strategy_grants.value}'


def test_pick_xiankui_count_loop_double_entry() -> None:
    """先亏后盈 count 循环入队(数量 2 = 族内首例 >1,卡文「获得2个」):
    拿卡 → 队列恰 (('先亏后盈', 4), ('先亏后盈', 4))(count 循环两条
    同卡条目,逐条独立倒计时)∧ 效果串两枚 strategy_grant_scheduled:
    简易武装箱@4 ∧ 零即时腿 ∧ kernel 侧零 hp 写(登记腿写行恰 2 笔全
    为队列通道——损血腿结构性不入登记效果体,防将来误把损血腿塞进
    登记腿的回归锁;写流↔轨迹同构的 kernel 半边由本锁钉死)。"""
    gs = _gs(equips=[])
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '先亏后盈', rand=False,
                                 sig=_lsig(), rng=random.Random(0))
    assert effects == ('strategy_grant_scheduled:简易武装箱@4',
                       'strategy_grant_scheduled:简易武装箱@4'), \
        f'效果串(count 枚): {effects}'
    assert gs.equips.value == [], f'即时腿误写装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == \
        (('先亏后盈', 4), ('先亏后盈', 4)), \
        f'队列值(count 双条目): {gs.pending_strategy_grants.value}'
    assert gs.write_seq == seq_before + 2, \
        f'写行数漂移(恰 2 笔队列写,零 hp 写): {gs.write_seq}'


def test_pick_xunuo_tequan_delayed_only_single_leg() -> None:
    """许诺特权 延时-only 登记腿直断(卡文「在进入7个节点后，获得
    1个【特权武装箱】。」纯延时单句,零即时腿):拿卡 → 队列恰
    (('许诺特权', 7),) ∧ 效果串单枚 strategy_grant_scheduled:
    特权武装箱@7 ∧ 零即时腿(equips 零写、无 equip_grant 字样;bench
    域零涉)。反向锁死「延时-only 卡直用两腿工厂派生」的错发形态
    (错发即时特权武装箱 = 行为级错误);@7 字面直断防族键序错位;
    逐名独立构造,姊妹双卡两腿锁不受影响。"""
    gs = _gs(equips=[])
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '许诺特权', rand=False,
                                 sig=_lsig(), rng=random.Random(0))
    assert effects == ('strategy_grant_scheduled:特权武装箱@7',), \
        f'效果串(单枚,零即时腿): {effects}'
    assert gs.equips.value == [], f'即时腿误写装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('许诺特权', 7),), \
        f'队列值: {gs.pending_strategy_grants.value}'
    assert gs.write_seq == seq_before + 1, \
        f'入队腿外出现额外写行(seq={gs.write_seq})'


def test_pick_haoyun_lingpai_yin_delayed_only_single_leg() -> None:
    """好运令牌·银 延时-only 登记腿直断(卡文「进入3个节点后，获得
    1个【好运令牌】。」纯延时单句,零即时腿):拿卡 → 队列恰
    (('好运令牌·银', 3),) ∧ 效果串单枚 strategy_grant_scheduled:
    好运令牌@3(物名载体直断,@3 字面防族键序错位)∧ 零即时腿
    (equips 零写、效果串无 equip_grant/box_grant 字样;bench 域零涉;
    发放物与卡名异名,效果串/队列各按物名/卡名各归其位)。
    反向锁死「延时-only 卡直用两腿工厂派生」的错发形态(错发即时
    好运令牌 = 行为级错误);逐名独立构造,族内既有锁不受影响。"""
    gs = _gs(equips=[])
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '好运令牌·银', rand=False,
                                 sig=_lsig(), rng=random.Random(0))
    assert effects == ('strategy_grant_scheduled:好运令牌@3',), \
        f'效果串(单枚,零即时腿): {effects}'
    assert gs.equips.value == [], f'即时腿误写装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('好运令牌·银', 3),), \
        f'队列值: {gs.pending_strategy_grants.value}'
    assert gs.write_seq == seq_before + 1, \
        f'入队腿外出现额外写行(seq={gs.write_seq})'


def test_pick_haoyun_lingpai_yin_unobserved_still_single_scheduled() -> None:
    """好运令牌·银 equips 未观察域载体分流直断(防伪锁,与主条逐名
    独立构造):两腿工厂在同域会多发 equip_grant placed=False 串,延时-
    only 载体效果串仍恰单枚 strategy_grant_scheduled(登记 = 队列
    通道非装备通道)∧ equips 保持未观察零写 ∧ 两腿成员集负成员
    (登记分流声明面,误入集 = 分派语义漂移在行为锁不可见,成员断言
    直锁)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_DELAYED_TWO_LEG_GRANTS,
        PICK_INVEST_EFFECTS,
    )
    assert '好运令牌·银' not in _STRATEGY_DELAYED_TWO_LEG_GRANTS, \
        '误入两腿成员集(入集 = 拿卡错发即时装备腿的分派面)'
    assert '好运令牌·银' in PICK_INVEST_EFFECTS, '显式单行登记条缺位'
    gs = _gs(equips=None)
    effects = on_strategy_gained(gs, '好运令牌·银', rand=False,
                                 sig=_lsig(), rng=random.Random(0))
    assert effects == ('strategy_grant_scheduled:好运令牌@3',), \
        f'效果串(未观察域仍单枚): {effects}'
    assert gs.equips.value is None, '未观察域出现装备栏写'
    assert gs.pending_strategy_grants.value == (('好运令牌·银', 3),), \
        f'队列值: {gs.pending_strategy_grants.value}'


def test_pick_shizuanshi_choice_set_schedule_zero_rng() -> None:
    """是钻石总会发光 登记腿直断(卡文「2个节点后，获得【红钻】或
    【蓝钻】。」纯延时单句,零即时腿;族内首个随机发放行,掷骰时点 =
    到点发放时现掷):拿卡 → 队列恰 (('是钻石总会发光', 2),) ∧ 效果串
    单枚 choice-set 形 strategy_grant_scheduled:红钻|蓝钻@2(封闭集
    竖线连接直断,连接字面 ∉ EQUIPMENTS 防伪物名)∧ 零即时腿 ∧
    登记 rng 零消耗(拿卡前后 rng.getstate 逐位相等——预掷被否的行为
    证据,锁裁决点 2)∧ 入队腿外零额外写行;逐名独立构造,族内既有
    锁不受影响。"""
    gs = _gs(equips=[])
    rng = random.Random(2026)
    state_before = rng.getstate()
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '是钻石总会发光', rand=False,
                                 sig=_lsig(), rng=rng)
    assert effects == ('strategy_grant_scheduled:红钻|蓝钻@2',), \
        f'效果串(单枚,choice-set 形): {effects}'
    assert gs.equips.value == [], f'即时腿误写装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('是钻石总会发光', 2),), \
        f'队列值: {gs.pending_strategy_grants.value}'
    assert gs.write_seq == seq_before + 1, \
        f'入队腿外出现额外写行(seq={gs.write_seq})'
    assert rng.getstate() == state_before, \
        '登记腿消费 rng(预掷被否面被破坏)'


def test_pick_shizuanshi_unobserved_still_choice_set_scheduled() -> None:
    """是钻石总会发光 equips 未观察域载体分流直断(防伪锁,与主条逐名
    独立构造):两腿工厂在同域会多发 equip_grant placed=False 串,延时-
    only 载体效果串仍恰单枚 strategy_grant_scheduled:红钻|蓝钻@2 ∧
    equips 保持未观察零写 ∧ 两腿成员集负成员(误入集 = 分派语义漂移
    在行为锁不可见,成员断言直锁)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_DELAYED_TWO_LEG_GRANTS,
        PICK_INVEST_EFFECTS,
    )
    assert '是钻石总会发光' not in _STRATEGY_DELAYED_TWO_LEG_GRANTS, \
        '误入两腿成员集(入集 = 拿卡错发即时装备腿的分派面)'
    assert '是钻石总会发光' in PICK_INVEST_EFFECTS, '显式单行登记条缺位'
    gs = _gs(equips=None)
    effects = on_strategy_gained(gs, '是钻石总会发光', rand=False,
                                 sig=_lsig(), rng=random.Random(0))
    assert effects == ('strategy_grant_scheduled:红钻|蓝钻@2',), \
        f'效果串(未观察域仍单枚): {effects}'
    assert gs.equips.value is None, '未观察域出现装备栏写'
    assert gs.pending_strategy_grants.value == (('是钻石总会发光', 2),), \
        f'队列值: {gs.pending_strategy_grants.value}'


def test_pick_huishou_combined_legs_schedule_category_pool() -> None:
    """回收计划 组合登记行登记腿直断(卡文「获得1件进阶装备，并在5个
    节点后获得1件随机简易装备。」,随机腿×延时入队腿双族交叉,PICK
    组合登记行,不入泛化表防同名键覆盖丢即时腿):拿卡 → 效果串恰
    2 条且腿序 = 卡文语序(即时随机腿 strategy_random_equip 在前/入队
    腿在后),入队腿效果串类别池形 strategy_grant_scheduled:随机简易
    (类别池)@5(池标记字形直断,构造点 = 入队原语发放物段单一构造点,
    连接字面 ∉ EQUIPMENTS 防伪物名)∧ 队列恰 (('回收计划', 5),) ∧
    rng 恰消费 1 次(同序预采样对拍 = 即时腿第 1 抽,入队腿零采样面,
    腿序改排/入队腿预掷均使采样名漂移即红)∧ 写行恰 2 笔(即时腿入栏
    + 队列登记);逐名独立构造,族内既有锁不受影响。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    # 预采样(独立 rng 实例按消费序恰 1 抽进阶池):与实际注入的 rng
    # 同种子同序——腿序改排(入队腿先)不改变首抽仍为进阶池采样,但
    # 「入队腿另掷一枚」会使实际首抽名漂移,同序对拍即红(掷序契约)。
    pick = roll_random_equip(random.Random(2026), '进阶')
    assert pick in equips_by_category('进阶'), '预验证:采样 ∈ 进阶池'
    gs = _gs(equips=[])
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '回收计划', rand=False,
                                 sig=_lsig(), rng=random.Random(2026))
    assert effects == (f'strategy_random_equip:{pick}',
                       'strategy_grant_scheduled:随机简易(类别池)@5'), \
        f'效果串(腿序 = 卡文语序): {effects}'
    assert gs.equips.value == [pick], f'即时腿入栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('回收计划', 5),), \
        f'队列值: {gs.pending_strategy_grants.value}'
    assert gs.write_seq == seq_before + 2, \
        f'写行数漂移(即时腿+入队腿恰 2 笔): {gs.write_seq}'
