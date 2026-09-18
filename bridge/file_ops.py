# bridge/file_ops.py
# FileOpsMixin：题库文件的加载 / 保存 / Excel 导入。
#
# 与拆分前 ControllerBridge 中对应方法一一对应，Slot 名、参数、返回值、
# 异常处理逻辑完全一致。仅做以下必要调整：
#
#   1. sys.platform == "android" → is_android()
#
#   2. _resolve_read / _resolve_write / _refresh 通过 MRO 动态派发，
#      Mixin 之间不直接 import。

from PySide6.QtCore import Slot

from platform_utils import is_android
from .signals import BridgeSignals


class FileOpsMixin(BridgeSignals):
    """loadFromJson / loadFromExcel / saveToFile / saveCurrent"""

    # ==============================================================
    # 打开
    # ==============================================================
    @Slot(str, result=int)
    def loadFromJson(self, raw):
        source, resolved = self._resolve_read(raw)
        if source is None:
            self.errorOccurred.emit(
                "无法读取所选文件。\n\n"
                "请确认文件存在且为有效的 JSON 格式。"
            )
            return 0

        try:
            count = self._controller.load_from_json_file(source)
        except Exception as e:
            self.errorOccurred.emit("打开失败：{}".format(e))
            return 0

        if count > 0:
            self._controller.current_file_path = resolved
            self._controller.is_modified = False

        self._refresh()
        if count == 0:
            self.errorOccurred.emit("该文件不包含有效题目数据")
        else:
            self.infoMessage.emit("已打开题库，共 {} 道题".format(count))
        return count

    @Slot(str, result=int)
    def loadFromExcel(self, raw):
        if is_android():
            self.errorOccurred.emit("Android 端不支持 Excel 导入，请使用 JSON 格式的题库。")
            return 0

        source, _ = self._resolve_read(raw)
        if source is None:
            self.errorOccurred.emit("无法读取所选文件")
            return 0

        try:
            count = self._controller.load_from_excel_file(source)
        except Exception as e:
            self.errorOccurred.emit(
                "导入失败：{}\n\n"
                "Android 端通常不支持 Excel，请先在桌面端转为 JSON。".format(e)
            )
            return 0

        if count > 0:
            self._controller.current_file_path = None
            self._controller.is_modified = True

        self._refresh()
        if count == 0:
            self.errorOccurred.emit("Excel 文件中没有有效题目")
        else:
            self.infoMessage.emit("已从 Excel 导入 {} 道题，请记得保存".format(count))
        return count

    # ==============================================================
    # 保存
    # ==============================================================
    @Slot(str, result=bool)
    def saveToFile(self, raw):
        if not self._controller.has_questions():
            self.errorOccurred.emit("没有可保存的数据")
            return False

        with self._resolve_write(raw) as pair:
            target, resolved = pair
            if target is None:
                self.errorOccurred.emit("保存失败：无法写入所选位置")
                return False
            try:
                self._controller.save_to_file(target)
            except Exception as e:
                self.errorOccurred.emit("保存失败：{}".format(e))
                return False

        self._controller.current_file_path = resolved
        self._controller.is_modified = False
        self._refresh()
        self.infoMessage.emit("已保存")
        return True

    @Slot(result=bool)
    def saveCurrent(self):
        path = self._controller.current_file_path
        if not self._controller.has_questions() or not path:
            return False
        return self.saveToFile(path)
