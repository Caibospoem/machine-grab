import json
import halcon as ha

class ModelData:
    def __init__(self):
        """Initialize the object with default values."""
        # 定位模型
        self.modelId = None 
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



    def to_dict(self):
        """Convert the object to a dictionary."""
        return {

            "baseRow": self.baseRow,
            "baseCol": self.baseCol,
            "rowPoints": self.rowPoints,
            "colPoints": self.colPoints,
            "robotx": self.robotx,
            "roboty": self.roboty,
            
            
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
        instance.matrix = ha.vector_to_hom_mat2d(instance.rowPoints,instance.colPoints,instance.roboty,instance.robotx)
        
        return instance

    def save(self, file_path):
        """Serialize the object to a JSON file."""
        with open(file_path, 'w') as file:
            json.dump(self.to_dict(), file)
        ha.write_metrology_model(self.lineId,"metrology_model.hdml")
        ha.write_shape_model(self.modelId,"shape_model.hmod")
        

    @staticmethod
    def load(file_path):
        if not ha.file_exists(file_path): return ModelData()
        """Deserialize the object from a JSON file."""
        with open(file_path, 'r') as file:
            modelData = ModelData.from_dict(json.load(file))
        modelData.lineId = ha.read_metrology_model("metrology_model.hdml")
        modelData.modelId = ha.read_shape_model("shape_model.hmod")
        return modelData