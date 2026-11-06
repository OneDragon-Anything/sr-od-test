"""close_shop 上报测试(镜像 src = kernel/cw_action_report/close_shop.py)。

锁面(《商店黑板容器化方案》§4-M1 投影直测,CloseShop 分支):结构离屏
= shop payload 置 None(leave_screen 语义);本动作期望态语义由「终结
作废」契约承载——期望态随终结作废,离屏域值失效等价于下帧观察全量重建。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_close_shop_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCloseShopParam,
)

# 改写依据(分诊):写入者登记面随「商店单动作循环纳入统一管理」演进——
# 生产写点 actor 现役 = CwScreenShop(cw_screen_shop,登记面已登记),
# 旧名 CwOpBuyCards 已退役;测试模拟生产写入随登记面改名。
_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                  mode='compute', group_id='act:CwScreenShop@1')


def _gs_of(**axes):
    """M1 场景种子(原裸帧合成配方承接:节点整域不写、空店离屏;
    域覆盖集与原合成口逐域一致)。"""
    return cw4_gs(node_fill=False, shop_screen='off', **axes)


def test_close_shop_leaves_screen():
    """CwActionCloseShopParam:结构离屏(shop payload → None,left_screen)。"""
    gs = _gs_of(gold=30, shop=[_card('希儿')])
    assert gs.shop.value is not None
    report_action_close_shop_param(gs, CwActionCloseShopParam(), _SIG)
    assert gs.shop.value is None
