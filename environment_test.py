import torch

# 检查CUDA是否可用
if torch.cuda.is_available():
    print("CUDA 可用")
    # 获取当前CUDA设备
    device = torch.device("cuda")
    print(f"当前CUDA设备: {torch.cuda.get_device_name(0)}")
else:
    print("CUDA 不可用")