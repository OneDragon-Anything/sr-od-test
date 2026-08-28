"""cw_first_passage(18 号目标函数层 v0)测试:K1 理论对拍 + 三区律(ADR-0161)
+ v1 位面条件化与 hp_floor 反解(ADR-0176)。"""
import math

from sr_od.application.currency_war.cw_first_passage import (
    _loss_dist,
    first_passage_win,
    hp_floor,
    plane_hp_ratio,
    p_win_lambda,
    posture_guidance,
    risk_posture,
)


def test_k1_gamblers_ruin_flip():
    """K1 核心:同均值异方差两线,选择随 hp 翻转(教学校验例)。

    线 A(低方差,板强 3):μ≈0.8 → hp=25 剩 2 节点必活。
    线 B(高方差,板强 0):μ≈14,CV 0.5 → 掉血离散大,hp=15 剩 2 节点均值必死但右尾存活。
    """
    # HP=25 剩 2 节点:A 必活,B 有死亡尾
    pa = first_passage_win(3, 25, 2)
    pb = first_passage_win(0, 25, 2)
    assert pa > pb
    # HP=15 剩 2 节点:A(强板)仍高;弱板 B 的 P(win) 仍有右尾 > 0(首达语义:不是期望判死)
    pb15 = first_passage_win(0, 15, 2)
    assert 0.0 < pb15 < 0.5


def test_first_passage_monotone():
    """P(win) 对 hp 单调不减;nodes_left 越多越难。"""
    for hp in (10, 30, 60):
        assert first_passage_win(2, hp, 5) >= first_passage_win(2, hp - 1, 5)
    assert first_passage_win(2, 40, 9) <= first_passage_win(2, 40, 2)


def test_lambda_peak_shape():
    """λ_hp 峰形断言(18 号主张二):远离屏障≈0 → 临界带峰 → 漂移深处回落。

    弱板(μ=14)剩 9 节点:均值耗血 126 → hp=200(远离)λ 小;hp≈120-140(P(win) 0.4-0.85
    临界带)λ 峰;hp=60(均值路径深处,P(win)≈0)λ 回落为 0。
    (弱板长程下「必死边缘」的 hp 绝对值高 —— 漂移 14/节点把屏障推到 ~130;三区律的区
    边界由 (μ, hp, nodes) 联合解出,正是「手写 hp 阈值」要被替代的证据。)
    """
    lam_far = p_win_lambda(0, 200, 9)
    lam_peak = max(p_win_lambda(0, h, 9) for h in range(115, 145, 5))
    lam_deep = p_win_lambda(0, 60, 9)
    assert lam_peak > lam_far       # 峰 > 远离屏障区
    assert lam_peak > lam_deep      # 峰 > 漂移深处(P(win)≈0 区,±1 血无差)


def test_three_zones():
    """三区律:强板高血=盈余;中血=临界;弱板低血长程=必死边缘。"""
    assert risk_posture(3, 90, 3) in ('盈余', '临界')
    assert risk_posture(0, 10, 9) == '必死边缘'
    assert posture_guidance('必死边缘').startswith('方差追求')
    assert posture_guidance('临界').startswith('方差回避')


def test_degenerate_cases():
    assert first_passage_win(3, 100, 0) == 1.0   # 无节点剩 = 活
    assert first_passage_win(3, 0, 1) == 0.0     # 无血 = 死


# —— v1(ADR-0176):位面条件化 + hp_floor 反解 + 位面乘子模型导出 ——


