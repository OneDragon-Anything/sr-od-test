"""泄金阶梯单帧测试(ADR-0604 判据测试;测试清单 = 设计方案 §4.3
本批归属 L1-L7 + 档 2 轮内新鲜度排除,方案正本指针 = ADR-0604 头注)。

测试清单(§4.3 表存续面):
- LF′ 档 2 轮内新鲜度排除载体相位过期:跨轮/跨位面读数空集(排除
      上界 ≤1 轮;发射位排除面归写端与消费位测试辖)。
- L3′ prep 位 M6 摘旗可达性:stop_flag=False(线未齐)∧ gold>g* ∧
      席满帧,M6 prep 块被触达(m6_bench_full 拒因显影——摘旗前该帧
      被 stop_flag 短路、拒因结构性不可见)。
(原 L7 ALL IN 类别过滤面已随域辖谓词删除退役——hp-purge
      迭代 3.1 A-6,见文末退役注。)

测试构造声明:候选/帧构造基建(_km/_bc/_card/_off_name/_session_stub/
_st)保留 = test_front_window_predicates 的候选构造单一源(跨文件
消费);L1/L1b/L2/L3/L5/LF 发射面测试与档 1 锁线门负分支已退役。
"""
from types import SimpleNamespace
from typing import TYPE_CHECKING

from sr_od.application.currency_war.data.cw_chars import CHARACTERS

if TYPE_CHECKING:
    pass
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
)

from sr_od.application.currency_war.kernel.cw_comps import (
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)

_COMP = '列车同行·反震'


# ===== 测试基建(exit3 同族口径)=====


def _km() -> list[str]:
    return list(predicates.line_members(get_comp(_COMP)))


def _bc(name: str, star: int = 1):
    """行域单位(容器形状;本文件与 press_narrow 转型域共用直构面)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import Unit
    return Unit(char_id=name, star=star)


def _st(gold: int, cards, *, locked: bool = True, level: int = 5,
        deploy_cap: int | None = None, bench=None, deployed=None,
        plane: int = 2, hp: int = 60, xp=None) -> dict:
    """漏斗阶梯场景种子轴(旧帧配方退役承接 = 桥/feed 两配方公共
    kwargs;``deployed`` = 旧槽表序 Units,前 4 位前排/其余后排的语义
    在此分行承接,槽号 1 基信息位随行重排;``locked`` 轴不在容器域,
    保留参数位 = session 侧语义,由调用方自持)。"""
    axes: dict = {'gold': gold, 'level': level, 'round_num': 2, 'hp': hp,
                  'plane': plane, 'shop': list(cards)}
    if bench is not None:
        axes['bench'] = bench
    if deployed is not None:
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        axes['front_row'] = [
            Unit(char_id=u.char_id, star=u.star,
                 equips=list(u.equips or []))
            for i, u in enumerate(deployed[:4])]
        axes['back_row'] = [
            Unit(char_id=u.char_id, star=u.star,
                 equips=list(u.equips or []))
            for i, u in enumerate(deployed[4:], start=4)]
    if deploy_cap is not None:
        axes['deploy_cap'] = deploy_cap
    if xp is not None:
        axes['xp'] = xp
    return axes


def _bs(name: str, star: int = 1, slot: int = 1):
    """容器占席条目(P4 载体迁移:MandateFrame/判据直构面)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        Unit,
    )
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))


def _bu(name: str, star: int = 1, slot: int = 1):
    """容器行域单位(P4 载体迁移:deployed 直构面)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import Unit
    return Unit(char_id=name, star=star)


def _card(name: str, cost: int = 2, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _off_name(exclude: tuple[str, ...] = (), *, min_cost: int = 1) -> str:
    """线外注册表角色名(候选构造;避开目标线成员,防邻近臂抢发射
    ——C1 单卡核心/保护集囤货臂候选身份已随统一让位优先级迭代 3.4
    退役,非线内即可,不再需要核心/保护身份规避)。"""
    bad = set(exclude) | set(_km())
    for n, ch in CHARACTERS.items():
        if n in bad or (ch.cost or 0) < min_cost:
            continue
        return n
    raise AssertionError('注册表缺少合适线外角色(测试前提失效)')


def _session_stub(locked: bool = True, target_comp=None) -> SimpleNamespace:
    s = SimpleNamespace()
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = target_comp if target_comp is not None else get_comp(_COMP)
    st.v3_intention = SimpleNamespace(
        locked_comp=(_COMP if locked else ''))
    return s


# ===== LF′:档 2 轮内新鲜度排除载体相位过期 =====


class TestL2L5LFM6Compression:

    def test_lf_round_registry_expiry(self):
        """新鲜度载体键式相位过期:跨轮/跨位面读数空集(排除上界 ≤1 轮)。"""
        sess = SimpleNamespace()
        axes = {'gold': 10, 'level': 5, 'round_num': 3, 'plane': 2}
        mandate.record_round_sold(sess, _bsb(**axes), '甲')
        assert mandate.round_sold_names(sess, _bsb(**axes)) == frozenset({'甲'})
        axes['round_num'] = 4
        assert mandate.round_sold_names(sess, _bsb(**axes)) == frozenset()
        axes['round_num'] = 3
        axes['plane'] = 3
        assert mandate.round_sold_names(sess, _bsb(**axes)) == frozenset()


# ===== L3′:prep 位 M6 摘旗可达性 =====


class TestL3FlagRemoval:

    def test_l3_prep_m6_reachable_without_stop_flag(self):
        """prep 位 M6 摘旗可达性:stop_flag=False(线未齐)∧ gold>g*
        ∧ 席满帧,M6 prep 块被触达(m6_bench_full 拒因显影)——摘旗前
        该帧 M6 prep 被 stop_flag 短路、拒因结构性不可见。"""
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            StrategySession,
        )
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        bench = [_bs(f'高价{i}', star=3, slot=i + 1) for i in range(9)]
        frame = mandate.MandateFrame(
            gold=60, level=3, bench=bench, deployed=[],
            deploy_cap=5, node_type=None, stop_flag=False,
            k_members=('目标件',), round_num=3)
        state = _bsb(gold=60, level=3, round_num=3, hp=60)
        mandate.run_mandate(frame, sess, state=state)
        assert state_of(sess).cw4_counters.get('m6_bench_full', 0) >= 1


# (原 L4:P72 拒帧档 1/2 挂起测试随 P72 预算闸/L4 挂起面退役删除
#  商店期升级决策面收缩——闸写点不存在,挂起分支结构性死路;档 2 同帧
#  挂起的 TestShopM3M6 承载声明随之失效。)


# (原 L7 ALL IN 类别过滤域谓词测试已随辖域谓词本体删除退役
# ——hp-purge 迭代 3.1 A-6 挂空死码删除;P72 闸 ALL IN 支收窄测试
# test_l7_gate_rejects_non_support_xp 已随 levelup_budget_gate 量闸本体
# 退役消亡(迭代 2026-10-12-prep-shop-workflow-redesign 批 3.4;
# line_and_upgrade §2.3 P72(3a) 本体删除行:量闸整体不再存在,
# 「ALL IN 帧类别白名单拒 XP」的防线语义随之消亡——ALL IN 帧花光拦截
# 现役载体 = 无,末位面末战保底金门出辖 = ALL IN 花光原语义;替代语义
# 考古走 git 历史)。)
