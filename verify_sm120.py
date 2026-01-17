#!/usr/bin/env python3
"""
验证脚本：检查 Docker 镜像是否支持 sm_120 (RTX 50 系列)
运行方式：docker run --gpus all yue-inference:cuda13 python /app/verify_sm120.py
"""

import sys
import torch

def check_cuda_availability():
    """检查 CUDA 是否可用"""
    print("=" * 60)
    print("CUDA 支持检查")
    print("=" * 60)
    
    if not torch.cuda.is_available():
        print("❌ CUDA 不可用！")
        return False
    
    print("✅ CUDA 可用")
    print(f"   CUDA 版本: {torch.version.cuda}")
    print(f"   cuDNN 版本: {torch.backends.cudnn.version()}")
    return True

def check_gpu_info():
    """检查 GPU 信息"""
    print("\n" + "=" * 60)
    print("GPU 信息")
    print("=" * 60)
    
    device_count = torch.cuda.device_count()
    print(f"GPU 数量: {device_count}")
    
    for i in range(device_count):
        print(f"\nGPU {i}:")
        print(f"  名称: {torch.cuda.get_device_name(i)}")
        
        # 获取计算能力
        capability = torch.cuda.get_device_capability(i)
        print(f"  计算能力 (Compute Capability): {capability[0]}.{capability[1]}")
        
        # 判断是否为 sm_120
        if capability[0] == 12 and capability[1] == 0:
            print("  ✅ 这是 sm_120 (Blackwell 架构，RTX 50 系列)")
        elif capability[0] >= 12:
            print(f"  ⚠️  这是 sm_{capability[0]}{capability[1]} (可能是更新的架构)")
        else:
            print(f"  ℹ️  这是 sm_{capability[0]}{capability[1]} (非 Blackwell 架构)")
        
        # 显存信息
        props = torch.cuda.get_device_properties(i)
        print(f"  总显存: {props.total_memory / 1024**3:.2f} GB")
        print(f"  多处理器数量: {props.multi_processor_count}")

def check_arch_support():
    """检查架构支持"""
    print("\n" + "=" * 60)
    print("架构支持检查")
    print("=" * 60)
    
    try:
        # 获取支持的架构列表
        arch_list = torch.cuda.get_arch_list()
        print(f"支持的架构列表: {arch_list}")
        
        # 检查是否包含 sm_120
        if 'sm_120' in arch_list or '12.0' in str(arch_list):
            print("✅ sm_120 架构在支持列表中")
            return True
        else:
            print("❌ sm_120 架构不在支持列表中")
            print("   这意味着 PyTorch 可能没有为 sm_120 编译内核")
            return False
    except Exception as e:
        print(f"⚠️  无法获取架构列表: {e}")
        return False

def test_tensor_operations():
    """测试张量操作"""
    print("\n" + "=" * 60)
    print("GPU 张量操作测试")
    print("=" * 60)
    
    try:
        # 创建测试张量
        device = torch.device('cuda:0')
        x = torch.randn(1000, 1000, device=device)
        y = torch.randn(1000, 1000, device=device)
        
        # 执行矩阵乘法
        z = torch.matmul(x, y)
        
        print("✅ GPU 张量操作成功")
        print(f"   测试张量形状: {z.shape}")
        print(f"   设备: {z.device}")
        return True
    except RuntimeError as e:
        if "no kernel image" in str(e).lower() or "sm_120" in str(e):
            print(f"❌ GPU 操作失败: {e}")
            print("   这通常意味着当前 GPU 架构不被支持")
            return False
        else:
            print(f"⚠️  GPU 操作出错: {e}")
            return False
    except Exception as e:
        print(f"⚠️  测试出错: {e}")
        return False

def check_flash_attention():
    """检查 FlashAttention 是否安装"""
    print("\n" + "=" * 60)
    print("FlashAttention 检查")
    print("=" * 60)
    
    try:
        import flash_attn
        print(f"✅ FlashAttention 已安装")
        print(f"   版本: {flash_attn.__version__ if hasattr(flash_attn, '__version__') else '未知'}")
        return True
    except ImportError:
        print("⚠️  FlashAttention 未安装")
        print("   这可能会影响 YuE 的性能和内存使用")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("YuE Docker 镜像 sm_120 支持验证")
    print("=" * 60)
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"Python 版本: {sys.version}")
    
    results = {
        'cuda_available': False,
        'arch_supported': False,
        'tensor_ops': False,
        'flash_attn': False
    }
    
    # 检查 CUDA
    results['cuda_available'] = check_cuda_availability()
    if not results['cuda_available']:
        print("\n❌ CUDA 不可用，无法继续检查")
        sys.exit(1)
    
    # 检查 GPU 信息
    check_gpu_info()
    
    # 检查架构支持
    results['arch_supported'] = check_arch_support()
    
    # 测试张量操作
    results['tensor_ops'] = test_tensor_operations()
    
    # 检查 FlashAttention
    results['flash_attn'] = check_flash_attention()
    
    # 总结
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    
    all_passed = all([
        results['cuda_available'],
        results['arch_supported'],
        results['tensor_ops']
    ])
    
    if all_passed:
        print("✅ 所有关键检查通过！镜像应该可以在 RTX 50 系列显卡上运行")
    else:
        print("⚠️  部分检查未通过，可能存在问题：")
        if not results['arch_supported']:
            print("   - PyTorch 可能没有为 sm_120 编译内核")
            print("   - 建议使用 PyTorch nightly 构建")
        if not results['tensor_ops']:
            print("   - GPU 张量操作失败")
            print("   - 可能是驱动版本过低或架构不支持")
    
    if results['flash_attn']:
        print("✅ FlashAttention 已安装，YuE 应该可以正常运行")
    else:
        print("⚠️  FlashAttention 未安装，可能影响性能")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

