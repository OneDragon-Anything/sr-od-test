"""W62 件1(ADR-0329)恢复局锁定态检测锁:判据三态 / 探针裁决 / 锁定解除。

判定/探针/解除抽成纯函数(cw_resume_lock.py),battle_loop 只做薄接线——
单帧锁锁纯函数(设计章1.8 测试锁设计)。
"""
from sr_od.application.currency_war.cw_resume_lock import (
    locked_after_start_battle,
    probe_resolve,
    resume_candidate,
)


def test_resume_candidate_three_states():
    """锁 1(判据三态,设计章1.2):
    新 match + round>1 → 候选;正常新局 r1 → 非候选;续跑/局中 → 不检测。"""
    assert resume_candidate(True, 1, 5) is True       # 恢复局(同判据:plane1 round5)
    assert resume_candidate(True, 2, 1) is True       # 恢复局(plane>1 同样候选)
    assert resume_candidate(True, 1, 1) is False      # 正常新局 r1
    assert resume_candidate(False, 2, 3) is False     # bot 自己跑的中间备战,不检测


def test_probe_resolve():
    """锁 2(探针裁决,设计章1.3):商店可开=非锁定;零响应=锁定。"""
    assert probe_resolve(True) == 'normal'
    assert probe_resolve(False) == 'locked'


def test_locked_cleared_on_battle_success():
    """锁 3(解除,设计章1.5/1.8):StartBattle 成功 → 清锁;未落地 → 保锁重试。"""
    assert locked_after_start_battle(True) is False    # 出战成功 → 解除
    assert locked_after_start_battle(False) is True    # 未落地 → 保锁(不新增死循环)
