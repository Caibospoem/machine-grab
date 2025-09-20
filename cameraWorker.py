from PyQt5.QtCore import QObject, QThread, pyqtSignal

import halcon as ha

class CameraWorker(QObject):
    image_ready = pyqtSignal(object)  # 用于发送获取到的图像
    error_occurred = pyqtSignal(str)  # 用于发送错误信息

    def __init__(self, camera_handle):
        super().__init__()
        self.camera_handle = camera_handle
        self.running = False
        
    def run(self):
        self.running = True
        while self.running:
            try:
                # 从摄像头获取图像
                image = ha.grab_image(self.camera_handle)
                # 发送图像信号
                self.image_ready.emit(image)
                # 简单延时，避免占用过多CPU
                QThread.msleep(30)
            except Exception as e:
                self.error_occurred.emit(f"Camera error: {str(e)}")
                break
                
    def stop(self):
        self.running = False