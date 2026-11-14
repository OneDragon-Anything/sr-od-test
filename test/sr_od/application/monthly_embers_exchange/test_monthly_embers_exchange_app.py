"""MonthlyEmbersExchangeApp 可测逻辑:兑换排序 / 结果分支 / 运行记录字段。

运行记录测试把写盘根重定向 tmp_path(monkeypatch os_utils,测试纪律:
项目目录内不写任何文件)。
"""

from one_dragon.base.operation.application_run_record import AppRunRecord
from sr_od.application.monthly_embers_exchange.monthly_embers_exchange_app import (
    classify_purchase_result,
    resolve_exchange_order,
)
from sr_od.application.monthly_embers_exchange.monthly_embers_exchange_run_record import (
    MonthlyEmbersExchangeRunRecord,
)


def test_resolve_exchange_order_priority_and_filter() -> None:
    """关闭项过滤 + priority 升序。"""
    order = resolve_exchange_order([
        ('special_pass', True, 10),
        ('pass', False, 20),
        ('tracks_of_destiny', True, 5),
    ])
    assert order == ['tracks_of_destiny', 'special_pass'], order


def test_resolve_exchange_order_tie_uses_fixed_order() -> None:
    """同优先级按固定序兜底:专票 > 通票 > 足迹(用户裁定 8)。"""
    order = resolve_exchange_order([
        ('tracks_of_destiny', True, 10),
        ('pass', True, 10),
        ('special_pass', True, 10),
    ])
    assert order == ['special_pass', 'pass', 'tracks_of_destiny'], order


def test_resolve_exchange_order_all_disabled() -> None:
    """全部关闭 = 空顺序(预期内无事可做,照常标完成)。"""
    assert resolve_exchange_order([
        ('special_pass', False, 10),
        ('pass', False, 20),
        ('tracks_of_destiny', False, 30),
    ]) == []


def test_classify_purchase_result_branches() -> None:
    """§3.1 分支表:四语义态 + 成功 + 无语义非预期。"""
    assert classify_purchase_result(True, None) == 'BOUGHT'
    assert classify_purchase_result(False, 'SOLD_OUT') == 'SKIP'
    assert classify_purchase_result(False, 'CARD_UNAVAILABLE') == 'SKIP'
    assert classify_purchase_result(False, 'NOT_FOUND') == 'SKIP'
    assert classify_purchase_result(False, 'INSUFFICIENT_MATERIALS') == 'STOP_BALANCE'
    assert classify_purchase_result(False, None) == 'ABORT'


def test_run_record_skip_and_reset(
    tmp_path,
    monkeypatch,
) -> None:
    """skip_note 追加格式(goods:STATUS 分号连接)+ reset 清零。"""
    monkeypatch.setattr(
        'one_dragon.utils.os_utils.get_path_under_work_dir',
        lambda *parts: str(tmp_path),
    )
    record = MonthlyEmbersExchangeRunRecord()
    record.record_purchase('pass', 2)
    record.record_skip('special_pass:SOLD_OUT')
    record.record_skip('tracks_of_destiny:SKIP_BALANCE')
    record.record_balance_left(41382)
    assert record.bought_pass == 2
    assert record.skip_note == 'special_pass:SOLD_OUT;tracks_of_destiny:SKIP_BALANCE'
    assert record.balance_left == 41382

    record.reset_record()
    assert record.run_status == AppRunRecord.STATUS_WAIT
    assert record.bought_pass == 0
    assert record.skip_note == ''
    assert record.balance_left is None
