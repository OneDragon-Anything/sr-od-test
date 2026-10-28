"""cw_shop_deal 发牌采样器测试(2★ 直出分支,T-22 人才下沉)。

锁面(设计 = .debug/progress/2026-09-23-invest-effects-calc/designs/
T-22-rencai-xiachen.md §4;过程件引用寿命 = 迭代,语义以测试本体为准):
1. 登记闸:ENV_SHOP_TWO_STAR_DEAL_PROB 手抄锁值(占位非真值,先例 =
   test_sim_offer 的 ENV_ORE_PANEL_BONUS 同式);
2. 行为锁:注册表命中环境发牌出现 2★(cost = 基准费×3,cost_source
   维持 'roster'),表外环境恒 1★,空槽不翻;
3. rng 零扰动锁(计数形态):表外环境 random() 消耗 = 每槽恰 1 次
   费用档掷点(翻星掷点零发生);命中环境每非空槽恰 +1 次;翻星频率
   量级 = 注册表 p(固定种子下确定,粗带防参数错接)。
"""
import random

from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.data.cw_shop_odds import REFRESH_PROB
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_SHOP_TWO_STAR_DEAL_PROB,
)
from sr_od.application.currency_war.kernel.cw_shop_deal import sample_shop_deal
from sr_od.application.currency_war.sim.cw_sim_backend import (
    _BASE_DISCLOSURES,
    SHOP_TWO_STAR_DEAL_PLACEHOLDER,
)

_DEAL_TIMES = 100
_SEED = 'cw-shop-two-star-branch'


class _CountingRandom(random.Random):
    """计数桩:统计 random() 调用次数。子类覆写 random() 触发
    ``Random.__init_subclass__`` 把 _randbelow 改走 random() 路径——
    故费用档掷点(choices)与抽名(choice)各计 1 发,计数覆盖全部
    消耗;两侧运行同用本桩,口径对齐。"""

    def __init__(self, seed: object) -> None:
        super().__init__(seed)
        self.random_calls = 0

    def random(self) -> float:
        self.random_calls += 1
        return super().random()


def _deal(gs: object) -> tuple[object, _CountingRandom]:
    rng = _CountingRandom(_SEED)
    payload = sample_shop_deal(gs, rng, level=3)
    return payload, rng


def test_registry_manual_lock() -> None:
    """登记闸:占位值手抄锁(值变更 = 用户重裁/实采校准,须显式改本锁)。"""
    assert ENV_SHOP_TWO_STAR_DEAL_PROB == {'人才下沉': 0.2}


def test_env_hit_deals_two_star() -> None:
    """行为锁:命中环境出 2★(cost = 基准费×3,cost_source 维持),
    空槽不翻(三态一致);翻星频率量级 = 注册表 p(粗带)。"""
    two_star_seen = 0
    content_seen = 0
    for _ in range(_DEAL_TIMES):
        payload, _ = _deal(cw4_gs(active_env='人才下沉'))
        assert len(payload.cards) == 5
        for slot in payload.cards:
            if slot.card is None:
                assert slot.kind == 'empty', '空槽三态一致(翻星不造卡)'
                continue
            assert slot.kind == 'content'
            content_seen += 1
            assert slot.card.cost_source == 'roster', '构造信源不变'
            if slot.card.star == 2:
                two_star_seen += 1
                assert slot.card.cost % 3 == 0, '2★ 读数 = 基准费×3'
                assert slot.card.cost // 3 in REFRESH_PROB[3], \
                    '基准费落在费用档表内'
            else:
                assert slot.card.star == 1
                assert slot.card.cost in REFRESH_PROB[3]
    assert two_star_seen > 0, 'p=0.2 × 100 店必现 2★(固定种子,行为丢失即红)'
    rate = two_star_seen / content_seen
    assert 0.05 < rate < 0.4, f'翻星频率粗带(实测 {rate:.3f},防参数错接)'


def test_off_env_no_two_star() -> None:
    """表外环境:任意 deal 零 2★(白名单外恒 1★)。"""
    for _ in range(_DEAL_TIMES):
        payload, _ = _deal(cw4_gs(active_env=''))
        assert all(s.card is None or s.card.star == 1
                   for s in payload.cards), '表外恒 1★'


def test_rng_zero_perturbation() -> None:
    """rng 零扰动锁(计数形态):计数桩下每次抽签(费用档/抽名/翻星)
    恰 1 发 random()——表外局消耗 = 槽数 + 非空槽数(翻星掷点零发生,
    即与无翻星分支实现同式);命中局 = 槽数 + 2×非空槽数(每非空槽恰 +1
    次翻星掷点)。注:翻星掷点与费用档/抽名共用同一流,命中局后续槽位
    抽牌结果随翻星分叉属预期,零扰动性质由计数恒等式承载。"""
    base_payload, base_rng = _deal(cw4_gs(active_env=''))
    base_content = sum(1 for s in base_payload.cards if s.card is not None)
    assert base_rng.random_calls \
        == len(base_payload.cards) + base_content, \
        '表外 = 槽数 + 非空槽数(翻星掷点零发生 = 无翻星分支同式)'

    env_payload, env_rng = _deal(cw4_gs(active_env='人才下沉'))
    env_content = sum(1 for s in env_payload.cards if s.card is not None)
    assert env_rng.random_calls \
        == len(env_payload.cards) + 2 * env_content, \
        '命中环境 = 槽数 + 非空槽×2(每非空槽恰 +1 次翻星掷点)'


def test_disclosure_key_registered() -> None:
    """披露键在册闸:_BASE_DISCLOSURES 接线即随局披露。"""
    assert _BASE_DISCLOSURES.get(SHOP_TWO_STAR_DEAL_PLACEHOLDER) == \
        'user_placeholder_pending_field_sampling'
