# 썸네일 배경색 바꾸기 (다시 렌더링하지 않고): 예전 배경 #dce6ee에 가까운 픽셀일수록 새 배경 #f2f4f6 쪽으로 옮긴다.
# 가장자리(부품과 배경이 섞인 픽셀)는 섞인 정도만큼만 옮겨서 테두리가 번지지 않게.
import sys, glob, numpy as np
from PIL import Image
OLD = np.array([0xdc, 0xe6, 0xee], float); NEW = np.array([0xf2, 0xf4, 0xf6], float)
for f in sys.argv[1:]:
    a = np.asarray(Image.open(f).convert('RGB'), float)
    d = np.linalg.norm(a - OLD, axis=2)
    w = np.clip(1 - d / 40, 0, 1)[..., None]          # 배경에 가까울수록 1
    out = np.clip(a + w * (NEW - OLD), 0, 255).astype(np.uint8)
    Image.fromarray(out).save(f, 'WEBP', quality=82)
print(len(sys.argv) - 1, 'files')
