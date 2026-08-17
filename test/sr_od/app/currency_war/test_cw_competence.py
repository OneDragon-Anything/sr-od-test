"""cw_competence(09 号认知主权层 v0)测试:主权/边际/分诊(ADR-0167)。"""
from sr_od.application.currency_war.cw_competence import (
    ADV_MARGIN,
    CompetenceMap,
    cell_id,
)


def test_cell_id_stable():
    assert cell_id('列车', 1, 80, '裸装') == '列车|P1|60-101|裸装'
    assert cell_id('列车', 9, 20, '成型') == '列车|P3|0-30|成型'
    assert cell_id('x', 2, 45, '未知档') == 'x|P2|30-60|部分'   # 非法档归默认


def test_sovereignty_monotone_in_density():
    """密度越高主权越大(连续混合非二值);空白格 → 低权不零权(0.2 手写主导)。"""
    m = CompetenceMap()
    lo = cell_id('散装', 1, 80, '裸装')
    hi = cell_id('列车', 2, 70, '成型')
    for _ in range(60):
        m.observe(hi)
    assert m.sovereignty(hi) == 1.0
    assert 0.0 < m.sovereignty(lo) <= 0.25        # 空白格低权
    mid = cell_id('仙舟', 1, 50, '部分')
    for _ in range(6):
        m.observe(mid)
    assert 0.25 < m.sovereignty(mid) < 1.0        # 连续混合(n=12 处爬升段)


def test_prior_half_weight_and_own_double():
    """自家样本 2×权重,plaza 先验半权(幸存者偏差;亲历 > 攻略)。"""
    m = CompetenceMap()
    a = cell_id('A', 1, 70, '部分')
    b = cell_id('B', 1, 70, '部分')
    m.observe(a, prior=True)
    m.observe(b)
    assert m.density(b) == 2   # own=1 → n=2
    assert m.density(a) == 1   # prior=1 → n=1


def test_irreversible_gate_ignorance_margin():
    """不可逆门:低密度格需要更大优势;显著优势任何格放行。"""
    m = CompetenceMap()
    known = cell_id('列车', 2, 70, '成型')
    for _ in range(80):
        m.observe(known)
    unknown = cell_id('量子', 3, 20, '裸装')
    adv = ADV_MARGIN * 1.2
    ok_k, _ = m.irreversible_gate(adv, known)
    ok_u, why_u = m.irreversible_gate(adv, unknown)
    assert ok_k and not ok_u        # 同优势:已知放行未知拦
    ok_big, w = m.irreversible_gate(3.0, unknown)
    assert ok_big and '显著优势' in w   # 显著优势放行
    # stakes 收紧边际
    ok_low, _ = m.irreversible_gate(ADV_MARGIN * 1.05, known, stakes='low_hp')
    assert not ok_low


def test_exploration_bonus_surplus_only():
    """探索价:富余+低覆盖 → 正;非富余(stakes 高)→ 负。"""
    m = CompetenceMap()
    rare = cell_id('遐蝶', 1, 90, '裸装')
    assert m.exploration_bonus(rare, surplus=True) > 0
    assert m.exploration_bonus(rare, surplus=False) < 0


def test_off_map_flag():
    """off-map 分诊:低于有效密度 → True(日志独立维度)。"""
    m = CompetenceMap()
    rare = cell_id('虫族', 3, 20, '部分')
    assert m.off_map(rare) is True
    for _ in range(8):
        m.observe(rare)
    assert m.off_map(rare) is False
