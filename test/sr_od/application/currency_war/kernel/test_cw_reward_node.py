"""cw_reward_node 镜像测试面(扑满环境名单派生完备锁)。

锁的靶子 = PIGGY_ENV_NAMES 派生判据(PLAZA_PORTALS 效果文本含「奖励
节点替换」子串)的已申报盲区:版本改词致子串消失 → 派生漏卡 → 扑满
守卫(抑制豁免/帧型判据/sim 递延收入/不掉血豁免全套)对漏卡局系统性
静默关闭,代码内不可检测——本锁把检测从实机静默降档提前到测试期变红
(设计 designs/T-20-jingji-yanzhong-guore.md §2.1.1)。方向边界:仅
闭合「改词 → 子串消失 → 漏派生」单向;反向「desc 改写仍含子串而语义
漂移 → 派生恒真」由版本重采人工效果文本比对承载,不在本锁覆盖域。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_reward_node import (
    PIGGY_ENV_NAMES,
)

#: 在册扑满卡手抄件(卡面 = cw_invest_data PlazaPortal:id 105/id 119)。
#: 手抄 = 闸:版本重采增删扑满卡或改派生判据时,此处必须显式更新——
#: 与 kernel 侧 ENV_ORE_PANEL_BONUS 键集完全一致校验同纪律(增删扑满
#: 环境须逐处显式拍定,禁静默跟随)。
_IN_REGISTER_PIGGY_ENVS: frozenset[str] = frozenset(
    {'经济过热', '经济严重过热'})


def test_piggy_env_names_derivation_covers_registered_cards() -> None:
    """派生完备锁:名单 ⊇ 在册两扑满卡。缺员即红 = 版本改词漏派生在
    测试期暴露,而非扑满全套行为对漏卡局静默关闭。"""
    assert _IN_REGISTER_PIGGY_ENVS <= PIGGY_ENV_NAMES, \
        f'扑满名单缺员: {sorted(_IN_REGISTER_PIGGY_ENVS - PIGGY_ENV_NAMES)}'
