import numpy as np
from PIL import Image

def generate_chunky_noise(width=1920, height=1080, pixel_size=10, output_path="chunky_noise.png"):
    """
    width: 最终图片的宽度
    height: 最终图片的高度
    pixel_size: 每个“噪点方块”的大小（像素）
    """
    # 计算缩小后的分辨率
    low_res_width = width // pixel_size
    low_res_height = height // pixel_size

    # 1. 先生成一个小尺寸的随机数组
    random_pixels = np.random.randint(0, 256, (low_res_height, low_res_width), dtype=np.uint8)
    
    # 2. 转换为图片
    img = Image.fromarray(random_pixels)
    
    # 3. 使用 NEAREST (最近邻插值) 放大回原始尺寸
    # 这样一个像素点就会变成一个 pixel_size x pixel_size 的大方块
    img = img.resize((width, height), resample=Image.NEAREST)
    
    # 保存
    img.save(output_path)

if __name__ == "__main__":
    generate_chunky_noise(pixel_size=10)