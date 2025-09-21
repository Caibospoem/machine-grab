import json
import halcon as ha

class runData():
    def __init__(self):
        """Initialize the object with default values."""
        # 定位模型
        self.modelId = None 
        self.modelId2 = None
        self.modelId3 = None
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

        self.colorName1="红色"
        self.colorName2="绿色"
        self.colorName3="蓝色"
        self.colorMin1=0
        self.colorMax1=255
        self.colorMin2=0
        self.colorMax2=255
        self.colorMin3=0
        self.colorMax3=255

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
        }

    @classmethod
    def from_dict(cls, data):
        """Create an instance from a dictionary."""
        instance = cls()
        
        instance.baseRow = data.get("baseRow")
        instance.baseCol = data.get("baseCol")
        instance.rowPoints = data.get("rowPoints")
        instance.colPoints = data.get("colPoints")
        instance.robotx = data.get("robotx")
        instance.roboty = data.get("roboty")
        if(len(instance.rowPoints)==9 and len(instance.colPoints)==9 and len(instance.robotx)==9 and len(instance.roboty)==9):
            instance.matrix = ha.vector_to_hom_mat2d(instance.rowPoints,instance.colPoints,instance.roboty,instance.robotx)
        instance.colorName1 = data.get("colorName1")
        instance.colorName2 = data.get("colorName2")
        instance.colorName3 = data.get("colorName3")
        instance.colorMin1 = data.get("colorMin1")
        instance.colorMax1 = data.get("colorMax1")
        instance.colorMin2 = data.get("colorMin2")
        instance.colorMax2 = data.get("colorMax2")
        instance.colorMin3 = data.get("colorMin3")
        instance.colorMax3 = data.get("colorMax3")
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
        

    @staticmethod
    def load(file_path):
        if not ha.file_exists(file_path): return runData()
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
        return modelData