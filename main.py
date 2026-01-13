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
         self.cameraHandle = ha.open_framegrabber("MVision", 1, 1, 0, 0, 0, 0, "progressive", 8, "default", -1, "false", "auto", "GEV:DA7209089 MV-CS050-60GC", 0, -1)
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
        self.haWindow.update()
        rest = self.process()
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
            print(strrest)
            self.tcp_worker.send_response(strrest)
        else:
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
                
                #self.modelData.save("model_data_backup.json")  # Replace with your desired path
                self.runData.colorName1=self.leColorName1.text()
                self.runData.colorName2=self.leColorName2.text()
                self.runData.colorName3=self.leColorName3.text()
                self.runData.colorMin1=self.spColorMin1.value()
                self.runData.colorMax1=self.spColorMax1.value()
                self.runData.colorMin2=self.spColorMin2.value()
                self.runData.colorMax2=self.spColorMax2.value()
                self.runData.colorMin3=self.spColorMin3.value()
                self.runData.colorMax3=self.spColorMax3.value()
                self.runData.save("param/run_data_backup.json")
                event.accept()  # Proceed with closing
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save data: {str(e)}")
                event.ignore()  # Cancel closing
        else:
            event.ignore()  # Cancel closing
    def process(self):
        if self.haWindow.h_image is not None and (
                self.runData.modelId is not None or self.runData.modelId2 is not None or self.runData.modelId3 is not None or
                self.runData.modelId4 is not None or self.runData.modelId5 is not None):
                tempPoints=[]
                h = s = v = None
                color=0
                if(ha.count_channels(self.haWindow.h_image)[0]>1):
                    r,g,b = ha.decompose3(self.haWindow.h_image)
                    h,s,v = ha.trans_from_rgb(r,g,b,"hsv")
                else:
                    # grayscale camera: treat as V channel
                    v = self.haWindow.h_image
                if self.runData.modelId!=None:
                    row,col,angle,score = ha.find_shape_model(self.haWindow.h_image, self.runData.modelId, -0.39, 7, 0.7, 0, 0.5, "least_squares", 2, 0.9)
                    for i in range(len(row)):
                        self.haWindow.disp_text(f"row: {row[i]:.2f},col: {float(col[i]):.2f},angle:{angle[i]/math.pi*180:.2f}","image", row[i],col[i]+20,"black",[],[])
                        if(v is not None):
                           color = self.inspect_battery_defect(row[i], col[i], angle[i], s, v)
                           
                        tempPoints.append([1,color,row[i],col[i],angle[i]/math.pi*180])
                if self.runData.modelId2!=None:
                    row,col,angle,score = ha.find_shape_model(self.haWindow.h_image, self.runData.modelId2, 0, 1.57, 0.7, 0, 0.5, "least_squares", 2, 0.9)
                    for i in range(len(row)):
                        self.haWindow.disp_text(f"row: {row[i]:.2f},col: {float(col[i]):.2f},angle:{angle[i]/math.pi*180:.2f}","image", row[i],col[i]+20,"black",[],[])
                        if(v is not None):
                           color = self.inspect_battery_defect(row[i], col[i], angle[i], s, v)
                        tempPoints.append([2,color,row[i],col[i],angle[i]/math.pi*180])
                if self.runData.modelId3!=None:
                    row,col,angle,score = ha.find_shape_model(self.haWindow.h_image, self.runData.modelId3, 0, 2.09, 0.9, 0, 0.5, "least_squares", 2, 0.9)
                    for i in range(len(row)):
                        self.haWindow.disp_text(f"row: {row[i]:.2f},col: {float(col[i]):.2f},angle:{angle[i]/math.pi*180:.2f}","image", row[i],col[i]+20,"black",[],[])
                        if(v is not None):
                           color = self.inspect_battery_defect(row[i], col[i], angle[i], s, v)
                        tempPoints.append([3,color,row[i],col[i],angle[i]/math.pi*180])
                if self.runData.modelId4!=None:
                    row,col,angle,score = ha.find_shape_model(self.haWindow.h_image, self.runData.modelId4, 0, 1.04, 0.7, 0, 0.5, "least_squares", 2, 0.9)
                    for i in range(len(row)):
                        self.haWindow.disp_text(f"row: {row[i]:.2f},col: {float(col[i]):.2f},angle:{angle[i]/math.pi*180:.2f}","image", row[i],col[i]+20,"black",[],[])
                        if(v is not None):
                           color = self.inspect_battery_defect(row[i], col[i], angle[i], s, v)
                        tempPoints.append([4,color,row[i],col[i],angle[i]/math.pi*180])
                if self.runData.modelId5!=None:
                    row,col,angle,score = ha.find_shape_model(self.haWindow.h_image, self.runData.modelId5, 0, 1.25, 0.7, 0, 0.5, "least_squares", 2, 0.9)
                    for i in range(len(row)):
                        self.haWindow.disp_text(f"row: {row[i]:.2f},col: {float(col[i]):.2f},angle:{angle[i]/math.pi*180:.2f}","image", row[i],col[i]+20,"black",[],[])
                        if(v is not None):
                           color = self.inspect_battery_defect(row[i], col[i], angle[i], s, v)
                        tempPoints.append([5,color,row[i],col[i],angle[i]/math.pi*180])
            
                return tempPoints
                    
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

    def inspect_battery_defect(self, row, col, angle_rad, s_img, v_img):
        """Detect battery end-cap defect (e.g. missing/abnormal cap).
        Returns: 1=OK, 2=Defect, 3=Unknown.
        The thresholds are reused from UI spin boxes:
          - [Min1, Max1] => OK
          - [Min2, Max2] => Defect
          - else => Unknown
        """
        # ---- ROI sizing (from template ROI when creating shape model) ----
        L1 = float(getattr(self.runData, 'battLen1', 200))
        L2 = float(getattr(self.runData, 'battLen2', 80))
        end_offset = L1 * float(getattr(self.runData, 'endOffsetRatio', 0.85))
        cap_l1 = max(8.0, L1 * float(getattr(self.runData, 'capLenRatio', 0.18)))
        cap_l2 = max(6.0, L2 * float(getattr(self.runData, 'capWidthRatio', 0.80)))

        # ---- build 2 end ROIs (rectangle2) ----
        dr = end_offset * math.sin(angle_rad)
        dc = end_offset * math.cos(angle_rad)
        r1, c1 = row + dr, col + dc
        r2, c2 = row - dr, col - dc

        reg1 = ha.gen_rectangle2(r1, c1, angle_rad, cap_l1, cap_l2)
        reg2 = ha.gen_rectangle2(r2, c2, angle_rad, cap_l1, cap_l2)

        mean1, _ = ha.intensity(reg1, v_img)
        mean2, _ = ha.intensity(reg2, v_img)

        # choose the brighter end as "cap candidate"
        if mean1[0] >= mean2[0]:
            reg_cap = reg1
            v_cap = float(mean1[0])
        else:
            reg_cap = reg2
            v_cap = float(mean2[0])

        # optional: use Saturation to suppress highlights on non-metallic parts
        score = v_cap
        if s_img is not None:
            s_mean, _ = ha.intensity(reg_cap, s_img)
            score = v_cap - 0.5 * float(s_mean[0])

        # draw ROI for debugging
        try:
            self.haWindow.disp_obj(reg_cap, "yellow", "margin")
        except Exception:
            pass

        # ---- classify (reuse existing UI ranges) ----
        if(score > self.spColorMin2.value() and score < self.spColorMax2.value()):
            self.haWindow.disp_text(f"{self.leColorName2.text()},score:{score:.1f}", "image", row+20, col, "black", [], [])
            return 2  # Defect
        elif(score > self.spColorMin1.value() and score < self.spColorMax1.value()):
            self.haWindow.disp_text(f"{self.leColorName1.text()},score:{score:.1f}", "image", row+20, col, "black", [], [])
            return 1  # OK
        else:
            self.haWindow.disp_text(f"{self.leColorName3.text()},score:{score:.1f}", "image", row+20, col, "black", [], [])
            return 3  # Unknown

    def get_color(self,region ,image,row,col):
        mean, _ = ha.intensity(region,image)
        if(mean[0]>self.spColorMin1.value() and mean[0]<self.spColorMax1.value()):
            self.haWindow.disp_text(f"{self.leColorName1.text()},{mean[0]:.2f}","image", row+20,col,"black",[],[])
            #int_bytes = struct.pack('!h', 1)  # 将整数打包为2字节的大端格式
            #self.plc_client.write_area(Areas.MK, 0, 4, int_bytes)
            #print("写入1")
            return 1 # 红色
        elif(mean[0]>self.spColorMin2.value() and mean[0]<self.spColorMax2.value()):
            self.haWindow.disp_text(f"{self.leColorName2.text()},{mean[0]:.2f}","image", row+20,col,"black",[],[])
            #int_bytes = struct.pack('!h', 2)  # 将整数打包为2字节的大端格式
            #self.plc_client.write_area(Areas.MK, 0, 4, int_bytes)
            #print("写入2")
            return 2 # 绿色
        else:
            self.haWindow.disp_text(f"{self.leColorName3.text()},{mean[0]:.2f}","image", row+20,col,"black",[],[])
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

# Create application and run
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())