import socket
from PyQt5.QtCore import QObject, pyqtSignal, QThread

class TCPServerWorker(QObject):
    # 自定义信号：接收到客户端命令
    received_command = pyqtSignal(str)  # 参数类型为 str
    destroyed = pyqtSignal()  # 用于检测线程是否销毁
    def __init__(self, host='127.0.0.1', port=6000):
        super().__init__()
        self.host = host
        
        self.port = port
        print(f"TCP服务器已启动，监听地址: {self.host}:{self.port}")
        self.running = True
        self.server_socket = None
        self.client_socket = None  # 存储客户端连接的 socket

    def run(self):
        """在独立线程中运行 TCP 服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"TCP 服务器已启动，监听 {self.host}:{self.port} ...")

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                self.client_socket=client_socket
                print(f"客户端已连接: {addr}")
                self.handle_client(client_socket)
            except Exception as e:
                print(f"服务器错误: {e}")
                break

    def handle_client(self, client_socket):
        """处理客户端交互"""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break  # 客户端断开连接
                
                message = data.decode('utf-8').strip()
                print(f"收到消息: {message}")
                
                # === 发送信号：传递接收到的命令 ===
                self.received_command.emit(message)  # 发射信号
                
                # 特定命令退出
                if message.lower() == "exit":
                    client_socket.send("服务器已结束连接。".encode('utf-8'))
                    break
                #else:
                    # 回传确认信息（可选）
                    #client_socket.send(f"已收到: {message}".encode('utf-8'))
        except Exception as e:
            print(f"客户端通信错误: {e}")
        finally:
            client_socket.close()
            print("客户端连接已关闭")

    def stop(self):
        """停止服务器"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.client_socket:
            self.client_socket.close()
        print("TCP 服务器已关闭")
        self.destroyed.emit()
    
    def send_response(self, response):
        """将响应发送给客户端"""
        if self.client_socket is not None:
            self.client_socket.send(response.encode('ascii'))
            print("已发送响应：", response)