import json
import halcon as ha

class runData():
    def __init__(self):
        """Initialize the object with default values."""
        # 定位模型
        self.modelId = None 
        self.modelId2 = None
        self.modelId3 = None
        self.modelId4 = None
        self.modelId5 = None
        #找圆模型 
        self.lineId = None
        #转换矩阵
        self.matrix = None
        #行坐标点
        self.rowPoints = []
        #列坐标点
        self.colPoints = []
        self.robotx=[]
        self.roboty=[]

        self.baseRow = None
        self.baseCol = None

        self.colorName1="正常电池"
        self.colorName2="缺陷电池"
        self.colorName3="未知"
        self.colorMin1=0
        self.colorMax1=255
        self.colorMin2=0
        self.colorMax2=255
        self.colorMin3=0
        self.colorMax3=255


        # ===== Battery defect params (used for defect ROI sizing) =====
        self.battLen1 = 200  # template rectangle length1 (half of battery length) in pixels
        self.battLen2 = 80   # template rectangle length2 (half of battery width) in pixels
        self.endOffsetRatio = 0.85
        self.capLenRatio = 0.18
        self.capWidthRatio = 0.80
        # ROI position/angle adjustment (for fine-tuning defect detection)
        self.roiOffsetRowScale = 1.0  # scale factor for row offset (dr)
        self.roiOffsetColScale = 1.0  # scale factor for col offset (dc)
        self.roiAngleOffset = 0.0     # additional angle offset (radians) for ROI rotation
    def to_dict(self):
        """Convert the object to a dictionary."""
        return {

            "baseRow": self.baseRow,
            "baseCol": self.baseCol,
            "rowPoints": self.rowPoints,
            "colPoints": self.colPoints,
            "robotx": self.robotx,
            "roboty": self.roboty,
            "colorName1": self.colorName1,
            "colorName2": self.colorName2,  
            "colorName3": self.colorName3,
            "colorMin1": self.colorMin1,
            "colorMax1": self.colorMax1,
            "colorMin2": self.colorMin2,
            "colorMax2": self.colorMax2,
            "colorMin3": self.colorMin3,
            "colorMax3": self.colorMax3,
            "battLen1": self.battLen1,
            "battLen2": self.battLen2,
            "endOffsetRatio": self.endOffsetRatio,
            "capLenRatio": self.capLenRatio,
            "capWidthRatio": self.capWidthRatio,
            "roiOffsetRowScale": self.roiOffsetRowScale,
            "roiOffsetColScale": self.roiOffsetColScale,
            "roiAngleOffset": self.roiAngleOffset,
        }

    @classmethod
    def from_dict(cls, data):
        """Create an instance from a dictionary."""
        instance = cls()
        
        instance.baseRow = data.get("baseRow")
        instance.baseCol = data.get("baseCol")
        instance.rowPoints = data.get("rowPoints", [])
        instance.colPoints = data.get("colPoints", [])
        instance.robotx = data.get("robotx", [])
        instance.roboty = data.get("roboty", [])
        if(instance.rowPoints and len(instance.rowPoints)==9 and len(instance.colPoints)==9 and len(instance.robotx)==9 and len(instance.roboty)==9):
            instance.matrix = ha.vector_to_hom_mat2d(instance.rowPoints,instance.colPoints,instance.roboty,instance.robotx)
        instance.colorName1 = data.get("colorName1", instance.colorName1)
        instance.colorName2 = data.get("colorName2", instance.colorName2)
        instance.colorName3 = data.get("colorName3", instance.colorName3)
        instance.colorMin1 = data.get("colorMin1", instance.colorMin1)
        instance.colorMax1 = data.get("colorMax1", instance.colorMax1)
        instance.colorMin2 = data.get("colorMin2", instance.colorMin2)
        instance.colorMax2 = data.get("colorMax2", instance.colorMax2)
        instance.colorMin3 = data.get("colorMin3", instance.colorMin3)
        instance.colorMax3 = data.get("colorMax3", instance.colorMax3)
        instance.battLen1 = data.get("battLen1", instance.battLen1)
        instance.battLen2 = data.get("battLen2", instance.battLen2)
        instance.endOffsetRatio = data.get("endOffsetRatio", instance.endOffsetRatio)
        instance.capLenRatio = data.get("capLenRatio", instance.capLenRatio)
        instance.capWidthRatio = data.get("capWidthRatio", instance.capWidthRatio)
        instance.roiOffsetRowScale = data.get("roiOffsetRowScale", instance.roiOffsetRowScale)
        instance.roiOffsetColScale = data.get("roiOffsetColScale", instance.roiOffsetColScale)
        instance.roiAngleOffset = data.get("roiAngleOffset", instance.roiAngleOffset)
        return instance

    def save(self, file_path):
        """Serialize the object to a JSON file."""
        with open(file_path, 'w') as file:
            json.dump(self.to_dict(), file)
        if(self.lineId!=None):
            ha.write_metrology_model(self.lineId,"run_metrology_model.hdml")
        if(self.modelId!=None):
            ha.write_shape_model(self.modelId,"run_shape_model.hmod")
        if(self.modelId2!=None):
            ha.write_shape_model(self.modelId2,"run_shape_model2.hmod")
        if(self.modelId3!=None):
            ha.write_shape_model(self.modelId3,"run_shape_model3.hmod")
        if(self.modelId4!=None):
            ha.write_shape_model(self.modelId4,"run_shape_model4.hmod")
        if(self.modelId5!=None):
            ha.write_shape_model(self.modelId5,"run_shape_model5.hmod")

    @staticmethod
    def load(file_path):
        if not ha.file_exists(file_path): 
            instance = runData()
            # Save defaults on first creation
            instance.save(file_path)
            return instance
        """Deserialize the object from a JSON file."""
        with open(file_path, 'r') as file:
            modelData = runData.from_dict(json.load(file))

        if(ha.file_exists("run_metrology_model.hdml") ):
            modelData.lineId = ha.read_metrology_model("run_metrology_model.hdml")
        if( ha.file_exists("run_shape_model.hmod")):
            modelData.modelId = ha.read_shape_model("run_shape_model.hmod")
        if( ha.file_exists("run_shape_model2.hmod")):
            modelData.modelId2 = ha.read_shape_model("run_shape_model2.hmod")
        if( ha.file_exists("run_shape_model3.hmod")):
            modelData.modelId3 = ha.read_shape_model("run_shape_model3.hmod")
        if(ha.file_exists("run_shape_model4.hmod")):
            modelData.modelId4=ha.read_shape_model("run_shape_model4.hmod")
        if(ha.file_exists("run_shape_model5.hmod")):
            modelData.modelId5=ha.read_shape_model("run_shape_model5.hmod")
        return modelData