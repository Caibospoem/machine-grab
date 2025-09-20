import sys
from PyQt5.QtWidgets import QMainWindow, QApplication
from View.Ui_main_ui import Ui_MainWindow
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QMessageBox
import halcon as ha
import math
import modelData as md
import runData as rd
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QThread
from TCPServerThread import TCPServerWorker
from calib import CalibWindow
from cameraWorker import CameraWorker

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        # Setup the UI components
        self.setupUi(self)
        # Connect signals and slots (optional)
        self.pbOpen.clicked.connect(self.on_open_clicked)
        self.pBRead.clicked.connect(self.on_Read_clicked)
        self.pbStop.clicked.connect(self.on_stop_clicked)
        self.cbReal.stateChanged.connect(self.on_real_clicked)
        self.pbSave.clicked.connect(self.on_save_clicked)
        self.TestAction.triggered.connect(self.on_findModel_clicked)
        self.pbCreateModel.clicked.connect(self.on_createModel_clicked)
        self.pbStartTcp.clicked.connect(self.on_startTcp_clicked)
        self.calibAction.triggered.connect(self.on_calib_clicked)
        self.haWindow.roiChanged.connect(self.on_roi_changed)
        self.ImagePoints = []
        self.runData=rd.runData.load("run_data_backup.json")
        self.modelData=md.ModelData.load("model_data_backup.json")
        self.tcp_worker = None
        self.cameraHandle = None
        self.camera_worker = None

    def on_save_clicked(self):
        if self.haWindow.h_image is not None:
            file_name, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "Images (*.png *.jpg *.bmp)")
            if file_name:
                ha.write_image(self.haWindow.h_image, "bmp",0, file_name)
                QMessageBox.information(self, "Success", "Image saved successfully.")
        else:
            QMessageBox.warning(self, "Warning", "No image to save.")

    def on_open_clicked(self):
         self.cameraHandle = ha.open_framegrabber("MVision", 1, 1, 0, 0, 0, 0, "progressive", 8, "default", -1, "false", "auto", "GEV:DA6028740 cam02", 0, -1)
         self.pbOpen.setEnabled(False)
         self.cbReal.setEnabled(True)
         
    def on_stop_clicked(self):
        if self.cameraHandle is not None:
            ha.close_framegrabber(self.cameraHandle)
        self.pbOpen.setEnabled(True)
        self.cbReal.setEnabled(False)
    def on_real_clicked(self,state):
        if state == 2:
            self.start_camera_thread()
        else:
            self.stop_camera_thread()

    def start_camera_thread(self):
        # 如果已经有摄像头线程在运行，先停止它
        if self.camera_worker is not None:
            self.stop_camera_thread()
        
        # 确保摄像头已经打开
        if self.cameraHandle is None:
            self.on_open_clicked()
            
            if self.cameraHandle is None:
                QMessageBox.warning(self, "Warning", "Failed to open camera. Please check camera connection.")
                self.cbReal.setChecked(False)
                return
        self.camera_worker = CameraWorker(self.cameraHandle)
        # 创建摄像头线程和工作对象
        self.camera_thread = QThread()
        
        
        # 将Worker移动到线程中
        self.camera_worker.moveToThread(self.camera_thread)
        
        # 连接信号与槽
        self.camera_thread.started.connect(self.camera_worker.run)
        self.camera_worker.image_ready.connect(self.process_camera_image)
        self.camera_worker.error_occurred.connect(self.handle_camera_error)
        self.camera_worker.destroyed.connect(self.camera_thread.quit)
        self.camera_thread.finished.connect(self.camera_thread.deleteLater)
        
        # 启动线程
        self.camera_thread.start()

    def process_camera_image(self, image):
        self.haWindow.set_image(image)
        self.haWindow.update()
    def handle_camera_error(self, error_message):
        QMessageBox.critical(self, "Camera Error", error_message)
        self.stop_camera_thread()
        self.cbReal.setChecked(False)
    def stop_camera_thread(self):
        if self.camera_worker is not None:
            if self.camera_worker.running:
                self.camera_worker.stop()
            self.camera_worker = None
            # 确保线程完全停止
            if self.camera_thread is not None:
                self.camera_thread.quit()
                self.camera_thread.wait(1000)
                self.camera_thread = None
    def on_calib_clicked(self):
        
        self.calibWindow = CalibWindow()  # Create an instance of the CalibWindow class
        self.calibWindow.modelData=self.modelData
        self.calibWindow.show()  # Show the window
    def on_startTcp_clicked(self):
        
        if self.tcp_worker is not None and self.tcp_worker.running:
            self.tcp_worker.stop()
            self.pbStartTcp.setText("启动")
        else:
            self.init_tcp_server()
            self.pbStartTcp.setText("停止")
        
    def init_tcp_server(self):
        # 创建 TCP 服务器线程
        self.tcp_thread = QThread()
        self.tcp_worker = TCPServerWorker(self.leAddress.text(), self.spPort.value())

        # 将 Worker 移动到线程中
        self.tcp_worker.moveToThread(self.tcp_thread)

        # 连接信号与槽
        self.tcp_thread.started.connect(self.tcp_worker.run)  # 线程启动时运行服务器
        self.tcp_worker.received_command.connect(self.on_received_command)  # 接收命令信号
        self.tcp_worker.destroyed.connect(self.tcp_thread.quit)  # Worker 销毁时退出线程
        self.tcp_thread.finished.connect(self.tcp_thread.deleteLater)  # 线程结束时清理

        # 启动线程
        self.tcp_thread.start()

    def on_received_command(self, command):
        print(command)
        rest = self.process()
        for i in range(len(rest)):
            row =rest[i][0]
            col =rest[i][1]
            ha.affine_trans_point_2d(self.modelData.matrix, row, col)
            
        if rest is not None:
            self.tcp_worker.send_response(",".join(map(str,rest)))

    def closeEvent(self, event):
       
        """
        Handle the window close event.
        """
        # Optional: Prompt the user to confirm exiting
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Save modelData state before closing
            try:
                #self.modelData.save("model_data_backup.json")  # Replace with your desired path
                self.runData.save("run_data_backup.json")
                event.accept()  # Proceed with closing
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save data: {str(e)}")
                event.ignore()  # Cancel closing
        else:
            event.ignore()  # Cancel closing
    def process(self):
        if self.haWindow.h_image is not None and self.runData.modelId is not None:
                row,col,angle,score = ha.find_shape_model(self.haWindow.h_image, self.runData.modelId, -0.39, 7, 0.5, 0, 0.5, "least_squares", 2, 0.9)
                if(len(row) == 0):
                    return
                tempPoints=[]
                for i in range(len(row)):
                    self.haWindow.disp_text(f"row: {row[i]:.2f},col: {float(col[i]):.2f}","image", row[i],col[i]+20,"black",[],[])
                    tempPoints.append([row[i],col[i],angle[i]])
                return tempPoints
                    


    def on_Read_clicked(self):
        # 打开文件对话框，选择图像文件
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.bmp);;All Files (*)")
        if file_path:
            # 使用 HalconView 显示图像
            self.haWindow.clear()
            self.haWindow.load_image(file_path)
            self.process()
                

    
    def on_roi_changed(self, draw, event):
        self.haWindow.clearRegions()
        # 处理创建模型的逻辑
        regions = self.haWindow.get_rois_regions()
        for region in regions:
            self.haWindow.disp_obj(region, "green","margin")
        if len(regions) > 0:
            try:
                roiParam=self.haWindow.get_rois_params()  
                region =ha.gen_rectangle2(roiParam[0]['row'],roiParam[0]['column'],roiParam[0]['phi'],roiParam[0]['length1'],roiParam[0]['length2'])  
                _, rowCenter,colCenter=ha.area_center(region)         
                modelImage=ha.reduce_domain(self.haWindow.h_image,region)
                self.runData.modelId = ha.create_shape_model(modelImage,"auto", 0, 7, "auto", "auto", 'use_polarity', "auto", "auto")
                contour = ha.get_shape_model_contours(self.runData.modelId, 1 )

                hom = ha.vector_angle_to_rigid(0, 0, 0, rowCenter, colCenter, 0)
                self.runData.baseRow=rowCenter
                self.runData.baseCol=colCenter
                affineContour = ha.affine_trans_contour_xld(contour, hom)
                # 显示最终的模型轮廓
                self.haWindow.disp_obj(affineContour,"red")
            except Exception as e:
                print(f"Error: {e}")
    

    
    def on_createModel_clicked(self):
        self.createFlg="shape"
        self.haWindow.clear()
        self.haWindow.add_rectangle2(row=100, col=100, phi=0, length1=50, length2=50, color="red")        
            
    def on_findModel_clicked(self):
        # 处理查找模型的逻辑
        self.process()

    def calculate_rectangle_vertices(self, cy,cx, theta, length, width):
        # 将角度转换为弧度
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        
        # 未旋转时相对于中心的顶点
        points_relative = [
            (length , width ),
            (length , -width ),
            (-length , -width ),
            (-length , width )
        ]
        
        vertices = []
        for x0, y0 in points_relative:
            # 旋转
            x_rotated = x0 * cos_theta - y0 * sin_theta
            y_rotated = x0 * sin_theta + y0 * cos_theta
            # 平移
            x_final = x_rotated + cx
            y_final = y_rotated + cy
            vertices.append((x_final, y_final))
        
        return vertices

# Create application and run
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())