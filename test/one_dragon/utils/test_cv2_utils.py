"""契约锁:save_image 的 webp 落盘是无损编码,经 read_image 回读与源像素逐值相等。

背景:模板资产规范依赖「裁模板用 webp 无损归档」(AGENTS.md 画面识别节),
template_info.save_raw() 的 raw.webp 是唯一固定 webp 落点——若编码有损,模板
像素与归档源静默漂移。OpenCV IMWRITE_WEBP_QUALITY 语义 quality>100 走无损
分支、1-100 全域有损,故 101 是 cv2 4.x 下唯一无损入口(官方 imgcodecs flags
文档);样本用固定种子随机噪声图,有损编码对噪声样本必然产生逐值差异,检出
灵敏度最高。
"""

import numpy as np

from one_dragon.utils.cv2_utils import read_image, save_image


def test_save_image_webp_lossless_roundtrip(tmp_path) -> None:
    """webp 存读往返无损:回读图像与源 RGB 像素 array_equal 为真。"""
    rng = np.random.default_rng(42)
    img = rng.integers(0, 256, size=(120, 160, 3), dtype=np.uint8)

    file_path = str(tmp_path / 'noise.webp')
    save_image(img, file_path)

    loaded = read_image(file_path)
    assert loaded is not None, 'webp 落盘后应可正常回读'
    assert loaded.shape == img.shape
    assert np.array_equal(loaded, img), 'webp 往返必须逐像素无损'
