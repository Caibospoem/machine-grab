# Import the base UI class from the provided module


from View.Ui_calib_ui import Ui_calibWindow
from PyQt5.QtWidgets import QWidget, QDialog,QFileDialog
import halcon as ha
import modelData as md
from PyQt5.QtGui import QStandardItemModel, QStandardItem
class CalibWindow(QDialog, Ui_calibWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)  # Initialize the UI components defined in the .ui file
        self.pbRead.clicked.connect(self.on_read_clicked)  # Connect the button click event to a custom method
        self.pbCreateShape.clicked.connect(self.on_createShape_clicked)
        self.halDisplay.roiChanged.connect(self.on_roi_changed)
        self.pbCreateCircle.clicked.connect(self.on_createCircle_clicked)
        self.pbFindAll.clicked.connect(self.on_findAll_clicked)
        self.pbWrite.clicked.connect(self.on_write_clicked)
        self.pbCalib.clicked.connect(self.on_calculate_clicked)

        self.createFlg="shape"

        self.robotModel=QStandardItemModel(0,5)
        self.robotModel.setHorizontalHeaderLabels(["ID","row","col","y","x"])
        
        for i in range(9):
            items = [QStandardItem(str(field)) for field in [i,0,0,0,0]]
            self.robotModel.appendRow(items)
        
        self.tvRobotData.setModel(self.robotModel)
        self.ImagePoints = []

    def closeEvent(self, event):
        self.modelData.save("model_data_backup.json")
    def on_write_clicked(self):
        self.robotModel.removeRows(0,self.robotModel.rowCount())
        id = 0
        for data in self.ImagePoints:
            items = [QStandardItem(f"{field:.2f}") for field in [id,data[0],data[1],0,0]]
            self.robotModel.appendRow(items)
            id = id+1
    def on_findAll_clicked(self):
        self.process()
    
    def process(self):
        if self.halDisplay.h_image is not None and self.modelData.lineId is not None and self.modelData.modelId is not None:
                row,col,angle,score = ha.find_shape_model(self.halDisplay.h_image, self.modelData.modelId, -0.39, 7, 0.5, 0, 0.5, "least_squares", 2, 0.9)
                if(len(row) == 0):
                    return
                tempPoints=[]
                for i in range(len(row)):
                    ha.align_metrology_model(self.modelData.lineId, row[i], col[i], angle[i])
                    ha.apply_metrology_model( self.halDisplay.h_image,self.modelData.lineId)
                    contour,_,_ = ha.get_metrology_object_measures(self.modelData.lineId, "all", "all")
                    self.halDisplay.disp_obj(contour,"blue")
                    result = ha.get_metrology_object_result_contour(self.modelData.lineId, "all", "all",1.5)
                    self.halDisplay.disp_obj(result,"green")  
                   
                    self.halDisplay.disp_text(f"row: {row[i]:.2f},col: {float(col[i]):.2f}","image", row[i],col[i]+20,"black",[],[])
                    tempPoints.append([row[i],col[i]])
        tempPoints.sort(key=lambda x: x[0])
        for i in range(3):
            rows=tempPoints[i*3:i*3+3]
            rows.sort(key=lambda x: x[1])
            for j in range(3):
                self.ImagePoints.append(rows[j])
    def on_read_clicked(self):
        # Implement your custom logic here
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.bmp);;All Files (*)")
        if file_path:
            # 使用 HalconView 显示图像
            self.halDisplay.clear()
            self.halDisplay.load_image(file_path)
    def on_createShape_clicked(self):
        self.createFlg="shape"
        self.halDisplay.clear()
        self.halDisplay.add_rectangle2(row=100, col=100, phi=0, length1=50, length2=50, color="red")
        
    def on_createCircle_clicked(self):
        self.createFlg="circle"
        self.halDisplay.clear()
        self.halDisplay.add_circle(row=100, col=100, radius=50, color="red")
    def on_write_clicked(self):
        self.robotModel.removeRows(0,self.robotModel.rowCount())
        id = 0
        for data in self.ImagePoints:
            items = [QStandardItem(f"{field:.2f}") for field in [id,data[0],data[1],0,0]]
            self.robotModel.appendRow(items)
            id = id+1
    def on_roi_changed(self, draw, event):
        self.halDisplay.clearRegions()
        # 处理创建模型的逻辑
        regions = self.halDisplay.get_rois_regions()
        for region in regions:
            self.halDisplay.disp_obj(region, "green", "margin")
        if(self.createFlg=="shape"):
            if len(regions) > 0:
                try: 
                    roiParam = self.halDisplay.get_rois_params()
                    region = ha.gen_rectangle2(roiParam[0]['row'], roiParam[0]['column'], roiParam[0]['phi'],
                                            roiParam[0]['length1'], roiParam[0]['length2'])
                    _, rowCenter, colCenter = ha.area_center(region)
                    modelImage = ha.reduce_domain(self.halDisplay.h_image, region)
                    self.modelData.modelId = ha.create_shape_model(modelImage, "auto", 0, 7, "auto", "auto", 'use_polarity',
                                                                "auto", "auto")
                    contour = ha.get_shape_model_contours(self.modelData.modelId, 1)

                    hom = ha.vector_angle_to_rigid(0, 0, 0, rowCenter, colCenter, 0)
                    self.modelData.baseRow = rowCenter
                    self.modelData.baseCol = colCenter
                    affineContour = ha.affine_trans_contour_xld(contour, hom)
                    # 显示最终的模型轮廓
                    self.halDisplay.disp_obj(affineContour, "red")

                except: pass
        elif(self.createFlg=="circle"):
            try:
                roiParam=self.halDisplay.get_rois_params()  
                self.modelData.lineId = ha.create_metrology_model()
                width,height =  ha.get_image_size(self.halDisplay.h_image)
                ha.set_metrology_model_image_size(self.modelData.lineId, width, height)

                ha.add_metrology_object_circle_measure(self.modelData.lineId,row=roiParam[0]['row'],column=roiParam[0]['column'], radius=roiParam[0]['radius'],measure_length_1=30,measure_length_2=2,measure_sigma=1,measure_threshold=30,gen_param_name=[],gen_param_value=[])

                contour,row,col = ha.get_metrology_object_measures(self.modelData.lineId, "all", "all")
                self.halDisplay.disp_obj(contour,"blue")
                ha.set_metrology_model_param(self.modelData.lineId,"reference_system",[self.modelData.baseRow[0],self.modelData.baseCol[0],0])
            except: pass
            
    def on_calculate_clicked(self):
       
        for i in range(self.robotModel.rowCount()):
            row = self.robotModel.item(i,1).text()
            col = self.robotModel.item(i,2).text()
            y=self.robotModel.item(i,3).text()
            x=self.robotModel.item(i,4).text()
            self.modelData.robotx .append(float(x))
            self.modelData.roboty.append(float(y))
            self.modelData.rowPoints.append(float(row))
            self.modelData.colPoints.append(float(col))
        self.modelData.matrix = ha.vector_to_hom_mat2d(self.modelData.rowPoints,self.modelData.colPoints,self.modelData.roboty,self.modelData.robotx)    


    def get_all_data_from_model(self):
        """从模型获取全部数据"""
        model = self.tvRobotData.model()  # 获取模型引用[1,4,5](@ref)
        row_count = model.rowCount()    # 获取行数[1,5](@ref)
        col_count = model.columnCount() # 获取列数[1,5](@ref)
        all_data = []

        for row in range(row_count):
            row_data = []
            for col in range(col_count):
                index = model.index(row, col) # 创建QModelIndex索引[1,4,5](@ref)
                cell_data = model.data(index) # 获取DisplayRole数据[1,4,5](@ref)
                # 或者显式指定角色：model.data(index, Qt.DisplayRole)
                row_data.append(cell_data)
            all_data.append(row_data)

        return all_data

          