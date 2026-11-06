"""expert_conditional_trigger 判据单元测试(镜像 src =
kernel/cw_gain_chain.py 的该被测函数,按拆目录规范落位)。

测试面依据 = T-42 设计(迭代 2026-09-23-invest-effects-calc,designs/
T-42-teyao-zhuanjia-yinlang.md)§4 锁 1:三条件各缺一不触发(非银狼LV.999
名 / active_env 非本卡 / 已解锁)/ 全命中解锁 + 效果布尔 / 幂等
(已解锁后再次获得零写)/ active_env 空(未选择)不触发。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    expert_conditional_trigger,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)

_SIG = ChannelSig(family='logic_action', actor='CwGainChain', mode='compute')
_SIG_RAND = ChannelSig(family='logic_hook', actor='CwGainChain', mode='compute')
_ENV = '特邀专家:银狼'


def _gs(*, active_env: str | None = _ENV,
        unlocked: tuple[str, ...] = ()) -> GameState:
    """直构状态容器(active_env 经 logic 写 = 注册链同形;None = 不写未选择)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if active_env is not None:
        gs.write_logic(gs.active_env, active_env, produced_by='TestWriter',
                       evidence='t', sig=_SIG)
    if unlocked:
        gs.write_logic(gs.unlocked_experts, unlocked, produced_by='TestWriter',
                       evidence='t', sig=_SIG)
    return gs


def test_all_three_conditions_met_unlocks() -> None:
    """全命中:解锁写 unlocked_experts 含银狼,evidence 带 #expert_unlock
    族后缀(与 advisor/策略/装备解锁道同后缀,遥测可过滤)。"""
    gs = _gs()
    seq_before = gs.write_seq
    assert expert_conditional_trigger(gs, '银狼LV.999', rand=False, sig=_SIG,
                                      evidence='on_character_gained') is True
    assert gs.unlocked_experts.value == ('银狼',), '解锁写入'
    assert gs.unlocked_experts.evidence == \
        'on_character_gained#expert_unlock', 'evidence 族后缀'
    assert gs.write_seq - seq_before == 1, '恰一行解锁写'


def test_name_mismatch_no_trigger() -> None:
    """条件①缺:顾问名/其他名不触发(名按规范名直等,无自触发循环;
    零写)。"""
    gs = _gs()
    seq_before = gs.write_seq
    assert expert_conditional_trigger(gs, '银狼', rand=False, sig=_SIG,
                                      evidence='t') is False
    assert gs.unlocked_experts.value in (None, ()), '零解锁写'
    assert gs.write_seq == seq_before


def test_env_mismatch_no_trigger() -> None:
    """条件②缺:active_env 非本卡不触发(单环境互斥——欢愉契约送
    银狼LV.999 即此形态)。"""
    gs = _gs(active_env='欢愉契约')
    assert expert_conditional_trigger(gs, '银狼LV.999', rand=False, sig=_SIG,
                                      evidence='t') is False
    assert gs.unlocked_experts.value in (None, ()), '零解锁写'


def test_env_absent_no_trigger() -> None:
    """条件②缺(active_env 空/未选择形态):不触发——active_env 开局
    种子初始值 = ''(未选择),判据读空值短路。"""
    gs = _gs(active_env=None)
    assert expert_conditional_trigger(gs, '银狼LV.999', rand=False, sig=_SIG,
                                      evidence='t') is False
    gs2 = _gs(active_env='')
    assert expert_conditional_trigger(gs2, '银狼LV.999', rand=False,
                                      sig=_SIG, evidence='t') is False
    assert gs.unlocked_experts.value in (None, ())
    assert gs2.unlocked_experts.value in (None, ())


def test_already_unlocked_idempotent_zero_write() -> None:
    """条件③缺 = 幂等(已解锁后再次获得零写):「已触发」与「已解锁」
    同一事实,防重发与消费同源;升星产物递归重进与假想双发同此短路。"""
    gs = _gs(unlocked=('银狼',))
    seq_before = gs.write_seq
    assert expert_conditional_trigger(gs, '银狼LV.999', rand=False, sig=_SIG,
                                      evidence='t') is False
    assert gs.unlocked_experts.value == ('银狼',), '名单不变'
    assert gs.write_seq == seq_before, '零写(幂等短路)'


def test_rand_true_writes_rand_channel_after_anchor() -> None:
    """rand 透传(采样链纪律):置一次性标志位后 rand=True 仍走随机态通道
    (write_logic_rand),rand=False 走确定面——通道选择入口单一收尾。"""
    gs_rand = _gs()
    gs_rand.prep_anchored = True
    assert expert_conditional_trigger(gs_rand, '银狼LV.999', rand=True,
                                      sig=_SIG_RAND,
                                      evidence='t') is True
    assert gs_rand.unlocked_experts.source == 'logic_rand', 'rand=True 随机态'
    gs_det = _gs()
    gs_det.prep_anchored = True
    assert expert_conditional_trigger(gs_det, '银狼LV.999', rand=False,
                                      sig=_SIG, evidence='t') is True
    assert gs_det.unlocked_experts.source == 'logic', 'rand=False 确定面'
