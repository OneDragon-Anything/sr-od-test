"""商店保护集囤货臂单帧测试(统一保护集迭代 买面批)。

被测 = ``src/sr_od/application/currency_war/strategies/impl/mandate_v1/
shop.py`` :func:`decide_shop_action` 序 1 的保护集囤货臂(位次 = M2b
后、序 2 前)与 D7 拒因键迁移、保护集纯计数键重定义。

出处 = ``docs/develop/sr_od/application/currency_war/changes/2026-10-15-
unified-protection-set/design.md`` §2.2(囤货臂命中条件/门序/出口键/
义务面囤货面拆分)/ §2.3(D7 键序迁移:义务面收窄 +
``protection_member_rejected`` 新增)/ §2.4(计数键重定义)与同目录
``landing.md`` 3.2 完成判据。

**帧态六元组与构造依据(design §2.6 钉面)**:

- owned 集 = {藿藿, 青雀, 佩拉}(bench 1★)——设计钉面约束:三者的
  首副本若不持有,会按货架序先于目标件命中囤臂,断言钉错机制;
- 候选快照 = 空(无候选线;义务面 = 方向成员 ∪ 贯穿件);
- 点亮状态 = 非点亮(藿藿+青雀 = 仙舟 2/3 不达标;囤臂守卫 = 终局
  锁定态 ``line_members_view.locked``,与过渡锁定槽无耦合——点亮状态
  登记为六元组完整面,非本臂判据输入);
- 方向态 = **设计钉死构造值**(列车系早期对 stand-in =
  ``opening_recipe_comp``;病灶局 g_20261015_154239 的方向态为已登记
  源缺——复盘报告完整性审计:方向状态键不在 kernel state 输出),
  fixture 按 design §2.2 名单构成构造与病灶局同构的场景,单帧验证的
  是**臂语义**非历史复现;
- 金 = 30 / 席位 = 备战席 3/9(有空位前提一并钉入)。

成员身份锚(注册表 cw_chars 事实,机械重推):爻光/藿藿/青雀 =
factions 仙舟;佩拉 = factions 贝洛伯格(希儿系放大器阵营);丹恒·
饮月 = factions 仙舟、列车同行——四者 ∈ 四体系保护集;风堇 =
昼之半神/治疗、燃血——非四体系(病灶局填充件,复盘报告 r3 行)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_card,
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)

# 注册表真实费用(cw_chars 单一源;卡面 cost 与注册表一致,禁另拍)。
_FACE_R3 = (('风堇', 2), ('藿藿', 1), ('青雀', 1), ('佩拉', 2), ('爻光', 1))
_FACE_R6 = (('风堇', 2), ('藿藿', 1), ('青雀', 1), ('佩拉', 2),
            ('丹恒·饮月', 2))
_OWNED = ('藿藿', '青雀', '佩拉')


def _frame(face, *, gold: int = 30):
    """病灶同构牌面帧(六元组见模块 docstring;返回 gs/sess/config)。

    方向态 = 列车系早期对 stand-in(core ∪ shared = 姬子·启行/三月七/
    花火/瓦尔特,与本牌面零交集 → 义务面在店为空,首笔买入必出自囤臂)。
    """
    sess = StrategySession()
    st = state_of(sess)
    st.cw4_counters = {}
    st.v3_intention = IntentionState()
    st.target_comp = None                       # 未锁定(囤臂守卫开启)
    st.opening_recipe_comp = get_comp('列车同行')   # 方向态构造值
    st.line_candidates = ()
    gs = cw4_gs(sess, plane=1, round_num=3, node='battle',
                gold=gold, level=7, hp=80, deploy_cap=5,
                bench=[cw4_bc(n) for n in _OWNED],
                shop=[cw4_card(n, cost=c, star=1, x=i)
                      for i, (n, c) in enumerate(face)])
    return gs, sess, SimpleNamespace(ev_arm='full')


class TestProtectionHoardArm:
    """囤货臂语义(design §2.2;landing 3.2 单帧判据)。"""

    def test_r3_yao_guang_hoard_bought(self):
        """r3 同构牌面(风堇/藿藿/青雀/佩拉/爻光;owned 钉藿藿/青雀/
        佩拉已持)→ 必发 ``BuyCard 爻光``(囤货臂买因
        ``protection_hoard``;design §2.6 / landing 3.2)。

        附锁:①义务面在店为空 → 首笔买入必出自囤臂(方向态构造值与
        牌面零交集);②帧首 D7 拒因迁移(§2.3):在售未买囤货面成员 =
        ``protection_member_rejected``、非保护填充件 = ``non_line``、
        已持囤货面成员 = 中性 ``owned``;③保护集纯计数键重定义(§2.4):
        备战席上保护集成员数 = 3。"""
        gs, sess, cfg = _frame(_FACE_R3)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionBuyCardParam), f'未发买入: {act!r}'
        assert act.card.name == '爻光'
        assert act.reason == 'protection_hoard'
        ct = state_of(sess).cw4_counters
        assert ct.get('protection_hoard_hit') == 1
        # 帧首快照拒因(D7 键序迁移;快照先于动作,囤臂随后命中)
        rejects = getattr(state_of(sess), 'cw4_shop_rejects', {})
        assert rejects.get('爻光') == 'protection_member_rejected'
        assert rejects.get('风堇') == 'non_line'
        assert rejects.get('藿藿') == 'owned'
        # 保护集纯计数键(键值 = 备战席上保护集成员数;design §2.4)
        assert ct.get('transition_hold_locked_frame') == 3

    def test_r6_yin_yue_hoard_bought(self):
        """r6 同构牌面含饮月 → 必发 ``BuyCard 饮月``(囤货臂;design
        §2.6——病灶局 r6·r8 饮月 2 费在架拒买为缺陷本体,同臂语义二锚)。"""
        gs, sess, cfg = _frame(_FACE_R6)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionBuyCardParam), f'未发买入: {act!r}'
        assert act.card.name == '丹恒·饮月'
        assert act.reason == 'protection_hoard'
        assert state_of(sess).cw4_counters.get('protection_hoard_hit') == 1

    def test_unaffordable_records_exit_and_opportunity(self):
        """金不可负担帧:期权级无筹资特权(design §2.2/§2.5-2——囤臂
        门序 = 1★ 全额退 → 金可负担,无筹资分支)→ ``protection_hoard_
        unaffordable`` 计数 + 牌进机会清单(拦因 gold_short),不发出
        筹资卖出、零买入。(面 = 单卡爻光:隔离序 2 场况插件支,使
        断言域 = 囤臂出口键本身。)"""
        gs, sess, cfg = _frame((('爻光', 1),), gold=0)
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionCloseShopParam), f'非收工: {act!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('protection_hoard_unaffordable') == 1
        assert not ct.get('session_funding_sell'), \
            '囤货臂金不足帧发出筹资卖出 = 期权级筹资特权违例'
        assert any(r.card_name == '爻光' and r.blocked_by == 'gold_short'
                   for r in state_of(sess).shop_opportunities), \
            f'机会清单缺席: {state_of(sess).shop_opportunities}'


# ============================================================
# 卖面批:店内置换账跳过保护集(design §2.3 装配 A 身份段;landing 3.3)
# ============================================================


_SWAP_BENCH = ('椒丘', '风堇')   # 椒丘 = 保护档;风堇 = 非四体系 1★ 2费(最低价值让位件,病灶局填充件同款)


def _swap_frame():
    """置换场景帧(design §2.6「席满 + 手上椒丘 + 店内杂件」同构):
    席满 9/9(椒丘 + 风堇〔非四体系杂件 = 让位件〕+ 7 张 3★ 注册表外
    高价值持有)+ 方向态 = 列车系早期对 stand-in(同 3.2 帧构造值)+
    店内方向件瓦尔特(5费,过序 1 义务判据,席满拦;置换账 X 侧高费件
    value ≈365 支配 Y 侧杂件 value ≈23.5,注册表现算非手拍)+ 场上
    1 件注册表外填充(绕空板止损守卫)。"""
    sess = StrategySession()
    st = state_of(sess)
    st.cw4_counters = {}
    st.v3_intention = IntentionState()
    st.target_comp = None                       # 未锁定
    st.opening_recipe_comp = get_comp('列车同行')   # 方向态构造值
    st.line_candidates = ()
    bench = [cw4_bc(n) for n in _SWAP_BENCH] \
        + [cw4_bc(f'c{i}', star=3) for i in range(3, 10)]   # 高价值持有(3★)
    assert len(bench) == 9, '席满前提'
    gs = cw4_gs(sess, plane=1, round_num=3, node='battle',
                gold=30, level=7, hp=80, deploy_cap=5,
                bench=bench,
                front_row=[Unit(char_id='c9', star=1)],   # 非空板(空板守卫绕行)
                shop=[cw4_card('瓦尔特', cost=5, star=1, x=0)])
    return gs, sess, SimpleNamespace(ev_arm='full')


class TestShopSwapSkipsProtection:
    """置换场景(landing 3.3 单帧判据):席满 + 手上椒丘 + 店内方向件
    → 置换卖杂件,椒丘不在卖出候选(design §2.3:保护集成员常规通道
    绝对禁卖,置换账 = 常规面场景)。"""

    def test_swap_sells_junk_and_skips_protected(self):
        """评估器候选不含椒丘(身份段排除)、含风堇;置换账首位让位件 =
        风堇 → 发出 ``CwActionSellBenchParam(expect=风堇, reason=shop_
        swap)``,保护档椒丘留席。"""
        from sr_od.application.currency_war.kernel.cw_vocab import (
            CwActionSellBenchParam,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.sell_candidates import (
            evaluate_sell_candidates,
        )
        gs, sess, cfg = _swap_frame()
        cands, why = evaluate_sell_candidates(gs, 'shop_swap')
        assert why == ''
        names = [c.char_id for c in cands]
        assert '椒丘' not in names, \
            f'保护档成员进置换候选(常规通道禁卖失守): {names}'
        assert '风堇' in names
        act = decide_shop_action(gs, sess, cfg)
        assert isinstance(act, CwActionSellBenchParam), f'非置换卖出: {act!r}'
        assert act.reason == 'shop_swap'
        assert act.expect == '风堇', \
            f'置换让位件非杂件(保护档被卖或排序失守): {act.expect!r}'
