import sys
from PyQt5.QtWidgets import QMainWindow, QApplication
from View.Ui_main_ui import Ui_MainWindow
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread
import halcon as ha
import math
import modelData as md
import runData as rd
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from TCPServerThread import TCPServerWorker
from calib import CalibWindow
from cameraWorker import CameraWorker
import os
import numpy as np
import snap7
import struct
from snap7.util import *
from snap7.type import Areas

import requests
import json
from pathlib import Path

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
        self.pbCreateModel2.clicked.connect(self.on_createModel2_clicked)
        self.pbCreateModel3.clicked.connect(self.on_createModel3_clicked)
        self.pbCreateModel4.clicked.connect(self.on_createModel4_clicked)   
        self.pbCreateModel5.clicked.connect(self.on_createModel5_clicked)
        self.pbStartTcp.clicked.connect(self.on_startTcp_clicked)
        self.calibAction.triggered.connect(self.on_calib_clicked)
        self.haWindow.roiChanged.connect(self.on_roi_changed)
        
        # Auto-calibration buttons (try to connect if they exist, otherwise create dynamically)
        try:
            self.pbSampleNormal.clicked.connect(self.on_sample_normal_clicked)
            self.pbSampleDefect.clicked.connect(self.on_sample_defect_clicked)
        except AttributeError:
            # Create buttons dynamically if not in UI
            from PyQt5.QtWidgets import QPushButton, QHBoxLayout
            try:
                # Try to add buttons to an existing layout (you may need to adjust based on your UI)
                if hasattr(self, 'centralwidget') and hasattr(self.centralwidget, 'layout'):
                    layout = self.centralwidget.layout()
                    if layout is None:
                        layout = QHBoxLayout(self.centralwidget)
                    
                    self.pbSampleNormal = QPushButton("采样正常")
                    self.pbSampleDefect = QPushButton("采样缺陷")
                    self.pbSampleNormal.clicked.connect(self.on_sample_normal_clicked)
                    self.pbSampleDefect.clicked.connect(self.on_sample_defect_clicked)
                    layout.addWidget(self.pbSampleNormal)
                    layout.addWidget(self.pbSampleDefect)
            except Exception as e:
                print(f"Could not create calibration buttons: {e}")
        
        self.ImagePoints = []
        self.runData=rd.runData.load("param/run_data_backup.json")
        self.modelData=md.ModelData.load("param/model_data_backup.json")
        self.leColorName1.setText(self.runData.colorName1)
        self.leColorName2.setText(self.runData.colorName2)
        self.leColorName3.setText(self.runData.colorName3)
        self.spColorMin1.setValue(self.runData.colorMin1)
        self.spColorMax1.setValue(self.runData.colorMax1)
        self.spColorMin2.setValue(self.runData.colorMin2)
        self.spColorMax2.setValue(self.runData.colorMax2)
        self.spColorMin3.setValue(self.runData.colorMin3)
        self.spColorMax3.setValue(self.runData.colorMax3)

        self.tcp_worker = None
        self.cameraHandle = None
        self.camera_worker = None
        self.shapeId=1
        self.plc_client=snap7.client.Client()
        try:
            self.plc_client.connect("192.168.0.1",0,1)
            if self.plc_client.get_connected():
                print("连接plc成功")
            else:
                print("连接plc失败")
        except:
            print("连接plc失败")
        

    def on_save_clicked(self):
        if self.haWindow.h_image is not None:
            file_name, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "Images (*.png *.jpg *.bmp)")
            if file_name:
                ha.write_image(self.haWindow.h_image, "bmp",0, file_name)
                QMessageBox.information(self, "Success", "Image saved successfully.")
        else:
            QMessageBox.warning(self, "Warning", "No image to save.")

    def on_open_clicked(self):
        self.cameraHandle = ha.open_framegrabber("MVision", 1, 1, 0, 0, 0, 0, "progressive", 8, "default", -1, "false", "auto", "GEV:DA7209078 MV-CS050-60GC", 0, -1)
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
        image = ha.grab_image(self.cameraHandle)
        self.haWindow.set_image(image)
        
        api_url = "https://api.xnnehang.top/yolo/final"

        # 1) 编码成 jpg（也可以改成 .png）
        ok, buf = cv2.imencode(".jpg", image)
        if not ok:
            raise RuntimeError("imencode failed")
        # 2) 组织 multipart files
        files = {
            "file": ("frame.jpg", buf.tobytes(), "image/jpeg")  # 字段名通常是 file / image，看你接口要求
        }

        try:
            response = requests.post(api_url, files=files)
            result = response.json()
        except Exception as e:
            print("request error:", e)

        result = {
            "detections": [
                {
                    "xmin": 437.20843505859375,
                    "ymin": 814.6345825195312,
                    "xmax": 1012.6439819335938,
                    "ymax": 1054.2001953125,
                    "confidence": 0.9252163171768188,
                    "class": 0,
                    "name": "batteries"
                }
            ],
            "code": "200",
            "message": "Object detection processed successfully"
        }


        self.haWindow.update()

        detections = result.get("detections", [])

        # 你需要的输出
        tempPoints = []

        # 你自己的 color（这里给个示例：如果 command 里有就用，没有就默认 0）
        # 如果 command 不是 dict，就把这行改成你自己的 color 值
        color = command.get("color", 0) if isinstance(command, dict) else 0

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

        # rest = self.process()
        strrest = ""
        if(command=="1"):
            outPoints = self.remove_close_points_both(rest,400)
            
            for i in range(1):
                if(len(outPoints)>=1 and outPoints[i][2]>229 and outPoints[i][2]<2004 and outPoints[i][3]>591 and outPoints[i][3]<1936):
                    row =outPoints[i][2]
                    col =outPoints[i][3]
                    id = outPoints[i][0]
                    y,x= ha.affine_trans_point_2d(self.modelData.matrix, row, col)
                    if(len(x)>0 and len(y)>0):
                        strrest = strrest + f"{outPoints[i][0]},{outPoints[i][1]},{x[0]:.2f},{y[0]:.2f},{outPoints[i][4]:.2f},"
                        int_bytes = struct.pack("h",outPoints[i][1]) # 将整数打包为2字节的大端格式
                        self.plc_client.write_area(Areas.MK,0,4,int_bytes)
                        print(f"写入{outPoints[i][1]}")
        elif(command=="2"):
            for i in range(len(rest)):
                if(rest[i][1]==2 and rest[i][2]>229 and rest[i][2]<2004 and rest[i][3]>591 and rest[i][3]<1936):
                    row =rest[i][2]
                    col =rest[i][3]
                    id = rest[i][0]
                    y,x= ha.affine_trans_point_2d(self.modelData.matrix, row, col)
                    if(len(x)>0 and len(y)>0 ) :
                        strrest = strrest + f"{rest[i][0]},{rest[i][1]},{x[0]:.2f},{y[0]:.2f},{rest[i][4]:.2f},"
                        int_bytes = struct.pack("h",rest[i][1]) # 将整数打包为2字节的大端格式
                        self.plc_client.write_area(Areas.MK,0,4,int_bytes)
                        print(f"写入{rest[i][1]}")
                        break
        elif(command=="3"):
            for i in range(len(rest)):
                if(rest[i][1]==3 and rest[i][2]>229 and rest[i][2]<2004 and rest[i][3]>591 and rest[i][3]<1936):
                    row =rest[i][2]
                    col =rest[i][3]
                    id = rest[i][0]
                    y,x= ha.affine_trans_point_2d(self.modelData.matrix, row, col)
                    if(len(x)>0 and len(y)>0  ):
                        strrest = strrest + f"{rest[i][0]},{rest[i][1]},{x[0]:.2f},{y[0]:.2f},{rest[i][4]:.2f},"
                        int_bytes = struct.pack("h",rest[i][1]) # 将整数打包为2字节的大端格式
                        self.plc_client.write_area(Areas.MK,0,4,int_bytes)
                        print(f"写入{rest[i][1]}")
                        break
        if strrest!="":
            # Log TCP payload before sending
            print(f"[TCP SEND] {strrest}")
            self.tcp_worker.send_response(strrest)
        else:
            # Log default payload before sending
            print("[TCP SEND] 0,0,0,0,0")
            self.tcp_worker.send_response("0,0,0,0,0")

    def ensure_param_directory(self):
        """确保param文件夹存在"""
        param_dir = "param"
        if not os.path.exists(param_dir):
            os.makedirs(param_dir)
            print(f"Created missing directory: {param_dir}")
    def closeEvent(self, event):
        self.ensure_param_directory()
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
                # Update UI-controlled parameters
                self.runData.colorName1=self.leColorName1.text()
                self.runData.colorName2=self.leColorName2.text()
                self.runData.colorName3=self.leColorName3.text()
                self.runData.colorMin1=self.spColorMin1.value()
                self.runData.colorMax1=self.spColorMax1.value()
                self.runData.colorMin2=self.spColorMin2.value()
                self.runData.colorMax2=self.spColorMax2.value()
                self.runData.colorMin3=self.spColorMin3.value()
                self.runData.colorMax3=self.spColorMax3.value()
                # Note: roiOffsetRowScale/ColScale/AngleOffset should be manually edited in JSON
                # They are preserved from file and not overwritten here
                self.runData.save("param/run_data_backup.json")
                event.accept()  # Proceed with closing
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save data: {str(e)}")
                event.ignore()  # Cancel closing
        else:
            event.ignore()  # Cancel closing
                    
    # def filter_close_points(self,list_of_lists, distance_threshold):
    #     """
    #     过滤掉坐标距离过近的子列表。
        
    #     :param list_of_lists: 列表，每个元素是一个子列表，格式为 [0, 0, row, col, angl]
    #     :param distance_threshold: 距离阈值，两点距离小于此值则视为过近
    #     :return: 过滤后的列表，剔除了距离过近的点
    #     """
    #     filtered_lists = []  # 保存过滤后的完整子列表
    #     filtered_coords = []  # 保存已保留点的坐标，用于快速距离计算
        
    #     for lst in list_of_lists:
    #         # 提取当前点的坐标 (row, col)
    #         current_coord = [lst[2], lst[3]]
            
    #         # 检查当前点是否与任何已保留点距离过近
    #         too_close = False
    #         for kept_coord in filtered_coords:
    #             # 计算欧几里得距离
    #             dist = np.linalg.norm(np.array(current_coord) - np.array(kept_coord))
    #             if dist < distance_threshold:
    #                 too_close = True
    #                 break  # 只要与一个已保留点过近就跳出循环
            
    #         # 如果不过近，则保留该点及其坐标
    #         if not too_close:
    #             filtered_lists.append(lst)
    #             filtered_coords.append(current_coord)
        
    #     return filtered_lists

   
    def remove_close_points_both(self, points, threshold):
        """
        剔除距离过近的点（将两个点都剔除）。

        :param points: 包含 [0, 0, row, col, angle] 的列表
        :param threshold: 距离阈值，如果两点之间的距离小于此值，则两个点都被剔除
        :return: 剔除后的点列表
        """
        def euclidean_distance(p1, p2):
            # 计算两点之间的欧几里得距离（基于 row 和 col）
            return ((p1[2] - p2[2]) ** 2 + (p1[3] - p2[3]) ** 2) ** 0.5

        # 标记需要剔除的点索引
        to_remove = set()

        # 遍历所有点对
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                if euclidean_distance(points[i], points[j]) < threshold and euclidean_distance(points[i], points[j])>60:
                    # 如果两点距离小于阈值，标记这两个点
                    to_remove.add(i)
                    to_remove.add(j)

        # 生成剔除后的点列表
        filtered_points = [point for idx, point in enumerate(points) if idx not in to_remove]

        return filtered_points

    
    def get_color(self,region ,image,row,col):
        mean, _ = ha.intensity(region,image)
        val = float(mean[0]) if (hasattr(mean, '__len__') and len(mean) > 0) else 0.0
        if(val >= self.spColorMin1.value() and val <= self.spColorMax1.value()):
            self.haWindow.disp_text(f"{self.leColorName1.text()},{mean[0]:.2f}","image", row+20,col,"black",[],[])
            #int_bytes = struct.pack('!h', 1)  # 将整数打包为2字节的大端格式
            #self.plc_client.write_area(Areas.MK, 0, 4, int_bytes)
            #print("写入1")
            return 1 # 红色
        elif(val >= self.spColorMin2.value() and val <= self.spColorMax2.value()):
            self.haWindow.disp_text(f"{self.leColorName2.text()},{val:.2f}","image", row+20,col,"black",[],[])
            #int_bytes = struct.pack('!h', 2)  # 将整数打包为2字节的大端格式
            #self.plc_client.write_area(Areas.MK, 0, 4, int_bytes)
            #print("写入2")
            return 2 # 绿色
        else:
            self.haWindow.disp_text(f"{self.leColorName3.text()},{val:.2f}","image", row+20,col,"black",[],[])
            #int_bytes = struct.pack('!h', 3)  # 将整数打包为2字节的大端格式
            #self.plc_client.write_area(Areas.MK, 0, 4, int_bytes)
            #print("写入3")
            return 3 # 蓝色
    def on_Read_clicked(self):
        # 打开文件对话框，选择图像文件
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.bmp);;All Files (*)")
        if file_path:
            # 使用 HalconView 显示图像
            self.haWindow.clear()
            self.haWindow.load_image(file_path)
            #self.process()
                

    
    def on_roi_changed(self, draw, event):
        self.haWindow.clearRegions()
        # 处理创建模型的逻辑
        regions = self.haWindow.get_rois_regions()
        for region in regions:
            self.haWindow.disp_obj(region, "green","margin")
        if len(regions) > 0:
            try:
                roiParam=self.haWindow.get_rois_params()  
                # save template ROI size for defect inspection
                try:
                    self.runData.battLen1 = roiParam[0].get('length1', self.runData.battLen1)
                    self.runData.battLen2 = roiParam[0].get('length2', self.runData.battLen2)
                except Exception:
                    pass
                region =ha.gen_rectangle2(roiParam[0]['row'],roiParam[0]['column'],roiParam[0]['phi'],roiParam[0]['length1'],roiParam[0]['length2'])  
                _, rowCenter,colCenter=ha.area_center(region)         
                modelImage=ha.reduce_domain(self.haWindow.h_image,region)
                
                modelId = ha.create_shape_model(modelImage,"auto", 0, 7, "auto", "auto", 'use_polarity', "auto", "auto")
                contour = ha.get_shape_model_contours(modelId, 1 )
                if(self.shapeId==1):
                    self.runData.modelId=modelId
                elif(self.shapeId==2):
                    self.runData.modelId2=modelId
                elif(self.shapeId==3):
                    self.runData.modelId3=modelId
                elif(self.shapeId==4):
                    self.runData.modelId4=modelId
                elif(self.shapeId==5):
                    self.runData.modelId5=modelId

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
        self.shapeId=1
        self.haWindow.add_rectangle2(row=100, col=100, phi=0, length1=50, length2=50, color="red")    
    def on_createModel2_clicked(self):
        self.createFlg="shape"
        self.haWindow.clear()
        self.shapeId=2
        self.haWindow.add_rectangle2(row=100, col=100, phi=0, length1=50, length2=50, color="red")

    def on_createModel3_clicked(self):
        self.createFlg="shape"
        self.haWindow.clear()
        self.shapeId=3
        self.haWindow.add_rectangle2(row=100, col=100, phi=0, length1=50, length2=50, color="red")
    def on_createModel4_clicked(self):
        self.createFlg="shape"
        self.haWindow.clear()
        self.shapeId=4
        self.haWindow.add_rectangle2(row=100, col=100, phi=0, length1=50, length2=50, color="red")
    def on_createModel5_clicked(self):
        self.createFlg="shape"
        self.haWindow.clear()
        self.shapeId=5
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

    def on_sample_normal_clicked(self):
        """Sample a battery by drawing its bounding box and auto-calibrate normal threshold."""
        if self.haWindow.h_image is None:
            QMessageBox.warning(self, "Warning", "No image loaded.")
            return
        
        regions = self.haWindow.get_rois_regions()
        if len(regions) == 0:
            QMessageBox.warning(self, "Warning", "Please draw a ROI around the battery to sample.")
            return
        
        # Get image channels
        h = s = v = None
        if ha.count_channels(self.haWindow.h_image)[0] > 1:
            r, g, b = ha.decompose3(self.haWindow.h_image)
            h, s, v = ha.trans_from_rgb(r, g, b, "hsv")
        else:
            v = self.haWindow.h_image
        
        # Calculate center of bounding box
        region = regions[0]
        _, row_center, col_center = ha.area_center(region)
        row_center = float(row_center[0]) if (hasattr(row_center, '__len__') and len(row_center) > 0) else 0.0
        col_center = float(col_center[0]) if (hasattr(col_center, '__len__') and len(col_center) > 0) else 0.0
        
        # Use angle from last detection, or default to 0
        angle_rad = getattr(self, '_last_battery_angle', 0.0)
        
        # Call defect inspector to sample end caps (returns 1/2/3, we only care about the score calculation)
        # For now, manually calculate score like in inspect_battery_defect
        try:
            L1 = float(getattr(self.runData, 'battLen1', 200))
            L2 = float(getattr(self.runData, 'battLen2', 80))
            end_offset = L1 * float(getattr(self.runData, 'endOffsetRatio', 0.85))
            cap_l1 = max(8.0, L1 * float(getattr(self.runData, 'capLenRatio', 0.18)))
            cap_l2 = max(6.0, L2 * float(getattr(self.runData, 'capWidthRatio', 0.80)))
            
            row_scale = float(getattr(self.runData, 'roiOffsetRowScale', 1.0))
            col_scale = float(getattr(self.runData, 'roiOffsetColScale', 1.0))
            angle_offset = float(getattr(self.runData, 'roiAngleOffset', 0.0))
            angle_adjusted = angle_rad + angle_offset
            
            # Calculate end ROIs
            dr = end_offset * math.sin(angle_adjusted) * row_scale
            dc = end_offset * math.cos(angle_adjusted) * col_scale
            r1, c1 = row_center + dr, col_center + dc
            r2, c2 = row_center - dr, col_center - dc
            
            reg1 = ha.gen_rectangle2(r1, c1, angle_adjusted, cap_l1, cap_l2)
            reg2 = ha.gen_rectangle2(r2, c2, angle_adjusted, cap_l1, cap_l2)
            
            # Sample brightness
            if v is not None:
                mean1, _ = ha.intensity(reg1, v)
                mean2, _ = ha.intensity(reg2, v)
                
                v1 = float(mean1[0]) if (hasattr(mean1, '__len__') and len(mean1) > 0) else 0.0
                v2 = float(mean2[0]) if (hasattr(mean2, '__len__') and len(mean2) > 0) else 0.0
                
                # Use brighter end
                v_cap = max(v1, v2)
                score = float(v_cap)
                
                # Adjust with saturation
                if s is not None:
                    reg_cap = reg1 if v1 >= v2 else reg2
                    mean_s, _ = ha.intensity(reg_cap, s)
                    s_val = float(mean_s[0]) if (hasattr(mean_s, '__len__') and len(mean_s) > 0) else 0.0
                    score = score - 0.5 * s_val
                
                # Set threshold range (±15 around sample score)
                margin = 15
                min_val = max(0, int(score - margin))
                max_val = min(255, int(score + margin))
                
                self.spColorMin1.setValue(min_val)
                self.spColorMax1.setValue(max_val)
                self.runData.colorMin1 = min_val
                self.runData.colorMax1 = max_val
                
                QMessageBox.information(self, "Sample Normal Battery", 
                    f"Battery center: ({row_center:.0f}, {col_center:.0f})\n"
                    f"Angle: {angle_rad*180/math.pi:.1f}°\n"
                    f"Sampled end score: {score:.1f}\n"
                    f"Set threshold range: [{min_val}, {max_val}]")
                print(f"[Calibration] Normal: center=({row_center:.0f},{col_center:.0f}), angle={angle_rad:.3f}, score={score:.1f}, range=[{min_val}, {max_val}]")
        except Exception as e:
            print(f"Error sampling normal: {e}")
            QMessageBox.critical(self, "Error", f"Failed to sample: {str(e)}")
        
        self.haWindow.clearRegions()

    def on_sample_defect_clicked(self):
        """Sample a battery by drawing its bounding box and auto-calibrate defect threshold."""
        if self.haWindow.h_image is None:
            QMessageBox.warning(self, "Warning", "No image loaded.")
            return
        
        regions = self.haWindow.get_rois_regions()
        if len(regions) == 0:
            QMessageBox.warning(self, "Warning", "Please draw a ROI around the battery to sample.")
            return
        
        # Get image channels
        h = s = v = None
        if ha.count_channels(self.haWindow.h_image)[0] > 1:
            r, g, b = ha.decompose3(self.haWindow.h_image)
            h, s, v = ha.trans_from_rgb(r, g, b, "hsv")
        else:
            v = self.haWindow.h_image
        
        # Calculate center of bounding box
        region = regions[0]
        _, row_center, col_center = ha.area_center(region)
        row_center = float(row_center[0]) if (hasattr(row_center, '__len__') and len(row_center) > 0) else 0.0
        col_center = float(col_center[0]) if (hasattr(col_center, '__len__') and len(col_center) > 0) else 0.0
        
        # Use angle from last detection, or default to 0
        angle_rad = getattr(self, '_last_battery_angle', 0.0)
        
        # Call defect inspector to sample end caps
        try:
            L1 = float(getattr(self.runData, 'battLen1', 200))
            L2 = float(getattr(self.runData, 'battLen2', 80))
            end_offset = L1 * float(getattr(self.runData, 'endOffsetRatio', 0.85))
            cap_l1 = max(8.0, L1 * float(getattr(self.runData, 'capLenRatio', 0.18)))
            cap_l2 = max(6.0, L2 * float(getattr(self.runData, 'capWidthRatio', 0.80)))
            
            row_scale = float(getattr(self.runData, 'roiOffsetRowScale', 1.0))
            col_scale = float(getattr(self.runData, 'roiOffsetColScale', 1.0))
            angle_offset = float(getattr(self.runData, 'roiAngleOffset', 0.0))
            angle_adjusted = angle_rad + angle_offset
            
            # Calculate end ROIs
            dr = end_offset * math.sin(angle_adjusted) * row_scale
            dc = end_offset * math.cos(angle_adjusted) * col_scale
            r1, c1 = row_center + dr, col_center + dc
            r2, c2 = row_center - dr, col_center - dc
            
            reg1 = ha.gen_rectangle2(r1, c1, angle_adjusted, cap_l1, cap_l2)
            reg2 = ha.gen_rectangle2(r2, c2, angle_adjusted, cap_l1, cap_l2)
            
            # Sample brightness
            if v is not None:
                mean1, _ = ha.intensity(reg1, v)
                mean2, _ = ha.intensity(reg2, v)
                
                v1 = float(mean1[0]) if (hasattr(mean1, '__len__') and len(mean1) > 0) else 0.0
                v2 = float(mean2[0]) if (hasattr(mean2, '__len__') and len(mean2) > 0) else 0.0
                
                # Use brighter end
                v_cap = max(v1, v2)
                score = float(v_cap)
                
                # Adjust with saturation
                if s is not None:
                    reg_cap = reg1 if v1 >= v2 else reg2
                    mean_s, _ = ha.intensity(reg_cap, s)
                    s_val = float(mean_s[0]) if (hasattr(mean_s, '__len__') and len(mean_s) > 0) else 0.0
                    score = score - 0.5 * s_val
                
                # Set threshold range (±15 around sample score)
                margin = 15
                min_val = max(0, int(score - margin))
                max_val = min(255, int(score + margin))
                
                self.spColorMin2.setValue(min_val)
                self.spColorMax2.setValue(max_val)
                self.runData.colorMin2 = min_val
                self.runData.colorMax2 = max_val
                
                QMessageBox.information(self, "Sample Defect Battery", 
                    f"Battery center: ({row_center:.0f}, {col_center:.0f})\n"
                    f"Angle: {angle_rad*180/math.pi:.1f}°\n"
                    f"Sampled end score: {score:.1f}\n"
                    f"Set threshold range: [{min_val}, {max_val}]")
                print(f"[Calibration] Defect: center=({row_center:.0f},{col_center:.0f}), angle={angle_rad:.3f}, score={score:.1f}, range=[{min_val}, {max_val}]")
        except Exception as e:
            print(f"Error sampling defect: {e}")
            QMessageBox.critical(self, "Error", f"Failed to sample: {str(e)}")
        
        self.haWindow.clearRegions()

# Create application and run
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())