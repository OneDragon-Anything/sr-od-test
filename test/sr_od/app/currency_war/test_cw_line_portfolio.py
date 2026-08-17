"""cw_line_portfolio(21 号线组合管理器 v0)测试:T2 方向性/T3 容量/交棒(ADR-0172)。"""
from sr_od.application.currency_war.cw_line_portfolio import Line, LinePortfolio


def _portfolio(capacity=9):
    lines = [
        Line('列车线', ('姬子·启行', '瓦尔特'), entry_cost=5.0, exit_cost=8.0),
        Line('万敌线', ('万敌', '黑塔'), entry_cost=3.0, exit_cost=5.0),
        Line('量子线', ('希儿', '银狼'), entry_cost=6.0, exit_cost=9.0),
    ]
    return LinePortfolio(lines, capacity=capacity)


def test_t2_evidence_directionality():
    """T2:开局 boss 克 A 线 → A 后验被压(argmax 翻转到其他线)。"""
    pf = _portfolio()
    pf.boss_prior({'列车线': 0.1, '万敌线': 0.5, '量子线': 0.6})   # boss 克列车
    w = pf.normalized_weights()
    assert w['列车线'] < w['量子线']
    assert pf.lines['列车线'].posterior < pf.lines['量子线'].posterior


def test_t2_pool_depletion_pushes_line_down():
    """T2:核心卡池枯(LR 高)→ 线后验压(不用等 drought 5 轮)。"""
    pf = _portfolio()
    pf.pool_feasibility({'量子线': 8.0})   # 量子核心枯
    w = pf.normalized_weights()
    assert w['量子线'] < w['列车线']


def test_t2_pickup_shock_boosts_dependent():
    """T2:棱彩拾取冲击:依赖线上跳,无关下压(硬绑表=依赖度 1 特例)。"""
    pf = _portfolio()
    pf.pickup_shock('黑塔纪元', {'列车线': 0.1, '万敌线': 0.9, '量子线': 0.1})
    assert pf.lines['万敌线'].posterior > pf.lines['列车线'].posterior


def test_t3_concentration_gate_paths():
    """T3/集中门:后验分离触发;判别耗尽强制集中;未触发时多线持有。"""
    pf = _portfolio()
    ok, why = pf.concentration_gate()
    assert not ok and '多线持有' in why
    # 强证据分离
    pf.boss_prior({'量子线': 0.95})
    pf.pool_feasibility({'列车线': 6.0, '万敌线': 6.0})
    ok2, why2 = pf.concentration_gate()
    assert ok2 and '后验分离' in why2
    assert pf.concentrated == '量子线'
    # 集中后静默(交棒)
    ok3, why3 = pf.concentration_gate()
    assert ok3 and '静默' in why3


def test_t3_deadline_forced_concentration():
    """判别日程耗尽 → 强制集中到先验最优(=现状行为,损失封顶)。"""
    pf = _portfolio()
    pf.discriminators_consumed(5)      # 全部耗尽
    ok, why = pf.concentration_gate()
    assert ok and '判别日程耗尽' in why


def test_handoff_and_hold_value():
    """交棒协议:集中 → hypothesis 数据;持有价值含共享红利与容量成本。"""
    pf = _portfolio(capacity=9)
    h = pf.hold_value('瓦尔特', {'列车线': 1.0, '量子线': 0.8})   # 两线共享
    h_single = pf.hold_value('万敌', {'万敌线': 1.0})
    assert h > 0 and '共享' not in str(h)   # 数值语义(共享红利已含)
    # 容量逼紧 → 持有更贵(值更低)
    pf_tight = _portfolio(capacity=1)
    v_loose = pf.hold_value('X', {'列车线': 1.0})
    v_tight = pf_tight.hold_value('X', {'列车线': 1.0})
    assert v_tight < v_loose
    # 交棒
    pf.boss_prior({'量子线': 0.95})
    pf.pool_feasibility({'列车线': 6.0, '万敌线': 6.0})
    pf.concentration_gate()
    hand = pf.handoff_hypothesis()
    assert hand is not None and hand[0] == '量子线' and 0 in hand[1]
