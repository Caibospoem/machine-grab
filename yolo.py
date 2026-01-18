import requests
import json
from pathlib import Path

def test_remote_yolo():
    # 1. API 配置
    # 如果是远程服务器，请将 127.0.0.1 换成服务器 IP，比如 http://192.168.1.100:8000/...
    api_url = "https://api.xnnehang.top/yolo/final"
    
    # 2. 图片路径
    image_path = Path("4.jpg")
    
    if not image_path.exists():
        print(f"❌ 错误: 图片文件不存在: {image_path}")
        return

    print(f"📡 正在向 {api_url} 发送图片...")

    try:
        # 3. 发送 POST 请求
        # 'file' 是服务端 FastAPI 中定义的参数名 (file: UploadFile)
        # 必须用 rb (二进制读取) 模式打开
        with open(image_path, "rb") as f:
            # files 参数格式: {'参数名': ('文件名', 文件对象, 'MIME类型')}
            files = {"file": (image_path.name, f, "image/jpeg")}
            
            response = requests.post(api_url, files=files)

        # 4. 检查响应状态
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功! 服务端返回:")
            # 美化打印 JSON
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # 简单的结果解析展示
            detections = result.get("detections", [])

            # 你需要的输出
            tempPoints = []

            # 你自己的 color（这里给个示例：如果 command 里有就用，没有就默认 0）
            # 如果 command 不是 dict，就把这行改成你自己的 color 值
            color = 0

            for det in detections:
                # 只处理电池（按你的返回示例 name = "batteries"）
                if det.get("name") != "batteries":
                    continue

                xmin = float(det["xmin"])
                ymin = float(det["ymin"])
                xmax = float(det["xmax"])
                ymax = float(det["ymax"])

                # 中心点（注意：图像坐标一般 x=列 col, y=行 row）
                cx = (xmin + xmax) / 2.0  # x 中心
                cy = (ymin + ymax) / 2.0  # y 中心

                # YOLO 返回里没有角度，先给 0（单位：度）
                angle_deg = 0.0

                # 如果你坚持 row= x, col= y，就这样放：
                tempPoints.append([5, color, cx, cy, angle_deg])

                # 如果你想按“row= y, col= x”的常规习惯，就换成：
                # tempPoints.append([5, color, cy, cx, angle_deg])

            rest = tempPoints  # ✅ rest 就是你要的数组

            print("🔍 解析后的结果 (rest):", rest)
        else:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print("响应内容:", response.text)

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请检查 FastAPI 是否正在运行，IP和端口是否正确。")
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    test_remote_yolo()