def test_plane_scales_loss():
    """位面难度进掉血分布(W443 合一后 μ 方向由标定决定,非单调先验):
    - tier≥1:P2 严劣于 P1(μ_P2(tier)=(1−p(rung))·L_cond_mix > P1 先验 μ
      tier1 7.0 / tier2 2.5)→ P(win) 单调不升(浮点容差 1e-9);
    - tier0 显式例外:P1 先验 μ0=14(弱板粗锚)高于 P2 标定 μ0≈13.2
      ——P2 无条件期望不含「每战全损」悲观注入,方向反转是标定事实,
      本锁固化防回退到「P2 恒更凶」的旧先验。
    (P3 别名 P2:非单调断言对 plane=3 同值成立。)"""
    for tier in (1, 2):
        for hp in (20, 40, 60):
            p1 = first_passage_win(tier, hp, 6, plane=1)
            p2 = first_passage_win(tier, hp, 6, plane=2)
            p3 = first_passage_win(tier, hp, 6, plane=3)
            assert p1 + 1e-9 >= p2 >= p3 - 1e-9, (
                f"tier={tier} hp={hp}: P1≥P2≥P3 违反({p1:.4f}/{p2:.4f}/{p3:.4f})")
    # tier0 反转例外(P3=P2 别名逐位)
    mu1 = _loss_dist(0, 1)[1][0]
    mu2 = _loss_dist(0, 2)[1][0]
    mu3 = _loss_dist(0, 3)[1][0]
    assert mu1 > mu2, f"P1 弱板先验 μ={mu1} 应高于 P2 标定 μ={mu2}"
    assert mu2 == mu3, "P3 别名 P2(标定域声明)"


def test_hp_floor_definition():
    """hp_floor = 最小 hp 使 P(win) ≥ target;单调、且该 hp-1 处不达 target(有解时)。"""
    for (tier, nodes, target) in ((1, 8, 0.6), (2, 4, 0.7), (3, 6, 0.6)):
        fl = hp_floor(tier, nodes, target)
        assert first_passage_win(tier, fl, nodes) >= target, f"floor {fl} 未达 target"
        if 1 < fl < 100:
            assert first_passage_win(tier, fl - 1, nodes) < target, f"floor {fl} 非最小"
    # 强板短程:低血即可达标 → 地板低
    assert hp_floor(3, 2, 0.6) <= 10
    # 弱板长程:hp_cap 内无解 → 返回 cap(模型如实说「无底可保」,决策侧由 ratio 接管)
    assert hp_floor(0, 9, 0.9) == 100


def test_plane_hp_ratio_semantics():
    """位面乘子语义(W443 两态标定合一后的现语义;旧 0176 v1 主张
    「弱板长程 > 强板短程」随 PLANE_LOSS_SCALE 退役——新标定下强板
    P1 分支 μ 极小(0.8)而 P2 μ 由胜率通道给出(≈4.6),比值天然顶
    2.0 夹界,方向反转是标定事实非退化):

    - 弱板长程:ratio > 1(该更早保血);
    - 强板短程:顶 2.0 夹界(P1 分母极小,P2 标定 μ 相对大);
    - 夹界:任意 (tier, nodes) ratio ∈ [1.0, 2.0];
    - P3 别名 P2(标定域声明)逐位相等;
    - 弱板长程扩展 cap:真实血上限内两原均无解时 ratio 仍正确(≠1 假性退化)。
    """
    r2_weak = plane_hp_ratio(1, 9, target_pwin=0.6, plane=2)
    r3_weak = plane_hp_ratio(1, 9, target_pwin=0.6, plane=3)
    assert r2_weak > 1.0, "弱板长程 P2 应上浮"
    assert r2_weak == r3_weak, "P3 别名 P2 → 乘子逐位相等"
    r2_strong = plane_hp_ratio(3, 2, target_pwin=0.6, plane=2)
    assert r2_strong == 2.0, "强板短程顶夹界(P1 分支 μ=0.8 vs P2 标定)"
    for tier in (0, 1, 2, 3):
        for nodes in (2, 6, 9, 18):
            for plane in (2, 3):
                r = plane_hp_ratio(tier, nodes, target_pwin=0.6, plane=plane)
                assert 1.0 <= r <= 2.0, f"ratio 夹界违反:tier={tier} n={nodes} p={plane} → {r}"
    # 扩展 cap:tier0 长程真实 cap 内两原无解,ratio 仍反映位面标定(不退化 1.0)
    r0 = plane_hp_ratio(0, 18, target_pwin=0.6, plane=2)
    assert r0 >= 1.0