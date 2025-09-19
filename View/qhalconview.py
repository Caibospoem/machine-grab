
import sys
from PyQt5 import QtWidgets, QtCore
from ctypes import CFUNCTYPE, c_long, c_char_p
import halcon as ha
import ctypes

# 1. 定义C回调函数的类型签名 (根据Halcon文档调整参数和返回类型)
# 假设Halcon期望的回调函数接受long(绘图对象句柄), long(窗口句柄), char*(事件类型)参数，返回int。
C_DRAW_CALLBACK = CFUNCTYPE(c_long, c_long, c_long, c_char_p)
# 全局映射：window_handle → QHalconView 实例
_halcon_window_map = {}
class QHalconView(QtWidgets.QWidget):
    # ROI 变化信号：event='attach'|'on_drag'|'on_resize'|'on_select'|'detach' 等
    roiChanged = QtCore.pyqtSignal(object, str)


    def __init__(self, parent=None):
        super().__init__(parent)
        # 确保有原生窗口句柄以供 HALCON 嵌入
        self.setAttribute(QtCore.Qt.WA_NativeWindow)
        self.setMouseTracking(True)
        self.setMinimumSize(685, 581)
        
        # HALCON 句柄与状态
        self.h_window = None
        self.h_image = None
        self.img_w = 0
        self.img_h = 0

        # 当前显示的图像“视口”（set_part）
        # row1, col1, row2, col2，表示图像坐标中的可视区域
        self.part = [0, 0, 0, 0]

        # 交互状态（平移）
        self._panning = False
        self._pan_last = QtCore.QPoint()

        # 绘图对象管理
        self._draw_objects = []  # list of drawing object handles

        # 定时刷新（可保持绘图对象的显示稳定）
        # self._timer = QtCore.QTimer(self)
        # self._timer.timeout.connect(self._refresh)
        # self._timer.start(33)  # ~30 FPS
        self._c_callback = C_DRAW_CALLBACK(self.halcon_window_callback) 
        self.current_draw = None

        

    # ---------- 公共 API ----------
    def halcon_window_callback(self,draw_id, window_handle, event_type):
        self.roiChanged.emit(None, "")
        return 0 
    def load_image(self, path: str):
        """读取并显示图像（路径或 HALCON 支持的句柄名）"""
        self._ensure_window()
        self.h_image = ha.read_image(path)

        w, h = ha.get_image_size(self.h_image)
        self.img_w, self.img_h = int(w[0]), int(h[0])
        self._fit_part()
        self._disp()
    def disp_obj(self, region, color="green", mode="fill"):
        """显示一个 Halcon Region"""
        self._ensure_window()
        if not self.h_image or self.h_window is None:
            return
        ha.set_color(self.h_window, color)
        ha.set_draw(self.h_window, mode)
        ha.disp_obj(region, self.h_window)
    def disp_text(self, text, mode="window", row=12, col=12, color="green", box=[], font=[]):
        """在窗口或图像上显示文字"""
        self._ensure_window()
        if not self.h_image or self.h_window is None:
            return
        ha.set_color(self.h_window, color)
        ha.set_draw(self.h_window, "fill")
        if mode == "window":
            ha.disp_text(self.h_window, text, "window", row, col, color, box, font)
        else:
            ha.disp_text(self.h_window, text, "image", row, col, color, box, font)
    def set_image(self, h_image):
        """直接设置 HALCON 图像对象并显示"""
        self._ensure_window()
        self.h_image = h_image
        w, h = ha.get_image_size(self.h_image)
        self.img_w, self.img_h = int(w), int(h)
        self._fit_part()
        self._disp()

    def clear(self):
        """清除图像与所有绘图对象"""
        self._detach_all_rois()
        self.img_w = self.img_h = 0
        self._disp(clear=True)
    def clearRegions(self):
        """清除所有显示的 Region"""
        if self.h_window:
            ha.clear_window(self.h_window)
            if self.h_image:
                ha.disp_image(self.h_image, self.h_window)

    def fit_to_window(self):
        """自适应到控件显示区域"""
        if self.h_image:
            self._fit_part()
            self._disp()

    def zoom(self, factor: float, center_widget_pos: QtCore.QPoint = None):
        """围绕控件坐标点缩放显示"""
        if not self.h_image or factor <= 0:
            return
        if center_widget_pos is None:
            center_widget_pos = QtCore.QPoint(self.width() // 2, self.height() // 2)

        # 1) 控件点 -> 图像坐标
        img_c, img_r = self._widget_to_image(center_widget_pos)
        if img_c is None:
            return

        # 2) 当前 part 尺寸
        r1, c1, r2, c2 = self.part
        cur_w = c2 - c1 + 1
        cur_h = r2 - r1 + 1

        # 3) 新尺寸
        new_w = max(8, int(cur_w / factor))
        new_h = max(8, int(cur_h / factor))

        # 4) 以 img_c/img_r 为中心设置新 part
        c1_new = int(img_c - new_w / 2)
        r1_new = int(img_r - new_h / 2)
        c2_new = c1_new + new_w - 1
        r2_new = r1_new + new_h - 1

        self._clamp_part(r1_new, c1_new, r2_new, c2_new)
        self._disp()

    def pan(self, dx: int, dy: int):
        """平移显示（单位：控件像素，会自动按比例换算为图像像素）"""
        if not self.h_image:
            return
        # 控件位移 -> 图像位移
        scale_x, scale_y = self._display_scale()
        move_c = int(dx * scale_x)
        move_r = int(dy * scale_y)

        r1, c1, r2, c2 = self.part
        self._clamp_part(r1 + move_r, c1 + move_c, r2 + move_r, c2 + move_c)
        self._disp()

    def add_rectangle(self, row1: float, col1: float, row2: float, col2: float, color="red"):
        """添加 axis-aligned 矩形 ROI"""
        self._ensure_window()
        draw = ha.create_drawing_object_rectangle1(row1, col1, row2, col2)
        self.current_draw = draw
        ha.set_drawing_object_params(draw, "color", color)
        self._attach_roi(draw)
        return draw

    def add_rectangle2(self, row: float=100, col: float=100, phi: float=0, length1: float=50, length2: float=50, color="red"):
        """添加旋转矩形 ROI（row/col/phi/半宽/半高）"""
        self._ensure_window()
        draw = ha.create_drawing_object_rectangle2(row, col, phi, length1, length2)
        ha.set_drawing_object_params(draw, "color", color)
        self._attach_roi(draw)
        return draw

    def add_circle(self, row: float=100, col: float=100, radius: float=50, color="orange"):
        """添加圆形 ROI"""
        self._ensure_window()
        draw = ha.create_drawing_object_circle(row, col, radius)
        ha.set_drawing_object_params(draw, "color", color)
        self._attach_roi(draw)
        return draw

    def remove_roi(self, draw):
        """移除一个 ROI"""
        if draw in self._draw_objects and self.h_window:
            try:
                ha.detach_drawing_object_from_window(self.h_window, draw)
            except Exception:
                pass
            self._draw_objects.remove(draw)
            self.roiChanged.emit(draw, "detach")

    def clear_rois(self):
        """移除所有 ROI"""
        self._detach_all_rois()

    def get_rois_params(self):
        """获取所有 ROI 的参数（以 dict 列表返回）"""
        result = []
        for d in list(self._draw_objects):
            result.append(self._read_drawing_params(d))
        return result

    def get_rois_regions(self):
        """将所有 ROI 转为 Region（可能较慢），返回 region 列表"""
        regions = []
        for d in list(self._draw_objects):
            try:
                regions.append(ha.get_drawing_object_iconic(d))
            except Exception:
                pass
        return regions

    # ---------- Qt 事件 ----------

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_window()
        self._apply_window_extents()
        self._disp()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_window_extents()
        self._disp()
        

    def wheelEvent(self, event):
        if not self.h_image:
            return
        delta = event.angleDelta().y()
        factor = 1.25 if delta > 0 else (1 / 1.25)
        self.zoom(factor, event.pos())

    def mousePressEvent(self, event):
        if event.button() in (QtCore.Qt.MiddleButton, QtCore.Qt.RightButton):
            self._panning = True
            self._pan_last = event.pos()

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_last
            self._pan_last = event.pos()
            # 注意：pan 的 dx,dy 要用控件坐标（像素）
            self.pan(-delta.x(), -delta.y())  # 方向取反：拖动视图 vs 拖动内容

    def mouseReleaseEvent(self, event):
        if event.button() in (QtCore.Qt.MiddleButton, QtCore.Qt.RightButton):
            self._panning = False

    def mouseDoubleClickEvent(self, event):
        if self.h_image:
            self.fit_to_window()

    def closeEvent(self, event):
        self._detach_all_rois()
        if self.h_window:
            try:
                ha.close_window(self.h_window)
            except Exception:
                pass
            self.h_window = None
        super().closeEvent(event)
        event.accept()

    # ---------- 内部实现 ----------

    def _ensure_window(self):
        if self.h_window is not None:
            return
        win_id = int(self.winId())
        w = max(1, self.width())-10
        h = max(1, self.height())+100
        self.h_window = ha.open_window(0, 0, w, h, win_id, "visible", "")
        
        # 更高质量的缩放可设 Interpolation（可选）
        ha.set_system("clip_region", "true")
        

    def _apply_window_extents(self):
        if not self.h_window:
            return
        w = max(1, self.geometry().width())
        h = max(1, self.geometry().height())
        # 更新窗口尺寸
        ha.set_window_extents(self.h_window, 0, 0, w, h)
        
        # 按当前 part 重设（避免拉伸）
        if self.h_image and all(v is not None for v in self.part):
            ha.set_part(self.h_window, *self.part)

    def _fit_part(self):
        """根据控件大小自适应设置 part"""
        if not self.h_image:
            return
        view_w = max(1, self.width())
        view_h = max(1, self.height())
        img_w, img_h = self.img_w, self.img_h

        # 以较短边匹配控件，保持比例
        img_aspect = img_w / img_h
        view_aspect = view_w / view_h

        if view_aspect > img_aspect:
            # 以高度为基准，左右留白 -> 扩展列范围
            target_h = img_h
            target_w = int(target_h * view_aspect)
        else:
            target_w = img_w
            target_h = int(target_w / view_aspect)

        # 居中扩展的 part（超出图像范围没关系，HALCON 会裁剪）
        c_center = img_w / 2.0
        r_center = img_h / 2.0
        c1 = int(round(c_center - target_w / 2))
        r1 = int(round(r_center - target_h / 2))
        c2 = c1 + target_w - 1
        r2 = r1 + target_h - 1

        self.part = [r1, c1, r2, c2]
        if self.h_window:
            ha.set_part(self.h_window, *self.part)

    def _clamp_part(self, r1, c1, r2, c2):
        """限制 part 范围并更新内部状态"""
        # 允许略超出图像以保持居中/平滑滚动，但不要过大
        margin = max(8, min(self.img_w, self.img_h) // 2) if (self.img_w and self.img_h) else 64
        r1 = max(-margin, r1)
        c1 = max(-margin, c1)
        r2 = min(self.img_h - 1 + margin, r2)
        c2 = min(self.img_w - 1 + margin, c2)

        # 防止反转/零尺寸
        if r2 <= r1:
            r2 = r1 + 1
        if c2 <= c1:
            c2 = c1 + 1

        self.part = [int(r1), int(c1), int(r2), int(c2)]
        if self.h_window:
            ha.set_part(self.h_window, *self.part)

    def _disp(self, clear=False):
        if not self.h_window:
            return
        if clear or not self.h_image:
            # 清空：用一个空的灰底显示（可选）
            return
        # 设置 part 并显示
        ha.set_part(self.h_window, *self.part)
        ha.disp_image( self.h_image,self.h_window)

    def _refresh(self):
        # 周期性重绘，保持 DrawingObject 的显示与窗口一致
        if self.h_window and self.h_image:
            self._disp()

    def _attach_roi(self, draw):
        if not self.h_window:
            self._ensure_window()
        ha.attach_drawing_object_to_window(self.h_window, draw)
        # 注册常见回调
        try:
            callback_addr = ctypes.cast(self._c_callback, ctypes.c_void_p).value
            ha.set_drawing_object_callback(draw, "on_drag", callback_addr)
            ha.set_drawing_object_callback(draw, "on_resize", callback_addr)
            ha.set_drawing_object_callback(draw, "on_select", callback_addr)
            ha.set_drawing_object_callback(draw, "detach", callback_addr)
            ha.set_drawing_object_callback(draw, "attach", callback_addr)
        except Exception:
            # 某些版本下回调设置可能不完全支持
            pass
        self._draw_objects.append(draw)
        self.roiChanged.emit(draw, "attach")

    @staticmethod
    def _on_draw_event(draw_id, window_handle, event_type):
        # 由于是静态函数，无法直接访问 self；通过 window_handle 找不到实例的话，
        # 这里只做最小打印示例。实际项目可改为全局注册映射或者只用信号侧更新。
        print(f"Drawing event: {event_type}")
        # 查找对应实例
        instance = _halcon_window_map.get(int(window_handle))
        if instance:
            instance.roiChanged.emit(draw_id, event_type)
        return 0

    def _detach_all_rois(self):
        if not self.h_window:
            self._draw_objects.clear()
            return
        for d in list(self._draw_objects):
            try:
                ha.detach_drawing_object_from_window(self.h_window, d)
            except Exception:
                pass
            self.roiChanged.emit(d, "detach")
        self._draw_objects.clear()

    def _display_scale(self):
        """返回图像像素/控件像素的缩放：scale_x, scale_y"""
        # 控件像素 -> 图像像素 的比例
        view_w = max(1, self.width())
        view_h = max(1, self.height())
        r1, c1, r2, c2 = self.part
        img_w_in_view = (c2 - c1 + 1)
        img_h_in_view = (r2 - r1 + 1)
        scale_x = img_w_in_view / view_w
        scale_y = img_h_in_view / view_h
        return scale_x, scale_y

    def _widget_to_image(self, pos: QtCore.QPoint):
        """控件坐标 -> 图像坐标（列, 行）"""
        if not self.h_image:
            return (None, None)
        r1, c1, r2, c2 = self.part
        scale_x, scale_y = self._display_scale()
        c = c1 + pos.x() * scale_x
        r = r1 + pos.y() * scale_y
        return (c, r)

    def _read_drawing_params(self, draw):
        """将 DrawingObject 的关键参数读成 dict（兼容常见类型）"""
        try:
            typ = ha.get_drawing_object_params(draw, "type")
        except Exception:
            typ = "unknown"
        info = {"type": typ[0]}
        def getp(name, cast=float):
            try:
                v = ha.get_drawing_object_params(draw, name)
                return cast(v[0])
            except Exception:
                return None
        if info["type"] == "rectangle1":
            info.update({
                "row1": getp("row1"), "column1": getp("column1"),
                "row2": getp("row2"), "column2": getp("column2")
            })
        elif info["type"] == "rectangle2":
            info.update({
                "row": getp("row"), "column": getp("column"),
                "phi": getp("phi"), "length1": getp("length1"), "length2": getp("length2")
            })
        elif info["type"] == "circle":
            info.update({
                "row": getp("row"), "column": getp("column"), "radius": getp("radius")
            })
        else:
            # 其他类型按需扩展
            pass
        return info